# ExportGuard — BigQuery + Looker Studio Setup Guide

This guide walks you through connecting ExportGuard to Google Cloud BigQuery
and building a Looker Studio dashboard — all on the free tier.

---

## Step 1: Create a Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Click the project dropdown at the top → **New Project**
3. Name it `exportguard` (or anything)
4. Click **Create**
5. Wait for it to finish, then select your new project from the dropdown

---

## Step 2: Enable APIs

1. Go to https://console.cloud.google.com/apis/library
2. Search for and enable **both** of these:
   - **BigQuery API**
   - **Cloud Storage API**

---

## Step 3: Create a Service Account Key

1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts
2. Click **+ Create Service Account**
3. Name: `exportguard-sa` → Click **Create and Continue**
4. Click **Select a role** → Add these three roles (one at a time):
   - `BigQuery Data Editor`
   - `BigQuery Job User`
   - `Storage Object Admin`
5. Click **Continue** → Click **Done**
6. In the service accounts list, click on `exportguard-sa`
7. Go to the **Keys** tab → **Add Key** → **Create New Key** → **JSON**
8. The JSON file downloads automatically — keep it safe

---

## Step 4: Set Environment Variables & Run Setup

Open **PowerShell** or **Command Prompt** in the project folder and run:

```powershell
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\the\downloaded-key.json
set GOOGLE_CLOUD_PROJECT=exportguard-XXXXX    (use YOUR actual project ID)
python backend/setup_bigquery.py --dataset=exportguard
```

The script will:
- Create the dataset
- Upload all 3 CSV tables
- Create 3 analytics views

Expected output:
```
[OK] Created dataset exportguard
[OK] Created table exportguard.shipments
[OK] Loaded 3,000,000 rows into shipments
[OK] Created table exportguard.country_risk
[OK] Loaded 2,880 rows into country_risk
[OK] Created table exportguard.buyer_history
[OK] Loaded 8,000 rows into buyer_history
[OK] Created view buyer_risk_summary
[OK] Created view country_risk_trend
[OK] Created view shipment_outcomes_by_hs_code
```

---

## Step 5: Start the BigQuery-Powered API

```powershell
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\key.json
set GOOGLE_CLOUD_PROJECT=exportguard-XXXXX
set EXPORTGUARD_DATASET=exportguard
python backend/bq_main.py
```

This runs the same API at http://localhost:8000 but reads from BigQuery.

The frontend at http://localhost:3000 connects to this automatically.

---

## Step 6: Build the Looker Studio Dashboard

1. Go to https://lookerstudio.google.com/
2. Click **Create** → **Report**
3. Click **Add Data** → Select **BigQuery**
4. Choose your project → dataset `exportguard`
5. For EACH of the 3 views, click **Add**:

### Chart 1: Buyer Risk Leaderboard
- Data source: `buyer_risk_summary`
- Chart type: **Bar chart**
- Setup:
  - Dimension: `buyer_id`
  - Metric: `risk_score` → sort **Descending**, show **Top 20**
  - Color by: `risk_category` (add as Breakdown dimension)
  - Title: "Top 20 Buyers by Risk Score"

### Chart 2: Country Risk Over Time
- Data source: `country_risk_trend`
- Chart type: **Time series** (line chart)
- Setup:
  - Date range dimension: `month`
  - Metric: `composite_risk_index` → aggregation **AVG**
  - Breakdown dimension: `country` → filter to Top 10
  - Title: "Country Risk Index Over Time"

### Chart 3: HS-code Exposure Breakdown
- Data source: `shipment_outcomes_by_hs_code`
- Chart type: **Stacked bar chart**
- Setup:
  - Dimension: `product_category`
  - Metric: `total_value_usd`
  - Sort: `total_value_usd` Descending
  - Title: "Shipment Value by Product Category"

### Dashboard layout (recommended):
```
+---------------------------------------------+
|  ExportGuard — Trade Risk Dashboard          |
+---------------------------------------------+
|  Buyer Risk Leaderboard  |  Country Risk     |
|  (bar chart, left)       |  Over Time         |
|                          |  (line chart, right)|
+---------------------------------------------+
|  HS-code Exposure Breakdown                  |
|  (stacked bar, full width)                  |
+---------------------------------------------+
```

---

## Step 7: Verify End-to-End

1. Open http://localhost:3000
2. Enter a deal and submit
3. The risk score and terms come from BigQuery via the API
4. The same data appears in your Looker Studio dashboard at the Looker URL

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS not set` | Run the `set` command in the SAME terminal |
| `BigQuery API not enabled` | Go to APIs & Services → Enable it (may take 2 min) |
| `Dataset already exists` | Use a different `--dataset` name or delete manually |
| `Permission denied` | Make sure the service account has the 3 roles listed above |
| Looker Studio shows no data | Check that the views have data: run `SELECT * FROM ... LIMIT 5` in BigQuery console |
