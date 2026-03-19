'use client'

import Link from 'next/link'
import { ExternalLink, RefreshCw } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { CreditCard, Server, Users } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { tenantsApi } from '@/lib/api/tenants'
import { billingApi } from '@/lib/api/billing'
import { useAuthStore } from '@/lib/stores/authStore'

function StatCard({
  title, value, icon: Icon, loading,
}: { title: string; value: string | number; icon: React.ElementType; loading: boolean }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {loading ? <Skeleton className="h-8 w-24" /> : <p className="text-2xl font-bold capitalize">{value}</p>}
      </CardContent>
    </Card>
  )
}

const STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  active: 'default',
  provisioning: 'secondary',
  suspended: 'destructive',
  error: 'destructive',
  deleting: 'outline',
}

export default function DashboardPage() {
  const { user } = useAuthStore()

  const { data: tenants, isLoading: tenantsLoading } = useQuery({
    queryKey: ['tenants'],
    queryFn: tenantsApi.list,
  })

  const { data: subscription, isLoading: subLoading } = useQuery({
    queryKey: ['subscription'],
    queryFn: billingApi.getSubscription,
  })

  // 1 subscription = 1 tenant
  const tenant = tenants?.[0] ?? null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Welcome back, {user?.email?.split('@')[0] ?? 'there'} 👋</h1>
        <p className="text-muted-foreground mt-1">Here's an overview of your Collective Access account.</p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          title="Current Plan"
          value={subscription?.plan ?? (subLoading ? '' : 'No plan')}
          icon={CreditCard}
          loading={subLoading}
        />
        <StatCard
          title="Instance Status"
          value={tenant?.status ?? (tenantsLoading ? '' : 'Not provisioned')}
          icon={Server}
          loading={tenantsLoading}
        />
        <StatCard
          title="Member Since"
          value={user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
          icon={Users}
          loading={false}
        />
      </div>

      {/* Instance card */}
      <Card>
        <CardHeader>
          <CardTitle>Your Instance</CardTitle>
          <CardDescription>Your dedicated Collective Access installation</CardDescription>
        </CardHeader>
        <CardContent>
          {tenantsLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : !tenant ? (
            <div className="flex flex-col items-center py-8 text-center gap-3">
              <p className="text-muted-foreground">No instance yet.</p>
              <p className="text-sm text-muted-foreground">
                Purchase a subscription on the Billing page and your instance will be provisioned automatically.
              </p>
              <Button asChild className="mt-2">
                <Link href="/billing">Go to Billing</Link>
              </Button>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-lg border px-4 py-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <p className="font-medium">{tenant.namespace}</p>
                  <Badge variant={STATUS_VARIANT[tenant.status] ?? 'secondary'}>{tenant.status}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">{tenant.domain}</p>

              </div>
              <div className="flex gap-2">
                <Button asChild variant="outline" size="sm">
                  <Link href={`/tenants/${tenant.id}`}>
                    <RefreshCw className="mr-1 h-3 w-3" /> Details
                  </Link>
                </Button>
                {tenant.status === 'active' && (
                  <Button asChild size="sm">
                    <a href={`https://${tenant.domain}`} target="_blank" rel="noreferrer">
                      <ExternalLink className="mr-1 h-3 w-3" /> Open
                    </a>
                  </Button>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
