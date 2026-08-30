# AI AssemblyTwin

> **A real-time AI-powered digital twin for vehicle assembly lines that predicts bottlenecks, detects anomalies, and traces potential defects before they impact production.**

**Submission for the Accenture Innovation Challenge 2026 — Problem Statement: DigitalTwin.ai**

---

## 📌 Project Overview

**AI AssemblyTwin** is a real-time digital twin of a **45-station vehicle assembly line**. It combines discrete-event simulation, real-time data processing, and machine learning to help manufacturing teams identify production risks early and make informed operational decisions.

The platform focuses on three key capabilities:

- **Predicting bottlenecks** before they significantly affect production.
- **Detecting and tracing defects** to their potential upstream root causes.
- **Simulating interventions virtually** before a supervisor approves an action.

The system also supports different stakeholder needs through dedicated dashboards for floor supervisors, plant managers, and leadership.

---

## 🚀 Key Features

### 1. Real-Time Digital Twin
A **SimPy-based simulation** represents the behavior of a 45-station vehicle assembly line and provides a live view of production activity.

### 2. AI-Powered Bottleneck Prediction
An **LSTM model built with PyTorch** learns temporal patterns and sequence drifts across stations to predict potential bottlenecks.

### 3. Anomaly Detection
An **Isolation Forest** detects unusual production behavior, such as changes in station cycle times, without requiring perfectly labelled historical defect data.

### 4. Defect Risk & Root-Cause Tracing
A **Random Forest defect-risk model** uses lag features to capture upstream relationships between stations. For example, a torque drift at an earlier station can be associated with a quality failure detected at a later station.

### 5. Sensor Data Imputation
For stations with limited sensor coverage, **Gaussian Process Regression** estimates missing torque/vibration information while providing uncertainty estimates.

### 6. Virtual Intervention Simulation
The system uses **read-only OPC-UA data collection** and does not directly modify PLCs. Potential interventions are first evaluated virtually through the Intervention Simulator.

### 7. Multi-Stakeholder Dashboards
Different views provide relevant information for:
- **Floor Supervisors** — live production monitoring and alerts.
- **Plant Managers** — production analytics and maintenance insights.
- **Leadership** — ROI, payback analysis, and sensor-upgrade priorities.

---

## 🏗️ Architecture

AI AssemblyTwin combines a Python-based backend, real-time communication, machine-learning models, and an interactive Next.js frontend.

### Core Architecture

1. **Simulation Layer** — SimPy models the 45-station assembly line.
2. **Data & API Layer** — FastAPI handles backend services and WebSocket-based real-time communication.
3. **AI/ML Layer** — Isolation Forest, LSTM, Random Forest, and Gaussian Process models support anomaly detection, bottleneck prediction, defect analysis, and sensor imputation.
4. **Intervention Layer** — Potential operational actions are tested virtually before approval.
5. **Visualization Layer** — Next.js and React provide interactive dashboards for different stakeholders.

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| **Simulation** | `SimPy` | Discrete-event simulation of the assembly line |
| **Backend / API** | `FastAPI` | Backend services and real-time APIs |
| **Real-Time Communication** | `WebSockets` | Low-latency streaming of data and predictions |
| **Frontend** | `Next.js 14` + `React` | Interactive dashboards and visualizations |
| **Anomaly Detection** | `Isolation Forest` | Detects unusual production behavior |
| **Bottleneck Prediction** | `PyTorch` (LSTM) | Learns temporal patterns and predicts bottlenecks |
| **Defect Risk Analysis** | `Random Forest` | Identifies potential defect risks and upstream causes |
| **Sensor Imputation** | `Gaussian Process Regression` | Estimates missing sensor values with uncertainty |
| **Industrial Data** | `OPC-UA` | Read-only industrial data collection |

---

## ⚡ Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 20+**

### Installation

1. Clone this repository.
2. Run `run.bat` on Windows, or start the services manually.

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev -- -p 3000
```

3. Open the application at:

```text
https://digital-twin-ai-three.vercel.app/
```

---

## 🎮 How to Demo

The application includes a floating **Demo Controls** panel in the bottom-right corner.

### Bottleneck Scenario

1. Open **Live Floor**.
2. Use **Demo Controls** to inject a bottleneck at **Station 12**.
3. Wait approximately **30–60 seconds** for the cycle-time drift to develop.
4. The **Isolation Forest** detects the anomaly.
5. The **LSTM model** predicts the bottleneck and generates an alert.
6. Select **Simulate →** to view virtual intervention options and approve an intervention.

### Defect Scenario

1. Use **Demo Controls** to inject a defect at **Station 7**.
2. Open the **Defect Trace** page.
3. Observe how the **Random Forest** identifies Station 7 as a potential root cause of a defect that is detected later at **Station 44**.

---

## 📊 Stakeholder Views

### Floor Supervisor — Live Floor
Provides an animated real-time view of all **45 stations**, along with immediate production alerts.

### Plant Manager — Analytics
Provides:
- 7-day throughput trends
- Recurring bottleneck analysis
- AI-recommended maintenance scheduling

### Leadership — Analytics
Provides:
- ROI calculator
- Payback-period analysis
- Sensor coverage analysis
- Recommendations on which legacy stations should be upgraded

---

## 💡 Why AI AssemblyTwin?

Traditional production monitoring can identify problems after they occur. AI AssemblyTwin is designed to move from **reactive monitoring to predictive decision-making** by combining a digital twin with AI models.

This enables manufacturing stakeholders to:

**Monitor → Detect → Predict → Simulate → Decide**

The goal is to help teams identify production risks earlier, understand potential root causes, and evaluate interventions before taking action on the real production line.

---

## 👥 Team

- **Jayanth**
- **Abhinav**
- **Vidya Sagar**

---

## 🏆 Challenge

**Accenture Innovation Challenge 2026**

**Problem Statement:** DigitalTwin.ai

---

## 📄 License

This project was developed as part of the **Accenture Innovation Challenge 2026**.
