# shellcheck disable=SC2148
# ~/.profile — bootstrap stub.
#
# Home Manager handles PATH additions via home.sessionPath
# (see home.nix).  This stub is only present before the first
# `home-manager switch`.

if [ -d "$HOME/bin" ]; then
    PATH="$HOME/bin:$PATH"
fi

if [ -d "$HOME/.local/bin" ]; then
    PATH="$HOME/.local/bin:$PATH"
fi
