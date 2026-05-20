"""One-time script to generate assets/format_guide.png."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont

from config import OPTIONAL_HEADERS, REQUIRED_HEADERS
OUT = ROOT / "assets" / "format_guide.png"


def main():
    rows = [("Column", "Required?")]
    for h in REQUIRED_HEADERS:
        rows.append((h, "Yes"))
    for h in OPTIONAL_HEADERS:
        rows.append((h, "No"))

    col_w = [420, 100]
    row_h = 36
    pad = 24
    w = sum(col_w) + pad * 2
    h = row_h * len(rows) + pad * 2 + 40

    img = Image.new("RGB", (w, h), "#1a1a2e")
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        header_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        cell_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except OSError:
        title_font = header_font = cell_font = ImageFont.load_default()

    draw.text((pad, pad), "List Enrichment Dropbox — CSV columns", fill="#eaeaea", font=title_font)

    y0 = pad + 36
    for ri, (c1, c2) in enumerate(rows):
        y = y0 + ri * row_h
        bg = "#16213e" if ri == 0 else ("#0f3460" if ri % 2 else "#1a1a40")
        draw.rectangle([pad, y, w - pad, y + row_h], fill=bg)
        draw.text((pad + 8, y + 8), c1, fill="#ffffff" if ri == 0 else "#e8e8e8", font=header_font if ri == 0 else cell_font)
        draw.text((pad + col_w[0] + 8, y + 8), c2, fill="#7fdbca" if c2 == "Yes" else "#aaaaaa" if c2 == "No" else "#ffffff", font=header_font if ri == 0 else cell_font)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
