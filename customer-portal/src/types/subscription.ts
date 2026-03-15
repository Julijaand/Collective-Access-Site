export type PlanId = 'starter' | 'pro' | 'museum' | 'enterprise'

export interface Plan {
  id: PlanId
  name: string
  price_eur: number | null   // null = custom
  users: number | 'unlimited'
  storage_gb: number
  description: string
  features: string[]
}

export const PLANS: Plan[] = [
  {
    id: 'starter',
    name: 'Starter',
    price_eur: 49,
    users: 3,
    storage_gb: 10,
    description: 'Small private collectors',
    features: ['3 users', '10 GB storage', 'Basic support', 'Automated backups'],
  },
  {
    id: 'pro',
    name: 'Pro',
    price_eur: 199,
    users: 10,
    storage_gb: 100,
    description: 'Galleries & small museums',
    features: ['10 users', '100 GB storage', 'Priority support', 'Custom domain', 'Advanced analytics'],
  },
  {
    id: 'museum',
    name: 'Museum',
    price_eur: 799,
    users: Infinity as unknown as 'unlimited',
    storage_gb: 1000,
    description: 'Large institutions',
    features: ['Unlimited users', '1 TB storage', 'Dedicated support', 'SLA 99.9%', 'Custom integrations'],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price_eur: null,
    users: Infinity as unknown as 'unlimited',
    storage_gb: Infinity,
    description: 'Multi-site organizations',
    features: ['Custom users', 'Custom storage', '24/7 support', 'On-prem option', 'White-label'],
  },
]

export interface Subscription {
  id: string
  tenant_id: number
  plan: PlanId
  status: 'active' | 'trialing' | 'past_due' | 'canceled' | 'incomplete'
  current_period_start: string
  current_period_end: string
  cancel_at_period_end: boolean
  stripe_subscription_id: string
}

export interface Invoice {
  id: string
  amount_paid: number   // in cents
  currency: string
  created: string
  status: 'paid' | 'open' | 'void' | 'uncollectible'
  invoice_pdf: string | null
  hosted_invoice_url: string | null
}
