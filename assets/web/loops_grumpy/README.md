# Grantige Tiere (neue Linie) – Assets zum Einbauen

Ersetzt die freundlichen Köpfe aus `assets/web/loops/` und die Flaschen aus `assets/web/bottles3/`. Alles transparent (WebP mit Alpha).

| Sorte | Standbild | Hover-Loop (animiert, 5 s, nahtlos) | Flasche 60 ml Chubby |
|---|---|---|---|
| Lemon Pie · Lemmy | `lemur_still.webp` | `lemur.webp` | `flasche_lemon_pie.webp` |
| Mango Lassi · Fabantu | `elefant_still.webp` | `elefant.webp` | `flasche_mango_lassi.webp` |
| Mandarine Nuss · Chippy | `chipmunk_still.webp` | `chipmunk.webp` | `flasche_mandarine_nuss.webp` |
| Öpfuchueche · Pandu | `panda_still.webp` | `panda.webp` | `flasche_apple_pie.webp` |

- Standbild und Loop haben pro Tier **denselben Ausschnitt und dasselbe Seitenverhältnis** → übereinanderlegen, beim Hover vom Standbild auf den Loop umblenden (wie bisher in `index.html`: `img.still` + `img.loop` mit `data-src`).
- Seitenverhältnisse (Breite/Höhe): Lemur 0.929 · Elefant 1.04 · Chipmunk 0.986 · Panda 1.01 → `--ar` in `index.html` anpassen.
- Loops: 600 px breit, 61 Frames, 12 fps. Standbilder ~1300 px.
- Flaschen: 1600 px hoch, Seitenverhältnis ~0.23–0.255.
- Rohmaterial (Originale, Greenscreen-Fassungen, Videos, Skripte `_key.py`, `_loops.py`): `assets/heads_src/grumpy/`.
