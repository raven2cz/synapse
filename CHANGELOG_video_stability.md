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
