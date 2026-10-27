# Cottonil — Light Palette (single source of truth)

All UI colors come from **`app/theme.py`**. No page may hardcode a hex color —
add a token to `theme.py` instead. `PALETTE.md` documents the exact operative
tokens; `app/theme.py` remains authoritative when values change.

## Brand

| Token | Hex | Use |
|---|---|---|
| `NAVY` | `#17365D` | Brand identity: sidebar background, major headings |
| `ACCENT` | `#2878D0` | Primary blue: primary buttons, active navigation, main chart series |
| `ACCENT_2` | `#56A6E8` | Light blue: large-area graphic colour only (never body text) |
| `ACCENT_SOFT` | `rgba(40,120,208,0.10)` | Soft blue fill (line fills, selected states) |
| `ACCENT_2_SOFT` | `rgba(86,166,232,0.16)` | Graph fill above soft blue |
| `PIE_TEXT` | `#FFFFFF` | Text inside coloured slices |

## Surfaces & text

| Token | Hex | Use |
|---|---|---|
| `BG` | `#F5F7FB` | App/page background (light) |
| `CARD` (surface) | `#FFFFFF` | Cards, sidebar widgets, panels, tables |
| `CARD_2` (surface-2) | `#EDF2F7` | Inputs, code chips, light hovers |
| `BORDER` | `#DCE4EE` | Card borders, dividers, widget borders |
| `GRID` | `#E8EEF7` | Chart gridlines |
| `TEXT` | `#172B4D` | Primary text |
| `TEXT_MUTED` | `#64748B` | Captions, axis labels, non-primary text |

## Coordinated chart family (background of the categorical sequence)

Saturated colours for chart series, accents, indicators and small strips —
never a card background. Text/status chips stay on the darker semantic trio.

| Token | Hex | Intended use |
|---|---|---|
| `TEAL` | `#14B8A6` | Sales channels, operations, secondary series |
| `VIOLET` | `#8B5CF6` | Customer intelligence, segmentation, model identity |
| `AMBER` | `#F59E0B` | Promotions and attention indicators (charts) |
| `ROSE` | `#E879A9` | Product analytics and category comparisons |
| `GREEN` | `#16A34A` | Positive performance lines/bands |
| `RED` | `#EF4444` | Losses and risk lines/bands |
| `ORANGE` | `#C2410C` | Inventory signal colour: low-cover band (14-30 days) |

## Chart categorical sequence (`theme.COLORS` / Plotly `colorway`)

1. `ACCENT` `#2878D0` (blue)
2. `TEAL` `#14B8A6`
3. `VIOLET` `#8B5CF6`
4. `AMBER` `#F59E0B`
5. `ROSE` `#E879A9`
6. `GREEN` `#16A34A`
7. `RED` `#EF4444`
8. `ACCENT_2` `#56A6E8` — pads dense mixes
9. `NAVY` `#17365D`
10. `NEUTRAL` `#94A3B8`

Equivalent metrics keep the same colour on every dashboard (e.g. net sales =
blue, gross profit = amber `WARN`, wholesale channel = `TEAL`, e-commerce =
`VIOLET`). Business-specific signal colours that carry meaning (delayed rate =
`BAD`, return-rate overlays = `BAD`, customer-status/stock-signal maps, the
inventory low-cover `ORANGE`) are preserved verbatim where they exist.

## Semantic status colours (text/chips, AA on white)

| Token | Hex | Use |
|---|---|---|
| `GOOD` | `#157347` | Positive delta chips, "connected" status |
| `BAD` | `#B42318` | Negative delta chips, risk lines |
| `WARN` | `#B45309` | Warning chips, amber series for warnings (text-grade amber) |
| `NEUTRAL` | `#94A3B8` | Neutral chips, "no signal" series |
| `GOOD_SOFT` | `rgba(21,115,71,0.10)` | Soft positive background |
| `BAD_SOFT` | `rgba(180,35,24,0.08)` | Soft negative background |
| `WARN_SOFT` | `rgba(180,83,9,0.10)` | Soft warning background |

## Sidebar (brand navy)

- Sidebar background: `NAVY`.
- Sidebar text: widget labels `#CFDDF2`, body/captions `#A8BBD8`, nav links
  `#CFDDF2`, group labels `#8FA6C8`, footer `#A8BBD8` on `#CFDDF2` labels.
- Nav hover: `rgba(255,255,255,0.09)` + white text.
- Active page: `rgba(86,166,232,0.26)` + white text + bold (not colour alone).
- Brand header: woven-mark tile (blue gradient `ACCENT_2 → ACCENT → #1F63B0`),
  name white `#FFFFFF`, subtitle `#9CB6DB`, divider `rgba(255,255,255,0.16)`.
- Filter widgets pages add (selects, radios) remain white inputs via `CARD`;
  checked radio option: `rgba(86,166,232,0.26)` + white.

## KPI tone strips (§5 — restrained accents)

`.cottonil-kpi.tone-<tone>` colors the 3px top strip only; cards stay white.

| Tone | Gradient | Typical metric family |
|---|---|---|
| `blue` (default) | `ACCENT → ACCENT_2` | Net sales, money series |
| `teal` | `TEAL → #0D9488` | Orders, volume, operations |
| `violet` | `VIOLET → #7C3AED` | Customers, models, structures |
| `amber` | `AMBER → #D97706` | Promotions, averages, attention |
| `rose` | `ROSE → #DB6D97` | Products, returns, category mixes |
| `green` | `GREEN → #15803D` | Profit, efficiency, growth |
| `red` | `RED → #DC2626` | Risk metrics (return rate, churn, critical stock) |

Good/bad delta chips keep their own `GOOD`/`BAD` semantics; the strip never
replaces them.

## Assistant (floating dock)

FAB and panel resolve to existing tokens: FAB = `ACCENT` circle; panel =
`CARD` surface, `BORDER` borders, `NAVY` title, `TEXT_MUTED` metadata,
`ACCENT_SOFT` user bubbles, shadows `rgba(23,54,93,…)` (lightened `NAVY`).

## Rules

- KPI/table/chart surfaces: white (`CARD`) with 1px `BORDER`, radius 14-16px,
  soft shadow.
- Charts: `plotly_white`, transparent plot/paper over the card, grid = `GRID`,
  axis text = `TEXT_MUTED`, titles = `NAVY`, hover = white `CARD` label.
- Pie/donut labels on dense mixes stay off; short mixes label outside and the
  coloured slice keeps `PIE_TEXT` for inside text.
- Never reintroduce a hex into a page — add a token to `theme.py` instead.
