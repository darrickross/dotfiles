#!/usr/bin/env python3
"""
Scan a folder for .mkv files and display a summary table:
  filename, size, duration, chapters, video resolution, audio track count, subtitle count.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich.rule import Rule
    from rich import box

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ns_to_hms(ns: int) -> str:
    """Nanoseconds → H:MM:SS."""
    s = ns // 1_000_000_000
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}"


def fmt_bytes(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


# ---------------------------------------------------------------------------
# mkvmerge invocation
# ---------------------------------------------------------------------------


def run_mkvmerge(path: Path) -> dict | None:
    """Return parsed mkvmerge JSON for *path*, or None on error."""
    try:
        r = subprocess.run(
            ["mkvmerge", "-J", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.loads(r.stdout)
    except FileNotFoundError:
        print("Error: mkvmerge not found. Install mkvtoolnix.", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        return None


# ---------------------------------------------------------------------------
# Per-file extraction
# ---------------------------------------------------------------------------


def extract_row(path: Path, data: dict) -> dict:
    props = data.get("container", {}).get("properties", {})

    size = path.stat().st_size if path.exists() else None
    duration_ns = props.get("duration")

    chapters = sum(c.get("num_entries", 0) for c in data.get("chapters", []))

    tracks = data.get("tracks", [])
    video_tracks = [t for t in tracks if t["type"] == "video"]
    audio_tracks = [t for t in tracks if t["type"] == "audio"]
    sub_tracks   = [t for t in tracks if t["type"] == "subtitles"]

    # Resolution from first video track
    video_info = "—"
    if video_tracks:
        vp = video_tracks[0].get("properties", {})
        dims = vp.get("pixel_dimensions", "")
        codec = video_tracks[0].get("codec", "")
        dur_ns = vp.get("default_duration")
        fps = f" @ {1_000_000_000 / dur_ns:.3f}fps" if dur_ns else ""
        parts = [p for p in [dims, codec] if p]
        video_info = "  ".join(parts) + fps if parts else "—"

    return {
        "name":      path.name,
        "size":      fmt_bytes(size) if size is not None else "—",
        "duration":  ns_to_hms(duration_ns) if duration_ns else "—",
        "chapters":  str(chapters) if chapters else "0",
        "video":     video_info,
        "audio":     str(len(audio_tracks)),
        "subs":      str(len(sub_tracks)),
    }


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------


def make_rich_table(rows: list[dict], console: "Console") -> "Table":
    table = Table(
        box=box.ROUNDED,
        show_lines=True,
        expand=True,
        header_style="bold white",
    )
    table.add_column("Filename",    ratio=5, overflow="fold", style="cyan")
    table.add_column("Size",        width=10, justify="right", style="yellow")
    table.add_column("Duration",    width=10, justify="center", style="green")
    table.add_column("Chapters",    width=9,  justify="center")
    table.add_column("Video",       ratio=3, overflow="fold", style="magenta")
    table.add_column("Audio",       width=7,  justify="center", style="yellow")
    table.add_column("Subs",        width=6,  justify="center", style="cyan")

    for r in rows:
        chapters_cell = (
            Text(r["chapters"], style="dim") if r["chapters"] == "0"
            else Text(r["chapters"])
        )
        audio_cell = Text(r["audio"], style="dim" if r["audio"] == "0" else "yellow")
        subs_cell  = Text(r["subs"],  style="dim" if r["subs"]  == "0" else "cyan")
        table.add_row(
            r["name"],
            r["size"],
            r["duration"],
            chapters_cell,
            r["video"],
            audio_cell,
            subs_cell,
        )
    return table


def print_plain_table(rows: list[dict]) -> None:
    headers = ["Filename", "Size", "Duration", "Chapters", "Video", "Audio", "Subs"]
    keys    = ["name",     "size", "duration", "chapters", "video", "audio", "subs"]
    col_w   = [
        max(len(h), max((len(r[k]) for r in rows), default=0))
        for h, k in zip(headers, keys)
    ]
    sep = "+-" + "-+-".join("-" * w for w in col_w) + "-+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_w) + " |"
    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for r in rows:
        print(fmt.format(*[r[k] for k in keys]))
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List .mkv files in a folder with key metadata in a table."
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        metavar="DIR",
        help="Folder to scan (default: current directory)",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Scan subdirectories recursively",
    )
    parser.add_argument(
        "-s", "--sort",
        choices=["name", "size", "duration"],
        default="name",
        help="Sort order (default: name)",
    )
    args = parser.parse_args()

    root = Path(args.folder).resolve()
    if not root.exists():
        print(f"Error: '{root}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not root.is_dir():
        print(f"Error: '{root}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    console = Console() if HAS_RICH else None

    glob_fn = root.rglob if args.recursive else root.glob
    mkv_files = sorted(p for p in glob_fn("*.mkv") if p.is_file())

    if not mkv_files:
        msg = f"No .mkv files found in '{root}'."
        if HAS_RICH:
            console.print(f"[yellow]{msg}[/yellow]")
        else:
            print(msg)
        return

    if HAS_RICH:
        console.print(f"\n[bold blue]Scanning:[/bold blue] {root}")
    else:
        print(f"\nScanning: {root}")

    term_w = console.width if HAS_RICH and console else 80
    rows: list[dict] = []
    errors: list[tuple[Path, str]] = []
    total = len(mkv_files)

    for i, path in enumerate(mkv_files, 1):
        rel = str(path.relative_to(root))
        label = f"  [{i}/{total}] "
        max_name = term_w - len(label) - 1
        display = rel if len(rel) <= max_name else "\u2026" + rel[-(max_name - 1):]
        sys.stdout.write(f"\r{label}{display:<{max_name}}")
        sys.stdout.flush()

        data = run_mkvmerge(path)
        if data is None:
            errors.append((path, "failed to parse mkvmerge output"))
            continue
        if data.get("errors"):
            errors.append((path, "; ".join(data["errors"])))
            continue

        rows.append(extract_row(path, data))

    # Clear progress line
    sys.stdout.write(f"\r{' ' * term_w}\r")
    sys.stdout.flush()

    if not rows:
        msg = "Could not read metadata from any file."
        if HAS_RICH:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        if errors:
            for p, reason in errors:
                print(f"  {p.name}: {reason}", file=sys.stderr)
        return

    # Sort
    SORT_KEY = {
        "name":     lambda r: r["name"].lower(),
        "size":     lambda r: r["name"].lower(),   # size already formatted; sort by name fallback
        "duration": lambda r: r["duration"],
    }
    rows.sort(key=SORT_KEY[args.sort])

    # Header
    if HAS_RICH:
        console.print(Rule(f"[bold cyan]{total} MKV file{'s' if total != 1 else ''}[/bold cyan]"))
        console.print(make_rich_table(rows, console))
    else:
        print(f"\n{total} MKV file{'s' if total != 1 else ''}:\n")
        print_plain_table(rows)
        print()

    # Errors
    if errors:
        if HAS_RICH:
            console.print(f"\n[red]Errors ({len(errors)}):[/red]")
            for p, reason in errors:
                console.print(f"  [red dim]• {p.name}: {reason}[/red dim]")
        else:
            print(f"\nErrors ({len(errors)}):")
            for p, reason in errors:
                print(f"  • {p.name}: {reason}")


if __name__ == "__main__":
    main()
