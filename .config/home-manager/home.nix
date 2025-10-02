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
    eza
    jq
    gh # github cli
    nixfmt-rfc-style # vscode plugin: jnoortheen.nix-ide
    oh-my-posh
    opentofu
    (python313.withPackages (py: [
      py.ansible-core # vscode plugin: redhat.ansible
      py.black # vscode plugin: ms-python.black-formatter
      py.cfn-lint # vscode plugin: kddejong.vscode-cfn-lint
      py.pillow # dotfiles/scripts/pdf/convert_tif_jpg_to_pdf.py
      py.pypdf2 # dotfiles/scripts/pdf/<multiple>
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
    yq
  ];

  # Packages that are allowed to be "Unfree"
  # nixpkgs.config.allowUnfreePredicate =
  #   pkg:
  #   builtins.elem (pkgs.lib.getName pkg) [
  #     "terraform"
  #   ];

  # Home Manager is pretty good at managing dotfiles. The primary way to manage
  # plain files is through 'home.file'.
  # home.file = { ".bashrc".source = ../../.bashrc; };

  programs.bash.enable = true;

  programs.bash.bashrcExtra = ''
    source ${../../.bashrc}
  '';

  programs.bash.shellAliases = {
    cat = "bat";
    ls = "eza --git";
    hms = "home-manager switch && exec \$SHELL -l";
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
    # EDITOR = "emacs";
  };

  # Let Home Manager install and manage itself.
  programs.home-manager.enable = true;
}
