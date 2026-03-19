'use client'

import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useTenants } from '@/lib/hooks/useTenants'
import type { TenantStatus } from '@/types/tenant'

const STATUS_COLORS: Record<TenantStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  active: 'default',
  provisioning: 'secondary',
  suspended: 'destructive',
  error: 'destructive',
  deleting: 'outline',
}

export default function TenantsPage() {
  const { data: tenants, isLoading } = useTenants()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Instances</h1>
        <p className="text-muted-foreground mt-1">
          Your Collective Access instances. Each subscription automatically provisions one dedicated instance.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-lg" />)}
        </div>
      ) : tenants?.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center py-12 text-center gap-4">
            <p className="text-muted-foreground">No instances yet.</p>
            <p className="text-sm text-muted-foreground">
              Purchase a subscription on the{' '}
              <Link href="/billing" className="underline underline-offset-4 text-foreground">
                Billing page
              </Link>{' '}
              and your instance will be provisioned automatically.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tenants?.map((tenant) => (
            <Card key={tenant.id} className="flex flex-col">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-base">{tenant.name}</CardTitle>
                  <Badge variant={STATUS_COLORS[tenant.status]}>{tenant.status}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">{tenant.domain}</p>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col justify-end gap-2">
                <div className="flex gap-2 pt-2">
                  <Button asChild variant="outline" size="sm" className="flex-1">
                    <Link href={`/tenants/${tenant.id}`}>Details</Link>
                  </Button>
                  {tenant.status === 'active' && (
                    <Button variant="outline" size="sm" asChild>
                      <a href={`https://${tenant.domain}`} target="_blank" rel="noreferrer">
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </Button>
                  )}

                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
