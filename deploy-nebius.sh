#!/usr/bin/env bash
# deploy-nebius.sh — Deploy full stack to Nebius Kubernetes via Kustomize.
#
# Manifests stay in their original locations (saas-backend/k8s/, customer-portal/k8s/).
# Environment patches live in k8s/overlays/nebius/ — nothing else is modified.
#
# The standalone kustomize CLI is required (not kubectl -k) because our overlay
# references files outside its own directory tree. kustomize handles this with
# --load-restrictor LoadRestrictionsNone.
#
# Usage:
#   ./deploy-nebius.sh            # full deploy
#   ./deploy-nebius.sh --dry-run  # print rendered manifests, nothing applied

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
OVERLAY="$PROJECT_ROOT/k8s/overlays/nebius"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# ─── Ensure kustomize CLI is available ────────────────────────────────────────
if ! command -v kustomize &>/dev/null; then
  echo "📦 Installing kustomize..."
  brew install kustomize
fi

# ─── Preflight ────────────────────────────────────────────────────────────────
if ! kubectl cluster-info &>/dev/null; then
  echo "❌ kubectl cannot reach the cluster. Run:"
  echo "   source ~/.nebius/path.zsh.inc"
  echo "   nebius mk8s cluster get-credentials --id mk8scluster-e00j3jx577ajba60nm --external"
  exit 1
fi

echo "✅ Cluster reachable"
echo "📦 Overlay: k8s/overlays/nebius"
echo ""

# ─── Render helper (--load-restrictor lets base reference files outside k8s/) ─
render() {
  kustomize build --load-restrictor LoadRestrictionsNone "$OVERLAY"
}

# ─── Dry run ──────────────────────────────────────────────────────────────────
if $DRY_RUN; then
  echo "⚠️  DRY RUN — printing rendered manifests, nothing applied"
  echo ""
  render
  exit 0
fi

# ─── Namespace ────────────────────────────────────────────────────────────────
kubectl create namespace ca-system --dry-run=client -o yaml | kubectl apply -f -

# ─── Deploy ───────────────────────────────────────────────────────────────────
echo "🚀 Applying k8s/overlays/nebius/ ..."
render | kubectl apply -f -

# ─── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "🎉 Manifests applied!"
echo ""
echo "Watch pods:"
echo "  kubectl get pods -n ca-system -w"
echo ""

# Load DOMAIN from secrets.nebius.env if available
if [[ -f "$PROJECT_ROOT/secrets.nebius.env" ]]; then
  source "$PROJECT_ROOT/secrets.nebius.env"
fi
DOMAIN="${DOMAIN:-<LB-IP>.nip.io}"

echo "Health check (once pods are Running):"
echo "  curl https://api.portal.${DOMAIN}/health"
echo ""
echo "Register Stripe webhook:"
echo "  URL:    https://api.portal.${DOMAIN}/api/stripe/webhook"
echo "  Events: checkout.session.completed, customer.subscription.deleted, invoice.payment_failed"
