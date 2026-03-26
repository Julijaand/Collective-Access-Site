# Collective Access - Dockerized Deployment

Production-ready Docker containerization for [Collective Access](https://collectiveaccess.org/), the open-source collections management software for museums, archives, and galleries.

## 📋 Overview

This Docker setup provides:
- ✅ **Reproducible Deployments** - Run CA anywhere with consistent configuration
- ✅ **Kubernetes Ready** - Nginx + PHP-FPM architecture for K8s Ingress
- ✅ **Simplified Configuration** - Environment-based with sensible defaults
- ✅ **Health Checks** - Built-in monitoring for K8s probes
- ✅ **Minimal Footprint** - ~400MB image, optimized build time

## 🏗️ Architecture

```
Internet / Kubernetes Ingress
       ↓
┌──────────────────┐
│  CA Container    │  Port 80 (HTTP)
│  ┌────────────┐  │
│  │   Nginx    │  │  :80 → HTTP server
│  └─────┬──────┘  │
│        ↓         │
│  ┌────────────┐  │
│  │  PHP-FPM   │  │  :9000 → FastCGI
│  └────────────┘  │
└──────────────────┘
       ↓
┌──────────────────┐
│   MySQL 8.0      │  Port 3306
│   (Database)     │
└──────────────────┘
```

**Key Design:**
- **Single container** with Nginx + PHP-FPM (standard PHP SaaS pattern)
- **Nginx** handles HTTP, serves static files, proxies PHP to PHP-FPM
- **PHP-FPM** executes PHP code via FastCGI protocol
- **Kubernetes Ingress** routes traffic to port 80 (in production)

## 📁 Project Structure

```
ca-docker/
├── Dockerfile              # Nginx + PHP-FPM + CA
├── docker-compose.yml      # Local development setup
├── .env                    # Environment variables
├── .env.example            # Environment template
├── nginx/
│   └── nginx.conf         # Nginx configuration (port 80 → PHP-FPM 9000)
├── php/
│   └── php.ini            # Essential PHP settings (8 lines)
├── scripts/
│   └── entrypoint.sh      # Startup: wait for DB, start services
└── README.md              # This file
```

## 🚀 Quick Start

### Prerequisites

- Docker 24.0+
- Docker Compose 2.20+
- 2GB RAM minimum
- 10GB disk space

### 1. Clone and Configure

```bash
# Navigate to project directory
cd ca-docker

# Copy environment file
cp .env.example .env

# Edit environment variables (optional - defaults work for local dev)
nano .env
```

### 2. Start Services

```bash
# Build and start all containers
docker-compose up --build

# Or run in background
docker-compose up -d --build

# View logs
docker-compose logs -f ca

# Check status
docker-compose ps
```

### 3. Access Collective Access

- **Application**: http://localhost:8080
- **Installer**: http://localhost:8080/install

**Default Credentials:**
- Username: `administrator`
- Password: `admin`

⚠️ **Important**: Change default passwords before production deployment!

## ⚙️ Configuration

### Environment Variables

All configuration is in `.env` file:

#### Database Settings
```bash
DB_HOST=db
DB_PORT=3306
DB_NAME=ca
DB_USER=ca_user
DB_PASSWORD=db_pass
MYSQL_ROOT_PASSWORD=MySQL_pass
MYSQL_VERSION=8.0
```

#### Site Settings
```bash
CA_SITE_HOST=localhost:8080
CA_ADMIN_EMAIL=admin@example.com
CA_ADMIN_PASSWORD=admin
CA_TIMEZONE=Europe/Paris          # Set your timezone
```

#### Instance Identification (Multi-tenant SaaS)
```bash
CA_INSTANCE_ID=local-dev
CA_TENANT_NAME=default
```

#### Docker Settings
```bash
CA_PORT=8080                      # External port (host → container :80)
CA_APP_DIR=/var/www/html/ca      # CA installation path
DB_CONTAINER_NAME=ca-db
CA_CONTAINER_NAME=ca-app
```

## 🛠️ Common Tasks

### Building the Image

```bash
# Build CA image
docker-compose build

# Build with no cache
docker-compose build --no-cache

# Tag for registry
docker tag ca-app:latest your-registry.com/collectiveaccess:latest
```

### Managing Containers

```bash
# Start services
docker-compose up -d

# Stop services (preserves data)
docker-compose stop

# Stop and remove containers (DELETES VOLUMES - fresh start)
docker-compose down

# Stop and remove containers but keep volumes
docker-compose down --volumes=false

# Restart containers (preserves all data)
docker-compose restart

# View logs
docker-compose logs -f ca db

# Execute commands in container
docker-compose exec ca bash
```

⚠️ **Important**: Use `docker-compose restart` or `docker-compose stop` to preserve your database and uploaded files. The `docker-compose down` command removes volumes by default.
### Database Management

```bash
# Access MySQL CLI
docker-compose exec db mysql -u ca_user -p ca

# Backup database
docker-compose exec db mysqldump -u ca_user -p ca > backup.sql

# Restore database
docker-compose exec -T db mysql -u ca_user -p ca < backup.sql

# Reset database (WARNING: deletes all data!)
docker-compose down -v
docker-compose up -d
```

### File Management

```bash
# Copy files to container
docker cp ./my-file.txt ca-app:/var/www/html/ca/

# Copy files from container
docker cp ca-app:/var/www/html/ca/media/ ./local-media/

# Check disk usage
docker-compose exec ca du -sh /var/www/html/ca/media
```

### Health Checks

```bash
# Check app health
curl http://localhost:8080/

# Check container health status
docker-compose ps

# Test Nginx configuration
docker-compose exec ca nginx -t

# Check PHP-FPM status
docker-compose exec ca php-fpm -t

# View PHP info
docker-compose exec ca php -i
```

## 📊 Monitoring

### Container Health

```bash
# Check container status
docker-compose ps

# View resource usage
docker stats ca-app ca-db

# Inspect container
docker inspect ca-app
```

### Logs

```bash
# Application logs
docker-compose logs -f ca

# Database logs
docker-compose logs -f db

# CA application logs
docker-compose exec ca tail -f /var/www/html/ca/app/log/system.log

# Follow all logs
docker-compose logs -f
```

## 🔒 Security Best Practices

### Before Production Deployment

1. **Change All Default Passwords**
   ```bash
   DB_PASSWORD=<strong-random-password>
   CA_ADMIN_PASSWORD=<strong-random-password>
   MYSQL_ROOT_PASSWORD=<strong-random-password>
   ```

2. **Never Commit Secrets**
   - `.env` is in `.gitignore` - keep it that way
   - Use Docker Secrets or Kubernetes Secrets in production
   - Use environment-specific config files

3. **Enable HTTPS** (In production via Kubernetes Ingress + cert-manager)
   - Let Kubernetes Ingress handle TLS termination
   - Container stays on HTTP (port 80)

4. **Network Security**
   - Expose only necessary ports
   - Use Kubernetes NetworkPolicies
   - Implement rate limiting at Ingress level

5. **Regular Updates**
   ```bash
   docker-compose pull
   docker-compose up -d --build
   ```

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check logs for errors
docker-compose logs ca

# Verify database connection
docker-compose exec ca ping db

# Check disk space
df -h

# Rebuild from scratch
docker-compose down -v
docker-compose up --build
```

### Database Connection Issues

```bash
# Test MySQL connection
docker-compose exec ca mysql -h db -u ca_user -p

# Check MySQL status
docker-compose exec db mysqladmin status -u root -p

# Wait for database to be ready
docker-compose logs db | grep "ready for connections"

# Restart database
docker-compose restart db
```

### Permission Issues

```bash
# Fix file permissions
docker-compose exec ca chown -R www-data:www-data /var/www/html/ca

# Check permissions
docker-compose exec ca ls -la /var/www/html/ca/app/tmp
```

### Can't Access Application

1. Check if containers are running: `docker-compose ps`
2. Check port conflicts: `lsof -i :8080`
3. Verify firewall settings
4. Check Nginx logs: `docker-compose logs ca | grep nginx`
5. Check PHP-FPM: `docker-compose exec ca php-fpm -t`

### Nginx/PHP Issues

```bash
# Test Nginx config
docker-compose exec ca nginx -t

# Restart services (entrypoint handles both)
docker-compose restart ca

# Check if PHP-FPM is running
docker-compose exec ca ps aux | grep php-fpm

# Check if Nginx is running
docker-compose exec ca ps aux | grep nginx
```

### Reset Administrator Password

```bash
# Reset password using CA's built-in utility
docker-compose exec ca php /var/www/html/ca/support/bin/caUtils reset-password --username=administrator --password=YourNewPassword
```

This is the recommended way to reset passwords as it properly handles CA's authentication requirements.

## 🚢 Production Deployment

### Kubernetes Deployment

This Docker setup is Kubernetes-ready. Key points:

- **Ingress Controller** routes traffic to pod port 80
- **Nginx inside container** handles HTTP and proxies to PHP-FPM
- **Health checks** work with K8s liveness/readiness probes
- **Environment variables** map to ConfigMaps/Secrets

See Phase 2 of the [roadmap](../ROADMAP.md) for Helm chart creation.

### Registry Push

```bash
# Tag image
docker tag ca-app:latest registry.example.com/collectiveaccess:latest

# Push to registry
docker push registry.example.com/collectiveaccess:latest
```

## 📚 Additional Resources

- [Collective Access Documentation](https://manual.collectiveaccess.org/)
- [Collective Access GitHub](https://github.com/collectiveaccess/providence)
- [Docker Documentation](https://docs.docker.com/)
- [Project Roadmap](../ROADMAP.md)

## 🤝 Support

For issues related to:
- **Docker Setup**: Open an issue in this repository
- **Collective Access**: Visit [CA Support Forum](https://collectiveaccess.org/support/)
- **SaaS Platform**: See [roadmap](../ROADMAP.md)

## 📝 License

This Docker configuration is released under MIT License.  
Collective Access is licensed under GPL v3.

---

**Next Steps**: Once Phase 1 is complete, proceed to [Phase 2: Kubernetes Deployment](../ROADMAP.md)

**Version**: 1.1  
**Last Updated**: January 13, 2026
