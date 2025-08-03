# shellcheck disable=SC2148
# Ignore the need for script to start with '#!/bin/bash' or similar
#
# ~/.bashrc: executed by bash(1) for non-login shells.
# see /usr/share/doc/bash/examples/startup-files (in the package bash-doc)
# for examples

# If not running interactively, don't do anything
case $- in
*i*) ;;
*) return ;;
esac

# How to install and apply nix home-manager
print_help_msg_install_home_manager() {
    echo
    echo "This shell is not managed by Nix Home-Manager flake"
    echo "Install and use Nix Home-Manager flake using the instructions:"

    COUNT=1

    if ! command -v nix >/dev/null 2>&1; then
        echo
        echo "$COUNT) Install Nix:"
        echo "   curl -L https://nixos.org/nix/install | sh"
        ((COUNT++))
    fi

    if ! nix-channel --list | grep -q '^home-manager'; then
        echo
        echo "$COUNT) Add Home Manager Nix Channel"
        echo "   nix-channel --add https://github.com/nix-community/home-manager/archive/release-25.11.tar.gz home-manager && nix-channel --update"
        ((COUNT++))
    fi

    if ! command -v home-manager >/dev/null 2>&1; then
        echo
        echo "$COUNT) Install Home Manager"
        echo "   nix-shell '<home-manager>' -A install"
        ((COUNT++))
    fi

    # if [ -z "$__HM_SESS_VARS_SOURCED" ]; then
    #     echo "NOT a home-manager"
    # fi

    echo
    echo "$COUNT) Run Home Manager via flakes:"
    echo "   home-manager switch --flake ~/projects/dotfiles/.config/home-manager#$(whoami) && exec \$SHELL -l"
    echo
    echo "Make sure to to remove some conflicting files first:"
    echo "   rm ~/.bash_profile"
    echo "   rm ~/.bashrc"
    echo "   rm ~/.profile"
    echo
}

# don't put duplicate lines or lines starting with space in the history.
# See bash(1) for more options
export HISTCONTROL=ignoreboth:erasedups

# append to the history file, don't overwrite it
shopt -s histappend

# for setting history length see HISTSIZE and HISTFILESIZE in bash(1)
export HISTSIZE=100000
export HISTFILESIZE=100000

# check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# Save and reload the history after each command finishes
export PROMPT_COMMAND="history -a; history -c; history -r; $PROMPT_COMMAND"

# If set, the pattern "**" used in a pathname expansion context will
# match all files and zero or more directories and subdirectories.
#shopt -s globstar

# make less more friendly for non-text input files, see lesspipe(1)
[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "${debian_chroot:-}" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# set a fancy prompt (non-color, unless we know we "want" color)
case "$TERM" in
xterm-color | *-256color) color_prompt=yes ;;
esac

# uncomment for a colored prompt, if the terminal has the capability; turned
# off by default to not distract the user: the focus in a terminal window
# should be on the output of commands, not on the prompt
force_color_prompt=yes

if [ -n "$force_color_prompt" ]; then
    if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
        # We have color support; assume it's compliant with Ecma-48
        # (ISO/IEC-6429). (Lack of such support is extremely rare, and such
        # a case would tend to support setf rather than setaf.)
        color_prompt=yes
    else
        color_prompt=
    fi
fi

if [ "$color_prompt" = yes ]; then
    PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
else
    PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '
fi
unset color_prompt force_color_prompt

# If this is an xterm set the title to user@host:dir
case "$TERM" in
xterm* | rxvt*)
    PS1="\[\e]0;${debian_chroot:+($debian_chroot)}\u@\h: \w\a\]$PS1"
    ;;
*) ;;
esac

# enable color support of ls and also add handy aliases
if [ -x /usr/bin/dircolors ]; then
    # shellcheck disable=SC2015
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    #alias dir='dir --color=auto'
    #alias vdir='vdir --color=auto'

    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# colored GCC warnings and errors
#export GCC_COLORS='error=01;31:warning=01;35:note=01;36:caret=01;32:locus=01:quote=01'

# some more ls aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# Add an "alert" alias for long running commands.  Use like so:
#   sleep 10; alert
alias alert='notify-send --urgency=low -i "$([ $? = 0 ] && echo terminal || echo error)" "$(history|tail -n1|sed -e '\''s/^\s*[0-9]\+\s*//;s/[;&|]\s*alert$//'\'')"'

# Alias definitions.
# You may want to put all your additions into a separate file like
# ~/.bash_aliases, instead of adding them here directly.
# See /usr/share/doc/bash-doc/examples in the bash-doc package.

if [ -f ~/.bash_aliases ]; then
    # shellcheck disable=SC1090
    . ~/.bash_aliases
fi

# enable programmable completion features (you don't need to enable
# this, if it's already enabled in /etc/bash.bashrc and /etc/profile
# sources /etc/bash.bashrc).
if ! shopt -oq posix; then
    if [ -f /usr/share/bash-completion/bash_completion ]; then
        # shellcheck disable=SC1091
        . /usr/share/bash-completion/bash_completion
    elif [ -f /etc/bash_completion ]; then
        # shellcheck disable=SC1091
        . /etc/bash_completion
    fi
fi

# ==============================================================================
# WSL only things
# ==============================================================================
if grep -qEi "(Microsoft|WSL)" /proc/version &>/dev/null; then
    # Make clipboard easier to paste to
    alias clipboard="/mnt/c/WINDOWS/system32/clip.exe"

    # Add ssh-sk-helper for WSL
    export SSH_SK_HELPER="/mnt/c/Program Files/OpenSSH/ssh-sk-helper.exe"

    alias gpg="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpg.exe"
    alias gpg-agent="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpg-agent.exe"
    alias gpg-connect-agent="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpg-connect-agent.exe"
    alias gpg-wks-client="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpg-wks-client.exe"
    alias gpgconf="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpgconf.exe"
    # alias gpgparsemail=""
    alias gpgsm="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpgsm.exe"
    # alias gpgsplit=""
    alias gpgtar="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpgtar.exe"
    alias gpgv="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpgv.exe"
fi

# This has the exact same condition as above, but needs to be separate
# Because if its in the same parsing group it won't call the alias version of gpgconf
# https://www.shellcheck.net/wiki/SC2262
if grep -qEi "(Microsoft|WSL)" /proc/version &>/dev/null; then
    GPG_AGENT_SOCK=$(wslpath -u "$(gpgconf --list-dirs agent-socket | tr -d '\r')")
    export GPG_AGENT_SOCK
    export SSH_AUTH_SOCK=$GPG_AGENT_SOCK
fi

# Set Python 3 as default
alias python='python3'

# Make sure ~/.local/bin is in PATH
# oh-my-posh is installed in ~/.local/bin
USERS_LOCAL_BIN="$HOME/.local/bin"

if [ -d "$USERS_LOCAL_BIN" ] && [[ ":$PATH:" != *":$USERS_LOCAL_BIN:"* ]]; then
    export PATH="$USERS_LOCAL_BIN:$PATH"
fi

# If oh-my-posh is installed, use it
# Otherwise, use custom bash prompt in PS1
if oh-my-posh --version >/dev/null 2>&1; then

    # Use oh-my-posh
    eval "$(oh-my-posh init bash --config ~/.config/ohmyposh/bash_prompt.toml)"

else

    package_manager="apt"

    if dnf --version >/dev/null 2>&1; then
        package_manager="dnf"
    fi

    echo "Oh-My-Posh not found. https://ohmyposh.dev/docs/installation/prompt"
    echo "Install cmd:"
    echo
    echo "   sudo $package_manager install -y curl unzip"
    echo "   curl -s https://ohmyposh.dev/install.sh | bash -s"

    # Custom prompt
    # [HH:MM:SS][ExitCode][Hostname]@Username:WorkingDirectory$_
    export PS1='[\[\e[32m\]\t\[\e[0m\]][\[\e[91m\]$?\[\e[0m\]]\[\e[35m\]\h\[\e[0m\]@\[\e[36m\]\u\[\e[0m\]:\[\e[33m\]\w\[\e[0m\]\\$\[\e[35m\] \[\e[0m\]'
fi

# Fast Simple Node Manager
FNM_PATH="/home/itsjustmech/.local/share/fnm"
if [ -d "$FNM_PATH" ]; then
    export PATH="$FNM_PATH:$PATH"
    eval "$(fnm env)"
fi

# Include nix in my shell if it exists
if [ -e "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then
    # shellcheck disable=SC1091
    . "$HOME/.nix-profile/etc/profile.d/nix.sh"
fi

# Configure Nix Home Manager
if [ -e "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
    # Home Manager is already active in this shell
    # shellcheck disable=SC1091
    . "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
fi

# Check if the shell is currently managed by home-manager
if [[ -L "$HOME/.bashrc" ]]; then
    LINK_TARGET=$(readlink "$HOME/.bashrc")
    if [[ "$LINK_TARGET" != /nix/store/*-home-manager-files/.bashrc ]]; then
        print_help_msg_install_home_manager
    fi
fi
