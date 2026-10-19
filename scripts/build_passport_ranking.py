"""Rank passports: data/processed/passport_ranking.csv.

passport_score = sum over all destinations (home country included, at the '-' weight)
of entry-code weight / 100 * destination tourism score.
pct_of_max divides that by the score of a passport that could enter everywhere at 100.
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "data/raw", ROOT / "data/processed"


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


tourism = {r["iso2"]: float(r["tourism_score"]) for r in read(OUT / "tourism_scores.csv")}
weights = {r["code"]: float(r["weight"]) for r in read(RAW / "entry_codes.csv")}
countries = {r["iso2"]: r for r in read(RAW / "countries.csv") if r["include"] == "1"}

score, codes = defaultdict(float), defaultdict(Counter)
for r in read(OUT / "visa_matrix.csv"):
    p, d, c = r["passport"], r["destination"], r["code"]
    score[p] += weights[c] / 100 * tourism[d]
    codes[p][c] += 1

max_score = sum(tourism.values())
ranked = sorted(score, key=lambda p: -score[p])

with open(OUT / "passport_ranking.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["rank", "iso2", "name_zh", "name_en", "passport_score", "pct_of_max", "home_tourism_score",
                "S", "A", "B", "C", "D", "E", "F", "visa_free_like"])
    rank = 0
    for i, p in enumerate(ranked):
        if i == 0 or round(score[p], 2) != round(score[ranked[i - 1]], 2):
            rank = i + 1
        k = codes[p]
        w.writerow([rank, p, countries[p]["name_zh"], countries[p]["name_en"], round(score[p], 2),
                    round(100 * score[p] / max_score, 2), tourism[p],
                    *(k[c] for c in "SABCDEF"), sum(k[c] for c in "SABC")])
print(f"{len(ranked)} passports -> {OUT / 'passport_ranking.csv'}")
