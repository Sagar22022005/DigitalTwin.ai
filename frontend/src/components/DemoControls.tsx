"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { API_BASE } from "@/lib/utils";
import { Zap, Bug, RotateCcw, ChevronDown } from "lucide-react";

const STATIONS = Array.from({ length: 45 }, (_, i) => i + 1);

export default function DemoControls() {
  const [open,          setOpen]          = useState(false);
  const [bStation,      setBStation]      = useState(12);
  const [dStation,      setDStation]      = useState(7);
  const [injecting,     setInjecting]     = useState(false);
  const [lastAction,    setLastAction]    = useState<string | null>(null);

  async function inject(type: "bottleneck" | "defect", sid: number) {
    setInjecting(true);
    try {
      await fetch(`${API_BASE}/api/demo/inject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ station_id: sid, fault_type: type }),
      });
      setLastAction(`Injected ${type} @ S${sid}`);
    } finally {
      setInjecting(false);
    }
  }

  async function reset() {
    setInjecting(true);
    try {
      await fetch(`${API_BASE}/api/demo/reset`, { method: "POST" });
      setLastAction("Simulation reset");
    } finally {
      setInjecting(false);
    }
  }

  return (
    <div
      className="fixed bottom-6 right-6 z-50 rounded-2xl overflow-hidden shadow-2xl"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        minWidth: 260,
      }}
    >
      {/* Toggle header */}
      <button
        onClick={() => setOpen((p) => !p)}
        className="w-full flex items-center justify-between px-4 py-3"
        style={{ color: "var(--accent)" }}
      >
        <span className="text-xs font-bold tracking-widest">DEMO CONTROLS</span>
        <ChevronDown
          size={14}
          style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
        />
      </button>

      {open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="flex flex-col gap-3 px-4 pb-4"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          {/* Bottleneck injection */}
          <div className="flex flex-col gap-1.5 pt-3">
            <label className="text-[10px] font-semibold tracking-wider"
                   style={{ color: "var(--muted)" }}>
              INJECT BOTTLENECK
            </label>
            <div className="flex gap-2">
              <select
                value={bStation}
                onChange={(e) => setBStation(Number(e.target.value))}
                className="flex-1 rounded-lg px-2 py-1.5 text-xs"
                style={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                }}
              >
                {STATIONS.map((s) => (
                  <option key={s} value={s}>Station {s}</option>
                ))}
              </select>
              <button
                disabled={injecting}
                onClick={() => inject("bottleneck", bStation)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
                style={{
                  background: "rgba(239,68,68,0.15)",
                  color: "var(--danger)",
                  border: "1px solid rgba(239,68,68,0.4)",
                }}
              >
                <Zap size={11} /> Inject
              </button>
            </div>
          </div>

          {/* Defect injection */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-semibold tracking-wider"
                   style={{ color: "var(--muted)" }}>
              INJECT DEFECT
            </label>
            <div className="flex gap-2">
              <select
                value={dStation}
                onChange={(e) => setDStation(Number(e.target.value))}
                className="flex-1 rounded-lg px-2 py-1.5 text-xs"
                style={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                }}
              >
                {STATIONS.filter(s => s <= 43).map((s) => (
                  <option key={s} value={s}>Station {s}</option>
                ))}
              </select>
              <button
                disabled={injecting}
                onClick={() => inject("defect", dStation)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
                style={{
                  background: "rgba(245,158,11,0.15)",
                  color: "var(--warning)",
                  border: "1px solid rgba(245,158,11,0.4)",
                }}
              >
                <Bug size={11} /> Inject
              </button>
            </div>
          </div>

          {/* Reset */}
          <button
            disabled={injecting}
            onClick={reset}
            className="flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold"
            style={{
              background: "rgba(100,116,139,0.15)",
              color: "var(--muted)",
              border: "1px solid var(--border)",
            }}
          >
            <RotateCcw size={11} /> Reset Simulation
          </button>

          {lastAction && (
            <p className="text-[10px] text-center" style={{ color: "var(--success)" }}>
              ✓ {lastAction}
            </p>
          )}
        </motion.div>
      )}
    </div>
  );
}
