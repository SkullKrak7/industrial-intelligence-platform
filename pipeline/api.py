import json
import logging
import os
import pickle
import time
from typing import Optional

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from prometheus_client import (
    Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST,
)

from models import SensorReading, PredictResponse

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_NAME          = os.getenv("MLFLOW_MODEL_NAME", "FailureClassifier")
API_KEY             = os.getenv("API_KEY")  # if unset, auth is disabled (dev mode)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("pipeline.api")

app = FastAPI(title="Predictive Maintenance API")

# ── Prometheus metrics ────────────────────────────────────────────────────────
PREDICT_COUNTER = Counter(
    "api_predict_requests_total",
    "Total POST /v1/predict calls",
    ["anomaly"],
)
INFERENCE_LATENCY = Histogram(
    "api_inference_duration_ms",
    "End-to-end /v1/predict latency in milliseconds",
    buckets=[0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500],
)

# ── Optional API key auth ─────────────────────────────────────────────────────
async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


MODEL    = None
SCALER   = None
FEATURES = ["Rotational_speed_rpm", "Torque_Nm", "Tool_wear_min"]

_FIELD_TO_FEATURE = {
    "rotational_speed": "Rotational_speed_rpm",
    "torque":           "Torque_Nm",
    "tool_wear":        "Tool_wear_min",
}


# ── Model loading ─────────────────────────────────────────────────────────────
def _load_from_mlflow() -> None:
    global MODEL, SCALER, FEATURES
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()
    mv     = client.get_model_version_by_alias(MODEL_NAME, "champion")
    run_id = mv.run_id

    local_pkl = mlflow.artifacts.download_artifacts(f"runs:/{run_id}/model.pkl")
    with open(local_pkl, "rb") as f:
        arts = pickle.load(f)

    MODEL    = arts["model"]
    SCALER   = arts.get("scaler")
    FEATURES = arts.get("feature_names") or FEATURES
    logger.info(json.dumps({"event": "model_loaded", "source": "mlflow", "run_id": run_id}))


def _load_from_pkl() -> None:
    global MODEL, SCALER, FEATURES
    with open("model.pkl", "rb") as f:
        arts = pickle.load(f)
    MODEL    = arts["model"]
    SCALER   = arts.get("scaler")
    FEATURES = arts.get("feature_names") or FEATURES
    logger.info(json.dumps({"event": "model_loaded", "source": "local_pkl"}))


try:
    _load_from_mlflow()
except Exception as e:
    logger.warning(json.dumps({"event": "mlflow_unavailable", "error": str(e), "fallback": "model.pkl"}))
    _load_from_pkl()


# ── Inference ─────────────────────────────────────────────────────────────────
def vectorize(payload: SensorReading) -> np.ndarray:
    row  = {feat: 0.0 for feat in FEATURES}
    data = payload.model_dump()
    for api_key, feat in _FIELD_TO_FEATURE.items():
        if feat in row:
            row[feat] = float(data[api_key])
    X = np.array([[row[f] for f in FEATURES]], dtype=float)
    if SCALER is not None:
        X = SCALER.transform(X)
    return X


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/v1/predict",
    response_model=PredictResponse,
    dependencies=[Depends(verify_api_key)],
)
def predict(payload: SensorReading, threshold: float = 0.5):
    t0    = time.time()
    X     = vectorize(payload)
    proba = (
        float(MODEL.predict_proba(X)[0, 1])
        if hasattr(MODEL, "predict_proba")
        else float(MODEL.predict(X)[0])
    )
    elapsed_ms = round((time.time() - t0) * 1000, 2)
    anomaly = proba >= threshold
    PREDICT_COUNTER.labels(anomaly=str(anomaly)).inc()
    INFERENCE_LATENCY.observe(elapsed_ms)
    logger.info(json.dumps({
        "endpoint":         "/v1/predict",
        "machine_id":       payload.machine_id,
        "confidence":       round(proba, 6),
        "anomaly":          anomaly,
        "threshold":        threshold,
        "inference_time_ms": elapsed_ms,
    }))

    return PredictResponse(
        machine_id=payload.machine_id,
        confidence=proba,
        anomaly=anomaly,
        threshold=threshold,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
