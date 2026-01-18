# Patch Instructions for BrowsePage.tsx

## Problem
MediaPreview component was using `useSettingsStore` hook internally, causing
each card to have its own store subscription. This caused performance issues
and stuttering when many cards were rendered.

## Solution
Pass `nsfwBlurEnabled` as a prop from the parent component (BrowsePage) where
the store is read only once.

## How to Apply

### Step 1: Find the import section in BrowsePage.tsx
Add this import at the top:
```tsx
import { useSettingsStore } from '@/stores/settingsStore'
```

### Step 2: Add store hook at component level
Near the top of the BrowsePage function, add:
```tsx
const { nsfwBlurEnabled } = useSettingsStore()
```

### Step 3: Find all MediaPreview usages and add the prop
Search for `<MediaPreview` and add `nsfwBlurEnabled={nsfwBlurEnabled}` prop.

Example - change from:
```tsx
<MediaPreview
  src={preview.url}
  type={preview.media_type}
  thumbnailSrc={preview.thumbnail_url}
  nsfw={preview.nsfw}
  aspectRatio="portrait"
  className="w-full h-full rounded-xl"
  onClick={() => openFullscreen(idx)}
/>
```

To:
```tsx
<MediaPreview
  src={preview.url}
  type={preview.media_type}
  thumbnailSrc={preview.thumbnail_url}
  nsfw={preview.nsfw}
  nsfwBlurEnabled={nsfwBlurEnabled}
  aspectRatio="portrait"
  className="w-full h-full rounded-xl"
  onClick={() => openFullscreen(idx)}
/>
```

### Step 4: Same for PackDetailPage.tsx and PacksPage.tsx
Apply the same pattern - read store once at component level, pass as prop.

---

## Alternative: Quick Inline Fix

If you want a quick fix without modifying parent components, you can add
a selector to the store hook to prevent unnecessary re-renders:

```tsx
// In MediaPreview.tsx, use shallow comparison
import { shallow } from 'zustand/shallow'

const nsfwBlurEnabled = useSettingsStore(
  (state) => state.nsfwBlurEnabled,
  shallow
)
```

But the prop-based approach is cleaner and more React-idiomatic.
