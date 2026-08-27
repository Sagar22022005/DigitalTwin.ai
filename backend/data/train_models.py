"""
data/train_models.py — Loads historical telemetry from SQLite and trains
all 4 ML models, saving artifacts to models/artifacts/.

Run after generate_data.py:
    python data/train_models.py
"""
import sys
import sqlite3
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.anomaly_detector import AnomalyDetector
from models.bottleneck_predictor import BottleneckPredictor
from models.defect_predictor import DefectPredictor
from models.sensor_imputer import SensorImputer
from simulator.assembly_line import DB_PATH

def load_df() -> pd.DataFrame:
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql("SELECT * FROM station_events ORDER BY timestamp", conn)
    conn.close()
    df["fault_active"] = df["fault_active"].astype(bool)
    df["is_sensor_poor"] = df["is_sensor_poor"].astype(bool)
    print(f"Loaded {len(df):,} events from DB.")
    return df


if __name__ == "__main__":
    print("=" * 60)
    print("AI AssemblyTwin — Model Training Pipeline")
    print("=" * 60)

    df = load_df()

    # Use first 6 days for training, day 7 for validation
    cutoff = df["timestamp"].quantile(0.86)
    df_train = df[df["timestamp"] <= cutoff].copy()
    df_test  = df[df["timestamp"] >  cutoff].copy()
    print(f"Train: {len(df_train):,} | Test: {len(df_test):,}\n")

    # 1. Anomaly Detector
    print("--- Training AnomalyDetector (Isolation Forest) ---")
    normal_train = df_train[~df_train["fault_active"]]
    ad = AnomalyDetector(contamination=0.04)
    ad.fit(normal_train)

    # 2. Bottleneck Predictor
    print("\n--- Training BottleneckPredictor (LSTM) ---")
    bp = BottleneckPredictor()
    bp.fit(df_train, epochs=25)

    # 3. Defect Predictor
    print("\n--- Training DefectPredictor (Random Forest) ---")
    dp = DefectPredictor()
    dp.fit(df_train)

    # 4. Sensor Imputer
    print("\n--- Training SensorImputer (GP Regression) ---")
    si = SensorImputer()
    si.fit(df_train)

    print("\n" + "=" * 60)
    print("All models trained and saved to models/artifacts/")
    print("Next: uvicorn main:app --reload")
