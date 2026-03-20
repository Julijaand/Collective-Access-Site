#!/bin/bash

# Phase 4 Customer Portal - Setup Script
# Run this from inside the customer-portal/ directory after cloning the repo.
# Usage: bash setup-customer-portal.sh

set -e  # Exit on error

echo "🚀 Starting Customer Portal Setup..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Always run from the directory where this script lives (customer-portal/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}Step 1/4: Installing npm dependencies...${NC}"
npm install axios \
  zustand \
  @tanstack/react-query \
  react-hook-form \
  zod \
  date-fns \
  recharts \
  lucide-react \
  @stripe/stripe-js \
  @stripe/react-stripe-js \
  socket.io-client

echo ""
echo -e "${BLUE}Step 2/4: Initialising shadcn/ui...${NC}"
if [ -f components.json ]; then
  echo "  components.json already exists (cloned repo) — skipping shadcn init"
else
  npx shadcn@latest init -y
fi

echo ""
echo -e "${BLUE}Step 3/4: Installing shadcn/ui components...${NC}"
if [ -d src/components/ui ] && [ "$(ls -A src/components/ui 2>/dev/null)" ]; then
  echo "  src/components/ui/ already populated (cloned repo) — skipping shadcn add"
else
  npx shadcn@latest add button card input label form dialog dropdown-menu \
    avatar badge progress table tabs sonner alert skeleton separator sheet \
    select textarea -y
fi

echo ""
echo -e "${BLUE}Step 4/4: Creating environment file...${NC}"
if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "  Created .env.local from .env.example"
else
  echo "  .env.local already exists — skipping"
fi

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit .env.local with your actual API keys and domain"
echo "2. Expose the backend:  kubectl port-forward svc/saas-backend 8000:8000 -n ca-system"
echo "3. Start the portal:    npm run dev"
echo ""
echo -e "${BLUE}Helpful commands:${NC}"
echo "  npm run dev        - Start development server (http://localhost:3000)"
echo "  npm run build      - Build for production"
echo "  npm run lint       - Run ESLint"
echo ""
echo "Happy coding! 🎨"
