"""Compare visa_matrix.csv with Wikipedia's "Visa requirements for X citizens" tables.

    python3 scripts/factcheck_wikipedia.py WIKI_DIR US GB JP ...   # -> data/processed/factcheck_wikipedia.csv

WIKI_DIR holds each page's raw wikitext saved as <ISO2>.txt
(https://en.wikipedia.org/w/index.php?title=Visa_requirements_for_<X>_citizens&action=raw).
Each status is mapped onto our codes with the project's rules:
- "online visa required" (UK/Canada/Australia-style full assessed visas) is E, not an e-visa;
- options marked "conditional" (e.g. visa-free only with a US visa) do not count;
- a cell offering several routes ("eVisa / Visa on arrival") takes the easiest one.
Rows where we and Wikipedia disagree are written out for review; nothing is changed here.
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC = ROOT / "data/raw", ROOT / "data/processed"
ORDER = "SABCDEF"

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


def wiki_code(status):
    s = status.lower()
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
        else:
            continue
        best = c if best is None or ORDER.index(c) < ORDER.index(best) else best
    return best or "?"


def parse(text):
    """{name: (status, duration)} from a 'Visa requirements for X citizens' main table."""
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    out = {}
    for block in re.split(r"\n\|-[^\n]*\n", text):
        # "| {{flag|X}}", "| {{flag|People's Republic of China|name=China}}", "| {{nowrap|{{flag|X}}}}", "| {{flag|X}} and ..."
        m = re.search(r"^\|\s*(?:\{\{nowrap\|)?\{\{flag(?:country)?\|([^}|]+)[^\n]*$", block, re.M)
        if not m:
            continue
        rest = block[m.end():]
        st = re.search(r"\{\{(?:yes2?|no|partial|maybe|optional|yes-no|okay|dunno|unknown|n/a)\|([^}]*)\}\}", rest, re.I)
        if not st:
            continue
        dur = re.search(r"^\|\s*([^\n|{]*?(?:day|month|year|week)s?[^\n|{]*)$", rest, re.M | re.I)
        name = m.group(1).strip()
        out.setdefault(name, (re.sub(r"\[\[(?:[^]|]*\|)?([^]]*)\]\]", r"\1", st.group(1)).strip(),
                              dur.group(1).strip() if dur else ""))
    return out


def main():
    wiki_dir, passports = Path(sys.argv[1]), sys.argv[2:]
    with open(RAW / "countries.csv", encoding="utf-8-sig") as f:
        names = {r["name_en"]: r["iso2"] for r in csv.DictReader(f) if r["include"] == "1"}
    names.update(ALIAS)
    with open(PROC / "visa_matrix.csv", encoding="utf-8") as f:
        matrix = {(r["passport"], r["destination"]): r for r in csv.DictReader(f)}

    rows = []
    for p in passports:
        table = parse((wiki_dir / f"{p}.txt").read_text(encoding="utf-8"))
        seen = set()
        for name, (status, dur) in table.items():
            d = names.get(name)
            if not d or d == p or (p, d) not in matrix:
                continue
            seen.add(d)
            cur = matrix[p, d]
            w = wiki_code(status)
            if w != cur["code"]:
                rows.append({"passport": p, "destination": d, "current": cur["code"], "wikipedia": w,
                             "wiki_status": status, "wiki_stay": dur, "current_source": cur["source"]})
        missing = sorted(d for (q, d) in matrix if q == p and d != p and d not in seen)
        print(f"{p}: {len(table)} rows parsed, {sum(r['passport'] == p for r in rows)} differ; not found: {' '.join(missing)}")

    with open(PROC / "factcheck_wikipedia.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["passport", "destination", "current", "wikipedia", "wiki_status",
                                          "wiki_stay", "current_source"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} differences -> {PROC / 'factcheck_wikipedia.csv'}")


if __name__ == "__main__":
    main()
