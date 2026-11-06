import api from './api'

export interface ReviewLocation {
  latitude: number | null
  longitude: number | null
  address?: string | null
  landmark?: string | null
}

export interface ReviewPhoto {
  url: string
  file_name?: string | null
  perceptual_hash?: string | null
}

export interface ReviewReport {
  complaint_id: string
  title: string
  description: string
  category?: string
  channel?: string
  location: ReviewLocation
  photos: ReviewPhoto[]
}

export interface ReviewCandidate {
  incident_id: string
  title: string
  category: string
  status: string
  location: ReviewLocation
  photos: ReviewPhoto[]
  score: number
  distance_m: number | null
  signals: Record<string, number | null>
  reports: Array<Pick<ReviewReport, 'complaint_id' | 'title' | 'description' | 'channel' | 'photos'>>
}

export interface DuplicateReview {
  review_id: string
  complaint_id: string
  reason: string
  failures: string[]
  report: ReviewReport
  candidates: ReviewCandidate[]
}

export const duplicateReviewService = {
  async list(): Promise<DuplicateReview[]> {
    const response = await api.get<DuplicateReview[]>('/officer/duplicate-reviews')
    return response.data
  },
  async decide(
    reviewId: string,
    action: 'confirm_link' | 'reject_match' | 'merge_incidents' | 'split_report',
    candidateIncidentId: string | null,
    note: string,
  ): Promise<void> {
    await api.post(`/officer/duplicate-reviews/${reviewId}/decision`, {
      action,
      candidate_incident_id: candidateIncidentId,
      note,
    })
  },
  async analytics(): Promise<{
    duplicates_linked: number
    work_orders_avoided: number
    review_queue_volume: number
    officer_agreement_rate: number | null
    agreement_pair_count: number
  }> {
    const response = await api.get('/analytics/duplicate-operations')
    return response.data
  },
}
