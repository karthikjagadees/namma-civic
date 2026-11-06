import api from './api';

export interface VerificationDetails {
  verified: boolean;
  verification_status: string;
  confidence_score: number;
  defect_clearance_detected: boolean;
  structural_restoration_score: number;
  multimodal_comparison: {
    original_evidence_present: boolean;
    resolution_evidence_provided: boolean;
    ai_vision_finding: string;
  };
  verified_at: string;
}

export interface ResolutionResponse {
  complaint_id: string;
  new_status: string;
  resolved_at: string;
  verification: VerificationDetails;
  timeline_note: string;
}

export const resolutionService = {
  async submitResolution(
    complaintId: string,
    notes: string,
    imageUrl?: string
  ): Promise<ResolutionResponse> {
    const res = await api.post<ResolutionResponse>(`/resolution/verify/${complaintId}`, {
      resolution_notes: notes,
      resolution_image_url: imageUrl,
    });
    return res.data;
  },
};
