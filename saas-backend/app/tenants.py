"""
Tenant management endpoints — authenticated, user-scoped.

GET    /api/tenants           → list tenants belonging to the logged-in user
GET    /api/tenants/{id}      → get one tenant (must belong to user)
DELETE /api/tenants/{id}      → delete tenant (Helm + K8s + DB cleanup)
GET    /api/tenants/{id}/metrics → live pod status from Kubernetes
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from .auth import get_current_user
from .database import get_db
from .models import Tenant, TenantStatus, User, Subscription
from .provisioning import TenantProvisioner
from .k8s import KubernetesManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


# ---------------------------------------------------------------------------
# Response schemas (local — keeps this file self-contained)
# ---------------------------------------------------------------------------

class TenantOut(BaseModel):
    id: int
    name: str
    namespace: str
    domain: str
    plan: str
    status: TenantStatus
    ca_admin_username: Optional[str] = None
    ca_admin_password: Optional[str] = None
    created_at: datetime
    deployed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantListOut(BaseModel):
    tenants: list[TenantOut]
    total: int


# ---------------------------------------------------------------------------
# Helper: ownership check
# ---------------------------------------------------------------------------

def get_owned_tenant(tenant_id: int, user: User, db: Session) -> Tenant:
    """Return tenant if it belongs to the current user, else 404."""
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.user_id == user.id
    ).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=TenantListOut)
def list_tenants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all tenants belonging to the logged-in user with active subscriptions."""
    tenants = (
        db.query(Tenant)
        .filter(Tenant.user_id == current_user.id)
        .join(Subscription, Subscription.tenant_id == Tenant.id)
        .filter(Subscription.status != "canceled")
        .order_by(Tenant.created_at.desc())
        .all()
    )
    return {"tenants": tenants, "total": len(tenants)}


@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a single tenant owned by the logged-in user."""
    return get_owned_tenant(tenant_id, current_user, db)


@router.delete("/{tenant_id}")
def delete_tenant(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a tenant:
    1. Verify ownership
    2. Helm uninstall + delete K8s namespace
    3. Remove DB record
    """
    tenant = get_owned_tenant(tenant_id, current_user, db)

    provisioner = TenantProvisioner(db)
    success = provisioner.delete_tenant(tenant_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete tenant resources")

    return {"status": "deleted", "tenant_id": tenant_id, "namespace": tenant.namespace}


@router.get("/{tenant_id}/metrics")
def get_tenant_metrics(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return live Kubernetes pod status for a tenant.
    No metrics-server required — uses pod phase only.
    """
    tenant = get_owned_tenant(tenant_id, current_user, db)

    try:
        k8s = KubernetesManager()
        pod_status = k8s.get_pod_status(tenant.namespace)
    except Exception as e:
        logger.error(f"K8s metrics failed for tenant {tenant_id}: {e}")
        pod_status = {"total": 0, "running": 0, "pending": 0, "failed": 0}

    running = pod_status.get("running", 0)
    total = pod_status.get("total", 0)

    if total == 0:
        health = "down"
    elif running == total:
        health = "healthy"
    else:
        health = "degraded"

    return {
        "tenant_id": tenant.id,
        "namespace": tenant.namespace,
        "health_status": health,
        "pods_total": total,
        "pods_running": running,
        "pods_pending": pod_status.get("pending", 0),
        "pods_failed": pod_status.get("failed", 0),
    }
