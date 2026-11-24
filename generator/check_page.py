"""Sichtprüfung einer Seite: Screenshots mobil (390 px), Desktop (1280 px) und Dunkelmodus, plus Test auf horizontales Überlaufen.
Aufruf: python3 generator/check_page.py site/kuenstler/<slug>/index.html  [Ausgabeordner]
Braucht Playwright (pip install playwright --break-system-packages) und Chrome/Chromium."""
import sys, os, pathlib
from playwright.sync_api import sync_playwright
src = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/marktatlas-shots"
os.makedirs(out, exist_ok=True)
url = src if src.startswith("http") else pathlib.Path(src).resolve().as_uri()
exe = next((p for p in ("/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser") if os.path.exists(p)), None)
bad = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    for name, w, scheme in (("mobil", 390, "light"), ("mobil375", 375, "light"), ("desktop", 1280, "light"), ("dunkel", 390, "dark")):
        pg = b.new_page(viewport={"width": w, "height": 844}, color_scheme=scheme, device_scale_factor=1)
        pg.goto(url); pg.wait_for_timeout(400)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        if sw > w: bad.append(f"{name}: Seite {sw}px breit bei {w}px Viewport")
        pg.screenshot(path=f"{out}/{name}.png", full_page=False)
        pg.screenshot(path=f"{out}/{name}_voll.png", full_page=True)
    b.close()
print("\n".join(bad) if bad else "Kein Überlauf.", "Screenshots in", out)
sys.exit(1 if bad else 0)
