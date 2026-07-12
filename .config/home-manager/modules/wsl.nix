# WSL2 integration: clipboard helper, hardware-key SSH, and GPG via the
# Windows-side GnuPG installation.
#
# Two separate `if` blocks are intentional: the GPG socket detection calls
# `gpgconf`, which must resolve to the aliased Windows binary set in the
# first block.  Merging them into one block would cause SC2262 (alias not
# yet in effect).  See https://www.shellcheck.net/wiki/SC2262
{ ... }:
{
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
