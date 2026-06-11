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

        # Generate admin password upfront — stored before deployment so it's
        # never lost even if the post-install step fails
        ca_admin_password = uuid.uuid4().hex[:12]

        # Per-tenant JWT secret for CA GraphQL services (32+ chars required by firebase/php-jwt HS256)
        ca_jwt_secret = uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars

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
            ca_admin_password=ca_admin_password,  # stored now, set on pod after deploy
            ca_jwt_secret=ca_jwt_secret,
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
            tenant.provisioning_step = "namespace"
            self.db.commit()
            self._ensure_namespace(k8s_namespace)
            time.sleep(15)

            # Tenant database
            tenant.provisioning_step = "database"
            self.db.commit()
            self._ensure_database(db_name, db_user, db_password)
            time.sleep(15)

            # Helm release / CollectiveAccess deployment
            tenant.provisioning_step = "helm"
            self.db.commit()
            self._ensure_helm_release(
                release=helm_release_name,
                namespace=k8s_namespace,
                domain=domain,
                plan=plan,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
                ca_app_name=ca_app_name,
                admin_email=email,  # use actual tenant user's email
                jwt_secret=ca_jwt_secret,
                admin_password=ca_admin_password,
                install_profile=settings.CA_INSTALL_PROFILE,
            )

            # After Helm --atomic returns the pod is Running/Ready (nginx up),
            # but CA's first-boot DB install can still be in progress.
            # Wait until the administrator user actually exists in MySQL before
            # resetting the password.
            tenant.provisioning_step = "ca_install"
            self.db.commit()
            time.sleep(15)  # ensure UI polls at least 7 times before checking
            self._wait_for_ca_ready(db_name, db_user, db_password, timeout=1200)

            tenant.provisioning_step = "finalizing"
            self.db.commit()
            self._set_ca_password(k8s_namespace, helm_release_name, ca_admin_password)
            time.sleep(15)

            # Update tenant metadata
            tenant.status = TenantStatus.ACTIVE
            tenant.provisioning_step = None
            tenant.deployed_at = datetime.utcnow()
            # ca_admin_password already set on tenant before deployment

            log.status = "completed"
            log.message = f"Successfully provisioned {helm_release_name}"
            log.completed_at = datetime.utcnow()

            self.db.commit()
            logger.info(f"Provisioned tenant {helm_release_name}")
            return tenant, None

        except Exception as e:
            logger.exception("Provisioning failed")

            tenant.status = TenantStatus.FAILED
            tenant.provisioning_step = None
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
            # Derive ca_app_name from helm_release_name (same logic as provision_tenant)
            _suffix = tenant.helm_release_name.replace("tenant-", "")
            _ca_app_name = f"tenant_{_suffix}"
            self._ensure_helm_release(
                release=tenant.helm_release_name,
                namespace=tenant.namespace,
                domain=tenant.domain,
                plan=plan,
                db_name=tenant.db_name,
                db_user=tenant.db_user,
                db_password=tenant.db_password,
                ca_app_name=_ca_app_name,
                admin_email="",
                jwt_secret=tenant.ca_jwt_secret or "",
                admin_password=tenant.ca_admin_password,
                install_profile=settings.CA_INSTALL_PROFILE,
            )

            self._wait_for_ca_ready(tenant.db_name, tenant.db_user, tenant.db_password)
            self._set_ca_password(tenant.namespace, tenant.helm_release_name, tenant.ca_admin_password)

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
        admin_email: str,
        jwt_secret: str = "",
        admin_password: str = "",
        install_profile: str = "default",
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
            ca_app_name=ca_app_name,
            admin_email=admin_email,
            jwt_secret=jwt_secret,
            admin_password=admin_password,
            install_profile=install_profile,
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

    def _wait_for_ca_ready(self, db_name: str, db_user: str, db_password: str, timeout: int = 1200) -> bool:
        """
        Poll tenant MySQL until the 'administrator' user row exists in ca_users.
        Returns True when ready, False on timeout.
        CA first-boot install can take 10-20 min; nginx readiness probe passes
        long before the DB schema is populated.
        """
        deadline = time.time() + timeout
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            try:
                conn = pymysql.connect(
                    host=self.mysql_host,
                    port=self.mysql_port,
                    user=db_user,
                    password=db_password,
                    database=db_name,
                    connect_timeout=5,
                )
                with conn.cursor() as c:
                    c.execute("SELECT COUNT(*) FROM ca_users WHERE user_name='administrator'")
                    (count,) = c.fetchone()
                conn.close()
                if count > 0:
                    logger.info(f"CA install complete for {db_name} (attempt {attempt})")
                    return True
            except Exception as e:
                # Table not yet created, or connection refused — still installing
                logger.debug(f"_wait_for_ca_ready attempt {attempt}: {e}")
            time.sleep(15)
        logger.error(f"_wait_for_ca_ready timed out after {timeout}s for {db_name}")
        return False

    def _set_ca_password(self, namespace: str, tenant_name: str, password: str) -> bool:
        """
        Set the CA administrator password using caUtils reset-password.
        Must be called after _wait_for_ca_ready() confirms the administrator
        user exists in MySQL.
        """
        try:
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
                logger.warning(f"No pod found in {namespace} to set CA password")
                return False

            result = subprocess.run(
                [
                    "kubectl", "exec", "-n", namespace, pod_name,
                    "--", "php", "/var/www/html/ca/support/bin/caUtils",
                    "reset-password",
                    "--user", "administrator",
                    "--password", password,
                ],
                capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0:
                logger.error(f"reset-password failed: {result.stderr}")
                return False

            logger.info(f"CA admin password set for {tenant_name}")
            return True

        except Exception as e:
            logger.error(f"_set_ca_password failed: {e}")
            return False


    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _event_processed(self, stripe_event_id: str) -> bool:
        return (
            self.db.query(ProvisioningLog)
            .filter(ProvisioningLog.stripe_event_id == stripe_event_id)
            .first() is not None
        )
