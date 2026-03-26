# ============================================================================
# Collective Access - Kubernetes-Ready Container
# Simple & optimized for SaaS multi-tenant deployment
# ============================================================================

FROM php:8.2-fpm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nginx \
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    libzip-dev \
    libmagickwand-dev \
    imagemagick \
    unzip \
    git \
    curl \
    mariadb-client \
    gettext-base \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j$(nproc) pdo_mysql mysqli zip gd exif intl opcache bcmath \
    && pecl install imagick \
    && docker-php-ext-enable imagick \
    && rm -rf /var/lib/apt/lists/*

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Download Collective Access
WORKDIR /var/www/html
RUN git clone --depth 1 --branch master \
    https://github.com/collectiveaccess/providence.git ca

# Mark repo as safe for git
RUN git config --global --add safe.directory /var/www/html/ca

# Install PHP dependencies via Composer
WORKDIR /var/www/html/ca
RUN composer install --no-dev --optimize-autoloader --no-interaction --no-security-blocking \
    && chown -R www-data:www-data /var/www/html/ca

# Copy configuration files
COPY php/php.ini /usr/local/etc/php/php.ini
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY config/setup.php.template /config/setup.php.template
COPY scripts/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

WORKDIR /var/www/html/ca

RUN mkdir -p \
  /var/www/html/ca/app/tmp \
  /var/www/html/ca/app/cache \
  /var/www/html/ca/media \
 && chown -R www-data:www-data /var/www/html/ca

# Expose HTTP port (Nginx serves HTTP, proxies to PHP-FPM internally)
EXPOSE 80

# Health check for Kubernetes probes
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD php -r "exit(is_file('/var/www/html/ca/index.php') ? 0 : 1);"

CMD ["/entrypoint.sh"]
