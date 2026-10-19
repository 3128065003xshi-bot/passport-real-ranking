"""Render the countdown video: the passports scroll past from last place to first.

    python scripts/make_video.py                 # -> video/passport-real-ranking-2026.mp4 (1920x1080, 60 fps)
    python scripts/make_video.py --stills 0 60 250 268   # write PNG frames at those seconds instead

Needs Pillow, imageio-ffmpeg (bundles ffmpeg) and macOS's Helvetica Neue + Hiragino Sans GB.
Passports listed in SKIP are left out of the video (ranks are kept as in the data, so their slot is a gap).
The note under each passport comes from data/processed/video_notes.csv (scripts/build_video_notes.py).
Flags come from assets/flags/ (flagcdn.com, w320). Passport covers are stylised, not real cover art:
each cover takes the flag's dominant colour, darkened.
"""
import argparse
import csv
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PROC, FLAGS, OUT = ROOT / "data/processed", ROOT / "assets/flags", ROOT / "video"
NOTES = ROOT / "data/processed/video_notes.csv"  # from scripts/build_video_notes.py
SKIP = {"TW"}

W, H, FPS = 1920, 1080, 60
INTRO, SCROLL, HOLD = 7.0, 240.0, 8.0  # seconds
DECEL = 6.0  # the scroll slows to a stop over its last DECEL seconds
CARD_W, GAP, CARD_Y, CARD_H = 344, 24, 150, 830
STRIDE = CARD_W + GAP

BG, PANEL, INK, QUIET, GOLD = (12, 20, 33), (22, 33, 50), (255, 255, 255), (143, 163, 191), (226, 190, 110)
MEDALS = {1: (240, 200, 90), 2: (205, 212, 222), 3: (214, 150, 95)}
CODE_COLOURS = {"S": (124, 92, 255), "A": (46, 189, 133), "B": (91, 192, 235), "C": (242, 193, 78),
                "D": (242, 140, 56), "E": (229, 72, 77), "F": (90, 90, 90)}
CODE_NAMES = {"S": "Free movement 自由流动", "A": "Visa-free 免签", "B": "eTA 电子授权", "C": "On arrival 落地签",
              "D": "e-Visa 电子签", "E": "Visa 需签证", "F": "Banned 禁止"}
GITHUB = "github.com/3128065003xshi-bot/passport-real-ranking"

LATIN = "/System/Library/Fonts/HelveticaNeue.ttc"
CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"
REGULAR, BOLD, MEDIUM = 0, 1, 10


def latin(size, face=REGULAR):
    return ImageFont.truetype(LATIN, size, index=face)


def cjk(size, bold=False):
    return ImageFont.truetype(CJK, size, index=1 if bold else 0)


def one_dp(value):
    return Decimal(value).quantize(Decimal("0.1"), ROUND_HALF_UP)


def centred(d, cx, y, text, f, fill):
    w = d.textlength(text, font=f)
    d.text((cx - w / 2, y), text, font=f, fill=fill)


def fit(d, text, f_for_size, max_w, start):
    """Largest font size <= start at which text fits max_w."""
    size = start
    while size > 14 and d.textlength(text, font=f_for_size(size)) > max_w:
        size -= 2
    return f_for_size(size)


def cover_colour(flag):
    """Dominant non-white, non-near-black colour of the flag, darkened for a passport cover."""
    small = flag.convert("RGB").resize((64, 40))
    counts = Counter(small.get_flattened_data())
    for (r, g, b), _ in counts.most_common():
        if max(r, g, b) - min(r, g, b) > 40 or max(r, g, b) < 200:  # skip whites and pale greys
            k = 0.42
            return int(r * k + 10), int(g * k + 10), int(b * k + 14)
    return 30, 40, 70


def make_card(r, codes, note):
    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    rank = int(r["rank"])
    medal = MEDALS.get(rank)
    d.rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), radius=22, fill=PANEL,
                        outline=medal or (40, 54, 76), width=4 if medal else 2)
    cx = CARD_W / 2

    centred(d, cx, 22, f"#{rank}", latin(64, BOLD), medal or INK)

    # Stylised passport cover.
    flag = Image.open(FLAGS / f"{r['iso2'].lower()}.png").convert("RGBA")
    bw, bh, bx, by = 200, 260, (CARD_W - 200) // 2, 108
    shadow = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((bx + 8, by + 10, bx + bw + 8, by + bh + 10), radius=14, fill=(0, 0, 0, 120))
    card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)))
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=14, fill=cover_colour(flag))
    d.line((bx + 18, by + 6, bx + 18, by + bh - 6), fill=(0, 0, 0), width=2)  # spine
    centred(d, bx + bw / 2 + 8, by + 22, "PASSPORT", latin(22, BOLD), GOLD)
    fw = 116
    emblem = flag.resize((fw, round(flag.height * fw / flag.width)), Image.LANCZOS)
    ex, ey = int(bx + bw / 2 + 8 - fw / 2), int(by + bh / 2 - emblem.height / 2)
    d.rectangle((ex - 3, ey - 3, ex + fw + 2, ey + emblem.height + 2), fill=GOLD)
    card.alpha_composite(emblem, (ex, ey))
    name_up = r["name_en"].upper()
    centred(d, bx + bw / 2 + 8, by + bh - 46, name_up, fit(d, name_up, lambda s: latin(s, MEDIUM), bw - 40, 18), GOLD)

    # Names, score.
    centred(d, cx, 390, r["name_zh"], fit(d, r["name_zh"], lambda s: cjk(s, True), CARD_W - 30, 44), INK)
    centred(d, cx, 446, r["name_en"], fit(d, r["name_en"], latin, CARD_W - 30, 28), QUIET)
    centred(d, cx, 488, f"{one_dp(r['pct_of_max'])}%", latin(66, BOLD), medal or INK)
    centred(d, cx, 562, "of max score · 满分占比", cjk(20), QUIET)

    # Entry-type mix across 199 destinations.
    x0, bar_w, y = 22, CARD_W - 44, 604
    total = sum(codes.values())
    x = x0
    for code, colour in CODE_COLOURS.items():
        w = bar_w * codes.get(code, 0) / total
        if w:
            d.rectangle((x, y, x + w, y + 26), fill=colour)
        x += w
    no_visa = sum(codes.get(c, 0) for c in "SABC")
    centred(d, cx, y + 40, f"No visa · 无需签证  {no_visa} / 199", cjk(20), QUIET)

    if note:
        d.line((40, 680, CARD_W - 40, 680), fill=(52, 68, 92), width=2)
        for y, key, font, colour in ((694, "note_zh1", cjk, GOLD), (726, "note_en1", latin, INK),
                                     (758, "note_zh2", cjk, GOLD), (790, "note_en2", latin, INK)):
            text = note[key]
            size = 22 if font is cjk else 18
            if key in ("note_zh2", "note_en2") and d.textlength(text, font=font(15)) > CARD_W - 28:
                text = note[key + "_short"]  # two destinations per type do not fit: one each
            if text:
                centred(d, cx, y, text, fit(d, text, font, CARD_W - 28, size), colour)
    return card


def make_frame_base():
    base = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(base)
    d.text((48, 34), "PASSPORT REAL RANKING 2026", font=latin(46, BOLD), fill=INK)
    d.text((48 + d.textlength("PASSPORT REAL RANKING 2026", font=latin(46, BOLD)) + 28, 38),
           "护照真实含金量排行榜", font=cjk(40, True), fill=GOLD)
    d.text((50, 100), "Passports weighted by how much each destination is worth · 按目的地价值加权的护照排名",
           font=cjk(24), fill=QUIET)
    # Legend.
    x, y = 48, 1010
    for code, colour in CODE_COLOURS.items():
        d.rectangle((x, y + 4, x + 22, y + 26), fill=colour)
        d.text((x + 30, y), CODE_NAMES[code], font=cjk(21), fill=QUIET)
        x += 34 + d.textlength(CODE_NAMES[code], font=cjk(21)) + 26
    d.text((W - 48 - d.textlength(GITHUB, font=latin(24)), 106), GITHUB, font=latin(24), fill=QUIET)
    return base


def make_intro():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    centred(d, W / 2, 250, "PASSPORT REAL RANKING 2026", latin(92, BOLD), INK)
    centred(d, W / 2, 370, "护照真实含金量排行榜", cjk(80, True), GOLD)
    centred(d, W / 2, 520, "Not how many countries you can enter, but how much they are worth.", latin(40), INK)
    centred(d, W / 2, 580, "不只看能去多少国家，更看那些地方值多少。", cjk(38), INK)
    centred(d, W / 2, 690, "Passport score = Σ  ease of entry × destination tourism score", latin(34), QUIET)
    centred(d, W / 2, 740, "护照得分 = Σ 入境便利度 × 目的地旅游分数   ·   199 destinations 个目的地", cjk(30), QUIET)
    centred(d, W / 2, 900, GITHUB, latin(28), QUIET)
    return img


def scroll_offset(t, distance):
    """Pixels scrolled after t seconds of the scroll phase: constant speed, then a smooth stop."""
    v = distance / (SCROLL - DECEL / 2)
    cruise = SCROLL - DECEL
    if t <= cruise:
        return v * t
    s = min(t - cruise, DECEL)
    return v * cruise + v * (s - s * s / (2 * DECEL))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", nargs="*", type=float, help="write PNG frames at these seconds instead of the video")
    args = ap.parse_args()

    with open(PROC / "passport_ranking.csv", encoding="utf-8-sig") as f:
        ranking = sorted((r for r in csv.DictReader(f) if r["iso2"] not in SKIP), key=lambda r: -int(r["rank"]))
    with open(NOTES, encoding="utf-8-sig") as f:
        notes = {r["iso2"]: r for r in csv.DictReader(f)}
    with open(PROC / "visa_matrix.csv", encoding="utf-8") as f:
        mix = {}
        for r in csv.DictReader(f):
            mix.setdefault(r["passport"], Counter())[r["code"]] += 1

    cards = [make_card(r, mix[r["iso2"]], notes.get(r["iso2"])) for r in ranking]
    base, intro = make_frame_base(), make_intro()

    # Card i sits at x = W + i * STRIDE - offset; the scroll ends with #1 (the last card) centred.
    distance = W + (len(cards) - 1) * STRIDE - (W - CARD_W) / 2

    def frame(t):
        if t < INTRO:
            alpha = min(1.0, t / 0.8, max(0.0, (INTRO - t) / 0.8))
            return Image.blend(Image.new("RGB", (W, H), BG), intro, alpha)
        img = base.copy()
        off = scroll_offset(t - INTRO, distance)
        first = max(0, int((off - W - CARD_W) // STRIDE))
        for i in range(first, len(cards)):
            x = int(W + i * STRIDE - off)
            if x > W:
                break
            if x + CARD_W >= 0:
                img.paste(cards[i], (x, CARD_Y), cards[i])
        return img

    total = INTRO + SCROLL + HOLD
    if args.stills is not None:
        OUT.mkdir(exist_ok=True)
        for s in args.stills:
            frame(min(s, total - 1 / FPS)).save(OUT / f"still-{s:g}s.png")
        print(f"{len(args.stills)} stills -> {OUT}")
        return

    import imageio_ffmpeg

    OUT.mkdir(exist_ok=True)
    path = OUT / "passport-real-ranking-2026.mp4"
    writer = imageio_ffmpeg.write_frames(str(path), (W, H), fps=FPS, codec="libx264", quality=None, macro_block_size=1,
                                         output_params=["-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p"])
    writer.send(None)
    n = int(total * FPS)
    for k in range(n):
        writer.send(frame(k / FPS).tobytes())
        if k % (FPS * 30) == 0:
            print(f"{k / FPS:.0f}s / {total:.0f}s", flush=True)
    writer.close()
    print(f"{n} frames, {total:.0f}s -> {path}")


if __name__ == "__main__":
    main()
