"""Render the 5:2 header image (assets/header.png, 3000x1200) from data/processed/passport_ranking.csv.

Needs Pillow (pip install pillow) and macOS's Helvetica Neue; everything else in this repo is stdlib only.
"""
import csv
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/header.png"
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
REGULAR, BOLD, LIGHT, MEDIUM = 0, 1, 7, 10

W, H = 3000, 1200
BG, INK, QUIET, BAR, ACCENT = "#0E1A2B", "#FFFFFF", "#8FA3BF", "#3A4B63", "#4C8DFF"
SHOWN = [("SE", "Sweden"), ("JP", "Japan"), ("US", "United States"), ("CN", "China"), ("AF", "Afghanistan")]


def font(size, face=REGULAR):
    return ImageFont.truetype(FONT, size, index=face)


with open(ROOT / "data/processed/passport_ranking.csv", encoding="utf-8-sig") as f:
    ranking = {r["iso2"]: r for r in csv.DictReader(f)}

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# Left: the pitch.
x0 = 170
d.text((x0, 300), "PASSPORT REAL RANKING", font=font(54, MEDIUM), fill=ACCENT)
d.text((x0, 390), "What is your passport", font=font(124, BOLD), fill=INK)
d.text((x0, 530), "really worth?", font=font(124, BOLD), fill=INK)
d.text((x0, 730), "199 passports, weighted by how much", font=font(56, LIGHT), fill=QUIET)
d.text((x0, 805), "every destination they unlock is worth.", font=font(56, LIGHT), fill=QUIET)
d.text((x0, 990), "github.com/3128065003xshi-bot/passport-real-ranking", font=font(40), fill=QUIET)

# Right: five passports as bars, % of the maximum score.
label_x, bar_x, bar_w, top, step, bar_h = 1700, 2210, 560, 380, 150, 44
d.text((label_x, top - 100), "% of maximum score", font=font(40), fill=QUIET)
for i, (iso2, name) in enumerate(SHOWN):
    r = ranking[iso2]
    pct, y = float(r["pct_of_max"]), top + i * step
    shown = Decimal(r["pct_of_max"]).quantize(Decimal("0.1"), ROUND_HALF_UP)  # 87.25 -> 87.3, as in the article
    lead = i == 0
    d.text((label_x, y - 8), f"#{r['rank']}", font=font(40), fill=QUIET)
    d.text((label_x + 110, y - 14), name, font=font(52, MEDIUM if lead else REGULAR), fill=INK)
    d.rounded_rectangle((bar_x, y, bar_x + bar_w * pct / 100, y + bar_h), radius=10,
                        fill=ACCENT if lead else BAR)
    d.text((bar_x + bar_w * pct / 100 + 24, y - 6), f"{shown}%", font=font(48, BOLD if lead else REGULAR),
           fill=INK)

OUT.parent.mkdir(exist_ok=True)
img.save(OUT, optimize=True)
print(f"{W}x{H} -> {OUT}")
