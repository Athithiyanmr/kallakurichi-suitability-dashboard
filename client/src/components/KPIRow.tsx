import { useEffect, useRef } from "react";
import type { Parcel } from "../types";

function useCountUp(target: number, duration = 600) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef(0);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const start = prev.current; const diff = target - start;
    const startTime = performance.now();
    const step = (now: number) => {
      const progress = Math.min((now - startTime) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      const current = start + diff * ease;
      el.textContent = target % 1 === 0
        ? Math.round(current).toLocaleString()
        : current.toFixed(2);
      if (progress < 1) requestAnimationFrame(step);
      else prev.current = target;
    };
    requestAnimationFrame(step);
  }, [target, duration]);
  return ref;
}

interface KPICardProps {
  label: string;
  value: number;
  unit: string;
  decimals?: number;
  variant?: "default" | "accent" | "success" | "warning";
  icon: string;
}

function KPICard({ label, value, unit, decimals = 0, variant = "default", icon }: KPICardProps) {
  const ref = useCountUp(value);
  return (
    <div className={`kpi-card ${variant} fade-up`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value tabular-nums flex items-baseline gap-1">
        <span>{icon}</span>
        <span ref={ref}>{decimals > 0 ? value.toFixed(decimals) : value.toLocaleString()}</span>
      </div>
      <div className="kpi-sub">{unit}</div>
    </div>
  );
}

interface KPIRowProps {
  parcels: Parcel[];
}

export function KPIRow({ parcels }: KPIRowProps) {
  const n = parcels.length;
  const avg = n ? parcels.reduce((s, p) => s + p.suitability_score, 0) / n : 0;
  const best = n ? Math.max(...parcels.map((p) => p.suitability_score)) : 0;
  const nHigh = parcels.filter((p) => p.suitability_score >= 2.5).length;
  const avgGhi = n ? parcels.reduce((s, p) => s + p.ghi_kwh_m2_yr, 0) / n : 0;
  const avgPV = n ? parcels.reduce((s, p) => s + p.pv_yield_kwh_kwp, 0) / n : 0;
  const pctHigh = n ? (nHigh / n * 100) : 0;

  return (
    <div className="grid grid-cols-6 gap-3 px-5 py-4">
      <KPICard label="Parcels"         value={n}       unit="after filters"         icon="📍" />
      <KPICard label="Avg Score"       value={avg}     unit="out of 4.0"  decimals={2} variant="default" icon="📊" />
      <KPICard label="Best Score"      value={best}    unit="top parcel"  decimals={2} variant="success" icon="🏆" />
      <KPICard label="High Suitability" value={pctHigh} unit="score ≥ 2.5" decimals={1} variant="accent"  icon="✅" />
      <KPICard label="Avg GHI"         value={avgGhi}  unit="kWh/m²/yr — PVGIS ERA5" decimals={0} icon="☀️" />
      <KPICard label="Avg PV Yield"    value={avgPV}   unit="kWh/kWp/yr" decimals={0} variant="warning"  icon="⚡" />
    </div>
  );
}
