-- View: workforce_monthly
-- Grain: branch x month, only branch-months with at least one payroll record
-- Key columns: paid employees, base/overtime/bonus/deductions/net paid, branch sales/orders/units,
--              sales and payroll per paid employee, labor cost ratio, ever-attached employees
-- Derivation: raw.payroll JOIN raw.employees (branch), aggregated to branch-month; LEFT JOIN
--             branch_daily for branch sales; roster count from raw.employees.
-- Notes: paid_employees counts employees with a payroll record in the month, not active headcount
--        or FTE. net_paid = base + overtime + bonus - deductions. Branch sales include all
--        channels (e-commerce/wholesale also carry a branch_id). No hours, attendance, checkout
--        times, task completion or service scores exist (audit A16).
CREATE OR REPLACE VIEW views.workforce_monthly AS
WITH payroll AS (
    SELECT
        p.pay_month                                         AS ym,
        e.branch_id,
        COUNT(DISTINCT p.employee_id)                       AS paid_employees,
        SUM(p.base_salary_EGP)                              AS base_salary,
        SUM(p.overtime_EGP)                                 AS overtime,
        SUM(p.bonus_EGP)                                    AS bonus,
        SUM(p.deductions_EGP)                               AS deductions,
        SUM(p.base_salary_EGP + p.overtime_EGP + p.bonus_EGP) AS gross_payroll,
        SUM(p.net_paid_EGP)                                 AS net_paid
    FROM raw.payroll p
    JOIN raw.employees e USING (employee_id)
    GROUP BY 1, 2
),
sales AS (
    SELECT
        ym,
        branch_id,
        SUM(net_sales)                                      AS net_sales,
        SUM(orders)                                         AS orders,
        SUM(units)                                          AS units
    FROM views.branch_daily
    GROUP BY 1, 2
),
ever_attached AS (
    SELECT branch_id, COUNT(*)                              AS employees_ever_attached
    FROM raw.employees
    GROUP BY 1
)
SELECT
    p.ym,
    p.ym = strftime(DATE '{DATA_END_DATE}', '%Y-%m')        AS is_edge_month,
    p.branch_id,
    b.branch_name_ar,
    b.governorate_ar,
    b.retail_location_type                                  AS branch_type,
    e.employees_ever_attached,
    p.paid_employees,
    p.paid_employees::DOUBLE
        / NULLIF(e.employees_ever_attached, 0)              AS paid_share_of_ever_attached,
    p.base_salary,
    p.overtime,
    p.bonus,
    p.deductions,
    p.gross_payroll,
    p.net_paid,
    s.net_sales,
    s.orders,
    s.units,
    s.net_sales / NULLIF(p.paid_employees, 0)               AS net_sales_per_paid_employee,
    p.net_paid / NULLIF(p.paid_employees, 0)                AS net_paid_per_paid_employee,
    p.net_paid / NULLIF(s.net_sales, 0)                     AS labor_cost_ratio
FROM payroll p
JOIN raw.branches b USING (branch_id)
JOIN ever_attached e USING (branch_id)
LEFT JOIN sales s USING (branch_id, ym);
