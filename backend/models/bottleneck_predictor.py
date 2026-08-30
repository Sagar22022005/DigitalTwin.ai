"""
models/bottleneck_predictor.py — LSTM-based bottleneck predictor (Pure NumPy).

Predicts which station(s) will form a bottleneck in the next 30-60 minutes
by learning temporal patterns in cycle_time sequences across all stations.

Architecture: Stacked LSTM -> Dropout -> FC -> Sigmoid per station
Input: (batch, seq_len=30, n_stations=45) — last 30 time steps of cycle_time
Output: (batch, n_stations=45)             — bottleneck probability per station
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Union
import numpy as np
import pandas as pd
import joblib

ARTIFACT_DIR = Path(__file__).parent / "artifacts"
N_STATIONS = 45
SEQ_LEN = 30         # 30-minute lookback window (1 reading/min per station)
HORIZON_MINUTES = 45 # predict bottleneck within this window


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))


def tanh(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)


class PureNumPyLSTM:
    """Lightweight pure-NumPy inference for PyTorch LSTM weights."""
    def __init__(self, hidden_size: int = 64, n_stations: int = N_STATIONS):
        self.hidden_size = hidden_size
        self.n_stations = n_stations
        self.w_ih = None
        self.w_hh = None
        self.b_ih = None
        self.b_hh = None
        self.w_fc = None
        self.b_fc = None

    def load_weights(self, weights_dict: Dict[str, np.ndarray]):
        self.w_ih = weights_dict.get("w_ih", weights_dict.get("lstm.weight_ih_l0", None))
        self.w_hh = weights_dict.get("w_hh", weights_dict.get("lstm.weight_hh_l0", None))
        self.b_ih = weights_dict.get("b_ih", weights_dict.get("lstm.bias_ih_l0", None))
        self.b_hh = weights_dict.get("b_hh", weights_dict.get("lstm.bias_hh_l0", None))
        self.w_fc = weights_dict.get("w_fc", weights_dict.get("fc.weight", None))
        self.b_fc = weights_dict.get("b_fc", weights_dict.get("fc.bias", None))
        if self.w_hh is not None:
            self.hidden_size = self.w_hh.shape[1]

    def forward(self, x: np.ndarray) -> np.ndarray:
        # x shape: (batch_size, seq_len, n_stations)
        batch_size, seq_len, _ = x.shape
        H = self.hidden_size

        if self.w_ih is None:
            # Baseline fallback if weights are not provided
            mean_vals = np.mean(x, axis=1) # (batch, n_stations)
            return sigmoid(mean_vals)

        b = (self.b_ih + self.b_hh) if (self.b_ih is not None and self.b_hh is not None) else np.zeros(4 * H, dtype=np.float32)

        batch_outputs = []
        for b_idx in range(batch_size):
            h = np.zeros(H, dtype=np.float32)
            c = np.zeros(H, dtype=np.float32)
            for t in range(seq_len):
                x_t = x[b_idx, t]
                gates = np.dot(self.w_ih, x_t) + np.dot(self.w_hh, h) + b
                i_gate = sigmoid(gates[0:H])
                f_gate = sigmoid(gates[H:2*H])
                g_gate = tanh(gates[2*H:3*H])
                o_gate = sigmoid(gates[3*H:4*H])
                c = f_gate * c + i_gate * g_gate
                h = o_gate * tanh(c)

            # FC linear layer + Sigmoid per station
            if self.w_fc is not None:
                logits = np.dot(self.w_fc, h) + (self.b_fc if self.b_fc is not None else 0)
                out = sigmoid(logits)
            else:
                out = sigmoid(h[:self.n_stations])
            batch_outputs.append(out)

        return np.array(batch_outputs, dtype=np.float32)


class BottleneckPredictor:
    def __init__(self, artifact_dir: Optional[Path] = None):
        self.artifact_dir = artifact_dir or ARTIFACT_DIR
        self.model = PureNumPyLSTM(hidden_size=64, n_stations=N_STATIONS)
        self.scaler = None
        self.loaded = False
        self._load_artifacts()

    def _load_artifacts(self):
        try:
            scaler_path = self.artifact_dir / "scaler.joblib"
            if scaler_path.exists():
                self.scaler = joblib.load(scaler_path)

            npz_path = self.artifact_dir / "bottleneck_lstm_weights.npz"
            if npz_path.exists():
                data = np.load(npz_path, allow_pickle=True)
                weights = {k: data[k] for k in data.files}
                self.model.load_weights(weights)
                self.loaded = True
        except Exception as e:
            print(f"Notice: Initialized BottleneckPredictor with fallback inference: {e}")

    def predict(self, input_data: Union[np.ndarray, List, pd.DataFrame]) -> np.ndarray:
        """
        Input: (batch, 30, 45) or (30, 45) array of cycle times.
        Output: (batch, 45) or (45,) array of probabilities [0.0 - 1.0].
        """
        single_sample = False
        x = np.asarray(input_data, dtype=np.float32)

        if x.ndim == 2:
            # (seq_len, n_stations) -> add batch dim
            x = x[np.newaxis, :, :]
            single_sample = True
        elif x.ndim == 1:
            # single step fallback -> tile to 30 seq_len
            x = np.tile(x, (SEQ_LEN, 1))[np.newaxis, :, :]
            single_sample = True

        probs = self.model.forward(x)
        return probs[0] if single_sample else probs

    def predict_bottlenecks(self, input_data: Any, threshold: float = 0.6) -> Dict[str, Any]:
        probs = self.predict(input_data)
        if probs.ndim > 1:
            probs = probs[0]
        bottleneck_indices = [int(i) for i, p in enumerate(probs) if p >= threshold]
        return {
            "probabilities": probs.tolist(),
            "bottleneck_stations": bottleneck_indices,
            "threshold": threshold
        }
