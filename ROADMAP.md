# Collective Access SaaS Platform — Engineering Roadmap

**Project:** Museum-grade SaaS platform for Collective Access deployment via Kubernetes  
**Timeline:** 18+ weeks (MVP → production-ready)  
**Last Updated:** January 13, 2026

---

## 🎯 Project Vision

Build a zero-IT SaaS platform for art collectors, galleries, and museums that allows them to:

- Subscribe and instantly get a dedicated Collective Access instance
- Scale storage and users on demand
- Get AI-powered support and diagnostics
- Trust enterprise-grade backups and security

**Business Model:** Subscription-based SaaS with automated Kubernetes pod provisioning.

---

## 📊 Initial Pricing Tiers

| Plan | Users | Storage | Price | Target Audience |
|------|-------|---------|-------|-----------------|
| Starter | 3 | 10 GB | €49/mo | Small private collectors |
| Pro | 10 | 100 GB | €199/mo | Galleries, small museums |
| Museum | Unlimited | 1 TB | €799/mo | Large institutions |
| Enterprise | Custom | Custom | Custom | Multi-site organizations |

---

## 🧭 Phase 0 — Foundation & Legal (Week 0-2)

**Objectives:** Validate product-market fit, resolve licensing, set up business infrastructure

**Tasks:**

- Define personas, customer journey, SLAs
- Conduct 5–10 interviews with collectors/museums
- Review Collective Access GPL license and SaaS implications
- Draft terms of service & privacy policy
- Set up company, Stripe account, domain, email
- Prepare GitHub, project management, and documentation infrastructure

**Deliverables:**
- ✅ Business plan
- ✅ Legal compliance checklist
- ✅ Pricing model
- ✅ Customer personas & journey map

---

## 🧱 Phase 1 — Containerize Collective Access (Week 1-3)

**Objectives:** Build reproducible Docker image for Collective Access, support external DB and storage

**Tasks:**

- Local development: install CA manually, document dependencies
- Dockerize CA with PHP 8.x, required extensions, nginx, entrypoint scripts
- Configure MySQL/PostgreSQL, handle migrations, and set permissions
- Storage setup:
  * Local storage for development (media, cache, tmp)
  * Plan for S3-compatible storage (AWS S3, Backblaze, MinIO) for production multi-tenant deployments
  * Ensure media file handling is structured and backup-friendly
- Test with docker-compose: fresh install, data import, all CA features

**Deliverables:**
- ✅ Docker image & Compose setup for local testing
- ✅ Health checks & configuration templates
- ✅ Documentation for containerized CA in container with storage considerations

---

## ☸️ Phase 2 — Kubernetes Base Platform (Week 3-6) ✅ COMPLETE

**Objectives:** Production-grade K8s cluster, multi-tenant deployment, automated TLS, persistent storage

**Tasks:**

- ✅ Nginx Ingress controller setup
- ✅ cert-manager for automatic TLS
- ✅ Longhorn/cloud storage configuration
- ✅ Simplified Helm chart (5 essential templates)
- ✅ External database architecture (shared MySQL)
- ✅ Per-tenant namespace isolation
- ✅ Health probes and resource limits
- ✅ Step-by-step deployment guide

**Deliverables:**
- ✅ Simplified Helm chart
- ✅ Step-by-step README with cluster setup
- ✅ External MySQL deployment
- ✅ Automatic TLS via cert-manager
- ✅ Persistent storage for media files
- ✅ Production-ready with health checks

**Files Created:**
- `k8s/helm/collectiveaccess/Chart.yaml` - Chart metadata (v1.0.0)
- `k8s/helm/collectiveaccess/values.yaml` - Tenant configuration (16 lines)
- `k8s/helm/collectiveaccess/templates/secret.yaml` - Database credentials
- `k8s/helm/collectiveaccess/templates/pvc.yaml` - Media storage
- `k8s/helm/collectiveaccess/templates/deployment.yaml` - CA app with probes
- `k8s/helm/collectiveaccess/templates/service.yaml` - Internal service
- `k8s/helm/collectiveaccess/templates/ingress.yaml` - TLS ingress
- `k8s/README.md` - Complete deployment guide
- `k8s/SIMPLIFIED_STRUCTURE.md` - Architecture summary

---

## 🧠 Phase 3 — SaaS Backend API (Week 5-10)

**Objectives:** Orchestration layer: subscriptions → K8s, user management, Stripe integration

**Tasks:**

- Backend setup: FastAPI/NestJS, PostgreSQL, Redis, logging
- Backend setup: FastAPI/NestJS, PostgreSQL, Redis, logging
- DB schema: users, tenants, subscriptions, deployments, tickets, audit logs
- Auth: JWT, OAuth, RBAC, invitation system
- Stripe: checkout, webhooks, subscription lifecycle
- K8s automation: CRUD for namespaces + Helm, retry & queue logic
- Background workers: provisioning, health checks, backups

**Deliverables:**
- ✅ REST API + OpenAPI
- ✅ Stripe integration & webhooks
- ✅ K8s automation
- ✅ Background job processing

---

## 🌐 Phase 4 — Customer Portal (Week 8-12)

**Objectives:** Build user-facing dashboard: subscription, tenant monitoring, responsive UI

**Tasks:**

- Frontend: Next.js + Tailwind + shadcn/ui
- Auth: JWT + OAuth, login/signup/password reset
- Dashboard: tenant overview, resource usage, backups, upgrade/downgrade
- Billing & team management, support interface
- Reusable component library, API integration, real-time metrics
- Mobile-first responsive design

**Deliverables:**
- ✅ Functional portal with dashboard
- ✅ Authentication & subscription management
- ✅ Tenant monitoring & support UI
- ✅ Component library & tests

---

## 💾 Phase 5 — Backups, Security & Observability (Week 10-14)

**Objectives:** Automated backup/restore, monitoring, logging, security hardening

**Tasks:**

- Velero backups, retention policies, restore workflows
- Database dumps with encryption, PITR
- Prometheus + Grafana dashboards, alerts
- Loki/ELK logging, log retention
- Cluster & application security: Pod Security, network policies, secrets, WAF, DDoS, CSP
- Compliance & audit logging
- Upgrade automation: rolling updates, rollback

**Deliverables:**
- ✅ Backup & restore system
- ✅ Monitoring dashboards & alerting
- ✅ Security checklist & audit logs
- ✅ Disaster recovery tested

---

## 🤖 Phase 6 — AI Support Layer (Week 14-18)

**Objectives:** AI chatbot & automation for troubleshooting, ticket triage, self-service knowledge base

**Tasks:**

- Knowledge base: CA docs + internal FAQs
- RAG system: vector DB, embeddings, retrieval
- AI agent: tenant status, logs, diagnostics, ticket creation
- Chat UI: streaming responses, markdown, feedback
- Automated diagnostics: pod restarts, disk cleanup, certificate renewal
- Observability: track AI performance & user satisfaction

**Deliverables:**
- ✅ RAG chatbot
- ✅ Automated ticket classification & diagnostic tools
- ✅ Admin analytics dashboard

---

## 🏢 Phase 7 — Enterprise Features (Week 18+)

**Objectives:** Enterprise-grade capabilities: SSO, custom domains, multi-region, white-label, advanced billing

**Tasks:**

- SSO (SAML/OAuth) + multi-org support
- Custom domain provisioning + auto SSL
- Enterprise RBAC + audit logs
- Private networking + VPC/VPN support
- Multi-region deployment & disaster recovery
- On-prem Helm installation & airgap
- White-label portal & CA branding
- Advanced billing, SLAs, analytics

**Deliverables:**
- ✅ SSO, domains, RBAC
- ✅ Multi-region deployment
- ✅ Enterprise-grade billing & SLA monitoring
- ✅ White-label options

---

## 📋 Technical Stack Summary

**Infrastructure:** Kubernetes (GKE/EKS/Hetzner), Docker registry, S3-compatible storage, Cloudflare CDN/DNS  
**Backend:** FastAPI/NestJS, PostgreSQL, Redis, Celery/Bull, optional Elasticsearch  
**Frontend:** Next.js + TypeScript, Tailwind, shadcn/ui, TanStack Query, Zustand  
**DevOps:** Terraform, GitHub Actions, Prometheus/Grafana, Loki/ELK, Velero, Vault/Sealed Secrets  
**AI/ML:** GPT-4/Claude, LangChain/LlamaIndex, ChromaDB/Pinecone, LangSmith/Langfuse  
**External Services:** Stripe, Auth0/custom JWT, SendGrid/AWS SES, UptimeRobot, PostHog/Plausible

---

## 🎯 Key Milestones

| Week | Phase | Milestone |
|------|-------|-----------|
| 0-2 | Phase 0 | Business foundation complete |
| 3 | Phase 1 | CA Docker image working |
| 6 | Phase 2 | First tenant deployed on K8s |
| 10 | Phase 3 | Backend API + Stripe live |
| 12 | Phase 4 | Customer portal MVP |
| 14 | Phase 5 | Security & backups in production |
| 18 | Phase 6 | AI support chatbot operational |
| 20+ | Phase 7 | Enterprise features rolling out |

---

## 🎉 Success Metrics

**Technical:** uptime > 99.9%, API p95 < 200ms, provisioning < 3 min, backup success 100%  
**Business:** 100 customers first year, €10k MRR, churn <5%, NPS > 50  
**Product:** signup → active >70%, time to first value <10 min, daily active users >60%, AI resolution >60%

---

**Version:** 1.0  
**Last Updated:** January 13, 2026  
**Next Review:** February 13, 2026