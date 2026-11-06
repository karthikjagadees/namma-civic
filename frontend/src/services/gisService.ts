/**
 * Namma Civic — GIS & Geocoding Service
 * Client for forward geocoding, reverse geocoding, and address autocomplete.
 */
import api from './api'

export interface GeocodeResult {
  latitude: number
  longitude: number
  formatted_address: string
  street?: string
  neighborhood?: string
  city?: string
  state?: string
  postal_code?: string
  confidence: number
  provider: string
}

export interface ReverseGeocodeResult {
  latitude: number
  longitude: number
  address: string
  formatted_address: string
  street?: string
  neighborhood?: string
  city?: string
  state?: string
  postal_code?: string
  provider: string
}

export interface AutocompleteResult {
  title: string
  formatted_address: string
  latitude?: number
  longitude?: number
  city?: string
  provider: string
}

export interface GISStatus {
  active_provider: string
  google_maps_configured: boolean
  nominatim_enabled: boolean
}

export const gisService = {
  /**
   * Check GIS backend configuration and status
   */
  async getStatus(): Promise<GISStatus> {
    const res = await api.get<GISStatus>('/gis/status')
    return res.data
  },

  /**
   * Forward geocode address or landmark into coordinates
   */
  async geocode(address: string): Promise<GeocodeResult> {
    const res = await api.get<GeocodeResult>('/gis/geocode', {
      params: { address },
    })
    return res.data
  },

  /**
   * Reverse geocode coordinates (lat, lng) into street address
   */
  async reverseGeocode(lat: number, lng: number): Promise<ReverseGeocodeResult> {
    const res = await api.get<ReverseGeocodeResult>('/gis/reverse-geocode', {
      params: { lat, lng },
    })
    return res.data
  },

  /**
   * Live address autocomplete suggestions
   */
  async autocomplete(query: string, limit: number = 5): Promise<AutocompleteResult[]> {
    if (!query || query.trim().length < 2) return []
    const res = await api.get<AutocompleteResult[]>('/gis/autocomplete', {
      params: { query, limit },
    })
    return res.data
  },
}

export default gisService
