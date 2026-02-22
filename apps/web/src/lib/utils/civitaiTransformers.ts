/**
 * Civitai Data Transformers for Phase 5
 *
 * These transformers convert tRPC API responses to the unified CivitaiModel format.
 * CRITICAL: Video detection must match backend logic in src/utils/media_detection.py!
 */

import type {
  CivitaiModel,
  ModelPreview,
  ModelVersion,
  ModelDetail,
  ModelFile,
} from '@/lib/api/searchTypes'
import type { MediaType } from '@/lib/media'

// =============================================================================
// Image Proxy (for Civitai CDN URLs)
// =============================================================================

/**
 * Convert a Civitai CDN URL to use our image proxy.
 * This avoids CORS issues and potential blocking.
 */
export function toProxyUrl(url: string): string {
  if (!url) return url

  // Already proxied — don't double-wrap
  if (url.includes('/api/browse/image-proxy')) {
    return url
  }

  // Only proxy Civitai CDN URLs
  if (
    !url.includes('image.civitai.com') &&
    !url.includes('images.civitai.com') &&
    !url.includes('cdn.civitai.com')
  ) {
    return url
  }

  return `/api/browse/image-proxy?url=${encodeURIComponent(url)}`
}

// =============================================================================
// Media Detection (MUST match backend!)
// =============================================================================

/**
 * Check if filename indicates a video file.
 * tRPC API returns filename in the `name` field (e.g., "video.mp4", "image.jpeg")
 */
function isVideoFilename(filename: string | null): boolean {
  if (!filename) return false
  return /\.(mp4|webm|mov|avi|mkv)$/i.test(filename)
}

/**
 * Detect media type from URL.
 * CRITICAL: This MUST match backend logic in src/utils/media_detection.py!
 */
export function detectMediaType(url: string): MediaType {
  if (!url) return 'unknown'

  const lowerUrl = url.toLowerCase()

  // Extension check - video extensions
  if (lowerUrl.match(/\.(mp4|webm|mov|avi|mkv)(\?|$)/)) {
    return 'video'
  }

  // Civitai transcode=true pattern indicates video
  // BUT anim=false means it's a static thumbnail
  if (lowerUrl.includes('transcode=true') && !lowerUrl.includes('anim=false')) {
    return 'video'
  }

  // Path pattern - /videos/ in URL
  if (lowerUrl.includes('/videos/')) {
    return 'video'
  }

  // type=video query param
  if (lowerUrl.includes('type=video')) {
    return 'video'
  }

  // Default to image (same as backend)
  return 'image'
}

/**
 * Get video thumbnail URL (static frame).
 * CRITICAL: This MUST match backend logic in src/utils/media_detection.py!
 */
export function getVideoThumbnailUrl(url: string, width = 450): string {
  if (!url) return url

  // Non-Civitai: simple extension replacement
  if (!url.includes('civitai.com')) {
    return url.replace(/\.(mp4|webm|mov)$/i, '.jpg')
  }

  // Civitai uses path-based params like /anim=false,width=450/
  // Find the params segment or create one
  const parts = url.split('/')
  const filename = parts.pop() || ''

  // Look for existing params segment (contains '=' but not '://')
  let paramsIdx = parts.findIndex((p) => p.includes('=') && !p.includes('://'))

  if (paramsIdx === -1) {
    // No params yet, add before filename
    parts.push(`anim=false,transcode=true,width=${width}`)
  } else {
    // Modify existing params
    let params = parts[paramsIdx]

    // Ensure anim=false (for static thumbnail)
    if (params.includes('anim=true')) {
      params = params.replace('anim=true', 'anim=false')
    } else if (!params.includes('anim=')) {
      params = `anim=false,${params}`
    }

    // Update width
    params = params.replace(/width=\d+/, `width=${width}`)
    if (!params.includes('width=')) {
      params += `,width=${width}`
    }

    parts[paramsIdx] = params
  }

  parts.push(filename)
  return parts.join('/')
}

// =============================================================================
// tRPC Model Transformer
// =============================================================================

/**
 * Transform tRPC model item to CivitaiModel.
 * Handles video detection for previews - CRITICAL!
 */
export function transformTrpcModel(item: Record<string, unknown>): CivitaiModel {
  const versions = transformVersions(item.modelVersions as Record<string, unknown>[] | undefined)

  // tRPC model.getAll returns images at TOP LEVEL, not in modelVersions!
  // Try multiple locations for images:
  // 1. item.images (tRPC list response)
  // 2. item.modelVersions[].images (full model response - ALL versions!)
  let images: Record<string, unknown>[] = []

  // Check top-level images first (tRPC list format)
  if (Array.isArray(item.images) && item.images.length > 0) {
    images = item.images as Record<string, unknown>[]
  }
  // Fallback to modelVersions (full model format) - collect from ALL versions
  else if (item.modelVersions) {
    const allVersions = item.modelVersions as Record<string, unknown>[]
    for (const version of allVersions) {
      if (version?.images && Array.isArray(version.images)) {
        images.push(...(version.images as Record<string, unknown>[]))
      }
    }
  }

  const previews: ModelPreview[] = images.slice(0, 8).map(transformPreview)

  // Get creator name
  const user = item.user as Record<string, unknown> | undefined
  const creator = item.creator as Record<string, unknown> | undefined
  const creatorName = (user?.username || creator?.username || '') as string

  // Get stats
  const stats = item.stats as Record<string, unknown> | undefined

  return {
    id: item.id as number,
    name: (item.name as string) || '',
    description: item.description as string | undefined,
    type: (item.type as string) || '',
    // CRITICAL: Model-level NSFW
    nsfw: (item.nsfw as boolean) || false,
    tags: (item.tags as string[]) || [],
    creator: creatorName,
    stats: {
      downloadCount: stats?.downloadCount as number | undefined,
      favoriteCount: stats?.favoriteCount as number | undefined,
      commentCount: stats?.commentCount as number | undefined,
      ratingCount: stats?.ratingCount as number | undefined,
      rating: stats?.rating as number | undefined,
      thumbsUpCount: stats?.thumbsUpCount as number | undefined,
    },
    versions,
    previews,
  }
}

/**
 * Build full Civitai image URL from UUID.
 * tRPC returns only UUID, we need to construct full URL.
 */
function buildCivitaiImageUrl(
  uuid: string,
  filename: string | null,
  isVideo = false,
  width = 450
): string {
  if (!uuid) return ''

  // If it's already a full URL, return as-is
  if (uuid.startsWith('http')) return uuid

  // Civitai CDN base
  const cdnBase = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA'

  // Use filename or default
  let name = filename || (isVideo ? 'video.mp4' : 'image.jpeg')

  // For videos, ensure .mp4 extension
  if (isVideo && !name.toLowerCase().endsWith('.mp4')) {
    name = name.replace(/\.[^.]+$/, '.mp4')
  }

  // Build params based on type
  const params = isVideo
    ? `transcode=true,width=${width}`
    : `width=${width}`

  return `${cdnBase}/${uuid}/${params}/${name}`
}

/**
 * Transform a single preview/image.
 */
export function transformPreview(img: Record<string, unknown>): ModelPreview {
  const rawUrl = (img.url as string) || ''
  const filename = img.name as string | null
  const imgType = img.type as string | undefined

  // Determine if video:
  // 1. tRPC provides explicit type field
  // 2. Filename extension (e.g., "video.mp4") - critical for tRPC UUID responses!
  // 3. Fallback to URL-based detection (for REST/other formats)
  const isVideoByType = imgType === 'video'
  const isVideoByFilename = isVideoFilename(filename)
  const isVideoByUrl = rawUrl.startsWith('http') && detectMediaType(rawUrl) === 'video'
  const isVideo = isVideoByType || isVideoByFilename || isVideoByUrl

  // Build full URL from UUID if needed
  const originalUrl = buildCivitaiImageUrl(rawUrl, filename, isVideo)

  // CRITICAL: Proxy Civitai URLs to avoid CORS/blocking
  const url = toProxyUrl(originalUrl)

  // Determine media type
  const mediaType: MediaType = isVideo ? 'video' : 'image'

  // CRITICAL: NSFW detection - both flag and nsfwLevel
  const nsfwLevel = (img.nsfwLevel as number) || 0
  const isNsfw = (img.nsfw as boolean) === true || nsfwLevel >= 2

  // CRITICAL: Video thumbnail - also needs proxy
  const thumbnailUrl =
    mediaType === 'video' ? toProxyUrl(getVideoThumbnailUrl(originalUrl)) : undefined

  return {
    url,
    nsfw: isNsfw,
    width: img.width as number | undefined,
    height: img.height as number | undefined,
    meta: img.meta as Record<string, unknown> | undefined,
    media_type: mediaType,
    thumbnail_url: thumbnailUrl,
  }
}

/**
 * Transform versions array.
 */
function transformVersions(
  versions: Record<string, unknown>[] | undefined
): ModelVersion[] {
  if (!versions) return []

  return versions.map((ver) => {
    const files = (ver.files as Record<string, unknown>[]) || []
    const primaryFile =
      files.find((f) => f.primary as boolean) || files[0] || {}

    return {
      id: ver.id as number,
      name: (ver.name as string) || '',
      base_model: ver.baseModel as string | undefined,
      download_url:
        (primaryFile.downloadUrl as string) ||
        (ver.downloadUrl as string) ||
        undefined,
      file_size: primaryFile.sizeKB
        ? Math.round((primaryFile.sizeKB as number) * 1024)
        : undefined,
      trained_words: (ver.trainedWords as string[]) || [],
      files: files.map(transformFile),
      published_at: ver.publishedAt as string | undefined,
    }
  })
}

/**
 * Transform a single file.
 */
function transformFile(f: Record<string, unknown>): ModelFile {
  const hashes = f.hashes as Record<string, unknown> | undefined

  return {
    id: (f.id as number) || 0,
    name: (f.name as string) || '',
    size_kb: f.sizeKB as number | undefined,
    download_url: f.downloadUrl as string | undefined,
    hash_autov2: hashes?.AutoV2 as string | undefined,
    hash_sha256: hashes?.SHA256 as string | undefined,
  }
}

// =============================================================================
// tRPC Model Detail Transformer
// =============================================================================

/**
 * Transform tRPC model detail response to ModelDetail.
 * Collects up to 50 previews from ALL versions (more than base transformer).
 */
export function transformTrpcModelDetail(
  data: Record<string, unknown>
): ModelDetail {
  const base = transformTrpcModel(data)
  const allVersions = (data.modelVersions as Record<string, unknown>[] | undefined) || []
  const firstVersion = allVersions[0]
  const stats = data.stats as Record<string, unknown> | undefined

  // Collect ALL images from ALL versions (up to 50)
  // Note: Images are injected from posts[] by trpcBridgeAdapter before calling this
  const allImages: Record<string, unknown>[] = []
  for (const version of allVersions) {
    if (version?.images && Array.isArray(version.images)) {
      allImages.push(...(version.images as Record<string, unknown>[]))
    }
  }

  // Transform to previews with proxy URLs (up to 50 for model detail)
  const previews = allImages.slice(0, 50).map(transformPreview)

  return {
    ...base,
    previews, // Override base previews with full collection
    trained_words: (firstVersion?.trainedWords as string[]) || [],
    base_model: firstVersion?.baseModel as string | undefined,
    download_count: stats?.downloadCount as number | undefined,
    rating: stats?.rating as number | undefined,
    rating_count: stats?.ratingCount as number | undefined,
    published_at: data.publishedAt as string | undefined,
    example_params: extractExampleParams(data),
  }
}

/**
 * Extract example generation parameters from model images.
 */
function extractExampleParams(
  data: Record<string, unknown>
): Record<string, unknown> | undefined {
  const firstVersion = (data.modelVersions as Record<string, unknown>[] | undefined)?.[0]
  const images = (firstVersion?.images as Record<string, unknown>[]) || []

  for (const img of images) {
    const meta = img.meta as Record<string, unknown> | undefined
    if (meta) {
      return {
        sampler: meta.sampler,
        steps: meta.steps,
        cfg_scale: meta.cfgScale,
        clip_skip: meta.clipSkip,
        seed: meta.seed,
      }
    }
  }

  return undefined
}

// =============================================================================
// Meilisearch Model Transformer
// =============================================================================

/**
 * Build Civitai image URL from Meilisearch profilePicture or image data.
 * Meilisearch returns a different structure than tRPC.
 */
function buildMeilisearchImageUrl(
  img: Record<string, unknown>,
  width = 450
): string {
  const uuid = img.url as string
  if (!uuid) return ''

  // If it's already a full URL, return as-is
  if (uuid.startsWith('http')) return uuid

  // Civitai CDN base - path-based params!
  const cdnBase = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA'

  // Meilisearch provides hash/type/name in the structure
  const imgType = img.type as string | undefined
  const isVideo = imgType === 'video'
  const name = (img.name as string) || (isVideo ? 'video.mp4' : 'image.jpeg')

  // Build params - Civitai uses comma-separated path params, NOT query strings
  // Example: /uuid/width=450,optimized=true/filename.jpeg
  const params = isVideo
    ? `transcode=true,width=${width},optimized=true`
    : `width=${width},optimized=true`

  return `${cdnBase}/${uuid}/${params}/${name}`
}

/**
 * Transform Meilisearch hit to ModelPreview.
 */
function transformMeilisearchPreview(
  img: Record<string, unknown>
): ModelPreview {
  const imgType = img.type as string | undefined
  const isVideo = imgType === 'video'

  // Build full URL
  const originalUrl = buildMeilisearchImageUrl(img)
  const url = toProxyUrl(originalUrl)

  // Media type
  const mediaType: MediaType = isVideo ? 'video' : 'image'

  // NSFW detection
  const nsfwLevel = (img.nsfwLevel as number) || 1
  const isNsfw = nsfwLevel >= 4 // Meilisearch: 1=None, 2=Soft, 4=Mature, 8=X, 16=Blocked

  // Video thumbnail
  const thumbnailUrl =
    mediaType === 'video' ? toProxyUrl(getVideoThumbnailUrl(originalUrl)) : undefined

  return {
    url,
    nsfw: isNsfw,
    width: img.width as number | undefined,
    height: img.height as number | undefined,
    meta: img.metadata as Record<string, unknown> | undefined,
    media_type: mediaType,
    thumbnail_url: thumbnailUrl,
  }
}

/**
 * Transform Meilisearch hit to CivitaiModel.
 *
 * Meilisearch returns a flattened structure with different field names:
 * - id, name, type, nsfw (same)
 * - nsfwLevel: [1,2,4,8,16,32] array
 * - metrics: { downloadCount, thumbsUpCount, ... }
 * - user: { id, username, ... }
 * - hashes, triggerWords, etc.
 */
export function transformMeilisearchModel(
  item: Record<string, unknown>
): CivitaiModel {
  // User info
  const user = item.user as Record<string, unknown> | undefined
  const creatorName = (user?.username as string) || ''

  // Stats/metrics
  const metrics = item.metrics as Record<string, unknown> | undefined

  // NSFW - Meilisearch returns array of levels
  const nsfwLevels = (item.nsfwLevel as number[]) || []
  const maxNsfwLevel = Math.max(...nsfwLevels, 1)
  const isNsfw = maxNsfwLevel >= 4 // 4=Mature, 8=X, etc.

  // Model preview images — Meilisearch includes up to 10 images per model
  const images = (item.images as Record<string, unknown>[] | undefined) || []
  const previews: ModelPreview[] = images.slice(0, 8).map(transformMeilisearchPreview)

  // Version info (Meilisearch has flattened version data)
  const version = item.version as Record<string, unknown> | undefined
  const versions: ModelVersion[] = []

  if (version) {
    versions.push({
      id: (version.id as number) || 0,
      name: (version.name as string) || '',
      base_model: version.baseModel as string | undefined,
      trained_words: (item.triggerWords as string[]) || [],
      files: [],
      published_at: item.lastVersionAt as string | undefined,
    })
  }

  return {
    id: item.id as number,
    name: (item.name as string) || '',
    description: undefined, // Meilisearch doesn't include description in list
    type: (item.type as string) || '',
    nsfw: (item.nsfw as boolean) || isNsfw,
    tags: [], // Tags are in facets, not individual items
    creator: creatorName,
    stats: {
      downloadCount: metrics?.downloadCount as number | undefined,
      favoriteCount: undefined,
      commentCount: metrics?.commentCount as number | undefined,
      ratingCount: undefined,
      rating: undefined,
      thumbsUpCount: metrics?.thumbsUpCount as number | undefined,
    },
    versions,
    previews,
  }
}
