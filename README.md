# Cottonil — Data, AI & Business Intelligence Project

> Implementation of **HVIA Task 3** using the Cottonil dataset: data foundation, core dashboards, and an AI-powered business assistant — per the concept deck (`COTTONIL/HVIA_TASK_3_COTTONIL_ALL_23_IMAGES.pdf`, 23 pages).

## Quickstart (planned → Phase 1 verified ✅)

```powershell
uv sync                 # create venv + install deps (python 3.12)
uv run build            # load COTTONIL_Data CSVs -> data/cottonil.duckdb (25 tables + 14 views)
uv run checks           # data-quality gate: 34 integrity/reconciliation checks
uv run pytest           # pipeline tests (builds temp DB, ~20 s)
uv run streamlit run app/Home.py   # the dashboard app (needs the build first)
```

- View definitions live in `pipeline/views/` (numbered, applied in order); the auto-generated contract doc is [`pipeline/VIEW_CATALOG.md`](pipeline/VIEW_CATALOG.md).
- Metric definitions + anomaly policies: [`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md).

## What this repo is

| Area | Where |
|---|---|
| Master project plan (phases, scope, timeline) | [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) |
| Dataset audit + metric dictionary + anomaly policies | [`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md) |
| All 21 dashboards from the deck × data availability → build order | [`docs/DASHBOARD_SCOPE_MATRIX.md`](docs/DASHBOARD_SCOPE_MATRIX.md) |
| Current feature (Core 5 dashboards + AI assistant): spec/plan/tasks | [`specs/001-core-platform/`](specs/001-core-platform/) |
| Spec-kit process (constitution) | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |

## Source of truth

- Concept deck: `COTTONIL/HVIA_TASK_3_COTTONIL_ALL_23_IMAGES.pdf` — design language only (see Principle II in the constitution: numbers in the deck are illustrative; the real dataset differs: 80 branches, 85K customers, 540K orders to 2026-10-18).
- Dataset: `COTTONIL/COTTONIL_Data/` (25 CSVs). Kept out of git (large); place it at that path.
