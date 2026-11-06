import api from './api'

export interface PublicIncidentTimelineEvent {
  status: string
  event: string
  note: string
  created_at: string
}

export interface PublicIncidentTracker {
  incident_id: string
  title: string
  category: string
  status: string
  priority: string
  reporter_count: number
  responsible_department: string | null
  expected_by: string
  sla_status: string
  what_happens_next: string
  timeline: PublicIncidentTimelineEvent[]
}

export interface TrackedReport extends PublicIncidentTracker {
  tracking_id: string
  submitted_at: string
}

export interface IncidentNotificationPreferences {
  sms_enabled: boolean
  email_enabled: boolean
}

export const incidentService = {
  /** Public lookup by the citizen-facing tracking ID (no login needed). */
  async trackByTrackingId(trackingId: string): Promise<TrackedReport> {
    const response = await api.get<TrackedReport>(`/incidents/track/${encodeURIComponent(trackingId.trim())}`)
    return response.data
  },

  async getTrackerForComplaint(complaintId: string): Promise<PublicIncidentTracker> {
    const response = await api.get<PublicIncidentTracker>(`/incidents/by-report/${complaintId}/tracker`)
    return response.data
  },

  async getNotificationPreferences(): Promise<IncidentNotificationPreferences> {
    const response = await api.get<IncidentNotificationPreferences>('/notifications/preferences')
    return response.data
  },

  async updateNotificationPreferences(preferences: IncidentNotificationPreferences): Promise<IncidentNotificationPreferences> {
    const response = await api.put<IncidentNotificationPreferences>('/notifications/preferences', preferences)
    return response.data
  },

  async disputeResolvedIncident(incidentId: string, reason: string): Promise<void> {
    await api.post(`/incidents/${incidentId}/dispute`, { reason })
  },
}
