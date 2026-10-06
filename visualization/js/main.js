/* Entry point: loads the imagery, builds the catalog, stands the scene up,
   wires the HUD and runs the clock. Fully static — no backend, no keys. */

import { buildCatalog } from './catalog.js';
import { createViz } from './scene.js';
import { initUI } from './ui.js';

const SENSOR_SITES = [
  { name: 'South Island NZ', lat: -43.9, lon: 170.45, beam: 'star' },
  { name: 'West Texas US', lat: 31.95, lon: -102.35, beam: 'fan' },
  { name: 'Guanacaste CR', lat: 10.62, lon: -85.51, beam: 'cone' },
  { name: 'Interior Alaska US', lat: 65.12, lon: -147.47, beam: 'cone' },
  { name: 'Azores PT', lat: 37.78, lon: -25.5, beam: 'fan' },
  { name: 'Great Sandy AU', lat: -19.9, lon: 120.62, beam: 'fan' },
  { name: 'Hokkaido JP', lat: 43.52, lon: 143.0, beam: 'star' },
];

const bootLine = document.getElementById('boot-line');

function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null); // the scene tolerates a missing layer
    img.src = src;
  });
}

/* The two sky textures were 2.3MB of a 3.2MB page, which is most of what a
   visitor waits for. Both are WebP now, with the originals kept as a fallback:

     earth   1428KB jpg -> 648KB webp q82   (40.7dB PSNR, no visible change)
     night    883KB png -> 143KB webp lossless

   The starfield is lossless because it is almost entirely flat black with
   small bright points, which lossless compresses to a sixth of the PNG.
   Encoding it lossily made the file *larger* while smearing the stars.

   Any browser that can run WebGL can decode WebP, so the fallback should never
   fire. It costs one line and the scene already tolerates a null layer. */
async function loadTexture(webp, original) {
  return (await loadImage(webp)) || (await loadImage(original));
}

async function boot() {
  bootLine.textContent = 'Loading imagery…';
  const [earthImg, nightImg] = await Promise.all([
    loadTexture('img/earth-blue-marble.webp', 'img/earth-blue-marble.jpg'),
    loadTexture('img/night-sky.webp', 'img/night-sky.png'),
  ]);

  bootLine.textContent = 'Generating resident-object catalog…';
  await new Promise((r) => setTimeout(r, 0));
  const objects = buildCatalog();

  bootLine.textContent = 'Standing up the scene…';
  const canvas = document.getElementById('globe');
  const viz = createViz({
    canvas,
    textures: { earth: earthImg, night: nightImg },
    objects,
    sensorSites: SENSOR_SITES,
  });

  /* ---- time engine: the clock advances at the Speed slider's multiplier ---- */
  const time = {
    multiplier: 100,
    simMs: Date.now(),
    setMultiplier(m) { this.multiplier = m; },
    update(dtMs) { this.simMs += dtMs * this.multiplier; },
  };

  const ui = initUI({ viz, objects, time, sensorSites: SENSOR_SITES });
  window.__viz = viz; // console handle, also used by the harness
  window.__time = time;

  const resize = () => viz.resize(window.innerWidth, window.innerHeight);
  window.addEventListener('resize', resize);
  resize();

  // The catalog streams in over the first seconds, the way a live feed pages
  // object states down to the client.
  viz.setReveal(0);
  let revealT = 0;

  /* ---- intro pull-in ---- */
  const introFrom = viz.camera.position.clone().normalize().multiplyScalar(64);
  const introTo = viz.camera.position.clone();
  let introT = 0;
  viz.camera.position.copy(introFrom);

  let last = performance.now();
  let firstFrame = true;
  function loop(now) {
    const dt = Math.min(now - last, 250);
    last = now;

    if (introT < 1) {
      // a selection during the pull-in takes the camera over — stop animating
      if (viz.selected >= 0) introT = 1;
      else {
        introT = Math.min(1, introT + dt / 2400);
        const k = 1 - Math.pow(1 - introT, 3);
        viz.camera.position.lerpVectors(introFrom, introTo, k);
      }
    }
    if (revealT < 1) {
      revealT = Math.min(1, revealT + dt / 3400);
      viz.setReveal(revealT * revealT * (3 - 2 * revealT));
    }

    time.update(dt);
    viz.setTime(time.simMs);
    viz.render();
    ui.tick(now);

    if (firstFrame) {
      firstFrame = false;
      document.getElementById('boot').classList.add('gone');
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}

boot().catch((err) => {
  bootLine.textContent = `Failed to start: ${err.message}`;
  console.error(err);
});
