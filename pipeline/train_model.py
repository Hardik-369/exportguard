"""
ExportGuard — cuML Risk Model Training.

Trains a RandomForestClassifier (or LogisticRegression) on the
feature-engineered dataset to predict payment_default_risk.

Output:
  - model/exportguard_model.pkl  (cuml or sklearn artifact)
  - model/model_config.json      (score bands → payment terms)
  - model/feature_importance.png (top 15 features)
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.transform import run_pipeline

MODEL_DIR = PROJECT_ROOT / "model"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def try_import_cuml():
    """Try to import cuML; fall back to sklearn."""
    try:
        from cuml.ensemble import RandomForestClassifier
        from cuml.metrics import accuracy_score
        print("Using cuML (GPU-accelerated)")
        return "cuml", RandomForestClassifier, accuracy_score
    except ImportError:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score
        print("cuML not available. Falling back to sklearn (CPU).")
        return "sklearn", RandomForestClassifier, accuracy_score


def prepare_features(df: pd.DataFrame):
    """Select feature columns and target from the engineered DataFrame."""
    feature_cols = [
        "invoice_value_usd",
        "payment_delay_days",
        "political_stability_score",
        "currency_volatility_index",
        "trade_sanctions_flag",
        "buyer_total_orders",
        "buyer_total_value",
        "buyer_avg_delay",
        "buyer_dispute_rate",
        "buyer_avg_invoice",
        "buyer_paid_in_full_rate",
        "buyer_order_rank",
    ]
    target_col = "payment_default_risk"

    # Filter to only available columns
    available = [c for c in feature_cols if c in df.columns]
    missing = set(feature_cols) - set(available)
    if missing:
        print(f"Warning: missing columns {missing}, continuing with available")

    X = df[available].copy()
    y = df[target_col].copy()

    # Convert booleans to int
    for c in X.columns:
        if X[c].dtype == bool:
            X[c] = X[c].astype(int)

    # Fill any remaining NaN
    X = X.fillna(X.median(numeric_only=True))

    return X, y, available


def score_to_payment_term(score: float) -> str:
    """Map risk score 0–100 to recommended payment term."""
    if score < 30:
        return "Credit terms acceptable (net 30/60)"
    elif score < 60:
        return "Letter of Credit (LC) required"
    else:
        return "Advance payment only"


def main():
    print("=" * 60)
    print("ExportGuard - Risk Model Training")
    print("=" * 60)

    # Step 1: Run the full pipeline to get engineered data
    print("\n[1/4] Running feature engineering pipeline...")
    df = run_pipeline("pandas")
    print(f"  Dataset shape: {df.shape}")

    # Step 2: Prepare features
    print("\n[2/4] Preparing features...")
    X, y, feature_cols = prepare_features(df)
    print(f"  Features: {len(feature_cols)}")
    print(f"  X shape: {X.shape}, y distribution:\n  {y.value_counts().to_dict()}")

    # Step 3: Train the model
    print("\n[3/4] Training model...")
    backend, ModelClass, score_func = try_import_cuml()

    # Use 80/20 split
    split = int(0.8 * len(X))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    # Check if we're using cuML
    use_cuml = backend == "cuml"
    if use_cuml:
        # cuML expects numpy arrays or cuDF DataFrames
        # We can pass pandas DataFrames directly
        model = ModelClass(
            n_estimators=200,
            max_depth=16,
            random_state=42,
            n_streams=1,
            verbosity=0,
        )
    else:
        model = ModelClass(
            n_estimators=200,
            max_depth=16,
            random_state=42,
            n_jobs=-1,
        )

    model.fit(X_train, y_train)

    # Step 4: Evaluate
    y_pred = model.predict(X_test)
    accuracy = score_func(y_test, y_pred)

    # Get probabilities (for risk score)
    if hasattr(model, "predict_proba"):
        y_proba = model.predict_proba(X_test)
        risk_scores = y_proba[:, 1] * 100  # probability of default → 0-100
    else:
        risk_scores = y_pred.astype(float) * 100

    print(f"  Test accuracy: {accuracy:.4f}")
    print(f"  Avg risk score: {risk_scores.mean():.2f} / 100")

    # Feature importance
    if hasattr(model, "feature_importances_"):
        importance = model.feature_importances_
        print("\n  Top 10 features:")
        sorted_idx = np.argsort(importance)[::-1]
        for i in sorted_idx[:10]:
            print(f"    {feature_cols[i]}: {importance[i]:.4f}")
    else:
        importance = None

    # Save model
    print("\n[4/4] Saving model artifact...")
    model_path = MODEL_DIR / "exportguard_model.pkl"
    try:
        import joblib
        joblib.dump(model, model_path)
        print(f"  Model saved to {model_path}")
    except Exception as e:
        # Try pickle directly
        import pickle
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        print(f"  Model saved (pickle) to {model_path}")

    # Save config
    config = {
        "model_backend": backend,
        "feature_columns": feature_cols,
        "test_accuracy": round(float(accuracy), 4),
        "score_bands": {
            "advance_only": {"min": 0, "max": 30, "term": "Advance payment only"},
            "lc_required": {"min": 30, "max": 60, "term": "Letter of Credit (LC) required"},
            "credit_terms": {"min": 60, "max": 100, "term": "Credit terms acceptable (net 30/60)"},
        },
        "score_to_term_fn": "score_to_payment_term",
    }
    config_path = MODEL_DIR / "model_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Config saved to {config_path}")

    print("\nTraining complete!")
    return model, config


if __name__ == "__main__":
    main()
