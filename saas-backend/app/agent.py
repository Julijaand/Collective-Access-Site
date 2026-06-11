"""
CA Agent Proxy — /api/agent/chat
Looks up the tenant's CA credentials from the database and forwards
the user's message to the ca_agent service, injecting credentials.

This keeps secrets server-side: the browser never sees CA passwords.
"""
import logging
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from .auth import get_current_user
from .database import get_db
from .models import Tenant, TenantStatus, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Internal cluster URL for the ca-agent service
CA_AGENT_URL = os.getenv(
    "CA_AGENT_URL", "http://ca-agent.ca-system.svc.cluster.local:8001"
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class AgentChatRequest(BaseModel):
    message: str
    tenant_id: Optional[int] = None   # If omitted, uses the user's first active tenant
    session_id: Optional[str] = None


class AgentChatResponse(BaseModel):
    reply: str
    session_id: str
    action_taken: Optional[str] = None
    records: Optional[list] = None
    timestamp: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    req: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Resolve tenant
    tenant = _resolve_tenant(db, current_user, req.tenant_id)

    # Build per-tenant CA credentials
    # Use internal cluster URL (namespace = tenant ID, service name = tenant ID)
    ns = tenant.namespace or tenant.id
    ca_url = f"http://{ns}.{ns}.svc.cluster.local"
    ca_username = tenant.ca_admin_username or "administrator"
    ca_password = tenant.ca_admin_password or ""

    if not ca_password:
        raise HTTPException(
            status_code=503,
            detail="CA credentials are not yet available for this tenant. "
                   "Please wait until the instance is fully provisioned.",
        )

    # Forward to ca_agent service
    payload = {
        "message": req.message,
        "session_id": req.session_id,
        "ca_url": ca_url,
        "ca_username": ca_username,
        "ca_password": ca_password,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CA_AGENT_URL}/chat",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            return AgentChatResponse(**resp.json())
    except httpx.TimeoutException:
        logger.error("ca_agent timeout for tenant %s", tenant.id)
        raise HTTPException(status_code=504, detail="CA agent timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        logger.error("ca_agent HTTP error: %s", e)
        raise HTTPException(status_code=502, detail="CA agent returned an error.")
    except Exception as e:
        logger.error("ca_agent unreachable: %s", e)
        raise HTTPException(
            status_code=503,
            detail="CA agent is currently unavailable.",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve_tenant(db: Session, user: User, tenant_id: Optional[int]) -> Tenant:
    """Return the requested tenant, or the user's first active tenant."""
    query = db.query(Tenant).filter(
        Tenant.user_id == user.id,
        Tenant.status == TenantStatus.ACTIVE,
    )
    if tenant_id:
        tenant = query.filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Active tenant {tenant_id} not found for this user.",
            )
        return tenant

    tenant = query.first()
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail="No active Collective Access instance found. "
                   "Please provision a tenant first.",
        )
    return tenant
