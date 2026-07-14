#!/usr/bin/env python3
"""Validation checks for this dotfiles repo.

Runs the same checks Claude/agents and humans should run after editing the
home-manager config, without applying anything:

  fmt      nixfmt --check every git-tracked .nix file
  eval     evaluate the flake's homeConfigurations (catches syntax errors,
           failed assertions, references to untracked files)
  scripts  render every executable home.file script from the flake and run
           `bash -n` + shellcheck on the exact text home-manager would
           deploy; also `bash -n` the generated programs.bash.initExtra
  all      everything above (the default when no command is given)

The flake is evaluated through `git+file://` (not a plain path) on purpose:
that is how the flake sees the repo for real, so files that were never
`git add`ed are invisible and correctly reported as errors here instead of
surfacing later during `hms`.

Exit status: 0 when every check passes, 1 otherwise — safe for CI or a
pre-commit hook.

Examples:
  ./scripts/checks/check.py            # run everything
  ./scripts/checks/check.py fmt        # only formatting
  ./scripts/checks/check.py scripts    # only the rendered-script lints
  dotfiles-check                       # alias deployed by home-manager

Requires nix, nixfmt, shellcheck, git, and bash on PATH — all of which
home-manager installs (see .config/home-manager/home.nix).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# The repo root is derived from this file's location (<root>/scripts/checks/),
# so the script works from any cwd and never hardcodes the clone path.
ROOT = Path(__file__).resolve().parents[2]
FLAKE = f"git+file://{ROOT}?dir=.config/home-manager"

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, capturing output; never raises on non-zero exit."""
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kwargs)


def clean_stderr(text: str) -> str:
    """Drop the noisy-but-harmless 'Git tree is dirty' warning from nix."""
    lines = [l for l in text.splitlines() if "Git tree" not in l or "dirty" not in l]
    return "\n".join(lines).strip()


def nix_eval(installable: str, *extra: str) -> subprocess.CompletedProcess:
    return run(["nix", "eval", installable, *extra])


def report(ok: bool, label: str, detail: str = "") -> bool:
    print(f"{PASS if ok else FAIL} {label}")
    if not ok and detail:
        print("\n".join(f"    {l}" for l in detail.splitlines()))
    return ok


def home_config_names() -> list[str]:
    """Return the attribute names under homeConfigurations (usually one)."""
    proc = nix_eval(f"{FLAKE}#homeConfigurations", "--json", "--apply", "builtins.attrNames")
    if proc.returncode != 0:
        sys.exit(f"error: cannot list homeConfigurations:\n{clean_stderr(proc.stderr)}")
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_fmt() -> bool:
    """nixfmt --check every git-tracked .nix file."""
    ls = run(["git", "ls-files", "*.nix"])
    files = ls.stdout.split()
    if not files:
        return report(False, "fmt: no tracked .nix files found")
    proc = run(["nixfmt", "--check", *files])
    return report(
        proc.returncode == 0,
        f"fmt: nixfmt --check on {len(files)} .nix files",
        (proc.stdout + proc.stderr).strip(),
    )


def check_eval() -> bool:
    """Evaluate each homeConfiguration's activation package (no build)."""
    ok = True
    for name in home_config_names():
        proc = nix_eval(f"{FLAKE}#homeConfigurations.{name}.activationPackage.drvPath")
        ok &= report(
            proc.returncode == 0,
            f"eval: homeConfigurations.{name} evaluates",
            clean_stderr(proc.stderr),
        )
    return ok


def check_scripts() -> bool:
    """Lint the rendered text of every executable home.file bash script.

    The text is taken from the evaluated flake — the exact bytes home-manager
    would deploy — so nix-level escaping mistakes (''${ vs ${) are caught,
    not just problems in the repo source.
    """
    ok = True
    # Select executable home.file entries defined inline via `text` (entries
    # using `source` point at files already tracked in the repo and are not
    # rendered scripts). builtins only — lib is unavailable in --apply.
    select = (
        "fs: builtins.listToAttrs (map (n: { name = n; value = fs.${n}.text; })"
        " (builtins.filter (n: ((fs.${n}.executable or false) == true)"
        " && ((fs.${n}.text or null) != null)) (builtins.attrNames fs)))"
    )
    for name in home_config_names():
        cfg = f"{FLAKE}#homeConfigurations.{name}.config"
        proc = nix_eval(f"{cfg}.home.file", "--json", "--apply", select)
        if proc.returncode != 0:
            ok &= report(False, f"scripts: render home.file for {name}", clean_stderr(proc.stderr))
            continue
        scripts: dict[str, str] = json.loads(proc.stdout)

        with tempfile.TemporaryDirectory(prefix="dotfiles-check.") as tmpdir:
            for path, text in sorted(scripts.items()):
                first_line = text.splitlines()[0] if text else ""
                if "bash" not in first_line and "sh" not in first_line:
                    print(f"{PASS} scripts: {path} (non-shell shebang, skipped)")
                    continue
                tmp = Path(tmpdir) / path.replace("/", "_")
                tmp.write_text(text)
                syn = run(["bash", "-n", str(tmp)])
                lint = run(["shellcheck", "--shell=bash", str(tmp)])
                detail = (syn.stderr + lint.stdout + lint.stderr).strip()
                ok &= report(
                    syn.returncode == 0 and lint.returncode == 0,
                    f"scripts: {path} (bash -n + shellcheck)",
                    detail,
                )

            # initExtra is a fragment of the generated .bashrc, not a
            # standalone script — syntax-check it, but skip shellcheck,
            # which assumes a whole script and flags fragment idioms.
            proc = nix_eval(f"{cfg}.programs.bash.initExtra", "--raw")
            if proc.returncode != 0:
                ok &= report(False, "scripts: render programs.bash.initExtra", clean_stderr(proc.stderr))
            else:
                tmp = Path(tmpdir) / "initExtra"
                tmp.write_text(proc.stdout)
                syn = run(["bash", "-n", str(tmp)])
                ok &= report(
                    syn.returncode == 0,
                    "scripts: programs.bash.initExtra (bash -n)",
                    syn.stderr.strip(),
                )
    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

CHECKS = {
    "fmt": check_fmt,
    "eval": check_eval,
    "scripts": check_scripts,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="check.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "check",
        nargs="?",
        default="all",
        choices=[*CHECKS, "all"],
        help="which check to run (default: all)",
    )
    args = parser.parse_args()

    selected = CHECKS.values() if args.check == "all" else [CHECKS[args.check]]
    ok = all([fn() for fn in selected])  # list() so every check runs
    print("\nAll checks passed." if ok else "\nSome checks FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
