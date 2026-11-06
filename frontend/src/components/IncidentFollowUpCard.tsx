import { useEffect, useState } from 'react'
import { Bell, CalendarClock, Users } from 'lucide-react'
import { incidentService, type IncidentNotificationPreferences, type PublicIncidentTracker } from '../services/incidentService'

interface IncidentFollowUpCardProps {
  complaintId: string
}

export function IncidentFollowUpCard({ complaintId }: IncidentFollowUpCardProps) {
  const [tracker, setTracker] = useState<PublicIncidentTracker | null>(null)
  const [preferences, setPreferences] = useState<IncidentNotificationPreferences | null>(null)
  const [disputeReason, setDisputeReason] = useState('The issue remains after the reported repair.')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([
      incidentService.getTrackerForComplaint(complaintId),
      incidentService.getNotificationPreferences(),
    ]).then(([trackerData, preferenceData]) => {
      if (!active) return
      setTracker(trackerData)
      setPreferences(preferenceData)
    }).catch(() => {
      if (active) setError('Incident updates are not available for this report yet.')
    })
    return () => { active = false }
  }, [complaintId])

  const savePreferences = async (next: IncidentNotificationPreferences) => {
    setPreferences(next)
    try {
      await incidentService.updateNotificationPreferences(next)
    } catch {
      setError('Could not save notification preferences.')
    }
  }

  const disputeResolution = async () => {
    if (!tracker || disputeReason.trim().length < 5) return
    setBusy(true)
    setError(null)
    try {
      await incidentService.disputeResolvedIncident(tracker.incident_id, disputeReason.trim())
      setTracker(await incidentService.getTrackerForComplaint(complaintId))
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Could not reopen this incident.')
    } finally {
      setBusy(false)
    }
  }

  if (!tracker && !error) return <div className="card p-4 text-sm text-gray-500">Loading incident updates…</div>
  if (!tracker) return <div className="card p-4 text-sm text-gray-500">{error}</div>

  return (
    <section className="card p-4 space-y-4" aria-label="Shared incident tracker">
      <div>
        <h2 className="section-label mb-2">Shared incident</h2>
        <p className="text-sm font-semibold text-gray-900">{tracker.title}</p>
        <p className="mt-1 text-xs text-gray-500 capitalize">{tracker.status.replace(/_/g, ' ')} · {tracker.priority} priority</p>
      </div>

      <div className="space-y-2 text-xs text-gray-600">
        <p className="flex items-center gap-2"><Users size={14} aria-hidden="true" />{tracker.reporter_count} citizens have reported this issue</p>
        <p className="flex items-center gap-2"><CalendarClock size={14} aria-hidden="true" />Expected by {new Date(tracker.expected_by).toLocaleString()}</p>
        {tracker.responsible_department && <p>Responsible department: {tracker.responsible_department}</p>}
        <p>{tracker.what_happens_next}</p>
      </div>

      {tracker.timeline.length > 0 && (
        <ol className="space-y-2 border-l border-gray-200 pl-3">
          {tracker.timeline.map((event, index) => (
            <li key={`${event.created_at}-${index}`} className="text-xs">
              <p className="font-medium text-gray-800">{event.note}</p>
              <time className="text-gray-400">{new Date(event.created_at).toLocaleString()}</time>
            </li>
          ))}
        </ol>
      )}

      {preferences && (
        <div className="border-t border-gray-100 pt-3 space-y-2">
          <p className="flex items-center gap-2 text-xs font-semibold text-gray-700"><Bell size={14} aria-hidden="true" />Incident notifications</p>
          <label className="flex items-center gap-2 text-xs text-gray-600">
            <input type="checkbox" checked={preferences.sms_enabled} onChange={(event) => void savePreferences({ ...preferences, sms_enabled: event.target.checked })} />
            SMS updates
          </label>
          <label className="flex items-center gap-2 text-xs text-gray-600">
            <input type="checkbox" checked={preferences.email_enabled} onChange={(event) => void savePreferences({ ...preferences, email_enabled: event.target.checked })} />
            Email updates
          </label>
        </div>
      )}

      {tracker.status === 'resolved' && (
        <div className="border-t border-gray-100 pt-3 space-y-2">
          <label className="block text-xs font-semibold text-gray-700" htmlFor="incident-dispute-reason">Still unresolved?</label>
          <textarea id="incident-dispute-reason" className="w-full rounded-lg border border-gray-200 p-2 text-xs" rows={2} value={disputeReason} onChange={(event) => setDisputeReason(event.target.value)} />
          <button className="rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50" disabled={busy || disputeReason.trim().length < 5} onClick={() => void disputeResolution()}>
            {busy ? 'Reopening…' : 'Dispute resolution and reopen'}
          </button>
        </div>
      )}
      {error && <p role="status" className="text-xs text-red-600">{error}</p>}
    </section>
  )
}
