"""Build data/processed/visa_matrix.csv from the base snapshot + free-movement groups + overrides.

Order: base dataset -> free-movement groups (S) -> overrides (top to bottom, later rows win).
In visa_overrides.csv, passport/destination/only_if/except take ';'-separated lists, '*' means all.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "data/raw", ROOT / "data/processed"
BASE = RAW / "passport_index_2025-01-12.csv"

BASE_CODES = {"visa free": "A", "eta": "B", "visa on arrival": "C", "e-visa": "D",
              "visa required": "E", "no admission": "F", "-1": "-"}


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split(field, universe):
    field = field.strip()
    if field == "*":
        return set(universe)
    return {x.strip() for x in field.split(";") if x.strip()}


countries = [r for r in read(RAW / "countries.csv") if r["include"] == "1"]
codes = [c["iso2"] for c in countries]
weights = {r["code"]: r["weight"] for r in read(RAW / "entry_codes.csv")}

matrix = {}
for r in read(BASE):
    req = r["Requirement"]
    code, days = (("A", req) if req.isdigit() else (BASE_CODES[req], ""))
    matrix[r["Passport"], r["Destination"]] = {"code": code, "days": days,
                                               "source": "passport_index_2025-01-12", "note": ""}

for g in read(RAW / "free_movement_groups.csv"):
    if g["enabled"] != "1":
        continue
    members = split(g["members"], codes)
    for p in members:
        for d in members:
            if p != d:
                matrix[p, d] = {"code": "S", "days": "", "source": f"group:{g['group']}", "note": g["note"]}

for i, o in enumerate(read(RAW / "visa_overrides.csv"), start=2):
    only_if = split(o["only_if"], weights) if o["only_if"] else None
    excluded = split(o["except"], codes) if o["except"] else set()
    for p in split(o["passport"], codes) - excluded:
        for d in split(o["destination"], codes) - excluded:
            if p == d or (p, d) not in matrix:
                continue
            if only_if and matrix[p, d]["code"] not in only_if:
                continue
            matrix[p, d] = {"code": o["code"], "days": o["days"],
                            "source": f"override:row{i}", "note": o["note"]}

OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "visa_matrix.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["passport", "destination", "code", "weight", "days", "source", "note"])
    for (p, d), v in sorted(matrix.items()):
        w.writerow([p, d, v["code"], weights.get(v["code"], ""), v["days"], v["source"], v["note"]])

# Wide view for eyeballing in Excel: rows = passport, columns = destination.
with open(OUT / "visa_matrix_wide.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["passport", "name_zh"] + codes)
    for c in countries:
        w.writerow([c["iso2"], c["name_zh"]] + [matrix.get((c["iso2"], d), {}).get("code", "") for d in codes])

print(f"{len(matrix)} pairs -> {OUT / 'visa_matrix.csv'}")
