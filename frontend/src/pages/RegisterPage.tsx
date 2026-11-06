import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Shield, Mail, Lock, User, Phone, Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { PublicShell } from '../components/AppShell'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { register, isLoading, error, clearError } = useAuthStore()

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    password: '',
    confirm: '',
  })
  const [showPw, setShowPw] = useState(false)
  const [validationError, setValidationError] = useState('')

  const update = (field: string, value: string) => {
    setForm((f) => ({ ...f, [field]: value }))
    clearError()
    setValidationError('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (form.password !== form.confirm) {
      setValidationError('Passwords do not match.')
      return
    }
    if (form.password.length < 8) {
      setValidationError('Password must be at least 8 characters.')
      return
    }
    try {
      await register({
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        phone: form.phone || undefined,
      })
      navigate('/dashboard', { replace: true })
    } catch { /* error in store */ }
  }

  const displayError = validationError || error

  return (
    <PublicShell>
      <div className="min-h-[calc(100dvh-120px)] flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="w-12 h-12 rounded-2xl bg-blue-900 flex items-center justify-center mx-auto mb-4 shadow-lg" aria-hidden="true">
              <Shield size={24} className="text-white" />
            </div>
            <h1 className="text-heading-1 text-gray-900">Create account</h1>
            <p className="text-gray-500 text-sm mt-1">Join Namma Civic and report a Bengaluru issue</p>
          </div>

          {/* Card */}
          <div className="card p-6 sm:p-7">
            {displayError && (
              <div className="alert alert-error mb-5 text-sm">
                <AlertCircle size={16} className="shrink-0" aria-hidden="true" />
                <span>{displayError}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {/* Name */}
              <div>
                <label htmlFor="reg-name" className="label">Full name <span className="text-red-600" aria-hidden="true">*</span></label>
                <div className="relative">
                  <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true" />
                  <input
                    id="reg-name"
                    type="text"
                    value={form.full_name}
                    onChange={(e) => update('full_name', e.target.value)}
                    required
                    autoComplete="name"
                    placeholder="Priya Sharma"
                    className="input pl-9"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label htmlFor="reg-email" className="label">Email address <span className="text-red-600" aria-hidden="true">*</span></label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true" />
                  <input
                    id="reg-email"
                    type="email"
                    value={form.email}
                    onChange={(e) => update('email', e.target.value)}
                    required
                    autoComplete="email"
                    placeholder="you@example.com"
                    className="input pl-9"
                  />
                </div>
              </div>

              {/* Phone */}
              <div>
                <label htmlFor="reg-phone" className="label">Phone <span className="text-gray-400 text-xs font-normal">(optional)</span></label>
                <div className="relative">
                  <Phone size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true" />
                  <input
                    id="reg-phone"
                    type="tel"
                    value={form.phone}
                    onChange={(e) => update('phone', e.target.value)}
                    autoComplete="tel"
                    placeholder="+91 98765 43210"
                    className="input pl-9"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label htmlFor="reg-pw" className="label">Password <span className="text-red-600" aria-hidden="true">*</span></label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true" />
                  <input
                    id="reg-pw"
                    type={showPw ? 'text' : 'password'}
                    value={form.password}
                    onChange={(e) => update('password', e.target.value)}
                    required
                    minLength={8}
                    autoComplete="new-password"
                    placeholder="Min. 8 characters"
                    className="input pl-9 pr-10"
                    aria-describedby="pw-hint"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    aria-label={showPw ? 'Hide password' : 'Show password'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-1"
                  >
                    {showPw ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                  </button>
                </div>
                <p id="pw-hint" className="hint">Minimum 8 characters</p>
              </div>

              {/* Confirm */}
              <div>
                <label htmlFor="reg-confirm" className="label">Confirm password <span className="text-red-600" aria-hidden="true">*</span></label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true" />
                  <input
                    id="reg-confirm"
                    type={showPw ? 'text' : 'password'}
                    value={form.confirm}
                    onChange={(e) => update('confirm', e.target.value)}
                    required
                    autoComplete="new-password"
                    placeholder="Repeat password"
                    className={`input pl-9 ${form.confirm && form.password !== form.confirm ? 'error' : ''}`}
                  />
                </div>
              </div>

              <button
                id="register-submit-btn"
                type="submit"
                disabled={isLoading || !form.full_name || !form.email || !form.password || !form.confirm}
                className="btn btn-primary w-full mt-2"
              >
                {isLoading ? (
                  <><Loader2 size={16} className="spinner" aria-hidden="true" /> Creating account…</>
                ) : 'Create Account'}
              </button>
            </form>
          </div>

          <p className="text-center text-sm text-gray-500 mt-5">
            Already have an account?{' '}
            <Link to="/login" className="text-blue-700 font-semibold hover:text-blue-900 transition-colors">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </PublicShell>
  )
}
