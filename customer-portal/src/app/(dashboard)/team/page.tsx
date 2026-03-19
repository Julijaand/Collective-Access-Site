'use client'

import { useState } from 'react'
import { UserPlus, Trash2, RefreshCw } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { teamApi } from '@/lib/api/team'
import { useTenants } from '@/lib/hooks/useTenants'
import type { TeamRole } from '@/types/team'

const inviteSchema = z.object({
  email: z.string().email('Invalid email'),
  role: z.enum(['admin', 'editor', 'viewer']),
})
type InviteForm = z.infer<typeof inviteSchema>

export default function TeamPage() {
  const qc = useQueryClient()
  const [inviteOpen, setInviteOpen] = useState(false)
  const { data: tenants } = useTenants()
  const tenantId = tenants?.[0]?.id ?? null

  const { data: members, isLoading } = useQuery({
    queryKey: ['team', tenantId],
    queryFn: () => teamApi.list(tenantId!),
    enabled: tenantId !== null,
  })

  const invite = useMutation({
    mutationFn: (data: InviteForm) => teamApi.invite(tenantId!, { email: data.email, role: data.role }),
    onSuccess: () => { toast.success('Invitation sent!'); qc.invalidateQueries({ queryKey: ['team', tenantId] }); setInviteOpen(false) },
    onError: () => toast.error('Failed to invite member'),
  })

  const remove = useMutation({
    mutationFn: (userId: number) => teamApi.remove(tenantId!, userId),
    onSuccess: () => { toast.success('Member removed'); qc.invalidateQueries({ queryKey: ['team', tenantId] }) },
    onError: () => toast.error('Failed to remove member'),
  })

  const form = useForm<InviteForm>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: '', role: 'viewer' },
  })

  const roleColors: Record<TeamRole, 'default' | 'secondary' | 'outline'> = {
    owner: 'default', admin: 'default', editor: 'secondary', viewer: 'outline',
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Team</h1>
          <p className="text-muted-foreground mt-1">Manage access to your instances.</p>
        </div>
        <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
          <DialogTrigger asChild>
            <Button disabled={tenantId === null}><UserPlus className="mr-2 h-4 w-4" /> Invite</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Invite a team member</DialogTitle>
              <DialogDescription>They'll receive an email invitation.</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit((d) => invite.mutate(d))} className="space-y-4 py-2">
                <FormField control={form.control} name="email" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl><Input placeholder="colleague@museum.org" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="role" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Role</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                      <SelectContent>
                        <SelectItem value="admin">Admin</SelectItem>
                        <SelectItem value="editor">Editor</SelectItem>
                        <SelectItem value="viewer">Viewer</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setInviteOpen(false)}>Cancel</Button>
                  <Button type="submit" disabled={invite.isPending}>
                    {invite.isPending && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />} Send Invite
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader><CardTitle>Members</CardTitle></CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-4 space-y-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
          ) : members?.length === 0 ? (
            <p className="p-6 text-center text-muted-foreground">No members yet.</p>
          ) : (
            <div className="divide-y">
              {members?.map((m) => {
                const initials = m.name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
                return (
                  <div key={m.id} className="flex items-center justify-between px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8">
                        <AvatarFallback className="text-xs">{initials}</AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="text-sm font-medium">{m.name}</p>
                        <p className="text-xs text-muted-foreground">{m.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={roleColors[m.role]}>{m.role}</Badge>
                      {m.role !== 'owner' && (
                        <Button
                          variant="ghost" size="icon"
                          onClick={() => remove.mutate(m.id)}
                          disabled={remove.isPending}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
