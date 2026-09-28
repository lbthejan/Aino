# tools

Building Aino's four sprite files from a video of your character getting up.

```bash
pip install pillow numpy scipy av
python tools/from_video.py mascot.mp4
```

Writes into `assets/`:

| File | What it is |
|---|---|
| `dino-wake.webp` | the animation, forwards |
| `dino-back.webp` | the same frames reversed, for lying back down |
| `dino-sleep.png` | frame 1 — shown while the chat is closed |
| `dino-awake.png` | the last frame — held while the chat is open |
| `dino-avatar.png` | a square head crop, handy for a chat header |

## What it does

**Knocks out the background.** Only white that the *image border can reach* is
removed, so interior white — teeth, an eye glint — survives as an island the
flood never gets to. The matte is then choked inward slightly, because the
outermost ring of a feathered edge is mostly backdrop and leaving it in gives a
pale halo on dark backgrounds. Edge pixels get the backdrop colour divided back
out of them, for the same reason.

**Uses one crop box for every frame.** A character that goes from lying flat to
standing upright would jitter and rescale if each frame were cropped to its own
bounds, so the box is the union across all of them.

**Writes WebP, not GIF.** GIF transparency is 1 bit — a pixel is either fully
there or fully gone — so a cut-out GIF gets hard jagged edges against any
background except the one it was matted on. WebP carries real 8-bit alpha.

## Flags

| Flag | Default | Effect |
|---|---|---|
| `--every` | `2` | Keep 1 frame in N. `2` → 12 fps, which is how cartoons are animated anyway, and halves the size. |
| `--width` | `340` | Output width in px. |
| `--quality` | `64` | Colour quality. 82 looked no better and cost 40% more. |
| `--alpha-quality` | `78` | Matte quality. Edges tolerate less than the colour does. |
| `--total-ms` | `8000` | Length of the forward clip. Must match `wake-ms`. |
| `--back-ms` | `8000` | Length of the reverse clip. Must match `back-ms`. |
| `--back-every` | `1` | Extra thinning for the reverse, on top of `--every`. |

If weight matters more than fidelity, thin the reverse first — settling reads
fine at a lower frame rate where getting up does not:

```bash
python tools/from_video.py mascot.mp4 --back-every 2 --back-ms 4000
```

Then set `back-ms="4000"` on the element.

## cutout.py on its own

For a single still, or to re-matte an existing GIF:

```bash
python tools/cutout.py raw.gif out.webp \
  --poster-first sleep.png --poster-last awake.png
```

| Flag | Default | Effect |
|---|---|---|
| `--threshold` | `236` | Minimum RGB to count as backdrop |
| `--sat` | `18` | Maximum channel spread to count as neutral |
| `--feather` | `0.7` | Edge softness in px |
| `--choke` | `0.42` | How far the matte shrinks inward |
| `--min-island` | `40` | Discard foreground blobs smaller than this |

`--choke` above about `0.5` starts eating a character's outline. Video frames
want a larger `--min-island` than a clean still — around 150 — because
compression speckles the backdrop with stray near-white pixels.

## Checking the result

Composite the output over black before you trust it. A pale halo and stray
specks are invisible on white and obvious on dark, which is exactly the
background your users might have.
