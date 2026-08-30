"use client";
import { motion } from "framer-motion";
import { X, Wifi, WifiOff } from "lucide-react";
import { StationStatus } from "@/types";
import { stationColor } from "@/lib/utils";

interface Props {
  station: StationStatus;
  onClose: () => void;
}

function MetricRow({
  label, value, unit, uncertain,
}: {
  label: string;
  value: number | null | undefined;
  unit: string;
  uncertain?: number | null;
}) {
  return (
    <div className="flex justify-between items-center py-2"
         style={{ borderBottom: "1px solid var(--border)" }}>
      <span className="text-xs" style={{ color: "var(--muted)" }}>{label}</span>
      <div className="text-right">
        {value != null ? (
          <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            {value.toFixed(2)} {unit}
          </span>
        ) : (
          <span className="text-xs italic" style={{ color: "var(--muted)" }}>no sensor</span>
        )}
        {uncertain != null && uncertain > 0 && (
          <div className="text-[10px]" style={{ color: "var(--warning)" }}>
            ± {uncertain.toFixed(2)} (GP est.)
          </div>
        )}
      </div>
    </div>
  );
}

export default function StationDrawer({ station, onClose }: Props) {
  const color = stationColor(station);

  return (
    <motion.div
      initial={{ x: "100%", opacity: 0 }}
      animate={{ x: 0,      opacity: 1 }}
      exit={{    x: "100%", opacity: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="fixed right-0 top-16 bottom-0 w-80 z-40 overflow-y-auto"
      style={{
        background: "var(--surface)",
        borderLeft: "1px solid var(--border)",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4"
           style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full" style={{ background: color }} />
          <div>
            <h3 className="font-bold text-sm" style={{ color: "var(--text)" }}>
              Station {station.station_id.toString().padStart(2, "0")}
            </h3>
            <p className="text-xs capitalize" style={{ color: "var(--muted)" }}>
              {station.zone} zone
            </p>
          </div>
        </div>
        <button onClick={onClose} style={{ color: "var(--muted)" }}
                className="hover:opacity-70 transition-opacity">
          <X size={18} />
        </button>
      </div>

      <div className="p-4 flex flex-col gap-4">
        {/* Sensor coverage badge */}
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
          style={{
            background: station.is_sensor_poor
              ? "rgba(245,158,11,0.1)"
              : "rgba(16,185,129,0.1)",
            border: `1px solid ${station.is_sensor_poor ? "var(--warning)" : "var(--success)"}`,
            color: station.is_sensor_poor ? "var(--warning)" : "var(--success)",
          }}
        >
          {station.is_sensor_poor ? <WifiOff size={12} /> : <Wifi size={12} />}
          {station.is_sensor_poor
            ? "Legacy station — GP imputation active"
            : "Full telemetry coverage"}
        </div>

        {/* Anomaly score */}
        <div>
          <p className="text-xs mb-2" style={{ color: "var(--muted)" }}>Anomaly Score</p>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full" style={{ background: "var(--border)" }}>
              <div
                className="h-2 rounded-full transition-all"
                style={{
                  width: `${Math.min(100, Math.max(0, (-(station.anomaly_score ?? 0)) * 200))}%`,
                  background: color,
                }}
              />
            </div>
            <span className="text-xs font-mono" style={{ color }}>
              {(station.anomaly_score ?? 0).toFixed(3)}
            </span>
          </div>
        </div>

        {/* Metrics */}
        <div>
          <p className="text-xs mb-2 font-semibold" style={{ color: "var(--muted)" }}>
            TELEMETRY
          </p>
          <MetricRow label="Cycle Time"   value={station.cycle_time_s}   unit="s" />
          <MetricRow
            label="Torque"
            value={station.torque_nm ?? station.torque_nm_imputed}
            unit="Nm"
            uncertain={station.is_sensor_poor ? station.imputation_uncertainty : null}
          />
          <MetricRow
            label="Vibration"
            value={station.vibration_g ?? station.vibration_g_imputed}
            unit="g"
            uncertain={station.is_sensor_poor ? station.vibration_uncertainty : null}
          />
          <MetricRow
            label="Temperature"
            value={station.temperature_c ?? station.temperature_c_imputed}
            unit="°C"
            uncertain={station.is_sensor_poor ? station.temperature_uncertainty : null}
          />
        </div>

        {/* Fault status */}
        {station.fault_active && (
          <div
            className="px-3 py-2 rounded-lg text-xs font-semibold glow-pulse"
            style={{
              background: "rgba(239,68,68,0.12)",
              border: "1px solid var(--danger)",
              color: "var(--danger)",
            }}
          >
            ⚠ ACTIVE FAULT DETECTED
          </div>
        )}
      </div>
    </motion.div>
  );
}
