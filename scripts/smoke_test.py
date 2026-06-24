"""Integration smoke test for the Predictive Maintenance API.

Usage:
    python scripts/smoke_test.py                    # default: http://localhost:8000
    BASE_URL=http://localhost:8000 python scripts/smoke_test.py
    API_KEY=secret python scripts/smoke_test.py     # also tests auth

Runs against a live running API (not TestClient). Exit code 0 = all pass, 1 = any failure.
"""
import os
import sys

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY  = os.getenv("API_KEY", "")

_VALID_PAYLOAD = {
    "machine_id":       "M-smoke",
    "rotational_speed": 1538.0,
    "torque":           40.0,
    "tool_wear":        108.0,
}

_GREEN = "\033[92m"
_RED   = "\033[91m"
_RESET = "\033[0m"


def _pass(label: str) -> None:
    print(f"  {_GREEN}PASS{_RESET}  {label}")


def _fail(label: str, reason: str) -> None:
    print(f"  {_RED}FAIL{_RESET}  {label}: {reason}")


def _run_checks() -> list[bool]:
    results: list[bool] = []

    def check(label: str, ok: bool, reason: str = "") -> bool:
        if ok:
            _pass(label)
        else:
            _fail(label, reason)
        results.append(ok)
        return ok

    headers = {"X-API-Key": API_KEY} if API_KEY else {}

    # ── 1. Health ──────────────────────────────────────────────────────────────
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        check("/health → 200", r.status_code == 200, f"got {r.status_code}")
        check("/health body has status=ok",
              r.json().get("status") == "ok", str(r.json()))
    except Exception as e:
        check("/health reachable", False, str(e))
        check("/health body has status=ok", False, "unreachable")

    # ── 2. Metrics (Prometheus text format) ───────────────────────────────────
    try:
        r = requests.get(f"{BASE_URL}/metrics", timeout=5)
        check("/metrics → 200", r.status_code == 200, f"got {r.status_code}")
        check("/metrics Prometheus format",
              "api_predict_requests_total" in r.text or "# TYPE" in r.text,
              r.text[:80])
    except Exception as e:
        check("/metrics reachable", False, str(e))

    # ── 3. Valid prediction ────────────────────────────────────────────────────
    try:
        r = requests.post(f"{BASE_URL}/v1/predict", json=_VALID_PAYLOAD,
                          headers=headers, timeout=5)
        ok = check("/v1/predict valid → 200", r.status_code == 200,
                   f"got {r.status_code}: {r.text[:120]}")
        if ok:
            body = r.json()
            check("response has machine_id",  "machine_id"  in body, str(body))
            check("response has confidence",  "confidence"  in body, str(body))
            check("response has anomaly",     "anomaly"     in body, str(body))
            check("response has threshold",   "threshold"   in body, str(body))
            check("confidence in [0, 1]",
                  isinstance(body.get("confidence"), float)
                  and 0.0 <= body["confidence"] <= 1.0,
                  str(body.get("confidence")))
            check("anomaly is bool",
                  isinstance(body.get("anomaly"), bool), str(body.get("anomaly")))
            check("machine_id echoed",
                  body.get("machine_id") == _VALID_PAYLOAD["machine_id"],
                  str(body.get("machine_id")))
    except Exception as e:
        check("/v1/predict reachable", False, str(e))

    # ── 4. Fault-injected prediction (high tool_wear) ─────────────────────────
    try:
        fault_payload = {**_VALID_PAYLOAD, "tool_wear": 250.0, "rotational_speed": 1200.0}
        r = requests.post(f"{BASE_URL}/v1/predict", json=fault_payload,
                          headers=headers, timeout=5)
        ok = check("/v1/predict fault payload → 200", r.status_code == 200,
                   f"got {r.status_code}")
        if ok:
            body = r.json()
            check("fault payload returns float confidence",
                  isinstance(body.get("confidence"), float), str(body))
    except Exception as e:
        check("/v1/predict fault payload reachable", False, str(e))

    # ── 5. Invalid payload → 422 ───────────────────────────────────────────────
    try:
        r = requests.post(f"{BASE_URL}/v1/predict",
                          json={"machine_id": "M-smoke", "rotational_speed": "fast"},
                          headers=headers, timeout=5)
        check("invalid payload → 422", r.status_code == 422, f"got {r.status_code}")
    except Exception as e:
        check("invalid payload request", False, str(e))

    # ── 6. Out-of-bounds → 422 ────────────────────────────────────────────────
    try:
        oob = {**_VALID_PAYLOAD, "rotational_speed": 9999.0}
        r = requests.post(f"{BASE_URL}/v1/predict", json=oob,
                          headers=headers, timeout=5)
        check("out-of-bounds rotational_speed → 422",
              r.status_code == 422, f"got {r.status_code}")
    except Exception as e:
        check("out-of-bounds request", False, str(e))

    # ── 7. Auth (only if API_KEY is set in env) ────────────────────────────────
    if API_KEY:
        try:
            # Missing key → 401
            r = requests.post(f"{BASE_URL}/v1/predict", json=_VALID_PAYLOAD, timeout=5)
            check("missing API key → 401", r.status_code == 401, f"got {r.status_code}")

            # Wrong key → 401
            r = requests.post(f"{BASE_URL}/v1/predict", json=_VALID_PAYLOAD,
                              headers={"X-API-Key": "wrong"}, timeout=5)
            check("wrong API key → 401", r.status_code == 401, f"got {r.status_code}")

            # Correct key → 200
            r = requests.post(f"{BASE_URL}/v1/predict", json=_VALID_PAYLOAD,
                              headers={"X-API-Key": API_KEY}, timeout=5)
            check("correct API key → 200", r.status_code == 200, f"got {r.status_code}")
        except Exception as e:
            check("auth checks reachable", False, str(e))
    else:
        print(f"  {'':4s}  (auth checks skipped — set API_KEY env var to run them)")

    return results


def main() -> None:
    print(f"\nSmoke test → {BASE_URL}")
    print("=" * 50)
    results = _run_checks()
    passed  = sum(results)
    total   = len(results)
    print("=" * 50)
    print(f"  {passed}/{total} checks passed")

    if passed < total:
        print(f"  {_RED}{total - passed} FAILED{_RESET}")
        sys.exit(1)
    else:
        print(f"  {_GREEN}All checks passed.{_RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
