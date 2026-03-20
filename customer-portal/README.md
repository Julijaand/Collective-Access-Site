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
portal.<MINIKUBE_IP>.nip.io          ← Next.js (K8s, local)
portal.yourdomain.com               ← Next.js (K8s, production)
   │
   │ HTTPS (REST)
   ▼
api.portal.<MINIKUBE_IP>.nip.io      ← saas-backend Ingress (local)
api.portal.yourdomain.com           ← saas-backend Ingress (production)
   │
   ▼
saas-backend ClusterIP :8000        ← FastAPI (K8s, ca-system)
   │
   ├── PostgreSQL                   ← K8s (ca-system) — backend metadata
   ├── MySQL                        ← K8s (ca-system) — per-tenant CA databases
   ├── Stripe API
   └── K8s API (Helm)
          │
          ├── tenant-abc123        ← CA instance, own namespace
          ├── tenant-def456
          └── ...  (1 tenant per subscription)
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

### 4. Start the App

```bash
npm run dev        # Start dev server (http://localhost:3000)
npm run build      # Build for production
npm run start      # Start production server
npm run lint       # Run ESLint
```

Open http://localhost:3000

---

## Kubernetes Deployment

### Step 1 — Build & Push Docker Image

```bash
docker build -t julijaand/ca-customer-portal:latest .
docker push julijaand/ca-customer-portal:latest
```

### Step 2 — Configure K8s manifests

```bash
# ConfigMap — public URLs (edit domain to match your setup)
cp k8s/configmap.yaml.template k8s/configmap.yaml
nano k8s/configmap.yaml

# Secret — Stripe publishable key
cp k8s/portal-secret.yaml.template k8s/portal-secret.yaml
nano k8s/portal-secret.yaml   # base64-encode your key: echo -n "pk_live_..." | base64

# Ingress — domain
nano k8s/ingress.yaml   # update host: portal.<MINIKUBE_IP>.nip.io (local) or portal.yourdomain.com (prod)
```

### Step 3 — Deploy

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/portal-secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

Verify:
```bash
kubectl get pods -n ca-system -l app=customer-portal
kubectl get ingress -n ca-system
kubectl get certificate -n ca-system   # customer-portal-tls should be READY = True
```

---

## Local Access via Minikube

> **Why port-forward?** Minikube with the Docker driver runs inside an isolated Docker network — the node IP is not directly reachable from macOS. `kubectl port-forward` bridges the gap.

> ℹ️ `minikube tunnel` is **not needed** — it only helps for `LoadBalancer` services. The ingress controller uses `NodePort`.

**1. Get your Minikube IP:**

```bash
MINIKUBE_IP=$(minikube ip)
echo $MINIKUBE_IP   # e.g. 192.168.49.2
```

**2. One-time: install dnsmasq for automatic wildcard DNS (no manual `/etc/hosts` per tenant)**

```bash
brew install dnsmasq

# Route all *.<MINIKUBE_IP>.nip.io to localhost (where port-forward listens)
echo "address=/${MINIKUBE_IP}.nip.io/127.0.0.1" | sudo tee /opt/homebrew/etc/dnsmasq.conf

# Tell macOS to use dnsmasq for this domain
sudo mkdir -p /etc/resolver
echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/${MINIKUBE_IP}.nip.io

# Start dnsmasq as a system service
sudo brew services start dnsmasq

# Verify it works (should return 127.0.0.1)
dig +short test-tenant.${MINIKUBE_IP}.nip.io @127.0.0.1
```

After this, **every** new tenant subdomain resolves automatically — no `/etc/hosts` changes needed.

**3. Portal & API — add once to `/etc/hosts`** (these use a fixed hostname):

```bash
echo "127.0.0.1  portal.${MINIKUBE_IP}.nip.io api.portal.${MINIKUBE_IP}.nip.io" | sudo tee -a /etc/hosts
```

**4. Start the ingress controller port-forward (keep this terminal open):**

```bash
sudo kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 80:80 443:443
```

This single port-forward covers **all** services — portal, backend API, and every tenant CA app. dnsmasq handles DNS resolution; the port-forward handles the actual traffic routing to nginx.

**Access:**
| Service | URL |
|---------|-----|
| Customer Portal | `https://portal.${MINIKUBE_IP}.nip.io` |
| Backend API | `https://api.portal.${MINIKUBE_IP}.nip.io` |
| Tenant CA app | `https://tenant-XXXXXXXX.${MINIKUBE_IP}.nip.io` |

> ⚠️ Browser will show a **self-signed certificate warning** — click **Advanced → Proceed** to continue.

### TLS Certificate Troubleshooting (Local)

Let's Encrypt **will not work locally** — it requires a publicly reachable domain. Use the self-signed ClusterIssuer instead.

```bash
# Check available issuers
kubectl get clusterissuer
# e.g. NAME = selfsigned

# Your ingress annotation must match:
# cert-manager.io/cluster-issuer: selfsigned
```

If certificate is stuck (`READY: False`):
```bash
kubectl delete certificate customer-portal-tls -n ca-system --ignore-not-found
kubectl delete secret customer-portal-tls -n ca-system --ignore-not-found
kubectl apply -f k8s/ingress.yaml

# Verify it becomes ready (takes ~10s)
kubectl get certificate -n ca-system
```

---

## Production Deployment

### 1. DNS — Wildcard record (one-time setup)

In your DNS provider (Cloudflare recommended):

| Type | Name | Value |
|------|------|-------|
| A | `portal` | `<cluster external IP>` |
| A | `api.portal` | `<cluster external IP>` |
| A | `*` (wildcard) | `<cluster external IP>` |

The wildcard `*` record means every new tenant subdomain (`tenant-abc123.yoursaas.com`) resolves automatically — no DNS changes needed per tenant.

```bash
# Get your cluster external IP
kubectl get svc ingress-nginx-controller -n ingress-nginx
# Copy EXTERNAL-IP column
```

### 2. Switch backend env vars

Edit `saas-backend/k8s/deployment.yaml`:

```yaml
- name: BASE_DOMAIN
  value: "yoursaas.com"    # your real domain (tenants get tenant-xyz.yoursaas.com)

- name: CA_CERT_ISSUER
  value: "letsencrypt"     # issues real TLS certs automatically per tenant
```

> ⚠️ In local dev these are `BASE_DOMAIN=$(minikube ip).nip.io` and `CA_CERT_ISSUER=selfsigned`. **Do not use `letsencrypt` locally** — it requires a publicly reachable domain and will fail.

Also update `k8s/ingress.yaml` in both `saas-backend/` and `customer-portal/` — change the `cert-manager.io/cluster-issuer` annotation from `selfsigned` to `letsencrypt` and update the hostnames to your real domain.

### 3. Stripe webhooks

In local dev, webhooks from Stripe cannot reach the cluster — the portal uses the `/billing/checkout/confirm` polling fallback instead.

In production, register a real webhook endpoint in the [Stripe Dashboard](https://dashboard.stripe.com/webhooks):
```
https://api.portal.yourdomain.com/webhooks/stripe
```
Events needed: `checkout.session.completed`, `customer.subscription.deleted`

Update the webhook secret in `saas-backend/k8s/saas-backend-secrets.yaml`:
```bash
echo -n "whsec_your_live_secret" | base64
# Paste into saas-backend-secrets.yaml → stripe-webhook-secret
kubectl apply -f saas-backend/k8s/saas-backend-secrets.yaml
```

### 4. Deploy

```bash
# Backend
cd saas-backend
docker build -t julijaand/ca-saas-backend:latest .
docker push julijaand/ca-saas-backend:latest
kubectl apply -f k8s/deployment.yaml
kubectl rollout restart deployment/saas-backend -n ca-system

# Portal
cd customer-portal
docker build -t julijaand/ca-customer-portal:latest .
docker push julijaand/ca-customer-portal:latest
kubectl apply -f k8s/
kubectl rollout restart deployment/customer-portal -n ca-system
```

### 5. Verify

```bash
kubectl get pods -n ca-system
kubectl get ingress -n ca-system
kubectl get certificate -n ca-system   # all should show READY = True
```

---

## Operations

### Accessing Tenant CA Apps

Each provisioned tenant gets a CA instance accessible via its own subdomain:

```bash
# List all tenant ingresses and their URLs
kubectl get ingress -A | grep tenant
```

If the tenant URL shows the CA installer, the setup wizard has not been completed yet.
Run it at: `https://tenant-XXXXXXXX.<your-domain>/install/index.php`

After installation completes, log in with `username: administrator` and the password shown at the end of the wizard.

### Deleting a Tenant

```bash
# 1. Uninstall Helm release + delete namespace
helm uninstall tenant-abc123 -n tenant-abc123
kubectl delete namespace tenant-abc123

# 2. Drop MySQL database
kubectl exec -n ca-system <mysql-pod> -- \
  mysql -u root -p<root-password> -e "DROP DATABASE IF EXISTS ca_abc123;"

# 3. Remove from PostgreSQL
kubectl exec -n ca-system <postgres-pod> -- \
  psql -U ca_saas -d ca_saas -c \
  "DELETE FROM tenants WHERE namespace = 'tenant-abc123';"
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
- [x] TypeScript types (`src/types/`)
- [x] API client + auth store (`src/lib/api/`, `src/stores/`)
- [x] Auth pages (login / signup)
- [x] Dashboard layout (sidebar + header)
- [x] Billing & subscription pages (Stripe Checkout + confirm flow)
- [x] Overview page — active instance card, plan & status stats
- [x] Automatic tenant provisioning on payment (1 subscription = 1 tenant)
- [x] Local wildcard DNS via dnsmasq (no manual /etc/hosts per tenant)
- [x] Team management page
- [x] Support tickets page
- [x] Backups page
- [ ] Real-time metrics (WebSocket)
- [ ] Production deployment

---

## Important Notes

### 🏗️ Local vs Production Differences

### 👥 Team Management

- The **owner** record is auto-created on first visit to the Team page (no manual setup needed)
- Inviting an email that already has a portal account → member is `active` immediately
- Inviting a new email → member shows as `pending` (in production: send invite email with signup link)
- **Owner cannot be removed or have their role changed** — protected by API
- Roles: `owner` > `admin` > `editor` > `viewer` (currently informational — full RBAC can be added later)

---

### 🎫 Support Tickets

- Tickets are scoped to the logged-in user (not per-tenant)
- First message = ticket description (submitted with the form)
- Replying to a `resolved` ticket automatically reopens it to `open`
- Closing a ticket blocks further replies
- In production: add email notifications and a support-agent UI to the admin backend

---

### 💾 Backups

- Manual backups are created instantly and marked `completed` with a simulated file size
- `storage_location` field is a path string — in production point this to S3/GCS
- The restore endpoint accepts the request and logs it — in production wire it to a K8s Job that runs `mysqldump` restore
- Automatic backups (type=`automatic`) would be created by a CronJob in production

---

**Related:**
- [Phase 2 — Kubernetes](../k8s/README.md)
- [Phase 3 — SaaS Backend](../saas-backend/README.md)
- [Full Roadmap](../ROADMAP.md)
