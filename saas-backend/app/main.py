"""
Collective Access SaaS Backend - Main Application
Phase 3: FastAPI application with tenant provisioning endpoints
"""
import logging
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from .config import settings
from .database import get_db, init_db
from .models import Tenant, User, TenantStatus
from .schemas import (
    TenantResponse,
    TenantListResponse,
    ProvisioningRequest,
    ProvisioningResponse,
    HealthCheckResponse
)
from .provisioning import TenantProvisioner
from .stripe_webhooks import StripeWebhookHandler
from .k8s import KubernetesManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Automated Collective Access SaaS Platform"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database and connections on startup"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down gracefully")


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/", response_model=HealthCheckResponse)
async def root():
    """Root endpoint - health check"""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "database": "connected",
        "kubernetes": "connected"
    }


@app.get("/health", response_model=HealthCheckResponse)
async def health_check(db: Session = Depends(get_db)):
    """Detailed health check endpoint"""
    try:
        # Test database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "error"
    
    try:
        # Test Kubernetes connection
        k8s = KubernetesManager()
        k8s.core_v1.list_namespace(limit=1)
        k8s_status = "connected"
    except Exception as e:
        logger.error(f"Kubernetes health check failed: {e}")
        k8s_status = "error"
    
    return {
        "status": "ok" if db_status == "connected" and k8s_status == "connected" else "degraded",
        "version": settings.APP_VERSION,
        "database": db_status,
        "kubernetes": k8s_status
    }


# ============================================================================
# Tenant Management Endpoints
# ============================================================================

@app.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all tenants"""
    tenants = db.query(Tenant).offset(skip).limit(limit).all()
    total = db.query(Tenant).count()
    
    return {
        "tenants": tenants,
        "total": total
    }


@app.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: int, db: Session = Depends(get_db)):
    """Get tenant details by ID"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return tenant


@app.get("/tenants/namespace/{namespace}", response_model=TenantResponse)
async def get_tenant_by_namespace(namespace: str, db: Session = Depends(get_db)):
    """Get tenant details by namespace"""
    tenant = db.query(Tenant).filter(Tenant.namespace == namespace).first()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return tenant


@app.post("/tenants/provision", response_model=ProvisioningResponse)
async def provision_tenant(
    request: ProvisioningRequest,
    db: Session = Depends(get_db)
):
    """
    Manually provision a new tenant (for testing/admin)
    In production, this is triggered by Stripe webhooks
    """
    provisioner = TenantProvisioner(db)
    
    tenant, error = provisioner.provision_tenant(
        user_id=request.user_id,
        email=request.email,
        plan=request.plan,
        stripe_subscription_id=request.stripe_subscription_id,
        stripe_customer_id=request.stripe_customer_id
    )
    
    if error:
        return {
            "tenant_id": tenant.id if tenant else None,
            "namespace": tenant.namespace if tenant else None,
            "domain": tenant.domain if tenant else None,
            "status": "failed",
            "message": error
        }
    
    return {
        "tenant_id": tenant.id,
        "namespace": tenant.namespace,
        "domain": tenant.domain,
        "status": tenant.status,
        "message": f"Tenant provisioned successfully. Access at https://{tenant.domain}"
    }


@app.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: int, db: Session = Depends(get_db)):
    """Delete a tenant"""
    provisioner = TenantProvisioner(db)
    
    if not provisioner.delete_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found or deletion failed")
    
    return {"status": "success", "message": f"Tenant {tenant_id} deleted"}


# ============================================================================
# Stripe Webhook Endpoint
# ============================================================================

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook endpoint
    Handles payment events and triggers tenant provisioning
    """
    handler = StripeWebhookHandler(db)
    return await handler.handle_webhook(request)


# ============================================================================
# Admin/Debug Endpoints
# ============================================================================

@app.get("/admin/tenants/{tenant_id}/status")
async def get_tenant_status(tenant_id: int, db: Session = Depends(get_db)):
    """Get detailed tenant status including Kubernetes pod info"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    k8s = KubernetesManager()
    pod_status = k8s.get_pod_status(tenant.namespace)
    
    return {
        "tenant_id": tenant.id,
        "namespace": tenant.namespace,
        "domain": tenant.domain,
        "status": tenant.status,
        "deployed_at": tenant.deployed_at,
        "kubernetes": {
            "namespace_exists": k8s.namespace_exists(tenant.namespace),
            "pods": pod_status
        }
    }


@app.post("/admin/tenants/{tenant_id}/suspend")
async def suspend_tenant(tenant_id: int, db: Session = Depends(get_db)):
    """Suspend a tenant (admin action)"""
    provisioner = TenantProvisioner(db)
    
    if not provisioner.suspend_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {"status": "success", "message": f"Tenant {tenant_id} suspended"}


@app.post("/admin/tenants/{tenant_id}/resume")
async def resume_tenant(tenant_id: int, db: Session = Depends(get_db)):
    """Resume a suspended tenant (admin action)"""
    provisioner = TenantProvisioner(db)
    
    if not provisioner.resume_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {"status": "success", "message": f"Tenant {tenant_id} resumed"}


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
