import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { complaintService, type Complaint, type ComplaintStatus } from '../services/complaintService'
import { AppShell } from '../components/AppShell'
import { TrackingId } from '../components/TrackingId'
import {
  StatTile,
  StatusBadge,
  PriorityBadge,
  Spinner,
  Button,
} from '../components/ui'
import {
  Plus,
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  MapPin,
  ArrowRight,
  RefreshCw,
} from 'lucide-react'

// ── Status progress steps ─────────────────────────────────────
const STATUS_STEPS: ComplaintStatus[] = [
  'pending', 'analyzing', 'verified', 'assigned', 'in_progress', 'resolved',
]

const StatusProgress: React.FC<{ status: ComplaintStatus }> = ({ status }) => {
  const idx = STATUS_STEPS.indexOf(status)
  const pct = status === 'rejected' ? 0 : idx >= 0 ? Math.round(((idx + 1) / STATUS_STEPS.length) * 100) : 0
  return (
    <div
      className="h-1 bg-gray-200 rounded-full overflow-hidden mt-2"
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Progress: ${pct}%`}
    >
      <div
        className={`h-full rounded-full transition-all duration-500 ${status === 'resolved' ? 'bg-green-500' : status === 'rejected' ? 'bg-red-400' : 'bg-blue-500'}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ── Complaint Card ────────────────────────────────────────────
const ComplaintCard: React.FC<{ complaint: Complaint }> = ({ complaint }) => {
  const img = complaint.media?.find((m) => m.media_type === 'image')
  const days = Math.floor((Date.now() - new Date(complaint.created_at).getTime()) / 86400000)

  return (
    <div className="card card-hover overflow-hidden flex flex-col">
      {/* Image */}
      {img && (
        <div className="w-full h-32 sm:h-36 overflow-hidden shrink-0">
          <img
            src={img.file_url}
            alt={`Evidence for: ${complaint.title}`}
            className="w-full h-full object-cover"
          />
        </div>
      )}
      <div className="p-4 flex flex-col gap-2 flex-1">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <Link
              to={`/complaints/${complaint.id}`}
              className="text-sm font-semibold text-gray-900 hover:text-blue-700 transition-colors truncate-2 leading-snug block"
            >
              {complaint.title}
            </Link>
            <span className="text-xs text-gray-500 font-mono capitalize mt-0.5 block">
              {complaint.category.replace(/_/g, ' ')}
            </span>
            <span className="mt-1.5 block"><TrackingId code={complaint.tracking_id} /></span>
          </div>
          <StatusBadge status={complaint.status} />
        </div>

        {/* Description */}
        <p className="text-xs text-gray-500 truncate-2 leading-relaxed">{complaint.description}</p>

        {/* Meta */}
        <div className="flex items-center gap-3 text-xs text-gray-400 flex-wrap">
          <span className="flex items-center gap-1">
            <Clock size={11} aria-hidden="true" />
            {days === 0 ? 'Today' : days === 1 ? 'Yesterday' : `${days}d ago`}
          </span>
          {complaint.address && (
            <span className="flex items-center gap-1 truncate">
              <MapPin size={11} aria-hidden="true" />
              <span className="truncate max-w-[140px]">{complaint.address}</span>
            </span>
          )}
          {complaint.priority && <PriorityBadge priority={complaint.priority} />}
        </div>

        {/* Progress */}
        <StatusProgress status={complaint.status} />

        {/* View link */}
        <Link
          to={`/complaints/${complaint.id}`}
          className="text-xs font-semibold text-blue-700 hover:text-blue-900 flex items-center gap-1 mt-1 transition-colors"
        >
          View Details <ArrowRight size={12} aria-hidden="true" />
        </Link>
      </div>
    </div>
  )
}

// ── Filter tabs ───────────────────────────────────────────────
const FILTER_TABS = [
  { id: 'all',         label: 'All'        },
  { id: 'analyzing',   label: 'AI Queue'   },
  { id: 'in_progress', label: 'In Progress'},
  { id: 'resolved',    label: 'Resolved'   },
]

// ── Main Component ────────────────────────────────────────────
export default function CitizenDashboard() {
  const { user, refreshMe } = useAuthStore()
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [summary, setSummary] = useState({ total: 0, active: 0, resolved: 0, critical: 0 })
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [res, sum] = await Promise.all([
        complaintService.getMyComplaints(1, 50),
        complaintService.getMySummary(),
      ])
      setComplaints(res.items || [])
      setSummary(sum)
    } catch (err) {
      console.error('Dashboard load error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshMe()
    load()
  }, [load, refreshMe])

  const filtered = filter === 'all' ? complaints : complaints.filter((c) => c.status === filter)
  const active = complaints.filter((c) => !['resolved', 'rejected'].includes(c.status)).length

  return (
    <AppShell>
      {/* ── Page Header ──────────────────────────────────── */}
      <div className="page-header">
        <div>
          <h1 className="text-heading-1 text-gray-900">
            Hello, {user?.full_name?.split(' ')[0] ?? 'Citizen'} 👋
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">Track your civic reports and AI processing status.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" icon={<RefreshCw size={15} />} onClick={load} aria-label="Refresh">
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Link to="/report" className="btn btn-primary btn-sm">
            <Plus size={15} aria-hidden="true" />
            <span>Report Issue</span>
          </Link>
        </div>
      </div>

      {/* ── Stats Row ─────────────────────────────────────── */}
      <div className="grid-4 mb-6">
        <StatTile label="Total Reports" value={summary.total} icon={<FileText size={18} />} />
        <StatTile label="Active" value={active} icon={<Clock size={18} />} />
        <StatTile label="Resolved" value={summary.resolved} icon={<CheckCircle2 size={18} />} variant="success" />
        <StatTile label="Critical" value={summary.critical} icon={<AlertTriangle size={18} />} variant={summary.critical > 0 ? 'danger' : 'default'} />
      </div>

      {/* ── Filter tabs ────────────────────────────────────── */}
      <div
        className="flex items-center gap-1.5 mb-5 overflow-x-auto pb-1 no-scrollbar"
        role="group"
        aria-label="Filter by status"
      >
        {FILTER_TABS.map(({ id, label }) => {
          const count = id === 'all' ? complaints.length : complaints.filter((c) => c.status === id).length
          return (
            <button
              key={id}
              onClick={() => setFilter(id)}
              aria-pressed={filter === id}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all shrink-0 ${
                filter === id
                  ? 'bg-blue-900 text-white'
                  : 'bg-white text-gray-600 border border-gray-200 hover:border-gray-400'
              }`}
            >
              {label}
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
                filter === id ? 'bg-white/20 text-white' : 'bg-gray-100 text-gray-500'
              }`}>{count}</span>
            </button>
          )
        })}
      </div>

      {/* ── Content ───────────────────────────────────────── */}
      {loading ? (
        <div className="flex justify-center items-center py-20" role="status">
          <Spinner label="Loading your complaints…" size={28} />
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mb-2" aria-hidden="true">
            <FileText size={28} className="text-gray-300" />
          </div>
          <p className="text-base font-semibold text-gray-600">
            {filter === 'all' ? 'No reports yet' : `No ${filter.replace('_', ' ')} reports`}
          </p>
          <p className="text-sm text-gray-400 max-w-xs">
            {filter === 'all' ? 'Spot a civic issue? Report it and let AI handle the rest.' : 'No complaints match this filter.'}
          </p>
          {filter === 'all' && (
            <Link to="/report" className="btn btn-primary mt-4">
              <Plus size={15} aria-hidden="true" /> Report First Issue
            </Link>
          )}
        </div>
      ) : (
        <div className="grid-2 lg:grid-cols-3">
          {filtered.map((c) => <ComplaintCard key={c.id} complaint={c} />)}
        </div>
      )}
    </AppShell>
  )
}
