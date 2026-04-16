# Deploying Collective Access SaaS on Nebius Cloud (Kubernetes)

> 🔄 **Update this table every time you recreate the cluster.**  
> It is the single source of truth — all commands below reference these values.

| Variable | Current value |
|---|---|
| **Cluster name** | `brown-orangutan-cluster-8` |
| **Cluster ID** | `mk8scluster-e00nyd0fmnh7z6r8ak` |
| **Region** | `eu-north1` |
| **Project ID** | `project-e00tq1vbpr00t31ecxsw93` |
| **LoadBalancer IP** | *(filled after Step 4 — `kubectl get svc -n ingress-nginx ingress-nginx-controller`)* |
| **Test domain** | `<LB-IP>.nip.io` |
| **Node group ID** | *(filled after Step 3 — `nebius mk8s node-group list --parent-id <cluster-id>`)* |

---

## Prerequisites

- Nebius CLI: `curl -sSL https://storage.eu-north1.nebius.cloud/cli/install.sh | bash`
- `kubectl`, `helm`, `kustomize` installed: `brew install kubectl helm kustomize`
- Docker Hub account with **multi-platform** images pushed (see Step 0)
- Stripe account (test or live keys)

---

## Step 0 — Build & Push Multi-Platform Docker Images

Nebius nodes run `linux/amd64`. If you build on Apple Silicon (M-chip Mac), images are `arm64` by default and pods will fail with `ErrImagePull: no match for platform in manifest`.

Build all three images as multi-platform before deploying:

```bash
# Create builder once (reuse on subsequent builds)
docker buildx create --use --name multiarch 2>/dev/null || docker buildx use multiarch

# 1. Customer portal
cd customer-portal
docker buildx build --platform linux/amd64,linux/arm64 \
  -t julijaand/customer-portal:latest --push .

# 2. saas-backend
cd ../saas-backend
docker buildx build --platform linux/amd64,linux/arm64 \
  -t julijaand/saas-backend:latest --push .

# 3. CollectiveAccess (tenant image)
cd ../ca-docker
docker buildx build --platform linux/amd64,linux/arm64 \
  -t julijaand/collectiveaccess:latest --push .
```

Verify platforms on Docker Hub:
```bash
docker manifest inspect julijaand/saas-backend:latest | grep architecture
# should show both: "arm64" and "amd64"
```

After code changes, rebuild + restart:
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t julijaand/saas-backend:latest --push .
kubectl rollout restart deployment/saas-backend -n ca-system
```

---

## Step 1 — Create Kubernetes Cluster

> **Skip if the cluster already exists** — jump to [Step 2](#step-2--connect-kubectl-to-cluster).

### Via CLI (recommended)

```bash
source ~/.nebius/path.zsh.inc

nebius mk8s cluster create \
  --parent-id project-e00tq1vbpr00t31ecxsw93 \
  --name <your-cluster-name> \
  --control-plane-version 1.33 \
  --control-plane-endpoints-public-endpoint=true
```

> ⚠️ **`--control-plane-endpoints-public-endpoint=true` is required.** Without it, `get-credentials --external` fails with `Error: cluster has empty endpoint` and kubectl cannot connect from your local machine.

Wait for `RUNNING` state:
```bash
nebius mk8s cluster get --id <cluster-id> | grep state
# state: RUNNING  (takes ~2 min)
```

Note the cluster ID from the output — you'll need it in all subsequent steps.

### Via Console

1. Nebius Console → **Managed Service for Kubernetes** → **Create cluster**
2. Fill in **Name**, select **Region** `eu-north1`, subnet
3. ✅ **Enable public endpoint** — easy to miss; without it `get-credentials --external` will fail
4. Click **Create** and wait for `RUNNING`

### If you forgot to enable the public endpoint (cluster already created)

```bash
nebius mk8s cluster update \
  --id <cluster-id> \
  --control-plane-endpoints-public-endpoint=true
# Wait ~1 min, then retry get-credentials
```

---

## Step 2 — Connect kubectl to Cluster

```bash
source ~/.nebius/path.zsh.inc

# Get kubeconfig for the cluster
nebius mk8s cluster get-credentials \
  --id <cluster-id> \
  --external

# Verify
kubectl cluster-info
kubectl get nodes
```

**~/.nebius/config.yaml** must have:
```yaml
endpoint: api.eu-north1.nebius.cloud:443   # no https://, no trailing slash
```

---

## Step 3 — Node Group

The cluster needs nodes before any workloads can run.

### Via Console (recommended)

1. Nebius Console → **Managed Service for Kubernetes** → click your cluster
2. **Node groups** tab → **Create node group**
3. Fill in the form:

| Section | Field | Value |
|---|---|---|
| **General** | Name | `main-nodes` |
| **Computing resources** | GPU | ❌ No GPU |
| | Platform | `cpu-e2` |
| | Preset | `4 vCPU / 16 GB` |
| **Scale** | Type | Fixed |
| | Node count | `2` |
| **Node storage** | Disk type | `network-ssd` |
| | Size | `64 GiB` |
| **Network** | Assign public IPv4 | ✅ Yes (nodes need internet to pull Docker images) |
| **Access** | Credentials name | `nebius-nodes` |
| | Public key | paste output of `cat ~/.ssh/nebius_nodes.pub` |
| **Access** | Service account | leave empty |
| **Additional** | Enable autoscaling | ❌ No |
| | GPU drivers | ❌ No |

4. Click **Create**

> ⚠️ After creation you may briefly see a warning:
> `Waiting for a node with matching ProviderID to exist for nodes mk8snodegroup-...`
> This is normal — the VMs are booting. Wait 3–5 min.

**Generate SSH key** (if you don't have one):
```bash
ssh-keygen -t ed25519 -C "nebius-nodes" -f ~/.ssh/nebius_nodes -N ""
cat ~/.ssh/nebius_nodes.pub   # paste this into the Public key field
```

### Via CLI
```bash
nebius mk8s node-group create \
  --parent-id <cluster-id> \
  --name main-nodes \
  --fixed-node-count 2 \
  --template-resources-platform cpu-e2 \
  --template-resources-preset 4vcpu-16gb \
  --template-boot-disk-type network-ssd \
  --template-boot-disk-size-gibibytes 64
```

Wait for nodes to be `Ready`:
```bash
source ~/.nebius/path.zsh.inc
kubectl get nodes -w
```

> **Node sizing rationale:** 2 × (4 vCPU / 16 GB) = 8 vCPU / 32 GB total.
> Covers: saas-backend (2 replicas) + portal + PostgreSQL + Ollama (llama3.2:1b CPU) + ingress-nginx + cert-manager + ~4 tenant CA pods.

---

## Step 4 — Install Cluster Dependencies

```bash
# Nginx Ingress Controller
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer

# Wait until EXTERNAL-IP is assigned (not <pending>) — takes ~1 min
kubectl get svc -n ingress-nginx ingress-nginx-controller -w

# cert-manager
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true

# Let's Encrypt ClusterIssuer
kubectl apply -f k8s/letsencrypt-issuer.yaml

# Create app namespace
kubectl create namespace ca-system
```

> **Nebius storage class:** The only available storage class is `compute-csi-default-sc` (not `network-ssd`).  
> This is already handled in `k8s/overlays/nebius/patch-pvcs.yaml` — no manual action needed.

---

## Step 5 — DNS

### Option A — Testing with nip.io (no domain needed)

Use `<LB-IP>.nip.io` — it resolves automatically to your IP, no DNS setup required:
```
<LB-IP>.nip.io            → customer frontend
api.<LB-IP>.nip.io        → saas-backend API
```
Set `DOMAIN=<LB-IP>.nip.io` in `secrets.nebius.env` and skip the rest of this step.

---

### Option B — Production with Cloudflare (real domain)

#### 1. Add DNS records in Cloudflare

1. Go to **[dash.cloudflare.com](https://dash.cloudflare.com)** → click your domain
2. **DNS** → **Records** → **Add record** — create all three:

| Type | Name | IPv4 address | Proxy status |
|------|------|-------------|------------------|
| A | `@` (root) | `<LB-IP from Step 4>` | **DNS only** (grey ☁️) |
| A | `api` | `<LB-IP from Step 4>` | **DNS only** (grey ☁️) |
| A | `*` | `<LB-IP from Step 4>` | **DNS only** (grey ☁️) |

**What each record does:**
- `@` (root) → `yourdomain.com` — customer-facing Next.js frontend
- `api` → `api.yourdomain.com` — FastAPI backend
- `*` (wildcard) → `tenant1.yourdomain.com`, `tenant2.yourdomain.com` etc. — CA tenants each get a dynamic subdomain at provisioning time

> Subdomain names are configurable via `APP_SUBDOMAIN` and `API_SUBDOMAIN` in `secrets.nebius.env`.
> Match whatever subdomains you set here to your DNS records above.

> ⚠️ **Start with DNS only (grey ☁️) — do NOT enable the orange Cloudflare proxy yet.**
> cert-manager uses Let's Encrypt HTTP-01 challenge to issue TLS certificates. With the proxy ON,
> Let's Encrypt hits Cloudflare's edge instead of your nginx — the challenge fails and no certificate
> is issued. Keep DNS only until certs are confirmed `READY: True` (Step 9), then follow
> [**§ Enable Cloudflare Proxy**](#enable-cloudflare-proxy-optional-but-recommended) below.

---

#### Enable Cloudflare Proxy (optional but recommended)

Enables DDoS protection, WAF, CDN caching and hides your origin server IP behind Cloudflare.

> ⚠️ **Prerequisites before enabling proxy:**
> - All certs must be `READY: True`: `kubectl get certificate -n ca-system`
> - `CLOUDFLARE_API_TOKEN` must be set in `secrets.nebius.env` and `./deploy-secrets.sh` run
> - [k8s/letsencrypt-issuer.yaml](k8s/letsencrypt-issuer.yaml) must use `dns01` solver (already updated)

**Step A — Create Cloudflare API Token**
1. Go to [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens)
2. **Create Token** → use template **"Edit zone DNS"**
3. Under **Zone Resources** → select your domain
4. Copy the token → add to `secrets.nebius.env`:
   ```
   CLOUDFLARE_API_TOKEN=your_token_here
   ```
5. Apply:
   ```bash
   RECREATE=true ./deploy-secrets.sh
   ```

**Step B — Switch cert-manager to DNS-01 challenge**
```bash
# Apply the updated ClusterIssuer (already uses dns01 solver)
kubectl apply -f k8s/letsencrypt-issuer.yaml
```

**Step C — Force certificate renewal**
```bash
# Delete existing certs — cert-manager will re-request via DNS-01
kubectl delete certificate customer-portal-tls saas-backend-tls -n ca-system
kubectl delete secret customer-portal-tls saas-backend-tls -n ca-system

# Watch re-issuance (takes ~1-2 min)
kubectl get certificate -n ca-system -w
# Wait for READY = True on all certs before proceeding
```

**Step D — Enable orange proxy in Cloudflare**
1. Cloudflare Dashboard → **DNS** → **Records**
2. Click the grey ☁️ on `@` (root) and `api` records → toggle to orange 🟠
3. Leave `*` (wildcard) as **DNS only** — Cloudflare free plan does not proxy wildcard records

**Step E — Set SSL/TLS mode to Full (strict)**
1. Cloudflare Dashboard → **SSL/TLS** → **Overview**
2. Select **Full (strict)** — validates that your nginx cert is a real trusted cert (Let's Encrypt ✅)
   - *Full* (without strict) accepts any cert including self-signed — less secure
   - *Flexible* sends plain HTTP to your server — never use this

| What you gain with proxy 🟠 | |
|---|---|
| DDoS protection | ✅ |
| Hides origin server IP | ✅ |
| Cloudflare WAF | ✅ |
| Free CDN / caching | ✅ |
| Cert issuance method | DNS-01 via Cloudflare API |

#### 2. Update secrets.nebius.env

```bash
# Edit secrets.nebius.env:
DOMAIN=yourdomain.com   # e.g. collective-museum.com
```

#### 3. Regenerate overlay patches

`configure-nebius.sh` reads `DOMAIN` from `secrets.nebius.env` and rewrites all overlay patch files:

```bash
./configure-nebius.sh
# Output confirms:
#   BASE_DOMAIN   = yourdomain.com
#   PORTAL_HOST   = yourdomain.com
#   API_HOST      = api.yourdomain.com
#   CERT_ISSUER   = letsencrypt
```

Files regenerated:
- `k8s/overlays/nebius/patch-backend-env.yaml` — `BASE_DOMAIN`, `APP_URL`
- `k8s/overlays/nebius/patch-backend-ingress.yaml` — ingress host, CORS origin, cert issuer
- `k8s/overlays/nebius/patch-portal-ingress.yaml` — ingress host, cert issuer
- `k8s/overlays/nebius/patch-portal-configmap.yaml` — `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_URL`
- `customer-portal/.env.production` — baked into the Next.js Docker image at build time

#### 4. Rebuild the customer-portal image

`NEXT_PUBLIC_*` URLs are **baked into the Next.js bundle at build time** — the running image won't
pick up the new domain from the configmap. Rebuild and push:

```bash
cd customer-portal
docker buildx build --platform linux/amd64,linux/arm64 \
  -t julijaand/customer-portal:latest --push .
```

> ⚠️ Always use `--platform linux/amd64,linux/arm64`. Building on Apple Silicon produces an `arm64`-only
> image — Nebius nodes are `linux/amd64` and pods will fail with `ErrImagePull: no match for platform`.

Verify both platforms are present:
```bash
docker manifest inspect julijaand/customer-portal:latest | grep architecture
# should show both: "arm64" and "amd64"
```

#### 5. Verify DNS propagation (optional)

```bash
# Should return your LB IP
dig +short yourdomain.com
dig +short api.yourdomain.com
```

DNS typically propagates within 1–5 minutes on Cloudflare.

---

## Step 6 — Secrets

All secrets are managed via `secrets.nebius.env` + `deploy-secrets.sh`. **Never commit `secrets.nebius.env`** — it's in `.gitignore`.

```bash
# Copy template and fill in values
cp secrets.nebius.env.template secrets.nebius.env
# Edit secrets.nebius.env with your actual values

# Create all K8s secrets in one shot
./deploy-secrets.sh

# To recreate (e.g. after rotating keys):
RECREATE=true ./deploy-secrets.sh
```

`deploy-secrets.sh` creates these secrets in `ca-system`:

| Secret name | Keys |
|---|---|
| `saas-backend-secrets` | `database-url`, `stripe-secret-key`, `stripe-webhook-secret`, `db-password`, `secret-key` |
| `ca-saas-db-secret` | `POSTGRES_PASSWORD` |
| `customer-portal-secret` | `stripe-publishable-key` |
| `mysql-root-password` | `mysql-root-password` |

> ⚠️ **Important:** Updating a K8s secret does **not** automatically propagate to running pods — env vars are only read at pod startup. After any secret change, always restart the affected deployment:
> ```bash
> RECREATE=true ./deploy-secrets.sh
> kubectl rollout restart deployment/saas-backend -n ca-system
> kubectl rollout restart deployment/customer-portal -n ca-system
> ```

---

## Step 7 — Kustomize Overlays (Multi-environment)

Manifests stay in their original locations (`saas-backend/k8s/`, `customer-portal/k8s/`). Environment-specific values live in overlays — **source files are never modified**.

```
k8s/
  base/kustomization.yaml          ← lists all manifests
  overlays/
    minikube/                      ← local dev, no patches needed
    nebius/                        ← Nebius cloud (current)
      patch-backend-env.yaml       → BASE_DOMAIN + CA_CERT_ISSUER
      patch-backend-ingress.yaml   → host, CORS, cert issuer
      patch-portal-ingress.yaml    → host, cert issuer
      patch-portal-configmap.yaml  → API/app URLs
      patch-pvcs.yaml              → storageClassName: compute-csi-default-sc
    production/                    ← real domain (yoursaas.com placeholder)
```

To add a new environment, copy `overlays/nebius/` and update the domain values in the patch files.

---

## Step 8 — Deploy

```bash
cd /path/to/Collective-Access-Site

# 0. (Optional) Preview rendered manifests without applying anything
./deploy-nebius.sh --dry-run

# 1. Update domain in secrets and regenerate overlay files
#    (required any time the domain or LB IP changes)
#    Edit secrets.nebius.env: DOMAIN=yourdomain.com (or <LB-IP>.nip.io for testing)
./configure-nebius.sh

# 2. Create / update all K8s secrets (once, or when rotating keys)
./deploy-secrets.sh

# 3. Full deploy — applies all manifests (idempotent, safe to re-run)
./deploy-nebius.sh

# 4. Force-restart backend to ensure it reads secrets from a clean boot
#    (pods may start before secrets are fully ready on a fresh cluster)
kubectl rollout restart deployment/saas-backend -n ca-system
```

`deploy-nebius.sh` uses `kustomize build --load-restrictor LoadRestrictionsNone` (required because the base references files outside `k8s/`) piped into `kubectl apply -f -`.

> ⚠️ **Portal image must be rebuilt whenever the domain changes.** The Next.js app bakes `NEXT_PUBLIC_*` URLs at build time — the image won't pick up the new domain from the configmap alone.
> ```bash
> cd customer-portal
> docker buildx build --platform linux/amd64,linux/arm64 -t julijaand/customer-portal:latest --push .
> kubectl rollout restart deployment/customer-portal -n ca-system
> ```

---

## Step 9 — Verify Deployment

### Pods
```bash
# All pods should be Running (except ai-ingest which will be Completed)
kubectl get pods -n ca-system

# Expected healthy state:
# ca-saas-db-xxx        1/1  Running    ← PostgreSQL
# customer-portal-xxx   1/1  Running    ← Next.js frontend
# ollama-xxx            1/1  Running    ← LLM (slow first start — pulling llama3.2)
# saas-backend-xxx      1/1  Running    ← FastAPI backend (2 replicas)
# ai-ingest-xxx         0/1  Completed  ← one-off vector DB population job
```

### TLS Certificates
```bash
# READY should be True for all certs
kubectl get certificate -n ca-system

# If a cert is stuck False, check why:
kubectl describe certificate <cert-name> -n ca-system | tail -20
kubectl logs -n cert-manager -l app=cert-manager --tail=30
```

### Ingress & LoadBalancer
```bash
# Confirm LB IP is assigned (not <pending>) and hosts are correct
kubectl get ingress -n ca-system
```

### API Health Check
```bash
curl -s https://api.collective-museum.com/health
# Expected: {"status":"ok","version":"1.0.0","database":"connected","kubernetes":"connected"}
```

### Cloudflare Proxy (after enabling orange cloud 🟠)
```bash
# 1. IP should be a Cloudflare IP (104.21.x.x or 172.67.x.x), NOT your Nebius LB IP
dig +short collective-museum.com

# 2. Response headers should show cloudflare server + cf-ray header
curl -sI https://collective-museum.com | grep -i "cf-ray\|server"
# Expected:
#   server: cloudflare
#   cf-ray: xxxxxxxxxxxxxxxx-AMS

# 3. API must still work through the proxy
curl -s https://api.collective-museum.com/health
# Expected: {"status":"ok",...}

# 4. Check SSL cert issuer (should be Let's Encrypt, not Cloudflare self-signed)
curl -sv https://collective-museum.com 2>&1 | grep -i "issuer"
# Expected: issuer: C=US; O=Let's Encrypt; CN=R10
```

---

## Step 10 — Register Stripe Webhook

1. Go to **[dashboard.stripe.com/test/webhooks](https://dashboard.stripe.com/test/webhooks)**
2. Click **"Add destination"** → choose **Webhook**
3. Set:
   - **URL:** `https://api.collective-museum.com/api/stripe/webhook` (or your domain)
   - **Events:** `checkout.session.completed`, `customer.subscription.deleted`, `invoice.payment_failed`
4. After saving, click **"Reveal"** under *Signing secret* → copy the `whsec_...` value
5. If the secret differs from what's in `saas-backend-secrets`, update it:
   ```bash
   RECREATE=true ./deploy-secrets.sh
   ```

> For production, repeat with live mode keys at `dashboard.stripe.com/webhooks`.

---

## Step 11 — First Login

The database is empty on first deploy — go to the portal URL and **sign up** (no email verification required):

```
https://collective-museum.com/login
```

> For nip.io deployments: `https://<LB-IP>.nip.io/login`

---

## Troubleshooting

### PVCs stuck in Pending
```bash
kubectl get storageclass   # Nebius only has: compute-csi-default-sc
kubectl describe pvc <name> -n ca-system | grep -A5 Events
```
The overlay already sets `storageClassName: compute-csi-default-sc`. If you see `storageclass "network-ssd" not found`, delete and redeploy:
```bash
kubectl scale deployment ca-saas-db ollama saas-backend --replicas=0 -n ca-system
kubectl delete pvc ai-vector-db-pvc ollama-models-pvc postgres-data-pvc -n ca-system
./deploy-nebius.sh
```

### ErrImagePull / ImagePullBackOff
Platform mismatch — image was built for `arm64` only. Rebuild with `--platform linux/amd64,linux/arm64` (see Step 0).

### PostgreSQL CrashLoopBackOff: "directory exists but is not empty"
Cloud block storage volumes contain a `lost+found` directory at root. Fixed in `postgres-deployment.yaml` via `PGDATA=/var/lib/postgresql/data/pgdata` — this is already set.

### saas-backend can't connect to postgres
Usually postgres is still starting. Wait 30s then:
```bash
kubectl rollout restart deployment/saas-backend -n ca-system
```

### Stripe 401 "Invalid API Key" / checkout fails
The pod is running with a stale secret from before the last `deploy-secrets.sh`. K8s secrets injected as env vars are **only read at pod startup** — updating the secret has no effect on already-running pods. Fix:
```bash
kubectl rollout restart deployment/saas-backend -n ca-system
```

### Error: cluster has empty endpoint
`get-credentials --external` fails because the cluster was created without a public endpoint.
```bash
# Enable public endpoint on existing cluster
nebius mk8s cluster update \
  --id <cluster-id> \
  --control-plane-endpoints-public-endpoint=true
# Wait ~1 min, then:
nebius mk8s cluster get-credentials --id <cluster-id> --external
```
To avoid this: always pass `--control-plane-endpoints-public-endpoint=true` at cluster creation time (see Step 1).

### kubectl can't reach cluster
```bash
source ~/.nebius/path.zsh.inc
nebius mk8s cluster get-credentials --id <cluster-id> --external
```

---

## Scaling Node Group

```bash
nebius mk8s node-group update \
  --id <node-group-id> \
  --fixed-node-count 4
```

Each CA tenant pod uses ~500m CPU / 512Mi RAM + 20Gi storage.  
2 nodes (4vCPU/16GB each) → comfortable capacity for ~4–6 active tenants.

---

## Cluster Info Reference

> Same values as the header table — update both when recreating the cluster.

| Resource | Value |
|---|---|
| Cluster name | `brown-orangutan-cluster-8` |
| Cluster ID | `mk8scluster-e00nyd0fmnh7z6r8ak` |
| Project ID | `project-e00tq1vbpr00t31ecxsw93` |
| Public endpoint | `https://pu.mk8scluster-e00nyd0fmnh7z6r8ak.mk8s.eu-north1.nebius.cloud:443` |
| Private endpoint | `https://pr.mk8scluster-e00nyd0fmnh7z6r8ak.mk8s.eu-north1.nebius.cloud:443` |
| LoadBalancer IP | *(see header table)* |
| Storage class | `compute-csi-default-sc` |
