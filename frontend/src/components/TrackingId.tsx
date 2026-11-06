import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, Copy, Search } from 'lucide-react'

interface TrackingIdProps {
  /** Citizen-facing code such as NC-7K4P-9XQ2. */
  code: string
  /** "card" is the large celebratory version; "inline" is the compact chip. */
  variant?: 'card' | 'inline'
  /** Show a link to the public Track page pre-filled with this code. */
  showTrackLink?: boolean
}

/** Copy text with a fallback for browsers/contexts without the async clipboard API. */
async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* fall through to the legacy path */
  }
  try {
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(area)
    return ok
  } catch {
    return false
  }
}

export function TrackingId({ code, variant = 'inline', showTrackLink = false }: TrackingIdProps) {
  const [copied, setCopied] = useState(false)
  const value = (code ?? '').trim()
  if (!value || value.toLowerCase() === 'undefined') return null

  const onCopy = async () => {
    if (await copyText(code)) {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    }
  }

  if (variant === 'inline') {
    return (
      <span className="tid-inline">
        <span className="tid-label">ID</span>
        <span className="tid-code">{code}</span>
        <button type="button" className="tid-copy-mini" onClick={onCopy} aria-label={`Copy tracking ID ${code}`}>
          {copied ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
        </button>
      </span>
    )
  }

  return (
    <div className="tid-card" role="group" aria-label="Your tracking ID">
      <p className="tid-card-title">Your tracking ID</p>
      <p className="tid-card-code" data-testid="tracking-id">{code}</p>
      <p className="tid-card-hint">Save this code. Anyone with it can follow this report&apos;s status, no login needed.</p>
      <div className="tid-card-actions">
        <button type="button" className="btn btn-accent" onClick={onCopy}>
          {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
          {copied ? 'Copied' : 'Copy ID'}
        </button>
        {showTrackLink && (
          <Link className="btn btn-secondary" to={`/track?id=${encodeURIComponent(code)}`}>
            <Search size={16} aria-hidden="true" /> Track this report
          </Link>
        )}
      </div>
    </div>
  )
}
