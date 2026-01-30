# How It Works - Helm Chart Architecture

## Overview

This Helm chart deploys a single Collective Access tenant as isolated Kubernetes resources. Each tenant gets its own namespace, domain, database, and storage.

---

## File Structure

```
k8s/
├── README.md                      # Step-by-step deployment guide
├── HOW_IT_WORKS.md               # This file - architecture explanation
├── SIMPLIFIED_STRUCTURE.md       # Simplification documentation
├── selfsigned-issuer.yaml        # ClusterIssuer for local testing
├── letsencrypt-issuer.yaml       # ClusterIssuer for production
├── mysql-deployment.yaml         # Shared MySQL database
└── helm/
    └── collectiveaccess/
        ├── Chart.yaml            # Chart metadata
        ├── values.yaml           # Tenant configuration
        └── templates/
            ├── secret.yaml       # Database credentials
            ├── pvc.yaml          # Persistent storage
            ├── deployment.yaml   # CA application
            ├── service.yaml      # Internal routing
            └── ingress.yaml      # External access + TLS
```

---

## Infrastructure Setup Files

Before deploying tenants, these files set up the cluster infrastructure:

### selfsigned-issuer.yaml
**Purpose:** ClusterIssuer for local Minikube testing

**Why:** Minikube doesn't have a public IP/domain, so Let's Encrypt won't work. Self-signed certificates allow testing HTTPS locally without external domain validation.

**Apply once:**
```bash
kubectl apply -f selfsigned-issuer.yaml
```

**Creates:** ClusterIssuer named `selfsigned` that issues self-signed certificates

---

### letsencrypt-issuer.yaml
**Purpose:** ClusterIssuer for production with real domains

**Contains:**
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt
spec:
  acme:
    email: julijaand111@gmail.com
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt
    solvers:
      - http01:
          ingress:
            class: nginx
```

**Why:** Let's Encrypt provides free, trusted TLS certificates that browsers accept (unlike self-signed).

**Apply once:**
```bash
kubectl apply -f letsencrypt-issuer.yaml
```

**How it works:** When Ingress has annotation `cert-manager.io/cluster-issuer: letsencrypt`, cert-manager automatically requests certificate from Let's Encrypt using HTTP-01 challenge.

---

### mysql-deployment.yaml
**Purpose:** Shared MySQL database for all tenants

**Contains:**
- **PersistentVolumeClaim:** 10Gi storage for MySQL data
- **Deployment:** MySQL 8.0 container with root password
- **Service:** ClusterIP service at `mysql.ca-system.svc.cluster.local:3306`

**Why shared:** One MySQL server, separate database per tenant = cheaper infrastructure, easier to manage.

**Apply once:**
```bash
kubectl create namespace ca-system
kubectl apply -f mysql-deployment.yaml
```

**Per-tenant setup:** Each tenant gets its own database:
```sql
CREATE DATABASE tenant1;
CREATE USER 'ca'@'%' IDENTIFIED BY 'secure-password';
GRANT ALL PRIVILEGES ON tenant1.* TO 'ca'@'%';
```

**DNS name:** `mysql.ca-system.svc.cluster.local` (accessible from any namespace)

---

## Helm Chart Files

These files create per-tenant resources:

---

## File Responsibilities

### Chart.yaml
**Purpose:** Chart metadata

**Contains:**
- Chart name: `collectiveaccess`
- Version: `1.0.0`
- App version: `2.0.10` (Collective Access version)

**Used by:** Helm to identify and version the chart

---

### values.yaml
**Purpose:** Tenant configuration values

**Contains:**
```yaml
tenantName: tenant1              # Names all resources
domain: tenant1.yourdomain.com   # Public domain
database:
  host: mysql.ca-system.svc.cluster.local
  name: tenant1                  # Database name
  user: ca
  password: secure-password
image: your-registry/ca-docker:latest
storageSize: 20Gi                # Media storage size
```

**Used by:** All template files via `{{ .Values.* }}` placeholders

**Why:** Separates configuration from infrastructure code. Change values without touching templates.

---

### templates/secret.yaml
**Purpose:** Store database credentials securely

**Creates:** Kubernetes Secret with DB connection details

**Generated resources:**
- Secret name: `{{ .Values.tenantName }}-db`
- Contains: `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

**How pods use it:** Environment variables injected via `envFrom.secretRef`

**Why secure:** Credentials not hardcoded in deployment. Encrypted at rest in etcd.

---

### templates/pvc.yaml
**Purpose:** Persistent storage for media files

**Creates:** PersistentVolumeClaim for uploaded images/documents

**Generated resources:**
- PVC name: `{{ .Values.tenantName }}-media`
- Size: From `{{ .Values.storageSize }}`
- Access mode: ReadWriteOnce (one pod writes)

**What it stores:** `/var/www/html/ca/media` directory

**Why important:** Media files survive pod crashes/restarts

---

### templates/deployment.yaml
**Purpose:** Main Collective Access application

**Creates:** Kubernetes Deployment with CA container

**Key features:**
- **Container:** Runs your CA Docker image
- **Replicas:** 1 (can scale manually)
- **Environment:** DB credentials from secret
- **Volume mount:** PVC mounted at `/var/www/html/ca/media`
- **Liveness probe:** HTTP GET to `:80/` (checks if alive)
- **Readiness probe:** HTTP GET to `:80/` (checks if ready for traffic)
- **Resources:**
  - Requests: 500m CPU, 512Mi RAM
  - Limits: 1000m CPU, 1Gi RAM

**Health checks:**
- Liveness: Restarts pod if fails
- Readiness: Removes from service if fails

**Why critical:** This is your actual application

---

### templates/service.yaml
**Purpose:** Internal routing to pods

**Creates:** ClusterIP Service

**Generated resources:**
- Service name: `{{ .Values.tenantName }}`
- Selector: `app={{ .Values.tenantName }}`
- Port: 80 → pod port 80

**DNS name:** `tenant1.tenant1.svc.cluster.local` (within cluster)

**Why needed:** Pods have dynamic IPs. Service provides stable endpoint. Ingress routes to service, not pod.

---

### templates/ingress.yaml
**Purpose:** External access with automatic TLS

**Creates:** Kubernetes Ingress

**Generated resources:**
- Ingress name: `{{ .Values.tenantName }}`
- Host: `{{ .Values.domain }}`
- Backend: Service `{{ .Values.tenantName }}:80`
- TLS secret: `{{ .Values.tenantName }}-tls`

**Annotations:**
- `cert-manager.io/cluster-issuer: letsencrypt` (production) or `selfsigned` (local)

**What happens:**
1. Ingress controller (nginx) sees new Ingress
2. Creates external LoadBalancer (or NodePort for Minikube)
3. Routes `tenant1.yourdomain.com` → Service → Pod
4. cert-manager sees annotation
5. Requests certificate from configured ClusterIssuer:
   - **letsencrypt:** Real trusted certificate via HTTP-01 challenge
   - **selfsigned:** Self-signed certificate (instant, but browser warning)
6. Stores certificate in TLS secret `tenant1-tls`
7. Ingress serves HTTPS

**Why important:** Makes tenant publicly accessible with HTTPS

---Complete Deployment Flow

### Infrastructure Setup (One-time)

**Step 0:** Set up cluster infrastructure
```bash
# 1. Start Minikube (or create cloud cluster)
minikube start --cpus=4 --memory=7000

# 2. Install NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/cloud/deploy.yaml

# 3. Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# 4. Create certificate issuer (choose one)
kubectl apply -f selfsigned-issuer.yaml    # For Minikube
kubectl apply -f letsencrypt-issuer.yaml   # For production

# 5. Deploy shared MySQL
kubectl create namespace ca-system
kubectl apply -f mysql-deployment.yaml

# 6. Push Docker image to registry
# Option A: Docker Hub
docker login
docker tag ca-docker-ca:latest yourusername/collectiveaccess:latest
docker push yourusername/collectiveaccess:latest

# Option B: Load into Minikube (local only)
minikube image load ca-docker-ca:latest
```

**Result:** Cluster ready for tenant deployments

---
Uses configured ClusterIssuer (letsencrypt or selfsigned)
- **Production:** Requests Let's Encrypt certificate via HTTP-01 challenge
- **Local:** Issues self-signed certificate instantly
- Stores certificate in `tenant1-tls` secret
- Ingress starts serving HTTPS

### Step 5: Create tenant database
```bash
kubectl exec -it -n ca-system deployment/mysql -- mysql -u root -prootpassword123
CREATE DATABASE tenant1;
CREATE USER 'ca'@'%' IDENTIFIED BY 'secure-password';
GRANT ALL PRIVILEGES ON tenant1.* TO 'ca'@'%';
FLUSH PRIVILEGES;
```

### Step 6: Tenant is live

**For Production:**
- **DNS:** `tenant1.yourdomain.com` → LoadBalancer IP
- **Traffic:** Internet → Ingress → Service → Pod
- **TLS:** Let's Encrypt certificate (trusted by browsers, auto-renewed)

**For Minikube (Local):**
- **/etc/hosts:** `192.168.49.2 tenant1.local` (maps domain to Minikube IP)
- **Tunnel:** `minikube tunnel` (routes traffic from Mac to LoadBalancer)
- **Traffic:** Browser → /etc/hosts → Minikube IP → Tunnel → Ingress → Service → Pod
- **TLS:** Self-signed certificate (browser warning - safe to accept)
- **Access:** http://tenant1.local

**Why both /etc/hosts AND tunnel?**
- `/etc/hosts`: Makes `tenant1.local` resolve to Minikube IP (192.168.49.2)
- `minikube tunnel`: Creates network route from your Mac to the LoadBalancer service inside Minikube
- Without tunnel: Ingress has no external IP, traffic won't reach pods

### Step 2: Helm processes templates
- Reads `values.yaml`
- Replaces all `{{ .Values.* }}` placeholders
- Generates 5 Kubernetes YAML files

### Step 3: Resources created in order
1. **Secret** - DB credentials stored
2. **PVC** - Storage volume provisioned
3. **Deployment** - Pod starts:
   - Pulls Docker image
   - Mounts PVC to `/var/www/html/ca/media`
   - Reads DB credentials from secret
   - Runs health checks
4. **Service** - Internal DNS created
5. **Ingress** - External routing configured

### Step 4: cert-manager provisions TLS
- Sees Ingress with `cert-manager.io/cluster-issuer` annotation
- Requests certificate from Let's Encrypt
- Completes HTTP-01 challenge
- Stores certificate in `tenant1-tls` secret
- Ingress starts serving HTTPS

### Step 5: Tenant is live
- DNS: `tenant1.yourdomain.com` → LoadBalancer IP
- Traffic: Internet → Ingress → Service → Pod
- TLS: Automatic certificate, auto-renewed every 90 days

---

## Multi-Tenant Isolation

### How tenants stay isolated:

**Kubernetes Namespaces:**
- `tenant1` namespace: All resources for tenant 1
- `tenant2` namespace: All resources for tenant 2
- Resources in different namespaces can't access each other by default

**Separate Databases:**
- `tenant1` database: Only tenant 1's data
- `tenant2` database: Only tenant 2's data
- Each tenant has own DB user with access only to their DB

**Separate Storage:**
- `tenant1-media` PVC: Only tenant 1's files
- `tenant2-media` PVC: Only tenant 2's files
- Volumes mounted only to their respective pods

**Separate Domains:**
- `tenant1.yourdomain.com` → tenant 1 pod
- `tenant2.yourdomain.com` → tenant 2 pod
- Ingress routes by hostname

---

## What Happens When...

### A pod crashes
1. Liveness probe fails
2. Kubernetes restarts pod
3. New pod mounts same PVC (media files intact)
4. Reads same secret (DB credentials)
5. Connects to same database
6. Service routes to new pod
7. **User sees no downtime** (if multiple replicas)

### You scale to 3 replicas
```bash
kubectl scale deployment/tenant1 -n tenant1 --replicas=3
```
1. Kubernetes creates 2 more pods
2. All 3 pods:
   - Mount same PVC (ReadWriteOnce - one writer at a time)
   - Read same secret
   - Connect to same database
3. Service load-balances across all 3 pods
4. **Handles 3x more traffic**

### Certificate expires
1. cert-manager watches certificates
2. Auto-renews 30 days before expiration
3. Updates TLS secret
4. Ingress picks up new certificate
5. **Zero downtime, automatic**

### You delete the tenant
```bash
helm uninstall tenant1 -n tenant1
```
1. Helm deletes: Ingress, Service, Deployment, Secret
2. Kubernetes terminates pod
3. **PVC persists** (manual delete required)
4. Database persists (manual drop required)
5. **Data is safe** - can reinstall

---

## Resource Naming Convention

All resources named with `{{ .Values.tenantName }}`:

- Deployment: `tenant1`
- Service: `tenant1`
- Ingress: `tenant1`
- Secret: `tenant1-db`
- PVC: `tenant1-media`
- TLS Secret: `tenant1-tls`

**Why consistent:** Easy to identify, manage, and debug

---

## Environment Variable Flow

```
values.yaml
  database.host: "mysql.ca-system.svc.cluster.local"
    ↓
secret.yaml
  stringData.DB_HOST: {{ .Values.database.host }}
    ↓
Kubernetes Secret
  DB_HOST: "mysql.ca-system.svc.cluster.local" (base64)
    ↓
deployment.yaml
  envFrom.secretRef: tenant1-db
    ↓
Pod Environment
  DB_HOST=mysql.ca-system.svc.cluster.local
    ↓
CA reads $_ENV['DB_HOST']
```

---

## Key Design Decisions

### Why external database?
- ❌ Embedded DB in pod: Data lost on restart
- ✅ External DB: Pods stateless, can scale freely
- ✅ Shared MySQL: All tenants on one DB server (cheaper)
- ✅ Separate databases: Data isolated per tenant

### Why PersistentVolumeClaim?
- ❌ Store in pod: Lost on restart
- ❌ Store in DB: Too slow for images
- ✅ PVC: Persistent, fast, survives restarts

### Why health probes?
- **Liveness:** Auto-restart if CA crashes
- **Readiness:** Don't send traffic until CA ready
- **Result:** Self-healing, no manual intervention

### Why resource limits?
- Prevents one tenant consuming all cluster resources
- Guarantees minimum resources (requests)
- Protects other tenants from noisy neighbors

### Why cert-manager?
- ❌ Manual certificates: Expire, tedious
- ✅ Automatic: Zero-touch TLS
- ✅ Free: Let's Encrypt
- ✅ Auto-renewal: Never expires

---

## Production Considerations

**Current setup is production-ready for:**
- Small to medium tenants (< 1000 users each)
- Standard museum/gallery workloads
- Monthly costs: $50-200/tenant depending on cloud

**To scale further:**
- Use managed database (AWS RDS, Cloud SQL)
- Add horizontal pod autoscaling (HPA)
- Use CDN for media files (CloudFront, Cloudflare)
- Add monitoring (Prometheus, Grafana)
- Add backup automation (Velero)

---

## Summary

This Helm chart turns manual Kubernetes deployment into repeatable, automated tenant provisioning. Each file has a single responsibility. Together, they create a secure, isolated, production-ready Collective Access instance in ~2 minutes.

**Next:** Phase 3 automates this with a REST API - create tenant via `POST /tenants`, return in seconds.
