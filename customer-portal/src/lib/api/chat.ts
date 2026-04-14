import { apiClient } from './client'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: { title: string; section: string }[]
}

export interface ChatRequest {
  message: string
  tenant_id?: number
}

export interface ChatResponse {
  reply: string
  sources: { title: string; section: string }[]
  used_rag: boolean
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const chatApi = {
  send: async (req: ChatRequest): Promise<ChatResponse> => {
    const { data } = await apiClient.post<ChatResponse>('/api/chat', req, {
      timeout: 120_000,
    })
    return data
  },

  /**
   * Streaming SSE chat — calls onToken for each token as it arrives,
   * then onDone with sources when generation is complete.
   */
  sendStream: async (
    req: ChatRequest,
    onToken: (token: string) => void,
    onDone: (sources: { title: string; section: string }[]) => void,
    onError: (msg: string) => void,
  ): Promise<void> => {
    const token = typeof window !== 'undefined'
      ? localStorage.getItem('access_token')
      : null

    const resp = await fetch(`${API_URL}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(req),
      signal: AbortSignal.timeout(120_000),
    })

    if (!resp.ok) {
      if (resp.status === 401) onError('session_expired')
      else onError('unavailable')
      return
    }

    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const parsed = JSON.parse(line.slice(6))
          if (parsed.error) { onError('unavailable'); return }
          if (parsed.token) onToken(parsed.token)
          if (parsed.done) onDone(parsed.sources ?? [])
        } catch { /* skip malformed lines */ }
      }
    }
  },

  health: async () => {
    const { data } = await apiClient.get('/api/chat/health')
    return data
  },
}
