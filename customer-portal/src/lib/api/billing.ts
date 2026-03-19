import apiClient from './client'
import type { Subscription, Invoice } from '@/types/subscription'
import type { PlanId } from '@/types/subscription'

export const billingApi = {
  getSubscription: async (): Promise<Subscription | null> => {
    const res = await apiClient.get('/api/subscriptions')
    const list: Subscription[] = res.data.subscriptions ?? res.data
    // Ignore canceled subscriptions — treat them as no subscription
    const active = list.find((s) => s.status !== 'canceled') ?? null
    return active
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

  confirmCheckout: async (sessionId: string): Promise<{ status: string; tenant_id?: number }> => {
    const res = await apiClient.post('/billing/checkout/confirm', { session_id: sessionId })
    return res.data
  },

  createPortalSession: async (opts?: { subscriptionId?: string }): Promise<string> => {
    const res = await apiClient.post('/billing/portal', opts ?? {})
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
