export type TeamRole = 'owner' | 'admin' | 'editor' | 'viewer'

export interface TeamMember {
  id: number
  email: string
  name: string
  role: TeamRole
  status: 'active' | 'pending'
  avatar_url?: string
  invited_at: string
  joined_at: string | null
}

export interface InviteMemberRequest {
  email: string
  role: TeamRole
}
