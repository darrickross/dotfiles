# shellcheck disable=SC2148
# ~/.bash_logout — bootstrap stub.
#
# Home Manager generates the real ~/.bash_logout via programs.bash.logoutExtra
# (see modules/bash/logout.nix).  This stub is only present before the first
# `home-manager switch`.

if [ "$SHLVL" = 1 ]; then
    [ -x /usr/bin/clear_console ] && /usr/bin/clear_console -q
fi
