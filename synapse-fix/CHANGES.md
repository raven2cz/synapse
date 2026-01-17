# Synapse Media Preview Fix - Optimized Implementation

## Problem Summary

Current implementation has several critical issues:

1. **Syntax error in loading skeleton**: Missing parentheses around OR condition
   ```tsx
   // BROKEN:
   {loadState === 'idle' || loadState === 'loading' && (<div/>)}
   // This evaluates as: idle || (loading && JSX) - skeleton never shows for 'idle'
   ```

2. **Blocking video loading**: Video waits to load before showing anything, causing "eternal spinner"

3. **Over-complicated state management**: Too many interdependent states causing race conditions

4. **All videos try to autoplay**: `autoPlay={true}` on every card overwhelms browser/network

5. **No proper thumbnail-first strategy**: Should show image immediately, video is progressive enhancement

---

## Solution Architecture

### Core Principles

1. **Thumbnail-first**: Always show image/thumbnail immediately, never wait
2. **Progressive enhancement**: Video loads lazily as enhancement
3. **Hover-to-play**: Videos only play on user interaction (hover)
4. **Minimal state**: Reduce state complexity, fewer race conditions
5. **Memoization**: Prevent unnecessary re-renders in grid

### New Component Structure

```
components/ui/
├── MediaPreview.tsx      # Simplified, thumbnail-first preview
├── ModelCard.tsx         # Memoized card for grid display
├── DetailPreviewGallery.tsx  # Gallery for model detail modal
├── FullscreenMediaViewer.tsx # Fullscreen viewer with inline video player
└── VideoPlayer.tsx       # Keep existing (for other uses)
```

---

## File Changes

### 1. Replace `apps/web/src/components/ui/MediaPreview.tsx`

Replace entire file with the new optimized version.

**Key changes:**
- Thumbnail always renders immediately with `loading="lazy"` 
- Video only loads when `isHovering && isInView`
- Proper parentheses in conditional rendering
- `memo()` wrapper for performance
- Simplified state machine

### 2. Replace `apps/web/src/components/ui/FullscreenMediaViewer.tsx`

Replace with new version that includes inline VideoPlayer.

**Key changes:**
- Inline video player component (no separate import needed)
- Portal rendering for proper z-index
- Preloading adjacent images
- Better keyboard shortcuts

### 3. Add new `apps/web/src/components/ui/ModelCard.tsx`

New dedicated card component for browse grid.

**Key changes:**
- Memoized for grid performance
- Self-contained hover/video logic
- No props drilling for video state

### 4. Add new `apps/web/src/components/ui/DetailPreviewGallery.tsx`

New gallery component for model detail modal.

### 5. Update `apps/web/src/components/modules/BrowsePage.tsx`

**Changes in Results Grid section:**

```tsx
// BEFORE (around line 350):
<div
  className="flex flex-wrap gap-4"
  style={{ '--card-width': `${cardWidth}px` } as React.CSSProperties}
>
  {allModels.map(model => (
    <div
      key={model.id}
      onClick={() => setSelectedModel(model.id)}
      className="group cursor-pointer"
      style={{ width: cardWidth }}
    >
      {/* ... complex nested JSX ... */}
      <MediaPreview
        src={model.previews[0]?.url || ''}
        type={model.previews[0]?.media_type}
        thumbnailSrc={model.previews[0]?.thumbnail_url}
        nsfw={model.nsfw}
        aspectRatio="portrait"
        className="w-full h-full"
        autoPlay={true}  // ❌ PROBLEM: All videos autoplay
        playFullOnHover={true}
      />
      {/* ... */}
    </div>
  ))}
</div>

// AFTER:
import { ModelCard } from '@/components/ui/ModelCard'

<div className="flex flex-wrap gap-4">
  {allModels.map(model => (
    <ModelCard
      key={model.id}
      id={model.id}
      name={model.name}
      type={model.type}
      creator={model.creator}
      nsfw={model.nsfw}
      preview={model.previews[0]}
      baseModel={model.versions[0]?.base_model}
      stats={model.stats}
      width={cardWidth}
      onClick={() => setSelectedModel(model.id)}
      onCopyLink={() => {
        navigator.clipboard.writeText(`https://civitai.com/models/${model.id}`)
        addToast('info', 'Link copied')
      }}
    />
  ))}
</div>
```

**Changes in Model Detail Modal Preview Gallery section:**

```tsx
// BEFORE (around line 480):
<div className="grid grid-cols-6 gap-3 max-h-[360px] overflow-y-auto p-1">
  {modelDetail.previews.map((preview, idx) => (
    <MediaPreview
      key={idx}
      src={preview.url}
      type={preview.media_type}
      thumbnailSrc={preview.thumbnail_url}
      nsfw={preview.nsfw}
      aspectRatio="portrait"
      className="cursor-pointer hover:ring-2 ring-synapse"
      onClick={() => setFullscreenIndex(idx)}
    />
  ))}
</div>

// AFTER:
import { DetailPreviewGallery } from '@/components/ui/DetailPreviewGallery'

<DetailPreviewGallery
  items={modelDetail.previews.map(p => ({
    url: p.url,
    thumbnailUrl: p.thumbnail_url,
    type: p.media_type,
    nsfw: p.nsfw,
    width: p.width,
    height: p.height,
    meta: p.meta,
  }))}
  onItemClick={setFullscreenIndex}
  maxHeight={360}
  columns={6}
/>
```

### 6. Update `apps/web/src/lib/media/index.ts`

Ensure proper exports:

```ts
export * from './detection'
export * from './constants'
export type { MediaType, MediaInfo } from './detection'
```

---

## Testing Checklist

After applying changes, verify:

- [ ] Browse page loads instantly (no spinners blocking grid)
- [ ] Thumbnails appear immediately for all cards
- [ ] Videos only start loading on hover
- [ ] Videos play smoothly on hover
- [ ] Videos pause when mouse leaves
- [ ] Model detail modal opens quickly
- [ ] Preview gallery in modal shows thumbnails immediately
- [ ] Clicking preview opens fullscreen viewer
- [ ] Fullscreen viewer navigates with arrows
- [ ] Video in fullscreen has working controls
- [ ] NSFW blur works for both images and videos
- [ ] No console errors about video playback

---

## Performance Expectations

| Metric | Before | After |
|--------|--------|-------|
| Initial grid render | 2-5s (waiting for videos) | <100ms (thumbnails only) |
| Memory usage (20 cards) | High (all videos buffering) | Low (only hovered video) |
| Network requests on load | Many (video metadata) | Few (images only) |
| Scroll performance | Janky (video elements) | Smooth (images only) |

---

## Browser Compatibility

- Chrome 90+ ✓
- Firefox 88+ ✓
- Safari 14+ ✓
- Edge 90+ ✓

Key APIs used:
- IntersectionObserver (all modern browsers)
- Native lazy loading (`loading="lazy"`)
- Video element with `preload="none"`
