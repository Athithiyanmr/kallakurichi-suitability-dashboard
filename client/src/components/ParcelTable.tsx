import { useState, useMemo } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown, Download } from "lucide-react";
import type { Parcel } from "../types";

type SortKey = keyof Pick<Parcel,
  "suitability_score" | "slope_score" | "lulc_score" | "ghi_score" |
  "power_score" | "road_score" | "temp_score" | "ghi_kwh_m2_yr" |
  "pv_yield_kwh_kwp" | "power_dist_km" | "road_dist_km"
>;

function ScoreCell({ v }: { v: number }) {
  const cls = v >= 4 ? "s4" : v >= 3 ? "s3" : v >= 2 ? "s2" : "s1";
  return <span className={`score-cell ${cls}`}>{v}</span>;
}

function SortIcon({ col, sort }: { col: string; sort: { key: string; dir: "asc" | "desc" } }) {
  if (sort.key !== col) return <ArrowUpDown size={11} className="opacity-30 ml-1" />;
  return sort.dir === "asc"
    ? <ArrowUp size={11} className="ml-1 text-accent" style={{ color: "hsl(var(--accent))" }} />
    : <ArrowDown size={11} className="ml-1 text-accent" style={{ color: "hsl(var(--accent))" }} />;
}

function exportCSV(data: Parcel[]) {
  const headers = ["Rank","Parcel ID","Village","Lat","Lon","Score","Slope","LULC","GHI","Grid","Road","Temp",
                   "GHI kWh/m²/yr","PV Yield kWh/kWp","Grid km","Road km","Temp °C","Elev m"];
  const rows = data.map((p, i) => [
    i+1, p.parcel_id, p.village, p.lat, p.lon,
    p.suitability_score, p.slope_score, p.lulc_score, p.ghi_score, p.power_score, p.road_score, p.temp_score,
    p.ghi_kwh_m2_yr, p.pv_yield_kwh_kwp, p.power_dist_km, p.road_dist_km, p.temp_c, p.elevation_m,
  ]);
  const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = "kallakurichi_top_parcels.csv";
  a.click();
}

function exportGeoJSON(data: Parcel[]) {
  const fc = {
    type: "FeatureCollection",
    features: data.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: {
        parcel_id: p.parcel_id, village: p.village,
        suitability_score: p.suitability_score, suitability_class: p.suitability_class,
        slope_score: p.slope_score, lulc_score: p.lulc_score, ghi_score: p.ghi_score,
        power_score: p.power_score, road_score: p.road_score, temp_score: p.temp_score,
        ghi_kwh_m2_yr: p.ghi_kwh_m2_yr, pv_yield_kwh_kwp: p.pv_yield_kwh_kwp,
      },
    })),
  };
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(fc, null, 2)], { type: "application/json" }));
  a.download = "kallakurichi_parcels.geojson";
  a.click();
}

interface Props { parcels: Parcel[]; topN?: number; }

export function ParcelTable({ parcels, topN = 30 }: Props) {
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "suitability_score", dir: "desc" });
  const [page, setPage] = useState(0);
  const PER_PAGE = topN;

  const sorted = useMemo(() => {
    return [...parcels].sort((a, b) => {
      const av = a[sort.key] as number, bv = b[sort.key] as number;
      return sort.dir === "asc" ? av - bv : bv - av;
    });
  }, [parcels, sort.key, sort.dir]);

  const paged = sorted.slice(page * PER_PAGE, (page + 1) * PER_PAGE);
  const totalPages = Math.ceil(sorted.length / PER_PAGE);

  function toggleSort(key: SortKey) {
    setSort((prev) => prev.key === key
      ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
      : { key, dir: "desc" }
    );
    setPage(0);
  }

  const TH = ({ k, label }: { k: SortKey; label: string }) => (
    <th onClick={() => toggleSort(k)} data-testid={`th-${k}`}>
      <span className="flex items-center gap-0.5">{label}<SortIcon col={k} sort={sort} /></span>
    </th>
  );

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: "hsl(var(--border))" }}>
        <div>
          <span className="font-semibold text-sm">Parcel Rankings</span>
          <span className="text-xs text-muted-foreground ml-2">{parcels.length} parcels · sorted by {sort.key.replace(/_/g," ")}</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => exportCSV(sorted.slice(0, topN))}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium border transition-colors"
            style={{ borderColor: "hsl(var(--border))", color: "hsl(var(--foreground))" }}
            data-testid="btn-export-csv"
          >
            <Download size={12} /> CSV
          </button>
          <button
            onClick={() => exportGeoJSON(sorted)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium border transition-colors"
            style={{ borderColor: "hsl(var(--border))", color: "hsl(var(--foreground))" }}
            data-testid="btn-export-geojson"
          >
            <Download size={12} /> GeoJSON
          </button>
        </div>
      </div>

      {/* Table scroll area */}
      <div className="flex-1 overflow-auto overscroll-contain">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Parcel</th>
              <th>Village</th>
              <TH k="suitability_score" label="Score ▼" />
              <TH k="slope_score"       label="Slope" />
              <TH k="lulc_score"        label="LULC" />
              <TH k="ghi_score"         label="GHI" />
              <TH k="power_score"       label="Grid" />
              <TH k="road_score"        label="Road" />
              <TH k="temp_score"        label="Temp" />
              <TH k="ghi_kwh_m2_yr"     label="GHI kWh/m²" />
              <TH k="pv_yield_kwh_kwp"  label="PV Yield" />
              <TH k="power_dist_km"     label="Grid km" />
              <TH k="road_dist_km"      label="Road km" />
              <th>Lat</th>
              <th>Lon</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((p, i) => {
              const rank = page * PER_PAGE + i + 1;
              const sc = p.suitability_score;
              const badgeCls = sc >= 3.25 ? "badge-vh" : sc >= 2.5 ? "badge-h" : sc >= 1.75 ? "badge-mod" : "badge-low";
              return (
                <tr key={p.parcel_id} data-testid={`row-${p.parcel_id}`}>
                  <td className="text-muted-foreground tabular-nums">{rank}</td>
                  <td className="font-mono text-xs font-medium">{p.parcel_id}</td>
                  <td className="text-xs">{p.village}</td>
                  <td>
                    <span className={`badge-score ${badgeCls}`}>
                      {p.suitability_score.toFixed(3)}
                    </span>
                  </td>
                  <td><ScoreCell v={p.slope_score} /></td>
                  <td><ScoreCell v={p.lulc_score} /></td>
                  <td><ScoreCell v={p.ghi_score} /></td>
                  <td><ScoreCell v={p.power_score} /></td>
                  <td><ScoreCell v={p.road_score} /></td>
                  <td><ScoreCell v={p.temp_score} /></td>
                  <td className="tabular-nums text-xs">{p.ghi_kwh_m2_yr.toFixed(0)}</td>
                  <td className="tabular-nums text-xs">{p.pv_yield_kwh_kwp.toFixed(0)}</td>
                  <td className="tabular-nums text-xs">{p.power_dist_km.toFixed(1)}</td>
                  <td className="tabular-nums text-xs">{p.road_dist_km.toFixed(1)}</td>
                  <td className="tabular-nums text-xs font-mono">{p.lat.toFixed(4)}</td>
                  <td className="tabular-nums text-xs font-mono">{p.lon.toFixed(4)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-5 py-2 border-t text-xs" style={{ borderColor: "hsl(var(--border))" }}>
          <span className="text-muted-foreground">Page {page + 1} of {totalPages}</span>
          <div className="flex gap-1">
            <button onClick={() => setPage(0)} disabled={page === 0}
              className="px-2 py-1 rounded border disabled:opacity-30" style={{ borderColor: "hsl(var(--border))" }}>«</button>
            <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
              className="px-2 py-1 rounded border disabled:opacity-30" style={{ borderColor: "hsl(var(--border))" }}>‹</button>
            <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page === totalPages - 1}
              className="px-2 py-1 rounded border disabled:opacity-30" style={{ borderColor: "hsl(var(--border))" }}>›</button>
            <button onClick={() => setPage(totalPages - 1)} disabled={page === totalPages - 1}
              className="px-2 py-1 rounded border disabled:opacity-30" style={{ borderColor: "hsl(var(--border))" }}>»</button>
          </div>
        </div>
      )}
    </div>
  );
}
