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
  home.packages = [
    # # It is sometimes useful to fine-tune packages, for example, by applying
    # # overrides. You can do that directly here, just don't forget the
    # # parentheses. Maybe you want to install Nerd Fonts with a limited number of
    # # fonts?
    # (pkgs.nerdfonts.override { fonts = [ "FantasqueSansMono" ]; })

    pkgs.bat
    pkgs.eza
    pkgs.jq
    pkgs.nixfmt-rfc-style # vscode plugin: jnoortheen.nix-ide
    pkgs.oh-my-posh
    pkgs.python313
    pkgs.python313Packages.ansible-core # vscode plugin: redhat.ansible
    pkgs.python313Packages.black # vscode plugin: ms-python.black-formatter
    pkgs.python313Packages.cfn-lint # vscode plugin: kddejong.vscode-cfn-lint
    pkgs.shellcheck # vscode plugin: timonwong.shellcheck
    pkgs.shfmt # vscode plugin: foxundermoon.shell-format
    pkgs.yq
  ];

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
