# Shell prompt: oh-my-posh when available, minimal colour PS1 as fallback.
{ ... }:
{
  programs.bash.initExtra = ''
    # Debian-chroot indicator (set by /etc/debian_chroot when inside a chroot).
    if [ -z "''${debian_chroot:-}" ] && [ -r /etc/debian_chroot ]; then
      debian_chroot=$(cat /etc/debian_chroot)
    fi

    if oh-my-posh --version >/dev/null 2>&1; then
      eval "$(oh-my-posh init bash --config ~/.config/ohmyposh/bash_prompt.toml)"
    else
      # Fallback: [HH:MM:SS][ExitCode][Hostname]@Username:WorkingDirectory$
      export PS1='[''${debian_chroot:+(''${debian_chroot})}\[\e[32m\]\t\[\e[0m\]][\[\e[91m\]$?\[\e[0m\]]\[\e[35m\]\h\[\e[0m\]@\[\e[36m\]\u\[\e[0m\]:\[\e[33m\]\w\[\e[0m\]\$\[\e[35m\] \[\e[0m\]'

      package_manager="apt"
      if dnf --version >/dev/null 2>&1; then
        package_manager="dnf"
      fi

      echo "Oh-My-Posh not found. https://ohmyposh.dev/docs/installation/prompt" >&2
      echo "Install cmd:" >&2
      echo >&2
      echo "   sudo $package_manager install -y curl unzip" >&2
      echo "   curl -s https://ohmyposh.dev/install.sh | bash -s" >&2
    fi
  '';
}
