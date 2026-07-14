#!/usr/bin/env python3
"""Reformat Markdown tables to the style required by AGENTS.md.

Every table in the input is rewritten so that:

  - column separator pipes line up (cells padded with spaces)
  - the delimiter row's dashes match the widest cell in each column
  - every cell has one space of inner padding: `| cell |`, never `|cell|`
  - GFM alignment markers are preserved and applied — `:---` pads left,
    `---:` pads right, `:--:` centers; the colons stay in the delimiter row
  - missing leading/trailing pipes and short rows are repaired
  - CJK and other wide characters count as two columns, so tables containing
    them still line up in a monospace font

Everything that is not a table — including tables inside ``` / ~~~ fenced
code blocks — passes through byte-for-byte untouched. Indentation and
blockquote prefixes (`> | a |`) in front of a table are kept.

Usage:
  cat notes.md | fix-tables.py              # stdin -> stdout (also with `-`)
  fix-tables.py README.md docs/*.md         # rewrite files in place
  fix-tables.py --stdout README.md          # print result, don't touch file
  fix-tables.py --check *.md                # report files needing fixes
  fix-tables.py --check --diff *.md         # ...and show a unified diff

Exit status: 0 all clean/fixed, 1 --check found files needing fixes,
2 bad usage or unreadable file. Stdlib only; needs Python 3.9+.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import unicodedata
from pathlib import Path

# Prefix a table row may carry: indentation and/or blockquote markers.
PREFIX_RE = re.compile(r"^([ \t]*(?:>[ \t]?)*)")
DELIMITER_CELL_RE = re.compile(r"^:?-+:?$")
FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")

MIN_COL_WIDTH = 3  # GFM needs at least one dash; 3 fits `:-:` and reads well


def display_width(text: str) -> int:
    """Monospace display width: wide/fullwidth chars count 2, combining 0."""
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _split_raw(row: str) -> list[str]:
    """Split a table row on pipes, ignoring `\\|` escapes and `` `code|spans` ``."""
    cells: list[str] = []
    buf: list[str] = []
    i, n = 0, len(row)
    while i < n:
        ch = row[i]
        if ch == "\\" and i + 1 < n:
            buf.append(row[i : i + 2])
            i += 2
        elif ch == "`":
            # A code span closes only on a backtick run of the same length.
            j = i
            while j < n and row[j] == "`":
                j += 1
            run = j - i
            k = j
            end = -1
            while k < n:
                if row[k] == "`":
                    m = k
                    while m < n and row[m] == "`":
                        m += 1
                    if m - k == run:
                        end = m
                        break
                    k = m
                else:
                    k += 1
            if end == -1:  # unclosed: the backticks are literal
                buf.append(row[i:j])
                i = j
            else:
                buf.append(row[i:end])
                i = end
        elif ch == "|":
            cells.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    cells.append("".join(buf))
    return cells


def strip_prefix(row: str) -> str:
    """Remove leading indentation / blockquote markers from a row."""
    return row[PREFIX_RE.match(row).end() :]


def split_cells(row: str) -> list[str]:
    """Cell contents of a row: pipe-split, outer empties from `| ... |` dropped."""
    cells = _split_raw(strip_prefix(row))
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [c.strip() for c in cells]


def has_pipe(row: str) -> bool:
    """True when the row contains at least one real (unescaped, non-code) pipe."""
    return len(_split_raw(row)) >= 2


def is_delimiter_row(row: str) -> bool:
    if "|" not in row:
        return False
    cells = split_cells(row)
    return bool(cells) and all(DELIMITER_CELL_RE.match(c) for c in cells)


def parse_alignment(cell: str) -> str:
    left, right = cell.startswith(":"), cell.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    if left:
        return "left"
    return "none"


def pad_cell(content: str, width: int, align: str) -> str:
    gap = width - display_width(content)
    if align == "right":
        return " " * gap + content
    if align == "center":
        return " " * (gap // 2) + content + " " * (gap - gap // 2)
    return content + " " * gap


def delimiter_cell(width: int, align: str) -> str:
    if align == "center":
        return ":" + "-" * (width - 2) + ":"
    if align == "right":
        return "-" * (width - 1) + ":"
    if align == "left":
        return ":" + "-" * (width - 1)
    return "-" * width


def format_table(prefix: str, header: str, aligns_row: str, body: list[str]) -> list[str]:
    header_cells = split_cells(header)
    aligns = [parse_alignment(c) for c in split_cells(aligns_row)]
    body_cells = [split_cells(row) for row in body]

    columns = max(len(header_cells), len(aligns), 1, *(len(r) for r in body_cells))
    aligns += ["none"] * (columns - len(aligns))

    widths = [MIN_COL_WIDTH] * columns
    for row in [header_cells, *body_cells]:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], display_width(cell))

    def render(cells: list[str]) -> str:
        cells = cells + [""] * (columns - len(cells))
        padded = [pad_cell(c, widths[i], aligns[i]) for i, c in enumerate(cells)]
        return prefix + "| " + " | ".join(padded) + " |"

    separator = prefix + "| " + " | ".join(delimiter_cell(widths[i], aligns[i]) for i in range(columns)) + " |"
    return [render(header_cells), separator, *(render(r) for r in body_cells)]


def fix_text(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    fence: str | None = None  # the run of ` or ~ that opened the current fence
    i = 0
    while i < len(lines):
        line = lines[i]
        m = FENCE_RE.match(line)
        if fence is not None:
            out.append(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line.strip(" \t" + fence[0]):
                fence = None
            i += 1
            continue
        if m:
            fence = m.group(1)
            out.append(line)
            i += 1
            continue

        if has_pipe(line) and i + 1 < len(lines) and is_delimiter_row(lines[i + 1]):
            prefix = PREFIX_RE.match(line).group(1)
            body: list[str] = []
            j = i + 2
            while j < len(lines) and has_pipe(lines[j]) and not FENCE_RE.match(lines[j]):
                body.append(lines[j])
                j += 1
            out.extend(format_table(prefix, line, lines[i + 1], body))
            i = j
            continue

        out.append(line)
        i += 1
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reformat Markdown tables (alignment-aware, code-fence-safe).",
        epilog="With no files (or `-`), reads stdin and writes stdout.",
    )
    parser.add_argument("files", nargs="*", help="Markdown files to fix in place")
    parser.add_argument("--check", action="store_true", help="don't write; exit 1 if any file needs fixing")
    parser.add_argument("--diff", action="store_true", help="print a unified diff of the changes")
    parser.add_argument("--stdout", action="store_true", help="print fixed output instead of writing files")
    args = parser.parse_args()

    if not args.files or args.files == ["-"]:
        original = sys.stdin.read()
        fixed = fix_text(original)
        if args.check:
            if args.diff and fixed != original:
                sys.stdout.writelines(difflib.unified_diff(original.splitlines(keepends=True), fixed.splitlines(keepends=True), "stdin", "fixed"))
            return 1 if fixed != original else 0
        sys.stdout.write(fixed)
        return 0

    needs_fix = False
    for name in args.files:
        path = Path(name)
        try:
            original = path.read_text(encoding="utf-8")
        except OSError as err:
            print(f"error: {err}", file=sys.stderr)
            return 2
        fixed = fix_text(original)
        if fixed == original:
            continue
        needs_fix = True
        if args.diff:
            sys.stdout.writelines(difflib.unified_diff(original.splitlines(keepends=True), fixed.splitlines(keepends=True), f"{name} (original)", f"{name} (fixed)"))
        if args.check:
            print(f"would fix: {name}")
        elif args.stdout:
            sys.stdout.write(fixed)
        else:
            path.write_text(fixed, encoding="utf-8")
            print(f"fixed: {name}")

    return 1 if (args.check and needs_fix) else 0


if __name__ == "__main__":
    sys.exit(main())
