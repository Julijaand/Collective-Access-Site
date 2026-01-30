"""
Collective Access SaaS Backend - Pydantic Schemas
Phase 3: Request/response validation schemas
"""
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from .models import TenantStatus


# ============================================================================
# Tenant Schemas
# ============================================================================

class TenantBase(BaseModel):
    """Base tenant schema"""
    domain: str
    plan: str


class TenantCreate(TenantBase):
    """Schema for creating a new tenant"""
    user_id: int
    stripe_subscription_id: str


class TenantResponse(TenantBase):
    """Schema for tenant API responses"""
    id: int
    namespace: str
    status: TenantStatus
    ca_admin_username: str
    ca_admin_password: Optional[str]
    created_at: datetime
    deployed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    """Schema for listing tenants"""
    tenants: list[TenantResponse]
    total: int


# ============================================================================
# User Schemas
# ============================================================================

class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str


class UserResponse(UserBase):
    """Schema for user API responses"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Subscription Schemas
# ============================================================================

class SubscriptionResponse(BaseModel):
    """Schema for subscription API responses"""
    id: int
    tenant_id: int
    stripe_subscription_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Provisioning Schemas
# ============================================================================

class ProvisioningRequest(BaseModel):
    """Schema for tenant provisioning request"""
    user_id: int
    email: EmailStr
    plan: str
    stripe_subscription_id: str
    stripe_customer_id: str


class ProvisioningResponse(BaseModel):
    """Schema for provisioning operation response"""
    tenant_id: int
    namespace: str
    domain: str
    status: str
    message: str


# ============================================================================
# Webhook Schemas
# ============================================================================

class StripeWebhookEvent(BaseModel):
    """Schema for Stripe webhook events"""
    type: str
    data: dict


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Schema for health check endpoint"""
    status: str
    version: str
    database: str
    kubernetes: str
