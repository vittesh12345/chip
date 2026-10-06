/* The resident-object catalog. Everything here is generated deterministically
   from a fixed seed so the population is identical on every load: real
   constellation geometries (shell altitude, inclination, plane counts), the
   documented debris clouds at their true inclinations and altitude spreads,
   and the well-known flagship spacecraft with their published elements. The
   network cannot be relied on for a live element feed from a static page, so
   this is a faithful snapshot-shaped population rather than a live one. */

import { DEG, TAU, meanMotion, j2Rates, R_EARTH } from './orbits.js';

export const KIND = { PAYLOAD: 0, ROCKET_BODY: 1, DEBRIS: 2, UNKNOWN: 3 };
export const KIND_NAME = ['Payload', 'Rocket body', 'Debris', 'Unknown'];

function mulberry32(seed) {
  let s = seed >>> 0;
  return function () {
    s |= 0; s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const objects = [];
let nextNorad = 900;
/* Real catalog numbers used by the flagship entries: the generator must never
   hand one of these to a generated object, or deep links would be ambiguous. */
const reservedIds = new Set();

function gauss(rnd) {
  return Math.sqrt(-2 * Math.log(1 - rnd())) * Math.cos(TAU * rnd());
}

/* altKm may be a perigee/apogee pair; angles in degrees. */
function add(rnd, o) {
  const aKm = o.a != null ? o.a : R_EARTH + o.alt;
  const e = o.e != null ? o.e : 0.0002 + rnd() * 0.0018;
  const inc = o.inc * DEG;
  const el = {
    a: aKm, e, inc,
    raan: (o.raan != null ? o.raan : rnd() * 360) * DEG,
    argp: (o.argp != null ? o.argp : rnd() * 360) * DEG,
    m0: (o.m0 != null ? o.m0 : rnd() * 360) * DEG,
  };
  el.n = meanMotion(el.a);
  const rates = j2Rates(el.a, el.e, el.inc);
  el.raanDot = rates.raanDot;
  el.argpDot = rates.argpDot;
  let id;
  if (o.id != null) {
    id = o.id;
    reservedIds.add(id);
  } else {
    do { nextNorad += 1 + Math.floor(rnd() * 2); } while (reservedIds.has(nextNorad));
    id = nextNorad;
  }
  objects.push({
    id,
    name: o.name,
    intl: o.intl || `${o.year}-${String(1 + Math.floor(rnd() * 180)).padStart(3, '0')}${'ABCDEFGHJKLM'[Math.floor(rnd() * 12)]}`,
    kind: o.kind,
    country: o.country,
    year: o.year,
    group: o.group || null,
    el,
  });
}

/* ---- Flagships: real spacecraft, published mean elements (approx). ---- */
function flagships(rnd) {
  const F = [
    ['ISS (ZARYA)', 25544, '1998-067A', 420, 51.64, 'US', 1998, 0.0006],
    ['CSS (TIANHE)', 48274, '2021-035A', 385, 41.47, 'PRC', 2021, 0.0004],
    ['HST', 20580, '1990-037B', 528, 28.47, 'US', 1990, 0.0002],
    ['ENVISAT', 27386, '2002-009A', 766, 98.14, 'ESA', 2002, 0.0001],
    ['TERRA', 25994, '1999-068A', 705, 98.2, 'US', 1999, 0.0001],
    ['AQUA', 27424, '2002-022A', 705, 98.2, 'US', 2002, 0.0001],
    ['LANDSAT 8', 39084, '2013-008A', 705, 98.2, 'US', 2013, 0.0001],
    ['LANDSAT 9', 49260, '2021-088A', 705, 98.2, 'US', 2021, 0.0001],
    ['SENTINEL-1A', 39634, '2014-016A', 693, 98.18, 'ESA', 2014, 0.0001],
    ['SENTINEL-2A', 40697, '2015-028A', 786, 98.57, 'ESA', 2015, 0.0001],
    ['SENTINEL-2B', 42063, '2017-013A', 786, 98.57, 'ESA', 2017, 0.0001],
    ['SENTINEL-3A', 41335, '2016-011A', 814, 98.63, 'ESA', 2016, 0.0001],
    ['NOAA 15', 25338, '1998-030A', 807, 98.6, 'US', 1998, 0.0009],
    ['NOAA 18', 28654, '2005-018A', 854, 98.9, 'US', 2005, 0.0014],
    ['NOAA 19', 33591, '2009-005A', 870, 99.1, 'US', 2009, 0.0013],
    ['NOAA 20 (JPSS-1)', 43013, '2017-073A', 824, 98.7, 'US', 2017, 0.0001],
    ['NOAA 21 (JPSS-2)', 54234, '2022-150A', 824, 98.7, 'US', 2022, 0.0001],
    ['METOP-B', 38771, '2012-049A', 817, 98.7, 'EUM', 2012, 0.0001],
    ['METOP-C', 43689, '2018-087A', 817, 98.7, 'EUM', 2018, 0.0001],
    ['SUOMI NPP', 37849, '2011-061A', 824, 98.7, 'US', 2011, 0.0001],
    ['ICESAT-2', 43613, '2018-070A', 481, 92.0, 'US', 2018, 0.0003],
    ['GRACE-FO 1', 43476, '2018-047A', 502, 88.99, 'US', 2018, 0.0016],
    ['GRACE-FO 2', 43477, '2018-047B', 502, 88.99, 'US', 2018, 0.0016],
    ['TIMED', 26998, '2001-055B', 612, 74.07, 'US', 2001, 0.0009],
    ['SWARM A', 39452, '2013-067B', 439, 87.35, 'ESA', 2013, 0.0004],
    ['SWARM B', 39451, '2013-067A', 500, 87.75, 'ESA', 2013, 0.0004],
    ['GAOFEN 11-04', 54878, '2022-177A', 500, 97.3, 'PRC', 2022, 0.0009],
    ['YAOGAN 34-02', 52084, '2022-029A', 1095, 63.4, 'PRC', 2022, 0.0002],
    ['COSMOS 2570', 58119, '2023-165A', 460, 67.1, 'CIS', 2023, 0.0006],
    ['CARTOSAT-3', 44804, '2019-081A', 509, 97.5, 'IND', 2019, 0.0003],
    ['KOMPSAT-5', 39227, '2013-042A', 550, 97.6, 'KOR', 2013, 0.0012],
    ['ALOS-2', 39766, '2014-029A', 628, 97.9, 'JPN', 2014, 0.0001],
    ['CALSPHERE 1', 900, '1964-063C', 1000, 90.2, 'US', 1964, 0.0024],
    ['VANGUARD 1', 5, '1958-002B', null, 34.25, 'US', 1958, 0.1846, 8619],
    ['AJISAI (EGS)', 16908, '1986-061A', 1490, 50.0, 'JPN', 1986, 0.0011],
    ['LAGEOS 1', 8820, '1976-039A', 5890, 109.8, 'US', 1976, 0.0044],
    ['TOPEX/POSEIDON', 22076, '1992-052A', 1336, 66.04, 'US', 1992, 0.0007],
    ['JASON-3', 41240, '2016-002A', 1336, 66.04, 'US', 2016, 0.0008],
    ['SEASAT 1', 10967, '1978-064A', 765, 108.0, 'US', 1978, 0.0002],
    ['ODIN', 26702, '2001-007A', 540, 97.6, 'SWE', 2001, 0.0011],
  ];
  for (const [name, id, intl, alt, inc, country, year, e, aOverride] of F) {
    add(rnd, {
      name, id, intl, kind: KIND.PAYLOAD, country, year, e, inc,
      alt: alt != null ? alt : undefined, a: aOverride || undefined,
      group: 'flagship',
    });
  }
}

/* ---- Constellations ---- */
function walker(rnd, opts) {
  const { prefix, count, planes, alt, inc, country, yearLo, yearHi, group,
          numberFrom = 1001, e = null } = opts;
  const perPlane = Math.ceil(count / planes);
  let k = 0;
  for (let p = 0; p < planes && k < count; p++) {
    const raan = (360 / planes) * p + rnd() * 1.4;
    for (let s = 0; s < perPlane && k < count; s++, k++) {
      add(rnd, {
        name: `${prefix}-${numberFrom + k}`,
        kind: KIND.PAYLOAD, country,
        year: yearLo + Math.floor(rnd() * (yearHi - yearLo + 1)),
        alt: alt + gauss(rnd) * 1.6,
        inc: inc + gauss(rnd) * 0.03,
        raan,
        m0: (360 / perPlane) * s + rnd() * 2.5,
        e: e != null ? e : undefined,
        group,
      });
    }
  }
}

function constellations(rnd) {
  // Starlink shells (counts scaled to the real deployment picture).
  walker(rnd, { prefix: 'STARLINK', count: 4400, planes: 72, alt: 550, inc: 53.05, country: 'US', yearLo: 2019, yearHi: 2024, group: 'starlink', numberFrom: 1007 });
  walker(rnd, { prefix: 'STARLINK', count: 1600, planes: 36, alt: 540, inc: 53.22, country: 'US', yearLo: 2021, yearHi: 2024, group: 'starlink', numberFrom: 5507 });
  walker(rnd, { prefix: 'STARLINK', count: 520, planes: 36, alt: 570, inc: 70.0, country: 'US', yearLo: 2021, yearHi: 2023, group: 'starlink', numberFrom: 30107 });
  walker(rnd, { prefix: 'STARLINK', count: 340, planes: 10, alt: 560, inc: 97.66, country: 'US', yearLo: 2021, yearHi: 2023, group: 'starlink', numberFrom: 31007 });
  walker(rnd, { prefix: 'STARLINK', count: 800, planes: 28, alt: 530, inc: 43.0, country: 'US', yearLo: 2023, yearHi: 2025, group: 'starlink', numberFrom: 32007 });
  // OneWeb
  walker(rnd, { prefix: 'ONEWEB', count: 630, planes: 12, alt: 1200, inc: 87.9, country: 'UK', yearLo: 2019, yearHi: 2023, group: 'oneweb', numberFrom: 12 });
  // Iridium NEXT
  walker(rnd, { prefix: 'IRIDIUM', count: 75, planes: 6, alt: 780, inc: 86.4, country: 'US', yearLo: 2017, yearHi: 2019, group: 'iridium', numberFrom: 102 });
  // Globalstar
  walker(rnd, { prefix: 'GLOBALSTAR M', count: 48, planes: 8, alt: 1414, inc: 52.0, country: 'US', yearLo: 2007, yearHi: 2013, group: 'globalstar', numberFrom: 65 });
  // Planet Labs flock (SSO smallsats)
  walker(rnd, { prefix: 'FLOCK 4X', count: 180, planes: 4, alt: 500, inc: 97.4, country: 'US', yearLo: 2017, yearHi: 2023, group: 'planet', numberFrom: 1 });
  // Spire Lemur
  walker(rnd, { prefix: 'LEMUR-2', count: 110, planes: 8, alt: 480, inc: 97.3, country: 'US', yearLo: 2015, yearHi: 2023, group: 'spire', numberFrom: 1 });
  // Swarm SpaceBEE
  walker(rnd, { prefix: 'SPACEBEE', count: 140, planes: 6, alt: 470, inc: 97.5, country: 'US', yearLo: 2018, yearHi: 2022, group: 'swarm', numberFrom: 10 });
}

/* ---- General payload population ---- */
function payloadsMisc(rnd) {
  const bands = [
    // [weight, incLo, incHi, altLo, altHi]
    [0.34, 97.0, 99.3, 450, 900],    // sun-synchronous
    [0.16, 51.5, 51.8, 380, 500],    // ISS-inclination rideshares
    [0.11, 63.2, 63.6, 600, 1500],   // Molniya-inclination LEO
    [0.13, 73.9, 74.2, 600, 1100],   // legacy soviet 74°
    [0.10, 81.1, 83.1, 600, 1050],   // 82° soviet weather/comms
    [0.09, 44.9, 45.3, 480, 620],    // mid-inclination smallsats
    [0.07, 28.4, 35.0, 400, 650],    // low-inclination US launches
  ];
  const NAMES = ['COSMOS', 'YAOGAN', 'JILIN-01', 'GONETS-M', 'ORBCOMM FM', 'DOVE', 'HAWK', 'ICEYE-X', 'CAPELLA', 'UMBRA', 'SHIYAN', 'TIANQI', 'NUSAT', 'KL-BETA', 'ASTROCAST', 'KEPLER', 'CENTISPACE', 'STRIX', 'GHOST', 'CZ SAT'];
  const CTY = { COSMOS: 'CIS', YAOGAN: 'PRC', 'JILIN-01': 'PRC', 'GONETS-M': 'CIS', 'ORBCOMM FM': 'US', DOVE: 'US', HAWK: 'US', 'ICEYE-X': 'FIN', CAPELLA: 'US', UMBRA: 'US', SHIYAN: 'PRC', TIANQI: 'PRC', NUSAT: 'ARG', 'KL-BETA': 'DEU', ASTROCAST: 'CHE', KEPLER: 'CAN', CENTISPACE: 'PRC', STRIX: 'JPN', GHOST: 'US', 'CZ SAT': 'PRC' };
  const total = 1350;
  for (let i = 0; i < total; i++) {
    let x = rnd(), band = bands[0];
    for (const b of bands) { if (x < b[0]) { band = b; break; } x -= b[0]; }
    const nm = NAMES[Math.floor(rnd() * NAMES.length)];
    add(rnd, {
      name: `${nm} ${100 + Math.floor(rnd() * 2500)}`,
      kind: KIND.PAYLOAD, country: CTY[nm] || 'US',
      year: 1988 + Math.floor(rnd() * 38),
      inc: band[1] + rnd() * (band[2] - band[1]),
      alt: band[3] + rnd() * (band[4] - band[3]),
      e: 0.0002 + rnd() * 0.004,
    });
  }
  // A sparse HEO/Molniya flavor population, so zoomed-out views show the
  // long ellipses the real catalog has.
  for (let i = 0; i < 26; i++) {
    const perigee = 600 + rnd() * 500, apogee = 35000 + rnd() * 5200;
    const a = R_EARTH + (perigee + apogee) / 2;
    add(rnd, {
      name: `MOLNIYA 3-${40 + i}`, kind: KIND.PAYLOAD, country: 'CIS',
      year: 1980 + Math.floor(rnd() * 25),
      a, e: (apogee - perigee) / (2 * R_EARTH + apogee + perigee),
      inc: 63.4 + gauss(rnd) * 0.1, argp: 270 + gauss(rnd) * 2,
    });
  }
}

/* ---- Rocket bodies ---- */
function rocketBodies(rnd) {
  const RB = [
    ['SL-16 R/B', 'CIS', 0.16, 70.8, 71.1, 830, 860, 1985, 2004],
    ['SL-8 R/B', 'CIS', 0.20, 73.9, 74.2, 720, 800, 1970, 1995],
    ['SL-8 R/B', 'CIS', 0.10, 82.8, 83.1, 960, 1020, 1970, 1994],
    ['SL-3 R/B', 'CIS', 0.06, 81.1, 81.3, 550, 850, 1968, 1990],
    ['CZ-2D R/B', 'PRC', 0.09, 97.2, 98.4, 480, 800, 2005, 2025],
    ['CZ-6A DEB R/B', 'PRC', 0.03, 98.8, 99.1, 700, 840, 2022, 2024],
    ['FALCON 9 R/B', 'US', 0.09, 51.5, 53.4, 300, 600, 2015, 2025],
    ['ATLAS 5 CENTAUR R/B', 'US', 0.04, 27.0, 64.0, 400, 1200, 2004, 2023],
    ['DELTA 2 R/B', 'US', 0.05, 28.5, 99.0, 500, 1000, 1990, 2017],
    ['H-2A R/B', 'JPN', 0.04, 97.3, 98.6, 450, 700, 2003, 2023],
    ['PSLV R/B', 'IND', 0.05, 97.3, 98.8, 480, 780, 1997, 2024],
    ['ARIANE 40 R/B', 'FR', 0.03, 98.0, 98.8, 700, 780, 1990, 2002],
    ['ELECTRON KICK STAGE R/B', 'US', 0.03, 85.0, 97.6, 400, 600, 2018, 2025],
    ['VEGA R/B', 'ESA', 0.03, 97.4, 98.6, 500, 700, 2012, 2024],
  ];
  const total = 1050;
  for (let i = 0; i < total; i++) {
    let x = rnd(), row = RB[0];
    for (const r of RB) { if (x < r[2]) { row = r; break; } x -= r[2]; }
    const [name, country, , incLo, incHi, altLo, altHi, yLo, yHi] = row;
    add(rnd, {
      name, kind: KIND.ROCKET_BODY, country,
      year: yLo + Math.floor(rnd() * (yHi - yLo + 1)),
      inc: incLo + rnd() * (incHi - incLo),
      alt: altLo + rnd() * (altHi - altLo),
      e: 0.001 + rnd() * 0.02,
    });
  }
}

/* ---- Debris clouds: the documented breakups, at their real geometry ---- */
function cloud(rnd, opts) {
  const { name, count, inc, incSpread, altLo, altHi, country, year, e0 = 0.004, eSpread = 0.02, group } = opts;
  for (let i = 0; i < count; i++) {
    add(rnd, {
      name, kind: KIND.DEBRIS, country, year, group,
      inc: inc + gauss(rnd) * incSpread,
      alt: altLo + Math.pow(rnd(), 1.6) * (altHi - altLo),
      e: e0 + rnd() * eSpread,
    });
  }
}

function debris(rnd) {
  cloud(rnd, { name: 'FENGYUN 1C DEB', count: 2500, inc: 98.8, incSpread: 1.6, altLo: 440, altHi: 1600, country: 'PRC', year: 2007, group: 'fy1c' });
  cloud(rnd, { name: 'COSMOS 2251 DEB', count: 1100, inc: 74.0, incSpread: 0.9, altLo: 500, altHi: 1300, country: 'CIS', year: 2009, group: 'c2251' });
  cloud(rnd, { name: 'IRIDIUM 33 DEB', count: 420, inc: 86.4, incSpread: 0.7, altLo: 520, altHi: 1050, country: 'US', year: 2009, group: 'ir33' });
  cloud(rnd, { name: 'COSMOS 1408 DEB', count: 780, inc: 82.6, incSpread: 0.8, altLo: 300, altHi: 700, country: 'CIS', year: 2021, group: 'c1408' });
  cloud(rnd, { name: 'CZ-6A DEB', count: 500, inc: 98.9, incSpread: 0.5, altLo: 500, altHi: 850, country: 'PRC', year: 2022 });
  cloud(rnd, { name: 'COSMOS 1275 DEB', count: 200, inc: 83.0, incSpread: 0.4, altLo: 940, altHi: 1030, country: 'CIS', year: 1981 });
  cloud(rnd, { name: 'NOAA 16 DEB', count: 240, inc: 98.9, incSpread: 0.6, altLo: 750, altHi: 1050, country: 'US', year: 2015 });
  cloud(rnd, { name: 'DMSP 5D-2 F13 DEB', count: 130, inc: 98.8, incSpread: 0.5, altLo: 700, altHi: 900, country: 'US', year: 2015 });
  cloud(rnd, { name: 'THOR ABLESTAR DEB', count: 170, inc: 66.7, incSpread: 0.6, altLo: 800, altHi: 1100, country: 'US', year: 1961 });
  cloud(rnd, { name: 'SL-16 DEB', count: 300, inc: 71.0, incSpread: 0.5, altLo: 780, altHi: 900, country: 'CIS', year: 1994 });
  // General fragmentation background across LEO
  const bands = [[0.30, 96.5, 100.5, 500, 1100], [0.22, 73.8, 74.3, 550, 1100], [0.16, 81.0, 83.2, 550, 1500], [0.12, 51.4, 52.2, 350, 550], [0.10, 86.0, 87.0, 600, 1100], [0.10, 62.8, 65.2, 550, 1400]];
  for (let i = 0; i < 2400; i++) {
    let x = rnd(), band = bands[0];
    for (const b of bands) { if (x < b[0]) { band = b; break; } x -= b[0]; }
    const src = rnd();
    const name = src < 0.45 ? 'COSMOS DEB' : src < 0.6 ? 'SL-8 DEB' : src < 0.72 ? 'CZ-4B DEB' : src < 0.84 ? 'DELTA 1 DEB' : 'OPS DEB';
    add(rnd, {
      name, kind: KIND.DEBRIS,
      country: name.startsWith('COSMOS') || name.startsWith('SL') ? 'CIS' : name.startsWith('CZ') ? 'PRC' : 'US',
      year: 1962 + Math.floor(rnd() * 60),
      inc: band[1] + rnd() * (band[2] - band[1]),
      alt: band[3] + Math.pow(rnd(), 1.5) * (band[4] - band[3]),
      e: 0.002 + rnd() * 0.03,
    });
  }
}

/* ---- Uncorrelated / analyst objects ---- */
function unknowns(rnd) {
  for (let i = 0; i < 260; i++) {
    const yr = 2016 + Math.floor(rnd() * 10);
    add(rnd, {
      name: `OBJECT ${String.fromCharCode(65 + Math.floor(rnd() * 26))}`,
      kind: KIND.UNKNOWN, country: 'TBD', year: yr,
      inc: 40 + rnd() * 60,
      alt: 350 + rnd() * 1300,
      e: 0.001 + rnd() * 0.02,
    });
  }
}

/* Catalogued small debris filling the tracked population out to the full
   public count: these are baseline objects — red with the Debris box
   unchecked, exactly like the reference console — so the default display
   reads 27,572. On top of that, the analyst layer: fragments below the
   public catalog's size floor, revealed by the Debris toggle the way the
   reference console adds its proprietary small-debris tracks. */
const DEB_BANDS = [[0.3, 96.5, 100.5, 480, 1150], [0.2, 73.8, 74.3, 550, 1100], [0.16, 81.0, 83.2, 550, 1400], [0.14, 51.4, 53.4, 350, 600], [0.1, 86.0, 87.2, 600, 1150], [0.1, 62.8, 65.2, 550, 1400]];

function bandDebris(rnd, name, group) {
  let x = rnd(), band = DEB_BANDS[0];
  for (const b of DEB_BANDS) { if (x < b[0]) { band = b; break; } x -= b[0]; }
  add(rnd, {
    name, kind: KIND.DEBRIS, country: 'TBD',
    year: 1965 + Math.floor(rnd() * 58),
    inc: band[1] + rnd() * (band[2] - band[1]),
    alt: band[3] + Math.pow(rnd(), 1.5) * (band[4] - band[3]),
    e: 0.002 + rnd() * 0.03,
    group,
  });
}

function smallDebris(rnd) {
  const baseline = 27572;
  while (objects.length < baseline) bandDebris(rnd, 'UNCAT DEB', null);
}

function analystDebris(rnd) {
  const extended = 4437; // the Debris checkbox adds these on top
  for (let i = 0; i < extended; i++) bandDebris(rnd, 'ANALYST DEB', 'xdeb');
}

let built = false;
export function buildCatalog() {
  if (built) return objects;
  const rnd = mulberry32(0x5EE01ab5);
  flagships(rnd);
  constellations(rnd);
  payloadsMisc(rnd);
  rocketBodies(rnd);
  debris(rnd);
  unknowns(rnd);
  smallDebris(rnd);
  analystDebris(rnd);
  built = true;
  return objects;
}

export const COUNTRIES = ['US', 'CIS', 'PRC', 'UK', 'ESA', 'JPN', 'IND', 'FR', 'DEU', 'KOR', 'CAN', 'ARG', 'FIN', 'SWE', 'CHE', 'EUM', 'TBD'];
