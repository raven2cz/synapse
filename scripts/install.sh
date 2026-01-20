#!/bin/bash
#
# ⬢ Synapse - Installation Script
#
# This script installs all dependencies for Synapse:
# - Python packages (using uv or pip)
# - Node.js packages
# - Initializes the Synapse data directory
#
# Usage: ./scripts/install.sh
#

set -e

VERSION="2.1.8"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD_MAGENTA='\033[1;35m'
BOLD='\033[1m'
NC='\033[0m'

# Synapse icon
HEX_ICON="⬢"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${MAGENTA}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║  ███████╗██╗   ██╗███╗   ██╗ █████╗ ██████╗ ███████╗███████╗      ║"
echo "║  ██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝      ║"
echo "║  ███████╗ ╚████╔╝ ██╔██╗ ██║███████║██████╔╝███████╗█████╗        ║"
echo "║  ╚════██║  ╚██╔╝  ██║╚██╗██║██╔══██║██╔═══╝ ╚════██║██╔══╝        ║"
echo "║  ███████║   ██║   ██║ ╚████║██║  ██║██║     ███████║███████╗      ║"
echo "║  ╚══════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝      ║"
echo "║                                                                    ║"
echo "║                    ${BOLD_MAGENTA}⬢${MAGENTA} Installation v${VERSION}                           ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# ============================================================================
# Prerequisites Check
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Checking prerequisites...${NC}"
echo ""

MISSING_DEPS=0

# Check Python 3
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}  ✓ Python 3: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}  ✗ Python 3 is not installed${NC}"
    echo -e "    Install with: ${YELLOW}sudo apt install python3 python3-venv python3-pip${NC}"
    MISSING_DEPS=1
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}  ✓ Node.js: $NODE_VERSION${NC}"
else
    echo -e "${RED}  ✗ Node.js is not installed${NC}"
    echo -e "    Install with: ${YELLOW}sudo apt install nodejs${NC}"
    echo -e "    Or use nvm: ${YELLOW}https://github.com/nvm-sh/nvm${NC}"
    MISSING_DEPS=1
fi

# Check npm
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}  ✓ npm: $NPM_VERSION${NC}"
else
    echo -e "${RED}  ✗ npm is not installed${NC}"
    echo -e "    Install with: ${YELLOW}sudo apt install npm${NC}"
    MISSING_DEPS=1
fi

# Check uv (optional but recommended)
if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version)
    echo -e "${GREEN}  ✓ uv: $UV_VERSION (recommended)${NC}"
    USE_UV=true
else
    echo -e "${YELLOW}  ! uv not found (optional, will use pip)${NC}"
    echo -e "    Install with: ${CYAN}curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
    USE_UV=false
fi

echo ""

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "${RED}Missing required dependencies. Please install them first.${NC}"
    exit 1
fi

# ============================================================================
# Python Dependencies
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Installing Python dependencies...${NC}"
echo ""

if [ "$USE_UV" = true ]; then
    # Using uv (faster)
    if [ ! -d ".venv" ]; then
        echo -e "${YELLOW}  Creating virtual environment with uv...${NC}"
        uv venv --python 3.11 .venv 2>/dev/null || uv venv .venv
    fi
    
    echo -e "${YELLOW}  Installing packages with uv...${NC}"
    uv pip install --python .venv/bin/python -r requirements.txt
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ Python dependencies installed${NC}"
    else
        echo -e "${RED}  ✗ Failed to install Python dependencies${NC}"
        exit 1
    fi
else
    # Using pip (fallback)
    if [ ! -d ".venv" ]; then
        echo -e "${YELLOW}  Creating virtual environment...${NC}"
        python3 -m venv .venv
    fi
    
    echo -e "${YELLOW}  Installing packages with pip...${NC}"
    source .venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt
    deactivate
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ Python dependencies installed${NC}"
    else
        echo -e "${RED}  ✗ Failed to install Python dependencies${NC}"
        exit 1
    fi
fi

echo ""

# ============================================================================
# Node.js Dependencies
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Installing Node.js dependencies...${NC}"
echo ""

cd "$PROJECT_ROOT/apps/web"

echo -e "${YELLOW}  Installing npm packages...${NC}"
npm install

if [ $? -eq 0 ]; then
    echo -e "${GREEN}  ✓ Node.js dependencies installed${NC}"
else
    echo -e "${RED}  ✗ Failed to install Node.js dependencies${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"
echo ""

# ============================================================================
# Initialize Synapse
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Initializing Synapse...${NC}"
echo ""

# Create data directory
mkdir -p ~/.synapse/store
mkdir -p ~/.synapse/packs

echo -e "${GREEN}  ✓ Data directories created${NC}"
echo ""

# ============================================================================
# Done!
# ============================================================================

echo -e "${GREEN}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║   ${BOLD_MAGENTA}⬢${NC} ${GREEN}Installation complete!                                        ║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║   To start Synapse, run:                                           ║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║     ${CYAN}./scripts/start-all.sh${NC}                                       ${GREEN}║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║   Or manually:                                                     ║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║     Terminal 1 (API):                                              ║${NC}"
echo -e "${GREEN}║       ${CYAN}source .venv/bin/activate${NC}                                  ${GREEN}║${NC}"
echo -e "${GREEN}║       ${CYAN}PYTHONPATH=. uvicorn apps.api.src.main:app${NC}                 ${GREEN}║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║     Terminal 2 (Web):                                              ║${NC}"
echo -e "${GREEN}║       ${CYAN}cd apps/web && npm run dev${NC}                                 ${GREEN}║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}║   Web UI: ${CYAN}http://localhost:5173${NC}                                  ${GREEN}║${NC}"
echo -e "${GREEN}║   API:    ${CYAN}http://localhost:8000${NC}                                  ${GREEN}║${NC}"
echo -e "${GREEN}║                                                                    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
