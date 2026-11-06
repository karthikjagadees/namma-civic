import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Shield, Mail, Lock, Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { PublicShell } from '../components/AppShell'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login, isLoading, error, clearError } = useAuthStore()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    try {
      await login(email, password)
      const currentUser = useAuthStore.getState().user
      if (currentUser?.role === 'officer') {
        navigate('/officer', { replace: true })
      } else if (currentUser?.role === 'admin') {
        navigate('/admin', { replace: true })
      } else {
        navigate('/dashboard', { replace: true })
      }
    } catch { /* error set in store */ }
  }

  const fillDemo = (role: 'citizen' | 'officer' | 'admin') => {
    setEmail(`${role}@demo.namma-civic.ai`)
    setPassword('password123')
    clearError()
  }

  return (
    <PublicShell>
      <div className="min-h-[calc(100dvh-120px)] flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="w-12 h-12 rounded-2xl bg-blue-900 flex items-center justify-center mx-auto mb-4 shadow-lg" aria-hidden="true">
              <Shield size={24} className="text-white" />
            </div>
            <h1 className="text-heading-1 text-gray-900">Welcome back</h1>
            <p className="text-gray-500 text-sm mt-1">Sign in to Namma Civic 2.0</p>
          </div>

          {/* Card */}
          <div className="card p-6 sm:p-7">
            {/* Error */}
            {error && (
              <div className="alert alert-error mb-5 text-sm">
                <AlertCircle size={16} className="shrink-0" aria-hidden="true" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {/* Email */}
              <div>
                <label htmlFor="email" className="label">Email address</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true" />
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    placeholder="you@example.com"
                    className="input pl-9"
                    aria-required="true"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label htmlFor="password" className="label">Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true" />
                  <input
                    id="password"
                    type={showPw ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                    placeholder="••••••••"
                    className="input pl-9 pr-10"
                    aria-required="true"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    aria-label={showPw ? 'Hide password' : 'Show password'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors p-1"
                  >
                    {showPw ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                  </button>
                </div>
              </div>

              <button
                id="login-submit-btn"
                type="submit"
                disabled={isLoading || !email || !password}
                className="btn btn-primary w-full mt-2"
              >
                {isLoading ? (
                  <><Loader2 size={16} className="spinner" aria-hidden="true" /> Signing in…</>
                ) : 'Sign In'}
              </button>
            </form>

            {/* Demo shortcuts */}
            <div className="mt-6 pt-5 border-t border-gray-200">
              <p className="text-xs text-gray-400 text-center mb-3">Quick demo access</p>
              <div className="grid grid-cols-3 gap-2">
                {(['citizen', 'officer', 'admin'] as const).map((role) => (
                  <button
                    key={role}
                    id={`demo-${role}-btn`}
                    type="button"
                    onClick={() => fillDemo(role)}
                    className="btn btn-secondary btn-sm capitalize justify-center"
                    aria-label={`Fill ${role} demo credentials`}
                  >
                    {role.charAt(0).toUpperCase() + role.slice(1)}
                  </button>
                ))}
              </div>
              <p className="text-xs text-gray-400 text-center mt-2">Password: <span className="font-mono">password123</span></p>
            </div>
          </div>

          <p className="text-center text-sm text-gray-500 mt-5">
            Don't have an account?{' '}
            <Link to="/register" className="text-blue-700 font-semibold hover:text-blue-900 transition-colors">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </PublicShell>
  )
}
