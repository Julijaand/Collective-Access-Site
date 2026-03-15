"""
Collective Access SaaS Backend — Billing Router
Endpoints: Stripe Checkout, Portal, Invoices, Subscriptions
"""
import logging
import stripe
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import Subscription, Tenant, User
from .config import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(tags=["billing"])

# ---------------------------------------------------------------------------
# Stripe Price ID ↔ Plan mapping  (keep in sync with stripe_webhooks.py)
# ---------------------------------------------------------------------------
PRICE_TO_PLAN: dict[str, str] = {
    "price_1SrGI3PcAaj5IlzyqjJ9kioz": "starter",
    "price_1SrGJJPcAaj5Ilzy0KOKspNI": "pro",
    "price_1SrGJsPcAaj5IlzyBbgP2Ys4": "museum",
}
PLAN_TO_PRICE: dict[str, str] = {v: k for k, v in PRICE_TO_PLAN.items()}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    plan: str
    tenant_name: str
    success_url: str
    cancel_url: str


class SubscriptionOut(BaseModel):
    id: str                       # Stripe subscription ID used as API-visible id
    tenant_id: int
    plan: str
    status: str
    current_period_start: str     # ISO datetime string
    current_period_end: str
    cancel_at_period_end: bool
    stripe_subscription_id: str


class InvoiceOut(BaseModel):
    id: str
    amount_paid: int              # cents
    currency: str
    created: str                  # ISO datetime string
    status: str
    invoice_pdf: Optional[str] = None
    hosted_invoice_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: get first subscription-bearing tenant for a user
# ---------------------------------------------------------------------------

def _customer_id_for_user(user: User, db: Session) -> Optional[str]:
    """Return the Stripe customer_id from the user's first active subscription."""
    tenant = (
        db.query(Tenant)
        .filter(Tenant.user_id == user.id)
        .join(Subscription, Subscription.tenant_id == Tenant.id)
        .first()
    )
    return tenant.subscription.stripe_customer_id if tenant and tenant.subscription else None


# ---------------------------------------------------------------------------
# GET /api/subscriptions — list caller's subscriptions
# ---------------------------------------------------------------------------

@router.get("/api/subscriptions")
async def get_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all subscriptions that belong to the current user."""
    tenants = (
        db.query(Tenant)
        .filter(Tenant.user_id == current_user.id)
        .all()
    )

    result = []
    for tenant in tenants:
        sub = tenant.subscription
        if not sub:
            continue

        # Refresh from Stripe for live status
        try:
            stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
            status = stripe_sub["status"]
            period_start = datetime.fromtimestamp(stripe_sub["current_period_start"]).isoformat()
            period_end = datetime.fromtimestamp(stripe_sub["current_period_end"]).isoformat()
            cancel_at_period_end = stripe_sub["cancel_at_period_end"]
        except Exception as e:
            logger.warning(f"Stripe fetch failed for {sub.stripe_subscription_id}: {e}")
            status = sub.status
            period_start = sub.current_period_start.isoformat() if sub.current_period_start else ""
            period_end = sub.current_period_end.isoformat() if sub.current_period_end else ""
            cancel_at_period_end = False

        result.append({
            "id": sub.stripe_subscription_id,
            "tenant_id": tenant.id,
            "plan": tenant.plan,
            "status": status,
            "current_period_start": period_start,
            "current_period_end": period_end,
            "cancel_at_period_end": cancel_at_period_end,
            "stripe_subscription_id": sub.stripe_subscription_id,
        })

    return {"subscriptions": result}


# ---------------------------------------------------------------------------
# PATCH /api/subscriptions/{subscription_id} — upgrade / switch plan
# ---------------------------------------------------------------------------

@router.patch("/api/subscriptions/{subscription_id}")
async def upgrade_plan(
    subscription_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upgrade or switch a subscription to a different plan."""
    plan = body.get("plan")
    if not plan:
        raise HTTPException(status_code=400, detail="plan is required")

    price_id = PLAN_TO_PRICE.get(plan)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan}")

    # Verify ownership
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()
    if not sub or sub.tenant.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    try:
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        item_id = stripe_sub["items"]["data"][0]["id"]
        stripe.Subscription.modify(
            subscription_id,
            items=[{"id": item_id, "price": price_id}],
            proration_behavior="create_prorations",
        )
        # Persist plan change locally
        sub.tenant.plan = plan
        sub.stripe_price_id = price_id
        db.commit()
        return {"status": "success", "plan": plan}
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# POST /billing/checkout — create Stripe Checkout Session
# ---------------------------------------------------------------------------

@router.post("/billing/checkout")
async def create_checkout(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout Session for a new subscription."""
    price_id = PLAN_TO_PRICE.get(body.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=current_user.email,
            metadata={
                "user_id": str(current_user.id),
                "tenant_name": body.tenant_name,
                "plan": body.plan,
            },
            subscription_data={
                "metadata": {
                    "user_id": str(current_user.id),
                    "tenant_name": body.tenant_name,
                    "plan": body.plan,
                }
            },
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
        return {"url": session.url}
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# POST /billing/portal — create Stripe Customer Portal session
# ---------------------------------------------------------------------------

@router.post("/billing/portal")
async def create_portal(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Customer Portal session so the user can manage their billing."""
    customer_id = _customer_id_for_user(current_user, db)
    if not customer_id:
        raise HTTPException(status_code=404, detail="No billing account found — purchase a plan first.")

    app_url = settings.APP_URL.rstrip("/") if settings.APP_URL else "https://portal.192.168.49.2.nip.io"

    try:
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{app_url}/billing",
        )
        return {"url": portal.url}
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# GET /billing/invoices — list Stripe invoices for the current user
# ---------------------------------------------------------------------------

@router.get("/billing/invoices")
async def get_invoices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the last 24 invoices for the current user from Stripe."""
    customer_id = _customer_id_for_user(current_user, db)
    if not customer_id:
        return {"invoices": []}

    try:
        invoices = stripe.Invoice.list(customer=customer_id, limit=24)
        result = []
        for inv in invoices["data"]:
            result.append({
                "id": inv["id"],
                "amount_paid": inv.get("amount_paid", 0),
                "currency": inv.get("currency", "eur"),
                "created": datetime.fromtimestamp(inv["created"]).isoformat(),
                "status": inv.get("status", "unknown"),
                "invoice_pdf": inv.get("invoice_pdf"),
                "hosted_invoice_url": inv.get("hosted_invoice_url"),
            })
        return {"invoices": result}
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
