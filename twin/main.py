import subprocess
import time

def show_menu():
    print("=== Digital Twin – Real-Time Industrial Monitoring ===")
    print("1. Generate sensor data (CSV)")
    print("2. Initialize SQLite database")
    print("3. Store CSV data into database")
    print("4. Train sensor-health anomaly detector")
    print("5. Evaluate trained models")
    print("6. Run both Flask API and Dash dashboard")

    choice = input("Choose an option (1–6): ").strip()

    if choice == "1":
        from scripts import data_gen
        data_gen.generate_sensor_data()
    elif choice == "2":
        from scripts import init_db
        init_db.init_db()
    elif choice == "3":
        from scripts import store_data
        store_data.store_sensor_data()
    elif choice == "4":
        from scripts import train_twin_model
        df = train_twin_model.load_sensor_data()
        df = train_twin_model.preprocess_data(df)
        train_twin_model.train_ai_model(df)
    elif choice == "5":
        from scripts import evaluate_model
        evaluate_model.main()
    elif choice == "6":
        api_process = subprocess.Popen(["python", "app/api.py"])
        time.sleep(5)  # give Flask time to boot up
        try:
            subprocess.run(["python", "app/dashboard.py"])
        finally:
            api_process.terminate()
    else:
        print("Invalid choice. Please run again.")

if __name__ == "__main__":
    show_menu()
