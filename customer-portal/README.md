# Collective Access — Customer Portal

**Phase 4** of the Collective Access SaaS Platform.  
User-facing dashboard for subscription management, tenant monitoring, billing, team management and support.

**Stack:** Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui · Zustand · TanStack Query · Stripe

---

## Architecture

```
Browser
   │
   │ HTTPS
   ▼
portal.yourdomain.com          ← Next.js (Vercel or K8s)
   │
   │ HTTPS (REST / WebSocket)
   ▼
api.yourdomain.com             ← saas-backend Ingress (ca-system namespace)
   │
   ▼
saas-backend ClusterIP :8000   ← FastAPI (K8s, ca-system)
   │
   ├── PostgreSQL               ← K8s (ca-system)
   ├── Stripe API
   └── K8s API
          │
          ├── ca-tenant-abc    ← CA instance per tenant
          ├── ca-tenant-xyz
          └── ...
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | ≥ 20 | https://nodejs.org |
| npm | ≥ 10 | bundled with Node |
| kubectl | any | https://kubernetes.io/docs/tasks/tools |
| K8s cluster | running | Phase 2 complete |
| saas-backend | deployed | Phase 3 complete |

---

## Local Development

### 1. Clone & Install

After cloning the repository, run the setup script from inside the `customer-portal/` directory:

```bash
cd customer-portal
chmod +x setup-customer-portal.sh
bash setup-customer-portal.sh
```

The script will:
1. Run `npm install` (all app dependencies)
2. Initialise shadcn/ui
3. Install all shadcn/ui components
4. Create `.env.local` from `.env.example`

#### What gets installed

**App dependencies:**

| Package | Purpose |
|---------|---------|
| `axios` | HTTP client for API calls |
| `zustand` | Lightweight state management (auth store, UI state) |
| `@tanstack/react-query` | Server state, caching, data fetching hooks |
| `react-hook-form` | Form handling with validation |
| `zod` | Schema validation for forms and API responses |
| `date-fns` | Date formatting for invoices, backups, tickets |
| `recharts` | Charts for resource usage / metrics dashboard |
| `lucide-react` | Icon library (used by shadcn/ui) |
| `@stripe/stripe-js` + `@stripe/react-stripe-js` | Stripe payment UI |
| `socket.io-client` | WebSocket client for real-time tenant metrics |

**shadcn/ui components:** `button` `card` `input` `label` `form` `dialog` `dropdown-menu` `avatar` `badge` `progress` `table` `tabs` `sonner` `alert` `skeleton` `separator` `sheet` `select` `textarea`

> Note: `sonner` is used for notifications — `toast` is deprecated in shadcn/ui.

### 2. Configure Environment

The setup script creates `.env.local` automatically from `.env.example`. Edit it with your values:

```bash
nano .env.local
```

```env
# Development — backend via kubectl port-forward
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Production — replace with your domain
# NEXT_PUBLIC_API_URL=https://api.yourdomain.com
# NEXT_PUBLIC_WS_URL=wss://api.yourdomain.com

NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### 3. Expose the K8s Backend Locally

The `saas-backend` runs inside Kubernetes (`ca-system` namespace).  
Use `kubectl port-forward` to reach it locally:

```bash
kubectl port-forward svc/saas-backend 8000:8000 -n ca-system
```

Keep this running in a separate terminal. The backend is now available at `http://localhost:8000`.

Verify it works:
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"...","database":"connected","kubernetes":"connected"}
```

Open http://localhost:3000

---

## Project Structure

```
customer-portal/
├── src/
│   ├── app/                        # Next.js App Router
│   │   ├── (auth)/                 # Unauthenticated routes
│   │   │   ├── login/page.tsx
│   │   │   ├── signup/page.tsx
│   │   │   ├── forgot-password/page.tsx
│   │   │   └── layout.tsx          # Centered auth layout
│   │   ├── (dashboard)/            # Protected routes
│   │   │   ├── dashboard/page.tsx  # Overview
│   │   │   ├── tenants/
│   │   │   │   ├── page.tsx        # Tenant list
│   │   │   │   └── [id]/page.tsx   # Tenant detail + metrics
│   │   │   ├── billing/page.tsx    # Plans, invoices, payment methods
│   │   │   ├── team/page.tsx       # Members, invites, roles
│   │   │   ├── support/
│   │   │   │   ├── page.tsx        # Ticket list
│   │   │   │   └── [id]/page.tsx   # Ticket conversation
│   │   │   ├── backups/page.tsx    # Backup list + restore
│   │   │   └── layout.tsx          # Sidebar + header layout
│   │   ├── layout.tsx              # Root layout + providers
│   │   └── globals.css
│   ├── components/
│   │   ├── auth/                   # LoginForm, SignupForm, OAuthButtons
│   │   ├── dashboard/              # Sidebar, Header, MobileMenu
│   │   ├── tenant/                 # TenantCard, ResourceUsage, StatusBadge
│   │   ├── billing/                # PricingCards, InvoiceList, PaymentMethod
│   │   ├── team/                   # TeamMemberList, InviteModal, RoleSelector
│   │   ├── support/                # TicketList, CreateTicketModal, Conversation
│   │   ├── backup/                 # BackupList, RestoreModal, Schedule
│   │   └── ui/                     # shadcn/ui components
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts           # Axios + JWT interceptors + auto-refresh
│   │   │   ├── auth.ts
│   │   │   ├── tenants.ts
│   │   │   ├── billing.ts
│   │   │   ├── team.ts
│   │   │   ├── support.ts
│   │   │   └── backups.ts
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useTenants.ts
│   │   │   ├── useSubscription.ts
│   │   │   └── useRealtime.ts      # WebSocket hook
│   │   └── stores/
│   │       ├── authStore.ts        # Zustand auth + token management
│   │       └── uiStore.ts          # Sidebar state, notifications
│   └── types/
│       ├── auth.ts
│       ├── tenant.ts
│       ├── subscription.ts
│       ├── team.ts
│       └── ticket.ts
├── .env.local                      # Local secrets (git-ignored)
├── .env.example                    # Template for team / CI
├── next.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

---

## Production Deployment

### Option A — Vercel (Recommended)

Simplest deployment — zero config needed.

```bash
npm install -g vercel
vercel login
vercel --prod
```

Set environment variables in the Vercel dashboard:
```
NEXT_PUBLIC_API_URL                = https://api.yourdomain.com
NEXT_PUBLIC_WS_URL                 = wss://api.yourdomain.com
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = pk_live_...
NEXT_PUBLIC_APP_URL                = https://portal.yourdomain.com
```

---

### Option B — Kubernetes (Same Cluster as Backend)

#### Step 1 — Build & Push Docker Image

```bash
docker build -t julijaand/ca-customer-portal:latest .
docker push julijaand/ca-customer-portal:latest
```

#### Step 2 — Configure K8s manifests

Copy and fill in the config files before deploying:

```bash
# ConfigMap — public URLs (edit domain to match your setup)
cp k8s/configmap.yaml.template k8s/configmap.yaml
nano k8s/configmap.yaml

# Secret — Stripe publishable key
cp k8s/portal-secret.yaml.template k8s/portal-secret.yaml
nano k8s/portal-secret.yaml   # base64-encode your key: echo -n "pk_live_..." | base64

# Ingress — domain
nano k8s/ingress.yaml   # update host: portal.yourdomain.com
```

#### Step 3 — Deploy to K8s

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/portal-secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

Verify everything is running:
```bash
kubectl get pods -n ca-system -l app=customer-portal
kubectl get ingress -n ca-system
kubectl get certificate -n ca-system
# customer-portal-tls should be READY = True
```

---

#### Step 4 — Local Access via Minikube (Docker Driver)

> **Why port-forward?** Minikube with the Docker driver runs inside an isolated Docker network — the node IP (`192.168.49.2`) is not directly reachable from macOS. `kubectl port-forward` bridges the gap.

> ℹ️ `minikube tunnel` is **not needed** here — it only helps for `LoadBalancer` services. The ingress controller uses `NodePort`.

**1. Add hostnames to `/etc/hosts` pointing to `127.0.0.1`:**

```bash
# Portal + backend API
echo "127.0.0.1  portal.192.168.49.2.nip.io api.portal.192.168.49.2.nip.io" | sudo tee -a /etc/hosts

# Tenant CA apps (add all active tenants)
echo "127.0.0.1  tenant-abc123.yoursaas.com tenant-def456.yoursaas.com" | sudo tee -a /etc/hosts

# Check all active tenant hostnames with:
# kubectl get ingress -A | grep tenant
```

**2. Start the ingress controller port-forward (keep this terminal open):**

```bash
sudo kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 80:80 443:443
```

This single port-forward covers **all** services — portal, backend API, and all tenant CA apps.

**Access:**
| Service | URL |
|---------|-----|
| Customer Portal | https://portal.192.168.49.2.nip.io |
| Tenant CA app | https://tenant-abc123.yoursaas.com |

> ⚠️ Browser will show a **self-signed certificate warning** — click **Advanced → Proceed** to continue.

---

#### Step 5 — TLS Certificate Troubleshooting (Local)

Let's Encrypt (`letsencrypt-prod`) **will not work locally** — it requires a publicly reachable domain. Use the self-signed ClusterIssuer instead.

Check your ingress annotation:
```bash
# Should reference your local self-signed issuer name
kubectl get clusterissuer
# e.g. NAME = selfsigned

# Your ingress annotation must match:
# cert-manager.io/cluster-issuer: selfsigned
```

If certificate is stuck (`READY: False`):
```bash
# 1. Fix the issuer name in ingress.yaml if needed, then:
kubectl delete certificate customer-portal-tls -n ca-system --ignore-not-found
kubectl delete secret customer-portal-tls -n ca-system --ignore-not-found
kubectl apply -f k8s/ingress.yaml

# 2. Verify it becomes ready (takes ~10s)
kubectl get certificate -n ca-system
```

---

#### Step 6 — Tenant CA Apps

Each provisioned tenant gets a CA instance accessible via its own subdomain. To access a tenant:

```bash
# List all tenant ingresses and their URLs
kubectl get ingress -A | grep tenant
```

If the tenant URL shows a blank page or CA installer, the **installation wizard has not been completed yet**.  
Run the installer at: `https://tenant-abc123.yoursaas.com/install/index.php`

After installation completes, log in with `username: administrator` and the password shown at the end of the wizard.

---

#### Step 7 — Deleting a Tenant

```bash
# 1. Uninstall Helm release + delete namespace
helm uninstall tenant-abc123 -n tenant-abc123
kubectl delete namespace tenant-abc123

# 2. Drop MySQL database
kubectl exec -n ca-system mysql-6b8f8f6668-lv7kw -- \
  mysql -u root -prootpassword123 -e "DROP DATABASE IF EXISTS ca_abc123;"

# 3. Remove from PostgreSQL
kubectl exec -n ca-system ca-saas-db-c58f44986-r5xfh -- \
  psql -U ca_saas -d ca_saas -c \
  "DELETE FROM tenants WHERE namespace = 'tenant-abc123';"
```

---

### Step 8 — Production DNS Configuration

In your DNS provider (Cloudflare recommended):

| Type | Name | Value |
|------|------|-------|
| A | `portal` | `<K8s cluster external IP>` |
| A | `api.portal` | `<K8s cluster external IP>` |
| A | `*.yoursaas.com` | `<K8s cluster external IP>` |

Get your cluster external IP:
```bash
kubectl get svc ingress-nginx-controller -n ingress-nginx
# Copy EXTERNAL-IP column
```

Switch cert-manager issuer to `letsencrypt-prod` in `k8s/ingress.yaml` for production TLS.

---

## Available Scripts

```bash
npm run dev        # Start dev server (http://localhost:3000)
npm run build      # Build for production
npm run start      # Start production server
npm run lint       # Run ESLint
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | ✅ | saas-backend base URL |
| `NEXT_PUBLIC_WS_URL` | ✅ | WebSocket URL for real-time updates |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | ✅ | Stripe public key (Stripe Dashboard) |
| `NEXT_PUBLIC_APP_URL` | ✅ | This app's public URL |
| `NEXT_PUBLIC_APP_NAME` | ❌ | Display name (default: Collective Access Portal) |

> ⚠️ Never use `NEXT_PUBLIC_*` for secret keys — they are exposed to the browser. All secrets (`STRIPE_SECRET_KEY`, DB credentials, etc.) live in the backend only.

---

## Connecting Frontend → Backend

| Environment | Frontend | → | Backend |
|-------------|----------|---|---------|
| Development | `localhost:3000` | kubectl port-forward | `localhost:8000` |
| Production | `portal.yourdomain.com` | Ingress TLS | `api.yourdomain.com` |

The API client (`src/lib/api/client.ts`) handles:
- JWT token attached to every request
- Automatic token refresh on 401
- Redirect to `/login` if refresh fails

---

## Pricing Plans

| Plan | Users | Storage | Price |
|------|-------|---------|-------|
| Starter | 3 | 10 GB | €49/mo |
| Pro | 10 | 100 GB | €199/mo |
| Museum | Unlimited | 1 TB | €799/mo |
| Enterprise | Custom | Custom | Custom |

---

## Phase Checklist

- [x] Next.js 15 + TypeScript + Tailwind initialized
- [x] shadcn/ui installed and configured
- [x] All npm dependencies installed
- [x] Environment variables configured
- [x] saas-backend K8s Ingress created (`../saas-backend/k8s/ingress.yaml`)
- [ ] TypeScript types
- [ ] API client + auth store
- [ ] Auth pages (login / signup / forgot password)
- [ ] Dashboard layout (sidebar + header)
- [ ] Tenant management pages
- [ ] Billing & subscription pages
- [ ] Team management page
- [ ] Support tickets page
- [ ] Backups page
- [ ] Real-time metrics (WebSocket)
- [ ] Production deployment

---

**Related:**
- [Phase 2 — Kubernetes](../k8s/README.md)
- [Phase 3 — SaaS Backend](../saas-backend/README.md)
- [Full Roadmap](../ROADMAP.md)
