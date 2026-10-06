/* The entry approach, and the hero's night sky.

   One live orbit-map canvas, mounted once. It arrives as a full-screen flight
   from deep space into COSMOS 2570, then retreats into the hero's upper right
   and stays there as the hero's background, drifting, until the hero scrolls
   off screen. This is product output, not a video: the same createViz() that
   renders /visualization/, the same catalog, the same star sphere.

   The stage never moves in the DOM. It attaches at z-index 400, which is the
   black screen the flight plays on, and drops to z-index 0 at the handoff.
   That single property change IS the settle: from that moment every band
   paints over it and only the hero, made transparent by body.bg-live, lets it
   through. No re-parenting, no second context, no crossfade between two
   near-identical framings: the pixels that were the entry become the
   backdrop, without a seam.

   Contract with the loader (scripts/entry-approach.js):
     prepareApproach()          - loads the 1k texture set + catalog. No DOM.
     runApproach(assets, opts)  - mounts the stage, returns a handle, or null
                                  if the scene could not be built.

   Every exit path settles rather than blanks. A visitor who skips, or whose
   backstop fires, gets the hero with its backdrop, not a torn-down hole. */

import { Vector3 } from 'three';
import { KM_TO_UNITS, R_MEAN } from './orbits.js';
import { buildCatalog } from './catalog.js';
import { createViz } from './scene.js';

const TARGET_NORAD = 58119;             // COSMOS 2570, 460 km, inc 67.1 — real catalog identity
const R_UNITS = R_MEAN * KM_TO_UNITS;   // globe radius, the same ~6.371 the scene uses

const START_R = 64;   // deep space, where the map's own intro begins
const PARK_R = 53;    // Earth ~1/3 of the frame height: a ~260px disc at 1440x800
const PARK_X = 0.64;  // preferred parked position, -1..1 from frame centre
const PARK_Y = 0.40;  // positive is up: clear of the pill and of the headline
const PARK_GAP = 28;  // how far the glyph cloud stays off the type and the edge
/* What actually touches the headline is the LEO shell, not the limb: the glyph
   cloud reaches well beyond the globe, so clearances are measured against it. */
const CLOUD_UNITS = 7.6;

const FADE_IN_MS = 200;   // the black screen arriving
const FLY_MS = 1600;      // the flight
const RETREAT_MS = 1200;  // shrink and slide into the corner
const SKIP_MS = 250;      // the same retreat, hurried, on any input
const BACKSTOP_MS = 4000; // armed at attach, never cleared: the page is always back

/* Two independent rates, and keeping them independent is the point.

   TIME_RATE is the DATA clock, and it has a ceiling: the orbit map's own Speed
   slider is the same multiplier, ships at 25 and stops at 100, so 100 is the
   fastest this can run and still be something the product itself does. At real
   time rate a LEO glyph moves under 1 px/s, which is a photograph.

   SKY_DRIFT is the CAMERA, and it has no ceiling, because a camera move
   asserts nothing about the data. It is what makes the star field move at all:
   the sky is a fixed sphere and the camera is inertial, so without this the
   stars are nailed in place no matter how fast the clock runs. Driven by real
   elapsed time, never by simMs, so changing one rate never silently changes
   the other. It turns against the planet's spin so the ground and the stars
   separate instead of cancelling.

   At 1440x800 this is ~7 px/s for the stars, ~17 px/s for the satellites and
   ~1.7 px/s across the disc: alive, without competing with the headline. */
const TIME_RATE = 100;
const SKY_DRIFT = -0.35 * (Math.PI / 180) / 1000; // radians per real millisecond
const FRAME_MS = 32; // ~30fps once parked; the flight itself runs uncapped

function ease3(t) { return 1 - Math.pow(1 - t, 3); }

function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

export async function prepareApproach() {
  /* The 1k earth is enough: the approach never gets close enough to the
     surface to want the 4k sheet, and it is a quarter of the bytes. The
     starfield is small already, and it is the whole point of the settled
     state, so it is not optional. */
  const [earth, night] = await Promise.all([
    loadImage('visualization/img/earth-blue-marble-1k.webp'),
    loadImage('visualization/img/night-sky.webp'),
  ]);
  if (!earth) throw new Error('earth texture failed');
  const objects = buildCatalog();
  const target = objects.findIndex((o) => o.id === TARGET_NORAD);
  if (target < 0) throw new Error('target not in catalog');
  return { earth, night, objects, target };
}

export function runApproach(assets, opts) {
  const o = opts || {};
  const theme = o.theme || 'site';
  const wantFlight = !!o.flight;
  const still = !!o.still; // reduced motion: one real frame, then nothing
  const hero = document.querySelector('.hero');
  const body = document.body;

  const stage = document.createElement('div');
  stage.className = 'approach-stage approach-' + theme;
  stage.setAttribute('aria-hidden', 'true');

  const canvas = document.createElement('canvas');
  stage.appendChild(canvas);

  /* Caption and skip hint belong to the flight only, and leave with it. */
  let cap = null;
  let skipHint = null;
  if (wantFlight) {
    cap = document.createElement('div');
    cap.className = 'approach-cap';
    cap.innerHTML =
      '<div>COSMOS 2570 · NORAD 58119 · INC 67.1°</div>' +
      '<div class="sub">Synthetic catalog · assessments simulated</div>';
    stage.appendChild(cap);

    skipHint = document.createElement('div');
    skipHint.className = 'approach-skip';
    skipHint.textContent = 'press any key to skip';
    stage.appendChild(skipHint);

    if (theme === 'defense') {
      const dtg = document.createElement('div');
      dtg.className = 'approach-dtg';
      const d = new Date();
      const p = (n) => String(n).padStart(2, '0');
      const MON = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
      dtg.textContent = p(d.getUTCDate()) + p(d.getUTCHours()) + p(d.getUTCMinutes()) + 'Z ' +
        MON[d.getUTCMonth()] + ' ' + p(d.getUTCFullYear() % 100);
      stage.appendChild(dtg);
    }
  }

  /* The parked globe is a door, not a picture. A circle over the disc and the
     label under it both open the orbit map, and hovering either turns the
     caveat into the invitation.

     This is its own layer, above the page rather than inside the stage. The
     stage has to stay BEHIND the hero's content, which is the whole settle,
     and anything buried under `.hero .wrap` can never be clicked or hovered:
     the wrap is a full-width block and wins hit-testing over the globe even
     where it is completely transparent. So the canvas stays at z-index 0 and
     the affordance rides at 2, over the hero and under the pill.

     The cost of being on top is that it would also cover the console frame
     once the page scrolls, so the layer is live only at the top of the page,
     which is exactly where the globe is unobstructed and labelled anyway.

     Mouse affordance only, hence aria-hidden and tabindex -1: this layer is
     appended at the end of <body>, so a focusable link here would land last in
     the tab order while appearing at the top of the page. The nav and the
     footer already carry real, correctly ordered orbit-map links.

     Order matters: the circle must precede the label for the CSS sibling
     selector that swaps the text. */
  const ui = document.createElement('div');
  ui.className = 'approach-ui';

  const hit = document.createElement('a');
  hit.className = 'approach-hit';
  hit.href = 'visualization/';
  hit.setAttribute('aria-hidden', 'true');
  hit.setAttribute('tabindex', '-1');
  ui.appendChild(hit);

  /* The catalog is deterministic-synthetic, and the design system requires the
     map's standing caveat wherever the map appears. The flight says it in its
     caption; the parked backdrop has to say it for itself, so this rides just
     under the globe and appears only once the stage has settled. The two spans
     are overlaid rather than swapped in place, so nothing reflows on hover. */
  const note = document.createElement('a');
  note.className = 'approach-note';
  note.href = 'visualization/';
  note.setAttribute('aria-hidden', 'true');
  note.setAttribute('tabindex', '-1');
  note.innerHTML =
    '<span class="rest">Orbit map · synthetic catalog</span>' +
    '<span class="open">Open orbit map ↗</span>';
  ui.appendChild(note);

  document.body.appendChild(stage);
  document.body.appendChild(ui);

  let viz;
  try {
    viz = createViz({
      canvas,
      textures: { earth: assets.earth, night: assets.night },
      objects: assets.objects,
      sensorSites: [],
    });
  } catch (_) {
    stage.remove();
    return null;
  }

  /* Scenery, not an instrument: OrbitControls binds to the canvas, so without
     this a visitor could drag the hero background and its wheel handler could
     eat page scroll. controls.update() still runs the lookAt we depend on. */
  viz.controls.enabled = false;
  /* Inertial camera: the stars hold still and the Earth turns under them,
     which is both the correct astronomy and the more legible image. With
     follow on, the camera co-rotates and the ground is what freezes. */
  viz.toggles.follow(false);
  viz.setReveal(1);

  const listeners = [];
  const timers = [];
  const on = (t, ev, fn, opt) => { t.addEventListener(ev, fn, opt); listeners.push([t, ev, fn, opt]); };
  const later = (fn, ms) => { timers.push(setTimeout(fn, ms)); };

  /* The parked position is a preference, not a promise. The globe's size
     scales with the viewport's HEIGHT (it is a slice of the vertical field of
     view) while the headline's width scales with WIDTH, so a fixed pair of
     constants cannot clear the type at every window: at 1440x800 the raw
     preference puts the glyph cloud about 48px into "And prove every call."
     So the clearances are solved against the real measured layout, and the
     preference is only where the globe goes when nothing is in the way. */
  let parkX = PARK_X;
  let parkY = PARK_Y;

  const radiusPx = (units) => {
    const tanV = Math.tan((viz.camera.fov * Math.PI / 180) / 2);
    return (stage.clientHeight / 2) * (Math.tan(Math.asin(Math.min(1, units / PARK_R))) / tanV);
  };

  function solveFraming() {
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    if (!w || !h) return;
    const cloud = radiusPx(CLOUD_UNITS);
    const disc = radiusPx(R_UNITS);

    /* Two different radii, because two different things are at stake. The
       viewport edge must clear the whole GLYPH CLOUD: a halo sliced by the
       window is a mistake. The headline only needs to clear the DISC: the
       hero's content paints above the stage, so white type over the sparse
       outer glyphs stays perfectly legible, while type over the lit body of
       the Earth would not.

       Ranges over the h1's line spans, not the h1 itself: its children are
       display:block, so a Range across the whole element measures the centred
       block (910px here) instead of the glyphs inside it (690px), and a
       clearance solved against that phantom pushes the globe 110px further
       right than it needs to go, or gives up and clamps. */
    let x = PARK_X;
    const h1 = document.querySelector('.hero h1');
    if (h1) {
      const lines = h1.children.length ? h1.children : [h1];
      const range = document.createRange();
      let right = 0;
      for (let i = 0; i < lines.length; i++) {
        range.selectNodeContents(lines[i]);
        right = Math.max(right, range.getBoundingClientRect().right);
      }
      if (right > 0) x = Math.max(x, ((right + PARK_GAP + disc) / (w / 2)) - 1);
    }
    /* Staying on screen wins: at narrow windows the type is simply too wide
       for both to hold, and a clipped globe is the worse failure. */
    parkX = Math.min(x, ((w - PARK_GAP - cloud) / (w / 2)) - 1);

    const pill = document.querySelector('.nav-pill');
    const below = (pill ? pill.getBoundingClientRect().bottom : 74) + PARK_GAP + cloud;
    parkY = Math.max(0, Math.min(PARK_Y, 1 - (below / (h / 2))));
  }

  /* The hit circle and the caveat line ride the solved position, so the target
     is exactly the disc a visitor can see and the label sits under it. The
     label is right-aligned to the disc's own right edge: left-aligned it runs
     into the lede's last line. */
  function placeGlobeUi() {
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    if (!w || !h) return;
    const rpx = radiusPx(R_UNITS);
    const cx = (w / 2) * (1 + parkX);
    const cy = (h / 2) * (1 - parkY);
    hit.style.left = Math.round(cx - rpx) + 'px';
    hit.style.top = Math.round(cy - rpx) + 'px';
    hit.style.width = Math.round(rpx * 2) + 'px';
    hit.style.height = Math.round(rpx * 2) + 'px';
    note.style.right = Math.round(w - (cx + rpx)) + 'px';
    note.style.top = Math.round(cy + rpx + 18) + 'px';
  }

  /* A resize moves the label and the hit circle immediately, but the camera is
     only re-framed by a frame, and there is not always one coming: the loop is
     stopped while the hero is off screen or the tab is hidden, and under
     reduced motion there is no loop at all. So a resize re-frames and redraws
     itself once parked, or the globe and its own hit area drift apart. */
  let ready = false;
  const size = () => {
    viz.resize(stage.clientWidth, stage.clientHeight);
    solveFraming();
    placeGlobeUi();
    if (ready && phase === 'park') {
      curX = parkX;
      curY = parkY;
      setRadius(curR);
      aim(curX, curY);
      viz.render();
    }
  };
  on(window, 'resize', size);
  size();

  /* The affordance is live only once the globe has actually arrived and only
     while the page is at the top. Two reasons, one rule: scrolled, the hero's
     own content slides under the pinned globe and would cut the label in half,
     and this layer sits above the console frame and must not take the clicks
     that belong to it. Backdrop the rest of the time. */
  let uiOn = false;
  const syncUi = () => {
    const want = phase === 'park' && scrollY < 24;
    if (want === uiOn) return;
    uiOn = want;
    ui.classList.toggle('live', want);
  };
  on(window, 'scroll', syncUi, { passive: true });

  /* ---- framing ----------------------------------------------------------
     The globe is put in its corner by shifting the LENS, not by turning the
     camera. The camera always looks straight at Earth's centre.

     Turning the camera is the obvious approach and it is a trap. Solving the
     off-centre look direction is a fixed-point iteration on a screen basis
     built from the world up axis, and that iteration comes apart when the
     look direction approaches the up axis: the basis flips from pass to pass
     and the solve converges somewhere wrong. The flight ends wherever
     COSMOS 2570 happens to be in its orbit, and at 67 degrees of inclination
     the camera regularly lands at 60 degrees of latitude or more, so the globe
     used to arrive in the right place on some visits and not others. It cost
     a screenshot that looked fine and a measurement that did not.

     An off-axis frustum has none of that geometry in it. `setViewOffset`
     renders a shifted window of a larger virtual frame, which is exactly what
     a shift lens does: ask for (0.64, 0.39) and Earth's centre projects to
     exactly (0.64, 0.39), at any latitude, at any aspect, with no iteration
     and nothing to converge. Verified exact at the latitude that broke the
     old solve. */
  const UP = new Vector3(0, 1, 0); // the sky drift's axis; the framing needs none

  function aim(sx, sy) {
    const cam = viz.camera;
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    viz.controls.target.set(0, 0, 0);
    if (!w || !h) return;
    if (sx === 0 && sy === 0) cam.clearViewOffset();
    else cam.setViewOffset(w, h, -sx * w / 2, sy * h / 2, w, h);
  }

  function setRadius(r) {
    const p = viz.camera.position;
    p.multiplyScalar(r / (p.length() || 1));
  }

  /* ---- state ------------------------------------------------------------ */
  const tmp = [0, 0, 0];
  let io = null;
  let phase = wantFlight ? 'fly' : 'park';
  let settled = !wantFlight;
  let dead = false;
  let paused = false;
  let heroOn = true;
  let tabOn = document.visibilityState === 'visible';
  let rafId = 0;
  let virt = 0; // dev-handle clock only; the live loop uses rAF timestamps
  let simMs = Date.now();
  let last = 0;
  let lastDraw = 0;
  let t0 = 0; // phase start, in the same clock as `now`
  let retreatMs = RETREAT_MS;
  let curR = wantFlight ? START_R : PARK_R;
  let curX = wantFlight ? 0 : parkX;
  let curY = wantFlight ? 0 : parkY;
  let fromR = curR;
  let fromX = curX;
  let fromY = curY;

  /* The handoff. Idempotent, and every exit path runs through it. */
  function settle() {
    if (settled || dead) return;
    settled = true;
    /* Both of these in one synchronous block, or the hero flashes its opaque
       dark band between the stage dropping and the hero going transparent. */
    stage.classList.add('settled');
    body.classList.add('bg-live');
    body.classList.remove('approach-veiled');
    if (cap) cap.classList.add('gone');
    if (skipHint) skipHint.classList.add('gone');
  }

  /* Retreat to the parked framing from wherever the camera is now. 0 snaps
     (the backstop), SKIP_MS hurries it (any input), RETREAT_MS is the
     flight's own ending. */
  function retreat(ms, now) {
    if (dead || phase === 'park') return;
    fromR = curR; fromX = curX; fromY = curY;
    retreatMs = ms;
    t0 = now;
    phase = ms > 0 ? 'retreat' : 'park';
    if (phase === 'park') { curR = PARK_R; curX = parkX; curY = parkY; }
    settle();
  }

  function tick(now) {
    if (dead) return;
    if (phase === 'park' && now - lastDraw < FRAME_MS) return;
    if (!last) last = now;
    const dt = Math.min(now - last, 250);
    last = now;
    lastDraw = now;

    simMs += dt * TIME_RATE;
    viz.setTime(simMs);

    if (phase === 'fly') {
      if (!t0) { t0 = now; stage.classList.add('show'); }
      /* The camera rides the target's own radial line, so looking at Earth's
         centre keeps the object dead centre for the whole approach: no
         selection, no tracking pivot, and controls.target stays ours. */
      const t = Math.min(1, (now - t0 - FADE_IN_MS * 0.5) / FLY_MS);
      viz.objectScenePos(assets.target, tmp);
      const len = Math.hypot(tmp[0], tmp[1], tmp[2]) || 1;
      const rEnd = len + 0.06; // ~60 km off the glyph, Earth filling the frame
      curR = START_R + (rEnd - START_R) * ease3(Math.max(0, t));
      viz.camera.position.set(tmp[0] / len * curR, tmp[1] / len * curR, tmp[2] / len * curR);
      aim(0, 0);
      viz.render();
      if (t >= 1) retreat(RETREAT_MS, now);
      return;
    }

    if (phase === 'retreat') {
      const k = ease3(Math.min(1, Math.max(0, (now - t0) / retreatMs)));
      curR = fromR + (PARK_R - fromR) * k;
      curX = fromX + (parkX - fromX) * k;
      curY = fromY + (parkY - fromY) * k;
      if (k >= 1) phase = 'park';
    }

    /* The sky sweep. Rotating the camera about the planet's axis is what moves
       the star field; the globe does not move with it, because aim() re-solves
       the look target every frame and holds it in its corner. Only what passes
       behind it changes. Real ms, so this is deaf to TIME_RATE. */
    viz.camera.position.applyAxisAngle(UP, SKY_DRIFT * dt);

    setRadius(curR);
    aim(curX, curY);
    viz.render();
    syncUi(); // cheap: it early-returns on every frame but the one that changes
  }

  const loop = (now) => {
    if (dead || (paused && settled)) { rafId = 0; return; }
    rafId = requestAnimationFrame(loop);
    tick(now);
  };

  function setPaused(v) {
    if (dead || paused === v) return;
    paused = v;
    if (v) return;
    last = 0;
    if (!rafId && !still) rafId = requestAnimationFrame(loop);
  }
  const syncPaused = () => setPaused(!(heroOn && tabOn));

  function destroy() {
    if (dead) return;
    dead = true;
    cancelAnimationFrame(rafId);
    rafId = 0;
    listeners.forEach(([t, ev, fn, opt]) => t.removeEventListener(ev, fn, opt));
    timers.forEach(clearTimeout);
    if (io) io.disconnect();
    body.classList.remove('approach-veiled', 'bg-live');
    stage.remove();
    ui.remove();
    try {
      const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
      const lose = gl && gl.getExtension('WEBGL_lose_context');
      if (lose) lose.loseContext();
    } catch (_) { /* best effort */ }
    if (window.__approach === handle) delete window.__approach;
  }

  /* ---- lifecycle --------------------------------------------------------
     Warm the pipeline before anything is timed. The first render of a 15k
     catalog compiles its shader programs, and that cost lands wherever the
     first frame is: paid inside the flight, it makes the flight begin already
     half way through. So the true t=0 frame is drawn here, while the stage is
     still at opacity 0, and the flight clock starts on an already-compiled
     pipeline. */
  try {
    if (wantFlight) {
      viz.objectScenePos(assets.target, tmp);
      const len = Math.hypot(tmp[0], tmp[1], tmp[2]) || 1;
      viz.camera.position.set(
        tmp[0] / len * START_R, tmp[1] / len * START_R, tmp[2] / len * START_R,
      );
      aim(0, 0);
    } else {
      setRadius(PARK_R);
      aim(parkX, parkY);
    }
    viz.setTime(simMs);
    viz.render();
  } catch (_) {
    /* Same contract as a createViz failure: leave no trace and let the page
       be exactly the page. The warm frame is inside the guard because it is
       the first code that touches the catalog, and a bad catalog throws here
       rather than in the constructor. */
    listeners.forEach(([t, ev, fn, opt]) => t.removeEventListener(ev, fn, opt));
    stage.remove();
    ui.remove();
    return null;
  }

  if (wantFlight) {
    /* The hold. Applied only once the stage is fully opaque, so the hero
       content is never seen disappearing, and released by settle() on every
       path. The backstop below is its hard guarantee. */
    later(() => { if (!settled && !dead) body.classList.add('approach-veiled'); }, FADE_IN_MS);
    later(() => retreat(0, performance.now()), BACKSTOP_MS);

    ['wheel', 'keydown', 'pointerdown', 'touchstart'].forEach((ev) =>
      on(window, ev, () => retreat(SKIP_MS, performance.now()), { passive: true }));
  } else {
    /* No flight: the warm frame above is already the parked framing, so the
       hero never flashes an empty canvas on the way in. */
    stage.classList.add('show', 'settled');
    body.classList.add('bg-live');
  }

  /* Pinned to the viewport for as long as any part of the hero is on screen,
     then simply covered: the bands below are opaque, so nothing needs to fade.
     Fading would reveal the body's light ground through the transparent hero. */
  if (hero && 'IntersectionObserver' in window) {
    io = new IntersectionObserver((entries) => {
      heroOn = entries.some((e) => e.isIntersecting);
      syncPaused();
    }, { threshold: 0 });
    io.observe(hero);
  }

  /* Nobody is watching a hidden tab: uncover instantly, hold nothing, and
     stop drawing. An IntersectionObserver does not re-fire on the way back,
     so the tab's own state is tracked separately from the hero's. */
  on(document, 'visibilitychange', () => {
    tabOn = document.visibilityState === 'visible';
    if (!tabOn) retreat(0, performance.now());
    syncPaused();
  });

  /* Reduced motion keeps the composition and loses the animation: the warm
     frame above is the only frame such a visitor ever gets. The affordance is
     not motion, so it still arrives, which is why syncUi() runs here and not
     only from the loop. */
  if (!still) rafId = requestAnimationFrame(loop);
  syncUi();
  ready = true; // from here a resize may re-frame and redraw on its own

  /* Dev handle, in the spirit of main.js's window.__viz: the only way to drive
     this under browser automation, where the tab reports hidden and rAF stalls. */
  const handle = {
    el: stage,
    canvas,
    viz,
    note,
    get phase() { return phase; },
    get settled() { return settled; },
    get paused() { return paused; },
    get framing() { return { r: curR, x: curX, y: curY }; },
    /* Virtual clock, so a walk through the timeline is deterministic even
       though each forced frame costs real milliseconds to draw. */
    step(ms) { virt = (virt || performance.now()) + (ms || 16); tick(virt); },
    parkNow() {
      phase = 'park';
      curR = PARK_R; curX = parkX; curY = parkY;
      settle();
      size();
      setRadius(PARK_R);
      aim(parkX, parkY);
      viz.setTime(simMs);
      viz.render();
      syncUi();
    },
    settle,
    setPaused,
    destroy,
  };
  window.__approach = handle;
  return handle;
}
