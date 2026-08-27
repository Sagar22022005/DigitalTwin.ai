# AI AssemblyTwin

> **Live digital twin of a vehicle assembly line — predicts bottlenecks and defects before they happen.**
> Submission for **Accenture Innovation Challenge 2026** (Problem Statement: DigitalTwin.ai).

## 🚀 Quick Start (Local Run)

Requires Python 3.11+ and Node.js 20+.

1. Clone this repository.
2. Run `run.bat` (Windows) or start services manually:

**Terminal 1 (Backend):**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm install
npm run dev -- -p 3000
```

3. Open **[http://localhost:3000](http://localhost:3000)**.

---

## 🏗️ Architecture

AI AssemblyTwin runs a real-time SimPy simulation of a 45-station vehicle assembly line. It handles the constraints given in the Round 2 brief natively:

1. **Uneven Sensor Coverage**: Legacy stations without torque/vibration sensors are imputed in real-time using **Gaussian Process Regression**, complete with uncertainty bounds displayed in the UI.
2. **Multi-causal Defect Origins**: Our **Random Forest** defect risk model uses lag features to capture upstream causality (e.g., a torque drift at Station 7 surfacing as a QC failure at Station 44).
3. **No Direct PLC Modifications**: The architecture assumes read-only OPC-UA data collection. Interventions are modelled virtually in our **Intervention Simulator** before a supervisor approves them.
4. **Multi-stakeholder Views**: A single backend serves three distinct dashboards via Next.js and FastAPI.

### Tech Stack
| Component | Technology | Why we chose it |
|---|---|---|
| **Simulation** | `SimPy` | Python-native discrete-event simulation. Lightweight but realistic. |
| **Real-time Pipeline** | `FastAPI` + `WebSockets` | Async Python for low-latency streaming inference and UI updates. |
| **Frontend** | `Next.js 14` + `React` | High-fidelity interactive UI with Framer Motion animations. |
| **Anomaly Model** | `Isolation Forest` | Unsupervised. Doesn't require perfectly labelled historical defect data. |
| **Bottleneck Model**| `PyTorch` (LSTM) | Learns non-linear temporal sequence drifts across all stations simultaneously. |
| **Sensor Imputation** | `Gaussian Process` | Crucial: provides explicit uncertainty estimates for sensor-poor stations. |

---

## 🎮 How to Demo

The app has a floating **Demo Controls** panel in the bottom right of the screen.

1. **Bottleneck Scenario**:
   - Go to **Live Floor**.
   - In Demo Controls, inject a Bottleneck at Station 12.
   - Wait ~30-60 seconds. The Isolation Forest will catch the cycle time drift.
   - The LSTM will predict a bottleneck. An alert pops up.
   - Click "Simulate →" to see virtual intervention options and approve one.

2. **Defect Scenario**:
   - Inject a Defect at Station 7.
   - Go to the **Defect Trace** page.
   - See how the Random Forest identifies Station 7 as the root cause of a defect that won't surface until Station 44.

---

## 📊 Stakeholder Views

1. **Floor Supervisor (Live Floor)**: Animated, real-time map of all 45 stations. Instant alerts.
2. **Plant Manager (Analytics)**: 7-day throughput trends, recurring bottleneck analysis, and AI-recommended maintenance scheduling.
3. **Leadership (Analytics)**: ROI calculator, payback period, and a sensor coverage map showing which legacy stations to upgrade next.

---

## 👥 Team
- [Your Name 1]
- [Your Name 2]
- [Your Name ...]
