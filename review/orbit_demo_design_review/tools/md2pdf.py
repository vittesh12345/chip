"""Convert a package Markdown file to HTML and PDF with headless Chromium.
usage: python md2pdf.py <in.md> [<out.pdf>]
Images and links are resolved relative to the Markdown file. The HTML is written
next to the PDF (same basename) so the PDF can be regenerated."""
import os, re, sys, pathlib, tempfile, markdown
from PIL import Image
from playwright.sync_api import sync_playwright

CSS = """
@page { size: A4; margin: 16mm 14mm 16mm 14mm; }
body { font-family: "DejaVu Sans", "Liberation Sans", Arial, sans-serif; font-size: 9.5pt; line-height: 1.38; color: #111; }
h1 { font-size: 16pt; margin: 0 0 4pt; } h2 { font-size: 12.5pt; margin: 14pt 0 4pt; border-bottom: 0.6pt solid #888; padding-bottom: 2pt; }
h3 { font-size: 10.5pt; margin: 10pt 0 3pt; } h4 { font-size: 9.5pt; margin: 8pt 0 2pt; }
p, li { margin: 3pt 0; } ul, ol { margin: 3pt 0 3pt 16pt; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0 8pt; font-size: 8.3pt; page-break-inside: auto; }
tr { page-break-inside: avoid; } th, td { border: 0.5pt solid #999; padding: 2pt 4pt; vertical-align: top; text-align: left; }
th { background: #eee; font-weight: bold; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.3pt; } pre { background: #f5f5f5; border: 0.5pt solid #ccc; padding: 4pt; font-size: 7.8pt; white-space: pre-wrap; word-break: break-all; }
img { max-width: 100%; display: block; margin: 4pt 0; } .caption, em.caption { font-size: 8pt; color: #333; }
a { color: #003c8f; text-decoration: none; }
"""

def main():
    src = pathlib.Path(sys.argv[1]).resolve()
    out = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else src.with_suffix(".pdf")
    text = src.read_text()
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])
    title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), src.stem)
    # Embed downscaled copies of large raster images so the PDF stays small; the
    # full-resolution originals stay in the package next to the Markdown.
    tmp = tempfile.mkdtemp()
    def shrink(m):
        ref = m.group(1)
        f = (src.parent / ref).resolve()
        if ref.startswith(("http:", "https:", "data:")) or not f.exists() or f.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            return m.group(0)
        im = Image.open(f)
        if f.stat().st_size <= 300_000 and im.width <= 1100:
            return m.group(0)
        im = im.convert("RGB")
        w = min(im.width, 1100)
        im = im.resize((w, w * im.height // im.width), Image.LANCZOS)
        t = os.path.join(tmp, f"{abs(hash(str(f)))}.jpg")
        im.save(t, "JPEG", quality=72, optimize=True)
        return f'src="{pathlib.Path(t).as_uri()}"'
    body = re.sub(r'src="([^"]+)"', shrink, body)
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title><base href='{src.parent.as_uri()}/'><style>{CSS}</style></head><body>{body}</body></html>"
    html_path = out.with_suffix(".html")
    html_path.write_text(html)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        pg = b.new_page()
        pg.goto(html_path.as_uri())
        pg.wait_for_load_state("networkidle")
        pg.pdf(path=str(out), format="A4", print_background=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template="<div style='font-size:7pt;width:100%;text-align:center;color:#555'>"
                               f"{title} &middot; page <span class='pageNumber'></span> / <span class='totalPages'></span></div>",
               margin={"top": "14mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
        b.close()
    html_path.unlink()  # the .md is the editable source; keep only md + pdf
    print(out)

if __name__ == "__main__":
    main()
