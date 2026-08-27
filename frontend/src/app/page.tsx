"use client";
import { useState, useCallback, useEffect } from "react";
import { AnimatePresence } from "framer-motion";
import { Activity, Bell, Zap } from "lucide-react";
import { StationStatus, Alert, WSMessage } from "@/types";
import { useWebSocket } from "@/lib/useWebSocket";
import { fetchJSON, API_BASE } from "@/lib/utils";
import FactoryFloorMap from "@/components/FactoryFloorMap";
import AlertPanel from "@/components/AlertPanel";
import DemoControls from "@/components/DemoControls";

export default function LiveFloorPage() {
  const [stations, setStations] = useState<Record<number, StationStatus>>({});
  const [alerts,   setAlerts]   = useState<Alert[]>([]);
  const [vehicles, setVehicles] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);

  // Seed with HTTP poll on load, then WebSocket takes over
  useEffect(() => {
    fetchJSON<{ stations: StationStatus[] }>("/api/stations/status")
      .then(({ stations: s }) => {
        const map: Record<number, StationStatus> = {};
        s.forEach((st) => { map[st.station_id] = st; });
        setStations(map);
      })
      .catch(() => {/* backend not up yet */});

    fetchJSON<{ alerts: Alert[] }>("/api/alerts")
      .then(({ alerts: a }) => setAlerts(a))
      .catch(() => {});
  }, []);

  const handleWS = useCallback((msg: WSMessage) => {
    setWsConnected(true);
    if (msg.type === "init") {
      setAlerts(msg.alerts);
    } else if (msg.type === "station_update") {
      setStations((prev) => ({ ...prev, [msg.data.station_id]: msg.data }));
      setVehicles((v) => v + 1);
    } else if (msg.type === "alert") {
      setAlerts((prev) => [...prev.filter(a => a.id !== msg.alert.id), msg.alert]);
    } else if (msg.type === "alert_resolved") {
      setAlerts((prev) =>
        prev.map((a) => a.id === msg.alert_id ? { ...a, status: "approved" } : a)
      );
    } else if (msg.type === "reset") {
      setAlerts([]);
    }
  }, []);

  useWebSocket(handleWS);

  const activeAlerts = alerts.filter((a) => a.status === "active");
  const anomalyCount = Object.values(stations).filter((s) => (s.anomaly_score ?? 0) < -0.05).length;

  return (
    <div className="flex flex-col min-h-screen p-6 gap-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text)" }}>
            Live Factory Floor
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
            45-station vehicle assembly line · Real-time digital twin
          </p>
        </div>

        {/* KPI summary bar */}
        <div className="flex items-center gap-4">
          {[
            {
              icon: Activity,
              label: "Vehicles Today",
              value: vehicles.toLocaleString(),
              color: "var(--accent)",
            },
            {
              icon: Zap,
              label: "Anomalies",
              value: anomalyCount,
              color: anomalyCount > 0 ? "var(--danger)" : "var(--success)",
            },
            {
              icon: Bell,
              label: "Active Alerts",
              value: activeAlerts.length,
              color: activeAlerts.length > 0 ? "var(--danger)" : "var(--success)",
            },
          ].map(({ icon: Icon, label, value, color }) => (
            <div
              key={label}
              className="flex flex-col items-center px-5 py-3 rounded-xl"
              style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            >
              <Icon size={14} color={color as string} />
              <span className="text-xl font-bold mt-1" style={{ color: color as string }}>
                {value}
              </span>
              <span className="text-[10px]" style={{ color: "var(--muted)" }}>{label}</span>
            </div>
          ))}

          {/* WS status */}
          <div className="flex items-center gap-2 text-xs"
               style={{ color: wsConnected ? "var(--success)" : "var(--warning)" }}>
            <span className="relative flex h-2 w-2">
              <span className={`${wsConnected ? "animate-ping" : ""} absolute inline-flex h-full w-full rounded-full opacity-75`}
                    style={{ background: wsConnected ? "var(--success)" : "var(--warning)" }} />
              <span className="relative inline-flex rounded-full h-2 w-2"
                    style={{ background: wsConnected ? "var(--success)" : "var(--warning)" }} />
            </span>
            {wsConnected ? "Connected" : "Connecting…"}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 text-xs" style={{ color: "var(--muted)" }}>
        {[
          { color: "#10b981", label: "Normal" },
          { color: "#f59e0b", label: "Watch (borderline)" },
          { color: "#ef4444", label: "Anomaly / Fault" },
          { color: "var(--muted)", opacity: 0.6, label: "· Sensor-poor (GP imputed)" },
        ].map(({ color, label, opacity }) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: color, opacity }} />
            {label}
          </div>
        ))}
      </div>

      {/* Main content — 2 columns */}
      <div className="flex gap-6 flex-1">
        {/* Factory map — left 70% */}
        <div className="flex-1 min-w-0">
          <FactoryFloorMap stations={stations} />
        </div>

        {/* Alert panel — right 30% */}
        <div className="w-80 shrink-0 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Bell size={14} color="var(--danger)" />
            <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
              Active Alerts
            </h2>
            {activeAlerts.length > 0 && (
              <span
                className="text-xs px-2 py-0.5 rounded-full font-bold"
                style={{ background: "var(--danger)", color: "#fff" }}
              >
                {activeAlerts.length}
              </span>
            )}
          </div>
          <AlertPanel
            alerts={alerts}
            onResolved={(id) =>
              setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, status: "dismissed" } : a))
            }
          />
        </div>
      </div>

      <DemoControls />
    </div>
  );
}
