# ExportGuard

**Real-time export risk intelligence for Indian MSME exporters.**

Decide, in seconds, whether a new export deal is safe to take and what payment terms to demand.

---

## Problem

Indian MSME exporters have no fast way to check a buyer's payment history, destination country risk, or HS-code tariff exposure before quoting. They either take deals blind or spend hours on manual research they don't have time for.

## Solution

ExportGuard provides a single risk score (0–100) + recommended payment terms + supporting evidence, delivered through a dashboard and a queryable API. The pipeline runs **10–50× faster on GPU** (cudf.pandas + RAPIDS cuML) than on CPU, making real-time scoring practical.

---

## Architecture

```
data/generate_synthetic_data.py     # 2-5M row synthetic dataset
pipeline/transform.py               # Shared cleaning + feature engineering
pipeline/benchmark.py               # pandas vs cudf.pandas timing comparison
pipeline/train_model.py             # cuML RandomForest risk model
pipeline/bigquery_setup.sql         # BigQuery tables + Looker Studio views
backend/main.py                     # FastAPI API server
backend/ingest_to_bq.py             # GCS + BigQuery uploader
frontend/                           # Next.js + Tailwind CSS app
model/exportguard_model.pkl         # Trained model artifact
model/model_config.json             # Score bands → payment terms mapping
```

---

## Quick Start

### 1. Generate synthetic data

```bash
cd exportguard
python data/generate_synthetic_data.py
```

This creates 3 CSV files in `data/raw/` (~1-2 GB total for 3M rows).

### 2. Run the benchmark (CPU baseline)

```bash
python pipeline/benchmark.py
```

Saves timing to `benchmark_results.json`.

### 3. Train the risk model

```bash
python pipeline/train_model.py
```

Creates `model/exportguard_model.pkl` and `model/model_config.json`.

### 4. Start the API

```bash
python backend/main.py
```

API available at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

---

## GPU Benchmark (Google Colab / Kaggle)

To see the 10-50× speedup, run the same pipeline on a free T4 GPU:

1. Upload `pipeline/benchmark.py` and `pipeline/transform.py` to a Colab/Kaggle notebook.
2. Ensure `data/raw/shipments.csv` and `data/raw/country_risk.csv` are available.
3. Install RAPIDS:
   ```python
   !pip install cudf-pandas cuml
   ```
4. Run the GPU-accelerated benchmark:
   ```python
   import cudf.pandas
   cudf.pandas.install()
   %run pipeline/benchmark.py
   ```
5. The script appends results to `benchmark_results.json`. Re-run on CPU for the baseline.

**Expected result:** A visible, non-trivial speed difference at 2-5M rows.

---

## Cloud Setup (BigQuery + Looker Studio)

ExportGuard can push data to Google Cloud for dashboarding:

### Prerequisites
- Google Cloud project with BigQuery + GCS enabled (free tier)
- Service account key with `roles/storage.objectAdmin`, `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`
- Set env vars:
  ```bash
  export GOOGLE_APPLICATION_CREDENTIALS="path/to/key.json"
  export GOOGLE_CLOUD_PROJECT="your-project-id"
  export EXPORTGUARD_GCS_BUCKET="exportguard-data-lake"
  ```

### Ingest
```bash
python backend/ingest_to_bq.py --dataset=exportguard
```

### Create views
Run `pipeline/bigquery_setup.sql` in BigQuery console.

### Looker Studio dashboard
1. Go to `https://lookerstudio.google.com/`
2. Create a new report, connect to BigQuery → your dataset
3. Add the 3 views as data sources:
   - `buyer_risk_summary` → **Buyer Risk Leaderboard** (bar chart, top 20 by risk_score)
   - `country_risk_trend` → **Country Risk Over Time** (time series, composite_risk_index)
   - `shipment_outcomes_by_hs_code` → **HS-code Exposure Breakdown** (stacked bar, total_value_usd)

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/score-deal` | POST | Score a deal — returns risk score, payment terms, reasons |
| `/buyer/{id}/history` | GET | Buyer aggregated shipment history |
| `/country/{country}/risk-trend` | GET | Country risk time series |
| `/benchmark` | GET | pandas vs cudf.pandas timing comparison |

### POST /score-deal

```json
{
  "buyer_id": "buyer_00001",
  "buyer_country": "USA",
  "hs_code": 61,
  "invoice_value_usd": 50000,
  "product_category": "textiles",
  "payment_terms": "credit_30"
}
```

Response:
```json
{
  "risk_score": 12.5,
  "risk_category": "Low Risk",
  "recommended_payment_terms": "Advance payment only",
  "supporting_reasons": [
    "Established buyer with 47 prior orders",
    "Relatively stable country (stability: 0.82)",
    "Buyer dispute rate is low (1.2%)"
  ]
}
```

---

## Synthetic Data Notes

The dataset in `data/raw/` is **synthetic** but statistically realistic:

- **Shipments:** 3M rows modeled on India DGFT / US Customs bulk data
- **Countries:** 80, with realistic political stability and currency volatility
- **Buyers:** 8,000, with heavy-tail order distribution (Pareto principle)
- **Payment behaviour:** Correlated with buyer risk profile — high-risk buyers have higher dispute rates and delays
- **Features engineered:** Rolling payment delay, dispute rate, order count, value trend, country risk signals

The synthetic data is designed so the pandas-vs-cudf.pandas benchmark produces a meaningful (10-50×) speed difference at scale.

---

## Screenshots

*(Add screenshots here once the app is running)*

- **Benchmark chart:** pandas vs cudf.pandas bar chart showing wall-clock time
- **Result card:** Risk score ring with supporting factors
- **Looker Studio dashboard:** Buyer risk leaderboard, country risk trend, HS-code breakdown

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI |
| Frontend | Next.js 14, Tailwind CSS 3 |
| Data (CPU) | pandas, scikit-learn |
| Data (GPU) | cudf.pandas, cuML (RAPIDS) |
| Cloud | Google Cloud Storage, BigQuery |
| Viz | Looker Studio |
| Benchmark | Custom wall-clock timing script |
