import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tenantsApi } from '@/lib/api/tenants'
import { toast } from 'sonner'

export const useTenants = () =>
  useQuery({
    queryKey: ['tenants'],
    queryFn: tenantsApi.list,
    // Poll every 4s while any tenant is provisioning
    refetchInterval: (query) => {
      const tenants = query.state.data
      if (Array.isArray(tenants) && tenants.some((t) => t.status === 'provisioning')) return 2000
      return false
    },
  })

export const useTenant = (id: number) =>
  useQuery({
    queryKey: ['tenant', id],
    queryFn: () => tenantsApi.get(id),
    enabled: !!id,
    // Poll every 4s while provisioning
    refetchInterval: (query) => {
      const tenant = query.state.data
      if (tenant?.status === 'provisioning') return 2000
      return false
    },
  })

export const useTenantMetrics = (id: number) =>
  useQuery({
    queryKey: ['tenant-metrics', id],
    queryFn: () => tenantsApi.getMetrics(id),
    enabled: !!id,
    refetchInterval: 30000,
  })

export const useDeleteTenant = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: tenantsApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tenants'] })
      toast.success('Tenant deleted')
    },
    onError: () => toast.error('Failed to delete tenant'),
  })
}
