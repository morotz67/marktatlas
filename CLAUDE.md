# Marktatlas – Arbeitsanweisung für automatische Läufe

Marktatlas (https://marktatlas.netlify.app) ist eine sachliche Informationsseite zu deutschen Künstlern: Auktionsergebnisse mit Quelle, Marktwert, bester Absatzmarkt, Echtheitsmerkmale, Werk und Leben. Betreiber ist Moritz, ein Kunsthändler in Köln. Jeder Push auf `main` wird von Netlify automatisch veröffentlicht (`netlify.toml`, Ordner `site/`).

Ein Lauf baut **eine** neue Künstlerseite (bei viel Restzeit eine zweite) und veröffentlicht sie. Arbeite ohne Rückfragen; niemand schaut zu.

## Grundsätze (nicht verhandelbar)

- **Nur belegte Zahlen.** Jeder Zuschlag stammt von einer Losseite oder Ergebnisliste, deren URL im Los steht. Nichts schätzen, runden oder aus dem Gedächtnis ergänzen. Lieber weniger Lose als ein unbelegtes.
- **Sachlich, nicht werbend.** Keine Kaufempfehlungen, keine Superlative ohne Zahl, keine Prognosen. Schwache Märkte so beschreiben, wie sie sind.
- **Eigener Bestand offenlegen.** Bei Einträgen mit `"eigener_bestand": true` in der Queue (Karl Raupp, Heinrich Nauen) setzt du in der Künstlerdatei das Feld `eigener_bestand`: „Der Betreiber von Marktatlas besitzt ein Werk von <Name> und könnte es verkaufen. Alle Zahlen auf dieser Seite stammen aus den verlinkten Auktionsergebnissen.“ Diese Seiten werden genauso nüchtern geschrieben wie alle anderen.
- **Keine Abbildungen von Werken.** Bis die Bildrechte geklärt sind, nutzt jede Seite nur die Regionsillustration.
- **robots.txt und Sperren respektieren.** Wenn ein Abruf abgelehnt wird, nicht umgehen (kein curl, kein Cache, kein Spiegel); andere Quelle nehmen.
- **Nicht anfassen:** `site/kuenstler/max-clarenbach/` (handgebaut), `generator/impressum.html`, `generator/datenschutz.html`, `site/impressum/`, `site/datenschutz/` (nur der Generator schreibt diese aus den Vorlagen).

## Ablauf eines Laufs

1. `git pull --rebase`. `pip install jinja2 playwright --break-system-packages -q` falls nötig.
2. **Künstler wählen und reservieren.** In `data/queue.json` den ersten Eintrag nehmen mit `status: "open"` oder `status: "claimed"` und `claimed_at` älter als 3 Stunden. Setze `status: "claimed"`, `claimed_at` (ISO-Zeit, UTC). Sofort committen und pushen (`claim: <slug>`). Schlägt der Push wegen eines Konflikts fehl: `git pull --rebase`, prüfen, ob ein anderer Lauf denselben Künstler genommen hat, dann den nächsten freien wählen.
3. **Recherchieren** (siehe unten) und `data/artists/<slug>.json` schreiben. Vorlage mit allen Feldern: `generator/tests/beispiel.json`.
4. **Bauen und prüfen:**
   - `python3 generator/selftest.py` (Generator intakt?)
   - `python3 generator/build.py` – bricht ab bei fehlenden Feldern, falschen Losen oder Euro-Beträgen im Text ohne Beleg.
   - `python3 generator/check_page.py site/kuenstler/<slug>/index.html /tmp/shots` und die Bilder `mobil.png`, `mobil_voll.png`, `desktop_voll.png`, `dunkel.png` mit dem Read-Werkzeug ansehen. Mobil zuerst: nichts darf überlaufen, abgeschnitten oder überlappt sein.
   - Jeden Satz mit Zahl gegen die Daten lesen.
5. **Abschließen.** In der Queue `status: "done"`, `done_at`, `lots: <Anzahl>`. Eine Zeile in `data/log.md` anhängen (Datum, Künstler, Lose, Häuser, Auffälligkeiten). Commit `künstler: <Name>` und push. Danach ist die Seite in ein bis zwei Minuten live.
6. Findest du **weniger als 5 belegte Lose**, keine Seite veröffentlichen: Queue `status: "zu_wenig_daten"` mit `note`, Log-Zeile, push, nächsten Künstler nehmen.
7. Bricht etwas ab, das du nicht lösen kannst: Queue `status: "fehler"` mit `note`, Log-Zeile, push. Nie halbfertige Seiten mit `status: "published"` hinterlassen.

## Recherche

**Lose (Kern der Seite).** Ziel 20–60 Lose der letzten fünf Jahre, Gemälde zuerst. Quellen in dieser Reihenfolge:
- Van Ham: `https://www.van-ham.com/en/artist/<name>.html` (Künstlerliste mit Seiten, Losdetail mit Datum). Deutsche Seiten und PDFs sind per robots.txt gesperrt – nicht verwenden.
- Lempertz: `https://www.lempertz.com/en/catalogues/lot/<auktion>/<los>-<name>.html`; Künstlerseiten unter lempertz.com.
- Ketterer, Grisebach, Karl & Faber, Neumeister, Nagel, Dorotheum, Hargesheimer, Stahl – je nach Künstler.
- Für Spitzenkünstler zusätzlich Christie's, Sotheby's, Phillips (nur Ergebnisse mit Losseite).

**Zuschlag statt Preis mit Aufgeld.** Gespeichert wird der Hammerpreis. Veröffentlicht ein Haus nur den Preis mit Aufgeld, rechne mit dem Aufgeldsatz des Hauses **zum Auktionsdatum** zurück (AGB/Konditionen nachsehen) und nenne den Satz in `methodik_extra`. Bekannt: Van Ham ÷ 1,32 (auch 2021, die Website rechnet alte Lose mit 32 %), Lempertz ÷ 1,26 (2021: ÷ 1,25); das Ergebnis ist meist eine runde Zahl – ist es das nicht, stimmt der Satz nicht. Gestaffelte Aufgelder (Christie's, Sotheby's, Ketterer) nach Staffel zurückrechnen. Ist der Zuschlag nur ungefähr bestimmbar (gerundete Preise, unklare Staffel), `"est_hammer": true` setzen.

**Los-Felder:** `house` (kurzer Hausname, einheitlich), `date` (JJJJ-MM-TT), `sale`, `lot`, `title`, `year` (optional), `tech` (wie im Katalog, deutsch), `medium` (`lw` Öl/Acryl auf Leinwand · `karton` Ölstudie auf Karton/Papier/Holz · `papier` Aquarell, Zeichnung, Gouache · `druck` Druckgrafik · `skulptur` · `foto`), `h`, `w` (cm), `lo`, `hi` (Schätzung), `hammer`, `status` (`v` verkauft, `u` vom Haus als unverkauft gemeldet, `n` ohne Ergebnis in der Liste), `url` (Losseite), optional `est_hammer`, `note`.

**Biografie und Fakten:** Wikipedia (de), Deutsche Biographie/DNB, Museumsseiten. Lebensdaten mit Ort. `same_as` mit Wikipedia/Wikidata/GND-Links.

**Absatzmarkt (`offers`, optional):** Angebote der letzten rund zehn Monate nach Haus zählen (z. B. Invaluable-Künstlerseite, falls abrufbar), dritter Wert `true` für Häuser in der Kernregion. Ohne verlässliche Zählung `offers` weglassen und keine Kennzahl dazu im Text verwenden.

**Ort auf der Karte der Startseite (`ort`):** Haupt-Wirkungsort, genau ein Name aus `PLACES` in `generator/build.py` (z. B. Düsseldorf, Hamburg, Worpswede, Berlin, Dresden, München, Chiemsee). Fehlt der Ort dort, mit Breite, Länge und Seite des Namens (`r`/`l`) ergänzen; liegen zwei Orte sehr nah beieinander, den kleineren Ort mit `l` beschriften oder den größeren Nachbarort nehmen. Danach die Startseite mobil prüfen (`check_page.py site/index.html`), ob Namen auf der Karte überlappen.

**Region der Illustration (`region`):** `kueste` (Ostsee, Nordsee, Ahrenshoop, Hiddensee, Sylt) · `moor` (Worpswede, Bremen, Hamburg, Norddeutschland) · `rhein` (Düsseldorf, Köln, Rheinland, Ruhr, Westfalen) · `mitte` (Dresden, Leipzig, Berlin, Weimar, Sachsen, Thüringen, Hessen) · `alpen` (München, Murnau, Bayern, Stuttgart, Karlsruhe, Südwesten). Nach Haupt-Wirkungsort.

## Texte

- Deutsch, zugänglich, kurze Sätze, keine Fachsprache ohne Erklärung. Gedankenstriche sparsam.
- **Euro-Beträge im Text als Platzhalter**, damit sie zu den Daten passen: `{max_hammer}`, `{med_new_main}`, `{q1_new_main}`–`{q3_new_main}`, `{med_old_main}`, `{years_old}`, `{years_new}`, `{main}`, `{sold_rate}`, `{period}`, `{n_lots}`, `{below_est_new_main}` von `{n_est_new_main}`, `{offers_region_pct}` usw. (vollständige Liste: `compute_stats` in `generator/build.py`). Beträge, die nicht aus den Losen kommen (z. B. ältere Rekorde mit Aufgeld), in `euro_ok` eintragen und in `quellen` belegen.
- `split_year`: Jahr, ab dem die Zeit „jetzt“ zählt (Standard 2024). So wählen, dass beide Hälften genug Lose haben.
- `figs`: vier Kennzahlen, `list_line`: eine Zeile für die Startseite (z. B. „Brücke-Expressionist · Zuschlag meist {q1_new_main}–{q3_new_main} €“).
- `echtheit`: konkrete Merkmale dieses Künstlers (Signatur, typische Rückseiten, Druckgrafik vs. Unikat, Werkverzeichnis und wer Expertisen ausstellt, bekannte Fälschungsfälle nur mit Quelle).
- `faq`: 4–6 Fragen, die Käufer und Erben wirklich stellen.

## Dateien

- `data/queue.json` – Reihenfolge und Status aller Künstler (Welle 1 Watchlist zuerst).
- `data/artists/<slug>.json` – eine Datei je Künstler; `status: "stub"` = Platzhalterseite (noindex, nicht auf der Startseite), `"published"` = volle Seite.
- `generator/` – `build.py`, Templates (`artist.html.j2`, `stub.html.j2`, `legal.html.j2`), Startseite `home.html`, Illustrationen `strips/`, Prüfskripte.
- `site/` – fertige Website, wird committet und von Netlify ausgeliefert. Nie von Hand ändern, immer über `build.py`.
- `data/log.md` – eine Zeile pro Lauf.
