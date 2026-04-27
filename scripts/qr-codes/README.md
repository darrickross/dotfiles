# WiFi QR Plaque Generator

Generates a printable PDF WiFi plaque (landscape 14×10 in) from a Jinja2 HTML template.
The `wifi-qr` shell alias wraps `scripts/qr-codes/generate.py`.

## Usage

```bash
wifi-qr -s <SSID> -p <password> [options]
```

All parameters can be passed as flags or left out to be prompted interactively.
The password is prompted securely (hidden input) when omitted.

### Parameters

| Flag                             | Short | Default               | Description                                                      |
| -------------------------------- | ----- | --------------------- | ---------------------------------------------------------------- |
| `--ssid`                         | `-s`  | prompted              | Network name. Max 32 bytes UTF-8.                                |
| `--password`                     | `-p`  | prompted              | WiFi password. Max 63 characters.                                |
| `--auth`                         | `-a`  | `WPA`                 | Encryption standard: `WPA`, `WEP`, or `nopass`                   |
| `--template`                     | `-t`  | `0`                   | Template number (see list below)                                 |
| `--output`                       | `-o`  | `./wifi-<ssid>.pdf`   | Output file or directory                                         |
| `--greeting`                     | `-g`  | *(template default)*  | Override the greeting text on the plaque                         |
| `--verbose`                      | `-v`  | off                   | Print WeasyPrint rendering warnings and errors to stderr         |
| `--no-text-color`                |       | off                   | Render all credential characters in the default ink color        |
| `--color-alpha`                  |       | `inherit`             | Color for **letter** characters (hex, e.g. `#2d6a4f`)            |
| `--color-number`                 |       | `#1f5fd9`             | Color for **digit** characters                                   |
| `--color-special`                |       | `#c0392b`             | Color for **symbol** characters                                  |
| `--ignore-ssid-character-check`  |       | off                   | Skip the unsafe-character warning (length limit still applies)   |
| `--scale-w`                      |       | *(none)*              | Scale output PDF to this width in inches (requires `--scale-h`)  |
| `--scale-h`                      |       | *(none)*              | Scale output PDF to this height in inches (requires `--scale-w`) |

### Validation

#### SSID

- Hard limit: SSID must be ≤ 32 bytes (UTF-8 encoded). The script exits if exceeded.
- Soft warning: characters outside `[A-Za-z0-9_.-]` prompt a confirmation before continuing. Pass `--ignore-ssid-character-check` to skip the prompt.

#### Password

- Hard limit: password must be ≤ 63 characters. The script exits if exceeded.

### Examples

```bash
# Basic — prompts for password
wifi-qr -s HomeNetwork

# Fully scripted
wifi-qr -s HomeNetwork -p s3cr3t -t 2 -o ~/Desktop/

# Custom greeting and accent colors
wifi-qr -s HomeNetwork -p s3cr3t -g "Make yourself at home." --color-number "#2d6a4f"

# No color coding on credentials
wifi-qr -s HomeNetwork -p s3cr3t --no-text-color
```

## Templates

| # | File                          | Style                               |
| - | ----------------------------- | ----------------------------------- |
| 0 | `plaque_v0_classic.html.j2`   | Classic split with squiggle divider |
| 1 | `plaque_v1_bubble.html.j2`    | Speech bubble with corner ticks     |
| 2 | `plaque_v2_tag.html.j2`       | Luggage tag with dashed separator   |
| 3 | `plaque_v3_postcard.html.j2`  | Tilted polaroid collage             |
| 4 | `plaque_v4_type.html.j2`      | Typographic / minimal               |

Template order is determined by filename sort — `plaque_v0_*` → 0, `plaque_v1_*` → 1, etc.

## Adding a new template

Create a `.html.j2` file in `templates/`. The script auto-discovers all `*.html.j2` files
(excluding those prefixed with `_`) and assigns numbers by sort order.

Your template will receive these Jinja2 variables:

| Variable        | Always set | Description                                                 |
| --------------- | ---------- | ----------------------------------------------------------- |
| `ssid`          | yes        | Network name string                                         |
| `password`      | yes        | Password string (empty string for `nopass`)                 |
| `qr_svg`        | yes        | Raw `<svg>…</svg>` markup — render with `\| safe`           |
| `accent`        | no         | Accent color hex (use `\| default('#e58a3b')`)              |
| `greeting`      | no         | Greeting override (use `\| default('your text')`)           |
| `color_alpha`   | yes        | CSS color for letter spans (`inherit` when colors disabled) |
| `color_number`  | yes        | CSS color for digit spans                                   |
| `color_special` | yes        | CSS color for symbol spans                                  |

Use the `colorize` macro to render credential values with per-character coloring. It also inserts a `<wbr>` soft-break hint every 10 characters to allow wrapping on long values:

```jinja
{%- macro colorize(text) -%}
{%- for ch in text -%}
{%- if ch.isalpha() %}<span class="ch-letter">{{ ch }}</span>
{%- elif ch.isdigit() %}<span class="ch-digit">{{ ch }}</span>
{%- elif ch == ' ' %}<span class="ch-space">&nbsp;</span>
{%- else %}<span class="ch-symbol">{{ ch | e }}</span>
{%- endif -%}
{%- if loop.index % 10 == 0 %}<wbr>{%- endif -%}
{%- endfor -%}
{%- endmacro -%}
```

Wire it up in CSS using the provided variables:

```css
.ch-letter { color: {{ color_alpha }}; }
.ch-digit  { color: {{ color_number }}; }
.ch-symbol { color: {{ color_special }}; }
.ch-space  { display: inline-block; }
```

Use the `fit_size` macro to scale font size based on text length, so long SSIDs or passwords don't overflow their box:

```jinja
{%- macro fit_size(text) -%}
{%- set n = (text | string | length) -%}
{%- if n <= 14 -%}80px
{%- elif n <= 22 -%}65px
{%- elif n <= 32 -%}51px
{%- elif n <= 42 -%}43px
{%- elif n <= 52 -%}38px
{%- elif n <= 63 -%}32px
{%- else -%}27px
{%- endif -%}
{%- endmacro -%}
```

Apply it inline on credential and greeting elements:

```html
<div class="value" style="font-size: {{ fit_size(ssid) }}">{{ colorize(ssid) }}</div>
<div class="greeting" style="font-size: {{ fit_size(greeting | default('Hi!')) }}">…</div>
```

Greetings use an accent-colored underline highlight rendered as a CSS gradient on a wrapper `<span>`:

```html
<span class="greeting-hl">{{ greeting | default('Hi!') }}</span>
```

```css
.greeting-hl {
  background: linear-gradient(transparent 68%, {{ accent | default('#e58a3b') ~ '59' }} 68%);
  -webkit-box-decoration-break: clone;
  box-decoration-break: clone;
}
```

Use `px` units for font sizes — WeasyPrint does not reliably support container query
units (`cqw`). The print page is 14in × 10in at 96 dpi = **1344 × 960 px**.

## Generating the examples

The `examples/` directory is generated by running each template with a matching SSID:

```bash
for t in 0 1 2 3 4; do wifi-qr -s "Example-$t" -t $t -p 'TEST123!@#' -o ./scripts/qr-codes/examples/; done
```
