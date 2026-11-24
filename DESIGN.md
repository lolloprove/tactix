# Tactix — Design System

Fonte di verità per UI e data-viz. Derivato da `design-refs/` (`screen.png`, `screen1.png`, `code.html`, `code1.html`, `DESIGN.md` originale). Dove i riferimenti divergono, vale quanto scritto qui.

**Carattere:** editoriale-clinico. Nero assoluto, bianco ottico, linee hairline da 1px, tipografia neo-grotesk stretta. Il colore non decora mai: è telemetria. Un dato, un colore, un significato.

**Vietato:** gradienti decorativi (viola/blu o altro), ombre, blur, glassmorphism, angoli arrotondati, badge ridondanti, layout "AI dashboard" a card colorate, icone decorative, zebra striping.

---

## 1. Palette (HEX esatti)

I token sono dichiarati in `src/app/globals.css` (`@theme`) e diventano utility Tailwind (`bg-canvas`, `text-ink-2`, `border-line`, `text-edge`, …).

### Superfici

| Token | HEX | Uso |
|---|---|---|
| `canvas` | `#000000` | Sfondo pagina. Mai sostituirlo con un grigio. |
| `inset` | `#0A0A0A` | Campo tattico, input, drawer/overlay (opachi, mai traslucidi). |
| `raised` | `#111111` | Modulo che necessita separazione tonale (es. contenitore foto). |
| `hover` | `#1A1A1A` | Hover/active di righe, celle, bottoni secondari. |

### Testo

| Token | HEX | Equivalente | Uso |
|---|---|---|---|
| `ink` | `#FFFFFF` | — | Titoli, numeri primari, label enfatizzate. |
| `ink-2` | `#E5E5E5` | — | Paragrafi editoriali lunghi (lead). |
| `ink-3` | `#888888` | ≈ white 53% | Testo secondario, label, didascalie, assi. Contrasto 5.9:1 su `#000`. |
| `ink-4` | `#616161` | white 38% | Metadati non essenziali (timestamp, indici). Solo ≥ 11px uppercase o decorativo. |
| `ink-5` | `#4D4D4D` | white 30% | Placeholder input, tick disabilitati. |

### Linee

| Token | HEX su `#000` | RGBA | Uso |
|---|---|---|---|
| `line-soft` | `#141414` | `rgba(255,255,255,0.08)` | Divisori interni a liste, griglie dei grafici. |
| `line` | `#1F1F1F` | `rgba(255,255,255,0.12)` | Hairline strutturale standard (bordi card, tabelle, campo). |
| `line-strong` | `#333333` | `rgba(255,255,255,0.20)` | Intestazioni di sezione, separatori editoriali. |
| `pitch-line` | `#2E2E2E` | `rgba(255,255,255,0.18)` | Linee del campo da gioco. |

Usare le RGBA quando l'elemento può stare su `inset`/`raised`; gli HEX solo su `canvas`.

### Semantica (gli unici tre colori cromatici ammessi)

| Token | HEX | Significato | Mai usare per |
|---|---|---|---|
| `edge` | `#10B981` | **Vantaggio / edge positivo**: delta favorevole, mismatch a favore, sovra-performance, stato attivo. | Decorazione, link generici. |
| `vuln` | `#F43F5E` | **Vulnerabilità / delta negativo**: zona di sofferenza, mismatch sfavorevole, sotto-performance. | Errori di sistema generici (usare `ink`+testo). |
| `shift` | `#38BDF8` | **Cambio tattico**: modulo diverso dal baseline, riassetto in partita, dato "nuovo vs storico". | Positivo/negativo (è neutro). |

Varianti consentite (solo per riempimenti di zone/aree nei grafici e per i chip selezionati), sempre come opacità del colore pieno, **mai come gradiente lineare**:

| Step | Opacità | Uso |
|---|---|---|
| `/12` | 0.12 | Fill area radar, zona a bassa intensità |
| `/24` | 0.24 | Zona media |
| `/40` | 0.40 | Zona alta |
| `/56` | 0.56 | Zona critica (max) |

### Regola di polarità (fondamentale)

Il colore codifica sempre **il punto di vista del soggetto della vista**, non il segno aritmetico:

| Metrica | Delta `+` | Delta `−` |
|---|---|---|
| `xg_delta`, `rating_delta`, `dribbles_delta` (attaccante), `duels_delta` | `edge` | `vuln` |
| `xga_delta`, `dribbles_conceded_delta`, `dribbles_past` | `vuln` | `edge` |
| `ppda` (più basso = pressing più intenso) | contesto: neutro `ink-3` | contesto: neutro `ink-3` |

- Pagina squadra / "Come batterla": le debolezze della squadra sono `vuln`.
- Pagina partita: un edge della squadra A è `edge` e si ancora visivamente al lato di A; la stessa informazione non viene ripetuta in `vuln` sul lato B.
- Il segno è **sempre stampato** (`+0.42`, `−0.19`): il colore non è mai l'unico veicolo dell'informazione.
- Delta entro ±0.05 (o ±1% per percentuali) = neutro `ink-3`.

---

## 2. Tipografia

- **Sans:** `Inter` (via `next/font`, variabile `--font-inter`), fallback `"Helvetica Neue", Helvetica, Arial, sans-serif`. Inter sostituisce l'Helvetica dei riferimenti per avere metriche identiche su tutte le piattaforme.
- **Mono:** `Geist Mono` (via `next/font`, variabile `--font-geist-mono`), fallback `ui-monospace, SFMono-Regular, Menlo, monospace`.
- **Numeri:** ogni valore numerico in tabelle, badge, KPI, assi e tooltip usa `font-mono tabular-nums` (`font-feature-settings: "tnum" 1, "zero" 1`). Nessuna eccezione.
- **Pesi ammessi:** 400, 500, 600. Il 500 è il peso dei titoli (come nei riferimenti). Mai light/thin, mai 800+.
- **Tracking:** display/headline stretti (negativi); label maiuscole larghe (+0.08em / +0.10em).

### Scala

| Token | Font | Size / Line-height | Peso | Tracking | Uso |
|---|---|---|---|---|---|
| `display-xl` | sans | 112 / 103 (0.92) | 500 | −0.04em | Hero (nome giocatore, claim). Tablet 90px, mobile 64px. |
| `display-lg` | sans | 72 / 72 | 500 | −0.03em | Titolo pagina squadra/partita. Mobile 40/44. |
| `headline-lg` | sans | 36 / 40 | 500 | −0.03em | Titoli di sezione editoriale. Mobile 28/32. |
| `headline-md` | sans | 24 / 28 | 500 | −0.02em | Titoli modulo. |
| `headline-sm` | sans | 15 / 20 | 500 | −0.01em | Sottotitolo modulo (sotto la label). |
| `lead` | sans | 21 / 34 | 400 | 0 | Sintesi tattica editoriale (`ink-2`). Mobile 18/29. Max 62ch. |
| `body-lg` | sans | 15 / 22 | 400 | 0 | Righe di lista, testo corrente. |
| `body-md` | sans | 13 / 18 | 400 | 0 | Testo denso, insight di zona. |
| `caption` | sans | 12 / 16 | 400 | 0 | Descrizioni secondarie (`ink-3`), nav, footer. |
| `label` | mono | 11 / 12 | 500 | +0.08em, MAIUSCOLO | Micro-label di KPI e intestazioni di colonna (`ink-3`). |
| `label-sm` | mono | 10 / 12 | 500 | +0.10em, MAIUSCOLO | Tick dei grafici, chip. |
| `stat-xl` | mono | 48 / 48 | 500 | −0.03em | KPI eroe (una per modulo). |
| `stat-lg` | mono | 26 / 28 | 500 | −0.02em | KPI in ribbon (come i 4 KPI di `screen1.png`). |
| `stat-md` | mono | 16 / 20 | 500 | 0 | Valori in liste e tabelle. |
| `stat-sm` | mono | 11 / 12 | 500 | 0 | Delta sotto i valori, percentili. |

Unità accanto a un numero: stesso baseline, `caption` o 14px `ink-3`, peso 400 (es. `11.8` `km`).

### Formattazione numeri

- Separatore decimale `.` (convenzione statistica dei riferimenti), migliaia senza separatore sotto 10 000.
- xG/xA/xGA: 2 decimali. Rating: 1 decimale. PPDA: 1 decimale. Percentuali: 1 decimale + `%`. Minuti: intero + `′` (es. `312′`). Partite: intero + ` P`.
- Delta sempre con segno; il meno è U+2212 `−` (stessa larghezza del `+` in mono).
- Dato mancante: `—` in `ink-4` e, a livello di modulo, lo stato esplicito **"Dati insufficienti"**. Mai `0` al posto di `null`.

---

## 3. Spaziatura e layout

- **Base 4px.** Scala ammessa: `4, 8, 12, 16, 24, 32, 48, 64, 96, 144` px. Niente valori fuori scala.
- Label → valore: 4px. Valore → delta: 4px. Righe di lista: padding verticale 16px. Padding card: 16px (denso) o 24px.
- Distanza tra sezioni editoriali: 96px mobile, 128–144px desktop, separate da hairline `line`.
- **Margini pagina:** 16px (< 640), 32px (640–1023), 56px (≥ 1024). Larghezza massima contenuto: 1400px, centrato.
- **Griglia:** 12 colonne desktop (gap 48px nelle sezioni editoriali), 6 tablet, 1–2 mobile. Nelle griglie dati il gutter è la hairline da 1px stessa (celle adiacenti con `border` condiviso).
- **Header:** 12px `caption`, tre zone (logo 1/4, nav centrata 2/4, CTA 1/4), padding top 32–40px. Link: bianco, hover underline 1px con offset 4px.
- **Mobile:** le tabelle dense diventano liste verticali (etichetta a sinistra, valore mono a destra) separate da hairline. Il campo tattico resta verticale e a tutta larghezza.

---

## 4. Bordi, forme, profondità

- **Raggio: 0px ovunque** (bottoni, card, chip, input, tooltip, campo). Unica eccezione: marker di dati circolari nei grafici e il dot di stato (6px).
- **Bordi:** 1px. Default `line`; focus/selezione → `ink` (#FFFFFF) o `edge`, transizione istantanea, nessun glow.
- **Profondità:** solo tonale. Nessuna ombra. Overlay e drawer: sfondo `inset` pieno + bordo 1px `ink`.
- **Motion:** fade-in di pagina 600ms `cubic-bezier(0.16, 1, 0.3, 1)`; hover righe 0ms; link 200ms su opacità. Con `prefers-reduced-motion` tutto a 0ms.

### Componenti base

- **Bottone primario:** fill `ink`, testo `canvas`, `label`, h 40px, px 20px. Hover: fill `edge`.
- **Bottone secondario:** trasparente, bordo `line`, testo `ink`. Hover: bordo `ink`. Active: `hover`.
- **Chip/badge:** h 24px, px 8px, `label-sm`, bordo 1px, **nessun fill** (eccezione: stato selezionato `/12`). Default bordo `line` + `ink-3`; positivo bordo+testo `edge`; critico `vuln`; cambio tattico `shift`. Niente dot pulsanti.
- **KPI card:** bordo `line` sui 4 lati, `label` in alto, `stat-xl`/`stat-lg` al centro, delta `stat-sm` colorato in basso.
- **Tabelle:** righe separate da `line` in basso, header in `label`, hover riga `raised` (0ms), valori allineati a destra in mono.
- **Liste "Punti di forza / Vulnerabilità":** due colonne, header con dot 6px e `label` colorato (`edge` / `vuln`) su hairline `line-strong`; riga = titolo `body-lg` + descrizione `caption`, a destra valore `stat-md` + delta `stat-sm`.

---

## 5. Stati di dato e confidenza

Ogni statistica condizionata espone campione e confidenza (`confidence`: `low` < 270′ / < 3 P, `medium` 270–540′ / 3–6 P, `high` > 540′ / > 6 P).

| Confidenza | Trattamento visivo |
|---|---|
| `high` | Tratti e fill pieni. Nessun avviso. |
| `medium` | Tratti pieni, chip `MEDIA` in `ink-3`. |
| `low` | Tratto tratteggiato `2 2`, fill dimezzato, chip `BASSA CONFIDENZA` in `ink-3`. Mai in posizione eroe. |
| `null` (delta mancante) | Nessuna geometria. Testo "Dati insufficienti" (`body-md`, `ink-3`) + campione stampato. |

Il campione si stampa sempre accanto al valore, in `stat-sm` `ink-4`: `N 312′` oppure `N 4 P`.

---

## 6. Standard grafici SVG

### Principi

1. SVG puri (componenti custom) per campo, corridoi, zone, frecce di mismatch; Recharts solo per grafici cartesiani/radar standard.
2. `viewBox` sempre definito, larghezza fluida (`width="100%"`), altezza da `aspect-ratio`. Leggibile a 360px.
3. `vector-effect="non-scaling-stroke"` su ogni tratto: le hairline restano 1px a qualunque scala.
4. Nessun filtro, ombra, blur, gradiente lineare. Unica concessione: heatmap KDE con `radialGradient` **monocromatico** di un solo token semantico.
5. Accessibilità: `role="img"`, `<title>` e `aria-label` con la sintesi del dato; il segno e il valore sono sempre testo, non solo colore.
6. Animazioni dei grafici disattivate (`isAnimationActive={false}`) o ≤ 300ms ease-out.

### Sistema di coordinate (allineato al DB)

Tutte le coordinate in tabella sono `0–100`, **dal punto di vista della squadra della riga**:

- `x` = larghezza (0 = fascia sinistra, 100 = fascia destra, guardando verso la porta avversaria).
- `y` = profondità (0 = propria linea di porta, 100 = porta avversaria). `avg_def_line_y` usa lo stesso asse.

Campo **verticale** di default (mobile-first), attacco verso l'alto, `viewBox="0 0 68 105"` (metri reali):

```
px = x * 0.68
py = (100 - y) * 1.05
```

Variante orizzontale per desktop wide: `viewBox="0 0 105 68"`, `px = y * 1.05`, `py = x * 0.68` (attacco verso destra).

### Campo

- Fondo `inset` (#0A0A0A), bordo esterno `line`, linee `pitch-line` 1px, nessuna striscia d'erba.
- Area di rigore 40.32 × 16.5 m, area piccola 18.32 × 5.5 m, cerchio centrale r 9.15 m, dischetto e centro r 0.3 m pieno `pitch-line`.
- Indicatore direzione d'attacco: freccia 1px `ink-4` + `label-sm` "DIREZIONE D'ATTACCO".

### Corridoi (`zone_corridor`)

Cinque fasce verticali uguali su `x`: `left` [0,20), `left_half` [20,40), `center` [40,60), `right_half` [60,80), `right` [80,100]. Separatori tratteggiati `line-soft` `3 3`. Il bias d'attacco (`attack_bias_*`, somma 100) si disegna come barre orizzontali sopra la trequarti, percentuale in `stat-sm`.

### Zone di sofferenza (`xga_zones_json.shot_zones`)

Griglia fissa nella metà campo difensiva della squadra (coordinate della squadra che difende):

| Zona | x | y |
|---|---|---|
| `six_yard` | 36.5–63.5 | 0–5.2 |
| `box_left` | 20.4–36.5 | 0–15.7 |
| `box_center` | 36.5–63.5 | 5.2–15.7 |
| `box_right` | 63.5–79.6 | 0–15.7 |
| `edge_left` | 0–36.5 | 15.7–26 |
| `edge_center` | 36.5–63.5 | 15.7–26 |
| `edge_right` | 63.5–100 | 15.7–26 |
| `long_range` | resto | > 26 |

Fill `vuln` quantizzato sui 4 step di opacità in base alla quota di xGA (`< 10%` → `/12`, `10–20%` → `/24`, `20–35%` → `/40`, `> 35%` → `/56`), bordo 1px `vuln` solo sulla zona peggiore. Valore xGA in `stat-sm` dentro la zona. `origin_corridors` (sinistra/centro/destra, nel riferimento della squadra che difende) si disegna come tre frecce in ingresso con spessore 1/2/3px proporzionale.

### Mismatch e duelli

- Linea 1px dal giocatore avvantaggiato a quello svantaggiato, colore `edge`, marker terminale a punta squadrata (nessun `stroke-linecap: round`).
- Nodi giocatore: cerchio r 2.2 m (in coordinate viewBox), fill `canvas`, stroke 1px `ink`; nodo protagonista fill `ink`. Etichetta cognome `label-sm`.
- Confidenza `low` → linea tratteggiata `2 2`.

### Cambio tattico

- Chip `shift`: `CAMBIO TATTICO`, seguito dalla transizione in mono: `4-2-3-1 → 3-4-2-1`.
- Sul campo: posizioni del baseline come cerchi vuoti tratteggiati `shift` `2 2`, posizioni reali come nodi pieni; collegamento 1px `shift`.

### Radar

- Max 6 assi. Anelli concentrici `line-soft`, assi `line`.
- Benchmark: poligono tratteggiato `3 3`, `rgba(255,255,255,0.30)`, nessun fill.
- Soggetto: stroke 1.5px `edge`, fill `edge/12` piatto, nodi r 3 fill `edge` stroke `canvas` 1.5.
- Etichetta asse: `caption` `ink` + percentile mono `edge` tra parentesi.

### Grafici cartesiani (Recharts)

- `CartesianGrid` solo orizzontale, `stroke="rgba(255,255,255,0.08)"`, `vertical={false}`.
- Assi: `axisLine={false}`, `tickLine={false}`, tick `fill="#888888"`, `fontFamily` mono, `fontSize={10}`.
- Linea dello zero/baseline: `ReferenceLine` 1px `line-strong`.
- Barre: angoli vivi (`radius={0}`), colore per polarità, larghezza max 24px.
- Scatter: punti r 4, fill `ink` (soggetto `edge`/`vuln`), quadranti etichettati in `label-sm` `ink-4`.
- Tooltip custom: fondo `canvas`, bordo 1px `ink`, raggio 0, nessuna ombra, `label` + `stat-md`.
- Contenitore: `ResponsiveContainer width="100%"` dentro un wrapper con `aspect-ratio` esplicito; componente client (`"use client"`).
