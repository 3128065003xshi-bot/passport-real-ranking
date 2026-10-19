"""Generate a short bilingual note for every passport in the videos -> data/processed/video_notes.csv.

Passports with few visa-free destinations (< FEW): their most valuable visa-free destinations, leaving out
the handful that admit nearly every passport, plus their best visa-on-arrival / e-visa options.
Passports with many: their most valuable destinations that still need a visa (leaving out the few that
need one from almost everyone), and the most valuable
destination where access differs from the neighbouring passport in the ranking.
Passports and destinations in SKIP are never shown or mentioned.
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC = ROOT / "data/raw", ROOT / "data/processed"
SKIP = {"TW"}
FEW = 60            # visa-free (S/A/B) destinations below this -> "what can it enter" note
UNIVERSAL = 0.9     # destinations visa-free for at least this share of passports are left out of those lists
CLOSED = 0.85       # destinations that need a visa for at least this share are "closed": named only if nothing else needs one
FREE, NO_VISA, VISA = set("SAB"), set("SABC"), set("EF")

SHORT_ZH = {"BA": "波黑", "VC": "圣文森特", "AG": "安提瓜", "KN": "圣基茨", "TT": "特立尼达", "ST": "圣多美",
            "PG": "巴新", "FM": "密克罗尼西亚", "SA": "沙特", "CF": "中非", "DO": "多米尼加", "VA": "梵蒂冈",
            "GQ": "赤道几内亚", "AE": "阿联酋", "MH": "马绍尔群岛", "SB": "所罗门群岛"}
SHORT_EN = {"US": "the US", "GB": "the UK", "AE": "UAE", "BA": "Bosnia", "VC": "St Vincent", "AG": "Antigua",
            "KN": "St Kitts", "TT": "Trinidad", "ST": "São Tomé", "PG": "PNG", "FM": "Micronesia", "SA": "Saudi",
            "CF": "CAR", "CD": "DR Congo", "CG": "Congo", "DO": "Dominican Rep.", "VA": "Vatican",
            "KR": "S. Korea", "KP": "N. Korea", "MH": "Marshall Is.", "SB": "Solomon Is.", "NL": "Netherlands",
            "HK": "Hong Kong", "MO": "Macao", "CZ": "Czechia", "MK": "N. Macedonia", "BO": "Bolivia",
            "VE": "Venezuela", "LA": "Laos", "MD": "Moldova", "SY": "Syria", "IR": "Iran", "RU": "Russia",
            "CI": "Côte d'Ivoire", "TZ": "Tanzania"}


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


countries = {r["iso2"]: r for r in read(RAW / "countries.csv")}
zh = lambda c: SHORT_ZH.get(c, countries[c]["name_zh"])
en = lambda c: SHORT_EN.get(c, countries[c]["name_en"])
tourism = {r["iso2"]: float(r["tourism_score"]) for r in read(PROC / "tourism_scores.csv")}
ranking = sorted((r for r in read(PROC / "passport_ranking.csv") if r["iso2"] not in SKIP), key=lambda r: int(r["rank"]))

code = {}
for r in read(PROC / "visa_matrix.csv"):
    if r["code"] != "-" and r["destination"] not in SKIP:
        code[r["passport"], r["destination"]] = r["code"]

dest_free = defaultdict(list)
for (p, d), c in code.items():
    dest_free[d].append(c in FREE)
universal = {d for d, v in dest_free.items() if sum(v) / len(v) >= UNIVERSAL}
dest_visa = defaultdict(list)
for (p, d), c in code.items():
    dest_visa[d].append(c in VISA)
closed = {d for d, v in dest_visa.items() if sum(v) / len(v) >= CLOSED}

ACCESS_ZH = {"S": "自由通行", "A": "免签", "B": "只需电子授权", "C": "可落地签", "D": "只需电子签", "E": "可申请签证"}
ACCESS_EN = {"S": "free movement to", "A": "visa-free to", "B": "only an eTA for", "C": "visa on arrival in",
             "D": "only an e-visa for", "E": "a visa available for"}


def top(p, codes, n, exclude=()):
    ds = [d for (q, d), c in code.items() if q == p and c in codes and d not in exclude]
    return sorted(ds, key=lambda d: -tourism[d])[:n]


def listing(ds, sep_zh="、", sep_en=", "):
    return sep_zh.join(zh(d) for d in ds), sep_en.join(en(d) for d in ds)


def mark_banned(p, ds):
    """Names for a visa list, flagging outright bans."""
    z = "、".join(zh(d) + ("(禁)" if code[p, d] == "F" else "") for d in ds)
    e = ", ".join(en(d) + (" (banned)" if code[p, d] == "F" else "") for d in ds)
    return z, e


WEIGHT = {r["code"]: float(r["weight"]) for r in read(RAW / "entry_codes.csv")}


def comparison(i):
    """The neighbouring passport (above, else below) and the most valuable destination where access differs.

    Prefer a difference across the visa line (one side needs a visa, the other does not); failing that, any
    difference in entry type, weighted by how much score it moves. Identical rules -> say so.
    """
    p = ranking[i]["iso2"]
    neighbours = [ranking[j]["iso2"] for j in (i - 1, i + 1) if 0 <= j < len(ranking)]
    for visa_line in (True, False):
        for q in neighbours:
            diffs = [d for d in tourism if d not in SKIP and d not in (p, q) and code[p, d] != code[q, d]
                     and (not visa_line or (code[p, d] in VISA) != (code[q, d] in VISA))]
            if not diffs:
                continue
            d = max(diffs, key=lambda d: abs(WEIGHT[code[p, d]] - WEIGHT[code[q, d]]) * tourism[d])
            rq = next(r["rank"] for r in ranking if r["iso2"] == q)
            tag_zh, tag_en = f"#{rq} {zh(q)}", f"#{rq} {en(q)}"
            if WEIGHT[code[p, d]] < WEIGHT[code[q, d]]:
                c = code[q, d]
                return f"{tag_zh} 去{zh(d)}{ACCESS_ZH[c]}", f"{tag_en}: {ACCESS_EN[c]} {en(d)}"
            c = code[p, d]
            return f"胜过 {tag_zh}：去{zh(d)}{ACCESS_ZH[c]}", f"Beats {tag_en}: {ACCESS_EN[c]} {en(d)}"
    return "", ""


rows = []
for i, r in enumerate(ranking):
    p = r["iso2"]
    n_free = sum(1 for (q, d), c in code.items() if q == p and c in FREE)
    short_z2 = short_e2 = ""
    if n_free < FEW:
        best = top(p, FREE, 3, exclude=universal)
        if best:
            z1, e1 = listing(best)
            z1, e1 = f"免签：{z1}", f"Visa-free: {e1}"
        else:
            z1, e1 = "仅少数小国免签", "Visa-free only to a few small states"
        # Best visa-on-arrival and e-visa options, each under its own label (never lumped together).
        def options(n):
            parts_zh, parts_en = [], []
            for c, lz, le in (("C", "落地签", "On arrival"), ("D", "电子签", "e-visa")):
                ds = top(p, {c}, n)
                if ds:
                    z, e = listing(ds)
                    parts_zh.append(f"{lz}：{z}")
                    parts_en.append(f"{le}: {e}")
            return " · ".join(parts_zh), " · ".join(parts_en)
        z2, e2 = options(2)
        short_z2, short_e2 = options(1)  # for narrow cards when two per type do not fit
    else:
        need = top(p, VISA, 3, exclude=closed)
        if need:
            z1, e1 = mark_banned(p, need)
            z1, e1 = f"需签证：{z1}", f"Visa needed: {e1}"
        else:
            few_closed = top(p, VISA, 2)
            z1, e1 = listing(few_closed)
            z1, e1 = f"仅{z1}等少数国家需签证", f"Visa needed only for {e1} and a few others"
        z2, e2 = comparison(i)
        if not z2:  # identical visa needs to both neighbours: say so
            q = ranking[i - 1] if i else ranking[i + 1]
            z2, e2 = f"入境规则与 #{q['rank']} {zh(q['iso2'])} 完全相同", f"Same entry rules as #{q['rank']} {en(q['iso2'])}"
    rows.append({"iso2": p, "rank": r["rank"], "mode": "few" if n_free < FEW else "many",
                 "note_zh1": z1, "note_en1": e1, "note_zh2": z2, "note_en2": e2,
                 "note_zh2_short": short_z2 if n_free < FEW else z2, "note_en2_short": short_e2 if n_free < FEW else e2})

with open(PROC / "video_notes.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} notes -> {PROC / 'video_notes.csv'}; universal visa-free destinations left out: "
      + ", ".join(en(d) for d in sorted(universal)))
