import apiClient from './client'
import type { TeamMember, InviteMemberRequest } from '@/types/team'

export const teamApi = {
  list: async (tenantId: number): Promise<TeamMember[]> => {
    const res = await apiClient.get(`/api/teams/${tenantId}/members`)
    return res.data.members ?? res.data
  },

  invite: async (tenantId: number, data: InviteMemberRequest): Promise<void> => {
    await apiClient.post(`/api/teams/${tenantId}/invite`, data)
  },

  updateRole: async (tenantId: number, memberId: number, role: string): Promise<void> => {
    await apiClient.patch(`/api/teams/${tenantId}/members/${memberId}`, { role })
  },

  remove: async (tenantId: number, memberId: number): Promise<void> => {
    await apiClient.delete(`/api/teams/${tenantId}/members/${memberId}`)
  },
}
