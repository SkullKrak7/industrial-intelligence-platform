import sqlite3
import os

# Correct path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def init_db():
    """Creates a database table for storing sensor data"""
    db_path = os.path.join(BASE_DIR, "sensor_data.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            temperature REAL,
            vibration REAL,
            pressure REAL
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully!!!")

if __name__ == "__main__":
    init_db()
