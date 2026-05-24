# shellcheck disable=SC2148
# ~/.bash_profile — bootstrap stub.
#
# Home Manager generates the real ~/.bash_profile (sources ~/.bashrc for
# login shells).  This file is only present before the first `home-manager switch`.

if [ -f "$HOME/.bashrc" ]; then
    # shellcheck disable=SC1091
    . "$HOME/.bashrc"
fi
