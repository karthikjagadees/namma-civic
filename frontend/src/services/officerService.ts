import api from './api';

export interface OfficerQueueItem {
  id: string;
  incident_id: string | null;
  report_count: number;
  reporter_count: number;
  tracking_id: string;
  title: string;
  description: string;
  category: string;
  status: string;
  priority: string;
  severity: number;
  address: string;
  latitude: number | null;
  longitude: number | null;
  department_id: string | null;
  department_name?: string;
  assigned_officer_id: string | null;
  created_at: string;
  sla: {
    deadline?: string | null;
    hours_remaining: number;
    percent_consumed: number;
    sla_status: 'ON_TRACK' | 'AT_RISK' | 'BREACHED' | 'RESOLVED';
    is_breached?: boolean;
    risk_level?: string;
  };
  media?: Array<{ file_url: string; media_type: string }>;
  images?: string[];
  media_count?: number;
  has_ai_analysis?: boolean;
}

export interface OfficerRosterItem {
  id: string;
  full_name: string;
  email: string;
  department_id: string | null;
  department_name: string;
}

export interface OfficerStats {
  total_cases: number;
  active_cases: number;
  resolved_cases: number;
  at_risk_cases: number;
  breached_cases: number;
  compliance_rate: number;
  duty_shift: string;
  telemetry_time: string;
}

export const officerService = {
  async getQueue(status?: string, priority?: string, departmentId?: string): Promise<OfficerQueueItem[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (priority) params.append('priority', priority);
    if (departmentId) params.append('department_id', departmentId);
    const res = await api.get<OfficerQueueItem[]>(`/officer/queue?${params.toString()}`);
    return res.data;
  },

  async getRoster(): Promise<OfficerRosterItem[]> {
    const res = await api.get<OfficerRosterItem[]>('/officer/roster');
    return res.data;
  },

  async getStats(): Promise<OfficerStats> {
    const res = await api.get<OfficerStats>('/officer/stats');
    return res.data;
  },

  async assignComplaint(
    complaintId: string,
    officerId: string,
    reason?: string,
    forceOverride = false,
    notes?: string
  ): Promise<any> {
    const res = await api.post(`/officer/assign/${complaintId}`, {
      officer_id: officerId,
      reason,
      force_override: forceOverride,
      notes,
    });
    return res.data;
  },

  async dispatchCrew(
    complaintId: string,
    crewId: string,
    deptCode: string,
    priority = 'HIGH',
    instructions = ''
  ): Promise<any> {
    const res = await api.post(`/officer/dispatch-crew/${complaintId}`, {
      crew_id: crewId,
      department_code: deptCode,
      priority,
      instructions,
    });
    return res.data;
  },
};
