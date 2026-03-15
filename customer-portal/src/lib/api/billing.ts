import apiClient from './client'
import type { Subscription, Invoice } from '@/types/subscription'
import type { PlanId } from '@/types/subscription'

export const billingApi = {
  getSubscription: async (): Promise<Subscription | null> => {
    const res = await apiClient.get('/api/subscriptions')
    const list: Subscription[] = res.data.subscriptions ?? res.data
    return list[0] ?? null
  },

  createCheckout: async (
    plan: PlanId,
    tenantName: string,
    urls?: { success_url?: string; cancel_url?: string },
  ): Promise<string> => {
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || window.location.origin
    const res = await apiClient.post('/billing/checkout', {
      plan,
      tenant_name: tenantName,
      success_url: urls?.success_url ?? `${appUrl}/billing?success=1`,
      cancel_url: urls?.cancel_url ?? `${appUrl}/billing`,
    })
    return res.data.url ?? res.data.checkout_url
  },

  createPortalSession: async (): Promise<string> => {
    const res = await apiClient.post('/billing/portal')
    return res.data.url
  },

  getInvoices: async (): Promise<Invoice[]> => {
    const res = await apiClient.get('/billing/invoices')
    return res.data.invoices ?? res.data
  },

  upgradePlan: async (subscriptionId: string, plan: PlanId): Promise<Subscription> => {
    const res = await apiClient.patch(`/api/subscriptions/${subscriptionId}`, { plan })
    return res.data
  },
}
