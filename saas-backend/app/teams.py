"""
Team management endpoints — authenticated, tenant-scoped.

GET    /api/teams/{tenant_id}/members       → list members
POST   /api/teams/{tenant_id}/invite        → invite a member by email + role
PATCH  /api/teams/{tenant_id}/members/{id}  → change a member's role
DELETE /api/teams/{tenant_id}/members/{id}  → remove a member
"""
import logging
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import TeamMember, Tenant, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TeamMemberOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    status: str
    invited_at: datetime
    joined_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InviteRequest(BaseModel):
    email: str
    role: Literal["admin", "editor", "viewer"]


class UpdateRoleRequest(BaseModel):
    role: Literal["admin", "editor", "viewer"]


# ---------------------------------------------------------------------------
# Helper: verify tenant belongs to current user
# ---------------------------------------------------------------------------

def _get_tenant_for_user(tenant_id: int, user: User, db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.user_id == user.id,
    ).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _seed_owner(tenant: Tenant, user: User, db: Session) -> None:
    """Auto-create the owner record if no team members exist yet."""
    existing = db.query(TeamMember).filter(TeamMember.tenant_id == tenant.id).first()
    if not existing:
        owner = TeamMember(
            tenant_id=tenant.id,
            user_id=user.id,
            email=user.email,
            name=user.email.split("@")[0],
            role="owner",
            status="active",
            invited_at=tenant.created_at,
            joined_at=tenant.created_at,
        )
        db.add(owner)
        db.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{tenant_id}/members", response_model=List[TeamMemberOut])
def list_members(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant = _get_tenant_for_user(tenant_id, current_user, db)
    _seed_owner(tenant, current_user, db)
    return db.query(TeamMember).filter(TeamMember.tenant_id == tenant_id).all()


@router.post("/{tenant_id}/invite", status_code=201)
def invite_member(
    tenant_id: int,
    body: InviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_tenant_for_user(tenant_id, current_user, db)

    # Don't allow duplicate email
    already = db.query(TeamMember).filter(
        TeamMember.tenant_id == tenant_id,
        TeamMember.email == body.email,
    ).first()
    if already:
        raise HTTPException(status_code=409, detail="This email is already a team member")

    # If the user already has an account, mark them active immediately
    invited_user = db.query(User).filter(User.email == body.email).first()
    now = datetime.utcnow()

    member = TeamMember(
        tenant_id=tenant_id,
        user_id=invited_user.id if invited_user else None,
        email=body.email,
        name=invited_user.email.split("@")[0] if invited_user else body.email.split("@")[0],
        role=body.role,
        status="active" if invited_user else "pending",
        invited_at=now,
        joined_at=now if invited_user else None,
    )
    db.add(member)
    db.commit()
    logger.info("Invited %s to tenant %d as %s", body.email, tenant_id, body.role)
    return {"message": "Invitation sent"}


@router.patch("/{tenant_id}/members/{member_id}", status_code=200)
def update_member_role(
    tenant_id: int,
    member_id: int,
    body: UpdateRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_tenant_for_user(tenant_id, current_user, db)

    member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.tenant_id == tenant_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot change the owner's role")

    member.role = body.role
    db.commit()
    return {"message": "Role updated"}


@router.delete("/{tenant_id}/members/{member_id}", status_code=200)
def remove_member(
    tenant_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_tenant_for_user(tenant_id, current_user, db)

    member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.tenant_id == tenant_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove the owner")

    db.delete(member)
    db.commit()
    logger.info("Removed member %d from tenant %d", member_id, tenant_id)
    return {"message": "Member removed"}
