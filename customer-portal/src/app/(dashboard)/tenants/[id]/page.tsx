'use client'

import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, ExternalLink, Trash2, RefreshCw, Cpu, HardDrive, MemoryStick } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useTenant, useTenantMetrics, useDeleteTenant } from '@/lib/hooks/useTenants'

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const tenantId = Number(id)
  const { data: tenant, isLoading } = useTenant(tenantId)
  const { data: metrics, isLoading: metricsLoading } = useTenantMetrics(tenantId)
  const deleteTenant = useDeleteTenant()

  const handleDelete = () => {
    if (confirm(`Delete "${tenant?.name}"? This cannot be undone.`)) {
      deleteTenant.mutate(tenantId, { onSuccess: () => router.push('/tenants') })
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!tenant) {
    return <p className="text-muted-foreground">Instance not found.</p>
  }

  const cpuData: { t: number; value: number }[] = []
  const memData: { t: number; value: number }[] = []

  return (
    <div className="space-y-6">
      {/* Back + Title */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push('/tenants')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{tenant.name}</h1>
          <p className="text-sm text-muted-foreground">{tenant.domain}</p>
        </div>
        <Badge variant={tenant.status === 'active' ? 'default' : 'secondary'}>{tenant.status}</Badge>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2">
        {tenant.status === 'active' && (
          <Button variant="outline" asChild>
            <a href={`https://${tenant.domain}`} target="_blank" rel="noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" /> Open
            </a>
          </Button>
        )}
        <Button variant="destructive" onClick={handleDelete} disabled={deleteTenant.isPending}>
          {deleteTenant.isPending
            ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            : <Trash2 className="mr-2 h-4 w-4" />}
          Delete
        </Button>
      </div>

      {/* Info Card */}
      <Card>
        <CardHeader><CardTitle>Details</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 text-sm">
          <div><p className="text-muted-foreground">ID</p><p className="font-mono">{tenant.id}</p></div>
          <div><p className="text-muted-foreground">Plan</p><p className="capitalize">{tenant.plan}</p></div>
          <div><p className="text-muted-foreground">Created</p><p>{new Date(tenant.created_at).toLocaleDateString()}</p></div>
          <div><p className="text-muted-foreground">Namespace</p><p className="font-mono text-xs">{tenant.namespace}</p></div>
        </CardContent>
      </Card>

      {/* Metrics */}
      <div className="grid gap-4 lg:grid-cols-3">
        {[
          { title: 'CPU Usage', icon: Cpu, value: metrics?.cpu_usage_percent, unit: '%', data: cpuData },
          { title: 'Memory Usage', icon: MemoryStick, value: (metrics?.memory_usage_mb != null && metrics?.memory_limit_mb) ? Math.round(metrics.memory_usage_mb / metrics.memory_limit_mb * 100) : undefined, unit: '%', data: memData },
          { title: 'Storage Used', icon: HardDrive, value: metrics?.storage_used_gb, unit: ' GB', data: [] },
        ].map(({ title, icon: Icon, value, unit, data }) => (
          <Card key={title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {metricsLoading
                ? <Skeleton className="h-8 w-20" />
                : <p className="text-2xl font-bold">{value ?? '—'}{value != null ? unit : ''}</p>}
              {data.length > 0 && (
                <ResponsiveContainer width="100%" height={60} className="mt-3">
                  <LineChart data={data}>
                    <Line type="monotone" dataKey="value" dot={false} strokeWidth={2} stroke="hsl(var(--primary))" />
                    <Tooltip formatter={(v) => [`${v}${unit}`, '']} labelFormatter={() => ''} />
                    <XAxis dataKey="t" hide />
                    <YAxis hide domain={[0, 100]} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
