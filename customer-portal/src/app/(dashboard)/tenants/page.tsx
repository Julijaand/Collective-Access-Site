'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Plus, ExternalLink, Trash2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useTenants, useDeleteTenant } from '@/lib/hooks/useTenants'
import { tenantsApi } from '@/lib/api/tenants'
import { useQueryClient } from '@tanstack/react-query'
import type { Tenant, TenantStatus } from '@/types/tenant'

const STATUS_COLORS: Record<TenantStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  active: 'default',
  provisioning: 'secondary',
  suspended: 'destructive',
  error: 'destructive',
  deleting: 'outline',
}

function CreateTenantDialog() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ name: '', domain: '', plan: 'starter', admin_email: '', admin_password: '' })

  const handleSubmit = async () => {
    if (!form.name || !form.domain || !form.admin_email) {
      toast.error('Name, domain and admin email are required')
      return
    }
    setLoading(true)
    try {
      await tenantsApi.provision({ name: form.name, plan: form.plan as Tenant['plan'], admin_email: form.admin_email, admin_password: form.admin_password || 'changeme', organization: form.name })
      toast.success('Instance is being provisioned!')
      qc.invalidateQueries({ queryKey: ['tenants'] })
      setOpen(false)
      setForm({ name: '', domain: '', plan: 'starter', admin_email: '', admin_password: '' })
    } catch {
      toast.error('Failed to create instance')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button><Plus className="mr-2 h-4 w-4" /> New Instance</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create a new instance</DialogTitle>
          <DialogDescription>Provision a new Collective Access instance for your organization.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1">
            <Label>Name</Label>
            <Input placeholder="My Museum" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label>Domain</Label>
            <Input placeholder="my-museum.yourdomain.com" value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value.toLowerCase().replace(/\s+/g, '-') })} />
          </div>
          <div className="space-y-1">
            <Label>Admin Email</Label>
            <Input type="email" placeholder="admin@museum.org" value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label>Plan</Label>
            <Select value={form.plan} onValueChange={(v) => setForm({ ...form, plan: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="starter">Starter</SelectItem>
                <SelectItem value="pro">Pro</SelectItem>
                <SelectItem value="museum">Museum</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : null}
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function TenantsPage() {
  const { data: tenants, isLoading } = useTenants()
  const deleteTenant = useDeleteTenant()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Instances</h1>
          <p className="text-muted-foreground mt-1">Manage your Collective Access instances.</p>
        </div>
        <CreateTenantDialog />
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-lg" />)}
        </div>
      ) : tenants?.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center py-12 text-center">
            <p className="text-muted-foreground">No instances yet. Create your first one!</p>
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
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => deleteTenant.mutate(tenant.id)}
                    disabled={deleteTenant.isPending}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
