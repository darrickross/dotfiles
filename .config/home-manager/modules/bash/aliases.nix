# Common shell aliases and color support for ls/grep.
{ pkgs, ... }:
{
  # Modern replacements backing the `cat`/`ls` aliases below.
  # (Also listed in home.nix; home.packages entries merge and dedupe.)
  home.packages = with pkgs; [
    bat
    eza
  ];

  programs.bash = {
    shellAliases = {
      # Better defaults (packages installed above)
      cat = "bat";
      ls = "eza --git";

      ll = "ls -alF";
      la = "ls -A";
      l = "ls -CF";

      # Prefer python3 when invoked as python.
      python = "python3";

      # Desktop notification for long-running commands.
      # Usage: sleep 30; alert
      alert = ''notify-send --urgency=low -i "$([ $? = 0 ] && echo terminal || echo error)" "$(history|tail -n1|sed -e 's/^\s*[0-9]\+\s*//;s/[;&|]\s*alert$//')"'';
    };

    initExtra = ''
      # cd into a directory and list its contents on success.
      cd() {
        builtin cd "$@" && ls -al
      }

      # Enable color output for grep family (ls color is handled by eza alias).
      if [ -x /usr/bin/dircolors ]; then
        test -r ~/.dircolors \
          && eval "$(dircolors -b ~/.dircolors)" \
          || eval "$(dircolors -b)"
        alias grep='grep --color=auto'
        alias fgrep='fgrep --color=auto'
        alias egrep='egrep --color=auto'
      fi

      # Source ~/.bash_aliases if it exists (for machine-local overrides).
      if [ -f ~/.bash_aliases ]; then
        # shellcheck disable=SC1090
        . ~/.bash_aliases
      fi
    '';
  };
}
