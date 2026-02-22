#!/bin/bash
#
# CDN/Proxy/Search Pipeline Smoke Tests Runner
#
# Usage:
#   ./tests/smoke/run_smoke_tests.sh              # All tests
#   ./tests/smoke/run_smoke_tests.sh --offline     # Only offline (Group 1)
#   ./tests/smoke/run_smoke_tests.sh --live        # Only live CDN (Groups 2-5)
#   ./tests/smoke/run_smoke_tests.sh --group N     # Specific group (1-5)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
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

# Defaults
MODE="all"
GROUP=""

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --offline)
            MODE="offline"
            shift
            ;;
        --live)
            MODE="live"
            shift
            ;;
        --group)
            GROUP="$2"
            shift 2
            ;;
        --help|-h)
            echo -e "${MAGENTA}CDN/Proxy/Search Smoke Tests${NC}"
            echo ""
            echo "Usage:"
            echo "  ./tests/smoke/run_smoke_tests.sh              # All tests"
            echo "  ./tests/smoke/run_smoke_tests.sh --offline     # Only offline (Group 1)"
            echo "  ./tests/smoke/run_smoke_tests.sh --live        # Only live CDN tests"
            echo "  ./tests/smoke/run_smoke_tests.sh --group N     # Specific group (1-5)"
            echo ""
            echo "Groups:"
            echo "  1  URL Construction (offline, <1s)"
            echo "  2  CDN Direct Fetch (live, 15-30s)"
            echo "  3  Proxy Endpoint (live, 10-30s)"
            echo "  4  Search Pipeline (mixed, 5-15s)"
            echo "  5  Juggernaut XL E2E (live+slow, 30-60s)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

FAILED=0

run_group() {
    local num=$1
    local name=$2
    local file=$3
    local extra_args=$4

    echo ""
    echo -e "${MAGENTA}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  Group ${num}: ${name}${NC}"
    echo -e "${MAGENTA}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""

    if uv run pytest "tests/smoke/${file}" -v --tb=long -s $extra_args; then
        echo -e "${GREEN}  ✓ Group ${num} passed${NC}"
    else
        echo -e "${RED}  ✗ Group ${num} FAILED${NC}"
        FAILED=1
    fi
}

echo -e "${MAGENTA}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║  CDN/Proxy/Search Pipeline — Smoke Tests                         ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

if [ -n "$GROUP" ]; then
    case $GROUP in
        1) run_group 1 "URL Construction (offline)" "test_01_url_construction.py" "" ;;
        2) run_group 2 "CDN Direct Fetch (live)" "test_02_cdn_direct.py" "" ;;
        3) run_group 3 "Proxy Endpoint" "test_03_proxy_endpoint.py" "" ;;
        4) run_group 4 "Search Pipeline" "test_04_search_pipeline.py" "" ;;
        5) run_group 5 "Juggernaut XL E2E (slow)" "test_05_juggernaut_e2e.py" "" ;;
        *) echo -e "${RED}Invalid group: $GROUP (use 1-5)${NC}"; exit 1 ;;
    esac
elif [ "$MODE" == "offline" ]; then
    run_group 1 "URL Construction (offline)" "test_01_url_construction.py" ""
elif [ "$MODE" == "live" ]; then
    run_group 2 "CDN Direct Fetch (live)" "test_02_cdn_direct.py" ""
    run_group 3 "Proxy Endpoint" "test_03_proxy_endpoint.py" ""
    run_group 4 "Search Pipeline" "test_04_search_pipeline.py" "-m live"
    run_group 5 "Juggernaut XL E2E (slow)" "test_05_juggernaut_e2e.py" ""
else
    # All groups
    run_group 1 "URL Construction (offline)" "test_01_url_construction.py" ""
    run_group 2 "CDN Direct Fetch (live)" "test_02_cdn_direct.py" ""
    run_group 3 "Proxy Endpoint" "test_03_proxy_endpoint.py" ""
    run_group 4 "Search Pipeline" "test_04_search_pipeline.py" ""
    run_group 5 "Juggernaut XL E2E (slow)" "test_05_juggernaut_e2e.py" ""
fi

echo ""
echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════════════╗${NC}"
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}║  ✓ All smoke tests passed!                                        ║${NC}"
else
    echo -e "${RED}║  ✗ Some smoke tests FAILED                                        ║${NC}"
fi
echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════════════╝${NC}"

exit $FAILED
