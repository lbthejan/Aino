"""
Knock the flat background out of a character image, keeping soft edges.

Works on a single still (-> PNG/WebP with 8-bit alpha) and on an animated
GIF/WebP (-> animated WebP or APNG, frame by frame). Run it on the real
dinosaur GIF when it arrives:

    python tools/cutout.py dino-raw.gif assets/dino.webp

Why not write the animation back out as a .gif? GIF alpha is 1 bit — every
pixel is fully opaque or fully gone — so a cut-out GIF gets hard jagged
edges over any background that isn't the one it was matted on. Animated WebP
and APNG carry real 8-bit alpha and are supported everywhere that matters.
"""

import argparse
import os

import numpy as np
from PIL import Image
from scipy import ndimage


def alpha_for(rgb, threshold, sat_limit, feather, choke, min_island):
    """Alpha channel for one RGB frame: background is the flat, desaturated
    region connected to the border. Interior whites (teeth, eye glints) stay."""
    a = rgb.astype(np.int16)
    lo = a.min(axis=2)
    hi = a.max(axis=2)

    # candidate background: bright AND close to neutral, so a pale-but-coloured
    # belly isn't mistaken for the backdrop
    candidate = (lo > threshold) & ((hi - lo) < sat_limit)

    # keep only what the border can reach — 4-connectivity, so anti-aliased
    # diagonal gaps can't leak the flood into the character
    labels, n = ndimage.label(candidate, structure=ndimage.generate_binary_structure(2, 1))
    if n:
        edge = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
        touching = set(np.unique(edge)) - {0}
        background = np.isin(labels, list(touching)) if touching else np.zeros_like(candidate)
    else:
        background = np.zeros_like(candidate)

    solid = ~background

    # drop stray 2-3px islands of "foreground" left in the backdrop
    if min_island > 0:
        lab, k = ndimage.label(solid, structure=ndimage.generate_binary_structure(2, 2))
        if k:
            sizes = np.bincount(lab.ravel())
            sizes[0] = 0
            solid = np.isin(lab, np.nonzero(sizes >= min_island)[0])

    alpha = solid.astype(np.float32)
    if feather > 0:
        alpha = ndimage.gaussian_filter(alpha, feather)

    # Choke the matte inward. The outermost ring of a feathered edge is mostly
    # backdrop, and leaving it in is what produces a pale halo once the sprite
    # sits on anything darker than the colour it was matted on.
    hi = min(choke + 0.40, 0.99)
    alpha = np.clip((alpha - choke) / (hi - choke), 0, 1)
    return alpha


def decontaminate(rgb, alpha, bg_color):
    """Undo the backdrop bleeding into semi-transparent edge pixels.

    An edge pixel is observed as  C = a·F + (1-a)·B, so the character's true
    colour is  F = (C - (1-a)·B) / a.  Without this the cut-out carries a pale
    halo that only shows up once you put it on a dark background."""
    a = alpha[..., None]
    # Floor the divisor: at alpha 0.02 this term amplifies by 50x and turns
    # edge noise into bright white pixels, which is worse than the halo.
    safe = np.maximum(a, 0.30)
    f = (rgb.astype(np.float32) - (1 - a) * bg_color) / safe
    out = np.where(a > 0.05, f, rgb.astype(np.float32))
    return np.clip(out, 0, 255).astype(np.uint8)


def cut(frame, threshold, sat_limit, feather, choke, min_island):
    rgb = np.asarray(frame.convert('RGB'))
    alpha = alpha_for(rgb, threshold, sat_limit, feather, choke, min_island)

    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).astype(np.float32)
    bg_color = np.median(border, axis=0)

    rgb = decontaminate(rgb, alpha, bg_color)
    out = np.dstack([rgb, (alpha * 255).round().astype(np.uint8)])
    return Image.fromarray(out, 'RGBA')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('src')
    p.add_argument('dst')
    p.add_argument('--threshold', type=int, default=236, help='min RGB to count as backdrop (default 236)')
    p.add_argument('--sat', type=int, default=18, help='max channel spread to count as neutral (default 18)')
    p.add_argument('--feather', type=float, default=0.7, help='edge softness in px (0 = hard, default 0.7)')
    p.add_argument('--choke', type=float, default=0.42,
                   help='shrink the matte inward to kill the pale halo (default 0.42)')
    p.add_argument('--min-island', type=int, default=40, dest='min_island',
                   help='discard foreground blobs smaller than this many px (default 40)')
    p.add_argument('--pad', type=int, default=1, help='transparent padding kept around the crop')
    p.add_argument('--no-trim', action='store_true', help='keep the original canvas instead of cropping')
    p.add_argument('--poster-first', dest='poster_first', metavar='PATH',
                   help='also write the FIRST frame as a still (the "asleep" poster)')
    p.add_argument('--poster-last', dest='poster_last', metavar='PATH',
                   help='also write the LAST frame as a still (the "awake" poster)')
    args = p.parse_args()

    src = Image.open(args.src)
    frames = []
    durations = []
    for i in range(getattr(src, 'n_frames', 1)):
        src.seek(i)
        frames.append(cut(src.copy(), args.threshold, args.sat, args.feather,
                          args.choke, args.min_island))
        durations.append(src.info.get('duration', 80))

    # one crop box for every frame, so an animation doesn't jitter
    if not args.no_trim:
        box = None
        for f in frames:
            b = f.getbbox()
            if b is None:
                continue
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                         max(box[2], b[2]), max(box[3], b[3]))
        if box:
            pad = args.pad
            box = (max(box[0] - pad, 0), max(box[1] - pad, 0),
                   min(box[2] + pad, frames[0].width), min(box[3] + pad, frames[0].height))
            frames = [f.crop(box) for f in frames]

    os.makedirs(os.path.dirname(os.path.abspath(args.dst)) or '.', exist_ok=True)
    ext = os.path.splitext(args.dst)[1].lower()

    if len(frames) == 1:
        frames[0].save(args.dst)
    elif ext == '.webp':
        frames[0].save(args.dst, save_all=True, append_images=frames[1:],
                       duration=durations, loop=0, lossless=True, exact=True)
    elif ext == '.png':
        frames[0].save(args.dst, save_all=True, append_images=frames[1:],
                       duration=durations, loop=0)
    else:
        raise SystemExit(f'{ext} cannot carry 8-bit alpha for an animation — use .webp or .png')

    # The widget hands off still -> animation -> still, so the posters have to
    # be the animation's own end frames on the same canvas, or it jumps.
    for path, frame in ((args.poster_first, frames[0]), (args.poster_last, frames[-1])):
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
            frame.save(path)
            print(f'  poster -> {path}')

    opaque = sum(int((np.asarray(f)[..., 3] > 0).sum()) for f in frames) / len(frames)
    total = frames[0].width * frames[0].height
    print(f'{args.src} -> {args.dst}')
    print(f'  frames {len(frames)}  size {frames[0].width}x{frames[0].height}'
          f'  kept {opaque / total * 100:.1f}% of pixels')


if __name__ == '__main__':
    main()
