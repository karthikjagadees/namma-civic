import api from './api';

export interface SLATelemetry {
  complaint_id: string;
  priority: string;
  total_sla_hours: number;
  created_at: string;
  deadline: string;
  hours_remaining: number;
  seconds_remaining: number;
  percent_consumed: number;
  sla_status: 'ON_TRACK' | 'AT_RISK' | 'BREACHED' | 'RESOLVED';
  risk_level: 'LOW' | 'HIGH' | 'CRITICAL' | 'NONE';
  is_closed: boolean;
}

export interface SLAOverview {
  total_complaints: number;
  active_complaints: number;
  on_track: number;
  at_risk: number;
  breached: number;
  resolved: number;
  sla_compliance_rate: number;
  audit_timestamp: string;
}

export const slaService = {
  async getOverview(): Promise<SLAOverview> {
    const res = await api.get<SLAOverview>('/sla/overview');
    return res.data;
  },

  async getComplaintSLA(complaintId: string): Promise<SLATelemetry> {
    const res = await api.get<SLATelemetry>(`/sla/complaint/${complaintId}`);
    return res.data;
  },

  async checkAndAutoEscalate(): Promise<any> {
    const res = await api.post('/sla/check-and-escalate');
    return res.data;
  },

  async manualEscalate(complaintId: string, reason?: string): Promise<any> {
    const res = await api.post(`/sla/escalate/${complaintId}`, {
      reason: reason || 'Urgent field escalation triggered by municipal officer',
      tier: 'TIER_1_SUPERVISOR'
    });
    return res.data;
  },
};
