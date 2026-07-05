"""
ExportGuard — FastAPI Backend

Endpoints:
  POST /score-deal      — Score a new deal (buyer, hs_code, value)
  GET  /buyer/{id}/history    — Buyer aggregated history
  GET  /country/{country}/risk-trend — Country risk time series
  GET  /benchmark        — pandas vs cudf.pandas timing comparison
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure pipeline module is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.transform import run_pipeline

app = FastAPI(title="ExportGuard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load model and config at startup ──────────────────────────────────────
MODEL_DIR = PROJECT_ROOT / "model"
DATA_RAW = PROJECT_ROOT / "data" / "raw"

model = None
config = None
transformed_df = None  # Cached for local inference

@app.on_event("startup")
def load_artifacts():
    global model, config, transformed_df
    model_path = MODEL_DIR / "exportguard_model.pkl"
    config_path = MODEL_DIR / "model_config.json"

    if model_path.exists():
        try:
            import joblib
            model = joblib.load(model_path)
            print(f"Model loaded from {model_path}")
        except Exception as e:
            print(f"Could not load model: {e}")
            model = None
    else:
        print("No model found. Run pipeline/train_model.py first.")
        model = None

    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        print(f"Config loaded from {config_path}")
    else:
        config = None

    # Pre-run pipeline so we have buyer/country data to query
    if DATA_RAW.joinpath("shipments.csv").exists():
        try:
            transformed_df = run_pipeline("pandas")
            print(f"Pipeline data cached: {len(transformed_df):,} rows")
        except Exception as e:
            print(f"Could not pre-run pipeline: {e}")
            transformed_df = None
    else:
        print("No raw data found. Generate it with data/generate_synthetic_data.py")
        transformed_df = None


# ── Models ────────────────────────────────────────────────────────────────

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


# ── Helper functions ──────────────────────────────────────────────────────

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


def _get_feature_row(
    buyer_id: str,
    buyer_country: str,
    hs_code: int,
    invoice_value_usd: float,
    product_category: str,
    payment_terms: str,
) -> pd.DataFrame:
    """Build a feature vector for a hypothetical new shipment."""
    # Look up buyer history from cached data
    buyer_data = None
    country_data = None
    if transformed_df is not None:
        bdf = transformed_df[transformed_df["buyer_id"] == buyer_id]
        if len(bdf) > 0:
            buyer_data = bdf.iloc[0]
            buyer_country = buyer_data.get("buyer_country", buyer_country)
        # Country risk — take median
        cdf = transformed_df[transformed_df["buyer_country"] == buyer_country.upper()]
        if len(cdf) > 0:
            country_data = cdf.iloc[0]

    features = {
        "invoice_value_usd": invoice_value_usd,
        "payment_delay_days": buyer_data.get("buyer_avg_delay", 30) if buyer_data is not None else 30,
        "political_stability_score": country_data.get("political_stability_score", 0.6) if country_data is not None else 0.6,
        "currency_volatility_index": country_data.get("currency_volatility_index", 0.3) if country_data is not None else 0.3,
        "trade_sanctions_flag": int(country_data.get("trade_sanctions_flag", 0)) if country_data is not None else 0,
        "buyer_total_orders": buyer_data.get("buyer_total_orders", 0) if buyer_data is not None else 0,
        "buyer_total_value": buyer_data.get("buyer_total_value", 0) if buyer_data is not None else 0,
        "buyer_avg_delay": buyer_data.get("buyer_avg_delay", 30) if buyer_data is not None else 30,
        "buyer_dispute_rate": buyer_data.get("buyer_dispute_rate", 0.05) if buyer_data is not None else 0.05,
        "buyer_avg_invoice": buyer_data.get("buyer_avg_invoice", invoice_value_usd) if buyer_data is not None else invoice_value_usd,
        "buyer_paid_in_full_rate": buyer_data.get("buyer_paid_in_full_rate", 0.9) if buyer_data is not None else 0.9,
        "buyer_order_rank": 1,  # New order
    }
    return pd.DataFrame([features])


def _predict_risk(features: pd.DataFrame) -> tuple[float, list[str]]:
    """Run model inference and return (risk_score, reasons)."""
    if model is None or config is None:
        # Fallback: rule-based scoring
        return _rule_based_score(features)

    feature_cols = config.get("feature_columns", list(features.columns))
    # Ensure all expected columns exist
    for c in feature_cols:
        if c not in features.columns:
            features[c] = 0

    X = features[feature_cols].fillna(0).astype(float)

    try:
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)
            score = float(proba[0][1] * 100)
        else:
            pred = model.predict(X)
            score = float(pred[0] * 100)
    except Exception:
        score = _rule_based_score(features)[0]

    reasons = _generate_reasons(features, score)
    return score, reasons


def _rule_based_score(features: pd.DataFrame) -> tuple[float, list[str]]:
    """Fallback scoring when no model is available."""
    row = features.iloc[0]
    score = 0.0
    reasons = []

    # Payment delay
    delay = row.get("payment_delay_days", 30)
    if delay > 60:
        score += 30
        reasons.append(f"High average payment delay ({delay:.0f} days)")
    elif delay > 30:
        score += 10

    # Dispute rate
    dispute = row.get("buyer_dispute_rate", 0.05)
    if dispute > 0.1:
        score += 25
        reasons.append(f"Elevated dispute rate ({dispute:.1%})")
    elif dispute > 0.05:
        score += 10

    # Country stability
    stability = row.get("political_stability_score", 0.6)
    if stability < 0.3:
        score += 20
        reasons.append("Low political stability in buyer's country")
    elif stability < 0.5:
        score += 10

    # Sanctions
    if row.get("trade_sanctions_flag", 0) == 1:
        score += 15
        reasons.append("Trade sanctions active on buyer's country")

    # Paid in full rate
    pif = row.get("buyer_paid_in_full_rate", 0.9)
    if pif < 0.7:
        score += 15
        reasons.append(f"Low payment completion rate ({pif:.1%})")

    # Invoice value relative to average
    avg_inv = row.get("buyer_avg_invoice", row.get("invoice_value_usd", 1000))
    inv = row.get("invoice_value_usd", 1000)
    if inv > 3 * avg_inv and avg_inv > 0:
        score += 10
        reasons.append(f"Invoice value (${inv:,.0f}) is 3x buyer's average — verify capacity")

    score = min(score, 100)

    if not reasons:
        reasons.append("No significant risk indicators found")

    return score, reasons


def _generate_reasons(features: pd.DataFrame, score: float) -> list[str]:
    """Generate top-3 supporting reasons from feature values."""
    reasons = []
    row = features.iloc[0]

    # Buyer history
    orders = row.get("buyer_total_orders", 0)
    if orders == 0:
        reasons.append("New buyer — no prior transaction history available")
    elif orders < 5:
        reasons.append(f"Limited history — only {int(orders)} prior orders")
    else:
        reasons.append(f"Established buyer with {int(orders)} prior orders")

    # Payment behaviour
    delay = row.get("payment_delay_days", 30)
    if delay > 60:
        reasons.append(f"Average payment delay of {delay:.0f} days — above threshold")
    elif delay > 30:
        reasons.append(f"Moderate payment delay ({delay:.0f} days)")

    # Country
    stability = row.get("political_stability_score", 0.6)
    if stability < 0.4:
        reasons.append(f"Country stability score is low ({stability:.2f})")
    elif stability > 0.7:
        reasons.append(f"Relatively stable country (stability: {stability:.2f})")

    # Sanctions
    if row.get("trade_sanctions_flag", 0) == 1:
        reasons.append("Destination country has active trade sanctions")

    # Dispute
    dispute = row.get("buyer_dispute_rate", 0)
    if dispute > 0.15:
        reasons.append(f"Buyer dispute rate is high ({dispute:.1%})")

    return reasons[:3]


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"service": "ExportGuard API", "status": "running"}


@app.post("/score-deal", response_model=DealScoreResponse)
def score_deal(req: DealScoreRequest):
    features = _get_feature_row(
        buyer_id=req.buyer_id or "new_buyer",
        buyer_country=req.buyer_country,
        hs_code=req.hs_code,
        invoice_value_usd=req.invoice_value_usd,
        product_category=req.product_category or "general",
        payment_terms=req.payment_terms or "credit_30",
    )

    risk_score, reasons = _predict_risk(features)

    f = features.iloc[0] if len(features) > 0 else {}
    delay = float(f.get("payment_delay_days", 0))
    dispute = float(f.get("buyer_dispute_rate", 0))
    orders = int(f.get("buyer_total_orders", 0))
    reliability = 100.0
    if orders > 0 and delay > 0:
        reliability = max(0, 100 - (delay * 1.5) - (dispute * 200))
    credit_limit = round(req.invoice_value_usd * (1 - risk_score / 100), 2)

    return DealScoreResponse(
        risk_score=round(risk_score, 1),
        risk_category=_score_to_category(risk_score),
        recommended_payment_terms=_score_to_term(risk_score),
        supporting_reasons=reasons,
        country_stability=round(float(f.get("political_stability_score", 0)), 3),
        currency_volatility=round(float(f.get("currency_volatility_index", 0)), 3),
        trade_sanctions=bool(int(f.get("trade_sanctions_flag", 0))),
        avg_payment_delay=round(delay, 1),
        dispute_rate=round(dispute, 4),
        buyer_reliability_score=round(reliability, 1),
        suggested_credit_limit=credit_limit,
    )


@app.get("/buyer/{buyer_id}/history")
def buyer_history(buyer_id: str):
    if transformed_df is None:
        raise HTTPException(503, "Data not loaded. Run the pipeline first.")

    bdf = transformed_df[transformed_df["buyer_id"] == buyer_id]
    if len(bdf) == 0:
        raise HTTPException(404, f"Buyer {buyer_id} not found")

    row = bdf.iloc[0]
    return BuyerHistoryResponse(
        buyer_id=buyer_id,
        total_orders=int(row.get("buyer_total_orders", 0)),
        total_value_usd=round(float(row.get("buyer_total_value", 0)), 2),
        avg_payment_delay_days=round(float(row.get("buyer_avg_delay", 0)), 1),
        dispute_rate=round(float(row.get("buyer_dispute_rate", 0)), 4),
        paid_in_full_rate=round(float(row.get("buyer_paid_in_full_rate", 0)), 4),
        primary_country=str(row.get("buyer_country", "")),
        primary_category=str(row.get("product_category", "")),
        value_trend="stable",
    )


@app.get("/country/{country}/risk-trend")
def country_risk_trend(country: str):
    if transformed_df is None:
        # Try loading raw country risk CSV
        risk_path = DATA_RAW / "country_risk.csv"
        if not risk_path.exists():
            raise HTTPException(503, "Data not available")
        cr = pd.read_csv(risk_path, parse_dates=["month"])
    else:
        cr = transformed_df.rename(columns={
            "political_stability_score": "political_stability_score",
            "currency_volatility_index": "currency_volatility_index",
            "trade_sanctions_flag": "trade_sanctions_flag",
        })

    country_upper = country.upper().strip()
    cdf = cr[cr["buyer_country"] == country_upper] if "buyer_country" in cr.columns else \
          cr[cr["country"] == country_upper]

    if len(cdf) == 0:
        raise HTTPException(404, f"Country {country} not found")

    records = cdf.to_dict(orient="records")
    return {"country": country_upper, "records": records[:100]}


@app.get("/benchmark")
def get_benchmark():
    results_path = PROJECT_ROOT / "benchmark_results.json"
    if not results_path.exists():
        return {
            "status": "no_data",
            "message": "Run pipeline/benchmark.py on CPU and GPU to generate comparison.",
        }

    with open(results_path) as f:
        data = json.load(f)

    # Build comparison summary
    pandas_time = data.get("pandas", {}).get("total_time_seconds")
    cudf_time = data.get("cudf.pandas", {}).get("total_time_seconds")

    summary = {
        "status": "complete",
        "pandas_seconds": pandas_time,
        "cudf_pandas_seconds": cudf_time,
        "speedup": round(pandas_time / cudf_time, 1) if pandas_time and cudf_time else None,
        "raw": data,
    }

    if pandas_time and cudf_time:
        summary["takeaway"] = (
            f"Same risk pipeline: {_fmt_time(pandas_time)} on CPU vs {_fmt_time(cudf_time)} on GPU "
            f"— the difference between running this once a week and running it live on every quote."
        )
    elif pandas_time:
        summary["takeaway"] = f"CPU baseline: {_fmt_time(pandas_time)}. Run on GPU for comparison."

    return summary


def _fmt_time(seconds: float) -> str:
    if seconds >= 60:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{seconds:.2f}s"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
