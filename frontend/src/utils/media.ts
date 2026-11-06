/**
 * Resolves media URLs for uploaded evidence and field photos.
 * Ensures relative `/uploads/*` paths route seamlessly through the local Vite proxy or backend server.
 */
function apiOrigin(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '')
  if (!configured) return ''
  return configured.replace(/\/api$/i, '')
}

export function getMediaUrl(url?: string | null): string {
  if (!url) {
    return 'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=600&auto=format&fit=crop&q=60'
  }
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url
  }
  const path = url.startsWith('/') ? url : `/${url}`
  const origin = apiOrigin()
  return origin ? `${origin}${path}` : path
}

export const FALLBACK_INCIDENT_IMAGE =
  'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=600&auto=format&fit=crop&q=60'
