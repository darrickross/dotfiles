#!/usr/bin/env python3
"""Move cSpell words out of VS Code settings into cspell configs.

VS Code's "Code Spell Checker" quick-fix buttons ("Add to workspace/user
settings") accumulate words in settings.json files that the cspell CLI never
reads. This script migrates them into real cspell configs, which BOTH the CLI
and the extension read:

  default mode (workspace)
      Reads ./.vscode/settings.json -> "cSpell.words" and merges it into the
      repo-level cspell config in the current directory. Prefers YAML: an
      existing config is reused whatever its format; when none exists a new
      cspell.config.yaml is created.

  --update-global-user-list <user>
      Reads the WINDOWS VS Code user settings
      (/mnt/c/Users/<user>/AppData/Roaming/Code/User/settings.json) — where
      the extension's "Add to user settings" stores words as
      "cSpell.userWords" (plus any "cSpell.words") — and merges into
      <dotfiles-root>/.config/cspell/cspell.json, the tracked file that
      home-manager deploys to ~/.config/cspell/cspell.json (the only global
      config path the cspell CLI honors; verified against cspell 9.7.0).
      Run 'hms' afterwards to deploy.

Word lists are deduplicated and sorted alphabetically (case-insensitive).
All edits are surgical text replacements, so comments and formatting in
settings.json (JSONC) and in the cspell configs survive. The one exception:
comments interleaved *between* items of a rewritten words list are dropped.

Options:
  --copy-and-delete   after merging, empty the "cSpell.words" list in the
                      source settings.json (the words now live in the config)
  --dry-run           report what would change without writing anything

Exit status: 0 on success or nothing-to-import, 1 on real errors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# The repo root is derived from this file's location (<root>/scripts/cspell/),
# so the script works from any cwd and never hardcodes the clone path.
REPO_ROOT = Path(__file__).resolve().parents[2]
GLOBAL_CONFIG = REPO_ROOT / ".config/cspell/cspell.json"
WINDOWS_SETTINGS = "/mnt/c/Users/{user}/AppData/Roaming/Code/User/settings.json"

# Workspace config candidates, YAML preferred; first match wins.
CONFIG_CANDIDATES = [
    "cspell.config.yaml",
    "cspell.config.yml",
    "cspell.yaml",
    "cspell.yml",
    ".cspell.yaml",
    "cspell.json",
    ".cspell.json",
    "cspell.config.json",
    "cSpell.json",
]
DEFAULT_WORKSPACE_CONFIG = "cspell.config.yaml"

OK = "\033[32m✓\033[0m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def warn(msg: str) -> None:
    print(f"{YELLOW}warning:{RESET} {msg}")


def error(msg: str) -> None:
    print(f"{RED}error:{RESET} {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# JSONC — parse tolerantly, edit surgically (comments must survive)
# ---------------------------------------------------------------------------


def _strip_comments(text: str) -> str:
    """Blank out // and /* */ comments (string-aware); length is preserved
    so every index into the result is valid in the original text."""
    out = list(text)
    i, n, in_str = 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            while i < end:
                if text[i] != "\n":
                    out[i] = " "
                i += 1
        else:
            i += 1
    return "".join(out)


def _strip_trailing_commas(text: str) -> str:
    """Blank out commas that directly precede } or ] (string-aware)."""
    out = list(text)
    i, n, in_str = 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                out[i] = " "
        i += 1
    return "".join(out)


def load_jsonc(text: str):
    return json.loads(_strip_trailing_commas(_strip_comments(text)))


def find_key_array_span(text: str, key: str) -> tuple[int, int] | None:
    """Span (start, end) of the [...] array that is the value of "key",
    or None. Indices are valid for the original (commented) text."""
    stripped = _strip_comments(text)
    token = f'"{key}"'
    idx = 0
    while (idx := stripped.find(token, idx)) != -1:
        j = idx + len(token)
        while j < len(stripped) and stripped[j] in " \t\r\n":
            j += 1
        if j >= len(stripped) or stripped[j] != ":":
            idx += len(token)
            continue
        j += 1
        while j < len(stripped) and stripped[j] in " \t\r\n":
            j += 1
        if j >= len(stripped) or stripped[j] != "[":
            idx += len(token)
            continue
        depth, k, in_str = 0, j, False
        while k < len(stripped):
            c = stripped[k]
            if in_str:
                if c == "\\":
                    k += 2
                    continue
                if c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return (j, k + 1)
            k += 1
        return None
    return None


def render_json_array(words: list[str], indent: str = "  ") -> str:
    if not words:
        return "[]"
    items = ",\n".join(f"{indent * 2}{json.dumps(w)}" for w in words)
    return "[\n" + items + "\n" + indent + "]"


# ---------------------------------------------------------------------------
# YAML — minimal, format-preserving handling of the `words:` block only
# ---------------------------------------------------------------------------

_YAML_ITEM = re.compile(r"""^\s+-\s+(?:"([^"]*)"|'([^']*)'|([^\s#]+))\s*(?:#.*)?$""")
_YAML_BLANK_OR_COMMENT = re.compile(r"^\s*(#.*)?$")


def yaml_find_words(text: str) -> tuple[int, int, list[str]] | None:
    """Locate the top-level `words:` entry. Returns (start, end, words) where
    text[start:end] is the whole entry (key line + items), or None."""
    m = re.search(r"(?m)^words:[ \t]*([^\n]*)$", text)
    if m is None:
        return None
    inline = m.group(1).split("#", 1)[0].strip()
    if inline.startswith("["):
        # Flow style: words: [a, b, ...] — find the matching ] and parse.
        start_br = m.start(1) + m.group(1).index("[")
        depth, k = 0, start_br
        while k < len(text):
            if text[k] == "[":
                depth += 1
            elif text[k] == "]":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        body = text[start_br + 1 : k]
        words = [w.strip().strip("'\"") for w in body.split(",") if w.strip()]
        return (m.start(), k + 1, words)
    # Block style: consume item lines that follow; blanks/comments may sit
    # between items but the block ends at the last actual item line.
    words: list[str] = []
    end = m.end()
    pos = m.end()
    if pos < len(text) and text[pos] == "\n":
        pos += 1
    while pos <= len(text):
        nl = text.find("\n", pos)
        line_end = len(text) if nl == -1 else nl
        line = text[pos:line_end]
        item = _YAML_ITEM.match(line)
        if item:
            words.append(next(g for g in item.groups() if g is not None))
            end = line_end
        elif not _YAML_BLANK_OR_COMMENT.match(line):
            break
        if nl == -1:
            break
        pos = nl + 1
    return (m.start(), end, words)


def yaml_quote(word: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", word):
        return word
    return json.dumps(word)  # a JSON string is valid YAML


def render_yaml_words(words: list[str]) -> str:
    if not words:
        return "words: []"
    return "words:\n" + "\n".join(f"  - {yaml_quote(w)}" for w in words)


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------


def sort_words(words) -> list[str]:
    return sorted(set(words), key=lambda w: (w.casefold(), w))


NEW_YAML_TEMPLATE = """\
# cspell word list for this repo — read by both the cspell CLI and the
# VS Code "Code Spell Checker" extension. Maintained by
# scripts/cspell/import-vscode-words.py (dedupes + sorts on every run).
version: "0.2"
{words}
"""

NEW_JSON_TEMPLATE = """\
{{
  "version": "0.2",
  "words": {words}
}}
"""


def merge_into_config(
    config: Path, new_words: list[str], dry_run: bool
) -> tuple[int, int]:
    """Merge new_words into config (YAML or JSON by suffix), keeping the rest
    of the file byte-identical. Returns (added_count, total_count)."""
    is_yaml = config.suffix in (".yaml", ".yml")
    text = config.read_text() if config.exists() else None

    if text is None:
        merged = sort_words(new_words)
        body = render_yaml_words(merged) if is_yaml else render_json_array(merged)
        template = NEW_YAML_TEMPLATE if is_yaml else NEW_JSON_TEMPLATE
        new_text = template.format(words=body)
        existing: list[str] = []
    elif is_yaml:
        found = yaml_find_words(text)
        existing = found[2] if found else []
        merged = sort_words(existing + new_words)
        block = render_yaml_words(merged)
        if found:
            new_text = text[: found[0]] + block + text[found[1] :]
        else:
            new_text = text.rstrip("\n") + "\n" + block + "\n"
    else:
        existing = load_jsonc(text).get("words") or []
        merged = sort_words(existing + new_words)
        span = find_key_array_span(text, "words")
        if span:
            new_text = text[: span[0]] + render_json_array(merged) + text[span[1] :]
        else:
            brace = text.rstrip().rfind("}")
            if brace == -1:
                raise ValueError(f"{config}: not a JSON object")
            before = text[:brace].rstrip()
            comma = "" if before.endswith("{") else ","
            entry = f'{comma}\n  "words": {render_json_array(merged)}\n'
            new_text = before + entry + text[brace:]

    added = len(set(merged) - set(existing))
    if not dry_run:
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(new_text)
    return added, len(merged)


def clear_source_words(source: Path, keys: list[str], dry_run: bool) -> None:
    raw = source.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    for key in keys:
        span = find_key_array_span(text, key)
        if span is None:  # verified present before calling; be safe anyway
            warn(f"{source}: could not locate the {key} array to clear")
            continue
        if dry_run:
            print(f"  would clear {key} in {source}")
            continue
        text = text[: span[0]] + "[]" + text[span[1] :]
    if not dry_run:
        source.write_bytes((("\ufeff" if bom else "") + text).encode("utf-8"))
        print(f"{OK} cleared {', '.join(keys)} in {source}")


def find_workspace_config(root: Path) -> Path:
    for name in CONFIG_CANDIDATES:
        if (root / name).is_file():
            return root / name
    return root / DEFAULT_WORKSPACE_CONFIG


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="import-vscode-words.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--update-global-user-list",
        metavar="USER",
        help="import from the Windows VS Code user settings of this Windows "
        "user into the repo's global cspell config instead",
    )
    parser.add_argument(
        "--copy-and-delete",
        action="store_true",
        help="empty the cSpell.words list in the source settings.json after merging",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report only; write nothing"
    )
    args = parser.parse_args()

    if args.update_global_user_list:
        source = Path(WINDOWS_SETTINGS.format(user=args.update_global_user_list))
        config = GLOBAL_CONFIG
        # "Add to user settings" writes cSpell.userWords in user settings.
        keys = ["cSpell.userWords", "cSpell.words"]
        deploy_hint = " — run 'hms' to deploy to ~/.config/cspell/cspell.json"
    else:
        source = Path.cwd() / ".vscode" / "settings.json"
        config = find_workspace_config(Path.cwd())
        keys = ["cSpell.words"]
        deploy_hint = ""

    if not source.is_file():
        warn(f"{source} not found — nothing to import")
        return 0

    try:
        settings = load_jsonc(source.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        error(f"{source}: cannot parse: {e}")
        return 1

    present = [k for k in keys if isinstance(settings.get(k), list)]
    words = [w for k in present for w in settings[k]]
    if not words:
        state = "empty" if present else "missing"
        print(f"{OK} {'/'.join(keys)} is {state} in {source} — nothing to import")
        return 0

    is_new = not config.exists()
    try:
        added, total = merge_into_config(config, words, args.dry_run)
    except (json.JSONDecodeError, ValueError) as e:
        error(f"{config}: cannot update: {e}")
        return 1

    action = "would add" if args.dry_run else "added"
    created = " (new file)" if is_new else ""
    print(
        f"{OK} {action} {added} word{'s' if added != 1 else ''} to "
        f"{config}{created} ({total} total, deduplicated + sorted){deploy_hint}"
    )

    if args.copy_and_delete:
        clear_source_words(source, present, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
