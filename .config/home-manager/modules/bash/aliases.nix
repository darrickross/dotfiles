# Common shell aliases and colour support for ls/grep.
#
# NOTE: `ls` and `cat` are intentionally omitted here — home.nix overrides
# them with eza and bat respectively.
{ ... }:
{
  programs.bash = {
    shellAliases = {
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
      # Enable colour output for grep family (ls colour is handled by eza alias).
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
