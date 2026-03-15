import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { billingApi } from '@/lib/api/billing'
import { toast } from 'sonner'
import type { PlanId } from '@/types/subscription'

export const useSubscription = () =>
  useQuery({ queryKey: ['subscription'], queryFn: billingApi.getSubscription })

export const useInvoices = () =>
  useQuery({ queryKey: ['invoices'], queryFn: billingApi.getInvoices })

export const useUpgradePlan = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ subscriptionId, plan }: { subscriptionId: string; plan: PlanId }) =>
      billingApi.upgradePlan(subscriptionId, plan),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscription'] })
      toast.success('Plan updated successfully')
    },
    onError: () => toast.error('Failed to update plan'),
  })
}
