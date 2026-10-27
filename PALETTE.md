# Cottonil — Light Pro Palette (single source of truth)

All UI colors come from `app/theme.py`. No page should hardcode a hex color.

## Brand
| Token | Hex | Use |
|---|---|---|
| PRIMARY | #0F4C75 | Primary buttons, headings accents, chart #1 |
| PRIMARY_DARK | #0B3553 | Hover/pressed, H1 |
| ACCENT | #1B7AC2 | Bars, links, interactive |
| ACCENT_2 | #0284C7 | Second series (sky-600 — #56CCF2 was too light on white) |

## Surfaces & text
| Token | Hex | Use |
|---|---|---|
| BG | #F7F8FA | App background |
| SURFACE | #FFFFFF | Cards, sidebar, panels |
| SURFACE_2 | #EEF2F7 | Inputs, secondary areas |
| BORDER | #E2E8F0 | Borders, gridlines, dividers |
| TEXT | #0F172A | Primary text |
| TEXT_MUTED | #64748B | Captions, axis labels |
| TEXT_ON_COLOR | #FFFFFF | Text inside coloured slices |

## Semantic (darkened for white — AA text contrast)
GOOD #159947 · BAD #DC3A3A · WARN #D97706 (amber, replaces unreadable yellow #F2C94C)

## Chart categorical order
#0F4C75 → #1B7AC2 → #0E9F8A → #E9A23B → #7C5CFC → #E85D75 → #22A06B → #64748B

## Rules
- KPI cards: white, 1px BORDER, radius 16px, soft shadow, hover lift.
- Charts: plotly_white, grid = BORDER, font = TEXT_MUTED, titles = TEXT.
- Pie/donut labels inside slices: always TEXT_ON_COLOR (white).
- Never reintroduce a hex in a page — add a token to theme.py instead.
