# BERNVAPES Website — Papercraft-Welten · Übergabe für Cursor

**Öffnen:** `index.html` doppelklicken (läuft lokal ohne Server). Zweite Seite: `werkstatt.html`.
Alles, was die Seiten brauchen, liegt unter `assets/web/`, `assets/css/site.css`, `assets/js/site.js`.
Der Rest unter `assets/` sind Quelldateien (Roh-Videos, Canva-Exporte, Schnittvorlagen).

---

## Die Idee
Die Fuchsmaske zerspringt — dahinter liegt eine Low-Poly-Papercraft-Welt. Jede Linie hat ihre eigene Welt,
die Tiere *stehen darin*, die Welt bewegt sich mit der Maus (Büsche vorne mehr als Berge hinten), Wind wiegt den
Vordergrund, Wolken driften. Die vier Tiere der neuen Linie leben: beim Hover läuft ihr Loop.

| Welt | Sektion | Tiere | Besonderes |
|---|---|---|---|
| Art-Déco-Sunburst (`worlds/neue.webp`) | `#hero` (gepinnt, 460 vh) | Lemur, Elefant, Chipmunk, Roter Panda | Fuchs-Entrance; Hover-Loops; Klick → Etikette + Flasche |
| Kraftpapier-Wald (`worlds/wald.webp`) | `#quartiere` (260 vh) | 7 Silhouetten | Schalter „On the rocks" tauscht 3 Tiere + kühlt die Welt |
| Alpen in der Dämmerung (`worlds/alpen.webp`) | `#bergtiere` (260 vh) | 9 Kupfer-Köpfe | Schalter „On the rocks" tauscht 3 Tiere |
| Kristallsee (`worlds/ice.webp`) | `werkstatt.html` | 6 Afrika-Konzepte (noch nicht im Sortiment) | plus Skizzenbuch-Studien |

---

## Engine (`assets/js/site.js`)

**`World`** — WebGL-Fragment-Shader auf einem Vollbild-Quad. Uniforms: `m` (Maus −1…1, geglättet), `time`, `zoom`,
`cool` (Eis-Tint 0…1), `dark`. Tiefe = vertikaler Verlauf (oben fern, unten nah):
- Parallaxe `m * (depth-0.38) * 0.024` → Vordergrund wandert mit der Maus, Himmel kaum
- Wind `sin(time*0.9 + x*7) * 0.0032 * depth²` → nur vorne
- Wolkendrift `time * 0.001 * (1-depth)` im oberen Drittel
- Basis-Zoom 1.08, damit an den Rändern nichts aufreisst. Rendert nur, wenn sichtbar (IntersectionObserver).
- Ohne WebGL: Fallback auf `<img>`.
Für mehr „echte" Tiefe später: pro Welt eine Depth-Map statt Verlauf (gleicher Shader, zweite Textur).

**`FoxScrub`** — 86 WebP-Frames mit Alpha (`assets/web/fox/000…085.webp`, 1152×648) auf einem 2D-Canvas, cover-fit.
Scroll-Fortschritt der Hero-Sektion → Frame-Index (geglättet). Darunter liegt die Welt, darum sieht man sie durchs Loch.
Phase A (0–52 %): Maske zerspringt, Welt zoomt 1.0→1.26 („hineinfliegen"), Schwarz blendet weg.
Phase B (52–74 %): Titel + Tiere kommen gestaffelt, Plaketten blitzen 3 s auf.
Mobile (< 900 px): Entrance läuft automatisch in 4,2 s ab, Tiere im 2er-Raster.

**`.beast`** — Tier in der Welt: `left/bottom` in %, `--w` Breite, `--ar` Bildverhältnis, `--d` Parallax-Tiefe (vorne 1.1, hinten 0.5).
`img.still` + optional `img.loop` (animiertes WebP mit Alpha; `data-src` wird erst beim ersten Hover gesetzt → kein Autoplay-Traffic).
Hover: Loop ein, 3D-Tilt, Plakette. `data-ice`/`data-warm` für den On-the-rocks-Tausch. Debug: `window.BV_FORCE_P=0.95` setzt die Hero-Phase fest.

---

## Die Hover-Loops (so entstanden, so weiterbauen)
Tier freigestellt → auf flachen Greenscreen (#00B140) komponiert (1024×1365, Tier auf 86 %) → Kling 3 Omni image2video,
**Start- und Endframe = dasselbe Bild** (nahtloser Loop, 5 s) → lokal per Chroma-Key (G − max(R,B) > 18…60) + Despill nur bei
Grün-Dominanz → 60 Frames à 12 fps → `assets/web/loops/<tier>.webp` (animiert, Alpha) + `.webm` (VP9 Alpha) + `_still.webp`.
Skript-Logik liegt in dieser Session dokumentiert; Rohmaterial unter `assets/video/green_*.mp4`, Frames unter `assets/keyed/`.

---

## Nächste Schritte in Cursor
1. **Komponenten:** `WorldCanvas` (Shader), `FoxEntrance`, `Beast`, `Scene`, `Toggle`, `Lightbox`.
2. **Depth-Maps** pro Welt (mit einem Depth-Estimator aus dem Panorama) → Parallaxe wird räumlich exakt.
3. **Echter 3D-Fuchs** (Three.js/R3F) statt Bildsequenz: `.glb` aus `../fox_reveal.blend`, Loch-aus-der-Mitte per Shader-Clip. Siehe `../Fuchs_Blender_Uebergabe.md`.
4. Shop-/CTA-Ziele, Afrika-Linie aus der Werkstatt in die Hauptseite ziehen, sobald sie produziert wird.
5. Performance: Loops (~2–3 MB je) erst bei Sichtbarkeit laden (ist vorbereitet), Welten als AVIF zusätzlich.

---

## Ordner
```
Web/
├─ index.html · werkstatt.html · README_Cursor.md
└─ assets/
   ├─ css/site.css   js/site.js
   ├─ web/                      ← was die Seiten brauchen
   │  ├─ worlds/   neue · ice · wald · alpen (2400 px WebP)
   │  ├─ fox/      000…085.webp (Alpha-Sequenz)
   │  ├─ loops/    lemur · elefant · chipmunk · panda (.webp animiert, .webm, _still)
   │  ├─ quartiere_cut/  bergtiere_cut/  afrika_cut/   (freigestellte Tiere)
   │  ├─ bottles/  labels/  studies/  quartiere/  bergtiere/  afrika/
   ├─ worlds/ (PNG-Originale) · fox_seq/ (PNG-Alpha-Frames) · video/ (Roh-Videos) · keyed/ (Loop-Frames)
   ├─ cutouts/ · cutout_src/ · afrika_src/ · afrika_labels/ · alte_linien/ · video_frames/
```

---

## Runde 3 (26.10.) — was neu ist
- **Welten sichtbar auch bei `file://`:** Browser blockieren Bilder von der Festplatte in WebGL. Die vier Panoramen liegen darum zusätzlich base64-eingebettet in `assets/js/worlds_data.js` (`window.BV_WORLDS`, Canvas `data-key`). Bei WebGL-Fehler greift ein CSS-Fallback (`.world-css`: ganzes Bild + maskierter Vordergrund, der stärker mitwandert). Auf einem echten Server (Cursor dev server) kann `worlds_data.js` entfallen.
- **Fuchs HD:** `assets/web/fox_hd/` — 86 Frames 1920×1080 mit Alpha, feineres Mesh (9'132 Flächen, Voxel 0.03). Startet 1.42× vergrössert und zoomt beim Aufreissen zurück (`fox.scale`).
- **Eine Flasche für alle:** `assets/bottle_src/bottle_base.png` (freigestellte Leerflasche) + `wrap.py` wickelt jedes Label zylindrisch auf (Winkel 1.06 π, Rundungs-Schattierung, Glanzstreifen). Ergebnis `assets/web/bottles2/<key>.webp` (komplett) und `<key>_label.webp` (nur Label, gleiche Leinwand). Keys: `lemon_pie…`, `q_<quartier>`, `b_<bergtier>`, `a_<afrika>`, `_ice`-Varianten.
- **Label-Schimmer:** `.bottle3 .shine` ist ein Gradient-Sweep mit `mask-image: var(--mask)` = Label-Layer → leuchtet beim Hover nur über dem Label.
- **Zutaten:** 36 Papercraft-Icons in `assets/web/ingredients/` (aus 3 Sammelbildern gekeyt). Zuordnung steht in `index.html` je Gruppe (`.ings`).
- **Gruppen:** `.beast.grp` = Tier (`.art`) + Flasche (`.bottle3`) + Zutaten (`.ings`) + Plakette. Hintere Reihen `.quiet` zeigen die Plakette nur beim Hover.
- **Stills:** scharfe Standbilder aus den HD-Freistellern in exakt der Loop-Geometrie (`web/loops/*_still.webp`), Loops jetzt 720 px breit.

---

## Runde 4 (26.10.) — was neu ist
- **Fuchs = echter Low-Poly:** Original-GLB → Voxel-Remesh 0.02 → Collapse-Decimate auf ~900 Dreiecke mit X-Symmetrie → grosse saubere Facetten (wie das Meshy-Modell), glänzendes Hellgrau, Loch-Modifier + Animation vom alten Fuchs übernommen (Blender 4.5: `animation_data.action_slot` mitkopieren!). Kamera-Shift −0.13, Full HD, 86 Alpha-Frames in `web/fox_hd/`. Start nur noch 1.14× vergrössert.
- **Shader-Drift behoben:** Wolkendrift ist jetzt `sin(time*0.045)` (begrenzt) statt endlos wachsend — das hatte die Welt nach links gezogen und Schlieren erzeugt. Parallaxe/Wind etwas sanfter.
- **Flaschen fotografisch, alle gleich hoch:** `web/bottles3/` — die 4 Original-Mockups der neuen Linie + 16 neu generierte (Quartiere 7, Bergtiere 9, gleiche Prompt-Vorlage, Referenz = Label-Panel) + 6 Afrika, alle per Code freigestellt und auf 1200 px Höhe auf 400×1210-Leinwand normiert. Die zylindrisch gewickelte Variante (`bottles2/`, `bottle_src/wrap.py`) ist verworfen.
- **Gruppen-Layout:** `.duo` = Tier (68 %) | Flasche (27 %) auf einer Standlinie; `.ings` sitzen zu Füssen (links unten). Label-Schimmer: Gradient-Sweep, maskiert mit Flaschen-Alpha ∩ vertikalem Label-Band (26–89 %).
- Debug: `window.BV_FORCE_P` (Hero-Phase), `window.BV_MOBILE_BP` (Breakpoint), `window.BV_TICKS` (Loop-Zähler).

---

## Runde 5 (26.10.) — was neu ist
- **Fenster-Maske im Hero:** Der Fuchs-Canvas zeichnet jetzt pro Frame: Schwarz über alles → Fenster in Fuchs-Silhouette (`web/fox_hd/window.webp`, aus Frame 0) per `destination-out` ausstanzen → Fuchs-Frame obendrauf. Die Welt ist nur dort sichtbar, wo die Maske aufbricht; ab 80 % der Phase A blendet das Schwarz aus (`fox.black`). Alles in derselben Transformation wie der Fuchs, daher deckungsgleich.
- **Einzel-Layer-Parallaxe:** `beastParallax` bewegt jetzt Gruppe, Flasche, Zutaten (und ggf. Ghost) mit *verschiedenen* Faktoren und *gegen* die Maus — konsistent mit dem Welt-Vordergrund. Pro Gruppe leicht andere Tiefe (`v`).
- **Quartiere:** keine Logos mehr; 10 Flaschen (7 + 3 on the rocks, Paare nebeneinander) mit grossen Zutaten zu Füssen; Eiswürfel-Icon markiert OTR. Plaketten nur beim Hover.
- **Bergtiere:** neuer Berg `worlds/berg.webp` (ein naher Low-Poly-Berg ohne Terrassen). 12 Flaschen stehen auf den Facetten, OTR oben im Schnee. Positionen in **Bild-Prozent** (`data-ix`/`data-iy`), `placeOnImage()` rechnet sie passend zur Shader-Abbildung (cover, zoom 1.08, Zentrum 0.5/0.52) auf den Bildschirm um — funktioniert auf jedem Seitenverhältnis. Titel steht links im Himmel (`.title.side`). Kein Schalter mehr.
- 6 OTR-Flaschen neu generiert (`bottles3/q_*_ice`, `b_*_ice`).

---

## Runde 6 (26.10.) — echte Produktfotos
- Quartiere und Bergtiere nutzen jetzt die **echten Produktfotos** aus `bernvapes-neu/app/static/produkte` (600×600 JPG, Kopie in `assets/produkte_src/`), per Code freigestellt und je Linie auf 1200 px Höhe normiert → `assets/web/produkte/*.webp`. 60 ml = schlank (`--bar:0.331`), 100 ml Bergtiere = dick (`--bar:0.342`).
- Quartiere: 8 Sorten + 4 OTR (Hirsch, Eule, Dachs, Falke) inkl. **Felsenau Fuchs**. Bergtiere: 10 Sorten + 3 OTR inkl. **Schnee Hase**. Sortenangaben für Felsenau Fuchs und Schnee Hase sind Platzhalter („Quartier-Sorte"/„Berg-Sorte") — bitte ergänzen (`index.html`, Plakette + `.ings`).
- Die generierten Flaschen in `bottles3/q_*`/`b_*` werden nicht mehr genutzt (neue Linie weiterhin `bottles3/lemon_pie` usw.).

---

## Runde 7 (26.10.) — Entrance-Sequenz
- Fuchs-Frames neu gerendert mit **stehender Kamera** (Pose von Frame 1, Lens 38 mm, Shift −0.13) und Lochradius bis 2.6 → bei Frame 170 ist nichts mehr übrig. Keine Riesen-Scherben mehr.
- Web: Fuchs jetzt `contain` (ganzer Kopf immer sichtbar), Phase A 0–50 % = Auflösen, Phase B 50–72 % = Welt-Zoom 1.0→1.34 + Schwarz blendet aus (die „Kamerafahrt"), Phase C ab 68 % = Tiere.
- Fenster-Silhouette um 3 px nach innen geschrumpft → keine Kontur mehr von Anfang an.

---

## Runde 8 (26.10.) — Material, Bruchstücke, Feinschliff
- **Fuchs-Material:** prozedurales Metall in Blender (Principled, metallic; dunkles Gunmetal + Rost-Noise als Farb-/Rauheits-Mix; Kratzer = zwei Wave-Texturen durch steile Color-Ramps → Bump + Rauheit; Reflexionen aus Blenders `city.exr`). Skript: `assets/fox_seq_lp/_render_lp.py`.
- **Bruchstück-Explosion:** eigener Geometry-Nodes-Baum `ChunkHole`: Voronoi-F1 (Scale 3.2) teilt den Kopf in Zellen, pro Zelle wird die Zellmitte mit dem Lochzentrum verglichen → ganze Zellen (mehrere Dreiecke) springen gemeinsam ab. Radius-Keys 26→0, 90→0.30, 130→0.62, 155→1.05, 170→1.9 (SINE-Interpolation), damit die Explosion über die ganze Sequenz läuft.
- **Vignette im Fenster:** `FoxScrub.draw` legt nach dem Ausstanzen einen radialen Verlauf (Mitte/Stirn klar, Rand dunkel) mit `fox.vignette` darüber; wird ab 45 % der Auflöse-Phase sanft weggeblendet.
- **Kürzerer Scrollweg:** Hero 330 vh (vorher 460). Phase A 0–40 %, Phase B 36–60 % (überlappt → weicher), Tiere ab 58 %. Alle Blenden per smoothstep.
- **Sonne als Papierlaterne:** Shader-Uniforms `sun` (Bild-UV, aus `data-sun="0.49,0.31"` am Canvas) und `glow`. Kern pulsiert (~8 s), warmer Halo, helle Flächen oben (Wolken) werden leicht angestrahlt. Wolken-Drift verdoppelt (begrenzter Sinus).
- **Getrenntes Schweben:** `.art` (floatA 7.5 s) und `.bottle3` (floatB 6.2 s, `top` + leichte Rotation, 9 % höher, −2.6 s Versatz) schweben unabhängig; Gruppe hat weiterhin `idle`.
- **Label-Schimmer** nur noch auf der Flasche: Maske `contain` / `bottom center` (vorher auf 100 %×100 % gestreckt → Schimmer lief in die Umgebung).
- **Hero-Titel:** halbtransparentes dunkles Band mit Gold-Hairlines + Backdrop-Blur, Versalien, zentriert. Liest sich auf jedem Hintergrund.
- Debug: `window.BV_FRAME(now)` ruft den Haupt-Loop manuell auf (für Tests ohne rAF).
- **Runde 8b:** Loch-Zentrum auf der Stirn (`ZF = z0 + 0.50·H` in `_render_lp.py`), Kamera Lens 32 / Shift −0.02 (ganzer Kopf inkl. Ohrspitzen im Bild, ~10 % kleiner), Rost in zwei Lagen (Flächenrost + dunkle Frassstellen mit Relief/matt), Backen-Whiskers per Vertexgruppe geglättet. Labels der 4 neuen Flaschen auf einheitliche Höhe (31–94 %) gebracht (Originale in `bottles3/_orig/`); Flasche in der Gruppe 22 % statt 27 %.
- **Runde 8c — Augen + Feuer:** Loch hat zwei Zentren an den Augen (`Center=(EX,0,ZF)`, gespiegelt per `(-1,1,1)`, Minimum beider Distanzen). Im Web (`FoxScrub.draw`): `fox.glow` = Glut hinter den Augenhöhlen (vor dem Fuchs-Frame gezeichnet, scheint durch die Löcher) + Bloom (`lighter`) darüber; schwillt bei a≈0.02–0.13 an, verglüht bis a≈0.48. `fox.fire`/`fox.fireR` = Feuer-Layer zwischen Maske und Welt: radialer Gold→Orange→Crimson-Verlauf um die Augenmitte, wächst mit dem Loch (`fireR`), 7 wandernde Flammenflecken, Bloom nach aussen; zündet bei a≈0.13, verglüht ab a≈0.62. Augenpositionen in Frame-Koordinaten (1920×1080): (817,768) und (1103,766).
- **Runde 8d:** Loch wieder *ein* Zentrum auf der Stirn zwischen den Augen (`ZF = z0+0.31·H`, x = 0), weniger Zufall (0.10) → rundes Loch, das zu den Aussenkanten wächst; Radius-Keys 26→0, 80→0.16, 120→0.42, 150→0.82, 163→1.25, 170→1.9. Augen glühen weiterhin als Vorbote. Feuer-Bloom über die Maskenkanten erst ab grossem Loch (`fi·ss(fireR)`), Feuer-Radius folgt dem Loch bis a≈0.95. Neue-Linie-Flaschen 7 % breiter (`aspect-ratio:0.355`, `object-fit:fill`, Shine-Maske gestreckt), keine Rotation mehr beim Schweben.
- **Runde 8e:** (1) Sonne: Strahlen glühen jetzt sichtbar wie ein Lampenschirm (Shader: helle Streifen im Himmel × Abstand zur Sonne × Puls, plus langsam wandernder Lichtkranz `sin(ang·5 − t·0.35)`), Kern/Halo kräftiger. (2) **Wolken als eigene Ebene:** 4 generierte Papier-Wolken (`web/clouds/c0–3.webp`, Quelle `clouds_src/clouds.png`, Chroma-gekeyt) in `.hero .clouds`, jede mit eigener Drift (`--dur`, `--amp`, alternate), Sonnen-Puls (`cloudLit` 8.4 s) und ferner Maus-Parallaxe (`--d`). (3) **Bruchstücke fliegen weg:** GN `ChunkHole` setzt jetzt per Zelle die Position (radial + nach oben + Zufall, `t^1.6`), dreht die Stücke (Axis-Angle) und löscht sie erst weit draussen (`t>1.15`); Voronoi wird auf Face-Mitten ausgewertet und die Kanten vorher gesplittet, damit Zellen zusammenbleiben. (4) Fenstermaske viel weicher: `MinFilter 9` + `GaussianBlur 26`. (5) Label-Schimmer ohne Mask-Composite: Maske = nur Flaschen-Alpha, das Label-Band steckt im `::before` (top 30 %, bottom 6 %). (6) Zutaten schweben eigenständig (`floatC`, −1.4 s versetzt).

---

## Runde 9 (27.10.) — Produktfotos sauber, Berg grüner, Dunst, Fuchs-Timing
- **Freistellen neu** (`assets/produkte_src/_key.py`, OpenCV): Hintergrund = nur die mit dem Bildrand verbundene helle Fläche (lum>196, sat<34) → Glanzlichter auf Kappen und weisse OTR-Labels bleiben opak. Flaschenkanten: häufigste Kantenposition über den Körper (Seiten sind gerade) → Lecks nach innen und Schattenreste nach aussen fallen weg; Kappe/Boden behalten ihre Kontur. Weiss-Saum per Unmultiply. Alte Dateien in `web/produkte_old/`. Neue Masse: 60 ml 279×1210 (`--bar:0.231`), 100 ml ~431×1210 (`--bar:0.356`); `--w` entsprechend angepasst.
- **Quartiere:** hintere Reihe versetzt in die Lücken (7/20/34/66/80/93 %), kleiner (4.2 %), leicht abgedunkelt; vordere Reihe 6.6 %. Zutaten enger an der eigenen Flasche (`.ings` 176 %), Standfleck-Schatten pro Gruppe. Hover hebt die Zutaten (+28 %, −22 %).
- **Bergtiere:** neues Panorama `worlds/berg3.png` → `web/worlds/berg.webp` (grüne Alpmatten, Bäume, mehr Facetten-Variation; gleiche Komposition, Positionen unverändert). Kein Schweben mehr (`#bergtiere … animation:none`). **Dunst:** `.mist.back` (z2) und `.mist.front` (z4, 55 %) mit weichen Ellipsen (`screen`, blur 14), ziehen in 85–140 s quer und den Hang hinunter (`mistDrift`). Hover hebt die Zutaten wie in den Quartieren.
- Produktfotos matter: `contrast(.93) brightness(.97) saturate(.94)`.
- **Fuchs:** zwei Fenstermasken — `window.webp` (hart, Stand) und `window_soft.webp` (blur 26) blendet mit `fox.soft` ab a≈0.35 ein. Feuer wird mit `destination-over` **hinter** Schwarz+Fenster gemalt (nur durchs Loch sichtbar), zündet erst bei a≈0.62 (Frame ~105), Bloom nach aussen schwach und erst ab fireR>0.45. Augen funkeln bis a≈0.6. Schwarz hält bis p=0.40, Kamera 0.40–0.62, Tiere ab 0.60. Letzte Reste (Ohrspitzen) werden ab a=0.9 ausgeblendet (`frameAlpha`). Hero-Titel ohne Band (Text mit Schatten).

---

## Runde 10 (27.10.) — OTR-Schalter = Winterwelt, Bern am Horizont
- **Quartiere-Welt neu** (`worlds/wald2.png` → `web/worlds/wald.webp`): gleiche Komposition, am Horizont Eiger-Mönch-Jungfrau, rechts der Münsterturm als Silhouette. **Winter-Version** `worlds/wald_w.png` → `web/worlds/wald_w.webp` (image2image, identische Komposition). **Bergtiere-Winter** `worlds/berg_w.png` → `web/worlds/berg_w.webp`. Alle vier in `js/worlds_data.js` (Keys `wald`, `wald_w`, `berg`, `berg_w`).
- **Schalter** (`button.toggle`, unten rechts): togglet `.cool` auf der Szene. Pro Szene liegt ein zweiter `canvas.world.winter` (eigene `World`-Instanz, Key `<id>_w`) über dem Sommer-Canvas und blendet per Opacity (1.4 s) ein. Flaschen tragen `data-season="s"|"w"`; `.scene.cool` zeigt nur `w`. Quartiere: Sommer 8 (5 vorne 12/30/48/66/84 %, 3 hinten 21/62/75 %), Winter 4 OTR (20/40/60/80 %, 7 %). Bergtiere: Sommer 10 (Positionen wie bisher), Winter 3 OTR auf halber Höhe (ix/iy 33/57, 50/53, 67/57; 6.4 %).
- **Schnee:** `canvas.snow` (z5) mit `Snow`-Klasse in site.js — 70 Flocken, Tiefe über Grösse/Tempo/Alpha, sanftes Pendeln, blendet mit dem Schalter ein/aus. Mobile: Winter-Canvas aus, stattdessen CSS-Filter auf der Sommerwelt.
- Fuchs: Bruchstücke grösser (Voronoi 2.1), Radius-Keys linear (26→0, 60→.22, 100→.55, 135→.95, 158→1.5, 170→2.4), Flugkurve `t^1.3`. **Scroll-Tempo:** `hero._ps` folgt dem echten Scroll zeitbasiert mit max. 18 %/s (Auflöse-Phase dauert min. ~2.2 s), Hero 280 vh.
- Hero-Text: "Wild. Fruchtig. Us Bärn." mit Kontur/Schatten; Plaketten: Lemmy (Lemon Pie · Lemur), Fabantu (Mango Lassi · Elefant), Chippy (Mandarine Nuss · Chipmunk), Pandu (Öpfuchueche · Roter Panda); Plakette unter dem Tier zentriert (`left:34%`).

- **Runde 10b:** Felsenau Fuchs und Schnee Hase sind bis auf Weiteres eingestellt → aus `index.html` entfernt (Fotos bleiben in `web/produkte/`). Quartiere: 7 Sorten (hinten jetzt Kater 24 %, Köter 70 %), Bergtiere: 9 Sorten.
- **Runde 10c:** Freistellen: Kappen oberhalb des Körpers behalten ihre eigene Kontur (100-ml-Kappe ist breiter als der Körper, wurde vorher abgeschnitten). 100 ml jetzt 393×1210 → `--bar:0.325`, `--w` 9 % kleiner. Fuchs-Übergang: `fox.black` wird ab a≈0.74 bis 0.55 durchlässig und mit der Kamerafahrt (f) ganz; Feuer halbtransparent (Welt scheint warm durch), Spitze a≈0.85, verglüht weich über f; Aussen-Bloom skaliert mit der Durchlässigkeit (`fox.spill`).

---

## Runde 11 (27.10.) — Bern im Hintergrund, Bergtiere-Legende, Git
- **Quartiere-Welt:** `worlds/bern.png` (Altstadt am Aare-Ufer: Münster, Bundeshaus-Kuppel, Zytglogge, Brücke, Alpen) → `web/worlds/wald.webp`; Winter `worlds/bern_w.png` → `wald_w.webp`. Titel jetzt links (`.title.side`), damit er das Münster nicht verdeckt.
- **Bergtiere:** Plaketten nur beim Hover (gross, über der Flasche). Links eine **Sortenliste** (`ol.legend`, Sommer/Winter getrennt); Hover/Klick auf einen Eintrag hebt die Flasche (`.hi`) und dimmt die anderen (`.dim`); Hover auf eine Flasche markiert den Listeneintrag (`.hot`). Verteilung neu als Zickzack in drei Höhen (oben 37/41, 50/35, 63/41 · Mitte 37/57, 52/60, 74/56 · unten 39/78, 56/80, 78/76; Winter-OTR 37/58, 54/52, 74/58).
- **Gestaffeltes Einblenden** beim Umschalten: jede Saison-Flasche hat `--i` (von unten nach oben, links nach rechts), `transition-delay: --i × 130 ms`.
- **Tierköpfe:** Varianten A/B für Lemur, Chipmunk, Panda in `assets/heads_src/` (+ `Uebersicht_Koepfe.jpg`) — noch **nicht** eingebaut, nur zum Vergleichen.
- **Git:** Repo in `Web/`, Remote `github.com/ischer187-cmyk/bernvapes-website`, `.gitignore` schliesst .env/Secrets, Render-PNGs, Rohvideos und Testkopien aus.
- **Runde 12b — Texte Berndeutsch:** alle sichtbaren Texte (Nav, Hero, Flaschen-Streifen, Quartiere, Bergtiere inkl. Plaketten/Legende, Werkstatt, Über uns, Footer, werkstatt.html) auf Berndeutsch, frecher. Grundlage: Tonfall der alten bernvapes.ch-Produkttexte (geduzt, Wortspiele mit den Tiernamen, „Garantiert kalorieefrei", „hate it or love it"). Zutaten gemäss alter Seite korrigiert (Dachs: Holunder; Falke: Jasmin + Schwarztee). Gesetzliche Hinweise (18+, Warnhinweis) bleiben Hochdeutsch. Hero-Claim „Dampf us dr Hauptstadt." + Satz mit Parlamänt-Pointe; Bergtiere „Je höcher, desto wiuder." — weitere Varianten werden per Multiple-Choice iteriert.
