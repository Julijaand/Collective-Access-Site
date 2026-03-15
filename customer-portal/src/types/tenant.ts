export type TenantStatus =
  | 'provisioning'
  | 'active'
  | 'error'
  | 'suspended'
  | 'deleting'

export interface Tenant {
  id: number
  name: string
  namespace: string
  domain: string
  status: TenantStatus
  plan: 'starter' | 'pro' | 'museum' | 'enterprise'
  storage_gb: number
  max_users: number
  created_at: string
  updated_at: string
  metadata?: {
    helm_release?: string
    ingress_ip?: string
  }
}

export interface TenantMetrics {
  tenant_id: number
  namespace: string
  health_status: 'healthy' | 'degraded' | 'down'
  pods_total: number
  pods_running: number
  pods_pending: number
  pods_failed: number
  // Optional extended metrics (not yet returned by backend)
  cpu_usage_percent?: number
  memory_usage_mb?: number
  memory_limit_mb?: number
  storage_used_gb?: number
}

export interface CreateTenantRequest {
  name: string
  plan: Tenant['plan']
  admin_email: string
  admin_password: string
  organization?: string
}
