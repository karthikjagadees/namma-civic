import api from './api'

export interface VisionAnalysis {
  has_damage_detected: boolean
  detected_damage_type: string
  visual_severity_estimate: number
  confidence_score: number
  visual_features: string[]
  safety_hazard_level: 'low' | 'medium' | 'high' | 'critical'
  details?: Record<string, any>
}

export interface AIAnalysisRecord {
  id: string
  complaint_id: string
  summary: string
  detected_category: string
  confidence_score: number
  urgency_score: number
  severity: number
  recommended_department: string
  reasoning: string
  extracted_entities: {
    location_mentions?: string[]
    landmarks?: string[]
    hazard_type?: string
    affected_population_scale?: string
    [key: string]: any
  }
  vision_analysis?: VisionAnalysis | null
  provider_used: string
  model_used: string
  processing_time_ms: number
  created_at: string
  updated_at: string
}

export interface StandaloneAIResponse {
  summary: string
  detected_category: string
  confidence_score: number
  urgency_score: number
  severity: number
  recommended_department: string
  reasoning: string
  extracted_entities: Record<string, any>
  vision_analysis?: VisionAnalysis | null
  provider_used: string
  model_used: string
  processing_time_ms: number
}

export const aiService = {
  async analyzeStandalone(payload: {
    text: string
    image_url?: string
    audio_url?: string
    category_hint?: string
  }): Promise<StandaloneAIResponse> {
    const res = await api.post<StandaloneAIResponse>('/ai/analyze', payload)
    return res.data
  },

  async getComplaintAIAnalysis(complaintId: string): Promise<AIAnalysisRecord> {
    const res = await api.get<AIAnalysisRecord>(`/ai/analysis/${complaintId}`)
    return res.data
  },

  async reanalyzeComplaint(complaintId: string): Promise<AIAnalysisRecord> {
    const res = await api.post<AIAnalysisRecord>(`/ai/reanalyze/${complaintId}`)
    return res.data
  },

  async triggerComplaintTriage(complaintId: string) {
    const res = await api.post(`/complaints/${complaintId}/analyze`)
    return res.data
  },
}

export default aiService
