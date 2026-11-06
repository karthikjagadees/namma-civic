import React, { useEffect, useState, useCallback } from 'react'
import {
  Users,
  Building2,
  FileCode,
  ShieldCheck,
  Server,
  Database,
  Cpu,
  RefreshCw,
  Search,
  Plus,
  Clock,
  Edit2,
  Sliders,
  Mail,
  Send,
  Eye,
} from 'lucide-react'
import { notificationService, type SMTPStatus, type OutboxItem } from '../services/notificationService'
import { AppShell } from '../components/AppShell'
import {
  Button,
  Card,
  StatTile,
  Badge,
  Modal,
  InputField,
  SelectField,
  TextareaField,
  Alert,
  Skeleton,
} from '../components/ui'
import {
  adminService,
  type SystemHealthMetrics,
  type AdminUserItem,
  type AdminDepartmentItem,
  type AuditLogItem,
} from '../services/adminService'

type AdminTab = 'system' | 'users' | 'departments' | 'audit' | 'notifications'

export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AdminTab>('system')
  const [metrics, setMetrics] = useState<SystemHealthMetrics | null>(null)
  const [users, setUsers] = useState<AdminUserItem[]>([])
  const [departments, setDepartments] = useState<AdminDepartmentItem[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([])

  // Notifications / SMTP state
  const [smtpStatus, setSmtpStatus] = useState<SMTPStatus | null>(null)
  const [outboxLogs, setOutboxLogs] = useState<OutboxItem[]>([])
  const [testEmailTo, setTestEmailTo] = useState('citizen@demo.namma-civic.ai')
  const [testEmailSubj, setTestEmailSubj] = useState('Namma Civic — Test Notification Alert')
  const [testEmailMsg, setTestEmailMsg] = useState('Testing SMTP gateway connectivity from Namma Civic Admin Panel.')
  const [testEmailSending, setTestEmailSending] = useState(false)
  const [previewEmail, setPreviewEmail] = useState<OutboxItem | null>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Users Tab filters & state
  const [userRoleFilter, setUserRoleFilter] = useState('')
  const [userSearch, setUserSearch] = useState('')
  const [editUser, setEditUser] = useState<AdminUserItem | null>(null)
  const [editRole, setEditRole] = useState<string>('citizen')
  const [editActive, setEditActive] = useState<boolean>(true)
  const [userUpdating, setUserUpdating] = useState(false)

  // Departments Tab state
  const [createDeptModal, setCreateDeptModal] = useState(false)
  const [deptName, setDeptName] = useState('')
  const [deptCode, setDeptCode] = useState('')
  const [deptDesc, setDeptDesc] = useState('')
  const [deptCreating, setDeptCreating] = useState(false)

  const fetchTabData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      if (activeTab === 'system') {
        const data = await adminService.getSystemMetrics()
        setMetrics(data)
      } else if (activeTab === 'users') {
        const res = await adminService.listUsers(
          userRoleFilter || undefined,
          userSearch || undefined
        )
        setUsers(res.items || [])
      } else if (activeTab === 'departments') {
        const data = await adminService.listDepartments()
        setDepartments(data || [])
      } else if (activeTab === 'audit') {
        const logs = await adminService.getAuditLogs(50)
        setAuditLogs(logs || [])
      } else if (activeTab === 'notifications') {
        const [statusData, outboxData] = await Promise.all([
          notificationService.getStatus(),
          notificationService.getOutbox(50),
        ])
        setSmtpStatus(statusData)
        setOutboxLogs(outboxData)
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || `Failed to load ${activeTab} data.`)
    } finally {
      setLoading(false)
    }
  }, [activeTab, userRoleFilter, userSearch])

  const handleSendTestEmail = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!testEmailTo) return
    setTestEmailSending(true)
    setError(null)
    try {
      const res = await notificationService.sendTestEmail({
        to_email: testEmailTo,
        subject: testEmailSubj,
        message: testEmailMsg,
      })
      setSuccessMsg(`Test email dispatched to ${testEmailTo}! Delivery Status: ${res.status}`)
      const updated = await notificationService.getOutbox(50)
      setOutboxLogs(updated)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to dispatch test email.')
    } finally {
      setTestEmailSending(false)
    }
  }

  useEffect(() => {
    fetchTabData()
  }, [fetchTabData])

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editUser) return
    setUserUpdating(true)
    try {
      await adminService.updateUser(editUser.id, editRole, editActive)
      setSuccessMsg(`User ${editUser.email} updated successfully.`)
      setEditUser(null)
      fetchTabData()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to update user.')
    } finally {
      setUserUpdating(false)
    }
  }

  const handleCreateDepartment = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!deptName || !deptCode) return
    setDeptCreating(true)
    try {
      await adminService.createDepartment({
        name: deptName,
        code: deptCode.toUpperCase(),
        description: deptDesc,
      })
      setSuccessMsg(`Department "${deptName}" created successfully.`)
      setCreateDeptModal(false)
      setDeptName('')
      setDeptCode('')
      setDeptDesc('')
      fetchTabData()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create department.')
    } finally {
      setDeptCreating(false)
    }
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-gray-200">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-900" />
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-blue-900">
                Governance & Infrastructure
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              Admin Control Center
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              LangGraph engine status, user access management, department routing, and security audits.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw size={15} className={loading ? 'animate-spin' : ''} />}
              onClick={fetchTabData}
              disabled={loading}
            >
              Sync State
            </Button>
          </div>
        </div>

        {/* Notifications */}
        {successMsg && (
          <Alert variant="success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}
        {error && (
          <Alert variant="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Navigation Tabs (Mobile-Scrollable) */}
        <div className="border-b border-gray-200 overflow-x-auto scrollbar-none">
          <div className="flex items-center gap-2 min-w-max pb-px">
            {[
              { id: 'system', label: 'System Health & AI', icon: Server },
              { id: 'users', label: 'User Directory', icon: Users },
              { id: 'departments', label: 'Departments & Routing', icon: Building2 },
              { id: 'audit', label: 'Audit Trail', icon: FileCode },
              { id: 'notifications', label: 'Email & Alerts', icon: Mail },
            ].map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as AdminTab)}
                  className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all cursor-pointer ${
                    isActive
                      ? 'border-blue-900 text-blue-900 bg-blue-50/30'
                      : 'border-transparent text-gray-500 hover:text-gray-900 hover:border-gray-300'
                  }`}
                >
                  <Icon size={16} />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* TAB 1: SYSTEM HEALTH */}
        {activeTab === 'system' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
              <StatTile
                label="LangGraph State"
                value="ONLINE"
                sub={metrics?.langgraph_checkpointer || 'MemorySaver'}
                variant="success"
                icon={<Cpu size={20} />}
              />
              <StatTile
                label="AI Provider"
                value={metrics?.ai_provider_active || 'Gemini'}
                sub="Multimodal Intake"
                variant="default"
                icon={<Server size={20} />}
              />
              <StatTile
                label="MCP Server"
                value={metrics?.mcp_server_status || 'CONNECTED'}
                sub={`${metrics?.mcp_tools_active ?? 8} Tools Registered`}
                variant="success"
                icon={<Sliders size={20} />}
              />
              <StatTile
                label="Database Engine"
                value={metrics?.database_engine || 'SQLite/PostGIS'}
                sub="Spatial queries active"
                icon={<Database size={20} />}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Architecture Stack */}
              <Card className="p-4 sm:p-5 border border-gray-200">
                <h3 className="font-bold text-gray-900 text-base mb-3 flex items-center gap-2">
                  <ShieldCheck size={18} className="text-blue-900" />
                  Active Subsystem Architecture
                </h3>
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-500 font-medium">Core Orchestrator</span>
                    <span className="font-mono font-semibold text-gray-900">LangGraph 10-Agent Supervisor</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-500 font-medium">Model Context Protocol</span>
                    <span className="font-mono font-semibold text-emerald-600">MCP FastMCP Local & Remote</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-500 font-medium">Spatial Engine</span>
                    <span className="font-mono font-semibold text-gray-900">PostGIS Geometry + Geopy Fallback</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-500 font-medium">Audio Processing</span>
                    <span className="font-mono font-semibold text-gray-900">Whisper / Mock Voice Intake</span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-gray-500 font-medium">Environment</span>
                    <span className="font-mono font-semibold text-gray-900">{metrics?.environment || 'development'}</span>
                  </div>
                </div>
              </Card>

              {/* Status Breakdown */}
              <Card className="p-4 sm:p-5 border border-gray-200">
                <h3 className="font-bold text-gray-900 text-base mb-3 flex items-center gap-2">
                  <Clock size={18} className="text-blue-900" />
                  Grievance State Distribution
                </h3>
                {metrics?.metrics?.complaints_by_status ? (
                  <div className="space-y-2 text-xs">
                    {Object.entries(metrics.metrics.complaints_by_status).map(([st, count]) => (
                      <div key={st} className="flex justify-between items-center py-1.5 border-b border-gray-100">
                        <span className="text-gray-600 font-medium capitalize">{st.replace('_', ' ')}</span>
                        <span className="font-mono font-bold text-gray-900 bg-gray-100 px-2 py-0.5 rounded">
                          {count}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-500">Telemetry pipeline is collecting initial complaint states.</p>
                )}
              </Card>
            </div>
          </div>
        )}

        {/* TAB 2: USER DIRECTORY */}
        {activeTab === 'users' && (
          <div className="space-y-4">
            {/* Filter Bar */}
            <div className="card p-3 bg-white flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2 flex-1">
                <div className="relative flex-1 min-w-[180px] sm:max-w-xs">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search by name or email…"
                    value={userSearch}
                    onChange={(e) => setUserSearch(e.target.value)}
                    className="input pl-8 py-1.5 text-xs h-9"
                  />
                </div>

                <select
                  value={userRoleFilter}
                  onChange={(e) => setUserRoleFilter(e.target.value)}
                  className="input text-xs py-1.5 px-2.5 h-9 w-auto"
                >
                  <option value="">All Roles</option>
                  <option value="citizen">Citizen</option>
                  <option value="officer">Officer</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>

              <div className="text-xs font-mono text-gray-500 self-end sm:self-center">
                <strong>{users.length}</strong> registered accounts
              </div>
            </div>

            {/* User List */}
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Card key={i} className="p-4 space-y-2">
                    <Skeleton height={20} width={140} />
                    <Skeleton height={14} width="60%" />
                  </Card>
                ))}
              </div>
            ) : users.length === 0 ? (
              <Card className="p-8 text-center text-sm text-gray-500">
                No users match the search filters.
              </Card>
            ) : (
              <div className="space-y-2.5">
                {users.map((u) => (
                  <Card key={u.id} className="p-3.5 sm:p-4 border border-gray-200">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-gray-900">{u.full_name}</span>
                          <Badge
                            variant={
                              u.role === 'admin'
                                ? 'danger'
                                : u.role === 'officer'
                                ? 'info'
                                : 'neutral'
                            }
                            className="text-[10px]"
                          >
                            {u.role.toUpperCase()}
                          </Badge>
                          {!u.is_active && (
                            <Badge variant="warning" className="text-[10px]">
                              Suspended
                            </Badge>
                          )}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5">{u.email}</div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-center">
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={<Edit2 size={13} />}
                          onClick={() => {
                            setEditUser(u)
                            setEditRole(u.role)
                            setEditActive(u.is_active)
                          }}
                        >
                          Modify Role
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: DEPARTMENTS */}
        {activeTab === 'departments' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="font-bold text-gray-900 text-base">Civic Divisions & Dispatch Codes</h3>
                <p className="text-xs text-gray-500">Manage municipal departments and their automated routing queues.</p>
              </div>
              <Button
                variant="primary"
                size="sm"
                icon={<Plus size={14} />}
                onClick={() => setCreateDeptModal(true)}
              >
                Add Department
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {departments.map((d) => (
                <Card key={d.id} className="p-4 sm:p-5 border border-gray-200">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <h4 className="font-bold text-gray-900 text-base">{d.name}</h4>
                      <span className="font-mono text-xs font-bold text-blue-900 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">
                        {d.code}
                      </span>
                    </div>
                    <Badge variant="neutral" className="text-[11px]">
                      {d.active_caseload} Active
                    </Badge>
                  </div>
                  {d.description && <p className="text-xs text-gray-600 mb-3">{d.description}</p>}
                  <div className="text-xs text-gray-400 space-y-1 pt-2 border-t border-gray-100">
                    <div>Head: {d.head_name || 'Designated Chief Engineer'}</div>
                    <div>Contact: {d.contact_email || 'dispatch@namma-civic.gov'}</div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: AUDIT TRAIL */}
        {activeTab === 'audit' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1">
              <h3 className="font-bold text-gray-900 text-base">Security & Action Audit Trail</h3>
              <span className="text-xs font-mono text-gray-400">Latest 50 events</span>
            </div>

            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} height={36} width="100%" />
                ))}
              </div>
            ) : auditLogs.length === 0 ? (
              <Card className="p-8 text-center text-sm text-gray-500">
                Audit log stream is clear. Platform actions are recorded continuously.
              </Card>
            ) : (
              <div className="space-y-2">
                {auditLogs.map((log) => (
                  <div
                    key={log.id}
                    className="p-3 bg-white rounded-lg border border-gray-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-gray-900">{log.status}</span>
                      <span className="text-gray-600">{log.note}</span>
                    </div>
                    <span className="text-gray-400 font-mono text-[11px] shrink-0">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 5: EMAIL & ALERTS */}
        {activeTab === 'notifications' && (
          <div className="space-y-6">
            {/* Top Gateway Stat Tiles */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
              <StatTile
                label="Gateway Mode"
                value={smtpStatus?.mode === 'LIVE_SMTP' ? 'LIVE SMTP' : 'DEV SIMULATION'}
                sub={smtpStatus?.status_description || 'Active delivery transport'}
                variant={smtpStatus?.mode === 'LIVE_SMTP' ? 'success' : 'default'}
                icon={<Mail size={20} />}
              />
              <StatTile
                label="SMTP Host & Port"
                value={`${smtpStatus?.host || 'smtp.gmail.com'}:${smtpStatus?.port || 587}`}
                sub={`TLS: ${smtpStatus?.use_tls ? 'Enabled' : 'Disabled'}`}
                variant="default"
                icon={<Server size={20} />}
              />
              <StatTile
                label="Sender Address"
                value={smtpStatus?.from_address || 'noreply@namma-civic.ai'}
                sub={smtpStatus?.username_configured ? 'Authenticated' : 'Unauthenticated'}
                variant={smtpStatus?.username_configured ? 'success' : 'warning'}
                icon={<ShieldCheck size={20} />}
              />
              <StatTile
                label="Dispatches Logged"
                value={outboxLogs.length.toString()}
                sub="In-memory outbox audit"
                variant="default"
                icon={<Send size={20} />}
              />
            </div>

            {/* Test Email Card */}
            <Card className="p-4 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-gray-100">
                <div>
                  <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                    <Send size={18} className="text-blue-900" />
                    Dispatch Test Notification
                  </h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Send a live test alert to verify relay delivery to external mailboxes or dev outbox.
                  </p>
                </div>
                {smtpStatus?.mode === 'LIVE_SMTP' && (
                  <Badge variant="success">SMTP Relay Connected</Badge>
                )}
              </div>

              <form onSubmit={handleSendTestEmail} className="space-y-4 max-w-2xl">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <InputField
                    label="Recipient Email"
                    id="test-to"
                    type="email"
                    value={testEmailTo}
                    onChange={(e) => setTestEmailTo(e.target.value)}
                    required
                    placeholder="e.g., your_email@domain.com"
                  />
                  <InputField
                    label="Subject"
                    id="test-subj"
                    value={testEmailSubj}
                    onChange={(e) => setTestEmailSubj(e.target.value)}
                    required
                    placeholder="Email subject line"
                  />
                </div>
                <TextareaField
                  label="Diagnostic Message"
                  id="test-msg"
                  rows={2}
                  value={testEmailMsg}
                  onChange={(e) => setTestEmailMsg(e.target.value)}
                  placeholder="Body content for diagnostic test..."
                />
                <Button
                  variant="primary"
                  type="submit"
                  loading={testEmailSending}
                  icon={<Send size={14} />}
                >
                  {testEmailSending ? 'Sending Test…' : 'Send Test Alert'}
                </Button>
              </form>
            </Card>

            {/* Outbox Delivery Logs */}
            <Card className="p-4 sm:p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-base font-bold text-gray-900">Outbox Delivery Logs</h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Audit log of automated lifecycle notifications sent to citizens and municipal staff.
                  </p>
                </div>
                <Badge variant="neutral">{outboxLogs.length} Records</Badge>
              </div>

              {outboxLogs.length === 0 ? (
                <div className="p-8 text-center text-sm text-gray-500">
                  No outbound email alerts recorded yet. File a report or send a test email to populate the outbox.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-gray-200 text-gray-500 uppercase tracking-wider font-semibold">
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3">Event Type</th>
                        <th className="py-2.5 px-3">Recipient</th>
                        <th className="py-2.5 px-3">Subject</th>
                        <th className="py-2.5 px-3">Channel</th>
                        <th className="py-2.5 px-3">Timestamp</th>
                        <th className="py-2.5 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 font-mono">
                      {outboxLogs.map((item) => (
                        <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                          <td className="py-3 px-3">
                            <Badge
                              variant={
                                item.status === 'SENT' ? 'success' :
                                item.status === 'SIMULATED' ? 'primary' :
                                item.status === 'FAILED' ? 'danger' : 'neutral'
                              }
                            >
                              {item.status}
                            </Badge>
                          </td>
                          <td className="py-3 px-3 font-sans font-medium text-gray-900">
                            {item.event_type}
                          </td>
                          <td className="py-3 px-3 text-gray-700">{item.to_email}</td>
                          <td className="py-3 px-3 font-sans text-gray-800 max-w-xs truncate">
                            {item.subject}
                          </td>
                          <td className="py-3 px-3 text-gray-500">{item.delivery_channel}</td>
                          <td className="py-3 px-3 text-gray-400 text-[11px]">
                            {new Date(item.created_at).toLocaleTimeString()}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              icon={<Eye size={13} />}
                              onClick={() => setPreviewEmail(item)}
                            >
                              Preview
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        )}

        {/* Edit User Modal */}
        <Modal
          isOpen={!!editUser}
          onClose={() => setEditUser(null)}
          title={`Edit Account: ${editUser?.email}`}
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button variant="ghost" onClick={() => setEditUser(null)} disabled={userUpdating}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleUpdateUser} loading={userUpdating}>
                Save Changes
              </Button>
            </div>
          }
        >
          {editUser && (
            <form onSubmit={handleUpdateUser} className="p-4 sm:p-6 space-y-4">
              <SelectField
                label="Assigned Platform Role"
                id="edit-role"
                value={editRole}
                onChange={(e) => setEditRole(e.target.value)}
                options={[
                  { value: 'citizen', label: 'Citizen (Standard Access)' },
                  { value: 'officer', label: 'Field Officer (Dispatch & Triage)' },
                  { value: 'admin', label: 'System Administrator (Full Governance)' },
                ]}
              />

              <div className="pt-2">
                <label className="flex items-center gap-2 text-sm font-medium text-gray-900 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editActive}
                    onChange={(e) => setEditActive(e.target.checked)}
                    className="rounded text-blue-900 focus:ring-blue-900 h-4 w-4"
                  />
                  Account Active & Enabled
                </label>
                <p className="text-xs text-gray-500 mt-1">
                  Unchecking will immediately revoke platform authentication tokens.
                </p>
              </div>
            </form>
          )}
        </Modal>

        {/* Create Department Modal */}
        <Modal
          isOpen={createDeptModal}
          onClose={() => setCreateDeptModal(false)}
          title="Register New Municipal Department"
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button variant="ghost" onClick={() => setCreateDeptModal(false)} disabled={deptCreating}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleCreateDepartment} loading={deptCreating}>
                Create Department
              </Button>
            </div>
          }
        >
          <form onSubmit={handleCreateDepartment} className="p-4 sm:p-6 space-y-4">
            <InputField
              label="Department Name"
              id="dept-name"
              placeholder="e.g., Waste Management & Environmental"
              value={deptName}
              onChange={(e) => setDeptName(e.target.value)}
              required
            />

            <InputField
              label="Routing Code"
              id="dept-code"
              placeholder="e.g., ENV_DEPT"
              value={deptCode}
              onChange={(e) => setDeptCode(e.target.value)}
              required
            />

            <TextareaField
              label="Mission & Description"
              id="dept-desc"
              placeholder="Brief description of duties and response scopes."
              rows={3}
              value={deptDesc}
              onChange={(e) => setDeptDesc(e.target.value)}
            />
          </form>
        </Modal>

        {/* Email Preview Modal */}
        <Modal
          isOpen={!!previewEmail}
          onClose={() => setPreviewEmail(null)}
          title={`Email Preview: ${previewEmail?.subject}`}
          footer={
            <div className="flex items-center justify-end w-full">
              <Button variant="secondary" onClick={() => setPreviewEmail(null)}>
                Close Preview
              </Button>
            </div>
          }
        >
          {previewEmail && (
            <div className="p-4 sm:p-6 space-y-4">
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 text-xs space-y-1 font-mono">
                <div><span className="text-gray-400">To:</span> {previewEmail.to_email}</div>
                <div><span className="text-gray-400">From:</span> {previewEmail.from_email}</div>
                <div><span className="text-gray-400">Event:</span> {previewEmail.event_type}</div>
                <div><span className="text-gray-400">Channel:</span> {previewEmail.delivery_channel}</div>
              </div>
              <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
                <div
                  className="p-4 max-h-96 overflow-y-auto"
                  dangerouslySetInnerHTML={{ __html: previewEmail.html_preview }}
                />
              </div>
            </div>
          )}
        </Modal>
      </div>
    </AppShell>
  )
}

export default AdminPage
