# Shell prompt: oh-my-posh when available, minimal colour PS1 as fallback.
{ ... }:
{
  programs.bash.initExtra = ''
    # Debian-chroot indicator (set by /etc/debian_chroot when inside a chroot).
    if [ -z "''${debian_chroot:-}" ] && [ -r /etc/debian_chroot ]; then
      debian_chroot=$(cat /etc/debian_chroot)
    fi

    # oh-my-posh is installed via home.packages, so the fallback only fires
    # if the home-manager environment is broken or not yet on PATH.
    if oh-my-posh --version >/dev/null 2>&1; then
      eval "$(oh-my-posh init bash --config ~/.config/ohmyposh/bash_prompt.toml)"
    else
      # Fallback: [HH:MM:SS][ExitCode][Hostname]@Username:WorkingDirectory$
      export PS1='[''${debian_chroot:+(''${debian_chroot})}\[\e[32m\]\t\[\e[0m\]][\[\e[91m\]$?\[\e[0m\]]\[\e[35m\]\h\[\e[0m\]@\[\e[36m\]\u\[\e[0m\]:\[\e[33m\]\w\[\e[0m\]\$\[\e[35m\] \[\e[0m\]'
      echo "oh-my-posh not found (it should be installed by home-manager — run 'hms')" >&2
    fi
  '';
}
