#!/usr/bin/env python3
"""List the misspelled words cspell finds in a folder (or single file).

Runs the cspell CLI — the same engine as the VS Code "Code Spell Checker"
extension — over the given path (default: current directory). Directories are
scanned recursively, honoring .gitignore; the nearest cspell config (e.g.
cspell.config.yaml) and the global ~/.config/cspell/cspell.json word list
apply, exactly as they do in the editor.

By default prints the unique unknown words, deduplicated and sorted — handy
for building a word list with scripts/cspell/import-vscode-words.py. Use
--full for every occurrence with file:line:column locations.

Exit status: 0 when nothing is misspelled, 1 when issues are found — safe
for CI or a pre-commit hook.

Examples:
  ./scripts/checks/spelling.py              # scan the current directory
  ./scripts/checks/spelling.py docs         # scan a folder
  ./scripts/checks/spelling.py README.md    # scan one file
  spell-check --full                        # alias deployed by home-manager

Uses cspell from PATH (installed by home-manager, see home.nix), falling
back to `nix run nixpkgs#cspell` when not on PATH.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def cspell_cmd() -> list[str]:
    if shutil.which("cspell"):
        return ["cspell"]
    return ["nix", "run", "nixpkgs#cspell", "--"]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="spelling.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="folder or file to check (default: current directory)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="show every occurrence with file:line:column instead of the unique word list",
    )
    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"error: {target} does not exist", file=sys.stderr)
        return 2

    if target.is_dir():
        cwd, globs = target, ["**"]
    else:
        cwd, globs = target.parent, [target.name]

    cmd = [*cspell_cmd(), "lint", "--no-progress", "--relative", "--gitignore"]
    if not args.full:
        cmd += ["--words-only", "--unique"]
    proc = subprocess.run([*cmd, *globs], cwd=cwd, capture_output=True, text=True)

    if proc.returncode not in (0, 1):  # cspell itself failed (bad config, ...)
        sys.stderr.write(proc.stderr)
        return proc.returncode

    if args.full:
        sys.stdout.write(proc.stdout)
    else:
        words = sorted(set(proc.stdout.split()), key=lambda w: (w.casefold(), w))
        if words:
            print("\n".join(words), flush=True)
        print(
            f"{len(words)} unknown word{'s' if len(words) != 1 else ''} in {target}",
            file=sys.stderr,
        )
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
