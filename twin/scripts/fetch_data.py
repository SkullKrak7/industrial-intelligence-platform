import sqlite3
import pandas as pd
import os

# Get the absolute path to the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fetch_sensor_data():
    """Fetches the last 5 records from the sensor database and displays them."""
    db_path = os.path.join(BASE_DIR, "sensor_data.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM sensors ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()

    conn.close()

    df = pd.DataFrame(rows, columns=["id", "timestamp", "temperature", "vibration", "pressure"])
    print(df)

if __name__ == "__main__":
    fetch_sensor_data()
