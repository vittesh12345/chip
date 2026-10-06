/* The 3D scene, matched to the reference console's look: a uniformly lit,
   label-free natural-color earth (no terminator, no clouds) with a crisp cyan
   rim and a Milky Way panorama behind it, the catalog as instanced 3D glyph
   models — dark solid fill + bright emissive edge outline — propagated
   per-instance in the vertex shader, and the radar network's large translucent
   red beam volumes. 1 scene unit = 1000 km; earth axis = +Y; the earth group
   carries the GMST rotation while every orbiting object lives in ECI. */

import * as THREE from '../vendor/three.module.min.js';
import { OrbitControls } from '../vendor/OrbitControls.js';
import {
  gmst, eciPosition, sceneFromEci, latLonToScene,
  KM_TO_UNITS, R_MEAN, TAU,
} from './orbits.js';

const R = R_MEAN * KM_TO_UNITS; // globe radius in units (~6.371)

/* Object-type palette sampled from the reference legend. */
export const TYPE_COLORS = [0x2ee83c, 0xf2c740, 0xff2e3d, 0x3f7dff];

/* ------------------------------------------------------------------ */
/* Sky: star-field panorama with a painted Milky Way band              */
/* ------------------------------------------------------------------ */
function buildSky(nightImg) {
  const w = 4096, h = 2048;
  const cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, w, h);
  if (nightImg) {
    ctx.globalAlpha = 0.68;
    ctx.drawImage(nightImg, 0, 0, w, h);
    ctx.globalAlpha = 1;
  }

  let s = 977;
  const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };

  // Galactic plane as a tilted great circle in the equirect projection.
  const tilt = 1.05, node = 0.62;
  const bandY = (u) => h / 2 - Math.asin(Math.sin(tilt) * Math.sin(TAU * (u - node))) / (Math.PI / 2) * (h / 2) * 0.92;

  const blob = (x, y, r, rgb, a) => {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(${rgb},${a})`);
    g.addColorStop(1, `rgba(${rgb},0)`);
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
  };

  // diffuse warm glow along the band, brightest near the "core"
  for (let i = 0; i < 900; i++) {
    const u = rnd();
    const x = u * w;
    const y = bandY(u) + (rnd() - 0.5) * 120;
    const core = Math.exp(-Math.pow(((u - 0.30 + 1.5) % 1) - 0.5, 2) / 0.02);
    blob(x, y, 50 + rnd() * 110, '235,225,205', 0.036 + 0.06 * core * rnd());
  }
  // brown dust lanes threading the band
  for (let i = 0; i < 500; i++) {
    const u = rnd();
    const x = u * w;
    const y = bandY(u) + (rnd() - 0.5) * 55;
    blob(x, y, 18 + rnd() * 60, '62,40,26', 0.06 + rnd() * 0.12);
  }
  // star dust concentrated toward the band
  ctx.fillStyle = 'rgba(255,250,240,0.85)';
  for (let i = 0; i < 8000; i++) {
    const u = rnd();
    const spread = 60 + rnd() * rnd() * 600;
    const x = u * w;
    const y = bandY(u) + (rnd() - 0.5) * spread;
    if (y < 0 || y >= h) continue;
    const b = 0.25 + rnd() * 0.6;
    ctx.globalAlpha = b * (spread < 220 ? 0.8 : 0.3);
    const r2 = rnd() < 0.93 ? 0.8 : 1.4;
    ctx.fillRect(x, y, r2, r2);
  }
  ctx.globalAlpha = 1;

  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = THREE.RepeatWrapping;
  const geo = new THREE.SphereGeometry(460, 48, 32);
  const mat = new THREE.MeshBasicMaterial({ map: tex, side: THREE.BackSide, depthWrite: false });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.z = 0.35; // tip the band diagonally like the reference view
  return mesh;
}

/* ------------------------------------------------------------------ */
/* Earth: uniformly lit natural color, graded vivid, crisp up close    */
/* ------------------------------------------------------------------ */

/* Tileable multi-octave value noise packed into rgb — the shader blends it in
   by distance so the surface keeps plausible terrain grain long after the
   4k basemap runs out of pixels. */
function buildDetailTexture() {
  const N = 512;
  let s = 4242;
  const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
  const grid = new Float32Array(N * N);
  for (let i = 0; i < grid.length; i++) grid[i] = rnd();
  const sample = (x, y, span) => {
    const xi = Math.floor(x), yi = Math.floor(y);
    const fx = x - xi, fy = y - yi;
    const g = (ix, iy) => grid[((iy % span + span) % span) * N + ((ix % span + span) % span)];
    const a = g(xi, yi), b = g(xi + 1, yi), c = g(xi, yi + 1), d = g(xi + 1, yi + 1);
    const ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
    return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy;
  };
  const fbm = (u, v, base) => {
    let n = 0, amp = 1, span = base, tot = 0;
    for (let o = 0; o < 4; o++) {
      n += sample(u * span, v * span, span) * amp;
      tot += amp;
      span *= 2; amp *= 0.55;
    }
    return n / tot;
  };
  const cv = document.createElement('canvas');
  cv.width = N; cv.height = N;
  const ctx = cv.getContext('2d');
  const img = ctx.createImageData(N, N);
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const u = x / N, v = y / N;
      const k = (y * N + x) * 4;
      img.data[k] = Math.round(fbm(u, v, 8) * 255);      // broad relief
      img.data[k + 1] = Math.round(fbm(u, v, 24) * 255); // fine grain
      img.data[k + 2] = Math.round(fbm(u, v, 64) * 255); // micro grain
      img.data[k + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  return tex;
}

function buildEarth(tex, detailTex) {
  const geo = new THREE.SphereGeometry(R, 128, 96);
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uMap: { value: tex },
      uDetail: { value: detailTex },
    },
    vertexShader: /* glsl */`
      varying vec2 vUv;
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        vUv = uv;
        vNormalW = normalize(mat3(modelMatrix) * normal);
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vPosW = wp.xyz;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }`,
    fragmentShader: /* glsl */`
      uniform sampler2D uMap;
      uniform sampler2D uDetail;
      varying vec2 vUv;
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        vec3 base = texture2D(uMap, vUv).rgb;
        // natural-color grade: gentle vibrance, land tamed away from orange
        // toward green/tan, and a multiplicative cool tint on ocean pixels so
        // the bathymetry relief stays visible instead of flooding blue
        float l = dot(base, vec3(0.299, 0.587, 0.114));
        vec3 col = mix(vec3(l), base, 1.22);
        col *= vec3(0.94, 1.08, 1.01);
        col = col * 1.35 + 0.02;
        float oceanW = smoothstep(0.03, 0.20, base.b - max(base.r, base.g));
        col = mix(col, col * vec3(0.55, 0.85, 1.35) + vec3(0.0, 0.02, 0.06), oceanW * 0.55);
        // distance-blended terrain grain: keeps close zooms crisp after the
        // basemap's own pixels run out
        float distFrag = distance(cameraPosition, vPosW);
        float k1 = smoothstep(3.0, 0.25, distFrag);
        float k2 = smoothstep(0.7, 0.04, distFrag);
        vec3 dtex = texture2D(uDetail, vUv * vec2(48.0, 24.0)).rgb;
        vec3 dtex2 = texture2D(uDetail, vUv * vec2(220.0, 110.0)).rgb;
        col *= mix(1.0, 0.86 + 0.28 * dtex.g, k1);
        col *= mix(1.0, 0.90 + 0.20 * dtex2.b, k2);
        col = clamp(col, 0.0, 1.0);
        // thin cool limb accent (the atmosphere shell carries the main rim)
        vec3 viewDir = normalize(cameraPosition - vPosW);
        float rim = pow(1.0 - clamp(dot(viewDir, vNormalW), 0.0, 1.0), 4.0);
        col += vec3(0.10, 0.28, 0.45) * rim * 0.30;
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
  return new THREE.Mesh(geo, mat);
}

function buildAtmosphere() {
  // thin, crisp cyan rim hugging the limb
  const geo = new THREE.SphereGeometry(R * 1.02, 96, 64);
  const mat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    uniforms: { uColor: { value: new THREE.Color(0x54d2ff) } },
    vertexShader: /* glsl */`
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        vNormalW = normalize(mat3(modelMatrix) * normal);
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vPosW = wp.xyz;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }`,
    fragmentShader: /* glsl */`
      uniform vec3 uColor;
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        vec3 viewDir = normalize(cameraPosition - vPosW);
        float f = pow(1.0 - abs(dot(viewDir, vNormalW)), 5.0);
        gl_FragColor = vec4(uColor, f * 0.85);
      }`,
  });
  return new THREE.Mesh(geo, mat);
}

/* ------------------------------------------------------------------ */
/* Catalog as instanced, velocity-aligned glyph models                 */
/* ------------------------------------------------------------------ */
/* Ten archetypes, instanced: Starlink flat slabs standing perpendicular to
   nadir (the shell reads as a band of upright panels at the limb), a bus with
   two solar wings, rocket bodies as cylinders with an engine bell, six
   visibly different torn-metal debris shards with a fixed random roll, and
   unknowns as chunks. Every glyph draws twice — a dark solid fill plus a
   bright emissive edge outline in the instance color — and a minimum
   screen-size clamp keeps the far field reading as clean bright specks. */

function boxPart(w, h, d, tx, ty, tz) {
  const g = new THREE.BoxGeometry(w, h, d).toNonIndexed();
  g.translate(tx, ty, tz);
  return g;
}

function concatGeoms(geoms) {
  let count = 0;
  for (const g of geoms) count += g.attributes.position.count;
  const pos = new Float32Array(count * 3);
  const nor = new Float32Array(count * 3);
  let o = 0;
  for (const g of geoms) {
    pos.set(g.attributes.position.array, o * 3);
    nor.set(g.attributes.normal.array, o * 3);
    o += g.attributes.position.count;
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  return out;
}

/* Irregular shard: fan-triangulated loop with per-point z jitter, drawn
   double-sided; the edge geometry is the outline loop itself. */
function shardGeoms(pts) {
  const c = [0, 0, 0];
  for (const p of pts) { c[0] += p[0]; c[1] += p[1]; c[2] += p[2]; }
  c[0] /= pts.length; c[1] /= pts.length; c[2] /= pts.length;
  const pos = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    pos.push(...c, ...a, ...b);
    pos.push(...c, ...b, ...a); // back face
  }
  const fill = new THREE.BufferGeometry();
  fill.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
  fill.computeVertexNormals();
  const line = [];
  for (let i = 0; i < pts.length; i++) {
    line.push(...pts[i], ...pts[(i + 1) % pts.length]);
  }
  const edges = new THREE.BufferGeometry();
  edges.setAttribute('position', new THREE.BufferAttribute(new Float32Array(line), 3));
  return { fill, edges };
}

function archetypeGeometries() {
  // x = along-track, y = cross-track, z = radial (matches the shader basis)
  const pair = (g, thresh = 12) => ({ fill: g, edges: new THREE.EdgesGeometry(g, thresh) });

  // 0 — Starlink flatsat slab, standing in the radial axis
  const slab = new THREE.BoxGeometry(0.95, 0.07, 1.5).toNonIndexed();

  // 1 — box bus with twin solar wings
  const bus = concatGeoms([
    boxPart(0.85, 0.42, 0.42, 0, 0, 0),
    boxPart(0.5, 0.85, 0.06, 0, 0.65, 0),
    boxPart(0.5, 0.85, 0.06, 0, -0.65, 0),
  ]);

  // 2 — rocket body: cylinder + engine bell
  const tube = new THREE.CylinderGeometry(0.26, 0.26, 1.25, 10);
  tube.rotateZ(Math.PI / 2);
  const bell = new THREE.CylinderGeometry(0.22, 0.4, 0.38, 10, 1, true);
  bell.rotateZ(-Math.PI / 2); // flare opens aft
  bell.translate(-0.8, 0, 0);
  const rb = concatGeoms([tube.toNonIndexed(), bell.toNonIndexed()]);

  // 3..8 — six visibly different debris shards
  const rod = new THREE.BoxGeometry(1.15, 0.1, 0.08).toNonIndexed();
  const chunk = new THREE.TetrahedronGeometry(0.6);
  chunk.scale(1.2, 0.62, 0.9);
  const bentA = boxPart(0.7, 0.5, 0.05, -0.18, 0, 0);
  const bentB = new THREE.BoxGeometry(0.42, 0.5, 0.05).toNonIndexed();
  bentB.rotateY(0.6);
  bentB.translate(0.38, 0, 0.1);
  const bent = concatGeoms([bentA, bentB]);
  const lplate = concatGeoms([
    boxPart(0.72, 0.34, 0.05, 0, -0.2, 0),
    boxPart(0.3, 0.55, 0.05, -0.21, 0.2, 0),
  ]);
  const tornPts = [
    [-0.5, -0.25, 0], [0.15, -0.35, 0.06], [0.5, 0.05, 0], [0.2, 0.15, 0.05],
    [0.35, 0.4, -0.04], [-0.2, 0.3, 0], [-0.45, 0.05, 0.07],
  ];
  const torn = shardGeoms(tornPts);
  const crescPts = [];
  for (let i = 0; i <= 7; i++) {
    const a = 0.35 + (i / 7) * Math.PI * 1.15;
    crescPts.push([Math.cos(a) * 0.55, Math.sin(a) * 0.55, (i % 2) * 0.06]);
  }
  for (let i = 7; i >= 0; i--) {
    const a = 0.35 + (i / 7) * Math.PI * 1.15;
    crescPts.push([Math.cos(a) * 0.3, Math.sin(a) * 0.3, 0]);
  }
  const cresc = shardGeoms(crescPts);

  // 9 — unknown chunk
  const unknown = new THREE.OctahedronGeometry(0.48);

  return [
    pair(slab),
    pair(bus),
    pair(rb),
    pair(rod),
    pair(chunk.toNonIndexed(), 4),
    pair(bent),
    pair(lplate),
    torn,
    cresc,
    pair(unknown.toNonIndexed(), 4),
  ];
}

const ORBIT_GLSL = /* glsl */`
  attribute vec4 iE1; // a(km), e, inc, raan
  attribute vec4 iE2; // argp, m0, n, raanDot
  attribute float iE3; // argpDot
  attribute float iVis;
  attribute float iRand;
  attribute vec3 iColor;
  uniform float uTime;
  uniform float uReveal;
  uniform float uScale;
  uniform float uLen;
  uniform float uRoll;
  uniform float uPixelFactor; // world units per pixel at unit view distance
  uniform float uMinPx;
  varying vec3 vCol;
  const float KM = 0.001;
  vec3 orbitPos(float t) {
    float a = iE1.x, e = iE1.y, inc = iE1.z;
    float raan = iE1.w + iE2.w * t;
    float argp = iE2.x + iE3 * t;
    float M = iE2.y + iE2.z * t;
    float E = M;
    for (int k = 0; k < 6; k++) {
      E = E - (E - e * sin(E) - M) / (1.0 - e * cos(E));
    }
    float cE = cos(E), sE = sin(E);
    float xp = a * (cE - e);
    float yp = a * sqrt(1.0 - e * e) * sE;
    float cO = cos(raan), sO = sin(raan);
    float cw = cos(argp), sw = sin(argp);
    float ci = cos(inc), si = sin(inc);
    float x1 = cw * xp - sw * yp;
    float y1 = sw * xp + cw * yp;
    return vec3(
      (cO * x1 - sO * ci * y1) * KM,
      (si * y1) * KM,
      -(sO * x1 + cO * ci * y1) * KM
    );
  }
  /* world scale with a minimum screen-size clamp; clampK reports how hard the
     clamp is driving (0 = true size, 1 = fully clamped speck) */
  float glyphScale(vec3 c0, float on, out float clampK) {
    float sc = uScale * (0.75 + iRand * 0.55) * uLen;
    float distv = length((modelViewMatrix * vec4(c0, 1.0)).xyz);
    float minWorld = uMinPx * distv * uPixelFactor;
    float outSc = max(sc, minWorld);
    clampK = smoothstep(1.0, 2.6, minWorld / max(sc, 1e-9));
    return outSc * on;
  }`;

function buildObjects(objects) {
  const n = objects.length;
  // archetype: 0 slab (Starlink), 1 bus, 2 rocket body, 3..8 debris shards,
  // 9 unknown — debris picks its shard from the per-object random
  const NARCH = 10;
  const archOf = (o, r) => {
    if (o.kind === 0) return o.group === 'starlink' ? 0 : 1;
    if (o.kind === 1) return 2;
    if (o.kind === 2) return 3 + Math.floor(r * 6) % 6;
    return 9;
  };
  const bases = archetypeGeometries();
  const uLen = [0.8, 1.0, 0.95, 0.62, 0.62, 0.62, 0.62, 0.62, 0.62, 0.7];
  const roll = [0, 0, 0, 1, 1, 1, 1, 1, 1, 1];

  const group = new THREE.Group();
  const parts = [];
  const slotK = new Uint8Array(n);
  const slotJ = new Uint32Array(n);
  const masterVis = new Float32Array(n).fill(1);
  let seed = 77;
  const nextRand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  const rands = new Float32Array(n);
  const byArch = Array.from({ length: NARCH }, () => []);
  for (let i = 0; i < n; i++) {
    rands[i] = nextRand();
    byArch[archOf(objects[i], rands[i])].push(i);
  }

  const shared = {
    uniforms: (len, rollOn) => ({
      uTime: { value: 0 },
      uReveal: { value: 1 },
      uDim: { value: 1 },
      uFlash: { value: 0 },
      uScale: { value: 0.032 },
      uLen: { value: len },
      uRoll: { value: rollOn },
      uSunDir: { value: new THREE.Vector3(1, 0, 0) },
      uPixelFactor: { value: 0.001 },
      uMinPx: { value: 3.5 },
    }),
  };

  const makeFillMat = (len, rollOn) => new THREE.ShaderMaterial({
    // fills sit behind their own outline: push them back so the edge pass
    // never z-fights
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
    uniforms: shared.uniforms(len, rollOn),
    vertexShader: ORBIT_GLSL + /* glsl */`
      uniform vec3 uSunDir;
      void main() {
        float on = iVis * step(iRand, uReveal);
        vec3 c0 = orbitPos(uTime);
        vec3 c1 = orbitPos(uTime + 2.0);
        vec3 f = normalize(c1 - c0);
        vec3 up = normalize(c0);
        vec3 s = normalize(cross(f, up));
        vec3 u2 = cross(s, f);
        vec3 lp = position;
        vec3 ln = normal;
        if (uRoll > 0.5) {
          float th = iRand * 6.28318;
          float cr = cos(th), sr = sin(th);
          lp = vec3(lp.x, lp.y * cr - lp.z * sr, lp.y * sr + lp.z * cr);
          ln = vec3(ln.x, ln.y * cr - ln.z * sr, ln.y * sr + ln.z * cr);
        }
        float clampK;
        float sc = glyphScale(c0, on, clampK);
        vec3 wpos = c0 + (f * lp.x + s * lp.y + u2 * lp.z) * sc;
        vec3 nrm = normalize(f * ln.x + s * ln.y + u2 * ln.z);
        float light = 0.5 + 0.5 * max(dot(nrm, uSunDir), 0.0);
        // dark solid fill up close; once the min-px clamp takes over the fill
        // brightens to the raw instance color so the far field reads as clean
        // bright specks instead of hollow outlines
        vec3 fillCol = iColor * (0.17 + 0.20 * light);
        vCol = mix(fillCol, iColor, clampK);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(wpos, 1.0);
      }`,
    fragmentShader: /* glsl */`
      uniform float uDim;
      uniform float uFlash;
      varying vec3 vCol;
      void main() {
        gl_FragColor = vec4(vCol * (1.0 + uFlash * 0.8) * uDim + vec3(1.0) * uFlash * 0.08, 1.0);
      }`,
  });

  const makeEdgeMat = (len, rollOn) => new THREE.ShaderMaterial({
    uniforms: shared.uniforms(len, rollOn),
    vertexShader: ORBIT_GLSL + /* glsl */`
      void main() {
        float on = iVis * step(iRand, uReveal);
        vec3 c0 = orbitPos(uTime);
        vec3 c1 = orbitPos(uTime + 2.0);
        vec3 f = normalize(c1 - c0);
        vec3 up = normalize(c0);
        vec3 s = normalize(cross(f, up));
        vec3 u2 = cross(s, f);
        vec3 lp = position;
        if (uRoll > 0.5) {
          float th = iRand * 6.28318;
          float cr = cos(th), sr = sin(th);
          lp = vec3(lp.x, lp.y * cr - lp.z * sr, lp.y * sr + lp.z * cr);
        }
        float clampK;
        float sc = glyphScale(c0, on, clampK);
        vec3 wpos = c0 + (f * lp.x + s * lp.y + u2 * lp.z) * sc;
        vCol = iColor * (1.0 + 0.15 * (1.0 - clampK));
        gl_Position = projectionMatrix * modelViewMatrix * vec4(wpos, 1.0);
      }`,
    fragmentShader: /* glsl */`
      uniform float uDim;
      uniform float uFlash;
      varying vec3 vCol;
      void main() {
        gl_FragColor = vec4(vCol * (1.0 + uFlash * 0.6) * uDim, 1.0);
      }`,
  });

  for (let k = 0; k < NARCH; k++) {
    const idx = byArch[k];
    const m = idx.length;
    const e1 = new THREE.InstancedBufferAttribute(new Float32Array(m * 4), 4);
    const e2 = new THREE.InstancedBufferAttribute(new Float32Array(m * 4), 4);
    const e3 = new THREE.InstancedBufferAttribute(new Float32Array(m), 1);
    const vis = new THREE.InstancedBufferAttribute(new Float32Array(m).fill(1), 1);
    const rand = new THREE.InstancedBufferAttribute(new Float32Array(m), 1);
    const color = new THREE.InstancedBufferAttribute(new Float32Array(m * 3), 3);
    for (let j = 0; j < m; j++) {
      const g = idx[j];
      const el = objects[g].el;
      e1.array[j * 4] = el.a; e1.array[j * 4 + 1] = el.e; e1.array[j * 4 + 2] = el.inc; e1.array[j * 4 + 3] = el.raan;
      e2.array[j * 4] = el.argp; e2.array[j * 4 + 1] = el.m0; e2.array[j * 4 + 2] = el.n; e2.array[j * 4 + 3] = el.raanDot;
      e3.array[j] = el.argpDot;
      rand.array[j] = rands[g];
      slotK[g] = k;
      slotJ[g] = j;
    }
    const wire = (geoBase, withNormals) => {
      const geo = new THREE.InstancedBufferGeometry();
      geo.setAttribute('position', geoBase.attributes.position);
      if (withNormals) geo.setAttribute('normal', geoBase.attributes.normal);
      geo.instanceCount = m;
      // fill and edges share the same per-instance attribute objects, so one
      // scatter pass updates both draws
      geo.setAttribute('iE1', e1);
      geo.setAttribute('iE2', e2);
      geo.setAttribute('iE3', e3);
      geo.setAttribute('iVis', vis);
      geo.setAttribute('iRand', rand);
      geo.setAttribute('iColor', color);
      geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 80);
      return geo;
    };
    const fillGeo = wire(bases[k].fill, true);
    const edgeGeo = wire(bases[k].edges, false);
    const mesh = new THREE.Mesh(fillGeo, makeFillMat(uLen[k], roll[k]));
    const edges = new THREE.LineSegments(edgeGeo, makeEdgeMat(uLen[k], roll[k]));
    mesh.frustumCulled = false;
    edges.frustumCulled = false;
    group.add(mesh, edges);
    parts.push({ mesh, geo: fillGeo, mat: mesh.material, emat: edges.material });
  }

  return { group, parts, slotK, slotJ, masterVis };
}

/* ------------------------------------------------------------------ */
/* Orbit path line for the selection                                   */
/* ------------------------------------------------------------------ */
/* One full revolution of the selected object's orbit, drawn as a thin
   white line hugging the globe — depth-tested, so it wraps behind the
   Earth like the reference. Refreshed as sim time advances so J2
   precession keeps the ring honest. */
function makeOrbitLine() {
  const N = 384;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array((N + 1) * 3), 3));
  const mat = new THREE.LineBasicMaterial({
    color: 0xffffff, transparent: true, opacity: 0.85, depthWrite: false,
  });
  const line = new THREE.Line(geo, mat);
  line.visible = false;
  line.frustumCulled = false;
  line.userData.N = N;
  return line;
}

function fillOrbitLine(line, el, t) {
  const N = line.userData.N;
  const arr = line.geometry.attributes.position.array;
  const period = TAU / el.n;
  const p = [0, 0, 0], s = [0, 0, 0];
  for (let i = 0; i <= N; i++) {
    eciPosition(el, t + (i / N) * period, p);
    sceneFromEci(p, s);
    arr[i * 3] = s[0]; arr[i * 3 + 1] = s[1]; arr[i * 3 + 2] = s[2];
  }
  line.geometry.attributes.position.needsUpdate = true;
  line.visible = true;
}

/* ------------------------------------------------------------------ */
/* Sensor sites and their beam volumes                                 */
/* ------------------------------------------------------------------ */
function diamondTexture() {
  const s = 96;
  const cv = document.createElement('canvas');
  cv.width = s; cv.height = s;
  const ctx = cv.getContext('2d');
  ctx.translate(s / 2, s / 2);
  ctx.rotate(Math.PI / 4);
  ctx.fillStyle = '#eaf6fa';
  const w = 30;
  ctx.fillRect(-w / 2, -w / 2, w, w);
  ctx.strokeStyle = 'rgba(255,255,255,0.9)';
  ctx.lineWidth = 5;
  ctx.strokeRect(-w / 2, -w / 2, w, w);
  return new THREE.CanvasTexture(cv);
}

/* Large translucent red volume with faint orange ray striations running down
   the local vertical, denser toward the rim so the shape stays readable while
   the terrain shows through — the camera can fly straight underneath. */
function beamMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    uniforms: {
      uColor: { value: new THREE.Color(0xe03434) },
      uRay: { value: new THREE.Color(0xff8a3c) },
    },
    vertexShader: /* glsl */`
      varying vec3 vLocal;
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        vLocal = position;
        vNormalW = normalize(mat3(modelMatrix) * normal);
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vPosW = wp.xyz;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }`,
    fragmentShader: /* glsl */`
      uniform vec3 uColor;
      uniform vec3 uRay;
      varying vec3 vLocal;
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        float az = atan(vLocal.z, vLocal.x);
        float stri = pow(0.5 + 0.5 * sin(az * 26.0), 8.0);
        vec3 col = mix(uColor, uRay, stri * 0.85);
        vec3 viewDir = normalize(cameraPosition - vPosW);
        float grazing = 1.0 - abs(dot(viewDir, vNormalW));
        float a = 0.10 + stri * 0.22;
        a *= 0.55 + 0.8 * grazing;
        gl_FragColor = vec4(col, a);
      }`,
  });
}

/* A cone whose apex sits at the origin, opening along +Y. */
function apexCone(radius, height, radial, thetaStart, thetaLength) {
  const g = new THREE.ConeGeometry(radius, height, radial, 1, true, thetaStart ?? 0, thetaLength ?? TAU);
  g.rotateX(Math.PI);
  g.translate(0, height / 2, 0);
  return g;
}

function buildBeamMesh(type) {
  const group = new THREE.Group();
  const add = (g) => group.add(new THREE.Mesh(g, beamMaterial()));
  if (type === 'star') {
    // rosette of tilted petals, like the reference's flower-footprint fences
    for (let k = 0; k < 6; k++) {
      const g = apexCone(0.85, 2.6, 12);
      g.scale(1, 1, 0.22);
      g.rotateX(0.68);
      g.rotateY((k / 6) * TAU);
      add(g);
    }
  } else if (type === 'fan') {
    // two broad crossed fans
    for (let k = 0; k < 2; k++) {
      const g = apexCone(1.7, 2.6, 20);
      g.scale(1, 1, 0.06);
      g.rotateZ(k === 0 ? 0.18 : -0.14);
      g.rotateY(k * Math.PI / 2 + 0.4);
      add(g);
    }
  } else if (type === 'dome') {
    // shallow translucent dome hugging the site
    const g = new THREE.SphereGeometry(1.35, 40, 18, 0, TAU, 0, Math.PI / 2);
    g.scale(1, 0.5, 1);
    add(g);
  } else if (type === 'wedge') {
    // curved wedge: a sector of a wide tilted cone
    const g = apexCone(2.1, 2.0, 28, 0.4, 1.5);
    g.rotateZ(0.3);
    add(g);
  } else { // wide surveillance cone
    add(apexCone(2.2, 1.9, 40));
  }
  return group;
}

function buildSensors(sites) {
  const group = new THREE.Group();
  const beams = new THREE.Group();
  const dTex = diamondTexture();
  const markers = [];
  const up = new THREE.Vector3(0, 1, 0);
  const tintGeo = new THREE.CircleGeometry(0.72, 40);
  for (const site of sites) {
    const pos = latLonToScene(site.lat, site.lon, R_MEAN * 1.002);
    const v = new THREE.Vector3(...pos);
    const marker = new THREE.Sprite(new THREE.SpriteMaterial({
      map: dTex, transparent: true, depthWrite: false,
    }));
    marker.position.copy(v);
    marker.scale.setScalar(0.16);
    group.add(marker);
    markers.push(marker);

    const beam = buildBeamMesh(site.beam || 'cone');
    beam.position.copy(v);
    beam.quaternion.setFromUnitVectors(up, v.clone().normalize());
    beams.add(beam);

    // red terrain tint inside the footprint
    const tint = new THREE.Mesh(tintGeo, new THREE.MeshBasicMaterial({
      color: 0xd23b3b, transparent: true, opacity: 0.12,
      depthWrite: false, side: THREE.DoubleSide,
    }));
    tint.position.copy(v.clone().multiplyScalar(1.001));
    tint.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), v.clone().normalize());
    beams.add(tint);
  }
  return { group, beams, markers, sites };
}

/* ------------------------------------------------------------------ */
/* Scene assembly                                                      */
/* ------------------------------------------------------------------ */
export function createViz({ canvas, textures, objects, sensorSites }) {
  const renderer = new THREE.WebGLRenderer({
    canvas, antialias: true, alpha: false, powerPreference: 'high-performance',
  });
  const pr = Math.min(window.devicePixelRatio || 1, 2);
  renderer.setPixelRatio(pr);
  renderer.setClearColor(0x000000, 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 2, 0.05, 900);
  camera.position.set(11.5, 6.4, 22.5);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;      // soft inertia
  controls.dampingFactor = 0.06;
  controls.rotateSpeed = 0.42;
  controls.minDistance = R + 0.001;   // ~1 km above the surface
  controls.maxDistance = 120;
  controls.zoomSpeed = 0.7;
  controls.enablePan = false;
  controls.zoomToCursor = true;

  const earthGroup = new THREE.Group();
  const earthTex = new THREE.Texture(textures.earth);
  earthTex.needsUpdate = true;
  earthTex.colorSpace = THREE.SRGBColorSpace;
  earthTex.anisotropy = Math.min(16, renderer.capabilities.getMaxAnisotropy?.() || 8);
  earthTex.wrapS = THREE.RepeatWrapping; // no dark seam at the antimeridian
  const earth = buildEarth(earthTex, buildDetailTexture());
  earthGroup.add(earth);
  const sensors = buildSensors(sensorSites);
  earthGroup.add(sensors.group);
  earthGroup.add(sensors.beams);
  scene.add(earthGroup);

  const sky = buildSky(textures.night);
  scene.add(sky);
  const atmosphere = buildAtmosphere();
  scene.add(atmosphere);

  const cloudObj = buildObjects(objects);
  scene.add(cloudObj.group);
  const eachCloudMat = (fn) => cloudObj.parts.forEach((p) => { fn(p.mat); fn(p.emat); });

  const orbitLine = makeOrbitLine();
  scene.add(orbitLine);

  let epochMs = Date.now();
  let simMs = epochMs;
  let selected = -1;
  let followEarth = true;
  let lastGmst = gmst(simMs);
  const tmpP = [0, 0, 0], tmpS = [0, 0, 0];
  const v3 = new THREE.Vector3();
  const yAxis = new THREE.Vector3(0, 1, 0);

  function tSec() { return (simMs - epochMs) / 1000; }

  function rebase() {
    const dt = tSec();
    for (let i = 0; i < objects.length; i++) {
      const el = objects[i].el;
      el.m0 = (el.m0 + el.n * dt) % TAU;
      el.raan += el.raanDot * dt;
      el.argp += el.argpDot * dt;
      const p = cloudObj.parts[cloudObj.slotK[i]];
      const j = cloudObj.slotJ[i];
      p.geo.attributes.iE1.array[j * 4 + 3] = el.raan;
      p.geo.attributes.iE2.array[j * 4] = el.argp;
      p.geo.attributes.iE2.array[j * 4 + 1] = el.m0;
    }
    for (const p of cloudObj.parts) {
      p.geo.attributes.iE1.needsUpdate = true;
      p.geo.attributes.iE2.needsUpdate = true;
    }
    epochMs = simMs;
  }

  function objectScenePos(i, out) {
    eciPosition(objects[i].el, tSec(), tmpP);
    return sceneFromEci(tmpP, out || tmpS);
  }

  const visArr = cloudObj.masterVis;

  /* Screen-space pick: nearest visible objects within maxPx of the cursor,
     nearest first, globe-occluded objects excluded. */
  function pickMulti(px, py, w, h, maxPx = 14, maxN = 1) {
    const proj = new THREE.Matrix4().multiplyMatrices(
      camera.projectionMatrix, camera.matrixWorldInverse);
    const r2 = maxPx * maxPx;
    const hits = [];
    const camPos = camera.position;
    for (let i = 0; i < objects.length; i++) {
      if (visArr[i] < 0.5) continue;
      objectScenePos(i, tmpS);
      v3.set(tmpS[0], tmpS[1], tmpS[2]);
      const toObj = v3.clone().sub(camPos);
      const dist = toObj.length();
      const tca = -camPos.dot(toObj) / (dist * dist);
      if (tca > 0 && tca < 1) {
        const closest = camPos.clone().addScaledVector(toObj, tca).length();
        if (closest < R * 0.995) continue;
      }
      v3.applyMatrix4(proj);
      if (v3.z > 1) continue;
      const sx = (v3.x * 0.5 + 0.5) * w;
      const sy = (-v3.y * 0.5 + 0.5) * h;
      const d = (sx - px) * (sx - px) + (sy - py) * (sy - py);
      if (d < r2) hits.push([d, i]);
    }
    hits.sort((a, b) => a[0] - b[0]);
    return hits.slice(0, maxN).map((hd) => hd[1]);
  }

  function pick(px, py, w, h) {
    const found = pickMulti(px, py, w, h, 14, 1);
    return found.length ? found[0] : -1;
  }

  function project(i, w, h) {
    objectScenePos(i, tmpS);
    v3.set(tmpS[0], tmpS[1], tmpS[2]);
    const camPos = camera.position;
    const toObj = v3.clone().sub(camPos);
    const dist = toObj.length();
    const tca = -camPos.dot(toObj) / (dist * dist);
    let occluded = false;
    if (tca > 0 && tca < 1) {
      occluded = camPos.clone().addScaledVector(toObj, tca).length() < R * 0.995;
    }
    const inFront = v3.clone().applyMatrix4(camera.matrixWorldInverse).z < 0;
    v3.project(camera);
    return {
      x: (v3.x * 0.5 + 0.5) * w,
      y: (-v3.y * 0.5 + 0.5) * h,
      visible: !occluded && inFront,
    };
  }

  /* Selection re-anchors the orbit/zoom pivot on the moving object: the pivot
     eases from its current point onto the object (no snap), then rides along
     with it — the camera keeps its offset, so the Earth drifts behind while
     drag orbits the object and scroll converges on it. Deselecting eases the
     pivot back to Earth center. */
  const TRACK_MIN = 0.02; // ~20 km: close enough that a glyph fills the frame
  const trackPrev = new THREE.Vector3();
  let trackAnim = null; // {phase:'in'|'lock'|'out', t, from}
  function select(i) {
    if (i >= 0) {
      selected = i;
      trackAnim = { phase: 'in', t: 0, from: controls.target.clone() };
      controls.minDistance = TRACK_MIN;
      fillOrbitLine(orbitLine, objects[i].el, tSec());
      lastOrbitRefresh = simMs;
    } else {
      selected = -1;
      if (trackAnim) trackAnim = { phase: 'out', t: 0, from: controls.target.clone() };
      controls.minDistance = R + 0.001;
      orbitLine.visible = false;
    }
  }

  let flyAnim = null;
  function flyTo(i, dist) {
    if (i < 0) return;
    objectScenePos(i, tmpS);
    v3.set(tmpS[0], tmpS[1], tmpS[2]).normalize();
    const d = dist || Math.max(camera.position.length(), 13);
    flyAnim = { from: camera.position.clone(), to: v3.clone().multiplyScalar(d), t: 0 };
  }

  function sensorScreenPos(idx, w, h) {
    const site = sensorSites[idx];
    const p = latLonToScene(site.lat, site.lon, R_MEAN * 1.002);
    v3.set(p[0], p[1], p[2]).applyAxisAngle(yAxis, earthGroup.rotation.y);
    const camPos = camera.position;
    const toObj = v3.clone().sub(camPos);
    const tca = -camPos.dot(toObj) / toObj.lengthSq();
    let occluded = false;
    if (tca > 0 && tca < 1) {
      occluded = camPos.clone().addScaledVector(toObj, tca).length() < R * 0.995;
    }
    const inFront = v3.clone().applyMatrix4(camera.matrixWorldInverse).z < 0;
    v3.project(camera);
    return {
      x: (v3.x * 0.5 + 0.5) * w,
      y: (-v3.y * 0.5 + 0.5) * h,
      visible: !occluded && inFront,
    };
  }

  let lastOrbitRefresh = 0;
  function setTime(ms) {
    simMs = ms;
    if (Math.abs(tSec()) > 3 * 86400) rebase();
    const t = tSec();
    eachCloudMat((m) => { m.uniforms.uTime.value = t; });
    if (selected >= 0 && Math.abs(simMs - lastOrbitRefresh) > 60000) {
      fillOrbitLine(orbitLine, objects[selected].el, t);
      lastOrbitRefresh = simMs;
    }
    const g = gmst(simMs);
    if (followEarth) {
      // keep the camera fixed over the ground: rotate it with the planet —
      // unless a tracked selection owns the camera frame
      const dg = g - lastGmst;
      const tracking = trackAnim && trackAnim.phase !== 'out';
      if (dg !== 0 && !flyAnim && !tracking) camera.position.applyAxisAngle(yAxis, dg);
    }
    lastGmst = g;
    earthGroup.rotation.y = g;
  }

  const ease3 = (x) => 1 - Math.pow(1 - x, 3);
  let lastFrame = performance.now();
  function render() {
    const nowF = performance.now();
    const dt = Math.min((nowF - lastFrame) / 1000, 0.25);
    lastFrame = nowF;

    if (flyAnim) {
      flyAnim.t += dt / 0.9;
      const k = flyAnim.t >= 1 ? 1 : ease3(flyAnim.t);
      camera.position.lerpVectors(flyAnim.from, flyAnim.to, k);
      if (flyAnim.t >= 1) flyAnim = null;
    }

    // tracked-selection pivot: ease in → ride along → ease back out
    if (trackAnim) {
      if (trackAnim.phase === 'in' && selected >= 0) {
        objectScenePos(selected, tmpS);
        v3.set(tmpS[0], tmpS[1], tmpS[2]);
        trackAnim.t += dt / 0.7;
        if (trackAnim.t >= 1) {
          controls.target.copy(v3);
          trackPrev.copy(v3);
          trackAnim = { phase: 'lock' };
        } else {
          controls.target.lerpVectors(trackAnim.from, v3, ease3(trackAnim.t));
        }
      } else if (trackAnim.phase === 'lock' && selected >= 0) {
        objectScenePos(selected, tmpS);
        v3.set(tmpS[0], tmpS[1], tmpS[2]);
        // ride along: the camera keeps its offset in the object's frame
        camera.position.add(v3.clone().sub(trackPrev));
        controls.target.copy(v3);
        trackPrev.copy(v3);
      } else if (trackAnim.phase === 'out') {
        trackAnim.t += dt / 0.8;
        if (trackAnim.t >= 1) {
          controls.target.set(0, 0, 0);
          trackAnim = null;
        } else {
          controls.target.lerpVectors(trackAnim.from, v3.set(0, 0, 0), ease3(trackAnim.t));
        }
      } else {
        trackAnim = null;
      }
    }

    controls.update();

    // dynamic near plane: keep depth precision sane from deep space down to
    // the 1 km terrain skim — and never clip a tracked object the camera has
    // converged on, so nearness is judged against the pivot too
    const alt = Math.max(camera.position.length() - R, 0.0006);
    const distT = camera.position.distanceTo(controls.target);
    const near = Math.min(0.05, Math.max(0.00018, Math.min(alt, distT) * 0.2));
    if (Math.abs(near - camera.near) / camera.near > 0.2) {
      camera.near = near;
      camera.updateProjectionMatrix();
    }

    const fl = cloudObj.parts[0].mat.uniforms.uFlash.value;
    if (fl > 0.002) eachCloudMat((m) => { m.uniforms.uFlash.value = fl * Math.exp(-dt * 3.2); });
    else if (fl !== 0) eachCloudMat((m) => { m.uniforms.uFlash.value = 0; });

    renderer.render(scene, camera);
  }

  function resize(w, h) {
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    const pf = (2 * Math.tan((camera.fov * Math.PI / 180) / 2)) / (h * pr);
    eachCloudMat((m) => { m.uniforms.uPixelFactor.value = pf; });
  }

  return {
    renderer, scene, camera, controls, objects,
    setTime, render, resize, pick, pickMulti, project, select, flyTo, sensorScreenPos,
    objectScenePos,
    get selected() { return selected; },
    get simMs() { return simMs; },
    get tracking() { return !!(trackAnim && trackAnim.phase === 'lock'); },
    tOf(ms) { return (ms - epochMs) / 1000; },
    setVis(updateFn) {
      updateFn(cloudObj.masterVis);
      for (let i = 0; i < objects.length; i++) {
        cloudObj.parts[cloudObj.slotK[i]].geo.attributes.iVis.array[cloudObj.slotJ[i]] = cloudObj.masterVis[i];
      }
      for (const p of cloudObj.parts) p.geo.attributes.iVis.needsUpdate = true;
    },
    /* Per-object colors for the view modes; fn(i) -> [r,g,b] in 0..1 */
    setColors(fn) {
      for (let i = 0; i < objects.length; i++) {
        const c = fn(i);
        const arr = cloudObj.parts[cloudObj.slotK[i]].geo.attributes.iColor.array;
        const j = cloudObj.slotJ[i];
        arr[j * 3] = c[0]; arr[j * 3 + 1] = c[1]; arr[j * 3 + 2] = c[2];
      }
      for (const p of cloudObj.parts) p.geo.attributes.iColor.needsUpdate = true;
    },
    toggles: {
      beams: (v) => { sensors.beams.visible = v; },
      instruments: (v) => { sensors.group.visible = v; },
      follow: (v) => { followEarth = v; },
    },
    setReveal(v) { eachCloudMat((m) => { m.uniforms.uReveal.value = v; }); },
    get reveal() { return cloudObj.parts[0].mat.uniforms.uReveal.value; },
    pulse() { eachCloudMat((m) => { m.uniforms.uFlash.value = 1; }); },
  };
}
