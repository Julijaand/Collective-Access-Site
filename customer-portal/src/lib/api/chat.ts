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

export const chatApi = {
  send: async (req: ChatRequest): Promise<ChatResponse> => {
    const { data } = await apiClient.post<ChatResponse>('/api/chat', req, {
      timeout: 120_000, // 2 min — LLM inference can be slow on CPU
    })
    return data
  },

  health: async () => {
    const { data } = await apiClient.get('/api/chat/health')
    return data
  },
}
