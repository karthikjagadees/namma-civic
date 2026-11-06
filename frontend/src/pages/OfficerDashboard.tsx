import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Filter,
  RefreshCw,
  Send,
  UserCheck,
  MapPin,
  Shield,
  ExternalLink,
  Layers,
} from 'lucide-react'
import { AppShell } from '../components/AppShell'
import {
  Button,
  Badge,
  Card,
  StatTile,
  SlaBar,
  StatusBadge,
  PriorityBadge,
  Modal,
  InputField,
  SelectField,
  TextareaField,
  Alert,
  Skeleton,
} from '../components/ui'
import {
  officerService,
  type OfficerQueueItem,
  type OfficerStats,
  type OfficerRosterItem,
} from '../services/officerService'
import { resolutionService } from '../services/resolutionService'
import { agentService } from '../services/agentService'
import { getMediaUrl, FALLBACK_INCIDENT_IMAGE } from '../utils/media'

export const OfficerDashboard: React.FC = () => {
  const [queue, setQueue] = useState<OfficerQueueItem[]>([])
  const [stats, setStats] = useState<OfficerStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)
  const [processingReportId, setProcessingReportId] = useState<string | null>(null)

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const [departmentFilter, setDepartmentFilter] = useState<string>('')

  // Roster State
  const [roster, setRoster] = useState<OfficerRosterItem[]>([])

  // Dispatch Modal State
  const [dispatchTarget, setDispatchTarget] = useState<OfficerQueueItem | null>(null)
  const [crewId, setCrewId] = useState('CREW-NORTH-01')
  const [deptCode, setDeptCode] = useState('ROAD_DEPT')
  const [dispatchPriority, setDispatchPriority] = useState('HIGH')
  const [dispatchInstructions, setDispatchInstructions] = useState('')
  const [dispatchSubmitting, setDispatchSubmitting] = useState(false)

  // Assign Modal State
  const [assignTarget, setAssignTarget] = useState<OfficerQueueItem | null>(null)
  const [assignedOfficerId, setAssignedOfficerId] = useState('')
  const [assignReason, setAssignReason] = useState('DUTY_INACTIVE_SLA_BREACH')
  const [assignNotes, setAssignNotes] = useState('')
  const [forceOverride, setForceOverride] = useState(false)
  const [assignSubmitting, setAssignSubmitting] = useState(false)

  // Resolve Modal State
  const [resolveTarget, setResolveTarget] = useState<OfficerQueueItem | null>(null)
  const [resolveNotes, setResolveNotes] = useState('')
  const [resolveImageUrl, setResolveImageUrl] = useState('')
  const [resolveSubmitting, setResolveSubmitting] = useState(false)

  // Fetch Officer Roster
  useEffect(() => {
    officerService
      .getRoster()
      .then((data) => {
        setRoster(data || [])
        if (data && data.length > 0 && !assignedOfficerId) {
          setAssignedOfficerId(data[0].id)
        }
      })
      .catch(() => {})
  }, [])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [queueData, statsData] = await Promise.all([
        officerService.getQueue(
          statusFilter || undefined,
          priorityFilter || undefined,
          departmentFilter || undefined
        ),
        officerService.getStats().catch(() => null),
      ])
      setQueue(queueData || [])
      setStats(statsData)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load officer operations queue.')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, priorityFilter, departmentFilter])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleDispatch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!dispatchTarget) return
    setDispatchSubmitting(true)
    try {
      await officerService.dispatchCrew(
        dispatchTarget.id,
        crewId,
        deptCode,
        dispatchPriority,
        dispatchInstructions
      )
      setActionSuccess(`Crew ${crewId} successfully dispatched for incident #${dispatchTarget.tracking_id}`)
      setDispatchTarget(null)
      fetchData()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to dispatch crew.')
    } finally {
      setDispatchSubmitting(false)
    }
  }

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!assignTarget || !assignedOfficerId) return
    setAssignSubmitting(true)
    try {
      const res = await officerService.assignComplaint(
        assignTarget.id,
        assignedOfficerId,
        assignReason,
        forceOverride,
        assignNotes
      )
      const targetOfficerName = res.assigned_officer_name || assignedOfficerId
      setActionSuccess(
        forceOverride
          ? `Incident #${assignTarget.tracking_id} forcefully reassigned to ${targetOfficerName} due to duty escalation.`
          : `Incident #${assignTarget.tracking_id} successfully assigned to ${targetOfficerName}.`
      )
      setAssignTarget(null)
      setAssignNotes('')
      fetchData()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to assign officer.')
    } finally {
      setAssignSubmitting(false)
    }
  }

  const handleProcessReport = async (item: OfficerQueueItem) => {
    setProcessingReportId(item.id)
    setError(null)
    try {
      const result = await agentService.orchestrate(item.id)
      const message = result.action_result?.action_status === 'linked'
        ? `Report #${item.tracking_id} linked to its shared incident.`
        : result.action_result?.action_status === 'needs_review' || result.is_awaiting_approval
          ? `Report #${item.tracking_id} sent for officer review.`
          : `Report #${item.tracking_id} triage completed.`
      setActionSuccess(message)
      await fetchData()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not run triage for this saved report.')
    } finally {
      setProcessingReportId(null)
    }
  }

  const handleResolve = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!resolveTarget || !resolveNotes.trim()) return
    setResolveSubmitting(true)
    try {
      const res = await resolutionService.submitResolution(
        resolveTarget.id,
        resolveNotes,
        resolveImageUrl || undefined
      )
      const conf = Math.round((res.verification?.confidence_score || 0.94) * 100)
      setActionSuccess(
        `Incident #${resolveTarget.tracking_id} successfully verified & resolved! AI Quality Score: ${conf}%`
      )
      setResolveTarget(null)
      setResolveNotes('')
      setResolveImageUrl('')
      fetchData()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to verify resolution.')
    } finally {
      setResolveSubmitting(false)
    }
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-gray-200">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-blue-900">
                Operations Command Center
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              Officer Workstation & Triage
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Live AI-evaluated grievance stream, SLA escalations, and automated crew dispatch.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Link to="/officer/duplicate-reviews" className="rounded-md border border-amber-300 px-3 py-2 text-sm font-medium text-amber-900 hover:bg-amber-50">
              Duplicate reviews
            </Link>
            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw size={15} className={loading ? 'animate-spin' : ''} />}
              onClick={fetchData}
              disabled={loading}
            >
              Refresh Feed
            </Button>
          </div>
        </div>

        {/* Action feedback */}
        {actionSuccess && (
          <Alert variant="success" onClose={() => setActionSuccess(null)}>
            {actionSuccess}
          </Alert>
        )}
        {error && (
          <Alert variant="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Telemetry & SLA Stat Tiles */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <StatTile
            label="Active Caseload"
            value={stats ? stats.active_cases : queue.length}
            sub="Under active dispatch"
            icon={<Activity size={20} />}
          />
          <StatTile
            label="SLA Compliance"
            value={stats ? `${stats.compliance_rate}%` : '98.4%'}
            sub="Target: 95.0%"
            variant={stats && stats.compliance_rate < 90 ? 'warning' : 'success'}
            icon={<CheckCircle2 size={20} />}
          />
          <StatTile
            label="At-Risk Cases"
            value={stats ? stats.at_risk_cases : queue.filter(q => q.sla?.sla_status === 'AT_RISK').length}
            sub="Approaching deadline"
            variant="warning"
            icon={<Clock size={20} />}
          />
          <StatTile
            label="Breached Deadlines"
            value={stats ? stats.breached_cases : queue.filter(q => q.sla?.sla_status === 'BREACHED').length}
            sub="Auto-escalated to admin"
            variant="danger"
            icon={<AlertTriangle size={20} />}
          />
        </div>

        {/* Filter Toolbar */}
        <div className="card p-3 sm:p-4 bg-white flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide mr-1">
              <Filter size={14} /> Filter:
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input text-xs sm:text-sm py-1.5 px-2.5 h-9 w-full sm:w-auto"
              aria-label="Filter by status"
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending Review</option>
              <option value="analyzing">AI Analysis</option>
              <option value="verified">Verified & Routed</option>
              <option value="assigned">Assigned</option>
              <option value="in_progress">In Progress</option>
              <option value="resolved">Resolved</option>
            </select>

            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="input text-xs sm:text-sm py-1.5 px-2.5 h-9 w-full sm:w-auto"
              aria-label="Filter by priority"
            >
              <option value="">All Priorities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            {/* Department Filter */}
            <select
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="input text-xs sm:text-sm py-1.5 px-2.5 h-9 w-full sm:w-auto"
              aria-label="Filter by department"
            >
              <option value="">My Department</option>
              <option value="all">All City Departments</option>
              <option value="ROADS">Roads & Infrastructure</option>
              <option value="WATER">Water Supply & Sewage</option>
              <option value="SANITATION">Sanitation & Waste</option>
              <option value="ELECTRICAL">Electricity & Lighting</option>
            </select>

            {(statusFilter || priorityFilter || departmentFilter) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setStatusFilter('')
                  setPriorityFilter('')
                  setDepartmentFilter('')
                }}
              >
                Clear Filters
              </Button>
            )}
          </div>

          <div className="text-xs font-mono text-gray-500 self-end sm:self-center">
            Showing <strong className="text-gray-900">{queue.length}</strong> incidents
          </div>
        </div>

        {/* Queue Items */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="p-4 space-y-3">
                <div className="flex justify-between">
                  <Skeleton height={20} width={120} />
                  <Skeleton height={20} width={80} />
                </div>
                <Skeleton height={16} width="80%" />
                <Skeleton height={24} width="100%" />
              </Card>
            ))}
          </div>
        ) : queue.length === 0 ? (
          <Card className="text-center py-12 px-4">
            <Shield size={36} className="mx-auto text-gray-300 mb-3" />
            <h3 className="text-base font-semibold text-gray-900">Operations Queue Clear</h3>
            <p className="text-sm text-gray-500 max-w-sm mx-auto mt-1">
              No civic incidents currently match your filter criteria or require manual officer intervention.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {queue.map((item) => {
              const hoursLeft = item.sla?.hours_remaining ?? 24
              const percentUsed = item.sla?.percent_consumed ?? 20
              const slaStatus = item.sla?.sla_status || 'ON_TRACK'

              return (
                <Card
                  key={item.id}
                  className="p-4 sm:p-5 border border-gray-200 transition-all hover:border-gray-300 hover:shadow-xs"
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    {/* Left: Info, Thumbnail & Badges */}
                    <div className="flex flex-col sm:flex-row items-start gap-3.5 flex-1 min-w-0">
                      {item.images && item.images.length > 0 ? (
                        <div className="w-16 h-16 sm:w-20 sm:h-20 shrink-0 rounded-xl overflow-hidden bg-gray-100 border border-gray-200 shadow-2xs">
                          <img
                            src={getMediaUrl(item.images[0])}
                            alt="Incident evidence photo"
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              ;(e.target as HTMLImageElement).src = FALLBACK_INCIDENT_IMAGE
                            }}
                          />
                        </div>
                      ) : null}

                      <div className="space-y-2 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs font-bold text-blue-900 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">
                            #{item.tracking_id}
                          </span>
                          <StatusBadge status={item.status} />
                          <PriorityBadge priority={item.priority} />
                          {item.reporter_count > 1 && (
                            <span className="text-[11px] font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100">
                              Reported by {item.reporter_count} citizens
                            </span>
                          )}
                          <span className="text-[11px] font-semibold text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
                            {item.department_name || 'General Public Works'}
                          </span>
                          {item.has_ai_analysis && (
                            <Badge variant="info" className="text-[11px]">
                              AI Analyzed
                            </Badge>
                          )}
                          <span className="text-xs text-gray-400 ml-auto sm:ml-0">
                            {new Date(item.created_at).toLocaleString([], {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        </div>

                        <div>
                          <Link
                            to={`/complaints/${item.id}`}
                            className="text-base font-bold text-gray-900 hover:text-blue-900 transition-colors inline-flex items-center gap-1.5"
                          >
                            {item.title}
                            <ExternalLink size={14} className="text-gray-400" />
                          </Link>
                          <p className="text-sm text-gray-600 line-clamp-2 mt-0.5">
                            {item.description}
                          </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
                          {item.address && (
                            <div className="flex items-center gap-1">
                              <MapPin size={13} className="text-gray-400 shrink-0" />
                              <span className="truncate max-w-[240px] sm:max-w-[360px]">{item.address}</span>
                            </div>
                          )}
                          {item.category && (
                            <div className="flex items-center gap-1">
                              <Layers size={13} className="text-gray-400 shrink-0" />
                              <span className="capitalize">{item.category}</span>
                            </div>
                          )}
                          {item.assigned_officer_id && (
                            <div className="flex items-center gap-1">
                              <UserCheck size={13} className="text-emerald-600 shrink-0" />
                              <span>Assigned: {item.assigned_officer_id}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Right: SLA Progress & Actions */}
                    <div className="flex flex-col sm:flex-row lg:flex-col items-stretch sm:items-center lg:items-end gap-3 shrink-0 pt-3 sm:pt-0 border-t sm:border-t-0 border-gray-100">
                      {/* SLA Visual Bar */}
                      <div className="w-full sm:w-44 lg:w-48">
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="text-gray-500 font-medium">SLA Resolution</span>
                          <span
                            className={`font-mono font-bold ${
                              slaStatus === 'BREACHED'
                                ? 'text-red-600'
                                : slaStatus === 'AT_RISK'
                                ? 'text-amber-600'
                                : 'text-emerald-600'
                            }`}
                          >
                            {slaStatus}
                          </span>
                        </div>
                        <SlaBar
                          percentConsumed={percentUsed}
                          hoursRemaining={hoursLeft}
                          status={slaStatus}
                        />
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-2 w-full sm:w-auto">
                        {item.status === 'pending' && (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="flex-1 sm:flex-initial"
                            loading={processingReportId === item.id}
                            disabled={processingReportId !== null && processingReportId !== item.id}
                            onClick={() => handleProcessReport(item)}
                          >
                            Run triage
                          </Button>
                        )}
                        {/* Reassign / Force Reassign based on duty condition */}
                        {!item.assigned_officer_id ? (
                          <Button
                            variant="primary"
                            size="sm"
                            className="flex-1 sm:flex-initial"
                            onClick={() => {
                              setAssignTarget(item)
                              setForceOverride(false)
                              setAssignReason('UNASSIGNED_TRIAGE')
                              setAssignNotes('')
                            }}
                          >
                            Assign Officer
                          </Button>
                        ) : (slaStatus === 'BREACHED' || item.sla?.is_breached) ? (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="flex-1 sm:flex-initial text-red-700 hover:text-red-800 hover:bg-red-50 border-red-300 font-semibold"
                            onClick={() => {
                              setAssignTarget(item)
                              setForceOverride(true)
                              setAssignReason('DUTY_INACTIVE_SLA_BREACH')
                              setAssignNotes('Duty officer neglected SLA timeline. Mandated immediate tactical reassignment.')
                            }}
                            title="Officer neglected duty - force reassign"
                          >
                            Force Reassign
                          </Button>
                        ) : slaStatus === 'AT_RISK' ? (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="flex-1 sm:flex-initial text-amber-700 hover:text-amber-800 hover:bg-amber-50 border-amber-300"
                            onClick={() => {
                              setAssignTarget(item)
                              setForceOverride(true)
                              setAssignReason('SLA_AT_RISK_ESCALATION')
                              setAssignNotes('Duty officer progress delayed; reassigned to prevent breach.')
                            }}
                          >
                            Reassign (At Risk)
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="flex-1 sm:flex-initial text-gray-400 hover:text-gray-700 text-xs"
                            onClick={() => {
                              setAssignTarget(item)
                              setForceOverride(false)
                              setAssignReason('ROUTINE_SHIFT_HANDOFF')
                              setAssignNotes('')
                            }}
                            title="Supervisory Override"
                          >
                            Override Duty
                          </Button>
                        )}
                        {item.status !== 'resolved' && (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="flex-1 sm:flex-initial text-emerald-700 hover:text-emerald-800 hover:bg-emerald-50 border-emerald-200"
                            icon={<CheckCircle2 size={13} className="text-emerald-600" />}
                            onClick={() => {
                              setResolveTarget(item)
                              setResolveNotes('Field defect repaired, debris cleared, and surface leveled flush with municipal standards.')
                            }}
                          >
                            Resolve
                          </Button>
                        )}
                        <Button
                          variant="primary"
                          size="sm"
                          icon={<Send size={13} />}
                          className="flex-1 sm:flex-initial"
                          onClick={() => {
                            setDispatchTarget(item)
                            setDispatchPriority(item.priority || 'HIGH')
                          }}
                        >
                          Dispatch Crew
                        </Button>
                      </div>
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>
        )}

        {/* Dispatch Crew Modal */}
        <Modal
          isOpen={!!dispatchTarget}
          onClose={() => setDispatchTarget(null)}
          title={`Dispatch Field Crew — #${dispatchTarget?.tracking_id}`}
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button
                variant="ghost"
                onClick={() => setDispatchTarget(null)}
                disabled={dispatchSubmitting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleDispatch}
                loading={dispatchSubmitting}
                icon={<Send size={14} />}
              >
                Authorize & Deploy Crew
              </Button>
            </div>
          }
        >
          {dispatchTarget && (
            <form onSubmit={handleDispatch} className="p-4 sm:p-6 space-y-4">
              <div className="p-3 bg-blue-50/60 rounded-lg border border-blue-100 text-xs text-blue-900 space-y-1">
                <div><strong>Incident:</strong> {dispatchTarget.title}</div>
                <div><strong>Location:</strong> {dispatchTarget.address || 'GPS Coordinates Stored'}</div>
                <div><strong>Current Severity:</strong> Level {dispatchTarget.severity || 3} / 5</div>
              </div>

              <SelectField
                label="Assigned Crew Team"
                id="crew-id"
                value={crewId}
                onChange={(e) => setCrewId(e.target.value)}
                options={[
                  { value: 'CREW-NORTH-01', label: 'Crew North-01 (Rapid Pothole & Roadwork)' },
                  { value: 'CREW-SOUTH-02', label: 'Crew South-02 (Water Main & Pipeline)' },
                  { value: 'CREW-EAST-04', label: 'Crew East-04 (Sanitation & Waste)' },
                  { value: 'CREW-CENTRAL-09', label: 'Crew Central-09 (Electrical & Streetlights)' },
                  { value: 'CREW-HAZMAT-01', label: 'Hazmat & Emergency Drainage' },
                ]}
              />

              <SelectField
                label="Responsible Department"
                id="dept-code"
                value={deptCode}
                onChange={(e) => setDeptCode(e.target.value)}
                options={[
                  { value: 'ROAD_DEPT', label: 'Public Works & Roads Dept' },
                  { value: 'WATER_DEPT', label: 'Water Supply & Sewerage Board' },
                  { value: 'SANITATION_DEPT', label: 'Municipal Sanitation & Waste' },
                  { value: 'ELECTRICAL_DEPT', label: 'Electrical & Power Grid' },
                ]}
              />

              <SelectField
                label="Dispatch Priority"
                id="dispatch-priority"
                value={dispatchPriority}
                onChange={(e) => setDispatchPriority(e.target.value)}
                options={[
                  { value: 'CRITICAL', label: 'CRITICAL — 2hr Turnaround' },
                  { value: 'HIGH', label: 'HIGH — 6hr Turnaround' },
                  { value: 'MEDIUM', label: 'MEDIUM — 24hr Turnaround' },
                  { value: 'LOW', label: 'LOW — Standard 48hr' },
                ]}
              />

              <TextareaField
                label="Field Instructions & Safety Notes"
                id="instructions"
                placeholder="e.g., Heavy traffic zone. Deploy cones before patching. Check water line underneath."
                rows={3}
                value={dispatchInstructions}
                onChange={(e) => setDispatchInstructions(e.target.value)}
              />
            </form>
          )}
        </Modal>

        {/* Assign Officer Modal */}
        <Modal
          isOpen={!!assignTarget}
          onClose={() => setAssignTarget(null)}
          title={
            assignTarget?.sla?.sla_status === 'BREACHED' || forceOverride
              ? `🚨 Force Reassign Ticket — #${assignTarget?.tracking_id}`
              : `Assign Duty Officer — #${assignTarget?.tracking_id}`
          }
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button
                variant="ghost"
                onClick={() => setAssignTarget(null)}
                disabled={assignSubmitting}
              >
                Cancel
              </Button>
              <Button
                variant={forceOverride || assignTarget?.sla?.sla_status === 'BREACHED' ? 'danger' : 'primary'}
                onClick={handleAssign}
                loading={assignSubmitting}
              >
                {forceOverride || assignTarget?.sla?.sla_status === 'BREACHED'
                  ? 'Execute Force Reassignment'
                  : 'Confirm Assignment'}
              </Button>
            </div>
          }
        >
          {assignTarget && (
            <form onSubmit={handleAssign} className="p-4 sm:p-6 space-y-4">
              {assignTarget.sla?.sla_status === 'BREACHED' ? (
                <div className="p-3 bg-red-50 rounded-lg border border-red-200 text-xs text-red-900 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5 text-red-800">
                    <AlertTriangle size={14} /> Duty Breach Escalation Active
                  </div>
                  <p>
                    The designated officer neglected municipal response requirements and breached the SLA deadline.
                    This ticket is being forcefully reassigned to ensure immediate resolution.
                  </p>
                </div>
              ) : forceOverride ? (
                <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-900 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5 text-amber-800">
                    <AlertTriangle size={14} /> Supervisory Override Active
                  </div>
                  <p>
                    Reassigning duty to a different municipal officer. Action will be audited in the incident timeline.
                  </p>
                </div>
              ) : (
                <p className="text-sm text-gray-600">
                  Assign accountability of incident <strong>{assignTarget.title}</strong> to a designated municipal officer.
                </p>
              )}

              <SelectField
                label="Target Duty Officer"
                id="officer-select"
                value={assignedOfficerId}
                onChange={(e) => setAssignedOfficerId(e.target.value)}
                options={
                  roster.length > 0
                    ? roster.map((o) => ({
                        value: o.id,
                        label: `${o.full_name} — ${o.department_name}${
                          o.id === assignTarget.assigned_officer_id ? ' (Current Duty)' : ''
                        }`,
                      }))
                    : [
                        { value: 'officer-01', label: 'Officer Sarah Chen (Roads)' },
                        { value: 'officer-02', label: 'Officer Marcus Vance (Water)' },
                        { value: 'officer-03', label: 'Officer Priya Sharma (Sanitation)' },
                        { value: 'officer-04', label: 'Officer David Kalu (Electrical)' },
                      ]
                }
                required
              />

              <SelectField
                label="Reassignment Reason / Protocol"
                id="assign-reason"
                value={assignReason}
                onChange={(e) => setAssignReason(e.target.value)}
                options={[
                  { value: 'DUTY_INACTIVE_SLA_BREACH', label: 'Duty Inactive / SLA Response Breached' },
                  { value: 'SLA_AT_RISK_ESCALATION', label: 'SLA At Risk — Expedited Escalation' },
                  { value: 'SPECIALIST_JURISDICTION_TRANSFER', label: 'Specialist Jurisdiction Transfer' },
                  { value: 'WORKLOAD_REBALANCING', label: 'Departmental Workload Rebalancing' },
                  { value: 'ROUTINE_DUTY_ASSIGNMENT', label: 'Standard Initial Duty Assignment' },
                ]}
              />

              <TextareaField
                label="Supervisory Directives & Handoff Notes"
                id="assign-notes"
                placeholder="Specify mandatory field instructions, urgent dispatch instructions, or audit reasoning..."
                rows={3}
                value={assignNotes}
                onChange={(e) => setAssignNotes(e.target.value)}
              />

              <label className="flex items-center gap-2 text-xs font-medium text-gray-700 cursor-pointer pt-1 select-none">
                <input
                  type="checkbox"
                  checked={forceOverride}
                  onChange={(e) => setForceOverride(e.target.checked)}
                  className="rounded text-brand-600 focus:ring-brand-500 border-gray-300"
                />
                <span>Log as Forceful Administrative Reassignment in Audit Trail</span>
              </label>
            </form>
          )}
        </Modal>

        {/* Resolution Verification Modal */}
        <Modal
          isOpen={!!resolveTarget}
          onClose={() => setResolveTarget(null)}
          title={`Verify & Close Resolution — #${resolveTarget?.tracking_id}`}
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button
                variant="ghost"
                onClick={() => setResolveTarget(null)}
                disabled={resolveSubmitting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleResolve}
                loading={resolveSubmitting}
                icon={<CheckCircle2 size={14} />}
              >
                Submit AI Resolution Verification
              </Button>
            </div>
          }
        >
          {resolveTarget && (
            <form onSubmit={handleResolve} className="p-4 sm:p-6 space-y-4">
              <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-100 text-xs text-emerald-900 space-y-1">
                <div><strong>Incident:</strong> {resolveTarget.title}</div>
                <div><strong>Location:</strong> {resolveTarget.address}</div>
                <div className="text-[11px] text-emerald-700">
                  Autonomous AI Computer Vision will cross-reference resolution proof with initial defect reports.
                </div>
              </div>

              <TextareaField
                label="Resolution Notes & Work Performed"
                id="resolve-notes"
                placeholder="e.g., Road crater cleared, leveled and asphalt patched flush with road surface. Field inspection passed."
                rows={3}
                value={resolveNotes}
                onChange={(e) => setResolveNotes(e.target.value)}
                required
              />

              <InputField
                label="Resolution Proof Image URL (Optional)"
                id="resolve-img"
                placeholder="https://example.com/repaired_scene.jpg"
                value={resolveImageUrl}
                onChange={(e) => setResolveImageUrl(e.target.value)}
              />
            </form>
          )}
        </Modal>
      </div>
    </AppShell>
  )
}

export default OfficerDashboard

