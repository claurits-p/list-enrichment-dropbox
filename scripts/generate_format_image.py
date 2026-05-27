"""Generate the per-list-type format guide PNGs in assets/.

Produces:
  assets/format_guide_contacts.png
  assets/format_guide_company.png
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont

from config import (
    COMPANY_OPTIONAL_HEADERS,
    COMPANY_REQUIRED_HEADERS,
    CONTACT_NAME_HEADERS,
    CONTACT_OPTIONAL_HEADERS,
    CONTACT_REQUIRED_HEADERS,
    DOMAIN_DISPLAY_HEADER,
    LIST_TYPE_COMPANY,
    LIST_TYPE_CONTACTS,
    RECORD_TYPES,
)

ASSETS = ROOT / "assets"
OUT_CONTACTS = ASSETS / "format_guide_contacts.png"
OUT_COMPANY = ASSETS / "format_guide_company.png"

SCALE = 4  # render at 4x then downscale for very crisp text


COLOR_BG = "#ffffff"
COLOR_PANEL_BORDER = "#dfe3eb"
COLOR_TITLE = "#001F5B"           # Paystand navy
COLOR_TEXT = "#333a47"
COLOR_TEXT_MUTED = "#6a7384"
COLOR_TABLE_HEADER_BG = "#f3f5fa"
COLOR_ROW_ALT = "#fafbfd"
COLOR_RULE = "#e6e9f0"
COLOR_NAME_BAR_BG = "#fff8e6"
COLOR_NAME_BAR_BORDER = "#f0a83d"
COLOR_NAME_BAR_TITLE = "#a85d1a"
COLOR_NAME_BAR_BODY = "#5a3a08"

BADGE_REQ_BG = "#e6f5ec"
BADGE_REQ_TEXT = "#1B7A45"
BADGE_NAME_BG = "#fff4dc"
BADGE_NAME_TEXT = "#a85d1a"
BADGE_OPT_BG = "#eef0f4"
BADGE_OPT_TEXT = "#5a6473"


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        ["/System/Library/Fonts/HelveticaNeue.ttc",
         "/System/Library/Fonts/SFNS.ttf",
         "/System/Library/Fonts/Helvetica.ttc"]
        if not bold else
        ["/System/Library/Fonts/HelveticaNeue.ttc",
         "/System/Library/Fonts/SFNSDisplay-Bold.otf",
         "/System/Library/Fonts/Helvetica.ttc"]
    )
    for p in candidates:
        try:
            return ImageFont.truetype(p, size * SCALE)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_pill(draw, x, y, text, font, bg, fg, pad_x=10, pad_y=4):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    px = pad_x * SCALE
    py = pad_y * SCALE
    radius = 12 * SCALE
    draw.rounded_rectangle(
        [x, y, x + tw + px * 2, y + th + py * 2],
        radius=radius,
        fill=bg,
    )
    draw.text((x + px, y + py - bbox[1]), text, fill=fg, font=font)
    return tw + px * 2, th + py * 2


def _display_label(header: str) -> str:
    """Substitute the user-facing label for the domain column."""
    if header == "Company Domain Name":
        return DOMAIN_DISPLAY_HEADER
    return header


def _build_rows(list_type: str) -> list[tuple[str, str]]:
    if list_type == LIST_TYPE_COMPANY:
        return (
            [(_display_label(h), "Required") for h in COMPANY_REQUIRED_HEADERS]
            + [(h, "Optional") for h in COMPANY_OPTIONAL_HEADERS]
        )
    return (
        [(_display_label(h), "Required") for h in CONTACT_REQUIRED_HEADERS]
        + [(h, "One required") for h in CONTACT_NAME_HEADERS]
        + [(h, "Optional") for h in CONTACT_OPTIONAL_HEADERS]
    )


def _render(list_type: str, out_path: Path) -> tuple[int, int]:
    title_suffix = (
        "— Company list" if list_type == LIST_TYPE_COMPANY else "— Contact list"
    )
    show_name_bar = list_type == LIST_TYPE_CONTACTS

    title_h = 38
    name_bar_h = 60 if show_name_bar else 0
    name_bar_gap = 14 if show_name_bar else 8
    table_header_h = 32
    row_h = 30
    col1_pad = 16
    col2_w = 160
    pad = 22
    footer_h = 48
    rows = _build_rows(list_type)

    w = 540
    h = (
        pad + title_h + name_bar_h + name_bar_gap
        + table_header_h + row_h * len(rows) + footer_h + pad
    )

    W, H = w * SCALE, h * SCALE
    img = Image.new("RGB", (W, H), COLOR_BG)
    draw = ImageDraw.Draw(img)

    title_font = _font(20, bold=True)
    header_font = _font(12, bold=True)
    cell_font = _font(13)
    pill_font = _font(11, bold=True)
    footer_font = _font(11)
    name_bar_title_font = _font(11, bold=True)
    name_bar_body_font = _font(13)

    draw.text(
        (pad * SCALE, pad * SCALE),
        f"List Enrichment Dropbox CSV columns {title_suffix}",
        fill=COLOR_TITLE,
        font=title_font,
    )

    if show_name_bar:
        nb_top = (pad + title_h) * SCALE
        nb_bottom = nb_top + name_bar_h * SCALE
        nb_left = pad * SCALE
        nb_right = (w - pad) * SCALE
        draw.rounded_rectangle(
            [nb_left, nb_top, nb_right, nb_bottom],
            radius=8 * SCALE,
            fill=COLOR_NAME_BAR_BG,
            outline=COLOR_NAME_BAR_BORDER,
            width=int(1.5 * SCALE),
        )
        draw.text(
            (nb_left + 14 * SCALE, nb_top + 10 * SCALE),
            "NAME RULE",
            fill=COLOR_NAME_BAR_TITLE,
            font=name_bar_title_font,
        )
        draw.text(
            (nb_left + 14 * SCALE, nb_top + 28 * SCALE),
            "Include Full Name  OR  both First Name + Last Name (per row).",
            fill=COLOR_NAME_BAR_BODY,
            font=name_bar_body_font,
        )
        table_top = nb_bottom + name_bar_gap * SCALE
    else:
        table_top = (pad + title_h + name_bar_gap) * SCALE

    table_left = pad * SCALE
    table_right = (w - pad) * SCALE

    draw.rounded_rectangle(
        [table_left, table_top, table_right, table_top + table_header_h * SCALE],
        radius=6 * SCALE,
        fill=COLOR_TABLE_HEADER_BG,
    )
    draw.text(
        (table_left + col1_pad * SCALE, table_top + 9 * SCALE),
        "Column",
        fill=COLOR_TEXT,
        font=header_font,
    )
    draw.text(
        (table_right - (col2_w + 4) * SCALE, table_top + 9 * SCALE),
        "Required?",
        fill=COLOR_TEXT,
        font=header_font,
    )

    y = table_top + table_header_h * SCALE
    for ri, (column, category) in enumerate(rows):
        if ri % 2 == 0:
            draw.rectangle(
                [table_left, y, table_right, y + row_h * SCALE],
                fill=COLOR_ROW_ALT,
            )
        draw.text(
            (table_left + col1_pad * SCALE, y + 8 * SCALE),
            column,
            fill=COLOR_TEXT,
            font=cell_font,
        )

        if category == "Required":
            bg, fg, label = BADGE_REQ_BG, BADGE_REQ_TEXT, "Required"
        elif category == "One required":
            bg, fg, label = BADGE_NAME_BG, BADGE_NAME_TEXT, "Name combo"
        else:
            bg, fg, label = BADGE_OPT_BG, BADGE_OPT_TEXT, "Optional"

        bbox = draw.textbbox((0, 0), label, font=pill_font)
        tw = bbox[2] - bbox[0]
        pill_w = tw + 20 * SCALE
        px = table_right - 14 * SCALE - pill_w
        py = y + 5 * SCALE
        _draw_pill(draw, px, py, label, pill_font, bg, fg)

        if ri < len(rows) - 1:
            line_y = y + row_h * SCALE - 1
            draw.line(
                [(table_left + col1_pad * SCALE, line_y),
                 (table_right - col1_pad * SCALE, line_y)],
                fill=COLOR_RULE,
                width=1,
            )
        y += row_h * SCALE

    draw.rounded_rectangle(
        [table_left, table_top, table_right, y],
        radius=6 * SCALE,
        outline=COLOR_PANEL_BORDER,
        width=int(1.0 * SCALE),
    )

    fy = y + 14 * SCALE
    domain_tip = (
        f"Tip: {DOMAIN_DISPLAY_HEADER} also accepts Company Domain Name, "
        "Domain, Company Website, URL."
    )
    draw.text(
        (table_left, fy),
        domain_tip,
        fill=COLOR_TEXT_MUTED,
        font=footer_font,
    )
    draw.text(
        (table_left, fy + 18 * SCALE),
        f"Record Type values (per row): {' | '.join(RECORD_TYPES)}",
        fill=COLOR_TEXT_MUTED,
        font=footer_font,
    )

    final = img.resize((w, h), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, optimize=True)
    return w, h


def main() -> None:
    for list_type, out_path in (
        (LIST_TYPE_CONTACTS, OUT_CONTACTS),
        (LIST_TYPE_COMPANY, OUT_COMPANY),
    ):
        w, h = _render(list_type, out_path)
        print(f"Wrote {out_path} ({w}x{h})")


if __name__ == "__main__":
    main()
