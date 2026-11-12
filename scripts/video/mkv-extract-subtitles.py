#!/usr/bin/env python3
"""
Extract the image-based (Blu-ray PGS) subtitles from .mkv files and OCR them
to a text transcript, so dialogue can be searched to identify an episode.

Pipeline per file:
  mkvmerge -J          pick the subtitle track (default: first non-forced English PGS)
  ffmpeg -c:s copy     pull that track out as a .sup stream (optionally only the first N minutes)
  built-in PGS parser  decode each subtitle bitmap (no Pillow needed)
  tesseract            OCR each bitmap

Output goes to --out-dir (default ./mkv-extract-subtitles), NOT next to the video, so Plex
never picks the OCR'd files up as external subtitles. For a directory input the
relative folder layout is mirrored under --out-dir.

  mkv-extract-subtitles.py episode.mkv --first-minutes 5
  mkv-extract-subtitles.py "Season 07/" --first-minutes 5 --out-dir /tmp/subs
  mkv-extract-subtitles.py "Season 07/" --agent        # JSON Lines summary on stdout

Only HDMV PGS tracks are supported (DVD VobSub and text tracks are reported
as errors). Requires mkvmerge, ffmpeg and tesseract on PATH.

OCR is imperfect (I/l confusion, odd punctuation); treat the output as search
material, not as a subtitle file to ship.
"""

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PGS_MAGIC = b"PG"
SEG_PDS, SEG_ODS, SEG_PCS, SEG_WDS, SEG_END = 0x14, 0x15, 0x16, 0x17, 0x80
PAD = 12  # white border around each bitmap; tesseract does better with a margin
TAIL_MS = 3000  # assumed display time when a subtitle is never explicitly cleared


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_agent_mode(args: argparse.Namespace) -> bool:
    env = os.environ.get("MKV_TOOLS_AGENT", "").strip().lower()
    return args.agent or env in ("1", "true", "yes")


def fmt_ts(ms: int, sep: str = ".") -> str:
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h}:{m:02d}:{s:02d}{sep}{milli:03d}"


def require_tools() -> None:
    missing = [t for t in ("mkvmerge", "ffmpeg", "tesseract") if not shutil.which(t)]
    if missing:
        sys.exit(
            f"Missing required tool(s): {', '.join(missing)}. "
            "They are declared in .config/home-manager/home.nix; run hms."
        )


def find_mkvs(paths: list[Path]) -> list[tuple[Path, Path]]:
    """Return (file, relative output stem path) pairs."""
    found = []
    for p in paths:
        if p.is_file():
            found.append((p, Path(p.stem)))
        elif p.is_dir():
            for f in sorted(p.rglob("*.mkv")):
                found.append((f, f.relative_to(p).with_suffix("")))
        else:
            print(f"warning: {p} not found", file=sys.stderr)
    return found


# ---------------------------------------------------------------------------
# Track selection
# ---------------------------------------------------------------------------


def pick_track(path: Path, lang: str, track_id: int | None) -> tuple[int, dict]:
    """Return (subtitle ordinal for ffmpeg -map 0:s:N, track dict)."""
    r = subprocess.run(
        ["mkvmerge", "-J", str(path)], capture_output=True, text=True, check=False
    )
    if r.returncode not in (0, 1):
        raise RuntimeError(f"mkvmerge failed: {r.stderr.strip() or r.stdout.strip()}")
    subs = [t for t in json.loads(r.stdout)["tracks"] if t["type"] == "subtitles"]
    if not subs:
        raise RuntimeError("no subtitle tracks")

    if track_id is not None:
        for ordinal, t in enumerate(subs):
            if t["id"] == track_id:
                return ordinal, t
        raise RuntimeError(f"no subtitle track with id {track_id}")

    def lang_of(t: dict) -> str:
        p = t["properties"]
        return (p.get("language") or p.get("language_ietf") or "").lower()

    candidates = [
        (i, t) for i, t in enumerate(subs) if lang_of(t).startswith(lang.lower())
    ]
    if not candidates:
        have = ", ".join(sorted({lang_of(t) or "und" for t in subs}))
        raise RuntimeError(f"no '{lang}' subtitle track (have: {have})")
    # Prefer a full track over a forced-only one.
    candidates.sort(key=lambda it: bool(it[1]["properties"].get("forced_track")))
    return candidates[0]


def extract_sup(path: Path, ordinal: int, out: Path, first_minutes: float | None) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-map", f"0:s:{ordinal}"]
    if first_minutes:
        cmd += ["-t", str(int(first_minutes * 60))]
    cmd += ["-c:s", "copy", "-f", "sup", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"ffmpeg extract failed: {r.stderr.strip()}")


# ---------------------------------------------------------------------------
# PGS parsing
# ---------------------------------------------------------------------------


def decode_rle(data: bytes, w: int, h: int) -> list[bytearray]:
    """Decode PGS run-length data into rows of palette indices."""
    rows: list[bytearray] = []
    row = bytearray()
    i, n = 0, len(data)
    while i < n and len(rows) < h:
        b = data[i]
        i += 1
        if b:
            row.append(b)
            continue
        if i >= n:
            break
        b = data[i]
        i += 1
        if b == 0:  # end of line
            row.extend(b"\x00" * (w - len(row)))
            rows.append(row[:w])
            row = bytearray()
            continue
        flag = b & 0xC0
        if flag == 0x00:
            run, color = b & 0x3F, 0
        elif flag == 0x40:
            run, color = ((b & 0x3F) << 8) | data[i], 0
            i += 1
        elif flag == 0x80:
            run, color = b & 0x3F, data[i]
            i += 1
        else:
            run, color = ((b & 0x3F) << 8) | data[i], data[i + 1]
            i += 2
        row.extend(bytes([color]) * run)
    while len(rows) < h:
        rows.append(bytearray(w))
    return rows


def parse_pgs(data: bytes) -> list[dict]:
    """
    Parse a .sup stream into display events:
      {"start": ms, "end": ms, "objects": [(x, y, w, h, rle, palette)]}
    """
    events: list[dict] = []
    palettes: dict[int, dict[int, tuple[int, int]]] = {}
    objects: dict[int, tuple[int, int, bytearray]] = {}
    partial: dict[int, list] = {}  # object id -> [w, h, bytearray]
    comp_objs: list[tuple[int, int, int]] = []  # (object id, x, y)
    comp_pal = 0
    comp_pts = 0
    open_event: dict | None = None
    pos, n = 0, len(data)

    while pos + 13 <= n:
        if data[pos : pos + 2] != PGS_MAGIC:
            pos += 1  # resync on garbage
            continue
        pts, _dts, seg_type, size = struct.unpack(">IIBH", data[pos + 2 : pos + 13])
        body = data[pos + 13 : pos + 13 + size]
        pos += 13 + size

        if seg_type == SEG_PCS:
            if open_event is not None:
                open_event["end"] = pts // 90
                events.append(open_event)
                open_event = None
            state = body[7]
            comp_pal = body[9]
            nobj = body[10]
            comp_pts = pts // 90
            comp_objs = []
            if state == 0x80:  # epoch start: all earlier definitions are void
                palettes.clear()
                objects.clear()
                partial.clear()
            off = 11
            for _ in range(nobj):
                oid, _win, crop, x, y = struct.unpack(">HBBHH", body[off : off + 8])
                comp_objs.append((oid, x, y))
                off += 8 + (8 if crop & 0x40 else 0)

        elif seg_type == SEG_PDS:
            pal = palettes.setdefault(body[0], {})
            for off in range(2, len(body) - 4, 5):
                idx, y, _cr, _cb, a = body[off : off + 5]
                pal[idx] = (y, a)

        elif seg_type == SEG_ODS:
            oid = struct.unpack(">H", body[0:2])[0]
            seq = body[3]
            if seq & 0x80:  # first fragment
                w, h = struct.unpack(">HH", body[7:11])
                partial[oid] = [w, h, bytearray(body[11:])]
            elif oid in partial:
                partial[oid][2].extend(body[4:])
            if seq & 0x40 and oid in partial:  # last fragment
                w, h, rle = partial.pop(oid)
                objects[oid] = (w, h, rle)

        elif seg_type == SEG_END:
            if comp_objs:
                pal = dict(palettes.get(comp_pal, {}))
                objs = []
                for oid, x, y in comp_objs:
                    if oid in objects:
                        w, h, rle = objects[oid]
                        objs.append((x, y, w, h, bytes(rle), pal))
                if objs:
                    open_event = {"start": comp_pts, "end": None, "objects": objs}

    if open_event is not None:
        open_event["end"] = open_event["start"] + TAIL_MS
        events.append(open_event)
    return events


# ---------------------------------------------------------------------------
# Rendering + OCR
# ---------------------------------------------------------------------------


def render_pgm(w: int, h: int, rle: bytes, palette: dict) -> bytes:
    """Render one subtitle bitmap as dark-text-on-white binary PGM."""
    # Opaque light fill -> near black, dark outline -> near white, transparent -> white.
    lut = bytearray([255] * 256)
    for idx, (y, a) in palette.items():
        lut[idx] = max(0, min(255, round(255 - y * (a / 255))))
    rows = decode_rle(rle, w, h)
    out_w, out_h = w + 2 * PAD, h + 2 * PAD
    blank = b"\xff" * out_w
    lines = [blank] * PAD
    border = b"\xff" * PAD
    for row in rows:
        lines.append(border + bytes(row).translate(bytes(lut)) + border)
    lines.extend([blank] * PAD)
    return b"P5\n%d %d\n255\n" % (out_w, out_h) + b"".join(lines)


def ocr(pgm: bytes, lang: str) -> str:
    env = dict(os.environ, OMP_THREAD_LIMIT="1")  # we parallelise across images instead
    r = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", lang, "--psm", "6"],
        input=pgm,
        capture_output=True,
        env=env,
        check=False,
    )
    return r.stdout.decode("utf-8", "replace")


def clean(text: str) -> str:
    lines = []
    for ln in text.splitlines():
        ln = " ".join(ln.replace("|", "I").split())
        if ln:
            lines.append(ln)
    return "\n".join(lines)


def ocr_event(ev: dict, lang: str) -> str:
    # One bitmap per text line is common; order them top to bottom.
    parts = []
    for x, y, w, h, rle, pal in sorted(ev["objects"], key=lambda o: (o[1], o[0])):
        if w and h:
            parts.append(clean(ocr(render_pgm(w, h, rle, pal), lang)))
    return "\n".join(p for p in parts if p)


def ocr_events(events: list[dict], lang: str, jobs: int) -> list[dict]:
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        texts = list(pool.map(lambda e: ocr_event(e, lang), events))
    cues: list[dict] = []
    for ev, text in zip(events, texts):
        if not text:
            continue
        # Fades and palette-only updates repeat a cue; merge identical neighbours.
        if cues and cues[-1]["text"] == text and ev["start"] - cues[-1]["end"] < 200:
            cues[-1]["end"] = ev["end"]
        else:
            cues.append({"start": ev["start"], "end": ev["end"], "text": text})
    return cues


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_txt(cues: list[dict], out: Path) -> None:
    with out.open("w", encoding="utf-8") as f:
        for c in cues:
            f.write(f"[{fmt_ts(c['start'])}] {c['text'].replace(chr(10), ' / ')}\n")


def write_srt(cues: list[dict], out: Path) -> None:
    with out.open("w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            f.write(
                f"{i}\n{fmt_ts(c['start'], ',')} --> {fmt_ts(c['end'], ',')}\n"
                f"{c['text']}\n\n"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def process(path: Path, rel: Path, args: argparse.Namespace) -> dict:
    out_base = args.out_dir / rel
    out = out_base.with_name(out_base.name + f".{args.format}")
    if out.exists() and not args.force:
        return {"path": str(path), "output": str(out), "skipped": "exists (use --force)"}

    ordinal, track = pick_track(path, args.lang, args.track_id)
    codec = track["codec"]
    if "PGS" not in codec:
        raise RuntimeError(f"unsupported subtitle codec '{codec}' (only HDMV PGS)")

    with tempfile.TemporaryDirectory(prefix="mkv-extract-subtitles-") as tmp:
        sup = Path(tmp) / "track.sup"
        extract_sup(path, ordinal, sup, args.first_minutes)
        events = parse_pgs(sup.read_bytes())

    cues = ocr_events(events, args.ocr_lang, args.jobs)
    out.parent.mkdir(parents=True, exist_ok=True)
    (write_srt if args.format == "srt" else write_txt)(cues, out)
    return {
        "path": str(path),
        "output": str(out),
        "track_id": track["id"],
        "language": track["properties"].get("language"),
        "bitmaps": len(events),
        "cues": len(cues),
        "last_cue_ms": cues[-1]["start"] if cues else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract PGS subtitles from MKVs and OCR them to text.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("paths", nargs="+", type=Path, help=".mkv files or folders (recursive)")
    ap.add_argument("--out-dir", type=Path, default=Path("mkv-extract-subtitles"), help="where transcripts go")
    ap.add_argument("--format", choices=("txt", "srt"), default="txt", help="txt = '[H:MM:SS.mmm] line'")
    ap.add_argument("--first-minutes", type=float, default=None, help="only the first N minutes (fast; enough to identify an episode)")
    ap.add_argument("--lang", default="eng", help="subtitle track language to select (mkv language code)")
    ap.add_argument("--track-id", type=int, default=None, help="mkvmerge track id; overrides --lang")
    ap.add_argument("--ocr-lang", default="eng", help="tesseract language data to use")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2, help="parallel tesseract processes")
    ap.add_argument("--force", action="store_true", help="overwrite existing transcripts")
    ap.add_argument("--agent", "--json", action="store_true", help="JSON Lines summary on stdout, no progress (or MKV_TOOLS_AGENT=1)")
    args = ap.parse_args()

    require_tools()
    agent = is_agent_mode(args)
    files = find_mkvs(args.paths)
    if not files:
        print("No .mkv files found.", file=sys.stderr)
        return 1

    failed = False
    for i, (path, rel) in enumerate(files, 1):
        if not agent and sys.stderr.isatty():
            print(f"[{i}/{len(files)}] {path.name}", file=sys.stderr)
        try:
            result = process(path, rel, args)
        except Exception as e:  # keep going; report per file
            failed = True
            result = {"path": str(path), "error": str(e)}
        if agent:
            print(json.dumps(result))
        elif "error" in result:
            print(f"ERROR {path}: {result['error']}", file=sys.stderr)
        elif "skipped" in result:
            print(f"skip  {path.name}: {result['skipped']}")
        else:
            print(f"{path.name}: {result['cues']} cues -> {result['output']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
