# Secrets tooling: Bitwarden vault -> sops+age(YubiKey) encrypted local file
# -> BWS access token -> application secrets via `cbws-exec` (wraps `bws run`).
# See AGENTS.md "Secrets architecture" for the full two-layer design.
#
# Everything the workflow needs lives in this module: the packages the
# scripts call (declared below so the scripts can never be deployed without
# their dependencies), the scripts themselves, and the age identity
# environment variable. Runtime-only requirements that nix
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
  # that cbws-sync-encrypted-secrets fetches. It must be a Secure Note whose
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
    bitwarden-cli # `bw` — vault access in cbws-sync-encrypted-secrets
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

        usage() {
          echo "Usage: sops-load-yubikey-recipient"
          echo ""
          echo "Reads the age recipient (public key) from YubiKey slot 1 and writes"
          echo "it into the dotfiles repo's .config/sops/.sops.yaml (clone located"
          echo "via dotfiles-root). Run 'hms' afterwards to deploy the updated file"
          echo "to ~/.config/sops/.sops.yaml. Setup-time only; reads public metadata"
          echo "only — no PIN or touch required."
          echo ""
          echo "Docs: ~/.local/share/doc/cbws/secrets.md"
        }

        if [[ $# -gt 0 ]]; then
          case "$1" in
            -h | --help) usage; exit 0 ;;
            *) echo "Error: unexpected argument: $1" >&2; usage >&2; exit 1 ;;
          esac
        fi

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

    # Primary way to run a command with BWS secrets. Decrypts the access
    # token (one YubiKey PIN + touch), then execs `bws run` scoped to a
    # project — each secret's Key becomes an environment variable in the
    # command's process tree, and the token dies with that process. The
    # token is never exported into the calling shell: this machine only
    # *reads* secrets; creating or editing them happens in the Bitwarden
    # Secrets Manager web UI.
    ".local/bin/cbws-exec" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        usage() {
          echo "Usage: cbws-exec [--project-id <UUID>] [--] <command> [args...]"
          echo ""
          echo "Runs <command> with BWS secrets injected as environment variables"
          echo "(each secret's Key becomes a variable name). Decrypting the access"
          echo "token costs one YubiKey PIN + touch; the token exists only for the"
          echo "lifetime of <command> and never enters the calling shell."
          echo ""
          echo "Options:"
          echo "  --project-id <UUID>  Inject secrets from this BWS project instead"
          echo "                       of the default_project_id stored in the"
          echo "                       encrypted secrets file."
          echo ""
          echo "Example:"
          echo "  cbws-exec -- ./my-script-here   # script reads secrets from env vars"
          echo ""
          echo "Docs: ~/.local/share/doc/cbws/secrets.md"
        }

        PROJECT_ID=""
        while [[ $# -gt 0 ]]; do
          case "$1" in
            --project-id)
              if [[ $# -lt 2 ]]; then
                echo "Error: --project-id requires a value." >&2
                exit 1
              fi
              PROJECT_ID="$2"
              shift 2
              ;;
            -h | --help)
              usage
              exit 0
              ;;
            --)
              shift
              break
              ;;
            -*)
              echo "Error: unknown option: $1" >&2
              usage >&2
              exit 1
              ;;
            *)
              break
              ;;
          esac
        done

        if [[ $# -eq 0 ]]; then
          echo "Error: no command given." >&2
          usage >&2
          exit 1
        fi

        SECRETS_FILE="$HOME/.local/secrets/bitwarden.yaml"

        # Preflight: check decryption prerequisites up front so failures
        # are actionable instead of a raw sops error.
        if ! command -v age-plugin-yubikey >/dev/null 2>&1; then
          echo "Error: age-plugin-yubikey not found on PATH." >&2
          echo "  On WSL it is deployed by modules/wsl.nix — run 'hms'." >&2
          exit 1
        fi
        if [[ ! -f "''${SOPS_AGE_KEY_FILE:-}" ]]; then
          echo "Error: age identity file not found at ''${SOPS_AGE_KEY_FILE:-<SOPS_AGE_KEY_FILE unset>}" >&2
          echo "  Generate it:  age-plugin-yubikey --identity --slot 1 > ~/.config/age/yubikey-identity.txt" >&2
          exit 1
        fi
        if [[ ! -f "$SECRETS_FILE" ]]; then
          echo "Error: secrets file not found at $SECRETS_FILE" >&2
          echo "  Run cbws-sync-encrypted-secrets to create it." >&2
          exit 1
        fi

        # Decrypt the whole file once — the YubiKey PIN/touch policy is
        # "Always", so per-key --extract calls would each cost a touch.
        # The plaintext only ever lives in this process's memory.
        SECRETS_YAML=$(sops --decrypt "$SECRETS_FILE") || {
          echo "Error: failed to decrypt $SECRETS_FILE" >&2
          exit 1
        }

        # printf | yq (not a herestring) so the plaintext never risks
        # touching a temp file on bash versions that back herestrings
        # with one.
        BWS_ACCESS_TOKEN=$(printf '%s\n' "$SECRETS_YAML" \
          | yq '.local_computer_machine_account_bws_access_token // ""' -)
        if [[ -z "$BWS_ACCESS_TOKEN" ]]; then
          echo "Error: local_computer_machine_account_bws_access_token is missing or empty in $SECRETS_FILE" >&2
          exit 1
        fi

        if [[ -z "$PROJECT_ID" ]]; then
          PROJECT_ID=$(printf '%s\n' "$SECRETS_YAML" | yq '.default_project_id // ""' -)
        fi
        if [[ -z "$PROJECT_ID" ]]; then
          echo "Error: no project id available." >&2
          echo "  Add default_project_id to the '${bitwardenVaultItem}' Secure Note and" >&2
          echo "  re-run cbws-sync-encrypted-secrets, or pass --project-id <UUID>." >&2
          exit 1
        fi

        # exec: the token is in the environment of `bws run` and its
        # children only; it vanishes when the command exits.
        BWS_ACCESS_TOKEN="$BWS_ACCESS_TOKEN" exec bws run --project-id "$PROJECT_ID" -- "$@"
      '';
    };

    # Lists all secrets the machine account can access. Self-contained:
    # runs as a subprocess, always decrypts a fresh token (one YubiKey
    # PIN + touch — any BWS_ACCESS_TOKEN inherited from the environment
    # is ignored), lists the secrets, and exits — the token dies with
    # this process and never enters the calling shell.
    ".local/bin/cbws-list-available-secrets" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        usage() {
          echo "Usage: cbws-list-available-secrets"
          echo ""
          echo "Lists the UUID and Key of every BWS secret the machine account can"
          echo "read. Self-contained: decrypts a fresh access token (one YubiKey"
          echo "PIN + touch), lists, and exits — the token dies with this process"
          echo "and never enters the calling shell."
          echo ""
          echo "Docs: ~/.local/share/doc/cbws/secrets.md"
        }

        if [[ $# -gt 0 ]]; then
          case "$1" in
            -h | --help) usage; exit 0 ;;
            *) echo "Error: unexpected argument: $1" >&2; usage >&2; exit 1 ;;
          esac
        fi

        SECRETS_FILE="$HOME/.local/secrets/bitwarden.yaml"

        # Preflight: check decryption prerequisites up front so failures
        # are actionable instead of a raw sops error.
        if ! command -v age-plugin-yubikey >/dev/null 2>&1; then
          echo "Error: age-plugin-yubikey not found on PATH." >&2
          echo "  On WSL it is deployed by modules/wsl.nix — run 'hms'." >&2
          exit 1
        fi
        if [[ ! -f "''${SOPS_AGE_KEY_FILE:-}" ]]; then
          echo "Error: age identity file not found at ''${SOPS_AGE_KEY_FILE:-<SOPS_AGE_KEY_FILE unset>}" >&2
          echo "  Generate it:  age-plugin-yubikey --identity --slot 1 > ~/.config/age/yubikey-identity.txt" >&2
          exit 1
        fi
        if [[ ! -f "$SECRETS_FILE" ]]; then
          echo "Error: secrets file not found at $SECRETS_FILE" >&2
          echo "  Run cbws-sync-encrypted-secrets to create it." >&2
          exit 1
        fi

        # Always decrypt a fresh token — never trust one inherited from
        # the environment.
        echo "Decrypting $SECRETS_FILE — confirm with your YubiKey PIN + touch." >&2
        BWS_ACCESS_TOKEN=$(
          sops --decrypt --extract '["local_computer_machine_account_bws_access_token"]' \
            "$SECRETS_FILE"
        ) || { echo "Error: failed to decrypt $SECRETS_FILE" >&2; exit 1; }
        [[ -n "$BWS_ACCESS_TOKEN" ]] || { echo "Error: decrypted token is empty" >&2; exit 1; }

        echo "             Secret UUID             | Key"

        BWS_ACCESS_TOKEN="$BWS_ACCESS_TOKEN" bws secret list --output json \
          | jq -r '.[] | "\(.id) | \(.key)"'
      '';
    };

    # The single, deliberate *write* path to Secrets Manager — everything
    # else here is read-only. Wraps scripts/bitwarden/secret-set.py, which
    # reads the value from stdin, decrypts the token itself (one YubiKey
    # PIN + touch), and asks before overwriting an existing key (-y/--yes
    # to skip). Requires the machine account to have read-write access to
    # the project. The Bitwarden SDK it imports is declared in home.nix's
    # main python env (not here) so the VS Code interpreter
    # (~/.nix-profile/bin/python3) can also import it.
    ".local/bin/cbws-secret-set" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail
        exec python3 "$(dotfiles-root)/scripts/bitwarden/secret-set.py" "$@"
      '';
    };

    # Sync secrets from Bitwarden and re-encrypt locally with YubiKey.
    # Run on first setup or after rotating tokens.
    ".local/bin/cbws-sync-encrypted-secrets" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        usage() {
          echo "Usage: cbws-sync-encrypted-secrets"
          echo ""
          echo "Setup/rotation only. Logs into the Bitwarden vault (interactive),"
          echo "fetches the '${bitwardenVaultItem}' Secure Note (BWS access token +"
          echo "project/organization ids), and writes it sops+age(YubiKey)"
          echo "encrypted to ~/.local/secrets/bitwarden.yaml — the file every"
          echo "other cbws-* command decrypts. Asks before replacing an existing"
          echo "file."
          echo ""
          echo "Docs: ~/.local/share/doc/cbws/secrets.md"
        }

        if [[ $# -gt 0 ]]; then
          case "$1" in
            -h | --help) usage; exit 0 ;;
            *) echo "Error: unexpected argument: $1" >&2; usage >&2; exit 1 ;;
          esac
        fi

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
