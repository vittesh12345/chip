/* Orbital mechanics for the visualization: two-body Kepler propagation with
   J2 secular drift on RAAN and argument of perigee. Units are km and seconds
   throughout; angles are radians. The same math runs in the point-cloud
   vertex shader — if a constant changes here, change it there too. */

export const MU = 398600.4418;      // km^3/s^2
export const R_EARTH = 6378.137;    // equatorial radius, km
export const R_MEAN = 6371.0;       // mean radius, km (globe sphere)
export const J2 = 1.08262668e-3;

export const TAU = Math.PI * 2;
export const DEG = Math.PI / 180;

/* Greenwich mean sidereal time, radians. IAU 1982 series, truncated: more
   than enough for a visualization (error well under a millidegree/decade). */
export function gmst(ms) {
  const d = (ms - Date.UTC(2000, 0, 1, 12)) / 86400000; // days since J2000
  const t = d / 36525;
  let g = 280.46061837 + 360.98564736629 * d + 0.000387933 * t * t;
  g %= 360;
  if (g < 0) g += 360;
  return g * DEG;
}

/* Approximate solar direction in ECI (unit vector). Low-precision series —
   drives the day/night shading only. */
export function sunEci(ms) {
  const d = (ms - Date.UTC(2000, 0, 1, 12)) / 86400000;
  const g = (357.529 + 0.98560028 * d) * DEG;           // mean anomaly
  const q = (280.459 + 0.98564736 * d) * DEG;           // mean longitude
  const L = q + (1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * DEG;
  const e = (23.439 - 0.00000036 * d) * DEG;            // obliquity
  return [Math.cos(L), Math.cos(e) * Math.sin(L), Math.sin(e) * Math.sin(L)];
}

export function solveKepler(M, e, iters = 8) {
  let E = e < 0.8 ? M : Math.PI;
  for (let k = 0; k < iters; k++) {
    E = E - (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
  }
  return E;
}

export function meanMotion(a) { return Math.sqrt(MU / (a * a * a)); } // rad/s

/* J2 secular rates, rad/s. p = a(1-e^2). */
export function j2Rates(a, e, inc) {
  const n = meanMotion(a);
  const p = a * (1 - e * e);
  const f = 1.5 * J2 * (R_EARTH / p) * (R_EARTH / p) * n;
  return {
    raanDot: -f * Math.cos(inc),
    argpDot: f * (2 - 2.5 * Math.sin(inc) * Math.sin(inc)),
  };
}

/* ECI position (km) of an element set at t seconds past its epoch.
   el: {a, e, inc, raan, argp, m0, n, raanDot, argpDot} */
export function eciPosition(el, t, out) {
  out = out || [0, 0, 0];
  const M = el.m0 + el.n * t;
  const E = solveKepler(((M % TAU) + TAU) % TAU, el.e);
  const cE = Math.cos(E), sE = Math.sin(E);
  const r = el.a * (1 - el.e * cE);
  // perifocal
  const xp = el.a * (cE - el.e);
  const yp = el.a * Math.sqrt(1 - el.e * el.e) * sE;
  const raan = el.raan + el.raanDot * t;
  const argp = el.argp + el.argpDot * t;
  const cO = Math.cos(raan), sO = Math.sin(raan);
  const cw = Math.cos(argp), sw = Math.sin(argp);
  const ci = Math.cos(el.inc), si = Math.sin(el.inc);
  const x1 = cw * xp - sw * yp;
  const y1 = sw * xp + cw * yp;
  out[0] = cO * x1 - sO * ci * y1;
  out[1] = sO * x1 + cO * ci * y1;
  out[2] = si * y1;
  return out;
}

/* ECI velocity magnitude at radius r (vis-viva), km/s. */
export function speedAt(a, r) { return Math.sqrt(MU * (2 / r - 1 / a)); }

/* Geodetic-ish readout from ECI at time ms (spherical earth is fine here). */
export function eciToLatLon(p, ms) {
  const r = Math.hypot(p[0], p[1], p[2]);
  const lat = Math.asin(p[2] / r) / DEG;
  let lon = (Math.atan2(p[1], p[0]) - gmst(ms)) / DEG;
  lon = ((lon + 540) % 360) - 180;
  return { lat, lon, alt: r - R_MEAN };
}

export function periodMinutes(a) { return TAU / meanMotion(a) / 60; }
export function apogeeKm(a, e) { return a * (1 + e) - R_EARTH; }
export function perigeeKm(a, e) { return a * (1 - e) - R_EARTH; }

/* Scene mapping: 1 unit = 1000 km, earth axis = +Y.
   sceneFromEci(v) = (x, z, -y) preserves handedness and puts ECI +Z (north)
   on scene +Y. Earth group rotation.y = gmst puts Greenwich at the correct
   inertial longitude. */
export const KM_TO_UNITS = 1 / 1000;
export function sceneFromEci(p, out) {
  out = out || [0, 0, 0];
  out[0] = p[0] * KM_TO_UNITS;
  out[1] = p[2] * KM_TO_UNITS;
  out[2] = -p[1] * KM_TO_UNITS;
  return out;
}

/* Position on the earth-fixed group (rotation applied by the group itself). */
export function latLonToScene(latDeg, lonDeg, rKm, out) {
  out = out || [0, 0, 0];
  const la = latDeg * DEG, lo = lonDeg * DEG;
  const r = rKm * KM_TO_UNITS;
  out[0] = r * Math.cos(la) * Math.cos(lo);
  out[1] = r * Math.sin(la);
  out[2] = -r * Math.cos(la) * Math.sin(lo);
  return out;
}

/* Is an ECI position sunlit? Cylindrical shadow model: in eclipse when the
   point is behind the terminator plane and inside the earth's shadow tube. */
export function isSunlit(p, sun) {
  const d = p[0] * sun[0] + p[1] * sun[1] + p[2] * sun[2];
  if (d > 0) return true;
  const px = p[0] - sun[0] * d, py = p[1] - sun[1] * d, pz = p[2] - sun[2] * d;
  return Math.hypot(px, py, pz) > R_EARTH;
}

export function fmtUtc(ms) {
  const d = new Date(ms);
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ` +
         `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())} UTC`;
}
