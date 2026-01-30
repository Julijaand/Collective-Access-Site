# Phase 3 — SaaS Backend (Provisioning Brain)

**Status:** ✅ Implementation Ready  
**Purpose:** Automated tenant provisioning and payment integration  
**Timeline:** Week 5-10

---

## Overview

The SaaS Backend is the **control plane** for the Collective Access platform. It automates the entire tenant lifecycle from subscription payment to deployed instance.

**Key Features:**

* Stripe payment processing and webhooks
* Automated tenant provisioning via Kubernetes API
* PostgreSQL database for tenant state management
* RESTful API for tenant operations
* Idempotent webhook handling
* Comprehensive logging and audit trail

---

## Architecture

```
User → Stripe Checkout → Webhook → SaaS Backend → Kubernetes → CA Tenant
                                          ↓
                                    PostgreSQL
```

**Components:**
1. **FastAPI Backend** - REST API and webhook handler
2. **PostgreSQL** - Tenant state and subscription tracking
3. **Kubernetes Client** - Automated namespace and Helm operations
4. **Stripe Integration** - Payment processing and lifecycle management

---

## Prerequisites

### Required
- Python 3.11+
- PostgreSQL 13+
- Kubernetes cluster (Minikube or cloud)
- Kubectl configured
- Helm 3.x installed
- Stripe account with test keys

### Phase 2 Complete
- Working Helm chart at `../k8s/helm/collectiveaccess`
- MySQL database in `ca-system` namespace
- Docker image at `julijaand/collectiveaccess:latest`

---

### Tenant Naming & Namespaces

Tenant identifiers are generated **once** during provisioning and reused consistently across:
- Kubernetes namespace
- Helm release name
- MySQL database name
- CollectiveAccess `CA_APP_NAME`

**Source of truth:** `provisioning.py`

Do **not** hardcode or mutate naming logic inside:
- Dockerfiles
- CA PHP config
- Helm templates

Changing naming logic must be done centrally in the provisioning layer to avoid namespace drift.

## Quick Start

### 1. Install Dependencies

```bash
cd saas-backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Setup PostgreSQL

> **Note:** This PostgreSQL database is for the **SaaS backend control plane** (tenant management, subscriptions, billing).

#### Option A: docker-compose (Recommended)

**Why docker-compose?** Configuration as code, easy multi-service management, automatic networking, and industry standard for development.

**Start all services:**

```bash
# Start PostgreSQL (and optionally backend later)
docker-compose up -d

# View logs
docker-compose logs -f postgres

# Check status
docker-compose ps
```

**Verify services are running:**
```bash
docker-compose ps
# Should show: ca-saas-db ... Up (healthy) ... 0.0.0.0:5432->5432/tcp

docker-compose logs postgres | tail -20
# Should show: "database system is ready to accept connections"
```

**Test connection:**
```bash
docker-compose exec postgres psql -U ca_saas -d ca_saas
# You should see: ca_saas=#
\q
```

**Daily management:**
```bash
# Stop all services (keeps data)
docker-compose stop

# Start all services
docker-compose start

# Restart specific service
docker-compose restart postgres

# View logs (follow mode)
docker-compose logs -f postgres

# Backup database
docker-compose exec postgres pg_dump -U ca_saas ca_saas > backup_$(date +%Y%m%d).sql

# Restore database
docker-compose exec -T postgres psql -U ca_saas ca_saas < backup.sql

# Remove all services and volumes (WARNING: deletes all data!)
docker-compose down -v
```

**DATABASE_URL for .env:**
```env
DATABASE_URL=postgresql://ca_saas:ca_saas_password@localhost:5432/ca_saas

```

**Optional services in docker-compose.yml:**
- **pgAdmin** - Uncomment to get a database management UI at http://localhost:5050
- **backend** - Uncomment when ready to run FastAPI alongside PostgreSQL

---

#### Option B: Standalone Docker Container (Alternative)

**Use this if:** You prefer manual container management or don't need docker-compose yet.

**Start PostgreSQL container:**

```bash
docker run -d \
  --name ca-saas-db \
  -e POSTGRES_DB=ca_saas \
  -e POSTGRES_USER=ca_saas \
  -e POSTGRES_PASSWORD=ca_saas_password \
  -p 5432:5432 \
  --restart unless-stopped \
  postgres:15

# Wait for startup
sleep 5
```

**Verify container:**
```bash
docker ps | grep ca-saas-db
docker logs ca-saas-db | tail -20
```

**Test connection:**
```bash
docker exec -it ca-saas-db psql -U ca_saas -d ca_saas
\q
```

**DATABASE_URL for .env:**
```env
DATABASE_URL=postgresql://ca_saas:ca_saas_password@localhost:5432/ca_saas
```

---

#### Option C: Local PostgreSQL (Alternative)

**Use this if:** You prefer native macOS apps or already have PostgreSQL installed via Homebrew.

**Check if PostgreSQL is installed:**
```bash
psql --version
```

**Install PostgreSQL (if needed):**

**macOS:**
```bash
# Using Homebrew
brew install postgresql@15
brew services start postgresql@15

# Add to PATH if needed
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Ubuntu/Debian:**
```bash
sudo apt updateAll Options

**Check database exists:**
```bash
# docker-compose (recommended)
docker-compose exec postgres psql -U ca_saas -d ca_saas -c "\dt"

# Standalone Docker container
docker exec ca-saas-db psql -U ca_saas -d ca_saas -c "\dt"

# Local PostgreSQL
psql -U ca_saas -d ca_saas -h localhost -c "\dt"
```

**Expected output:**
```
Did not find any relations.
```
This is normal - tables will be created when you run `init_db()` in step 4.

---

**Troubleshooting PostgreSQL:**

```bash
# docker-compose: Check if port 5432 is already in use
lsof -i :5432

# docker-compose: View detailed logs
docker-compose logs postgres --tail 100

# docker-compose: Restart database
docker-compose restart postgres

# docker-compose: Access database shell directly
docker-compose exec postgres bash
```
```bash
# Option 1: Quick create (uses default superuser)
createdb ca_saas

# Option 2: Full setup with dedicated user (recommended)
# Access PostgreSQL as superuser
psql postgres

# Then run these commands in psql:
CREATE USER ca_saas WITH PASSWORD 'ca_saas_password';
CREATE DATABASE ca_saas OWNER ca_saas;
GRANT ALL PRIVILEGES ON DATABASE ca_saas TO ca_saas;
\q
```

**Test connection:**
```bash
psql -U ca_saas -d ca_saas -h localhost
# Enter password: ca_saas_password
# If successful, you'll see: ca_saas=#
\q
```
---

#### Verify Database Setup (Both Options)

**Check database exists:**
```bash
# Docker (recommended)
docker exec ca-saas-db psql -U ca_saas -d ca_saas -c "\dt"

# Local PostgreSQL
psql -U ca_saas -d ca_saas -h localhost -c "\dt"
```

**Expected output:**
```
Did not find any relations.
```
This is normal - tables will be created when you run `init_db()` in step 4.

### 3. Configure Environment

#### Step 1: Copy Environment Template

```bash
cp .env.example .env
```

#### Step 2: Get Stripe API Keys

1. Go to **Stripe Dashboard** → **Developers** → **API keys**
   - https://dashboard.stripe.com/test/apikeys
2. Copy **Secret key** (starts with `sk_test_...`)
3. Copy **Publishable key** (starts with `pk_test_...`)
4. Update `.env`:
   ```env
   STRIPE_SECRET_KEY=sk_test_your_actual_key_here
   STRIPE_PUBLISHABLE_KEY=pk_test_your_actual_key_here
   ```

#### Step 3: Generate Security Secret

```bash
# Generate a secure random key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Copy the output and update .env:
# SECRET_KEY=the_generated_key_here
```

#### Step 4: Get Webhook Secret (Choose One Option)

**Option A: Stripe CLI (Recommended for Local Development)**

```bash
# Install Stripe CLI if not installed
brew install stripe/stripe-cli/stripe

# Login to Stripe
stripe login

# Start webhook forwarding (keep this running in a terminal)
stripe listen --forward-to localhost:8000/webhooks/stripe
```

**Output will show:**
```
> Ready! Your webhook signing secret is whsec_xxxxxxxxxxxxx
```

**Copy the `whsec_...` secret and update `.env`:**
```env
STRIPE_WEBHOOK_SECRET=whsec_the_secret_from_stripe_cli
```

**Option B: Stripe Dashboard (For Production/Public URL)**

1. Go to **Stripe Dashboard** → **Developers** → **Webhooks**
   - https://dashboard.stripe.com/test/webhooks
2. Click **"+ Add endpoint"**
3. Configure:
   - **Endpoint URL:** `https://your-domain.com/webhooks/stripe` (use ngrok for local testing)
   - **Events to send:** Select these 5 events:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_failed`
     - `invoice.payment_succeeded`
4. Click **"Add endpoint"**
5. Click **"Reveal"** next to "Signing secret"
6. Copy the `whsec_...` value and update `.env`

#### Step 5: Configure Other Variables

### 4. Initialize Database

```python
# Run from Python shell or create a script
from app.database import init_db
init_db()
```

### 5. Run Backend

```bash
# Development
uvicorn app.main:app --reload --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. Test Health

```bash
curl http://localhost:8000/health
```

---

## Stripe Setup

### 1. Create Products

In Stripe Dashboard → Products:

| Product | Price | Stripe Price ID |
|---------|-------|-----------------|
| Starter | €49/month | price_starter_xxx |
| Pro | €199/month | price_pro_xxx |
| Museum | €799/month | price_museum_xxx |

### 2. Configure Webhooks

**Webhook URL:** `https://your-domain.com/webhooks/stripe`

**Events to listen for:**
- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`
- `invoice.payment_succeeded`

### 3. Update Code

In `app/stripe_webhooks.py`, update the `plan_mapping` dictionary with your actual Stripe price IDs:

```python
plan_mapping = {
    "price_starter_xxx": "starter",
    "price_pro_xxx": "pro",
    "price_museum_xxx": "museum"
}
```

### 4. Test Webhooks Locally

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local backend
stripe listen --forward-to localhost:8000/webhooks/stripe
```

---

## API Endpoints

### Health & Status

```bash
# Health check
curl http://localhost:8000/health

# Root
curl http://localhost:8000/
```

### Tenant Management

```bash
# List all tenants
curl "http://localhost:8000/tenants?skip=0&limit=100"

# Get tenant by ID (replace 1 with actual tenant_id)
curl http://localhost:8000/tenants/1

# Get tenant by namespace (replace tenant-namespace with actual namespace)
curl http://localhost:8000/tenants/namespace/tenant-namespace

# Delete tenant (replace 1 with actual tenant_id)
curl -X DELETE http://localhost:8000/tenants/1
```

### Admin Operations

```bash
# Get detailed tenant status (replace 1 with actual tenant_id)
curl http://localhost:8000/admin/tenants/1/status

# Suspend tenant (replace 1 with actual tenant_id)
curl -X POST http://localhost:8000/admin/tenants/1/suspend

# Resume tenant (replace 1 with actual tenant_id)
curl -X POST http://localhost:8000/admin/tenants/1/resume
```

### Stripe Webhook

```bash
# Webhook endpoint (Stripe calls this)
curl -X POST http://localhost:8000/webhooks/stripe \
  -H "Stripe-Signature: test" \
  -d '{}'
```

---

## Database Schema

### Tables

**users**
- id, email, password_hash, created_at

**tenants**
- id, user_id, namespace, helm_release_name
- domain, plan, status, db_name, db_user
- ca_admin_username, ca_admin_password
- created_at, updated_at, deployed_at

**subscriptions**
- id, tenant_id, stripe_subscription_id
- stripe_customer_id, stripe_price_id, status
- current_period_start, current_period_end
- created_at, updated_at, canceled_at

**provisioning_logs**
- id, tenant_id, action, status, message
- error_details, stripe_event_id
- created_at, completed_at

### Tenant Status Flow

```
PENDING → PROVISIONING → ACTIVE
                ↓
              FAILED

ACTIVE → SUSPENDED (unpaid)
       → DELETED (canceled)
```

---

## Provisioning Workflow

When Stripe webhook `checkout.session.completed` fires:

1. **Extract data** - customer email, subscription ID, plan
2. **Create user** - if not exists
3. **Generate identifiers** - tenant-{uuid}, namespace, domain, db_name (single source of truth, reused across Helm, Kubernetes, CA_APP_NAME)
4. **Create database records** - tenant, subscription, provisioning_log
5. **Update status** - PENDING → PROVISIONING
6. **Create Kubernetes namespace**
7. **Create MySQL database** - via kubectl exec
8. **Deploy via Helm** - install chart with tenant-specific values
9. **Run CA installer** - caUtils install with default profile
10. **Extract admin password** - from installer output
11. **Update status** - PROVISIONING → ACTIVE
12. **Send welcome email** - (to be implemented)

**Time:** ~60-90 seconds from payment to live tenant

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | localhost:5432 |
| `STRIPE_SECRET_KEY` | Stripe API secret key | - |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | - |
| `KUBERNETES_IN_CLUSTER` | Running inside K8s cluster | false |
| `HELM_CHART_PATH` | Path to Helm chart | ../k8s/helm/collectiveaccess |
| `BASE_DOMAIN` | Base domain for tenants | yoursaas.com |
| `DB_HOST` | MySQL host (shared CA DB) | mysql.ca-system... |
| `DB_USER` | MySQL user | ca |
| `DB_PASSWORD` | MySQL password | capassword123 |
| `CA_DOCKER_IMAGE` | CA Docker image | julijaand/collectiveaccess:latest |
| `CA_CERT_ISSUER` | TLS issuer | letsencrypt |

---

## Testing

### 1. Manual Provisioning (No Stripe)

```bash
curl -X POST http://localhost:8000/tenants/provision \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "email": "test@example.com",
    "plan": "starter",
    "stripe_subscription_id": "sub_test123",
    "stripe_customer_id": "cus_test123"
  }'
```

### 2. Simulate Stripe Webhook

```bash
# With Stripe CLI
stripe trigger checkout.session.completed
```

### 3. Check Tenant Status

To list all tenants and find their IDs, run:
```bash
curl "http://localhost:8000/tenants?skip=0&limit=100"
```

Then, to check a specific tenant's status:
```bash
curl http://localhost:8000/tenants/<tenant_id>
```

If you get a "not found" error, the tenant may not have been created or provisioning may have failed. Check logs and try again.

### 4. Verify Kubernetes

> **Tip:** Replace `<tenant-namespace>` with the actual namespace (often tenant-<tenant_id> or similar).

```bash
# List all tenant namespaces
kubectl get namespaces | grep tenant

# List pods in a tenant namespace
kubectl get pods -n <tenant-namespace>

# List Helm releases in a tenant namespace
helm list -n <tenant-namespace>
```

---

## Deployment


### Deploy to Kubernetes

> ⚠️ **Environment note**
>
> - **Local development (Minikube):** requires `minikube tunnel` to expose Ingress on ports 80/443  
> - **Production:** does **NOT** use `minikube tunnel`. A real cloud LoadBalancer + DNS is used instead.

---

#### Step 1: Create PostgreSQL Secret
Before starting the Postgres pod, create the required secret for the database password:
1. Copy the template `ca-saas-db-secret.yaml.template` to `ca-saas-db-secret.yaml`.
2. Fill in your real values, base64-encoded (see template for instructions).
3. Apply the secret:
```bash
kubectl apply -f ca-saas-db-secret.yaml
```
> **Note:** The password in this secret must match the password in your backend's `DATABASE_URL`.

#### Step 2: Create Backend Secret
Before deploying the backend, create the required secret for environment variables:
1. Copy the template `saas-backend-secrets.yaml.template` to `saas-backend-secrets.yaml`.
2. Fill in your real values, base64-encoded (see template for instructions).
3. Apply the secret:
```bash
kubectl apply -f saas-backend-secrets.yaml
```
> **Tip:** To encode a value, use: `echo -n 'your-value-here' | base64`
Set the DATABASE_URL to use the Kubernetes service name:
```env
DATABASE_URL=postgresql://ca_saas:ca_saas_password@ca-saas-db:5432/ca_saas
```

#### Step 3: Deploy PostgreSQL to Kubernetes
Create the PostgreSQL deployment and service manifests:
```bash
kubectl apply -f postgres-deployment.yaml
kubectl apply -f postgres-service.yaml
```
This will create a PostgreSQL instance accessible within your cluster as ca-saas-db:5432.

#### Step 4: Build & Push Backend Image
Build and push your backend Docker image:
```bash
docker build -t your-registry/ca-saas-backend:latest .
docker push your-registry/ca-saas-backend:latest
```

#### Step 5: Create Service Account & RBAC
Apply the provided manifest for backend RBAC:
```bash
kubectl apply -f saas-backend-rbac.yaml
```

#### Step 6: Deploy Backend to Kubernetes
Apply your backend deployment manifest (ensure all referenced secrets exist):
```bash
kubectl apply -f deployment.yaml
```
Or, if using a folder:
```bash
kubectl apply -f k8s/deployment.yaml
```
> **Note:** All referenced secrets (e.g., saas-backend-secrets) must exist in your cluster before applying the deployment.

---

## Ingress & Web Access

### Local Development (Minikube)

Minikube does not expose a real cloud LoadBalancer by default.
To make Ingress accessible locally, run:

```sh
sudo minikube tunnel
```

⚠️ **This command must stay running while you access the app.**

Once the tunnel is running:
- Ingress is exposed on `localhost:80` and `localhost:443`
- Host-based routing is handled by the Ingress controller

#### Test via curl
```sh
curl -k https://localhost \
   -H "Host: tenant-xxxx.yoursaas.com"
```

#### Browser access
1. Add the tenant domain to `/etc/hosts`:
   ```
   127.0.0.1 tenant-xxxx.yoursaas.com
   ```
2. Then open in browser:
   ```
   https://tenant-xxxx.yoursaas.com
   ```
You should see the CollectiveAccess installer or configuration page.

---

### Production (Real-world setup)

🚫 **Do NOT use minikube tunnel in production**

In production:
- The Ingress controller Service is of type `LoadBalancer`
- Your cloud provider assigns a public external IP
- DNS (Route53 / Cloudflare) points tenant domains to that IP
- Ingress routes traffic based on hostname

**Example:**
```
tenant-123.yoursaas.com → LoadBalancer IP → Ingress → Tenant Service
```

---

## Troubleshooting

### Backend won't start

```bash
# Check logs
docker logs ca-saas-backend

# Check database connection
psql -U ca_saas -h localhost ca_saas

# Check Kubernetes connection
kubectl get nodes
kubectl logs deployment/saas-backend -n ca-system
kubectl get pods -n ca-system
kubectl describe pod <pod-name> -n ca-system
```

### Tenant provisioning succeeds but site not accessible
```bash
kubectl get ingress -A
kubectl get svc ingress-nginx-controller -n ingress-nginx

# Ensure:
# minikube tunnel is running (local only)
# /etc/hosts points tenant domain to 127.0.0.1
# Ingress has correct host: value
```

### CollectiveAccess shows “database not installed”
This is expected for a fresh tenant.
Complete installation via:
https://tenant-xxxx.yoursaas.com/install/

### Provisioning fails

```bash
# Check provisioning logs
curl http://localhost:8000/admin/tenants/1/status

# Check Kubernetes events
kubectl get events -n tenant-{id} --sort-by='.lastTimestamp'

# Check pod logs
kubectl logs -n tenant-{id} -l app=tenant-{id}
```

### Webhook not receiving events

```bash
# Test webhook endpoint
curl -X POST http://localhost:8000/webhooks/stripe \
  -H "Stripe-Signature: test"

# Check Stripe webhook logs in dashboard
# Verify webhook URL is correct and accessible
```

├── docker-compose.yml       # Multi-service orchestration
└── Dockerfile               # Backend container imagissues

```bash
# Reset database
dropdb ca_saas && createdb ca_saas

# Check migrations (if using Alembic)
alembic current
alembic upgrade head
```

---

## Security Considerations

1. **Secrets Management**
   - Store sensitive data in Kubernetes secrets or environment variables
   - Never commit .env files
   - Rotate Stripe keys regularly

2. **RBAC**
   - Limit service account permissions to minimum required
   - Separate dev/prod Kubernetes clusters

3. **Webhook Security**
   - Always verify Stripe signatures
   - Implement rate limiting
   - Log all webhook events

4. **Database**
   - Use connection pooling
   - Enable SSL for production
   - Regular backups

---

## Next Steps (Post Phase 3)

1. **Frontend** - User dashboard for tenant management
2. **DNS Automation** - Route53/Cloudflare API integration
3. **Email Notifications** - Welcome emails, alerts
4. **Monitoring** - Prometheus, Grafana
5. **Backups** - Velero for Kubernetes, pg_dump for PostgreSQL
6. **AI Support** - Chatbot for customer support (Phase 6)

---

## File Structure

```
saas-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database connection
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── k8s.py               # Kubernetes client
│   ├── provisioning.py      # Tenant provisioning logic
│   └── stripe_webhooks.py   # Stripe event handlers
├── tests/
│   └── (test files)
├── alembic/
│   └── (migration files)
├── requirements.txt
├── .env.example
└── Dockerfile
```

---

## Support

**Issues:** GitHub Issues  
**Documentation:** See `PHASE_3_SCENARIO.md` for detailed implementation guide  
**Contact:** julijaand111@gmail.com

---

**Status:** ✅ Ready for implementation and testing  
**Next:** Test locally with Minikube, then deploy to cloud
