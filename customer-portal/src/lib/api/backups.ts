import apiClient from './client'
import type { Backup, RestoreRequest } from '@/types/backup'

export const backupsApi = {
  list: async (tenantId: number): Promise<Backup[]> => {
    const res = await apiClient.get(`/api/backups/${tenantId}`)
    return res.data.backups ?? res.data
  },

  create: async (tenantId: number): Promise<Backup> => {
    const res = await apiClient.post(`/api/backups/${tenantId}`)
    return res.data
  },

  restore: async (backupId: number, data: RestoreRequest): Promise<void> => {
    await apiClient.post(`/api/backups/${backupId}/restore`, data)
  },
}
