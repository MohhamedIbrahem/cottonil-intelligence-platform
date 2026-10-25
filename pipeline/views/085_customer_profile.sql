-- View: customer_profile
-- Grain: one row per cataloged customer (85,000)
-- Key columns: segment, age band, governorate, lifetime orders/value, recency, rfm_tier
-- Notes: customers who never purchased use tier 'No purchase' (17% of catalog).
CREATE OR REPLACE VIEW views.customer_profile AS
SELECT
    c.customer_id,
    c.customer_name_ar,
    c.customer_segment,
    c.governorate_ar,
    CAST(c.joined_date AS DATE)                     AS joined_date,
    c.age_band,
    COALESCE(r.orders_lifetime, 0)                  AS orders_lifetime,
    COALESCE(r.monetary_value, 0)                   AS lifetime_value,
    r.first_order_date,
    r.last_order_date,
    r.recency_days,
    r.r_score,
    r.f_score,
    r.m_score,
    COALESCE(r.rfm_tier, 'No purchase')             AS rfm_tier
FROM raw.customers c
LEFT JOIN views.customer_rfm r ON r.customer_id = c.customer_id;
