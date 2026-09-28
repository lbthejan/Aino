/**
 * Aino — a chat button with a dinosaur asleep inside it.
 *
 * Open the chat and he takes the full clip to get up and roar, then holds
 * standing. Close it and the same clip runs backwards until he is asleep
 * again.
 *
 *   <script type="module" src="aino/src/aino.js"></script>
 *   <aino-button></aino-button>
 *
 *   document.querySelector('aino-button')
 *     .addEventListener('aino:toggle', e => e.detail.open ? openChat() : closeChat());
 *
 * Aino is only the button. Wiring it to a chat panel is the host app's job,
 * which is what makes it drop into any project.
 *
 * MIT licensed. See README for how to swap in your own character.
 */

/* ── why it is built this way ────────────────────────────────────────────
   A GIF or animated WebP cannot be paused: it starts the instant it decodes
   and the browser exposes no play, pause or seek. So the resting states are
   still images and an animation is only in the DOM while it is running.

   A browser also cannot play an animation backwards, hence a second file
   holding the same frames in reverse.

   Restarting needs a new URL — re-assigning the same one does nothing, and
   cache-busting with ?t= costs a round trip every time. Each clip is fetched
   once as a Blob and every play mints a fresh object URL from it: a new image
   as far as the browser is concerned, so it always starts at frame 0, with no
   network.
   ─────────────────────────────────────────────────────────────────────── */

const HERE = new URL('.', import.meta.url);
const asset = (name) => new URL(`../assets/${name}`, HERE).href;

const DEFAULT_LABEL = 'Aino';

const DEFAULTS = {
  sleep: () => asset('dino-sleep.png'),
  wake: () => asset('dino-wake.webp'),
  back: () => asset('dino-back.webp'),
  awake: () => asset('dino-awake.png'),
  wakeMs: 8000,
  backMs: 8000,
};

const MIME = { gif: 'image/gif', webp: 'image/webp', apng: 'image/apng', png: 'image/png' };

/** A Blob served as application/octet-stream will not render in an <img>. */
function retype(blob, url) {
  if (blob.type.startsWith('image/')) return blob;
  const ext = (url.split('?')[0].split('.').pop() || '').toLowerCase();
  return MIME[ext] ? new Blob([blob], { type: MIME[ext] }) : blob;
}

/** One animation file, fetched at most once. */
class Clip {
  constructor(src) {
    this.src = src;
    this.blob = null;
    this.ready = null;
    this.url = null;
  }

  warm() {
    if (!this.ready && this.src) this.ready = this.fetchOnce();
    return this.ready || Promise.resolve();
  }

  async fetchOnce() {
    try {
      // 'default', not 'force-cache': force-cache serves a stale entry
      // regardless of freshness, so replacing the file would keep showing the
      // old animation until the cache was cleared by hand.
      const res = await fetch(this.src, { cache: 'default' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      this.blob = retype(await res.blob(), this.src);
    } catch {
      // fetch() is blocked on file://, and a missing file lands here too.
      // Cache-busted URLs still restart correctly, just less efficiently.
      this.blob = null;
    }
  }

  nextUrl() {
    this.release();
    if (this.blob) {
      this.url = URL.createObjectURL(this.blob);
      return this.url;
    }
    return `${this.src}${this.src.includes('?') ? '&' : '?'}r=${Date.now()}`;
  }

  release() {
    if (this.url) {
      URL.revokeObjectURL(this.url);
      this.url = null;
    }
  }
}

const STYLE = `
:host {
  --aino-bg: #fff;
  --aino-color: #15191a;
  --aino-border: rgba(21, 25, 26, 0.12);
  --aino-accent: #608e23;
  --aino-accent-wash: #f0f6e4;
  --aino-radius: 999px;
  --aino-sprite: 78px;
  --aino-font: inherit;

  display: inline-block;
}
:host([hidden]) { display: none; }

button {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 5px 8px 5px 18px;
  border: 1.5px solid var(--aino-border);
  border-radius: var(--aino-radius);
  background: var(--aino-bg);
  color: var(--aino-color);
  font: inherit; font-family: var(--aino-font);
  font-size: 15px; font-weight: 500; line-height: 1;
  cursor: pointer;
  transition: border-color .25s, background .25s, transform .3s cubic-bezier(.22,1,.36,1);
}
button:hover { border-color: var(--aino-accent); background: var(--aino-accent-wash); }
button:active { transform: translateY(1px); }
button:focus-visible { outline: 2px solid var(--aino-accent); outline-offset: 3px; }

.label { white-space: nowrap; }
:host([label=""]) .label, .label:empty { display: none; }
:host([label=""]) button { padding-left: 8px; }

/* The sheet is wide because the sleeping pose is wide. The standing pose only
   fills the middle of it, which is what lets him rise without the button
   changing size. */
.sprite {
  position: relative; flex: none; display: block;
  width: var(--aino-sprite);
  aspect-ratio: var(--aino-aspect, 340 / 181);
}
.layer {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  object-fit: contain;
  opacity: 0;
  transition: opacity .3s ease;
}
:host([state="asleep"])   .sleep,
:host([state="waking"])   .anim,
:host([state="sleeping"]) .anim,
:host([state="awake"])    .awake { opacity: 1; }

/* a slow breath while asleep, so he reads as alive rather than as an icon */
:host([state="asleep"]) .sleep {
  animation: breathe 4.4s ease-in-out infinite;
  transform-origin: 50% 92%;
}
@keyframes breathe { 50% { transform: scale(1.03); } }

@media (prefers-reduced-motion: reduce) {
  /* the wake is the point of the thing, so it still plays — the ambient
     loop nobody asked for does not */
  :host([state="asleep"]) .sleep { animation: none; }
  button { transition: none; }
}
`;

export class AinoButton extends HTMLElement {
  static observedAttributes = ['label', 'wake', 'back', 'sleep', 'awake', 'wake-ms', 'back-ms'];

  #open = false;
  #state = 'asleep';
  #token = 0;
  #timer = 0;

  constructor() {
    super();
    const root = this.attachShadow({ mode: 'open' });

    const style = document.createElement('style');
    style.textContent = STYLE;

    this.$button = document.createElement('button');
    this.$button.type = 'button';
    this.$button.part = 'button';

    this.$label = document.createElement('span');
    this.$label.className = 'label';
    this.$label.part = 'label';

    this.$sprite = document.createElement('span');
    this.$sprite.className = 'sprite';
    this.$sprite.part = 'sprite';
    this.$sprite.setAttribute('aria-hidden', 'true');

    this.$sleep = this.#layer('sleep');
    this.$anim = this.#layer('anim');
    this.$awake = this.#layer('awake');
    this.$sprite.append(this.$sleep, this.$anim, this.$awake);

    this.$button.append(this.$label, this.$sprite);
    root.append(style, this.$button);

    this.$button.addEventListener('click', () => this.toggle());
    // reaching for the button is the earliest honest signal of intent
    for (const evt of ['pointerenter', 'focus', 'touchstart']) {
      this.$button.addEventListener(evt, () => this.wakeClip.warm(), { passive: true });
    }
  }

  #layer(cls) {
    const img = document.createElement('img');
    img.className = `layer ${cls}`;
    img.alt = '';
    return img;
  }

  connectedCallback() {
    this.#sync();
    this.#setState('asleep');
    this.#reflect();

    // Several hundred KB per clip, and plenty of visitors never open a chat,
    // so nothing loads eagerly. Getting up is warmed when the browser goes
    // idle; lying down only once the chat has actually been opened.
    const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 2000));
    idle(() => this.wakeClip.warm(), { timeout: 4000 });
  }

  attributeChangedCallback() {
    if (this.isConnected) this.#sync();
  }

  #sync() {
    this.$label.textContent = this.getAttribute('label') ?? DEFAULT_LABEL;

    const srcs = {
      sleep: this.getAttribute('sleep') || DEFAULTS.sleep(),
      wake: this.getAttribute('wake') || DEFAULTS.wake(),
      back: this.getAttribute('back') || DEFAULTS.back(),
      awake: this.getAttribute('awake') || DEFAULTS.awake(),
    };

    if (this.$sleep.getAttribute('src') !== srcs.sleep) this.$sleep.src = srcs.sleep;
    if (this.$awake.getAttribute('src') !== srcs.awake) this.$awake.src = srcs.awake;

    if (!this.wakeClip || this.wakeClip.src !== srcs.wake) this.wakeClip = new Clip(srcs.wake);
    if (!this.backClip || this.backClip.src !== srcs.back) this.backClip = new Clip(srcs.back);

    this.wakeMs = Number(this.getAttribute('wake-ms')) || DEFAULTS.wakeMs;
    this.backMs = Number(this.getAttribute('back-ms')) || DEFAULTS.backMs;

    // the sprite's own aspect keeps the button from reflowing mid-animation
    this.$sleep.decode?.().then(() => {
      if (this.$sleep.naturalWidth) {
        this.style.setProperty('--aino-aspect',
          `${this.$sleep.naturalWidth} / ${this.$sleep.naturalHeight}`);
      }
    }).catch(() => {});
  }

  #reflect() {
    this.$button.setAttribute('aria-expanded', String(this.#open));
    const label = this.getAttribute('label') ?? DEFAULT_LABEL;
    this.$button.setAttribute('aria-label', this.#open ? `Close ${label}` : `Open ${label}`);
  }

  #setState(state) {
    this.#state = state;
    this.setAttribute('state', state);
  }

  /**
   * Play a clip, then settle onto a still.
   * Uses the load event and NOT img.decode(): decode() never settles for an
   * animated image in Chrome — it neither resolves nor rejects — so awaiting
   * it leaves the sprite stuck. load fires in single-digit milliseconds.
   */
  async #run(clip, ms, during, after) {
    const token = ++this.#token;
    clearTimeout(this.#timer);

    await clip.warm();
    if (token !== this.#token) return;

    const ok = await new Promise((resolve) => {
      const img = this.$anim;
      const finish = (v) => { img.onload = img.onerror = null; clearTimeout(guard); resolve(v); };
      const guard = setTimeout(() => finish(true), 2500);   // never stall forever
      img.onload = () => finish(true);
      img.onerror = () => finish(false);
      img.src = clip.nextUrl();
    });

    if (token !== this.#token) return;
    if (!ok) { this.#settle(after, clip); return; }          // missing file: skip to the end

    this.#setState(during);

    // These files are authored loop-once, but an animation you did not author
    // may loop forever, so this is what actually stops it.
    this.#timer = setTimeout(() => {
      if (token === this.#token) this.#settle(after, clip);
    }, ms);
  }

  #settle(state, clip) {
    this.#setState(state);
    setTimeout(() => {                                       // let the fade finish
      if (this.#state !== state) return;
      this.$anim.removeAttribute('src');
      clip?.release();
    }, 320);
  }

  #wake() {
    if (this.#state === 'awake' || this.#state === 'waking') return;
    this.backClip.warm();                                    // needed on the way out
    this.#run(this.wakeClip, this.wakeMs, 'waking', 'awake');
  }

  #sleep() {
    if (this.#state === 'asleep' || this.#state === 'sleeping') return;

    // Interrupted halfway up he never reached standing, and the lie-down clip
    // begins from standing — playing it here would snap him upright first.
    if (this.#state === 'waking') {
      this.#token++;
      clearTimeout(this.#timer);
      this.#settle('asleep', this.wakeClip);
      return;
    }
    this.#run(this.backClip, this.backMs, 'sleeping', 'asleep');
  }

  // ── public API ────────────────────────────────────────────────────────

  /** Whether the host's chat is open. Set it to drive the sprite from code. */
  get open() { return this.#open; }

  set open(value) {
    const next = Boolean(value);
    if (next === this.#open) return;
    this.#open = next;
    this.#reflect();
    next ? this.#wake() : this.#sleep();
  }

  /** 'asleep' | 'waking' | 'awake' | 'sleeping' */
  get state() { return this.#state; }

  show() { this.#set(true); }
  hide() { this.#set(false); }
  toggle() { this.#set(!this.#open); }

  #set(next) {
    if (next === this.#open) return;
    this.open = next;
    this.dispatchEvent(new CustomEvent('aino:toggle', {
      detail: { open: this.#open },
      bubbles: true,
      composed: true,
    }));
  }
}

if (!customElements.get('aino-button')) {
  customElements.define('aino-button', AinoButton);
}

export default AinoButton;
