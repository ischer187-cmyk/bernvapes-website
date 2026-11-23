# Charisma-Varianten, Logo-Embleme, verspielte Details

Alles freigestellt (WebP mit Alpha). Übersicht: `assets/heads_src/charisma/Uebersicht_Charisma_Embleme_Details.jpg`.

## assets/web/charisma/ – neue Linie, frecher statt grantig (Panda bleibt wie in loops_grumpy)
- `lemur_a/_b`, `elefant_a/_b`, `chipmunk_a/_b` – gleicher Stil/Ausschnitt wie loops_grumpy, nur Ausdruck charmanter. Noch **ohne** Hover-Loop.
- `emblem_lemur|elefant|chipmunk|panda` – die vier Tiere als Emblem im Stil der alten Quartier-/Bergtier-Logos (nur Kopf, Kupferfacetten).

## assets/web/details/ – Easter Eggs für die Welten
- `detail_steinbock_logo.webp` – Original-Steinschlag-Bock-Logo lugt über einen Bergkamm (Unterkante gerade → an einen Grat setzen, per CSS von unten hochschieben).
- `detail_wolf_wolke_logo.webp` – Original-Nebel-Wolf-Logo schaut aus einer Papierwolke.
- `*_v1.webp` – freiere Varianten (nicht logo-treu).

Idee Animation: alle 20–40 s per `transform: translateY()` kurz hochfahren/abtauchen, Wolke mitdriften lassen.

## Fix
- `assets/web/loops_grumpy/flasche_lemon_pie.webp` – Etikett reicht jetzt gleich weit nach unten wie bei den anderen drei.
