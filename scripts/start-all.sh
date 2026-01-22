#!/bin/bash
#
# ⬢ Synapse - Start All Services
#
# Pack-first model manager for generative UIs
# Unified hub for ComfyUI, Forge/Forge-Neo, A1111, and SD.Next
#
# Usage: ./scripts/start-all.sh
#

set -e

VERSION="2.6.0"
API_PORT=8000
WEB_PORT=5173

# Colors
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
MAGENTA=$'\033[0;35m'
BOLD_MAGENTA=$'\033[1;35m'
BOLD=$'\033[1m'
NC=$'\033[0m'

# Synapse icon
HEX_ICON="⬢"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${MAGENTA}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║  ███████╗██╗   ██╗███╗   ██╗ █████╗ ██████╗ ███████╗███████╗       ║"
echo "║  ██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝       ║"
echo "║  ███████╗ ╚████╔╝ ██╔██╗ ██║███████║██████╔╝███████╗█████╗         ║"
echo "║  ╚════██║  ╚██╔╝  ██║╚██╗██║██╔══██║██╔═══╝ ╚════██║██╔══╝         ║"
echo "║  ███████║   ██║   ██║ ╚████║██║  ██║██║     ███████║███████╗       ║"
echo "║  ╚══════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝       ║"
echo "║                                                                    ║"
echo "║            ${BOLD_MAGENTA}⬢${MAGENTA} Synapse: Pack-First Model Manager v${VERSION}              ║"
echo "║          ComfyUI • Forge/Forge-Neo • A1111 • SD.Next               ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# Prerequisites Check
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Checking prerequisites...${NC}"

# Check uv (preferred) or pip
USE_UV=false
if command -v uv &> /dev/null; then
    echo -e "${GREEN}  ✓ uv: $(uv --version)${NC}"
    USE_UV=true
elif command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}  ! uv not found, using pip3${NC}"
    echo -e "${GREEN}  ✓ pip3: $(pip3 --version | head -c 20)${NC}"
else
    echo -e "${RED}  ✗ Neither uv nor pip3 found${NC}"
    echo "  Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}  ✓ Python: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}  ✗ Python 3 not found${NC}"
    exit 1
fi

# Check Node.js
if command -v node &> /dev/null; then
    echo -e "${GREEN}  ✓ Node.js: $(node --version)${NC}"
else
    echo -e "${RED}  ✗ Node.js not found${NC}"
    exit 1
fi

# Check npm
if command -v npm &> /dev/null; then
    echo -e "${GREEN}  ✓ npm: $(npm --version)${NC}"
else
    echo -e "${RED}  ✗ npm not found${NC}"
    exit 1
fi

echo ""

# ============================================================================
# Python Environment Setup
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Setting up Python environment...${NC}"

# Clear Python cache to avoid stale bytecode
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo -e "${GREEN}  ✓ Cache cleared${NC}"

if [ "$USE_UV" = true ]; then
    # Using uv
    if [ ! -d ".venv" ]; then
        echo -e "${YELLOW}  Creating virtual environment with uv...${NC}"
        uv venv --python 3.11 .venv 2>/dev/null || uv venv .venv
    fi
    
    echo -e "${YELLOW}  Installing Python dependencies...${NC}"
    uv pip install --python .venv/bin/python -r requirements.txt -q
    PYTHON_BIN=".venv/bin/python"
else
    # Using pip
    if [ ! -d ".venv" ]; then
        echo -e "${YELLOW}  Creating virtual environment...${NC}"
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    echo -e "${YELLOW}  Installing Python dependencies...${NC}"
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    PYTHON_BIN=".venv/bin/python"
fi

echo -e "${GREEN}  ✓ Python dependencies installed${NC}"
echo ""

# ============================================================================
# Node.js Dependencies
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Setting up Node.js dependencies...${NC}"

cd "$PROJECT_ROOT/apps/web"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}  Installing npm packages...${NC}"
    npm install --silent
fi
echo -e "${GREEN}  ✓ Node.js dependencies ready${NC}"
cd "$PROJECT_ROOT"
echo ""

# ============================================================================
# Kill Existing Processes on Ports
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Checking for existing processes...${NC}"

# Kill any process using API port
if lsof -ti:$API_PORT &>/dev/null; then
    echo -e "${YELLOW}  Killing existing process on port $API_PORT...${NC}"
    lsof -ti:$API_PORT | xargs kill -9 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}  ✓ Port $API_PORT freed${NC}"
else
    echo -e "${GREEN}  ✓ Port $API_PORT available${NC}"
fi

# Kill any process using Web port
if lsof -ti:$WEB_PORT &>/dev/null; then
    echo -e "${YELLOW}  Killing existing process on port $WEB_PORT...${NC}"
    lsof -ti:$WEB_PORT | xargs kill -9 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}  ✓ Port $WEB_PORT freed${NC}"
else
    echo -e "${GREEN}  ✓ Port $WEB_PORT available${NC}"
fi

echo ""

# ============================================================================
# Cleanup Function
# ============================================================================

cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down Synapse...${NC}"
    
    if [ ! -z "$API_PID" ]; then
        kill $API_PID 2>/dev/null || true
    fi
    if [ ! -z "$WEB_PID" ]; then
        kill $WEB_PID 2>/dev/null || true
    fi
    
    # Kill any orphan processes
    pkill -f "uvicorn apps.api.src.main:app" 2>/dev/null || true
    
    echo -e "${GREEN}Goodbye! 👋${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# ============================================================================
# Start API Server
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Starting API server...${NC}"

export PYTHONPATH="$PROJECT_ROOT"
$PYTHON_BIN -m uvicorn apps.api.src.main:app --host 0.0.0.0 --port $API_PORT --log-level warning &
API_PID=$!

# Wait for API to start
sleep 3
if ! kill -0 $API_PID 2>/dev/null; then
    echo -e "${RED}  ✗ Failed to start API server${NC}"
    echo -e "${YELLOW}  Check logs above for errors${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ API server running on http://localhost:$API_PORT${NC}"
echo ""

# ============================================================================
# Start Web Server
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Starting Web server...${NC}"

cd "$PROJECT_ROOT/apps/web"
npm run dev --silent &
WEB_PID=$!

sleep 4
if ! kill -0 $WEB_PID 2>/dev/null; then
    echo -e "${RED}  ✗ Failed to start Web server${NC}"
    kill $API_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}  ✓ Web server running on http://localhost:$WEB_PORT${NC}"
cd "$PROJECT_ROOT"

# ============================================================================
# Ready!
# ============================================================================

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║   ${BOLD_MAGENTA}⬢${NC} ${GREEN}Synapse v${VERSION} is ready!                                       ║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║   ${CYAN}Frontend:${NC}  ${GREEN}http://localhost:${WEB_PORT}                                 ║${NC}"
echo -e "${GREEN}║   ${CYAN}API:${NC}       ${GREEN}http://localhost:${API_PORT}                                 ║${NC}"
echo -e "${GREEN}║   ${CYAN}API Docs:${NC}  ${GREEN}http://localhost:${API_PORT}/docs                            ║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║   ${YELLOW}Press Ctrl+C to stop all services${NC}                                ${GREEN}║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Wait for processes
wait $API_PID $WEB_PID
