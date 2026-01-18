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
src/utils/media_detection.py - Added URL transformation functions
```

### Testing

1. Open Browse Civitai
2. Scroll through grid - all cards show static thumbnails
3. Hover over video card - video plays
4. Move mouse away - returns to thumbnail
5. Click "Load more" multiple times - no issues
6. Scroll rapidly - no black screens
