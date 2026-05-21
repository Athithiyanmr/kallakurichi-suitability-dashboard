export interface Parcel {
  parcel_id: string;
  village: string;
  lat: number;
  lon: number;
  elevation_m: number;
  slope_deg: number;
  slope_score: number;
  lulc_class: number;
  lulc_name: string;
  lulc_score: number;
  ghi_kwh_m2_yr: number;
  pv_yield_kwh_kwp: number;
  ghi_score: number;
  ghi_daily: number;
  temp_c: number;
  temp_score: number;
  power_dist_km: number;
  power_score: number;
  road_dist_km: number;
  road_score: number;
  suitability_score: number;
  suitability_class: string;
}

export interface Meta {
  total_parcels: number;
  villages: string[];
  lulc_names: string[];
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
  village:       string;
  lulc_name:     string;
  max_slope:     number;
  max_power_dist:number;
}
