#!/bin/bash

# Ensure the script is run from the folder where it is located
if [[ "$(dirname "$0")" != "." ]]; then
    echo "Please run the script from the folder where it is located."
    exit 1
fi

# Function to backup existing files
backup_files() {
    local conflicts=("$@")
    for file in "${conflicts[@]}"; do
        if [[ -e "$HOME/$file" ]]; then
            mv "$HOME/$file" "$HOME/$file.bak"
            echo "Backed up $HOME/$file to $HOME/$file.bak"
        fi
    done
}

# Find files that would conflict with stow
mapfile -t conflicting_files < <(stow -n -v 2 . 2>&1 | grep "CONFLICT" | grep "existing target is" | awk '{print $NF}')

if [[ ${#conflicting_files[@]} -gt 0 ]]; then
    echo "The following files will conflict with stow:"
    for file in "${conflicting_files[@]}"; do
        echo "$file"
    done

    read -p "Do you want to backup these files? (Y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        backup_files "${conflicting_files[@]}"
    fi
fi

# Install all files in this directory to the home directory
stow .
