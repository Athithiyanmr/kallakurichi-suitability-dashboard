import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import type { Parcel, Meta, Weights, Filters } from "../types";

function buildQuery(weights: Weights, filters: Filters) {
  const p = new URLSearchParams({
    w_slope:        String(weights.slope),
    w_lulc:         String(weights.lulc),
    w_ghi:          String(weights.ghi),
    w_power:        String(weights.power),
    w_road:         String(weights.road),
    w_temp:         String(weights.temp),
    lulc:           filters.lulc,
    suit_class:     filters.suit_class,
    max_slope:      String(filters.max_slope),
    max_power_dist: String(filters.max_power_dist),
    min_area:       String(filters.min_area),
  });
  return `/api/parcels?${p.toString()}`;
}

export function useParcels(weights: Weights, filters: Filters) {
  const url = buildQuery(weights, filters);
  return useQuery<Parcel[]>({
    queryKey: [url],
    staleTime: 0, // always recompute when weights / filters change
  });
}

export function useMeta() {
  return useQuery<Meta>({ queryKey: ["/api/meta"] });
}

// GeoJSON endpoint — used by the map directly
export function buildGeoJSONUrl(weights: Weights, filters: Filters) {
  const p = new URLSearchParams({
    w_slope:        String(weights.slope),
    w_lulc:         String(weights.lulc),
    w_ghi:          String(weights.ghi),
    w_power:        String(weights.power),
    w_road:         String(weights.road),
    w_temp:         String(weights.temp),
    lulc:           filters.lulc,
    suit_class:     filters.suit_class,
    max_slope:      String(filters.max_slope),
    max_power_dist: String(filters.max_power_dist),
    min_area:       String(filters.min_area),
  });
  return `/api/geojson?${p.toString()}`;
}
