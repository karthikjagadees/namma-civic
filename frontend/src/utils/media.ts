/**
 * Resolves media URLs for uploaded evidence and field photos.
 * Ensures relative `/uploads/*` paths route seamlessly through the local Vite proxy or backend server.
 */
export function getMediaUrl(url?: string | null): string {
  if (!url) {
    return 'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=600&auto=format&fit=crop&q=60'
  }
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url
  }
  return url.startsWith('/') ? url : `/${url}`
}

export const FALLBACK_INCIDENT_IMAGE =
  'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=600&auto=format&fit=crop&q=60'
