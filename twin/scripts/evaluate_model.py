"""Evaluate the sensor-health anomaly detector on the current telemetry stream.

Called from twin/main.py option 5. Expects telemetry_stream.csv to exist (run
generate_sensor_data or let the twin stream for a while first).
"""
import os

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Fault thresholds — match data_gen.py fault-injection bounds and train_twin_model.py
_TEMP_THRESHOLD = 87.0   # °C
_VIB_THRESHOLD  = 4.1    # g
_PRES_THRESHOLD = 91.0   # bar


def _load_data() -> pd.DataFrame:
    csv_path = os.path.join(BASE_DIR, "data", "telemetry_stream.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"telemetry_stream.csv not found at {csv_path}. "
            "Run option 1 (generate sensor data) first."
        )
    return pd.read_csv(csv_path)


def _label(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fault"] = (
        (df["temperature"] > _TEMP_THRESHOLD)
        | (df["vibration"] > _VIB_THRESHOLD)
        | (df["pressure"] > _PRES_THRESHOLD)
    ).astype(int)
    return df


def evaluate_model(model_path: str, X_test, y_test) -> None:
    import joblib

    model = joblib.load(model_path)
    preds = model.predict(X_test)
    acc   = accuracy_score(y_test, preds)

    print(f"\nModel: {os.path.basename(model_path)}")
    print(f"Accuracy: {acc:.4f}")
    print(classification_report(y_test, preds))

    cm = confusion_matrix(y_test, preds)
    plt.figure(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False)
    plt.title(f"Confusion Matrix — {os.path.basename(model_path)}")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.show()


def main() -> None:
    df = _load_data()
    df = _label(df)

    X = df[["temperature", "vibration", "pressure"]]
    y = df["fault"]

    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    models_dir = os.path.join(BASE_DIR, "models")
    if not os.path.isdir(models_dir):
        print(f"No models/ directory found at {models_dir}. Run option 4 (train) first.")
        return

    found = False
    for fname in ["fault_detection_rf.pkl", "fault_detection_xgb.pkl"]:
        path = os.path.join(models_dir, fname)
        if os.path.exists(path):
            evaluate_model(path, X_test, y_test)
            found = True

    if not found:
        print("No trained models found in models/. Run option 4 (train) first.")


if __name__ == "__main__":
    main()
