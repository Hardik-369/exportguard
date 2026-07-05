-- ============================================================================
-- ExportGuard — BigQuery Setup
-- ============================================================================
-- Run these statements in the Google Cloud Console BigQuery editor.
-- Replace `your_project` and `your_dataset` with your actual project/dataset.
--
-- Prerequisites:
--   1. A Google Cloud Project with BigQuery enabled (free tier works)
--   2. Upload the CSVs from data/raw/ as tables:
--        your_dataset.shipments
--        your_dataset.country_risk
--        your_dataset.buyer_history
--   3. Or run data/ingest_to_bq.py for automated upload
-- ============================================================================

-- ── Raw tables (create if not exists) ────────────────────────────────────
-- These should match the CSV schemas from generate_synthetic_data.py

-- CREATE TABLE IF NOT EXISTS your_project.your_dataset.shipments (
--   shipment_id STRING,
--   exporter_id STRING,
--   buyer_id STRING,
--   buyer_country STRING,
--   hs_code INT64,
--   product_category STRING,
--   shipment_date DATE,
--   invoice_value_usd FLOAT64,
--   payment_terms STRING,
--   payment_delay_days INT64,
--   was_disputed BOOL,
--   was_paid_in_full BOOL
-- );

-- CREATE TABLE IF NOT EXISTS your_project.your_dataset.country_risk (
--   country STRING,
--   month DATE,
--   political_stability_score FLOAT64,
--   currency_volatility_index FLOAT64,
--   trade_sanctions_flag INT64
-- );

-- CREATE TABLE IF NOT EXISTS your_project.your_dataset.buyer_history (
--   buyer_id STRING,
--   total_orders INT64,
--   total_value_usd FLOAT64,
--   avg_payment_delay_days FLOAT64,
--   dispute_rate FLOAT64,
--   paid_in_full_rate FLOAT64,
--   avg_invoice_value FLOAT64,
--   first_order_date DATE,
--   last_order_date DATE,
--   primary_country STRING,
--   primary_category STRING,
--   value_trend STRING
-- );

-- ============================================================================
-- VIEW 1: buyer_risk_summary
-- One row per buyer with current risk indicators.
-- Powers a Looker Studio "Buyer Risk Leaderboard" chart.
-- ============================================================================
CREATE OR REPLACE VIEW `your_project.your_dataset.buyer_risk_summary` AS
WITH buyer_stats AS (
  SELECT
    buyer_id,
    buyer_country,
    COUNT(*) AS total_shipments,
    SUM(invoice_value_usd) AS total_value,
    AVG(payment_delay_days) AS avg_delay_days,
    SAFE_DIVIDE(SUM(CAST(was_disputed AS INT64)), COUNT(*)) AS dispute_rate,
    SAFE_DIVIDE(SUM(CAST(was_paid_in_full AS INT64)), COUNT(*)) AS paid_in_full_rate,
    MAX(shipment_date) AS last_shipment,
    DATE_DIFF(CURRENT_DATE(), MAX(shipment_date), DAY) AS days_since_last_order,
    -- Composite risk score (0-100, higher = riskier)
    ROUND(
      (AVG(payment_delay_days) / 180) * 30
      + SAFE_DIVIDE(SUM(CAST(was_disputed AS INT64)), COUNT(*)) * 40
      + (1 - SAFE_DIVIDE(SUM(CAST(was_paid_in_full AS INT64)), COUNT(*))) * 30
    , 1) AS risk_score
  FROM `your_project.your_dataset.shipments`
  GROUP BY buyer_id, buyer_country
)
SELECT
  *,
  CASE
    WHEN risk_score < 30 THEN 'Low Risk'
    WHEN risk_score < 60 THEN 'Medium Risk'
    ELSE 'High Risk'
  END AS risk_category
FROM buyer_stats;


-- ============================================================================
-- VIEW 2: country_risk_trend
-- Monthly political + economic risk per country.
-- Powers a Looker Studio "Country Risk Over Time" time-series chart.
-- ============================================================================
CREATE OR REPLACE VIEW `your_project.your_dataset.country_risk_trend` AS
SELECT
  country,
  month,
  political_stability_score,
  currency_volatility_index,
  trade_sanctions_flag,
  -- Composite risk (0-100): lower stability + higher volatility + sanctions
  ROUND(
    (1 - political_stability_score) * 50
    + currency_volatility_index * 40
    + trade_sanctions_flag * 10
  , 1) AS composite_risk_index
FROM `your_project.your_dataset.country_risk`
ORDER BY country, month;


-- ============================================================================
-- VIEW 3: shipment_outcomes_by_hs_code
-- Aggregated shipment outcomes grouped by HS code section.
-- Powers a Looker Studio "HS-code Exposure Breakdown" chart.
-- ============================================================================
CREATE OR REPLACE VIEW `your_project.your_dataset.shipment_outcomes_by_hs_code` AS
SELECT
  hs_code,
  product_category,
  COUNT(*) AS total_shipments,
  SUM(invoice_value_usd) AS total_value_usd,
  ROUND(AVG(invoice_value_usd), 0) AS avg_invoice_value,
  ROUND(AVG(payment_delay_days), 1) AS avg_delay_days,
  SAFE_DIVIDE(SUM(CAST(was_disputed AS INT64)), COUNT(*)) AS dispute_rate,
  SAFE_DIVIDE(SUM(CAST(was_paid_in_full AS INT64)), COUNT(*)) AS paid_in_full_rate,
  -- Payment term distribution
  COUNTIF(payment_terms = 'advance') AS advance_count,
  COUNTIF(payment_terms = 'lc') AS lc_count,
  COUNTIF(payment_terms LIKE 'credit_%') AS credit_count
FROM `your_project.your_dataset.shipments`
GROUP BY hs_code, product_category
ORDER BY total_value_usd DESC;


-- ============================================================================
-- Looker Studio Chart Setup (documentation — executed in browser)
-- ============================================================================
-- Chart 1: Buyer Risk Leaderboard
--   Data source: buyer_risk_summary
--   Chart type: Bar chart
--   Dimension: buyer_id
--   Metric: risk_score (sorted descending, limit 20)
--   Breakdown: risk_category (color by Low/Medium/High)
--   Filter: risk_score IS NOT NULL
--
-- Chart 2: Country Risk Over Time
--   Data source: country_risk_trend
--   Chart type: Time series (line)
--   Dimension: month (DATE)
--   Metric: composite_risk_index (average)
--   Breakdown dimension: country
--   Filter: Select top 10 countries by total trade volume
--   Style: Smooth lines enabled, show value labels on hover
--
-- Chart 3: HS-code Exposure Breakdown
--   Data source: shipment_outcomes_by_hs_code
--   Chart type: Stacked bar chart
--   Dimension: product_category
--   Metrics: total_value_usd (bar), dispute_rate (reference line)
--   Breakdown: Not needed — single category per bar
--   Sort: total_value_usd descending
--   Style: Show data labels on bars
-- ============================================================================
