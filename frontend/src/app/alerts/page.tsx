"use client";
import { useState, useCallback } from "react";
import { Alert, WSMessage } from "@/types";
import { useWebSocket } from "@/lib/useWebSocket";
import AlertPanel from "@/components/AlertPanel";
import DemoControls from "@/components/DemoControls";
import { Bell, CheckCircle } from "lucide-react";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  const handleWS = useCallback((msg: WSMessage) => {
    if (msg.type === "init") setAlerts(msg.alerts);
    else if (msg.type === "alert")
      setAlerts((p) => [...p.filter((a) => a.id !== msg.alert.id), msg.alert]);
    else if (msg.type === "alert_resolved")
      setAlerts((p) => p.map((a) => a.id === msg.alert_id ? { ...a, status: "approved" } : a));
    else if (msg.type === "reset") setAlerts([]);
  }, []);

  useWebSocket(handleWS);

  const active   = alerts.filter((a) => a.status === "active");
  const resolved = alerts.filter((a) => a.status !== "active");

  return (
    <div className="max-w-3xl mx-auto p-6 flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--text)" }}>
          Alerts &amp; Intervention Simulator
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
          Active predictions — click Simulate to test interventions virtually before committing
        </p>
      </div>

      {/* Active alerts */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Bell size={16} color="var(--danger)" />
          <h2 className="font-semibold text-sm" style={{ color: "var(--text)" }}>
            Active ({active.length})
          </h2>
        </div>
        <AlertPanel
          alerts={alerts}
          onResolved={(id) =>
            setAlerts((p) => p.map((a) => a.id === id ? { ...a, status: "dismissed" } : a))
          }
        />
      </section>

      {/* Resolved history */}
      {resolved.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle size={16} color="var(--success)" />
            <h2 className="font-semibold text-sm" style={{ color: "var(--text)" }}>
              Resolved ({resolved.length})
            </h2>
          </div>
          <div className="flex flex-col gap-2">
            {resolved.map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between px-4 py-3 rounded-xl"
                style={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                }}
              >
                <span className="text-sm" style={{ color: "var(--muted)" }}>
                  Station {a.station_id} — {a.type}
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full capitalize"
                  style={{
                    background: a.status === "approved"
                      ? "rgba(16,185,129,0.12)"
                      : "rgba(100,116,139,0.12)",
                    color: a.status === "approved" ? "var(--success)" : "var(--muted)",
                    border: `1px solid ${a.status === "approved" ? "rgba(16,185,129,0.3)" : "var(--border)"}`,
                  }}
                >
                  {a.status}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      <DemoControls />
    </div>
  );
}
