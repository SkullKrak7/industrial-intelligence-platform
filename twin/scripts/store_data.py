import sqlite3
import pandas as pd
import os

# Get the absolute path to the root of your project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def store_sensor_data():
    """Reads sensor data from CSV and stores it in SQLite database."""

    csv_path = os.path.join(BASE_DIR, "data", "telemetry_stream.csv")
    db_path = os.path.join(BASE_DIR, "sensor_data.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    df = pd.read_csv(csv_path)

    for _, row in df.iterrows():
        cursor.execute(
            "INSERT INTO sensors(timestamp, temperature, vibration, pressure) VALUES (?,?,?,?)",
            (row["timestamp"], row["temperature"], row["vibration"], row["pressure"])
        )

    conn.commit()
    conn.close()
    print("Sensor data stored in database successfully!")

if __name__ == "__main__":
    store_sensor_data()
