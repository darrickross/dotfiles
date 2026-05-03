{ config, pkgs, ... }:

{
  # Home Manager needs a bit of information about you and the paths it should
  # manage.
  home.username = "itsjustmech";
  home.homeDirectory = "/home/itsjustmech";

  # This value determines the Home Manager release that your configuration is
  # compatible with. This helps avoid breakage when a new Home Manager release
  # introduces backwards incompatible changes.
  #
  # You should not change this value, even if you update Home Manager. If you do
  # want to update the value, then make sure to first check the Home Manager
  # release notes.
  home.stateVersion = "25.05"; # Please read the comment before changing.

  # The home.packages option allows you to install Nix packages into your
  # environment.
  home.packages = with pkgs; [
    # # It is sometimes useful to fine-tune packages, for example, by applying
    # # overrides. You can do that directly here, just don't forget the
    # # parentheses. Maybe you want to install Nerd Fonts with a limited number of
    # # fonts?
    # (nerdfonts.override { fonts = [ "FantasqueSansMono" ]; })

    ansible-lint
    bat
    bitwarden-cli # used by bw_sync_encrypted_secrets.sh
    bws # authenticated via BWS_ACCESS_TOKEN from the secrets file
    eza
    ffmpeg # ffprobe used by rename-media.py
    # fnm # Fast Node Manager - VSCode Plugin development?
    jq
    gh # github cli
    mkvtoolnix
    nixfmt # vscode plugin: jnoortheen.nix-ide
    oh-my-posh
    opentofu
    (python313.withPackages (py: [
      py.ansible-core # vscode plugin: redhat.ansible
      py.black # vscode plugin: ms-python.black-formatter
      py.cfn-lint # vscode plugin: kddejong.vscode-cfn-lint
      py.argcomplete # dotfiles/scripts/qr-codes/generate.py
      py.jinja2 # dotfiles/scripts/qr-codes/generate.py
      py.pillow # dotfiles/scripts/pdf/convert_tif_jpg_to_pdf.py
      py.pypdf # dotfiles/scripts/pdf/<multiple>
      py.rich # dotfiles/scripts/video/mkv-info, mkv-scan.py, rename-media.py
      py.segno # dotfiles/scripts/qr-codes/generate.py
      py.weasyprint # dotfiles/scripts/qr-codes/generate.py
    ]))
    shellcheck # vscode plugin: timonwong.shellcheck
    shfmt # vscode plugin: foxundermoon.shell-format
    # (terraform.overrideAttrs (old: {
    #   # Since this package comes directly from a GitHub fetch,
    #   # we can pull a specific version but its a bit weird to do this
    #   #
    #   # 1) GitHub repo, owner, and revisions/tag used:
    #   #
    #   #     nix edit nixpkgs#terraform | grep src -A 10
    #   #
    #   # NOTE: This must say "src = fetchFromGitHub", otherwise its a different method...
    #   #
    #   # 2) The url nix will use to fetch the package also has the above info in the url technically...
    #   #
    #   #     nix derivation show "github:NixOS/nixpkgs?config.allowUnfree=true#terraform.src" | jq '.[].env.urls' -r
    #   #
    #   # 3) Get the sha256 hash
    #   #
    #   #     nix hash convert --hash-algo sha256 --to sri $(nix-prefetch-url --unpack --type sha256 https://github.com/hashicorp/terraform/archive/v1.11.4.tar.gz 2>/dev/null)
    #   #
    #   # 4) vendorHash, ngl I just don't include it, and if it errors it will tell you what it wants, then fill that in...
    #   #
    #   version = "1.11.4";
    #   src = pkgs.fetchFromGitHub {
    #     owner = "hashicorp";
    #     repo = "terraform";
    #     rev = "v1.11.4";
    #     sha256 = "sha256-VGptJz+MbJ8nJRGUW9LzX6IDLYbjI5tK40ZhkZCGVf0=";
    #   };
    #   vendorHash = "sha256-pDtWGDKEnYq4wJYG+Rr5C1pWN/X92P+wvHrNm0Ldh+8=";
    # }))
    sops # used by bw_sync_encrypted_secrets.sh
    tree
    tldr
    yq-go # used by bw_sync_encrypted_secrets.sh
    # `yq` is a wrapper around `jq`
    # `yq-go` is a native yaml version
  ];

  # Packages that are allowed to be "Unfree"
  nixpkgs.config.allowUnfreePredicate =
    pkg:
    builtins.elem (pkgs.lib.getName pkg) [
      "bws"
      # "terraform"
    ];

  # sops-nix: use YubiKey retired key slot as the age identity for decryption.
  # age-plugin-yubikey uses the 20 retired key management slots (1-20), not the
  # standard PIV slots (9a-9e). Generate with: age-plugin-yubikey --generate --slot 1
  # No sops.secrets block — ~/.local/secrets/bitwarden.yaml is managed manually
  # by bw-bootstrap-secrets and never touched during home-manager activation.
  sops.age.keyFile = "${config.home.homeDirectory}/.config/age/yubikey-identity.txt";

  # Home Manager is pretty good at managing dotfiles. The primary way to manage
  # plain files is through 'home.file'.
  # home.file = { ".bashrc".source = ../../.bashrc; };

  home.file = {
    # age-plugin-yubikey wrapper: forwards to the Windows host binary so that
    # age/sops in WSL2 can discover it via PATH and use the YubiKey over USB.
    # age plugin discovery works by spawning an executable named
    # "age-plugin-<name>", so a shell alias won't work — it must be on PATH.
    ".local/bin/age-plugin-yubikey" = {
      executable = true; # mode is read-only by the nix store; no chmod needed
      force = true;
      text = ''
        #!/usr/bin/env bash
        exec "/mnt/c/Program Files/age-plugin-yubikey/age-plugin-yubikey.exe" "$@"
      '';
    };

    # Prefixed with _ so it is not called directly. The alias below sources it,
    # which is the only way exports reach the calling shell.
    # Must be sourced (. bws-load-local-machine-credential) so the export
    # reaches the calling shell. Running it directly has no effect on the
    # parent environment.
    ".local/bin/_bws-load-local-machine-credential" = {
      executable = true; # mode is read-only by the nix store; no chmod needed
      force = true;
      text = ''
        #!/usr/bin/env bash

        # Refuse to run as a subprocess — exports would be lost on exit.
        if [[ "''${BASH_SOURCE[0]}" == "''${0}" ]]; then
          echo "Error: this script must be sourced, not executed." >&2
          echo "  Run:  source bws-load-local-machine-credential" >&2
          exit 1
        fi

        SECRETS_FILE="$HOME/.local/secrets/bitwarden.yaml"

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

    # Lists all secrets available in the BWS project, showing only the key
    # (note) and ID of each entry. Requires BWS_ACCESS_TOKEN to be set in
    # the environment — run bws-load-local-machine-credential first.
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

    # Sync down the secret list from Bitwarden and re-encrypt it locally.
    # Use this on first setup, or when the BWS access token or other secrets have
    # been rotated and you need to refresh ~/.local/secrets/bitwarden.yaml.
    #
    # Expects the Bitwarden item "local-machine-bws-secrets" to be a Secure Note
    # whose Notes field contains valid YAML in the following format:
    #
    #   local_computer_machine_account_bws_access_token: "your-bws-access-token"
    #
    ".local/bin/bw_sync_encrypted_secrets.sh" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        SECRETS_FILE="$HOME/.local/secrets/bitwarden.yaml"

        # If the secrets file already exists, ask the user before overwriting.
        # Exit if they decline; shred the old file if they confirm.
        if [[ -f "$SECRETS_FILE" ]]; then
          read -r -p "Secrets file already exists at $SECRETS_FILE. Shred and replace it? [y/N] " CONFIRM
          if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
            echo "Aborted." >&2
            exit 1
          fi
          shred -u "$SECRETS_FILE"
          echo "Existing secrets file shredded."
        fi

        mkdir -p "$HOME/.local/secrets"

        # Log in or unlock — bw unlock only works on an already-authenticated vault,
        # so check status first and fall through to login on a fresh machine.
        echo "Connecting to your Bitwarden account:"
        BW_STATUS=$(bw status 2>/dev/null | jq -r '.status' 2>/dev/null || echo "unauthenticated")
        if [[ "$BW_STATUS" == "unauthenticated" ]]; then
          BW_SESSION=$(bw login --raw)
        else
          BW_SESSION=$(bw unlock --raw)
        fi
        export BW_SESSION

        # Write notes to a tmpfile inside the secrets dir so the path matches
        # the .sops.yaml creation rule and the YubiKey recipient is auto-selected.
        TMPFILE=$(mktemp "$HOME/.local/secrets/.sync.XXXXXX.yaml")
        trap 'shred -u "$TMPFILE" 2>/dev/null || rm -f "$TMPFILE"' EXIT

        bw get item "homelab-cli-secrets" | jq -r '.notes' > "$TMPFILE"

        # Encrypt in place (requires YubiKey touch)
        sops --encrypt "$TMPFILE" > "$SECRETS_FILE"
        chmod 600 "$SECRETS_FILE"

        bw logout --quiet || true
        echo "Successfully synced secrets to $SECRETS_FILE"
      '';
    };
  };

  # Expose ~/.local/bin (scripts above) to the shell PATH.
  home.sessionPath = [ "$HOME/.local/bin" ];

  programs.bash.enable = true;

  programs.bash.bashrcExtra = ''
    source ${../../.bashrc}
    _wifi_qr_complete() {
      local IFS=$'\013'
      local SUPPRESS_SPACE=0
      compopt +o nospace 2>/dev/null && SUPPRESS_SPACE=1
      COMPREPLY=( $(IFS="$IFS" COMP_LINE="$COMP_LINE" COMP_POINT="$COMP_POINT" \
        _ARGCOMPLETE=1 _ARGCOMPLETE_SUPPRESS_SPACE=$SUPPRESS_SPACE \
        python3 "$HOME/projects/dotfiles/scripts/qr-codes/generate.py" \
        8>&1 9>&2 1>/dev/null 2>/dev/null) )
      [[ $? == 0 && $SUPPRESS_SPACE == 1 ]] && compopt -o nospace
    }
    complete -o nospace -o default -F _wifi_qr_complete wifi-qr

    if [[ -z "''${_HM_CHECKED:-}" ]]; then
      export _HM_CHECKED=1
      _hm_profile="$HOME/.local/state/nix/profiles/home-manager"
      if [[ -L "$_hm_profile" ]]; then
        _hm_switch_time=$(stat -c %Y "$_hm_profile")
        _hm_newer=$(find -L "$HOME/.config/home-manager" -name "*.nix" -newermt "@$_hm_switch_time" 2>/dev/null | head -1)
        if [[ -n "$_hm_newer" ]]; then
          echo "home-manager: config changed since last switch — run 'hms' to apply" >&2
        fi
        unset _hm_newer
      fi
      unset _hm_profile
    fi
  '';

  programs.bash.shellAliases = {
    cat = "bat";
    ls = "eza --git";
    hms = "home-manager switch && exec \$SHELL -l";
    hmu = "nix flake update --flake $(dirname $(readlink -f ~/.config/home-manager/flake.nix))";
    rename-media = "python3 ~/projects/dotfiles/scripts/video/rename-media.py";
    mkv-info = "python3 ~/projects/dotfiles/scripts/video/mkv-info.py";
    mkv-scan = "python3 ~/projects/dotfiles/scripts/video/mkv-scan.py";
    wifi-qr = "python3 ~/projects/dotfiles/scripts/qr-codes/generate.py";
    bws-load-local-machine-credential = "source $HOME/.local/bin/_bws-load-local-machine-credential";
  };

  # Home Manager can also manage your environment variables through
  # 'home.sessionVariables'. These will be explicitly sourced when using a
  # shell provided by Home Manager. If you don't want to manage your shell
  # through Home Manager then you have to manually source 'hm-session-vars.sh'
  # located at either
  #
  #  ~/.nix-profile/etc/profile.d/hm-session-vars.sh
  #
  # or
  #
  #  ~/.local/state/nix/profiles/profile/etc/profile.d/hm-session-vars.sh
  #
  # or
  #
  #  /etc/profiles/per-user/itsjustmech/etc/profile.d/hm-session-vars.sh
  #
  home.sessionVariables = {
    # This should contain the age-plugin-yubikey key info
    # Output of `age-plugin-yubikey --identity --slot 1` (see README YubiKey setup)
    SOPS_AGE_KEY_FILE = "${config.home.homeDirectory}/.config/age/yubikey-identity.txt";
  };

  # Let Home Manager install and manage itself.
  programs.home-manager.enable = true;
}
