"""
assembly_line.py — SimPy discrete-event simulation of a 45-station vehicle
assembly line split across 3 manufacturing zones.

Fault injection modes:
  - Bottleneck: gradual cycle_time drift at a target station (tooling wear)
  - Defect:     bad torque reading upstream that surfaces at QC (Station 44)

Author: AI AssemblyTwin Team | AIC 2026
"""

import simpy
import numpy as np
import sqlite3
import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Station configuration
# ─────────────────────────────────────────────────────────────────────────────
ZONES = {
    "body":  list(range(1, 16)),   # Stations 1–15
    "paint": list(range(16, 29)),  # Stations 16–28
    "final": list(range(29, 46)),  # Stations 29–45
}

# Stations with legacy/no sensors — only cycle_time + operator_id available
SENSOR_POOR_STATIONS = {5, 11, 19, 23, 31, 37, 42}

# Normal operating parameters per zone (mean, std)
ZONE_PARAMS = {
    "body":  {"cycle_time": (62.0, 3.5), "torque": (45.0, 4.0), "vibration": (0.8, 0.15), "temp": (38.0, 3.0)},
    "paint": {"cycle_time": (95.0, 5.0), "torque": (20.0, 2.5), "vibration": (0.3, 0.08), "temp": (55.0, 5.0)},
    "final": {"cycle_time": (75.0, 4.0), "torque": (60.0, 5.0), "vibration": (1.1, 0.20), "temp": (35.0, 2.5)},
}

N_OPERATORS = 8
SHIFT_DURATION_S = 8 * 3600  # 8-hour shifts
DB_PATH = Path(__file__).parent.parent / "data" / "telemetry.db"


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class StationEvent:
    station_id: int
    zone: str
    vehicle_id: int
    timestamp: float
    cycle_time_s: float
    torque_nm: Optional[float]
    vibration_g: Optional[float]
    temperature_c: Optional[float]
    operator_id: int
    is_sensor_poor: bool
    fault_active: bool = False
    anomaly_score: Optional[float] = None
    bottleneck_prob: Optional[float] = None
    defect_prob: Optional[float] = None
    torque_nm_imputed: Optional[float] = None
    imputation_uncertainty: Optional[float] = None


@dataclass
class FaultState:
    """Tracks active faults in the simulation."""
    bottleneck_station: Optional[int] = None
    bottleneck_start: Optional[float] = None
    bottleneck_severity: float = 0.0       # 0.0 → 1.0 ramp over time
    defect_station: Optional[int] = None
    defect_start: Optional[float] = None
    defect_torque_offset: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Database helpers
# ─────────────────────────────────────────────────────────────────────────────
def init_db(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS station_events (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id              INTEGER NOT NULL,
            zone                    TEXT NOT NULL,
            vehicle_id              INTEGER NOT NULL,
            timestamp               REAL NOT NULL,
            cycle_time_s            REAL NOT NULL,
            torque_nm               REAL,
            vibration_g             REAL,
            temperature_c           REAL,
            operator_id             INTEGER NOT NULL,
            is_sensor_poor          INTEGER NOT NULL,
            fault_active            INTEGER NOT NULL DEFAULT 0,
            anomaly_score           REAL,
            bottleneck_prob         REAL,
            defect_prob             REAL,
            torque_nm_imputed       REAL,
            imputation_uncertainty  REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at           REAL NOT NULL,
            resolved_at          REAL,
            station_id           INTEGER NOT NULL,
            alert_type           TEXT NOT NULL,
            confidence           REAL NOT NULL,
            eta_minutes          INTEGER,
            status               TEXT NOT NULL DEFAULT 'active',
            approved_intervention TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_station ON station_events(station_id, timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_vehicle ON station_events(vehicle_id)")
    conn.commit()
    conn.close()


def insert_event(event: StationEvent, db_path: Path = DB_PATH):
    conn = sqlite3.connect(str(db_path))
    d = asdict(event)
    conn.execute("""
        INSERT INTO station_events
            (station_id, zone, vehicle_id, timestamp, cycle_time_s,
             torque_nm, vibration_g, temperature_c, operator_id,
             is_sensor_poor, fault_active, anomaly_score,
             bottleneck_prob, defect_prob, torque_nm_imputed, imputation_uncertainty)
        VALUES
            (:station_id, :zone, :vehicle_id, :timestamp, :cycle_time_s,
             :torque_nm, :vibration_g, :temperature_c, :operator_id,
             :is_sensor_poor, :fault_active, :anomaly_score,
             :bottleneck_prob, :defect_prob, :torque_nm_imputed, :imputation_uncertainty)
    """, d)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Core simulation
# ─────────────────────────────────────────────────────────────────────────────
def _get_zone(station_id: int) -> str:
    for zone, stations in ZONES.items():
        if station_id in stations:
            return zone
    raise ValueError(f"Station {station_id} not found in any zone")


def _sample_metrics(
    station_id: int,
    zone: str,
    fault_state: FaultState,
    sim_time: float,
    rng: np.random.Generator,
) -> tuple[float, Optional[float], Optional[float], Optional[float]]:
    """Sample realistic station metrics, applying fault perturbations."""
    params = ZONE_PARAMS[zone]
    is_poor = station_id in SENSOR_POOR_STATIONS

    # Base cycle time with optional bottleneck drift
    ct_mean, ct_std = params["cycle_time"]
    if fault_state.bottleneck_station == station_id and fault_state.bottleneck_start is not None:
        elapsed = sim_time - fault_state.bottleneck_start
        # Severity ramps over 40 minutes (2400 s), max +60% cycle time
        fault_state.bottleneck_severity = min(elapsed / 2400.0, 1.0)
        ct_mean = ct_mean * (1.0 + 0.60 * fault_state.bottleneck_severity)

    cycle_time = max(5.0, rng.normal(ct_mean, ct_std))

    if is_poor:
        return cycle_time, None, None, None

    # Torque — defect fault injects a systematic offset upstream
    t_mean, t_std = params["torque"]
    torque_offset = 0.0
    if fault_state.defect_station == station_id and fault_state.defect_start is not None:
        torque_offset = fault_state.defect_torque_offset
    torque = rng.normal(t_mean + torque_offset, t_std)

    vibration = max(0.0, rng.normal(*params["vibration"]))
    temperature = rng.normal(*params["temp"])

    return cycle_time, torque, vibration, temperature


class AssemblyLineSimulation:
    """
    SimPy-based assembly line simulation.

    Usage:
        sim = AssemblyLineSimulation()
        sim.run_historical(days=7)          # bulk data generation
        sim.run_live(callback=my_fn)        # real-time streaming
        sim.inject_fault("bottleneck", 12)  # inject fault at station 12
        sim.inject_intervention("reduce_feed_rate", 12)
    """

    def __init__(self, db_path: Path = DB_PATH, speed_multiplier: float = 1.0):
        self.db_path = db_path
        self.speed_multiplier = speed_multiplier  # >1 = faster than real time
        self.fault_state = FaultState()
        self.rng = np.random.default_rng(seed=42)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._callback: Optional[Callable] = None
        init_db(db_path)

    # ── Public API ────────────────────────────────────────────────────────────

    def inject_fault(self, fault_type: str, station_id: int):
        """Inject a fault into the running simulation (thread-safe)."""
        with self._lock:
            if fault_type == "bottleneck":
                self.fault_state.bottleneck_station = station_id
                self.fault_state.bottleneck_start = time.time()
                self.fault_state.bottleneck_severity = 0.0
            elif fault_type == "defect":
                self.fault_state.defect_station = station_id
                self.fault_state.defect_start = time.time()
                self.fault_state.defect_torque_offset = self.rng.uniform(12.0, 20.0)

    def inject_intervention(self, option: str, station_id: int):
        """Apply an approved intervention — reduces fault severity."""
        with self._lock:
            if option == "add_technician" and self.fault_state.bottleneck_station == station_id:
                self.fault_state.bottleneck_severity = max(0.0, self.fault_state.bottleneck_severity - 0.75)
                self.fault_state.bottleneck_start = None  # halt further drift
            elif option == "reduce_feed_rate" and self.fault_state.bottleneck_station == station_id:
                self.fault_state.bottleneck_severity = max(0.0, self.fault_state.bottleneck_severity - 0.55)
            elif option == "pause_buffer":
                self.fault_state.bottleneck_severity = 0.0
                self.fault_state.bottleneck_station = None

    def reset(self):
        """Reset all faults (for demo purposes)."""
        with self._lock:
            self.fault_state = FaultState()

    def stop(self):
        self._stop_event.set()

    # ── Historical bulk generation ────────────────────────────────────────────

    def run_historical(self, days: int = 7):
        """
        Generate `days` of synthetic telemetry using vectorised NumPy + batch
        SQLite inserts. Runs in seconds. SimPy is used only for live mode.
        """
        print(f"[Simulator] Generating {days} days of data (vectorised)...")
        sim_start_ts = time.time() - days * 86400
        vehicles_per_day = int(86400 / 30)   # 1 new vehicle every 30 s
        total_vehicles   = days * vehicles_per_day

        conn   = sqlite3.connect(str(self.db_path))
        batch: list[tuple] = []
        BATCH_SIZE = 5000

        for vid in range(1, total_vehicles + 1):
            vehicle_sim_time = (vid - 1) * 30.0
            with self._lock:
                b_station = self.fault_state.bottleneck_station
                b_start   = self.fault_state.bottleneck_start
                d_station = self.fault_state.defect_station
                d_offset  = self.fault_state.defect_torque_offset

            for station_id in range(1, 46):
                zone    = _get_zone(station_id)
                params  = ZONE_PARAMS[zone]
                is_poor = station_id in SENSOR_POOR_STATIONS

                ct_mean, ct_std = params["cycle_time"]
                if b_station == station_id and b_start is not None:
                    elapsed = vehicle_sim_time - b_start
                    sev     = min(max(elapsed / 2400.0, 0.0), 1.0)
                    ct_mean = ct_mean * (1.0 + 0.60 * sev)
                cycle_time = float(max(5.0, self.rng.normal(ct_mean, ct_std)))

                torque = vibration = temperature = None
                if not is_poor:
                    t_mean, t_std = params["torque"]
                    offset      = d_offset if d_station == station_id else 0.0
                    torque      = float(self.rng.normal(t_mean + offset, t_std))
                    vibration   = float(max(0.0, self.rng.normal(*params["vibration"])))
                    temperature = float(self.rng.normal(*params["temp"]))

                operator_id  = int(vehicle_sim_time // SHIFT_DURATION_S % N_OPERATORS) + 1
                fault_active = int(b_station == station_id or d_station == station_id)
                ts           = sim_start_ts + vehicle_sim_time

                batch.append((
                    station_id, zone, vid, ts, cycle_time,
                    torque, vibration, temperature, operator_id,
                    int(is_poor), fault_active,
                    None, None, None, None, None,
                ))

            if len(batch) >= BATCH_SIZE:
                conn.executemany("""
                    INSERT INTO station_events
                        (station_id,zone,vehicle_id,timestamp,cycle_time_s,
                         torque_nm,vibration_g,temperature_c,operator_id,
                         is_sensor_poor,fault_active,anomaly_score,
                         bottleneck_prob,defect_prob,torque_nm_imputed,
                         imputation_uncertainty)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, batch)
                conn.commit()
                batch.clear()

            if vid % 5000 == 0:
                print(f"  {vid/total_vehicles*100:.0f}% — vehicle {vid:,}/{total_vehicles:,}")

        if batch:
            conn.executemany("""
                INSERT INTO station_events
                    (station_id,zone,vehicle_id,timestamp,cycle_time_s,
                     torque_nm,vibration_g,temperature_c,operator_id,
                     is_sensor_poor,fault_active,anomaly_score,
                     bottleneck_prob,defect_prob,torque_nm_imputed,
                     imputation_uncertainty)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, batch)
            conn.commit()
        conn.close()
        total_events = total_vehicles * 45
        print(f"[Simulator] Done. {total_events:,} events written.")

    # ── Live streaming ────────────────────────────────────────────────────────

    def run_live(self, callback: Optional[Callable] = None):
        """
        Run simulation in real time. Calls callback(StationEvent) for each
        event — the FastAPI WebSocket broadcaster will use this hook.
        """
        self._callback = callback
        self._stop_event.clear()
        env = simpy.rt.RealtimeEnvironment(factor=1.0 / self.speed_multiplier, strict=False)
        sim_start_ts = time.time()
        vehicle_counter = [0]

        def vehicle_process(env, vehicle_id: int):
            for station_id in range(1, 46):
                if self._stop_event.is_set():
                    return
                zone = _get_zone(station_id)
                with self._lock:
                    fs_snap = FaultState(
                        bottleneck_station=self.fault_state.bottleneck_station,
                        bottleneck_start=self.fault_state.bottleneck_start,
                        bottleneck_severity=self.fault_state.bottleneck_severity,
                        defect_station=self.fault_state.defect_station,
                        defect_start=self.fault_state.defect_start,
                        defect_torque_offset=self.fault_state.defect_torque_offset,
                    )
                ct, torque, vib, temp = _sample_metrics(
                    station_id, zone, fs_snap, env.now, self.rng
                )
                is_fault = (
                    fs_snap.bottleneck_station == station_id or
                    fs_snap.defect_station == station_id
                )
                evt = StationEvent(
                    station_id=station_id,
                    zone=zone,
                    vehicle_id=vehicle_id,
                    timestamp=sim_start_ts + env.now,
                    cycle_time_s=ct,
                    torque_nm=torque,
                    vibration_g=vib,
                    temperature_c=temp,
                    operator_id=int(env.now // SHIFT_DURATION_S % N_OPERATORS) + 1,
                    is_sensor_poor=(station_id in SENSOR_POOR_STATIONS),
                    fault_active=is_fault,
                )
                insert_event(evt, self.db_path)
                if self._callback:
                    try:
                        self._callback(evt)
                    except Exception:
                        pass
                yield env.timeout(ct)

        def vehicle_spawner(env):
            vid = 0
            while not self._stop_event.is_set():
                vid += 1
                env.process(vehicle_process(env, vid))
                yield env.timeout(30)

        env.process(vehicle_spawner(env))
        try:
            env.run()
        except KeyboardInterrupt:
            pass
