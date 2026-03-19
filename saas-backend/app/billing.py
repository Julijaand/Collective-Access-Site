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
    """Return the Stripe customer_id from the user's active subscription."""
    tenant = (
        db.query(Tenant)
        .filter(Tenant.user_id == user.id)
        .join(Subscription, Subscription.tenant_id == Tenant.id)
        .filter(Subscription.status != "canceled")
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
        if not sub or sub.status == "canceled":
            continue

        # Refresh from Stripe for live status + plan (syncs upgrades done via portal)
        try:
            stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
            status = stripe_sub["status"]
            period_start = datetime.fromtimestamp(stripe_sub["current_period_start"]).isoformat()
            period_end = datetime.fromtimestamp(stripe_sub["current_period_end"]).isoformat()
            cancel_at_period_end = stripe_sub["cancel_at_period_end"]
            # Sync plan from Stripe price — catches upgrades done via Customer Portal
            live_price_id = stripe_sub["items"]["data"][0]["price"]["id"]
            live_plan = PRICE_TO_PLAN.get(live_price_id, tenant.plan)
            if live_plan != tenant.plan:
                logger.info(f"Syncing plan for tenant {tenant.namespace}: {tenant.plan} → {live_plan}")
                tenant.plan = live_plan
                sub.stripe_price_id = live_price_id
                db.commit()
        except Exception as e:
            logger.warning(f"Stripe fetch failed for {sub.stripe_subscription_id}: {e}")
            status = sub.status
            period_start = sub.current_period_start.isoformat() if sub.current_period_start else ""
            period_end = sub.current_period_end.isoformat() if sub.current_period_end else ""
            cancel_at_period_end = False
            live_plan = tenant.plan

        result.append({
            "id": sub.stripe_subscription_id,
            "tenant_id": tenant.id,
            "plan": live_plan,
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
            # Append Stripe's session ID so the portal can confirm provisioning
            # even when webhooks can't reach a local cluster
            success_url=body.success_url + ("&" if "?" in body.success_url else "?") + "session_id={CHECKOUT_SESSION_ID}",
            cancel_url=body.cancel_url,
        )
        return {"url": session.url}
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# POST /billing/checkout/confirm — called by portal after Stripe redirect
# Provisions the tenant if the session was paid and no tenant exists yet.
# This is the fallback for local/dev environments where Stripe webhooks
# cannot reach the cluster.
# ---------------------------------------------------------------------------

@router.post("/billing/checkout/confirm")
async def confirm_checkout(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if session.get("payment_status") != "paid":
        return {"status": "pending", "message": "Payment not completed yet"}

    subscription_id = session.get("subscription")
    if isinstance(subscription_id, dict):
        subscription_id = subscription_id["id"]
    customer_id = session.get("customer")
    metadata = session.get("metadata") or {}
    plan = metadata.get("plan", "starter")

    # Idempotency: check if tenant already exists for this subscription
    existing = db.query(Tenant).join(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()
    if existing:
        return {"status": "already_provisioned", "tenant_id": existing.id, "namespace": existing.namespace}

    # Provision
    from .provisioning import TenantProvisioner
    provisioner = TenantProvisioner(db)
    tenant, error = provisioner.provision_tenant(
        user_id=current_user.id,
        email=current_user.email,
        plan=plan,
        stripe_subscription_id=subscription_id,
        stripe_customer_id=customer_id,
        stripe_event_id=f"confirm_{session_id}",
    )

    if error or not tenant:
        raise HTTPException(status_code=500, detail=error or "Provisioning failed")

    logger.info(f"Confirmed and provisioned tenant {tenant.namespace} for session {session_id}")
    return {"status": "provisioned", "tenant_id": tenant.id, "namespace": tenant.namespace}




class PortalRequest(BaseModel):
    model_config = {"populate_by_name": True}
    plan: Optional[str] = None
    subscription_id: Optional[str] = None
    subscriptionId: Optional[str] = None

    def get_subscription_id(self) -> Optional[str]:
        return self.subscription_id or self.subscriptionId


@router.post("/billing/portal")
async def create_portal(
    body: PortalRequest = PortalRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Customer Portal session so the user can manage their billing.

    If subscription_id is provided, opens the portal directly on the
    subscription_update flow using the customer from that subscription.
    """
    app_url = settings.APP_URL.rstrip("/") if settings.APP_URL else "https://portal.192.168.49.2.nip.io"

    # If upgrading, get customer_id directly from the subscription to avoid mismatch
    sub_id = body.get_subscription_id()
    if sub_id:
        try:
            stripe_sub = stripe.Subscription.retrieve(sub_id)
            customer_id = stripe_sub["customer"]
        except stripe.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        customer_id = _customer_id_for_user(current_user, db)

    if not customer_id:
        raise HTTPException(status_code=404, detail="No billing account found — purchase a plan first.")

    session_kwargs: dict = {
        "customer": customer_id,
        "return_url": f"{app_url}/billing",
    }

    if sub_id:
        session_kwargs["flow_data"] = {
            "type": "subscription_update",
            "after_completion": {
                "type": "redirect",
                "redirect": {"return_url": f"{app_url}/billing?success=1"},
            },
            "subscription_update": {
                "subscription": sub_id,
            },
        }

    try:
        portal = stripe.billing_portal.Session.create(**session_kwargs)
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
