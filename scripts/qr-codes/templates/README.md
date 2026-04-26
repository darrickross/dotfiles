# WiFi QR Plaque · Jinja2 Templates

Five standalone Jinja2 templates for printing a landscape 14:10 WiFi QR plaque.
Each `.html.j2` file is fully self-contained (inlined CSS, fonts from Google
Fonts CDN). Pick whichever direction you like and render it from your code.

## Variables

| Name             | Required | Description                                           |
| ---------------- | -------- | ----------------------------------------------------- |
| `ssid`           | yes      | Network name to display                               |
| `password`       | yes      | Password to display                                   |
| `qr_svg`         | one of   | Raw `<svg>…</svg>` markup for the QR (rendered with `\|safe`) |
| `qr_data_url`    | one of   | `data:image/...` URL — used if `qr_svg` is not set    |
| `accent`         | no       | Accent color (default `#e58a3b`)                      |
| `greeting`       | no       | Friendly headline override (varies per template)      |

Pass exactly one of `qr_svg` or `qr_data_url`.

## Usage (Python)

```python
from jinja2 import Environment, FileSystemLoader
import segno  # pip install segno

env = Environment(loader=FileSystemLoader("templates"))
tpl = env.get_template("plaque_v1_classic.html.j2")

ssid = "Casa de Wifi"
password = "guest-2026"

# Build a WiFi-format QR so phones recognize it
wifi_payload = f"WIFI:T:WPA;S:{ssid};P:{password};;"
qr = segno.make(wifi_payload, error="m")

import io
buf = io.StringIO()
qr.save(buf, kind="svg", scale=1, border=0, xmldecl=False, svgns=False)
qr_svg = buf.getvalue()

html = tpl.render(ssid=ssid, password=password, qr_svg=qr_svg)
open("plaque.html", "w").write(html)
```

Then print to PDF at A4 / Letter landscape, or open in a browser.

## Files

- `plaque_v1_classic.html.j2`     — Classic split, squiggle divider
- `plaque_v2_bubble.html.j2`      — Speech bubble, corner ticks
- `plaque_v3_tag.html.j2`         — Luggage tag with perforation
- `plaque_v4_postcard.html.j2`    — Tilted polaroid collage
- `plaque_v5_type.html.j2`        — Typographic / minimal
