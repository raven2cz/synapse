#!/bin/bash
# Synapse Web Server Diagnostics
# Run this script to identify startup issues

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "=============================================="
echo "  Synapse Web Server Diagnostics"
echo "=============================================="
echo ""

# Find project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$SCRIPT_DIR" == *"/scripts" ]]; then
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi

WEB_DIR="$PROJECT_ROOT/apps/web"

if [ ! -d "$WEB_DIR" ]; then
    echo -e "${RED}ERROR: Web directory not found: $WEB_DIR${NC}"
    exit 1
fi

cd "$WEB_DIR"
echo -e "${CYAN}Working directory: $(pwd)${NC}"
echo ""

# 1. Check node_modules
echo -e "${CYAN}[1/5] Checking node_modules...${NC}"
if [ -d "node_modules" ]; then
    echo -e "${GREEN}  ✓ node_modules exists${NC}"
else
    echo -e "${RED}  ✗ node_modules MISSING - run 'npm install'${NC}"
    exit 1
fi
echo ""

# 2. Check TypeScript compilation
echo -e "${CYAN}[2/5] Checking TypeScript compilation...${NC}"
if npx tsc --noEmit 2>&1 | head -20; then
    echo -e "${GREEN}  ✓ TypeScript compilation passed${NC}"
else
    echo -e "${RED}  ✗ TypeScript compilation FAILED${NC}"
    echo -e "${YELLOW}  Full error output:${NC}"
    npx tsc --noEmit 2>&1
    exit 1
fi
echo ""

# 3. Check Vite config
echo -e "${CYAN}[3/5] Checking Vite configuration...${NC}"
if [ -f "vite.config.ts" ]; then
    echo -e "${GREEN}  ✓ vite.config.ts exists${NC}"
else
    echo -e "${RED}  ✗ vite.config.ts MISSING${NC}"
    exit 1
fi
echo ""

# 4. Check key imports
echo -e "${CYAN}[4/5] Checking key imports...${NC}"
echo "  Checking settingsStore..."
if [ -f "src/stores/settingsStore.ts" ]; then
    echo -e "${GREEN}  ✓ settingsStore.ts exists${NC}"
    if grep -q "zustand" "src/stores/settingsStore.ts"; then
        echo -e "${GREEN}  ✓ settingsStore uses zustand${NC}"
    else
        echo -e "${RED}  ✗ settingsStore does NOT use zustand - this is a problem!${NC}"
        echo -e "${YELLOW}    Your settingsStore may have been overwritten by a mock.${NC}"
        echo -e "${YELLOW}    Please restore the original settingsStore.ts${NC}"
    fi
else
    echo -e "${RED}  ✗ settingsStore.ts MISSING${NC}"
fi
echo ""

# 5. Try to start dev server with visible output
echo -e "${CYAN}[5/5] Starting Vite dev server (with full output)...${NC}"
echo -e "${YELLOW}  Press Ctrl+C to stop${NC}"
echo ""

npm run dev
