"""Workforce Productivity (Lite) (S17) - payroll-covered labour analytics.

Only payroll and branch sales exist. There are no hours, attendance, checkout
times, tasks or service scores, so this page deliberately reports payroll cost
and payroll-covered headcount rather than inventing an FTE productivity model.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app import data, theme
from app.filters import DATA_END, render_period_selector

st.set_page_config(
    page_title="Workforce Productivity · Cottonil",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

render_period_selector()  # shared control; payroll coverage, not the window, drives this page

REFERENCE_YEAR = "2023"

monthly = data.q(
    """
    SELECT ym,
           COUNT(DISTINCT branch_id) AS branches_paid,
           SUM(paid_employees)       AS paid_employees,
           SUM(net_paid)             AS net_paid,
           SUM(net_sales)            AS net_sales
    FROM views.workforce_monthly
    GROUP BY 1
    ORDER BY 1
    """
)
monthly["labor_cost_ratio"] = monthly.net_paid / monthly.net_sales

year = monthly[monthly.ym.str.startswith(REFERENCE_YEAR)]
avg_paid = float(year.paid_employees.mean())
net_paid = float(year.net_paid.sum())
net_sales = float(year.net_sales.sum())
employee_months = float(year.paid_employees.sum())
labor_ratio = net_paid / net_sales
sales_per_employee_month = net_sales / employee_months
pay_per_employee_month = net_paid / employee_months

annual = data.q(
    """
    SELECT LEFT(ym, 4)                                      AS year,
           COUNT(DISTINCT ym)                               AS months,
           COUNT(DISTINCT branch_id)                        AS branches_with_payroll,
           COUNT(*)                                         AS branch_months,
           COUNT(*)::DOUBLE
               / ((SELECT COUNT(*) FROM raw.branches) * 12) AS branch_month_coverage,
           SUM(paid_employees)::DOUBLE
               / COUNT(DISTINCT ym)                         AS avg_paid_employees,
           SUM(net_paid)                                    AS net_paid,
           SUM(net_sales)                                   AS net_sales,
           SUM(net_paid) / NULLIF(SUM(net_sales), 0)        AS labor_cost_ratio,
           SUM(net_paid) / NULLIF(SUM(paid_employees), 0)   AS net_paid_per_employee_month,
           SUM(net_sales) / NULLIF(SUM(paid_employees), 0)  AS net_sales_per_employee_month
    FROM views.workforce_monthly
    WHERE LEFT(ym, 4) BETWEEN '2019' AND '2025'
    GROUP BY 1
    ORDER BY 1
    """
)

branch = data.q(
    """
    WITH branch_year AS (
        SELECT branch_id,
               ANY_VALUE(branch_name_ar)   AS branch_name_ar,
               ANY_VALUE(governorate_ar)   AS governorate_ar,
               ANY_VALUE(branch_type)      AS branch_type,
               COUNT(DISTINCT ym)          AS months_paid,
               SUM(paid_employees)         AS employee_months,
               SUM(net_paid)               AS net_paid,
               SUM(net_sales)              AS net_sales,
               SUM(orders)                 AS orders
        FROM views.workforce_monthly
        WHERE LEFT(ym, 4) = ?
        GROUP BY branch_id
    )
    SELECT *,
           employee_months / 12.0                         AS avg_paid_employees,
           net_paid / NULLIF(net_sales, 0)                AS labor_cost_ratio,
           net_paid / NULLIF(employee_months, 0)          AS net_paid_per_employee_month,
           net_sales / NULLIF(employee_months, 0)         AS net_sales_per_employee_month
    FROM branch_year
    WHERE months_paid = 12
    ORDER BY labor_cost_ratio DESC
    """,
    (REFERENCE_YEAR,),
)

positions = data.q(
    """
    SELECT position_en,
           COUNT(*)                         AS employees,
           MEDIAN(salary_base_EGP_2026)     AS median_base_salary_2026
    FROM raw.employees
    GROUP BY 1
    ORDER BY employees DESC
    """
)
positions["share_of_roster"] = positions.employees / positions.employees.sum()

if branch.empty:
    st.error("No branch has 12 payroll months in the reference year.")
    st.stop()

corr = float(branch.avg_paid_employees.corr(branch.labor_cost_ratio))

theme.page_header(
    "Workforce Productivity (Lite)",
    f"Payroll-covered labour only · reference year **{REFERENCE_YEAR}** (broadest full-year "
    "coverage: 72 of 80 branches with 12 payroll months; 922 of 960 branch-months) · "
    "640 employees ever attached · no hours, attendance, "
    "checkout times, tasks or service scores · sidebar period does not change this page · "
    f"data through {DATA_END.isoformat()}",
    eyebrow="Advanced analytics",
    badges=('Payroll-covered',),
)

st.warning(
    "Payroll is the only workforce source. Sales per paid employee is not an FTE or "
    "hourly productivity measure, and the payroll tail is not evidence of layoffs "
    "(audit A16)."
)

cards = st.columns(4)
with cards[0]:
    theme.kpi_card(
        f"Avg paid employees · {REFERENCE_YEAR}",
        theme.fmt_int(avg_paid),
        sub="payroll-covered headcount per month · 640 employees ever attached",
    )
with cards[1]:
    theme.kpi_card(
        f"Net payroll · {REFERENCE_YEAR}",
        theme.fmt_egp(net_paid),
        sub="base + overtime + bonus − deductions · no employer burden",
    )
with cards[2]:
    theme.kpi_card(
        f"Labor cost ratio · {REFERENCE_YEAR}",
        f"{labor_ratio:.1%}",
        sub="net paid / sales in the same payroll-covered branch-months",
    )
with cards[3]:
    theme.kpi_card(
        "Sales per paid employee",
        theme.fmt_egp(sales_per_employee_month),
        sub=f"monthly · payroll {theme.fmt_egp(pay_per_employee_month)} per employee-month",
    )

st.divider()

left, right = st.columns((3, 2))

with left:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=monthly.ym,
            y=monthly.paid_employees,
            mode="lines",
            name="Paid employees",
            line={"color": theme.ACCENT, "width": 2.5},
            hovertemplate="%{x}<br>%{y:,.0f} paid employees<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=monthly.ym,
            y=monthly.labor_cost_ratio,
            mode="lines",
            name="Labor cost ratio",
            yaxis="y2",
            line={"color": theme.ACCENT_2, "width": 2, "dash": "dot"},
            hovertemplate="%{x}<br>%{y:.1%} labor cost ratio<extra></extra>",
        )
    )
    fig.update_layout(
        title="Paid headcount and labor cost ratio, monthly",
        yaxis={"title": "Paid employees"},
        yaxis2={
            "title": "Labor cost ratio",
            "overlaying": "y",
            "side": "right",
            "tickformat": ".0%",
        },
    )
    theme.apply_plotly_style(fig)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Paid employees = employees with a payroll record that month. Headcount peaks at "
        "225 in Mar 2023 and falls to 10 in Oct 2026; the tail is consistent with payroll "
        "windows ending and sparse coverage, not proof of layoffs. Oct 2026 is the dataset-edge "
        "month."
    )

with right:
    scatter = go.Figure()
    for branch_type, color in (
        ("Retail branch", theme.ACCENT),
        ("Point of sale / reseller", theme.ACCENT_2),
    ):
        part = branch[branch.branch_type == branch_type]
        if part.empty:
            continue
        scatter.add_trace(
            go.Scatter(
                x=part.avg_paid_employees,
                y=part.labor_cost_ratio,
                mode="markers",
                name=branch_type,
                marker={"color": color, "size": 9, "opacity": 0.75},
                customdata=part[
                    [
                        "branch_name_ar",
                        "governorate_ar",
                        "employee_months",
                        "net_sales",
                    ]
                ],
                hovertemplate=(
                    "%{customdata[0]} · %{customdata[1]}"
                    "<br>Avg paid employees %{x:.1f} · labor ratio %{y:.1%}"
                    "<br>Employee-months %{customdata[2]:,.0f}"
                    "<br>2023 net sales EGP %{customdata[3]:,.0f}<extra></extra>"
                ),
            )
        )
    if len(branch) > 2:
        coef = np.polyfit(branch.avg_paid_employees, branch.labor_cost_ratio, 1)
        xs = np.linspace(branch.avg_paid_employees.min(), branch.avg_paid_employees.max(), 50)
        scatter.add_trace(
            go.Scatter(
                x=xs,
                y=coef[0] * xs + coef[1],
                mode="lines",
                name="Linear fit",
                line={"color": theme.TEXT_MUTED, "width": 1, "dash": "dot"},
                hoverinfo="skip",
            )
        )
    scatter.update_layout(
        title=f"{REFERENCE_YEAR} labor ratio vs paid staff per branch",
        xaxis={"title": "Average paid employees per month"},
        yaxis={"title": "Labor cost ratio", "tickformat": ".0%"},
    )
    theme.apply_plotly_style(scatter)
    st.plotly_chart(scatter, width="stretch", config={"displayModeBar": False})
    st.caption(
        f"r = {corr:.2f} across {len(branch)} branches with 12 payroll months. More paid "
        "staff mechanically raises the ratio because branch sales are nearly uniform "
        "(EGP 0.87M–1.27M in 2023). This is not an efficiency ranking."
    )

st.divider()

theme.section_header("Annual payroll coverage and cost")
annual_view = annual.copy()
for column in ("branch_month_coverage", "labor_cost_ratio"):
    annual_view[column] *= 100
annual_view = annual_view.rename(
    columns={
        "year": "Year",
        "months": "Months",
        "branches_with_payroll": "Branches with payroll",
        "branch_months": "Branch-months",
        "branch_month_coverage": "Coverage (%)",
        "avg_paid_employees": "Avg paid employees",
        "net_paid": "Net payroll (EGP)",
        "net_sales": "Sales · covered months (EGP)",
        "labor_cost_ratio": "Labor cost ratio (%)",
        "net_paid_per_employee_month": "Payroll per employee-month (EGP)",
        "net_sales_per_employee_month": "Sales per employee-month (EGP)",
    }
)
st.dataframe(
    annual_view,
    hide_index=True,
    column_config={
        "Year": st.column_config.TextColumn("Year", width="small"),
        "Months": st.column_config.NumberColumn("Months", format="%.0f"),
        "Branches with payroll": st.column_config.NumberColumn(
            "Branches with payroll", format="%.0f"
        ),
        "Branch-months": st.column_config.NumberColumn("Branch-months", format="%.0f"),
        "Coverage (%)": st.column_config.NumberColumn("Coverage (%)", format="%.1f"),
        "Avg paid employees": st.column_config.NumberColumn(
            "Avg paid employees", format="%.1f"
        ),
        "Net payroll (EGP)": st.column_config.NumberColumn(
            "Net payroll (EGP)", format="%.0f"
        ),
        "Sales · covered months (EGP)": st.column_config.NumberColumn(
            "Sales · covered months (EGP)", format="%.0f"
        ),
        "Labor cost ratio (%)": st.column_config.NumberColumn(
            "Labor cost ratio (%)", format="%.1f"
        ),
        "Payroll per employee-month (EGP)": st.column_config.NumberColumn(
            "Payroll per employee-month (EGP)", format="%.0f"
        ),
        "Sales per employee-month (EGP)": st.column_config.NumberColumn(
            "Sales per employee-month (EGP)", format="%.0f"
        ),
    },
)
st.caption(
    "Coverage = branch-months with a payroll record / (80 branches × 12 months). Sales are "
    "shown only for the covered branch-months, so the ratio is internally consistent. 2018 "
    "and 2026 are excluded as partial years; 2025 coverage is 79.3%, so its ratio is more "
    "fragile."
)

st.divider()

theme.section_header(f"Branch detail · {REFERENCE_YEAR}")
branch_view = branch.copy()
branch_view["labor_cost_ratio"] *= 100
branch_view = branch_view.rename(
    columns={
        "branch_name_ar": "Branch",
        "governorate_ar": "Governorate",
        "branch_type": "Type",
        "avg_paid_employees": "Avg paid employees",
        "employee_months": "Employee-months",
        "net_paid": "Net payroll (EGP)",
        "net_sales": "Net sales (EGP)",
        "orders": "Orders",
        "labor_cost_ratio": "Labor cost ratio (%)",
        "net_paid_per_employee_month": "Payroll per employee-month (EGP)",
        "net_sales_per_employee_month": "Sales per employee-month (EGP)",
    }
)
st.dataframe(
    branch_view[
        [
            "Branch",
            "Governorate",
            "Type",
            "Avg paid employees",
            "Employee-months",
            "Net payroll (EGP)",
            "Net sales (EGP)",
            "Orders",
            "Labor cost ratio (%)",
            "Payroll per employee-month (EGP)",
            "Sales per employee-month (EGP)",
        ]
    ],
    hide_index=True,
    height=500,
    column_config={
        "Branch": st.column_config.TextColumn("Branch"),
        "Governorate": st.column_config.TextColumn("Governorate"),
        "Type": st.column_config.TextColumn("Type", width="small"),
        "Avg paid employees": st.column_config.NumberColumn(
            "Avg paid employees", format="%.1f"
        ),
        "Employee-months": st.column_config.NumberColumn(
            "Employee-months", format="%.0f"
        ),
        "Net payroll (EGP)": st.column_config.NumberColumn(
            "Net payroll (EGP)", format="%.0f"
        ),
        "Net sales (EGP)": st.column_config.NumberColumn(
            "Net sales (EGP)", format="%.0f"
        ),
        "Orders": st.column_config.NumberColumn("Orders", format="%.0f"),
        "Labor cost ratio (%)": st.column_config.NumberColumn(
            "Labor cost ratio (%)", format="%.1f"
        ),
        "Payroll per employee-month (EGP)": st.column_config.NumberColumn(
            "Payroll per employee-month (EGP)", format="%.0f"
        ),
        "Sales per employee-month (EGP)": st.column_config.NumberColumn(
            "Sales per employee-month (EGP)", format="%.0f"
        ),
    },
)
st.caption(
    f"{len(branch)} of 80 branches have 12 payroll months in {REFERENCE_YEAR}; the 8 "
    "partial-coverage branches are excluded because their ratios would be understated. "
    "Net sales are all-channel branch-attributed sales, not store footfall, and orders "
    "include guests."
)

st.divider()

left, right = st.columns((3, 2))

with left:
    theme.section_header("Roster profile")
    positions_view = positions.copy()
    positions_view["share_of_roster"] *= 100
    positions_view = positions_view.rename(
        columns={
            "position_en": "Position",
            "employees": "Employees",
            "median_base_salary_2026": "Median 2026 base salary (EGP)",
            "share_of_roster": "Share of roster (%)",
        }
    )
    st.dataframe(
        positions_view,
        hide_index=True,
        column_config={
            "Position": st.column_config.TextColumn("Position"),
            "Employees": st.column_config.NumberColumn("Employees", format="%.0f"),
            "Median 2026 base salary (EGP)": st.column_config.NumberColumn(
                "Median 2026 base salary (EGP)", format="%.0f"
            ),
            "Share of roster (%)": st.column_config.NumberColumn(
                "Share of roster (%)", format="%.1f"
            ),
        },
    )
    st.caption(
        "640 employees ever attached, exactly 8 per branch and 3 distinct positions per "
        "branch. Salary is the source's 2026 base field, not historical payroll."
    )

with right:
    theme.section_header("What this page does not measure")
    st.markdown(
        "- Hours, attendance, overtime hours, FTE, absenteeism or shift coverage.\n"
        "- Checkout speed, task completion, service scores, conversion or footfall.\n"
        "- Recruiting cost, turnover, benefits, employer social insurance or taxes.\n"
        "- Store-level labour productivity: branch sales include e-commerce and wholesale "
        "orders that carry a branch_id."
    )

with st.expander("Definitions and limits (audit A16)", expanded=False):
    st.markdown(
        f"- **View**: `views.workforce_monthly` has **5,644 branch-months** across 80 "
        "branches and 97 months (2018-10 to 2026-10). It is built from **13,210 payroll "
        "rows** for **640 employees**.\n"
        "- **Paid employees** = employees with a payroll record in that branch-month. Each "
        "employee has a continuous payroll window of **9–34 months** (median 20); there is "
        "no termination date, so a month without a record cannot be classified as "
        "termination, leave or a data gap. The decline from 225 paid employees in Mar 2023 "
        "to 10 in Oct 2026 is **payroll coverage/tenure behaviour, not proof of layoffs**.\n"
        "- **Pay**: `net_paid = base_salary + overtime + bonus − deductions` exactly across "
        "all 13,210 source rows. It excludes employer social insurance, benefits, taxes and "
        "any hours-based cost. There is no FTE or headcount-hours field.\n"
        f"- **Reference year {REFERENCE_YEAR}**: chosen for the broadest full-year coverage — "
        "72 of 80 branches have 12 payroll months (922 of 960 branch-months, 96.0%; 2024 has "
        "slightly more branch-months at 926 but only 69 full-year branches). Net payroll "
        "**EGP 10.99M**, sales in the same covered branch-months **EGP 80.88M**, "
        "labor cost ratio **13.59%**. Payroll is **EGP 4,261 per employee-month**; sales are "
        "**EGP 31,351 per employee-month**.\n"
        "- **Sales are branch-attributed, not store footfall**: e-commerce and wholesale "
        "orders also carry a `branch_id`. Sales per paid employee is therefore not an hourly "
        "or FTE productivity measure, and it is not comparable to a store-labour benchmark.\n"
        "- **Excluded branches**: 8 branches with fewer than 12 payroll months in 2023. "
        "Their labor ratios would be understated because payroll is missing while sales are "
        "not.\n"
        "- **Do not** use this page to claim layoffs, per-hour productivity, service quality, "
        "checkout speed, task completion or labour ROI. The data support payroll cost and "
        "payroll-covered headcount only."
    )
