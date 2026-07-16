{ pkgs, ... }:

{
  imports = [
    ./modules/bash
    ./modules/dotfiles.nix
    ./modules/secrets.nix
    ./modules/wsl.nix
  ];

  # ---------------------------------------------------------------------------
  # Identity
  # ---------------------------------------------------------------------------
  home.username = "itsjustmech";
  home.homeDirectory = "/home/itsjustmech";

  # This value determines the Home Manager release that your configuration is
  # compatible with. Do not change it even when updating Home Manager — check
  # the release notes first.
  home.stateVersion = "26.05";

  # ---------------------------------------------------------------------------
  # Packages
  # ---------------------------------------------------------------------------
  home.packages = with pkgs; [
    # # It is sometimes useful to fine-tune packages, for example, by applying
    # # overrides. You can do that directly here, just don't forget the
    # # parentheses. Maybe you want to install Nerd Fonts with a limited number of
    # # fonts?
    # (nerdfonts.override { fonts = [ "FantasqueSansMono" ]; })

    # NOTE: secrets tooling (bitwarden-cli, bws, jq, sops, yq-go) is declared
    # in ./modules/secrets.nix next to the scripts that require it.
    ansible-lint
    bat
    cspell # vscode plugin: streetsidesoftware.code-spell-checker; scripts/checks/spelling.py
    eza
    ffmpeg # ffprobe used by rename-media.py
    # fnm # Fast Node Manager - (VS Code plugin workflow)
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
      py.cryptography # dotfiles/scripts/certificates/convert-pfx.py
      py.jinja2 # dotfiles/scripts/qr-codes/generate.py
      py.pillow # dotfiles/scripts/pdf/convert_tif_jpg_to_pdf.py
      py.pypdf # dotfiles/scripts/pdf/<multiple>
      py.rich # dotfiles/scripts/video/mkv-info, mkv-scan.py, rename-media.py
      py.segno # dotfiles/scripts/qr-codes/generate.py
      py.weasyprint # dotfiles/scripts/qr-codes/generate.py

      # Bitwarden Secrets Manager SDK — dotfiles/scripts/bitwarden/secret-set.py
      # (cbws-secret-set, modules/secrets.nix). Lives in this main env (not a
      # private one in secrets.nix) so the VS Code interpreter
      # (~/.nix-profile/bin/python3) can import it. Not packaged in nixpkgs,
      # so built from the official PyPI binary wheel (cp39-abi3: one wheel
      # for every python >= 3.9, including this 3.13). To bump: update
      # version, take the new manylinux x86_64 wheel URL + sha256 from
      # https://pypi.org/pypi/bitwarden-sdk/json and convert the hash with
      # `nix hash convert --hash-algo sha256 --to sri <hex>`.
      (py.buildPythonPackage {
        pname = "bitwarden-sdk";
        version = "2.1.0";
        format = "wheel";
        src = pkgs.fetchurl {
          url = "https://files.pythonhosted.org/packages/7e/f4/ccdcadee82f88ec3c52a3b6e0db11df4c5587db171a2c979e4e9eb76b1d4/bitwarden_sdk-2.1.0-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl";
          hash = "sha256-tvayYk40AweJHtwgooYOwLfCFAaD7sLOLiDRB2/+kmg=";
        };
        # The wheel bundles a Rust native extension; autoPatchelf points it
        # at nix's libc/libgcc instead of the manylinux paths.
        nativeBuildInputs = [ pkgs.autoPatchelfHook ];
        buildInputs = [ pkgs.stdenv.cc.cc.lib ];
        dependencies = [ py.python-dateutil ];
        pythonImportsCheck = [ "bitwarden_sdk" ];
      })
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
    tree
    tldr
    yq-go
    # `yq` is a wrapper around `jq`
    # `yq-go` is a native yaml version
    # Both install to `yq`
  ];

  # Packages that are allowed to be "Unfree".
  # This predicate is a single function and cannot be merged across modules,
  # so it stays here even for packages declared elsewhere (bws is required
  # by ./modules/secrets.nix).
  nixpkgs.config.allowUnfreePredicate =
    pkg:
    builtins.elem (pkgs.lib.getName pkg) [
      "bws"
      # "terraform"
    ];

  # ---------------------------------------------------------------------------
  # Managed scripts / executables in ~/.local/bin
  # ---------------------------------------------------------------------------

  # NOTE: plain config files tracked in this repo (.gitconfig, .ssh/config,
  # sops rules, etc.) are deployed by ./modules/dotfiles.nix, and the
  # Bitwarden/sops secrets scripts live in ./modules/secrets.nix — only
  # general-purpose scripts live here.
  home.file = {
    # Prints the root of the live dotfiles clone. Works backwards from
    # ~/.config/home-manager/home.nix, which links into
    # <repo>/.config/home-manager/ — the same convention 'hms' and 'hmu'
    # already rely on to find the flake. The clone path cannot be baked in at
    # build time: flakes evaluate from a nix-store copy of the repo, so
    # home.nix never knows where the checkout lives. Resolving at runtime
    # keeps every alias and script clone-location independent.
    ".local/bin/dotfiles-root" = {
      executable = true;
      force = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        ANCHOR="$HOME/.config/home-manager/home.nix"

        if [[ ! -e "$ANCHOR" ]]; then
          echo "Error: $ANCHOR not found." >&2
          echo "  Link your clone:  ln -s \"\$INSTALL_DIR/.config/home-manager\" ~/.config/home-manager" >&2
          exit 1
        fi

        # readlink -f resolves whether home.nix itself is a symlink or a
        # parent directory is; three dirnames walk out of .config/home-manager.
        ROOT=$(dirname "$(dirname "$(dirname "$(readlink -f "$ANCHOR")")")")

        if [[ ! -e "$ROOT/.git" ]]; then
          echo "Error: resolved path $ROOT is not a git clone." >&2
          echo "  $ANCHOR must link into <repo>/.config/home-manager/" >&2
          exit 1
        fi

        printf '%s\n' "$ROOT"
      '';
    };
  };

  # ---------------------------------------------------------------------------
  # PATH
  # ---------------------------------------------------------------------------
  home.sessionPath = [
    "$HOME/.local/bin"
    "$HOME/bin"
  ];

  # ---------------------------------------------------------------------------
  # Shell aliases (home-manager / tooling specific)
  # ---------------------------------------------------------------------------
  programs.bash.shellAliases = {
    # NOTE: `cat` (bat) and `ls` (eza) aliases live in ./modules/bash/aliases.nix.

    # Home Manager workflow
    hms = "home-manager switch && exec $SHELL -l";
    hmu = "nix flake update --flake $(dirname $(readlink -f ~/.config/home-manager/flake.nix))";

    # Project scripts — resolved from the live clone at invocation time,
    # never a hardcoded clone path (see dotfiles-root above).
    # Repo validation: nixfmt --check, flake eval, shellcheck on rendered
    # scripts. Run after editing any .nix file, before 'hms'.
    dotfiles-check = ''python3 "$(dotfiles-root)/scripts/checks/check.py"'';

    # Spelling: list unknown words (cspell) / migrate VS Code cSpell.words
    # into cspell configs (see each script's --help).
    spell-check = ''python3 "$(dotfiles-root)/scripts/checks/spelling.py"'';
    cspell-import = ''python3 "$(dotfiles-root)/scripts/cspell/import-vscode-words.py"'';

    # PKCS#12: extract keys/certs from a .pfx bundle (see --help; password
    # via --password-stdin or an interactive no-echo prompt, never argv/env).
    convert-pfx = ''python3 "$(dotfiles-root)/scripts/certificates/convert-pfx.py"'';

    rename-media = ''python3 "$(dotfiles-root)/scripts/video/rename-media.py"'';
    mkv-info = ''python3 "$(dotfiles-root)/scripts/video/mkv-info.py"'';
    mkv-scan = ''python3 "$(dotfiles-root)/scripts/video/mkv-scan.py"'';
    wifi-qr = ''python3 "$(dotfiles-root)/scripts/qr-codes/generate.py"'';
  };

  # ---------------------------------------------------------------------------
  # Extra bash init — home-manager / repo-specific logic
  # ---------------------------------------------------------------------------
  programs.bash.initExtra = ''
    # Tab-completion for the wifi-qr script (uses argcomplete).
    _wifi_qr_complete() {
      local IFS=$'\013'
      local SUPPRESS_SPACE=0
      compopt +o nospace 2>/dev/null && SUPPRESS_SPACE=1
      COMPREPLY=( $(IFS="$IFS" COMP_LINE="$COMP_LINE" COMP_POINT="$COMP_POINT" \
        _ARGCOMPLETE=1 _ARGCOMPLETE_SUPPRESS_SPACE=$SUPPRESS_SPACE \
        python3 "$(dotfiles-root)/scripts/qr-codes/generate.py" \
        8>&1 9>&2 1>/dev/null 2>/dev/null) )
      [[ $? == 0 && $SUPPRESS_SPACE == 1 ]] && compopt -o nospace
    }
    complete -o nospace -o default -F _wifi_qr_complete wifi-qr

    # Tab-completion for cspell-import (scripts/cspell/import-vscode-words.py):
    # flags, plus Windows usernames from /mnt/c/Users after
    # --update-global-user-list (skipping non-user entries and names with
    # spaces, which COMPREPLY word splitting would mangle).
    _cspell_import_complete() {
      local cur="''${COMP_WORDS[COMP_CWORD]}"
      local prev="''${COMP_WORDS[COMP_CWORD - 1]}"
      if [[ "$prev" == "--update-global-user-list" ]]; then
        local dir user users=()
        for dir in /mnt/c/Users/*/; do
          user="''${dir%/}"
          user="''${user##*/}"
          [[ "$user" == *" "* || "$user" == "Default" || "$user" == "Public" ]] && continue
          users+=("$user")
        done
        mapfile -t COMPREPLY < <(compgen -W "''${users[*]}" -- "$cur")
        return
      fi
      mapfile -t COMPREPLY < <(compgen -W "--update-global-user-list --copy-and-delete --dry-run --help" -- "$cur")
    }
    complete -F _cspell_import_complete cspell-import

    # Warn when any .nix file in the home-manager config is newer than the
    # last `home-manager switch`, so you don't forget to apply changes.
    if [[ -z "''${_HM_CHECKED:-}" ]]; then
      export _HM_CHECKED=1
      _hm_profile="$HOME/.local/state/nix/profiles/home-manager"
      if [[ -L "$_hm_profile" ]]; then
        _hm_switch_time=$(stat -c %Y "$_hm_profile")
        _hm_newer=$(find -L "$HOME/.config/home-manager" -name "*.nix" \
          -newermt "@$_hm_switch_time" 2>/dev/null | head -1)
        if [[ -n "$_hm_newer" ]]; then
          echo "home-manager: config changed since last switch — run 'hms' to apply" >&2
        fi
        unset _hm_newer
      fi
      unset _hm_profile
    fi
  '';

  # ---------------------------------------------------------------------------
  # Let Home Manager manage itself
  # ---------------------------------------------------------------------------
  programs.home-manager.enable = true;
}
