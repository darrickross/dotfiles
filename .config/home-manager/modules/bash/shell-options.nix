# Miscellaneous interactive-shell options.
{ ... }:
{
  programs.bash = {
    # Re-check terminal size after each command so LINES/COLUMNS stay accurate.
    shellOptions = [ "checkwinsize" ];

    initExtra = ''
      # Make less handle non-text files (binaries, compressed files, etc.)
      [ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"
    '';
  };
}
