/* Vantage platform-section console preview
   ==========================================================================
   The platform section shows the Command Center. It showed it as a still
   PNG; this plays the real one instead.

   The important decision here is what it does NOT do. It does not rebuild the
   console, and it does not reimplement the feed: it embeds `/demo/`, which is
   already a replay of real engine output and is already labelled as a
   synthetic scenario on its own chrome. A second console on the landing page
   would be a second copy of the event data, and the two would drift. There is
   one console and this points at it.

   The screenshot was captured at exactly the viewport the demo lays out at
   (1584x928), so the live version occupies the same frame at the same
   proportions and the swap is invisible except that it moves.

   Timing is the whole problem this file has to solve. The replay runs for
   about four seconds and `/demo/` starts it on its own load, so mounting the
   iframe when the section merely begins to enter the viewport means the
   assembly is over before anyone is looking at it. The fix is to mount late:
   the iframe is not created until the figure reaches the middle band of the
   viewport, and because loading it is what starts it, arriving and playing
   become the same event. No reaching into the frame to drive it.

   Progressive enhancement, in the same shape as everything else here: the
   <img> is the default markup state and stays in the DOM. The iframe is laid
   over it, and only on paths where it is worth the weight. No script, small
   screen, reduced motion, or no IntersectionObserver all keep the still.
*/
(function () {
  'use strict';

  var DEMO_W = 1584, DEMO_H = 928;
  var MIN_WIDTH = 700;      /* below this the console is illegible scaled down */

  var stage = document.getElementById('shot-stage');
  if (!stage) return;

  /* Fails closed: without an observer this would have to load the demo
     eagerly on every visit, which is a real cost for a decorative upgrade.
     The still is a perfectly good answer, so keep it. */
  if (!('IntersectionObserver' in window)) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var frame = null;

  function rescale() {
    stage.style.setProperty('--shot-scale', stage.clientWidth / DEMO_W);
  }

  function mount() {
    if (frame || stage.clientWidth < MIN_WIDTH) return;
    frame = document.createElement('iframe');
    frame.width = DEMO_W;
    frame.height = DEMO_H;
    frame.setAttribute('scrolling', 'no');
    frame.setAttribute('tabindex', '-1');
    /* The still underneath keeps its alt text, so this is the same content
       twice as far as assistive tech is concerned. `inert` also keeps the
       demo's own buttons and feed rows out of the tab order: the whole frame
       is one link to /demo/, and tabbing into a preview would be a trap. */
    frame.setAttribute('aria-hidden', 'true');
    frame.inert = true;
    frame.title = '';
    /* Deliberately not loading="lazy". This is already the lazy path, and the
       attribute would add a second deferral on top of the one that just
       decided the visitor is looking at it. */
    frame.addEventListener('load', function () {
      rescale();
      /* Revealed only once it has something to show. Until then the still is
         what covers the load, so a slow network shows a screenshot rather
         than an empty console. */
      stage.classList.add('live');
    });
    frame.src = 'demo/';
    stage.appendChild(frame);
  }

  rescale();

  if ('ResizeObserver' in window) {
    new ResizeObserver(rescale).observe(stage);
  } else {
    addEventListener('resize', rescale);
  }

  /* What has to be true is that the figure's *centre* has reached the middle
     half of the viewport, so it is genuinely being looked at.

     Two ways of expressing that were wrong and are worth recording, because
     both look correct:

     - `threshold: 0.75` on the figure itself can never be satisfied on a
       viewport shorter than the figure, so short windows would never play it.
     - a `-25%` band on the figure itself fires the instant its top edge
       pokes into the bottom of the band, which measured 5px later than the
       naive threshold it was meant to replace. Intersection is about any
       overlap, and a 609px figure overlaps a centred band while almost
       entirely below the fold.

     Observing a zero-size sentinel pinned at the figure's midpoint fixes
     both: a point either is in the band or is not, at any viewport height and
     any figure height. */
  var sentinel = document.createElement('div');
  sentinel.setAttribute('aria-hidden', 'true');
  sentinel.style.cssText = 'position:absolute;left:0;top:50%;width:1px;height:1px;pointer-events:none';
  stage.appendChild(sentinel);

  var io = new IntersectionObserver(function (entries) {
    if (!entries[0].isIntersecting) return;
    io.disconnect();
    mount();
  }, { rootMargin: '-25% 0px -25% 0px', threshold: 0 });
  io.observe(sentinel);
})();
