# Collective Access SaaS Platform - Quick Roadmap

## 🧭 PHASE 0 — Product & Legal Foundation (Week 0–2)

Before you write serious code:

### 1. Decide Commercial Model

You need:
- Per-tenant pricing
- Storage tiers
- User limits

**Example Pricing:**

| Plan | Users | Storage | Price |
|------|-------|---------|-------|
| Starter | 3 | 10 GB | €49/mo |
| Pro | 10 | 100 GB | €199/mo |
| Museum | Unlimited | 1 TB | €799/mo |

### 2. Get Collective Access Licensing

CA is open source, but:
- You must comply with GPL
- You may need a commercial support agreement if reselling

This affects:
- How you bundle it
- Whether you can offer paid hosting

---

## 🧱 PHASE 1 — Containerize Collective Access (Week 1–3)

**Goal:** One reproducible CA image that can run anywhere.

### Tools
- Docker
- Nginx
- PHP-FPM
- MySQL or PostgreSQL
- CA source code

### What to Do

Create:
```
ca-app/
  Dockerfile
  nginx.conf
  php.ini
  entrypoint.sh
```

Your Docker image must:
- Install CA
- Connect to external DB
- Use external storage (S3)
- Read env variables for:
  - DB
  - Domain
  - Admin user

Test it locally:
```bash
docker-compose up
```

**This is critical.** Everything else depends on this.

---

## ☸️ PHASE 2 — Kubernetes Base Platform (Week 3–6)

**Goal:** A cluster that can run many CA tenants safely.

### Tools
- Kubernetes (EKS, GKE, or Hetzner)
- Helm
- NGINX Ingress
- cert-manager
- Longhorn or S3-compatible storage

### What You Set Up

Your cluster must have:
- Ingress controller
- TLS auto-certificates
- Persistent volumes
- Namespaces per tenant

Then create a Helm chart:
```
collectiveaccess-chart/
  templates/
    deployment.yaml
    service.yaml
    ingress.yaml
    pvc.yaml
    secret.yaml
```

**Values:**
- `tenantName`
- `dbName`
- `storageSize`
- `domain`

**Test:**
```bash
helm install tenant1 collectiveaccess-chart
```

You should see: `tenant1.yoursaas.com`

---

## 🧠 PHASE 3 — SaaS Backend (Week 5–10)

**Goal:** The "brain" that turns subscriptions into deployments.

### Tools
- **Backend:** Node.js (NestJS) or Python (FastAPI)
- **Database:** PostgreSQL
- **Payments:** Stripe
- **Infrastructure:** Kubernetes API client

### Your Backend Must Do:
- User signup & auth
- Subscription management
- Receive Stripe webhooks
- Call Kubernetes API
- Track tenant state

### Your Core Logic:
```
Stripe → webhook → provisionTenant()
                    |
                    v
            Kubernetes Helm install
```

### You Store:
- `user_id`
- `tenant_namespace`
- `domain`
- `plan`
- `status`

---

## 🌐 PHASE 4 — Customer Portal (Week 8–12)

**Goal:** Users can self-serve.

### Tools
- **Frontend:** Next.js / React
- **Auth:** Auth0 or Clerk
- **API:** Your backend

### Users Must See:
- Their CA URL
- Storage used
- Backups
- Billing
- Support chat

**This is your SaaS product.**

---

## 💾 PHASE 5 — Backups, Upgrades, and Security (Week 10–14)

**Goal:** This becomes "museum-grade".

### Tools
- **Backup:** Velero (K8s backups)
- **Storage:** S3 backups
- **Monitoring:** Prometheus + Grafana
- **Logging:** Loki

### You Must Support:
- Database backups
- Media file backups
- Restore per tenant
- Rolling CA upgrades

**This is what people pay for.**

---

## 🤖 PHASE 6 — AI Support Layer (Week 14–18)

**Goal:** Turn support into automation.

### Tools
- **LLM:** OpenAI or Claude
- **Vector DB:** Pinecone, Weaviate
- **Tickets:** Zendesk or custom

### Your AI Connects To:
- CA docs
- Your logs
- User tickets
- Deployment state

### It Can:
- Answer "How do I…"
- Detect broken pods
- Suggest fixes

**This is your moat.**

---

## 🏗️ PHASE 7 — Enterprise Hardening

**Later:**
- SSO (SAML)
- Custom domains
- Private networks
- On-premise Kubernetes

---

## 🧠 The Big Idea

**You are not selling CA.**  
**You are selling: "Zero-IT museum software"**

Your roadmap is exactly how modern SaaS platforms like GitHub, Shopify and Atlassian are built — but applied to cultural heritage.

---

*For detailed implementation steps, see [ROADMAP.md](ROADMAP.md)*
