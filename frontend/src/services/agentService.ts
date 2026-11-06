import api from './api'

export interface AgentOrchestrateResponse {
  complaint_id: string
  current_step: string
  steps_completed: string[]
  requires_human_approval: boolean
  is_awaiting_approval: boolean
  approval_reason?: string | null
  intake_result?: {
    summary?: string
    detected_category?: string
    confidence_score?: number
    urgency_score?: number
    severity?: number
    extracted_entities?: Record<string, any>
    vision_analysis?: Record<string, any>
    provider_name?: string
    model_name?: string
    processing_time_ms?: number
  } | null
  validation_result?: {
    is_valid: boolean
    spam_score: number
    validity_reason: string
    is_actionable: boolean
    flags: string[]
  } | null
  deduplication_result?: {
    is_duplicate: boolean
    duplicate_of_id?: string | null
    distance_meters?: number | null
    similarity_score: number
    cluster_id?: string | null
  } | null
  routing_result?: {
    department_id?: string | null
    department_name: string
    department_code: string
    priority: string
    severity: number
    sla_hours: number
    routing_rationale: string
  } | null
  action_result?: {
    work_order_id: string
    action_status: string
    notifications_queued: boolean
    dispatched_to: string
    timeline_note: string
  } | null
  human_decision?: {
    approved: boolean
    officer_id?: string | null
    officer_notes?: string
    override_dept?: string | null
    override_priority?: string | null
  } | null
}

export interface OfficerApprovalPayload {
  approved: boolean
  officer_notes?: string
  override_dept?: string
  override_priority?: string
}

export const agentService = {
  async orchestrate(complaintId: string): Promise<AgentOrchestrateResponse> {
    const res = await api.post<AgentOrchestrateResponse>(`/agents/orchestrate/${complaintId}`)
    return res.data
  },

  async getState(complaintId: string): Promise<AgentOrchestrateResponse> {
    const res = await api.get<AgentOrchestrateResponse>(`/agents/state/${complaintId}`)
    return res.data
  },

  async submitApproval(
    complaintId: string,
    payload: OfficerApprovalPayload
  ): Promise<AgentOrchestrateResponse> {
    const res = await api.post<AgentOrchestrateResponse>(`/agents/approve/${complaintId}`, payload)
    return res.data
  },
}

export default agentService
