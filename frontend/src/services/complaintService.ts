import api from './api'

export type ComplaintCategory =
  | 'pothole'
  | 'garbage'
  | 'water_leakage'
  | 'street_light'
  | 'drainage'
  | 'traffic_signal'
  | 'encroachment'
  | 'other'

export type ComplaintStatus =
  | 'pending'
  | 'analyzing'
  | 'verified'
  | 'assigned'
  | 'in_progress'
  | 'resolved'
  | 'rejected'

export type PriorityLevel = 'low' | 'medium' | 'high' | 'critical'

export interface ComplaintMedia {
  id: string
  media_type: 'image' | 'audio' | 'video' | 'document'
  file_url: string
  file_name: string
  file_size: number
  mime_type: string
  caption?: string | null
  is_resolution_evidence: boolean
  created_at: string
}

export interface ComplaintTimeline {
  id: string
  status: ComplaintStatus
  changed_by_id?: string | null
  note?: string | null
  created_at: string
}

export interface Complaint {
  id: string
  /** Citizen-facing unique code, e.g. NC-7K4P-9XQ2. */
  tracking_id: string
  citizen_id: string
  title: string
  description: string
  category: ComplaintCategory
  status: ComplaintStatus
  priority: PriorityLevel
  severity: number
  latitude?: number | null
  longitude?: number | null
  address?: string | null
  landmark?: string | null
  department_id?: string | null
  assigned_officer_id?: string | null
  source: string
  created_at: string
  updated_at: string
  resolved_at?: string | null
  media: ComplaintMedia[]
  timeline: ComplaintTimeline[]
  ai_analysis?: import('./aiService').AIAnalysisRecord | null
}

export interface ComplaintListResponse {
  items: Complaint[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface ComplaintSummary {
  total: number
  active: number
  resolved: number
  critical: number
}

export interface CreateComplaintPayload {
  title: string
  description: string
  category: ComplaintCategory
  latitude?: number | null
  longitude?: number | null
  address?: string | null
  landmark?: string | null
  source?: 'web' | 'mobile' | 'voice'
  media?: Array<{
    file_url: string
    file_name: string
    file_size: number
    mime_type: string
    media_type: 'image' | 'audio' | 'video' | 'document'
    caption?: string
  }>
}

export const complaintService = {
  /** Create a new complaint */
  async createComplaint(data: CreateComplaintPayload): Promise<Complaint> {
    const resp = await api.post<Complaint>('/complaints', data)
    return resp.data
  },

  /** Upload an image or audio file */
  async uploadMedia(file: File): Promise<{
    file_url: string
    file_name: string
    file_size: number
    mime_type: string
    media_type: 'image' | 'audio' | 'video' | 'document'
  }> {
    const formData = new FormData()
    formData.append('file', file)
    const resp = await api.post('/complaints/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return resp.data
  },

  /** Get list of complaints submitted by current user */
  async getMyComplaints(page = 1, limit = 20): Promise<ComplaintListResponse> {
    const resp = await api.get<ComplaintListResponse>('/complaints/my', {
      params: { page, limit },
    })
    return resp.data
  },

  /** Get counts summary for citizen dashboard */
  async getMySummary(): Promise<ComplaintSummary> {
    const resp = await api.get<ComplaintSummary>('/complaints/my/summary')
    return resp.data
  },

  /** Get complaint by ID */
  async getComplaintById(id: string): Promise<Complaint> {
    const resp = await api.get<Complaint>(`/complaints/${id}`)
    return resp.data
  },

  /** List all complaints with filters */
  async listComplaints(params?: {
    category?: ComplaintCategory
    status?: ComplaintStatus
    priority?: PriorityLevel
    page?: number
    limit?: number
  }): Promise<ComplaintListResponse> {
    const resp = await api.get<ComplaintListResponse>('/complaints', { params })
    return resp.data
  },
}
