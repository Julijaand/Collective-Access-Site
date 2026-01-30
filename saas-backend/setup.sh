#!/bin/bash
# ============================================================================
# Collective Access SaaS Backend - Quick Setup Script
# Phase 3: Automated setup for development environment
# ============================================================================

set -e

echo "========================================="
echo "CA SaaS Backend - Quick Setup"
echo "========================================="

# Check Python version
echo "→ Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Found Python $python_version"

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Create virtual environment
echo "→ Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "→ Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "→ Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "  ✓ Dependencies installed"

# Setup environment file
echo "→ Setting up environment configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  ✓ Created .env file from template"
    echo "  ⚠️  Please edit .env with your configuration"
else
    echo "  ✓ .env file already exists"
fi

# Check PostgreSQL
echo "→ Checking PostgreSQL..."
if command -v psql &> /dev/null; then
    echo "  ✓ PostgreSQL client found"
else
    echo "  ⚠️  PostgreSQL client not found"
    echo "  Install: brew install postgresql (macOS) or apt-get install postgresql-client (Linux)"
fi

# Check kubectl
echo "→ Checking kubectl..."
if command -v kubectl &> /dev/null; then
    echo "  ✓ kubectl found"
    kubectl version --client --short 2>/dev/null || echo "  (version check failed)"
else
    echo "  ❌ kubectl not found - required for tenant provisioning"
    exit 1
fi

# Check Helm
echo "→ Checking Helm..."
if command -v helm &> /dev/null; then
    helm_version=$(helm version --short 2>/dev/null)
    echo "  ✓ Helm found: $helm_version"
else
    echo "  ❌ Helm not found - required for tenant deployment"
    exit 1
fi

# Create database (optional)
echo ""
echo "========================================="
echo "Database Setup (Optional)"
echo "========================================="
read -p "Create PostgreSQL database 'ca_saas'? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    createdb ca_saas 2>/dev/null && echo "✓ Database created" || echo "⚠️  Database creation failed (may already exist)"
fi

# Initialize database
echo ""
echo "========================================="
echo "Initialize Database Tables"
echo "========================================="
read -p "Initialize database tables? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 -c "from app.database import init_db; init_db(); print('✓ Database initialized')"
fi

echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env with your configuration"
echo "2. Start the backend: uvicorn app.main:app --reload"
echo "3. Visit: http://localhost:8000"
echo "4. Check health: curl http://localhost:8000/health"
echo ""
echo "Documentation: README.md"
echo "========================================="
