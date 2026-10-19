"""Fact-check the visa matrix against Wikipedia's "Visa requirements for X citizens" tables.

    python3 scripts/build_visa_matrix.py --no-wikipedia      # matrix without earlier Wikipedia corrections
    python3 scripts/factcheck_wikipedia.py WIKI_DIR [ISO2 ...]  # all passports when none are given
    python3 scripts/build_visa_matrix.py                     # rebuild with the corrections

WIKI_DIR holds each page's raw wikitext as <ISO2>.txt and, optionally, meta.json
({"ts": {ISO2: last-edit timestamp}}) from the MediaWiki API.

Outputs
- data/processed/factcheck_wikipedia.csv: every disagreement, with decision (apply / keep) and reason;
- data/raw/visa_overrides_wikipedia.csv: the applied corrections, read by build_visa_matrix.py before the
  hand-researched visa_overrides.csv, so a rule we verified ourselves always has the last word.

Wikipedia statuses are mapped with the project's rules: a full visa applied for online (UK, Canada,
Australia style) is E; options marked "conditional" (e.g. visa-free only with a US visa) do not count;
a cell offering several routes ("eVisa / Visa on arrival") takes the easiest.
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC = ROOT / "data/raw", ROOT / "data/processed"
ORDER = "SABCDEF"
STALE_BEFORE = "2025-06-01"   # pages last edited before this are older than our Jan 2025 base + 2025-26 checks
SCHENGEN_ONLY = {"AD", "SM", "VA", "MC"}
# Countries whose online visitor visas are full, document-assessed visas (our code E, not a simple e-visa).
FULL_ONLINE_VISA = {"AU", "NZ", "KR", "CA", "GB", "US", "IE", "HK"}
# Most countries treat these passports identically, so their pages can correct each other (see eu_consensus).
EU_EEA = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE IS LI NO CH".split())
CONSENSUS = 0.7

ALIAS = {"Ivory Coast": "CI", "Côte d'Ivoire": "CI", "Cote d'Ivoire": "CI", "Democratic Republic of the Congo": "CD",
         "Republic of the Congo": "CG", "Congo": "CG", "East Timor": "TL", "Timor-Leste": "TL", "Turkey": "TR",
         "Türkiye": "TR", "Czech Republic": "CZ", "Czechia": "CZ", "Vatican City": "VA", "Holy See": "VA",
         "Federated States of Micronesia": "FM", "Micronesia": "FM", "Eswatini": "SZ", "Swaziland": "SZ",
         "Cape Verde": "CV", "Cabo Verde": "CV", "São Tomé and Príncipe": "ST", "Sao Tome and Principe": "ST",
         "The Gambia": "GM", "Gambia": "GM", "The Bahamas": "BS", "Bahamas": "BS", "North Korea": "KP",
         "South Korea": "KR", "State of Palestine": "PS", "Palestine": "PS", "Brunei": "BN", "Laos": "LA",
         "Myanmar": "MM", "Burma": "MM", "United States": "US", "United Kingdom": "GB", "United Arab Emirates": "AE",
         "Russia": "RU", "Moldova": "MD", "Syria": "SY", "Iran": "IR", "Venezuela": "VE", "Bolivia": "BO",
         "Tanzania": "TZ", "Vietnam": "VN", "Kosovo": "XK", "Saint Kitts and Nevis": "KN", "Saint Lucia": "LC",
         "Saint Vincent and the Grenadines": "VC", "North Macedonia": "MK", "China": "CN", "Taiwan": "TW",
         "Hong Kong": "HK", "Macau": "MO", "Macao": "MO", "Netherlands": "NL", "Guinea-Bissau": "GW",
         "People's Republic of China": "CN", "Republic of China": "TW"}

# Display texts the generic mapping cannot read.
SPECIAL = {"electronic border system": "B", "easy visitor permit": "C", "admission restricted": "F",
           "electronic entry visa": "D", "pre-enrolment": "D", "evoa": "C", "evisitors": "B",
           "electronic authorization": "B", "electronic authorization system": "B", "visa waiver program": "B",
           "ease": "B", "e-tourist card": "B", "eta": "B"}


def display(status):
    """{{sort|key|shown}} shows its second argument."""
    m = re.match(r"\{\{sort\|[^|]*\|(.*)", status)
    return (m.group(1) if m else status).strip()


def wiki_code(status):
    s = display(status).lower().rstrip("}").strip()
    if s in SPECIAL:
        return SPECIAL[s]
    if "tourist card" in s:   # Cuba: a card bought from the airline or online, no application
        return "B"
    if any(w in s for w in ("refused", "banned", "prohibited", "not permitted", "entry suspended")):
        return "F"
    best = None
    for opt in re.split(r"\s*/\s*|\s+or\s+", s):
        if "conditional" in opt:
            continue
        if "online visa required" in opt:
            c = "E"
        elif any(w in opt for w in ("not required", "visa-free", "visa free", "freedom of movement", "id card")):
            c = "A"
        elif re.search(r"\b(e?ta|esta|k-eta|nzeta|etias|evisitor)\b", opt) or "travel authori" in opt:
            c = "B"
        elif "on arrival" in opt or "e-voa" in opt:
            c = "C"
        elif any(w in opt for w in ("evisa", "e-visa", "online visa", "electronic visa")):
            c = "D"
        elif "required" in opt:
            c = "E"
        elif opt in SPECIAL:
            c = SPECIAL[opt]
        else:
            continue
        best = c if best is None or ORDER.index(c) < ORDER.index(best) else best
    return best or "?"


def parse(text):
    """{name: (status, stay)} from a 'Visa requirements for X citizens' main table (first occurrence wins)."""
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    out = {}
    for block in re.split(r"\n\|-[^\n]*\n", text):
        # "| {{flag|X}}", "| {{flag|People's Republic of China|name=China}}", "| {{nowrap|{{flag|X}}}}", "| {{flag|X}} and ..."
        m = re.search(r"^\|\s*(?:\{\{nowrap\|)?\{\{flag(?:country)?\|([^}|]+)[^\n]*$", block, re.M)
        if not m:
            continue
        rest = block[m.end():]
        st = re.search(r"\{\{(?:yes2?|no|partial|maybe|optional|yes-no|okay|dunno|unknown|n/a)\|(.*?)\}\}\s*$",
                       rest, re.I | re.M)
        if not st:
            continue
        dur = re.search(r"^\|\s*([^\n|{]*?(?:day|month|year|week)s?[^\n|{]*)$", rest, re.M | re.I)
        status = re.sub(r"\[\[(?:[^]|]*\|)?([^]]*)\]\]", r"\1", st.group(1)).strip()
        out.setdefault(m.group(1).strip(), (status, dur.group(1).strip() if dur else ""))
    return out


def remap(d, cur, w, status):
    """Destinations whose labels mean something different from our codes."""
    s = display(status).lower()
    if d in FULL_ONLINE_VISA and w == "D":   # an "online visa" / "eVisa" there is a full assessed visa
        return "E"
    if d == "DZ" and w == "C":   # Algeria's visa on arrival is only for agency-booked Saharan tours
        return "E"
    if d == "LK" and w == "B":   # Sri Lanka's "ETA" is a paid online short-stay visa
        return "C" if "on arrival" in s else "D"
    if d == "ZA" and w == "B" and cur in "DE":   # ETA for visa-required nationals = documented online visa
        return "D"
    return w


def stay_days(stay):
    """'90 days', '3 months', '1 year', '90 days within any 180-day period' -> 90 / 90 / 365 / 90; '' if none."""
    m = re.search(r"(\d+)\s*(day|week|month|year)", stay or "", re.I)
    if not m:
        return ""
    n, unit = int(m.group(1)), m.group(2).lower()
    return n * {"day": 1, "week": 7, "month": 30, "year": 365}[unit]


def decide(p, d, cur, w, status, fresh, matrix):
    """(decision, reason) for one disagreement."""
    if cur["source"].startswith("group:"):
        return "keep", "free movement group (S)"
    if cur["source"].startswith("override:"):
        return "keep", "hand-researched override"
    if d == "KP":
        return "keep", "North Korea: tourism closed (judgement)"
    if w == "?":
        return "keep", "status unparsed or conditional"
    if not fresh:
        return "keep", f"Wikipedia page not edited since {STALE_BEFORE}"
    if cur["code"] == "B" and w == "A":
        return "keep", "visa-free but pre-travel authorisation: B by rule"
    if d in SCHENGEN_ONLY and w == "A" and cur["code"] in "DE" and \
            {matrix.get((p, x), {}).get("code") for x in ("FR", "IT")} & set("DE"):
        return "keep", "reachable only through Schengen, which needs a visa"
    if d == "CN":
        return "keep", "China column checked against China's own visa policy (Wikipedia's 'port visa' is not a tourist VOA)"
    if d == "PS":
        return "keep", "Palestine is entered only through Israel"
    if d == "GB" and w == "D":
        return "keep", "UK 'eVisa' is the digital status of a full visa"
    if d == "AE" and cur["code"] == "D" and w == "E":
        return "keep", "UAE tourist visas are issued online via airlines/agents: e-visa"
    return "apply", ""


def eu_consensus(wiki, base):
    """Fix EU/EEA pages that are missing a destination or have not caught up with a change the others show.

    wiki: {passport: {destination: code}}; base: {(passport, destination): code before any correction}.
    For each destination, if at least CONSENSUS of the EU/EEA pages that list it agree on a code M, a page that
    lacks the destination, or still shows its own pre-correction value while M differs from it, gets M.
    A page that differs from both M and the old value is a genuine exception and is left alone.
    Returns {(passport, destination): code} adjustments.
    """
    from collections import Counter
    pages = [p for p in wiki if p in EU_EEA]
    dests = {d for p in pages for d in wiki[p]} - EU_EEA - SCHENGEN_ONLY
    out = {}
    for d in dests:
        votes = Counter(wiki[p][d] for p in pages if d in wiki[p] and wiki[p][d] != "?")
        if not votes:
            continue
        m, n = votes.most_common(1)[0]
        if n / sum(votes.values()) < CONSENSUS:
            continue
        for p in pages:
            old = base.get((p, d))
            if old is None or old == m:
                continue
            v = wiki[p].get(d)
            if v is None or v == "?" or (v == old and v != m):
                out[p, d] = m
    return out


def main():
    wiki_dir = Path(sys.argv[1])
    with open(RAW / "countries.csv", encoding="utf-8-sig") as f:
        countries = [r for r in csv.DictReader(f) if r["include"] == "1"]
    names = {r["name_en"]: r["iso2"] for r in countries}
    names.update(ALIAS)
    passports = sys.argv[2:] or [r["iso2"] for r in countries]
    meta = json.loads((wiki_dir / "meta.json").read_text()) if (wiki_dir / "meta.json").exists() else {"ts": {}}
    with open(PROC / "visa_matrix.csv", encoding="utf-8") as f:
        matrix = {(r["passport"], r["destination"]): r for r in csv.DictReader(f)}

    # Pass 1: read every page into {passport: {destination: (code, status, stay)}}.
    pages, stamps = {}, {}
    for p in passports:
        path = wiki_dir / f"{p}.txt"
        if not path.exists():
            print(f"{p}: no page")
            continue
        stamps[p] = meta["ts"].get(p, "")
        pages[p] = {}
        for name, (status, stay) in parse(path.read_text(encoding="utf-8")).items():
            d = names.get(name)
            if d and d != p and (p, d) in matrix and d not in pages[p]:
                pages[p][d] = (remap(d, matrix[p, d]["code"], wiki_code(status), status), status, stay)

    # Stay lengths for every row a page lists (used by the country profiles).
    with open(PROC / "stays_wikipedia.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["passport", "destination", "wiki_status", "stay", "stay_days"])
        for p, table in sorted(pages.items()):
            for d, (_, status, stay) in sorted(table.items()):
                w.writerow([p, d, display(status)[:80], stay, stay_days(stay)])

    # Pass 2: EU/EEA pages correct each other where one is missing a row or has not caught up.
    adjust = eu_consensus({p: {d: v[0] for d, v in t.items()} for p, t in pages.items()},
                          {k: r["code"] for k, r in matrix.items()})
    for (p, d), code in adjust.items():
        _, status, stay = pages[p].get(d, ("", "", ""))
        pages[p][d] = (code, f"EU/EEA consensus: {code} on >= {CONSENSUS:.0%} of EU/EEA pages"
                             + (f" (own page: {display(status)[:40]})" if status else " (missing on own page)"), stay)

    # Pass 3: compare and decide.
    report, applied = [], []
    for p, table in pages.items():
        ts = stamps[p]
        fresh = ts >= STALE_BEFORE if ts else True
        n = 0
        for d, (w, status, stay) in table.items():
            cur = matrix[p, d]
            if w == cur["code"]:
                continue
            decision, reason = decide(p, d, cur, w, status, fresh, matrix)
            n += 1
            report.append({"passport": p, "destination": d, "current": cur["code"], "wikipedia": w,
                           "decision": decision, "reason": reason, "wiki_status": display(status)[:120],
                           "wiki_stay": stay, "page_edited": ts[:10], "current_source": cur["source"]})
            if decision == "apply":
                days = re.match(r"(\d+)\s*days?", stay or "")
                title = meta.get("titles", {}).get(p, "").replace(" ", "_")
                applied.append([p, d, w, days.group(1) if days and w == "A" else "", "", "", ts[:10],
                                f"Wikipedia: {display(status)[:80]}", f"https://en.wikipedia.org/wiki/{title}"])
        missing = sorted(d for (q, d) in matrix if q == p and d != p and d not in table)
        print(f"{p}: {len(table)} rows, {n} differ (edited {ts[:10] or '?'}); not in table: {' '.join(missing)}")
    print(f"EU/EEA consensus adjusted {len(adjust)} page values")

    with open(PROC / "factcheck_wikipedia.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(report[0]) if report else ["passport"])
        w.writeheader()
        w.writerows(report)
    with open(RAW / "visa_overrides_wikipedia.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["passport", "destination", "code", "days", "only_if", "except", "effective", "note", "source"])
        w.writerows(applied)
    print(f"{len(report)} disagreements: {len(applied)} applied -> {RAW / 'visa_overrides_wikipedia.csv'}, "
          f"{len(report) - len(applied)} kept")


if __name__ == "__main__":
    main()
