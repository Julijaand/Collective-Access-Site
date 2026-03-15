'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Plus, RefreshCw } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useTenants } from '@/lib/hooks/useTenants'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { supportApi } from '@/lib/api/support'
import type { TicketPriority, TicketStatus } from '@/types/ticket'

const PRIORITY_COLORS: Record<TicketPriority, 'default' | 'secondary' | 'destructive'> = {
  low: 'secondary', medium: 'default', high: 'destructive', critical: 'destructive',
}
const STATUS_COLORS: Record<TicketStatus, 'default' | 'secondary' | 'outline'> = {
  open: 'default', in_progress: 'secondary', resolved: 'outline', closed: 'outline',
}

const createSchema = z.object({
  subject: z.string().min(5, 'Subject too short'),
  description: z.string().min(10, 'Description too short'),
  priority: z.enum(['low', 'medium', 'high', 'critical']),
})
type CreateForm = z.infer<typeof createSchema>

export default function SupportPage() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const { data: tenants } = useTenants()
  const tenantId = tenants?.[0]?.id

  const { data: tickets, isLoading } = useQuery({
    queryKey: ['tickets'],
    queryFn: supportApi.list,
  })

  const create = useMutation({
    mutationFn: (data: CreateForm) => supportApi.create({
      ...data,
      tenant_id: tenantId ?? 0,
      category: 'general',
    }),
    onSuccess: () => { toast.success('Ticket created!'); qc.invalidateQueries({ queryKey: ['tickets'] }); setOpen(false); form.reset() },
    onError: () => toast.error('Failed to create ticket'),
  })

  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { subject: '', description: '', priority: 'medium' },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Support</h1>
          <p className="text-muted-foreground mt-1">Get help with your Collective Access instances.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button><Plus className="mr-2 h-4 w-4" /> New Ticket</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create a support ticket</DialogTitle>
              <DialogDescription>Our team will respond within 24 hours.</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit((d) => create.mutate(d))} className="space-y-4 py-2">
                <FormField control={form.control} name="subject" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Subject</FormLabel>
                    <FormControl><Input placeholder="Cannot access admin panel" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="description" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl><Textarea rows={4} placeholder="Describe your issue..." {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="priority" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Priority</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                      <SelectContent>
                        <SelectItem value="low">Low</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="critical">Critical</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                  <Button type="submit" disabled={create.isPending}>
                    {create.isPending && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />} Submit
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="space-y-3">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
      ) : tickets?.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-muted-foreground">No tickets yet. 🎉</CardContent></Card>
      ) : (
        <Card>
          <CardHeader><CardTitle>Your Tickets</CardTitle></CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {tickets?.map((ticket) => (
                <Link key={ticket.id} href={`/support/${ticket.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors">
                  <div>
                    <p className="text-sm font-medium">{ticket.subject}</p>
                    <p className="text-xs text-muted-foreground">{new Date(ticket.created_at).toLocaleDateString()}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={PRIORITY_COLORS[ticket.priority]}>{ticket.priority}</Badge>
                    <Badge variant={STATUS_COLORS[ticket.status]}>{ticket.status.replace('_', ' ')}</Badge>
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
