import React, { useCallback, useEffect, useState } from 'react'
import { AppShell } from '../components/AppShell'
import { Alert, Button, Card, Skeleton } from '../components/ui'
import { duplicateReviewService, type DuplicateReview, type ReviewLocation, type ReviewPhoto } from '../services/duplicateReviewService'
import { getMediaUrl } from '../utils/media'

const pointLink = (location: ReviewLocation) => {
  if (location.latitude == null || location.longitude == null) return null
  return `https://www.openstreetmap.org/?mlat=${location.latitude}&mlon=${location.longitude}#map=18/${location.latitude}/${location.longitude}`
}

const mapEmbed = (location: ReviewLocation) => {
  if (location.latitude == null || location.longitude == null) return null
  const lat = location.latitude
  const lon = location.longitude
  const bbox = `${lon - 0.004},${lat - 0.003},${lon + 0.004},${lat + 0.003}`
  return `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${lat}%2C${lon}`
}

const PhotoStrip: React.FC<{ photos: ReviewPhoto[] }> = ({ photos }) => (
  <div className="grid grid-cols-2 gap-2 mt-3">
    {photos.map((photo, index) => (
      <a key={`${photo.url}-${index}`} href={getMediaUrl(photo.url)} target="_blank" rel="noreferrer">
        <img className="h-36 w-full rounded object-cover bg-gray-100" src={getMediaUrl(photo.url)} alt={photo.file_name || 'Report evidence'} />
      </a>
    ))}
    {!photos.length && <p className="text-sm text-gray-500">No photo evidence</p>}
  </div>
)

const LocationCard: React.FC<{ label: string; location: ReviewLocation }> = ({ label, location }) => {
  const url = pointLink(location)
  const embed = mapEmbed(location)
  return (
    <div className="rounded border border-gray-200 p-3 text-sm">
      <strong>{label}</strong>
      <p>{location.address || location.landmark || 'No address supplied'}</p>
      <p className="text-gray-500">{location.latitude ?? '—'}, {location.longitude ?? '—'}</p>
      {embed && <iframe className="mt-2 h-40 w-full rounded border" title={`${label} map`} src={embed} loading="lazy" />}
      {url && <a className="text-blue-700 underline" href={url} target="_blank" rel="noreferrer">Open map</a>}
    </div>
  )
}

export const DuplicateReviewPage: React.FC = () => {
  const [items, setItems] = useState<DuplicateReview[]>([])
  const [metrics, setMetrics] = useState<Awaited<ReturnType<typeof duplicateReviewService.analytics>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [notes, setNotes] = useState<Record<string, string>>({})

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [queue, summary] = await Promise.all([
        duplicateReviewService.list(),
        duplicateReviewService.analytics().catch(() => null),
      ])
      setItems(queue)
      setMetrics(summary)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not load the duplicate review queue.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const decide = async (item: DuplicateReview, action: 'confirm_link' | 'reject_match' | 'merge_incidents' | 'split_report', candidateId: string | null) => {
    setBusy(item.review_id)
    setError(null)
    try {
      await duplicateReviewService.decide(item.review_id, action, candidateId, notes[item.review_id] || 'Officer reviewed the report evidence.')
      setSuccess(`Review recorded: ${action.replaceAll('_', ' ')}.`)
      await refresh()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not save the officer decision.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <AppShell>
      <main className="space-y-5">
        <header className="flex items-center justify-between border-b pb-4">
          <div>
            <h1 className="text-2xl font-bold">Duplicate review queue</h1>
            <p className="text-sm text-gray-600">Compare the report with likely incident candidates and record your decision.</p>
          </div>
          <Button variant="secondary" onClick={() => void refresh()} disabled={loading}>Refresh</Button>
        </header>
        {error && <Alert variant="error" onClose={() => setError(null)}>{error}</Alert>}
        {success && <Alert variant="success" onClose={() => setSuccess(null)}>{success}</Alert>}
        {metrics && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ['Duplicates linked', metrics.duplicates_linked],
            ['Work orders avoided', metrics.work_orders_avoided],
            ['Waiting for review', metrics.review_queue_volume],
            ['Officer agreement', metrics.officer_agreement_rate == null ? 'Not enough double-reviewed pairs' : `${(metrics.officer_agreement_rate * 100).toFixed(1)}%`],
          ].map(([label, value]) => <Card key={String(label)}><p className="text-xs uppercase text-gray-500">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p></Card>)}
        </div>}
        {loading ? <Skeleton /> : !items.length ? <Card><p>No reports are waiting for duplicate review.</p></Card> : items.map((item) => (
          <Card key={item.review_id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><h2 className="text-lg font-semibold">{item.report.title}</h2><p className="text-sm text-gray-600">{item.reason} · {item.report.channel}</p></div>
              <span className="rounded bg-amber-100 px-2 py-1 text-xs text-amber-900">Officer review</span>
            </div>
            {!!item.failures.length && <p className="mt-2 text-sm text-amber-800">Signal failures: {item.failures.join('; ')}</p>}
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <section className="rounded border p-4">
                <h3 className="font-semibold">New report</h3><p className="mt-2 text-sm">{item.report.description}</p>
                <LocationCard label="Report location" location={item.report.location} />
                <PhotoStrip photos={item.report.photos} />
              </section>
              <section className="space-y-3">
                {!item.candidates.length && <div className="rounded border p-4"><p>No candidate incident could be retrieved. Split the report into its own incident after checking the evidence.</p><Button className="mt-3" disabled={busy === item.review_id} onClick={() => void decide(item, 'split_report', null)}>Split into new incident</Button></div>}
                {item.candidates.map((candidate) => (
                  <div key={candidate.incident_id} className="rounded border p-4">
                    <div className="flex flex-wrap justify-between gap-2"><h3 className="font-semibold">{candidate.title}</h3><span className="text-sm">Score {candidate.score.toFixed(3)} · {candidate.distance_m == null ? 'unknown distance' : `${candidate.distance_m.toFixed(1)} m`}</span></div>
                    <p className="mt-1 text-sm text-gray-600">{candidate.category} · {candidate.status}</p>
                    <LocationCard label="Candidate incident location" location={candidate.location} />
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">{Object.entries(candidate.signals).map(([name, value]) => <div key={name} className="rounded bg-gray-50 px-2 py-1 text-xs"><strong>{name}</strong>: {value == null ? 'unavailable' : value.toFixed(3)}</div>)}</div>
                    <div className="mt-3 space-y-2">{candidate.reports.map((report) => <div key={report.complaint_id} className="rounded bg-gray-50 p-2"><strong className="text-sm">{report.title} · {report.channel}</strong><p className="text-sm">{report.description}</p></div>)}</div>
                    <PhotoStrip photos={candidate.photos} />
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button disabled={busy === item.review_id} onClick={() => void decide(item, 'confirm_link', candidate.incident_id)}>Confirm link</Button>
                      <Button variant="secondary" disabled={busy === item.review_id} onClick={() => void decide(item, 'reject_match', candidate.incident_id)}>Reject match</Button>
                      <Button variant="secondary" disabled={busy === item.review_id} onClick={() => void decide(item, 'merge_incidents', candidate.incident_id)}>Merge incidents</Button>
                      <Button variant="secondary" disabled={busy === item.review_id} onClick={() => void decide(item, 'split_report', candidate.incident_id)}>Split report</Button>
                    </div>
                  </div>
                ))}
                <textarea className="w-full rounded border p-2 text-sm" rows={2} placeholder="Decision note (required)" value={notes[item.review_id] || ''} onChange={(e) => setNotes((current) => ({ ...current, [item.review_id]: e.target.value }))} />
              </section>
            </div>
          </Card>
        ))}
      </main>
    </AppShell>
  )
}
