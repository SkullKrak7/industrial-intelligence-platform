# Industrial Intelligence Platform

An end-to-end MLOps portfolio project merging a Digital Twin simulation layer with a Predictive Maintenance ML pipeline into one production-grade system. Demonstrates the full stack: simulated telemetry → feature engineering → model training → FastAPI serving → Dagster orchestration → real-time dashboard.

Built by **Sai Karthik Kagolanu**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  twin-sim (asyncio loop, 2 s interval)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  data_gen.py  →  telemetry_stream.csv                   │    │
│  │  watcher.py   ←  predictions.csv  (watchdog/inotify)    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │              ▲                        │
│                    [shared volume]  [shared volume]              │
│                          │              │                        │
│  pipeline-api (FastAPI)  │              │  Dagster write_predictions
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  POST /v1/predict  ←  SensorReading (Pydantic)          │    │
│  │  loads FailureClassifier@champion from MLflow registry  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  MLflow  (port 5001)     Dagster  (port 3000)                   │
│  ┌───────────────────┐   ┌──────────────────────────────────┐   │
│  │  experiment runs  │   │  raw_telemetry → dbt_models      │   │
│  │  model registry   │   │  → retrain_model                 │   │
│  │  @champion alias  │   │  → model_health_check (F1>0.70)  │   │
│  └───────────────────┘   │  → write_predictions             │   │
│                          └──────────────────────────────────┘   │
│                                                                  │
│  twin-dashboard  (Dash, port 8050)                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  sensor trend charts  │  failure predictions panel      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Two complementary ML models

| Model | Trains on | Predicts | File |
|---|---|---|---|
| Sensor-health anomaly detector | temperature, vibration, pressure | `fault: bool` | `twin/scripts/train_twin_model.py` |
| Failure classifier | rotational_speed, torque, tool_wear | `anomaly: bool`, `confidence: float` | `pipeline/train_model.py` |

Both models target ~4 % positive rate. The twin's `data_gen.py` deliberately fault-injects 4 % of rows with extreme values so both models fire during demos.

---

## Stack

| Layer | Technology |
|---|---|
| Digital Twin | Python asyncio simulation (`twin/`) |
| ML | XGBoost + scikit-learn |
| Experiment tracking | MLflow 2.x (aliases, not stages) |
| Data transform | dbt + DuckDB |
| Orchestration | Dagster (5 assets + daily schedule) |
| API | FastAPI + uvicorn |
| Dashboard | Plotly Dash |
| Containers | Docker Compose |
| CI | GitHub Actions |
| Language | Python 3.11+ |

---

## Quickstart

```bash
# 1. Clone and configure
cp .env.example .env          # edit if needed

# 2. Start everything
docker compose up --build

# Ports:
#   8050  →  Dash dashboard
#   8000  →  Pipeline API  (Swagger: http://localhost:8000/docs)
#   5001  →  MLflow UI
#   3000  →  Dagster UI
#   3001  →  Grafana  (admin / admin — Prometheus + Loki pre-wired)
#   9090  →  Prometheus
#   3100  →  Loki
```

### Local dev (no Docker)

```bash
# Install deps
pip install -r pipeline/requirements.txt
pip install -r requirements.txt   # dagster, dbt-duckdb, watchdog

# Train model and start API
cd pipeline
python train_model.py
uvicorn api:app --reload --port 8000

# Run dbt
dbt run --project-dir dbt/ --profiles-dir dbt/

# Dagster UI
dagster dev -f orchestration/dagster_pipeline.py

# Test
pytest pipeline/tests/ -q
```

---

## Integration interface

Two CSV files are the only coupling between twin and pipeline — no HTTP calls between services, no shared databases.

| File | Writer | Reader |
|---|---|---|
| `data/telemetry_stream.csv` | `twin-sim` (data_gen.py) | `pipeline-api`, Dagster `raw_telemetry` |
| `data/predictions.csv` | Dagster `write_predictions` | `twin-sim` (watcher.py), Dash dashboard |

Both files are gitignored (generated at runtime). See `data/.gitkeep`.

---

## Key design decisions

- **`@champion` alias** (not `Staging`/`Production`) — MLflow 2.x deprecated stage transitions; aliases are the canonical promotion mechanism.
- **CSV coupling at portfolio scale** — event-driven via filesystem; MQTT is the natural scale-up path with code changes only at I/O boundaries.
- **3-feature serving model** — deliberately excludes `Process temperature` and product `Type` from training so training and serving distributions are identical.
- **F1 > 0.70 promotion gate** — `model_health_check` asset sets `@champion` only when macro-F1 clears the threshold; the API always serves the last promoted version. Threshold is calibrated to this dataset's class imbalance (~4% failure rate, macro-F1 ~0.737).

---

## Project structure

```
industrial-intelligence-platform/
├── twin/
│   ├── app/            ← Dash dashboard + Flask data API
│   └── scripts/        ← data_gen, watcher, train_twin_model, store_data
├── pipeline/
│   ├── api.py          ← FastAPI  POST /v1/predict
│   ├── train_model.py  ← XGBoost + MLflow logging
│   ├── models.py       ← SensorReading, PredictResponse (Pydantic)
│   └── tests/          ← pytest suite (functional + auth)
├── dbt/
│   └── models/         ← staging → intermediate → mart (DuckDB)
├── orchestration/
│   └── dagster_pipeline.py  ← 5 Dagster assets + daily schedule
├── scripts/
│   └── smoke_test.py   ← integration smoke test (run after docker compose up)
├── .github/workflows/
│   ├── ci.yml          ← lint + test + docker build on every push
│   └── retrain.yml     ← retrain on train_model.py changes, report F1 in summary
├── data/               ← telemetry_stream.csv, predictions.csv (runtime, gitignored)
├── docker-compose.yml
├── .env.example
└── CLAUDE.md           ← dev rules + architecture reference
```

---

## Observability

The stack ships a full observability layer alongside the ML services:

| Tool | Purpose | Port |
|---|---|---|
| Prometheus | Scrapes `/metrics` (Prometheus format) from pipeline-api every 15 s | 9090 |
| Loki | Aggregates structured JSON logs from all containers via Promtail | 3100 |
| Grafana | Visualises both — Prometheus and Loki datasources pre-provisioned | 3001 |

Grafana credentials: **admin / admin**. Both datasources appear immediately after `docker compose up --build`.

---

## Build roadmap

| Week | Status |
|---|---|
| 1 — Merge repos, docker compose up | Done |
| 2 — FastAPI migration, fix vectorize bug, MLflow wiring | Done |
| 3 — Calibrated data_gen, dbt models, watchdog, Dagster | Done |
| 4 — Dagster in docker-compose, healthchecks, structured logging, auth | Done |
| 5 — CI workflows, smoke test, F1 calibration, Prometheus/Grafana/Loki, repo hardening | Done |
