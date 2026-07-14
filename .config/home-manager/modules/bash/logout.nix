# Clear the terminal when leaving a login shell (increases privacy at consoles).
{ ... }:
{
  programs.bash.logoutExtra = ''
    if [ "$SHLVL" = 1 ]; then
      [ -x /usr/bin/clear_console ] && /usr/bin/clear_console -q
    fi
  '';
}
