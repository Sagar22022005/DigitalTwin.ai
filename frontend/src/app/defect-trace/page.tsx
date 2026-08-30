"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { GitBranch, AlertTriangle, CheckCircle } from "lucide-react";

const STATIONS = Array.from({ length: 45 }, (_, i) => i + 1);

// Mock vehicle journey — in real app fetch from /api/history/vehicle/{id}
function generateJourney(defectOrigin: number) {
  return STATIONS.map((sid) => {
    let risk = 0.02 + Math.random() * 0.04;
    if (sid === defectOrigin)             risk = 0.72 + Math.random() * 0.15;
    else if (sid > defectOrigin && sid < 44) risk = Math.min(0.6, risk + (sid - defectOrigin) * 0.02);
    else if (sid === 44)                  risk = 0.85;
    return { station_id: sid, defect_prob: risk };
  });
}

export default function DefectTracePage() {
  const [vehicleId,     setVehicleId]     = useState(42);
  const [defectOrigin,  setDefectOrigin]  = useState(7);
  const [journey,       setJourney]       = useState(() => generateJourney(7));

  function load() {
    setJourney(generateJourney(defectOrigin));
  }

  const riskColor = (p: number) =>
    p > 0.6 ? "#ef4444" : p > 0.25 ? "#f59e0b" : "#10b981";

  const maxRisk   = Math.max(...journey.map((j) => j.defect_prob));
  const originStn = journey.find((j) => j.station_id === defectOrigin) ?? journey[0];

  return (
    <div className="max-w-5xl mx-auto p-6 flex flex-col gap-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--text)" }}>
          Defect Trace
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
          Track how a defect risk propagates through the assembly line —
          from origin upstream to detection at QC (Station 44)
        </p>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs" style={{ color: "var(--muted)" }}>Vehicle ID</label>
          <input
            type="number"
            value={vehicleId}
            onChange={(e) => setVehicleId(Number(e.target.value))}
            className="w-24 rounded-lg px-3 py-1.5 text-sm"
            style={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              color: "var(--text)",
            }}
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs" style={{ color: "var(--muted)" }}>Defect origin</label>
          <select
            value={defectOrigin}
            onChange={(e) => setDefectOrigin(Number(e.target.value))}
            className="rounded-lg px-3 py-1.5 text-sm"
            style={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              color: "var(--text)",
            }}
          >
            {STATIONS.filter((s) => s < 44).map((s) => (
              <option key={s} value={s}>Station {s}</option>
            ))}
          </select>
        </div>
        <button
          onClick={load}
          className="px-4 py-1.5 rounded-lg text-sm font-semibold"
          style={{
            background: "rgba(0,212,255,0.12)",
            color: "var(--accent)",
            border: "1px solid rgba(0,212,255,0.3)",
          }}
        >
          Load Vehicle
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          {
            label: "Defect Origin",
            value: `Station ${originStn.station_id}`,
            icon: AlertTriangle,
            color: "var(--danger)",
          },
          {
            label: "Max Risk Score",
            value: `${(maxRisk * 100).toFixed(0)}%`,
            icon: AlertTriangle,
            color: "var(--warning)",
          },
          {
            label: "Detection Point",
            value: "Station 44 (QC)",
            icon: CheckCircle,
            color: "var(--success)",
          },
        ].map(({ label, value, icon: Icon, color }) => (
          <div
            key={label}
            className="rounded-xl p-4 flex items-center gap-4"
            style={{ background: "var(--card)", border: "1px solid var(--border)" }}
          >
            <div className="p-2 rounded-lg" style={{ background: `${color}18` }}>
              <Icon size={18} color={color} />
            </div>
            <div>
              <p className="text-xs" style={{ color: "var(--muted)" }}>{label}</p>
              <p className="text-sm font-bold mt-0.5" style={{ color }}>{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Timeline */}
      <div
        className="rounded-2xl p-6"
        style={{ background: "var(--card)", border: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2 mb-6">
          <GitBranch size={16} color="var(--accent)" />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            Vehicle #{vehicleId} — Risk Propagation Timeline
          </h2>
        </div>

        {/* Station timeline — scrollable */}
        <div className="overflow-x-auto pb-4">
          <div className="flex items-end gap-2 min-w-max">
            {journey.map((j, idx) => {
              const color   = riskColor(j.defect_prob);
              const isOrigin = j.station_id === originStn.station_id;
              const isQC     = j.station_id === 44;
              const barH     = Math.max(8, j.defect_prob * 120);

              return (
                <div key={j.station_id} className="flex flex-col items-center gap-1">
                  {/* Bar */}
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: barH }}
                    transition={{ delay: idx * 0.015, duration: 0.4 }}
                    className="w-7 rounded-t-lg relative"
                    style={{ background: `${color}cc`, minHeight: 8 }}
                    title={`S${j.station_id}: ${(j.defect_prob * 100).toFixed(0)}%`}
                  >
                    {(isOrigin || isQC) && (
                      <div
                        className="absolute -top-5 left-1/2 -translate-x-1/2 text-[8px] font-bold whitespace-nowrap"
                        style={{ color }}
                      >
                        {isOrigin ? "ORIGIN" : "QC"}
                      </div>
                    )}
                  </motion.div>

                  {/* Station label */}
                  <span
                    className="text-[8px] font-mono rotate-45 origin-left ml-2"
                    style={{ color: isOrigin || isQC ? color : "var(--muted)" }}
                  >
                    S{j.station_id}
                  </span>
                </div>
              );
            })}
          </div>

          {/* X-axis labels */}
          <div className="flex items-center gap-2 mt-6 ml-1 text-[9px]"
               style={{ color: "var(--muted)" }}>
            <span>Body Construction →</span>
            <span style={{ marginLeft: "15.5rem" }}>Paint Shop →</span>
            <span style={{ marginLeft: "10rem" }}>Final Assembly → QC</span>
          </div>
        </div>

        {/* Legend */}
        <div className="flex gap-6 mt-4 text-xs" style={{ color: "var(--muted)" }}>
          {[
            { color: "#10b981", label: "Low risk (< 25%)" },
            { color: "#f59e0b", label: "Medium risk (25–60%)" },
            { color: "#ef4444", label: "High risk (> 60%)" },
          ].map(({ color, label }) => (
            <div key={label} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* Explanation */}
      <div
        className="rounded-xl px-5 py-4 text-sm"
        style={{
          background: "rgba(0,212,255,0.06)",
          border: "1px solid rgba(0,212,255,0.2)",
          color: "var(--muted)",
        }}
      >
        <span style={{ color: "var(--accent)", fontWeight: 600 }}>How this works: </span>
        The defect predictor uses lag features — torque deviation at Station {defectOrigin} becomes a
        feature for all downstream stations. The model learns that a ±12Nm torque offset at
        Station {defectOrigin} correlates with an 85% defect probability at QC (Station 44),
        typically surfacing after {44 - defectOrigin} downstream stations.
      </div>
    </div>
  );
}
