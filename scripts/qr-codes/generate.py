#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""Generate a WiFi QR plaque PDF from a Jinja2 template."""
import argparse
import getpass
import io
import re
import sys
from pathlib import Path

import argcomplete
import segno
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATES_DIR = Path(__file__).parent / "templates"
AUTH_CHOICES = ["WPA", "WEP", "nopass"]
_SAFE_SSID_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def validate_ssid(ssid: str, ignore_char_check: bool = False) -> None:
    byte_len = len(ssid.encode("utf-8"))
    if byte_len > 32:
        sys.exit(f"Error: SSID is {byte_len} bytes (max 32).")
    if not _SAFE_SSID_RE.match(ssid) and not ignore_char_check:
        unsafe = sorted({ch for ch in ssid if not _SAFE_SSID_RE.match(ch)})
        chars = ", ".join(repr(c) for c in unsafe)
        print(
            f"Warning: SSID contains characters that may cause issues on older devices: {chars}",
            file=sys.stderr,
        )
        if input("Continue anyway? [y/N] ").strip().lower() != "y":
            sys.exit("Aborted.")


def discover_templates():
    return sorted(
        p.name.removesuffix(".html.j2")
        for p in TEMPLATES_DIR.glob("*.html.j2")
        if not p.name.startswith("_")
    )


def build_qr_svg(ssid: str, password: str, auth: str) -> str:
    payload = f"WIFI:T:{auth};S:{ssid};P:{password};;"
    qr = segno.make(payload, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=1, border=0, xmldecl=False, svgns=False)
    return buf.getvalue().decode()


def prompt_if_missing(args):
    if not args.ssid:
        args.ssid = input("SSID (network name): ").strip()
        if not args.ssid:
            sys.exit("Error: SSID cannot be empty.")
    if args.auth != "nopass" and args.password is None:
        args.password = getpass.getpass("Password: ")
        if not args.password:
            sys.exit("Error: Password cannot be empty for WPA/WEP networks.")
    return args


def main():
    templates = discover_templates()
    if not templates:
        sys.exit("Error: No templates found in templates/")

    numbered = {str(i): name for i, name in enumerate(templates)}
    epilog = "Templates:\n" + "\n".join(
        f"  {i}  {name}" for i, name in numbered.items()
    )

    parser = argparse.ArgumentParser(
        description="Generate a WiFi QR plaque PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument("-s", "--ssid", help="Network name (SSID)")
    parser.add_argument(
        "-p",
        "--password",
        default=None,
        help="WiFi password (prompted securely if omitted)",
    )
    parser.add_argument(
        "-a",
        "--auth",
        default="WPA",
        choices=AUTH_CHOICES,
        metavar=f"{{{','.join(AUTH_CHOICES)}}}",
        help="Encryption standard (default: WPA)",
    )
    parser.add_argument(
        "-t",
        "--template",
        default="0",
        choices=list(numbered),
        metavar=f"{{0-{len(numbered) - 1}}}",
        help="Template number (default: 0)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output path — file or directory (default: wifi-<ssid>.pdf in cwd)",
    )
    parser.add_argument(
        "--ignore-ssid-character-check",
        action="store_true",
        help="Skip the unsafe-character warning prompt (length limit still applies)",
    )
    parser.add_argument(
        "--no-text-color",
        action="store_true",
        help="Render all characters in the default ink color (disables per-type coloring)",
    )
    parser.add_argument(
        "-g",
        "--greeting",
        metavar="TEXT",
        help="Override the greeting text shown on the plaque",
    )
    parser.add_argument(
        "--color-alpha",
        metavar="HEX",
        help="Color for letter characters (default: inherit)",
    )
    parser.add_argument(
        "--color-number",
        metavar="HEX",
        help="Color for digit characters (default: #1f5fd9)",
    )
    parser.add_argument(
        "--color-special",
        metavar="HEX",
        help="Color for symbol characters (default: #c0392b)",
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    args = prompt_if_missing(args)
    validate_ssid(args.ssid, ignore_char_check=args.ignore_ssid_character_check)

    output_path = (
        Path(args.output) if args.output else Path.cwd() / f"wifi-{args.ssid}.pdf"
    )
    if output_path.is_dir():
        output_path = output_path / f"wifi-{args.ssid}.pdf"

    qr_svg = build_qr_svg(args.ssid, args.password or "", args.auth)

    if args.no_text_color:
        color_alpha = color_number = color_special = "inherit"
    else:
        color_alpha = args.color_alpha or "inherit"
        color_number = args.color_number or "#1f5fd9"
        color_special = args.color_special or "#c0392b"

    template_name = numbered[args.template]
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    tpl = env.get_template(template_name + ".html.j2")
    render_vars = dict(
        ssid=args.ssid,
        password=args.password or "",
        qr_svg=qr_svg,
        color_alpha=color_alpha,
        color_number=color_number,
        color_special=color_special,
    )
    if args.greeting is not None:
        render_vars["greeting"] = args.greeting
    html_content = tpl.render(**render_vars)

    print(f"Rendering [{args.template}] {template_name} → {output_path}")
    HTML(string=html_content, base_url=str(TEMPLATES_DIR)).write_pdf(str(output_path))
    print(f"Saved: {output_path.resolve()}")


if __name__ == "__main__":
    main()
