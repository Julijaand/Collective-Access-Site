'use client'

import { useState, useRef, useEffect } from 'react'
import { MessageCircle, X, Send, Loader2, Bot, User, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { chatApi, type ChatMessage } from '@/lib/api/chat'
import { useTenants } from '@/lib/hooks/useTenants'
import { cn } from '@/lib/utils'

const WELCOME: ChatMessage = {
  role: 'assistant',
  content:
    "Hi! I'm your Collective Access assistant. I can help with:\n- How to use Collective Access\n- Billing and subscription questions\n- Troubleshooting issues\n\nWhat can I help you with?",
}

const SUGGESTIONS = [
  'How do I import data?',
  'I cannot log in to my instance',
  'How do I add team members?',
  'What plans are available?',
]

export function AiChatWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { data: tenants } = useTenants()
  const tenantId = tenants?.[0]?.id

  // Scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  // Focus textarea when opened
  useEffect(() => {
    if (open) setTimeout(() => textareaRef.current?.focus(), 100)
  }, [open])

  const send = async (text: string) => {
    const question = text.trim()
    if (!question || loading) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setLoading(true)

    // Add an empty assistant message that we'll fill in token by token
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      await chatApi.sendStream(
        { message: question, tenant_id: tenantId },
        // onToken — append each token to the last message
        (token) => {
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: updated[updated.length - 1].content + token,
            }
            return updated
          })
        },
        // onDone — attach sources
        (sources) => {
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              sources,
            }
            return updated
          })
          setLoading(false)
        },
        // onError
        (errType) => {
          const content = errType === 'session_expired'
            ? 'Your session has expired. Please [log in again](/login) to continue.'
            : 'Sorry, the AI assistant is currently unavailable. Please [open a support ticket](/support) and our team will help you.'
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = { role: 'assistant', content }
            return updated
          })
          setLoading(false)
        },
      )
    } catch {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: 'The assistant is taking too long to respond. Please try again in a moment.',
        }
        return updated
      })
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <>
      {/* Floating bubble */}
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition-all duration-200',
          open
            ? 'bg-muted text-muted-foreground'
            : 'bg-primary text-primary-foreground hover:scale-105',
        )}
        aria-label="Open AI assistant"
      >
        {open ? <ChevronDown className="h-5 w-5" /> : <MessageCircle className="h-6 w-6" />}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex w-[360px] max-h-[560px] flex-col rounded-xl border bg-background shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between rounded-t-xl bg-primary px-4 py-3 text-primary-foreground">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5" />
              <div>
                <p className="text-sm font-semibold leading-none">CA Assistant</p>
                <p className="text-xs opacity-70">Powered by Ollama + RAG</p>
              </div>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close">
              <X className="h-4 w-4 opacity-70 hover:opacity-100" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={cn(
                  'flex gap-2 text-sm',
                  msg.role === 'user' ? 'flex-row-reverse' : 'flex-row',
                )}
              >
                {/* Avatar */}
                <div
                  className={cn(
                    'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground',
                  )}
                >
                  {msg.role === 'user' ? (
                    <User className="h-3.5 w-3.5" />
                  ) : (
                    <Bot className="h-3.5 w-3.5" />
                  )}
                </div>

                {/* Bubble */}
                <div className="max-w-[260px] space-y-1">
                  <div
                    className={cn(
                      'rounded-xl px-3 py-2 leading-relaxed whitespace-pre-wrap',
                      msg.role === 'user'
                        ? 'bg-primary text-primary-foreground rounded-tr-sm'
                        : 'bg-muted text-foreground rounded-tl-sm',
                    )}
                  >
                    {msg.content}
                  </div>
                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {msg.sources.map((s, si) => (
                        <Badge key={si} variant="outline" className="text-[10px] px-1.5 py-0">
                          {s.section || s.title}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Typing indicator — only while the streaming reply hasn't started yet */}
            {loading && messages[messages.length - 1]?.content === '' && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                </div>
                <span className="text-xs">Thinking…</span>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Suggestions (shown only on welcome state) */}
          {messages.length === 1 && (
            <div className="px-3 pb-2 flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border px-2.5 py-1 text-xs hover:bg-muted transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="flex items-end gap-2 border-t p-3">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about Collective Access…"
              rows={1}
              className="min-h-[36px] max-h-[100px] resize-none text-sm"
              disabled={loading}
            />
            <Button
              size="icon"
              className="h-9 w-9 shrink-0"
              onClick={() => send(input)}
              disabled={!input.trim() || loading}
              aria-label="Send"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      )}
    </>
  )
}
