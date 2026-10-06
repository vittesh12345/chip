/* Vantage site shell behavior: mobile navigation and scroll reveal.
   Loaded with `defer` on every page. No dependencies. */
(function () {
  'use strict';

  var hdr = document.getElementById('hdr');
  var navToggle = document.querySelector('.nav-toggle');
  var navLinks = document.getElementById('primary-nav');

  /* --- Mobile menu -------------------------------------------------------
     The outside-click and Escape handlers are bound only while the menu is
     open, so a page-wide listener never runs for a menu that is not there. */
  if (hdr && navToggle && navLinks) {
    var onOutsideClick = function (e) {
      if (!hdr.contains(e.target)) closeMenu();
    };
    var onKeydown = function (e) {
      if (e.key === 'Escape') { closeMenu(); navToggle.focus(); }
    };
    var setMenu = function (open) {
      hdr.classList.toggle('menu-open', open);
      navToggle.setAttribute('aria-expanded', String(open));
      navToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
      var bind = open ? 'addEventListener' : 'removeEventListener';
      document[bind]('click', onOutsideClick);
      document[bind]('keydown', onKeydown);
    };
    var closeMenu = function () {
      if (hdr.classList.contains('menu-open')) setMenu(false);
    };

    navToggle.addEventListener('click', function () {
      setMenu(!hdr.classList.contains('menu-open'));
    });
    navLinks.addEventListener('click', function (e) {
      if (e.target.closest('a')) closeMenu();
    });
    addEventListener('resize', function () {
      if (innerWidth > 1040) closeMenu();
    });

    /* Header state: passive listener, at most one class write per frame. */
    var ticking = false;
    addEventListener('scroll', function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        hdr.classList.toggle('scrolled', scrollY > 10);
        ticking = false;
      });
    }, { passive: true });
  }

  /* --- Section position in the nav ---------------------------------------
     site.css already styled a current-nav state that nothing ever set, so the
     nav could tell you where you could go but never where you were. This
     writes it.

     Placed BEFORE the reveal block on purpose: that block ends in an early
     return from this IIFE, so anything after it dies on a page that has a nav
     and no .reveal elements.

     `location`, not `page`: `page` means "the current page within a set of
     pages" and the contact page already uses it correctly on its own link.
     Reusing it for an in-page section would make that marker ambiguous.

     Only same-document hash links are managed, so on /contact/ (whose hrefs
     are ../#platform) nothing resolves, the block disables itself, and the
     hand-written aria-current="page" there is never touched.

     No reduced-motion branch: nothing here animates. The colour change rides
     the existing transition on .navlinks a, and scroll-behavior is already
     gated below. Recorded because this file's convention is to say why
     something is absent.

     Fails closed without IntersectionObserver: unlike the reveal below, which
     must fail OPEN because its absence hides content, an absent position
     indicator costs a visitor nothing. */
  (function () {
    if (!navLinks || !('IntersectionObserver' in window)) return;

    var managed = [];
    navLinks.querySelectorAll('a[href^="#"]').forEach(function (link) {
      var id = link.getAttribute('href').slice(1);
      var section = id && document.getElementById(id);
      if (section) managed.push({ link: link, section: section, id: id });
    });
    if (!managed.length) return;

    /* Derived from the token rather than hard-coded, so a change to the fixed
       header height moves the band with it. */
    var offset = parseInt(getComputedStyle(document.documentElement)
      .getPropertyValue('--anchor-offset'), 10) || 108;

    var order = managed.map(function (m) { return m.id; });
    var visible = [];
    var current = null;

    var apply = function (id) {
      if (id === current) return;
      current = id;
      managed.forEach(function (m) {
        if (m.id === id) m.link.setAttribute('aria-current', 'location');
        else m.link.removeAttribute('aria-current');
      });
    };

    /* A top band just under the header, not "whichever section is most
       visible": these sections differ enormously in height, so an area test
       would keep the tallest one lit most of the way down the page. */
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var id = entry.target.id;
        var at = visible.indexOf(id);
        if (entry.isIntersecting) { if (at === -1) visible.push(id); }
        else if (at !== -1) visible.splice(at, 1);
      });
      /* The band can hold several sections or none. Take the last in document
         order; when it empties, hold whatever was last current. */
      if (!visible.length) return;
      visible.sort(function (a, b) { return order.indexOf(a) - order.indexOf(b); });
      apply(visible[visible.length - 1]);
    }, { rootMargin: (-offset) + 'px 0px -70% 0px', threshold: 0 });

    managed.forEach(function (m) { io.observe(m.section); });

    /* The hero owns no nav link, so "nothing current" is a real state at the
       top of the page rather than a gap to paper over. */
    addEventListener('scroll', function () {
      if (scrollY < 40) { visible.length = 0; apply(null); }
    }, { passive: true });
  })();

  /* --- UTC clock ----------------------------------------------------------
     Real system UTC in the pill: the only time displayed anywhere on the
     marketing pages, and it is never fabricated. The interval runs only
     while the tab is visible; a hidden tab's clock costs nothing and shows
     to nobody. Not gated on reduced motion: a clock is information. */
  (function () {
    var el = document.getElementById('utc');
    if (!el) return;
    var pad = function (n) { return String(n).padStart(2, '0'); };
    var render = function () {
      var d = new Date();
      el.textContent = pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes()) + ':' + pad(d.getUTCSeconds()) + 'Z';
      el.setAttribute('datetime', d.toISOString());
    };
    var timer = null;
    var start = function () { if (timer === null) { render(); timer = setInterval(render, 1000); } };
    var stop = function () { if (timer !== null) { clearInterval(timer); timer = null; } };
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') start(); else stop();
    });
    if (document.visibilityState === 'visible') start();
  })();

  /* --- Scrollspy rail (wide viewports) ------------------------------------
     S/0x designators in the left margin: the same top-band logic as the nav
     scrollspy, pointed at every top-level section instead of only the linked
     ones, so the page reads like a numbered tracking readout. Presentational
     only (the nav announces position), so the whole rail is aria-hidden, and
     it also fails closed without IntersectionObserver. The rail takes the
     tone of the current section so it never dissolves into a band. */
  (function () {
    if (!('IntersectionObserver' in window)) return;
    var sections = document.querySelectorAll('main > section');
    if (sections.length < 3) return;

    var rail = document.createElement('div');
    rail.className = 'rail-spy';
    rail.setAttribute('aria-hidden', 'true');
    var marks = [];
    sections.forEach(function (sec, i) {
      var s = document.createElement('span');
      s.textContent = 'S/' + String(i + 1).padStart(2, '0');
      rail.appendChild(s);
      marks.push({ el: s, sec: sec });
    });
    document.body.appendChild(rail);

    var offset = parseInt(getComputedStyle(document.documentElement)
      .getPropertyValue('--anchor-offset'), 10) || 108;
    var visible = [];
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var at = visible.indexOf(entry.target);
        if (entry.isIntersecting) { if (at === -1) visible.push(entry.target); }
        else if (at !== -1) visible.splice(at, 1);
      });
      if (!visible.length) return;
      var cur = visible.slice().sort(function (a, b) {
        return Array.prototype.indexOf.call(sections, a) - Array.prototype.indexOf.call(sections, b);
      }).pop();
      marks.forEach(function (m) { m.el.classList.toggle('cur', m.sec === cur); });
      rail.classList.toggle('on-dark', cur.classList.contains('tone-dark'));
    }, { rootMargin: (-offset) + 'px 0px -60% 0px', threshold: 0 });

    sections.forEach(function (sec) { io.observe(sec); });
  })();

  /* --- Figures resolve on entry -------------------------------------------
     Headline figures arrive as an unresolved readout and lock on, digit by
     digit, left to right: `-.---` becomes `0.963`.

     Deliberately not a count-up. A count-up renders a run of *wrong values*
     on the way to the right one, and this site's whole argument is that its
     numbers are checkable and sealed. A masked readout asserts nothing until
     it asserts the truth, and a half-resolved `0.9--` is legibly a readout
     mid-lock rather than a claim that the answer is 0.9.

     The mask is the value with every digit replaced by a hyphen, so it keeps
     the units, the decimal point and the thousands separator. Both figure
     tiers are set in IBM Plex Mono, which means the mask is exactly as wide
     as the value and nothing moves as it resolves.

     Scope is the model metrics and the counters, not every figure on the page.
     (`.gate .gv` and `.seal .digest` were in scope until the assurance panel
     was retired from the marketing pages on 2026-09-22; nothing matches them
     now, and `/demo/` does not load this file.)
     The hero metric rail is excluded on two counts that agree: one of its
     three figures is "under 15 km", which has nothing to resolve, and the
     rail sits above the fold, where this would fire during the intro and
     compete with the spacecraft. The rule is that **figures resolve when you
     scroll to them, and nothing resolves during the intro.**

     The real value is the resting state in the markup; script masks it and
     then restores it. So no-script and reduced-motion visitors never see a
     placeholder, and the DOM's settled truth is always the number. */
  (function () {
    /* Counters and chapter designators joined the scope with the two-product
       restructure; prose headlines never do (instrument, not game HUD). */
    /* The metric rail joined the scope when it moved out of the hero. The rule
       above excluded it for one reason, that it sat above the fold and would
       fire during the intro; under the product boxes it is scrolled to like
       everything else. "under 15 km" has no digits and resolve() already
       returns on a figure with nothing to mask. */
    var figures = document.querySelectorAll('.cap-metric .big, .cap-head .count, .chap-designator, .chap-count, .rail .num');
    if (!figures.length || !('IntersectionObserver' in window)) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var HOLD = 180;   /* mask is held while the row is still fading up */
    var STEP = 70;    /* per digit, so the longest figure lands inside 500ms */

    var resolve = function (el) {
      /* A digest is hex, so its letters are value characters and mask with
         everything else. Elsewhere only digits are masked, because a letter in
         a figure is a unit, and `-.- s` would be nonsense. */
      var hex = el.className.indexOf('digest') !== -1;
      var full = el.textContent, at = [], i, c;
      for (i = 0; i < full.length; i++) {
        c = full[i];
        if ((c >= '0' && c <= '9') || (hex && c >= 'a' && c <= 'f')) at.push(i);
      }
      if (!at.length) return;

      var render = function (shown) {
        var out = full.split('');
        for (var j = shown; j < at.length; j++) out[at[j]] = '-';
        el.textContent = out.join('');
      };
      render(0);

      var shown = 0;
      var tick = function () {
        render(++shown);
        if (shown < at.length) setTimeout(tick, STEP);
      };
      setTimeout(tick, HOLD);
    };

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        io.unobserve(entry.target);
        resolve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0 });

    figures.forEach(function (el) { io.observe(el); });
  })();

  /* --- Reveal on scroll --------------------------------------------------
     Stagger is computed within each visual group (the .reveal children of one
     parent), not across a flat document-order list, and the inline delay is
     removed once the reveal finishes so it cannot slow later transitions. */
  var targets = document.querySelectorAll('.reveal');
  if (!targets.length) return;

  if (!('IntersectionObserver' in window)) {
    targets.forEach(function (el) { el.classList.add('in'); });
    return;
  }

  var groups = new Set();
  targets.forEach(function (el) { groups.add(el.parentElement); });
  groups.forEach(function (group) {
    /* 60ms is the system default and suits a group of two or three that just
       needs to not arrive all at once. A group whose members are meant to read
       as a *sequence* rather than a set can ask for a longer step with
       data-stagger: four items at 60ms finish in 180ms, which reads as
       simultaneous. Opt-in, so nothing else on the site changes. */
    var step = parseInt(group.getAttribute('data-stagger'), 10) || 60;
    group.querySelectorAll(':scope > .reveal').forEach(function (el, i) {
      if (i > 0) el.style.transitionDelay = Math.min(i, 5) * step + 'ms';
    });
  });

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      io.unobserve(el);
      el.classList.add('in');
      if (!el.style.transitionDelay) return;
      el.addEventListener('transitionend', function () {
        el.style.transitionDelay = '';
      }, { once: true });
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0 });

  targets.forEach(function (el) { io.observe(el); });
})();
