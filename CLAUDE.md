@AGENTS.md

## What this is

`industrial-intelligence-platform` — a merged portfolio project combining a Digital Twin simulation layer with a Predictive Maintenance ML pipeline into one production-grade repo. Demonstrates the full MLOps stack: simulated telemetry → feature engineering → model training → API serving → orchestration. Built by Sai Karthik Kagolanu.

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + uvicorn (migrated from Flask) |
| ML | XGBoost + scikit-learn + MLflow (experiment tracking + model registry) |
| Data transform | dbt + DuckDB (local, zero-infra, runs in-process) |
| Orchestration | Dagster (5 assets + daily schedule) |
| Digital Twin | Python asyncio simulation (`twin/`) |
| Observability | Prometheus + Loki + Promtail + Grafana |
| Containerisation | Docker Compose — 10 services |
| CI/CD | GitHub Actions (`ci.yml` + `retrain.yml`) |
| Language | Python 3.11+ |
| Dataset | `pipeline/predictive_maintenance.csv` (521 KB, AI4I 2020 Kaggle) |

## Repo structure

```
industrial-intelligence-platform/
├── twin/                         ← Digital twin sim (app/, scripts/)
├── pipeline/
│   ├── api.py                    ← FastAPI /v1/predict + /health + /metrics
│   ├── train_model.py            ← XGBoost + MLflow logging + @champion promotion
│   ├── models.py                 ← Pydantic schemas (SensorReading, PredictResponse)
│   ├── predictive_maintenance.csv
│   └── tests/                    ← pytest suite (functional + auth)
├── dbt/
│   └── models/
│       ├── staging/              ← stg_sensor_readings.sql
│       ├── intermediate/         ← int_feature_engineering.sql
│       └── mart/                 ← mart_equipment_health.sql
├── orchestration/
│   └── dagster_pipeline.py       ← 5 Dagster assets + daily schedule
├── observability/
│   ├── prometheus.yml            ← scrape config (pipeline-api:8000/metrics)
│   ├── loki-config.yml
│   ├── promtail-config.yml       ← reads from Docker socket
│   └── grafana/provisioning/     ← Prometheus + Loki datasources pre-wired
├── scripts/
│   └── smoke_test.py             ← integration smoke test (run after stack is up)
├── .github/workflows/
│   ├── ci.yml                    ← lint + test + Docker build on every push
│   └── retrain.yml               ← retrain on train_model.py / CSV changes
├── data/                         ← telemetry_stream.csv + predictions.csv (runtime only)
├── docker-compose.yml
├── .env.example
└── requirements.txt              ← root deps (dagster, dbt-duckdb, mlflow, pandas …)
```

## Integration interface

Two CSV files are the only coupling between twin and pipeline — no HTTP calls, no shared databases. This is the portfolio-scale expression of the event-driven pattern that dominates production digital twin architecture in 2026 (MQTT/Kafka at scale; shared filesystem events here). If this project were to scale, replacing the CSV files with an MQTT broker is the natural next step — the twin and pipeline code would change only at their I/O boundaries.

| File | Writer | Reader | Purpose |
|---|---|---|---|
| `data/telemetry_stream.csv` | twin (`emit_telemetry`) | pipeline (`raw_telemetry` asset) | Sensor readings flowing forward |
| `data/predictions.csv` | pipeline (`write_predictions` asset) | twin (watchdog file-watcher) | Anomaly flags flowing back |

The twin watches `data/predictions.csv` using Python `watchdog` (OS filesystem events, not a polling loop). When a new row appears with `anomaly=True`, it updates that machine's visual state to `ALERT`. Do not add additional coupling points — keeping this to two files is a deliberate design choice that stays simple and explainable.

## Version-specific gotchas

- **MLflow 2.x**: Model stages (`Staging`, `Production`) are deprecated. Use **aliases** — `client.set_registered_model_alias(name, "champion", version)`. Load via `@champion` alias — see Rule 4 for the exact pattern (it is not `mlflow.sklearn.load_model`; it uses `get_model_version_by_alias()` + `download_artifacts()`). `@champion` is the MLflow-recommended alias name for the model serving production traffic.
- **dbt-duckdb**: Requires the `dbt-duckdb` adapter (`pip install dbt-duckdb`), not `dbt-core` alone. The dbt profile target must point to DuckDB, not Postgres.
- **Dagster assets**: `@asset` functions must be idempotent — they are retried on failure. Any asset writing to a file, registry, or database must be safe to re-run without duplicating or corrupting state.
- **FastAPI vs Flask**: Request bodies require Pydantic `BaseModel`, not raw dicts. Route decorators are `@app.post("/v1/predict")` not `@app.route(..., methods=["POST"])`. No `app.run()` — use `uvicorn` to serve.
- **watchdog file-watcher**: Use `Observer` not `PollingObserver` inside Docker — bind-mounted volumes emit inotify events on Linux, so `Observer` works. On macOS host, use `PollingObserver` as fallback if events are missed.

## Running locally

```bash
# 1. Configure env
cp .env.example .env

# 2. Start full stack (all services including Dagster)
docker compose up --build

# Ports:
#   8050  →  Dash dashboard
#   8000  →  Pipeline API  (Swagger: /docs)
#   5001  →  MLflow UI
#   3000  →  Dagster UI
#   3001  →  Grafana  (admin / $GRAFANA_ADMIN_PASSWORD)
#   9090  →  Prometheus
#   3100  →  Loki

# ── Individual components (local dev, no Docker) ──────────────────────────────
cd pipeline && python train_model.py                   # train + log to MLflow
uvicorn pipeline.api:app --reload --port 8000          # API (run from repo root)
dbt run --project-dir dbt/ --profiles-dir dbt/         # transform data
dagster dev -f orchestration/dagster_pipeline.py       # Dagster UI
mlflow server --host 0.0.0.0 --port 5001               # MLflow tracking server

# ── Integration smoke test (requires live API on port 8000) ───────────────────
# Checks: /health (200 + status=ok), /metrics (Prometheus format), POST /v1/predict
# with a known-good SensorReading (asserts machine_id/confidence/anomaly/threshold in
# response and confidence in [0,1]), 422 on invalid type, 422 on out-of-range value,
# and auth 401/200 when API_KEY is set. Exit 0 = all checks passed, 1 = any failure.
python scripts/smoke_test.py
# With auth enabled:
API_KEY=your_key python scripts/smoke_test.py

# Tests — run before every push
pytest pipeline/tests/ -q
```

> **Note on twin startup order (Docker only):** `twin-sim` seeds `telemetry_stream.csv` first (batch), then initialises the SQLite DB, then loads the DB, then enters the async streaming loop. The healthcheck gates `twin-api` on the DB being ready. Do not change this order.

---

## Rules — enforced, not optional

### 1. Discuss before implementing
For any non-trivial change (new layer, dependency, schema change): write a plan in 2–3 sentences and wait for approval before coding.
For small bug fixes and single-file changes: just do it.

### 2. Never hardcode paths or config
All file paths (`data/telemetry_stream.csv`), model names, dbt project dirs, and MLflow tracking URIs go in environment variables or a config object. No string literals embedded inside pipeline or orchestration code.

### 3. Never touch source data without explicit instruction
When investigating: read, observe, report. Do not modify `predictive_maintenance.csv` or `telemetry_stream.csv` unless explicitly instructed.

### 4. MLflow: always use aliases, never file paths
`api.py` resolves `@champion` via `MlflowClient().get_model_version_by_alias()`, then downloads the composite `model.pkl` from the run's artifact store with `mlflow.artifacts.download_artifacts()`. Never load directly from `model.pkl` on disk — the alias guarantees the API always serves the correct registered version. The local `model.pkl` is baked into the Docker image at build time as a fallback when the MLflow server is unreachable.

### 5. dbt models must run clean before declaring done
Run `dbt run --project-dir dbt/` and confirm all three models pass before reporting dbt work as complete.

### 6. Dagster assets must be idempotent
Write assets so re-running produces the same outcome — no duplicate MLflow runs, no double-appended CSV rows, no double-promoted model versions.

### 7. Keep existing tests green — every push
```bash
pytest pipeline/tests/
```
The pipeline repo already has tests. They must pass on every push. New pure functions (feature engineering helpers, validation logic) get unit tests.

### 8. No unsolicited work
A bug fix does not need surrounding refactors. A one-shot feature does not need an abstraction. No comments explaining WHAT code does — only WHY when the reason is non-obvious.

### 9. Web research
When researching, include the current month and year in queries (e.g. "June 2026"). Prefer official docs over blog posts. Stop at 3 sources if the answer is clear.
For genuine unknowns that need broader coverage, see **AGENTS.md → Web research protocol**.

### 10. F1 threshold is calibrated, not arbitrary
The 3-feature XGBoost model on AI4I 2020 achieves ~0.737 macro-F1 (not 0.85). Macro-F1 is penalised by the ~4% failure-class minority. The `F1_THRESHOLD` env var defaults to `0.70`. Do not raise it above 0.74 without retraining with additional features or a larger dataset — `@champion` will never be set and the API will always serve the fallback pkl.

---

## Architecture

### Two complementary ML models

This platform runs two ML models that answer different questions about the same machine:

| Model | Location | Input features | Output | Question answered |
|---|---|---|---|---|
| Sensor-health anomaly detector | `twin/scripts/train_twin_model.py` | `temperature`, `vibration`, `pressure` | `fault: bool` | Is the machine's sensor telemetry normal? |
| Failure classifier | `pipeline/train_model.py` + `pipeline/api.py` | `rotational_speed`, `torque`, `tool_wear` | `anomaly: bool`, `confidence: float` | Is a mechanical failure imminent? |

These are complementary, not redundant. The sensor-health model catches environmental/hardware faults (a failing temp sensor, vibration spikes). The failure classifier catches operational failure modes derived from the AI4I 2020 Kaggle dataset. Both run in the same Docker Compose stack and write their outputs to the shared data layer.

### Layer 1 — Digital Twin (`twin/`)
Simulates industrial machine telemetry. `twin/scripts/data_gen.py` generates all six columns on a calibrated distribution (rotational_speed/torque/tool_wear from AI4I 2020 mean/std; temperature/vibration/pressure as realistic normal distributions). ~4% of rows are fault-injected with extreme values so both models fire anomalies in demos.

I/O hooks:
- `stream_telemetry()` — async loop that appends a row to `data/telemetry_stream.csv` every 2 s
- A `watchdog` observer on `data/predictions.csv` — on any new row with `anomaly=True`, sets that machine's visual state to `ALERT`
- `train_twin_model.py` — trains the sensor-health anomaly detector on temperature/vibration/pressure; thresholds match fault-injection bounds (temp > 87°C, vib > 4.1 g, pressure > 91 bar)

Do not modify the twin's internal simulation logic — only its I/O interface.

### Layer 2 — ML Pipeline (`pipeline/`)
Failure classifier operating on operational parameters from `telemetry_stream.csv`.

- `train_model.py` — trains XGBoost on `predictive_maintenance.csv` (AI4I 2020), wraps run in `mlflow.start_run()`, logs params + metrics (F1, precision), registers model, sets `@champion` alias on best run. RandomForest is used only for feature importance audit — XGBoost is the serving model.
- `api.py` — `POST /v1/predict` accepts `SensorReading` (Pydantic), loads model via MLflow alias, returns `{ machine_id, anomaly: bool, confidence: float }`.
- `models.py` — Pydantic schemas. Source of truth for the request/response contract.

### Layer 3 — dbt (`dbt/`)
Three SQL model layers against DuckDB (in-process, no infra):
- `stg_sensor_readings` — raw CSV → typed, renamed columns
- `int_feature_engineering` — derived features: `temp_differential`, `power_output`, `tool_wear_pct`
- `mart_equipment_health` — per-machine aggregates: `avg_tool_wear`, `total_failures`, `peak_power`

`dbt/models/schema.yml` defines column-level tests — `not_null` on `machine_id` in all three model layers, plus `unique` on `machine_id` in the mart model (enforcing one row per machine in the aggregated output). Dagster calls `dbt run`. This is the entire data engineering layer.

### Layer 4 — Orchestration (`orchestration/`)
Five Dagster assets in dependency order:
1. `raw_telemetry` — reads `telemetry_stream.csv`
2. `dbt_models` — calls `dbt run`
3. `retrain_model` — runs `train_model.py`, logs to MLflow, registers new version
4. `model_health_check` — gates promotion only: F1 > 0.70 → set `@champion` alias; else alert, keep current version
5. `write_predictions` — calls `/v1/predict` with telemetry data, writes anomaly flags to `data/predictions.csv`

Splitting 4 and 5 keeps concerns separate: promotion is a registry operation, write-back is a serving operation. Produces a cleaner asset graph for the portfolio screenshot.

Daily `@schedule` runs the full chain automatically. Dagster UI gives live run visualisation — screenshot this for the portfolio README.

---

## CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | Every push | ruff lint, black check, `pytest pipeline/tests/`, Docker build |
| `retrain.yml` | Push to `main` touching `pipeline/train_model.py` or `pipeline/predictive_maintenance.csv` | Runs `train_model.py`, reports F1-macro + promotion gate result in Actions summary |

---

## Build order

| Week | Work | Status |
|---|---|---|
| 1 | Create repo, move both codebases in, get `docker compose up` running | Done |
| 2 | Flask → FastAPI (`api.py`), fix vectorize() bug, update models + tests | Done |
| 3 | Calibrate data_gen to AI4I distribution, asyncio streaming, dbt models, watchdog | Done |
| 4 | Dagster 5 assets, MLflow wiring, healthchecks, watchdog, README, core bug fixes | Done |
| 4.5 | Structured JSON logging, API key auth, column validation, .dockerignore, retrain.yml, volume path fixes | Done |
| 5 | F1 threshold calibration, smoke test, auth tests, requirements fixes, repo cleanup | Done |
| 5.5 | Prometheus /metrics format, Grafana + Loki + Promtail observability stack, retrain.yml fixes | Done |

**Current state:** Stack is complete. All known bugs fixed. `docker compose up --build` brings up 10 services (twin-sim, twin-api, twin-dashboard, pipeline-api, mlflow, dagster, prometheus, loki, promtail, grafana). Run `python scripts/smoke_test.py` after stack is up to verify end-to-end data flow. Portfolio screenshots (Dagster graph, MLflow run, dashboard, Grafana) are the only remaining manual step.

**Out-of-scope decisions (final):**
- DVC — dataset is 521 KB, already in git. DVC is for GB-scale files. Overhead without benefit here.
- Blue-green deployment — Docker Compose lacks rolling update primitives. This is a Kubernetes pattern.
