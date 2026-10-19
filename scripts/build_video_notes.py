"""Generate the note under every passport in the videos -> data/processed/video_notes.csv.

Each note has
- a headline: for strong passports the most valuable destinations that still need a visa (leaving out the few
  that need one from almost everyone); for weaker ones (< FEW visa-free destinations) the most valuable
  visa-free destinations (leaving out the few that admit almost everyone);
- regions: the share of each continent's destinations reachable without a visa (S/A/B/C);
- chips: entry to the popular destinations (China, US, Schengen, Japan, UK) and how much of Latin America needs no visa;
- up to two special notes: entry bans, free-movement areas, China's visa-free lists, Korea's K-ETA exemption.
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

REGIONS = [("Europe", "欧洲", "Europe"), ("Asia", "亚洲", "Asia"), ("Americas", "美洲", "Americas"),
           ("Africa", "非洲", "Africa"), ("Oceania", "大洋", "Oceania")]
LATAM = set("MX GT BZ HN SV NI CR PA CU DO HT CO VE EC PE BO BR PY UY AR CL GY SR".split())
SCHENGEN_PROXY = "FR"   # every Schengen state applies the same short-stay list
CHIP_ZH = {"S": "自由流动", "A": "免签", "B": "电子授权", "C": "落地签", "D": "电子签", "E": "需签证", "F": "禁止入境"}
CHIP_EN = {"S": "Free move", "A": "Visa-free", "B": "eTA", "C": "On arrival", "D": "e-Visa", "E": "Visa", "F": "Banned"}
CHIP_B = {"US": "ESTA", "GB": "ETA", "CA": "eTA", "KR": "K-ETA"}
# China's ordinary-passport visa-free lists (Visa policy of mainland China, Oct 2026).
CN_TEMPORARY = set("AT BE BG HR CY DK EE FI FR DE GR HU IE IT LV LU MT NL PL PT RO SK SI ES SE "
                   "AD AR AU BH BR CA CL IS JP KW LI MC ME NZ NO MK OM PE SA KR CH GB UY".split())
KETA_EXEMPT = set("AU AT BE CA DK FI FR DE IT JP NL NZ NO PL SG ES SE GB US HK MO".split())
GROUPS = {"EU_EEA_CH": ("欧盟/申根自由流动，凭身份证通行", "EU/EEA free movement on a national ID"),
          "MERCOSUR": ("南共市国家间凭身份证通行", "Mercosur: travel on a national ID"),
          "GCC": ("海合会国家间凭身份证通行", "GCC: travel on a national ID"),
          "CA4": ("中美洲四国自由通行", "Central America-4 free movement"),
          "CTA": ("英爱共同旅行区", "UK–Ireland Common Travel Area")}
groups_of = defaultdict(list)
for g in read(RAW / "free_movement_groups.csv"):
    if g["enabled"] == "1":
        for m in g["members"].split(";"):
            groups_of[m].append(g["group"])


def top(p, codes, n, exclude=()):
    ds = [d for (q, d), c in code.items() if q == p and c in codes and d not in exclude]
    return sorted(ds, key=lambda d: -tourism[d])[:n]


def listing(ds, sep_zh="、", sep_en=", "):
    return sep_zh.join(zh(d) for d in ds), sep_en.join(en(d) for d in ds)


def headline(p):
    n_free = sum(1 for (q, d), c in code.items() if q == p and c in FREE)
    if n_free < FEW:
        best = top(p, FREE, 3, exclude=universal)
        if not best:
            return "仅少数小国免签", "Visa-free only to a few small states"
        z, e = listing(best)
        return f"免签：{z}", f"Visa-free: {e}"
    need = top(p, VISA, 3, exclude=closed)
    if need:
        z, e = listing(need)
        return f"需签证：{z}", f"Visa needed: {e}"
    z, e = listing(top(p, VISA, 2))
    return f"仅{z}等少数国家需签证", f"Visa only for {e} & a few more"


def regions(p, lang="zh"):
    out = []
    for region, label_zh, label_en in REGIONS:
        ds = [d for d, c in countries.items() if c.get("region") == region and c["include"] == "1" and d != p]
        if ds:
            share = sum(code.get((p, d)) in NO_VISA for d in ds if (p, d) in code) / len(ds)
            out.append(f"{label_zh if lang == 'zh' else label_en}:{round(100 * share)}")
    return ";".join(out)


def chip(p, d, label, lang="zh"):
    if d == p:
        return f"{label}|{'本国' if lang == 'zh' else 'Home'}|-"
    c = code[p, d]
    names = CHIP_ZH if lang == "zh" else CHIP_EN
    text = CHIP_B.get(d, names["B"]) if c == "B" else names[c]
    return f"{label}|{text}|{c}"


def chips(p, lang="zh"):
    L = {"CN": ("中国", "China"), "US": ("美国", "US"), "EU": ("申根", "Schengen"), "JP": ("日本", "Japan"),
         "GB": ("英国", "UK"), "LA": ("拉美", "LatAm")}
    lab = {k: v[0] if lang == "zh" else v[1] for k, v in L.items()}
    out = [chip(p, "CN", lab["CN"], lang), chip(p, "US", lab["US"], lang)]
    free_move = "自由流动" if lang == "zh" else "Free move"
    out.append(f"{lab['EU']}|{free_move}|S" if "EU_EEA_CH" in groups_of[p] else chip(p, SCHENGEN_PROXY, lab["EU"], lang))
    out += [chip(p, "JP", lab["JP"], lang), chip(p, "GB", lab["GB"], lang)]
    ds = [d for d in LATAM if d != p]
    n = sum(code[p, d] in NO_VISA for d in ds)
    share = n / len(ds)
    out.append(f"{lab['LA']}|{n}/{len(ds)}|{'A' if share >= 0.8 else 'C' if share >= 0.5 else 'D' if share >= 0.3 else 'E'}")
    return ";".join(out)


def specials(p):
    out = []
    banned = [d for d in sorted(tourism, key=lambda d: -tourism[d]) if code.get((p, d)) == "F" and d not in ("KP",) + tuple(SKIP)]
    if banned:
        z, e = listing(banned[:3])
        more = "等" if len(banned) > 3 else ""
        out.append((f"禁止入境：{z}{more}", f"Entry banned: {e}" + (" and more" if len(banned) > 3 else "")))
    for g in groups_of[p]:
        out.append(GROUPS[g])
    if p in ("CZ", "LT"):
        out.append(("中国免签名单不含捷克、立陶宛", "China's visa-free list excludes Czechia and Lithuania"))
    elif p == "RU":
        out.append(("中国对俄罗斯免签，试行至2027年底", "China visa-free for Russians, trial to end-2027"))
    elif p in CN_TEMPORARY:
        out.append(("中国单方面免签30天，至2026年底", "China visa-free 30 days (unilateral, to end-2026)"))
    elif p != "CN" and code.get((p, "CN")) == "A" and p not in ("HK", "MO"):
        out.append(("与中国互免签证", "Mutual visa exemption with China"))
    if p in KETA_EXEMPT:
        out.append(("韩国 K-ETA 豁免至2026年底", "Korea K-ETA waived to end-2026"))
    if len(out) < 2:   # nothing special: show where the next-easiest entry is
        n_free = sum(1 for (q, d), c in code.items() if q == p and c in FREE)
        if n_free >= FEW:
            ds = top(p, {"D"}, 3) or top(p, {"C"}, 3)
            label = ("电子签", "e-visa") if top(p, {"D"}, 1) else ("落地签", "On arrival")
        else:
            ds = top(p, {"C", "D"}, 3)
            label = ("落地签/电子签可去", "On arrival / e-visa")
        if ds:
            z, e = listing(ds)
            out.append((f"{label[0]}：{z}", f"{label[1]}: {e}"))
    return out[:2]


rows = []
for r in ranking:
    p = r["iso2"]
    hz, he = headline(p)
    sp = specials(p) + [("", ""), ("", "")]
    rows.append({"iso2": p, "rank": r["rank"], "headline_zh": hz, "headline_en": he, "regions": regions(p),
                 "regions_en": regions(p, "en"), "chips": chips(p), "chips_en": chips(p, "en"),
                 "special1_zh": sp[0][0], "special1_en": sp[0][1],
                 "special2_zh": sp[1][0], "special2_en": sp[1][1]})

with open(PROC / "video_notes.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} notes -> {PROC / 'video_notes.csv'}; universal visa-free destinations left out: "
      + ", ".join(en(d) for d in sorted(universal)))
