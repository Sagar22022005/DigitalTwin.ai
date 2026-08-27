// Central type definitions shared across frontend and backend API responses

export interface StationStatus {
  station_id: number;
  zone: "body" | "paint" | "final";
  anomaly_score: number;       // negative = anomaly, 0 = normal (Isolation Forest scale)
  cycle_time_s: number;
  torque_nm: number | null;
  vibration_g: number | null;
  temperature_c: number | null;
  is_sensor_poor: boolean;
  fault_active: boolean;
  torque_nm_imputed?: number | null;
  imputation_uncertainty?: number | null;
}

export interface Alert {
  id: number;
  type: "bottleneck" | "defect";
  station_id: number;
  confidence: number;
  eta_minutes: number;
  status: "active" | "approved" | "dismissed";
  created_at: number;
  contributing: Record<string, number>;
  interventions: Intervention[];
}

export interface Intervention {
  id: string;
  label: string;
  recovery_pct: number;
  cost: "None" | "Low" | "Medium" | "High";
}

export interface ThroughputPoint {
  hour_ts: number;
  vehicles_completed: number;
  avg_cycle_time: number;
}

export interface ROIStats {
  throughput_recovered_pct: number;
  defect_cost_avoided_inr: number;
  interventions_approved: number;
  false_alerts_dismissed: number;
}

// WebSocket message types
export type WSMessage =
  | { type: "init";           alerts: Alert[] }
  | { type: "station_update"; data: StationStatus }
  | { type: "alert";          alert: Alert }
  | { type: "alert_resolved"; alert_id: number; option: string }
  | { type: "reset" };
