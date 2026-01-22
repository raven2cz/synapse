#!/bin/bash
#
# ⬢ Synapse - Verification Script
#
# Run this before committing to ensure all checks pass.
# Tests backend, frontend, TypeScript types, and code quality.
#
# Usage: ./scripts/verify.sh
#        ./scripts/verify.sh --quick    # Skip slow checks (build)
#

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# Parse arguments
QUICK_MODE=false
if [ "$1" == "--quick" ] || [ "$1" == "-q" ]; then
    QUICK_MODE=true
fi

echo -e "${MAGENTA}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║   ⬢ Synapse - Verification Script                                 ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "${CYAN}Project root: $PROJECT_ROOT${NC}"
if [ "$QUICK_MODE" == true ]; then
    echo -e "${YELLOW}Quick mode: Skipping build${NC}"
fi
echo ""

FAILED=0
WARNINGS=0

# ============================================================================
# Helper Functions
# ============================================================================

check_passed() {
    echo -e "${GREEN}  ✓ $1${NC}"
}

check_failed() {
    echo -e "${RED}  ✗ $1${NC}"
    FAILED=1
}

check_warning() {
    echo -e "${YELLOW}  ! $1${NC}"
    WARNINGS=$((WARNINGS + 1))
}

# ============================================================================
# 1. Python Environment Check
# ============================================================================

echo -e "${BOLD}[1/6] Checking Python Environment${NC}"

# Find Python - prefer venv
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
    check_passed "Using virtual environment: .venv"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
    check_warning "Using system Python (consider using .venv)"
else
    check_failed "Python not found"
    echo -e "${RED}Cannot continue without Python.${NC}"
    exit 1
fi

# Check pytest is available
if $PYTHON -c "import pytest" 2>/dev/null; then
    check_passed "pytest available"
else
    check_failed "pytest not installed. Run: $PYTHON -m pip install pytest"
fi
echo ""

# ============================================================================
# 2. Backend Tests
# ============================================================================

echo -e "${BOLD}[2/6] Running Backend Tests${NC}"

$PYTHON -m pytest tests/ --tb=short -q
if [ $? -eq 0 ]; then
    check_passed "Backend tests passed"
else
    check_failed "Backend tests FAILED"
fi
echo ""

# ============================================================================
# 3. Frontend Environment Check
# ============================================================================

echo -e "${BOLD}[3/6] Checking Frontend Environment${NC}"

if [ ! -d "apps/web" ]; then
    check_failed "Frontend directory not found: apps/web"
    exit 1
fi

cd apps/web

# Check pnpm/npm
if command -v pnpm &> /dev/null; then
    PKG_MANAGER="pnpm"
    check_passed "Using pnpm"
elif command -v npm &> /dev/null; then
    PKG_MANAGER="npm"
    check_warning "pnpm not found, using npm (consider installing pnpm)"
else
    check_failed "No package manager found (pnpm or npm)"
    exit 1
fi

# Check node_modules
if [ ! -d "node_modules" ]; then
    check_warning "node_modules not found. Installing..."
    $PKG_MANAGER install --silent
fi
check_passed "node_modules ready"
echo ""

# ============================================================================
# 4. Frontend Tests
# ============================================================================

echo -e "${BOLD}[4/6] Running Frontend Tests${NC}"

# Run tests in CI mode (not watch mode)
if [ "$PKG_MANAGER" == "pnpm" ]; then
    $PKG_MANAGER test --run
else
    $PKG_MANAGER test -- --run
fi
if [ $? -eq 0 ]; then
    check_passed "Frontend tests passed"
else
    check_failed "Frontend tests FAILED"
fi
echo ""

# ============================================================================
# 5. TypeScript Type Check
# ============================================================================

echo -e "${BOLD}[5/6] TypeScript Type Check${NC}"

npx tsc --noEmit 2>&1
if [ $? -eq 0 ]; then
    check_passed "TypeScript types OK"
else
    check_failed "TypeScript type errors found"
fi
echo ""

# ============================================================================
# 6. Frontend Build (skip in quick mode)
# ============================================================================

if [ "$QUICK_MODE" == false ]; then
    echo -e "${BOLD}[6/6] Building Frontend${NC}"

    $PKG_MANAGER run build > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        check_passed "Frontend build passed"
    else
        check_failed "Frontend build FAILED"
        echo -e "${YELLOW}Running build again to show errors:${NC}"
        $PKG_MANAGER run build
    fi
    echo ""
else
    echo -e "${BOLD}[6/6] Building Frontend${NC}"
    check_warning "Skipped (quick mode)"
    echo ""
fi

cd "$PROJECT_ROOT"

# ============================================================================
# Summary
# ============================================================================

echo ""
echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════════════╗${NC}"
if [ "$FAILED" -eq 0 ]; then
    if [ "$WARNINGS" -eq 0 ]; then
        echo -e "${GREEN}║  ✓ All checks passed! Ready to commit.                             ║${NC}"
    else
        echo -e "${YELLOW}║  ✓ Checks passed with $WARNINGS warning(s). Review above.              ║${NC}"
    fi
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}║  ✗ Some checks FAILED. Please fix before committing.               ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
