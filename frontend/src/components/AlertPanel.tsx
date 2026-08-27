"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, CheckCircle, XCircle, ChevronRight } from "lucide-react";
import { Alert, Intervention } from "@/types";
import { API_BASE } from "@/lib/utils";

interface Props {
  alerts: Alert[];
  onResolved: (alertId: number) => void;
}

function InterventionModal({
  alert,
  onClose,
  onApproved,
}: {
  alert: Alert;
  onClose: () => void;
  onApproved: (alertId: number) => void;
}) {
  const [approving, setApproving] = useState<string | null>(null);
  const [done, setDone]           = useState(false);

  async function approve(option: Intervention) {
    setApproving(option.id);
    try {
      await fetch(`${API_BASE}/api/interventions/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert_id: alert.id, option_id: option.id }),
      });
      setDone(true);
      setTimeout(() => { onApproved(alert.id); onClose(); }, 1200);
    } finally {
      setApproving(null);
    }
  }

  const costColor = { None: "#10b981", Low: "#10b981", Medium: "#f59e0b", High: "#ef4444" };

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <motion.div
        className="w-full max-w-lg rounded-2xl p-6 flex flex-col gap-5"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1,   y: 0 }}
        exit={{ scale: 0.9,    y: 20 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <h3 className="font-bold text-lg" style={{ color: "var(--text)" }}>
            Intervention Simulator
          </h3>
          <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
            Station {alert.station_id} — Bottleneck predicted in ~{alert.eta_minutes} min
          </p>
        </div>

        {done ? (
          <div className="flex flex-col items-center gap-3 py-8">
            <CheckCircle size={48} color="var(--success)" />
            <p className="font-semibold" style={{ color: "var(--success)" }}>
              Intervention approved — simulation updating
            </p>
          </div>
        ) : (
          <>
            {/* Comparison bar chart */}
            <div className="flex flex-col gap-3">
              {alert.interventions.map((opt) => (
                <motion.div
                  key={opt.id}
                  whileHover={{ scale: 1.02 }}
                  className="flex flex-col gap-2 p-4 rounded-xl cursor-pointer"
                  style={{
                    background: "var(--card)",
                    border: `1px solid ${approving === opt.id ? "var(--accent)" : "var(--border)"}`,
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
                      {opt.label}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs px-2 py-0.5 rounded-full"
                            style={{
                              background: `${costColor[opt.cost]}22`,
                              color: costColor[opt.cost],
                              border: `1px solid ${costColor[opt.cost]}44`,
                            }}>
                        Cost: {opt.cost}
                      </span>
                      <span className="text-sm font-bold" style={{ color: "var(--success)" }}>
                        +{opt.recovery_pct}%
                      </span>
                    </div>
                  </div>

                  {/* Recovery bar */}
                  <div className="h-2 rounded-full w-full" style={{ background: "var(--border)" }}>
                    <motion.div
                      className="h-2 rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${opt.recovery_pct}%` }}
                      transition={{ delay: 0.2, duration: 0.6 }}
                      style={{ background: "var(--success)" }}
                    />
                  </div>

                  <button
                    onClick={() => approve(opt)}
                    disabled={!!approving}
                    className="self-end flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all"
                    style={{
                      background: "rgba(0,212,255,0.12)",
                      color: "var(--accent)",
                      border: "1px solid rgba(0,212,255,0.3)",
                    }}
                  >
                    {approving === opt.id ? "Applying..." : <>Approve <ChevronRight size={12} /></>}
                  </button>
                </motion.div>
              ))}
            </div>

            <button
              onClick={onClose}
              className="text-xs self-center"
              style={{ color: "var(--muted)" }}
            >
              Dismiss
            </button>
          </>
        )}
      </motion.div>
    </motion.div>
  );
}

export default function AlertPanel({ alerts, onResolved }: Props) {
  const [modalAlert, setModalAlert] = useState<Alert | null>(null);
  const active = alerts.filter((a) => a.status === "active");

  if (active.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 rounded-xl py-12"
        style={{ background: "var(--card)", border: "1px solid var(--border)" }}
      >
        <CheckCircle size={32} color="var(--success)" />
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          No active alerts — line operating normally
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="flex flex-col gap-3">
        {active.map((alert) => (
          <motion.div
            key={alert.id}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1,  y: 0 }}
            exit={{    opacity: 0,  y: -10 }}
            className="rounded-xl p-4 glow-pulse"
            style={{
              background: "rgba(239,68,68,0.06)",
              border: "1px solid rgba(239,68,68,0.4)",
            }}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <AlertTriangle size={20} color="var(--danger)" />
                <div>
                  <p className="text-sm font-bold" style={{ color: "var(--danger)" }}>
                    Station {alert.station_id} — {alert.type === "bottleneck"
                      ? `Bottleneck in ~${alert.eta_minutes} min`
                      : "Defect Risk Detected"}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
                    Confidence: {(alert.confidence * 100).toFixed(0)}% &nbsp;·&nbsp;
                    {Object.entries(alert.contributing)
                      .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
                      .slice(0, 2)
                      .map(([k, v]) => `${k}: ${v > 0 ? "+" : ""}${v.toFixed(2)}σ`)
                      .join(" · ")}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setModalAlert(alert)}
                  className="text-xs font-semibold px-3 py-1.5 rounded-lg"
                  style={{
                    background: "rgba(0,212,255,0.12)",
                    color: "var(--accent)",
                    border: "1px solid rgba(0,212,255,0.3)",
                  }}
                >
                  Simulate →
                </button>
                <button
                  onClick={() => onResolved(alert.id)}
                  style={{ color: "var(--muted)" }}
                  className="hover:opacity-70"
                >
                  <XCircle size={16} />
                </button>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <AnimatePresence>
        {modalAlert && (
          <InterventionModal
            alert={modalAlert}
            onClose={() => setModalAlert(null)}
            onApproved={(id) => { onResolved(id); setModalAlert(null); }}
          />
        )}
      </AnimatePresence>
    </>
  );
}
