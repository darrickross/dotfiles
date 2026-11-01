#!/usr/bin/env python3
"""
Scan a folder for .mkv files and display a summary table:
  filename, size, duration, chapters, video resolution, audio track count, subtitle count.

With --agent (or MKV_TOOLS_AGENT=1) emit JSON Lines instead: one object per
file with raw numeric values and per-track detail, sorted by path, with no
progress line, banner or colour. Files that cannot be read are emitted as
{"path": ..., "relative_path": ..., "error": ...} and the exit code is 1.
"""

import argparse
import json
import os
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


def is_agent_mode(args: argparse.Namespace) -> bool:
    env = os.environ.get("MKV_TOOLS_AGENT", "").strip().lower()
    return args.agent or env in ("1", "true", "yes")


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
# Per-file extraction (raw values; formatting happens at display time)
# ---------------------------------------------------------------------------


def parse_dimensions(dims: str) -> tuple[int | None, int | None]:
    try:
        w, h = dims.split("x")
        return int(w), int(h)
    except ValueError:
        return None, None


def extract_row(path: Path, root: Path, data: dict) -> dict:
    props = data.get("container", {}).get("properties", {})

    size = path.stat().st_size if path.exists() else None
    duration_ns = props.get("duration")

    chapters = sum(c.get("num_entries", 0) for c in data.get("chapters", []))

    tracks = data.get("tracks", [])
    video_tracks = [t for t in tracks if t["type"] == "video"]
    audio_tracks = [t for t in tracks if t["type"] == "audio"]
    sub_tracks   = [t for t in tracks if t["type"] == "subtitles"]

    # Resolution from first video track
    video = None
    if video_tracks:
        vp = video_tracks[0].get("properties", {})
        width, height = parse_dimensions(vp.get("pixel_dimensions", ""))
        dur_ns = vp.get("default_duration")
        video = {
            "width":  width,
            "height": height,
            "codec":  video_tracks[0].get("codec"),
            "fps":    round(1_000_000_000 / dur_ns, 3) if dur_ns else None,
        }

    audio = []
    for t in audio_tracks:
        p = t.get("properties", {})
        audio.append({
            "id":       t["id"],
            "codec":    t.get("codec"),
            "language": p.get("language"),
            "name":     p.get("track_name"),
            "channels": p.get("audio_channels"),
            "default":  p.get("default_track", False),
        })

    subtitles = []
    for t in sub_tracks:
        p = t.get("properties", {})
        subtitles.append({
            "id":       t["id"],
            "codec":    t.get("codec"),
            "language": p.get("language"),
            "name":     p.get("track_name"),
            "default":  p.get("default_track", False),
            "forced":   p.get("forced_track", False),
        })

    return {
        "path":          str(path),
        "relative_path": str(path.relative_to(root)),
        "name":          path.name,
        "size_bytes":    size,
        "duration_s":    round(duration_ns / 1_000_000_000, 3) if duration_ns else None,
        "chapters":      chapters,
        "video":         video,
        "audio":         audio,
        "subtitles":     subtitles,
    }


def format_row(r: dict) -> dict:
    """Raw row → display strings for the human table."""
    video_info = "—"
    v = r["video"]
    if v:
        dims = f"{v['width']}x{v['height']}" if v["width"] and v["height"] else ""
        parts = [p for p in [dims, v["codec"]] if p]
        fps = f" @ {v['fps']:.3f}fps" if v["fps"] else ""
        video_info = "  ".join(parts) + fps if parts else "—"

    return {
        "name":     r["name"],
        "size":     fmt_bytes(r["size_bytes"]) if r["size_bytes"] is not None else "—",
        "duration": ns_to_hms(round(r["duration_s"] * 1_000_000_000)) if r["duration_s"] else "—",
        "chapters": str(r["chapters"]),
        "video":    video_info,
        "audio":    str(len(r["audio"])),
        "subs":     str(len(r["subtitles"])),
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
        help="Sort order (default: name). Ignored with --agent, which sorts by path",
    )
    parser.add_argument(
        "--min-duration", type=float, metavar="MIN",
        help="Only include files at least MIN minutes long",
    )
    parser.add_argument(
        "--max-duration", type=float, metavar="MIN",
        help="Only include files at most MIN minutes long",
    )
    parser.add_argument(
        "--agent", "--json", action="store_true", dest="agent",
        help="Machine-readable output: JSON Lines with raw values, no progress "
             "or colour (also enabled by MKV_TOOLS_AGENT=1)",
    )
    args = parser.parse_args()

    agent = is_agent_mode(args)
    # Progress line and banner are for a person watching a terminal.
    interactive = not agent and sys.stdout.isatty()

    root = Path(args.folder).resolve()
    if not root.exists():
        print(f"Error: '{root}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not root.is_dir():
        print(f"Error: '{root}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    console = Console() if HAS_RICH and not agent else None

    glob_fn = root.rglob if args.recursive else root.glob
    mkv_files = sorted(p for p in glob_fn("*.mkv") if p.is_file())

    if not mkv_files:
        msg = f"No .mkv files found in '{root}'."
        if agent:
            print(msg, file=sys.stderr)
        elif HAS_RICH:
            console.print(f"[yellow]{msg}[/yellow]")
        else:
            print(msg)
        return

    if not agent:
        if HAS_RICH:
            console.print(f"\n[bold blue]Scanning:[/bold blue] {root}")
        else:
            print(f"\nScanning: {root}")

    term_w = console.width if console else 80
    rows: list[dict] = []
    errors: list[dict] = []
    total = len(mkv_files)

    for i, path in enumerate(mkv_files, 1):
        rel = str(path.relative_to(root))

        if interactive:
            label = f"  [{i}/{total}] "
            max_name = term_w - len(label) - 1
            display = rel if len(rel) <= max_name else "…" + rel[-(max_name - 1):]
            sys.stdout.write(f"\r{label}{display:<{max_name}}")
            sys.stdout.flush()

        data = run_mkvmerge(path)
        if data is None:
            reason = "failed to parse mkvmerge output"
        elif data.get("errors"):
            reason = "; ".join(data["errors"])
        else:
            rows.append(extract_row(path, root, data))
            continue
        errors.append({"path": str(path), "relative_path": rel, "name": path.name, "error": reason})

    # Clear progress line
    if interactive:
        sys.stdout.write(f"\r{' ' * term_w}\r")
        sys.stdout.flush()

    # Duration filters (minutes). Files with no duration can't satisfy either bound.
    if args.min_duration is not None or args.max_duration is not None:
        def in_range(r: dict) -> bool:
            d = r["duration_s"]
            if d is None:
                return False
            if args.min_duration is not None and d < args.min_duration * 60:
                return False
            if args.max_duration is not None and d > args.max_duration * 60:
                return False
            return True

        rows = [r for r in rows if in_range(r)]

    # Agent mode: raw JSON Lines, sorted by path for stable diffs.
    if agent:
        records = sorted(rows + errors, key=lambda r: r["relative_path"])
        for rec in records:
            rec = {k: v for k, v in rec.items() if k != "name"}
            print(json.dumps(rec, ensure_ascii=False))
        if not records:
            print("No files match the duration filter.", file=sys.stderr)
        sys.exit(1 if errors else 0)

    if not rows and errors:
        msg = "Could not read metadata from any file."
        if HAS_RICH:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        for e in errors:
            print(f"  {e['name']}: {e['error']}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        msg = "No files match the duration filter."
        if HAS_RICH:
            console.print(f"[yellow]{msg}[/yellow]")
        else:
            print(msg)
        return

    # Sort on raw values so size and duration order numerically.
    SORT_KEY = {
        "name":     lambda r: r["name"].lower(),
        "size":     lambda r: (r["size_bytes"] or 0, r["relative_path"]),
        "duration": lambda r: (r["duration_s"] or 0, r["relative_path"]),
    }
    rows.sort(key=SORT_KEY[args.sort])
    display_rows = [format_row(r) for r in rows]

    # Header
    count = len(display_rows)
    if HAS_RICH:
        console.print(Rule(f"[bold cyan]{count} MKV file{'s' if count != 1 else ''}[/bold cyan]"))
        console.print(make_rich_table(display_rows, console))
    else:
        print(f"\n{count} MKV file{'s' if count != 1 else ''}:\n")
        print_plain_table(display_rows)
        print()

    # Errors
    if errors:
        if HAS_RICH:
            console.print(f"\n[red]Errors ({len(errors)}):[/red]")
            for e in errors:
                console.print(f"  [red dim]• {e['name']}: {e['error']}[/red dim]")
        else:
            print(f"\nErrors ({len(errors)}):")
            for e in errors:
                print(f"  • {e['name']}: {e['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
