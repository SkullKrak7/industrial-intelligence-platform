import csv
import os
import pickle
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from dagster import (
    AssetExecutionContext,
    Definitions,
    ScheduleDefinition,
    asset,
    define_asset_job,
)

TELEMETRY_PATH   = Path(os.getenv("TELEMETRY_PATH",   "data/telemetry_stream.csv"))
PREDICTIONS_PATH = Path(os.getenv("PREDICTIONS_PATH", "data/predictions.csv"))
PIPELINE_API_URL = os.getenv("PIPELINE_API_URL",      "http://pipeline-api:8000")
MLFLOW_URI       = os.getenv("MLFLOW_TRACKING_URI",   "http://mlflow:5000")
MODEL_NAME       = os.getenv("MLFLOW_MODEL_NAME",     "FailureClassifier")
F1_THRESHOLD     = float(os.getenv("F1_THRESHOLD",    "0.70"))
DBT_PROJECT_DIR  = Path(os.getenv("DBT_PROJECT_DIR",  "dbt"))
DBT_PROFILES_DIR = Path(os.getenv("DBT_PROFILES_DIR", "dbt"))


# ── Asset 1 ───────────────────────────────────────────────────────────────────
_REQUIRED_COLS = {
    "timestamp", "machine_id",
    "rotational_speed", "torque", "tool_wear",
    "temperature", "vibration", "pressure",
}

@asset
def raw_telemetry(context: AssetExecutionContext) -> pd.DataFrame:
    """Read the latest telemetry rows from the twin's streaming CSV."""
    if not TELEMETRY_PATH.exists():
        raise FileNotFoundError(f"{TELEMETRY_PATH} not found — is twin-sim running?")

    df = pd.read_csv(TELEMETRY_PATH, parse_dates=["timestamp"])

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"telemetry_stream.csv is missing required columns: {sorted(missing)}. "
            f"Got: {sorted(df.columns)}"
        )

    null_counts = df[list(_REQUIRED_COLS)].isnull().sum()
    bad_cols = null_counts[null_counts > 0]
    if not bad_cols.empty:
        context.log.warning(f"Null values found: {bad_cols.to_dict()} — dropping affected rows")
        df = df.dropna(subset=list(_REQUIRED_COLS))

    context.log.info(f"Loaded {len(df)} telemetry rows from {TELEMETRY_PATH}")
    return df


# ── Asset 2 ───────────────────────────────────────────────────────────────────
@asset(deps=[raw_telemetry])
def dbt_models(context: AssetExecutionContext) -> None:
    """Run dbt to refresh staging, intermediate, and mart models against DuckDB."""
    cmd = [
        "dbt", "run",
        "--project-dir", str(DBT_PROJECT_DIR),
        "--profiles-dir", str(DBT_PROFILES_DIR),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    context.log.info(result.stdout)
    if result.returncode != 0:
        context.log.error(result.stderr)
        raise RuntimeError(f"dbt run failed:\n{result.stderr}")
    context.log.info("dbt run completed successfully")


# ── Asset 3 ───────────────────────────────────────────────────────────────────
@asset(deps=[dbt_models])
def retrain_model(context: AssetExecutionContext) -> str:
    """Retrain the failure classifier and log the run to MLflow.

    Returns the MLflow run_id so downstream assets can reference it.
    """
    pipeline_dir = Path("pipeline")
    result = subprocess.run(
        ["python", "train_model.py"],
        capture_output=True,
        text=True,
        cwd=str(pipeline_dir),
    )
    context.log.info(result.stdout)
    if result.returncode != 0:
        context.log.error(result.stderr)
        raise RuntimeError(f"train_model.py failed:\n{result.stderr}")

    # Extract run_id from stdout ("MLflow run: <run_id>")
    run_id = None
    for line in result.stdout.splitlines():
        if line.startswith("MLflow run:"):
            run_id = line.split(":", 1)[1].strip()
            break

    if run_id is None:
        context.log.warning("Could not parse MLflow run_id from train output")
        run_id = "unknown"

    context.log.info(f"Training complete. MLflow run_id: {run_id}")
    return run_id


# ── Asset 4 ───────────────────────────────────────────────────────────────────
@asset
def model_health_check(context: AssetExecutionContext, retrain_model: str) -> bool:
    """Gate promotion: set @champion alias only if F1-macro >= threshold.

    This is a registry operation only — it does not serve predictions.
    Splitting promotion and serving into separate assets keeps concerns clean.
    """
    run_id = retrain_model
    if run_id == "unknown":
        context.log.warning("No run_id — skipping promotion check")
        return False

    try:
        import mlflow
        from mlflow.tracking import MlflowClient

        mlflow.set_tracking_uri(MLFLOW_URI)
        client  = MlflowClient()
        run     = client.get_run(run_id)
        f1      = run.data.metrics.get("f1_macro", 0.0)
        context.log.info(f"F1-macro for run {run_id}: {f1:.4f} (threshold {F1_THRESHOLD})")

        if f1 >= F1_THRESHOLD:
            # Find the model version registered from this run
            versions = client.search_model_versions(f"name='{MODEL_NAME}'")
            for mv in sorted(versions, key=lambda v: int(v.version), reverse=True):
                if mv.run_id == run_id:
                    client.set_registered_model_alias(MODEL_NAME, "champion", mv.version)
                    context.log.info(
                        f"✓ {MODEL_NAME} v{mv.version} → @champion (F1={f1:.4f})"
                    )
                    return True
            context.log.warning(f"No model version found for run {run_id}")
        else:
            context.log.warning(
                f"✗ F1={f1:.4f} < {F1_THRESHOLD} — @champion unchanged"
            )
    except Exception as e:
        context.log.error(f"MLflow promotion check failed: {e}")

    return False


# ── Asset 5 ───────────────────────────────────────────────────────────────────
@asset
def write_predictions(
    context: AssetExecutionContext,
    raw_telemetry: pd.DataFrame,
    model_health_check: bool,
) -> None:
    """Call /v1/predict for each telemetry row and append results to predictions.csv.

    Idempotent: skips any telemetry row whose timestamp is already in predictions.csv
    so re-running the asset never produces duplicate rows.
    Runs regardless of whether promotion happened — serves the current @champion.
    """
    PREDICTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load already-processed timestamps to avoid duplicates on re-run
    seen_timestamps: set = set()
    if PREDICTIONS_PATH.exists():
        try:
            existing = pd.read_csv(PREDICTIONS_PATH)
            seen_timestamps = set(existing["timestamp"].astype(str).tolist())
        except Exception:
            seen_timestamps = set()

    write_header = not PREDICTIONS_PATH.exists()
    rows_written = 0
    errors       = 0

    with open(PREDICTIONS_PATH, "a", newline="") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(["timestamp", "machine_id", "confidence", "anomaly", "threshold"])

        for _, row in raw_telemetry.iterrows():
            ts = str(row.get("timestamp", ""))
            if ts in seen_timestamps:
                continue  # already predicted this row — skip
            payload = {
                "machine_id":       str(row.get("machine_id", "M-001")),
                "rotational_speed": float(row.get("rotational_speed", 1538.0)),
                "torque":           float(row.get("torque", 40.0)),
                "tool_wear":        float(row.get("tool_wear", 108.0)),
            }
            try:
                resp = requests.post(
                    f"{PIPELINE_API_URL}/v1/predict",
                    json=payload,
                    timeout=5,
                )
                if resp.status_code == 200:
                    body = resp.json()
                    ts   = row.get("timestamp", datetime.now().isoformat())
                    writer.writerow([
                        ts, body["machine_id"], body["confidence"],
                        body["anomaly"], body["threshold"],
                    ])
                    seen_timestamps.add(str(ts))
                    rows_written += 1
                else:
                    context.log.warning(
                        f"Predict {resp.status_code} for {payload['machine_id']}"
                    )
                    errors += 1
            except Exception as e:
                context.log.warning(f"Request failed: {e}")
                errors += 1

    context.log.info(
        f"write_predictions: {rows_written} rows written, {errors} errors → {PREDICTIONS_PATH}"
    )


# ── Job + Schedule ─────────────────────────────────────────────────────────────
maintenance_job = define_asset_job(
    name="maintenance_pipeline",
    selection=[raw_telemetry, dbt_models, retrain_model, model_health_check, write_predictions],
)

daily_schedule = ScheduleDefinition(
    job=maintenance_job,
    cron_schedule="0 2 * * *",  # 02:00 UTC daily
)

defs = Definitions(
    assets=[raw_telemetry, dbt_models, retrain_model, model_health_check, write_predictions],
    jobs=[maintenance_job],
    schedules=[daily_schedule],
)
