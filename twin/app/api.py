import sqlite3
import pandas as pd
from flask import Flask, jsonify
import os

app = Flask(__name__)

# Dynamically detect project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fetch_latest_data():
    """Fetches the last 10 sensor readings from the database."""
    db_path = os.path.join(BASE_DIR, "sensor_data.db")
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM sensors ORDER BY id DESC LIMIT 10", conn)
    conn.close()
    return df.to_dict(orient="records")

@app.route("/data", methods=["GET"])
def get_sensor_data():
    """API endpoint to return the latest sensor readings."""
    data = fetch_latest_data()
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
