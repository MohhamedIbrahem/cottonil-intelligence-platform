# PROJECT PLAN — Cottonil Data, AI & Business Intelligence (HVIA Task 3)

**Created**: 2026-10-24 · **Status**: Features 001–004 shipped (2026-10-26) · **Process**: GitHub Spec Kit (opencode integration, initialized in repo).

## 1. What this project is

A local-first **AI-powered business analytics web app** for Cottonil:

1. **Data foundation** — 25 CSVs → typed DuckDB + curated views + DQ tests.
2. **Core 5 dashboards** — Executive, Sales, Branch, Inventory, Customers (deck pages 2–6).
3. **AI business assistant** — EN/AR chat over the dataset (NL→SQL, read-only, visible SQL, deep-links to dashboards) + shortcut rail (deck page 23).
4. **Roadmap** — remaining 16 deck dashboards per `docs/DASHBOARD_SCOPE_MATRIX.md`, only where the dataset can honestly support them.

The 23-image PDF deck is treated as the **product brief + design language** (navy KPI cards, delta badges, layouts), not literal numbers.

## 2. Approved scope decision

| Decision | Choice |
|---|---|
| Deliverable | Web app: dashboards + AI chat (Streamlit + DuckDB local) |
| Week-1 scope | Core 5 dashboards + assistant (`specs/001-core-platform`) |
| Spec process | GitHub Spec Kit — initialized; constitution ratified; feature 001 spec/plan/tasks written |
| Out of scope v1 | ESG, Planogram, Loss Prevention dashboards (no data); full store-expansion site selection (only the A17 coverage proxy shipped); deployment/auth |

## 3. Tooling & skills required

**Installed and verified on this machine**: Python 3.12, uv, Docker, VS Code, Node, Git, Ollama (assistant's default local LLM), Streamlit (global, but we re-create clean venv — the Anaconda base has broken numpy/numexpr against pandas).

| Layer | Tools | Skill needed |
|---|---|---|
| ETL/analytics | DuckDB, pandas, uv, pytest | advanced SQL (window funcs, CTEs), data modeling, data quality testing |
| App | Streamlit, Plotly, Navy theme | Python app structure, dashboard UX, visual design |
| Assistant | OpenAI-compatible client ↔ Ollama | prompt engineering, NL→SQL validation architecture, guardrails |
| Stats | pandas/statsmodels-in-002+ | forecasting basics, RFM/CLV, elasticity regression |
| Process | GitHub Spec Kit, git, markdown docs | spec-driven development discipline |

Deliberately NOT used: SQL Server/SSMS (installed but unnecessary), Power BI (custom web app chosen), cloud services.

## 4. Timeline (working days, solo dev)

| Phase | Days | Exit gate |
|---|---|---|
| 0 Setup (pyproject, uv, git, README) | 0.5 | `uv sync` green on clean machine |
| 1 Data pipeline + DQ tests (US1) | 2 | `uv run checks` exit 0; pytest green |
| 2 App shell navy theme + filters | 0.5 | shell + period filter works |
| 3 Core 5 dashboards (US2–US6) | 3 | pages <3s, definitions shown |
| 4 Assistant engine + chat + guard (US7) | 2.5 | goldset ≥80%, refuse write-scope |
| 5 Shortcut rail + reports (US8) | 1 | each shortcut valid answer |
| 6 Polish: docs, ruff, perf, demo | 1.5 | release-001 checklist |
| **Total 001** | **11 d** | |

Follow-ups (est.): 002 supply/marketing ≈ 6d · 003 analytics ≈ 8d · 004 optional ≈ 3d.

## 5. Feature roadmap after 001

| Feature | Dashboards | Extras |
|---|---|---|
| 002 Supply & marketing edge | Supply chain, Procurement, Returns, Marketing ROI, Wholesale | import USD conversion table, attribution method doc |
| 003 Advanced analytics | Forecasting, Pricing, Omnichannel-lite, Product margin, Replenishment, CLV/Churn | statsmodels dep; rules-based reorder |
| 004 Optional lites | Workforce-lite (labor), Expansion-gap view — only if owner wants | labeled proxies |

**Ship status**: 004 shipped 2026-10-26 as p17 Workforce Productivity (`pages/18`, payroll-covered labor, A16) and p12 Store Expansion gap proxy (`pages/19`, governorate coverage intensity, A17). No synthetic data was added; the remaining missing deck pages stay explicit out-of-scope.

## 6. Working agreements

- One feature per `specs/###` directory; run `/speckit.clarify` before `/speckit.plan` when a spec has [NEEDS CLARIFICATION].
- Commit per completed task ID from `specs/001-core-platform/tasks.md`; branch `001-core-platform`.
- DQ + goldset tests are release gates (constitution §VI).
- Data notes expander ships on every dashboard page (traceability to `docs/DATA_AUDIT.md`).
- Update the scope matrix status column whenever a build/non-build decision changes.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Broken Anaconda site-packages | uv-managed venv, never reuse base env |
| Weak local LLM SQL quality | curated narrow views, few-shot examples, SQL guard, ≤2 retries, goldset gate; cloud endpoint optional |
| Stakeholder confusion deck-vs-data | Principle II, scope matrix linked from README + page notes |
| Large data folder not in git | README documents path; optional git-lfs later |
| DuckDB single-writer | views materialized once; app read-only connections |
| Arabic text on Windows console | utf-8-sig reads, app UI handles Unicode (console display garbles only) |

## 8. Success criteria

From `specs/001-core-platform/spec.md` SC-001…SC-005: DQ tests pass (orphan-free, exact reconciliation), pages <3s, assistant ≥80% on 20-question gold set, 100% shipped KPIs defined, clean-machine quickstart reproducible.
