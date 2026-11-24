---
name: Tactix Studio
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#3a3939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#bbcabf'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#86948a'
  outline-variant: '#3c4a42'
  surface-tint: '#4edea3'
  primary: '#4edea3'
  on-primary: '#003824'
  primary-container: '#10b981'
  on-primary-container: '#00422b'
  inverse-primary: '#006c49'
  secondary: '#ffb2b7'
  on-secondary: '#67001b'
  secondary-container: '#b50036'
  on-secondary-container: '#ffc2c4'
  tertiary: '#ffb3af'
  on-tertiary: '#650911'
  tertiary-container: '#fc7c78'
  on-tertiary-container: '#711419'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ffbbe'
  primary-fixed-dim: '#4edea3'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#005236'
  secondary-fixed: '#ffdadb'
  secondary-fixed-dim: '#ffb2b7'
  on-secondary-fixed: '#40000d'
  on-secondary-fixed-variant: '#92002a'
  tertiary-fixed: '#ffdad7'
  tertiary-fixed-dim: '#ffb3af'
  on-tertiary-fixed: '#410005'
  on-tertiary-fixed-variant: '#842225'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  display-hero:
    fontFamily: Inter
    fontSize: 72px
    fontWeight: '700'
    lineHeight: 72px
    letterSpacing: -0.03em
  display-hero-mobile:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.03em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.025em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  tabular-stat-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.03em
  tabular-stat-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.08em
  label-caps-sm:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.10em
spacing:
  gutter: 1px
  gutter-desktop: 1px
  margin: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style
The design system operates at the intersection of high-fashion editorial print and clinical sports intelligence. It serves tactical analysts, club directors, scouts, and elite football purists who demand surgical clarity without visual noise.

The visual style is stark Minimalist Brutalism rendered with haute-couture restraint:
- Absolute rejection of skeuomorphism, blur filters, drop shadows, and ornamental gradients.
- Structural reliance on architectural hairline division lines and asymmetric grid tensions.
- Monochromatic dominance punctuated by razor-sharp functional status colors.
- Clinical typographic treatment that treats performance metrics with the gravity of financial ledger data and the elegance of an art monograph.

## Colors
The palette is hyper-disciplined, anchored by deep near-black and pure optical white. Color is never decorative; it functions strictly as data telemetry and tactical status.

- **Background Base (`#0A0A0A`):** The primary canvas. Non-reflective, void-like foundation.
- **Surface Layer 1 (`#121212`):** Discrete module surface fill when spatial separation is required.
- **Surface Layer 2 (`#1A1A1A`):** Hover states, interactive highlights, and active pitch coordinates.
- **Text & Core Contrast (`#FFFFFF`):** Primary display, tactical metrics, and emphasized analytical labels.
- **Subdued Text (`rgba(255, 255, 255, 0.60)`): Secondary contextual copy and secondary statistics.
- **Muted Text (`rgba(255, 255, 255, 0.38)`): Metadata, column indices, and timestamp watermarks.
- **Hairline Border (`rgba(255, 255, 255, 0.12)`): Primary 1px structural framing across the entire interface.
- **Primary Accent (`#10B981`):** Electric Green. Reserved solely for overperforming metrics (xG delta, possession gain, successful progressive passes, active system status).
- **Secondary Accent (`#F43F5E`):** Coral. Reserved strictly for underperforming data, turnovers, fouls, cards, and negative deltas.

## Typography
Typography is executed exclusively with neo-grotesque precision using `Inter` as the production standard fallback for classical Helvetica / Helvetica Neue typography.

Key rules:
- **Tabular Figures:** All numeric displays (match clocks, coordinate matrices, xG metrics, pass completion ratios) must enforce `font-feature-settings: "tnum" 1, "zero" 1`. Numbers must stack with absolute vertical alignment.
- **Tracking Extremes:** Large editorial headlines must sit exceptionally tight (`-0.03em`) to mimic high-end offset printing. Analytical labels, navigation links, and operational metadata must be all-caps with generous letter spacing (`+0.08em` to `+0.10em`) to remain sharp at microscopic scale.
- **Weight Restraint:** Never use light/thin weights that deteriorate on dark screens or extra-heavy weights that dilute clinical authority. Keep strictly between 400 (Regular), 500 (Medium), 600 (SemiBold), and 700 (Bold).

## Layout & Spacing
The layout relies on a strict modular column grid constructed through single-pixel hairline gridlines. The layout behaves like an unyielding ledger:

- **Desktop (1440px+):** 12-column rigid frame with 1px border dividers functioning as gutters. Outer framing margins are fixed at `3rem`. Elements align precisely along hairline borders, creating a spreadsheet-like architectural integrity.
- **Tablet (768px - 1439px):** 6-column grid with `2rem` margins. Sub-modules collapse vertically while maintaining 1px bounding partitions.
- **Mobile (<768px):** 2-column or single-column stacked layout with `1rem` margins. Dense data lists convert from horizontal data bands to stacked monolithic cards separated by horizontal 1px lines.
- **Rhythm:** Spacing between internal elements strictly follows 4px increments. Dense statistics use `space-xs` and `space-sm` for metric-to-label grouping, while `space-lg` and `space-xl` insulate major editorial dossiers.

## Elevation & Depth
Elevation in this system contains zero shadows, blurs, or volumetric simulation:

- **Strict Planar Flatness:** The z-axis is communicated exclusively through tonal boundary definition and line-drawn nesting. Drop shadows and elevation blurs are explicitly prohibited.
- **Structural Outlines:** Depth is represented by enclosing surfaces in 1px borders using `rgba(255, 255, 255, 0.12)`. When an element is selected or focused, the border transitions instantaneously to pure white (`#FFFFFF`) or electric green (`#10B981`) with zero blur.
- **Layer Stacking:** Higher-level overlays (such as tactical pitch inspection drawers or player comparison flyouts) retain `#0A0A0A` solid backgrounds bordered by a 1px white border, physically occluding the lower canvas without translucency.

## Shapes
The shape language is strictly orthogonal. All corner radii are set to `0px`.

- Every button, card, modal, pill, chip, input field, and pitch visualizer boundary must have razor-sharp 90-degree corners.
- Icons, tactical pitch diagrams, and directional arrows must also honor sharp terminals and unrounded vector paths.

## Components

### Buttons
- **Primary Action:** Solid white fill (`#FFFFFF`), pure black text (`#0A0A0A`), 0px radius, all-caps label (`label-caps`). Height: 40px. Padding: 0 20px. Hover: background switches to `#10B981` with black text.
- **Secondary / Outline:** Transparent fill, 1px border (`rgba(255, 255, 255, 0.12)`), white text (`#FFFFFF`). Hover: border becomes `#FFFFFF`. Active: background switches to `#1A1A1A`.
- **Negative Action:** Transparent fill, 1px border (`#F43F5E`), text `#F43F5E`. Hover: solid `#F43F5E` fill with black text.

### Data Chips & Badges
- Structural tags for player positions (e.g., `REGISTA`, `MEZZALA`, `BRACCETTO`), zones, and match phases.
- 0px border radius, 24px height, padding: `0 8px`.
- Default: 1px border `rgba(255, 255, 255, 0.12)`, text `label-caps` in subdued white.
- Positive Highlight: 1px solid `#10B981`, text `#10B981`, zero background fill.
- Critical Highlight: 1px solid `#F43F5E`, text `#F43F5E`, zero background fill.

### Metric Cards & Analytical Panels
- Bound by 1px `rgba(255, 255, 255, 0.12)` on all four sides.
- Internal padding: `space-md` (16px) or `space-lg` (24px).
- Top row houses the micro-label (`label-caps`) in muted white with tracking. Center houses the oversized tabular metric (`tabular-stat-lg`) in pure white. Bottom row contains the +/- delta indicator marked in `#10B981` or `#F43F5E`.

### Lists & Data Grids
- Full-width tabular rows separated by 1px bottom borders. No zebra striping.
- Header row features uppercase column descriptors (`label-caps`) aligned strictly with tabular column data below.
- Hover on table row: background shifts to `#121212` with instant transition (0ms).

### Input Fields & Search Bars
- 0px radius, 40px height, background `#0A0A0A`, 1px border `rgba(255, 255, 255, 0.12)`.
- Text: 13px mono-like neo-grotesque (`body-md`), text color `#FFFFFF`.
- Focus state: border immediately changes to `#FFFFFF` with no glow or outer shadow. Placeholder text set to `rgba(255, 255, 255, 0.30)`.

### Tactical Pitch Boards & Telemetry
- Pitch canvas rendered in `#0A0A0A` with lines drawn in 1px `rgba(255, 255, 255, 0.12)`.
- Player vectors and pass trajectories drawn as crisp 1px continuous or dashed vector lines without blur or drop shadow.
- Active pressure zones rendered via sharp polygonal wireframes with 1px border in `#10B981`.