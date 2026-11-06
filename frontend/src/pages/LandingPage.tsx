import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart3,
  Bot,
  Building2,
  CheckCircle2,
  ClipboardList,
  GitMerge,
  Megaphone,
  ScanSearch,
  Route,
} from 'lucide-react'
import { PublicShell } from '../components/AppShell'
import { useLang } from '../i18n'
import { useAuthStore } from '../store/authStore'
import { analyticsService, type CityHealthSummary } from '../services/analyticsService'
import { complaintService, type Complaint } from '../services/complaintService'

const HERO_PHOTOS = [
  { src: '/hero/bengaluru-1.jpg', alt: 'Vidhana Soudha and the Namma Metro at golden hour' },
  { src: '/hero/bengaluru-2.jpg', alt: 'Vidhana Soudha, a tree-lined road and the metro viaduct' },
  { src: '/hero/bengaluru-3.jpg', alt: 'Bengaluru skyline with Vidhana Soudha and the Karnataka flag' },
]

function HeroPhoto() {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % HERO_PHOTOS.length), 6000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className="nc-hero-photo">
      {HERO_PHOTOS.map((photo, i) => (
        <img
          key={photo.src}
          src={photo.src}
          alt={i === index ? photo.alt : ''}
          aria-hidden={i === index ? undefined : true}
          className={i === index ? 'on' : undefined}
        />
      ))}
      <div className="nc-hero-dots" role="group" aria-label="Choose banner photo">
        {HERO_PHOTOS.map((photo, i) => (
          <button
            key={photo.src}
            type="button"
            className={i === index ? 'on' : undefined}
            aria-label={`Show photo ${i + 1}`}
            aria-pressed={i === index}
            onClick={() => setIndex(i)}
          />
        ))}
      </div>
    </div>
  )
}
function CityBlob() {
  return (
    <svg viewBox="0 0 220 180" width="100%" height="150" aria-hidden="true">
      <path
        d="M40 70 C30 40 70 18 110 28 C150 10 190 36 188 72 C210 90 196 130 160 142 C130 168 70 160 48 136 C18 124 16 96 40 70 Z"
        fill="#9a2744"
        stroke="#f6c445"
        strokeWidth="3"
      />
      <circle cx="92" cy="78" r="5" fill="#ff5a5a" />
      <circle cx="124" cy="96" r="5" fill="#f6c445" />
      <circle cx="108" cy="118" r="4" fill="#7dffb2" />
      <circle cx="146" cy="74" r="4" fill="#ff5a5a" />
      <circle cx="78" cy="108" r="4" fill="#f6c445" />
    </svg>
  )
}

const EXAMPLES = [
  {
    id: 'INC-7842',
    title: 'Pothole Repair',
    place: 'Koramangala, 80ft Road',
    status: 'progress' as const,
    tone: '#c4a574',
  },
  {
    id: 'INC-7701',
    title: 'Garbage Clearance',
    place: 'BTM Layout',
    status: 'done' as const,
    tone: '#6aaa78',
  },
]

export default function LandingPage() {
  const { t } = useLang()
  const { isAuthenticated, user } = useAuthStore()
  const myHref = user?.role === 'admin' ? '/admin' : user?.role === 'officer' ? '/officer' : '/dashboard'
  const [summary, setSummary] = useState<CityHealthSummary | null>(null)
  const [mine, setMine] = useState<Complaint[]>([])

  useEffect(() => {
    let alive = true
    analyticsService.getSummary()
      .then((data) => { if (alive) setSummary(data) })
      .catch(() => { if (alive) setSummary(null) })
    if (isAuthenticated) {
      complaintService.getMyComplaints(1, 2)
        .then((res) => { if (alive) setMine(res.items || []) })
        .catch(() => { if (alive) setMine([]) })
    }
    return () => { alive = false }
  }, [isAuthenticated])

  const steps = [
    { icon: ScanSearch, title: t('detect'), sub: t('detectSub') },
    { icon: GitMerge, title: t('merge'), sub: t('mergeSub') },
    { icon: Route, title: t('route'), sub: t('routeSub') },
    { icon: CheckCircle2, title: t('resolve'), sub: t('resolveSub') },
  ]

  const flow = [t('submitted'), t('aiReview'), t('assigned'), t('inProgress'), t('resolved')]

  return (
    <PublicShell>
      <section className="nc-hero" aria-labelledby="hero-heading">
        <div className="nc-hero-copy">
          <h1 id="hero-heading" className="nc-hero-title">{t('heroTitle')}</h1>
          <p className="nc-hero-sub">{t('heroSub')}</p>
        </div>
        <HeroPhoto />
      </section>

      <div className="nc-rail-wrap">
        <nav className="nc-rail" aria-label="Quick actions">
          <Link to="/report" className="nc-rail-report">
            <span className="nc-rail-ico"><Megaphone size={18} /></span>
            <span className="nc-rail-label">
              <span className="kn">ದೂರು ದಾಖಲಿಸಿ</span>
              <strong>{t('report')}</strong>
            </span>
          </Link>
          <Link to={myHref} className="nc-rail-dark">
            <span className="nc-rail-ico"><ClipboardList size={18} /></span>
            <span className="nc-rail-label">
              <span className="kn">ವಿನಂತಿಗಳು</span>
              <strong>{t('myRequests')}</strong>
            </span>
          </Link>
          <Link to="/agents" className="nc-rail-dark">
            <span className="nc-rail-ico"><Bot size={18} /></span>
            <span className="nc-rail-label">
              <span className="kn">ಏಜೆಂಟ್‌ಗಳು</span>
              <strong>{t('agents')}</strong>
            </span>
          </Link>
          <Link to="/insights" className="nc-rail-dark">
            <span className="nc-rail-ico"><BarChart3 size={18} /></span>
            <span className="nc-rail-label">
              <span className="kn">ನಗರದ ಸ್ಥಿತಿ</span>
              <strong>{t('insights')}</strong>
            </span>
          </Link>
          <Link to="/departments" className="nc-rail-dark">
            <span className="nc-rail-ico"><Building2 size={18} /></span>
            <span className="nc-rail-label">
              <span className="kn">ಇಲಾಖೆಗಳು</span>
              <strong>{t('departments')}</strong>
            </span>
          </Link>
        </nav>
      </div>

      <section className="nc-home">
        <div className="nc-grid">
          <article className="nc-panel">
            <h2>{t('agentsTitle')}</h2>
            <p className="lede">{t('agentsLede')}</p>
            {steps.map(({ icon: Icon, title, sub }) => (
              <div className="nc-step" key={title}>
                <div className="nc-step-ico"><Icon size={18} /></div>
                <div>
                  <h3>{title}</h3>
                  <p>{sub}</p>
                </div>
              </div>
            ))}
          </article>

          <article className="nc-panel">
            <div className="nc-track-head">
              <h2>{t('live')}</h2>
            </div>
            <div className="nc-flow" aria-hidden="true">
              {flow.map((label, i) => (
                <div className="nc-flow-step" key={label}>
                  <span className={`nc-dot ${i < 2 ? 'done' : i === 2 ? 'on' : ''}`}>
                    {i < 2 ? <CheckCircle2 size={14} /> : <span style={{ width: 8, height: 8, borderRadius: 99, background: 'currentColor', display: 'block' }} />}
                  </span>
                  <small>{label}</small>
                </div>
              ))}
            </div>
            <div className="nc-track-head">
              <h2>{t('recent')}</h2>
              <Link className="nc-linkish" to={isAuthenticated ? myHref : '/track'}>{t('viewAll')}</Link>
            </div>
            {mine.length > 0 ? mine.map((c) => (
              <Link key={c.id} to={`/complaints/${c.id}`} className="nc-req" style={{ textDecoration: 'none', color: 'inherit' }}>
                <span className="nc-thumb" />
                <span>
                  <strong>{c.title}</strong>
                  <p>{c.address || c.category.replace(/_/g, ' ')}</p>
                </span>
                <span className={c.status === 'resolved' ? 'nc-chip nc-chip-done' : 'nc-chip nc-chip-progress'}>
                  {c.status.replace(/_/g, ' ')}
                </span>
              </Link>
            )) : EXAMPLES.map((item) => (
              <div className="nc-req" key={item.id}>
                <span className="nc-thumb" style={{ background: item.tone }} />
                <span>
                  <strong>{item.id} — {item.title}</strong>
                  <p>{item.place}</p>
                </span>
                <span className={item.status === 'done' ? 'nc-chip nc-chip-done' : 'nc-chip nc-chip-progress'}>
                  {item.status === 'done' ? t('resolved') : t('inProgress')}
                </span>
              </div>
            ))}
            {mine.length === 0 && <p className="nc-note">{t('sampleNote')}</p>}
          </article>

          <div>
            <article className="nc-map-card">
              <div className="nc-map-head">
                <h2>{t('mapTitle')}</h2>
                <span className="nc-live" style={summary ? undefined : { background: '#F6C445', color: '#4A1020' }}>
                  <i style={summary ? undefined : { background: '#4A1020' }} /> {summary ? 'Live' : 'Sample'}
                </span>
              </div>
              <div className="nc-map-body">
                <CityBlob />
                <div className="nc-legend">
                  <div><span className="nc-swatch" style={{ background: '#ff5a5a' }} /> {t('high')}</div>
                  <div><span className="nc-swatch" style={{ background: '#f6c445' }} /> {t('medium')}</div>
                  <div><span className="nc-swatch" style={{ background: '#7dffb2' }} /> {t('low')}</div>
                </div>
              </div>
              <Link className="nc-viewmap" to="/insights">{t('viewMap')} →</Link>
            </article>

            <article className="nc-glance">
              <h3>{t('glance')}</h3>
              <div className="nc-stats">
                <div className="nc-stat">
                  <b>{summary ? summary.total_grievances.toLocaleString() : '—'}</b>
                  <span>{t('total')}</span>
                </div>
                <div className="nc-stat">
                  <b>{summary ? summary.in_progress_count.toLocaleString() : '—'}</b>
                  <span>{t('inProgStat')}</span>
                </div>
                <div className="nc-stat">
                  <b>{summary ? summary.resolved_count.toLocaleString() : '—'}</b>
                  <span>{t('resolvedStat')}</span>
                </div>
                <div className="nc-stat">
                  <b>{summary ? `${Math.round(summary.resolution_rate)}%` : '—'}</b>
                  <span>{t('avg')}</span>
                </div>
              </div>
              {!summary && <p className="nc-note">{t('sampleNote')}</p>}
            </article>
          </div>
        </div>
      </section>
    </PublicShell>
  )
}


