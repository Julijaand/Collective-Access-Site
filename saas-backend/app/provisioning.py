"""
Collective Access SaaS Backend - Tenant Provisioning
Phase 3: Core provisioning logic for tenant lifecycle management
"""

import logging
import uuid
import os
import subprocess
import time
from datetime import datetime
from sqlalchemy.orm import Session
import pymysql
from .config import settings

from .models import (
    Tenant,
    TenantStatus,
    ProvisioningLog,
    ProvisioningAction,
    Subscription,
)
from .k8s import KubernetesManager, HelmManager

logger = logging.getLogger(__name__)


class TenantProvisioner:
    """Handles the complete tenant provisioning lifecycle"""

    def __init__(self, db: Session):
        self.db = db  # PostgreSQL session for backend metadata
        self.k8s = KubernetesManager()

        # MySQL host/port for tenant databases (per-tenant credentials handled later)
        self.mysql_host = settings.DB_HOST
        self.mysql_port = settings.DB_PORT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def provision_tenant(
        self,
        user_id: int,
        email: str,
        plan: str,
        stripe_subscription_id: str,
        stripe_customer_id: str,
        stripe_event_id: str | None = None,
    ) -> tuple[Tenant, str | None]:
        """
        Complete tenant provisioning workflow (idempotent + resumable)
        Handles:
        - RFC 1123-compliant Kubernetes namespace
        - CA_APP_NAME-safe identifier for CollectiveAccess (alphanumeric + underscore)
        """

        # Idempotency: Stripe event already processed
        if stripe_event_id and self._event_processed(stripe_event_id):
            logger.info(f"Stripe event {stripe_event_id} already processed")
            tenant = (
                self.db.query(Tenant)
                .join(Subscription)
                .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
                .first()
            )
            return tenant, None

        # Existing tenant check
        existing = (
            self.db.query(Tenant)
            .join(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
            .first()
        )

        if existing:
            if existing.status == TenantStatus.ACTIVE:
                logger.info(f"Tenant already active for subscription {stripe_subscription_id}")
                return existing, None
            logger.warning(f"Tenant exists but status={existing.status}, attempting resume")
            return self._resume_provisioning(existing, plan)

        # ------------------------------------------------------------------
        # New tenant provisioning
        # ------------------------------------------------------------------

        tenant_suffix = uuid.uuid4().hex[:8]

        # Kubernetes namespace: lowercase letters, numbers, hyphens only
        k8s_namespace = f"{settings.KUBERNETES_NAMESPACE_PREFIX}-{tenant_suffix}"

        # Helm release name: same as namespace
        helm_release_name = k8s_namespace

        # CollectiveAccess app name: alphanumeric + underscores
        ca_app_name = f"tenant_{tenant_suffix}"

        # Domain (DNS-safe)
        domain = f"{k8s_namespace}.{settings.BASE_DOMAIN}"

        # Tenant MySQL database credentials
        db_name = f"ca_{tenant_suffix}"
        db_user = f"ca_{tenant_suffix}"
        db_password = uuid.uuid4().hex

        # Create Tenant object (metadata stored in PostgreSQL)
        tenant = Tenant(
            user_id=user_id,
            namespace=k8s_namespace,
            helm_release_name=helm_release_name,
            domain=domain,
            plan=plan,
            status=TenantStatus.PENDING,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            ca_admin_username="administrator",
            ca_admin_password=None,  # to be filled after installation
        )

        self.db.add(tenant)
        self.db.flush()

        # Subscription object
        subscription = Subscription(
            tenant_id=tenant.id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            stripe_price_id="",
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
        )
        self.db.add(subscription)

        # Provisioning log
        log = ProvisioningLog(
            tenant_id=tenant.id,
            action=ProvisioningAction.CREATE,
            status="started",
            message=f"Starting provisioning for {helm_release_name}",
            stripe_event_id=stripe_event_id,
        )
        self.db.add(log)
        self.db.commit()

        tenant.status = TenantStatus.PROVISIONING
        self.db.commit()

        try:
            # Kubernetes namespace
            self._ensure_namespace(k8s_namespace)

            # Tenant database
            self._ensure_database(db_name, db_user, db_password)

            # Helm release / CollectiveAccess deployment
            self._ensure_helm_release(
                release=helm_release_name,
                namespace=k8s_namespace,
                domain=domain,
                plan=plan,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
                ca_app_name=ca_app_name,  # use CA-safe identifier
            )

            # Run CollectiveAccess installer inside pod
            ca_password = self._run_ca_installer(k8s_namespace, helm_release_name, ca_app_name)

            # Update tenant metadata
            tenant.status = TenantStatus.ACTIVE
            tenant.deployed_at = datetime.utcnow()
            tenant.ca_admin_password = ca_password or "Installer not completed"

            log.status = "completed"
            log.message = f"Successfully provisioned {helm_release_name}"
            log.completed_at = datetime.utcnow()

            self.db.commit()
            logger.info(f"Provisioned tenant {helm_release_name}")
            return tenant, None

        except Exception as e:
            logger.exception("Provisioning failed")

            tenant.status = TenantStatus.FAILED
            log.status = "failed"
            log.error_details = str(e)
            log.completed_at = datetime.utcnow()
            self.db.commit()

            return tenant, str(e)

    # ------------------------------------------------------------------
    # Resume logic
    # ------------------------------------------------------------------

    def _resume_provisioning(self, tenant: Tenant, plan: str) -> tuple[Tenant, str | None]:
        try:
            self._ensure_namespace(tenant.namespace)
            self._ensure_database(tenant.db_name, tenant.db_user, tenant.db_password)
            self._ensure_helm_release(
                tenant.helm_release_name, tenant.namespace, tenant.domain, plan,
                tenant.db_name, tenant.db_user, tenant.db_password
            )

            tenant.status = TenantStatus.ACTIVE
            tenant.deployed_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Resumed provisioning for {tenant.namespace}")
            return tenant, None
        except Exception as e:
            tenant.status = TenantStatus.FAILED
            self.db.commit()
            return tenant, str(e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_namespace(self, namespace: str):
        if not self.k8s.namespace_exists(namespace):
            logger.info(f"Creating namespace {namespace}")
            if not self.k8s.create_namespace(namespace):
                raise Exception("Failed to create namespace")

    def _ensure_database(self, db_name: str, db_user: str, db_password: str):
        if self._database_exists(db_name):
            return
        if not self._create_database(db_name, db_user, db_password):
            raise Exception(f"Failed to create tenant database {db_name}")

    def _ensure_helm_release(
        self,
        release: str,
        namespace: str,
        domain: str,
        plan: str,
        db_name: str,
        db_user: str,
        db_password: str,
        ca_app_name: str,  
    ):
        """
        Ensure Helm release exists for tenant.
        Pass CA-safe app name to Helm for setup.php/template.
        """
        if HelmManager.release_exists(release, namespace):
            return

        success, msg = HelmManager.install_tenant(
            tenant_name=release,
            namespace=namespace,
            domain=domain,
            plan=plan,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            ca_app_name=ca_app_name,  # <-- pass CA app name
        )

        if not success:
            raise Exception(f"Helm install failed: {msg}")


    # ------------------------------------------------------------------
    # MySQL helpers for tenant databases
    # ------------------------------------------------------------------

    def _database_exists(self, db_name: str) -> bool:
        conn = pymysql.connect(
            host=self.mysql_host,
            port=self.mysql_port,
            user="root",
            password=settings.MYSQL_ROOT_PASSWORD,
        )
        try:
            with conn.cursor() as c:
                c.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s",
                    (db_name,)
                )
                return c.fetchone() is not None
        finally:
            conn.close()

    def _create_database(self, db_name: str, db_user: str, db_password: str) -> bool:
        try:
            conn = pymysql.connect(
                host=self.mysql_host,
                port=self.mysql_port,
                user="root",
                password=settings.MYSQL_ROOT_PASSWORD,
                autocommit=True,
            )
            with conn.cursor() as c:
                c.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;")
                c.execute("CREATE USER IF NOT EXISTS %s@'%%' IDENTIFIED BY %s;", (db_user, db_password))
                c.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO %s@'%%';", (db_user,))
                c.execute("FLUSH PRIVILEGES;")
            conn.close()
            return True
        except Exception as e:
            logger.error(f"MySQL error: {e}")
            return False

    # ------------------------------------------------------------------
    # CA installer
    # ------------------------------------------------------------------

    def _run_ca_installer(self, namespace: str, tenant_name: str, ca_app_name: str) -> str | None:
        """
        Run the CollectiveAccess installer inside the tenant pod.
        Uses ca_app_name (alphanumeric + underscore) to avoid invalid CA_APP_NAME.
        """
        try:
            time.sleep(30)
            # Get pod name
            result = subprocess.run(
                [
                    "kubectl", "get", "pod", "-n", namespace,
                    "-l", f"app={tenant_name}",
                    "-o", "jsonpath={.items[0].metadata.name}"
                ],
                capture_output=True, text=True, timeout=30
            )
            pod_name = result.stdout.strip()
            if not pod_name:
                return None

            # Run installer inside pod
            result = subprocess.run(
                [
                    "kubectl", "exec", "-n", namespace, pod_name,
                    "--", "php", "/var/www/html/ca/support/bin/caUtils",
                    "install",
                    "--profile-name=default",
                    f"--admin-email={settings.CA_ADMIN_EMAIL}",
                    f"--app-name={ca_app_name}",   # << pass CA-safe app name
                    "--overwrite",
                ],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode != 0:
                logger.error(result.stderr)
                return None

            # Extract password from installer output
            for line in result.stdout.splitlines():
                if "password" in line.lower():
                    return line.split()[-1]
            return None

        except Exception as e:
            logger.error(f"CA installer failed: {e}")
            return None


    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _event_processed(self, stripe_event_id: str) -> bool:
        return (
            self.db.query(ProvisioningLog)
            .filter(ProvisioningLog.stripe_event_id == stripe_event_id)
            .first() is not None
        )
