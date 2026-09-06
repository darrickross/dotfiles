# A dedicated Windows Firefox profile for yt-dlp cookie extraction.
#
# Why a separate profile at all: yt-dlp's --cookies-from-browser reads
# cookies.sqlite off disk, and sites like YouTube rotate session cookies as
# you keep browsing — so cookies lifted from the profile you actually use go
# stale quickly. A profile that is only ever logged in and then left alone
# does not rotate, so one login keeps working. It also keeps a throwaway
# scraping login out of the primary browsing session (Firefox 67+ runs
# profiles as concurrent instances, so opening it disturbs nothing).
#
# Why not programs.firefox: that manages a *Linux* Firefox profile under
# ~/.mozilla. The browser here is the Windows install, and its profile lives
# under %APPDATA% on the Windows side — outside anything home-manager can
# declare. So this module ships two small scripts instead, and the profile is
# created lazily on first use rather than at activation time: `hms` should not
# depend on Windows interop being healthy, and a lazily created profile also
# repairs itself if the profile is ever deleted from the Firefox UI.
{ lib, ... }:
let
  # Single source of truth for the Windows-side Firefox install, matching the
  # gpg4win convention in ./wsl.nix. Change here only if Firefox moves.
  firefoxWin = "/mnt/c/Program Files/Mozilla Firefox/firefox.exe";

  # The profile name as it appears in Firefox's profile manager (`firefox -P`).
  profileName = "ytdlp";
in
{
  # Prints the WSL path of the dedicated profile directory, creating the
  # profile first if it does not exist yet. Kept separate from the yt-dlp
  # wrapper below so the path is also usable on its own — e.g. to pass a
  # container with yt-dlp's `firefox:PROFILE::CONTAINER` syntax.
  #
  # The directory name cannot be baked in at build time: Firefox prefixes it
  # with a random 8-character salt (Profiles/<salt>.ytdlp) chosen at creation,
  # and picks a fresh one if the profile is ever recreated. Likewise the
  # Windows username is unknown to nix, so %APPDATA% is resolved at runtime.
  home.file.".local/bin/firefox-ytdlp-profile" = {
    executable = true;
    force = true;
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      FIREFOX="${firefoxWin}"
      PROFILE_NAME="${profileName}"

      if [[ ! -x "$FIREFOX" ]]; then
        echo "firefox-ytdlp-profile: Windows Firefox not found at $FIREFOX" >&2
        echo "  Update firefoxWin in modules/firefox-ytdlp.nix if it moved." >&2
        exit 1
      fi

      # cmd.exe is run from /mnt/c so it does not warn about a UNC working
      # directory; the trailing \r of its CRLF output has to go before wslpath.
      APPDATA_WIN=$(cd /mnt/c && cmd.exe /c 'echo %APPDATA%' 2>/dev/null | tr -d '\r')
      if [[ -z "$APPDATA_WIN" ]]; then
        echo "firefox-ytdlp-profile: could not read %APPDATA% via cmd.exe" >&2
        exit 1
      fi
      FF_DIR="$(wslpath -u "$APPDATA_WIN")/Mozilla/Firefox"
      INI="$FF_DIR/profiles.ini"

      # Read the Path= of the section whose Name= matches PROFILE_NAME. The two
      # keys may appear in either order, so both are collected per section and
      # tested after each line; a leading [Section] resets them. Every line is
      # stripped of its CR because profiles.ini is CRLF.
      resolve_path() {
        [[ -f "$INI" ]] || return 0
        awk -v want="$PROFILE_NAME" '
          { sub(/\r$/, "") }
          /^\[/       { name = ""; path = "" }
          /^Name=/    { name = substr($0, 6) }
          /^Path=/    { path = substr($0, 6) }
          name == want && path != "" { print path; exit }
        ' "$INI"
      }

      REL=$(resolve_path)

      if [[ -z "$REL" ]]; then
        # -CreateProfile exits immediately without opening a window, and works
        # even while other Firefox instances are running.
        "$FIREFOX" -CreateProfile "$PROFILE_NAME" >/dev/null 2>&1 || true

        # Firefox writes profiles.ini from the Windows side a moment later.
        for _ in $(seq 1 20); do
          REL=$(resolve_path)
          [[ -n "$REL" ]] && break
          sleep 0.5
        done

        if [[ -z "$REL" ]]; then
          echo "firefox-ytdlp-profile: failed to create profile '$PROFILE_NAME'" >&2
          echo "  Create it by hand:  '$FIREFOX' -P" >&2
          exit 1
        fi
      fi

      # Path= is relative to the Firefox data dir when IsRelative=1 (the normal
      # case, and always so for profiles Firefox creates itself). An absolute
      # value is a Windows path and needs translating.
      if [[ "$REL" == ?:* || "$REL" == *\\* ]]; then
        PROFILE_DIR=$(wslpath -u "$REL")
      else
        PROFILE_DIR="$FF_DIR/$REL"
      fi

      if [[ ! -d "$PROFILE_DIR" ]]; then
        echo "firefox-ytdlp-profile: profiles.ini points at a missing directory:" >&2
        echo "  $PROFILE_DIR" >&2
        exit 1
      fi

      printf '%s\n' "$PROFILE_DIR"
    '';
  };

  # yt-dlp with cookies taken from the dedicated profile. Any extra arguments
  # are forwarded, so this is a drop-in replacement for `yt-dlp`.
  #
  # Note that cookies are only as fresh as the last time that profile was
  # logged in, and that yt-dlp copies cookies.sqlite without its -wal sidecar:
  # quit the ytdlp profile before running this or very recent cookie writes
  # can be missed. The profile is a real credential store — its contents are a
  # logged-in session — so treat the directory as sensitive.
  home.file.".local/bin/yt-dlp-cookies" = {
    executable = true;
    force = true;
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      if [[ ''${1-} == "--help" || $# -eq 0 ]]; then
        cat >&2 <<'USAGE'
      yt-dlp-cookies — yt-dlp using the dedicated "ytdlp" Firefox profile.

        yt-dlp-cookies [YT-DLP OPTIONS] URL...

      The profile is created on first use if missing. Log into it once with
      `firefox-ytdlp-profile` to get its path, or launch it directly:

        '${firefoxWin}' -P ${profileName}

      Use a normal window, not a private one: private-window cookies are held
      in memory and never written to disk, so no tool can read them back.
      USAGE
        [[ $# -eq 0 ]] && exit 1
        exit 0
      fi

      PROFILE_DIR=$(firefox-ytdlp-profile)

      exec yt-dlp --cookies-from-browser "firefox:$PROFILE_DIR" "$@"
    '';
  };

  # This module forwards to Windows-side Firefox and is meaningless off WSL2.
  # Fail `home-manager switch` up front rather than deploying scripts that
  # would only break at first use — same rationale as assertWsl in ./wsl.nix.
  home.activation.assertWslFirefox = lib.hm.dag.entryBefore [ "writeBoundary" ] ''
    if ! grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
      errorEcho "modules/firefox-ytdlp.nix: this machine does not look like WSL2."
      errorEcho "This module drives the Windows Firefox install for yt-dlp cookies;"
      errorEcho "remove ./modules/firefox-ytdlp.nix from the imports in home.nix."
      exit 1
    fi
  '';
}
