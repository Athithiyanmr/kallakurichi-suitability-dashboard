import { useEffect, useRef } from "react";
import { Sun, Zap, MapPin, TrendingUp, BarChart2, Thermometer } from "lucide-react";
import type { Parcel } from "../types";

// Count-up animation hook
function useCountUp(target: number, decimals = 0, duration = 700) {
  const ref  = useRef<HTMLSpanElement>(null);
  const prev = useRef(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const start     = prev.current;
    const diff      = target - start;
    const startTime = performance.now();

    const step = (now: number) => {
      const t        = Math.min((now - startTime) / duration, 1);
      const ease     = 1 - Math.pow(1 - t, 3);        // ease-out cubic
      const current  = start + diff * ease;
      el.textContent = decimals > 0
        ? current.toFixed(decimals)
        : Math.round(current).toLocaleString();
      if (t < 1) requestAnimationFrame(step);
      else prev.current = target;
    };

    requestAnimationFrame(step);
  }, [target, decimals, duration]);

  return ref;
}

interface KPICardProps {
  label: string;
  value: number;
  unit: string;
  decimals?: number;
  color: "blue" | "green" | "amber" | "violet" | "red" | "default";
  Icon: typeof Sun;
  suffix?: string;
}

const COLOR_MAP: Record<string, { icon: string; line: string }> = {
  blue:    { icon: "hsl(var(--primary-light))",  line: "hsl(var(--primary))" },
  green:   { icon: "hsl(var(--score-vh-bg))",    line: "hsl(var(--green))" },
  amber:   { icon: "hsl(var(--score-mod-bg))",   line: "hsl(var(--amber))" },
  violet:  { icon: "#ede9fe",                    line: "#7c3aed" },
  red:     { icon: "hsl(var(--score-low-bg))",   line: "hsl(var(--red))" },
  default: { icon: "hsl(var(--surface-variant))", line: "hsl(var(--foreground-tertiary))" },
};

function KPICard({ label, value, unit, decimals = 0, color, Icon, suffix = "" }: KPICardProps) {
  const valueRef = useCountUp(value, decimals);
  const { icon: iconBg, line } = COLOR_MAP[color] ?? COLOR_MAP.default;

  return (
    <div className={`kpi-card ${color} fade-up`} data-testid={`kpi-${label.toLowerCase().replace(/\s/g,'-')}`}>
      {/* Icon chip */}
      <div className={`kpi-icon ${color}`} style={{ background: iconBg }}>
        <Icon size={15} color={line} strokeWidth={2.2} />
      </div>

      {/* Value */}
      <div className="kpi-value">
        <span ref={valueRef}>
          {decimals > 0 ? value.toFixed(decimals) : value.toLocaleString()}
        </span>
        {suffix && (
          <span style={{ fontSize: 14, fontWeight: 500, marginLeft: 2, color: "hsl(var(--foreground-secondary))" }}>
            {suffix}
          </span>
        )}
      </div>

      <div className="kpi-label" style={{ marginTop: 4, marginBottom: 0 }}>{label}</div>
      <div className="kpi-sub">{unit}</div>
    </div>
  );
}

export function KPIRow({ parcels }: { parcels: Parcel[] }) {
  const n       = parcels.length;
  const avg     = n ? parcels.reduce((s, p) => s + p.suitability_score, 0) / n : 0;
  const best    = n ? Math.max(...parcels.map((p) => p.suitability_score)) : 0;
  const nHigh   = parcels.filter((p) => p.suitability_score >= 2.5).length;
  const avgGhi  = n ? parcels.reduce((s, p) => s + p.ghi_kwh_m2_yr, 0) / n : 0;
  const avgPV   = n ? parcels.reduce((s, p) => s + p.pv_yield_kwh_kwp, 0) / n : 0;
  const avgTemp = n ? parcels.reduce((s, p) => s + p.temp_c, 0) / n : 0;

  return (
    <div className="kpi-grid">
      <KPICard
        label="Parcels"
        value={n}
        unit="analysis grid"
        color="blue"
        Icon={MapPin}
      />
      <KPICard
        label="Avg Score"
        value={avg}
        unit="out of 4.0"
        decimals={2}
        color="default"
        Icon={BarChart2}
        suffix="/4"
      />
      <KPICard
        label="Top Score"
        value={best}
        unit="highest parcel"
        decimals={2}
        color="green"
        Icon={TrendingUp}
      />
      <KPICard
        label="High Suitability"
        value={nHigh}
        unit="score ≥ 2.5"
        color="amber"
        Icon={TrendingUp}
      />
      <KPICard
        label="Avg GHI"
        value={Math.round(avgGhi)}
        unit="kWh/m²/yr — PVGIS ERA5"
        color="amber"
        Icon={Sun}
      />
      <KPICard
        label="Mean Temp"
        value={avgTemp}
        unit="°C · NASA POWER"
        decimals={1}
        color="red"
        Icon={Thermometer}
      />
    </div>
  );
}
