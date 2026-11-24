"""Rendert generator/tests/beispiel.json mit dem Künstler-Template nach /tmp/marktatlas-selftest/ – prüft, dass Generator und Template laufen."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build, jinja2
env = jinja2.Environment(loader=jinja2.FileSystemLoader(build.GEN), autoescape=jinja2.select_autoescape(["j2"]))
a = json.load(open(f"{build.GEN}/tests/beispiel.json", encoding="utf-8"))
build.validate(a, "beispiel.json")
page, S = build.build_artist(a, env)
out = "/tmp/marktatlas-selftest/index.html"
os.makedirs(os.path.dirname(out), exist_ok=True); open(out, "w", encoding="utf-8").write(page)
assert S["n_lots"] == 65 and S["n_sold"] == 53, S
assert S["max_hammer"] == "21.000", S["max_hammer"]
assert S["med_old_main"] == "3.400" and S["med_new_main"] == "2.200", (S["med_old_main"], S["med_new_main"])
assert S["offers_region_pct"] == 73
print("Selbsttest ok:", out)
