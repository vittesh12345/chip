# Screenshot harness for site/chip-space/index.html (Playwright + SwiftShader).
# three.js is served from a local npm tarball copy (set V); usage: space_shots.py d|m|both [name filters]
import asyncio, sys, json, re
from playwright.async_api import async_playwright
V="/tmp/claude-0/-home-user-chip/6bdc94fa-7275-51e9-a492-50b01aa47cf0/scratchpad/three/package/"
OUT="/home/user/chip/reports/space/"
WRAP='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>BODY</body></html>'
# (name, section, progress)
DESK=[("01_hero","s-hero",0),("02_hero_beat","s-hero",0.75),("03_build_intro","s-build",0.08),("04_build_mid","s-build",0.42),
("05_build_full","s-build",0.78),("06_compressed","s-build",0.96),("07_rad_ab","s-rad",0.5),("07b_rad_hits","s-rad",0.2),("08_rad_tmr","s-rad",0.8),
("09_proof","s-proof",0.6),("10_cards_a","s-cards",0.25),("11_cards_b","s-cards",0.75),("12_pack_wires","s-pack",0.6),
("13_pack_lid","s-pack",0.9),("16_compare_head","s-compare",0.12),("17_compare_table","s-compare",0.45),("18_compare_scope","s-compare",0.8),("14_end","s-end",1.0),("15_specs","s-end",2.2)]
MOB=[("m01_hero","s-hero",0),("m01b_why","s-hero",0.72),("m02_build_mid","s-build",0.5),("m03_compressed","s-build",0.96),("m04_rad","s-rad",0.8),
("m05_proof","s-proof",0.6),("m06_cards","s-cards",0.5),("m07_pack","s-pack",0.7),("m09_compare_chart","s-compare",0.12),("m10_compare_table","s-compare",0.42),("m11_compare_scope","s-compare",0.75),("m08_specs","s-end",2.4)]
async def run(p, vp, shots, prefix):
    b = await p.chromium.launch(args=["--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
    pg = await b.new_page(viewport=vp, device_scale_factor=1)
    errs=[]
    pg.on("console", lambda m: errs.append(m.type+": "+m.text) if m.type in ("error","warning") else None)
    pg.on("pageerror", lambda e: errs.append("pageerror: "+str(e)))
    async def three(route): await route.fulfill(path=V+route.request.url.split("three@0.170.0/")[1], content_type="application/javascript")
    await pg.route("https://cdn.jsdelivr.net/npm/three@0.170.0/**", three)
    await pg.route(re.compile(r"https://fonts\."), lambda r: r.fulfill(body="", content_type="text/css"))
    pg.on("requestfailed", lambda r: errs.append("reqfail "+r.url[:90]))
    html=open("/home/user/chip/site/chip-space/index.html").read()
    await pg.route("http://127.0.0.1:8768/", lambda r: r.fulfill(body=WRAP.replace("BODY",html), content_type="text/html"))
    await pg.goto("http://127.0.0.1:8768/", timeout=120000)
    await pg.wait_for_timeout(4000)
    ov = await pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth, document.documentElement.scrollHeight]")
    print(prefix, "scrollWidth/innerWidth/height", ov, flush=True)
    for name, sec, pr in shots:
        if only and not any(o in name for o in only): continue
        y = await pg.evaluate(f"""(()=>{{const s=document.getElementById('{sec}');const top=s.getBoundingClientRect().top+scrollY;
          const vh=innerHeight; if('{sec}'==='s-end') return top-vh+{pr}*vh; return top+{pr}*(s.offsetHeight-vh);}})()""")
        await pg.evaluate(f"window.scrollTo(0,{y}); window.__story.jump();")
        await pg.wait_for_timeout(700)
        await pg.evaluate("window.__story.jump();")
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=OUT+name+".png", timeout=600000); print(name, flush=True)
    ov = await pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    print("overflow end", ov)
    print("\n".join(errs) or "no console errors")
    await b.close()
only = sys.argv[2:] 
async def main():
    async with async_playwright() as p:
        if sys.argv[1] in ("d","both"): await run(p, {"width":1440,"height":900}, DESK, "desk")
        if sys.argv[1] in ("m","both"): await run(p, {"width":390,"height":844}, MOB, "mob")
asyncio.run(main())
