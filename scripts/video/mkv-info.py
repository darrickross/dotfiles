#!/usr/bin/env python3
"""
Display detailed MKV track/container info from mkvmerge.
Optionally compare two files side-by-side with -c/--compare.
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
    from rich.panel import Panel
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


def fmt_bps(bps: int) -> str:
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.2f} Mbps"
    if bps >= 1_000:
        return f"{bps / 1_000:.1f} Kbps"
    return f"{bps} bps"


def yes_no(v: bool) -> str:
    return "Yes" if v else "No"


# ---------------------------------------------------------------------------
# mkvmerge invocation
# ---------------------------------------------------------------------------

def run_mkvmerge(path: Path) -> dict:
    try:
        r = subprocess.run(
            ["mkvmerge", "-J", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout)
    except FileNotFoundError:
        print("Error: mkvmerge not found. Install mkvtoolnix.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing mkvmerge output: {e}", file=sys.stderr)
        sys.exit(1)

    if data.get("errors"):
        for err in data["errors"]:
            print(f"mkvmerge error: {err.strip()}", file=sys.stderr)
        sys.exit(1)

    return data


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_container(data: dict) -> dict:
    props = data.get("container", {}).get("properties", {})
    file_path = Path(data.get("file_name", ""))
    size = file_path.stat().st_size if file_path.exists() else None

    duration_ns = props.get("duration")
    return {
        "File":         file_path.name,
        "Size":         fmt_bytes(size) if size is not None else "—",
        "Format":       data.get("container", {}).get("type", "—"),
        "Duration":     ns_to_hms(duration_ns) if duration_ns else "—",
        "Title":        props.get("title", "—"),
        "Date":         props.get("date_local", props.get("date_utc", "—")),
        "Muxer":        props.get("muxing_application", "—"),
        "Written by":   props.get("writing_application", "—"),
        "Segment UID":  props.get("segment_uid", "—"),
        "Chapters":     str(sum(c.get("num_entries", 0) for c in data.get("chapters", []))),
        "Attachments":  str(len(data.get("attachments", []))),
    }


def extract_tracks(data: dict) -> list[dict]:
    tracks = []
    for t in data.get("tracks", []):
        p = t.get("properties", {})

        # Build a clean display of audio properties
        audio_info = ""
        if t["type"] == "audio":
            ch = p.get("audio_channels")
            hz = p.get("audio_sampling_frequency")
            bits = p.get("audio_bits_per_sample")
            parts = []
            if ch:
                parts.append(f"{ch}ch")
            if hz:
                parts.append(f"{hz // 1000}kHz")
            if bits:
                parts.append(f"{bits}-bit")
            audio_info = " / ".join(parts)

        video_info = ""
        if t["type"] == "video":
            dims = p.get("pixel_dimensions", "")
            disp = p.get("display_dimensions", "")
            dur  = p.get("default_duration")
            fps  = f"{1_000_000_000 / dur:.3f}fps" if dur else ""
            video_info = dims
            if disp and disp != dims:
                video_info += f" (display: {disp})"
            if fps:
                video_info += f"  {fps}"

        bps = p.get("tag_bps")
        bitrate = fmt_bps(int(bps)) if bps and bps.isdigit() else "—"

        tracks.append({
            "id":       str(t["id"]),
            "type":     t["type"].capitalize(),
            "codec":    t.get("codec", "—"),
            "language": p.get("language", "—"),
            "name":     p.get("track_name", ""),
            "default":  yes_no(p.get("default_track", False)),
            "forced":   yes_no(p.get("forced_track", False)),
            "enabled":  yes_no(p.get("enabled_track", True)),
            "bitrate":  bitrate,
            "detail":   audio_info or video_info,
        })
    return tracks


def extract_attachments(data: dict) -> list[dict]:
    return [
        {
            "name":     a.get("file_name", "—"),
            "type":     a.get("content_type", "—"),
            "size":     fmt_bytes(a.get("size", 0)),
        }
        for a in data.get("attachments", [])
    ]


# ---------------------------------------------------------------------------
# Single-file display
# ---------------------------------------------------------------------------

def display_single(data: dict, console: "Console | None") -> None:
    container = extract_container(data)
    tracks    = extract_tracks(data)
    attachments = extract_attachments(data)

    if HAS_RICH:
        # Container panel
        console.print(Rule("[bold cyan]Container[/bold cyan]"))
        ct = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
        ct.add_column("Property", style="dim", width=16)
        ct.add_column("Value")
        for k, v in container.items():
            ct.add_row(k, v)
        console.print(ct)

        # Tracks
        console.print(Rule("[bold cyan]Tracks[/bold cyan]"))
        tt = Table(box=box.ROUNDED, show_lines=True, expand=True, header_style="bold white")
        tt.add_column("ID",       width=4,  justify="center")
        tt.add_column("Type",     width=10, style="bold")
        tt.add_column("Codec",    ratio=2)
        tt.add_column("Language", width=9,  justify="center")
        tt.add_column("Name",     ratio=2)
        tt.add_column("Bitrate",  width=12, justify="right")
        tt.add_column("Detail",   ratio=2)
        tt.add_column("Def",      width=4,  justify="center")
        tt.add_column("Frc",      width=4,  justify="center")

        TYPE_STYLE = {"Video": "magenta", "Audio": "yellow", "Subtitles": "cyan"}
        for t in tracks:
            style = TYPE_STYLE.get(t["type"], "white")
            def_cell = Text("Y", style="green") if t["default"] == "Yes" else Text("N", style="dim")
            frc_cell = Text("Y", style="yellow") if t["forced"] == "Yes" else Text("N", style="dim")
            tt.add_row(
                t["id"],
                Text(t["type"], style=style),
                t["codec"],
                t["language"],
                t["name"],
                t["bitrate"],
                t["detail"],
                def_cell,
                frc_cell,
            )
        console.print(tt)

        # Attachments
        if attachments:
            console.print(Rule("[bold cyan]Attachments[/bold cyan]"))
            at = Table(box=box.ROUNDED, show_lines=True, header_style="bold white")
            at.add_column("Name",  ratio=3)
            at.add_column("Type",  ratio=2)
            at.add_column("Size",  width=10, justify="right")
            for a in attachments:
                at.add_row(a["name"], a["type"], a["size"])
            console.print(at)
        console.print()

    else:
        # Plain fallback
        print("\n=== Container ===")
        for k, v in container.items():
            print(f"  {k:<16} {v}")
        print("\n=== Tracks ===")
        headers = ["ID", "Type", "Codec", "Lang", "Name", "Bitrate", "Detail", "Def", "Frc"]
        rows = [[t["id"], t["type"], t["codec"], t["language"],
                 t["name"], t["bitrate"], t["detail"],
                 t["default"][0], t["forced"][0]] for t in tracks]
        widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0)) for i, h in enumerate(headers)]
        sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
        fmt = "| " + " | ".join(f"{{:<{w}}}" for w in widths) + " |"
        print(sep)
        print(fmt.format(*headers))
        print(sep)
        for r in rows:
            print(fmt.format(*[str(c) for c in r]))
        print(sep)
        if attachments:
            print("\n=== Attachments ===")
            for a in attachments:
                print(f"  {a['name']} ({a['type']}, {a['size']})")
        print()


# ---------------------------------------------------------------------------
# Compare display
# ---------------------------------------------------------------------------

def diff_value(a: str, b: str) -> tuple[str, str, bool]:
    """Return (a_display, b_display, is_different)."""
    return a, b, a != b


def display_compare(data_a: dict, data_b: dict, console: "Console | None", verbose: bool = False) -> None:
    ca = extract_container(data_a)
    cb = extract_container(data_b)
    tracks_a = extract_tracks(data_a)
    tracks_b = extract_tracks(data_b)
    att_a = extract_attachments(data_a)
    att_b = extract_attachments(data_b)

    name_a = Path(data_a["file_name"]).name
    name_b = Path(data_b["file_name"]).name

    TRACK_FIELDS = [
        ("Codec",    "codec"),
        ("Language", "language"),
        ("Name",     "name"),
        ("Bitrate",  "bitrate"),
        ("Detail",   "detail"),
        ("Default",  "default"),
        ("Forced",   "forced"),
    ]

    if HAS_RICH:
        # Container comparison
        console.print(Rule("[bold cyan]Container Comparison[/bold cyan]"))
        ct = Table(box=box.ROUNDED, show_lines=True, expand=True, header_style="bold white")
        ct.add_column("Property",  style="dim", width=16)
        ct.add_column(f"A: {name_a}", ratio=3, overflow="fold")
        ct.add_column(f"B: {name_b}", ratio=3, overflow="fold")
        ct.add_column("Match", width=7, justify="center")

        container_diffs = 0
        for key in ca:
            va, vb = ca.get(key, "—"), cb.get(key, "—")
            same = va == vb
            if not same:
                container_diffs += 1
            if not same or verbose:
                match_cell = Text("✓", style="green") if same else Text("✗", style="bold red")
                ct.add_row(key, Text(va, style="" if same else "yellow"),
                           Text(vb, style="" if same else "yellow"), match_cell)

        if ct.row_count:
            console.print(ct)
        else:
            console.print("  [green]All container properties match.[/green]")

        # Track comparison — group by type, compare positionally within group
        console.print(Rule("[bold cyan]Track Comparison[/bold cyan]"))

        TYPE_STYLE = {"Video": "magenta", "Audio": "yellow", "Subtitles": "cyan"}

        for ttype in ("Video", "Audio", "Subtitles"):
            group_a = [t for t in tracks_a if t["type"] == ttype]
            group_b = [t for t in tracks_b if t["type"] == ttype]
            if not group_a and not group_b:
                continue

            style = TYPE_STYLE.get(ttype, "white")
            count_diff = len(group_a) != len(group_b)
            track_count = max(len(group_a), len(group_b))

            # Determine if this type has any differences at all
            type_has_diff = count_diff
            if not type_has_diff:
                for i in range(track_count):
                    ta = group_a[i] if i < len(group_a) else None
                    tb = group_b[i] if i < len(group_b) else None
                    for _, field in TRACK_FIELDS:
                        va = ta[field] if ta else "—"
                        vb = tb[field] if tb else "—"
                        if va != vb:
                            type_has_diff = True
                            break
                    if type_has_diff:
                        break

            if not type_has_diff and not verbose:
                continue

            console.print(f"\n  [bold {style}]{ttype} Tracks[/bold {style}]")

            for i in range(track_count):
                ta = group_a[i] if i < len(group_a) else None
                tb = group_b[i] if i < len(group_b) else None

                # Collect rows for this track pair
                field_rows = []
                track_has_diff = ta is None or tb is None
                for label, field in TRACK_FIELDS:
                    va = ta[field] if ta else "—"
                    vb = tb[field] if tb else "—"
                    same = va == vb
                    if not same:
                        track_has_diff = True
                    if not same or verbose:
                        field_rows.append((label, va, vb, same))

                if not field_rows and not verbose:
                    continue

                label_a = f"A #{ta['id']}" if ta else "A (missing)"
                label_b = f"B #{tb['id']}" if tb else "B (missing)"
                tt = Table(box=box.SIMPLE, show_header=True, header_style="bold dim",
                           expand=False, pad_edge=True)
                tt.add_column("Field",   style="dim", width=12)
                tt.add_column(label_a,   ratio=2, overflow="fold")
                tt.add_column(label_b,   ratio=2, overflow="fold")
                tt.add_column("Match",   width=7, justify="center")

                for label, va, vb, same in field_rows:
                    match_cell = Text("✓", style="green") if same else Text("✗", style="bold red")
                    tt.add_row(label,
                               Text(va, style="" if same else "yellow"),
                               Text(vb, style="" if same else "yellow"),
                               match_cell)
                console.print(tt)

            if count_diff:
                console.print(
                    f"  [yellow]Track count differs: A has {len(group_a)}, B has {len(group_b)}[/yellow]"
                )

        # Attachments
        if att_a or att_b:
            console.print(Rule("[bold cyan]Attachments[/bold cyan]"))
            at = Table(box=box.ROUNDED, show_lines=True, header_style="bold white")
            at.add_column("File A", ratio=3)
            at.add_column("File B", ratio=3)
            max_att = max(len(att_a), len(att_b))
            for i in range(max_att):
                va = f"{att_a[i]['name']} ({att_a[i]['size']})" if i < len(att_a) else Text("—", style="dim")
                vb = f"{att_b[i]['name']} ({att_b[i]['size']})" if i < len(att_b) else Text("—", style="dim")
                at.add_row(va, vb)
            console.print(at)

        console.print()

    else:
        # Plain compare fallback
        print(f"\n=== Container: A={name_a}  vs  B={name_b} ===")
        for key in ca:
            va, vb = ca.get(key, "—"), cb.get(key, "—")
            same = va == vb
            if not same or verbose:
                mark = "  " if same else "!!"
                print(f"{mark} {key:<16} A: {va}")
                if not same:
                    print(f"   {'':<16} B: {vb}")

        print("\n=== Tracks ===")
        for ttype in ("Video", "Audio", "Subtitles"):
            group_a = [t for t in tracks_a if t["type"] == ttype]
            group_b = [t for t in tracks_b if t["type"] == ttype]
            if not group_a and not group_b:
                continue
            print(f"\n  {ttype}:")
            for i in range(max(len(group_a), len(group_b))):
                ta = group_a[i] if i < len(group_a) else {}
                tb = group_b[i] if i < len(group_b) else {}
                rows_to_print = []
                for label, field in TRACK_FIELDS:
                    va = ta.get(field, "—")
                    vb = tb.get(field, "—")
                    same = va == vb
                    if not same or verbose:
                        rows_to_print.append((label, va, vb, same))
                if rows_to_print:
                    print(f"    Track {i + 1}:")
                    for label, va, vb, same in rows_to_print:
                        mark = "  " if same else "!!"
                        print(f"    {mark} {label:<10} A: {va}")
                        if not same:
                            print(f"       {'':<10} B: {vb}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show MKV info from mkvmerge. Optionally compare two files."
    )
    parser.add_argument("file", metavar="FILE", help="MKV file to inspect")
    parser.add_argument(
        "-c", "--compare", metavar="FILE2",
        help="Second MKV file to compare against",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="In compare mode, show all fields including matching ones",
    )
    args = parser.parse_args()

    path_a = Path(args.file)
    if not path_a.exists():
        print(f"Error: '{path_a}' does not exist.", file=sys.stderr)
        sys.exit(1)

    console = Console() if HAS_RICH else None

    if args.compare:
        path_b = Path(args.compare)
        if not path_b.exists():
            print(f"Error: '{path_b}' does not exist.", file=sys.stderr)
            sys.exit(1)

        if HAS_RICH:
            console.print(f"\n[bold]Comparing:[/bold]")
            console.print(f"  [cyan]A:[/cyan] {path_a}")
            console.print(f"  [cyan]B:[/cyan] {path_b}\n")
        else:
            print(f"\nComparing:\n  A: {path_a}\n  B: {path_b}\n")

        data_a = run_mkvmerge(path_a)
        data_b = run_mkvmerge(path_b)
        display_compare(data_a, data_b, console, verbose=args.verbose)

    else:
        if HAS_RICH:
            console.print(f"\n[bold cyan]{path_a.name}[/bold cyan]\n")
        else:
            print(f"\n{path_a.name}\n")

        data = run_mkvmerge(path_a)
        display_single(data, console)


if __name__ == "__main__":
    main()
