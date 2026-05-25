import { useState, useMemo } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown, Download } from "lucide-react";
import type { Parcel } from "../types";

type SortKey = keyof Pick<Parcel,
  "score" | "s_slope" | "s_lulc" | "s_ghi" |
  "s_power" | "s_road" | "s_temp" |
  "ghi" | "pv_yield" | "pwr_km" | "road_km" |
  "area_ha" | "slope" | "temp" | "elev"
>;

function ScoreCell({ v }: { v: number }) {
  const cls = v >= 4 ? "s4" : v >= 3 ? "s3" : v >= 2 ? "s2" : "s1";
  return <span className={`score-cell ${cls}`}>{v}</span>;
}

function SortIcon({ col, sort }: { col: string; sort: { key: string; dir: "asc" | "desc" } }) {
  if (sort.key !== col) return <ArrowUpDown size={11} className="opacity-30 ml-1" />;
  return sort.dir === "asc"
    ? <ArrowUp   size={11} className="ml-1" style={{ color: "hsl(var(--primary))" }} />
    : <ArrowDown size={11} className="ml-1" style={{ color: "hsl(var(--primary))" }} />;
}

// ─── Export helpers ──────────────────────────────────────────────────────────
function exportCSV(data: Parcel[]) {
  const headers = [
    "Rank","Parcel ID","LULC","Area ha","Lat","Lon","Score","Class",
    "s_slope","s_lulc","s_ghi","s_power","s_road","s_temp",
    "GHI kWh/m²/yr","PV Yield kWh/kWp","Slope °","Elev m",
    "Grid km","Road km","Temp °C",
  ];
  const rows = data.map((p, i) => [
    i+1, p.id, p.lulc, p.area_ha.toFixed(2), p.lat, p.lon,
    p.score.toFixed(3), p.class,
    p.s_slope, p.s_lulc, p.s_ghi, p.s_power, p.s_road, p.s_temp,
    p.ghi.toFixed(0), p.pv_yield.toFixed(0), p.slope.toFixed(1), p.elev.toFixed(0),
    p.pwr_km.toFixed(1), p.road_km.toFixed(1), p.temp.toFixed(1),
  ]);
  const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = "kallakurichi_barren_parcels.csv";
  a.click();
}

function exportGeoJSON(data: Parcel[]) {
  const fc = {
    type: "FeatureCollection",
    features: data.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: {
        id: p.id, lulc: p.lulc, area_ha: p.area_ha,
        score: p.score, class: p.class,
        s_slope: p.s_slope, s_lulc: p.s_lulc, s_ghi: p.s_ghi,
        s_power: p.s_power, s_road: p.s_road, s_temp: p.s_temp,
        ghi: p.ghi, pv_yield: p.pv_yield,
        pwr_km: p.pwr_km, road_km: p.road_km,
        slope: p.slope, elev: p.elev, temp: p.temp,
      },
    })),
  };
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(fc, null, 2)], { type: "application/json" }));
  a.download = "kallakurichi_barren_parcels.geojson";
  a.click();
}

// ─── Main component ──────────────────────────────────────────────────────────
interface Props { parcels: Parcel[]; topN?: number; }

export function ParcelTable({ parcels, topN = 50 }: Props) {
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "score", dir: "desc",
  });
  const [page, setPage] = useState(0);
  const PER_PAGE = topN;

  const sorted = useMemo(() =>
    [...parcels].sort((a, b) => {
      const av = a[sort.key] as number, bv = b[sort.key] as number;
      return sort.dir === "asc" ? av - bv : bv - av;
    }),
    [parcels, sort.key, sort.dir]
  );

  const paged      = sorted.slice(page * PER_PAGE, (page + 1) * PER_PAGE);
  const totalPages = Math.ceil(sorted.length / PER_PAGE);

  function toggleSort(key: SortKey) {
    setSort((prev) => prev.key === key
      ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
      : { key, dir: "desc" }
    );
    setPage(0);
  }

  const TH = ({ k, label }: { k: SortKey; label: string }) => (
    <th onClick={() => toggleSort(k)} data-testid={`th-${k}`} style={{ cursor: "pointer", userSelect: "none" }}>
      <span style={{ display: "flex", alignItems: "center", gap: 2 }}>
        {label}<SortIcon col={k} sort={sort} />
      </span>
    </th>
  );

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: "hsl(var(--border))" }}>
        <div>
          <span className="font-semibold text-sm">Parcel Rankings</span>
          <span className="text-xs text-muted-foreground ml-2">
            {parcels.length.toLocaleString()} parcels · sorted by {String(sort.key).replace(/_/g, " ")}
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => exportCSV(sorted)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium border transition-colors hover:bg-muted"
            style={{ borderColor: "hsl(var(--border))", color: "hsl(var(--foreground))" }}
            data-testid="btn-export-csv"
          >
            <Download size={12} /> CSV
          </button>
          <button
            onClick={() => exportGeoJSON(sorted)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium border transition-colors hover:bg-muted"
            style={{ borderColor: "hsl(var(--border))", color: "hsl(var(--foreground))" }}
            data-testid="btn-export-geojson"
          >
            <Download size={12} /> GeoJSON
          </button>
        </div>
      </div>

      {/* Scrollable table */}
      <div className="flex-1 overflow-auto overscroll-contain">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Parcel ID</th>
              <th>LULC</th>
              <TH k="area_ha"  label="Area ha" />
              <TH k="score"    label="Score" />
              <th>Class</th>
              <TH k="s_slope"  label="Slope" />
              <TH k="s_lulc"   label="LULC" />
              <TH k="s_ghi"    label="GHI" />
              <TH k="s_power"  label="Grid" />
              <TH k="s_road"   label="Road" />
              <TH k="s_temp"   label="Temp" />
              <TH k="ghi"      label="GHI kWh" />
              <TH k="pv_yield" label="PV Yield" />
              <TH k="slope"    label="Slope °" />
              <TH k="pwr_km"   label="Grid km" />
              <TH k="road_km"  label="Road km" />
              <TH k="temp"     label="Temp °C" />
              <th>Lat</th>
              <th>Lon</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((p, i) => {
              const rank = page * PER_PAGE + i + 1;
              const sc = p.score;
              const badgeCls = sc >= 3.5 ? "badge-vh" : sc >= 2.75 ? "badge-h" : sc >= 2.0 ? "badge-mod" : "badge-low";
              return (
                <tr key={p.id} data-testid={`row-${p.id}`}>
                  <td className="text-muted-foreground tabular-nums">{rank}</td>
                  <td className="font-mono text-xs font-medium">{p.id}</td>
                  <td>
                    <span style={{ fontSize: 11 }}>
                      {p.lulc === "Bare/sparse veg" ? "🟤" : "🟢"} {p.lulc}
                    </span>
                  </td>
                  <td className="tabular-nums text-xs">{p.area_ha.toFixed(1)}</td>
                  <td>
                    <span className={`badge-score ${badgeCls}`}>
                      {p.score.toFixed(3)}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontSize: 10, fontWeight: 600, color:
                      sc >= 3.5 ? "#0d8043" : sc >= 2.75 ? "#1a73e8" : sc >= 2.0 ? "#e37400" : "#c5221f"
                    }}>
                      {p.class}
                    </span>
                  </td>
                  <td><ScoreCell v={p.s_slope} /></td>
                  <td><ScoreCell v={p.s_lulc} /></td>
                  <td><ScoreCell v={p.s_ghi} /></td>
                  <td><ScoreCell v={p.s_power} /></td>
                  <td><ScoreCell v={p.s_road} /></td>
                  <td><ScoreCell v={p.s_temp} /></td>
                  <td className="tabular-nums text-xs">{p.ghi.toFixed(0)}</td>
                  <td className="tabular-nums text-xs">{p.pv_yield.toFixed(0)}</td>
                  <td className="tabular-nums text-xs">{p.slope.toFixed(1)}</td>
                  <td className="tabular-nums text-xs">{p.pwr_km.toFixed(1)}</td>
                  <td className="tabular-nums text-xs">{p.road_km.toFixed(1)}</td>
                  <td className="tabular-nums text-xs">{p.temp.toFixed(1)}</td>
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
          <span className="text-muted-foreground">
            Page {page + 1} of {totalPages} · {parcels.length.toLocaleString()} total
          </span>
          <div className="flex gap-1">
            {[
              { label: "«", action: () => setPage(0), disabled: page === 0 },
              { label: "‹", action: () => setPage((p) => Math.max(0, p - 1)), disabled: page === 0 },
              { label: "›", action: () => setPage((p) => Math.min(totalPages - 1, p + 1)), disabled: page === totalPages - 1 },
              { label: "»", action: () => setPage(totalPages - 1), disabled: page === totalPages - 1 },
            ].map(({ label, action, disabled }) => (
              <button key={label} onClick={action} disabled={disabled}
                className="px-2 py-1 rounded border disabled:opacity-30"
                style={{ borderColor: "hsl(var(--border))" }}>
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
