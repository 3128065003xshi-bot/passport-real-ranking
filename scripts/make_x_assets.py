"""Render the images for the X Article (X's editor has no tables or charts) into assets/x/.

01-ranking-chart.png   21 passports, % of max
02-entry-codes.png     entry codes and weights
03-indicators.png      destination-score indicators and weights
04-four-passports.png  Switzerland / US / China / Iran breakdown

Needs Pillow and macOS's Helvetica Neue, like make_header.py.
"""
import csv
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC, OUT = ROOT / "data/raw", ROOT / "data/processed", ROOT / "assets/x"
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
REGULAR, BOLD, MEDIUM = 0, 1, 10
BG, INK, QUIET, RULE, BAR, ACCENT, HEAD_BG = "#FFFFFF", "#0E1A2B", "#5B6B82", "#DDE3EA", "#C3CBD6", "#2F6FE4", "#F2F5F9"
W, PAD = 2000, 80


def font(size, face=REGULAR):
    return ImageFont.truetype(FONT, size, index=face)


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def one_dp(value):
    return Decimal(value).quantize(Decimal("0.1"), ROUND_HALF_UP)


def title_block(d, title, subtitle):
    d.text((PAD, 60), title, font=font(52, BOLD), fill=INK)
    d.text((PAD, 130), subtitle, font=font(32), fill=QUIET)
    return 210


def table(name, title, subtitle, header, rows, widths, bold_first_col=True):
    """Simple table: widths are column widths in px, summing to W - 2 * PAD."""
    row_h, head_h = 74, 70
    h = 210 + head_h + row_h * len(rows) + 60
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    y = title_block(d, title, subtitle)
    d.rectangle((PAD, y, W - PAD, y + head_h), fill=HEAD_BG)
    x = PAD
    for text, w in zip(header, widths):
        d.text((x + 20, y + 20), text, font=font(30, MEDIUM), fill=QUIET)
        x += w
    y += head_h
    for row in rows:
        x = PAD
        for c, (text, w) in enumerate(zip(row, widths)):
            d.text((x + 20, y + 20), str(text), font=font(32, BOLD if c == 0 and bold_first_col else REGULAR), fill=INK)
            x += w
        y += row_h
        d.line((PAD, y, W - PAD, y), fill=RULE, width=2)
    img.save(OUT / name, optimize=True)


def ranking_chart(ranking):
    shown = ["SE", "ES", "DE", "CH", "KR", "SG", "JP", "AE", "AU", "GB", "CA", "US",
             "HK", "BR", "MX", "MO", "TW", "RU", "CN", "IN", "SY"]
    labels = {"AE": "UAE", "HK": "Hong Kong", "MO": "Macao"}
    focus = {"US", "CN"}
    step, bar_h, label_x, bar_x, bar_w = 62, 36, PAD, PAD + 420, 1300
    h = 230 + step * len(shown) + 50
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    y = title_block(d, "The top 16 passports are all European; the US is 43rd, China 116th",
                    "Passport score as % of the maximum (100 at all 199 destinations), 21 passports in rank order")
    y += 20
    for iso2 in shown:
        r = ranking[iso2]
        pct, bold = float(r["pct_of_max"]), iso2 in focus
        d.text((label_x, y + 2), f"#{r['rank']}", font=font(30), fill=QUIET)
        d.text((label_x + 110, y - 2), labels.get(iso2, r["name_en"]), font=font(34, BOLD if bold else REGULAR), fill=INK)
        d.rounded_rectangle((bar_x, y, bar_x + bar_w * pct / 100, y + bar_h), radius=6,
                            fill=ACCENT if bold else BAR)
        d.text((bar_x + bar_w * pct / 100 + 18, y - 1), f"{one_dp(r['pct_of_max'])}%",
               font=font(32, BOLD if bold else REGULAR), fill=INK)
        y += step
    img.save(OUT / "01-ranking-chart.png", optimize=True)


OUT.mkdir(parents=True, exist_ok=True)
ranking = {r["iso2"]: r for r in read(PROC / "passport_ranking.csv")}
tourism = {r["iso2"]: r for r in read(PROC / "tourism_scores.csv")}
codes = read(RAW / "entry_codes.csv")
matrix = read(PROC / "visa_matrix.csv")

ranking_chart(ranking)

pairs = Counter(r["code"] for r in matrix)
examples = {"S": "Within the EU, UK–Ireland, GCC, Mercosur", "A": "A Japanese passport entering France",
            "B": "UK ETA, Canada eTA, US ESTA", "C": "Issued at the border, fee and queue",
            "D": "Applied for online before departure", "E": "Embassy, consulate or visa centre",
            "F": "2026 US travel ban; North Korea"}
table("02-entry-codes.png", "Model 1: the real barrier is the embassy",
      "S to D span 22 points; D to E drops 70",
      ["Code", "Entry type", "Weight", "Example", "Pairs"],
      [(c["code"], c["name_en"], c["weight"], examples[c["code"]], f"{pairs[c['code']]:,}")
       for c in codes if c["code"] in examples],
      [140, 420, 160, 880, 240])

names = {"gdp_per_capita_usd": "GDP per capita", "tourist_arrivals_m": "Inbound overnight tourists",
         "nature_score": "Nature & scenery", "gdp_usd_bn": "Total GDP", "culture_score": "Culture & heritage",
         "price_level_us100": "Price level (US = 100)", "crime_index": "Crime index",
         "cities_1m_plus": "Cities 1M+", "cities_5m_plus": "Cities 5M+", "cities_10m_plus": "Cities 10M+"}
transforms = {"log": "Log", "sqrt": "Square root", "linear": "Linear"}
weights = sorted(read(RAW / "indicator_weights.csv"), key=lambda w: -round(float(w["weight"]), 1))
table("03-indicators.png", "Model 2: what makes a destination worth visiting",
      "10 indicators, each scaled 0–100 across 199 countries, weighted to a 100-point tourism score",
      ["Indicator", "Weight", "Direction", "Transform"],
      [(names[w["field"]], f"{float(w['weight']):g}" if float(w["weight"]) % 1 in (0, 0.5) else "3.33",
        "Higher is better" if w["direction"] == "higher" else "Lower is better",
        transforms[w["transform"]] + (f", capped at ${int(w['cap']) // 1000}k" if w.get("cap") else ""))
       for w in weights],
      [620, 220, 400, 600])

four = ["CH", "US", "CN", "IR"]
count = {p: Counter(r["code"] for r in matrix if r["passport"] == p) for p in four}
rows = [("Passport rank", *(ranking[p]["rank"] for p in four)),
        ("% of max", *(f"{one_dp(ranking[p]['pct_of_max'])}%" for p in four))]
rows += [(f"{c['code']}  {c['name_en']}", *(count[p][c["code"]] for p in four)) for c in codes if c["code"] != "-"]
rows.append(("Tourism score as a destination", *(f"{one_dp(tourism[p]['tourism_score'])} (#{tourism[p]['rank']})" for p in four)))
table("04-four-passports.png", "Great destinations, weaker passports",
      "Destinations reached by each entry type, out of 199",
      ["", "Switzerland", "United States", "China", "Iran"], rows, [640, 300, 300, 300, 300])

print(f"4 images -> {OUT}")
