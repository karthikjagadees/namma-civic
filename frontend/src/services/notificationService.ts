/**
 * Namma Civic — Notifications & Email Gateway Service
 * Client for checking SMTP status, sending test alerts, and inspecting the outbox.
 */
import api from './api'

export interface SMTPStatus {
  mode: 'LIVE_SMTP' | 'SIMULATED_DEV_MODE'
  host: string
  port: number
  use_tls: boolean
  from_address: string
  username_configured: boolean
  total_outbox_logged: number
  status_description: string
}

export interface SendTestEmailPayload {
  to_email: string
  subject?: string
  message?: string
}

export interface OutboxItem {
  id: string
  to_email: string
  from_email: string
  subject: string
  event_type: string
  complaint_id?: string
  html_preview: string
  text_preview: string
  created_at: string
  status: 'SENT' | 'SIMULATED' | 'FAILED' | 'PENDING'
  delivery_channel: string
  error?: string
}

export const notificationService = {
  /**
   * Check SMTP gateway health and active delivery mode
   */
  async getStatus(): Promise<SMTPStatus> {
    const res = await api.get<SMTPStatus>('/notifications/status')
    return res.data
  },

  /**
   * Dispatch a live or simulated test email
   */
  async sendTestEmail(payload: SendTestEmailPayload): Promise<{
    message_id: string
    status: string
    recipient: string
    subject: string
    note?: string
  }> {
    const res = await api.post('/notifications/test-email', payload)
    return res.data
  },

  /**
   * Fetch recent outbox delivery logs
   */
  async getOutbox(limit: number = 50): Promise<OutboxItem[]> {
    const res = await api.get<OutboxItem[]>('/notifications/outbox', {
      params: { limit },
    })
    return res.data
  },
}

export default notificationService
