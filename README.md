<div align="center">

# Aino

**A chat button with a dinosaur asleep inside it.**

Open the chat and he takes the full eight seconds to get up and roar.
Close it and the same eight seconds runs backwards until he is asleep again.

</div>

---

## Install

No build step, no dependencies, no framework. Copy the folder in, or add it as
a submodule:

```bash
git submodule add https://github.com/lbthejan/Aino.git vendor/aino
```

```html
<script type="module" src="/vendor/aino/src/aino.js"></script>

<aino-button id="aino"></aino-button>
```

```js
document.getElementById('aino').addEventListener('aino:toggle', (e) => {
  e.detail.open ? openMyChat() : closeMyChat();
});
```

That is the whole integration. **Aino is only the button** — it does not ship a
chat panel, because you already have one and yours will not look like mine.

## Works in whatever you are using

It is a Web Component, so there is no React build, no Vue build, no adapter.

<table>
<tr><td>

**React**

```jsx
import 'aino/src/aino.js';

export function Header() {
  const ref = useRef(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const el = ref.current;
    const on = (e) => setOpen(e.detail.open);
    el.addEventListener('aino:toggle', on);
    return () => el.removeEventListener('aino:toggle', on);
  }, []);

  return <aino-button ref={ref} />;
}
```

</td><td>

**Vue**

```vue
<script setup>
import 'aino/src/aino.js';
const open = ref(false);
</script>

<template>
  <aino-button @aino:toggle="open = $event.detail.open" />
</template>
```

</td></tr>
</table>

In Vue, tell the compiler it is a custom element:

```js
// vite.config.js
vue({ template: { compilerOptions: { isCustomElement: (t) => t.startsWith('aino-') } } })
```

## API

### Attributes

| Attribute | Default | What it does |
|---|---|---|
| `label` | `Aino` | Button text. Set `label=""` for the sprite alone. |
| `sleep` | bundled | Still shown while closed — must be **frame 1** of `wake` |
| `wake` | bundled | The get-up animation |
| `back` | bundled | The lie-down animation — `wake`'s frames reversed |
| `awake` | bundled | Still held while open — must be the **last frame** of `wake` |
| `wake-ms` | `8000` | How long `wake` runs before the `awake` still takes over |
| `back-ms` | `8000` | How long `back` runs before the `sleep` still takes over |

`wake-ms` and `back-ms` must match your clips. Set them wrong and he freezes
mid-roar, or snaps to standing early.

### Properties and methods

```js
aino.open          // boolean, read/write
aino.state         // 'asleep' | 'waking' | 'awake' | 'sleeping'
aino.show()        // open  — fires aino:toggle
aino.hide()        // close — fires aino:toggle
aino.toggle()      // fires aino:toggle
```

Setting `.open` directly drives the sprite **without** firing `aino:toggle`.
That is deliberate: if your chat can also be opened some other way, sync it
with `aino.open = true` and you will not get a feedback loop.

### Events

| Event | Detail | When |
|---|---|---|
| `aino:toggle` | `{ open: boolean }` | The user pressed the button. Bubbles, crosses shadow boundaries. |

### Styling

Custom properties pierce the shadow root:

```css
aino-button {
  --aino-bg: #fff;
  --aino-color: #15191a;
  --aino-border: rgba(21, 25, 26, .12);
  --aino-accent: #608e23;        /* hover border + focus ring */
  --aino-accent-wash: #f0f6e4;   /* hover fill */
  --aino-radius: 999px;
  --aino-sprite: 78px;           /* sprite width; the button sizes to it */
  --aino-font: inherit;
}
```

Or reach the internals with `::part(button)`, `::part(label)`, `::part(sprite)`.

The sprite's aspect ratio is read off your own `sleep` image at runtime, so
swapping in a differently-shaped character does not need a CSS change.

## Using your own character

Drop four files next to each other and point the attributes at them:

```html
<aino-button
  sleep="/mascot/sleep.png"
  wake="/mascot/wake.webp"
  back="/mascot/back.webp"
  awake="/mascot/awake.png"
  wake-ms="5000" back-ms="5000">
</aino-button>
```

If you have a video of your character getting up, `tools/` builds all four
from it in one command:

```bash
python tools/from_video.py mascot.mp4
```

It knocks out a flat background, crops every frame to one shared box, writes
the animation forwards and backwards, and emits the two stills. See
[`tools/README.md`](tools/README.md).

**The four files must share a canvas size**, and `sleep`/`awake` must be the
first and last frames of `wake`. Otherwise the sprite visibly jumps at each
hand-off.

## Why it is built the way it is

**A GIF cannot be paused.** It starts animating the instant it decodes and the
browser exposes no play, pause or seek. So the resting states are still images
and an animation is only in the DOM while it is actually running.

**A browser cannot play an animation backwards.** No reverse, no playback rate,
no seeking. Lying down has to be its own file with the frames written out in
reverse, which is what `--back-*` produces.

**Replaying needs a new URL.** Re-assigning the same one does nothing — the
browser keeps the decoded, already-running image. Cache-busting with `?t=`
costs a round trip every open. Each clip is fetched once as a Blob and every
play mints a fresh object URL from it: a new image to the browser, so it always
starts at frame 0, with no network.

**Nothing loads eagerly.** The clips are a few hundred KB each and plenty of
visitors never open a chat. Getting up is fetched when the browser goes idle or
the pointer reaches the button, whichever lands first; lying down only once the
chat has actually been opened. Clicking before a fetch finishes still works.

### Two traps, so you do not have to find them

**`img.decode()` never settles for an animated image** in Chrome — it neither
resolves nor rejects. Awaiting it leaves the sprite stuck forever. Aino waits
on the `load` event, which fires in single-digit milliseconds for the same file.

**`fetch(url, { cache: 'force-cache' })` serves a stale entry** regardless of
freshness, so replacing an animation keeps showing the old one until the cache
is cleared by hand. Aino uses `cache: 'default'`.

## Behaviour worth knowing

- Closing while he is still getting up settles him straight back to asleep
  rather than playing the lie-down clip — that clip starts from standing, so
  playing it there would snap him upright first.
- Re-opening while he is lying down restarts getting up.
- Every transition carries a token; an in-flight one bails if anything happened
  meanwhile, so rapid clicking cannot strand him.
- `prefers-reduced-motion` stops the idle breathing loop. The wake still plays,
  because that is the thing you asked for by clicking.

## Requirements

Any browser with custom elements, shadow DOM and animated WebP — so Chrome,
Edge, Firefox and Safari 16+. No polyfills, no bundler, no dependencies.

## Licence

Code: [MIT](LICENSE).

**The bundled dinosaur sprites are example assets, not part of the MIT grant.**
They came from a generated video and no licence is asserted over them here.
Replace them with artwork you own before shipping anything public.
