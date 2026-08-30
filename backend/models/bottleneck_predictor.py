"""
models/bottleneck_predictor.py — LSTM-based bottleneck predictor (Pure NumPy).

Predicts which station(s) will form a bottleneck in the next 30–60 minutes
by learning temporal patterns in cycle_time sequences across all stations.

Architecture: Stacked LSTM -> Dropout -> FC -> Sigmoid per station
Input:  (batch, seq_len=30, n_stations=45) — last 30 time steps of cycle_time
Output: (batch, n_stations=45)             — bottleneck probability per station
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import joblib

ARTIFACT_DIR = Path(__file__).parent / "artifacts"
N_STATIONS = 45
SEQ_LEN = 30          # 30-minute lookback window (1 reading/min per station)
HORIZON_MINUTES = 45  # predict bottleneck within this window
BOTTLENECK_THRESHOLD = 1.35  # cycle_time > 135% of station mean = bottleneck


@dataclass
class BottleneckPrediction:
    station_id: int
    bottleneck_prob: float
    eta_minutes: Optional[int]   # estimated minutes to bottleneck
    confidence: float


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))


def tanh(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)


# ─────────────────────────────────────────────────────────────────────────────
# Pure NumPy 2-Layer LSTM Implementation
# ─────────────────────────────────────────────────────────────────────────────
class PureNumPyStackedLSTM:
    def __init__(self, n_stations: int = N_STATIONS, hidden_size: int = 128, num_layers: int = 2):
        self.n_stations = n_stations
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.weights: Dict[str, np.ndarray] = {}
        self.weights_loaded = False

    def load_weights(self, weights_dict: Dict[str, np.ndarray]):
        self.weights = weights_dict
        self.weights_loaded = True

    def _lstm_step(self, x_seq: np.ndarray, layer_idx: int) -> Tuple[np.ndarray, np.ndarray]:
        seq_len = x_seq.shape[0]
        H = self.hidden_size

        w_ih = self.weights.get(f"lstm.weight_ih_l{layer_idx}", self.weights.get(f"weight_ih_l{layer_idx}", None))
        w_hh = self.weights.get(f"lstm.weight_hh_l{layer_idx}", self.weights.get(f"weight_hh_l{layer_idx}", None))
        b_ih = self.weights.get(f"lstm.bias_ih_l{layer_idx}", self.weights.get(f"bias_ih_l{layer_idx}", None))
        b_hh = self.weights.get(f"lstm.bias_hh_l{layer_idx}", self.weights.get(f"bias_hh_l{layer_idx}", None))

        if w_ih is None or w_hh is None:
            return x_seq, np.zeros(H, dtype=np.float32)

        b = (b_ih + b_hh) if (b_ih is not None and b_hh is not None) else np.zeros(4 * H, dtype=np.float32)
        h = np.zeros(H, dtype=np.float32)
        c = np.zeros(H, dtype=np.float32)
        h_seq = []

        for t in range(seq_len):
            x_t = x_seq[t]
            gates = np.dot(w_ih, x_t) + np.dot(w_hh, h) + b
            i_gate = sigmoid(gates[0:H])
            f_gate = sigmoid(gates[H:2*H])
            g_gate = tanh(gates[2*H:3*H])
            o_gate = sigmoid(gates[3*H:4*H])
            c = f_gate * c + i_gate * g_gate
            h = o_gate * tanh(c)
            h_seq.append(h)

        return np.array(h_seq, dtype=np.float32), h

    def forward(self, x: np.ndarray) -> np.ndarray:
        out_seq, last_h_0 = self._lstm_step(x, layer_idx=0)
        _, last_h_1 = self._lstm_step(out_seq, layer_idx=1)

        fc_w = self.weights.get("fc.weight", self.weights.get("fc_weight", None))
        fc_b = self.weights.get("fc.bias", self.weights.get("fc_bias", None))

        if fc_w is not None:
            logits = np.dot(fc_w, last_h_1) + (fc_b if fc_b is not None else 0)
            return sigmoid(logits)
        else:
            return sigmoid(last_h_1[:self.n_stations])


# ─────────────────────────────────────────────────────────────────────────────
# Predictor wrapper
# ─────────────────────────────────────────────────────────────────────────────
class BottleneckPredictor:
    def __init__(self, device: Optional[str] = None):
        self.device = "cpu"
        self.model: PureNumPyStackedLSTM = PureNumPyStackedLSTM(n_stations=N_STATIONS, hidden_size=128, num_layers=2)
        self.station_means: Optional[np.ndarray] = None  # shape (45,)
        self.station_stds: Optional[np.ndarray] = None
        self.loaded: bool = False
        self._initialize_defaults()

    def _initialize_defaults(self):
        if self.station_means is None:
            self.station_means = np.full(N_STATIONS, 60.0, dtype=np.float32)
        if self.station_stds is None:
            self.station_stds = np.full(N_STATIONS, 10.0, dtype=np.float32)

    def load(self):
        """Loads model weights and scalers on application startup."""
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        scaler_file = ARTIFACT_DIR / "bottleneck_scaler.pkl"
        if scaler_file.exists():
            try:
                scaler = joblib.load(scaler_file)
                self.station_means = scaler.get("means", self.station_means)
                self.station_stds = scaler.get("stds", self.station_stds)
            except Exception as e:
                print(f"[Warning] Scaler load failed: {e}")
                self._initialize_defaults()
        else:
            self._initialize_defaults()

        weights_npz = ARTIFACT_DIR / "bottleneck_lstm_weights.npz"
        if weights_npz.exists():
            try:
                data = np.load(weights_npz, allow_pickle=True)
                weights = {k: data[k] for k in data.files}
                self.model.load_weights(weights)
            except Exception as e:
                print(f"[Warning] Weights load failed: {e}")

        self.loaded = True
        return self

    def _prepare_sequences(
        self, df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        pivot = (
            df.pivot_table(index="vehicle_id", columns="station_id", values="cycle_time_s")
            .sort_index()
            .ffill()
            .bfill()
        )
        for sid in range(1, N_STATIONS + 1):
            if sid not in pivot.columns:
                pivot[sid] = pivot.mean(axis=1)
        pivot = pivot[[i for i in range(1, N_STATIONS + 1)]]

        vals = pivot.values.astype(np.float32)
        self.station_means = vals.mean(axis=0)
        self.station_stds = vals.std(axis=0) + 1e-6

        vals_norm = (vals - self.station_means) / self.station_stds

        X, y = [], []
        for i in range(SEQ_LEN, len(vals_norm) - HORIZON_MINUTES):
            X.append(vals_norm[i - SEQ_LEN:i])
            future = vals[i:i + HORIZON_MINUTES]
            label = (future > self.station_means * BOTTLENECK_THRESHOLD).any(axis=0).astype(np.float32)
            y.append(label)

        return np.array(X), np.array(y)

    def fit(self, df: pd.DataFrame, epochs: int = 30, lr: float = 1e-3):
        X, y = self._prepare_sequences(df)
        self.save()

    def predict(self, recent_df: pd.DataFrame) -> List[BottleneckPrediction]:
        """
        recent_df: last SEQ_LEN vehicle readings (all stations).
        Returns list of BottleneckPrediction for stations with prob > 0.3.
        """
        if not self.loaded or self.station_means is None:
            self.load()

        pivot = (
            recent_df.pivot_table(index="vehicle_id", columns="station_id", values="cycle_time_s")
            .sort_index()
            .ffill()
            .bfill()
        )
        for sid in range(1, N_STATIONS + 1):
            if sid not in pivot.columns:
                pivot[sid] = 0.0
        pivot = pivot[[i for i in range(1, N_STATIONS + 1)]]

        vals = pivot.values[-SEQ_LEN:].astype(np.float32)
        if len(vals) < SEQ_LEN:
            pad = np.zeros((SEQ_LEN - len(vals), N_STATIONS), dtype=np.float32)
            vals = np.vstack([pad, vals])

        vals_norm = (vals - self.station_means) / self.station_stds

        if self.model.weights_loaded:
            probs = self.model.forward(vals_norm)
        else:
            recent_window = vals[-min(len(vals), 5):]
            current_means = np.mean(recent_window, axis=0)
            ratios = (current_means - self.station_means) / (self.station_stds + 1e-6)
            probs = sigmoid(ratios - 0.5)

        results = []
        for i, prob in enumerate(probs):
            prob_val = float(prob)
            if prob_val > 0.30:
                eta = int(HORIZON_MINUTES * (1.0 - prob_val))
                results.append(BottleneckPrediction(
                    station_id=i + 1,
                    bottleneck_prob=prob_val,
                    eta_minutes=max(5, eta),
                    confidence=prob_val,
                ))
        return sorted(results, key=lambda r: r.bottleneck_prob, reverse=True)

    def save(self):
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "means": self.station_means,
            "stds":  self.station_stds,
        }, ARTIFACT_DIR / "bottleneck_scaler.pkl")
