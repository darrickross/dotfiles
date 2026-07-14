# Bash module entry point.
# Enables bash + completion and pulls in all sub-modules.
{ ... }:
{
  imports = [
    ./history.nix
    ./shell-options.nix
    ./prompt.nix
    ./aliases.nix
    ./logout.nix
  ];

  programs.bash = {
    enable = true;
    enableCompletion = true;
  };
}
