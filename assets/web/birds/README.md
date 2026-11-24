# Low-Poly-Papercraft-Vögel (fliegen über die Bereiche)

Drei Vögel, je 4 Flügelschlag-Frames, freigestellt (transparent), alle Frames am Schnabel ausgerichtet, damit der Körper beim Abspielen nicht springt.

| Vogel | Loop (Dauer-Flattern) | Loop mit Gleitphase | Sprite-Strip (4 Frames) | Frame B×H | Tempo |
|---|---|---|---|---|---|
| Schwalbe (blau/creme/rot) | `schwalbe.webp` | `schwalbe_gleiten.webp` | `schwalbe_sprite.webp` | 279×400 | schnell, 70 ms/Frame |
| Alpendohle (schwarz, gelber Schnabel) | `dohle.webp` | `dohle_gleiten.webp` | `dohle_sprite.webp` | 282×400 | mittel, 110 ms/Frame |
| Steinadler (Kupfer/Ocker) | `adler.webp` | `adler_gleiten.webp` | `adler_sprite.webp` | 311×400 | langsam, 150 ms/Frame |

`*_f1..f4.png` = Einzelframes (Flügel oben → waagrecht → unten → halb oben).
Alle Vögel schauen nach **rechts**. Für Flug nach links: `transform: scaleX(-1)`.

## Einbau-Idee (am flexibelsten: Sprite-Strip, Tempo per CSS steuerbar)

```html
<div class="bird bird--schwalbe" style="--y:18vh; --dur:14s; --delay:2s; --size:56px"></div>
<div class="bird bird--adler"    style="--y:8vh;  --dur:30s; --delay:6s; --size:110px"></div>
<div class="bird bird--dohle bird--rtl" style="--y:30vh; --dur:20s; --delay:0s; --size:70px"></div>
```

```css
.bird{position:absolute;left:0;top:var(--y);height:var(--size);aspect-ratio:var(--ar);
  background:var(--img) 0 0/400% 100% no-repeat;pointer-events:none;z-index:3;
  animation:bird-flap var(--flap) steps(4) infinite,
            bird-fly var(--dur) linear var(--delay) infinite;}
.bird--schwalbe{--img:url(../web/birds/schwalbe_sprite.webp);--ar:.698;--flap:.28s}
.bird--dohle   {--img:url(../web/birds/dohle_sprite.webp);   --ar:.705;--flap:.44s}
.bird--adler   {--img:url(../web/birds/adler_sprite.webp);   --ar:.777;--flap:.6s}
@keyframes bird-flap{to{background-position:133.333% 0}}   /* 4 Frames */
@keyframes bird-fly{
  0%  {transform:translate(-15vw,0)}
  50% {transform:translate(50vw,-3vh)}
  100%{transform:translate(115vw,1vh)}}
.bird--rtl{scale:-1 1;animation-direction:normal,reverse}
@media (prefers-reduced-motion:reduce){.bird{animation:none;display:none}}
```

Tipps:
- Pro Bereich 1–3 Vögel, unterschiedliche `--dur`/`--delay`, damit es nicht synchron wirkt.
- Schwalben klein und schnell und gern zu zweit oder dritt; der Adler gross und langsam, am besten über dem Berg-Bereich; die Dohlen passen zu Fels und Gipfel.
- Für eine Gleitphase statt Dauer-Flattern einfach `<img src="…_gleiten.webp">` nehmen (2 Schläge, dann gleiten).
- Rohmaterial + Skript: `assets/heads_src/birds/` (`_birds.py`).

## Austausch auf der Website (Stand 24.11.)

Die Website nutzt nur die Sprite-Strips: `schwalbe_sprite.webp`, `dohle_sprite.webp`, `adler_sprite.webp`.
**Adler bleibt**: die Website nimmt ihn aus `assets/web/birds_fix/adler_sprite.webp` (abgenommen, nicht ersetzen); `birds/adler_sprite.webp` wird von der Website nicht mehr benutzt.
Neue Schwalbe/Dohle: Datei gleichen Namens ersetzen (4 Frames nebeneinander, gleich breit, Blick nach rechts, transparent),
dann `python3 scripts/cachebust.py`. Das Seitenverhältnis liest `assets/js/birds.js` selbst aus der Datei.
Flugbahnen/Anzahl: `CFG` in `assets/js/birds.js`. Im Intro (Hero) fliegen bewusst keine Vögel.
