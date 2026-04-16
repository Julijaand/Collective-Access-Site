#!/bin/bash
# deploy-secrets.sh — Create all K8s secrets for the CA SaaS stack on Nebius
# Usage:
#   cp secrets.nebius.env.template secrets.nebius.env
#   # fill in secrets.nebius.env
#   ./deploy-secrets.sh
#
# To use a different env file: ENV_FILE=my.env ./deploy-secrets.sh
# To delete and recreate existing secrets: RECREATE=true ./deploy-secrets.sh

set -euo pipefail

ENV_FILE="${ENV_FILE:-secrets.nebius.env}"
RECREATE="${RECREATE:-false}"
NAMESPACE="ca-system"

# ── Load env file ─────────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ $ENV_FILE not found."
  echo "   cp secrets.nebius.env.template secrets.nebius.env"
  echo "   Then fill in the values and re-run."
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# ── Validate required vars ────────────────────────────────────────────────────
required=(DOMAIN DB_PASSWORD STRIPE_SECRET_KEY STRIPE_PUBLISHABLE_KEY STRIPE_WEBHOOK_SECRET MYSQL_ROOT_PASSWORD)
for var in "${required[@]}"; do
  val="${!var:-}"
  if [[ -z "$val" || "$val" == *CHANGE_ME* ]]; then
    echo "❌ $var is not set or still a placeholder in $ENV_FILE"
    exit 1
  fi
done

echo "✅ All variables loaded from $ENV_FILE"
echo "🌍 Domain: $DOMAIN"
echo "📦 Namespace: $NAMESPACE"
echo ""

# ── Helper: create or recreate secret ────────────────────────────────────────
apply_secret() {
  local name="$1"
  shift
  if kubectl get secret "$name" -n "$NAMESPACE" &>/dev/null; then
    if [[ "$RECREATE" == "true" ]]; then
      echo "🔄 Recreating secret: $name"
      kubectl delete secret "$name" -n "$NAMESPACE"
    else
      echo "⏭️  Secret already exists (skipping): $name  — use RECREATE=true to overwrite"
      return
    fi
  fi
  kubectl create secret generic "$name" --namespace "$NAMESPACE" "$@"
  echo "✅ Created: $name"
}

# ── Generate app secret key ───────────────────────────────────────────────────
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL="postgresql://ca_saas:${DB_PASSWORD}@ca-saas-db.ca-system.svc.cluster.local:5432/ca_saas"

# ── Create secrets ────────────────────────────────────────────────────────────
echo "--- Creating secrets in namespace: $NAMESPACE ---"

apply_secret saas-backend-secrets \
  --from-literal=database-url="$DATABASE_URL" \
  --from-literal=stripe-secret-key="$STRIPE_SECRET_KEY" \
  --from-literal=stripe-webhook-secret="$STRIPE_WEBHOOK_SECRET" \
  --from-literal=db-password="$DB_PASSWORD" \
  --from-literal=secret-key="$SECRET_KEY"

apply_secret ca-saas-db-secret \
  --from-literal=POSTGRES_PASSWORD="$DB_PASSWORD"

apply_secret customer-portal-secret \
  --from-literal=stripe-publishable-key="$STRIPE_PUBLISHABLE_KEY"

apply_secret mysql-root-password \
  --from-literal=mysql-root-password="$MYSQL_ROOT_PASSWORD"

# ── Cloudflare API token (cert-manager namespace, for DNS-01 challenge) ───────
echo "--- Creating Cloudflare token secret in namespace: cert-manager ---"
if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  if kubectl get secret cloudflare-api-token -n cert-manager &>/dev/null; then
    if [[ "$RECREATE" == "true" ]]; then
      echo "🔄 Recreating secret: cloudflare-api-token"
      kubectl delete secret cloudflare-api-token -n cert-manager
    else
      echo "⏭️  Secret already exists (skipping): cloudflare-api-token  — use RECREATE=true to overwrite"
    fi
  fi
  if ! kubectl get secret cloudflare-api-token -n cert-manager &>/dev/null; then
    kubectl create secret generic cloudflare-api-token \
      --from-literal=api-token="$CLOUDFLARE_API_TOKEN" \
      -n cert-manager
    echo "✅ Created: cloudflare-api-token (cert-manager)"
  fi
else
  echo "⚠️  CLOUDFLARE_API_TOKEN not set — skipping cloudflare-api-token secret."
  echo "   Set it in $ENV_FILE if you want Cloudflare proxy / DNS-01 TLS."
fi

echo ""
echo "🎉 All secrets created successfully!"
echo ""
echo "Next: update manifests for domain $DOMAIN then run deploy-nebius.sh"
