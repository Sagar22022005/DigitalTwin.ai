"""
models/bottleneck_predictor.py — LSTM-based bottleneck predictor.

Predicts which station(s) will form a bottleneck in the next 30–60 minutes
by learning temporal patterns in cycle_time sequences across all stations.

Architecture: Stacked LSTM → Dropout → FC → Sigmoid per station
Input:  (batch, seq_len=30, n_stations=45) — last 30 time steps of cycle_time
Output: (batch, n_stations=45)             — bottleneck probability per station
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import joblib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

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


# ─────────────────────────────────────────────────────────────────────────────
# Model definition
# ─────────────────────────────────────────────────────────────────────────────
class BottleneckLSTM(nn.Module):
    def __init__(self, n_stations: int = N_STATIONS, hidden_size: int = 128, num_layers: int = 2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_stations,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.3,
        )
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(hidden_size, n_stations)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, n_stations)
        lstm_out, _ = self.lstm(x)
        last_hidden = lstm_out[:, -1, :]          # take last time step
        out = self.dropout(last_hidden)
        out = self.fc(out)
        return self.sigmoid(out)


# ─────────────────────────────────────────────────────────────────────────────
# Predictor wrapper
# ─────────────────────────────────────────────────────────────────────────────
class BottleneckPredictor:
    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model: Optional[BottleneckLSTM] = None
        self.station_means: Optional[np.ndarray] = None  # shape (45,)
        self.station_stds: Optional[np.ndarray] = None

    def _prepare_sequences(
        self, df: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Pivot telemetry into (n_samples, SEQ_LEN, N_STATIONS) sequences.
        Labels: 1 if station cycle_time exceeds threshold within HORIZON_MINUTES
        """
        # Pivot: index = time step, columns = station_id
        pivot = (
            df.pivot_table(index="vehicle_id", columns="station_id", values="cycle_time_s")
            .sort_index()
            .fillna(method="ffill")
            .fillna(method="bfill")
        )
        # Ensure all 45 stations are present
        for sid in range(1, N_STATIONS + 1):
            if sid not in pivot.columns:
                pivot[sid] = pivot.mean(axis=1)
        pivot = pivot[[i for i in range(1, N_STATIONS + 1)]]

        vals = pivot.values.astype(np.float32)  # (n_vehicles, n_stations)
        self.station_means = vals.mean(axis=0)
        self.station_stds  = vals.std(axis=0) + 1e-6

        # Normalise
        vals_norm = (vals - self.station_means) / self.station_stds

        X, y = [], []
        for i in range(SEQ_LEN, len(vals_norm) - HORIZON_MINUTES):
            X.append(vals_norm[i - SEQ_LEN:i])          # (SEQ_LEN, 45)
            # Label: is any station's raw cycle_time > threshold * mean in horizon?
            future = vals[i:i + HORIZON_MINUTES]         # (horizon, 45)
            label = (future > self.station_means * BOTTLENECK_THRESHOLD).any(axis=0).astype(np.float32)
            y.append(label)                              # (45,)

        return np.array(X), np.array(y)

    def fit(self, df: pd.DataFrame, epochs: int = 30, lr: float = 1e-3):
        X, y = self._prepare_sequences(df)
        X_t = torch.tensor(X, dtype=torch.float32).to(self.device)
        y_t = torch.tensor(y, dtype=torch.float32).to(self.device)

        dataset = torch.utils.data.TensorDataset(X_t, y_t)
        loader  = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)

        self.model = BottleneckLSTM().to(self.device)
        optimiser = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.BCELoss()

        self.model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            for xb, yb in loader:
                optimiser.zero_grad()
                preds = self.model(xb)
                loss  = criterion(preds, yb)
                loss.backward()
                optimiser.step()
                epoch_loss += loss.item()
            if (epoch + 1) % 5 == 0:
                print(f"  Epoch {epoch+1}/{epochs} | Loss: {epoch_loss/len(loader):.4f}")

        self.save()

    def predict(self, recent_df: pd.DataFrame) -> list[BottleneckPrediction]:
        """
        recent_df: last SEQ_LEN vehicle readings (all stations).
        Returns list of BottleneckPrediction for stations with prob > 0.3.
        """
        if self.model is None:
            self.load()

        pivot = (
            recent_df.pivot_table(index="vehicle_id", columns="station_id", values="cycle_time_s")
            .sort_index()
            .fillna(method="ffill")
            .fillna(method="bfill")
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
        X_t = torch.tensor(vals_norm[np.newaxis], dtype=torch.float32).to(self.device)

        self.model.eval()
        with torch.no_grad():
            probs = self.model(X_t).cpu().numpy()[0]   # shape (45,)

        results = []
        for i, prob in enumerate(probs):
            if prob > 0.30:
                eta = int(HORIZON_MINUTES * (1.0 - prob))   # rough ETA estimate
                results.append(BottleneckPrediction(
                    station_id=i + 1,
                    bottleneck_prob=float(prob),
                    eta_minutes=max(5, eta),
                    confidence=float(prob),
                ))
        return sorted(results, key=lambda r: r.bottleneck_prob, reverse=True)

    def save(self):
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), ARTIFACT_DIR / "bottleneck_lstm.pt")
        joblib.dump({
            "means": self.station_means,
            "stds":  self.station_stds,
        }, ARTIFACT_DIR / "bottleneck_scaler.pkl")

    def load(self):
        self.model = BottleneckLSTM().to(self.device)
        self.model.load_state_dict(torch.load(
            ARTIFACT_DIR / "bottleneck_lstm.pt",
            map_location=self.device,
        ))
        self.model.eval()
        scaler = joblib.load(ARTIFACT_DIR / "bottleneck_scaler.pkl")
        self.station_means = scaler["means"]
        self.station_stds  = scaler["stds"]
        return self
