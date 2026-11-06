import api from './api';

export interface AdminUserItem {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: 'citizen' | 'officer' | 'admin';
  is_active: boolean;
  is_verified: boolean;
  department_id: string | null;
  created_at: string;
  last_login_at: string | null;
}

export interface AdminUserListResponse {
  total: number;
  items: AdminUserItem[];
  skip: number;
  limit: number;
}

export interface AdminDepartmentItem {
  id: string;
  name: string;
  code: string;
  description: string | null;
  head_name: string | null;
  contact_email: string | null;
  active_caseload: number;
}

export interface SystemHealthMetrics {
  system_name: string;
  version: string;
  environment: string;
  database_engine: string;
  ai_provider_active: string;
  langgraph_checkpointer: string;
  mcp_server_status: string;
  mcp_tools_active: number;
  telemetry_timestamp: string;
  metrics: {
    complaints_by_status: Record<string, number>;
    users_by_role: Record<string, number>;
  };
}

export interface AuditLogItem {
  id: string;
  complaint_id: string;
  status: string;
  note: string;
  created_at: string;
}

export const adminService = {
  async listUsers(role?: string, search?: string, isActive?: boolean): Promise<AdminUserListResponse> {
    const params = new URLSearchParams();
    if (role) params.append('role', role);
    if (search) params.append('search', search);
    if (isActive !== undefined) params.append('is_active', String(isActive));
    const res = await api.get<AdminUserListResponse>(`/admin/users?${params.toString()}`);
    return res.data;
  },

  async updateUser(
    userId: string,
    role?: string,
    isActive?: boolean,
    deptId?: string
  ): Promise<any> {
    const res = await api.patch(`/admin/users/${userId}`, {
      role,
      is_active: isActive,
      department_id: deptId,
    });
    return res.data;
  },

  async listDepartments(): Promise<AdminDepartmentItem[]> {
    const res = await api.get<AdminDepartmentItem[]>('/admin/departments');
    return res.data;
  },

  async createDepartment(data: { name: string; code: string; description?: string }): Promise<any> {
    const res = await api.post('/admin/departments', data);
    return res.data;
  },

  async getSystemMetrics(): Promise<SystemHealthMetrics> {
    const res = await api.get<SystemHealthMetrics>('/admin/system/metrics');
    return res.data;
  },

  async getAuditLogs(limit = 50): Promise<AuditLogItem[]> {
    const res = await api.get<AuditLogItem[]>(`/admin/audit-logs?limit=${limit}`);
    return res.data;
  },
};
