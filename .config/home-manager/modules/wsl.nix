# WSL2 integration: clipboard helper, hardware-key SSH, YubiKey age plugin,
# and GPG via the Windows-side GnuPG installation.
#
# Two separate `if` blocks are intentional: the GPG socket detection calls
# `gpgconf`, which must resolve to the aliased Windows binary set in the
# first block.  Merging them into one block would cause SC2262 (alias not
# yet in effect).  See https://www.shellcheck.net/wiki/SC2262
{ ... }:
{
  # age-plugin-yubikey wrapper: forwards to the Windows host binary so that
  # age/sops in WSL2 can discover it via PATH.  A shell alias won't work
  # because age plugin discovery requires a real executable named
  # "age-plugin-<name>" on PATH.
  home.file.".local/bin/age-plugin-yubikey" = {
    executable = true;
    force = true;
    text = ''
      #!/usr/bin/env bash
      exec "/mnt/c/Program Files/age-plugin-yubikey/age-plugin-yubikey.exe" "$@"
    '';
  };

  # gpg wrapper: git's gpg.program (see .gitconfig) points here so commit
  # signing reaches the Windows Gpg4win install (and the YubiKey) from WSL2.
  # The interactive alias below is not enough — git invokes gpg directly,
  # not through an interactive shell.  On non-WSL machines the wrapper falls
  # through to the first real gpg on PATH, keeping .gitconfig portable.
  home.file.".local/bin/gpg" = {
    executable = true;
    force = true;
    text = ''
      #!/usr/bin/env bash
      if grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
        exec "/mnt/c/Program Files (x86)/GnuPG/bin/gpg.exe" "$@"
      fi

      # Not WSL: run the first gpg on PATH that is not this wrapper.
      SELF=$(readlink -f "''${BASH_SOURCE[0]}")
      while IFS= read -r CANDIDATE; do
        [[ $(readlink -f "$CANDIDATE") == "$SELF" ]] && continue
        exec "$CANDIDATE" "$@"
      done < <(type -ap gpg)

      echo "gpg: no gpg executable found on PATH besides this wrapper" >&2
      exit 127
    '';
  };

  programs.bash.initExtra = ''
    if grep -qEi "(Microsoft|WSL)" /proc/version &>/dev/null; then

      # Pipe text to the Windows clipboard.
      alias clipboard="/mnt/c/WINDOWS/system32/clip.exe"

      # Hardware-backed SSH key support via Windows OpenSSH.
      export SSH_SK_HELPER="/mnt/c/Program Files/OpenSSH/ssh-sk-helper.exe"

      # Route all GPG operations through the Windows GnuPG installation.
      alias gpg="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpg.exe"
      alias gpg-agent="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpg-agent.exe"
      alias gpg-connect-agent="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpg-connect-agent.exe"
      alias gpg-wks-client="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpg-wks-client.exe"
      alias gpgconf="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpgconf.exe"
      alias gpgsm="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpgsm.exe"
      alias gpgtar="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpgtar.exe"
      alias gpgv="/mnt/c/Program\ Files\ \(x86\)/GnuPG/bin/gpgv.exe"

    fi

    # Must be a separate block so the gpgconf alias above is already active.
    if grep -qEi "(Microsoft|WSL)" /proc/version &>/dev/null; then
      GPG_AGENT_SOCK=$(wslpath -u "$(gpgconf --list-dirs agent-socket | tr -d '\r')")
      export GPG_AGENT_SOCK
      export SSH_AUTH_SOCK=$GPG_AGENT_SOCK
    fi
  '';
}
