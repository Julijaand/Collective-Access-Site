export interface User {
  id: number
  email: string
  avatar_url?: string
  role: 'owner' | 'admin' | 'member'
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  user: User
}
