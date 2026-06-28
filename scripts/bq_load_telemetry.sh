#!/usr/bin/env bash
# Load the telemetry CSV into a BigQuery landing table for the dbt 'bigquery' target.
# All config comes from env vars — no hardcoded project, dataset, or paths.
# Idempotent: --replace overwrites the table, so re-running never duplicates rows.
#
# Prereqs: gcloud SDK installed and authed (`gcloud auth login` + a billing-enabled
# project). Run before `DBT_TARGET=bigquery dbt run`.
#
# Usage:
#   GCP_PROJECT=my-proj scripts/bq_load_telemetry.sh
set -euo pipefail

: "${GCP_PROJECT:?set GCP_PROJECT to your GCP project id}"
BQ_DATASET="${BQ_DATASET:-industrial_intelligence}"
BQ_LOCATION="${BQ_LOCATION:-US}"
TELEMETRY_PATH="${TELEMETRY_PATH:-data/telemetry_stream.csv}"

bq --project_id="$GCP_PROJECT" --location="$BQ_LOCATION" \
  mk --dataset --force "${GCP_PROJECT}:${BQ_DATASET}"

bq --project_id="$GCP_PROJECT" --location="$BQ_LOCATION" load \
  --source_format=CSV \
  --autodetect \
  --replace \
  "${GCP_PROJECT}:${BQ_DATASET}.telemetry_stream" \
  "$TELEMETRY_PATH"

echo "Loaded ${TELEMETRY_PATH} → ${GCP_PROJECT}:${BQ_DATASET}.telemetry_stream"
