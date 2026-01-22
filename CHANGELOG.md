# Changelog

All notable changes to Synapse will be documented in this file.

## [2.6.0] - 2026-01-20 (Phase 4: Packs Video & Import Upgrade)

### Added

#### Video Preview Support
- **Backend video download** - Full video support during pack import
  - `pack_builder.py` - Video download with filters, timeouts, progress callback
  - `pack_service.py` - Analogous changes for pack service
  - `media_detection.py` - Multi-layer media type detection utility
  - Civitai fake JPEG video handling (videos served as .jpeg)

- **Import Wizard Modal** - New UI for importing packs with options
  - Multi-version selection (select specific versions to import)
  - Download options: images, videos, NSFW content
  - Thumbnail selection for pack cover
  - "Download from all versions" checkbox
  - Preview stats showing counts before import
  - Integrated into BrowsePage

- **PacksPage Video Support** - Video autoPlay system (like BrowsePage)
  - `MediaPreview` component with `autoPlay={true}`
  - Automatic video playback for video thumbnails
  - `FullscreenMediaViewer` integration
  - NSFW blur support for videos
  - Local .mp4 file playback support

- **Metadata Panel in FullscreenViewer**
  - `GenerationDataPanel` integration (inline)
  - Toggle button in control bar
  - Keyboard shortcut 'I' to toggle
  - Auto-update on navigation
  - Responsive design (side panel on desktop)

- **User Flags Display**
  - `is_nsfw` and `is_nsfw_hidden` fields from API
  - Special tag colors: nsfw-pack, nsfw-pack-hide, favorites, to-review, wip, archived
  - nsfw-pack-hide packs hidden when NSFW blur enabled

#### API Enhancements
- **thumbnail_type field** - API now returns 'image' or 'video' for pack thumbnails
- **cover_url support** - User-selected thumbnail saved and respected
- **Multi-version import** - N versions selected = N dependencies created
- **download_from_all_versions** option in ImportRequest

### Fixed
- **Video playback in PacksPage** - Local videos now play correctly with autoPlay
- **NSFW global toggle** - Reset revealed state when blur is re-enabled
- **Multi-version dependencies** - Each selected version creates separate dependency
- **Civitai video thumbnail loading** - Fallback to video element when image fails

### Tests
- Backend: test_pack_builder_video.py, test_media_detection.py
- Backend: test_pack_service_v2.py (multi-version, cover_url)
- Frontend: import-wizard.test.ts
- Frontend: fullscreen-metadata-panel.test.ts
- Frontend: pack-detail-verification.test.ts

## [2.2.0] - 2026-01-17 (Video Preview Support)

### Added

#### Video Preview Core Library
- **`src/utils/media_detection.py`** - Multi-layer media type detection
  - URL extension check (fast, no network)
  - URL pattern matching for known video CDNs
  - Content-Type HEAD request (optional, accurate)
  - Handles Civitai's fake JPEG videos

- **`apps/web/src/lib/media/`** - Frontend media utilities
  - `detection.ts` - Client-side media type detection
  - `constants.ts` - Shared constants for video playback

#### Frontend Components
- **`MediaPreview.tsx`** - Unified image/video preview component
  - Auto-detection of media type from URL
  - 5-second auto-play preview with loop
  - Full playback on hover
  - NSFW blur support for videos
  - Lazy loading with Intersection Observer
  - Audio indicator with mute toggle

- **`VideoPlayer.tsx`** - Full-featured video player
  - Custom control bar
  - Progress bar with seek
  - Keyboard shortcuts (Space, M, F, arrows)
  - Volume control with slider
  - Fullscreen toggle
  - Time display

- **`FullscreenMediaViewer.tsx`** - Modal media viewer
  - Image zoom and pan
  - Video player with full controls and audio
  - Previous/Next navigation
  - NSFW content handling
  - Keyboard navigation (Esc, arrows)
  - Download and external link buttons

#### Backend Updates
- Extended `PreviewImage` model with video fields:
  - `media_type`: 'image' | 'video' | 'unknown'
  - `duration`: Video duration in seconds
  - `has_audio`: Whether video has audio track
  - `thumbnail_url`: Poster image for videos

- Extended `ModelPreview` in browse.py with same fields
- Extended `PreviewInfo` in store/models.py with same fields
- Updated `pack_builder.py` to detect and download video previews

#### Tests
- `tests/utils/test_media_detection.py` - Comprehensive tests for media detection

### Changed
- Browse Civitai page now displays video previews
- Pack detail page supports video preview playback
- Fullscreen viewer supports both images and videos

### Technical Notes
- Video previews are lazy-loaded to save bandwidth
- Auto-play is muted by default (browser requirement)
- NSFW videos are blurred until revealed (same as images)
- Backward compatible - existing packs without `media_type` default to 'image'

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

## [2.1.7] - 2026-01-03

### Fixed
- **PackDependency Missing description**: Added `description` field to PackDependency model
  - Fixed 404 error: "'PackDependency' object has no attribute 'description'"
  - Pack detail page now loads correctly

## [2.1.6] - 2026-01-03

### Fixed - Critical Bug Fixes
- **Logger Missing**: Added logger import to api.py
- **PATCH user_tags 422 Error**: Fixed UpdatePackRequest body parsing
- **Parameters Storage**: Parameters now stored in pack.json
- **Delete Dependency**: Implemented delete resource endpoint
- **Download Progress**: Fixed NaN/undefined display
- **Civitai Download HTML Issue**: Fixed API authentication

### Added
- **NSFW Pack Flags**: Two-tier NSFW system via user_tags
  - `nsfw-pack`: Blur previews in pack list
  - `nsfw-pack-hide`: Completely hide pack when NSFW mode off

- **Extended Dependencies Display**: Rich metadata in UI

### Changed
- **Workflows → ComfyUI Workflows**: Section renamed in UI
- **AssetInfo Interface Extended**: More fields in TypeScript

## [2.1.5] - 2026-01-03

### Fixed - Critical Bug Fixes
- **resolve-base-model Endpoint**: Fixed HTTP 400 error when resolving base models
- **Civitai Search Duplicate Keys**: Fixed React warning about duplicate keys
- **Local Models Integration**: Fixed ComfyUI models scanning
- **Parameters Display**: Fixed generation parameters not showing in UI
- **Download Asset**: Fixed dependency lookup in download-asset endpoint

### Added
- **all_installed Field**: New field in pack response for better status checking
- **Comprehensive Tests**: 19 new tests for v2 API critical functionality

### Changed
- **Backend Model Aliases**: Added backwards compatibility aliases in models.py

## [2.1.4] - 2026-01-03

### CRITICAL FIX
- **Complete v1 Removal**: Removed ALL v1 API code from production use
  - main.py now uses ONLY v2_packs_router from src/store/api.py
  - All pack operations now use v2 Store with blob architecture

### Added
- **V2 Download Endpoints**: Proper download-asset implementation using v2 blob store
- **V2 Workflow Endpoints**: Delete workflow with symlink cleanup
- **V2 Import Model**: Import local model file to ComfyUI
- **Automated Tests**: New test suite to prevent v1 regression

## [2.1.3] - 2026-01-03

### Fixed
- **Download Assets**: Fixed critical bug where download button failed
- **Generate Default Button**: Now properly shows disabled state with tooltip

### Added
- **Local Model Import**: New feature to import models from filesystem into ComfyUI
- **Asset Description Display**: Shows description field for dependencies

## [2.1.2] - 2026-01-03

### Fixed
- **Base Model Display**: Fixed dependency display for base models
- **Generation Settings**: Section now always visible

### Verified
- **Workflows**: Upload, generate default, symlink, delete all working
- **Parameters API**: PATCH endpoint functional

## [2.1.1] - 2026-01-03

### Fixed
- **Preview Meta Data Algorithm**: Implemented v1's complex merge algorithm

### Added
- **ModelInfo and GenerationParameters**: Added missing model types to Pack
- **Extended Zoom Controls**: Preview grid zoom expanded from 3 to 5 levels

### Improved
- **Base Model Display**: model_info.base_model now properly populated
- **Dependency Colors**: Verified v1 coloring scheme

## [2.1.0] - 2026-01-02

### Major Changes
- **Restored V1 Backend**: Complete restoration of V1 `packs.py` router (2213 lines)

### Fixed
- Import endpoint: Frontend now correctly uses `/api/packs/import/url`
- Preview mount path: Uses V1 `synapse_data_path/packs` layout

## [2.0.9] - 2026-01-02

### Added
- **V1 Frontend Merge**: Complete restoration of all v1 UI components
  - Base Model Resolver with 3 tabs (Local, Civitai, HuggingFace)
  - NSFW toggle with animations and hover effects
  - Full pack preview formatting

### Fixed
- API compatibility layer for v1 UI endpoints

## [2.0.8] - 2026-01-02

### Fixed
- ResolvedArtifact attribute access
- Missing Pack metadata fields
- Pack detail page 404 errors

## [2.0.7] - 2026-01-02

### Fixed
- pack_path() method errors in profiles router
- Route shadowing in profiles router
- Missing Runtime.get_stack() method

## [2.0.6] - 2026-01-01

### Added
- Complete v2 Store implementation with content-addressable storage
- CLI interface with typer
- API routers for packs, profiles, and downloads
- 114 passing tests

## [2.0.0] - 2025-12-31

### Added
- Initial v2 architecture with Store facade
- Multi-UI support (profiles system)
- State machine for pack lifecycle
- Blob store for content-addressable storage

---

For detailed migration guide, see [README.md](README.md).
