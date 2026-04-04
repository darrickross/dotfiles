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
    bitwarden-cli # used by bw-unlock / bw-bootstrap-secrets
    eza
    ffmpeg # scripts/video/rename-video-metadata.sh
    jq
    gh # github cli
    mkvtoolnix
    nixfmt-rfc-style # vscode plugin: jnoortheen.nix-ide
    oh-my-posh
    opentofu
    (python313.withPackages (py: [
      py.ansible-core # vscode plugin: redhat.ansible
      py.black # vscode plugin: ms-python.black-formatter
      py.cfn-lint # vscode plugin: kddejong.vscode-cfn-lint
      py.pillow # dotfiles/scripts/pdf/convert_tif_jpg_to_pdf.py
      py.pypdf2 # dotfiles/scripts/pdf/<multiple>
      py.rich # dotfiles/scripts/video/rename-media.py
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
    sops # used by bw-unlock / bw-bootstrap-secrets
    tree
    tldr
    yq-go # used by bw-unlock / bw-bootstrap-secrets
    # `yq` is a wrapper around `jq`
    # `yq-go` is a native yaml version
  ];

  # Packages that are allowed to be "Unfree"
  # nixpkgs.config.allowUnfreePredicate =
  #   pkg:
  #   builtins.elem (pkgs.lib.getName pkg) [
  #     "terraform"
  #   ];

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
      executable = true;
      text = ''
        #!/usr/bin/env bash
        exec "/mnt/c/Program Files/age-plugin-yubikey/age-plugin-yubikey.exe" "$@"
      '';
    };

    # Unlock Bitwarden vault and emit a BW_SESSION token.
    # Usage: export BW_SESSION=$(bw-unlock)
    ".local/bin/bw-unlock" = {
      executable = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        SECRETS_FILE="$HOME/.local/secrets/bitwarden.yaml"

        if [[ ! -f "$SECRETS_FILE" ]]; then
          echo "Error: Secrets file not found at $SECRETS_FILE" >&2
          echo "Run 'bw-bootstrap-secrets' to initialize it first." >&2
          exit 1
        fi

        echo "Make sure to touch the yubikey after entering the pin!"

        # Decrypt the secrets file (requires YubiKey touch)
        DECRYPTED=$(sops --decrypt "$SECRETS_FILE")

        # Parse credentials from decrypted YAML
        BW_CLIENTID=$(printf '%s\n' "$DECRYPTED" | yq '.bw_client_id')
        BW_CLIENTSECRET=$(printf '%s\n' "$DECRYPTED" | yq '.bw_client_secret')
        BW_PASSWORD=$(printf '%s\n' "$DECRYPTED" | yq '.bw_password')

        export BW_CLIENTID BW_CLIENTSECRET BW_PASSWORD

        # Login via API key — non-interactive, bypasses 2FA by design
        bw login --apikey --quiet 2>/dev/null || true

        # Unlock vault and output session token
        bw unlock --passwordenv BW_PASSWORD --raw
      '';
    };

    # One-time bootstrap: pull credentials from the primary Bitwarden account,
    # encrypt them with sops + age (YubiKey touch required), and store at
    # ~/.local/secrets/bitwarden.yaml outside the git repo.
    #
    # The Bitwarden item "homelab-cli-secrets" must be a Secure Note whose
    # Notes field contains valid YAML in the following format:
    #
    #   bw_client_id: "user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    #   bw_client_secret: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    #   bw_password: "your-bitwarden-master-password"
    #
    # bw_client_id / bw_client_secret come from the Bitwarden web vault under:
    #   Account Settings → Security → API Key → Client ID / Client Secret
    # These are for the *homelab* Bitwarden account (not your primary account).
    ".local/bin/bw-bootstrap-secrets" = {
      executable = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        SECRETS_FILE="$HOME/.local/secrets/bitwarden.yaml"

        if [[ -f "$SECRETS_FILE" ]]; then
          echo "Error: Secrets file already exists at $SECRETS_FILE" >&2
          echo "Remove it first if you want to re-bootstrap." >&2
          exit 1
        fi

        mkdir -p "$HOME/.local/secrets"

        # Interactive login with primary Bitwarden account
        echo "Log in to your primary Bitwarden account:"
        bw login

        BW_SESSION=$(bw unlock --raw)
        export BW_SESSION

        # Write notes to a tmpfile inside the secrets dir so the path matches
        # the .sops.yaml creation rule and the YubiKey recipient is auto-selected.
        TMPFILE=$(mktemp "$HOME/.local/secrets/.bootstrap.XXXXXX.yaml")
        trap 'shred -u "$TMPFILE" 2>/dev/null || rm -f "$TMPFILE"' EXIT

        bw get item "homelab-cli-secrets" | jq -r '.notes' > "$TMPFILE"

        # Encrypt in place (requires YubiKey touch)
        sops --encrypt "$TMPFILE" > "$SECRETS_FILE"
        chmod 600 "$SECRETS_FILE"

        bw logout --quiet || true
        echo "Successfully bootstrapped secrets to $SECRETS_FILE"
      '';
    };
  };

  # Expose ~/.local/bin (scripts above) to the shell PATH.
  home.sessionPath = [ "$HOME/.local/bin" ];

  programs.bash.enable = true;

  programs.bash.bashrcExtra = ''
    source ${../../.bashrc}
  '';

  programs.bash.shellAliases = {
    cat = "bat";
    ls = "eza --git";
    hms = "home-manager switch && exec \$SHELL -l";
    hmu = "nix flake update --flake $(dirname $(readlink -f ~/.config/home-manager/flake.nix))";
    rename-media = "python3 ~/projects/dotfiles/scripts/video/rename-media.py";
    mkv-info = "python3 ~/projects/dotfiles/scripts/video/mkv-info.py";
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
    # Output of `age-plugin-yubikey -i` and the slot the key is in
    SOPS_AGE_KEY_FILE = "${config.home.homeDirectory}/.config/age/yubikey-identity.txt";
  };

  # Let Home Manager install and manage itself.
  programs.home-manager.enable = true;
}
