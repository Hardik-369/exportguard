"""
ExportGuard — shared data transformation pipeline.

This module contains ONE function that both the pandas (CPU) and
cudf.pandas (GPU) codepaths call.  The only difference between
the two runs is whether `import cudf.pandas; cudf.pandas.install()`
has been called before `import pandas as pd`.

Output:
  - Cleaned + feature-engineered DataFrame with columns:
    shipment_id, buyer_id, buyer_country, hs_code, product_category,
    shipment_date, invoice_value_usd, payment_terms, payment_delay_days,
    was_disputed, was_paid_in_full,
    political_stability_score, currency_volatility_index, trade_sanctions_flag,
    buyer_total_orders, buyer_avg_delay, buyer_dispute_rate, buyer_total_value,
    buyer_order_rank (recency), payment_default_risk (derived label)
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def load_data(engine: str = "pandas"):
    """
    Load raw CSVs from data/raw/.
    engine is informational only — both paths use pd.read_csv.
    """
    print(f"[{engine}] Loading shipment data...")
    shipments = pd.read_csv(DATA_RAW / "shipments.csv", parse_dates=["shipment_date"])
    print(f"[{engine}]   {len(shipments):,} shipment rows loaded")

    print(f"[{engine}] Loading country risk data...")
    country_risk = pd.read_csv(DATA_RAW / "country_risk.csv", parse_dates=["month"])
    print(f"[{engine}]   {len(country_risk):,} country-month rows loaded")

    return shipments, country_risk


def engineer_features(shipments: pd.DataFrame, country_risk: pd.DataFrame, engine: str = "pandas"):
    """
    Shared transformation pipeline — cleans, joins, and engineers features.

    Steps:
      1. Clean nulls, standardise codes, parse dates.
      2. Join shipments → country_risk on (buyer_country, shipment_month).
      3. Compute buyer-level aggregates (rolling & cumulative).
      4. Derive payment_default_risk label.
      5. Add recency / order-rank features.
    """
    print(f"[{engine}] Step 1/5 - Cleaning rows...")
    before = len(shipments)
    shipments = shipments.dropna(subset=[
        "buyer_id", "buyer_country", "hs_code", "invoice_value_usd"
    ])
    print(f"[{engine}]   Dropped {before - len(shipments):,} rows with missing critical fields")

    # Standardise country codes (uppercase, strip)
    shipments["buyer_country"] = shipments["buyer_country"].str.strip().str.upper()
    country_risk["country"] = country_risk["country"].str.strip().str.upper()

    # Extract month for join
    shipments["shipment_month"] = shipments["shipment_date"].dt.to_period("M").dt.to_timestamp()

    print(f"[{engine}] Step 2/5 - Joining country risk...")
    joined = shipments.merge(
        country_risk,
        left_on=["buyer_country", "shipment_month"],
        right_on=["country", "month"],
        how="left",
    )
    # Fill missing country risk (new / unmapped countries)
    risk_cols = ["political_stability_score", "currency_volatility_index"]
    for c in risk_cols:
        joined[c] = joined[c].fillna(joined[c].median())
    joined["trade_sanctions_flag"] = joined["trade_sanctions_flag"].fillna(0).astype(int)

    print(f"[{engine}] Step 3/5 - Computing buyer-level aggregates...")
    # Sort by buyer + date for rolling calculations
    joined = joined.sort_values(["buyer_id", "shipment_date"]).reset_index(drop=True)

    buyer_agg = joined.groupby("buyer_id").agg(
        buyer_total_orders=("shipment_id", "count"),
        buyer_total_value=("invoice_value_usd", "sum"),
        buyer_avg_delay=("payment_delay_days", "mean"),
        buyer_dispute_rate=("was_disputed", "mean"),
        buyer_avg_invoice=("invoice_value_usd", "mean"),
        buyer_paid_in_full_rate=("was_paid_in_full", "mean"),
    ).reset_index()

    # Rename columns to avoid confusion
    buyer_agg.columns = [
        "buyer_id", "buyer_total_orders", "buyer_total_value",
        "buyer_avg_delay", "buyer_dispute_rate",
        "buyer_avg_invoice", "buyer_paid_in_full_rate"
    ]

    joined = joined.merge(buyer_agg, on="buyer_id", how="left")

    # Recency: order rank per buyer (1 = most recent)
    joined["buyer_order_rank"] = joined.groupby("buyer_id").cumcount(ascending=False) + 1

    print(f"[{engine}] Step 4/5 - Deriving payment_default_risk label...")
    # Composite label: 0 (safe) → 1 (high risk)
    # Based on: was_disputed, payment_delay_days, was_paid_in_full
    # We create a continuous score, then binarize at a threshold
    delay_score = np.clip(joined["payment_delay_days"] / 180.0, 0, 1)
    dispute_penalty = joined["was_disputed"].astype(float) * 0.5
    nonpayment_penalty = (1 - joined["was_paid_in_full"].astype(float)) * 0.3

    joined["payment_default_risk_score"] = (
        0.3 * delay_score
        + 0.4 * dispute_penalty
        + 0.3 * nonpayment_penalty
    )
    # Binarize at 0.3 for classification
    joined["payment_default_risk"] = (joined["payment_default_risk_score"] > 0.3).astype(int)

    print(f"[{engine}] Step 5/5 - Dropping temporary columns...")
    drop_cols = ["shipment_month", "country", "month"]
    joined = joined.drop(columns=[c for c in drop_cols if c in joined.columns], errors="ignore")

    print(f"[{engine}] Done. Output shape: {joined.shape}")
    return joined


def run_pipeline(engine: str = "pandas") -> pd.DataFrame:
    """Convenience wrapper: load + transform."""
    shipments, country_risk = load_data(engine)
    result = engineer_features(shipments, country_risk, engine)
    return result


if __name__ == "__main__":
    # Test run with plain pandas
    df = run_pipeline("pandas")
    print(df.head())
    print(f"\nColumns: {list(df.columns)}")
    print(f"Label distribution:\n{df['payment_default_risk'].value_counts()}")
