#!/bin/bash
# Synapse v2 - Pre-commit verification script
# Run this before committing to ensure all checks pass

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Go to project root (parent of scripts/)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=============================================="
echo "  Synapse v2 - Pre-commit Verification"
echo "  Project root: $PROJECT_ROOT"
echo "=============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0

# 1. Backend Tests
echo "=== [1/3] Running Backend Tests ==="
if python -m pytest tests/ -v --tb=short; then
    echo -e "${GREEN}✓ Backend tests passed${NC}"
else
    echo -e "${RED}✗ Backend tests FAILED${NC}"
    FAILED=1
fi
echo ""

# 2. Frontend Build
echo "=== [2/3] Building Frontend ==="
if [ -d "apps/web" ]; then
    cd apps/web
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}! node_modules not found. Running npm install...${NC}"
        if npm install > /dev/null 2>&1; then
            echo -e "${GREEN}✓ npm install completed${NC}"
        else
            echo -e "${RED}✗ npm install FAILED${NC}"
            echo -e "${YELLOW}  Please run 'cd apps/web && npm install' manually${NC}"
            FAILED=1
            cd "$PROJECT_ROOT"
        fi
    fi
    
    # Run build only if we haven't already failed
    if [ "$FAILED" -eq 0 ] || [ -d "node_modules" ]; then
        if npm run build > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Frontend build passed${NC}"
        else
            echo -e "${RED}✗ Frontend build FAILED${NC}"
            npm run build  # Run again to show errors
            FAILED=1
        fi
    fi
    
    cd "$PROJECT_ROOT"
else
    echo -e "${RED}✗ Frontend directory not found: apps/web${NC}"
    FAILED=1
fi
echo ""

# 3. Legacy API Check
echo "=== [3/3] Checking for Legacy APIs ==="
LEGACY=$(grep -rn "/api/comfyui" --include="*.py" --include="*.ts" --include="*.tsx" . 2>/dev/null | grep -v node_modules | grep -v "test_api" | wc -l)
if [ "$LEGACY" -eq 0 ]; then
    echo -e "${GREEN}✓ No legacy /api/comfyui references found${NC}"
else
    echo -e "${RED}✗ Found $LEGACY legacy /api/comfyui references!${NC}"
    grep -rn "/api/comfyui" --include="*.py" --include="*.ts" --include="*.tsx" . 2>/dev/null | grep -v node_modules | grep -v "test_api"
    FAILED=1
fi
echo ""

# Summary
echo "=============================================="
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}All checks passed! Ready to commit.${NC}"
    exit 0
else
    echo -e "${RED}Some checks FAILED. Please fix before committing.${NC}"
    exit 1
fi
