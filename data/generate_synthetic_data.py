"""
Generate synthetic but statistically realistic export trade data
for the ExportGuard benchmark and risk model.

Outputs:
  - data/raw/shipments.csv          (2-5M rows)
  - data/raw/country_risk.csv       (country × month signals)
  - data/raw/buyer_history.csv      (pre-computed aggregates)

Scale: 2-5 million rows so the pandas-vs-cudf.pandas benchmark
is meaningful (CPU baseline > 30s, GPU version < 10s).
"""

import numpy as np
import pandas as pd
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw"
BASE.mkdir(parents=True, exist_ok=True)

np.random.seed(42)

# ── configuration ──────────────────────────────────────────────────────────
N_SHIPMENTS = 3_000_000  # 3M rows — big enough for a real benchmark
N_COUNTRIES = 80
N_BUYERS = 8_000
N_EXPORTERS = 600
N_HSSECTIONS = 21       # HS 2-digit sections
MONTHS = pd.date_range("2022-01-01", "2024-12-01", freq="MS")

PAYMENT_TERMS = ["advance", "lc", "credit_30", "credit_60", "credit_90"]
PAYMENT_WEIGHTS = [0.15, 0.30, 0.30, 0.15, 0.10]

PRODUCT_CATEGORIES = [
    "textiles", "chemicals", "machinery", "electronics", "automotive",
    "pharmaceuticals", "plastics", "agricultural", "steel", "ceramics",
    "leather", "paper", "wood", "minerals", "food_processed",
    "rubber", "glass", "precious_metals", "base_metals", "footwear", "optical"
]

# ── helper: generate country risk profiles ─────────────────────────────────
def generate_country_risk():
    """Generate monthly political/economic risk for each country."""
    country_names = [f"country_{i:03d}" for i in range(N_COUNTRIES)]
    # Some "known" country names for realism
    real_countries = [
        "India", "USA", "China", "UAE", "UK", "Germany", "Brazil",
        "Nigeria", "Bangladesh", "Vietnam", "Indonesia", "Mexico",
        "South Africa", "Turkey", "Russia", "Japan", "South Korea",
        "Australia", "Canada", "Saudi Arabia", "Egypt", "Pakistan",
        "Thailand", "Malaysia", "Singapore", "Netherlands", "France",
        "Italy", "Spain", "Poland", "Chile", "Argentina", "Peru",
        "Colombia", "Kenya", "Ghana", "Morocco", "Algeria", "Angola",
        "Ethiopia", "Tanzania", "Sri Lanka", "Myanmar", "Philippines",
        "Taiwan", "Switzerland", "Sweden", "Norway", "Denmark", "Finland",
    ]
    # Fill rest with generic names
    while len(real_countries) < N_COUNTRIES:
        real_countries.append(f"ctry_{len(real_countries):03d}")
    real_countries = real_countries[:N_COUNTRIES]

    rows = []
    for country in real_countries:
        base_stability = np.clip(np.random.normal(0.6, 0.25), 0.05, 0.95)
        base_volatility = np.clip(np.random.normal(0.3, 0.15), 0.01, 0.95)
        sanctions = 1 if np.random.random() < 0.08 else 0
        for i, month in enumerate(MONTHS):
            # Random walk-ish deviation
            walk = 0.05 * np.sin(2 * np.pi * i / 12)
            stability = np.clip(base_stability + walk + np.random.normal(0, 0.03), 0.0, 1.0)
            volatility = np.clip(base_volatility + 0.5 * walk + np.random.normal(0, 0.02), 0.0, 1.0)
            rows.append({
                "country": country,
                "month": month,
                "political_stability_score": round(stability, 4),
                "currency_volatility_index": round(volatility, 4),
                "trade_sanctions_flag": sanctions,
            })
    return pd.DataFrame(rows)


# ── helper: generate shipment records ──────────────────────────────────────
def generate_shipments(country_risk_df):
    """Generate shipment transaction records with realistic correlations."""
    countries = country_risk_df["country"].unique()
    buyers = [f"buyer_{i:05d}" for i in range(N_BUYERS)]
    exporters = [f"exporter_{i:04d}" for i in range(N_EXPORTERS)]

    # Assign each buyer a home country (weighted toward major economies)
    buyer_country = np.random.choice(countries, size=N_BUYERS, p=None)

    # Build buyer risk profiles (~20% are high-risk)
    buyer_risk_type = np.random.choice(["low", "medium", "high"], size=N_BUYERS, p=[0.5, 0.3, 0.2])

    # Country-level risk lookup
    country_risk_map = {}
    for _, row in country_risk_df.iterrows():
        country_risk_map.setdefault(row["country"], []).append(row)

    records = []
    batch_size = 100_000
    total_batches = N_SHIPMENTS // batch_size + 1

    for batch in range(total_batches):
        start = batch * batch_size
        end = min(start + batch_size, N_SHIPMENTS)
        n = end - start
        if n <= 0:
            break

        shipment_ids = [f"SHP-{start+i:07d}" for i in range(n)]

        # Pick buyers (some repeat — heavy-tail distribution)
        buyer_ids = np.random.choice(buyers, size=n, p=None)

        # Buyer-level features
        buyer_risk_types = [buyer_risk_type[buyers.index(b)] for b in buyer_ids]
        buyer_home_countries = [buyer_country[buyers.index(b)] for b in buyer_ids]

        # Exporters
        exporter_ids = np.random.choice(exporters, size=n)

        # HS code sections (higher categories for certain countries)
        hs_codes = np.random.choice(range(1, N_HSSECTIONS + 1), size=n)

        # Product categories
        categories = np.random.choice(PRODUCT_CATEGORIES, size=n)

        # Shipping dates
        dates = np.random.choice(MONTHS, size=n) + pd.to_timedelta(
            np.random.randint(0, 28, size=n), unit="D"
        )

        # Invoice values — lognormal distribution (most small, some large)
        invoice_values = np.round(np.random.lognormal(mean=9.5, sigma=1.2, size=n), 2)
        invoice_values = np.clip(invoice_values, 100, 5_000_000)

        # Payment terms correlated with buyer risk
        terms = []
        for rt in buyer_risk_types:
            if rt == "high":
                p = [0.50, 0.35, 0.10, 0.04, 0.01]
            elif rt == "medium":
                p = [0.15, 0.40, 0.30, 0.10, 0.05]
            else:
                p = [0.05, 0.20, 0.35, 0.25, 0.15]
            terms.append(np.random.choice(PAYMENT_TERMS, p=p))

        # Payment delay days — depends on payment term and buyer risk
        payment_delays = []
        for rt, term in zip(buyer_risk_types, terms):
            if term == "advance":
                base = 0
                std = 2
            elif term == "lc":
                base = 15
                std = 8
            elif term == "credit_30":
                base = 30
                std = 10
            elif term == "credit_60":
                base = 60
                std = 15
            else:
                base = 90
                std = 20

            if rt == "high":
                delay = int(np.random.normal(base + 20, std * 2))
            elif rt == "medium":
                delay = int(np.random.normal(base + 5, std * 1.2))
            else:
                delay = int(np.random.normal(base, std * 0.8))
            payment_delays.append(max(0, int(delay)))

        # Dispute flag — correlated with delay and risk
        was_disputed = []
        was_paid_in_full = []
        for rt, delay in zip(buyer_risk_types, payment_delays):
            dispute_prob = 0.01
            if rt == "high":
                dispute_prob = 0.12
            elif rt == "medium":
                dispute_prob = 0.04

            if delay > 120:
                dispute_prob += 0.10
            elif delay > 60:
                dispute_prob += 0.05

            disputed = np.random.random() < dispute_prob

            if disputed:
                paid_full_prob = 0.20
            elif rt == "high":
                paid_full_prob = 0.70
            elif rt == "medium":
                paid_full_prob = 0.88
            else:
                paid_full_prob = 0.97

            was_disputed.append(disputed)
            was_paid_in_full.append(np.random.random() < paid_full_prob)

        for i in range(n):
            records.append({
                "shipment_id": shipment_ids[i],
                "exporter_id": exporter_ids[i],
                "buyer_id": buyer_ids[i],
                "buyer_country": buyer_home_countries[i],
                "hs_code": int(hs_codes[i]),
                "product_category": categories[i],
                "shipment_date": dates[i],
                "invoice_value_usd": invoice_values[i],
                "payment_terms": terms[i],
                "payment_delay_days": payment_delays[i],
                "was_disputed": int(was_disputed[i]),
                "was_paid_in_full": int(was_paid_in_full[i]),
            })

        print(f"  Batch {batch+1}/{total_batches}: {n} rows generated ({start}-{end})")

    return pd.DataFrame(records)


# ── helper: compute buyer history aggregates ─────────────────────────────
def compute_buyer_history(shipments_df):
    """Derive buyer-level summary stats from shipment records."""
    agg = shipments_df.groupby("buyer_id").agg(
        total_orders=("shipment_id", "count"),
        total_value_usd=("invoice_value_usd", "sum"),
        avg_payment_delay_days=("payment_delay_days", "mean"),
        dispute_rate=("was_disputed", "mean"),
        paid_in_full_rate=("was_paid_in_full", "mean"),
        avg_invoice_value=("invoice_value_usd", "mean"),
        first_order_date=("shipment_date", "min"),
        last_order_date=("shipment_date", "max"),
        primary_country=("buyer_country", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]),
        primary_category=("product_category", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]),
    ).reset_index()

    agg["value_trend"] = "stable"
    # Mark declining if avg invoice < 70% of overall avg
    overall_avg = shipments_df["invoice_value_usd"].mean()
    agg.loc[agg["avg_invoice_value"] < 0.7 * overall_avg, "value_trend"] = "declining"
    agg.loc[agg["avg_invoice_value"] > 1.3 * overall_avg, "value_trend"] = "growing"

    return agg


# ── main ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== ExportGuard Synthetic Data Generator ===")
    print(f"Target: {N_SHIPMENTS:,} shipment rows\n")

    print("[1/3] Generating country risk signals...")
    country_risk_df = generate_country_risk()
    country_path = BASE / "country_risk.csv"
    country_risk_df.to_csv(country_path, index=False)
    print(f"  -> {len(country_risk_df):,} rows saved to {country_path}")

    print("\n[2/3] Generating shipment records...")
    shipments_df = generate_shipments(country_risk_df)
    ship_path = BASE / "shipments.csv"
    shipments_df.to_csv(ship_path, index=False)
    print(f"  -> {len(shipments_df):,} rows saved to {ship_path}")
    print(f"  Columns: {list(shipments_df.columns)}")
    print(f"  Date range: {shipments_df['shipment_date'].min()} to {shipments_df['shipment_date'].max()}")

    print("\n[3/3] Computing buyer history aggregates...")
    buyer_df = compute_buyer_history(shipments_df)
    buyer_path = BASE / "buyer_history.csv"
    buyer_df.to_csv(buyer_path, index=False)
    print(f"  -> {len(buyer_df):,} buyers saved to {buyer_path}")

    # File sizes
    for f in [country_path, ship_path, buyer_path]:
        size_mb = os.path.getsize(f) / 1_024 / 1_024
        print(f"  {f.name}: {size_mb:.1f} MB")

    print("\nDone. Data ready for pipeline/transform.py")
