import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../services/api'

const AUTH_KEY = 'namma-civic-auth'
const TOKEN_KEY = 'namma-civic-token'

// Keep a session that was saved before the rename.
if (typeof localStorage !== 'undefined') {
  if (!localStorage.getItem(AUTH_KEY)) {
    const previous = localStorage.getItem('civicfix-auth')
    if (previous) localStorage.setItem(AUTH_KEY, previous)
  }
  if (!localStorage.getItem(TOKEN_KEY)) {
    const previous = localStorage.getItem('civicfix_token')
    if (previous) localStorage.setItem(TOKEN_KEY, previous)
  }
}

export interface AuthUser {
  id: string
  email: string
  full_name: string
  phone: string | null
  role: 'citizen' | 'officer' | 'admin'
  is_active: boolean
  is_verified: boolean
  department_id: string | null
  created_at: string
}

interface AuthState {
  user: AuthUser | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  // Actions
  login: (email: string, password: string) => Promise<void>
  register: (data: RegisterData) => Promise<void>
  logout: () => void
  clearError: () => void
  refreshMe: () => Promise<void>
}

export interface RegisterData {
  email: string
  password: string
  full_name: string
  phone?: string
}

export const useAuthStore = create<AuthState>()(
  persist<AuthState>(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (email, password) => {
        set({ isLoading: true, error: null })
        try {
          const resp = await api.post('/auth/login', { email, password })
          const { access_token, user } = resp.data
          localStorage.setItem(TOKEN_KEY, access_token)
          set({ token: access_token, user, isAuthenticated: true, isLoading: false })
        } catch (err: unknown) {
          const msg =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            'Login failed. Please check your credentials.'
          set({ error: msg, isLoading: false })
          throw err
        }
      },

      register: async (data) => {
        set({ isLoading: true, error: null })
        try {
          const resp = await api.post('/auth/register', data)
          const { access_token, user } = resp.data
          localStorage.setItem(TOKEN_KEY, access_token)
          set({ token: access_token, user, isAuthenticated: true, isLoading: false })
        } catch (err: unknown) {
          const msg =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            'Registration failed. Please try again.'
          set({ error: msg, isLoading: false })
          throw err
        }
      },

      logout: () => {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem('civicfix_token')
        set({ user: null, token: null, isAuthenticated: false, error: null })
      },

      clearError: () => set({ error: null }),

      refreshMe: async () => {
        if (!get().token) return
        try {
          const resp = await api.get('/auth/me')
          set({ user: resp.data, isAuthenticated: true })
        } catch {
          get().logout()
        }
      },
    }),
    {
      name: AUTH_KEY,
      partialize: (state) =>
        ({
          token: state.token,
          user: state.user,
          isAuthenticated: state.isAuthenticated,
        } as unknown as AuthState),
    }
  )
)
