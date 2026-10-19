"""Render the 9:16 vertical cut (1080x1920, 60 fps) for Shorts / Reels / TikTok, under 3 minutes.

    python scripts/make_video_vertical.py                    # -> video/passport-real-ranking-2026-vertical.mp4
    python scripts/make_video_vertical.py --stills 4 90 165  # PNG frames at those seconds instead
    python scripts/make_video_vertical.py --lang en          # English only -> ...-vertical-en.mp4

Passports scroll up as rows, #199 at the bottom first, ending on #1. Shares data, fonts, covers,
notes and SKIP with make_video.py.
"""
import argparse
import csv
from collections import Counter

from PIL import Image, ImageDraw, ImageFilter

import make_video as mv
from make_video import BG, CODE_COLOURS, CODE_NAMES, GITHUB, GOLD, INK, MEDALS, PANEL, QUIET, centred, cjk, fit, latin

W, H, FPS = 1080, 1920, 60
INTRO, SCROLL, HOLD, DECEL = 8.0, 165.0, 6.0, 5.0  # 179 s in all: under the 3-minute Shorts limit
X_ARTICLE = "x.com/i/article/2111989228271775744"  # public link of the X Article; check once it is published
ROW_W, ROW_H, GAP, LEFT = 1000, 414, 22, 40
STRIDE = ROW_H + GAP
TOP, BOTTOM = 300, 1740  # the band the rows scroll through


def make_row(r, codes, note):
    row = Image.new("RGBA", (ROW_W, ROW_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(row)
    rank = int(r["rank"])
    medal = MEDALS.get(rank)
    d.rounded_rectangle((0, 0, ROW_W - 1, ROW_H - 1), radius=22, fill=PANEL,
                        outline=medal or (40, 54, 76), width=4 if medal else 2)

    centred(d, 95, 30, f"#{rank}", fit(d, f"#{rank}", lambda s: latin(s, mv.BOLD), 160, 64), medal or INK)

    flag = Image.open(mv.FLAGS / f"{r['iso2'].lower()}.png").convert("RGBA")
    bw, bh, bx, by = 150, 196, 22, 102
    shadow = Image.new("RGBA", (ROW_W, ROW_H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((bx + 6, by + 8, bx + bw + 6, by + bh + 8), radius=10, fill=(0, 0, 0, 120))
    row.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)))
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=10, fill=mv.cover_colour(flag))
    d.line((bx + 13, by + 5, bx + 13, by + bh - 5), fill=(0, 0, 0), width=2)
    centred(d, bx + bw / 2 + 6, by + 16, "PASSPORT", latin(16, mv.BOLD), GOLD)
    fw = 88
    emblem = flag.resize((fw, round(flag.height * fw / flag.width)))
    ex, ey = int(bx + bw / 2 + 6 - fw / 2), int(by + bh / 2 - emblem.height / 2)
    d.rectangle((ex - 2, ey - 2, ex + fw + 1, ey + emblem.height + 1), fill=GOLD)
    row.alpha_composite(emblem, (ex, ey))

    x = 210
    en = mv.LANG == "en"
    if en:
        d.text((x, 34), r["name_en"], font=fit(d, r["name_en"], lambda s: latin(s, mv.BOLD), 470, 50), fill=INK)
    else:
        d.text((x, 20), r["name_zh"], font=fit(d, r["name_zh"], lambda s: cjk(s, True), 470, 50), fill=INK)
        d.text((x, 84), r["name_en"], font=fit(d, r["name_en"], latin, 470, 28), fill=QUIET)
    pct = f"{mv.one_dp(r['pct_of_max'])}%"
    pf = latin(70, mv.BOLD)
    d.text((ROW_W - 30 - d.textlength(pct, font=pf), 18), pct, font=pf, fill=medal or INK)
    sub = "of max score" if en else "of max · 满分占比"
    d.text((ROW_W - 30 - d.textlength(sub, font=cjk(19)), 98), sub, font=cjk(19), fill=QUIET)

    bar_x, bar_w, y = x, ROW_W - 30 - x, 134
    total, cur = sum(codes.values()), bar_x
    for code, colour in CODE_COLOURS.items():
        w = bar_w * codes.get(code, 0) / total
        if w:
            d.rectangle((cur, y, cur + w, y + 20), fill=colour)
        cur += w
    no_visa = sum(codes.get(c, 0) for c in "SABC")
    d.text((bar_x, y + 28), f"No visa needed: {no_visa} / 198" if en else f"No visa · 无需签证  {no_visa} / 198",
           font=latin(21) if en else cjk(20), fill=QUIET)

    if note and en:
        d.text((bar_x, 190), note["headline_en"], font=fit(d, note["headline_en"], lambda s: latin(s, mv.BOLD), bar_w, 27), fill=GOLD)
        mv.draw_pills(d, bar_x, 230, bar_w, 30, note["regions_en"], 18)
        mv.draw_chips(d, bar_x, 268, bar_w, 32, note["chips_en"], 3, 18, row_gap=5)
        y = 346
        for k in ("special1", "special2"):
            if note[k + "_en"]:
                d.text((bar_x, y), note[k + "_en"], font=fit(d, note[k + "_en"], latin, bar_w, 20), fill=GOLD)
                y += 27
    elif note:
        d.text((bar_x, 192), note["headline_zh"], font=fit(d, note["headline_zh"], lambda s: cjk(s, True), bar_w, 26), fill=GOLD)
        d.text((bar_x, 226), note["headline_en"], font=fit(d, note["headline_en"], latin, bar_w, 19), fill=INK)
        mv.draw_pills(d, bar_x, 258, bar_w, 32, note["regions"], 17)
        mv.draw_chips(d, bar_x, 300, bar_w, 34, note["chips"], 6, 17)
        y = 346
        for k in ("special1", "special2"):
            if note[k + "_zh"]:
                d.text((bar_x, y), note[k + "_zh"], font=fit(d, note[k + "_zh"], cjk, bar_w, 22), fill=GOLD)
                y += 30
    return row


def make_base():
    base = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(base)
    if mv.LANG == "en":
        centred(d, W / 2, 62, "PASSPORT REAL RANKING 2026", latin(62, mv.BOLD), INK)
        centred(d, W / 2, 148, "Weighted by how much each destination is worth", latin(32), QUIET)
        centred(d, W / 2, 202, mv.AS_OF, latin(30, mv.MEDIUM), GOLD)
        y = 1772
        for row_codes in ("SABC", "DEF"):
            items = [(c, mv.CODE_NAMES_EN[c]) for c in row_codes]
            widths = [34 + d.textlength(n, font=latin(24)) for _, n in items]
            x = (W - sum(widths) - 26 * (len(items) - 1)) / 2
            for (code, name), w in zip(items, widths):
                d.rectangle((x, y + 4, x + 22, y + 26), fill=CODE_COLOURS[code])
                d.text((x + 32, y + 1), name, font=latin(24), fill=QUIET)
                x += w + 26
            y += 42
        centred(d, W / 2, 1868, GITHUB, latin(24), QUIET)
        return base
    centred(d, W / 2, 60, "PASSPORT REAL RANKING 2026", latin(62, mv.BOLD), INK)
    centred(d, W / 2, 142, "护照真实含金量排行榜", cjk(58, True), GOLD)
    centred(d, W / 2, 226, "Weighted by how much each destination is worth · 按目的地价值加权", cjk(26), QUIET)
    # Legend in two rows, then the repo link.
    y = 1772
    for row_codes in ("SABC", "DEF"):
        items = [(c, CODE_NAMES[c]) for c in row_codes]
        widths = [34 + d.textlength(n, font=cjk(22)) for _, n in items]
        x = (W - sum(widths) - 24 * (len(items) - 1)) / 2
        for (code, name), w in zip(items, widths):
            d.rectangle((x, y + 4, x + 22, y + 26), fill=CODE_COLOURS[code])
            d.text((x + 32, y), name, font=cjk(22), fill=QUIET)
            x += w + 24
        y += 42
    centred(d, W / 2, 1868, GITHUB, latin(24), QUIET)
    return base


def make_intro():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    if mv.LANG == "en":
        centred(d, W / 2, 380, "PASSPORT", latin(130, mv.BOLD), INK)
        centred(d, W / 2, 520, "REAL RANKING 2026", latin(88, mv.BOLD), INK)
        centred(d, W / 2, 700, "Not how many countries you can enter,", latin(44), INK)
        centred(d, W / 2, 758, "but how much they are worth.", latin(44), INK)
        centred(d, W / 2, 870, "Score = Σ ease of entry × destination value", latin(36), QUIET)
        d.rounded_rectangle((110, 990, W - 110, 1130), radius=24, fill=mv.PANEL, outline=GOLD, width=2)
        centred(d, W / 2, 1012, "Data as of October 2026", latin(42, mv.MEDIUM), GOLD)
        centred(d, W / 2, 1070, "Updated monthly", latin(36), GOLD)
        d.rounded_rectangle((70, 1330, W - 70, 1650), radius=24, fill=mv.PANEL, outline=(52, 68, 92), width=2)
        centred(d, W / 2, 1365, "Full method & data", latin(34, mv.BOLD), GOLD)
        centred(d, W / 2, 1430, "GitHub", latin(30, mv.MEDIUM), QUIET)
        centred(d, W / 2, 1470, GITHUB, fit(d, GITHUB, latin, W - 180, 34), INK)
        centred(d, W / 2, 1545, "X Article", latin(30, mv.MEDIUM), QUIET)
        centred(d, W / 2, 1585, X_ARTICLE, fit(d, X_ARTICLE, latin, W - 180, 34), INK)
        return img
    centred(d, W / 2, 420, "PASSPORT", latin(120, mv.BOLD), INK)
    centred(d, W / 2, 550, "REAL RANKING 2026", latin(84, mv.BOLD), INK)
    centred(d, W / 2, 680, "护照真实含金量排行榜", cjk(76, True), GOLD)
    centred(d, W / 2, 860, "Not how many countries you can enter,", latin(42), INK)
    centred(d, W / 2, 916, "but how much they are worth.", latin(42), INK)
    centred(d, W / 2, 990, "不只看能去多少国家，更看那些地方值多少。", cjk(38), INK)
    centred(d, W / 2, 1110, "Score = Σ ease of entry × destination value", latin(36), QUIET)
    centred(d, W / 2, 1160, "得分 = Σ 入境便利度 × 目的地价值", cjk(34), QUIET)
    # Links.
    d.rounded_rectangle((70, 1330, W - 70, 1650), radius=24, fill=mv.PANEL, outline=(52, 68, 92), width=2)
    centred(d, W / 2, 1365, "Full method & data · 完整方法与数据", cjk(32, True), GOLD)
    centred(d, W / 2, 1430, "GitHub", latin(30, mv.MEDIUM), QUIET)
    centred(d, W / 2, 1470, GITHUB, fit(d, GITHUB, latin, W - 180, 34), INK)
    centred(d, W / 2, 1545, "X Article", latin(30, mv.MEDIUM), QUIET)
    centred(d, W / 2, 1585, X_ARTICLE, fit(d, X_ARTICLE, latin, W - 180, 34), INK)
    return img


def scroll_offset(t, distance):
    v = distance / (SCROLL - DECEL / 2)
    cruise = SCROLL - DECEL
    if t <= cruise:
        return v * t
    s = min(t - cruise, DECEL)
    return v * cruise + v * (s - s * s / (2 * DECEL))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", nargs="*", type=float)
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    args = ap.parse_args()
    mv.LANG = args.lang
    suffix = "" if args.lang == "zh" else "-en"

    with open(mv.PROC / "passport_ranking.csv", encoding="utf-8-sig") as f:
        ranking = sorted((r for r in csv.DictReader(f) if r["iso2"] not in mv.SKIP), key=lambda r: -int(r["rank"]))
    with open(mv.NOTES, encoding="utf-8-sig") as f:
        notes = {r["iso2"]: r for r in csv.DictReader(f)}
    with open(mv.PROC / "visa_matrix.csv", encoding="utf-8") as f:
        mix = {}
        for r in csv.DictReader(f):
            mix.setdefault(r["passport"], Counter())[r["code"]] += 1

    rows = [make_row(r, mix[r["iso2"]], notes.get(r["iso2"])) for r in ranking]
    base, intro = make_base(), make_intro()
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rectangle((0, TOP, W, BOTTOM), fill=255)

    # Row i sits at y = BOTTOM + i * STRIDE - offset; the scroll ends with #1 (the last row) at the foot of the
    # band, so the top three stay on screen.
    distance = BOTTOM + (len(rows) - 1) * STRIDE - (BOTTOM - ROW_H - 30)

    def frame(t):
        if t < INTRO:
            alpha = min(1.0, t / 0.8, max(0.0, (INTRO - t) / 0.8))
            return Image.blend(Image.new("RGB", (W, H), BG), intro, alpha)
        layer = base.copy()
        off = scroll_offset(t - INTRO, distance)
        for i, row in enumerate(rows):
            y = int(BOTTOM + i * STRIDE - off)
            if y > BOTTOM:
                break
            if y + ROW_H >= TOP:
                layer.paste(row, (LEFT, y), row)
        out = base.copy()
        out.paste(layer, (0, 0), mask)  # rows are clipped to the band, header and legend stay clean
        return out

    total = INTRO + SCROLL + HOLD
    mv.OUT.mkdir(exist_ok=True)
    if args.stills is not None:
        for s in args.stills:
            frame(min(s, total - 1 / FPS)).save(mv.OUT / f"still-v{suffix}-{s:g}s.png")
        print(f"{len(args.stills)} stills -> {mv.OUT}")
        return

    import imageio_ffmpeg

    path = mv.OUT / f"passport-real-ranking-2026-vertical{suffix}.mp4"
    writer = imageio_ffmpeg.write_frames(str(path), (W, H), fps=FPS, codec="libx264", quality=None, macro_block_size=1,
                                         output_params=["-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p"])
    writer.send(None)
    n = int(total * FPS)
    for k in range(n):
        writer.send(frame(k / FPS).tobytes())
    writer.close()
    print(f"{n} frames, {total:.0f}s -> {path}")


if __name__ == "__main__":
    main()
