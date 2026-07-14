# WSL2 integration: clipboard helper, hardware-key SSH, YubiKey age plugin,
# and GPG via the Windows-side GnuPG installation.
#
# Two separate `if` blocks are intentional: the GPG socket detection calls
# `gpgconf`, which must resolve to the aliased Windows binary set in the
# first block.  Merging them into one block would cause SC2262 (alias not
# yet in effect).  See https://www.shellcheck.net/wiki/SC2262
{ config, lib, ... }:
let
  # Single source of truth for the Windows Gpg4win install location — used
  # by the gpg wrapper and every alias below. If Gpg4win moves (e.g. a
  # future installer drops the "(x86)" directory), change it here only.
  gpg4win = "/mnt/c/Program Files (x86)/GnuPG/bin";
in
{
  # This module forwards YubiKey/GPG/SSH operations to Windows-side binaries
  # and is meaningless off WSL2. Fail `home-manager switch` up front (before
  # any files are written) instead of deploying wrappers that would break at
  # first use. Nix `assertions` evaluate purely and cannot inspect the
  # machine, so this is an activation-time check instead.
  home.activation.assertWsl = lib.hm.dag.entryBefore [ "writeBoundary" ] ''
    if ! grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
      errorEcho "modules/wsl.nix: this machine does not look like WSL2 (/proc/version)."
      errorEcho "This module forwards YubiKey/GPG operations to Windows binaries;"
      errorEcho "remove ./modules/wsl.nix from the imports in home.nix on non-WSL machines."
      exit 1
    fi
  '';

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
  # not through an interactive shell.  The non-WSL fallthrough to the first
  # real gpg on PATH is defense in depth: the assertWsl check above means
  # home-manager never deploys this module off WSL, but a hand-copied
  # wrapper still degrades gracefully.
  home.file.".local/bin/gpg" = {
    executable = true;
    force = true;
    text = ''
      #!/usr/bin/env bash
      if grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
        exec "${gpg4win}/gpg.exe" "$@"
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

  # git needs an absolute path to the gpg wrapper — PATH is not reliable for
  # non-interactive git invocations (IDEs, hooks) — but the home directory
  # differs per machine. The tracked .gitconfig therefore [include]s this
  # generated file instead of hardcoding the path; git silently skips the
  # include on machines where wsl.nix (and thus this file) is absent.
  home.file.".gitconfig.local" = {
    force = true;
    text = ''
      [gpg]
          program = ${config.home.homeDirectory}/.local/bin/gpg
    '';
  };

  programs.bash.initExtra = ''
    if grep -qEi "(Microsoft|WSL)" /proc/version &>/dev/null; then

      # Pipe text to the Windows clipboard.
      alias clipboard="/mnt/c/WINDOWS/system32/clip.exe"

      # Hardware-backed SSH key support via Windows OpenSSH.
      export SSH_SK_HELPER="/mnt/c/Program Files/OpenSSH/ssh-sk-helper.exe"

      # Route all GPG operations through the Windows GnuPG installation.
      # The single quotes end up inside the alias value so the space- and
      # paren-containing path stays one word when the alias expands.
      alias gpg="'${gpg4win}/gpg.exe'"
      alias gpg-agent="'${gpg4win}/gpg-agent.exe'"
      alias gpg-connect-agent="'${gpg4win}/gpg-connect-agent.exe'"
      alias gpg-wks-client="'${gpg4win}/gpg-wks-client.exe'"
      alias gpgconf="'${gpg4win}/gpgconf.exe'"
      alias gpgsm="'${gpg4win}/gpgsm.exe'"
      alias gpgtar="'${gpg4win}/gpgtar.exe'"
      alias gpgv="'${gpg4win}/gpgv.exe'"

    fi

    # Must be a separate block so the gpgconf alias above is already active.
    if grep -qEi "(Microsoft|WSL)" /proc/version &>/dev/null; then
      GPG_AGENT_SOCK=$(wslpath -u "$(gpgconf --list-dirs agent-socket | tr -d '\r')")
      export GPG_AGENT_SOCK
      export SSH_AUTH_SOCK=$GPG_AGENT_SOCK
    fi
  '';
}
