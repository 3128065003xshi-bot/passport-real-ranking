"""Score each destination from data/processed/country_indicators.csv using data/raw/indicator_weights.csv.

Per field: transform (log = ln(1 + x), sqrt = square root, linear = as is), min-max scale across all countries to 0-100
(flipped when direction = lower), then multiply by weight / 100. The tourism score is
the sum of those points, so it is 0-100 when the weights add up to 100.
A missing value scores 0 and is listed in the `missing` column.
"""
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "data/raw", ROOT / "data/processed"


# sqrt sits between log and linear: it compresses big values, but less than log does.
TRANSFORMS = {"log": math.log1p, "sqrt": math.sqrt, "linear": lambda v: v}


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


rows = read(OUT / "country_indicators.csv")
weights = read(RAW / "indicator_weights.csv")

total_weight = sum(float(w["weight"]) for w in weights)
if abs(total_weight - 100) > 0.01:
    print(f"warning: weights add up to {total_weight}, not 100")

out = [{"iso2": r["iso2"], "name_zh": r["name_zh"], "name_en": r["name_en"], "missing": []} for r in rows]
for w in weights:
    field, weight = w["field"], float(w["weight"])
    values = []
    for r in rows:
        v = None if r[field] == "" else float(r[field])
        values.append(None if v is None else TRANSFORMS[w["transform"]](v))
    present = [v for v in values if v is not None]
    lo, hi = min(present), max(present)
    for o, v in zip(out, values):
        if v is None:
            score = 0.0
            o["missing"].append(field)
        else:
            score = 100 * (v - lo) / (hi - lo) if hi > lo else 100.0
            if w["direction"] == "lower":
                score = 100 - score
        o[f"{field}_score"] = round(score, 1)
        o[f"{field}_pts"] = round(score * weight / 100, 2)

pts = [f"{w['field']}_pts" for w in weights]
for o in out:
    o["tourism_score"] = round(sum(o[p] for p in pts), 2)
    o["missing"] = ";".join(o["missing"])
out.sort(key=lambda o: -o["tourism_score"])
for i, o in enumerate(out, start=1):
    o["rank"] = i

cols = (["rank", "iso2", "name_zh", "name_en", "tourism_score"]
        + [f"{w['field']}_{k}" for w in weights for k in ("score", "pts")] + ["missing"])
with open(OUT / "tourism_scores.csv", "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=cols)
    wr.writeheader()
    wr.writerows(out)
print(f"{len(out)} countries -> {OUT / 'tourism_scores.csv'}")
