import asyncio
import os

import numpy as np
import pandas as pd


_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEMETRY_PATH = os.path.join(_BASE, "data", "telemetry_stream.csv")

COLUMNS = [
    "timestamp",
    "machine_id",
    "temperature",
    "vibration",
    "pressure",
    "rotational_speed",
    "torque",
    "tool_wear",
]

_MACHINE_ID = os.getenv("MACHINE_ID", "M-001")

# Fault injection rate — ~4% of rows carry extreme values so both models fire anomalies
_FAULT_RATE = 0.04


def _sample_row() -> dict:
    fault = np.random.random() < _FAULT_RATE

    if fault:
        # Sensor-health fault: spike at least one twin sensor past its threshold
        temperature = round(float(np.random.uniform(88, 100)), 3)
        vibration   = round(float(np.random.uniform(4.2, 5.0)), 4)
        pressure    = round(float(np.random.uniform(92, 100)), 3)
        # Pipeline fault: high tool_wear + low rotational_speed → failure imminent
        rotational_speed = round(float(np.clip(np.random.normal(1200, 80), 1168, 1400)), 1)
        torque           = round(float(np.clip(np.random.normal(65, 5), 3.8, 76.6)), 3)
        tool_wear        = round(float(np.clip(np.random.normal(220, 20), 0, 253)), 1)
    else:
        # Normal operation — distributions calibrated to AI4I 2020 training data
        temperature = round(float(np.clip(np.random.normal(60, 10), 30, 87)), 3)
        vibration   = round(float(np.clip(np.random.normal(1.5, 0.8), 0.1, 4.1)), 4)
        pressure    = round(float(np.clip(np.random.normal(55, 15), 10, 91)), 3)
        # N(μ, σ) from AI4I 2020: rpm N(1539, 179), torque N(40, 10), wear N(108, 64)
        rotational_speed = round(float(np.clip(np.random.normal(1538.78, 179.28), 1168, 2886)), 1)
        torque           = round(float(np.clip(np.random.normal(39.99, 9.97), 3.8, 76.6)), 3)
        tool_wear        = round(float(np.clip(np.random.normal(107.95, 63.65), 0, 253)), 1)

    return {
        "timestamp":        pd.Timestamp.now().isoformat(),
        "machine_id":       _MACHINE_ID,
        "temperature":      temperature,
        "vibration":       vibration,
        "pressure":        pressure,
        "rotational_speed": rotational_speed,
        "torque":          torque,
        "tool_wear":       tool_wear,
    }


def _ensure_header(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        pd.DataFrame(columns=COLUMNS).to_csv(path, index=False)


async def stream_telemetry(interval_s: float = 2.0) -> None:
    """Append one sensor row to telemetry_stream.csv every interval_s seconds."""
    _ensure_header(TELEMETRY_PATH)
    print(f"Streaming telemetry → {TELEMETRY_PATH}  (interval={interval_s}s)")
    while True:
        pd.DataFrame([_sample_row()]).to_csv(
            TELEMETRY_PATH, mode="a", header=False, index=False
        )
        await asyncio.sleep(interval_s)


def generate_sensor_data(n: int = 100) -> None:
    """One-shot batch for local dev (main.py option 1). Writes to telemetry_stream.csv."""
    _ensure_header(TELEMETRY_PATH)
    rows = [_sample_row() for _ in range(n)]
    pd.DataFrame(rows).to_csv(TELEMETRY_PATH, index=False)
    print(f"Sensor data saved to {TELEMETRY_PATH}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from watcher import start_watcher
    start_watcher()
    asyncio.run(stream_telemetry())
