"""
ExportGuard — Cloud Storage & BigQuery Ingestion.

Uploads raw CSV files from data/raw/ to Google Cloud Storage,
then loads them into BigQuery tables.

Prerequisites:
  - Google Cloud project with BigQuery + GCS enabled (free tier)
  - Service account key JSON with roles:
      roles/storage.objectAdmin
      roles/bigquery.dataEditor
      roles/bigquery.jobUser
  - GOOGLE_APPLICATION_CREDENTIALS env var set to key path

Usage:
  python backend/ingest_to_bq.py --project=my-project --dataset=exportguard

If credentials are not configured, this script logs a clear warning
and skips the upload — the system still works with local CSVs.
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"

GCS_BUCKET = os.environ.get("EXPORTGUARD_GCS_BUCKET", "exportguard-data-lake")


def check_gcs_bq_available() -> bool:
    """Check if GCS / BigQuery credentials are available."""
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not cred_path or not Path(cred_path).exists():
        return False
    try:
        from google.cloud import storage
        client = storage.Client()
        # Just test that we can list — will fail if auth is bad
        list(client.list_buckets(max_results=1))
        return True
    except Exception:
        return False


def upload_to_gcs():
    """Upload raw CSVs to Cloud Storage bucket."""
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)

    if not bucket.exists():
        bucket.create(location="US")
        print(f"Created bucket: gs://{GCS_BUCKET}")

    for csv_file in DATA_RAW.glob("*.csv"):
        blob = bucket.blob(f"raw/{csv_file.name}")
        blob.upload_from_filename(str(csv_file))
        print(f"  Uploaded: gs://{GCS_BUCKET}/raw/{csv_file.name}")


def load_to_bigquery(dataset: str):
    """Load CSVs from GCS into BigQuery tables."""
    from google.cloud import bigquery

    client = bigquery.Client()

    # Ensure dataset exists
    dataset_ref = client.dataset(dataset)
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        client.create_dataset(dataset_ref)
        print(f"Created dataset: {dataset}")

    table_configs = [
        {
            "table": "shipments",
            "uri": f"gs://{GCS_BUCKET}/raw/shipments.csv",
            "schema": [
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
        },
        {
            "table": "country_risk",
            "uri": f"gs://{GCS_BUCKET}/raw/country_risk.csv",
            "schema": [
                bigquery.SchemaField("country", "STRING"),
                bigquery.SchemaField("month", "DATE"),
                bigquery.SchemaField("political_stability_score", "FLOAT64"),
                bigquery.SchemaField("currency_volatility_index", "FLOAT64"),
                bigquery.SchemaField("trade_sanctions_flag", "INT64"),
            ],
        },
        {
            "table": "buyer_history",
            "uri": f"gs://{GCS_BUCKET}/raw/buyer_history.csv",
            "schema": [
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
        },
    ]

    for cfg in table_configs:
        table_id = f"{client.project}.{dataset}.{cfg['table']}"
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            schema=cfg["schema"],
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            autodetect=False,
        )
        load_job = client.load_table_from_uri(
            cfg["uri"], table_id, job_config=job_config
        )
        load_job.result()  # Wait for completion
        table = client.get_table(table_id)
        print(f"  Loaded {table.num_rows:,} rows into {table_id}")


def main():
    parser = argparse.ArgumentParser(description="Ingest ExportGuard data to GCS + BigQuery")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT", ""))
    parser.add_argument("--dataset", default="exportguard")
    parser.add_argument("--skip-gcs", action="store_true", help="Skip GCS upload, only load to BQ")
    args = parser.parse_args()

    if not check_gcs_bq_available():
        print("=" * 60)
        print("WARNING: Google Cloud credentials not configured.")
        print("Set GOOGLE_APPLICATION_CREDENTIALS to a valid service account key.")
        print("Skipping GCS/BigQuery upload. The system will work with local CSV files.")
        print("=" * 60)
        return

    if not args.skip_gcs:
        print("\n[1/2] Uploading to GCS...")
        upload_to_gcs()

    print("\n[2/2] Loading into BigQuery...")
    load_to_bigquery(args.dataset)

    print(f"\nDone. Data available in project {args.project}.{args.dataset}")
    print("Now run the SQL views from pipeline/bigquery_setup.sql")


if __name__ == "__main__":
    main()
