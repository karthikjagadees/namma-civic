import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload, Mic, X, CheckCircle2,
  Loader2, Camera, FileText, AlertCircle, Info, ArrowLeft, ArrowRight,
} from 'lucide-react'
import { complaintService, type ComplaintCategory, type CreateComplaintPayload } from '../services/complaintService'
import { agentService, type AgentOrchestrateResponse } from '../services/agentService'
import { AppShell } from '../components/AppShell'
import { Alert, Button } from '../components/ui'
import { TrackingId } from '../components/TrackingId'
import { LocationPickerMap } from '../components/LocationPickerMap'

const CATEGORIES: Array<{ id: ComplaintCategory; label: string; emoji: string }> = [
  { id: 'pothole',        label: 'Pothole / Road Damage',  emoji: '🕳️' },
  { id: 'garbage',        label: 'Garbage / Waste',         emoji: '🗑️' },
  { id: 'water_leakage',  label: 'Water Leakage',           emoji: '💧' },
  { id: 'street_light',   label: 'Street Light Outage',     emoji: '💡' },
  { id: 'drainage',       label: 'Drainage / Flooding',     emoji: '🌊' },
  { id: 'traffic_signal', label: 'Traffic Signal Issue',    emoji: '🚦' },
  { id: 'encroachment',   label: 'Encroachment',            emoji: '🚧' },
  { id: 'other',          label: 'Other',                    emoji: '📋' },
]

interface UploadedFile {
  file: File
  preview?: string
  url?: string
  uploading?: boolean
  error?: string
}

type Step = 'category' | 'details' | 'location' | 'media' | 'review' | 'done'
type PipelineStatus = 'idle' | 'processing' | 'complete' | 'awaiting_review' | 'failed'
const STEPS: Step[] = ['category', 'details', 'location', 'media', 'review', 'done']

const STEP_LABELS: Record<Step, string> = {
  category: 'Category',
  details:  'Details',
  location: 'Location',
  media:    'Evidence',
  review:   'Review',
  done:     'Done',
}

export default function ReportComplaintPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('category')
  const [category, setCategory] = useState<ComplaintCategory>('pothole')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [address, setAddress] = useState('')
  const [landmark, setLandmark] = useState('')
  const [gps, setGps] = useState<{ lat: number; lng: number } | null>(null)
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [createdId, setCreatedId] = useState<string | null>(null)
  const [trackingId, setTrackingId] = useState<string | null>(null)
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus>('idle')
  const [pipelineError, setPipelineError] = useState<string | null>(null)
  const [pipelineResult, setPipelineResult] = useState<AgentOrchestrateResponse | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const stepIdx = STEPS.indexOf(step)

  const goNext = () => {
    const next = STEPS[stepIdx + 1]
    if (next) setStep(next)
  }
  const goPrev = () => {
    const prev = STEPS[stepIdx - 1]
    if (prev) setStep(prev)
  }

  const handleLocationSelect = useCallback((loc: {
    address: string
    landmark: string
    latitude: number
    longitude: number
  }) => {
    setAddress(loc.address)
    setLandmark(loc.landmark)
    setGps({ lat: loc.latitude, lng: loc.longitude })
  }, [])

  const handleFiles = useCallback(async (incoming: File[]) => {
    const newEntries: UploadedFile[] = incoming.map((f) => ({
      file: f,
      preview: f.type.startsWith('image/') ? URL.createObjectURL(f) : undefined,
      uploading: true,
    }))
    setFiles((prev) => [...prev, ...newEntries])

    for (const file of incoming) {
      try {
        const res = await complaintService.uploadMedia(file)
        setFiles((prev) =>
          prev.map((m) => m.file === file ? { ...m, uploading: false, url: res.file_url } : m)
        )
      } catch {
        setFiles((prev) =>
          prev.map((m) => m.file === file ? { ...m, uploading: false, error: 'Upload failed' } : m)
        )
      }
    }
  }, [])

  const processComplaint = async (complaintId: string) => {
    setPipelineStatus('processing')
    setPipelineError(null)
    try {
      const result = await agentService.orchestrate(complaintId)
      setPipelineResult(result)
      setPipelineStatus(
        result.is_awaiting_approval || result.requires_human_approval ||
          result.action_result?.action_status === 'needs_review'
          ? 'awaiting_review'
          : 'complete'
      )
    } catch (err: unknown) {
      setPipelineStatus('failed')
      setPipelineError(err instanceof Error ? err.message : 'Automatic report processing failed.')
    }
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setSubmitError(null)
    setPipelineError(null)
    try {
      const payload: CreateComplaintPayload = {
        title: title.trim(),
        description: description.trim(),
        category,
        address: address || undefined,
        landmark: landmark || undefined,
        latitude: gps?.lat,
        longitude: gps?.lng,
        source: 'web',
        media: files.filter((f) => f.url).map((f) => ({
          file_url: f.url!,
          file_name: f.file.name,
          file_size: f.file.size,
          mime_type: f.file.type,
          media_type: f.file.type.startsWith('image/') ? 'image' : f.file.type.startsWith('audio/') ? 'audio' : 'document',
        })),
      }
      const res = await complaintService.createComplaint(payload)
      setCreatedId(res.id)
      setTrackingId(res.tracking_id)
      setStep('done')
      await processComplaint(res.id)
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Submission failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const catObj = CATEGORIES.find((c) => c.id === category)

  const submissionMessage = pipelineStatus === 'processing'
    ? 'Your report is saved. We are checking for related incidents and routing it.'
    : pipelineStatus === 'awaiting_review'
      ? 'Your report is saved and needs officer review before work is assigned.'
      : pipelineStatus === 'failed'
        ? 'Your report is saved, but automatic processing did not finish.'
        : pipelineResult?.action_result?.action_status === 'linked'
          ? 'Your report was linked to an existing incident. Your original report remains in your account.'
          : pipelineStatus === 'complete'
            ? 'Your report was processed. Check your dashboard for its current status.'
            : 'Your report has been saved.'

  return (
    <AppShell>
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="text-heading-1 text-gray-900">Report a Civic Issue</h1>
          <p className="text-sm text-gray-500 mt-0.5">AI-powered multimodal intake — fill each step below</p>
        </div>
      </div>

      {/* Stepper */}
      {step !== 'done' && (
        <div className="card p-4 mb-6" aria-label="Report submission steps">
          <div className="flex items-center gap-0 overflow-x-auto no-scrollbar">
            {STEPS.filter((s) => s !== 'done').map((s, idx) => {
              const sIdx = STEPS.indexOf(s)
              const isCurrent = s === step
              const isDone = stepIdx > sIdx
              return (
                <div key={s} className="flex items-center gap-0 shrink-0">
                  <div className="flex flex-col items-center gap-1">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                        isDone ? 'bg-green-600 text-white' :
                        isCurrent ? 'bg-blue-900 text-white' :
                        'bg-gray-200 text-gray-500'
                      }`}
                      aria-current={isCurrent ? 'step' : undefined}
                    >
                      {isDone ? <CheckCircle2 size={16} aria-hidden="true" /> : idx + 1}
                    </div>
                    <span className={`text-[10px] font-semibold whitespace-nowrap ${isCurrent ? 'text-blue-900' : 'text-gray-400'}`}>
                      {STEP_LABELS[s]}
                    </span>
                  </div>
                  {idx < STEPS.filter((s) => s !== 'done').length - 1 && (
                    <div className={`h-0.5 w-6 sm:w-10 mx-1 mb-4 rounded-full ${isDone ? 'bg-green-500' : 'bg-gray-200'}`} aria-hidden="true" />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Step Content */}
      <div className="card p-5 sm:p-6">

        {/* ── DONE ─────────────────────────────────────────── */}
        {step === 'done' && (
          <div className="flex flex-col items-center py-8 text-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-green-50 border border-green-100 flex items-center justify-center">
              <CheckCircle2 size={32} className="text-green-600" />
            </div>
            <h2 className="text-heading-2 text-gray-900">Report Submitted!</h2>
            <p className="text-sm text-gray-500 max-w-xs">
              {submissionMessage}
            </p>
            {pipelineError && <Alert variant="error" className="max-w-md text-sm">{pipelineError}</Alert>}
            {trackingId && <TrackingId code={trackingId} variant="card" showTrackLink />}
            <div className="flex flex-col sm:flex-row gap-3 w-full max-w-xs">
              <Button variant="primary" fullWidth onClick={() => navigate('/dashboard')}>View Dashboard</Button>
              {pipelineStatus === 'failed' && createdId ? (
                <Button variant="secondary" fullWidth onClick={() => void processComplaint(createdId)}>
                  Retry processing
                </Button>
              ) : null}
              <Button variant="secondary" fullWidth onClick={() => { setStep('category'); setTitle(''); setDescription(''); setFiles([]); setCreatedId(null); setTrackingId(null); setPipelineStatus('idle'); setPipelineError(null); setPipelineResult(null) }}>
                New Report
              </Button>
            </div>
          </div>
        )}

        {/* ── CATEGORY ─────────────────────────────────────── */}
        {step === 'category' && (
          <div>
            <h2 className="text-heading-2 text-gray-900 mb-1">Select Issue Category</h2>
            <p className="text-sm text-gray-500 mb-5">What type of civic issue are you reporting?</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-6">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setCategory(cat.id)}
                  aria-pressed={category === cat.id}
                  className={`flex flex-col items-center gap-2 p-3 sm:p-4 rounded-xl border-2 text-center transition-all cursor-pointer ${
                    category === cat.id
                      ? 'border-blue-700 bg-blue-50'
                      : 'border-gray-200 bg-white hover:border-gray-400'
                  }`}
                >
                  <span className="text-2xl leading-none" aria-hidden="true">{cat.emoji}</span>
                  <span className={`text-xs font-semibold leading-tight ${category === cat.id ? 'text-blue-800' : 'text-gray-700'}`}>
                    {cat.label}
                  </span>
                </button>
              ))}
            </div>
            <Button variant="primary" onClick={goNext} iconRight={<ArrowRight size={15} />}>
              Continue
            </Button>
          </div>
        )}

        {/* ── DETAILS ──────────────────────────────────────── */}
        {step === 'details' && (
          <div>
            <h2 className="text-heading-2 text-gray-900 mb-1">Describe the Issue</h2>
            <p className="text-sm text-gray-500 mb-5">Clear descriptions improve AI routing accuracy.</p>
            <div className="space-y-4">
              <div>
                <label htmlFor="report-title" className="label">Brief title <span className="text-red-600" aria-hidden="true">*</span></label>
                <input
                  id="report-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                  maxLength={120}
                  placeholder="e.g., Deep pothole near Indiranagar Metro gate"
                  className="input"
                />
                <p className="hint">{title.length}/120 characters</p>
              </div>
              <div>
                <label htmlFor="report-desc" className="label">Detailed description <span className="text-red-600" aria-hidden="true">*</span></label>
                <textarea
                  id="report-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                  rows={4}
                  maxLength={1000}
                  placeholder="Describe the issue, its impact, when you noticed it, and any safety hazard…"
                  className="input textarea"
                />
                <p className="hint">{description.length}/1000</p>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <Button variant="ghost" icon={<ArrowLeft size={15} />} onClick={goPrev}>Back</Button>
              <Button variant="primary" disabled={title.trim().length < 5 || description.trim().length < 10} onClick={goNext} iconRight={<ArrowRight size={15} />}>
                Continue
              </Button>
            </div>
          </div>
        )}

        {/* ── LOCATION ─────────────────────────────────────── */}
        {step === 'location' && (
          <div>
            <h2 className="text-heading-2 text-gray-900 mb-1">Where is the Issue?</h2>
            <p className="text-sm text-gray-500 mb-5">
              Pinpoint the exact location on the map, use GPS, or search for a street or landmark.
            </p>
            <LocationPickerMap
              initialLat={gps?.lat || 12.9716}
              initialLng={gps?.lng || 77.5946}
              initialAddress={address}
              initialLandmark={landmark}
              onLocationSelect={handleLocationSelect}
            />
            <div className="flex gap-3 mt-6">
              <Button variant="ghost" icon={<ArrowLeft size={15} />} onClick={goPrev}>Back</Button>
              <Button
                variant="primary"
                disabled={!address.trim()}
                onClick={goNext}
                iconRight={<ArrowRight size={15} />}
              >
                Continue
              </Button>
            </div>
          </div>
        )}

        {/* ── MEDIA ────────────────────────────────────────── */}
        {step === 'media' && (
          <div>
            <h2 className="text-heading-2 text-gray-900 mb-1">Upload Evidence</h2>
            <p className="text-sm text-gray-500 mb-5">Photos dramatically improve AI classification accuracy. Optional but recommended.</p>

            {/* Drop zone */}
            <div
              role="button"
              tabIndex={0}
              className={`drop-zone mb-4 ${dragOver ? 'drag-over' : ''}`}
              aria-label="Upload evidence files"
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click() }}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                const dropped = Array.from(e.dataTransfer.files)
                if (dropped.length) handleFiles(dropped)
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*,audio/*,video/*,.pdf"
                className="sr-only"
                aria-hidden="true"
                onChange={(e) => {
                  if (e.target.files) handleFiles(Array.from(e.target.files))
                  e.target.value = ''
                }}
              />
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center" aria-hidden="true">
                  <Upload size={24} className="text-blue-600" />
                </div>
                <p className="text-sm font-semibold text-gray-700">
                  {dragOver ? 'Release to upload' : 'Tap to add photos / videos'}
                </p>
                <p className="text-xs text-gray-400">or drag & drop — max 20MB each</p>
                <div className="flex gap-2 mt-1">
                  {[{ label: 'Photo', Icon: Camera }, { label: 'Audio', Icon: Mic }, { label: 'Doc', Icon: FileText }].map(({ label, Icon }) => (
                    <span key={label} className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-100 text-gray-500 text-xs">
                      <Icon size={11} aria-hidden="true" /> {label}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Previews */}
            {files.length > 0 && (
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 mb-4">
                {files.map((f, idx) => (
                  <div
                    key={idx}
                    className="relative rounded-xl border border-gray-200 overflow-hidden bg-gray-50 aspect-square flex items-center justify-center"
                  >
                    {f.preview ? (
                      <img src={f.preview} alt={`Preview ${idx + 1}`} className="w-full h-full object-cover" />
                    ) : (
                      <FileText size={20} className="text-gray-400" aria-hidden="true" />
                    )}
                    {f.uploading && (
                      <div className="absolute inset-0 bg-white/80 flex items-center justify-center">
                        <Loader2 size={18} className="spinner text-blue-600" aria-hidden="true" />
                      </div>
                    )}
                    {f.error && (
                      <div className="absolute inset-0 bg-red-50/90 flex items-center justify-center p-1">
                        <AlertCircle size={14} className="text-red-600" aria-hidden="true" />
                      </div>
                    )}
                    {!f.uploading && (
                      <button
                        type="button"
                        onClick={() => setFiles((prev) => { URL.revokeObjectURL(f.preview || ''); return prev.filter((_, i) => i !== idx) })}
                        aria-label={`Remove file ${idx + 1}`}
                        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-gray-900/80 text-white flex items-center justify-center"
                      >
                        <X size={10} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="alert alert-info mb-5 text-xs">
              <Info size={14} className="shrink-0" aria-hidden="true" />
              <span>Vision AI will analyze your photos to improve category detection and routing accuracy.</span>
            </div>

            <div className="flex gap-3">
              <Button variant="ghost" icon={<ArrowLeft size={15} />} onClick={goPrev}>Back</Button>
              <Button variant="primary" disabled={files.some((f) => f.uploading)} onClick={goNext} iconRight={<ArrowRight size={15} />}>
                Continue
              </Button>
            </div>
          </div>
        )}

        {/* ── REVIEW ───────────────────────────────────────── */}
        {step === 'review' && (
          <div>
            <h2 className="text-heading-2 text-gray-900 mb-5">Review & Submit</h2>
            <div className="space-y-3 mb-6">
              {[
                { label: 'Category', value: `${catObj?.emoji} ${catObj?.label}` },
                { label: 'Title', value: title },
                { label: 'Description', value: description },
                { label: 'Address', value: address || '—' },
                { label: 'Landmark', value: landmark || '—' },
                { label: 'Files', value: files.length > 0 ? `${files.length} file${files.length > 1 ? 's' : ''} attached` : 'No files' },
              ].map(({ label, value }) => (
                <div key={label} className="flex gap-3 py-2.5 border-b border-gray-100 last:border-0">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide w-24 shrink-0 mt-0.5">{label}</span>
                  <span className="text-sm text-gray-800 flex-1 break-words">{value}</span>
                </div>
              ))}
            </div>

            {submitError && <Alert variant="error" className="mb-4 text-sm">{submitError}</Alert>}

            <div className="flex gap-3">
              <Button variant="ghost" icon={<ArrowLeft size={15} />} onClick={goPrev}>Back</Button>
              <Button
                variant="primary"
                loading={submitting}
                onClick={handleSubmit}
                icon={<CheckCircle2 size={15} />}
              >
                {submitting ? 'Submitting…' : 'Submit Report'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
