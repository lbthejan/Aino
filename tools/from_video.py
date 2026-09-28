"""
Turn the source video into the three assets the widget needs.

    python tools/from_video.py "D:/Downloads/getup_layz_and_roar_....mp4"

Writes:
    assets/dino-wake.webp    the animation, 8s, loop-once, 8-bit alpha
    assets/dino-sleep.png    its first frame  (shown while the chat is closed)
    assets/dino-awake.png    its last frame   (held once the chat is open)

All three share one canvas. That matters: the widget hands off still ->
animation -> still, and if the canvases or poses differ by even a pixel the
sprite visibly jumps at each swap.

The crop box is the union across every frame, not per-frame. The character
goes from lying flat to standing upright, so a per-frame tight crop would make
him jitter and rescale as he moves.
"""

import argparse
import os
import sys

import av
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cutout import cut  # noqa: E402  same matting used for the still


def frames_from(path):
    container = av.open(path)
    stream = container.streams.video[0]
    fps = float(stream.average_rate)
    for frame in container.decode(video=0):
        yield Image.fromarray(frame.to_ndarray(format='rgb24'))
    container.close()
    return fps


def main():
    p = argparse.ArgumentParser()
    p.add_argument('src')
    p.add_argument('--width', type=int, default=340,
                   help='output width in px (default 340, ~1.4x the on-screen size)')
    p.add_argument('--total-ms', type=int, default=8000, help='animation length (default 8000)')
    p.add_argument('--every', type=int, default=2,
                   help='keep 1 in N frames. Default 2 = 12fps, which is how cartoons '
                        'are animated anyway, and halves the file size.')
    p.add_argument('--threshold', type=int, default=236)
    p.add_argument('--sat', type=int, default=18)
    p.add_argument('--feather', type=float, default=0.8)
    p.add_argument('--choke', type=float, default=0.42)
    p.add_argument('--min-island', type=int, default=150, dest='min_island',
                   help='bigger than the still default: video compression speckles the backdrop')
    p.add_argument('--back-every', type=int, default=1, dest='back_every',
                   help='extra frame thinning for the reverse clip, on top of --every (default 1)')
    p.add_argument('--back-ms', type=int, default=8000, dest='back_ms',
                   help='length of the reverse clip (default 8000 — a true 1:1 reverse)')
    p.add_argument('--quality', type=int, default=64)
    p.add_argument('--alpha-quality', type=int, default=78, dest='alpha_quality',
                   help='alpha channel quality; the matte tolerates less than the colour')
    args = p.parse_args()

    container = av.open(args.src)
    raw = [Image.fromarray(f.to_ndarray(format='rgb24')) for f in container.decode(video=0)]
    container.close()
    raw = raw[::args.every]
    print(f'{len(raw)} frames at {raw[0].size[0]}x{raw[0].size[1]}')

    cutouts = [cut(f, args.threshold, args.sat, args.feather, args.choke, args.min_island)
               for f in raw]

    # one box for all of them
    box = None
    for f in cutouts:
        b = f.getbbox()
        if b is None:
            continue
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                     max(box[2], b[2]), max(box[3], b[3]))
    print(f'union crop {box}  ->  {box[2]-box[0]}x{box[3]-box[1]}')

    cw = box[2] - box[0]
    scale = args.width / cw
    size = (args.width, max(int(round((box[3] - box[1]) * scale)), 1))
    frames = [f.crop(box).resize(size, Image.LANCZOS) for f in cutouts]
    print(f'output canvas {size[0]}x{size[1]}')

    # durations that sum to exactly total_ms, no drift
    n = len(frames)
    edges = [round(i * args.total_ms / n) for i in range(n + 1)]
    durations = [edges[i + 1] - edges[i] for i in range(n)]

    os.makedirs('assets', exist_ok=True)
    frames[0].save('assets/dino-wake.webp', save_all=True, append_images=frames[1:],
                   duration=durations, loop=1, quality=args.quality,
                   alpha_quality=args.alpha_quality, method=4, exact=True)

    # The same frames reversed: he lies back down when the chat closes.
    # A browser cannot play an animation backwards, so this has to exist as its
    # own file. By default it is a true 1:1 mirror of getting up — same frames,
    # same length. --back-every / --back-ms can thin or shorten it if the
    # weight ever matters more than the fidelity.
    back = frames[::-1][::args.back_every]
    bn = len(back)
    bedges = [round(i * args.back_ms / bn) for i in range(bn + 1)]
    bdur = [bedges[i + 1] - bedges[i] for i in range(bn)]
    back[0].save('assets/dino-back.webp', save_all=True, append_images=back[1:],
                 duration=bdur, loop=1, quality=args.quality,
                 alpha_quality=args.alpha_quality, method=4, exact=True)
    frames[0].save('assets/dino-sleep.png')
    frames[-1].save('assets/dino-awake.png')

    # A square avatar for the chat header, cropped to the head of the final
    # frame. The full poster is mostly empty space once it is 38px wide.
    last = frames[-1]
    b = last.getbbox()
    side = max((b[2] - b[0]), (b[3] - b[1]) // 2)
    cx = (b[0] + b[2]) // 2
    head = last.crop((max(cx - side // 2, 0), b[1],
                      min(cx + side // 2, last.width), min(b[1] + side, last.height)))
    head.resize((96, 96), Image.LANCZOS).save('assets/dino-avatar.png')


    for path in ('assets/dino-wake.webp', 'assets/dino-back.webp', 'assets/dino-sleep.png',
                 'assets/dino-awake.png', 'assets/dino-avatar.png'):
        print(f'  {path:26s} {os.path.getsize(path)/1024:7.0f} KB')
    print(f'  wake  {sum(durations)} ms over {n} frames')
    print(f'  back  {sum(bdur)} ms over {bn} frames')
    print(f'\nCSS: --dino-aspect: {size[0]} / {size[1]}')


if __name__ == '__main__':
    main()
