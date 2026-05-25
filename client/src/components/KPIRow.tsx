import { useEffect, useRef } from "react";
import { Sun, Zap, MapPin, TrendingUp, BarChart2, Thermometer, Leaf, Maximize2 } from "lucide-react";
import type { Parcel } from "../types";

// ─── Count-up animation ───────────────────────────────────────────────────────
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
      const t       = Math.min((now - startTime) / duration, 1);
      const ease    = 1 - Math.pow(1 - t, 3);
      const current = start + diff * ease;
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
  label:    string;
  value:    number;
  unit:     string;
  decimals?: number;
  color:    "blue" | "green" | "amber" | "violet" | "red" | "teal" | "default";
  Icon:     typeof Sun;
  suffix?:  string;
}

const COLOR_MAP: Record<string, { icon: string; line: string }> = {
  blue:    { icon: "hsl(var(--primary-light))",   line: "hsl(var(--primary))" },
  green:   { icon: "#ceead6",                     line: "#0d8043" },
  amber:   { icon: "#fce8b2",                     line: "#e37400" },
  violet:  { icon: "#ede9fe",                     line: "#7c3aed" },
  red:     { icon: "#fce8e6",                     line: "#c5221f" },
  teal:    { icon: "#d2e3fc",                     line: "#1a73e8" },
  default: { icon: "hsl(var(--surface-variant))", line: "hsl(var(--foreground-tertiary))" },
};

function KPICard({ label, value, unit, decimals = 0, color, Icon, suffix = "" }: KPICardProps) {
  const valueRef = useCountUp(value, decimals);
  const { icon: iconBg, line } = COLOR_MAP[color] ?? COLOR_MAP.default;

  return (
    <div className={`kpi-card ${color} fade-up`} data-testid={`kpi-${label.toLowerCase().replace(/\s/g, "-")}`}>
      <div className="kpi-icon" style={{ background: iconBg }}>
        <Icon size={15} color={line} strokeWidth={2.2} />
      </div>
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
  const n         = parcels.length;
  const totalHa   = n ? parcels.reduce((s, p) => s + p.area_ha, 0) : 0;
  const avg       = n ? parcels.reduce((s, p) => s + p.score, 0) / n : 0;
  const nHigh     = parcels.filter((p) => p.score >= 2.75).length;
  const avgGhi    = n ? parcels.reduce((s, p) => s + p.ghi, 0) / n : 0;
  const avgTemp   = n ? parcels.reduce((s, p) => s + p.temp, 0) / n : 0;
  const avgSlope  = n ? parcels.reduce((s, p) => s + p.slope, 0) / n : 0;
  const avgPwr    = n ? parcels.reduce((s, p) => s + p.pwr_km, 0) / n : 0;
  const avgPV     = n ? parcels.reduce((s, p) => s + p.pv_yield, 0) / n : 0;

  return (
    <div className="kpi-grid">
      <KPICard
        label="Polygons"
        value={n}
        unit="barren parcels"
        color="blue"
        Icon={MapPin}
      />
      <KPICard
        label="Total Area"
        value={Math.round(totalHa / 1000 * 10) / 10}
        unit="thousand ha"
        decimals={1}
        color="teal"
        Icon={Maximize2}
        suffix=" k ha"
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
        label="High Suitability"
        value={nHigh}
        unit="score ≥ 2.75"
        color="green"
        Icon={TrendingUp}
      />
      <KPICard
        label="Avg GHI"
        value={Math.round(avgGhi)}
        unit="kWh/m²/yr · PVGIS"
        color="amber"
        Icon={Sun}
      />
      <KPICard
        label="Avg PV Yield"
        value={Math.round(avgPV)}
        unit="kWh/kWp/yr"
        color="amber"
        Icon={Zap}
      />
      <KPICard
        label="Avg Slope"
        value={avgSlope}
        unit="degrees · SRTM"
        decimals={1}
        color="default"
        Icon={Leaf}
      />
      <KPICard
        label="Avg Grid Dist."
        value={avgPwr}
        unit="km to power tower"
        decimals={1}
        color="violet"
        Icon={Zap}
      />
    </div>
  );
}
