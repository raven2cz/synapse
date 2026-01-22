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
// Media Detection (MUST match backend!)
// =============================================================================

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
  // 2. item.modelVersions[0].images (full model response)
  let images: Record<string, unknown>[] = []

  // Check top-level images first (tRPC list format)
  if (Array.isArray(item.images) && item.images.length > 0) {
    images = item.images as Record<string, unknown>[]
  }
  // Fallback to modelVersions (full model format)
  else if (item.modelVersions) {
    const firstVersion = (item.modelVersions as Record<string, unknown>[])?.[0]
    if (firstVersion?.images) {
      images = firstVersion.images as Record<string, unknown>[]
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
function transformPreview(img: Record<string, unknown>): ModelPreview {
  const rawUrl = (img.url as string) || ''
  const filename = img.name as string | null
  const imgType = img.type as string | undefined

  // Determine if video:
  // 1. tRPC provides explicit type field
  // 2. Fallback to URL-based detection (for REST/other formats)
  const isVideoByType = imgType === 'video'
  const isVideoByUrl = rawUrl.startsWith('http') && detectMediaType(rawUrl) === 'video'
  const isVideo = isVideoByType || isVideoByUrl

  // Build full URL from UUID if needed
  const url = buildCivitaiImageUrl(rawUrl, filename, isVideo)

  // Determine media type
  const mediaType: MediaType = isVideo ? 'video' : 'image'

  // CRITICAL: NSFW detection - both flag and nsfwLevel
  const nsfwLevel = (img.nsfwLevel as number) || 0
  const isNsfw = (img.nsfw as boolean) === true || nsfwLevel >= 2

  return {
    url,
    nsfw: isNsfw,
    width: img.width as number | undefined,
    height: img.height as number | undefined,
    meta: img.meta as Record<string, unknown> | undefined,
    media_type: mediaType,
    // CRITICAL: Video thumbnail
    thumbnail_url: mediaType === 'video' ? getVideoThumbnailUrl(url) : undefined,
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
 */
export function transformTrpcModelDetail(
  data: Record<string, unknown>
): ModelDetail {
  const base = transformTrpcModel(data)
  const firstVersion = (data.modelVersions as Record<string, unknown>[] | undefined)?.[0]
  const stats = data.stats as Record<string, unknown> | undefined

  return {
    ...base,
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
