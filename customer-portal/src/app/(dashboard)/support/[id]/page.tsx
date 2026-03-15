'use client'

import { useState, useRef, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Send, RefreshCw } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { supportApi } from '@/lib/api/support'
import { useAuthStore } from '@/lib/stores/authStore'

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const [message, setMessage] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const ticketId = Number(id)

  const { data: ticket, isLoading } = useQuery({
    queryKey: ['ticket', ticketId],
    queryFn: () => supportApi.get(ticketId),
  })

  const { data: messages, isLoading: msgLoading } = useQuery({
    queryKey: ['ticket-messages', ticketId],
    queryFn: () => supportApi.getMessages(ticketId),
    refetchInterval: 10000,
  })

  const sendMsg = useMutation({
    mutationFn: () => supportApi.addMessage(ticketId, message),
    onSuccess: () => { setMessage(''); qc.invalidateQueries({ queryKey: ['ticket-messages', ticketId] }) },
    onError: () => toast.error('Failed to send message'),
  })

  const closeTicket = useMutation({
    mutationFn: () => supportApi.close(ticketId),
    onSuccess: () => { toast.success('Ticket closed'); qc.invalidateQueries({ queryKey: ['ticket', ticketId] }) },
  })

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-64 w-full" /></div>
  if (!ticket) return <p className="text-muted-foreground">Ticket not found.</p>

  return (
    <div className="space-y-4 flex flex-col h-full">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push('/support')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-xl font-bold">{ticket.subject}</h1>
          <p className="text-xs text-muted-foreground">#{ticket.id} · opened {new Date(ticket.created_at).toLocaleDateString()}</p>
        </div>
        <Badge variant={ticket.status === 'open' ? 'default' : 'secondary'}>{ticket.status.replace('_', ' ')}</Badge>
        {ticket.status !== 'closed' && (
          <Button variant="outline" size="sm" onClick={() => closeTicket.mutate()} disabled={closeTicket.isPending}>
            {closeTicket.isPending && <RefreshCw className="mr-2 h-3 w-3 animate-spin" />} Close
          </Button>
        )}
      </div>

      <Card className="flex-1 flex flex-col min-h-[400px]">
        <CardHeader><CardTitle className="text-sm">Conversation</CardTitle></CardHeader>
        <CardContent className="flex-1 overflow-y-auto space-y-4 max-h-[400px]">
          {/* Original subject */}
          <div className="flex gap-3">
            <Avatar className="h-7 w-7 shrink-0">
              <AvatarFallback className="text-xs">{(user?.email?.[0] ?? 'U').toUpperCase()}</AvatarFallback>
            </Avatar>
            <div className="rounded-lg bg-muted px-3 py-2 text-sm max-w-[80%]">
              <p className="font-medium text-xs text-muted-foreground mb-1">{user?.email} · original</p>
              <p>{ticket.subject}</p>
            </div>
          </div>

          {msgLoading && <Skeleton className="h-16 w-3/4" />}

          {messages?.map((msg) => {
            const isMe = msg.author_role === 'user'
            return (
              <div key={msg.id} className={`flex gap-3 ${isMe ? 'flex-row-reverse' : ''}`}>
                <Avatar className="h-7 w-7 shrink-0">
                  <AvatarFallback className="text-xs">{msg.author_name?.[0] ?? '?'}</AvatarFallback>
                </Avatar>
                <div className={`rounded-lg px-3 py-2 text-sm max-w-[80%] ${isMe ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                  <p className="font-medium text-xs opacity-70 mb-1">{msg.author_name}</p>
                  <p>{msg.message}</p>
                </div>
              </div>
            )
          })}
          <div ref={bottomRef} />
        </CardContent>
      </Card>

      {ticket.status !== 'closed' && (
        <div className="flex gap-2">
          <Textarea
            rows={2}
            className="resize-none"
            placeholder="Type a reply..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (message.trim()) sendMsg.mutate() } }}
          />
          <Button onClick={() => sendMsg.mutate()} disabled={!message.trim() || sendMsg.isPending} size="icon" className="self-end">
            {sendMsg.isPending ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      )}
    </div>
  )
}
