"use client";
import { useEffect, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { fetchJSON, formatINR } from "@/lib/utils";
import { ThroughputPoint, ROIStats } from "@/types";
import { TrendingUp, DollarSign, ShieldCheck, Users } from "lucide-react";

const TABS = ["Floor Supervisor", "Plant Manager", "Leadership"] as const;
type Tab = typeof TABS[number];

// ── Shared card ──────────────────────────────────────────────────────────────
function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl p-5 ${className}`}
         style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
      {children}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, sub, color }:
  { icon: React.ElementType; label: string; value: string; sub?: string; color: string }) {
  return (
    <Card>
      <div className="flex items-center gap-3 mb-3">
        <div className="p-2 rounded-lg" style={{ background: `${color}18` }}>
          <Icon size={18} color={color} />
        </div>
        <span className="text-xs" style={{ color: "var(--muted)" }}>{label}</span>
      </div>
      <p className="text-2xl font-bold" style={{ color }}>{value}</p>
      {sub && <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{sub}</p>}
    </Card>
  );
}

// ── Tooltip ──────────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg px-3 py-2 text-xs"
         style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text)" }}>
      <p style={{ color: "var(--muted)" }}>{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
        </p>
      ))}
    </div>
  );
};

// ── Mock recurring bottleneck data ────────────────────────────────────────────
const BOTTLENECK_DATA = [
  { station: "S12", count: 8 }, { station: "S07", count: 6 },
  { station: "S23", count: 5 }, { station: "S34", count: 4 },
  { station: "S19", count: 3 }, { station: "S41", count: 2 },
];

// ── Tab content ──────────────────────────────────────────────────────────────
function SupervisorTab() {
  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm" style={{ color: "var(--muted)" }}>
        Real-time shift summary and active station status — open Live Floor for the interactive map.
      </p>
      <div className="grid grid-cols-3 gap-4">
        <StatCard icon={TrendingUp}  label="Throughput (this shift)" value="312 vehicles" color="var(--accent)" />
        <StatCard icon={ShieldCheck} label="Alerts resolved"         value="3"            color="var(--success)" />
        <StatCard icon={Users}       label="Active operators"         value="6 / 8"        color="var(--warning)" />
      </div>
      <Card>
        <p className="text-xs font-semibold mb-4" style={{ color: "var(--muted)" }}>
          CURRENT SHIFT — STATION STATUS
        </p>
        <div className="grid grid-cols-9 gap-2">
          {Array.from({ length: 45 }, (_, i) => {
            const colours = ["#10b981","#10b981","#10b981","#f59e0b","#10b981",
                             "#10b981","#10b981","#ef4444","#10b981","#10b981"];
            const c = colours[i % colours.length];
            return (
              <div key={i}
                className="flex items-center justify-center rounded-lg text-[9px] font-bold"
                style={{ background: `${c}18`, border: `1px solid ${c}44`, color: c, height: 32 }}>
                S{(i+1).toString().padStart(2,"0")}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

function ManagerTab({ throughput }: { throughput: ThroughputPoint[] }) {
  const chartData = throughput.slice(0, 24).reverse().map((t, i) => ({
    hour:     `H-${24 - i}`,
    vehicles: t.vehicles_completed,
    cycle:    t.avg_cycle_time,
  }));

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-6">
        {/* Throughput */}
        <Card>
          <p className="text-xs font-semibold mb-4" style={{ color: "var(--muted)" }}>
            VEHICLES COMPLETED / HOUR (LAST 24H)
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="hour" tick={{ fill: "var(--muted)", fontSize: 10 }} />
              <YAxis tick={{ fill: "var(--muted)", fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Line type="monotone" dataKey="vehicles" stroke="var(--accent)"
                    strokeWidth={2} dot={false} name="Vehicles" />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* Recurring bottlenecks */}
        <Card>
          <p className="text-xs font-semibold mb-4" style={{ color: "var(--muted)" }}>
            RECURRING BOTTLENECK STATIONS (LAST 7 DAYS)
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={BOTTLENECK_DATA} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" tick={{ fill: "var(--muted)", fontSize: 10 }} />
              <YAxis dataKey="station" type="category" tick={{ fill: "var(--muted)", fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" name="Incidents" radius={[0,4,4,0]}>
                {BOTTLENECK_DATA.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? "var(--danger)" : "var(--accent)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Maintenance schedule */}
      <Card>
        <p className="text-xs font-semibold mb-4" style={{ color: "var(--muted)" }}>
          AI-RECOMMENDED MAINTENANCE ACTIONS
        </p>
        <div className="flex flex-col gap-2">
          {[
            { station: "S12", action: "Tooling inspection — cycle time drift +18% over 3 days", priority: "HIGH" },
            { station: "S07", action: "Torque calibration — variance spike detected 2 shifts ago", priority: "MED" },
            { station: "S23", action: "Sensor installation recommended — currently sensor-poor", priority: "LOW" },
          ].map(({ station, action, priority }) => {
            const pc = priority === "HIGH" ? "var(--danger)" : priority === "MED" ? "var(--warning)" : "var(--success)";
            return (
              <div key={station}
                className="flex items-center gap-4 px-4 py-3 rounded-lg"
                style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                <span className="text-xs font-mono font-bold" style={{ color: "var(--accent)" }}>
                  {station}
                </span>
                <span className="text-xs flex-1" style={{ color: "var(--text)" }}>{action}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                      style={{ background: `${pc}18`, color: pc, border: `1px solid ${pc}44` }}>
                  {priority}
                </span>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

function LeadershipTab({ roi }: { roi: ROIStats | null }) {
  const [payback, setPayback] = useState(1);  // months
  const monthlySaving = 1_80_000 + (roi?.defect_cost_avoided_inr ?? 0) / 12;
  const investment    = 45_00_000;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-4 gap-4">
        <StatCard icon={TrendingUp}  label="Throughput Recovered"
                  value={`${(roi?.throughput_recovered_pct ?? 0).toFixed(1)}%`}
                  sub="vs baseline"   color="var(--accent)" />
        <StatCard icon={DollarSign}  label="Defect Cost Avoided"
                  value={formatINR(roi?.defect_cost_avoided_inr ?? 0)}
                  sub="this session"  color="var(--success)" />
        <StatCard icon={ShieldCheck} label="Interventions Approved"
                  value={String(roi?.interventions_approved ?? 0)}
                  color="var(--success)" />
        <StatCard icon={Users}       label="Alerts Dismissed"
                  value={String(roi?.false_alerts_dismissed ?? 0)}
                  sub="false positives" color="var(--warning)" />
      </div>

      {/* Payback calculator */}
      <Card>
        <p className="text-xs font-semibold mb-4" style={{ color: "var(--muted)" }}>
          PAYBACK PERIOD CALCULATOR
        </p>
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-4">
            <span className="text-xs w-32" style={{ color: "var(--muted)" }}>
              Deployment horizon: {payback} month{payback > 1 ? "s" : ""}
            </span>
            <input type="range" min={1} max={24} value={payback}
                   onChange={(e) => setPayback(Number(e.target.value))}
                   className="flex-1 accent-[var(--accent)]" />
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            {[
              { label: "Investment",  value: formatINR(investment),                  color: "var(--danger)" },
              { label: "Savings",     value: formatINR(monthlySaving * payback),      color: "var(--success)" },
              { label: "Net ROI",     value: formatINR(monthlySaving * payback - investment),
                color: monthlySaving * payback > investment ? "var(--success)" : "var(--warning)" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-lg p-4"
                   style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                <p className="text-2xl font-bold" style={{ color }}>{value}</p>
                <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{label}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-center" style={{ color: "var(--muted)" }}>
            Breakeven at ~{Math.ceil(investment / monthlySaving)} months
          </p>
        </div>
      </Card>

      {/* Sensor coverage map */}
      <Card>
        <p className="text-xs font-semibold mb-4" style={{ color: "var(--muted)" }}>
          SENSOR COVERAGE — INVESTMENT ROADMAP
        </p>
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 45 }, (_, i) => {
            const sid = i + 1;
            const poor = [5,11,19,23,31,37,42].includes(sid);
            return (
              <div key={sid}
                className="flex items-center justify-center rounded-lg text-[9px] font-bold"
                style={{
                  width: 44, height: 36,
                  background: poor ? "rgba(245,158,11,0.12)" : "rgba(16,185,129,0.12)",
                  border: `1px solid ${poor ? "rgba(245,158,11,0.4)" : "rgba(16,185,129,0.3)"}`,
                  color: poor ? "var(--warning)" : "var(--success)",
                }}>
                S{sid.toString().padStart(2,"0")}
              </div>
            );
          })}
        </div>
        <div className="flex gap-6 mt-4 text-xs" style={{ color: "var(--muted)" }}>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--success)" }} />
            Fully instrumented (38 stations)
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--warning)" }} />
            Sensor-poor — priority for next maintenance window (7 stations)
          </div>
        </div>
      </Card>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [tab,        setTab]        = useState<Tab>("Floor Supervisor");
  const [throughput, setThroughput] = useState<ThroughputPoint[]>([]);
  const [roi,        setRoi]        = useState<ROIStats | null>(null);

  useEffect(() => {
    fetchJSON<{ throughput: ThroughputPoint[] }>("/api/history/throughput")
      .then(({ throughput: t }) => setThroughput(t)).catch(() => {});
    fetchJSON<{ roi: ROIStats }>("/api/roi")
      .then(({ roi: r }) => setRoi(r)).catch(() => {});
  }, []);

  return (
    <div className="max-w-6xl mx-auto p-6 flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--text)" }}>Analytics</h1>
        <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
          One model, three stakeholder lenses
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl w-fit"
           style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-5 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: tab === t ? "var(--accent)" : "transparent",
              color:      tab === t ? "#000"          : "var(--muted)",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "Floor Supervisor" && <SupervisorTab />}
      {tab === "Plant Manager"    && <ManagerTab throughput={throughput} />}
      {tab === "Leadership"       && <LeadershipTab roi={roi} />}
    </div>
  );
}
