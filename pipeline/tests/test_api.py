import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import warnings
import pytest
from fastapi.testclient import TestClient
from api import app
import api as api_module

warnings.filterwarnings(
    "ignore",
    message=r"X does not have valid feature names, but StandardScaler was fitted with feature names",
    category=UserWarning,
    module=r"sklearn\.utils\.validation",
)

c = TestClient(app)

_VALID = {
    "machine_id": "M-001",
    "rotational_speed": 1200.0,
    "torque": 35.0,
    "tool_wear": 10.0,
}


def test_health_ok():
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_prometheus_format():
    r = c.get("/metrics")
    assert r.status_code == 200
    # Prometheus text format — not JSON
    assert "application/json" not in r.headers.get("content-type", "")
    text = r.text
    assert "api_predict_requests_total" in text or "api_inference_duration_ms" in text


def test_predict_valid():
    r = c.post("/v1/predict", json=_VALID)
    body = r.json()
    assert r.status_code == 200
    assert 0.0 <= body["confidence"] <= 1.0
    assert isinstance(body["anomaly"], bool)
    assert set(body.keys()) == {"machine_id", "confidence", "anomaly", "threshold"}
    assert isinstance(body["confidence"], float)


def test_predict_invalid_422():
    r = c.post(
        "/v1/predict",
        json={"machine_id": "M-001", "rotational_speed": "fast"},
    )
    assert r.status_code == 422


def test_predict_bounds():
    bad = {"machine_id": "M-001", "rotational_speed": 5000, "torque": 30, "tool_wear": 5}
    r = c.post("/v1/predict", json=bad)
    assert r.status_code == 422


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_auth_disabled_when_no_env_key(monkeypatch):
    """When API_KEY env var is unset, every request is accepted regardless of header."""
    monkeypatch.setattr(api_module, "API_KEY", None)
    r = c.post("/v1/predict", json=_VALID)
    assert r.status_code == 200


def test_auth_missing_key_returns_401(monkeypatch):
    monkeypatch.setattr(api_module, "API_KEY", "secret")
    r = c.post("/v1/predict", json=_VALID)
    assert r.status_code == 401


def test_auth_wrong_key_returns_401(monkeypatch):
    monkeypatch.setattr(api_module, "API_KEY", "secret")
    r = c.post("/v1/predict", json=_VALID, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_auth_correct_key_returns_200(monkeypatch):
    monkeypatch.setattr(api_module, "API_KEY", "secret")
    r = c.post("/v1/predict", json=_VALID, headers={"X-API-Key": "secret"})
    assert r.status_code == 200
