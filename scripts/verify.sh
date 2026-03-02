#!/bin/bash
#
# ⬢ Synapse - Verification Script v2.7.0
#
# Comprehensive verification tool for the Synapse project.
# Run before committing to ensure all checks pass.
#
# Usage:
#   ./scripts/verify.sh              # Full verification (default)
#   ./scripts/verify.sh --quick      # Skip build, fast tests only
#   ./scripts/verify.sh --backend    # Backend tests only
#   ./scripts/verify.sh --frontend   # Frontend tests only
#   ./scripts/verify.sh --unit       # Unit tests only (fastest)
#   ./scripts/verify.sh --integration # Integration tests only
#   ./scripts/verify.sh --lint       # Lint/architecture tests only
#   ./scripts/verify.sh --help       # Show help
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
DIM='\033[2m'
NC='\033[0m'

# Default modes
RUN_BACKEND=true
RUN_FRONTEND=true
RUN_TYPES=true
RUN_BUILD=true
RUN_AVATAR=true
RUN_E2E=false
QUICK_MODE=false
VERBOSE=false

# Test filters — external tests (real CDN/API) excluded by default
PYTEST_MARKERS="not smoke and not external"
PYTEST_PATHS="tests/"

# ============================================================================
# Help
# ============================================================================

show_help() {
    echo -e "${MAGENTA}⬢ Synapse Verification Script${NC}"
    echo ""
    echo -e "${BOLD}Usage:${NC}"
    echo "  ./scripts/verify.sh [OPTIONS]"
    echo ""
    echo -e "${BOLD}Options:${NC}"
    echo "  --help, -h        Show this help message"
    echo "  --quick, -q       Quick mode: skip build, exclude slow tests"
    echo "  --verbose, -v     Verbose output (show all test details)"
    echo ""
    echo -e "${BOLD}Scope Options:${NC}"
    echo "  --backend, -b     Run only backend (Python) tests"
    echo "  --frontend, -f    Run only frontend (TypeScript) tests"
    echo "  --all, -a         Run all checks (default)"
    echo ""
    echo -e "${BOLD}Backend Test Filters:${NC}"
    echo "  --unit            Run only unit tests (tests/unit/)"
    echo "  --integration     Run only integration tests (tests/integration/)"
    echo "  --store           Run only store tests (tests/store/)"
    echo "  --lint            Run only lint/architecture tests (tests/lint/)"
    echo "  --smoke           Run offline smoke tests (CDN/proxy pipeline)"
    echo "  --smoke-live      Run all smoke tests including live CDN"
    echo "  --no-slow         Exclude tests marked @pytest.mark.slow"
    echo "  --external        Include external tests (real CDN/API calls)"
    echo "  --full            Run ALL tests (external + slow + smoke)"
    echo "  --avatar          Run only avatar-engine version checks"
    echo "  --no-avatar       Skip avatar-engine version checks"
    echo "  --e2e             Run Playwright E2E tests (requires running servers)"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  ./scripts/verify.sh                    # Standard CI (no external)"
    echo "  ./scripts/verify.sh --quick            # Fast verification"
    echo "  ./scripts/verify.sh --external         # Include real CDN/API tests"
    echo "  ./scripts/verify.sh --full             # ALL tests (pre-release)"
    echo "  ./scripts/verify.sh --backend --unit   # Only Python unit tests"
    echo "  ./scripts/verify.sh -b --no-slow       # Backend without slow tests"
    echo "  ./scripts/verify.sh --lint             # Architecture checks only"
    echo ""
    echo -e "${BOLD}Test Structure:${NC}"
    echo "  tests/"
    echo "  ├── unit/           # Fast, isolated tests"
    echo "  │   ├── core/       # src/core/ tests"
    echo "  │   ├── clients/    # src/clients/ tests"
    echo "  │   └── utils/      # src/utils/ tests"
    echo "  ├── store/          # Store/API tests"
    echo "  ├── integration/    # Multi-component tests"
    echo "  └── lint/           # Architecture enforcement"
    echo ""
    echo -e "${BOLD}Pytest Markers:${NC}"
    echo "  @pytest.mark.slow         # Long-running tests"
    echo "  @pytest.mark.integration  # Require multiple components"
    echo "  @pytest.mark.external     # Real external services (excluded by default)"
    echo "  @pytest.mark.civitai      # Civitai API related (subset of external)"
    echo ""
}

# ============================================================================
# Parse Arguments
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --quick|-q)
            QUICK_MODE=true
            RUN_BUILD=false
            PYTEST_MARKERS="not slow and not smoke and not external"
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --backend|-b)
            RUN_BACKEND=true
            RUN_FRONTEND=false
            RUN_TYPES=false
            RUN_BUILD=false
            shift
            ;;
        --frontend|-f)
            RUN_BACKEND=false
            RUN_FRONTEND=true
            RUN_TYPES=true
            RUN_BUILD=true
            shift
            ;;
        --all|-a)
            RUN_BACKEND=true
            RUN_FRONTEND=true
            RUN_TYPES=true
            RUN_BUILD=true
            shift
            ;;
        --unit)
            PYTEST_PATHS="tests/unit/"
            shift
            ;;
        --integration)
            PYTEST_PATHS="tests/integration/"
            shift
            ;;
        --store)
            PYTEST_PATHS="tests/store/"
            shift
            ;;
        --lint)
            PYTEST_PATHS="tests/lint/"
            shift
            ;;
        --smoke)
            PYTEST_PATHS="tests/smoke/"
            PYTEST_MARKERS="not live"
            RUN_BACKEND=true
            RUN_FRONTEND=false
            RUN_TYPES=false
            RUN_BUILD=false
            shift
            ;;
        --smoke-live)
            PYTEST_PATHS="tests/smoke/"
            PYTEST_MARKERS=""
            RUN_BACKEND=true
            RUN_FRONTEND=false
            RUN_TYPES=false
            RUN_BUILD=false
            shift
            ;;
        --no-slow)
            if [ -z "$PYTEST_MARKERS" ]; then
                PYTEST_MARKERS="not slow"
            else
                PYTEST_MARKERS="$PYTEST_MARKERS and not slow"
            fi
            shift
            ;;
        --avatar)
            RUN_AVATAR=true
            RUN_BACKEND=false
            RUN_FRONTEND=false
            RUN_TYPES=false
            RUN_BUILD=false
            shift
            ;;
        --no-avatar)
            RUN_AVATAR=false
            shift
            ;;
        --e2e)
            RUN_E2E=true
            shift
            ;;
        --external)
            # Include external tests (real CDN/API calls)
            PYTEST_MARKERS="not smoke"
            shift
            ;;
        --full)
            # Run ALL tests including external, slow, smoke
            PYTEST_MARKERS=""
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ============================================================================
# Header
# ============================================================================

echo -e "${MAGENTA}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║   ⬢ Synapse - Verification Script v2.7.0                          ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "${CYAN}Project root: $PROJECT_ROOT${NC}"

# Show active modes
echo -e "${DIM}Modes: backend=$RUN_BACKEND frontend=$RUN_FRONTEND build=$RUN_BUILD${NC}"
if [ "$QUICK_MODE" == true ]; then
    echo -e "${YELLOW}Quick mode enabled${NC}"
fi
if [ -n "$PYTEST_MARKERS" ]; then
    echo -e "${DIM}Pytest markers: $PYTEST_MARKERS${NC}"
fi
if [ "$PYTEST_PATHS" != "tests/" ]; then
    echo -e "${DIM}Test path: $PYTEST_PATHS${NC}"
fi
echo ""

FAILED=0
WARNINGS=0
STEP=0
TOTAL_STEPS=0

# Calculate total steps
[ "$RUN_AVATAR" == true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))   # avatar version check
[ "$RUN_BACKEND" == true ] && TOTAL_STEPS=$((TOTAL_STEPS + 2))  # env + tests
[ "$RUN_FRONTEND" == true ] && TOTAL_STEPS=$((TOTAL_STEPS + 2)) # env + tests
[ "$RUN_TYPES" == true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$RUN_BUILD" == true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$RUN_E2E" == true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))

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

check_skipped() {
    echo -e "${DIM}  ○ $1 (skipped)${NC}"
}

next_step() {
    STEP=$((STEP + 1))
    echo -e "${BOLD}[$STEP/$TOTAL_STEPS] $1${NC}"
}

# ============================================================================
# Avatar Engine Version Check
# ============================================================================

if [ "$RUN_AVATAR" == true ]; then

    next_step "Avatar Engine Version Check"

    # Python avatar-engine
    if command -v uv &> /dev/null; then
        AE_PY_VERSION=$(uv run python -c "
try:
    import avatar_engine
    print(getattr(avatar_engine, '__version__', 'unknown'))
except ImportError:
    print('not_installed')
" 2>/dev/null || echo "error")
    else
        AE_PY_VERSION="error"
    fi

    if [ "$AE_PY_VERSION" == "not_installed" ]; then
        check_warning "Python avatar-engine: not installed"
    elif [ "$AE_PY_VERSION" == "error" ] || [ "$AE_PY_VERSION" == "unknown" ]; then
        check_warning "Python avatar-engine: version unknown"
    else
        check_passed "Python avatar-engine: v${AE_PY_VERSION}"
    fi

    # npm packages — check they're from registry (not link:)
    if [ -f "apps/web/pnpm-lock.yaml" ]; then
        if grep -q "'@avatar-engine.*link:" apps/web/pnpm-lock.yaml 2>/dev/null; then
            check_failed "npm @avatar-engine packages use link: — should be from registry"
        else
            # Extract versions from lockfile (pnpm hoisted store may not expose require())
            NPM_AE_CORE=$(grep -oP '@avatar-engine/core@\K[0-9]+\.[0-9]+\.[0-9]+' apps/web/pnpm-lock.yaml 2>/dev/null | head -1 || echo "unknown")
            NPM_AE_REACT=$(grep -oP '@avatar-engine/react@\K[0-9]+\.[0-9]+\.[0-9]+' apps/web/pnpm-lock.yaml 2>/dev/null | head -1 || echo "unknown")
            check_passed "@avatar-engine/core: v${NPM_AE_CORE}, @avatar-engine/react: v${NPM_AE_REACT}"
        fi
    else
        check_warning "No pnpm-lock.yaml found — skipping npm avatar check"
    fi

    echo ""
fi

# ============================================================================
# Backend Checks
# ============================================================================

if [ "$RUN_BACKEND" == true ]; then

    # 1. Python Environment
    next_step "Checking Python Environment"

    # Find Python - prefer uv, then venv, then system
    if command -v uv &> /dev/null; then
        PYTHON_CMD="uv run python"
        PYTEST_CMD="uv run pytest"
        check_passed "Using uv (recommended)"
    elif [ -f ".venv/bin/python" ]; then
        PYTHON_CMD=".venv/bin/python"
        PYTEST_CMD=".venv/bin/pytest"
        check_passed "Using virtual environment: .venv"
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        PYTEST_CMD="python3 -m pytest"
        check_warning "Using system Python (consider using uv or .venv)"
    else
        check_failed "Python not found"
        exit 1
    fi

    # Check pytest is available
    if $PYTEST_CMD --version &> /dev/null; then
        check_passed "pytest available"
    else
        check_failed "pytest not installed"
    fi
    echo ""

    # 2. Backend Tests
    next_step "Running Backend Tests"

    # Build pytest command
    PYTEST_ARGS="$PYTEST_PATHS --tb=short"

    if [ "$VERBOSE" == true ]; then
        PYTEST_ARGS="$PYTEST_ARGS -v"
    else
        PYTEST_ARGS="$PYTEST_ARGS -q"
    fi

    if [ -n "$PYTEST_MARKERS" ]; then
        PYTEST_ARGS="$PYTEST_ARGS -m \"$PYTEST_MARKERS\""
    fi

    echo -e "${DIM}Running: pytest $PYTEST_ARGS${NC}"

    if eval "$PYTEST_CMD $PYTEST_ARGS"; then
        check_passed "Backend tests passed"
    else
        check_failed "Backend tests FAILED"
    fi
    echo ""
fi

# ============================================================================
# Frontend Checks
# ============================================================================

if [ "$RUN_FRONTEND" == true ] || [ "$RUN_TYPES" == true ] || [ "$RUN_BUILD" == true ]; then

    if [ ! -d "apps/web" ]; then
        check_failed "Frontend directory not found: apps/web"
        exit 1
    fi

    cd apps/web

    # Check package manager
    if command -v pnpm &> /dev/null; then
        PKG_MANAGER="pnpm"
    elif command -v npm &> /dev/null; then
        PKG_MANAGER="npm"
    else
        check_failed "No package manager found (pnpm or npm)"
        exit 1
    fi

    # Check node_modules
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing dependencies...${NC}"
        $PKG_MANAGER install --silent
    fi
fi

if [ "$RUN_FRONTEND" == true ]; then

    # 3. Frontend Environment
    next_step "Checking Frontend Environment"
    check_passed "Using $PKG_MANAGER"
    check_passed "node_modules ready"
    echo ""

    # 4. Frontend Tests
    next_step "Running Frontend Tests"

    # Run tests in CI mode (not watch mode)
    if [ "$PKG_MANAGER" == "pnpm" ]; then
        TEST_CMD="$PKG_MANAGER test --run"
    else
        TEST_CMD="$PKG_MANAGER test -- --run"
    fi

    if [ "$VERBOSE" == true ]; then
        if $TEST_CMD; then
            check_passed "Frontend tests passed"
        else
            check_failed "Frontend tests FAILED"
        fi
    else
        if $TEST_CMD > /dev/null 2>&1; then
            check_passed "Frontend tests passed"
        else
            check_failed "Frontend tests FAILED"
            echo -e "${YELLOW}Running again to show errors:${NC}"
            $TEST_CMD
        fi
    fi
    echo ""
fi

if [ "$RUN_TYPES" == true ]; then

    # 5. TypeScript Type Check
    next_step "TypeScript Type Check"

    if [ "$VERBOSE" == true ]; then
        if npx tsc --noEmit; then
            check_passed "TypeScript types OK"
        else
            check_failed "TypeScript type errors found"
        fi
    else
        if npx tsc --noEmit 2>&1 > /dev/null; then
            check_passed "TypeScript types OK"
        else
            check_failed "TypeScript type errors found"
            echo -e "${YELLOW}Running again to show errors:${NC}"
            npx tsc --noEmit
        fi
    fi
    echo ""
fi

if [ "$RUN_BUILD" == true ]; then

    # 6. Frontend Build
    next_step "Building Frontend"

    if [ "$VERBOSE" == true ]; then
        if $PKG_MANAGER run build; then
            check_passed "Frontend build passed"
        else
            check_failed "Frontend build FAILED"
        fi
    else
        if $PKG_MANAGER run build > /dev/null 2>&1; then
            check_passed "Frontend build passed"
        else
            check_failed "Frontend build FAILED"
            echo -e "${YELLOW}Running again to show errors:${NC}"
            $PKG_MANAGER run build
        fi
    fi
    echo ""
fi

cd "$PROJECT_ROOT"

# ============================================================================
# E2E Tests (Playwright)
# ============================================================================

if [ "$RUN_E2E" == true ]; then

    next_step "Running E2E Tests (Playwright)"

    if [ ! -d "apps/web" ]; then
        check_failed "Frontend directory not found: apps/web"
    else
        cd apps/web
        # Run Tier 1 only (exclude @live tests)
        E2E_CMD="npx playwright test --grep-invert @live"
        if [ "$VERBOSE" == true ]; then
            if $E2E_CMD; then
                check_passed "E2E tests passed"
            else
                check_failed "E2E tests FAILED"
            fi
        else
            if $E2E_CMD > /dev/null 2>&1; then
                check_passed "E2E tests passed"
            else
                check_failed "E2E tests FAILED"
                echo -e "${YELLOW}Running again to show errors:${NC}"
                $E2E_CMD
            fi
        fi
        cd "$PROJECT_ROOT"
    fi
    echo ""
fi

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
    echo ""
    echo -e "${CYAN}Tip: Use --verbose for detailed output${NC}"
    exit 1
fi
