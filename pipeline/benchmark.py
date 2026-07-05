"""
ExportGuard — pandas vs cudf.pandas benchmark.

Run this on a machine with a GPU (Google Colab, Kaggle, or local with RAPIDS).
On a CPU-only machine it can still run the pandas path for reference.

Usage:
    # CPU baseline only
    python pipeline/benchmark.py

    # GPU-accelerated (requires RAPIDS)
    # In a Colab/Kaggle notebook, run cells:
    #   !pip install cudf-pandas cuml
    #   import cudf.pandas; cudf.pandas.install()
    #   %run pipeline/benchmark.py

Output:
  - benchmark_results.json  (wall-clock seconds for each codepath)
  - Prints summary to stdout
"""

import json
import time
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PIPELINE_DIR.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"

# ── detect if cudf.pandas is active ────────────────────────────────────────
def is_gpu_active():
    """Check if cudf.pandas has monkey-patched pandas."""
    try:
        import pandas as pd
        # If cudf.pandas is installed, DataFrame will have a _using_cudf attr
        import io, csv
        test = pd.DataFrame({"a": [1, 2, 3]})
        return hasattr(test, "_using_cudf") and test._using_cudf
    except Exception:
        return False


GPU_ACTIVE = is_gpu_active()
ENGINE = "cudf.pandas" if GPU_ACTIVE else "pandas"

print("=" * 60)
print(f"ExportGuard Benchmark - Engine: {ENGINE}")
print(f"GPU active: {GPU_ACTIVE}")
print("=" * 60)

# ── import the shared transform ────────────────────────────────────────────
sys.path.insert(0, str(PROJECT_ROOT))
from pipeline.transform import load_data, engineer_features


def benchmark_run(label: str) -> float:
    """Run the full pipeline and return wall-clock seconds."""
    print(f"\n{'-' * 40}")
    print(f"Starting: {label}")
    print(f"{'-' * 40}")

    t0 = time.time()
    shipments, country_risk = load_data(ENGINE)
    t1 = time.time()
    print(f"  Load time: {t1 - t0:.2f}s")

    result = engineer_features(shipments, country_risk, ENGINE)
    t2 = time.time()
    print(f"  Transform time: {t2 - t1:.2f}s")
    print(f"  Total time: {t2 - t0:.2f}s")
    print(f"  Result shape: {result.shape}")

    return t2 - t0


# ── run the benchmark ──────────────────────────────────────────────────────
total_time = benchmark_run(f"Full pipeline ({ENGINE})")

# Save results
result = {
    "engine": ENGINE,
    "gpu_active": GPU_ACTIVE,
    "total_time_seconds": round(total_time, 3),
    "total_time_formatted": f"{int(total_time // 60)}m {int(total_time % 60)}s"
    if total_time > 60
    else f"{total_time:.2f}s",
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
}

results_path = PROJECT_ROOT / "benchmark_results.json"
# Load existing results if any, then update
if results_path.exists():
    with open(results_path) as f:
        try:
            existing = json.load(f)
        except json.JSONDecodeError:
            existing = {}
    existing[ENGINE] = result
else:
    existing = {ENGINE: result}

with open(results_path, "w") as f:
    json.dump(existing, f, indent=2)

print(f"\nResults saved to {results_path}")
print(json.dumps(existing, indent=2))

# ── if this was the first (pandas) run, hint about GPU ─────────────────────
if not GPU_ACTIVE:
    print("\n" + "!" * 60)
    print("CPU baseline complete. To run the GPU-accelerated path:")
    print("  1. Open in Google Colab or Kaggle with a T4 GPU")
    print("  2. Install RAPIDS: !pip install cudf-pandas cuml")
    print("  3. Import cudf.pandas before pandas:")
    print("       import cudf.pandas; cudf.pandas.install()")
    print("  4. Run: %run pipeline/benchmark.py")
    print("!" * 60)
else:
    print("\n" + "!" * 60)
    print("GPU run complete!")
    print("To compare: run on CPU-only to get the pandas baseline,")
    print("then on Colab/Kaggle GPU for cudf.pandas.")
    print("!" * 60)
