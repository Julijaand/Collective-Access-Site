"""
Collective Access SaaS Backend - Database Models
Phase 3: Core data models for tenant and subscription management
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base


class TenantStatus(str, enum.Enum):
    """Tenant lifecycle states"""
    PENDING = "pending"           # Payment received, not yet deployed
    PROVISIONING = "provisioning" # Kubernetes deployment in progress
    ACTIVE = "active"             # Tenant is live and accessible
    FAILED = "failed"             # Deployment or configuration failed
    SUSPENDED = "suspended"       # Subscription unpaid or cancelled
    DELETED = "deleted"           # Tenant destroyed


class ProvisioningAction(str, enum.Enum):
    """Types of provisioning operations"""
    CREATE = "create"
    UPDATE = "update"
    SUSPEND = "suspend"
    RESUME = "resume"
    DELETE = "delete"


class User(Base):
    """SaaS platform users"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tenants = relationship("Tenant", back_populates="user")


class Tenant(Base):
    """Collective Access tenant instances"""
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Kubernetes identifiers
    namespace = Column(String, unique=True, nullable=False, index=True)
    helm_release_name = Column(String, nullable=False)
    
    # Domain and access
    domain = Column(String, unique=True, nullable=False)
    
    # Plan and status
    plan = Column(String, nullable=False)  # starter, pro, museum
    status = Column(Enum(TenantStatus), default=TenantStatus.PENDING)
    
    # Database credentials (stored securely in K8s secrets)
    db_name = Column(String, nullable=False)
    db_user = Column(String, nullable=False)
    db_password = Column(String, nullable=True)
    
    # Admin credentials (generated during installation)
    ca_admin_username = Column(String, default="administrator")
    ca_admin_password = Column(String)  # Store initial password, user should change
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deployed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="tenants")
    subscription = relationship("Subscription", back_populates="tenant", uselist=False)
    provisioning_logs = relationship("ProvisioningLog", back_populates="tenant")


class Subscription(Base):
    """Stripe subscription tracking"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True)
    
    # Stripe identifiers
    stripe_subscription_id = Column(String, unique=True, nullable=False, index=True)
    stripe_customer_id = Column(String, nullable=False, index=True)
    stripe_price_id = Column(String, nullable=False)
    
    # Status
    status = Column(String, nullable=False)  # active, past_due, canceled, etc.
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    canceled_at = Column(DateTime, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="subscription")


class ProvisioningLog(Base):
    """Audit trail for tenant provisioning operations"""
    __tablename__ = "provisioning_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    # Operation details
    action = Column(Enum(ProvisioningAction), nullable=False)
    status = Column(String, nullable=False)  # started, completed, failed
    message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)
    
    # Idempotency
    stripe_event_id = Column(String, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="provisioning_logs")
