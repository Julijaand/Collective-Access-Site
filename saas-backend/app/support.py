"""
Support ticket endpoints — authenticated, user-scoped.

GET    /api/tickets                    → list user's tickets
POST   /api/tickets                    → create a ticket
GET    /api/tickets/{id}               → get one ticket
PATCH  /api/tickets/{id}               → update status (close)
GET    /api/tickets/{id}/messages      → list messages
POST   /api/tickets/{id}/messages      → add a message
"""
import logging
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import SupportTicket, TicketMessage, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickets", tags=["support"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TicketOut(BaseModel):
    id: int
    tenant_id: Optional[int] = None
    subject: str
    status: str
    priority: str
    category: str
    created_at: datetime
    updated_at: datetime
    messages_count: int = 0

    model_config = {"from_attributes": True}


class TicketMessageOut(BaseModel):
    id: int
    ticket_id: int
    author_name: str
    author_role: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateTicketRequest(BaseModel):
    tenant_id: Optional[int] = None
    subject: str
    description: str
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    category: str = "general"


class UpdateTicketRequest(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"]


class AddMessageRequest(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ticket(ticket_id: int, user: User, db: Session) -> SupportTicket:
    ticket = db.query(SupportTicket).filter(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == user.id,
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _to_out(ticket: SupportTicket) -> TicketOut:
    return TicketOut(
        id=ticket.id,
        tenant_id=ticket.tenant_id,
        subject=ticket.subject,
        status=ticket.status,
        priority=ticket.priority,
        category=ticket.category,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        messages_count=len(ticket.messages),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tickets = (
        db.query(SupportTicket)
        .filter(SupportTicket.user_id == current_user.id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )
    return [_to_out(t) for t in tickets]


@router.post("", status_code=201)
def create_ticket(
    body: CreateTicketRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = SupportTicket(
        user_id=current_user.id,
        tenant_id=body.tenant_id,
        subject=body.subject,
        priority=body.priority,
        category=body.category,
        status="open",
    )
    db.add(ticket)
    db.flush()  # get ticket.id

    # First message = the description
    first_msg = TicketMessage(
        ticket_id=ticket.id,
        user_id=current_user.id,
        author_name=current_user.email.split("@")[0],
        author_role="user",
        message=body.description,
    )
    db.add(first_msg)
    db.commit()
    db.refresh(ticket)
    logger.info("Created ticket %d for user %d", ticket.id, current_user.id)
    return _to_out(ticket)


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _to_out(_get_ticket(ticket_id, current_user, db))


@router.patch("/{ticket_id}", status_code=200)
def update_ticket(
    ticket_id: int,
    body: UpdateTicketRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_ticket(ticket_id, current_user, db)
    ticket.status = body.status
    db.commit()
    return {"message": "Ticket updated"}


@router.get("/{ticket_id}/messages", response_model=List[TicketMessageOut])
def list_messages(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_ticket(ticket_id, current_user, db)
    return ticket.messages


@router.post("/{ticket_id}/messages", status_code=201, response_model=TicketMessageOut)
def add_message(
    ticket_id: int,
    body: AddMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_ticket(ticket_id, current_user, db)
    if ticket.status == "closed":
        raise HTTPException(status_code=400, detail="Cannot reply to a closed ticket")

    msg = TicketMessage(
        ticket_id=ticket.id,
        user_id=current_user.id,
        author_name=current_user.email.split("@")[0],
        author_role="user",
        message=body.message,
    )
    db.add(msg)
    # Reopen if resolved
    if ticket.status == "resolved":
        ticket.status = "open"
    db.commit()
    db.refresh(msg)
    return msg
