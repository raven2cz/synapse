# Changelog

All notable changes to Synapse will be documented in this file.

## [2.1.8] - 2026-01-03

### Added - Workflow Management System
- **Workflow Generator**: Full implementation of default workflow generation
  - Generates ComfyUI-compatible workflows based on pack type and parameters
  - Supports SD 1.5, SDXL, Illustrious, Pony, Flux architectures
  - Automatically detects architecture from pack.base_model
  - Includes checkpoint loader, LoRA loaders, CLIP text encode, KSampler, VAE decode, SaveImage
  - Respects pack parameters (steps, CFG, sampler, dimensions, clip_skip)
  - Uses trigger words from pack.model_info

- **WorkflowInfo Model**: Added to v2 models
  - Fields: name, filename, description, source_url, is_default
  - Pack.workflows field for storing workflow metadata

- **Workflow Management Endpoints**:
  - `POST /api/packs/{pack_name}/generate-workflow` - Generate default workflow
  - `POST /api/packs/{pack_name}/workflow/add` - Add workflow info to pack.json
  - `PATCH /api/packs/{pack_name}/workflow/{filename}` - Rename workflow
  - `DELETE /api/packs/{pack_name}/workflow/{filename}` - Delete workflow (file + pack.json + symlink)
  - `POST /api/packs/{pack_name}/workflow/upload-file` - Upload workflow with optional metadata
  - `POST /api/packs/{pack_name}/workflow/symlink` - Create symlinks for all pack workflows
  - `POST /api/packs/{pack_name}/workflow/{filename}/symlink` - Create symlink for specific workflow

- **ComfyUI Integration**:
  - Symlinks created in ComfyUI user/default/workflows folder
  - Format: `[PackName] workflow.json` to avoid conflicts
  - Automatic cleanup of symlinks when deleting workflows

### Fixed
- **Workflow Loading**: get_pack now uses pack.json as primary source for workflows
  - Shows metadata (name, description, is_default) from pack.json
  - Detects orphaned workflow files not in pack.json
  - Checks for symlinks in both old and new formats

### Tests
- Added TestWorkflowManagement test class with 7 tests
  - WorkflowInfo model validation
  - Pack.workflows field verification
  - Architecture detection (_detect_architecture)
  - API endpoints existence verification

## [2.1.7] - 2026-01-03

### Fixed
- **PackDependency Missing description**: Added `description` field to PackDependency model
  - Fixed 404 error: "'PackDependency' object has no attribute 'description'"
  - Pack detail page now loads correctly

## [2.1.6] - 2026-01-03

### Fixed - Critical Bug Fixes
- **Logger Missing**: Added logger import to api.py
  - Fixed NameError: name 'logger' is not defined

- **PATCH user_tags 422 Error**: Fixed UpdatePackRequest body parsing
  - Created proper UpdatePackRequest model with user_tags and name fields
  - PATCH endpoint now correctly accepts JSON body
  - Added rename support (change pack name)

- **Parameters Storage**: Parameters now stored in pack.json
  - Removed external parameters.json file dependency
  - Parameters are part of pack manifest (pack.parameters field)
  - Generator workflow can read parameters from pack.json

- **Delete Dependency**: Implemented delete resource endpoint
  - DELETE `/api/packs/{pack_name}/dependencies/{dep_id}/resource`
  - Option to delete blob only (default) or also remove dependency
  - Frontend delete button now functional

- **Download Progress**: Fixed NaN/undefined display
  - Added speed_bps calculation with proper sampling
  - ETA calculation based on remaining bytes and current speed
  - formatSpeed and formatEta handle undefined/NaN gracefully

- **Civitai Download HTML Issue**: Fixed API authentication
  - BlobStore now receives civitai_api_key from Store
  - Token appended to Civitai download URLs
  - Store constructor accepts civitai_api_key parameter

### Added
- **NSFW Pack Flags**: Two-tier NSFW system via user_tags
  - `nsfw-pack`: Blur previews in pack list (existing behavior)
  - `nsfw-pack-hide`: Completely hide pack when NSFW mode off
  - list_packs accepts `show_nsfw` query parameter
  - Pack model has `is_nsfw` and `is_nsfw_hidden` properties

- **Extended Dependencies Display**: Rich metadata in UI
  - Version name, creator, model name from source_info
  - SHA256 hash display (truncated)
  - Download URL preview
  - Provider name

### Changed
- **Workflows → ComfyUI Workflows**: Section renamed in UI
  - Clarifies these are specifically ComfyUI workflow files
  - Prepares for future support of other UI workflows

- **AssetInfo Interface Extended**: More fields in TypeScript
  - source_info with model_id, version_id, model_name, etc.
  - sha256, provider_name, description fields

## [2.1.5] - 2026-01-03

### Fixed - Critical Bug Fixes
- **resolve-base-model Endpoint**: Fixed HTTP 400 error when resolving base models
  - Corrected PackLock creation (uses `pack` not `pack_name`)
  - Uses correct v2 model classes (ResolvedArtifact, ArtifactProvider, etc.)
  - Proper SelectorStrategy values (CIVITAI_FILE, HUGGINGFACE_FILE, etc.)
  - ArtifactProvider now uses `name: ProviderName` correctly

- **Civitai Search Duplicate Keys**: Fixed React warning about duplicate keys
  - Search results now use unique keys including file_name and index
  - Selection comparison uses both model_id and file_name

- **Local Models Integration**: Fixed ComfyUI models scanning
  - Frontend now calls `/api/comfyui/models/checkpoints` correctly
  - Text changed from "Add to ComfyUI" to "Import to Synapse"

- **Parameters Display**: Fixed generation parameters not showing in UI
  - Parameters now loaded from resources/parameters.json in get_pack
  - Update endpoint merges new values with existing (preserves values)
  - camelCase to snake_case conversion for consistent storage

- **Download Asset**: Fixed dependency lookup in download-asset endpoint
  - Uses `dep.id` instead of `dep.dependency_id`
  - Gets URL from lock file's resolved artifact
  - Updates lock with SHA256 after successful download
  - Extended asset type mapping for all ComfyUI model types

### Added
- **all_installed Field**: New field in pack response for better status checking
  - `all_installed`: True only when ALL assets are in installed status
  - `can_generate`: True when all_installed and no workflows yet
  - Frontend uses allDependenciesInstalled for Generate Default button

- **Comprehensive Tests**: 19 new tests for v2 API critical functionality
  - tests/store/test_api_v2_critical.py
  - Tests for resolve-base-model, parameters, download-asset
  - Tests for v2 model structures (PackDependency, ResolvedDependency, etc.)
  - Tests to ensure no v1 code in production paths

### Changed
- **Backend Model Aliases**: Added backwards compatibility aliases in models.py
  - Artifact = ResolvedArtifact
  - DownloadInfo = ArtifactDownload
  - IntegrityInfo = ArtifactIntegrity

## [2.1.4] - 2026-01-03

### CRITICAL FIX
- **Complete v1 Removal**: Removed ALL v1 API code from production use
  - main.py now uses ONLY v2_packs_router from src/store/api.py
  - apps/api/src/routers/packs.py renamed to packs_v1_DEPRECATED.py
  - routers/__init__.py no longer exports packs_router
  - All pack operations now use v2 Store with blob architecture

### Added
- **V2 Download Endpoints**: Proper download-asset implementation using v2 blob store
  - POST /api/packs/{name}/download-asset - downloads with progress tracking
  - GET /api/packs/downloads/active - list active downloads  
  - DELETE /api/packs/downloads/completed - clear completed downloads
  - POST /api/packs/{name}/download-all - install all blobs

- **V2 Workflow Endpoints**:
  - DELETE /api/packs/{name}/workflow/{filename} - delete workflow with symlink cleanup

- **V2 Import Model**:
  - POST /api/packs/import-model - import local model file to ComfyUI

- **Automated Tests**: New test suite to prevent v1 regression
  - tests/test_no_v1_imports.py - ensures no v1 imports in API code
  - Checks main.py uses v2_packs_router
  - Checks routers/__init__.py doesn't export packs_router
  - Verifies all required endpoints exist in v2 API

### Architecture
- All downloads now go through v2 BlobStore (content-addressable)
- v2 Store handles all pack CRUD operations
- v1 code preserved only as deprecated reference (packs_v1_DEPRECATED.py)

## [2.1.3] - 2026-01-03

### Fixed
- **Download Assets**: Fixed critical bug where download button failed with "Store object has no attribute 'install_pack'"
  - Removed conflicting v2 store API endpoints that were shadowing v1 packs router
  - v1 download implementation with proper progress tracking now correctly used
  - All asset downloads (LoRA, checkpoints, etc.) now work correctly

- **Generate Default Button**: Now properly shows disabled state with tooltip explanation
  - Button visually grayed out when models unresolved
  - Hover tooltip: "Resolve all models before generating workflow"

### Added
- **Local Model Import**: New feature to import models from filesystem into ComfyUI
  - Browse button in "Local Models" tab opens import dialog
  - Supports .safetensors, .ckpt, .pt, .bin files
  - Model metadata form: type (checkpoint/LoRA/VAE), display name, base architecture
  - Copies file to appropriate ComfyUI models directory
  - Auto-selects imported model for immediate use

- **Asset Description Display**: Shows description field for dependencies
  - Base models show helpful text like "Required base model: Illustrious. Please select a specific checkpoint."
  - Description displayed in amber italic text below asset info

### Improved
- **Local Models Tab**: Enhanced UI with import section
  - Clear "Import Local Model" button at top with explanation
  - Shows count of found local models
  - Truncated paths for cleaner display

## [2.1.2] - 2026-01-03

### Fixed
- **Base Model Display**: Fixed dependency display for base models
  - Now shows actual asset name (e.g. "Base Model: Illustrious") instead of generic "Base Model"
  - Shows actual asset_type instead of hardcoded "BASE MODEL"
  - Displays `base_model_hint` in amber color when available
  - All asset information (source, size, version) now properly visible

- **Generation Settings**: Section now always visible (not conditionally hidden)
  - Users can add parameters even when none exist
  - Shows "No generation parameters set. Click Edit to add some." when empty
  - Edit modal properly saves parameters to pack.json via API

### Verified
- **Workflows**: Upload, generate default, symlink, delete all working
  - Generate Default disabled when base model unresolved (correct behavior)
  - Upload workflow accepts JSON files and saves to pack
- **Parameters API**: `/api/packs/{name}/parameters` PATCH endpoint functional
  - Handles strength, cfgScale, steps, sampler, clipSkip, width, height, denoise, scheduler

## [2.1.1] - 2026-01-03

### Fixed
- **Preview Meta Data Algorithm**: Implemented v1's complex merge algorithm for preview metadata
  - Fetches detailed version data from Civitai API for full meta information
  - Creates lookup map by URL for efficient merging
  - Properly extracts nested 'meta' keys (API quirk handling)
  - Saves both to pack.json and sidecar JSON files for compatibility

### Added
- **ModelInfo and GenerationParameters**: Added missing model types to Pack
  - `model_info` field with full Civitai details (base_model, trigger_words, rating, etc.)
  - `parameters` field for generation settings
  - Import now extracts and saves all model metadata

- **Extended Zoom Controls**: Preview grid zoom expanded from 3 to 5 levels
  - New sizes: xs (10 cols), sm (8 cols), md (6 cols), lg (4 cols), xl (3 cols)
  - Default changed to 'sm' for smaller previews on page load
  - Zoom buttons properly disable at limits (xs/xl)

### Improved
- **Base Model Display**: model_info.base_model now properly populated from Civitai
- **Dependency Colors**: Verified v1 coloring scheme:
  - Green: installed/resolved
  - Blue: ready to download (has URL)
  - Amber: needs resolution (unresolved status)
  - Synapse/purple: currently downloading

## [2.1.0] - 2026-01-02

### Major Changes
- **Restored V1 Backend**: Complete restoration of V1 `packs.py` router (2213 lines)
  - Full CRUD operations for packs
  - Complete Base Model Resolver with Local/Civitai/HuggingFace tabs
  - Download asset functionality with progress tracking
  - Workflow generation and management
  - URL repair for Civitai links
  - Asset validation and auto-repair

### Fixed
- Import endpoint: Frontend now correctly uses `/api/packs/import/url`
- Preview mount path: Uses V1 `synapse_data_path/packs` layout
- All V1 API endpoints restored and functional

### Architecture
- V1 `packs.py` router (2213 lines) at `/api/packs/*`
- V2 Store features preserved at `/api/store/*`, `/api/profiles/*`, etc.
- Frontend uses V1 API endpoints for pack management

## [2.0.9] - 2026-01-02

### Added
- **V1 Frontend Merge**: Complete restoration of all v1 UI components
  - Base Model Resolver with 3 tabs (Local, Civitai, HuggingFace)
  - NSFW toggle with animations and hover effects
  - Full pack preview formatting
  - Download section with icons and modal access
  - Browse Civitai with complete image download and metadata merge
  - Workflow generation panel

### Fixed
- API compatibility layer for v1 UI endpoints
- `/api/comfyui/models/checkpoints` endpoint for local model scanning
- Pack import endpoint path (`/api/packs/import`)
- Selector-based dependency access in pack details

### Changed
- Frontend now uses v1 API endpoints wrapping v2 Store operations
- PacksPage handles v2 API response format `{ packs: [...] }`

## [2.0.8] - 2026-01-02

### Fixed
- ResolvedArtifact attribute access (provider.filename, download.urls)
- Missing Pack metadata fields (version, description, base_model, author, tags)
- Pack detail page 404 errors with real pack data

## [2.0.7] - 2026-01-02

### Fixed
- pack_path() method errors in profiles router
- Route shadowing in profiles router
- Missing Runtime.get_stack() method
- Orphaned async/await code block causing build errors

## [2.0.6] - 2026-01-01

### Added
- Complete v2 Store implementation with content-addressable storage
- CLI interface with typer
- API routers for packs, profiles, and downloads
- 114 passing tests

### Changed
- Removed v1 packs router (replaced by v2 Store API)
- Pydantic warnings fixed
- Previews mount always creates directory

## [2.0.0] - 2025-12-31

### Added
- Initial v2 architecture with Store facade
- Multi-UI support (profiles system)
- State machine for pack lifecycle
- Blob store for content-addressable storage

---

For detailed migration guide, see [README.md](README.md).
