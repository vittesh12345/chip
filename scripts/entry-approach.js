/* Entry-approach loader: decides what the hero's orbit-map canvas is allowed
   to be, and only then pays for it. The hero has already painted; this module
   is additive or absent, never blocking.

   Two gates, not one.

   The BACKDROP gate is hardware and preference only: wide enough viewport,
   WebGL, no save-data or 2g. Everything that passes it gets the parked globe
   in the hero's upper right, on every visit, because the backdrop is part of
   the hero's design rather than a first-visit reward. A late backdrop costs
   nothing, so it waits for the hero to actually be on screen and has no time
   budget at all.

   The FLIGHT gate is the time-critical one, and it is the old gauntlet: once
   per session, and the flag is set only when the flight is SEEN; no reduced
   motion; tab visible; page at the top; ready inside 2500ms; no input yet.
   Miss any of it and the backdrop still arrives, without the flight. */
(() => {
  'use strict';
  const FLAG = 'vantage-approach';
  const BUDGET_MS = 2500;

  /* --- backdrop gate ---------------------------------------------------- */
  const conn = navigator.connection;
  if (conn && (conn.saveData || /(^|-)2g$/.test(conn.effectiveType || ''))) return;
  if (innerWidth < 700) return;
  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) return;
  const hero = document.querySelector('.hero');
  if (!hero) return;

  /* Reduced motion keeps the composition and loses the animation: the parked
     globe is rendered once and never again, and the flight never runs. */
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* --- flight gate ------------------------------------------------------- */
  let flagged = 'done';
  try { flagged = sessionStorage.getItem(FLAG) || ''; } catch (_) { /* storage off = play once per load */ }
  let wantFlight = flagged !== 'done' && !still &&
    document.visibilityState === 'visible' && scrollY < 8;

  let aborted = false;
  const abort = () => { aborted = true; };
  const evs = ['wheel', 'keydown', 'pointerdown', 'touchstart'];
  if (wantFlight) evs.forEach((ev) => addEventListener(ev, abort, { passive: true, once: true }));
  const unarm = () => evs.forEach((ev) => removeEventListener(ev, abort));

  let pending = null;
  const load = () => {
    if (!pending) {
      pending = import('../visualization/js/approach.js')
        .then((m) => m.prepareApproach().then((assets) => ({ m, assets })))
        .catch(() => null);
    }
    return pending;
  };

  const run = (hit) => {
    unarm();
    if (!hit) return;
    const flight = wantFlight && !aborted &&
      scrollY < 8 && document.visibilityState === 'visible';
    /* Set only when the flight is actually about to be seen, so a timed-out
       or abandoned first visit can still play warm later in the session. */
    if (flight) { try { sessionStorage.setItem(FLAG, 'done'); } catch (_) { /* best effort */ } }
    hit.m.runApproach(hit.assets, {
      theme: document.body.dataset.approachTheme || 'site',
      flight,
      still,
    });
  };

  /* The backdrop waits until the hero is worth paying for; a deep link to a
     section far down the page never builds a scene nobody will look at. */
  const whenHeroSeen = () => {
    if (!('IntersectionObserver' in window)) { load().then(run); return; }
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      io.disconnect();
      load().then(run);
    }, { threshold: 0 });
    io.observe(hero);
  };

  if (!wantFlight) { whenHeroSeen(); return; }

  /* The flight, and only the flight, races a budget: it has to land before a
     visitor has moved on. Expiry drops it and falls back to the backdrop. */
  const budget = new Promise((r) => setTimeout(() => r(null), BUDGET_MS));
  Promise.race([budget, load()]).then((hit) => {
    if (hit) { run(hit); return; }
    wantFlight = false;
    unarm();
    whenHeroSeen();
  });
})();
