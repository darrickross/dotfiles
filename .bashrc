# shellcheck disable=SC2148
# ~/.bashrc — bootstrap stub.
#
# This file is only active before Nix Home Manager is installed.
# After `home-manager switch`, ~/.bashrc becomes a symlink into the Nix store
# and this file is no longer read.
#
# The real shell configuration lives in:
#   ~/projects/dotfiles/.config/home-manager/modules/

# If not running interactively, do nothing.
case $- in
*i*) ;;
*) return ;;
esac

# ==============================================================================
# Install Nix Home Manager to get started
# ==============================================================================
echo
echo "This shell is not managed by Nix Home-Manager."
echo "Follow the steps below to set it up:"
echo

COUNT=1

if ! command -v nix >/dev/null 2>&1; then
    echo "$COUNT) Install Nix:"
    echo "   curl -L https://nixos.org/nix/install | sh"
    echo
    ((COUNT++))
fi

if ! nix-channel --list 2>/dev/null | grep -q '^home-manager'; then
    echo "$COUNT) Add the Home Manager channel:"
    echo "   nix-channel --add https://github.com/nix-community/home-manager/archive/release-25.11.tar.gz home-manager"
    echo "   nix-channel --update"
    echo
    ((COUNT++))
fi

if ! command -v home-manager >/dev/null 2>&1; then
    echo "$COUNT) Install Home Manager:"
    echo "   nix-shell '<home-manager>' -A install"
    echo
    ((COUNT++))
fi

echo "$COUNT) Remove conflicting files and apply the flake:"
echo "   rm -f ~/.bash_profile ~/.bashrc ~/.profile"
echo "   home-manager switch --flake ~/projects/dotfiles/.config/home-manager#\$(whoami)"
echo "   exec \$SHELL -l"
echo
