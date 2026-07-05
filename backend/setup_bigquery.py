"""
ExportGuard — BigQuery One-Click Setup.

Run this AFTER setting up a Google Cloud project and service account.

Usage:
    set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\key.json
    set GOOGLE_CLOUD_PROJECT=your-project-id
    python backend/setup_bigquery.py --dataset=exportguard

This script:
  1. Creates the BigQuery dataset (if not exists)
  2. Creates raw tables (shipments, country_risk, buyer_history)
  3. Loads CSV data from data/raw/ into the tables
  4. Creates the 3 analytics views (buyer_risk_summary, country_risk_trend, shipment_outcomes_by_hs_code)
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
sys.path.insert(0, str(PROJECT_ROOT))

# ── Check credentials ───────────────────────────────────────────────────

def check_credentials():
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not cred_path or not Path(cred_path).exists():
        print("=" * 60)
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS not set or file not found.")
        print("")
        print("Steps to fix:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a new project (or select existing)")
        print("  3. Go to APIs & Services > Library")
        print("  4. Enable 'BigQuery API' and 'Cloud Storage API'")
        print("  5. Go to IAM & Admin > Service Accounts")
        print("  6. Create a new service account → click 'Create and Continue'")
        print("  7. Assign roles:")
        print("       - BigQuery Data Editor")
        print("       - BigQuery Job User")
        print("       - Storage Object Admin")
        print("  8. Click 'Done', then click on the new service account")
        print("  9. Go to 'Keys' tab → 'Add Key' → 'Create New Key' → JSON")
        print(" 10. Download the JSON file to your computer")
        print("")
        print("Then run:")
        print(f'    set GOOGLE_APPLICATION_CREDENTIALS=C:\\path\\to\\downloaded-key.json')
        print(f'    set GOOGLE_CLOUD_PROJECT=your-project-id')
        print(f"    python backend/setup_bigquery.py --dataset=exportguard")
        print("=" * 60)
        return False
    if not project:
        print("ERROR: GOOGLE_CLOUD_PROJECT environment variable not set.")
        print(f'Example: set GOOGLE_CLOUD_PROJECT=my-project-12345')
        return False
    return True


# ── Main setup ──────────────────────────────────────────────────────────

def setup_bigquery(dataset_id: str):
    from google.cloud import bigquery

    client = bigquery.Client()
    project = client.project
    print(f"Using project: {project}")
    print(f"Dataset: {dataset_id}")

    # 1. Create dataset
    dataset_ref = bigquery.DatasetReference(project, dataset_id)
    try:
        client.get_dataset(dataset_ref)
        print(f"[OK] Dataset {dataset_id} already exists")
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset)
        print(f"[OK] Created dataset {dataset_id}")

    # 2. Table schemas
    tables = {
        "shipments": [
            bigquery.SchemaField("shipment_id", "STRING"),
            bigquery.SchemaField("exporter_id", "STRING"),
            bigquery.SchemaField("buyer_id", "STRING"),
            bigquery.SchemaField("buyer_country", "STRING"),
            bigquery.SchemaField("hs_code", "INT64"),
            bigquery.SchemaField("product_category", "STRING"),
            bigquery.SchemaField("shipment_date", "DATE"),
            bigquery.SchemaField("invoice_value_usd", "FLOAT64"),
            bigquery.SchemaField("payment_terms", "STRING"),
            bigquery.SchemaField("payment_delay_days", "INT64"),
            bigquery.SchemaField("was_disputed", "BOOL"),
            bigquery.SchemaField("was_paid_in_full", "BOOL"),
        ],
        "country_risk": [
            bigquery.SchemaField("country", "STRING"),
            bigquery.SchemaField("month", "DATE"),
            bigquery.SchemaField("political_stability_score", "FLOAT64"),
            bigquery.SchemaField("currency_volatility_index", "FLOAT64"),
            bigquery.SchemaField("trade_sanctions_flag", "INT64"),
        ],
        "buyer_history": [
            bigquery.SchemaField("buyer_id", "STRING"),
            bigquery.SchemaField("total_orders", "INT64"),
            bigquery.SchemaField("total_value_usd", "FLOAT64"),
            bigquery.SchemaField("avg_payment_delay_days", "FLOAT64"),
            bigquery.SchemaField("dispute_rate", "FLOAT64"),
            bigquery.SchemaField("paid_in_full_rate", "FLOAT64"),
            bigquery.SchemaField("avg_invoice_value", "FLOAT64"),
            bigquery.SchemaField("first_order_date", "DATE"),
            bigquery.SchemaField("last_order_date", "DATE"),
            bigquery.SchemaField("primary_country", "STRING"),
            bigquery.SchemaField("primary_category", "STRING"),
            bigquery.SchemaField("value_trend", "STRING"),
        ],
    }

    # 3. Create tables + load CSV data
    for table_name, schema in tables.items():
        csv_path = DATA_RAW / f"{table_name}.csv"
        if not csv_path.exists():
            print(f"[SKIP] {csv_path} not found — skipping {table_name}")
            continue

        table_id = f"{project}.{dataset_id}.{table_name}"

        # Delete existing table if present
        try:
            client.delete_table(table_id)
        except Exception:
            pass

        table = bigquery.Table(table_id, schema=schema)
        client.create_table(table)
        print(f"[OK] Created table {table_id}")

        # Load CSV
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            autodetect=False,
        )
        with open(csv_path, "rb") as f:
            load_job = client.load_table_from_file(f, table_id, job_config=job_config)
        load_job.result()
        table = client.get_table(table_id)
        print(f"[OK] Loaded {table.num_rows:,} rows into {table_name}")

    # 4. Create views
    views_sql = {
        "buyer_risk_summary": f"""
            CREATE OR REPLACE VIEW `{project}.{dataset_id}.buyer_risk_summary` AS
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
                ROUND(
                  (AVG(payment_delay_days) / 180) * 30
                  + SAFE_DIVIDE(SUM(CAST(was_disputed AS INT64)), COUNT(*)) * 40
                  + (1 - SAFE_DIVIDE(SUM(CAST(was_paid_in_full AS INT64)), COUNT(*))) * 30
                , 1) AS risk_score
              FROM `{project}.{dataset_id}.shipments`
              GROUP BY buyer_id, buyer_country
            )
            SELECT *, CASE
                WHEN risk_score < 30 THEN 'Low Risk'
                WHEN risk_score < 60 THEN 'Medium Risk'
                ELSE 'High Risk'
              END AS risk_category
            FROM buyer_stats
        """,
        "country_risk_trend": f"""
            CREATE OR REPLACE VIEW `{project}.{dataset_id}.country_risk_trend` AS
            SELECT
              country, month,
              political_stability_score,
              currency_volatility_index,
              trade_sanctions_flag,
              ROUND(
                (1 - political_stability_score) * 50
                + currency_volatility_index * 40
                + trade_sanctions_flag * 10
              , 1) AS composite_risk_index
            FROM `{project}.{dataset_id}.country_risk`
            ORDER BY country, month
        """,
        "shipment_outcomes_by_hs_code": f"""
            CREATE OR REPLACE VIEW `{project}.{dataset_id}.shipment_outcomes_by_hs_code` AS
            SELECT
              hs_code, product_category,
              COUNT(*) AS total_shipments,
              SUM(invoice_value_usd) AS total_value_usd,
              ROUND(AVG(invoice_value_usd), 0) AS avg_invoice_value,
              ROUND(AVG(payment_delay_days), 1) AS avg_delay_days,
              SAFE_DIVIDE(SUM(CAST(was_disputed AS INT64)), COUNT(*)) AS dispute_rate,
              SAFE_DIVIDE(SUM(CAST(was_paid_in_full AS INT64)), COUNT(*)) AS paid_in_full_rate,
              COUNTIF(payment_terms = 'advance') AS advance_count,
              COUNTIF(payment_terms = 'lc') AS lc_count,
              COUNTIF(payment_terms LIKE 'credit_%') AS credit_count
            FROM `{project}.{dataset_id}.shipments`
            GROUP BY hs_code, product_category
            ORDER BY total_value_usd DESC
        """,
    }

    for view_name, sql in views_sql.items():
        try:
            job = client.query(sql)
            job.result()
            print(f"[OK] Created view {view_name}")
        except Exception as e:
            print(f"[ERROR] Creating view {view_name}: {e}")

    print(f"\n{'=' * 60}")
    print(f"SETUP COMPLETE!")
    print(f"{'=' * 60}")
    print(f"")
    print(f"BigQuery tables and views are ready at: {project}.{dataset_id}")
    print(f"")
    print(f"Views created:")
    for v in views_sql:
        print(f"  - {v}")
    print(f"")
    print(f"Next: Open Looker Studio → https://lookerstudio.google.com/")
    print(f"  1. Click 'Create' → 'Report'")
    print(f"  2. Click 'Add Data' → 'BigQuery'")
    print(f"  3. Select your project → {dataset_id} → choose a view")
    print(f"  4. For each view, create the corresponding chart:")
    print(f"")
    print(f"  CHART 1: Buyer Risk Leaderboard")
    print(f"    View: buyer_risk_summary")
    print(f"    Chart: Bar chart")
    print(f"    Dimension: buyer_id")
    print(f"    Metric: risk_score (sorted DESC, limit 20)")
    print(f"")
    print(f"  CHART 2: Country Risk Over Time")
    print(f"    View: country_risk_trend")
    print(f"    Chart: Time series (line chart)")
    print(f"    Dimension: month")
    print(f"    Metric: composite_risk_index (AVG)")
    print(f"    Breakdown: country")
    print(f"")
    print(f"  CHART 3: HS-code Exposure Breakdown")
    print(f"    View: shipment_outcomes_by_hs_code")
    print(f"    Chart: Stacked bar chart")
    print(f"    Dimension: product_category")
    print(f"    Metrics: total_value_usd")


def main():
    parser = argparse.ArgumentParser(description="ExportGuard BigQuery Setup")
    parser.add_argument("--dataset", default="exportguard", help="BigQuery dataset name")
    args = parser.parse_args()

    if not check_credentials():
        sys.exit(1)

    setup_bigquery(args.dataset)


if __name__ == "__main__":
    main()
