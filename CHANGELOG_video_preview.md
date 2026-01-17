## [2.2.0] - 2025-01-17 (Video Preview Support)

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
  - Extension-based detection
  - URL pattern detection
  - Content-Type detection
  - Civitai fake JPEG handling

### Changed
- Browse Civitai page now displays video previews
- Pack detail page supports video preview playback
- Fullscreen viewer supports both images and videos

### Technical Notes
- Video previews are lazy-loaded to save bandwidth
- Auto-play is muted by default (browser requirement)
- NSFW videos are blurred until revealed (same as images)
- Backward compatible - existing packs without `media_type` default to 'image'

### Known Limitations
- Civitai Archive support pending (Phase 5)
- Mobile auto-play may be restricted by browser
- Some Civitai videos served as .jpeg require Content-Type check
