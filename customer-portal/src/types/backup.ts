export type BackupStatus = 'completed' | 'in_progress' | 'failed'
export type BackupType = 'automatic' | 'manual'

export interface Backup {
  id: number
  tenant_id: number
  type: BackupType
  status: BackupStatus
  size_mb: number
  created_at: string
  storage_location?: string
}

export interface RestoreRequest {
  target_tenant_id: number
  confirm: boolean
}
