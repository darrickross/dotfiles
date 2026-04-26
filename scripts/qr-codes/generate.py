#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""Generate a WiFi QR plaque PDF from a Jinja2 template."""
import argparse
import getpass
import io
import sys
from pathlib import Path

import argcomplete
import segno
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATES_DIR = Path(__file__).parent / "templates"
AUTH_CHOICES = ["WPA", "WEP", "nopass"]


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
    epilog = "Templates:\n" + "\n".join(f"  {i}  {name}" for i, name in numbered.items())

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
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    args = prompt_if_missing(args)

    output_path = (
        Path(args.output) if args.output else Path.cwd() / f"wifi-{args.ssid}.pdf"
    )
    if output_path.is_dir():
        output_path = output_path / f"wifi-{args.ssid}.pdf"

    qr_svg = build_qr_svg(args.ssid, args.password or "", args.auth)

    template_name = numbered[args.template]
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    tpl = env.get_template(template_name + ".html.j2")
    html_content = tpl.render(
        ssid=args.ssid, password=args.password or "", qr_svg=qr_svg
    )

    print(f"Rendering [{args.template}] {template_name} → {output_path}")
    HTML(string=html_content, base_url=str(TEMPLATES_DIR)).write_pdf(str(output_path))
    print(f"Saved: {output_path.resolve()}")


if __name__ == "__main__":
    main()
