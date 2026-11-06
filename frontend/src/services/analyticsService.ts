import api from './api';

export interface Centroid {
  latitude: number;
  longitude: number;
}

export interface HotspotCluster {
  cluster_id: string;
  centroid: Centroid;
  incident_count: number;
  primary_category: string;
  average_severity: number;
  zone_type: string;
  risk_label: string;
  nearest_address: string;
  sample_incident_ids: string[];
}

export interface DepartmentScorecard {
  department_id: string;
  name: string;
  code: string;
  total_assigned: number;
  active_cases: number;
  resolved_cases: number;
  breached_cases: number;
  sla_compliance_rate: number;
  efficiency_score: number;
  crew_readiness: string;
}

export interface CityHealthSummary {
  civic_health_index: number;
  status_rating: string;
  total_grievances: number;
  resolved_count: number;
  in_progress_count: number;
  pending_intake_count: number;
  resolution_rate: number;
  category_distribution: Record<string, number>;
  telemetry_timestamp: string;
}

export const analyticsService = {
  async getSummary(): Promise<CityHealthSummary> {
    const res = await api.get<CityHealthSummary>('/analytics/summary');
    return res.data;
  },

  async getHotspots(radiusM = 500): Promise<HotspotCluster[]> {
    const res = await api.get<HotspotCluster[]>(`/analytics/hotspots?radius_m=${radiusM}`);
    return res.data;
  },

  async getDepartmentScorecard(): Promise<DepartmentScorecard[]> {
    const res = await api.get<DepartmentScorecard[]>('/analytics/departments');
    return res.data;
  },
};
