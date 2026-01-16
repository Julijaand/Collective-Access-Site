# Phase 2 — Kubernetes Base Platform

Complete step-by-step guide to deploy Collective Access as a multi-tenant SaaS.

## Prerequisites

- Kubernetes cluster (EKS, GKE, Hetzner, or Minikube)
- `kubectl` configured
- `helm` 3.x installed
- Domain name with DNS access

---

## Step 1: Create Kubernetes Cluster

Choose your provider:

**AWS EKS:**
```bash
eksctl create cluster --name ca-cluster --region us-east-1
```

**Google GKE:**
```bash
gcloud container clusters create ca-cluster --zone us-central1-a
```

**Hetzner** (cheapest):
```bash
# Use Hetzner Cloud Console - 3 nodes, CX21 or higher
```

**Local (Minikube):**
```bash
brew install minikube
minikube start --cpus=4 --memory=7000
```

Verify:
```bash
kubectl get nodes
# All nodes must be "Ready"
```

---

## Step 2: Install NGINX Ingress Controller

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/cloud/deploy.yaml
```

Wait for it to be ready:
```bash
kubectl get pods -n ingress-nginx
# ingress-nginx-controller should be "Running"
```

---

## Step 3: Install cert-manager (Automatic TLS)

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
```

Wait:
```bash
kubectl get pods -n cert-manager
# All pods must be "Running"
```

---

## Step 4: Create Let's Encrypt ClusterIssuer (for production). For local testing we use self-signed issuer since we don't have a real public domain yet

Create `letsencrypt.yaml`:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt
spec:
  acme:
    email: your-email@example.com  # Change this!
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt
    solvers:
      - http01:
          ingress:
            class: nginx
```

Apply:
```bash
kubectl apply -f letsencrypt.yaml
```

---

## Step 5: Install Storage (production). Minikube has a default storage provisioner, verify it with:
```bash
kubectl get storageclass
```

**Option A: Longhorn (recommended for Hetzner/bare-metal)**
```bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/master/deploy/longhorn.yaml
```

**Option B: Cloud provider storage**
- EKS: Uses EBS automatically
- GKE: Uses GCE PD automatically

Verify:
```bash
kubectl get storageclass
# You should see a default storage class
```

---

## Step 6: Set Up External Database

**Option A: Managed Database (recommended for production)**
- AWS RDS MySQL
- Google Cloud SQL
- Hetzner Cloud Database

**Option B: Deploy MySQL in Kubernetes**

```bash
kubectl create namespace ca-system

cat <<EOFDB | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-pvc
  namespace: ca-system
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mysql
  namespace: ca-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
      - name: mysql
        image: mysql:8.0
        env:
        - name: MYSQL_ROOT_PASSWORD
          value: your-root-password
        ports:
        - containerPort: 3306
        volumeMounts:
        - name: data
          mountPath: /var/lib/mysql
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: mysql-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: mysql
  namespace: ca-system
spec:
  selector:
    app: mysql
  ports:
    - port: 3306
EOFDB
```

Wait for MySQL to be ready:
```bash
kubectl get pods -n ca-system
# mysql-xxx should be "Running"
```

---

## Step 7: Deploy Your First Tenant

### 1. Create tenant namespace
```bash
kubectl create namespace tenant1
```

### 2. Edit values

Edit `helm/collectiveaccess/values.yaml`:

```yaml
# Tenant configuration
tenantName: tenant1
domain: tenant1.yourdomain.com

# Database (external)
database:
  host: mysql.ca-system.svc.cluster.local
  name: tenant1
  user: ca
  password: secure-password

# Docker image
image: your-registry/ca-docker:latest

# Storage
storageSize: 20Gi
```

### 3. Deploy with Helm

```bash
helm install tenant1 ./helm/collectiveaccess -n tenant1
```

### 4. Create database for tenant

```bash
kubectl exec -it -n ca-system deployment/mysql -- mysql -u root -p

# In MySQL prompt:
CREATE DATABASE tenant1;
CREATE USER 'ca'@'%' IDENTIFIED BY 'secure-password';
GRANT ALL PRIVILEGES ON tenant1.* TO 'ca'@'%';
FLUSH PRIVILEGES;
EXIT;
```

---

## Step 8: Access Your Tenant

**For Minikube (macOS with Docker driver):**

The Docker driver on macOS doesn't support direct ingress access. Use port-forwarding:

```bash
# Option 1: kubectl port-forward (recommended - consistent port)
kubectl port-forward -n tenant1 svc/tenant1 8080:80
# Access: http://localhost:8080

# Option 2: minikube service (random port each time)
minikube service tenant1 -n tenant1
# Access: http://127.0.0.1:<random-port>
```

**For Production (Cloud):**

Get your LoadBalancer IP:
```bash
kubectl get svc -n ingress-nginx ingress-nginx-controller
# Look for EXTERNAL-IP
```

Create DNS A record:
```
tenant1.yourdomain.com  →  <EXTERNAL-IP>
```

Access:
```
https://tenant1.yourdomain.com
```

---

## Step 9: Verify Deployment

Check all resources:
```bash
# Check all pods across all namespaces
kubectl get pods -A

# Check tenant1 pod specifically
kubectl get pods -n tenant1
# tenant1-xxx should be "Running"

# Check ingress
kubectl get ingress -n tenant1

# Check service
kubectl get svc -n tenant1
```

View logs:
```bash
kubectl logs -n tenant1 -l app=tenant1 --tail=50
```

**Login credentials:**
- Username: `administrator`
- Password: `admin123`

**Note for Minikube:** Ingress shows ADDRESS but direct access doesn't work with Docker driver on macOS. Use port-forwarding (Step 8) instead.

---

## Deploy Additional Tenants

For tenant 2:

```bash
# 1. Create namespace
kubectl create namespace tenant2

# 2. Create database
kubectl exec -it -n ca-system deployment/mysql -- mysql -u root -p
CREATE DATABASE tenant2;
GRANT ALL PRIVILEGES ON tenant2.* TO 'ca'@'%';
EXIT;

# 3. Deploy
helm install tenant2 ./helm/collectiveaccess -n tenant2 \
  --set tenantName=tenant2 \
  --set domain=tenant2.yourdomain.com \
  --set database.name=tenant2

# 4. Configure DNS
# Add A record: tenant2.yourdomain.com → <EXTERNAL-IP>
```

---

## Management Commands

### View all tenants
```bash
kubectl get namespaces | grep tenant
helm list --all-namespaces
```

### View tenant logs
```bash
kubectl logs -n tenant1 -l app=tenant1 -f
```

### Scale tenant
```bash
kubectl scale deployment/tenant1 -n tenant1 --replicas=3
```

### Delete tenant
```bash
helm uninstall tenant1 -n tenant1
kubectl delete namespace tenant1

# Don't forget to drop the database:
kubectl exec -it -n ca-system deployment/mysql -- mysql -u root -p
DROP DATABASE tenant1;
```

### Reset admin password
```bash
POD=$(kubectl get pod -n tenant1 -l app=tenant1 -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n tenant1 $POD -- \
  php /var/www/html/ca/support/bin/caUtils reset-password \
  --username=administrator --password=newpass
```

### Backup tenant data
```bash
# Backup media files
POD=$(kubectl get pod -n tenant1 -l app=tenant1 -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n tenant1 $POD -- tar czf /tmp/media-backup.tar.gz -C /var/www/html/ca/media .
kubectl cp tenant1/$POD:/tmp/media-backup.tar.gz ./tenant1-media-backup.tar.gz

# Backup database
kubectl exec -n ca-system deployment/mysql -- \
  mysqldump -u root -pyour-root-password tenant1 > tenant1-db-backup.sql
```

---

## Troubleshooting

### Pod not starting
```bash
kubectl describe pod -n tenant1 <pod-name>
kubectl logs -n tenant1 <pod-name>
```

### Database connection failed
```bash
# Test from pod
kubectl exec -it -n tenant1 <pod-name> -- \
  mysql -h mysql.ca-system.svc.cluster.local -u ca -p
```

### TLS certificate not issued
```bash
kubectl get certificate -n tenant1
kubectl describe certificate -n tenant1 tenant1-tls
kubectl logs -n cert-manager -l app=cert-manager
```

### Ingress not working
```bash
kubectl get ingress -n tenant1
kubectl describe ingress -n tenant1
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
```

### Check events
```bash
kubectl get events -n tenant1 --sort-by='.lastTimestamp'
```

---

## Helm Chart Structure

```
helm/collectiveaccess/
├── Chart.yaml              # Chart metadata (v1.0.0)
├── values.yaml             # Tenant configuration
└── templates/
    ├── secret.yaml         # Database credentials
    ├── pvc.yaml           # Persistent storage for media
    ├── deployment.yaml     # CA application
    ├── service.yaml       # Internal service
    └── ingress.yaml       # External access + TLS
```

**📖 See [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for detailed architecture explanation**

---

## What You've Built

✅ **Multi-tenant SaaS platform**  
✅ **Automatic TLS certificates**  
✅ **Persistent storage per tenant**  
✅ **Isolated namespaces**  
✅ **Custom domains per tenant**  
✅ **Production-ready with health checks**

Ready for Phase 3: Backend API automation!

---

## Next Steps (Phase 3)

Build a backend API that:
- Creates tenants automatically via REST API
- Provisions databases programmatically
- Executes `helm install` via Kubernetes API
- Manages DNS records automatically
- Handles Stripe subscriptions
- Monitors tenant health

This turns manual deployment into full SaaS automation.
