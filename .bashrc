# shellcheck disable=SC2148
# ~/.bashrc — bootstrap stub.
#
# This file is only active before Nix Home Manager is installed.
# After `home-manager switch`, ~/.bashrc becomes a symlink into the Nix store
# and this file is no longer read.
#
# The real shell configuration lives in the repo at:
#   .config/home-manager/modules/

# If not running interactively, do nothing.
case $- in
*i*) ;;
*) return ;;
esac

# ==============================================================================
# Install Nix Home Manager to get started (full walkthrough in the README)
# ==============================================================================
echo
echo "This shell is not managed by Nix Home-Manager."
echo "Follow the steps below to set it up (see the repo README for details):"
echo

COUNT=1

if ! command -v nix >/dev/null 2>&1; then
    echo "$COUNT) Install Nix (with the daemon):"
    echo "   sh <(curl -L https://nixos.org/nix/install) --daemon"
    echo
    ((COUNT++))
fi

if [ ! -e "$HOME/.config/home-manager/flake.nix" ]; then
    echo "$COUNT) Link your dotfiles clone so home-manager (and dotfiles-root) can find it:"
    echo "   mkdir -p ~/.config"
    echo "   ln -s \"\$INSTALL_DIR/.config/home-manager\" ~/.config/home-manager"
    echo
    ((COUNT++))
fi

echo "$COUNT) Remove conflicting files and apply the flake:"
echo "   rm -f ~/.bash_profile ~/.bashrc ~/.profile ~/.bash_logout"
echo "   nix run home-manager/master -- switch --flake ~/.config/home-manager#\$(whoami)"
echo "   exec \$SHELL -l"
echo
