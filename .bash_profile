# shellcheck disable=SC2148

# Moved from ~/.profile
# Remove this section completely:
# if [ -n "$BASH_VERSION" ]; then
#     if [ -f "$HOME/.bashrc" ]; then
#         . "$HOME/.bashrc"
#     fi
# fi

# ~/.bash_profile
# Add this:
if [ -f "$HOME/.bashrc" ]; then
    # shellcheck disable=SC1091
    . "$HOME/.bashrc"
fi