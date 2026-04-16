#!/usr/bin/env python3
"""
Rename media files to match the format: Title (YYYY).<RES>.<ENC>.<EXT>

Scans for .mkv/.mp4 files that don't already conform, pulls resolution and
codec from ffprobe where needed, then presents a table of proposed renames
before asking whether to apply them.
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich import box

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ---------------------------------------------------------------------------
# ANSI helpers (used for non-table output regardless of rich availability)
# ---------------------------------------------------------------------------


class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @staticmethod
    def red(s: str) -> str:
        return f"{C.RED}{s}{C.RESET}"

    @staticmethod
    def green(s: str) -> str:
        return f"{C.GREEN}{s}{C.RESET}"

    @staticmethod
    def yellow(s: str) -> str:
        return f"{C.YELLOW}{s}{C.RESET}"

    @staticmethod
    def cyan(s: str) -> str:
        return f"{C.CYAN}{s}{C.RESET}"

    @staticmethod
    def magenta(s: str) -> str:
        return f"{C.MAGENTA}{s}{C.RESET}"

    @staticmethod
    def blue(s: str) -> str:
        return f"{C.BLUE}{s}{C.RESET}"

    @staticmethod
    def bold(s: str) -> str:
        return f"{C.BOLD}{s}{C.RESET}"

    @staticmethod
    def dim(s: str) -> str:
        return f"{C.DIM}{s}{C.RESET}"


# ---------------------------------------------------------------------------
# Constants / lookup tables
# ---------------------------------------------------------------------------

CODEC_NORMALIZE: dict[str, str] = {
    "hevc": "hevc",
    "h265": "hevc",
    "x265": "hevc",
    "libx265": "hevc",
    "h264": "h264",
    "avc": "h264",
    "avc1": "h264",
    "x264": "h264",
    "libx264": "h264",
    "av1": "av1",
    "vp9": "vp9",
}

# Regex for the fully-correct filename format
# Groups: 1=title, 2=year, 3=episode(optional, incl. name), 4=res, 5=codec, 6=tail(optional), 7=tail-suffix, 8=ext
# Episode group captures e.g. " - s01e01" or " - s01e01-e05 - Episode Name"
FULL_PATTERN = re.compile(
    r"^(.+?)\s*\((\d{4})\)( - s\d+e[\de-]+(?:\s+-\s+[^.]+)?)?\.(4k|\d{3,4}p)\.([\w]+)( \{[^}]+\}( - pt\d+)?)?\.(mkv|mp4)$",
    re.IGNORECASE,
)

# Regexes for extracting individual parts from arbitrary filenames
_RE_YEAR = re.compile(r"\((\d{4})\)")
_RE_RES = re.compile(r"\b(4k|2160p|\d{3,4}p)\b", re.IGNORECASE)
_RE_CODEC = re.compile(r"\b(h264|hevc|h265|x264|x265|av1|vp9|avc)\b", re.IGNORECASE)
# Episode: " - s01e01" or " - s01e01-e05 - Episode Name"
_RE_EPISODE = re.compile(r"( - s\d+e[\de-]+(?:\s+-\s+[^()\[\]{}.]+)?)", re.IGNORECASE)
# Tail: " {anything}" optionally followed by " - ptN", must be at end of stem
_RE_TAIL = re.compile(r"( \{[^}]+\}( - pt\d+)?)$")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MediaFile:
    path: Path
    ext: str = ""
    title: str | None = None
    year: str | None = None
    resolution: str | None = None
    codec: str | None = None
    episode: str = ""  # e.g. " - s01e01" or " - s01e01-e05"
    tail: str = ""  # e.g. " {edition-Theatrical}" or " {edition-DC} - pt1"
    folder_match: bool | None = None  # None = not evaluated
    proposed_name: str | None = None
    missing_parts: list[str] = field(default_factory=list)
    already_correct: bool = False
    skip_reason: str | None = None

    def needs_rename(self) -> bool:
        return (
            not self.already_correct
            and self.proposed_name is not None
            and self.proposed_name != self.path.name
        )


# ---------------------------------------------------------------------------
# ffprobe
# ---------------------------------------------------------------------------


def get_ffprobe_info(path: Path) -> tuple[str | None, str | None, str | None]:
    """Return (codec, resolution, error) via ffprobe. On failure, codec and resolution are None."""
    try:
        base_args = [
            "ffprobe",
            "-v",
            "error",
            "-probesize",
            "5000000",
            "-analyzeduration",
            "0",
            "-select_streams",
            "v:0",
        ]
        r_codec = subprocess.run(
            [
                *base_args,
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        r_height = subprocess.run(
            [
                *base_args,
                "-show_entries",
                "stream=height",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        codec_raw = r_codec.stdout.strip().lower()
        height_str = r_height.stdout.strip()

        if not codec_raw or not height_str:
            return None, None, "ffprobe found no video stream"

        codec = CODEC_NORMALIZE.get(codec_raw, codec_raw)
        height = int(height_str)
        res = "4k" if height >= 2160 else f"{height}p"
        return codec, res, None
    except subprocess.TimeoutExpired:
        return None, None, "ffprobe timed out"
    except Exception as e:
        return None, None, f"ffprobe error: {e}"


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------


def extract_title(stem: str) -> str:
    """Best-effort: strip year/res/codec tokens, replace separators with spaces."""
    s = stem

    # Strip everything from (YYYY) onwards
    s = re.sub(r"\s*\(\d{4}\).*", "", s)

    # Strip resolution + everything after
    s = re.sub(r"[\.\s\-](4k|2160p|\d{3,4}p)[\.\s\-].*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[\.\s\-](4k|2160p|\d{3,4}p)$", "", s, flags=re.IGNORECASE)

    # Strip codec + everything after
    s = re.sub(
        r"[\.\s\-](h264|hevc|h265|x264|x265|av1|vp9|avc)[\.\s\-].*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"[\.\s\-](h264|hevc|h265|x264|x265|av1|vp9|avc)$", "", s, flags=re.IGNORECASE
    )

    # Replace dots/underscores with spaces
    s = re.sub(r"[\._]+", " ", s)

    return s.strip(" .-_")


def normalize_resolution(res: str) -> str:
    return "4k" if res.lower() in ("2160p", "4k") else res.lower()


def folder_matches_title(path: Path, title: str) -> bool:
    def norm(s: str) -> str:
        s = re.sub(r"\s*\(\d{4}\)", "", s)  # drop (year)
        s = re.sub(r"[\s\._\-]+", " ", s)
        return s.strip().lower()

    return norm(path.parent.name) == norm(title)


# ---------------------------------------------------------------------------
# File analysis
# ---------------------------------------------------------------------------


def analyze_file(path: Path, verbose: bool = False) -> MediaFile:
    ext = path.suffix.lstrip(".").lower()
    stem = path.stem
    media = MediaFile(path=path, ext=ext)

    # Already correct?
    m = FULL_PATTERN.match(path.name)
    if m:
        media.title = m.group(1).strip()
        media.year = m.group(2)
        media.episode = m.group(3) or ""
        media.resolution = m.group(4).lower()
        media.codec = m.group(5).lower()
        media.tail = m.group(6) or ""
        media.already_correct = True
        media.folder_match = folder_matches_title(path, media.title)
        if verbose:
            print(f"  {C.dim('skip (correct format): ' + path.name)}")
        return media

    # Strip tail from stem before parsing other parts
    tail_m = _RE_TAIL.search(stem)
    if tail_m:
        media.tail = tail_m.group(1)
        stem = stem[: tail_m.start()]

    # Strip episode identifier (e.g. " - s01e01 - Episode Name")
    ep_m = _RE_EPISODE.search(stem)
    if ep_m:
        media.episode = ep_m.group(1).rstrip()
        stem = stem[: ep_m.start()] + stem[ep_m.end() :]

    # Extract what we can from the (tail+episode-stripped) filename
    year_m = _RE_YEAR.search(stem)
    res_m = _RE_RES.search(stem)
    codec_m = _RE_CODEC.search(stem)

    media.year = year_m.group(1) if year_m else None
    media.resolution = normalize_resolution(res_m.group(1)) if res_m else None
    media.codec = (
        CODEC_NORMALIZE.get(codec_m.group(1).lower(), codec_m.group(1).lower())
        if codec_m
        else None
    )
    media.title = extract_title(stem) or None

    # Fill missing res/codec from ffprobe
    if not media.resolution or not media.codec:
        if verbose:
            print(f"  {C.cyan('ffprobe: ' + path.name)}")
        ff_codec, ff_res, ff_err = get_ffprobe_info(path)
        if ff_codec is None:
            media.skip_reason = ff_err or "ffprobe found no video stream"
            return media
        if not media.codec:
            media.codec = ff_codec
        if not media.resolution:
            media.resolution = ff_res

    # Record what remains genuinely unknown
    if not media.title:
        media.missing_parts.append("Title")
    if not media.year:
        media.missing_parts.append("YYYY")

    # Folder check
    if media.title:
        media.folder_match = folder_matches_title(path, media.title)

    # Build proposed name
    if media.title and media.resolution and media.codec:
        year_part = f" ({media.year})" if media.year else ""
        media.proposed_name = f"{media.title}{year_part}{media.episode}.{media.resolution}.{media.codec}{media.tail}.{ext}"
    else:
        missing = media.missing_parts or ["title"]
        media.skip_reason = f"cannot determine new name (missing: {', '.join(missing)})"

    return media


# ---------------------------------------------------------------------------
# Diff highlighting
# ---------------------------------------------------------------------------


def build_diff_cells(current: str, proposed: str) -> tuple["Text", "Text"]:
    """
    Return (current_text, proposed_text) with character-level diff highlighting.
      current:  unchanged=white  |  deleted/replaced=bold red
      proposed: unchanged=white  |  inserted=bold green  |  replaced=bold yellow
    """
    matcher = SequenceMatcher(None, current, proposed, autojunk=False)
    curr_text = Text()
    prop_text = Text()
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        c = current[i1:i2]
        p = proposed[j1:j2]
        if tag == "equal":
            curr_text.append(c)
            prop_text.append(p)
        elif tag == "replace":
            curr_text.append(c, style="bold red")
            prop_text.append(p, style="bold yellow")
        elif tag == "delete":
            curr_text.append(c, style="bold red")
        elif tag == "insert":
            prop_text.append(p, style="bold green")
    return curr_text, prop_text


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------


def make_rich_table(files: list[MediaFile]) -> "Table":
    table = Table(
        box=box.ROUNDED, show_lines=True, expand=True, header_style="bold white"
    )
    table.add_column("Title", style="cyan", overflow="fold", ratio=3)
    table.add_column("YYYY", style="yellow", width=6, justify="center")
    table.add_column("Episode", style="dim white", overflow="fold", ratio=2)
    table.add_column("RES", style="green", width=7, justify="center")
    table.add_column("ENC", style="magenta", width=7, justify="center")
    table.add_column("EXT", style="blue", width=5, justify="center")
    table.add_column("Edition", style="dim cyan", overflow="fold", ratio=2)
    table.add_column("Folder", width=8, justify="center")
    table.add_column("Current Filename", overflow="fold", ratio=4)
    table.add_column("Proposed Filename", overflow="fold", ratio=4)

    for f in files:
        year_cell = (
            Text(f.year, style="yellow") if f.year else Text("?", style="bold red")
        )
        res_cell = (
            Text(f.resolution, style="green")
            if f.resolution
            else Text("?", style="bold red")
        )
        enc_cell = (
            Text(f.codec, style="magenta") if f.codec else Text("?", style="bold red")
        )
        edition_cell = (
            Text(f.tail.strip(), style="dim cyan") if f.tail else Text("", style="dim")
        )

        if f.folder_match is None:
            folder_cell = Text("-", style="dim")
        elif f.folder_match:
            folder_cell = Text("OK", style="green")
        else:
            folder_cell = Text("NO", style="bold red")

        if f.proposed_name:
            curr_cell, prop_cell = build_diff_cells(f.path.name, f.proposed_name)
        else:
            curr_cell = Text(f.path.name)
            prop_cell = Text("—", style="dim")

        episode_cell = (
            Text(f.episode.lstrip(" -").strip(), style="dim white")
            if f.episode
            else Text("", style="dim")
        )

        table.add_row(
            f.title or Text("?", style="bold red"),
            year_cell,
            episode_cell,
            res_cell,
            enc_cell,
            f.ext,
            edition_cell,
            folder_cell,
            curr_cell,
            prop_cell,
        )
    return table


def print_plain_table(files: list[MediaFile]) -> None:
    headers = [
        "Title",
        "YYYY",
        "Episode",
        "RES",
        "ENC",
        "EXT",
        "Edition",
        "Folder",
        "Current Filename",
        "Proposed Filename",
    ]
    rows = [
        [
            f.title or "?",
            f.year or "?",
            f.episode.lstrip(" -").strip() if f.episode else "",
            f.resolution or "?",
            f.codec or "?",
            f.ext,
            f.tail.strip() if f.tail else "",
            ("OK" if f.folder_match else "NO") if f.folder_match is not None else "-",
            f.path.name,
            f.proposed_name or "—",
        ]
        for f in files
    ]
    col_w = [
        max(len(h), max((len(str(r[i])) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    sep = "+-" + "-+-".join("-" * w for w in col_w) + "-+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_w) + " |"
    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rename media files to: Title (YYYY).RES.ENC.ext"
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        metavar="DIR",
        help="Directory to search (default: current directory)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show every file found, including those being skipped",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Preflight checks
    # ------------------------------------------------------------------

    errors: list[str] = []
    result = subprocess.run(["which", "ffprobe"], capture_output=True)
    if result.returncode != 0:
        errors.append(
            "ffprobe not found — install ffmpeg (e.g. add 'ffmpeg' to home.nix packages)"
        )
    if errors:
        for e in errors:
            print(C.red(f"Error: {e}"))
        sys.exit(1)

    root = Path(args.root).resolve()
    if not root.exists():
        print(C.red(f"Error: '{root}' does not exist."))
        sys.exit(1)

    console = Console() if HAS_RICH else None

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    if HAS_RICH:
        console.print(f"\n[bold blue]Scanning:[/bold blue] {root}")
    else:
        print(f"\n{C.bold(C.blue('Scanning:'))} {root}")

    all_files = sorted(
        p for p in root.rglob("*") if p.suffix.lower() in (".mkv", ".mp4")
    )
    found_count = len(all_files)

    already_ok: list[MediaFile] = []
    to_rename: list[MediaFile] = []
    unresolvable: list[MediaFile] = []

    term_w = console.width if HAS_RICH and console else 80

    for i, path in enumerate(all_files, 1):
        if not args.verbose:
            rel = str(path.relative_to(root))
            label = f"  [{i}/{found_count}] "
            max_name = term_w - len(label)
            if len(rel) > max_name:
                rel = "\u2026" + rel[-(max_name - 1) :]
            sys.stdout.write(f"\r{label}{rel:<{max_name}}")
            sys.stdout.flush()

        media = analyze_file(path, verbose=args.verbose)

        if media.skip_reason:
            unresolvable.append(media)
            if args.verbose:
                if HAS_RICH:
                    console.print(
                        f"  [yellow]skip ({media.skip_reason}):[/yellow] {path.name}"
                    )
                else:
                    print(f"  {C.yellow(f'skip ({media.skip_reason}):')} {path.name}")
        elif media.already_correct:
            already_ok.append(media)
        elif media.needs_rename():
            to_rename.append(media)
        else:
            already_ok.append(media)

    if not args.verbose:
        sys.stdout.write(f"\r{' ' * term_w}\r")
        sys.stdout.flush()

    # ------------------------------------------------------------------
    # Scan summary
    # ------------------------------------------------------------------

    if HAS_RICH:
        console.print("\n[bold]Scan Results[/bold]")
        console.print(f"  [cyan]Files found:[/cyan]       {found_count}")
        console.print(f"  [green]Already correct:[/green]  {len(already_ok)}")
        console.print(f"  [yellow]Need renaming:[/yellow]    {len(to_rename)}")
        if unresolvable:
            console.print(f"  [red]Could not analyze:[/red] {len(unresolvable)}")
            for f in unresolvable:
                console.print(
                    f"    [red dim]• {f.path.name}: {f.skip_reason}[/red dim]"
                )
    else:
        print(C.bold("Scan Results"))
        print(f"  {C.cyan('Files found:       ' + str(found_count))}")
        print(f"  {C.green('Already correct:   ' + str(len(already_ok)))}")
        print(f"  {C.yellow('Need renaming:     ' + str(len(to_rename)))}")
        if unresolvable:
            print(f"  {C.red('Could not analyze: ' + str(len(unresolvable)))}")
            for f in unresolvable:
                print(f"    {C.red('• ' + f.path.name + ': ' + (f.skip_reason or ''))}")

    if not to_rename:
        msg = "All files are already correctly named!"
        if HAS_RICH:
            console.print(f"\n[bold green]{msg}[/bold green]\n")
        else:
            print(f"\n{C.bold(C.green(msg))}\n")
        return

    # ------------------------------------------------------------------
    # Table of files to rename
    # ------------------------------------------------------------------

    header = f"Files needing renaming ({len(to_rename)})"
    if HAS_RICH:
        console.print(f"\n[bold yellow]{header}[/bold yellow]\n")
        console.print(make_rich_table(to_rename))
    else:
        print(f"\n{C.bold(C.yellow(header))}\n")
        print_plain_table(to_rename)

    # ------------------------------------------------------------------
    # Confirmation
    # ------------------------------------------------------------------

    try:
        answer = input(C.bold("Apply these renames? [y/N]: ")).strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        if HAS_RICH:
            console.print("[yellow]Aborted.[/yellow]\n")
        else:
            print(f"{C.yellow('Aborted.')}\n")
        return

    if answer not in ("y", "yes"):
        if HAS_RICH:
            console.print("[yellow]No changes made.[/yellow]\n")
        else:
            print(f"{C.yellow('No changes made.')}\n")
        return

    # ------------------------------------------------------------------
    # Apply renames
    # ------------------------------------------------------------------

    success = 0
    failed: list[tuple[MediaFile, str]] = []

    for f in to_rename:
        new_path = f.path.parent / f.proposed_name
        try:
            if new_path.exists():
                reason = f"target already exists"
                failed.append((f, reason))
                if HAS_RICH:
                    console.print(
                        f"  [yellow]SKIP[/yellow]  {f.path.name}  →  {reason}"
                    )
                else:
                    print(f"  {C.yellow('SKIP')}  {f.path.name}  →  {reason}")
                continue

            f.path.rename(new_path)
            success += 1
            if HAS_RICH:
                console.print(
                    f"  [green]OK[/green]    {f.path.name}  →  {f.proposed_name}"
                )
            else:
                print(f"  {C.green('OK')}    {f.path.name}  →  {f.proposed_name}")

        except OSError as e:
            failed.append((f, str(e)))
            if HAS_RICH:
                console.print(f"  [red]FAIL[/red]  {f.path.name}  →  {e}")
            else:
                print(f"  {C.red('FAIL')}  {f.path.name}  →  {e}")

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------

    sep = "─" * 52
    if HAS_RICH:
        console.print(f"\n[bold]{sep}[/bold]")
        console.print("[bold]Final Summary[/bold]")
        console.print(f"[bold]{sep}[/bold]")
        console.print(f"  [cyan]Found:                {found_count}[/cyan]")
        console.print(f"  [yellow]Needed renaming:      {len(to_rename)}[/yellow]")
        console.print(f"  [green]Successfully updated: {success}[/green]")
        if failed:
            console.print(f"  [red]Failed:               {len(failed)}[/red]")
            for f, reason in failed:
                console.print(f"    [red]• {f.path.name}: {reason}[/red]")
        console.print()
    else:
        print(f"\n{C.bold(sep)}")
        print(C.bold("Final Summary"))
        print(C.bold(sep))
        print(f"  {C.cyan( 'Found:                ' + str(found_count))}")
        print(f"  {C.yellow('Needed renaming:      ' + str(len(to_rename)))}")
        print(f"  {C.green( 'Successfully updated: ' + str(success))}")
        if failed:
            print(f"  {C.red('Failed:               ' + str(len(failed)))}")
            for f, reason in failed:
                print(f"    {C.red('• ' + f.path.name + ': ' + reason)}")
        print()


if __name__ == "__main__":
    main()
