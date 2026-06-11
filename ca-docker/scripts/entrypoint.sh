#!/bin/bash
# Note: intentionally no "set -e" — CA install failure must not crash the container.
# Nginx must start regardless so the readiness probe passes and Helm --atomic doesn't roll back.

echo "========================================="
echo "Collective Access - Starting"
echo "========================================="

CA_APP_DIR="${CA_APP_DIR:-/var/www/html/ca}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-ca}"
DB_USER="${DB_USER:-ca_user}"
DB_PASSWORD="${DB_PASSWORD}"

echo "→ Database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"

# Wait for database
echo "→ Waiting for database..."
until MYSQL_PWD="${DB_PASSWORD}" mysql -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" -e "SELECT 1" >/dev/null 2>&1; do
    echo "   Waiting..."
    sleep 2
done
echo "✓ Database ready!"

# Set permissions
# CA_INSTANCE_ID uses hyphens (k8s name), CA_APP_NAME uses underscores (CA internal name).
# CA expects directories named after CA_APP_NAME, so create both to be safe.
echo "→ Setting permissions..."
mkdir -p "${CA_APP_DIR}/media/${CA_INSTANCE_ID}"
mkdir -p "${CA_APP_DIR}/media/${CA_APP_NAME}"
mkdir -p "${CA_APP_DIR}/app/tmp"
mkdir -p "${CA_APP_DIR}/app/cache"
mkdir -p "${CA_APP_DIR}/app/tmp/${CA_INSTANCE_ID}Cache"
mkdir -p "${CA_APP_DIR}/app/tmp/${CA_APP_NAME}Cache"
mkdir -p "${CA_APP_DIR}/app/tmp/purifier"
chown -R www-data:www-data \
    "${CA_APP_DIR}/media" \
    "${CA_APP_DIR}/app/tmp" \
    "${CA_APP_DIR}/app/cache"
echo "✓ Done!"

echo "========================================="
echo "✓ Collective Access is ready!"
echo "========================================="

# Generate setup.php from template
SETUP_FILE="${CA_APP_DIR}/setup.php"
if [ ! -f "$SETUP_FILE" ]; then
  echo "→ Generating setup.php from template..."
  envsubst < /config/setup.php.template > "$SETUP_FILE"
  chown www-data:www-data "$SETUP_FILE"
  echo "✓ setup.php created!"
fi

# Patch CA config for GraphQL/JWT support
echo "→ Patching CA config for GraphQL services..."
APP_CONF="${CA_APP_DIR}/app/conf/app.conf"
AUTH_CONF="${CA_APP_DIR}/app/conf/authentication.conf"

if [ -f "$APP_CONF" ]; then
  # Set a strong JWT key for GraphQL services (32+ chars required by firebase/php-jwt HS256)
  JWT_KEY="${CA_JWT_SECRET:-ca-saas-jwt-secret-key-for-collective-access-graphql-api-2026}"
  if grep -q "^graphql_services_jwt_token_key" "$APP_CONF"; then
    sed -i "s|^graphql_services_jwt_token_key.*|graphql_services_jwt_token_key = ${JWT_KEY}|" "$APP_CONF"
  else
    echo "graphql_services_jwt_token_key = ${JWT_KEY}" >> "$APP_CONF"
  fi
  echo "✓ JWT key configured (${#JWT_KEY} chars)"
fi

if [ -f "$AUTH_CONF" ]; then
  # Enable CaUsers auth adapter for GraphQL service requests
  if grep -q "^#.*auth_adapter_for_services" "$AUTH_CONF"; then
    sed -i "s|^#.*auth_adapter_for_services.*|auth_adapter_for_services = CaUsers|" "$AUTH_CONF"
  elif ! grep -q "^auth_adapter_for_services" "$AUTH_CONF"; then
    echo "auth_adapter_for_services = CaUsers" >> "$AUTH_CONF"
  fi
  echo "✓ auth_adapter_for_services = CaUsers"
fi

# Start PHP-FPM (always needed — for both install and serving requests)
php-fpm -D
sleep 2

# Auto-install CA if not already installed
INSTALL_FLAG="${CA_APP_DIR}/media/.ca_installed"
if [ ! -f "$INSTALL_FLAG" ]; then
  echo "→ Running CA headless installation..."
  PROFILE="${CA_PROFILE:-default}"
  ADMIN_EMAIL="${CA_ADMIN_EMAIL:-admin@collective-museum.com}"

  su -s /bin/bash www-data -c "php ${CA_APP_DIR}/support/bin/caUtils install \
    --profile-name '${PROFILE}' \
    --profile-directory '${CA_APP_DIR}/install/profiles/xml' \
    --admin-email '${ADMIN_EMAIL}'" 2>&1

  INSTALL_EXIT=$?
  if [ $INSTALL_EXIT -eq 0 ]; then
    echo "✓ CA installation complete!"

    # Immediately reset password to our known value so saas-backend DB stays in sync
    if [ -n "${CA_ADMIN_PASSWORD}" ]; then
      su -s /bin/bash www-data -c "php ${CA_APP_DIR}/support/bin/caUtils reset-password \
        --username administrator \
        --password '${CA_ADMIN_PASSWORD}'" 2>&1
      echo "✓ Admin password set"
    fi

    touch "$INSTALL_FLAG"
  else
    echo "✗ CA installation failed (exit $INSTALL_EXIT) — nginx will start anyway"
  fi
else
  echo "→ CA already installed, skipping install step"
fi

# Deploy AI agent widget and PHP proxy into CA web root
echo "→ Deploying AI agent widget..."
cp /scripts/ca-agent-proxy.php "${CA_APP_DIR}/ca-agent-proxy.php"
cp /assets/ca-chat-widget.js   "${CA_APP_DIR}/ca-chat-widget.js"
chown www-data:www-data \
    "${CA_APP_DIR}/ca-agent-proxy.php" \
    "${CA_APP_DIR}/ca-chat-widget.js"
echo "✓ AI agent widget deployed"

# Start Nginx in foreground
echo "→ Starting Nginx..."
exec nginx -g 'daemon off;'
