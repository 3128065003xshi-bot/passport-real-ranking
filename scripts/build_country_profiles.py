"""Write country_profiles/<ISO2>-<name>/ for every passport-issuing country or region.

Each folder holds
- README.md               summary: passport rank and access, best and missing destinations, the country as a destination
- visa_free_access.csv    where this passport can go: entry type, max stay, destination value, source for all destinations
- inbound_access.csv      who can enter this country, and how
plus country_profiles/README.md, an index of all of them.

Run after build_passport_ranking.py and factcheck_wikipedia.py (for stay lengths).
"""
import csv
import re
from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC, OUT = ROOT / "data/raw", ROOT / "data/processed", ROOT / "country_profiles"
REPO = "https://github.com/3128065003xshi-bot/passport-real-ranking"
ORDER = "SABCDEF"
TYPES = {"S": "Free movement", "A": "Visa-free", "B": "ETA (pre-travel authorisation)", "C": "Visa on arrival",
         "D": "e-Visa", "E": "Visa required", "F": "Banned / not possible"}
TYPES_ZH = {"S": "自由流动", "A": "免签", "B": "电子旅行授权", "C": "落地签", "D": "电子签", "E": "需签证", "F": "禁止入境"}
NO_VISA = set("SABC")


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def one_dp(v):
    return Decimal(str(v)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


countries = {r["iso2"]: r for r in read(RAW / "countries.csv") if r["include"] == "1"}
ranking = {r["iso2"]: r for r in read(PROC / "passport_ranking.csv")}
tourism = {r["iso2"]: r for r in read(PROC / "tourism_scores.csv")}
indicators = {r["iso2"]: r for r in read(PROC / "country_indicators.csv")}
weights = {r["code"]: float(r["weight"]) for r in read(RAW / "entry_codes.csv")}
matrix = {(r["passport"], r["destination"]): r for r in read(PROC / "visa_matrix.csv")}
stays = {(r["passport"], r["destination"]): r["stay_days"] for r in read(PROC / "stays_wikipedia.csv")}
notes = {r["iso2"]: r for r in read(PROC / "video_notes.csv")}
disagreed = {(r["passport"], r["destination"]) for r in read(PROC / "factcheck_wikipedia.csv")}

# source label of each matrix row -> (description, url)
row_sources = {}
for path, label in ((RAW / "visa_overrides_wikipedia.csv", "wikipedia"), (RAW / "visa_overrides.csv", "override")):
    for i, r in enumerate(read(path), start=2):
        row_sources[f"{label}:row{i}"] = r["source"]


def source_of(cell):
    s = cell["source"]
    if s.startswith("passport_index"):
        if (cell["passport"], cell["destination"]) in stays and (cell["passport"], cell["destination"]) not in disagreed:
            return "Passport Index (Jan 2025), confirmed by Wikipedia (Oct 2026)", "https://github.com/ilyankou/passport-index-dataset"
        return "Passport Index (Jan 2025), not on the passport's Wikipedia page", "https://github.com/ilyankou/passport-index-dataset"
    if s.startswith("group:"):
        return f"Free movement area ({s[6:]})", ""
    if s.startswith("wikipedia:"):
        return "Wikipedia fact-check (Oct 2026)", row_sources.get(s, "")
    return "Researched policy (2025–26)", row_sources.get(s, "")


def stay_of(p, d, code):
    if code not in "ABC":
        return ""
    return matrix[p, d]["days"] or stays.get((p, d), "")


def num(v, dp=0):
    """'98814.0' -> '98,814'; '' -> '–'."""
    if v in ("", None):
        return "–"
    return f"{float(v):,.{dp}f}"


def name(iso):
    return countries[iso]["name_en"]


def folder(iso):
    return f"{iso}-{slug(name(iso))}"


def outbound(p):
    rows = []
    for d in countries:
        if d == p:
            continue
        c = matrix[p, d]
        code = c["code"]
        desc, url = source_of(c)
        score = float(tourism[d]["tourism_score"])
        rows.append({"destination_iso2": d, "destination": name(d), "destination_zh": countries[d]["name_zh"],
                     "access": TYPES[code], "code": code, "max_stay_days": stay_of(p, d, code),
                     "destination_tourism_score": one_dp(score), "destination_tourism_rank": tourism[d]["rank"],
                     "points": one_dp(weights[code] / 100 * score), "source": desc, "note": c["note"],
                     "source_url": url})
    rows.sort(key=lambda r: (ORDER.index(r["code"]), -float(r["destination_tourism_score"])))
    return rows


def inbound(d):
    rows = []
    for p in countries:
        if p == d:
            continue
        code = matrix[p, d]["code"]
        rows.append({"passport_iso2": p, "passport": name(p), "passport_zh": countries[p]["name_zh"],
                     "access": TYPES[code], "code": code, "max_stay_days": stay_of(p, d, code),
                     "passport_rank": ranking[p]["rank"], "note": matrix[p, d]["note"]})
    rows.sort(key=lambda r: (ORDER.index(r["code"]), int(r["passport_rank"])))
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


ordered = sorted(countries, key=lambda k: (int(ranking[k]["rank"]), name(k)))


def neighbours(p):
    i = ordered.index(p)
    return [ordered[j] for j in (i - 1, i + 1) if 0 <= j < len(ordered)]


def readme(p, out_rows, in_rows):
    c, r, t, ind = countries[p], ranking[p], tourism[p], indicators[p]
    counts = Counter(x["code"] for x in out_rows)
    value = Counter()
    for x in out_rows:
        value[x["code"]] += float(x["points"])
    total_value = sum(value.values())
    no_visa = sum(counts[k] for k in NO_VISA)
    best = [x for x in out_rows if x["code"] in NO_VISA][:10]
    need = sorted((x for x in out_rows if x["code"] in "EF"), key=lambda x: -float(x["destination_tourism_score"]))[:10]
    in_counts = Counter(x["code"] for x in in_rows)
    in_free = [x for x in in_rows if x["code"] in "SA"]
    n = notes.get(p)

    lines = [f"# {c['name_en']} · {c['name_zh']}", "",
             f"Passport and destination profile from [Passport Real Ranking]({REPO}). Data as of {date.today():%Y-%m-%d}.", "",
             "## Passport", "",
             f"**Rank #{r['rank']} of {len(countries)}** · score {r['passport_score']} · "
             f"**{one_dp(r['pct_of_max'])}% of the maximum** · no visa needed for **{no_visa} of {len(out_rows)}** destinations.", ""]
    if n and n.get("note_en1"):
        lines += [f"> {n['note_en1']}" + (f" — {n['note_en2']}" if n.get("note_en2") else ""), ""]
    lines += [table(["Entry type", "Destinations", "Share of passport score"],
                    [[f"{TYPES[k]} · {TYPES_ZH[k]}", counts[k], f"{100 * value[k] / total_value:.1f}%" if total_value else "–"]
                     for k in ORDER if counts[k]]), ""]
    lines += ["### Most valuable destinations without a visa", "",
              table(["Destination", "Entry", "Max stay", "Tourism score"],
                    [[f"{x['destination']} · {x['destination_zh']}", TYPES[x["code"]],
                      f"{x['max_stay_days']} days" if x["max_stay_days"] else "–", x["destination_tourism_score"]] for x in best]), ""]
    lines += ["### Most valuable destinations that need a visa", "",
              table(["Destination", "Entry", "Tourism score"],
                    [[f"{x['destination']} · {x['destination_zh']}", TYPES[x["code"]], x["destination_tourism_score"]]
                     for x in need]) if need else "None.", ""]
    nb = neighbours(p)
    lines += ["### Neighbours in the ranking", "",
              table(["Rank", "Passport", "% of max"],
                    [[ranking[q]["rank"], f"{name(q)} · {countries[q]['name_zh']}", one_dp(ranking[q]["pct_of_max"])]
                     for q in sorted(nb + [p], key=lambda q: ordered.index(q))]), ""]
    lines += ["## As a destination", "",
              f"**Tourism score {one_dp(t['tourism_score'])} / 100 · rank #{t['rank']} of {len(countries)}**", "",
              table(["Indicator", "Value", "Points"],
                    [["GDP (US$ bn)", num(ind["gdp_usd_bn"], 1), t["gdp_usd_bn_pts"]],
                     ["GDP per capita (US$)", num(ind["gdp_per_capita_usd"]), t["gdp_per_capita_usd_pts"]],
                     ["Inbound overnight tourists (m)", f"{ind['tourist_arrivals_m']} ({ind['arrivals_year']})" if ind["tourist_arrivals_m"] else "–", t["tourist_arrivals_m_pts"]],
                     ["Nature & scenery (0–100)", ind["nature_score"], t["nature_score_pts"]],
                     ["Culture & heritage (0–100)", ind["culture_score"], t["culture_score_pts"]],
                     ["Price level (US = 100)", num(ind["price_level_us100"]), t["price_level_us100_pts"]],
                     ["Crime index (0–100, lower is safer)", ind["crime_index"] or "–", t["crime_index_pts"]],
                     ["Cities 1M+ / 5M+ / 10M+", f"{ind['cities_1m_plus']} / {ind['cities_5m_plus']} / {ind['cities_10m_plus']}",
                      f"{float(t['cities_1m_plus_pts']) + float(t['cities_5m_plus_pts']) + float(t['cities_10m_plus_pts']):.2f}"]]), ""]
    lines += ["### Who can enter", "",
              table(["Entry type", "Passports"], [[f"{TYPES[k]} · {TYPES_ZH[k]}", in_counts[k]] for k in ORDER if in_counts[k]]), ""]
    if in_free:
        lines += [f"Free movement or visa-free ({len(in_free)}): " + ", ".join(x["passport"] for x in in_free) + ".", ""]
    lines += ["## Files", "",
              "- [`visa_free_access.csv`](visa_free_access.csv) — every destination for this passport: entry type, max stay, destination value, source.",
              "- [`inbound_access.csv`](inbound_access.csv) — every passport entering this country: entry type and max stay.", "",
              "## Sources and caveats", "",
              "- Entry rules: Passport Index open dataset (Jan 2025), fact-checked against Wikipedia's visa-requirement and visa-policy pages (Oct 2026) and official or news sources for 2025–26 changes; each row's source is in the CSV.",
              "- Max stay comes from the same pages; blank means not stated.",
              "- Destination scores use World Bank, UN Tourism, UN WUP 2018 and UNESCO data; nature and culture scores are hand-rated.",
              f"- Method: [{REPO}]({REPO}).", ""]
    return "\n".join(lines)


OUT.mkdir(exist_ok=True)
for p in countries:
    d = OUT / folder(p)
    d.mkdir(exist_ok=True)
    out_rows, in_rows = outbound(p), inbound(p)
    write_csv(d / "visa_free_access.csv", out_rows)
    write_csv(d / "inbound_access.csv", in_rows)
    (d / "README.md").write_text(readme(p, out_rows, in_rows), encoding="utf-8")

index = ["# Country profiles", "",
         f"One folder per passport-issuing country or region ({len(countries)}), each with a summary (`README.md`), "
         "where its passport can go (`visa_free_access.csv`) and who can enter it (`inbound_access.csv`).", "",
         table(["Passport rank", "Country / region", "% of max", "No visa needed", "Tourism rank"],
               [[ranking[p]["rank"], f"[{name(p)} · {countries[p]['name_zh']}]({folder(p)}/README.md)",
                 one_dp(ranking[p]["pct_of_max"]), ranking[p]["visa_free_like"], tourism[p]["rank"]] for p in ordered]), ""]
(OUT / "README.md").write_text("\n".join(index), encoding="utf-8")
print(f"{len(countries)} profiles -> {OUT}")
