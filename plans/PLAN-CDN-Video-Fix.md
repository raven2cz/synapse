# CDN/Proxy Video Fix — Integration Plan

## Status: ✅ IMPLEMENTED — čeká manuální test v prohlížeči

**Date:** 2026-02-22
**Based on:** Smoke test analysis & Civitai source code review

---

## Root Cause Analysis

### Problem 1: Videos Don't Play (Browse + Pack Detail)
**Root cause:** Missing `anim=true` parameter in video URL construction.

| URL params | CDN behavior | Result |
|------------|-------------|--------|
| `anim=true,transcode=true,width=450` | Cloudflare serves directly | **200**, video/mp4, 31MB, 1.2s |
| `transcode=true,width=450` (no anim) | Redirect to B2 storage | **301 → 401** auth failure |
| `anim=false,transcode=true,width=450` | Static thumbnail | **200**, image/webp, 14KB, 38ms |

**Evidence:** Civitai's own `useEdgeUrl()` in `cf-images-utils.ts`:
```typescript
if (type === 'video') {
  transcode = true;
  anim = anim ?? true;  // DEFAULT anim=true for videos!
}
```

### Problem 2: "Failed loads" Messages in Search Results
**Root cause:** Same as Problem 1. Video cards with `autoPlay={true}` attempt to load `.mp4` through proxy → proxy gets 301→B2→401 → returns 502 → `handleVideoError()` shows "Load failed".

### Problem 3: `optimized=true` in URLs
**Status:** No longer causes CDN errors (Civitai fixed it), but was present in 4 files as dead/redundant code. Returns WebP (9KB) vs JPEG (19KB) — it's a format hint, not a bug. Cleaned up.

---

## Implemented Fixes

### ✅ Fix 1: Add `anim=true` to Video URLs

| Soubor | Funkce | Změna |
|--------|--------|-------|
| `civitaiTransformers.ts` | `buildCivitaiImageUrl()` | `transcode=true,width=…` → `anim=true,transcode=true,width=…` |
| `civitaiTransformers.ts` | `buildMeilisearchImageUrl()` | stejná změna |
| `MediaPreview.tsx` | `getCivitaiVideoUrl()` | `transcode=true,width=…,optimized=true` → `anim=true,transcode=true,width=…` |
| `FullscreenMediaViewer.tsx` | `getCivitaiVideoUrl()` | stejná změna |

### ✅ Fix 1b: Remove `optimized=true`

| Soubor | Funkce | Změna |
|--------|--------|-------|
| `MediaPreview.tsx` | `getCivitaiThumbnailUrl()` | odstraněno `,optimized=true` |
| `FullscreenMediaViewer.tsx` | `getCivitaiThumbnailUrl()` | odstraněno `,optimized=true` |
| `media_detection.py` | `get_video_thumbnail_url()` | odstraněno `,optimized=true` + docstring |

### ✅ Fix 2: Remove Video Fast-Fail Timeout

| Soubor | Změna |
|--------|-------|
| `browse.py` | `timeout = 5.0 if is_video else 30.0` → `timeout = 30.0` |

S `anim=true` video URL neředirectuje na B2, servíruje přímo z Cloudflare. 5s fast-fail už není potřeba.

### ⚠️ Fix 3: Dual `<source>` Tags (WebM + MP4) — ČEKÁ OVĚŘENÍ

**Změna:** `<video src={url}>` → `<video><source src="...webm" /><source src="...mp4" /></video>`

Aplikováno v:
- `MediaPreview.tsx` — video element
- `FullscreenMediaViewer.tsx` — video element

**POZOR:** Nebylo ověřeno, zda Civitai CDN servíruje `.webm` verzi! Pokud ne, prohlížeč provede zbytečný failed request na `.webm` před tím, než přejde na `.mp4`. Civitai v svém kódu (`EdgeVideo.tsx`) toto používá, ale neověřili jsme to live.

**Pokud nefunguje:** Vrátit na `<video src={videoUrl}>` v obou souborech.

---

## ZAMÍTNUTO

### ❌ Fix 3 (původní): VideoPlaybackManager v MediaPreview
~~Napojení `useManagedVideo()` s MAX_CONCURRENT=3 do MediaPreview.~~

**Zamítnuto uživatelem** — všechna videa se musí přehrávat, žádné omezování.

### ❌ Fix 5: Deduplikace URL logiky
Lokální funkce v `MediaPreview.tsx` a `FullscreenMediaViewer.tsx` (`getCivitaiVideoUrl`, `getCivitaiThumbnailUrl`, `isCivitaiDirectUrl`, `isLikelyVideo`) jsou duplicitní s `civitaiTransformers.ts`. Ale plní jinou roli (direct CDN URL vs proxy URL transformace). Odloženo.

---

## Test Results (po všech fixech)

| Suite | Count | Status |
|-------|-------|--------|
| Backend (pytest) | 1172 | ✅ All pass |
| Frontend (vitest) | 676 | ✅ All pass |
| Smoke tests | 87 | ✅ All pass |
| Smoke audit (optimized=true) | 5/5 | ✅ All pass |

### Smoke Test Groups

| Group | Tests | Status |
|-------|-------|--------|
| 1: URL Construction (offline) | 33 | ✅ All pass |
| 2: CDN Direct (live) | 18 | ✅ All pass |
| 3: Proxy Endpoint (live) | 13 | ✅ All pass |
| 4: Search Pipeline (mixed) | 12 | ✅ All pass |
| 5: Juggernaut E2E (live) | 12 | ✅ All pass |

---

## Smoke Test Infrastructure

### Created Files (13)
```
tests/smoke/
├── __init__.py
├── conftest.py                     # Shared fixtures, httpx clients, markers
├── fixtures/
│   ├── __init__.py
│   └── known_urls.py               # Stable CDN UUIDs, URLs, magic bytes
├── utils/
│   ├── __init__.py
│   ├── http_logger.py              # Redirect chain tracer
│   └── cdn_prober.py               # Python port of URL builders
├── test_01_url_construction.py     # 33 offline tests
├── test_02_cdn_direct.py           # 18 live CDN tests
├── test_03_proxy_endpoint.py       # 13 proxy tests
├── test_04_search_pipeline.py      # 12 pipeline tests
├── test_05_juggernaut_e2e.py       # 12 E2E tests
└── run_smoke_tests.sh              # Runner script
```

### Modified Files (2)
- `tests/conftest.py` — smoke, live, proxy markers + auto-marking
- `scripts/verify.sh` — `--smoke` / `--smoke-live` options, excluded smoke from default

### How to Run
```bash
# Offline only (<1s)
uv run pytest tests/smoke/test_01_url_construction.py -v -s

# Live CDN
uv run pytest tests/smoke/ -v -s

# Via verify.sh
./scripts/verify.sh --smoke        # offline only
./scripts/verify.sh --smoke-live   # all including live
```

---

## Manual Browser Test Checklist

- [ ] Browse page → hledat "Juggernaut XL"
- [ ] Video preview autoplay funguje
- [ ] Všechna videa se přehrávají (žádný limit)
- [ ] Click na video → FullscreenMediaViewer přehrává video
- [ ] Quality selector (SD/HD/FHD) funguje
- [ ] Žádné "Failed load" hlášky
- [ ] Thumbnail (anim=false) se zobrazuje správně
- [ ] WebM/MP4 dual source funguje (nebo vrátit na single `<video src>`)

---

*Poslední aktualizace: 2026-02-22*
