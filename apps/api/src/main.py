"""
Synapse API - FastAPI Backend

REST API for Synapse pack manager with WebSocket support
for real-time updates during downloads.

NOTE: This is v2 API ONLY. All endpoints use v2 Store architecture.
"""

# IMPORTANT: Set up paths BEFORE any other imports
import sys
from pathlib import Path

# Add project root to Python path (synapse/)
# This file is at: synapse/apps/api/src/main.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from .routers import system, downloads, browse, comfyui

# Store v2 routers - ALL pack operations use v2 Store
from src.store.api import (
    store_router, 
    v2_packs_router,  # This is the ONLY packs router - uses v2 Store
    profiles_router,
    updates_router, 
    search_router,
)
from .core.config import settings

# Configure logging - DEBUG level for detailed output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Also set DEBUG for our modules
logging.getLogger('src').setLevel(logging.DEBUG)
logging.getLogger('apps.api').setLevel(logging.DEBUG)


class StatusEndpointFilter(logging.Filter):
    """Filter out noisy polling endpoints from logs."""
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "/api/system/status" in message:
            return False
        if "/api/downloads/progress" in message:
            return False
        if "/api/packs/downloads/active" in message:
            return False
        return True


# Apply filter to uvicorn access logs only
logging.getLogger("uvicorn.access").addFilter(StatusEndpointFilter())


# Create FastAPI app
app = FastAPI(
    title="Synapse API v2",
    description="ComfyUI Asset & Workflow Manager - Store v2",
    version="2.1.8",
)


# Global exception handler - logs ALL errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all exceptions and log them with full traceback."""
    error_msg = str(exc)
    tb = traceback.format_exc()
    
    logger.error("=" * 60)
    logger.error(f"UNHANDLED EXCEPTION: {error_msg}")
    logger.error(f"URL: {request.url}")
    logger.error(f"Method: {request.method}")
    logger.error(f"Traceback:\n{tb}")
    logger.error("=" * 60)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": error_msg,
            "traceback": tb.split('\\n')[-5:] if tb else []
        }
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# API Routes - v2 Only
# =============================================================================

# System & utility routes
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(downloads.router, prefix="/api/downloads", tags=["Downloads"])
app.include_router(browse.router, prefix="/api/browse", tags=["Browse"])
app.include_router(comfyui.router, prefix="/api/comfyui", tags=["ComfyUI"])

# V2 Packs router - ALL pack operations use v2 Store with blob architecture
app.include_router(v2_packs_router, prefix="/api/packs", tags=["Packs"])

# Store v2 routes - additional functionality
app.include_router(store_router, prefix="/api/store", tags=["Store"])
app.include_router(profiles_router, prefix="/api/profiles", tags=["Profiles"])
app.include_router(updates_router, prefix="/api/updates", tags=["Updates"])
app.include_router(search_router, prefix="/api/search", tags=["Search"])

# Serve preview images - V2 Store path
from pathlib import Path
import os

# V2 layout: <synapse_root>/store/state/packs/<pack_name>/resources/previews/
# We need to find the synapse root, similar to src/store/layout.py
synapse_root = Path(os.environ.get("SYNAPSE_ROOT", Path.home() / ".synapse")).expanduser().resolve()
previews_path = synapse_root / "store" / "state" / "packs"

# Always create directory and mount
previews_path.mkdir(parents=True, exist_ok=True)
app.mount("/previews", StaticFiles(directory=str(previews_path)), name="previews")


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("=" * 50)
    logger.info("  SYNAPSE API v2.1.8")
    logger.info("  V2 Store Architecture - No v1 Code")
    logger.info("=" * 50)
    logger.info(f"  ComfyUI path: {settings.comfyui_path}")
    logger.info(f"  Data path: {settings.synapse_data_path}")
    logger.info("=" * 50)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Synapse API v2.1.8", "version": "2.1.8"}
