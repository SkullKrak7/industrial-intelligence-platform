import sqlite3
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb
import joblib
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_sensor_data() -> pd.DataFrame:
    """Load sensor readings from SQLite into a DataFrame."""
    db_path = os.path.join(BASE_DIR, "sensor_data.db")
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM sensors", conn)
    conn.close()
    return df


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """Label each row as a sensor-health fault (1) or normal (0).

    Thresholds: temperature > 87°C, vibration > 4.1 g, pressure > 91 bar.
    These match the fault-injection bounds in data_gen.py so the classifier
    sees a realistic ~4% positive rate rather than the ~35% it would get from
    the old uniform(30, 100) temperature distribution.
    """
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.drop(columns=["id"], inplace=True, errors="ignore")
    df["fault"] = (
        (df["temperature"] > 87) |
        (df["vibration"] > 4.1) |
        (df["pressure"] > 91)
    ).astype(int)
    return df


def train_ai_model(df: pd.DataFrame) -> None:
    """Train a sensor-health anomaly detector on temperature/vibration/pressure.

    Saves two artefacts to twin/models/:
      fault_detection_rf.pkl  — RandomForest (interpretable, audit trail)
      fault_detection_xgb.pkl — XGBoost     (serving model)

    This is intentionally separate from the pipeline failure classifier
    (pipeline/train_model.py), which operates on rotational_speed/torque/tool_wear.
    """
    X = df[["temperature", "vibration", "pressure"]]
    y = df["fault"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)

    # eval_metric replaces deprecated use_label_encoder
    xgb_model = xgb.XGBClassifier(eval_metric="logloss", random_state=42)
    xgb_model.fit(X_train, y_train)

    model_dir = os.path.join(BASE_DIR, "models")
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(rf, os.path.join(model_dir, "fault_detection_rf.pkl"))
    joblib.dump(xgb_model, os.path.join(model_dir, "fault_detection_xgb.pkl"))
    print("Sensor-health anomaly detector trained and saved.")


if __name__ == "__main__":
    df = load_sensor_data()
    df = preprocess_data(df)
    train_ai_model(df)
