'use client'

import { Progress } from '@/components/ui/progress'
import type { TenantStatus } from '@/types/tenant'
import { Loader2 } from 'lucide-react'

const STEPS: { key: string; label: string; pct: number }[] = [
  { key: 'namespace',  label: 'Creating namespace',    pct: 10 },
  { key: 'database',   label: 'Setting up database',   pct: 25 },
  { key: 'helm',       label: 'Deploying application', pct: 50 },
  { key: 'ca_install', label: 'Installing CA',         pct: 80 },
  { key: 'finalizing', label: 'Finalizing setup',      pct: 95 },
]

interface ProvisioningProgressProps {
  step?: string | null
  status: TenantStatus
}

export function ProvisioningProgress({ step, status }: ProvisioningProgressProps) {
  if (status !== 'provisioning') return null

  const current = STEPS.find((s) => s.key === step)
  const pct = current?.pct ?? 5
  const label = current?.label ?? 'Starting…'

  return (
    <div className="mt-2 space-y-1">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin shrink-0" />
        <span>{label}</span>
        <span className="ml-auto">{pct}%</span>
      </div>
      <Progress value={pct} className="h-1.5" />
    </div>
  )
}
