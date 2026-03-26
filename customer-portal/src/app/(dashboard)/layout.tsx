'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Sidebar } from '@/components/dashboard/Sidebar'
import { Header } from '@/components/dashboard/Header'
import { AiChatWidget } from '@/components/dashboard/AiChatWidget'
import { useAuthStore } from '@/lib/stores/authStore'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { isAuthenticated, fetchUser, _hasHydrated, user } = useAuthStore()

  useEffect(() => {
    if (!_hasHydrated) return
    if (!isAuthenticated) {
      router.push('/login')
      return
    }
    // Only re-validate token if we don't already have user data
    if (!user) fetchUser()
  }, [isAuthenticated, _hasHydrated, user, router, fetchUser])

  if (!_hasHydrated) return null
  if (!isAuthenticated) return null

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          {children}
        </main>
      </div>
      <AiChatWidget />
    </div>
  )
}
