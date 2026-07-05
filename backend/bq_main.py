"""
ExportGuard — BigQuery-Powered Backend

Same API as main.py, but reads data from BigQuery instead of local CSVs.
Use this when you have set up BigQuery (run setup_bigquery.py first).

Usage:
    set GOOGLE_APPLICATION_CREDENTIALS=C:\\path\\to\\key.json
    set GOOGLE_CLOUD_PROJECT=your-project-id
    set EXPORTGUARD_DATASET=exportguard
    python backend/bq_main.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

app = FastAPI(title="ExportGuard API (BigQuery)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_DIR = PROJECT_ROOT / "model"
DATA_RAW = PROJECT_ROOT / "data" / "raw"

model = None
config = None
bq_client = None
dataset_name = os.environ.get("EXPORTGUARD_DATASET", "exportguard")


class DealScoreRequest(BaseModel):
    buyer_id: Optional[str] = None
    buyer_country: str
    hs_code: int
    invoice_value_usd: float
    product_category: Optional[str] = None
    payment_terms: Optional[str] = "credit_30"


class DealScoreResponse(BaseModel):
    risk_score: float
    risk_category: str
    recommended_payment_terms: str
    supporting_reasons: list[str]
    country_stability: float = 0.0
    currency_volatility: float = 0.0
    trade_sanctions: bool = False
    avg_payment_delay: float = 0.0
    dispute_rate: float = 0.0
    buyer_reliability_score: float = 0.0
    suggested_credit_limit: float = 0.0


class BuyerHistoryResponse(BaseModel):
    buyer_id: str
    total_orders: int
    total_value_usd: float
    avg_payment_delay_days: float
    dispute_rate: float
    paid_in_full_rate: float
    primary_country: str
    primary_category: str
    value_trend: str


@app.on_event("startup")
def startup():
    global model, config, bq_client

    # Load model
    model_path = MODEL_DIR / "exportguard_model.pkl"
    config_path = MODEL_DIR / "model_config.json"

    if model_path.exists():
        try:
            import joblib
            model = joblib.load(model_path)
            print(f"Model loaded from {model_path}")
        except Exception as e:
            print(f"Model load failed: {e}")
            model = None

    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        print(f"Config loaded from {config_path}")

    # Connect to BigQuery
    cred_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")

    # Support passing credentials as JSON string env var (Render-friendly)
    if cred_json and not cred_path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(cred_json)
        tmp.close()
        cred_path = tmp.name
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
        print(f"Wrote service account from GOOGLE_CREDENTIALS_JSON to {cred_path}")

    if cred_path and Path(cred_path).exists() and project:
        try:
            from google.cloud import bigquery
            bq_client = bigquery.Client(project=project)
            # Test connection
            tables = list(bq_client.list_tables(f"{project}.{dataset_name}"))
            print(f"Connected to BigQuery: {project}.{dataset_name} ({len(tables)} tables)")
        except Exception as e:
            print(f"BigQuery connection failed: {e}")
            bq_client = None
    else:
        print("BigQuery credentials not configured. Set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_CREDENTIALS_JSON.")


def _query(sql: str, job_config=None):
    if bq_client is None:
        raise HTTPException(503, "BigQuery not connected. Set GOOGLE_APPLICATION_CREDENTIALS.")
    job = bq_client.query(sql, job_config=job_config)
    return [dict(row) for row in job.result()]


def _score_to_term(score: float) -> str:
    if score < 30:
        return "Credit terms acceptable (net 30/60)"
    elif score < 60:
        return "Letter of Credit (LC) required"
    else:
        return "Advance payment only"


def _score_to_category(score: float) -> str:
    if score < 30:
        return "Low Risk"
    elif score < 60:
        return "Medium Risk"
    else:
        return "High Risk"


@app.get("/")
@app.head("/")
def root():
    return {"service": "ExportGuard API (BigQuery)", "status": "running"}


@app.post("/score-deal", response_model=DealScoreResponse)
def score_deal(req: DealScoreRequest):
    project = bq_client.project if bq_client else ""
    ds = dataset_name

    # Fetch buyer stats from BigQuery
    buyer_params = QueryJobConfig(
        query_parameters=[
            ScalarQueryParameter("buyer_id", "STRING", req.buyer_id or "")
        ]
    )
    if bq_client:
        try:
            rows = _query(f"""
                SELECT
                  COALESCE(AVG(payment_delay_days), 30) as avg_delay,
                  COALESCE(AVG(IF(was_disputed, 1.0, 0.0)), 0.05) as dispute_rate,
                  COALESCE(AVG(IF(was_paid_in_full, 1.0, 0.0)), 0.9) as paid_in_full_rate,
                  COUNT(*) as total_orders,
                  COALESCE(SUM(invoice_value_usd), 0) as total_value,
                  COALESCE(AVG(invoice_value_usd), {req.invoice_value_usd}) as avg_invoice
                FROM `{project}.{ds}.shipments`
                WHERE buyer_id = @buyer_id
            """, job_config=buyer_params)
            buyer_stats = rows[0] if rows else {}
        except Exception:
            buyer_stats = {}
    else:
        buyer_stats = {}

    # Fetch country risk from BigQuery
    country_params = QueryJobConfig(
        query_parameters=[
            ScalarQueryParameter("country", "STRING", req.buyer_country or "")
        ]
    )
    try:
        country_rows = _query(f"""
            SELECT
              AVG(political_stability_score) as stability,
              AVG(currency_volatility_index) as volatility,
              MAX(trade_sanctions_flag) as sanctions
            FROM `{project}.{ds}.country_risk`
            WHERE UPPER(country) = @country
        """, job_config=country_params)
        country_data = country_rows[0] if country_rows else {}
    except Exception:
        country_data = {}

    # Build feature vector
    stability = country_data.get("stability")
    volatility = country_data.get("volatility")
    sanctions = country_data.get("sanctions")
    features = {
        "payment_delay_days": buyer_stats.get("avg_delay", 30),
        "buyer_dispute_rate": buyer_stats.get("dispute_rate", 0.05),
        "buyer_paid_in_full_rate": buyer_stats.get("paid_in_full_rate", 0.9),
        "invoice_value_usd": req.invoice_value_usd,
        "buyer_total_orders": buyer_stats.get("total_orders", 0),
        "buyer_total_value": buyer_stats.get("total_value", 0),
        "buyer_avg_invoice": buyer_stats.get("avg_invoice", req.invoice_value_usd),
        "buyer_order_rank": 1,
        "political_stability_score": stability if stability is not None else 0.6,
        "currency_volatility_index": volatility if volatility is not None else 0.3,
        "trade_sanctions_flag": int(sanctions) if sanctions is not None else 0,
        "buyer_avg_delay": buyer_stats.get("avg_delay", 30),
    }

    # Score using model or rule-based fallback
    import pandas as pd
    fdf = pd.DataFrame([features])

    if model is not None and config is not None:
        feature_cols = config.get("feature_columns", list(fdf.columns))
        for c in feature_cols:
            if c not in fdf.columns:
                fdf[c] = 0
        X = fdf[feature_cols].fillna(0).astype(float)
        try:
            if hasattr(model, "predict_proba"):
                score = float(model.predict_proba(X)[0][1] * 100)
            else:
                score = float(model.predict(X)[0] * 100)
        except Exception:
            score = 50
    else:
        score = 50

    # Generate reasons
    reasons = []
    orders = features["buyer_total_orders"]
    if orders == 0:
        if bq_client is None:
            reasons.append("Fallback scoring — BigQuery unavailable, using country & value only")
        else:
            reasons.append("Buyer not found in BigQuery — using country-level risk only")
    elif orders < 5:
        reasons.append(f"Limited history — only {int(orders)} prior orders")
    else:
        reasons.append(f"Established buyer with {int(orders)} prior orders")

    delay = features["payment_delay_days"]
    if delay > 60:
        reasons.append(f"Average payment delay of {delay:.0f} days — above threshold")

    stability = features["political_stability_score"]
    if stability < 0.4:
        reasons.append(f"Country stability score is low ({stability:.2f})")
    elif stability > 0.7:
        reasons.append(f"Relatively stable country (stability: {stability:.2f})")

    if features["trade_sanctions_flag"]:
        reasons.append("Destination country has active trade sanctions")

    if features["buyer_dispute_rate"] > 0.15:
        reasons.append(f"Buyer dispute rate is high ({features['buyer_dispute_rate']:.1%})")

    reasons = reasons[:3]
    if not reasons:
        reasons.append("No significant risk indicators found")

    reliability = 100.0
    delay = features["payment_delay_days"]
    dispute = features["buyer_dispute_rate"]
    if orders > 0 and delay > 0:
        reliability = max(0, 100 - (delay * 1.5) - (dispute * 200))

    credit_limit = round(req.invoice_value_usd * (1 - score / 100), 2)

    return DealScoreResponse(
        risk_score=round(score, 1),
        risk_category=_score_to_category(score),
        recommended_payment_terms=_score_to_term(score),
        supporting_reasons=reasons,
        country_stability=round(features["political_stability_score"], 3),
        currency_volatility=round(features["currency_volatility_index"], 3),
        trade_sanctions=bool(features["trade_sanctions_flag"]),
        avg_payment_delay=round(delay, 1),
        dispute_rate=round(dispute, 4),
        buyer_reliability_score=round(reliability, 1),
        suggested_credit_limit=credit_limit,
    )


@app.get("/buyer/{buyer_id}/history")
def buyer_history(buyer_id: str):
    if bq_client is None:
        raise HTTPException(503, "BigQuery not connected")
    project = bq_client.project
    history_params = QueryJobConfig(
        query_parameters=[
            ScalarQueryParameter("buyer_id", "STRING", buyer_id or "")
        ]
    )
    rows = _query(f"""
        SELECT *
        FROM `{project}.{dataset_name}.buyer_risk_summary`
        WHERE buyer_id = @buyer_id
        LIMIT 1
    """, job_config=history_params)
    if not rows:
        raise HTTPException(404, f"Buyer {buyer_id} not found")
    row = rows[0]
    return BuyerHistoryResponse(
        buyer_id=buyer_id,
        total_orders=row.get("total_shipments", 0),
        total_value_usd=round(float(row.get("total_value", 0)), 2),
        avg_payment_delay_days=round(float(row.get("avg_delay_days", 0)), 1),
        dispute_rate=round(float(row.get("dispute_rate", 0)), 4),
        paid_in_full_rate=round(float(row.get("paid_in_full_rate", 0)), 4),
        primary_country=str(row.get("buyer_country", "")),
        primary_category="",
        value_trend="stable",
    )


@app.get("/country/{country}/risk-trend")
def country_risk_trend(country: str):
    if bq_client is None:
        raise HTTPException(503, "BigQuery not connected")
    project = bq_client.project
    trend_params = QueryJobConfig(
        query_parameters=[
            ScalarQueryParameter("country", "STRING", country.upper())
        ]
    )
    rows = _query(f"""
        SELECT * FROM `{project}.{dataset_name}.country_risk_trend`
        WHERE UPPER(country) = @country
        ORDER BY month
        LIMIT 100
    """, job_config=trend_params)
    if not rows:
        raise HTTPException(404, f"Country {country} not found")
    return {"country": country.upper(), "records": rows}


@app.get("/benchmark")
def get_benchmark():
    results_path = PROJECT_ROOT / "benchmark_results.json"
    if not results_path.exists():
        return {"status": "no_data", "message": "Run pipeline/benchmark.py first."}
    with open(results_path) as f:
        data = json.load(f)
    return {
        "status": "complete",
        "note": "Data sourced from BigQuery. Benchmark is from local pipeline run.",
        **data,
    }


@app.get("/looker-studio-url")
def looker_studio_url():
    """Returns the Looker Studio dashboard URL template."""
    project = bq_client.project if bq_client else "<your-project>"
    return {
        "dashboard_url": f"https://lookerstudio.google.com/reporting/create?c.bigQuery.projectId={project}&c.bigQuery.datasetName={dataset_name}",
        "instructions": (
            "1. Open the URL above\n"
            "2. Click 'Create Report'\n"
            "3. Add the 3 views as data sources\n"
            "4. Build the charts as documented in pipeline/bigquery_setup.sql"
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.bq_main:app", host="0.0.0.0", port=8000, reload=True)
