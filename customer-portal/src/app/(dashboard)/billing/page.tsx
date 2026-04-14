'use client'

import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { CreditCard, ExternalLink, Check, RefreshCw, Rocket } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useSubscription, useInvoices } from '@/lib/hooks/useSubscription'
import { billingApi } from '@/lib/api/billing'
import { PLANS, type PlanId } from '@/types/subscription'

export default function BillingPage() {
  const searchParams = useSearchParams()
  const { data: subscription, isLoading: subLoading, refetch: refetchSub } = useSubscription()
  const { data: invoices, isLoading: invLoading } = useInvoices()
  const [portalLoading, setPortalLoading] = useState(false)

  // Subscribe dialog state
  const [checkoutPlan, setCheckoutPlan] = useState<PlanId | null>(null)
  const [tenantName, setTenantName] = useState('')
  const [checkoutLoading, setCheckoutLoading] = useState(false)

  // Handle ?success=1 redirect from Stripe — confirm and provision tenant
  useEffect(() => {
    if (searchParams.get('success') !== '1') return
    const sessionId = searchParams.get('session_id')
    if (sessionId) {
      billingApi.confirmCheckout(sessionId)
        .then((res) => {
          if (res.status === 'provisioned') {
            toast.success('Payment successful! Your instance is being provisioned — check the Instances page in a few minutes.')
          } else if (res.status === 'already_provisioned') {
            toast.success('Payment confirmed — your instance is already provisioned.')
          } else {
            toast.info('Payment received. Provisioning will complete shortly.')
          }
        })
        .catch(() => {
          toast.success('Payment successful! Your instance is being provisioned — check the Instances page in a few minutes.')
        })
        .finally(() => refetchSub())
    } else {
      // Returning from Customer Portal (upgrade/cancel) — no session_id
      toast.success('Subscription updated successfully.')
      refetchSub()
    }
  }, [searchParams, refetchSub])

  const openPortal = async () => {
    setPortalLoading(true)
    try {
      const url = await billingApi.createPortalSession()
      window.location.href = url
    } catch {
      toast.error('Could not open billing portal')
    } finally {
      setPortalLoading(false)
    }
  }

  const openPortalForUpgrade = async (plan: PlanId) => {
    if (!subscription) return
    setPortalLoading(true)
    try {
      const url = await billingApi.createPortalSession({ subscriptionId: subscription.id })
      window.location.href = url
    } catch {
      toast.error('Could not open upgrade page')
    } finally {
      setPortalLoading(false)
    }
  }

  const startCheckout = async () => {
    if (!tenantName.trim()) {
      toast.error('Please enter a name for your instance')
      return
    }
    if (!checkoutPlan) return
    setCheckoutLoading(true)
    try {
      const appUrl = process.env.NEXT_PUBLIC_APP_URL || window.location.origin
      const url = await billingApi.createCheckout(checkoutPlan, tenantName.trim(), {
        success_url: `${appUrl}/billing?success=1`,
        cancel_url: `${appUrl}/billing`,
      })
      window.location.href = url
    } catch {
      toast.error('Could not start checkout. Please try again.')
      setCheckoutLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Billing &amp; Plans</h1>
        <p className="text-muted-foreground mt-1">Manage your subscription and payment details.</p>
      </div>

      {/* Current Plan */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Current Plan</CardTitle>
            <CardDescription>Your active subscription</CardDescription>
          </div>
          {subscription && (
            <Button variant="outline" onClick={openPortal} disabled={portalLoading}>
              {portalLoading
                ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                : <ExternalLink className="mr-2 h-4 w-4" />}
              Manage Billing
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {subLoading ? (
            <Skeleton className="h-10 w-48" />
          ) : subscription ? (
            <div className="flex items-center gap-4">
              <div>
                <p className="text-xl font-bold capitalize">{subscription.plan}</p>
                <p className="text-sm text-muted-foreground">
                  Renews {new Date(subscription.current_period_end).toLocaleDateString()}
                </p>
              </div>
              <Badge variant={subscription.status === 'active' ? 'default' : 'secondary'}>
                {subscription.status}
              </Badge>
            </div>
          ) : (
            <p className="text-muted-foreground">No active subscription — choose a plan below to get started.</p>
          )}
        </CardContent>
      </Card>

      {/* Plans */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Available Plans</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PLANS.map((plan) => {
            const isCurrent = subscription?.plan === plan.id
            const isHigher = subscription
              ? (plan.price_eur ?? 0) > (PLANS.find((p) => p.id === subscription.plan)?.price_eur ?? 0)
              : false
            return (
              <Card key={plan.id} className={`flex flex-col h-full ${isCurrent ? 'border-primary ring-1 ring-primary' : ''}`}>
                <CardHeader>
                  <CardTitle className="text-base">{plan.name}</CardTitle>
                  <p className="text-2xl font-bold">
                    {plan.price_eur !== null ? `€${plan.price_eur}` : 'Custom'}
                    {plan.price_eur !== null && <span className="text-sm font-normal text-muted-foreground">/mo</span>}
                  </p>
                </CardHeader>
                <CardContent className="flex flex-col flex-1 gap-4">
                  <ul className="space-y-1 text-sm flex-1">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-center gap-2">
                        <Check className="h-3 w-3 text-green-500 shrink-0" /> {f}
                      </li>
                    ))}
                  </ul>
                  <div className="mt-auto">
                  {isCurrent ? (
                    <Button className="w-full" disabled>Current plan</Button>
                  ) : plan.id === 'enterprise' ? (
                    <Button className="w-full" variant="outline" asChild>
                      <a href="mailto:sales@yourdomain.com">Contact sales</a>
                    </Button>
                  ) : subscription ? (
                    /* Existing subscriber: redirect to Stripe portal upgrade flow */
                    <Button
                      className="w-full"
                      variant="outline"
                      onClick={() => openPortalForUpgrade(plan.id)}
                      disabled={portalLoading}
                    >
                      {portalLoading ? <RefreshCw className="mr-2 h-3 w-3 animate-spin" /> : null}
                      {isHigher ? 'Upgrade' : 'Switch'}
                    </Button>
                  ) : (
                    /* New user: open subscribe dialog */
                    <Button
                      className="w-full"
                      onClick={() => { setCheckoutPlan(plan.id); setTenantName('') }}
                    >
                      <Rocket className="mr-2 h-4 w-4" /> Subscribe
                    </Button>
                  )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>

      <Separator />

      {/* Invoices */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Invoice History</h2>
        {invLoading ? (
          <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
        ) : invoices?.length === 0 ? (
          <p className="text-muted-foreground">No invoices yet.</p>
        ) : (
          <Card>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="border-b">
                  <tr className="text-left text-muted-foreground">
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Amount</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {invoices?.map((inv) => (
                    <tr key={inv.id} className="border-b last:border-0">
                      <td className="px-4 py-3">{new Date(inv.created).toLocaleDateString()}</td>
                      <td className="px-4 py-3">€{(inv.amount_paid / 100).toFixed(2)}</td>
                      <td className="px-4 py-3">
                        <Badge variant={inv.status === 'paid' ? 'default' : 'secondary'}>{inv.status}</Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {inv.invoice_pdf && (
                          <Button variant="ghost" size="sm" asChild>
                            <a href={inv.invoice_pdf} target="_blank" rel="noreferrer">
                              <CreditCard className="mr-1 h-3 w-3" /> PDF
                            </a>
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Subscribe Dialog */}
      <Dialog open={!!checkoutPlan} onOpenChange={(open) => !open && setCheckoutPlan(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Subscribe to {PLANS.find((p) => p.id === checkoutPlan)?.name}</DialogTitle>
            <DialogDescription>
              Give your Collective Access instance a name. You&apos;ll be taken to Stripe to complete payment — your instance will be provisioned automatically after checkout.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="tenant-name">Instance name</Label>
            <Input
              id="tenant-name"
              placeholder="e.g. My Museum"
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && startCheckout()}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCheckoutPlan(null)}>Cancel</Button>
            <Button onClick={startCheckout} disabled={checkoutLoading || !tenantName.trim()}>
              {checkoutLoading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
              Go to checkout
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
