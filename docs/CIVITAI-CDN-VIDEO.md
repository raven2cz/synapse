# Civitai CDN & Video Playback — Technical Reference

**Date:** 2026-02-22
**Related:** `plans/PLAN-CDN-Video-Fix.md`, `tests/smoke/`

---

## 1. Civitai CDN URL Structure

Base: `https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/{uuid}/{params}/{filename}`

Params are **comma-separated path segments** (NOT query strings):

| Use case | Params | Filename | Result |
|----------|--------|----------|--------|
| Image | `width=450` | `image.jpeg` | Static image (JPEG/WebP) |
| Video thumbnail | `anim=false,transcode=true,width=450` | `*.jpeg` | Static first frame (WebP) |
| Video playback | `anim=true,transcode=true,width=450` | `*.mp4` | MP4 video stream |

### Critical: `anim=true` Parameter

| URL params | CDN behavior | Result |
|------------|-------------|--------|
| `anim=true,transcode=true,width=450` | Cloudflare serves directly | **200**, video/mp4 |
| `transcode=true,width=450` (no anim) | Redirect to B2 storage | **301 → 401** auth failure |
| `anim=false,transcode=true,width=450` | Static thumbnail | **200**, image/webp |
| `width=450` (image UUID) | Cloudflare serves directly | **200**, image/jpeg |
| `width=450` (video UUID, no anim) | CDN can't process | **500** Internal Server Error |

**Source:** Civitai's own `useEdgeUrl()` in `cf-images-utils.ts`:
```typescript
if (type === 'video') {
  transcode = true;
  anim = anim ?? true;  // DEFAULT anim=true for videos!
}
```

### `optimized=true` Parameter

- Format hint: returns WebP (9KB) vs JPEG (19KB)
- NOT required for functionality — Civitai fixed CDN errors related to it
- Removed from codebase as cleanup (2026-02-22)

---

## 2. URL Construction — Where It Happens

### Browse Page (Civitai Search Results)

Two adapters build URLs differently:

| Adapter | File | URL Source | Video Params |
|---------|------|-----------|-------------|
| **tRPC** | `civitaiTransformers.ts` | Builds from UUID | `anim=true,transcode=true,width=450` |
| **REST** | `browse.py` → `create_model_preview()` | Raw Civitai API URL | **None** (passes through as-is) |

**tRPC adapter** (`buildCivitaiImageUrl()`):
- Receives UUID from tRPC API
- Constructs full CDN URL with correct params
- Video detection: `img.type === 'video'` OR filename `.mp4/.webm` extension
- **Warning:** If tRPC returns video with `type: undefined` and `name: "image.jpeg"`, it gets misdetected as image → CDN 500

**REST adapter** (`create_model_preview()`):
- Receives full URL from Civitai REST API (e.g., `https://image.civitai.com/.../original=true/file.jpeg`)
- Passes URL through unchanged — NO param transformation
- Only `detect_media_type()` for type classification, no URL rewriting

### Pack Detail Page (Local Files)

- URLs are local: `/previews/{pack_name}/resources/previews/{filename}`
- `isCivitaiDirectUrl()` returns **false** → NO URL transformation applied
- `getCivitaiVideoUrl()` / `getCivitaiThumbnailUrl()` do NOT modify local URLs
- Videos served directly by FastAPI static file mount

### MediaPreview Internal Transforms

`MediaPreview.tsx` has its own URL functions for **direct Civitai CDN URLs only**:
- `isCivitaiDirectUrl(url)` — checks `civitai.com` AND excludes `/api/browse/image-proxy`
- `getCivitaiVideoUrl(url)` — adds `anim=true,transcode=true,width=450` + `.mp4`
- `getCivitaiThumbnailUrl(url)` — adds `anim=false,transcode=true,width=450`

These are **duplicates** of `civitaiTransformers.ts` but serve different role (direct CDN vs proxy URLs).

---

## 3. Image Proxy

**Endpoint:** `/api/browse/image-proxy?url={encoded_url}`
**File:** `apps/api/src/routers/browse.py`

- Domain whitelist: `image.civitai.com`, `images.civitai.com`, etc.
- Handles B2 redirect (301/302) with stripped headers
- Retry once on transient 500/502/503 (images only, not videos)
- Uniform 30s timeout (was 5s for video before anim=true fix)

---

## 4. `<video>` Element Rules (MediaPreview.tsx)

### MUST have:
```tsx
<video
  ref={videoRef}
  src={isVideoVisible && videoUrl ? videoUrl : undefined}
  autoPlay={autoPlay && isVideoVisible}    // ← REQUIRED! Native browser autoplay
  loop
  muted={isMuted}
  playsInline
  preload={isVideoVisible || forceVideoDisplay ? "auto" : "none"}
  onLoadedData={handleVideoLoadedData}
  onError={handleVideoError}
/>
```

### NEVER do:
- **Remove `autoPlay` attribute** — programmatic `video.play()` alone has timing issues with local files
- **Use `<source>` children** instead of `src` attribute — local files have no `.webm` version, error events on `<source>` don't bubble to `<video>`, React conditional rendering of `<source>` can cause browser to not detect source changes
- **Limit concurrent video playback** (e.g., VideoPlaybackManager with MAX_CONCURRENT) — ALL videos must play simultaneously, no throttling
- **Add `optimized=true`** — removed, not needed

### Local video fallback flow:
1. `<img>` tries to load `.mp4` as thumbnail → fails
2. `handleImageError()` detects `isVideo` → sets `forceVideoDisplay=true` (NOT `imageError`)
3. `<video>` element becomes visible, starts loading
4. `onLoadedData` → `videoLoaded=true` → loading placeholder disappears
5. If video also fails → `handleVideoError()` → `imageError=true` → "Failed to load"

---

## 5. Smoke Tests

**Location:** `tests/smoke/`

```bash
# Offline only (<1s) — URL construction, audit
uv run pytest tests/smoke/test_01_url_construction.py -v

# All smoke tests including live CDN
uv run pytest tests/smoke/ -v -s

# Via verify.sh
./scripts/verify.sh --smoke        # offline only
./scripts/verify.sh --smoke-live   # all including live
```

| File | Tests | Type | What it tests |
|------|-------|------|--------------|
| `test_01_url_construction.py` | 33 | Offline | URL building, media detection, optimized=true audit |
| `test_02_cdn_direct.py` | 18 | Live | CDN responses, anim=true behavior, redirects |
| `test_03_proxy_endpoint.py` | 13 | Live | Proxy endpoint, domain whitelist, video handling |
| `test_04_search_pipeline.py` | 12 | Mixed | Meilisearch → transform → proxy pipeline |
| `test_05_juggernaut_e2e.py` | 12 | Live | Full E2E with real model (Juggernaut XL) |

---

## 6. Lessons Learned (Mistakes to Avoid)

### 1. Never remove `autoPlay` from `<video>` (2026-02-22)
**What happened:** During dual-source refactor, `autoPlay={autoPlay && isVideoVisible}` was accidentally removed. Pack detail videos stopped playing — showed permanent loading state.
**Why tests didn't catch it:** Vitest tests mock DOM, don't test actual browser video playback.
**Rule:** The `<video>` element in MediaPreview MUST always have the `autoPlay` attribute.

### 2. Never use dual `<source>` tags for video (2026-02-22)
**What happened:** Changed `<video src={url}>` to `<video><source .webm/><source .mp4/></video>`. Broke local pack videos because `.webm` files don't exist locally → failed request → browser didn't fallback reliably.
**Rule:** Always use `<video src={url} />` with direct `src` attribute, never `<source>` children.

### 3. Never limit video playback count (2026-02-22)
**What happened:** Wired `VideoPlaybackManager` (MAX_CONCURRENT=3) into MediaPreview. User rejected — ALL videos must play simultaneously.
**Rule:** No throttling of concurrent video playback. `VideoPlaybackManager.ts` exists but MUST NOT be used in MediaPreview.

### 4. Never make visual/functional changes without user approval (2026-02-22)
**What happened:** Dual source tags and VideoPlaybackManager were added as "improvements" without informing the user. Both had to be reverted.
**Rule:** Always inform user about ANY change that affects visual behavior or functionality before implementing.

### 5. Always test with BOTH Browse AND PackDetail (2026-02-22)
**What happened:** Browse page worked fine after changes, but PackDetail was broken. Different URL pipelines (Civitai CDN vs local files) behave differently.
**Rule:** When changing MediaPreview or video-related code, always verify on both Browse (CDN URLs) and PackDetail (local file URLs).

---

*Last updated: 2026-02-22*
