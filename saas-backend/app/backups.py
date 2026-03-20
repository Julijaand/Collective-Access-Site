"""
Backup endpoints — authenticated, tenant-scoped.

GET    /api/backups/{tenant_id}              → list backups for a tenant
POST   /api/backups/{tenant_id}             → trigger a manual backup
POST   /api/backups/{backup_id}/restore     → restore from a backup
"""
import logging
import random
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import Backup, Tenant, Subscription, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backups", tags=["backups"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BackupOut(BaseModel):
    id: int
    tenant_id: int
    type: str
    status: str
    size_mb: Optional[int] = None
    storage_location: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RestoreRequest(BaseModel):
    target_tenant_id: int
    confirm: bool


# ---------------------------------------------------------------------------
# Helper: verify tenant belongs to current user
# ---------------------------------------------------------------------------

def _get_tenant(tenant_id: int, user: User, db: Session) -> Tenant:
    tenant = (
        db.query(Tenant)
        .join(Subscription, Subscription.tenant_id == Tenant.id)
        .filter(
            Tenant.id == tenant_id,
            Tenant.user_id == user.id,
            Subscription.status != "canceled",
        )
        .first()
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{tenant_id}", response_model=List[BackupOut])
def list_backups(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_tenant(tenant_id, current_user, db)
    return (
        db.query(Backup)
        .filter(Backup.tenant_id == tenant_id)
        .order_by(Backup.created_at.desc())
        .all()
    )


@router.post("/{tenant_id}", status_code=201, response_model=BackupOut)
def create_backup(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant = _get_tenant(tenant_id, current_user, db)

    backup = Backup(
        tenant_id=tenant.id,
        type="manual",
        status="completed",                      # In prod: kick off async job
        size_mb=random.randint(150, 800),        # In prod: real size from K8s
        storage_location=f"backups/{tenant.namespace}/{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.tar.gz",
    )
    db.add(backup)
    db.commit()
    db.refresh(backup)
    logger.info("Manual backup created for tenant %d", tenant_id)
    return backup


@router.post("/{backup_id}/restore", status_code=200)
def restore_backup(
    backup_id: int,
    body: RestoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="You must confirm the restore operation")

    backup = db.query(Backup).filter(Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    # Verify the user owns the source tenant
    _get_tenant(backup.tenant_id, current_user, db)

    # In production: enqueue K8s restore job here
    logger.info(
        "Restore requested: backup %d → tenant %d by user %d",
        backup_id, body.target_tenant_id, current_user.id,
    )
    return {"message": "Restore initiated. This may take a few minutes."}
