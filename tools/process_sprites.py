#!/usr/bin/env python3
"""
process_sprites.py — clean + register Carl's sprite PNGs into a uniform set.

The important trick is REGISTRATION: if each image is trimmed to its own content
box, Carl jumps around when the sketch swaps faces. Instead we:

  1. key the flat background (magenta) to transparency (skipped if already alpha),
  2. find each image's content box, then the UNION box across all of them,
  3. crop every image to that same union box and center it on an identical square
     canvas — so Carl stays locked in the same place and scale across variants.

Usage (normally via process_sprites.sh, which handles the venv):
    process_sprites.py --in raw/ --out sprites/ --size 360

Outputs: <out>/<name>.png (size x size, transparent) for each input, plus
<out>/_preview.png — a labeled contact sheet so you can eyeball registration.
"""
import argparse
import os
import sys
from glob import glob

import numpy as np
from PIL import Image, ImageDraw


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def load_rgba(path):
    return Image.open(path).convert("RGBA")


def pad_to(im, w, h):
    """Center im on a transparent w x h canvas (no scaling)."""
    if im.width == w and im.height == h:
        return im
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return canvas


def key_background(im, bg, tol):
    """Turn the flat background color transparent. If the image already carries
    meaningful transparency (e.g. gpt-image-1 output), trust it and return as-is."""
    arr = np.asarray(im).astype(np.int32)   # int32: avoids overflow in the dist² below
    a = arr[..., 3]
    if (a < 250).mean() > 0.02:          # already has real transparency
        return im
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    dist = np.sqrt((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2)
    out = arr.copy()
    out[..., 3] = np.where(dist < tol, 0, 255)
    # de-fringe: kill the semi-magenta halo just outside the hard cutoff
    fringe = (dist >= tol) & (dist < tol * 1.8) & (g < np.minimum(r, b) - 20)
    out[fringe, 3] = 0
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def alpha_bbox(im, thresh=16):
    a = np.asarray(im)[..., 3]
    ys, xs = np.where(a > thresh)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def union(boxes):
    xs0 = min(b[0] for b in boxes)
    ys0 = min(b[1] for b in boxes)
    xs1 = max(b[2] for b in boxes)
    ys1 = max(b[3] for b in boxes)
    return [xs0, ys0, xs1, ys1]


def fit_center(im, size, pad_frac):
    """Scale im to fit within a size x size canvas (minus padding), preserving
    aspect, then center it. All inputs share the same crop dims, so this yields
    identical placement for every sprite."""
    inner = int(size * (1 - 2 * pad_frac))
    scale = min(inner / im.width, inner / im.height)
    new = im.resize((max(1, round(im.width * scale)),
                     max(1, round(im.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(new, ((size - new.width) // 2, (size - new.height) // 2), new)
    return canvas


def make_preview(outputs, size):
    n = len(outputs)
    cols = min(n, 3)
    rows = (n + cols - 1) // cols
    cell = size + 28
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (40, 40, 46, 255))
    draw = ImageDraw.Draw(sheet)
    # checkerboard so transparency is visible
    for i, (name, im) in enumerate(outputs):
        cx, cy = (i % cols) * cell, (i // cols) * cell
        for yy in range(0, size, 16):
            for xx in range(0, size, 16):
                if ((xx // 16) + (yy // 16)) % 2 == 0:
                    draw.rectangle([cx + xx, cy + yy, cx + xx + 16, cy + yy + 16],
                                   fill=(70, 70, 78, 255))
        sheet.alpha_composite(im, (cx, cy))
        draw.text((cx + 6, cy + size + 6), name, fill=(230, 230, 235, 255))
    return sheet


def main():
    ap = argparse.ArgumentParser(description="Clean + register Carl sprite PNGs.")
    ap.add_argument("--in", dest="indir", default="raw",
                    help="input dir of PNGs (default: raw/)")
    ap.add_argument("--out", dest="outdir", default="sprites",
                    help="output dir (default: sprites/)")
    ap.add_argument("--size", type=int, default=360,
                    help="output square size in px (default: 360)")
    ap.add_argument("--bg", default="FF00FF",
                    help="background color to key out, hex (default: FF00FF)")
    ap.add_argument("--tol", type=float, default=60,
                    help="color distance tolerance for keying (default: 60)")
    ap.add_argument("--margin", type=float, default=0.06,
                    help="transparent margin as a fraction of size (default: 0.06)")
    args = ap.parse_args()

    paths = sorted(glob(os.path.join(args.indir, "*.png")) +
                   glob(os.path.join(args.indir, "*.PNG")))
    if not paths:
        sys.exit(f"No PNGs found in {args.indir!r}. Drop Carl's images there first.")

    bg = hex_to_rgb(args.bg)
    os.makedirs(args.outdir, exist_ok=True)

    # Load + normalize to a common canvas size (so the union box shares coords).
    imgs = [(os.path.splitext(os.path.basename(p))[0], load_rgba(p)) for p in paths]
    maxw = max(im.width for _, im in imgs)
    maxh = max(im.height for _, im in imgs)
    imgs = [(name, key_background(pad_to(im, maxw, maxh), bg, args.tol))
            for name, im in imgs]

    boxes = []
    for name, im in imgs:
        bb = alpha_bbox(im)
        if bb is None:
            sys.exit(f"{name}: image is fully transparent after keying — wrong --bg?")
        boxes.append(bb)
    ubox = union(boxes)
    print(f"union content box: {ubox}  (from {len(imgs)} images @ {maxw}x{maxh})")

    outputs = []
    for name, im in imgs:
        cropped = im.crop(ubox)
        final = fit_center(cropped, args.size, args.margin)
        out_path = os.path.join(args.outdir, f"{name}.png")
        final.save(out_path)
        outputs.append((name, final))
        print(f"  {name:<16} -> {out_path}")

    preview = os.path.join(args.outdir, "_preview.png")
    make_preview(outputs, args.size).convert("RGB").save(preview)
    print(f"\nWrote {len(outputs)} sprites + {preview}")
    print("Open _preview.png and check Carl doesn't jump between cells.")


if __name__ == "__main__":
    main()
