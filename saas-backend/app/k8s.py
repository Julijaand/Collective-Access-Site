"""
Collective Access SaaS Backend - Kubernetes & Helm Integration
Phase 3: Automated tenant deployment via Kubernetes API and Helm
"""

import subprocess
import logging
import json
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from .config import settings

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Kubernetes Manager
# -------------------------------------------------------------------

class KubernetesManager:
    """Manages Kubernetes operations for tenant deployment"""

    def __init__(self):
        try:
            if settings.KUBERNETES_IN_CLUSTER:
                config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes configuration")
            else:
                config.load_kube_config()
                logger.info("Loaded local Kubernetes configuration")

            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()

        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise

    def create_namespace(self, namespace: str) -> bool:
        try:
            ns = client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=namespace,
                    labels={
                        "app": "collectiveaccess",
                        "managed-by": "saas-backend"
                    }
                )
            )
            self.core_v1.create_namespace(ns)
            logger.info(f"Created namespace: {namespace}")
            return True

        except ApiException as e:
            if e.status == 409:
                logger.info(f"Namespace {namespace} already exists")
                return True
            logger.error(f"Failed to create namespace {namespace}: {e}")
            return False

    def namespace_exists(self, namespace: str) -> bool:
        try:
            self.core_v1.read_namespace(namespace)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            logger.error(f"Namespace check failed for {namespace}: {e}")
            return False

    def get_pod_status(self, namespace: str) -> dict:
        try:
            pods = self.core_v1.list_namespaced_pod(namespace)
            return {
                "total": len(pods.items),
                "running": sum(1 for p in pods.items if p.status.phase == "Running"),
                "pending": sum(1 for p in pods.items if p.status.phase == "Pending"),
                "failed": sum(1 for p in pods.items if p.status.phase == "Failed"),
            }
        except ApiException as e:
            logger.error(f"Failed to get pod status for {namespace}: {e}")
            return {}


# -------------------------------------------------------------------
# Helm Manager
# -------------------------------------------------------------------

class HelmManager:
    """Manages Helm-based tenant installations"""

    @staticmethod
    def release_exists(release: str, namespace: str) -> bool:
        try:
            cmd = [
                "helm", "list",
                "--namespace", namespace,
                "--filter", f"^{release}$",
                "--short"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return release in result.stdout.splitlines()
        except Exception as e:
            logger.error(f"Failed to check Helm release {release}: {e}")
            return False

    @staticmethod
    def install_tenant(
        tenant_name: str,
        namespace: str,
        domain: str,
        plan: str,
        db_name: str,
        db_user: str,
        db_password: str,
        ca_app_name: str,
    ) -> tuple[bool, str]:
        """
        Install or upgrade a tenant Helm release (idempotent)
        Passes CA-safe app name to chart.
        """

        storage_map = {
            "starter": "10Gi",
            "basic": "20Gi",
            "pro": "100Gi",
            "museum": "1Ti",
        }
        storage_size = storage_map.get(plan, settings.CA_STORAGE_SIZE)

        cmd = [
            "helm", "upgrade", "--install", tenant_name,
            settings.HELM_CHART_PATH,
            "--namespace", namespace,
            "--create-namespace",
            "--atomic",
            "--timeout", "300s",

            "--set", f"tenantName={tenant_name}",
            "--set", f"domain={domain}",

            "--set", f"database.name={db_name}",
            "--set", f"database.user={db_user}",
            "--set", f"database.password={db_password}",
            "--set", f"database.host={settings.DB_HOST}",
            "--set", f"database.port={settings.DB_PORT}",

            "--set", f"image={settings.CA_DOCKER_IMAGE}",
            "--set", f"storageSize={storage_size}",
            "--set", f"certIssuer={settings.CA_CERT_ISSUER}",

            "--set", f"app.timezone={settings.CA_TIMEZONE}",
            "--set", f"app.adminEmail={settings.CA_ADMIN_EMAIL}",
            "--set", f"app.instanceId={tenant_name}",
            "--set", f"app.tenantDisplayName={tenant_name}",
            "--set", f"app.caAppName={ca_app_name}",
        ]

        logger.info(f"Running Helm command: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Helm install succeeded for {tenant_name}")
            return True, result.stdout

        except subprocess.CalledProcessError as e:
            # Detect if Helm release is locked
            if "another operation (install/upgrade/rollback) is in progress" in e.stderr:
                logger.warning(f"Helm release '{tenant_name}' is locked. Attempting rollback...")

                # Get the last revision number
                rev_result = subprocess.run(
                    ["helm", "history", tenant_name, "-n", namespace, "--max=1", "--output=json"],
                    capture_output=True, text=True, check=True
                )
                last_rev = json.loads(rev_result.stdout)[-1]["revision"]
                logger.info(f"Rolling back release '{tenant_name}' to revision {last_rev}")

                subprocess.run(["helm", "rollback", tenant_name, str(last_rev), "-n", namespace],
                            check=True, capture_output=True, text=True)
                logger.info(f"Rollback complete for '{tenant_name}', retrying install...")

                # Retry the original install command
                result_retry = subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.info(f"Helm install succeeded for {tenant_name} after rollback")
                return True, result_retry.stdout

            # Other Helm errors
            logger.error(f"Helm install failed for {tenant_name}: {e.stderr}")
            return False, e.stderr

    @staticmethod
    def uninstall_tenant(tenant_name: str, namespace: str) -> tuple[bool, str]:
        try:
            cmd = ["helm", "uninstall", tenant_name, "--namespace", namespace]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Helm uninstall failed for {tenant_name}: {result.stderr}")
                return False, result.stderr

            logger.info(f"Uninstalled tenant {tenant_name}")
            return True, result.stdout

        except Exception as e:
            logger.error(f"Helm uninstall error for {tenant_name}: {e}")
            return False, str(e)
