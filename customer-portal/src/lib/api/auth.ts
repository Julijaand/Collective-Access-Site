import apiClient from './client'
import type { AuthResponse, LoginRequest, RegisterRequest, User } from '@/types/auth'

export const authApi = {
  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const res = await apiClient.post('/api/auth/login', data)
    return res.data
  },

  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const res = await apiClient.post('/api/auth/register', data)
    return res.data
  },

  me: async (): Promise<User> => {
    const res = await apiClient.get('/api/auth/me')
    return res.data
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/api/auth/logout').catch(() => {})
  },

  forgotPassword: async (email: string): Promise<void> => {
    await apiClient.post('/api/auth/forgot-password', { email })
  },

  resetPassword: async (token: string, password: string): Promise<void> => {
    await apiClient.post('/api/auth/reset-password', { token, password })
  },
}
