/**
 * Namma Civic — Interactive Location Picker Map
 * Allows citizens and officers to drop a pin, search locations, or use GPS.
 * Bi-directionally syncs with address & landmark via forward/reverse geocoding.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { MapPin, Search, Navigation, Loader2, CheckCircle2, Sparkles } from 'lucide-react'
import { gisService, type AutocompleteResult } from '../services/gisService'

// Fix default Leaflet icon paths
const customIcon = L.icon({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

interface LocationPickerProps {
  initialLat?: number
  initialLng?: number
  initialAddress?: string
  initialLandmark?: string
  onLocationSelect: (location: {
    address: string
    landmark: string
    latitude: number
    longitude: number
  }) => void
}

export const LocationPickerMap: React.FC<LocationPickerProps> = ({
  initialLat = 12.9716,
  initialLng = 77.5946,
  initialAddress = '',
  initialLandmark = '',
  onLocationSelect,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<L.Map | null>(null)
  const markerRef = useRef<L.Marker | null>(null)

  const [coords, setCoords] = useState<{ lat: number; lng: number }>({
    lat: initialLat,
    lng: initialLng,
  })
  const [address, setAddress] = useState<string>(initialAddress)
  const [landmark, setLandmark] = useState<string>(initialLandmark)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [suggestions, setSuggestions] = useState<AutocompleteResult[]>([])
  const [isSearching, setIsSearching] = useState<boolean>(false)
  const [isGeocoding, setIsGeocoding] = useState<boolean>(false)
  const [isGpsLoading, setIsGpsLoading] = useState<boolean>(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [provider, setProvider] = useState<string>('OpenStreetMap Nominatim')

  // Check provider status on mount
  useEffect(() => {
    gisService.getStatus().then((status) => {
      setProvider(
        status.active_provider === 'google_maps' ? 'Google Maps Platform' : 'OpenStreetMap Nominatim'
      )
    }).catch(() => {})
  }, [])

  // Reverse geocode a coordinate and update address
  const handleReverseGeocode = useCallback(
    async (lat: number, lng: number) => {
      setIsGeocoding(true)
      setStatusMessage('Resolving physical address…')
      try {
        const res = await gisService.reverseGeocode(lat, lng)
        if (res && res.address) {
          setAddress(res.address)
          const derivedLandmark = res.neighborhood || res.street || ''
          if (derivedLandmark && !landmark) {
            setLandmark(derivedLandmark)
          }
          setStatusMessage('Address resolved')
          onLocationSelect({
            address: res.address,
            landmark: landmark || derivedLandmark,
            latitude: lat,
            longitude: lng,
          })
        }
      } catch (err) {
        console.error('Reverse geocode failed:', err)
        setStatusMessage('Coordinates recorded')
        onLocationSelect({
          address: address || `Coordinates: ${lat.toFixed(5)}, ${lng.toFixed(5)}`,
          landmark,
          latitude: lat,
          longitude: lng,
        })
      } finally {
        setIsGeocoding(false)
        setTimeout(() => setStatusMessage(null), 3500)
      }
    },
    [address, landmark, onLocationSelect]
  )

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [coords.lat, coords.lng],
        zoom: 14,
        scrollWheelZoom: false,
      })

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map)

      const marker = L.marker([coords.lat, coords.lng], {
        icon: customIcon,
        draggable: true,
      }).addTo(map)

      // Drag event
      marker.on('dragend', () => {
        const pos = marker.getLatLng()
        setCoords({ lat: pos.lat, lng: pos.lng })
        handleReverseGeocode(pos.lat, pos.lng)
      })

      // Map click event
      map.on('click', (e: L.LeafletMouseEvent) => {
        const { lat, lng } = e.latlng
        marker.setLatLng([lat, lng])
        setCoords({ lat, lng })
        handleReverseGeocode(lat, lng)
      })

      markerRef.current = marker
      mapInstanceRef.current = map
    }

    return () => {
      // Map cleanup on unmount
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [])

  // Update marker & pan when coords change externally
  const panToCoords = (lat: number, lng: number) => {
    setCoords({ lat, lng })
    if (markerRef.current) {
      markerRef.current.setLatLng([lat, lng])
    }
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([lat, lng], 15, { duration: 1.2 })
    }
  }

  // Handle GPS location
  const handleUseGps = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.')
      return
    }

    setIsGpsLoading(true)
    setStatusMessage('Acquiring high-precision GPS…')

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude
        const lng = pos.coords.longitude
        panToCoords(lat, lng)
        setIsGpsLoading(false)
        handleReverseGeocode(lat, lng)
      },
      (err) => {
        setIsGpsLoading(false)
        setStatusMessage('GPS request declined or timed out')
        setTimeout(() => setStatusMessage(null), 3000)
        console.warn('Geolocation error:', err)
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    )
  }

  // Search input debounced autocomplete
  useEffect(() => {
    if (!searchQuery || searchQuery.trim().length < 2) {
      setSuggestions([])
      return
    }

    const timer = setTimeout(async () => {
      setIsSearching(true)
      try {
        const items = await gisService.autocomplete(searchQuery.trim(), 5)
        setSuggestions(items)
      } catch (err) {
        console.error('Autocomplete failed:', err)
      } finally {
        setIsSearching(false)
      }
    }, 350)

    return () => clearTimeout(timer)
  }, [searchQuery])

  // Select search suggestion
  const handleSelectSuggestion = async (item: AutocompleteResult) => {
    setSearchQuery('')
    setSuggestions([])
    setAddress(item.formatted_address)

    if (item.latitude && item.longitude) {
      panToCoords(item.latitude, item.longitude)
      onLocationSelect({
        address: item.formatted_address,
        landmark: item.title || landmark,
        latitude: item.latitude,
        longitude: item.longitude,
      })
    } else {
      // Forward geocode full address if coordinates missing from autocomplete item
      try {
        setIsGeocoding(true)
        const geo = await gisService.geocode(item.formatted_address)
        if (geo) {
          panToCoords(geo.latitude, geo.longitude)
          onLocationSelect({
            address: geo.formatted_address,
            landmark: geo.neighborhood || landmark,
            latitude: geo.latitude,
            longitude: geo.longitude,
          })
        }
      } catch (e) {
        console.error('Geocode lookup failed:', e)
      } finally {
        setIsGeocoding(false)
      }
    }
  }

  return (
    <div className="space-y-4">
      {/* Search Bar & GPS Trigger */}
      <div className="relative">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
              aria-hidden="true"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search area, road, or landmark (e.g. MG Road, Bengaluru)…"
              className="input pl-9 pr-8"
              aria-label="Search map location"
            />
            {isSearching && (
              <Loader2
                size={14}
                className="spinner absolute right-3 top-1/2 -translate-y-1/2 text-blue-600"
              />
            )}
          </div>

          <button
            type="button"
            onClick={handleUseGps}
            disabled={isGpsLoading}
            className="btn btn-secondary shrink-0"
            title="Snap pin to my device GPS position"
          >
            {isGpsLoading ? (
              <Loader2 size={15} className="spinner" />
            ) : (
              <Navigation size={15} className="text-blue-700" />
            )}
            <span className="hidden sm:inline">Use GPS</span>
          </button>
        </div>

        {/* Autocomplete Dropdown */}
        {suggestions.length > 0 && (
          <div className="absolute z-[1000] mt-1 w-full bg-white rounded-lg border border-gray-200 shadow-xl overflow-hidden divide-y divide-gray-100">
            {suggestions.map((item, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSelectSuggestion(item)}
                className="w-full text-left px-3.5 py-2.5 hover:bg-blue-50 transition-colors flex items-start gap-2.5 group"
              >
                <MapPin size={15} className="text-gray-400 group-hover:text-blue-600 shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold text-gray-900 truncate">{item.title}</div>
                  <div className="text-[11px] text-gray-500 truncate">{item.formatted_address}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Interactive Map Container */}
      <div className="relative rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div
          ref={mapContainerRef}
          style={{ height: '320px', width: '100%', zIndex: 1 }}
          className="cursor-crosshair"
          aria-label="Interactive incident map"
        />

        {/* Floating status badge */}
        {(isGeocoding || statusMessage) && (
          <div className="absolute top-3 right-3 z-[400] bg-white/95 backdrop-blur-sm border border-gray-200/80 px-2.5 py-1.5 rounded-md shadow-md text-xs font-medium text-gray-700 flex items-center gap-1.5">
            {isGeocoding ? (
              <Loader2 size={13} className="spinner text-blue-600" />
            ) : (
              <CheckCircle2 size={13} className="text-green-600" />
            )}
            <span>{statusMessage || 'Updating…'}</span>
          </div>
        )}

        {/* Bottom map overlay strip */}
        <div className="absolute bottom-2 left-2 right-2 z-[400] pointer-events-none flex items-center justify-between">
          <div className="bg-white/90 backdrop-blur-sm border border-gray-200 px-2 py-1 rounded text-[10px] font-mono text-gray-600 shadow-sm pointer-events-auto">
            📍 {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)}
          </div>
          <div className="bg-white/90 backdrop-blur-sm border border-gray-200 px-2 py-1 rounded text-[10px] text-gray-500 shadow-sm">
            {provider}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <span className="flex items-center gap-1 text-blue-900 font-medium">
          <Sparkles size={13} />
          Click or drag pin to pinpoint exact grievance spot
        </span>
        <span className="text-gray-400">Zoom: Scroll or pinch</span>
      </div>

      {/* Synchronized Address & Landmark Fields */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
        <div>
          <label htmlFor="report-address" className="label">
            Street Address / Location <span className="text-red-600">*</span>
          </label>
          <input
            id="report-address"
            type="text"
            value={address}
            onChange={(e) => {
              setAddress(e.target.value)
              onLocationSelect({
                address: e.target.value,
                landmark,
                latitude: coords.lat,
                longitude: coords.lng,
              })
            }}
            placeholder="e.g., Near Gate 2, Metro Station, MG Road"
            className="input text-xs sm:text-sm"
            required
          />
        </div>

        <div>
          <label htmlFor="report-landmark" className="label">
            Nearest Landmark / Ward
          </label>
          <input
            id="report-landmark"
            type="text"
            value={landmark}
            onChange={(e) => {
              setLandmark(e.target.value)
              onLocationSelect({
                address,
                landmark: e.target.value,
                latitude: coords.lat,
                longitude: coords.lng,
              })
            }}
            placeholder="e.g., Pillar 42, Central Market, Ward 12"
            className="input text-xs sm:text-sm"
          />
        </div>
      </div>
    </div>
  )
}

export default LocationPickerMap
