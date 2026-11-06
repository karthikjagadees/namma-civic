import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Bot,
  Building2,
  CheckCircle2,
  Droplets,
  Lightbulb,
  Loader2,
  MapPin,
  Recycle,
  Route,
  ScanSearch,
  Search,
  TrafficCone,
  Trees,
  Waves,
} from 'lucide-react'
import { PublicShell } from '../components/AppShell'
import { useLang } from '../i18n'
import { incidentService, type TrackedReport } from '../services/incidentService'
import { analyticsService, type CityHealthSummary, type DepartmentScorecard } from '../services/analyticsService'

function PageFrame({
  title,
  kn,
  lead,
  children,
}: {
  title: string
  kn: string
  lead: ReactNode
  children: ReactNode
}) {
  return (
    <PublicShell>
      <div className="nc-page">
        <div className="nc-page-inner">
          <h1 className="nc-page-title">
            {title}
            <span className="kn">{kn}</span>
          </h1>
          <p className="nc-page-lead">{lead}</p>
          {children}
        </div>
      </div>
    </PublicShell>
  )
}

const SERVICES = [
  { icon: TrafficCone, en: 'Potholes and roads', kn: 'ರಸ್ತೆ ಹಾಗೂ ಗುಂಡಿ', to: '/report', blurb: 'Report a broken stretch so it can be routed to roads.' },
  { icon: Recycle, en: 'Garbage and waste', kn: 'ಕಸ ಸಂಗ್ರಹ', to: '/report', blurb: 'Missed pickup, dumping, or overflowing bins.' },
  { icon: Lightbulb, en: 'Street lights', kn: 'ಬೀದಿ ದೀಪ', to: '/report', blurb: 'Dark stretches and lights that stay on by day.' },
  { icon: Droplets, en: 'Water leakage', kn: 'ನೀರಿನ ಸೋರಿಕೆ', to: '/report', blurb: 'Leaks, low pressure, and contaminated supply.' },
  { icon: Waves, en: 'Drains and flooding', kn: 'ಚರಂಡಿ', to: '/report', blurb: 'Blocked storm drains before the next rain.' },
  { icon: Trees, en: 'Parks and trees', kn: 'ಉದ್ಯಾನಗಳು', to: '/report', blurb: 'Fallen branches, unsafe parks, and horticulture work.' },
]

export function ServicesPage() {
  const { lang } = useLang()
  return (
    <PageFrame
      title={lang === 'kn' ? 'ಸೇವೆಗಳು' : 'Services'}
      kn={lang === 'kn' ? 'ನಾಗರಿಕ ಸೇವೆಗಳು' : 'Civic services'}
      lead={lang === 'kn'
        ? 'ಒಂದೇ ವಿನಂತಿ ಫಾರ್ಮ್. ವಿಷಯವನ್ನು ಆರಿಸಿ, ಸ್ಥಳ ಸೇರಿಸಿ, ಫೋಟೋ ಹಾಕಿ.'
        : 'One request form for every civic service. Pick the issue, add a place, and attach a photo if you have one.'}
    >
      <div className="nc-cards cols-3">
        {SERVICES.map(({ icon: Icon, en, kn, to, blurb }) => (
          <Link key={en} to={to} className="nc-service">
            <Icon size={20} color="#7B1A33" />
            <h3>{lang === 'kn' ? kn : en}</h3>
            <p>{lang === 'kn' ? kn : blurb}</p>
          </Link>
        ))}
      </div>
    </PageFrame>
  )
}

const TRACK_STEPS = [
  { en: 'Submitted', kn: 'ಸಲ್ಲಿಕೆ' },
  { en: 'Under review', kn: 'ಪರಿಶೀಲನೆ' },
  { en: 'In progress', kn: 'ಪ್ರಗತಿಯಲ್ಲಿ' },
  { en: 'Resolved', kn: 'ಬಗೆಹರಿದಿದೆ' },
]

/** Drop empty or broken query values such as the literal "undefined". */
function trackingIdFromQuery(raw: string | null): string {
  const value = (raw ?? '').trim()
  if (!value || value.toLowerCase() === 'undefined' || value.toLowerCase() === 'null') return ''
  return value.toUpperCase()
}

/** Index of the step currently active for a public incident status. */
function trackStepIndex(status: string): number {
  if (status === 'resolved' || status === 'closed') return 3
  if (status === 'in_progress') return 2
  return 1
}

export function TrackPage() {
  const { lang } = useLang()
  const [params, setParams] = useSearchParams()
  const initial = trackingIdFromQuery(params.get('id'))
  const [code, setCode] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<TrackedReport | null>(null)

  const lookup = useCallback(async (value: string) => {
    setBusy(true)
    setError(null)
    setReport(null)
    try {
      setReport(await incidentService.trackByTrackingId(value))
    } catch (err) {
      const status = (err as { response?: { status?: number } }).response?.status
      setError(status === 404
        ? (lang === 'kn'
          ? 'ಈ ಟ್ರ್ಯಾಕಿಂಗ್ ಐಡಿಗೆ ಯಾವುದೇ ವರದಿ ಸಿಗಲಿಲ್ಲ. ಐಡಿ ಸರಿಯಾಗಿ ಬರೆದಿದ್ದೀರಾ ಎಂದು ಪರಿಶೀಲಿಸಿ.'
          : 'No report matches that tracking ID. Check the code and try again.')
        : (lang === 'kn'
          ? 'ಸೇವೆ ಈಗ ಲಭ್ಯವಿಲ್ಲ. ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಪ್ರಯತ್ನಿಸಿ.'
          : 'The tracking service is unavailable right now. Please try again shortly.'))
    } finally {
      setBusy(false)
    }
  }, [lang])

  // Auto-run when the page is opened from a "Track this report" link.
  useEffect(() => {
    if (initial) void lookup(initial)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial])

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const value = code.trim()
    if (!value) return
    if (value === initial) void lookup(value)
    else setParams({ id: value })
  }

  const step = report ? trackStepIndex(report.status) : 0
  /** "work_order_created" -> "Work order created". */
  const sentenceCase = (raw: string): string => {
    const text = raw.replace(/_/g, ' ').trim()
    return text.charAt(0).toUpperCase() + text.slice(1)
  }

  return (
    <PageFrame
      title={lang === 'kn' ? 'ವಿನಂತಿ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ' : 'Track a request'}
      kn={lang === 'kn' ? 'ಸ್ಥಿತಿ ನೋಡಿ' : 'Follow your report'}
      lead={lang === 'kn' ? (
        <>ದೂರು ದಾಖಲಿಸಿದಾಗ ಸಿಕ್ಕ ಟ್ರ್ಯಾಕಿಂಗ್ ಐಡಿ (ಉದಾ. <span className="nowrap">NC-7K4P-9XQ2</span>) ಹಾಕಿ. ಲಾಗಿನ್ ಅಗತ್ಯವಿಲ್ಲ. ಇತರರ ವೈಯಕ್ತಿಕ ಮಾಹಿತಿ ಕಾಣಿಸುವುದಿಲ್ಲ.</>
      ) : (
        <>Enter the tracking ID you received when you reported the issue (for example <span className="nowrap">NC-7K4P-9XQ2</span>). No login needed, and other reporters’ personal details stay hidden.</>
      )}
    >
      <form className="nc-form" onSubmit={onSubmit}>
        <label className="label" htmlFor="track-id">{lang === 'kn' ? 'ಟ್ರ್ಯಾಕಿಂಗ್ ಐಡಿ' : 'Tracking ID'}</label>
        <input
          id="track-id"
          className="input track-input"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="NC-XXXX-XXXX"
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          required
        />
        <button className="btn btn-primary" style={{ marginTop: 12 }} disabled={busy || code.trim().length < 6} type="submit">
          {busy ? <Loader2 size={16} className="spinner" /> : <Search size={16} />}
          {lang === 'kn' ? 'ಸ್ಥಿತಿ ನೋಡಿ' : 'Check status'}
        </button>
        {error && <p className="error-msg" role="alert">{error}</p>}
      </form>

      {report && (
        <article className="nc-panel track-result">
          <div className="track-head">
            <div>
              <p className="track-code">{report.tracking_id}</p>
              <h2>{report.title}</h2>
              <p className="lede">
                {report.category.replace(/_/g, ' ')} · {lang === 'kn' ? 'ಸಲ್ಲಿಸಿದ ದಿನ' : 'Submitted'}{' '}
                {new Date(report.submitted_at).toLocaleDateString(lang === 'kn' ? 'kn-IN' : 'en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
              </p>
            </div>
          </div>

          <ol className="track-steps" aria-label="Progress">
            {TRACK_STEPS.map((s, i) => (
              <li key={s.en} className={i < step ? 'done' : i === step ? 'now' : undefined}>
                <span className="track-dot">{i < step ? <CheckCircle2 size={16} /> : i + 1}</span>
                <span className="track-label">{lang === 'kn' ? s.kn : s.en}</span>
              </li>
            ))}
          </ol>

          <div className="nc-step">
            <div className="nc-step-ico"><Building2 size={16} /></div>
            <div>
              <h3>{report.responsible_department || (lang === 'kn' ? 'ಇಲಾಖೆ ನಿಗದಿಯಾಗುತ್ತಿದೆ' : 'Department being assigned')}</h3>
              <p>{report.what_happens_next}</p>
            </div>
          </div>
          <div className="nc-step">
            <div className="nc-step-ico"><MapPin size={16} /></div>
            <div>
              <h3>
                {lang === 'kn'
                  ? `${report.reporter_count} ನಾಗರಿಕರು ವರದಿ ಮಾಡಿದ್ದಾರೆ`
                  : `${report.reporter_count} ${report.reporter_count === 1 ? 'citizen has' : 'citizens have'} reported this`}
              </h3>
              <p>{lang === 'kn' ? 'ನಿರೀಕ್ಷಿತ ಅವಧಿ' : 'Expected by'} {new Date(report.expected_by).toLocaleDateString(lang === 'kn' ? 'kn-IN' : 'en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</p>
            </div>
          </div>
          {report.timeline.map((event) => (
            <div className="nc-step" key={`${event.created_at}-${event.event}`}>
              <div className="nc-step-ico"><Route size={16} /></div>
              <div>
                <h3>{sentenceCase(event.event)}</h3>
                <p>{event.note.replace(/_/g, ' ')}</p>
              </div>
            </div>
          ))}
        </article>
      )}
    </PageFrame>
  )
}
const AGENT_STEPS = [
  { icon: ScanSearch, en: 'Detect', kn: 'ಪತ್ತೆ', text: 'Reads the report text and photo and names the issue type.' },
  { icon: Route, en: 'Validate', kn: 'ಪರಿಶೀಲನೆ', text: 'Checks that a place and a usable description are present.' },
  { icon: Bot, en: 'Duplicate resolution', kn: 'ನಕಲು ಪರಿಹಾರ', text: 'Links a repeat report to the existing incident instead of opening a second work order.' },
  { icon: Building2, en: 'Route', kn: 'ಮಾರ್ಗ', text: 'Sends a new incident to the department that owns that kind of work.' },
  { icon: MapPin, en: 'Action', kn: 'ಕ್ರಮ', text: 'Opens one work order for a new or reopened incident and tells the reporter.' },
]

export function AgentsPage() {
  const { lang } = useLang()
  return (
    <PageFrame
      title={lang === 'kn' ? 'ಏಐ ಏಜೆಂಟ್‌ಗಳು' : 'AI agents'}
      kn={lang === 'kn' ? 'ಒಟ್ಟಿಗೆ ಕೆಲಸ ಮಾಡುವ ಏಜೆಂಟ್‌ಗಳು' : 'How the pipeline collaborates'}
      lead={lang === 'kn'
        ? 'ಪ್ರತಿ ದೂರು ಒಂದೇ ಸರಣಿಯಲ್ಲಿ ಹಾದುಹೋಗುತ್ತದೆ. ನಕಲು ದೂರು ಹೊಸ ಕೆಲಸದ ಆದೇಶವಾಗುವುದಿಲ್ಲ.'
        : 'Every report walks the same pipeline. A duplicate becomes a link on the existing incident, not a second work order.'}
    >
      <div className="nc-cards cols-2">
        {AGENT_STEPS.map(({ icon: Icon, en, kn, text }) => (
          <article key={en} className="nc-service">
            <Icon size={20} color="#7B1A33" />
            <h3>{lang === 'kn' ? kn : en}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
    </PageFrame>
  )
}

const DEPT_FALLBACK = [
  { name: 'Roads and Infrastructure', kn: 'ರಸ್ತೆ ಮತ್ತು ಮೂಲಸೌಕರ್ಯ', code: 'ROADS' },
  { name: 'Solid Waste Management', kn: 'ಘನ ತ್ಯಾಜ್ಯ', code: 'SWM' },
  { name: 'Street Lighting', kn: 'ಬೀದಿ ದೀಪ', code: 'LIGHT' },
  { name: 'Water Supply', kn: 'ನೀರು ಸರಬರಾಜು', code: 'WATER' },
  { name: 'Storm Water Drains', kn: 'ಮಳೆನೀರು ಚರಂಡಿ', code: 'DRAIN' },
  { name: 'Parks and Horticulture', kn: 'ಉದ್ಯಾನ', code: 'PARKS' },
]

export function DepartmentsPage() {
  const { lang } = useLang()
  const [rows, setRows] = useState<DepartmentScorecard[] | null>(null)

  useEffect(() => {
    analyticsService.getDepartmentScorecard()
      .then(setRows)
      .catch(() => setRows(null))
  }, [])

  return (
    <PageFrame
      title={lang === 'kn' ? 'ಇಲಾಖೆಗಳು' : 'Departments'}
      kn={lang === 'kn' ? 'ಯಾರು ಕೆಲಸ ಮಾಡುತ್ತಾರೆ' : 'Who owns the work'}
      lead={lang === 'kn'
        ? 'ಪ್ರತಿ ಘಟನೆ ಒಂದು ಇಲಾಖೆಗೆ ಹೋಗುತ್ತದೆ. ಅಂಕಿಗಳು ಸೇವೆ ಲಭ್ಯವಿದ್ದಾಗ ನೇರವಾಗಿ ಬರುತ್ತವೆ.'
        : 'Each incident is owned by one department. Live workload numbers appear when the analytics service is available.'}
    >
      <div className="nc-cards cols-3">
        {(rows && rows.length > 0 ? rows.map((d) => ({
          key: d.department_id,
          title: d.name,
          code: d.code,
          detail: `${d.active_cases} active · ${d.resolved_cases} resolved`,
        })) : DEPT_FALLBACK.map((d) => ({
          key: d.code,
          title: lang === 'kn' ? d.kn : d.name,
          code: d.code,
          detail: lang === 'kn' ? 'ನೇರ ಅಂಕಿ ಲಭ್ಯವಿಲ್ಲ' : 'Live counts unavailable',
        }))).map((d) => (
          <article key={d.key} className="nc-service">
            <Building2 size={20} color="#7B1A33" />
            <h3>{d.title}</h3>
            <p>{d.code}</p>
            <p>{d.detail}</p>
          </article>
        ))}
      </div>
    </PageFrame>
  )
}

export function InsightsPage() {
  const { lang } = useLang()
  const [summary, setSummary] = useState<CityHealthSummary | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    analyticsService.getSummary()
      .then(setSummary)
      .catch(() => setFailed(true))
  }, [])

  return (
    <PageFrame
      title={lang === 'kn' ? 'ನಗರದ ಸ್ಥಿತಿ' : 'City insights'}
      kn={lang === 'kn' ? 'ಬೆಂಗಳೂರು ಒಂದು ನೋಟ' : 'Bengaluru at a glance'}
      lead={lang === 'kn'
        ? 'ಒಟ್ಟು ದೂರು, ಪ್ರಗತಿ ಮತ್ತು ಬಗೆಹರಿಕೆ. ನಕ್ಷೆಯ ವಿವರವಾದ ನೋಟಕ್ಕೆ ವಿಶ್ಲೇಷಣೆ ಪುಟ ತೆರೆಯಿರಿ.'
        : 'Totals, work in progress, and resolutions. Open the full analytics view for the hotspot map.'}
    >
      <div className="nc-cards cols-3">
        <article className="nc-service">
          <h3>{summary ? summary.total_grievances.toLocaleString() : '—'}</h3>
          <p>{lang === 'kn' ? 'ಒಟ್ಟು ದೂರುಗಳು' : 'Total complaints'}</p>
        </article>
        <article className="nc-service">
          <h3>{summary ? summary.in_progress_count.toLocaleString() : '—'}</h3>
          <p>{lang === 'kn' ? 'ಪ್ರಗತಿಯಲ್ಲಿ' : 'In progress'}</p>
        </article>
        <article className="nc-service">
          <h3>{summary ? summary.resolved_count.toLocaleString() : '—'}</h3>
          <p>{lang === 'kn' ? 'ಬಗೆಹರಿದಿದೆ' : 'Resolved'}</p>
        </article>
      </div>
      {summary && (
        <div className="nc-cards cols-2">
          {Object.entries(summary.category_distribution).map(([name, count]) => (
            <article key={name} className="nc-service">
              <h3>{name.replace(/_/g, ' ')}</h3>
              <p>{count.toLocaleString()}</p>
            </article>
          ))}
        </div>
      )}
      {failed && <p className="nc-note">{lang === 'kn' ? 'ನಗರ ಸೇವೆ ಈಗ ಲಭ್ಯವಿಲ್ಲ.' : 'The city analytics service is not reachable right now.'}</p>}
      <div style={{ marginTop: 18 }}>
        <Link to="/analytics" className="btn btn-primary">{lang === 'kn' ? 'ಪೂರ್ಣ ನಕ್ಷೆ' : 'Open full map'}</Link>
      </div>
    </PageFrame>
  )
}
