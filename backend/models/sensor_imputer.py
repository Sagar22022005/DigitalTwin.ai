"""
models/sensor_imputer.py — Gaussian Process Regression for sensor-poor stations.

For the 7 legacy stations with no torque/vibration/temperature sensors,
estimates values from neighbouring well-instrumented stations and reports
uncertainty explicitly — the twin never hides what it doesn't know.
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from dataclasses import dataclass
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel
from sklearn.preprocessing import StandardScaler
from typing import Optional

ARTIFACT_DIR = Path(__file__).parent / "artifacts"
SENSOR_POOR_STATIONS = {5, 11, 19, 23, 31, 37, 42}

# Nearest well-instrumented neighbours for each sensor-poor station
NEIGHBOURS = {
    5:  [4, 6],
    11: [10, 12],
    19: [18, 20],
    23: [22, 24],
    31: [30, 32],
    37: [36, 38],
    42: [41, 43],
}

TARGETS = ["torque_nm", "vibration_g", "temperature_c"]


@dataclass
class ImputationResult:
    station_id: int
    torque_nm_est: Optional[float]
    torque_uncertainty: Optional[float]
    vibration_g_est: Optional[float]
    vibration_uncertainty: Optional[float]
    temperature_c_est: Optional[float]
    temperature_uncertainty: Optional[float]


class SensorImputer:
    """
    Fits one GP per (sensor-poor station, target metric) pair.
    Features: cycle_time + torque/vibration/temp of the 2 neighbouring stations.
    """

    def __init__(self):
        # gps[(station_id, target)] = GaussianProcessRegressor
        self.gps: dict[tuple[int, str], GaussianProcessRegressor] = {}
        self.scalers_X: dict[tuple[int, str], StandardScaler] = {}
        self.scalers_y: dict[tuple[int, str], StandardScaler] = {}

    def _build_feature_matrix(
        self,
        df: pd.DataFrame,
        station_id: int,
        neighbours: list[int],
    ) -> pd.DataFrame:
        """Build X = [cycle_time_station, neighbour_metrics...] from wide df."""
        pivot_ct = df.pivot_table(index="vehicle_id", columns="station_id", values="cycle_time_s")
        pivot_tq = df.pivot_table(index="vehicle_id", columns="station_id", values="torque_nm")
        pivot_vb = df.pivot_table(index="vehicle_id", columns="station_id", values="vibration_g")
        pivot_tp = df.pivot_table(index="vehicle_id", columns="station_id", values="temperature_c")

        features = {}
        if station_id in pivot_ct.columns:
            features[f"ct_{station_id}"] = pivot_ct[station_id]
        for n in neighbours:
            if n in pivot_ct.columns:
                features[f"ct_{n}"]  = pivot_ct[n]
            if n in pivot_tq.columns:
                features[f"tq_{n}"]  = pivot_tq[n]
            if n in pivot_vb.columns:
                features[f"vb_{n}"]  = pivot_vb[n]
            if n in pivot_tp.columns:
                features[f"tp_{n}"]  = pivot_tp[n]

        return pd.DataFrame(features).dropna()

    def fit(self, df: pd.DataFrame):
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        kernel = ConstantKernel(1.0) * RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)

        for station_id in SENSOR_POOR_STATIONS:
            neighbours = NEIGHBOURS[station_id]
            X_df = self._build_feature_matrix(df, station_id, neighbours)
            if len(X_df) < 30:
                continue

            for target in TARGETS:
                # y comes from the nearest neighbour's actual reading (proxy)
                proxy_station = neighbours[0]
                pivot_target = df.pivot_table(
                    index="vehicle_id", columns="station_id", values=target
                )
                if proxy_station not in pivot_target.columns:
                    continue

                y_series = pivot_target[proxy_station].reindex(X_df.index).dropna()
                X_aligned = X_df.loc[y_series.index]

                scaler_X = StandardScaler()
                scaler_y = StandardScaler()
                X_scaled = scaler_X.fit_transform(X_aligned.values)
                y_scaled = scaler_y.fit_transform(y_series.values.reshape(-1, 1)).ravel()

                # Subsample for speed (GP is O(n^3))
                if len(X_scaled) > 300:
                    idx = np.random.choice(len(X_scaled), 300, replace=False)
                    X_scaled = X_scaled[idx]
                    y_scaled  = y_scaled[idx]

                gp = GaussianProcessRegressor(
                    kernel=kernel,
                    alpha=1e-3,
                    normalize_y=False,
                    n_restarts_optimizer=3,
                )
                gp.fit(X_scaled, y_scaled)

                key = (station_id, target)
                self.gps[key] = gp
                self.scalers_X[key] = scaler_X
                self.scalers_y[key] = scaler_y

        self.save()
        print(f"[SensorImputer] Trained {len(self.gps)} GP models.")

    def impute(self, station_id: int, neighbour_readings: dict) -> ImputationResult:
        """
        Impute all metrics for a sensor-poor station.
        neighbour_readings: {neighbour_station_id: {metric: value}}
        Returns ImputationResult with estimates and uncertainty (1-sigma).
        """
        result = ImputationResult(
            station_id=station_id,
            torque_nm_est=None, torque_uncertainty=None,
            vibration_g_est=None, vibration_uncertainty=None,
            temperature_c_est=None, temperature_uncertainty=None,
        )

        for target, attr_est, attr_unc in [
            ("torque_nm",     "torque_nm_est",    "torque_uncertainty"),
            ("vibration_g",   "vibration_g_est",  "vibration_uncertainty"),
            ("temperature_c", "temperature_c_est","temperature_uncertainty"),
        ]:
            key = (station_id, target)
            if key not in self.gps:
                continue

            gp       = self.gps[key]
            scaler_X = self.scalers_X[key]
            scaler_y = self.scalers_y[key]

            # Build feature row from neighbour readings
            neighbours = NEIGHBOURS[station_id]
            feature_vals = []
            for n in neighbours:
                if n in neighbour_readings:
                    nr = neighbour_readings[n]
                    feature_vals.extend([
                        nr.get("cycle_time_s", 0.0),
                        nr.get("torque_nm", 0.0),
                        nr.get("vibration_g", 0.0),
                        nr.get("temperature_c", 0.0),
                    ])
                else:
                    feature_vals.extend([0.0, 0.0, 0.0, 0.0])

            X_row = np.array(feature_vals[:scaler_X.n_features_in_]).reshape(1, -1)
            try:
                X_scaled = scaler_X.transform(X_row)
                y_scaled_pred, y_scaled_std = gp.predict(X_scaled, return_std=True)
                y_pred = scaler_y.inverse_transform(y_scaled_pred.reshape(-1, 1))[0, 0]
                y_std  = float(y_scaled_std[0]) * scaler_y.scale_[0]
                setattr(result, attr_est, float(y_pred))
                setattr(result, attr_unc, float(y_std))
            except Exception:
                pass

        return result

    def save(self):
        joblib.dump(
            {"gps": self.gps, "scalers_X": self.scalers_X, "scalers_y": self.scalers_y},
            ARTIFACT_DIR / "sensor_imputer.pkl",
        )

    def load(self):
        data = joblib.load(ARTIFACT_DIR / "sensor_imputer.pkl")
        self.gps       = data["gps"]
        self.scalers_X = data["scalers_X"]
        self.scalers_y = data["scalers_y"]
        return self
