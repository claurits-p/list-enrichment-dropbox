"""Generate assets/format_guide.png — dark navy theme, crisp text."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont

from config import NAME_HEADERS, OPTIONAL_HEADERS, RECORD_TYPES, REQUIRED_HEADERS

OUT = ROOT / "assets" / "format_guide.png"

SCALE = 4  # render at 4x then downscale for very crisp text

COLOR_BG = "#0c1733"
COLOR_TITLE = "#ffffff"
COLOR_TEXT = "#e8ecf6"
COLOR_TEXT_MUTED = "#9aa3b6"
COLOR_HEADER_BG = "#102251"
COLOR_HEADER_TEXT = "#ffffff"
COLOR_ROW_A = "#13265a"
COLOR_ROW_B = "#0f1e44"
COLOR_YES = "#7fdbca"
COLOR_NAME = "#f5c66c"
COLOR_OPT = "#9aa3b6"
COLOR_CALLOUT_BG = "#3a2a08"
COLOR_CALLOUT_BORDER = "#f0a83d"
COLOR_CALLOUT_TITLE = "#f5c66c"
COLOR_CALLOUT_BODY = "#ffe7b8"


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size * SCALE)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    rows: list[tuple[str, str]] = [("Column", "Required")]
    for h in REQUIRED_HEADERS:
        rows.append((h, "Yes"))
    for h in NAME_HEADERS:
        rows.append((h, "Name combo"))
    for h in OPTIONAL_HEADERS:
        rows.append((h, "No"))

    col_w = [320, 150]
    row_h = 30
    pad = 20
    title_h = 36
    callout_h = 56
    footnote_h = 44
    w = sum(col_w) + pad * 2
    h_total = title_h + callout_h + row_h * len(rows) + pad * 2 + footnote_h

    W, H = w * SCALE, h_total * SCALE
    img = Image.new("RGB", (W, H), COLOR_BG)
    draw = ImageDraw.Draw(img)

    title_font = _font(18, bold=True)
    header_font = _font(13, bold=True)
    cell_font = _font(12)
    callout_title_font = _font(11, bold=True)
    callout_body_font = _font(13)

    # title
    draw.text((pad * SCALE, pad * SCALE), "List Enrichment Dropbox CSV columns",
              fill=COLOR_TITLE, font=title_font)

    # callout
    cx = pad * SCALE
    cy = (pad + title_h) * SCALE
    cx2 = (w - pad) * SCALE
    cy2 = cy + (callout_h - 8) * SCALE
    draw.rounded_rectangle(
        [cx, cy, cx2, cy2],
        radius=6 * SCALE,
        fill=COLOR_CALLOUT_BG,
        outline=COLOR_CALLOUT_BORDER,
        width=int(1.5 * SCALE),
    )
    draw.text((cx + 12 * SCALE, cy + 8 * SCALE), "NAME RULE",
              fill=COLOR_CALLOUT_TITLE, font=callout_title_font)
    draw.text((cx + 12 * SCALE, cy + 24 * SCALE),
              "Include Full Name  OR  both First Name + Last Name (per row).",
              fill=COLOR_CALLOUT_BODY, font=callout_body_font)

    # table
    y0 = (pad + title_h + callout_h) * SCALE
    for ri, (c1, c2) in enumerate(rows):
        y = y0 + ri * row_h * SCALE
        if ri == 0:
            bg = COLOR_HEADER_BG
        else:
            bg = COLOR_ROW_B if ri % 2 else COLOR_ROW_A
        draw.rectangle(
            [pad * SCALE, y, (w - pad) * SCALE, y + row_h * SCALE],
            fill=bg,
        )

        if ri == 0:
            tcr = COLOR_HEADER_TEXT
        elif c2 == "Yes":
            tcr = COLOR_YES
        elif c2 == "Name combo":
            tcr = COLOR_NAME
        else:
            tcr = COLOR_OPT
        tcl = COLOR_HEADER_TEXT if ri == 0 else COLOR_TEXT

        draw.text(((pad + 10) * SCALE, y + 6 * SCALE), c1, fill=tcl,
                  font=header_font if ri == 0 else cell_font)
        draw.text(((pad + col_w[0] + 10) * SCALE, y + 6 * SCALE), c2, fill=tcr,
                  font=header_font if ri == 0 else cell_font)

    # footnotes
    fy = y0 + len(rows) * row_h * SCALE + 8 * SCALE
    draw.text((pad * SCALE, fy),
              "Tip: Company Domain Name accepts these headers: Domain, Website, Company Website, URL.",
              fill=COLOR_TEXT_MUTED, font=cell_font)
    draw.text((pad * SCALE, fy + 18 * SCALE),
              f"Record Type values (per row): {' | '.join(RECORD_TYPES)}",
              fill=COLOR_TEXT_MUTED, font=cell_font)

    final = img.resize((w, h_total), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    final.save(OUT, optimize=True)
    print(f"Wrote {OUT} ({w}x{h_total}, rendered at {W}x{H})")


if __name__ == "__main__":
    main()
