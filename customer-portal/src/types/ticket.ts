export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed'
export type TicketPriority = 'low' | 'medium' | 'high' | 'critical'

export interface Ticket {
  id: number
  tenant_id: number
  subject: string
  status: TicketStatus
  priority: TicketPriority
  category: string
  created_at: string
  updated_at: string
  messages_count: number
}

export interface TicketMessage {
  id: number
  ticket_id: number
  author_name: string
  author_role: 'user' | 'support'
  message: string
  created_at: string
}

export interface CreateTicketRequest {
  tenant_id: number
  subject: string
  description: string
  priority: TicketPriority
  category: string
}
