#!/bin/bash
set -e

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
echo "→ Setting permissions..."
mkdir -p "${CA_APP_DIR}/media/${CA_INSTANCE_ID}"
mkdir -p "${CA_APP_DIR}/app/tmp"
mkdir -p "${CA_APP_DIR}/app/cache"
mkdir -p "${CA_APP_DIR}/app/tmp/${CA_INSTANCE_ID}Cache"
mkdir -p "${CA_APP_DIR}/app/tmp/purifier"
chown -R www-data:www-data "${CA_APP_DIR}"
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

# Start PHP-FPM in background
php-fpm -D

# Start Nginx in foreground
echo "→ Starting Nginx..."
exec nginx -g 'daemon off;'
