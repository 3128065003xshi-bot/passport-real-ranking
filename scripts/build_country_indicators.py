"""Build data/processed/country_indicators.csv from the source snapshots in data/raw/sources/
plus hand-entered values in data/raw/manual_estimates.csv and data/raw/manual_scores.csv.

Manual estimates fill gaps; a row with override = 1 also replaces a distorted source value.
"""
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, SRC, OUT = ROOT / "data/raw", ROOT / "data/raw/sources", ROOT / "data/processed"

# crime_index = 100 * log(1 + homicides per 100k) / log(1 + CRIME_CAP), capped at 100.
CRIME_CAP = 40


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


countries = [r for r in read(RAW / "countries.csv") if r["include"] == "1"]

# World Bank: latest value per (country, indicator); arrivals already capped at 2019 in the snapshot.
wb = {}
for r in read(SRC / "worldbank_2010-2025.csv"):
    key = (r["iso2"], r["indicator"])
    if key not in wb or int(r["year"]) > wb[key][0]:
        wb[key] = (int(r["year"]), float(r["value"]))

# Price level = PPP factor (private consumption) / market exchange rate, same year, US = 100.
by_year = defaultdict(dict)
for r in read(SRC / "worldbank_2010-2025.csv"):
    if r["indicator"] in ("PA.NUS.PRVT.PP", "PA.NUS.FCRF"):
        by_year[r["iso2"], int(r["year"])][r["indicator"]] = float(r["value"])
price = {}
for (iso2, year), v in by_year.items():
    if len(v) == 2 and (iso2 not in price or year > price[iso2][0]):
        price[iso2] = (year, v["PA.NUS.PRVT.PP"] / v["PA.NUS.FCRF"])
us_ratio = price["US"][1]
price = {k: (y, 100 * r / us_ratio) for k, (y, r) in price.items()}

cities = defaultdict(list)
for r in read(SRC / "un_wup2018_cities_300k_2020.csv"):
    cities[r["iso2"]].append(float(r["pop_2020_k"]))

whs = defaultdict(Counter)
for r in read(SRC / "unesco_whs_2024.csv"):
    whs[r["iso2"]][r["category"]] += 1

# UN Tourism overnight arrivals (via Our World in Data). Prefer 2023+, then pre-COVID 2017-2019,
# then 2022 (still COVID-depressed); anything else falls back to World Bank 2019 / manual.
untourism = defaultdict(dict)
for r in read(SRC / "untourism_overnight_arrivals_1995-2024.csv"):
    untourism[r["iso2"]][int(r["year"])] = float(r["overnight_arrivals"])


def pick_arrivals(iso2):
    years = untourism.get(iso2, {})
    for pool in ([y for y in years if y >= 2023], [y for y in years if 2017 <= y <= 2019],
                 [y for y in years if y == 2022]):
        if pool:
            return max(pool), years[max(pool)]
    return None


manual = {(r["iso2"], r["field"]): r for r in read(RAW / "manual_estimates.csv")}
scores = {r["iso2"]: r for r in read(RAW / "manual_scores.csv")}

FIELDS = {  # output field -> World Bank indicator
    "gdp_usd": "NY.GDP.MKTP.CD",
    "gdp_per_capita_usd": "NY.GDP.PCAP.CD",
    "population": "SP.POP.TOTL",
    "tourist_arrivals": "ST.INT.ARVL",
    "homicide_per_100k": "VC.IHR.PSRC.P5",
}

rows = []
for c in countries:
    iso2, est = c["iso2"], []
    vals = {}
    for field, ind in FIELDS.items():
        forced = manual.get((iso2, field), {}).get("override") == "1"
        if (iso2, ind) in wb and not forced:
            vals[field] = wb[iso2, ind]
        elif (iso2, field) in manual:
            m = manual[iso2, field]
            vals[field] = (int(m["year"]), float(m["value"]))
            est.append(field)
        else:
            vals[field] = (None, None)
    forced = manual.get((iso2, "price_level_us100"), {}).get("override") == "1"
    arrivals_source = "UN Tourism"
    if pick_arrivals(iso2):
        vals["tourist_arrivals"] = pick_arrivals(iso2)
        est = [f for f in est if f != "tourist_arrivals"]
    elif "tourist_arrivals" not in est and vals["tourist_arrivals"][1] is not None:
        arrivals_source = "World Bank"
    else:
        arrivals_source = "estimate"

    if iso2 in price and not forced:
        vals["price_level_us100"] = price[iso2]
    elif (iso2, "price_level_us100") in manual:
        m = manual[iso2, "price_level_us100"]
        vals["price_level_us100"] = (int(m["year"]), float(m["value"]))
        est.append("price_level_us100")
    else:
        vals["price_level_us100"] = (None, None)

    h = vals["homicide_per_100k"][1]
    crime = None if h is None else min(100, round(100 * math.log1p(h) / math.log1p(CRIME_CAP)))
    pops = cities[iso2]
    fmt = lambda v, nd: "" if v is None else round(v, nd)
    scaled = lambda field, d: None if vals[field][1] is None else vals[field][1] / d
    rows.append({
        "iso2": iso2, "name_zh": c["name_zh"], "name_en": c["name_en"],
        "gdp_usd_bn": fmt(scaled("gdp_usd", 1e9), 1),
        "gdp_per_capita_usd": fmt(vals["gdp_per_capita_usd"][1], 0),
        "gdp_year": vals["gdp_usd"][0] or "",
        "population_m": fmt(scaled("population", 1e6), 3),
        "cities_1m_plus": sum(p >= 1000 for p in pops),
        "cities_5m_plus": sum(p >= 5000 for p in pops),
        "cities_10m_plus": sum(p >= 10000 for p in pops),
        "tourist_arrivals_m": fmt(scaled("tourist_arrivals", 1e6), 3),
        "arrivals_year": vals["tourist_arrivals"][0] or "",
        "arrivals_source": arrivals_source,
        "price_level_us100": fmt(vals["price_level_us100"][1], 0),
        "price_year": vals["price_level_us100"][0] or "",
        "homicide_per_100k": fmt(h, 2),
        "crime_index": "" if crime is None else crime,
        "nature_score": scores[iso2]["nature_score"],
        "culture_score": scores[iso2]["culture_score"],
        "whs_cultural": whs[iso2]["Cultural"],
        "whs_natural": whs[iso2]["Natural"],
        "whs_mixed": whs[iso2]["Mixed"],
        "estimated": ";".join(est),
    })

OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "country_indicators.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} countries -> {OUT / 'country_indicators.csv'}")
