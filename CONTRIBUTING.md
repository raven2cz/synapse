# Contributing to Synapse

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- uv (Python package manager)

### Install Dependencies

```bash
# Backend
cd /path/to/synapse
uv pip install -e ".[dev]"

# Frontend
cd apps/web
npm install
```

## Definition of Done (DoD)

Before any PR/commit is considered complete, the following checks **MUST** pass:

### 1. Backend Tests (Required)
```bash
cd /path/to/synapse
python -m pytest tests/ -v
```
✅ All tests must pass (0 failures)

### 2. Frontend Build (Required)
```bash
cd apps/web
npm run build
```
✅ TypeScript compilation must succeed  
✅ Vite build must complete without errors

### 3. No Legacy API References
```bash
grep -rn "/api/comfyui" --include="*.py" --include="*.ts" --include="*.tsx" . | grep -v node_modules | grep -v test
```
✅ Must return 0 results (no production code references to removed endpoints)

## Quick Verification Script

Run this before committing:

```bash
#!/bin/bash
set -e

echo "=== Running Backend Tests ==="
python -m pytest tests/ -v --tb=short

echo "=== Building Frontend ==="
cd apps/web && npm run build && cd ../..

echo "=== Checking for Legacy APIs ==="
LEGACY=$(grep -rn "/api/comfyui" --include="*.py" --include="*.ts" --include="*.tsx" . 2>/dev/null | grep -v node_modules | grep -v test | wc -l)
if [ "$LEGACY" -gt 0 ]; then
    echo "ERROR: Found legacy /api/comfyui references!"
    exit 1
fi

echo "=== All checks passed! ==="
```

## Architecture Notes

### v2 Store Architecture
- All state in `<store_root>/state/`
- Packs in `<store_root>/state/packs/<pack_name>/`
- Views in `<store_root>/views/<ui>/`
- No more v1 packs router - everything through `/api/packs/` and `/api/store/`

### UI Attach System
- ComfyUI: Patches `extra_model_paths.yaml` directly with backup
- Forge/A1111/SD.Next: Creates symlinks in model folders
- `use/back` only refreshes already-attached UIs (doesn't auto-attach)

### Critical Endpoints
- `POST /api/packs/import` - Import from URL
- `POST /api/packs/{name}/resolve` - Resolve dependencies
- `POST /api/packs/{name}/install` - Download resolved assets
- `GET /api/store/attach-status` - Get UI attachment status
- `POST /api/store/attach` - Attach UIs
- `POST /api/store/detach` - Detach UIs
