// ── UI Primitive Components ──────────────────────────────────
// Button, Badge, Spinner, Skeleton, Alert, Modal — all in one barrel export

import React, { useEffect, useRef } from 'react'
import { X, AlertCircle, CheckCircle2, Info, AlertTriangle, Loader2 } from 'lucide-react'

// ── Button ───────────────────────────────────────────────────
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: React.ReactNode
  iconRight?: React.ReactNode
  fullWidth?: boolean
  as?: 'button' | 'a'
  href?: string
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  iconRight,
  fullWidth = false,
  children,
  disabled,
  className = '',
  ...props
}) => {
  const cls = [
    'btn',
    `btn-${variant}`,
    size !== 'md' ? `btn-${size}` : '',
    fullWidth ? 'w-full' : '',
    className,
  ].filter(Boolean).join(' ')

  return (
    <button
      {...props}
      className={cls}
      disabled={disabled || loading}
      aria-busy={loading}
    >
      {loading ? (
        <Loader2 size={size === 'sm' ? 14 : 16} className="spinner shrink-0" aria-hidden="true" />
      ) : icon ? (
        <span className="shrink-0" aria-hidden="true">{icon}</span>
      ) : null}
      {children}
      {iconRight && !loading && (
        <span className="shrink-0" aria-hidden="true">{iconRight}</span>
      )}
    </button>
  )
}

// ── Badge ────────────────────────────────────────────────────
type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'primary'

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  dot?: boolean
  className?: string
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  children,
  dot = false,
  className = '',
}) => (
  <span className={`badge badge-${variant} ${className}`}>
    {dot && (
      <span
        className={`w-1.5 h-1.5 rounded-full shrink-0 ${
          variant === 'success' ? 'bg-green-600' :
          variant === 'warning' ? 'bg-amber-600' :
          variant === 'danger'  ? 'bg-red-600' :
          variant === 'info'    ? 'bg-blue-600' :
          variant === 'primary' ? 'bg-white' : 'bg-gray-500'
        }`}
        aria-hidden="true"
      />
    )}
    {children}
  </span>
)

// ── Spinner ──────────────────────────────────────────────────
interface SpinnerProps {
  size?: number
  className?: string
  label?: string
}

export const Spinner: React.FC<SpinnerProps> = ({
  size = 20,
  className = '',
  label = 'Loading…',
}) => (
  <span role="status" aria-label={label} className={`inline-flex ${className}`}>
    <Loader2 size={size} className="spinner" style={{ color: '#7B1A33' }} aria-hidden="true" />
    <span className="sr-only">{label}</span>
  </span>
)

// ── Skeleton ─────────────────────────────────────────────────
interface SkeletonProps {
  className?: string
  height?: string | number
  width?: string | number
}

export const Skeleton: React.FC<SkeletonProps> = ({ className = '', height, width }) => (
  <div
    className={`skeleton ${className}`}
    style={{ height, width }}
    aria-hidden="true"
  />
)

// ── Alert ────────────────────────────────────────────────────
type AlertVariant = 'error' | 'warning' | 'info' | 'success'

interface AlertProps {
  variant: AlertVariant
  children: React.ReactNode
  className?: string
  onClose?: () => void
}

const ALERT_ICONS: Record<AlertVariant, React.ElementType> = {
  error:   AlertCircle,
  warning: AlertTriangle,
  info:    Info,
  success: CheckCircle2,
}

export const Alert: React.FC<AlertProps> = ({
  variant,
  children,
  className = '',
  onClose,
}) => {
  const Icon = ALERT_ICONS[variant]
  return (
    <div
      role="alert"
      className={`alert alert-${variant} ${className}`}
    >
      <Icon size={16} className="shrink-0 mt-px" aria-hidden="true" />
      <div className="flex-1 min-w-0">{children}</div>
      {onClose && (
        <button
          onClick={onClose}
          aria-label="Dismiss alert"
          className="icon-btn shrink-0 -mr-1 -mt-1 self-start"
        >
          <X size={14} aria-hidden="true" />
        </button>
      )}
    </div>
  )
}

// ── Modal ────────────────────────────────────────────────────
interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
  footer?: React.ReactNode
  maxWidth?: 'sm' | 'md' | 'lg'
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  footer,
}) => {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    setTimeout(() => panelRef.current?.focus(), 50)
    return () => {
      document.body.style.overflow = prev
      document.removeEventListener('keydown', handler)
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        ref={panelRef}
        className="modal-panel"
        tabIndex={-1}
        style={{ outline: 'none' }}
      >
        {/* Handle bar (mobile) */}
        <div className="flex justify-center pt-3 pb-1 sm:hidden" aria-hidden="true">
          <div className="w-10 h-1 rounded-full bg-gray-300" />
        </div>

        {/* Header */}
        {title && (
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
            <h2 className="text-heading-2 text-gray-900">{title}</h2>
            <button
              onClick={onClose}
              aria-label="Close modal"
              className="icon-btn -mr-1"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto overscroll-contain">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="px-5 py-4 border-t border-gray-200 shrink-0 bg-gray-50">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Card ─────────────────────────────────────────────────────
interface CardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
  onClick?: () => void
}

const PADDING_MAP = {
  none: '',
  sm:   'p-3',
  md:   'p-4 sm:p-5',
  lg:   'p-5 sm:p-6',
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  hover = false,
  padding = 'md',
  onClick,
}) => (
  <div
    className={`card ${hover ? 'card-hover' : ''} ${PADDING_MAP[padding]} ${className}`}
    onClick={onClick}
    role={onClick ? 'button' : undefined}
    tabIndex={onClick ? 0 : undefined}
    onKeyDown={onClick ? (e) => { if (e.key === 'Enter') onClick() } : undefined}
  >
    {children}
  </div>
)

// ── Input Field with label ────────────────────────────────────
interface InputFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string
  id: string
  error?: string
  hint?: string
  icon?: React.ReactNode
}

export const InputField: React.FC<InputFieldProps> = ({
  label,
  id,
  error,
  hint,
  icon,
  className = '',
  ...props
}) => (
  <div>
    <label htmlFor={id} className="label">
      {label}
      {props.required && <span className="text-red-600 ml-0.5" aria-hidden="true">*</span>}
    </label>
    <div className="relative">
      {icon && (
        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true">
          {icon}
        </div>
      )}
      <input
        id={id}
        className={`input ${icon ? 'pl-9' : ''} ${error ? 'error' : ''} ${className}`}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        {...props}
      />
    </div>
    {error && <p id={`${id}-error`} className="error-msg"><AlertCircle size={12} aria-hidden="true" />{error}</p>}
    {hint && !error && <p id={`${id}-hint`} className="hint">{hint}</p>}
  </div>
)

// ── Select Field ──────────────────────────────────────────────
interface SelectFieldProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  id: string
  error?: string
  options: Array<{ value: string; label: string }>
}

export const SelectField: React.FC<SelectFieldProps> = ({
  label,
  id,
  error,
  options,
  className = '',
  ...props
}) => (
  <div>
    <label htmlFor={id} className="label">
      {label}
      {props.required && <span className="text-red-600 ml-0.5" aria-hidden="true">*</span>}
    </label>
    <select
      id={id}
      className={`input select ${error ? 'error' : ''} ${className}`}
      aria-invalid={!!error}
      {...props}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
    {error && <p className="error-msg"><AlertCircle size={12} aria-hidden="true" />{error}</p>}
  </div>
)

// ── Textarea Field ────────────────────────────────────────────
interface TextareaFieldProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  id: string
  error?: string
  hint?: string
}

export const TextareaField: React.FC<TextareaFieldProps> = ({
  label,
  id,
  error,
  hint,
  className = '',
  ...props
}) => (
  <div>
    <label htmlFor={id} className="label">
      {label}
      {props.required && <span className="text-red-600 ml-0.5" aria-hidden="true">*</span>}
    </label>
    <textarea
      id={id}
      className={`input textarea ${error ? 'error' : ''} ${className}`}
      aria-invalid={!!error}
      aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
      {...props}
    />
    {error && <p id={`${id}-error`} className="error-msg"><AlertCircle size={12} aria-hidden="true" />{error}</p>}
    {hint && !error && <p id={`${id}-hint`} className="hint">{hint}</p>}
  </div>
)

// ── Stat Tile ─────────────────────────────────────────────────
interface StatTileProps {
  label: string
  value: string | number
  sub?: string
  icon?: React.ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger'
}

const STAT_VARIANTS = {
  default: { bg: '', label: 'text-gray-500', value: 'text-gray-900', icon: 'text-gray-400', border: '' },
  success: { bg: 'bg-green-50 border-green-100', label: 'text-green-700', value: 'text-green-900', icon: 'text-green-600', border: '' },
  warning: { bg: 'bg-amber-50 border-amber-100', label: 'text-amber-700', value: 'text-amber-900', icon: 'text-amber-600', border: '' },
  danger:  { bg: 'bg-red-50 border-red-100',     label: 'text-red-700',   value: 'text-red-900',   icon: 'text-red-600',   border: '' },
}

export const StatTile: React.FC<StatTileProps> = ({
  label,
  value,
  sub,
  icon,
  variant = 'default',
}) => {
  const v = STAT_VARIANTS[variant]
  return (
    <div className={`stat-tile ${v.bg}`} role="figure" aria-label={`${label}: ${value}`}>
      {icon && <div className={`mb-2 ${v.icon}`} aria-hidden="true">{icon}</div>}
      <div className={`text-2xl font-bold font-mono leading-none mb-1 ${v.value}`}>{value}</div>
      <div className={`text-xs font-semibold uppercase tracking-wide ${v.label}`}>{label}</div>
      {sub && <div className={`text-xs mt-0.5 ${v.label} opacity-80`}>{sub}</div>}
    </div>
  )
}

// ── SLA Bar ───────────────────────────────────────────────────
interface SlaBarProps {
  percentConsumed: number
  hoursRemaining: number
  status: 'ON_TRACK' | 'AT_RISK' | 'BREACHED' | 'RESOLVED'
  compact?: boolean
}

export const SlaBar: React.FC<SlaBarProps> = ({
  percentConsumed,
  hoursRemaining,
  status,
  compact = false,
}) => {
  const cls = status === 'BREACHED' ? 'sla-breached' : status === 'AT_RISK' ? 'sla-at-risk' : 'sla-on-track'
  const label =
    hoursRemaining < 0
      ? `${Math.abs(Math.round(hoursRemaining))}h overdue`
      : hoursRemaining < 1
      ? `${Math.round(hoursRemaining * 60)}m left`
      : `${Math.round(hoursRemaining)}h left`

  return (
    <div className={compact ? '' : 'flex flex-col gap-1'}>
      <div
        className="sla-track"
        role="progressbar"
        aria-valuenow={Math.min(100, percentConsumed)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`SLA: ${label}`}
      >
        <div
          className={`sla-fill ${cls}`}
          style={{ width: `${Math.min(100, percentConsumed)}%` }}
        />
      </div>
      {!compact && (
        <span className={`font-mono text-xs font-semibold ${
          status === 'BREACHED' ? 'text-red-600' :
          status === 'AT_RISK'  ? 'text-amber-600' : 'text-gray-500'
        }`}>
          {label}
        </span>
      )}
    </div>
  )
}

// ── Status Badge helper ───────────────────────────────────────
const STATUS_MAP: Record<string, { label: string; variant: BadgeVariant }> = {
  pending:     { label: 'Pending',     variant: 'warning' },
  analyzing:   { label: 'AI Review',   variant: 'info'    },
  verified:    { label: 'Verified',    variant: 'info'    },
  assigned:    { label: 'Assigned',    variant: 'neutral' },
  in_progress: { label: 'In Progress', variant: 'warning' },
  resolved:    { label: 'Resolved',    variant: 'success' },
  rejected:    { label: 'Rejected',    variant: 'danger'  },
}

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const cfg = STATUS_MAP[status] || { label: status, variant: 'neutral' as BadgeVariant }
  return <Badge variant={cfg.variant} dot>{cfg.label}</Badge>
}

// ── Priority Badge ────────────────────────────────────────────
const PRIORITY_MAP: Record<string, BadgeVariant> = {
  critical: 'danger',
  high:     'warning',
  medium:   'info',
  low:      'neutral',
}

export const PriorityBadge: React.FC<{ priority: string }> = ({ priority }) => (
  <Badge variant={PRIORITY_MAP[priority?.toLowerCase()] || 'neutral'}>
    {priority?.charAt(0).toUpperCase() + priority?.slice(1).toLowerCase()}
  </Badge>
)
