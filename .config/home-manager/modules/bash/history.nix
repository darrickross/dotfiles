# Bash history: deduplication, large ring-buffer, and per-command sync
# across concurrent shells via PROMPT_COMMAND.
{ ... }:
{
  programs.bash = {
    # ignoreboth  = ignorespace + ignoredups
    # erasedups   = remove older duplicates from the file
    historyControl = [
      "ignoreboth"
      "erasedups"
    ];

    historySize = 100000;
    historyFileSize = 100000;

    # Append to the history file rather than overwriting it.
    shellOptions = [ "histappend" ];

    # After every command: flush this shell's history to disk, clear the
    # in-memory list, then reload from disk so all open terminals share history.
    initExtra = ''
      export PROMPT_COMMAND="history -a; history -c; history -r''${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
    '';
  };
}
