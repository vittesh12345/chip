#!/usr/bin/env python3
"""Serve and screenshot the ORBIT-AI 3D die viewer (viz/index.html).

viz/index.html is written as claude.ai Artifact page content (no doctype,
html/head/body tags); the Artifact host wraps it in a skeleton. This script
wraps it the same way into --site-dir, copies layout.json/layout.bin next to
it, serves the folder over HTTP and either keeps serving (--serve) or drives
the preinstalled Chromium with Playwright to write screenshots:

  viewer_iso.png               desktop 1440x900, light theme, isometric first frame
  viewer_top.png               top view
  viewer_lowangle.png          low-angle view with the layers spread apart
  viewer_redundancy.png        flip-flops highlighted by copy (all groups)
  viewer_redundancy_lane0.png  lane-0 accumulator A/B with same-bit lines, top view
  viewer_dark.png              dark theme, isometric
  viewer_dark_redundancy.png   dark theme, flip-flops highlighted
  viewer_phone.png             390x844 phone layout, light (full page)
  viewer_phone_dark.png        390x844 phone layout, dark (full page)
  glb_preview.png              the exported GLB loaded with three.js GLTFLoader

For screenshots the page is loaded unmodified, with its CDN URLs, under a
Content-Security-Policy modelled on the Artifact sandbox; CDN requests are
answered from byte-identical local copies (CdnMirror), every contacted host is
logged, and a host outside the allowlist, a CSP violation, a page error or
horizontal overflow makes the script exit non-zero. --cdn uses the real CDNs.

WebGL runs on SwiftShader in headless Chromium, so a frame of the full die
takes seconds to tens of seconds; the script waits for rendering to settle.
"""

import argparse
import functools
import hashlib
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import tarfile
import sys
import threading
import time
import urllib.parse

SKELETON_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
/* approximation of the Artifact host skeleton reset */
:root { color-scheme: light; padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }
body { margin: 0; font: 14px system-ui, sans-serif; background: #fafaf9; }
img { max-width: 100%; }
[hidden] { display: none !important; }
</style>
</head>
<body>
"""
SKELETON_TAIL = "\n</body>\n</html>\n"

GLB_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;height:100%;background:#e4ecf0}canvas{display:block}</style></head><body>
<script type="importmap">{"imports":{"three":"%(three)sbuild/three.module.js",
"three/addons/":"%(three)sexamples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
const r = new THREE.WebGLRenderer({antialias:true}); r.setSize(innerWidth, innerHeight); r.setClearColor(0xe4ecf0);
document.body.appendChild(r.domElement);
const scene = new THREE.Scene();
scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 2.2));
const d = new THREE.DirectionalLight(0xffffff, 2.0); d.position.set(-1, 2, 1.5); scene.add(d);
new GLTFLoader().load('./model.glb', (g) => {
  const root = g.scene;
  root.scale.y = %(zscale)s;   // vertical exaggeration for the preview only
  scene.add(root);
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
  const cam = new THREE.PerspectiveCamera(32, innerWidth / innerHeight, size.x / 1000, size.x * 20);
  cam.position.set(c.x - size.x * 0.95, c.y + size.x * 1.1, c.z + size.x * 1.5);
  cam.lookAt(c);
  r.render(scene, cam);
  const names = []; root.traverse((o) => { if (o.isMesh) names.push(o.name); });
  window.__glb = {ok: true, meshes: names, size: [size.x, size.y, size.z]};
}, undefined, (e) => { window.__glb = {ok: false, error: String(e && e.message || e)}; });
</script></body></html>
"""


def build_site(page_dir, site_dir, glb=None):
    os.makedirs(site_dir, exist_ok=True)
    src = open(os.path.join(page_dir, "index.html"), encoding="utf-8").read()
    if src.lstrip().lower().startswith("<!doctype"):
        html = src
    else:
        html = SKELETON_HEAD + src + SKELETON_TAIL
    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    for name in ("layout.json", "layout.bin"):
        p = os.path.join(page_dir, name)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(site_dir, name))
        else:
            print(f"viz_shots: warning: {p} missing (the page will show its error state)")
    if glb and os.path.exists(glb):
        shutil.copyfile(glb, os.path.join(site_dir, "model.glb"))


def _curl(url, dest, ua=None):
    cmd = ["curl", "-fsSL", "-m", "120", "-o", dest, url]
    if ua:
        cmd[1:1] = ["-A", ua]
    return subprocess.run(cmd, capture_output=True, text=True).returncode == 0


CHROME_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/141.0.0.0 Safari/537.36")
THREE_FILES = ["build/three.module.js", "examples/jsm/controls/OrbitControls.js",
               "examples/jsm/loaders/GLTFLoader.js", "examples/jsm/utils/BufferGeometryUtils.js"]


def vendor_assets(site_dir, cache_dir):
    """Local copies of the page's CDN assets for --serve (local viewing).

    The published page loads three.js from cdn.jsdelivr.net/npm/ (a mirror of
    the npm package) and its fonts from Google Fonts. Build machines may not
    reach those hosts, so for local viewing the harness takes the same pinned
    three.js release from the npm registry tarball (byte-identical files) and
    the font files from Google Fonts, and rewrites the site copy of the page
    to use them. Screenshots do not use this (see CdnMirror).
    Returns a list of notes."""
    notes = []
    index = os.path.join(site_dir, "index.html")
    html = open(index, encoding="utf-8").read()
    m = re.search(r"https://cdn\.jsdelivr\.net/npm/three@([0-9.]+)/", html)
    if m:
        ver = m.group(1)
        tgz = os.path.join(cache_dir, f"three-{ver}.tgz")
        os.makedirs(cache_dir, exist_ok=True)
        if not os.path.exists(tgz) and not _curl(f"https://registry.npmjs.org/three/-/three-{ver}.tgz", tgz):
            notes.append(f"could not fetch three@{ver} from the npm registry; the page keeps the CDN URLs")
        else:
            dst = os.path.join(site_dir, "vendor", f"three@{ver}")
            with tarfile.open(tgz) as tf:
                for rel in THREE_FILES:
                    member = tf.getmember("package/" + rel)
                    os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
                    with tf.extractfile(member) as fsrc, open(os.path.join(dst, rel), "wb") as fdst:
                        fdst.write(fsrc.read())
            html = html.replace(f"https://cdn.jsdelivr.net/npm/three@{ver}/", f"./vendor/three@{ver}/")
            notes.append(f"three@{ver} served locally from the npm tarball")
    m = re.search(r'href="(https://fonts\.googleapis\.com/css2[^"]+)"', html)
    if m:
        css_url = m.group(1).replace("&amp;", "&")
        css_path = os.path.join(cache_dir, "fonts.css")
        if _curl(css_url, css_path, ua=CHROME_UA):
            css = open(css_path).read()
            fdir = os.path.join(site_dir, "vendor", "fonts")
            os.makedirs(fdir, exist_ok=True)
            ok = True
            for i, u in enumerate(sorted(set(re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", css)))):
                name = f"f{i}" + os.path.splitext(u.split("?")[0])[1]
                cached = os.path.join(cache_dir, "fonts", name)
                os.makedirs(os.path.dirname(cached), exist_ok=True)
                if not os.path.exists(cached) and not _curl(u, cached):
                    ok = False
                    continue
                shutil.copyfile(cached, os.path.join(fdir, name))
                css = css.replace(u, "./fonts/" + name)
            with open(os.path.join(site_dir, "vendor", "fonts.css"), "w") as f:
                f.write(css)
            html = html.replace(m.group(1), "./vendor/fonts.css")
            notes.append("Google Fonts served locally" + ("" if ok else " (some files missing)"))
        else:
            notes.append("could not fetch the Google Fonts stylesheet; screenshots use fallback fonts")
    with open(index, "w", encoding="utf-8") as f:
        f.write(html)
    return notes


# Hosts the Artifact sandbox admits (scripts from the three CDNs, styles and
# font files from Google Fonts) and a CSP modelled on its allowlist.
ALLOWED_HOSTS = {"cdn.jsdelivr.net", "cdnjs.cloudflare.com", "unpkg.com",
                 "fonts.googleapis.com", "fonts.gstatic.com"}
ARTIFACT_CSP = ("default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net/npm/ "
                "https://unpkg.com https://cdn.tailwindcss.com https://code.jquery.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
                "img-src 'self' data: blob:; connect-src 'self'")


class CdnMirror:
    """Answers the page's own CDN requests from local, byte-identical copies.

    The page is loaded unmodified, so the browser requests exactly the URLs
    the published page requests (three.js from cdn.jsdelivr.net/npm/, the
    fonts from Google Fonts); Playwright routing fulfils them from the npm
    registry tarball of the same pinned three.js release and from cached
    Google Fonts files. Build machines often cannot reach the CDNs directly.
    """

    def __init__(self, html, cache_dir):
        self.notes = []
        self.three_prefix = None
        self.tgz = None
        self.css = None
        self.fonts = {}
        os.makedirs(cache_dir, exist_ok=True)
        m = re.search(r"https://cdn\.jsdelivr\.net/npm/three@([0-9.]+)/", html)
        if m:
            ver = m.group(1)
            tgz = os.path.join(cache_dir, f"three-{ver}.tgz")
            if os.path.exists(tgz) or _curl(f"https://registry.npmjs.org/three/-/three-{ver}.tgz", tgz):
                self.tgz = tarfile.open(tgz)
                self.three_prefix = f"https://cdn.jsdelivr.net/npm/three@{ver}/"
                self.notes.append(f"three@{ver}: CDN requests answered from the npm registry tarball")
            else:
                self.notes.append(f"could not fetch three@{ver} from the npm registry")
        m = re.search(r'href="(https://fonts\.googleapis\.com/css2[^"]+)"', html)
        if m:
            css_path = os.path.join(cache_dir, "fonts.css")
            if _curl(m.group(1).replace("&amp;", "&"), css_path, ua=CHROME_UA) or os.path.exists(css_path):
                self.css = open(css_path, encoding="utf-8").read()
                missing = 0
                for u in sorted(set(re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", self.css))):
                    name = hashlib.sha1(u.encode()).hexdigest()[:16] + os.path.splitext(u.split("?")[0])[1]
                    cached = os.path.join(cache_dir, "fonts-by-url", name)
                    os.makedirs(os.path.dirname(cached), exist_ok=True)
                    if os.path.exists(cached) or _curl(u, cached):
                        self.fonts[u] = cached
                    else:
                        missing += 1
                self.notes.append("Google Fonts answered from cached files" +
                                  (f" ({missing} missing)" if missing else ""))
            else:
                self.notes.append("could not fetch the Google Fonts stylesheet; screenshots use fallback fonts")

    def lookup(self, url):
        """(body bytes, content type) for a mirrored URL, else None."""
        if self.three_prefix and url.startswith(self.three_prefix):
            try:
                with self.tgz.extractfile("package/" + url[len(self.three_prefix):].split("?")[0]) as f:
                    return f.read(), "text/javascript"
            except KeyError:
                return None
        u = urllib.parse.urlparse(url)
        if u.hostname == "fonts.googleapis.com" and u.path == "/css2" and self.css:
            return self.css.encode(), "text/css"
        if url in self.fonts:
            return open(self.fonts[url], "rb").read(), "font/woff2"
        return None


def make_router(mirror, hosts, csp=ARTIFACT_CSP):
    """Playwright route handler: logs every host, adds the CSP to the page,
    answers CDN URLs from the mirror (or the real network with --cdn) and
    blocks every host the Artifact sandbox would block."""
    def handler(route, request):
        u = urllib.parse.urlparse(request.url)
        hosts.setdefault(u.hostname or u.scheme, set()).add(u.path[:100])
        if u.hostname in ("127.0.0.1", "localhost"):
            if u.path in ("/", "/index.html") and csp:
                r = route.fetch()
                headers = dict(r.headers)
                headers["content-security-policy"] = csp
                return route.fulfill(response=r, headers=headers)
            return route.continue_()
        if u.scheme in ("data", "blob"):
            return route.continue_()
        if u.hostname not in ALLOWED_HOSTS:
            return route.abort("blockedbyclient")
        if mirror is None:
            return route.continue_()
        hit = mirror.lookup(request.url)
        if hit is None:
            return route.abort("internetdisconnected")
        body, ctype = hit
        return route.fulfill(status=200, body=body,
                             headers={"content-type": ctype, "access-control-allow-origin": "*"})
    return handler


def poll(page, expr, timeout_s):
    """Wait for a JS expression to become truthy. page.wait_for_function
    compiles its predicate with eval, which the page's CSP forbids."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            if page.evaluate(expr):
                return True
        except Exception:  # noqa: BLE001  (navigation in progress)
            pass
        time.sleep(0.2)
    return False


def free_port(preferred=0):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", preferred))
    except OSError:
        s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map,
                          **{".bin": "application/octet-stream", ".glb": "model/gltf-binary",
                             ".json": "application/json"})

    def log_message(self, *a):
        pass


def serve(site_dir, port):
    handler = functools.partial(QuietHandler, directory=site_dir)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def wait_settled(page, quiet_ms=1500, timeout=240):
    """Wait until the on-demand render loop has stopped producing frames."""
    t0 = time.time()
    last = page.evaluate("window.__vizFrames || 0")
    last_change = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.25)
        cur = page.evaluate("window.__vizFrames || 0")
        if cur != last:
            last, last_change = cur, time.time()
        elif (time.time() - last_change) * 1000 >= quiet_ms and cur > 0:
            return cur
    return last


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page-dir", default="viz")
    ap.add_argument("--site-dir", default="build/viz/site")
    ap.add_argument("--out-dir", default="reports/viz")
    ap.add_argument("--glb", default=None, help="GLB to preview (default: the one named in layout.json)")
    ap.add_argument("--serve", action="store_true", help="only serve the page until interrupted")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--only", default=None, help="comma list of shot names to take")
    ap.add_argument("--cdn", action="store_true", help="keep the CDN URLs instead of local copies")
    ap.add_argument("--cache-dir", default="build/viz/vendor-cache")
    args = ap.parse_args()

    glb = args.glb
    meta_path = os.path.join(args.page_dir, "layout.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    if glb is None and meta.get("glb", {}).get("path"):
        glb = meta["glb"]["path"]
    build_site(args.page_dir, args.site_dir, glb)
    port = free_port(args.port)
    url = f"http://127.0.0.1:{port}/"
    if args.serve:
        # For viewing in a local browser: rewrite the site copy to local
        # three.js/font files in case this machine cannot reach the CDNs.
        if not args.cdn:
            for n in vendor_assets(args.site_dir, args.cache_dir):
                print("viz_shots:", n)
        httpd = serve(args.site_dir, port)
        print(f"viz: serving {os.path.abspath(args.site_dir)} at {url}  (Ctrl-C to stop)")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0
    httpd = serve(args.site_dir, port)

    # Screenshots load the page exactly as published (CDN URLs intact) under an
    # Artifact-like CSP; CDN requests are answered from local copies.
    mirror = None
    if not args.cdn:
        mirror = CdnMirror(open(os.path.join(args.site_dir, "index.html"), encoding="utf-8").read(),
                           args.cache_dir)
        for n in mirror.notes:
            print("viz_shots:", n)
    hosts = {}

    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    from playwright.sync_api import sync_playwright

    only = set(args.only.split(",")) if args.only else None
    want = lambda n: only is None or n in only  # noqa: E731
    os.makedirs(args.out_dir, exist_ok=True)
    problems = []
    written = []

    def shot(page, name, full_page=False):
        page.mouse.move(2, 2)  # no stray :hover styling from the last click
        path = os.path.join(args.out_dir, name + ".png")
        page.screenshot(path=path, full_page=full_page, timeout=600000)
        written.append(path)
        print(f"viz_shots: wrote {path}")

    def set_range(page, sel, value):
        page.eval_on_selector(sel, "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }",
                              value)

    def scroll_to_redundancy(page):
        page.evaluate("document.getElementById('h-red').scrollIntoView({block: 'start'})")

    gl_args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
               "--enable-webgl", "--disable-dev-shm-usage"]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=list(gl_args))

        def open_page(width, height, scheme="light", dpr=1, mobile=False):
            ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=dpr,
                                      color_scheme=scheme, reduced_motion="reduce", is_mobile=mobile,
                                      has_touch=mobile)
            ctx.route("**/*", make_router(mirror, hosts))
            page = ctx.new_page()
            logs = []
            page.on("console", lambda m: logs.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
            page.goto(url, wait_until="load")
            if not poll(page, "['ready', 'error'].includes(document.documentElement.dataset.vizState)", 240):
                problems.append(f"{width}x{height} {scheme}: page never became ready")
            state = page.evaluate("document.documentElement.dataset.vizState || 'none'")
            if state != "ready":
                problems.append(f"{width}x{height} {scheme}: viewer state {state}: " +
                                page.evaluate("(document.getElementById('ov-title')||{}).textContent + ' / ' + (document.getElementById('ov-detail')||{}).textContent"))
            wait_settled(page)
            sw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            if sw[0] > sw[1]:
                problems.append(f"{width}x{height} {scheme}: horizontal overflow, scrollWidth {sw[0]} > {sw[1]}")
            return ctx, page, logs

        need_desktop = any(want(n) for n in ("viewer_iso", "viewer_top", "viewer_lowangle",
                                             "viewer_redundancy", "viewer_redundancy_lane0"))
        if need_desktop:
            ctx, page, logs = open_page(1440, 900)
            if want("viewer_iso"):
                shot(page, "viewer_iso")
            if want("viewer_top"):
                page.click("#v-top")
                wait_settled(page)
                shot(page, "viewer_top")
            if want("viewer_lowangle"):
                page.click("#v-low")
                set_range(page, "#s-gap", 3)
                wait_settled(page)
                shot(page, "viewer_lowangle")
                set_range(page, "#s-gap", 0)
            if want("viewer_redundancy"):
                page.click("#v-iso")
                page.check("#r-on")
                scroll_to_redundancy(page)
                wait_settled(page)
                shot(page, "viewer_redundancy")
                # hover check: the tooltip must name the flip-flop under the pointer
                pt = page.evaluate("window.orbitViz.screenOf(0)")
                if pt:
                    page.mouse.move(pt["x"], pt["y"])
                    if poll(page, "!document.getElementById('tip').hidden", 120):
                        tip = page.inner_text("#tip")
                        print("viz_shots: hover tooltip:", " | ".join(tip.split("\n")))
                    else:
                        problems.append(f"hover over {pt['name']} showed no tooltip")
                    page.mouse.move(5, 5)
            if want("viewer_redundancy_lane0"):
                has = page.evaluate("[...document.querySelectorAll('#r-group option')].some(o => o.value === 'acc_lane0')")
                if has:
                    page.select_option("#r-group", "acc_lane0")
                    page.click("#v-top")
                    scroll_to_redundancy(page)
                    wait_settled(page)
                    shot(page, "viewer_redundancy_lane0")
                else:
                    print("viz_shots: no acc_lane0 group in this data; skipping viewer_redundancy_lane0")
            problems.extend(f"desktop console {l}" for l in logs)
            ctx.close()

        if want("viewer_dark") or want("viewer_dark_redundancy"):
            ctx, page, logs = open_page(1440, 900, scheme="dark")
            if want("viewer_dark"):
                shot(page, "viewer_dark")
            if want("viewer_dark_redundancy"):
                page.check("#r-on")
                scroll_to_redundancy(page)
                wait_settled(page)
                shot(page, "viewer_dark_redundancy")
            problems.extend(f"dark console {l}" for l in logs)
            ctx.close()

        for name, scheme in (("viewer_phone", "light"), ("viewer_phone_dark", "dark")):
            if want(name):
                ctx, page, logs = open_page(390, 844, scheme=scheme, dpr=2, mobile=True)
                shot(page, name, full_page=True)
                problems.extend(f"phone {scheme} console {l}" for l in logs)
                ctx.close()

        if want("glb_preview") and glb and os.path.exists(glb):
            zs = 4
            with open(os.path.join(args.site_dir, "glb.html"), "w") as f:
                f.write(GLB_PAGE.replace("%(zscale)s", str(zs))
                        .replace("%(three)s", "https://cdn.jsdelivr.net/npm/three@0.170.0/"))
            ctx = browser.new_context(viewport={"width": 1200, "height": 800})
            ctx.route("**/*", make_router(mirror, {}, csp=None))
            page = ctx.new_page()
            logs = []
            page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
            page.goto(url + "glb.html")
            poll(page, "window.__glb !== undefined", 240)
            res = page.evaluate("window.__glb") or {"ok": False, "error": "timed out"}
            if not res.get("ok"):
                problems.append(f"GLB did not load in three.js GLTFLoader: {res}")
            else:
                print(f"viz_shots: GLB loaded in three.js: meshes {res['meshes']}")
            time.sleep(1.0)
            path = os.path.join(args.out_dir, "glb_preview.png")
            page.screenshot(path=path, timeout=600000)
            written.append(path)
            print(f"viz_shots: wrote {path} (vertical ×{zs} applied in the preview only)")
            problems.extend(f"glb console {l}" for l in logs)
            ctx.close()
        browser.close()
    print("viz_shots: hosts the page contacted:", ", ".join(sorted(h for h in hosts if h)))
    bad = sorted(h for h in hosts if h and h not in ALLOWED_HOSTS and h not in ("127.0.0.1", "localhost"))
    if bad:
        problems.append("page contacted hosts outside the Artifact allowlist: " + ", ".join(bad))
    httpd.shutdown()
    for pr in problems:
        print("viz_shots: PROBLEM:", pr)
    fatal = ("pageerror", "never became ready", "state error", "allowlist", "Content Security Policy", "overflow")
    return 1 if any(any(f in p for f in fatal) for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
