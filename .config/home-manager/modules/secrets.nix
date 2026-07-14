# Secrets tooling: Bitwarden vault -> sops+age(YubiKey) encrypted local file
# -> BWS access token -> application secrets via `bws run`.
# See AGENTS.md "Secrets architecture" for the full two-layer design.
#
# Everything the workflow needs lives in this module: the packages the
# scripts call (declared below so the scripts can never be deployed without
# their dependencies), the scripts themselves, the sourcing alias, and the
# age identity environment variable. Runtime-only requirements that nix
# cannot guarantee (the deployed sops config, the age-plugin-yubikey wrapper
# from wsl.nix, the identity file) are preflight-checked inside the scripts
# with actionable errors.
#
# NOTE: `bws` is unfree — home.nix must keep "bws" in allowUnfreePredicate.
# The sops creation rules themselves (.config/sops/.sops.yaml) are deployed
# by ./dotfiles.nix like every other tracked config file.
{ config, pkgs, ... }:
let
  # Name of the Bitwarden *vault* item (personal vault, not Secrets Manager)
  # that bw_sync_encrypted_secrets.sh fetches. It must be a Secure Note whose
  # Notes field contains the YAML documented in README.md ("local-machine-
  # bws-secrets Secure Note" section), including the BWS access token.
  #
  # This name must match the item in the vault exactly — if you rename the
  # item in Bitwarden, change it here and re-run 'hms', or the sync script
  # will fail at `bw get item` and the encrypted token file can no longer
  # be recreated.
  bitwardenVaultItem = "local-machine-bws-secrets";
in
{
  # Guard against the wrong yq: nixpkgs has both `yq` (a python wrapper
  # around jq with different syntax) and `yq-go` (the native Go
  # implementation these scripts are written against). Both install
  # `bin/yq`, so having both would fail the build with a cryptic buildEnv
  # collision — and `yq` alone would break sops-load-yubikey-recipient at
  # runtime. Fail the switch during evaluation with a clear message instead.
  assertions = [
    {
      assertion = !(builtins.any (p: pkgs.lib.getName p == "yq") config.home.packages);
      message = "home.packages contains 'yq' (python jq wrapper); the secrets scripts require 'yq-go'. Remove 'yq'.";
    }
  ];

  home.packages = with pkgs; [
    bitwarden-cli # `bw` — vault access in bw_sync_encrypted_secrets.sh
    bws # Bitwarden Secrets Manager CLI, authenticated via BWS_ACCESS_TOKEN
    jq # JSON parsing in the scripts below (also a general-purpose tool)
    sops # encrypt/decrypt the local secrets file
    yq-go # YAML editing in sops-load-yubikey-recipient
    # `yq` is a wrapper around `jq`
    # `yq-go` is a native yaml version
  ];

  # Age identity file for sops decryption via YubiKey.
  # Output of `age-plugin-yubikey --identity --slot 1` (see README YubiKey setup).
  home.sessionVariables = {
    SOPS_AGE_KEY_FILE = "${config.home.homeDirectory}/.config/age/yubikey-identity.txt";
  };

  programs.bash.shellAliases = {
    # Must be sourced so the exported token reaches the calling shell.
    bws-load-local-machine-credential = "source $HOME/.local/bin/_bws-load-local-machine-credential";
  };

  home.file = {
    # Loads the age recipient from YubiKey slot 1 into the repo's
    # .config/sops/.sops.yaml. The live clone is resolved with
    # dotfiles-root (deployed by home.nix) so this runs from any
    # directory and the clone location is never hardcoded; afterwards
    # run 'hms' to deploy the updated file to ~/.config/sops/.sops.yaml.
    ".local/bin/sops-load-yubikey-recipient" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        # dotfiles-root prints its own actionable error if the
        # ~/.config/home-manager symlink is missing or broken.
        REPO_ROOT=$(dotfiles-root)

        SOPS_FILE="$REPO_ROOT/.config/sops/.sops.yaml"
        if [[ ! -f "$SOPS_FILE" ]]; then
          echo "Error: $SOPS_FILE not found — is $REPO_ROOT the dotfiles repo?" >&2
          exit 1
        fi

        # Read the recipient for slot 1 straight from the connected YubiKey.
        # --identity respects --slot (plain --list does not filter by slot).
        # This reads public metadata only — no PIN or touch required.
        RECIPIENT=$(age-plugin-yubikey --identity --slot 1 | grep -oE 'age1yubikey1[a-z0-9]+' | head -1)
        if [[ -z "$RECIPIENT" ]]; then
          echo "Error: could not read an age recipient from YubiKey slot 1." >&2
          echo "  Is the YubiKey plugged into the (Windows host) system?" >&2
          exit 1
        fi

        CURRENT=$(yq '.creation_rules[0].age' "$SOPS_FILE")
        if [[ "$CURRENT" == "$RECIPIENT" ]]; then
          echo "Recipient already up to date in $SOPS_FILE"
          exit 0
        fi

        yq -i ".creation_rules[0].age = \"$RECIPIENT\"" "$SOPS_FILE"
        echo "Updated $SOPS_FILE"
        echo "  old: $CURRENT"
        echo "  new: $RECIPIENT"
        echo "Run 'hms' to deploy it to ~/.config/sops/.sops.yaml"
      '';
    };

    # Must be *sourced* (not executed) so that `export BWS_ACCESS_TOKEN`
    # reaches the calling shell.  The underscore prefix signals this.
    # No `set -euo pipefail` — it would leak into the calling shell (AGENTS.md).
    ".local/bin/_bws-load-local-machine-credential" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash

        # Refuse to run as a subprocess — exports would be lost on exit.
        if [[ "''${BASH_SOURCE[0]}" == "''${0}" ]]; then
          echo "Error: this script must be sourced, not executed." >&2
          echo "  Run:  bws-load-local-machine-credential" >&2
          exit 1
        fi

        SECRETS_FILE="$HOME/.local/secrets/bitwarden.yaml"

        # Preflight: decryption needs the age plugin and the YubiKey identity
        # file — check them up front so failures are actionable instead of a
        # raw sops error.
        if ! command -v age-plugin-yubikey >/dev/null 2>&1; then
          echo "Error: age-plugin-yubikey not found on PATH." >&2
          echo "  On WSL it is deployed by modules/wsl.nix — run 'hms'." >&2
          return 1
        fi
        if [[ ! -f "''${SOPS_AGE_KEY_FILE:-}" ]]; then
          echo "Error: age identity file not found at ''${SOPS_AGE_KEY_FILE:-<SOPS_AGE_KEY_FILE unset>}" >&2
          echo "  Generate it:  age-plugin-yubikey --identity --slot 1 > ~/.config/age/yubikey-identity.txt" >&2
          return 1
        fi
        if [[ ! -f "$SECRETS_FILE" ]]; then
          echo "Error: secrets file not found at $SECRETS_FILE" >&2
          echo "  Run bw_sync_encrypted_secrets.sh to create it." >&2
          return 1
        fi

        BWS_ACCESS_TOKEN=$(
          sops --decrypt --extract '["local_computer_machine_account_bws_access_token"]' \
            "$SECRETS_FILE"
        ) || { echo "Error: failed to decrypt $SECRETS_FILE" >&2; return 1; }
        [[ -n "$BWS_ACCESS_TOKEN" ]] || { echo "Error: decrypted token is empty" >&2; return 1; }
        export BWS_ACCESS_TOKEN

        echo "BWS_ACCESS_TOKEN set for this shell session only."
      '';
    };

    # Lists all secrets available in the BWS project (requires BWS_ACCESS_TOKEN).
    ".local/bin/bws-check-available-secrets" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        if [[ -z "''${BWS_ACCESS_TOKEN:-}" ]]; then
          echo "Error: BWS_ACCESS_TOKEN is not set." >&2
          echo "  Run:  bws-load-local-machine-credential" >&2
          exit 1
        fi

        echo "             Secret UUID             | Key"

        bws secret list --output json | jq -r '.[] | "\(.id) | \(.key)"'
      '';
    };

    # Sync secrets from Bitwarden and re-encrypt locally with YubiKey.
    # Run on first setup or after rotating tokens.
    ".local/bin/bw_sync_encrypted_secrets.sh" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        # Ensure the secrets file (and the tmpfiles below) are never created
        # world/group readable.
        umask 077

        SECRETS_FILE="$HOME/.local/secrets/bitwarden.yaml"

        # Preflight: sops only searches upward from cwd for .sops.yaml, so
        # cwd-based discovery breaks depending on where this script is invoked
        # from. Pin it to the copy home-manager places at a fixed home path.
        SOPS_CONFIG="$HOME/.config/sops/.sops.yaml"
        if [[ ! -f "$SOPS_CONFIG" ]]; then
          echo "Error: sops config not found at $SOPS_CONFIG" >&2
          echo "  Run 'hms' (home-manager switch) to place it." >&2
          exit 1
        fi

        # Preflight: encrypting to an age *plugin* recipient requires the
        # plugin binary on PATH, even though no PIN or touch is needed.
        if ! command -v age-plugin-yubikey >/dev/null 2>&1; then
          echo "Error: age-plugin-yubikey not found on PATH." >&2
          echo "  On WSL it is deployed by modules/wsl.nix — run 'hms'." >&2
          exit 1
        fi

        # Confirm the replacement up front, but touch nothing yet — the
        # existing encrypted file stays intact until the new one is fully
        # written, so a failed login or fetch cannot destroy the only
        # working copy of the token.
        if [[ -f "$SECRETS_FILE" ]]; then
          read -r -p "Secrets file already exists at $SECRETS_FILE. Replace it? [y/N] " CONFIRM
          if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
            echo "Aborted." >&2
            exit 1
          fi
        fi

        mkdir -p "$HOME/.local/secrets"

        # One EXIT trap for every path out of this script: shred the
        # plaintext, drop the staged ciphertext, and always close the vault
        # session — including on mid-script failure.
        PLAINTEXT_TMP=""
        ENCRYPTED_TMP=""
        cleanup() {
          [[ -n "$PLAINTEXT_TMP" ]] && { shred -u "$PLAINTEXT_TMP" 2>/dev/null || rm -f "$PLAINTEXT_TMP"; }
          [[ -n "$ENCRYPTED_TMP" ]] && rm -f "$ENCRYPTED_TMP"
          bw logout --quiet 2>/dev/null || true
        }
        trap cleanup EXIT

        # Log in or unlock — bw unlock only works on an already-authenticated
        # vault, so check status first and fall through to login on a fresh
        # machine.
        echo "Connecting to your Bitwarden account:"
        BW_STATUS=$(bw status 2>/dev/null | jq -r '.status' 2>/dev/null || echo "unauthenticated")
        if [[ "$BW_STATUS" == "unauthenticated" ]]; then
          BW_SESSION=$(bw login --raw)
        else
          BW_SESSION=$(bw unlock --raw)
        fi
        export BW_SESSION

        # Validate the notes field before writing anything — jq outputs the
        # literal string "null" when the field is absent, which would
        # otherwise be encrypted and stored as broken YAML (AGENTS.md).
        NOTES=$(bw get item "${bitwardenVaultItem}" | jq -r '.notes')
        [[ "$NOTES" != "null" && -n "$NOTES" ]] || {
          echo "Error: notes field is empty or missing on '${bitwardenVaultItem}'" >&2
          exit 1
        }

        # Plaintext tmpfile lives inside the secrets dir so the .sops.yaml
        # path regex matches and the YubiKey recipient is auto-selected.
        PLAINTEXT_TMP=$(mktemp "$HOME/.local/secrets/.sync.XXXXXX.yaml")
        printf '%s\n' "$NOTES" > "$PLAINTEXT_TMP"

        # Encrypt to a staging file; the real secrets file is untouched until
        # sops has fully succeeded.
        ENCRYPTED_TMP=$(mktemp "$HOME/.local/secrets/.sync-enc.XXXXXX.yaml")
        sops --config "$SOPS_CONFIG" --encrypt "$PLAINTEXT_TMP" > "$ENCRYPTED_TMP"

        # Point of no return: shred the old file, then move the replacement
        # into place.
        if [[ -f "$SECRETS_FILE" ]]; then
          shred -u "$SECRETS_FILE"
          echo "Existing secrets file shredded."
        fi
        mv "$ENCRYPTED_TMP" "$SECRETS_FILE"
        ENCRYPTED_TMP=""
        chmod 600 "$SECRETS_FILE"

        echo "Successfully synced secrets to $SECRETS_FILE"
      '';
    };
  };
}
