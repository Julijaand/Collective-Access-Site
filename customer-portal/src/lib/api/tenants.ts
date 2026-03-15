import apiClient from './client'
import type { Tenant, TenantMetrics, CreateTenantRequest } from '@/types/tenant'

export const tenantsApi = {
  list: async (): Promise<Tenant[]> => {
    const res = await apiClient.get('/api/tenants')
    return res.data.tenants ?? res.data
  },

  get: async (id: number): Promise<Tenant> => {
    const res = await apiClient.get(`/api/tenants/${id}`)
    return res.data
  },

  provision: async (data: CreateTenantRequest): Promise<Tenant> => {
    const res = await apiClient.post('/tenants/provision', data)
    return res.data
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/tenants/${id}`)
  },

  getMetrics: async (id: number): Promise<TenantMetrics> => {
    const res = await apiClient.get(`/api/tenants/${id}/metrics`)
    return res.data
  },
}
