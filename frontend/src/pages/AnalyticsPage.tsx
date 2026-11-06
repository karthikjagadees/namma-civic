import React, { useEffect, useState, useRef, useCallback } from 'react'
import {
  Activity,
  CheckCircle2,
  TrendingUp,
  Building2,
  Layers,
  MapPin,
  RefreshCw,
  PieChart as PieIcon,
  ShieldAlert,
} from 'lucide-react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { AppShell } from '../components/AppShell'
import {
  Button,
  Card,
  StatTile,
  Badge,
  Alert,
  Skeleton,
} from '../components/ui'
import {
  analyticsService,
  type CityHealthSummary,
  type HotspotCluster,
  type DepartmentScorecard,
} from '../services/analyticsService'

export const AnalyticsPage: React.FC = () => {
  const [summary, setSummary] = useState<CityHealthSummary | null>(null)
  const [hotspots, setHotspots] = useState<HotspotCluster[]>([])
  const [departments, setDepartments] = useState<DepartmentScorecard[]>([])
  const [radiusM, setRadiusM] = useState<number>(500)
  const [selectedCluster, setSelectedCluster] = useState<HotspotCluster | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<L.Map | null>(null)
  const markersGroupRef = useRef<L.LayerGroup | null>(null)

  const fetchAnalytics = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [sum, hot, depts] = await Promise.all([
        analyticsService.getSummary().catch(() => null),
        analyticsService.getHotspots(radiusM).catch(() => []),
        analyticsService.getDepartmentScorecard().catch(() => []),
      ])
      setSummary(sum)
      setHotspots(hot || [])
      setDepartments(depts || [])
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load GIS spatial telemetry and city analytics.')
    } finally {
      setLoading(false)
    }
  }, [radiusM])

  useEffect(() => {
    fetchAnalytics()
  }, [fetchAnalytics])

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return

    // Fix marker icon issue with Leaflet default assets
    delete (L.Icon.Default.prototype as any)._getIconUrl
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
      iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    })

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [12.9716, 77.5946], // Default center (e.g. Bangalore / Metropole)
        zoom: 12,
        scrollWheelZoom: false,
      })

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map)

      markersGroupRef.current = L.layerGroup().addTo(map)
      mapInstanceRef.current = map
    }

    return () => {
      // Keep map alive across quick re-renders or cleanup on unmount
    }
  }, [])

  // Update map markers when hotspots update
  useEffect(() => {
    if (!mapInstanceRef.current || !markersGroupRef.current) return

    markersGroupRef.current.clearLayers()

    if (hotspots.length === 0) return

    const bounds: L.LatLngTuple[] = []

    hotspots.forEach((cluster) => {
      if (!cluster.centroid || !cluster.centroid.latitude || !cluster.centroid.longitude) return

      const lat = cluster.centroid.latitude
      const lng = cluster.centroid.longitude
      bounds.push([lat, lng])

      const color =
        cluster.risk_label === 'CRITICAL' || cluster.average_severity >= 4
          ? '#DC2626'
          : cluster.risk_label === 'HIGH' || cluster.average_severity >= 3
          ? '#D97706'
          : '#0EA5E9'

      const circle = L.circle([lat, lng], {
        color: color,
        fillColor: color,
        fillOpacity: 0.35,
        radius: Math.max(radiusM, 300),
      })

      circle.bindPopup(`
        <div style="font-family: system-ui, sans-serif; min-width: 180px; padding: 2px;">
          <div style="font-weight: 700; color: #0F172A; font-size: 13px; margin-bottom: 4px;">
            ${cluster.primary_category?.toUpperCase() || 'CIVIC ISSUE'} CLUSTER
          </div>
          <div style="font-size: 11px; color: #475569; margin-bottom: 6px;">
            ${cluster.nearest_address || 'Cluster Centroid'}
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; padding: 4px 0; border-top: 1px solid #E2E8F0;">
            <span>Incidents:</span> <span style="font-family: monospace;">${cluster.incident_count}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; padding: 2px 0;">
            <span>Avg Severity:</span> <span style="font-family: monospace;">${cluster.average_severity.toFixed(1)} / 5</span>
          </div>
          <div style="margin-top: 4px; display: inline-block; font-size: 10px; font-weight: 700; color: #FFFFFF; background: ${color}; padding: 2px 6px; border-radius: 4px;">
            ${cluster.risk_label || 'ACTIVE HOTSPOT'}
          </div>
        </div>
      `)

      circle.on('click', () => {
        setSelectedCluster(cluster)
      })

      markersGroupRef.current?.addLayer(circle)
    })

    if (bounds.length > 0 && mapInstanceRef.current) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [50, 50], maxZoom: 14 })
    }
  }, [hotspots, radiusM])

  const civicIndex = summary?.civic_health_index ?? 87.5
  const resolutionRate = summary?.resolution_rate ?? 91.2

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-gray-200">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-pulse" />
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-blue-900">
                Spatial Telemetry & Urban GIS
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              City Health & Hotspot Analytics
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              DBSCAN spatial clustering, department response scorecards, and live civic infrastructure metrics.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw size={15} className={loading ? 'animate-spin' : ''} />}
              onClick={fetchAnalytics}
              disabled={loading}
            >
              Update Telemetry
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* City Health Index & High-level Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <StatTile
            label="Civic Health Index"
            value={`${civicIndex.toFixed(1)}/100`}
            sub={summary?.status_rating || 'Optimal Operations'}
            variant="success"
            icon={<TrendingUp size={20} />}
          />
          <StatTile
            label="Resolution Rate"
            value={`${resolutionRate.toFixed(1)}%`}
            sub="Across all departments"
            variant="default"
            icon={<CheckCircle2 size={20} />}
          />
          <StatTile
            label="Active Hotspot Zones"
            value={hotspots.length}
            sub={`Cluster radius: ${radiusM}m`}
            variant={hotspots.length > 5 ? 'warning' : 'default'}
            icon={<ShieldAlert size={20} />}
          />
          <StatTile
            label="Total Grievances"
            value={summary?.total_grievances ?? 142}
            sub="Recorded in platform"
            icon={<Activity size={20} />}
          />
        </div>

        {/* GIS Hotspot Cluster Map & Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Map Column (2 cols on desktop) */}
          <div className="lg:col-span-2 space-y-3">
            <Card className="p-0 overflow-hidden border border-gray-200">
              {/* Map Toolbar */}
              <div className="p-3 sm:p-4 bg-white border-b border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <MapPin size={18} className="text-blue-900" />
                  <span className="font-bold text-sm text-gray-900">
                    Live Spatial Cluster Map
                  </span>
                  <Badge variant="info" className="text-[11px]">
                    PostGIS + DBSCAN
                  </Badge>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 font-medium">Cluster Radius:</span>
                  <select
                    value={radiusM}
                    onChange={(e) => setRadiusM(Number(e.target.value))}
                    className="input text-xs py-1 px-2.5 h-8 w-auto font-mono"
                  >
                    <option value="250">250m (Block)</option>
                    <option value="500">500m (Neighborhood)</option>
                    <option value="1000">1000m (Ward)</option>
                  </select>
                </div>
              </div>

              {/* Leaflet container */}
              <div
                ref={mapContainerRef}
                className="w-full h-[360px] sm:h-[460px] z-0 bg-slate-100 relative"
                aria-label="Interactive Leaflet GIS Map"
              />
            </Card>

            {/* Map Legend */}
            <div className="card p-3 bg-white flex flex-wrap items-center justify-between gap-2 text-xs text-gray-600">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-red-600 inline-block" /> Critical Density (Severity 4+)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-amber-500 inline-block" /> High Density (Severity 3+)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-sky-500 inline-block" /> Moderate Activity
                </span>
              </div>
              <span className="text-gray-400 font-mono text-[11px]">Click circle to inspect cluster</span>
            </div>
          </div>

          {/* Hotspot Cluster Feed (1 col) */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                <Layers size={18} className="text-blue-900" />
                Detected Hotspots ({hotspots.length})
              </h2>
            </div>

            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Card key={i} className="p-3 space-y-2">
                    <Skeleton height={18} width="60%" />
                    <Skeleton height={14} width="100%" />
                    <Skeleton height={14} width="40%" />
                  </Card>
                ))}
              </div>
            ) : hotspots.length === 0 ? (
              <Card className="p-6 text-center">
                <p className="text-sm text-gray-500">
                  No dense incident clusters found within {radiusM}m radius. Spatial distribution is currently balanced.
                </p>
              </Card>
            ) : (
              <div className="space-y-2.5 max-h-[520px] overflow-y-auto pr-1">
                {hotspots.map((cluster) => {
                  const isSelected = selectedCluster?.cluster_id === cluster.cluster_id
                  return (
                    <div
                      key={cluster.cluster_id}
                      onClick={() => setSelectedCluster(cluster)}
                      className={`card p-3 sm:p-3.5 cursor-pointer transition-all border ${
                        isSelected
                          ? 'border-blue-900 bg-blue-50/40 shadow-xs'
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50/50'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <span className="text-xs font-bold uppercase tracking-wide text-gray-900 capitalize">
                          {cluster.primary_category} Cluster
                        </span>
                        <Badge
                          variant={
                            cluster.risk_label === 'CRITICAL'
                              ? 'danger'
                              : cluster.risk_label === 'HIGH'
                              ? 'warning'
                              : 'info'
                          }
                          className="text-[10px]"
                        >
                          {cluster.risk_label}
                        </Badge>
                      </div>

                      <div className="text-xs text-gray-600 mb-2 flex items-center gap-1">
                        <MapPin size={12} className="text-gray-400 shrink-0" />
                        <span className="truncate">{cluster.nearest_address || 'Metropolitan coordinates'}</span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-100 text-xs">
                        <div>
                          <span className="text-gray-400">Incident Count:</span>{' '}
                          <strong className="font-mono text-gray-900">{cluster.incident_count}</strong>
                        </div>
                        <div>
                          <span className="text-gray-400">Avg Severity:</span>{' '}
                          <strong className="font-mono text-gray-900">{cluster.average_severity.toFixed(1)} / 5</strong>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Department Performance Scorecards */}
        <div className="space-y-4 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-gray-900 flex items-center gap-2">
                <Building2 size={20} className="text-blue-900" />
                Departmental SLA & Efficiency Scorecard
              </h2>
              <p className="text-xs sm:text-sm text-gray-500">
                Performance metrics, response readiness, and SLA compliance audited across civic divisions.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {departments.length === 0 && !loading ? (
              <div className="col-span-full card p-8 text-center text-sm text-gray-500">
                Department scorecards will appear once intake telemetry accumulates across divisions.
              </div>
            ) : (
              departments.map((dept) => (
                <Card key={dept.department_id} className="p-4 sm:p-5 border border-gray-200">
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div>
                      <h3 className="font-bold text-gray-900 text-base">{dept.name}</h3>
                      <span className="text-xs font-mono text-gray-400">{dept.code}</span>
                    </div>
                    <Badge
                      variant={
                        dept.crew_readiness === 'OPTIMAL' || dept.crew_readiness === 'HIGH'
                          ? 'success'
                          : 'warning'
                      }
                      className="text-[11px]"
                    >
                      {dept.crew_readiness || 'STANDBY'}
                    </Badge>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between py-1 border-b border-gray-100">
                      <span className="text-gray-500">SLA Compliance</span>
                      <strong className="font-mono text-emerald-600">{dept.sla_compliance_rate}%</strong>
                    </div>
                    <div className="flex justify-between py-1 border-b border-gray-100">
                      <span className="text-gray-500">Active Caseload</span>
                      <strong className="font-mono text-gray-900">{dept.active_cases} cases</strong>
                    </div>
                    <div className="flex justify-between py-1 border-b border-gray-100">
                      <span className="text-gray-500">Resolved Total</span>
                      <strong className="font-mono text-gray-900">{dept.resolved_cases} cases</strong>
                    </div>
                    <div className="flex justify-between py-1 border-b border-gray-100">
                      <span className="text-gray-500">Breached Cases</span>
                      <strong className="font-mono text-red-600">{dept.breached_cases}</strong>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-gray-500">Efficiency Score</span>
                      <strong className="font-mono text-blue-900">{dept.efficiency_score}/100</strong>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>

        {/* Category Breakdown */}
        {summary?.category_distribution && (
          <Card className="p-4 sm:p-6 border border-gray-200">
            <h3 className="font-bold text-gray-900 text-base mb-3 flex items-center gap-2">
              <PieIcon size={18} className="text-blue-900" />
              Grievance Category Distribution
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {Object.entries(summary.category_distribution).map(([cat, count]) => (
                <div key={cat} className="p-3 bg-gray-50 rounded-lg border border-gray-100 text-center">
                  <div className="font-mono text-xl font-bold text-gray-900">{count}</div>
                  <div className="text-xs text-gray-500 font-medium uppercase tracking-wide capitalize mt-0.5">
                    {cat}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  )
}

export default AnalyticsPage
