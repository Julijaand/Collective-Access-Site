import apiClient from './client'
import type { Ticket, TicketMessage, CreateTicketRequest } from '@/types/ticket'

export const supportApi = {
  list: async (): Promise<Ticket[]> => {
    const res = await apiClient.get('/api/tickets')
    return res.data.tickets ?? res.data
  },

  get: async (id: number): Promise<Ticket> => {
    const res = await apiClient.get(`/api/tickets/${id}`)
    return res.data
  },

  create: async (data: CreateTicketRequest): Promise<Ticket> => {
    const res = await apiClient.post('/api/tickets', data)
    return res.data
  },

  getMessages: async (id: number): Promise<TicketMessage[]> => {
    const res = await apiClient.get(`/api/tickets/${id}/messages`)
    return res.data.messages ?? res.data
  },

  addMessage: async (id: number, message: string): Promise<TicketMessage> => {
    const res = await apiClient.post(`/api/tickets/${id}/messages`, { message })
    return res.data
  },

  close: async (id: number): Promise<void> => {
    await apiClient.patch(`/api/tickets/${id}`, { status: 'closed' })
  },
}
