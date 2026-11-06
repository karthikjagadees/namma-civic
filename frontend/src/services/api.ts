import axios from 'axios'

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '')
const apiBaseUrl = configuredApiBaseUrl
  ? `${configuredApiBaseUrl.replace(/\/api$/i, '')}/api`
  : '/api'

const api = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
})

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('namma-civic-token') ?? localStorage.getItem('civicfix_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // The instance default is application/json. A file upload must keep the
  // multipart boundary that the browser generates, or the API rejects the photo.
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    config.headers.delete('Content-Type')
  }
  return config
})

// Handle auth errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('namma-civic-token')
      localStorage.removeItem('civicfix_token')
      // Redirect to login in Phase 2
    }
    return Promise.reject(error)
  }
)

export default api

// ── Health API ─────────────────────────────────────────────────
export const healthApi = {
  check: () => api.get<{ status: string; service: string; version: string; environment: string }>('/health'),
  detailed: () => api.get('/health/detailed'),
}
