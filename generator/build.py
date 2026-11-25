"""Marktatlas-Generator.

Baut aus data/artists/*.json die Künstlerseiten, die Startseite, Rechtsseiten, robots.txt und sitemap.xml nach site/.
Aufruf:  python3 generator/build.py            (alles bauen, bricht bei Fehlern ab)
         python3 generator/build.py --check    (nur prüfen)
"""
import json, os, re, sys, html, glob, datetime, statistics as st
import jinja2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN, DATA, SITE = f"{ROOT}/generator", f"{ROOT}/data", f"{ROOT}/site"
BASE = "https://marktatlas.netlify.app"
STATIC = [  # handgebaute Seiten, die der Generator nicht anfasst
    dict(slug="max-clarenbach", name="Max Clarenbach", dates="1880–1952", line="Düsseldorfer Malerschule · Zuschlag meist 1.550–2.900 €", sort="Clarenbach"),
]
HOUSE_COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"]
HOUSE_SHAPES = ["circle", "square", "diamond", "triangle"]
MED_PAINT = ("lw", "karton")
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]

class BuildError(Exception): pass

def de(n):
    if n is None: return "–"
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " Mio."
    return f"{n:,.0f}".replace(",", ".")

def pct(v, p):
    v = sorted(v); i = (len(v) - 1) * p; lo = int(i); hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)

def nice_max(x):
    for m in [1000, 2000, 2500, 5000, 10000, 15000, 20000, 25000, 50000, 100000, 150000, 200000, 250000, 500000,
              1_000_000, 2_000_000, 2_500_000, 5_000_000, 10_000_000, 20_000_000, 25_000_000, 50_000_000, 100_000_000]:
        if x <= m: return m
    return x

def ticks_for(mx, n=None):
    s = str(int(mx))
    n = n or (3 if s.startswith("15") else 5 if s.startswith(("25", "5")) else 4)
    step = mx / n
    return [round(step * i) for i in range(n + 1)]

def size_class(l):
    if not l.get("h"): return None
    L = max(l["h"], l["w"]); return "klein" if L <= 55 else ("mittel" if L <= 90 else "gross")

def ddmmyyyy(d): return f"{d[8:10]}.{d[5:7]}.{d[:4]}"
def month_year(d): return f"{MONTHS[int(d[5:7]) - 1]} {d[:4]}"

def compute_stats(a):
    lots = a["lots"]; sold = [l for l in lots if l["status"] == "v"]
    paint = [l for l in sold if l["medium"] in MED_PAINT]
    houses = []
    for l in lots:
        if l["house"] not in houses: houses.append(l["house"])
    houses.sort(key=lambda h: -sum(1 for l in lots if l["house"] == h))
    S = {"name": a["name"], "n_lots": len(lots), "n_sold": len(sold), "n_houses": len(houses),
         "houses": ", ".join(houses)}
    if lots:
        dates = sorted(l["date"] for l in lots)
        S["period"] = f"{month_year(dates[0])} bis {month_year(dates[-1])}"
    base = paint or sold
    if base:
        v = [l["hammer"] for l in base]
        S.update(med_all=de(pct(v, .5)), q1_all=de(pct(v, .25)), q3_all=de(pct(v, .75)), min_all=de(min(v)), max_all=de(max(v)), n_paint=len(base))
        top = max(sold, key=lambda l: l["hammer"])
        S.update(max_hammer=de(top["hammer"]), max_title=top["title"], max_house=top["house"], max_year=top["date"][:4],
                 max_size=(f'{fmt_num(top["h"])} × {fmt_num(top["w"])} cm' if top.get("h") else ""))
        split = a.get("split_year", 2024)
        old = [l["hammer"] for l in base if int(l["date"][:4]) < split]; new = [l["hammer"] for l in base if int(l["date"][:4]) >= split]
        S["years_old"] = f"{min(int(l['date'][:4]) for l in lots)}–{split - 1}"; S["years_new"] = f"{split}–{max(int(l['date'][:4]) for l in lots)}"
        if old: S.update(med_old=de(pct(old, .5)), n_old=len(old))
        if new: S.update(med_new=de(pct(new, .5)), q1_new=de(pct(new, .25)), q3_new=de(pct(new, .75)), n_new=len(new))
        for lab, rng in (("old", lambda y: y < split), ("new", lambda y: y >= split)):
            e = [l for l in sold if l.get("lo") and rng(int(l["date"][:4]))]
            S[f"n_est_{lab}"] = len(e); S[f"below_est_{lab}"] = sum(1 for l in e if l["hammer"] < l["lo"])
        for lab, rng in (("old", lambda y: y < split), ("new", lambda y: y >= split)):
            e = [l for l in sold if l.get("lo") and l["house"] == houses[0] and rng(int(l["date"][:4]))]
            S[f"n_est_{lab}_main"] = len(e); S[f"below_est_{lab}_main"] = sum(1 for l in e if l["hammer"] < l["lo"])
        mb = [l for l in base if l["house"] == houses[0]]
        mo = [l["hammer"] for l in mb if int(l["date"][:4]) < split]; mn = [l["hammer"] for l in mb if int(l["date"][:4]) >= split]
        S["main"] = houses[0]
        if mo: S.update(med_old_main=de(pct(mo, .5)), n_old_main=len(mo))
        if mn: S.update(med_new_main=de(pct(mn, .5)), q1_new_main=de(pct(mn, .25)), q3_new_main=de(pct(mn, .75)), n_new_main=len(mn))
    offered = len(lots); S["sold_rate"] = f"{len(sold)} von {offered}"
    for i, h in enumerate(houses):
        hv = [l["hammer"] for l in base if l["house"] == h]
        S[f"house{i+1}"] = h; S[f"n_house{i+1}"] = sum(1 for l in lots if l["house"] == h)
        if hv: S[f"med_house{i+1}"] = de(pct(hv, .5)); S[f"max_house{i+1}"] = de(max(hv))
    o = a.get("offers")
    if o:
        tot = sum(h[1] for h in o["houses"]); reg = sum(h[1] for h in o["houses"] if h[2])
        S.update(offers_total=tot, offers_region=reg, offers_region_pct=round(reg / tot * 100), offers_houses=len(o["houses"]))
    return S, houses

def fmt_num(x): return str(x).replace(".", ",")

def fill(text, S, where):
    def rep(m):
        k = m.group(1)
        if k not in S: raise BuildError(f"Unbekannter Platzhalter {{{k}}} in {where}")
        return str(S[k])
    return re.sub(r"\{([a-z0-9_]+)\}", rep, text)

def fill_all(obj, S, where="text"):
    if isinstance(obj, str): return fill(obj, S, where)
    if isinstance(obj, list): return [fill_all(x, S, where) for x in obj]
    if isinstance(obj, dict): return {k: (fill_all(v, S, f"{where}.{k}") if k not in ("lots", "offers", "slug") else v) for k, v in obj.items()}
    return obj

def ranges(rows, groups, mx):
    out = []
    pc = lambda v: f"{v / mx * 100:.2f}%"
    for lab, vals, suffix in groups:
        v = sorted(vals); n = len(v)
        if not n: continue
        wh = f'<span class="wh" style="left:{pc(v[0])};width:{pc(max(v[-1] - v[0], mx * 0.004))}"></span>'
        if n >= 3:
            q1, md, q3 = pct(v, .25), pct(v, .5), pct(v, .75)
            bar = wh + f'<span class="box" style="left:{pc(q1)};width:{pc(q3 - q1)}"></span><span class="md" style="left:{pc(md)}"></span>'
            val = f"Median {de(md)}&nbsp;€<small>{de(q1)}–{de(q3)}&nbsp;€</small>"
            aria = f"{lab}: Median {de(md)} Euro, mittlere Hälfte {de(q1)} bis {de(q3)} Euro"
        else:
            bar = wh + "".join(f'<span class="md" style="left:{pc(x)}"></span>' for x in sorted(set(v)))
            ca = "ca. " if suffix else ""
            shown = f"je {ca}{de(v[0])}" if n > 1 and len(set(v)) == 1 else ca + " und ".join(de(x) for x in v)
            val = f'{shown}&nbsp;€<small>Einzelwerte{suffix}</small>'
            aria = f"{lab}: Einzelwerte {' und '.join(de(x) for x in v)} Euro"
        out.append(f'<div class="rr" role="img" aria-label="{html.escape(aria)}"><div class="rl">{html.escape(lab)}<small>n = {n}</small></div><div class="rt">{bar}</div><div class="rv">{val}</div></div>')
    return "\n".join(out)

def axis(mx):
    bs = []
    for i, t in enumerate(ticks_for(mx)):
        stl = f"left:{t / mx * 100:.2f}%" + (";transform:none" if i == 0 else (";transform:translateX(-100%)" if t == mx else ""))
        bs.append(f'<b style="{stl}">{de(t)} €</b>')
    dense = " dense" if mx >= 10000 and len(ticks_for(mx)) >= 5 else ""  # mobil: jede zweite Beschriftung ausblenden
    return f'<div class="rax{dense}"><span></span><div>{"".join(bs)}</div><span></span></div>'

def copyright_line(a):
    d = a.get("death", {}).get("date")
    if not d: return "geschützt (lebender Künstler)"
    y = int(d[:4])
    if y + 70 < datetime.date.today().year: return f"gemeinfrei seit 1. Januar {y + 71}"
    return f"geschützt bis 31. Dezember {y + 70}"

def lifespan(a):
    b = a.get("birth", {}).get("date", "")[:4]; d = a.get("death", {}).get("date", "")[:4]
    return f"{b}–{d}" if d else f"geb. {b}"

def validate(a, path):
    req = ["slug", "name", "status", "birth", "region"]
    for k in req:
        if k not in a: raise BuildError(f"{path}: Feld {k} fehlt")
    if a["status"] not in ("stub", "published"): raise BuildError(f"{path}: status muss stub oder published sein")
    if a["region"] not in ("kueste", "moor", "rhein", "mitte", "alpen"): raise BuildError(f"{path}: region unbekannt")
    if a["status"] == "stub": return
    for k in ["lead", "facts", "headline", "kurz", "figs", "markt", "absatz", "echtheit", "leben", "werkgruppen", "faq", "quellen", "lots", "stand", "marktwert", "absatzmarkt"]:
        if k not in a: raise BuildError(f"{path}: Feld {k} fehlt")
    for k, subs in (("markt", ["preis", "kaeufer"]), ("absatz", ["text", "liquiditaet"]), ("echtheit", ["punkte", "preis_drueckt", "werkverzeichnis"]), ("leben", ["text", "timeline"])):
        for s in subs:
            if not a[k].get(s): raise BuildError(f"{path}: Feld {k}.{s} fehlt oder leer")
    for f in a["faq"]:
        if not (f.get("q") and f.get("a")): raise BuildError(f"{path}: FAQ-Eintrag ohne q oder a")
    for g in a["werkgruppen"]:
        if not (g.get("t") and g.get("d")): raise BuildError(f"{path}: Werkgruppe ohne t oder d")
    if len(a["lots"]) < 5: raise BuildError(f"{path}: weniger als 5 Lose – Seite nicht veröffentlichen, status stub lassen")
    seen = set()
    for i, l in enumerate(a["lots"]):
        for k in ["house", "date", "lot", "title", "tech", "medium", "status", "url"]:
            if k not in l: raise BuildError(f"{path}: Los {i} ohne {k}")
        if l["status"] not in ("v", "u", "n"): raise BuildError(f"{path}: Los {i} status ungültig")
        if l["status"] == "v" and not isinstance(l.get("hammer"), (int, float)): raise BuildError(f"{path}: Los {i} verkauft ohne Zuschlag")
        if l["status"] != "v" and l.get("hammer"): raise BuildError(f"{path}: Los {i} ohne Zuschlag, aber mit hammer")
        if not re.match(r"\d{4}-\d{2}-\d{2}$", l["date"]): raise BuildError(f"{path}: Los {i} Datum nicht JJJJ-MM-TT")
        if l["medium"] not in ("lw", "karton", "papier", "druck", "skulptur", "foto"): raise BuildError(f"{path}: Los {i} medium ungültig")
        if not l["url"].startswith("http"): raise BuildError(f"{path}: Los {i} ohne Quelle")
        key = (l["house"], l["date"], str(l["lot"]))
        if key in seen: raise BuildError(f"{path}: Los {key} doppelt")
        seen.add(key)

def euro_check(a, S, txt_fields):
    """Warnt, wenn im Fließtext Euro-Beträge stehen, die weder in den Losen noch in den Kennzahlen vorkommen."""
    allowed = {de(l["hammer"]) for l in a["lots"] if l.get("hammer")} | {de(l["lo"]) for l in a["lots"] if l.get("lo")} | {de(l["hi"]) for l in a["lots"] if l.get("hi")}
    allowed |= {str(v) for v in S.values()}
    allowed |= set(a.get("euro_ok", []))
    warn = []
    for t in txt_fields:
        for m in re.finditer(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?\s?(?:Mio\.\s?)?€", t):
            if m.group(1) not in allowed and m.group(0).replace("\xa0", " ").strip().rstrip("€").strip() not in allowed:
                warn.append(m.group(0))
    return warn

def strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, list):
        for x in o: yield from strings(x)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k not in ("lots", "offers", "quellen", "slug", "url"): yield from strings(v)

def build_artist(a, env, strict=True):
    S, houses = compute_stats(a)
    A = fill_all(a, S, a["slug"])
    warns = euro_check(a, S, list(strings(A)))
    if warns and strict and not a.get("euro_warn_ok"):
        raise BuildError(f"{a['slug']}: Euro-Beträge ohne Beleg im Text: {sorted(set(warns))} – als Platzhalter schreiben oder in euro_ok begründen")
    lots = sorted(a["lots"], key=lambda l: (l["date"], l["house"], str(l["lot"])))
    hc = {h: (HOUSE_COLORS[i] if i < 4 else "var(--gray)", HOUSE_SHAPES[i] if i < 4 else "circle") for i, h in enumerate(houses)}
    sold = [l for l in lots if l["status"] == "v"]
    paint = [l for l in sold if l["medium"] in MED_PAINT]
    base = paint or sold
    main = houses[0] if houses else None
    split = a.get("split_year", 2024)
    gh = [(h, [l["hammer"] for l in base if l["house"] == h], ", geschätzt" if all(l.get("est_hammer") for l in base if l["house"] == h) and any(l["house"] == h for l in base) else "") for h in houses]
    gh = [g for g in gh if g[1]]
    mx_h = nice_max(max([max(g[1]) for g in gh] or [1000]) * 1.05)
    mb = [l for l in base if l["house"] == main]
    gv = [(f"{S['years_old']}", [l["hammer"] for l in mb if int(l["date"][:4]) < split], ""),
          (f"{S['years_new']}", [l["hammer"] for l in mb if int(l["date"][:4]) >= split], ""),
          ("Öl auf Leinwand", [l["hammer"] for l in sold if l["house"] == main and l["medium"] == "lw"], ""),
          ("Ölstudien auf Karton, Papier, Holz", [l["hammer"] for l in sold if l["house"] == main and l["medium"] == "karton"], ""),
          ("klein, bis 55 cm", [l["hammer"] for l in mb if size_class(l) == "klein"], ""),
          ("mittel, 56–90 cm", [l["hammer"] for l in mb if size_class(l) == "mittel"], ""),
          ("groß, über 90 cm", [l["hammer"] for l in mb if size_class(l) == "gross"], ""),
          ("Papierarbeiten", [l["hammer"] for l in sold if l["house"] == main and l["medium"] == "papier"], ""),
          ("Druckgrafik", [l["hammer"] for l in sold if l["house"] == main and l["medium"] == "druck"], "")]
    gv = [g for g in gv if g[1]]
    mx_v = nice_max(max([max(g[1]) for g in gv] or [1000]) * 1.05)
    rows = []
    for l in lots:
        t = l["title"] + (f" ({l['year']})" if l.get("year") else "")
        size = f'{fmt_num(l["h"])} × {fmt_num(l["w"])}' if l.get("h") else ""
        est = (de(l["lo"]) + ("–" + de(l["hi"]) if l.get("hi") else "")) if l.get("lo") else ""
        rows.append(dict(l, t=t, size=size, est=est, dd=ddmmyyyy(l["date"]),
                         ham=(("ca. " if l.get("est_hammer") else "") + de(l["hammer"]) + ("*" if l.get("est_hammer") else "")) if l["status"] == "v" else ("unverkauft" if l["status"] == "u" else "ohne Zuschlag"),
                         src=l.get("src") or f'{l["house"]}{(" " + str(l["sale"]).split(" ")[0]) if str(l.get("sale", "")).split(" ")[0][:1].isdigit() else ""}, Los {l["lot"]}'))
    data_js = [dict(date=l["date"], house=l["house"], title=r["t"], size=(r["size"] + " cm") if r["size"] else "", est=r["est"], lo=l.get("lo"),
                    hammer=l.get("hammer"), status=l["status"], est_h=bool(l.get("est_hammer")), url=l["url"], sale=str(l.get("sale", "")), lot=str(l["lot"]), tech=l["tech"])
               for l, r in zip(lots, rows)]
    o = a.get("offers")
    offers_html = ""
    if o:
        m = max(h[1] for h in o["houses"])
        offers_html = "\n".join(f'<div class="hb"><span class="hn">{html.escape(n)}</span><span class="ht"><i class="{"nrw" if f else ""}" style="width:{c / m * 100:.1f}%"></i></span><span class="hv">{c}</span></div>' for n, c, f in o["houses"])
    strip = open(f"{GEN}/strips/{a['region']}.svg", encoding="utf-8").read()
    ymax = nice_max(max([l["hammer"] for l in sold] or [1000]) * 1.05)
    ctx = dict(a=A, S=S, lots=rows, houses=[(h, hc[h][0], hc[h][1]) for h in houses], strip=strip,
               ranges_house=ranges(None, gh, mx_h) if len(gh) > 1 else "", axis_house=axis(mx_h) if len(gh) > 1 else "",
               ranges_main=ranges(None, gv, mx_v), axis_main=axis(mx_v), main=main, offers_html=offers_html,
               data_json=json.dumps(data_js, ensure_ascii=False).replace("</", "<\\/"), ymax=ymax, yticks=ticks_for(ymax),
               house_colors=json.dumps({h: hc[h][0] for h in houses}), house_shapes=json.dumps({h: hc[h][1] for h in houses}),
               lifespan=lifespan(a), copyright=copyright_line(a), base=BASE, style=open(f"{GEN}/artist_style.css.part", encoding="utf-8").read(),
               faq_ld=json.dumps([{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in A["faq"]], ensure_ascii=False),
               person_ld=json.dumps({k: v for k, v in {"@type": "Person", "@id": "#kuenstler", "name": a["name"], "birthDate": a["birth"].get("date"), "birthPlace": a["birth"].get("place"),
                                     "deathDate": a.get("death", {}).get("date"), "deathPlace": a.get("death", {}).get("place"), "description": A["lead"], "sameAs": a.get("same_as", [])}.items() if v}, ensure_ascii=False),
               dataset_ld=json.dumps({"@type": "Dataset", "name": f"Auktionsergebnisse {a['name']} ({S.get('period', '')})", "description": f"{S['n_lots']} Lose mit Datum, Haus, Titel, Technik, Maßen, Schätzung und Zuschlag (ohne Aufgeld), je Los mit Link zur Quelle.",
                                      "about": {"@id": "#kuenstler"}, "dateModified": a["stand"]}, ensure_ascii=False))
    return env.get_template("artist.html.j2").render(**ctx), S

def build(check_only=False):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(GEN), autoescape=jinja2.select_autoescape(["j2"]))
    published, errors = [], []
    for p in sorted(glob.glob(f"{DATA}/artists/*.json")):
        if os.path.basename(p).startswith("_"): continue
        try:
            a = json.load(open(p, encoding="utf-8"))
            validate(a, p)
            if a["slug"] in [s["slug"] for s in STATIC]: raise BuildError(f"{p}: slug ist eine statische Seite")
            out = f"{SITE}/kuenstler/{a['slug']}/index.html"
            if a["status"] == "stub":
                page = env.get_template("stub.html.j2").render(a=a, lifespan=lifespan(a), base=BASE)
            else:
                page, S = build_artist(a, env)
                published.append(dict(slug=a["slug"], name=a["name"], dates=lifespan(a), line=fill(a.get("list_line", "{years_new}: Median {med_all} €"), S, "list_line"),
                                      sort=a.get("sort_name", a["name"].split()[-1])))
            if not check_only:
                os.makedirs(os.path.dirname(out), exist_ok=True); open(out, "w", encoding="utf-8").write(page)
        except (BuildError, KeyError, ValueError, jinja2.TemplateError) as e:
            errors.append(f"{os.path.basename(p)}: {type(e).__name__}: {e}")
    if errors:
        print("FEHLER:\n  " + "\n  ".join(errors)); sys.exit(1)
    if check_only:
        print("Prüfung ok:", len(published), "veröffentlichte Künstler"); return
    allp = STATIC + published
    allp.sort(key=lambda x: x["sort"])
    tpl = open(f"{GEN}/home.html", encoding="utf-8").read()
    lis = "\n".join(f'<li><a href="/kuenstler/{x["slug"]}/"><b>{html.escape(x["name"])}</b><span>{html.escape(x["dates"])} · {html.escape(x["line"])}</span></a></li>' for x in allp)
    itemlist = json.dumps({"@type": "ItemList", "name": "Künstler im Marktatlas", "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{BASE}/kuenstler/{x['slug']}/", "name": x["name"]} for i, x in enumerate(allp)]}, ensure_ascii=False)
    n = len(allp)
    out = tpl.replace("{{ARTISTS}}", lis).replace("{{ITEMLIST}}", itemlist).replace("{{COUNT}}", f"{n} Künstler")
    open(f"{SITE}/index.html", "w", encoding="utf-8").write(out)
    for slug, title in (("impressum", "Impressum"), ("datenschutz", "Datenschutz")):
        os.makedirs(f"{SITE}/{slug}", exist_ok=True)
        open(f"{SITE}/{slug}/index.html", "w", encoding="utf-8").write(env.get_template("legal.html.j2").render(title=title, body=open(f"{GEN}/{slug}.html", encoding="utf-8").read(), slug=slug, base=BASE))
    open(f"{SITE}/robots.txt", "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n")
    today = datetime.date.today().isoformat()
    urls = ["/"] + [f"/kuenstler/{x['slug']}/" for x in allp]
    open(f"{SITE}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(f"<url><loc>{BASE}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls) + "\n</urlset>\n")
    print(f"Gebaut: {n} Künstler auf der Startseite ({len(published)} generiert, {len(STATIC)} statisch)")

if __name__ == "__main__":
    build(check_only="--check" in sys.argv)
