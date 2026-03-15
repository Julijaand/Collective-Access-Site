'use client'

import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { LayoutGrid, Database, CreditCard, Users } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className="text-2xl font-bold">{value}</p>
        )}
      </CardContent>
    </Card>
  )
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

  const activeTenants = tenants?.filter((t) => t.status === 'active').length ?? 0
  const totalTenants = tenants?.length ?? 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Welcome back, {user?.email?.split('@')[0] ?? 'there'} 👋</h1>
        <p className="text-muted-foreground mt-1">Here's an overview of your Collective Access instances.</p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Instances" value={totalTenants} icon={LayoutGrid} loading={tenantsLoading} />
        <StatCard title="Active Instances" value={activeTenants} icon={Database} loading={tenantsLoading} />
        <StatCard
          title="Current Plan"
          value={subscription?.plan ?? '—'}
          icon={CreditCard}
          loading={subLoading}
        />
        <StatCard
          title="Member Since"
          value={user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
          icon={Users}
          loading={false}
        />
      </div>

      {/* Recent Tenants */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Your Instances</CardTitle>
          <Button asChild size="sm">
            <Link href="/tenants">View all</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {tenantsLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : tenants?.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>No instances yet.</p>
              <Button asChild className="mt-4">
                <Link href="/tenants">Create your first instance</Link>
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {tenants?.slice(0, 5).map((tenant) => (
                <div key={tenant.id} className="flex items-center justify-between rounded-lg border px-4 py-3">
                  <div>
                    <p className="font-medium text-sm">{tenant.name}</p>
                    <p className="text-xs text-muted-foreground">{tenant.domain}</p>
                  </div>
                  <Badge variant={tenant.status === 'active' ? 'default' : 'secondary'}>
                    {tenant.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
