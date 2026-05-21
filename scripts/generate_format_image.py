"""One-time script to generate assets/format_guide.png."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont

from config import NAME_HEADERS, OPTIONAL_HEADERS, REQUIRED_HEADERS

OUT = ROOT / "assets" / "format_guide.png"

# Render at 2x then downscale for crisper anti-aliased text
SCALE = 2


def _font(path_candidates: list[str], size: int) -> ImageFont.ImageFont:
    for p in path_candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    from config import RECORD_TYPES
    rows: list[tuple[str, str]] = [("Column", "Required")]
    for h in REQUIRED_HEADERS:
        rows.append((h, "Yes"))
    for h in NAME_HEADERS:
        rows.append((h, "Name combo"))
    for h in OPTIONAL_HEADERS:
        rows.append((h, "No"))
    record_type_values = " | ".join(RECORD_TYPES)

    col_w = [320, 150]
    row_h = 30
    pad = 20
    title_h = 36
    callout_h = 56
    footnote_h_pad = 44
    w = sum(col_w) + pad * 2
    h = title_h + callout_h + row_h * len(rows) + pad * 2 + footnote_h_pad

    W, H = w * SCALE, h * SCALE
    img = Image.new("RGB", (W, H), "#0c1733")
    draw = ImageDraw.Draw(img)

    title_font = _font(
        ["/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"],
        18 * SCALE,
    )
    header_font = _font(
        ["/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"],
        13 * SCALE,
    )
    cell_font = _font(
        ["/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"],
        12 * SCALE,
    )
    callout_title_font = _font(
        ["/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"],
        12 * SCALE,
    )
    callout_body_font = _font(
        ["/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"],
        13 * SCALE,
    )

    draw.text(
        (pad * SCALE, pad * SCALE),
        "List Enrichment Dropbox CSV columns",
        fill="#ffffff",
        font=title_font,
    )

    callout_x = pad * SCALE
    callout_y = (pad + title_h) * SCALE
    callout_x2 = (w - pad) * SCALE
    callout_y2 = callout_y + (callout_h - 8) * SCALE
    draw.rectangle(
        [callout_x, callout_y, callout_x2, callout_y2],
        fill="#3a2a08",
        outline="#f0a83d",
        width=2,
    )
    draw.text(
        (callout_x + 12 * SCALE, callout_y + 8 * SCALE),
        "NAME RULE",
        fill="#f5c66c",
        font=callout_title_font,
    )
    draw.text(
        (callout_x + 12 * SCALE, callout_y + 24 * SCALE),
        "Include Full Name  OR  both First Name + Last Name (per row).",
        fill="#ffe7b8",
        font=callout_body_font,
    )

    y0 = (pad + title_h + callout_h) * SCALE
    footnote_h = 18
    for ri, (c1, c2) in enumerate(rows):
        y = y0 + ri * row_h * SCALE
        if ri == 0:
            bg = "#102251"
        else:
            bg = "#0f1e44" if ri % 2 else "#13265a"
        draw.rectangle(
            [pad * SCALE, y, (w - pad) * SCALE, y + row_h * SCALE],
            fill=bg,
        )

        text_color_left = "#ffffff" if ri == 0 else "#e8ecf6"
        if ri == 0:
            text_color_right = "#ffffff"
        elif c2 == "Yes":
            text_color_right = "#7fdbca"
        elif c2 == "Name combo":
            text_color_right = "#f5c66c"
        else:
            text_color_right = "#9aa3b6"

        draw.text(
            ((pad + 10) * SCALE, y + 6 * SCALE),
            c1,
            fill=text_color_left,
            font=header_font if ri == 0 else cell_font,
        )
        draw.text(
            ((pad + col_w[0] + 10) * SCALE, y + 6 * SCALE),
            c2,
            fill=text_color_right,
            font=header_font if ri == 0 else cell_font,
        )

    footnote_y = y0 + len(rows) * row_h * SCALE + 8 * SCALE
    draw.text(
        (pad * SCALE, footnote_y),
        "Tip: Company Domain Name accepts these headers: Domain, Website, Company Website, URL.",
        fill="#9aa3b6",
        font=cell_font,
    )
    draw.text(
        (pad * SCALE, footnote_y + 18 * SCALE),
        f"Record Type values (per row): {record_type_values}",
        fill="#9aa3b6",
        font=cell_font,
    )

    final = img.resize((w, h), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    final.save(OUT, optimize=True)
    print(f"Wrote {OUT} ({w}x{h}, rendered at {W}x{H})")


if __name__ == "__main__":
    main()
