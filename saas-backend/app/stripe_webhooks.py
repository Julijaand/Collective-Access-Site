"""
Collective Access SaaS Backend - Stripe Webhook Handler
Phase 3: Payment event processing and tenant lifecycle management
"""
import logging
import stripe
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session
from .config import settings
from .provisioning import TenantProvisioner
from .models import Tenant, Subscription

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeWebhookHandler:
    """Handles Stripe webhook events"""
    
    def __init__(self, db: Session):
        self.db = db
        self.provisioner = TenantProvisioner(db)
    
    async def handle_webhook(self, request: Request) -> dict:
        """
        Process incoming Stripe webhooks
        
        Args:
            request: FastAPI Request object
            
        Returns:
            dict: Response message
        """
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.error("Invalid payload")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid signature")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        event_type = event["type"]
        event_id = event["id"]
        
        logger.info(f"Received Stripe event: {event_type} ({event_id})")
        
        # Route to appropriate handler
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_failed": self._handle_payment_failed,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
        }
        
        handler = handlers.get(event_type)
        if handler:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error handling {event_type}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        else:
            logger.info(f"Unhandled event type: {event_type}")
        
        return {"status": "success"}
    
    def _handle_checkout_completed(self, event: dict):
        """
        Handle successful checkout - provision new tenant
        
        Event triggered when: User completes subscription purchase
        Action: Create and deploy new CA tenant
        """
        session = event["data"]["object"]
        
        # Extract relevant data
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        
        # Get subscription details from Stripe
        subscription = stripe.Subscription.retrieve(subscription_id)
        plan_id = subscription["items"]["data"][0]["price"]["id"]
        
        # Map Stripe price ID to plan name (you'll need to set these in Stripe)
        plan_mapping = {
            # Update these with your actual Stripe price IDs
            "price_1SrGI3PcAaj5IlzyqjJ9kioz": "starter",
            "price_1SrGJJPcAaj5Ilzy0KOKspNI": "pro",
            "price_1SrGJsPcAaj5IlzyBbgP2Ys4": "museum"
        }
        
        plan = plan_mapping.get(plan_id, "starter")
        
        # Get or create user (simplified - you'll want proper user management)
        from .models import User
        user = self.db.query(User).filter(User.email == customer_email).first()
        if not user:
            user = User(email=customer_email, password_hash="set_via_oauth_or_registration")
            self.db.add(user)
            self.db.commit()
        
        # Provision tenant
        logger.info(f"Provisioning tenant for {customer_email} (plan: {plan})")
        
        tenant, error = self.provisioner.provision_tenant(
            user_id=user.id,
            email=customer_email,
            plan=plan,
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id,
            stripe_event_id=event["id"]
        )
        
        if error:
            logger.error(f"Provisioning failed: {error}")
            # In production, send notification email to support
        else:
            logger.info(f"Successfully provisioned tenant: {tenant.namespace}")
            # In production, send welcome email to customer
    
    def _handle_subscription_updated(self, event: dict):
        """
        Handle subscription changes
        
        Event triggered when: Subscription status changes (upgrade, downgrade, etc.)
        Action: Update tenant status or resources
        """
        subscription_data = event["data"]["object"]
        subscription_id = subscription_data["id"]
        status = subscription_data["status"]
        
        # Find subscription in database
        subscription = self.db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()
        
        if not subscription:
            logger.warning(f"Subscription {subscription_id} not found in database")
            return
        
        # Update subscription status
        subscription.status = status
        self.db.commit()
        
        # Handle status changes
        if status == "past_due" or status == "unpaid":
            logger.info(f"Suspending tenant for subscription {subscription_id}")
            self.provisioner.suspend_tenant(subscription.tenant_id)
        elif status == "active":
            logger.info(f"Resuming tenant for subscription {subscription_id}")
            self.provisioner.resume_tenant(subscription.tenant_id)
        
        logger.info(f"Updated subscription {subscription_id} to status: {status}")
    
    def _handle_subscription_deleted(self, event: dict):
        """
        Handle subscription cancellation
        
        Event triggered when: User cancels subscription
        Action: Mark tenant for deletion (with grace period)
        """
        subscription_data = event["data"]["object"]
        subscription_id = subscription_data["id"]
        
        subscription = self.db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()
        
        if not subscription:
            logger.warning(f"Subscription {subscription_id} not found")
            return
        
        # Suspend tenant (don't delete immediately - give grace period)
        logger.info(f"Subscription {subscription_id} canceled, suspending tenant")
        self.provisioner.suspend_tenant(subscription.tenant_id)
        
        # Update subscription status
        subscription.status = "canceled"
        self.db.commit()
        
        # In production: Schedule deletion after 30 days grace period
    
    def _handle_payment_failed(self, event: dict):
        """
        Handle failed payment
        
        Event triggered when: Payment attempt fails
        Action: Notify user, suspend if multiple failures
        """
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")
        
        if not subscription_id:
            return
        
        subscription = self.db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()
        
        if subscription:
            logger.warning(f"Payment failed for subscription {subscription_id}")
            # In production: Send notification email to customer
    
    def _handle_payment_succeeded(self, event: dict):
        """
        Handle successful payment
        
        Event triggered when: Payment succeeds (renewal, etc.)
        Action: Ensure tenant is active
        """
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")
        
        if not subscription_id:
            return
        
        subscription = self.db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()
        
        if subscription and subscription.tenant.status != "active":
            logger.info(f"Payment succeeded, resuming tenant for {subscription_id}")
            self.provisioner.resume_tenant(subscription.tenant_id)
