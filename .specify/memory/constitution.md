# Cottonil AI Business Assistant Constitution

## Core Principles

### I. Local-First, Minimal Stack
The project runs on a single developer machine with zero cloud infrastructure: Python 3.12 + DuckDB + Streamlit + an LLM (local via Ollama by default, cloud providers optional via env vars). No servers, no databases to install, no CI required to demo. Cloud/deployment steps are deferred until the core works (YAGNI).

### II. Real Data Beats Mockup Numbers
The 23 PDF dashboard images are the design language (layout, KPI cards, navy/blue theme), NOT literal numbers. Mockup figures (e.g., 1.24M customers, 186 branches, $12.4M wholesale) are illustrative and conflict with the actual dataset (85,000 customers, 80 branches, 8 years of transactions). Every shipped screen uses figures computed from the real CSVs. Where a mockup metric has no source data, the feature is explicitly labeled, scoped as derived proxy, or cut — never faked silently.

### III. Single Source of Truth
All metrics are computed through one governed layer: raw CSV → typed DuckDB database → curated analytical views (`views` schema) → UI/assistant. Ad-hoc calculations inside Streamlit pages are forbidden. The assistant queries only the curated views, never raw tables.

### IV. Trust & Traceability (NON-NEGOTIABLE)
- Every metric has a written definition in `docs/DATA_AUDIT.md` (metric dictionary) before it ships.
- Known data anomalies (PO value scale, marketing attribution inflation, refund over-shoot) have documented handling policies.
- Data-quality SQL checks (join integrity, reconciliation, referential rules) run on every pipeline refresh and are a release gate.
- Any number a user sees must be reproducible by a stored SQL view.

### V. Secure By Default
The assistant is read-only: generated SQL is validated to SELECT-only statements against an allowlist of views, with forced LIMIT. No write-back, no destructive operations, no customer PII beyond what the dataset contains. Secrets live in environment variables, never in the repo.

### VI. Testing Gates
The pipeline has pytest-based tests (row-count sanity, join integrity, reconciliation of gross/net/tax). The assistant has a gold question set (≥20 business questions with expected answer shapes) used to measure answer quality. A feature is done when its tests pass, not when it "looks right".

### VII. Incremental Delivery
Each user story is independently demoable. We build Core 5 dashboards + assistant before any advanced analytics. Advanced dashboards (forecasting, CLV, replenishment) come only after the core is solid.

## Additional Constraints

- **Technology stack (locked for Phase 1)**: Python 3.12, uv for env management, DuckDB, Polars/pandas, Streamlit multipage app with Plotly, pytest. Streamlit pages follow the Cottonil light theme with blue accents.
- **Currency**: all monetary reporting in EGP. The PDF's wholesale page uses USD ($M) — normalize to EGP and document.
- **Reporting period**: default "Last 12 months" (data ends 2026-10-18); calendar-year and all-time filters selectable. The mockup's "Jan 2024–Dec 2024" is one selectable period, not the default.
- **Language**: UI in English; entity names stored as found in source (Arabic for branch/customer/product names) and rendered as-is.
- **Out of scope for Phase 1**: ESG/planogram/loss-prevention dashboards (no source data exists — see scope matrix), deployment, multi-user auth, mobile.

## Development Workflow

- Spec-Driven Development via GitHub Spec Kit (already initialized, opencode integration): constitution → `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` per feature.
- Every feature lives in `specs/###-<name>/` with spec.md, plan.md, tasks.md and its own tasks checklist.
- Commit after each completed task; branch per feature.
- Roadmap-level scope decisions live in `docs/DASHBOARD_SCOPE_MATRIX.md` and are updated when data-availability decisions change.

## Governance

- This constitution supersedes ad-hoc practices. Amendments require editing this file and noting the change in the git history with rationale.
- Complexity must be justified against Principle I; prefer stdlib and existing tools over new dependencies.
- `docs/DATA_AUDIT.md` is the runtime guidance for data handling decisions.

**Version**: 1.0.0 | **Ratified**: 2026-10-24 | **Last Amended**: 2026-10-24
