"use client";
import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { StationStatus } from "@/types";
import { stationColor, stationLabel } from "@/lib/utils";
import StationDrawer from "./StationDrawer";

/* Layout: 3 zones in rows, 15-13-17 stations each */
const ZONE_LAYOUT = [
  { zone: "body",  label: "ZONE A — Body Construction", ids: Array.from({ length: 15 }, (_, i) => i + 1) },
  { zone: "paint", label: "ZONE B — Paint Shop",        ids: Array.from({ length: 13 }, (_, i) => i + 16) },
  { zone: "final", label: "ZONE C — Final Assembly",    ids: Array.from({ length: 17 }, (_, i) => i + 29) },
];

const ZONE_COLORS: Record<string, string> = {
  body:  "rgba(0,212,255,0.06)",
  paint: "rgba(124,58,237,0.06)",
  final: "rgba(16,185,129,0.06)",
};

interface Props {
  stations: Record<number, StationStatus>;
}

export default function FactoryFloorMap({ stations }: Props) {
  const [selected, setSelected] = useState<number | null>(null);

  const handleClick = useCallback((id: number) => {
    setSelected((prev) => (prev === id ? null : id));
  }, []);

  return (
    <div className="flex flex-col gap-4 w-full">
      {ZONE_LAYOUT.map(({ zone, label, ids }) => (
        <div
          key={zone}
          className="rounded-xl p-4"
          style={{
            background: ZONE_COLORS[zone],
            border: "1px solid var(--border)",
          }}
        >
          {/* Zone header */}
          <div className="flex items-center gap-3 mb-4">
            <div
              className="h-px flex-1"
              style={{ background: "var(--border)" }}
            />
            <span className="text-xs font-semibold tracking-widest"
                  style={{ color: "var(--muted)" }}>
              {label}
            </span>
            <div className="h-px flex-1" style={{ background: "var(--border)" }} />
          </div>

          {/* Station grid */}
          <div className="flex flex-wrap gap-3 justify-center">
            {ids.map((sid) => {
              const st = stations[sid];
              const color = st ? stationColor(st) : "#334155";
              const lbl   = st ? stationLabel(st)  : "—";
              const isRed    = color === "#ef4444";
              const isAmber  = color === "#f59e0b";
              const isSelected = selected === sid;

              return (
                <motion.button
                  key={sid}
                  onClick={() => handleClick(sid)}
                  whileHover={{ scale: 1.06, y: -2 }}
                  whileTap={{ scale: 0.96 }}
                  className={`relative flex flex-col items-center justify-center rounded-xl cursor-pointer transition-all
                    ${isRed   ? "glow-pulse"  : ""}
                    ${isAmber ? "glow-amber"  : ""}
                  `}
                  style={{
                    width: 76,
                    height: 72,
                    background: isSelected
                      ? `${color}22`
                      : "var(--card)",
                    border: `2px solid ${isSelected ? color : isRed ? `${color}88` : "var(--border)"}`,
                  }}
                >
                  {/* Status dot */}
                  <div
                    className="absolute top-2 right-2 w-2 h-2 rounded-full"
                    style={{ background: color }}
                  />
                  {/* Sensor-poor indicator */}
                  {st?.is_sensor_poor && (
                    <div
                      className="absolute top-2 left-2 w-1.5 h-1.5 rounded-full"
                      style={{ background: "var(--muted)", opacity: 0.6 }}
                      title="Sensor-poor station"
                    />
                  )}

                  {/* Station ID */}
                  <span className="text-xs font-bold" style={{ color: "var(--muted)" }}>
                    S{sid.toString().padStart(2, "0")}
                  </span>

                  {/* Cycle time */}
                  <span className="text-base font-bold mt-0.5" style={{ color }}>
                    {st ? `${st.cycle_time_s.toFixed(0)}s` : "—"}
                  </span>

                  {/* Status label */}
                  <span className="text-[9px] font-semibold tracking-wider mt-0.5"
                        style={{ color }}>
                    {lbl}
                  </span>
                </motion.button>
              );
            })}
          </div>

          {/* Flow arrows between zones */}
        </div>
      ))}

      {/* Vehicle flow SVG connector */}
      <svg height="0" className="absolute">
        <defs>
          <marker id="arrow" markerWidth="6" markerHeight="6"
                  refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="var(--border)" />
          </marker>
        </defs>
      </svg>

      {/* Station detail drawer */}
      <AnimatePresence>
        {selected !== null && stations[selected] && (
          <StationDrawer
            station={stations[selected]}
            onClose={() => setSelected(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
