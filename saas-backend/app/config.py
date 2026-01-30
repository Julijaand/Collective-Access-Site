"""
Collective Access SaaS Backend - Configuration
Phase 3: Centralized configuration management
"""
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    # MySQL root password for database creation
    MYSQL_ROOT_PASSWORD: str = Field(
        default="",
        description="MySQL root password for database creation"
    )
    # Application
    APP_NAME: str = "Collective Access SaaS Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database (required in production)
    DATABASE_URL: str = Field(
        default="postgresql://ca_saas:ca_saas_password@localhost:5432/ca_saas",
        description="PostgreSQL connection string for backend database"
    )
    
    # Stripe (required in production)
    STRIPE_SECRET_KEY: str = Field(
        default="",
        description="Stripe secret key for API calls"
    )
    STRIPE_WEBHOOK_SECRET: str = Field(
        default="",
        description="Stripe webhook signing secret"
    )
    STRIPE_PUBLISHABLE_KEY: str = Field(
        default="",
        description="Stripe publishable key for frontend"
    )
    
    # Kubernetes
    KUBERNETES_IN_CLUSTER: bool = Field(
        default=False,
        description="Whether running inside Kubernetes cluster"
    )
    KUBERNETES_NAMESPACE_PREFIX: str = Field(
        default="tenant",
        description="Prefix for tenant namespaces"
    )
    HELM_CHART_PATH: str = Field(
        default="/app/k8s/helm/collectiveaccess",
        description="Path to Helm chart for tenant deployment"
    )
    
    # Domain & DNS
    BASE_DOMAIN: str = Field(
        default="yoursaas.com",
        description="Base domain for tenant subdomains"
    )
    
    # Shared MySQL Configuration (for CA databases)
    DB_HOST: str = Field(
        default="mysql.ca-system.svc.cluster.local",
        description="MySQL host for Collective Access databases"
    )
    DB_PORT: int = Field(
        default=3306,
        description="MySQL port"
    )
    DB_USER: str = Field(
        default="ca",
        description="MySQL user with database creation privileges"
    )
    DB_PASSWORD: str = Field(
        default="",
        description="MySQL password (required in production)"
    )
    
    # Collective Access Defaults
    CA_ADMIN_EMAIL: str = Field(
        default="admin@yoursaas.com",
        description="Default admin email for CA instances"
    )
    CA_TIMEZONE: str = Field(
        default="UTC",
        description="Default timezone for CA instances"
    )
    CA_DOCKER_IMAGE: str = Field(
        default="julijaand/collectiveaccess:latest",
        description="Docker image for CA deployment"
    )
    CA_CERT_ISSUER: str = Field(
        default="letsencrypt",
        description="cert-manager issuer for SSL certificates"
    )
    
    # Storage
    CA_STORAGE_SIZE: str = Field(
        default="20Gi",
        description="Persistent volume size for CA instances"
    )
    
    # Security
    SECRET_KEY: str = Field(
        default="",
        description="Secret key for JWT tokens (required in production)"
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="JWT token expiration time"
    )
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = Settings()
