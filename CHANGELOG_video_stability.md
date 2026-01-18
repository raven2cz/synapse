## [2.5.2] - 2025-01-18 (Unit Tests)

### Added: Comprehensive Test Suite

**Frontend Tests (Vitest)**
- `civitai-url-utils.test.ts` - URL transformation tests
  - getCivitaiThumbnailUrl (anim=false, width params)
  - getCivitaiVideoUrl (quality levels, mp4 conversion)
  - isLikelyVideo detection
  - Edge cases (malformed URLs, special chars)

- `media-preview-nsfw.test.ts` - NSFW blur logic tests
  - shouldBlur calculation
  - Eye icon visibility rules
  - NSFW badge visibility rules
  - State transitions (reveal/hide)
  - CSS class application

- `fullscreen-viewer.test.ts` - Fullscreen viewer tests
  - Quality selector (SD/HD/FHD)
  - Video fit mode (contain/cover)
  - Autoplay conditions
  - Navigation (next/prev/goToIndex)
  - Keyboard shortcuts mapping
  - Time formatting
  - Progress bar calculation

- `settings-store.test.ts` - Settings store tests
  - NSFW blur toggle
  - Zustand selector pattern
  - Global toggle effect on cards

**Backend Tests (Pytest)**
- `test_media_detection.py` - Media detection utility tests
  - MediaType enum values
  - URL extension detection
  - URL pattern detection
  - detect_media_type function
  - is_video_url function
  - is_likely_animated function
  - get_video_thumbnail_url
  - get_optimized_video_url
  - transform_civitai_url
  - MediaInfo dataclass
  - Edge cases handling

**Test Configuration**
- Added vitest.config.ts with jsdom environment
- Added test setup with mocks (IntersectionObserver, ResizeObserver, HTMLMediaElement)
- Updated package.json with test scripts and dependencies

**Run Tests**
```bash
# Frontend
cd apps/web
npm install
npm run test

# Backend
cd synapse
python -m pytest tests/unit/test_media_detection.py -v
```

---

## [2.5.1] - 2025-01-18 (Quality Selector + Autoplay + Fit Mode)

### New Features

**🎬 Video Autoplay**
- Videos now automatically start playing when fullscreen opens
- No more waiting or clicking play button

**📺 Quality Selector**
- `SD` (450p) - Fast, instant playback (same as preview)
- `HD` (720p) - Higher quality
- `FHD` (1080p) - Full HD quality
- Click quality badge to switch
- Highlighted when using higher quality

**🖼️ Fit Mode Toggle**
- `Contain` - Fit video to screen with letterboxing (default)
- `Cover` - Fill entire screen, may crop edges
- Click maximize/minimize icon to toggle

### UI Improvements
- Quality menu with "Fast" and "Best" hints
- Loop indicator is now clickable (toggles loop)
- Better control button styling

---

## [2.5.0] - 2025-01-18 (Professional Fullscreen Viewer)

### Major Redesign: FullscreenMediaViewer

**🚀 Fast Video Loading**
- Now uses SAME quality (width=450) as preview thumbnails
- Video starts INSTANTLY - no re-downloading when opening fullscreen
- Previously used width=1080 which caused 20+ second delays

**🎬 Professional Video Controls (YouTube/Vimeo style)**
- Smooth progress bar with:
  - Hover time preview
  - Buffered indicator
  - Animated thumb on hover
- Skip back/forward 10 seconds buttons
- Volume slider (appears on hover)
- Playback speed selector (0.25x - 2x)
- Loop toggle with visual indicator
- Play/Pause overlay icon
- Buffering spinner
- Time display (current / total)

**🖼️ Advanced Image Viewer**
- Wheel zoom (smooth, up to 5x)
- Double-click to toggle zoom (1x ↔ 2.5x)
- Pan/drag when zoomed (cursor changes to grab)
- Reset view button
- Zoom percentage display

**⌨️ Complete Keyboard Shortcuts**
| Key | Action |
|-----|--------|
| Space | Play/Pause |
| M | Mute/Unmute |
| L | Toggle Loop |
| F | Fullscreen |
| ←/→ | Previous/Next |
| Shift+←/→ | Seek ±10s |
| ↑/↓ | Volume ±10% |
| ,/. | Frame step (±1/30s) |
| +/- | Zoom in/out |
| 0 | Reset zoom |
| Esc | Close |

**🎨 Modern UI**
- Gradient overlays (top/bottom)
- Auto-hide controls after 3s
- Smooth hover animations
- Backdrop blur effects
- Color-coded states (indigo for active, red for NSFW)
- Professional button styling
- Keyboard shortcuts help text

---

## [2.5.0] - 2025-01-18 (Professional Fullscreen Viewer)

### ⚡ INSTANT Video Loading in Fullscreen

**Problem:** Video took 20+ seconds to load in fullscreen because it was downloading a higher resolution version (width=1080).

**Solution:** Now uses the SAME resolution as preview (width=450), so video starts INSTANTLY because it's already cached.

```diff
- getCivitaiVideoUrl(url, 1080)  // Downloads new HQ video
+ getCivitaiVideoUrl(url, 450)   // Uses cached preview video
```

### 🎬 Netflix-Style Video Controls

- **Progress bar** with gradient and hover thumb indicator
- **Skip ±10s buttons** (J/;) for quick navigation
- **Volume slider** - appears on hover
- **Loop indicator** (LOOP/ONCE) with toggle
- **Buffering spinner** while loading
- **Big center play button** when paused
- **Auto-hide controls** after 3 seconds

### 🖼️ PhotoSwipe-Style Image Viewer

- **Mouse wheel zoom** - smooth zoom in/out
- **Double-click zoom** - toggle between 1x and 2x
- **Drag to pan** - when zoomed in
- **Reset zoom button** - back to 1x
- **Zoom percentage display** in header

### 📸 Thumbnail Strip

- Shows all media items at bottom
- Click to navigate directly
- Current item highlighted with indigo ring
- Videos marked with play icon
- NSFW items blurred if enabled

### ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space/K | Play/Pause |
| J | Skip back 10s |
| ; | Skip forward 10s |
| M | Mute/Unmute |
| L | Toggle loop |
| +/- | Zoom in/out (images) |
| 0 | Reset zoom |
| F | Native fullscreen |
| ←/→ | Previous/Next |
| Esc | Close |
| ↑/↓ | Volume up/down |

### 💾 Download

- Download button fetches HQ version (1080p for video)
- Proper filename: `synapse_1.mp4` or `synapse_1.jpg`

### 🎨 Visual Design

- **Glassmorphism** - translucent controls with blur
- **Gradient progress bar** - indigo to purple
- **Smooth transitions** - controls fade in/out
- **Dark background** - pure black for maximum contrast

---

## [2.4.2] - 2025-01-18 (Final NSFW + Z-index Fix)

### Critical Fixes

**1. NSFW Eye Icon Visibility:**
- Eye toggle button now **HIDDEN** when card is blurred
- Shows **ONLY when card is revealed** (EyeOff icon to hide back)
- Clicking anywhere on blurred card reveals it
- Clean UX: No distracting icon on blurred content

**2. FullscreenMediaViewer Z-Index:**
- Changed from `z-50` to `z-[100]`
- Now properly displays ABOVE modal dialogs (which use z-50)

**3. Store Usage:**
- Using Zustand selector: `useSettingsStore((state) => state.nsfwBlurEnabled)`
- Efficient - only re-renders when nsfwBlurEnabled actually changes
- Global toggle in header works correctly

### NSFW Behavior Summary

| State | Eye Button | Overlay | Badge |
|-------|------------|---------|-------|
| Blur ON, NOT revealed | Hidden | Visible (EyeOff + NSFW text) | - |
| Blur ON, revealed | Visible (EyeOff) | Hidden | - |
| Blur OFF globally | - | - | Red NSFW badge |

---

## [2.4.1] - 2025-01-18 (Performance Fix + NSFW Features)

### Performance Critical Fix

**Problem:** Using `useSettingsStore` inside MediaPreview caused each card to have its own
store subscription, leading to massive re-renders and stuttering.

**Solution:** `nsfwBlurEnabled` is now passed as a prop from parent component.

### NSFW Features Restored

- ✅ Global NSFW toggle in header works
- ✅ Eye icon (top-right) for individual reveal/hide
- ✅ Blur effect on NSFW content
- ✅ Red "NSFW" badge when blur is globally disabled
- ✅ No flickering (removed backdrop-blur from overlays)

### FullscreenMediaViewer Enhanced

- ✅ Loop toggle button (Repeat icon, keyboard: L)
- ✅ Custom video controls (progress bar, play/pause, mute)
- ✅ Time display
- ✅ Keyboard shortcuts: Space, M, L, Esc, arrows

### CRITICAL: Parent Patches Required

**You MUST update parent components to pass `nsfwBlurEnabled` prop!**

See `patches/` folder for:
- `BrowsePage.patch`
- `PackDetailPage.patch`

Quick fix pattern:
```tsx
// Add at component level
const { nsfwBlurEnabled } = useSettingsStore()

// Pass to MediaPreview
<MediaPreview ... nsfwBlurEnabled={nsfwBlurEnabled} />
```

---

## [2.4.0] - 2025-01-18 (CivArchive Approach - Complete Rewrite)

### Root Cause Analysis

After analyzing CivArchive (which works perfectly), the issue was identified:

**The Problem:** Civitai API returns URLs that may be "fake JPEGs" - files with `.jpeg` extension that are actually videos. Browsers (especially Firefox) don't know how to handle these properly.

**CivArchive Solution:** They use proper Civitai CDN URL transformations:
- **Thumbnail:** `anim=false,transcode=true,width=450,optimized=true` → actual JPEG
- **Video:** `transcode=true,width=450,optimized=true` + `.mp4` → actual MP4

### Complete Rewrite

The MediaPreview component was completely rewritten with a simple, stable approach:

1. **Always show `<img>` for thumbnail** - Uses `anim=false` URL to get actual JPEG
2. **Show `<video>` only on hover** - Uses proper `.mp4` URL
3. **No complex state management** - Simple isHovering toggle
4. **No Intersection Observer complexity** - Just basic React state
5. **Proper URL transformation** - Civitai CDN params are correctly set

### Key Functions Added

```tsx
// Get static thumbnail (first frame as JPEG)
getCivitaiThumbnailUrl(url) 
// → anim=false,transcode=true,width=450,optimized=true

// Get actual MP4 video  
getCivitaiVideoUrl(url)
// → transcode=true,width=450,optimized=true + .mp4 extension
```

### How It Works Now

1. **Default state:** Shows `<img>` with thumbnail URL (anim=false)
2. **On hover:** Shows `<video>` with MP4 URL, hides image
3. **On mouse leave:** Pauses video, shows image again
4. **On video error:** Falls back to image only

### Benefits

- ✅ No more "fake JPEG" issues
- ✅ No black screen bugs
- ✅ No stuck videos
- ✅ Works in Firefox
- ✅ Simple, maintainable code
- ✅ Matches CivArchive behavior

### Files Changed

```
apps/web/src/components/ui/MediaPreview.tsx - Complete rewrite (~300 lines)
apps/web/src/components/ui/FullscreenMediaViewer.tsx - Loop toggle + controls
src/utils/media_detection.py - Added URL transformation functions
patches/BrowsePage.patch - Parent component patch
patches/PackDetailPage.patch - Parent component patch
```

### Testing

1. **Apply patches first!**
2. Open Browse Civitai
3. Scroll through grid - all cards show static thumbnails
4. Hover over video card - video plays smoothly
5. Toggle NSFW in header - works immediately
6. Click eye icon on NSFW card - reveals/hides
7. Open fullscreen - test loop toggle
8. Scroll rapidly - no stuttering
