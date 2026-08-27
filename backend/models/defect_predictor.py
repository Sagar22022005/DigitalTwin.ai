"""
models/defect_predictor.py — Random Forest defect risk predictor.

Key insight: defects originate upstream but surface at QC (Station 44).
Lag features capture this: torque anomaly at Station 7 → defect at Station 44.

Features per vehicle include metrics from ALL upstream stations (with lags)
so the model learns multi-station causal chains.
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from dataclasses import dataclass
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report
from typing import Optional

ARTIFACT_DIR = Path(__file__).parent / "artifacts"
QC_STATION = 44
LAG_STATIONS = list(range(1, 45))  # all upstream of QC


@dataclass
class DefectPrediction:
    vehicle_id: int
    defect_prob: float
    risk_station: int          # most likely origin station
    risk_feature: str          # which metric drove the risk
    confidence: float


class DefectPredictor:
    def __init__(self):
        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: list[str] = []

    def _build_vehicle_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build one row per vehicle with lag features from all upstream stations.
        Features: cycle_time, torque, vibration from each of stations 1–43
        plus operator_id at key stations.
        """
        rows = []
        for vehicle_id, vdf in df.groupby("vehicle_id"):
            station_data = vdf.set_index("station_id")
            feature_row = {"vehicle_id": vehicle_id}

            for sid in LAG_STATIONS:
                if sid in station_data.index:
                    row = station_data.loc[sid]
                    feature_row[f"ct_s{sid}"]  = row.get("cycle_time_s", np.nan)
                    feature_row[f"tq_s{sid}"]  = row.get("torque_nm",    np.nan)
                    feature_row[f"vb_s{sid}"]  = row.get("vibration_g",  np.nan)
                    feature_row[f"tp_s{sid}"]  = row.get("temperature_c",np.nan)
                else:
                    feature_row[f"ct_s{sid}"]  = np.nan
                    feature_row[f"tq_s{sid}"]  = np.nan
                    feature_row[f"vb_s{sid}"]  = np.nan
                    feature_row[f"tp_s{sid}"]  = np.nan

            # Label: did this vehicle have fault_active at any upstream station?
            # (proxy for defect since we inject defects via fault_active flag)
            upstream_fault = vdf[
                (vdf["station_id"] < QC_STATION) & (vdf["fault_active"] == True)
            ]
            feature_row["defect_label"] = 1 if len(upstream_fault) > 0 else 0
            rows.append(feature_row)

        return pd.DataFrame(rows)

    def fit(self, df: pd.DataFrame, test_size: float = 0.2):
        feat_df = self._build_vehicle_features(df)
        feat_cols = [c for c in feat_df.columns if c not in ("vehicle_id", "defect_label")]
        self.feature_names = feat_cols

        X = feat_df[feat_cols].fillna(0).values
        y = feat_df["defect_label"].values

        # Train/test split by vehicle_id order (temporal)
        split = int(len(X) * (1 - test_size))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        self.scaler = StandardScaler()
        X_train_s = self.scaler.fit_transform(X_train)
        X_test_s  = self.scaler.transform(X_test)

        self.model = RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            class_weight="balanced",    # handles imbalanced defect labels
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train_s, y_train)

        y_pred = self.model.predict(X_test_s)
        print("[DefectPredictor] Test set evaluation:")
        print(classification_report(y_test, y_pred, target_names=["normal", "defect"]))

        self.save()

    def predict(self, vehicle_station_data: pd.DataFrame) -> DefectPrediction:
        """
        vehicle_station_data: all station readings for one vehicle so far.
        Returns DefectPrediction with probability and likely origin station.
        """
        if self.model is None:
            self.load()

        vehicle_id = int(vehicle_station_data["vehicle_id"].iloc[0])
        station_data = vehicle_station_data.set_index("station_id")
        feature_row = {}
        for sid in LAG_STATIONS:
            if sid in station_data.index:
                row = station_data.loc[sid]
                feature_row[f"ct_s{sid}"]  = row.get("cycle_time_s", 0.0)
                feature_row[f"tq_s{sid}"]  = row.get("torque_nm",    0.0)
                feature_row[f"vb_s{sid}"]  = row.get("vibration_g",  0.0)
                feature_row[f"tp_s{sid}"]  = row.get("temperature_c",0.0)
            else:
                feature_row[f"ct_s{sid}"]  = 0.0
                feature_row[f"tq_s{sid}"]  = 0.0
                feature_row[f"vb_s{sid}"]  = 0.0
                feature_row[f"tp_s{sid}"]  = 0.0

        X_row = np.array([feature_row.get(f, 0.0) for f in self.feature_names]).reshape(1, -1)
        X_scaled = self.scaler.transform(X_row)

        prob = float(self.model.predict_proba(X_scaled)[0][1])

        # Find most important upstream station from feature importances
        importances = self.model.feature_importances_
        feat_importance = {f: importances[i] for i, f in enumerate(self.feature_names)}

        # Top feature and its station
        top_feat = max(feat_importance, key=feat_importance.get)
        risk_station = int(top_feat.split("_s")[-1]) if "_s" in top_feat else 1

        return DefectPrediction(
            vehicle_id=vehicle_id,
            defect_prob=prob,
            risk_station=risk_station,
            risk_feature=top_feat,
            confidence=prob,
        )

    def save(self):
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model":        self.model,
            "scaler":       self.scaler,
            "feature_names": self.feature_names,
        }, ARTIFACT_DIR / "defect_predictor.pkl")

    def load(self):
        data = joblib.load(ARTIFACT_DIR / "defect_predictor.pkl")
        self.model         = data["model"]
        self.scaler        = data["scaler"]
        self.feature_names = data["feature_names"]
        return self
