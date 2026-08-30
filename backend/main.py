"""
main.py — FastAPI backend for AI AssemblyTwin.

Endpoints:
  WS   /ws/live                    real-time station events + alerts
  POST /api/demo/inject            inject a fault {station_id, fault_type}
  POST /api/demo/reset             reset simulation
  POST /api/interventions/approve  approve intervention {alert_id, option_id}
  GET  /api/history/station/{id}   last N cycles for a station
  GET  /api/history/throughput     aggregated throughput by hour
  GET  /api/alerts                 all active alerts
  GET  /api/roi                    ROI metrics
  GET  /api/stations/status        current status of all 45 stations
"""

import asyncio
import json
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Internal imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from simulator.assembly_line import AssemblyLineSimulation, DB_PATH, SENSOR_POOR_STATIONS
from models.anomaly_detector import AnomalyDetector
from models.bottleneck_predictor import BottleneckPredictor
from models.defect_predictor import DefectPredictor
from models.sensor_imputer import SensorImputer

# ─────────────────────────────────────────────────────────────────────────────
# Application state
# ─────────────────────────────────────────────────────────────────────────────
class AppState:
    sim: AssemblyLineSimulation
    anomaly_detector: AnomalyDetector
    bottleneck_predictor: BottleneckPredictor
    defect_predictor: DefectPredictor
    sensor_imputer: SensorImputer
    ws_clients: set[WebSocket]
    station_windows: dict[int, list[dict]]   # rolling 10-cycle buffer per station
    active_alerts: dict[int, dict]           # alert_id → alert dict
    alert_counter: int
    vehicles_completed: int
    sim_session_id: int
    roi_stats: dict
    loop: Optional[asyncio.AbstractEventLoop] = None

state = AppState()
state.ws_clients        = set()
state.station_windows   = {sid: [] for sid in range(1, 46)}
state.active_alerts     = {}
state.alert_counter     = 0
state.vehicles_completed = 0
state.sim_session_id    = 1
state.roi_stats         = {
    "throughput_recovered_pct": 0.0,
    "defect_cost_avoided_inr":  0.0,
    "interventions_approved":   0,
    "false_alerts_dismissed":   0,
}


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — startup & shutdown
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    state.loop = asyncio.get_running_loop()
    print("[Startup] Loading ML models...")
    ARTIFACTS = Path(__file__).parent / "models" / "artifacts"
    state.anomaly_detector    = AnomalyDetector()
    state.bottleneck_predictor = BottleneckPredictor()
    state.defect_predictor    = DefectPredictor()
    state.sensor_imputer      = SensorImputer()

    if (ARTIFACTS / "anomaly_models.pkl").exists():
        state.anomaly_detector.load()
        print("  [OK] AnomalyDetector")
    if (ARTIFACTS / "bottleneck_lstm.pt").exists():
        state.bottleneck_predictor.load()
        print("  [OK] BottleneckPredictor")
    if (ARTIFACTS / "defect_predictor.pkl").exists():
        state.defect_predictor.load()
        print("  [OK] DefectPredictor")
    if (ARTIFACTS / "sensor_imputer.pkl").exists():
        state.sensor_imputer.load()
        print("  [OK] SensorImputer")

    print("[Startup] Starting simulation...")
    state.sim = AssemblyLineSimulation(speed_multiplier=35.0)  # 5x real time for demo

    # Run simulation in background thread
    def run_sim():
        state.sim.run_live(callback=on_sim_event)

    sim_thread = threading.Thread(target=run_sim, daemon=True)
    sim_thread.start()

    # Auto-play demo: inject bottleneck at station 12 after 3 min
    async def auto_demo():
        await asyncio.sleep(180)
        state.sim.inject_fault("bottleneck", 12)
        print("[Demo] Auto-injected bottleneck at Station 12")
        await asyncio.sleep(300)
        state.sim.inject_fault("defect", 7)
        print("[Demo] Auto-injected defect at Station 7")

    asyncio.create_task(auto_demo())
    dispatcher_task = asyncio.create_task(event_dispatcher())

    yield

    dispatcher_task.cancel()
    state.sim.stop()
    print("[Shutdown] Simulation stopped.")


# ─────────────────────────────────────────────────────────────────────────────
# Simulation event callback (runs in sim thread, posts to async queue)
# ─────────────────────────────────────────────────────────────────────────────
_event_queue: asyncio.Queue = asyncio.Queue()

def on_sim_event(event, session_id: Optional[int] = None):
    """Called by SimPy thread for each station event. Thread-safe bridge."""
    if state.loop and state.loop.is_running():
        evt_dict = asdict(event)
        evt_dict["sim_session_id"] = session_id if session_id is not None else state.sim_session_id
        state.loop.call_soon_threadsafe(_event_queue.put_nowait, evt_dict)


# ─────────────────────────────────────────────────────────────────────────────
# Inference pipeline
# ─────────────────────────────────────────────────────────────────────────────
async def process_event(event: dict) -> dict:
    """Run inference pipeline on a raw sim event. Returns enriched event."""
    sid = event["station_id"]

    # Sensor imputation for poor stations
    if event.get("is_sensor_poor"):
        neighbours_data = {}
        from simulator.assembly_line import NEIGHBOURS
        for n_sid in NEIGHBOURS.get(sid, []):
            if state.station_windows[n_sid]:
                neighbours_data[n_sid] = state.station_windows[n_sid][-1]
        if neighbours_data:
            imp = state.sensor_imputer.impute(
                sid,
                neighbours_data,
                event.get("cycle_time_s", 60.0)
            )
            event["torque_nm_imputed"]       = imp.torque_nm_est
            event["imputation_uncertainty"]  = imp.torque_uncertainty
            event["vibration_g_imputed"]     = imp.vibration_g_est
            event["vibration_uncertainty"]   = imp.vibration_uncertainty
            event["temperature_c_imputed"]   = imp.temperature_c_est
            event["temperature_uncertainty"] = imp.temperature_uncertainty

    # Update rolling window
    window = state.station_windows[sid]
    window.append(event)
    if len(window) > 10:
        window.pop(0)

    # Completed vehicle counter (Station 45 final assembly)
    if sid == 45:
        state.vehicles_completed += 1
    event["vehicles_completed"] = state.vehicles_completed

    # Anomaly detection & Fault alerts
    if event.get("fault_active"):
        await maybe_raise_alert(event, {})
    elif len(window) >= 3:
        win_df = pd.DataFrame(window)
        anom = state.anomaly_detector.predict(win_df, sid)
        event["anomaly_score"] = anom.anomaly_score
        if anom.is_anomaly and anom.anomaly_score < -0.12:
            await maybe_raise_alert(event, anom.contributing_features)

    return event


async def maybe_raise_alert(event: dict, contributing_features: dict):
    """Raise a bottleneck or defect alert if confidence is sufficient."""
    sid = event["station_id"]
    is_injected_fault = bool(event.get("fault_active"))

    # Avoid duplicate active alerts for same station
    existing = [a for a in state.active_alerts.values()
                if a["station_id"] == sid and a["status"] == "active"]
    if existing:
        return

    confidence = None
    eta_minutes = None

    # Check LSTM bottleneck predictor
    recent_df = pd.DataFrame([
        e for window in state.station_windows.values() for e in window
    ])
    if len(recent_df) >= 10:
        try:
            bp_preds = state.bottleneck_predictor.predict(recent_df)
            bp_match = next((p for p in bp_preds if p.station_id == sid), None)
            if bp_match and bp_match.bottleneck_prob > 0.40:
                confidence  = float(bp_match.confidence)
                eta_minutes = int(bp_match.eta_minutes)
        except Exception:
            pass

    # Fallback ONLY for explicitly injected demo faults during model warm-up
    if is_injected_fault:
        if confidence is None:
            confidence = 0.85
        if eta_minutes is None:
            eta_minutes = 15
    else:
        # Normal simulation: ONLY raise if genuine model prediction exists
        if confidence is None or eta_minutes is None:
            return

    state.alert_counter += 1
    alert = {
        "id":           state.alert_counter,
        "type":         "bottleneck" if sid != 7 else "defect",
        "station_id":   sid,
        "confidence":   confidence,
        "eta_minutes":  eta_minutes,
        "status":       "active",
        "created_at":   time.time(),
        "contributing": contributing_features if contributing_features else {"cycle_time_s": 2.5, "vibration_g": 1.2},
        "interventions": [
            {"id": "add_technician",  "label": "Add 1 Technician",       "recovery_pct": 73, "cost": "Low"},
            {"id": "reduce_feed",     "label": "Reduce Feed Rate 15%",   "recovery_pct": 55, "cost": "None"},
            {"id": "pause_buffer",    "label": "Pause Upstream Buffer",  "recovery_pct": 100,"cost": "Medium"},
        ],
    }
    state.active_alerts[state.alert_counter] = alert
    _insert_alert_db(alert)
    await broadcast({"type": "alert", "alert": alert})


def _insert_alert_db(alert: dict):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        INSERT INTO alerts (created_at, station_id, alert_type, confidence, eta_minutes, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (alert["created_at"], alert["station_id"], alert["type"],
          alert["confidence"], alert["eta_minutes"], alert["status"]))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket broadcast
# ─────────────────────────────────────────────────────────────────────────────
async def broadcast(message: dict):
    dead = set()
    for ws in state.ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    state.ws_clients -= dead


async def event_dispatcher():
    """Background task: drain queue, run inference, broadcast."""
    while True:
        try:
            event = await asyncio.wait_for(_event_queue.get(), timeout=1.0)
            if event.get("sim_session_id") != state.sim_session_id:
                continue   # Discard stale events from previous simulation runs
            enriched = await process_event(event)
            await broadcast({"type": "station_update", "data": enriched})
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"[Dispatcher] Error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="AI AssemblyTwin API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.ws_clients.add(ws)
    # Send current alert state on connect
    await ws.send_json({"type": "init", "alerts": list(state.active_alerts.values())})
    try:
        while True:
            await ws.receive_text()   # keep connection alive
    except WebSocketDisconnect:
        state.ws_clients.discard(ws)


# ── REST endpoints ────────────────────────────────────────────────────────────
class InjectRequest(BaseModel):
    station_id: int
    fault_type: str   # "bottleneck" | "defect"

class ApproveRequest(BaseModel):
    alert_id: int
    option_id: str    # "add_technician" | "reduce_feed" | "pause_buffer"


@app.post("/api/demo/inject")
async def inject_fault(req: InjectRequest):
    if req.fault_type not in ("bottleneck", "defect"):
        raise HTTPException(400, "fault_type must be 'bottleneck' or 'defect'")
    if not (1 <= req.station_id <= 45):
        raise HTTPException(400, "station_id must be between 1 and 45")
    state.sim.inject_fault(req.fault_type, req.station_id)
    return {"status": "injected", "station_id": req.station_id, "fault_type": req.fault_type}


@app.post("/api/demo/reset")
async def reset_simulation():
    # 1. Increment session ID (invalidates any events in flight from old thread)
    state.sim_session_id += 1
    current_session = state.sim_session_id

    # 2. Stop current simulation thread
    state.sim.stop()

    # 3. Drain lingering event queue
    while not _event_queue.empty():
        try:
            _event_queue.get_nowait()
        except Exception:
            break

    # 4. Reset all state, rolling windows, alerts, and counters
    state.station_windows    = {sid: [] for sid in range(1, 46)}
    state.active_alerts.clear()
    state.vehicles_completed = 0
    state.roi_stats          = {
        "throughput_recovered_pct": 0.0,
        "defect_cost_avoided_inr":  0.0,
        "interventions_approved":   0,
        "false_alerts_dismissed":   0,
    }

    # 5. Create fresh simulation instance and start background thread
    state.sim = AssemblyLineSimulation(speed_multiplier=35.0, session_id=current_session)
    def run_sim():
        state.sim.run_live(callback=on_sim_event)
    threading.Thread(target=run_sim, daemon=True).start()

    # 6. Broadcast reset payload to all connected WebSockets
    await broadcast({"type": "reset", "vehicles_completed": 0, "sim_session_id": current_session})
    return {"status": "reset", "sim_session_id": current_session}


@app.post("/api/interventions/approve")
async def approve_intervention(req: ApproveRequest):
    alert = state.active_alerts.get(req.alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")

    option_map = {
        "add_technician": "add_technician",
        "reduce_feed":    "reduce_feed_rate",
        "pause_buffer":   "pause_buffer",
    }
    sim_option = option_map.get(req.option_id)
    if sim_option:
        state.sim.inject_intervention(sim_option, alert["station_id"])

    alert["status"] = "approved"
    alert["approved_intervention"] = req.option_id
    state.roi_stats["interventions_approved"] += 1
    state.roi_stats["throughput_recovered_pct"] += 5.2   # illustrative
    state.roi_stats["defect_cost_avoided_inr"]  += 350000

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("UPDATE alerts SET status=?, approved_intervention=?, resolved_at=? WHERE id=?",
                 ("approved", req.option_id, time.time(), req.alert_id))
    conn.commit()
    conn.close()

    await broadcast({"type": "alert_resolved", "alert_id": req.alert_id, "option": req.option_id})
    return {"status": "approved", "alert_id": req.alert_id}


@app.get("/api/alerts")
async def get_alerts():
    return {"alerts": list(state.active_alerts.values())}


@app.get("/api/stations/status")
async def get_station_status():
    result = []
    for sid in range(1, 46):
        window = state.station_windows[sid]
        if window:
            latest = window[-1]
            result.append({
                "station_id":             sid,
                "anomaly_score":           latest.get("anomaly_score", 0.0),
                "cycle_time_s":            latest.get("cycle_time_s", 0.0),
                "is_sensor_poor":          sid in SENSOR_POOR_STATIONS,
                "fault_active":            latest.get("fault_active", False),
                "torque_nm_imputed":      latest.get("torque_nm_imputed"),
                "imputation_uncertainty": latest.get("imputation_uncertainty"),
                "vibration_g_imputed":     latest.get("vibration_g_imputed"),
                "vibration_uncertainty":   latest.get("vibration_uncertainty"),
                "temperature_c_imputed":   latest.get("temperature_c_imputed"),
                "temperature_uncertainty": latest.get("temperature_uncertainty"),
            })
        else:
            result.append({
                "station_id":             sid,
                "anomaly_score":           0.0,
                "cycle_time_s":            0.0,
                "is_sensor_poor":          sid in SENSOR_POOR_STATIONS,
                "fault_active":            False,
                "torque_nm_imputed":      None,
                "imputation_uncertainty": None,
                "vibration_g_imputed":     None,
                "vibration_uncertainty":   None,
                "temperature_c_imputed":   None,
                "temperature_uncertainty": None,
            })
    return {"stations": result, "vehicles_completed": state.vehicles_completed}


@app.get("/api/history/station/{station_id}")
async def get_station_history(station_id: int, n: int = 100):
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql(
        "SELECT * FROM station_events WHERE station_id=? ORDER BY timestamp DESC LIMIT ?",
        conn, params=(station_id, n)
    )
    conn.close()
    return {"station_id": station_id, "events": df.to_dict(orient="records")}


@app.get("/api/history/throughput")
async def get_throughput():
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql("""
        SELECT
            CAST(timestamp / 3600 AS INTEGER) * 3600 AS hour_ts,
            COUNT(DISTINCT vehicle_id) AS vehicles_completed,
            AVG(cycle_time_s) AS avg_cycle_time
        FROM station_events
        WHERE station_id = 45
        GROUP BY hour_ts
        ORDER BY hour_ts DESC
        LIMIT 168
    """, conn)
    conn.close()
    return {"throughput": df.to_dict(orient="records")}


@app.get("/api/roi")
async def get_roi():
    return {"roi": state.roi_stats}


@app.get("/health")
async def health():
    return {"status": "ok", "sim_running": True, "ws_clients": len(state.ws_clients)}
