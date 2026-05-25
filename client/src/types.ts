// ─── New polygon-based Parcel schema (short field names from barren_parcels_flat.json)
export interface Parcel {
  id:         string;         // KLK-XXXX
  lulc:       string;         // "Bare/sparse veg" | "Shrubland"
  lulc_class: number;         // 60 | 20
  area_ha:    number;
  lat:        number;
  lon:        number;
  elev:       number;         // elevation_m
  slope:      number;         // slope_deg
  ghi:        number;         // ghi_kwh_m2_yr
  pv_yield:   number;         // E_y kWh/kWp/yr
  temp:       number;         // T2M_c
  pwr_km:     number;         // distance to nearest OSM power tower (km)
  road_km:    number;         // distance to nearest OSM highway node (km)
  s_slope:    number;         // score 1-4
  s_ghi:      number;
  s_power:    number;
  s_road:     number;
  s_temp:     number;
  s_lulc:     number;
  score:      number;         // composite suitability
  class:      string;         // "Very High" | "High" | "Moderate" | "Low"
}

export interface Meta {
  total_parcels: number;
  total_area_ha: number;
  lulc_types:    string[];
  suit_classes:  string[];
  bbox: { min_lat: number; max_lat: number; min_lon: number; max_lon: number };
  data_sources: Record<string, string>;
}

export interface Weights {
  slope: number;
  lulc:  number;
  ghi:   number;
  power: number;
  road:  number;
  temp:  number;
}

export interface Filters {
  lulc:           string;
  suit_class:     string;
  max_slope:      number;
  max_power_dist: number;
  min_area:       number;
}
