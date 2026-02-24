#!/bin/bash
#
# Avatar Engine Upgrade Script
#
# Upgrades avatar-engine on both Python (PyPI) and JavaScript (npm) sides,
# then verifies the build and prints a version summary.
#
# Usage:
#   ./scripts/avatar-upgrade.sh          # Upgrade + verify
#   ./scripts/avatar-upgrade.sh --check  # Just print current versions
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
    CHECK_ONLY=true
fi

echo -e "${CYAN}${BOLD}⬢ Avatar Engine Upgrade${NC}"
echo ""

# ── Current versions ─────────────────────────────────────────────────

echo -e "${BOLD}Current versions:${NC}"

# Python
PY_VERSION=$(uv run python -c "
try:
    import avatar_engine
    print(getattr(avatar_engine, '__version__', 'unknown'))
except ImportError:
    print('not installed')
" 2>/dev/null || echo "error")
echo -e "  Python avatar-engine:     ${CYAN}${PY_VERSION}${NC}"

# npm (extract from lockfile — pnpm hoisted store may not expose require())
if [ -f "apps/web/pnpm-lock.yaml" ]; then
    NPM_CORE=$(grep -oP '@avatar-engine/core@\K[0-9]+\.[0-9]+\.[0-9]+' apps/web/pnpm-lock.yaml 2>/dev/null | head -1 || echo "unknown")
    NPM_REACT=$(grep -oP '@avatar-engine/react@\K[0-9]+\.[0-9]+\.[0-9]+' apps/web/pnpm-lock.yaml 2>/dev/null | head -1 || echo "unknown")
else
    NPM_CORE="no lockfile"
    NPM_REACT="no lockfile"
fi
echo -e "  @avatar-engine/core:      ${CYAN}${NPM_CORE}${NC}"
echo -e "  @avatar-engine/react:     ${CYAN}${NPM_REACT}${NC}"

# Check for link: in lockfile
if [ -f "apps/web/pnpm-lock.yaml" ]; then
    if grep -q "'@avatar-engine.*link:" apps/web/pnpm-lock.yaml 2>/dev/null; then
        echo -e "  ${YELLOW}⚠ npm packages are using link: (not from registry)${NC}"
    fi
fi

echo ""

if [ "$CHECK_ONLY" = true ]; then
    exit 0
fi

# ── Upgrade Python ───────────────────────────────────────────────────

echo -e "${BOLD}[1/4] Upgrading Python avatar-engine...${NC}"
if uv pip install --upgrade "avatar-engine[web]" 2>&1; then
    echo -e "${GREEN}  ✓ Python package upgraded${NC}"
else
    echo -e "${RED}  ✗ Python upgrade failed${NC}"
    exit 1
fi
echo ""

# ── Upgrade npm ──────────────────────────────────────────────────────

echo -e "${BOLD}[2/4] Upgrading npm @avatar-engine packages...${NC}"
cd apps/web
if pnpm update @avatar-engine/react @avatar-engine/core 2>&1; then
    echo -e "${GREEN}  ✓ npm packages upgraded${NC}"
else
    echo -e "${RED}  ✗ npm upgrade failed${NC}"
    exit 1
fi
cd "$PROJECT_ROOT"
echo ""

# ── Verify build ─────────────────────────────────────────────────────

echo -e "${BOLD}[3/4] Verifying frontend build...${NC}"
cd apps/web
if pnpm build > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ Frontend build passed${NC}"
else
    echo -e "${RED}  ✗ Frontend build failed${NC}"
    echo -e "${YELLOW}  Run 'cd apps/web && pnpm build' for details${NC}"
    exit 1
fi
cd "$PROJECT_ROOT"
echo ""

# ── Verify tests ─────────────────────────────────────────────────────

echo -e "${BOLD}[4/4] Running quick tests...${NC}"
cd apps/web
if pnpm test --run > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ Frontend tests passed${NC}"
else
    echo -e "${YELLOW}  ⚠ Some frontend tests failed — check with 'cd apps/web && pnpm test --run'${NC}"
fi
cd "$PROJECT_ROOT"
echo ""

# ── Summary ──────────────────────────────────────────────────────────

echo -e "${BOLD}Updated versions:${NC}"

PY_VERSION_NEW=$(uv run python -c "
try:
    import avatar_engine
    print(getattr(avatar_engine, '__version__', 'unknown'))
except ImportError:
    print('not installed')
" 2>/dev/null || echo "error")
if [ -f "apps/web/pnpm-lock.yaml" ]; then
    NPM_CORE_NEW=$(grep -oP '@avatar-engine/core@\K[0-9]+\.[0-9]+\.[0-9]+' apps/web/pnpm-lock.yaml 2>/dev/null | head -1 || echo "unknown")
    NPM_REACT_NEW=$(grep -oP '@avatar-engine/react@\K[0-9]+\.[0-9]+\.[0-9]+' apps/web/pnpm-lock.yaml 2>/dev/null | head -1 || echo "unknown")
else
    NPM_CORE_NEW="no lockfile"
    NPM_REACT_NEW="no lockfile"
fi

echo -e "  Python avatar-engine:     ${PY_VERSION} → ${GREEN}${PY_VERSION_NEW}${NC}"
echo -e "  @avatar-engine/core:      ${NPM_CORE} → ${GREEN}${NPM_CORE_NEW}${NC}"
echo -e "  @avatar-engine/react:     ${NPM_REACT} → ${GREEN}${NPM_REACT_NEW}${NC}"
echo ""
echo -e "${GREEN}${BOLD}✓ Avatar Engine upgrade complete${NC}"
