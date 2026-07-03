#!/usr/bin/env python3
"""
make_gifs.py — render preview GIFs of Carl's states for the README.

Renders in the device's native 480px coordinate space (so the animation math and
overlay positions match the sketch exactly), masks to a circle to mimic the round
display, then downscales for file size. Also writes an expressions grid PNG.

    tools/.venv/bin/python tools/make_gifs.py --in sprites --out docs
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFont

S = 480                    # render size (matches the device)
R = 240                    # round-screen radius
CXY = 240
OUT = 300                  # downscaled output size

BG      = (74, 110, 105)
BEZEL   = (22, 22, 26)
POOP    = (122, 82, 52)
POOP_SH = (94, 60, 36)
HEART   = (235, 90, 110)
DOT     = (245, 245, 245)
WHITE   = (250, 250, 250)
DARK    = (30, 24, 20)
FLASH   = [(230, 60, 60), (240, 150, 40), (240, 220, 60),
           (70, 200, 90), (70, 160, 235), (180, 90, 220)]

sprites = {}
_mask = None


def load(indir):
    global _mask
    for name in ("neutral", "happy", "dizzy", "sleepy", "thinking", "butt"):
        sprites[name] = Image.open(os.path.join(indir, f"carl_{name}.png")).convert("RGBA")
    _mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(_mask).ellipse([CXY - R, CXY - R, CXY + R, CXY + R], fill=255)


def fe(d, cx, cy, rx, ry, col):
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=col)


def draw_poop(d, cx, by, lean):
    xb = cx
    xm = cx + lean // 2
    xt = cx + lean
    xp = cx + lean * 13 // 10
    fe(d, xb + 3, by - 12, 34, 16, POOP_SH)
    fe(d, xb, by - 14, 34, 16, POOP)
    fe(d, xm, by - 30, 25, 14, POOP)
    fe(d, xt, by - 44, 16, 11, POOP)
    d.polygon([(xp - 9, by - 47), (xp + 9, by - 47), (xp, by - 60)], fill=POOP)
    fe(d, xb - 6, by - 22, 14, 4, POOP_SH)
    fe(d, xm + 5, by - 37, 10, 3, POOP_SH)
    fe(d, xm - 8, by - 33, 4, 4, WHITE)
    fe(d, xm + 8, by - 33, 4, 4, WHITE)
    fe(d, xm - 8, by - 33, 2, 2, DARK)
    fe(d, xm + 8, by - 33, 2, 2, DARK)
    d.line([(xm - 6, by - 24), (xm, by - 21), (xm + 6, by - 24)], fill=DARK, width=2)


def draw_heart(d, x, y, s):
    fe(d, x - s // 2, y - s // 4, s // 2, s // 2, HEART)
    fe(d, x + s // 2, y - s // 4, s // 2, s // 2, HEART)
    d.polygon([(x - s, y - s // 6), (x + s, y - s // 6), (x, y + s)], fill=HEART)


def frame(bg, carl=None, angle=0.0, dx=0, dy=0, overlays=None):
    """Compose one masked frame -> downscaled RGB image."""
    disc = Image.new("RGBA", (S, S), bg + (255,))
    if carl is not None:
        spr = sprites[carl]
        if angle:
            spr = spr.rotate(angle, resample=Image.BICUBIC, expand=False)
        disc.alpha_composite(spr, ((S - spr.width) // 2 + dx, (S - spr.height) // 2 + dy))
    if overlays:
        overlays(ImageDraw.Draw(disc))
    out = Image.new("RGB", (S, S), BEZEL)
    out.paste(disc.convert("RGB"), (0, 0), _mask)
    return out.resize((OUT, OUT), Image.LANCZOS)


def save_gif(path, frames, ms):
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=ms, loop=0, disposal=2, optimize=True)
    print(f"  {os.path.basename(path):<16} {len(frames)} frames  {os.path.getsize(path)//1024} KB")


def build(outdir):
    os.makedirs(outdir, exist_ok=True)

    # idle — breathing bob
    fr = [frame(BG, "neutral", dy=round(5 * math.sin(2 * math.pi * i / 40))) for i in range(40)]
    save_gif(f"{outdir}/idle.gif", fr, 90)

    # spin — full rotation (tracks the knob on-device)
    fr = [frame(BG, "neutral", angle=i * 10) for i in range(36)]
    save_gif(f"{outdir}/spin.gif", fr, 45)

    # dizzy — wobble + bob, spiral eyes
    fr = [frame(BG, "dizzy",
                angle=10 * math.sin(2 * math.pi * i / 15),
                dy=round(4 * math.sin(2 * math.pi * i / 10))) for i in range(30)]
    save_gif(f"{outdir}/dizzy.gif", fr, 70)

    # thinking — color drumroll + building dots
    fr = []
    for i in range(36):
        dots = min(3, 1 + i * 3 // 36)
        def ov(d, dots=dots):
            for k in range(dots):
                fe(d, 300 + k * 24, 108 - k * 10, 7, 7, DOT)
        fr.append(frame(FLASH[(i // 3) % 6], "thinking",
                        dy=round(5 * math.sin(2 * math.pi * i / 20)), overlays=ov))
    save_gif(f"{outdir}/thinking.gif", fr, 95)

    # yes — happy bounce + rock + hearts
    fr = []
    for i in range(30):
        p = 2 * math.pi * i / 10
        def ov(d, i=i):
            if (i // 3) % 2 == 0:
                draw_heart(d, 120, 150, 20)
                draw_heart(d, 360, 150, 20)
        fr.append(frame(BG, "happy", angle=9 * math.sin(p),
                        dy=-round(16 * abs(math.sin(p))), overlays=ov))
    save_gif(f"{outdir}/yes.gif", fr, 60)

    # no — turn, plop, and the Carl+poop duet (mirrors ANSWER_NO exactly)
    fr = []
    for i in range(56):
        ph = i * 60
        if ph < 550:
            dx = round(22 * math.sin(ph * 0.025))
            def ov(d, ph=ph):
                if ph > 200:
                    pt = min(1.0, (ph - 200) / 300.0)
                    drop = round((1 - pt) * (1 - pt) * -70)
                    draw_poop(d, CXY, 458 + drop, 0)
            fr.append(frame(BG, "butt", dx=dx, overlays=ov))
        else:
            t2 = ph - 550
            sway = round(18 * math.sin(t2 * 0.008))
            carlHop = round(14 * abs(math.sin(t2 * 0.012)))
            poopHop = round(14 * abs(math.sin(t2 * 0.012 + math.pi)))
            lean = round(10 * math.sin(t2 * 0.02))
            def ov(d, sway=sway, poopHop=poopHop, lean=lean):
                draw_poop(d, CXY - round(sway * 0.7), 458 - poopHop, lean)
            fr.append(frame(BG, "butt", dx=sway, dy=-carlHop, overlays=ov))
    save_gif(f"{outdir}/no.gif", fr, 60)

    # expressions grid (3x2)
    cell, pad = OUT, 16
    labels = [("neutral", "neutral"), ("happy", "happy"), ("dizzy", "dizzy"),
              ("sleepy", "sleepy"), ("thinking", "thinking"), ("butt", "nope!")]
    cols, rows = 3, 2
    grid = Image.new("RGB", (cols * (cell + pad) + pad, rows * (cell + pad + 26) + pad), BEZEL)
    gd = ImageDraw.Draw(grid)
    for idx, (name, cap) in enumerate(labels):
        tile = frame(BG, name)
        cx = pad + (idx % cols) * (cell + pad)
        cy = pad + (idx // cols) * (cell + pad + 26)
        grid.paste(tile, (cx, cy))
        gd.text((cx + 6, cy + cell + 4), cap, fill=(230, 230, 235))
    grid.save(f"{outdir}/expressions.png")
    print(f"  expressions.png  {os.path.getsize(f'{outdir}/expressions.png')//1024} KB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", default="sprites")
    ap.add_argument("--out", dest="outdir", default="docs")
    args = ap.parse_args()
    load(args.indir)
    build(args.outdir)
    print("done")


if __name__ == "__main__":
    main()
