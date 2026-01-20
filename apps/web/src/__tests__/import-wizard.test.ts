/**
 * Tests for ImportWizardModal Component
 *
 * Tests cover:
 * - Version selection logic
 * - Import options state management
 * - Thumbnail selection
 * - File size calculations
 * - Preview collection and deduplication
 */

import { describe, it, expect } from 'vitest'

// ============================================================================
// Test Types (mirroring ImportWizardModal types)
// ============================================================================

interface VersionFile {
  id: number
  name: string
  sizeKB?: number
  type?: string
  primary?: boolean
}

interface VersionPreview {
  url: string
  nsfw?: boolean
  nsfwLevel?: number
  width?: number
  height?: number
  type?: 'image' | 'video'
}

interface ModelVersion {
  id: number
  name: string
  baseModel?: string
  downloadCount?: number
  files: VersionFile[]
  images: VersionPreview[]
}

interface ImportOptions {
  downloadImages: boolean
  downloadVideos: boolean
  includeNsfw: boolean
  downloadFromAllVersions: boolean
}

// ============================================================================
// Utility Functions (mirroring ImportWizardModal)
// ============================================================================

function formatFileSize(sizeKB?: number): string {
  if (!sizeKB) return 'Unknown'
  if (sizeKB < 1024) return `${sizeKB.toFixed(0)} KB`
  if (sizeKB < 1024 * 1024) return `${(sizeKB / 1024).toFixed(1)} MB`
  return `${(sizeKB / (1024 * 1024)).toFixed(2)} GB`
}

function formatNumber(num?: number): string {
  if (!num) return '0'
  if (num < 1000) return num.toString()
  if (num < 1000000) return `${(num / 1000).toFixed(1)}K`
  return `${(num / 1000000).toFixed(1)}M`
}

function getTotalSize(versions: ModelVersion[], selectedIds: Set<number>): number {
  return versions
    .filter(v => selectedIds.has(v.id))
    .reduce((total, v) => {
      const primaryFile = v.files.find(f => f.primary) || v.files[0]
      return total + (primaryFile?.sizeKB || 0)
    }, 0)
}

function collectPreviews(
  versions: ModelVersion[],
  selectedIds: Set<number>,
  maxPreviews: number = 16
): VersionPreview[] {
  const seenUrls = new Set<string>()
  const previews: VersionPreview[] = []

  for (const version of versions) {
    if (!selectedIds.has(version.id)) continue

    for (const preview of version.images || []) {
      if (seenUrls.has(preview.url)) continue
      seenUrls.add(preview.url)
      previews.push(preview)

      if (previews.length >= maxPreviews) break
    }

    if (previews.length >= maxPreviews) break
  }

  return previews
}

function isPreviewNsfw(preview: VersionPreview): boolean {
  return preview.nsfw === true || (preview.nsfwLevel || 1) >= 4
}

/**
 * Collects all unique previews from ALL versions (regardless of selection).
 */
function collectAllPreviews(versions: ModelVersion[]): VersionPreview[] {
  const seenUrls = new Set<string>()
  const previews: VersionPreview[] = []

  for (const version of versions) {
    for (const preview of version.images || []) {
      if (seenUrls.has(preview.url)) continue
      seenUrls.add(preview.url)
      previews.push(preview)
    }
  }

  return previews
}

/**
 * Calculate preview stats based on options.
 */
function calculatePreviewStats(
  previews: VersionPreview[],
  options: ImportOptions
): { imageCount: number; videoCount: number; estimatedSize: number } {
  let imageCount = 0
  let videoCount = 0
  let estimatedSize = 0

  for (const preview of previews) {
    const isNsfw = isPreviewNsfw(preview)
    if (isNsfw && !options.includeNsfw) continue

    const isVideo = preview.type === 'video'

    if (isVideo) {
      if (options.downloadVideos) {
        videoCount++
        estimatedSize += 10 * 1024 // ~10MB per video
      }
    } else {
      if (options.downloadImages) {
        imageCount++
        estimatedSize += 500 // ~500KB per image
      }
    }
  }

  return { imageCount, videoCount, estimatedSize }
}

function getCivitaiThumbnailUrl(url: string): string {
  if (!url.includes('civitai.com')) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}anim=false`
}

// ============================================================================
// Version Selection Tests
// ============================================================================

describe('Version Selection', () => {
  const mockVersions: ModelVersion[] = [
    {
      id: 1,
      name: 'v1.0 - HIGH',
      baseModel: 'SDXL',
      files: [{ id: 101, name: 'model-high.safetensors', sizeKB: 5242880, primary: true }],
      images: [{ url: 'https://civitai.com/img1.jpg' }],
    },
    {
      id: 2,
      name: 'v1.0 - LOW',
      baseModel: 'SDXL',
      files: [{ id: 102, name: 'model-low.safetensors', sizeKB: 2621440, primary: true }],
      images: [{ url: 'https://civitai.com/img2.jpg' }],
    },
    {
      id: 3,
      name: 'v0.9',
      baseModel: 'SD 1.5',
      files: [{ id: 103, name: 'model-old.safetensors', sizeKB: 1048576, primary: true }],
      images: [{ url: 'https://civitai.com/img3.jpg' }],
    },
  ]

  describe('Single version selection', () => {
    it('should default to first version selected', () => {
      const selectedIds = new Set([mockVersions[0].id])
      expect(selectedIds.has(1)).toBe(true)
      expect(selectedIds.size).toBe(1)
    })

    it('should toggle version selection', () => {
      const selectedIds = new Set<number>([1])

      // Toggle off
      selectedIds.delete(1)
      expect(selectedIds.has(1)).toBe(false)

      // Toggle on
      selectedIds.add(1)
      expect(selectedIds.has(1)).toBe(true)
    })
  })

  describe('Multi-version selection (WAN 2.2 use case)', () => {
    it('should allow selecting multiple versions (HIGH + LOW)', () => {
      const selectedIds = new Set<number>([1, 2])

      expect(selectedIds.has(1)).toBe(true) // HIGH
      expect(selectedIds.has(2)).toBe(true) // LOW
      expect(selectedIds.size).toBe(2)
    })

    it('should select all versions', () => {
      const selectedIds = new Set(mockVersions.map(v => v.id))

      expect(selectedIds.size).toBe(3)
      expect(selectedIds.has(1)).toBe(true)
      expect(selectedIds.has(2)).toBe(true)
      expect(selectedIds.has(3)).toBe(true)
    })

    it('should deselect all versions', () => {
      const selectedIds = new Set(mockVersions.map(v => v.id))
      selectedIds.clear()

      expect(selectedIds.size).toBe(0)
    })
  })

  describe('Total size calculation', () => {
    it('should calculate size for single version', () => {
      const selectedIds = new Set([1])
      const totalSize = getTotalSize(mockVersions, selectedIds)

      expect(totalSize).toBe(5242880) // 5 GB in KB
    })

    it('should calculate size for multiple versions', () => {
      const selectedIds = new Set([1, 2])
      const totalSize = getTotalSize(mockVersions, selectedIds)

      expect(totalSize).toBe(5242880 + 2621440) // HIGH + LOW
    })

    it('should return 0 when no versions selected', () => {
      const selectedIds = new Set<number>()
      const totalSize = getTotalSize(mockVersions, selectedIds)

      expect(totalSize).toBe(0)
    })
  })
})

// ============================================================================
// Import Options Tests
// ============================================================================

describe('Import Options', () => {
  describe('Default options', () => {
    it('should have sensible defaults', () => {
      const defaultOptions: ImportOptions = {
        downloadImages: true,
        downloadVideos: true,
        includeNsfw: true,
      }

      expect(defaultOptions.downloadImages).toBe(true)
      expect(defaultOptions.downloadVideos).toBe(true)
      expect(defaultOptions.includeNsfw).toBe(true)
    })
  })

  describe('Option toggling', () => {
    it('should toggle downloadImages', () => {
      const options: ImportOptions = {
        downloadImages: true,
        downloadVideos: true,
        includeNsfw: true,
      }

      options.downloadImages = !options.downloadImages
      expect(options.downloadImages).toBe(false)
    })

    it('should toggle downloadVideos', () => {
      const options: ImportOptions = {
        downloadImages: true,
        downloadVideos: true,
        includeNsfw: true,
      }

      options.downloadVideos = !options.downloadVideos
      expect(options.downloadVideos).toBe(false)
    })

    it('should toggle includeNsfw', () => {
      const options: ImportOptions = {
        downloadImages: true,
        downloadVideos: true,
        includeNsfw: true,
      }

      options.includeNsfw = !options.includeNsfw
      expect(options.includeNsfw).toBe(false)
    })
  })
})

// ============================================================================
// Preview Collection Tests
// ============================================================================

describe('Preview Collection', () => {
  const mockVersionsWithPreviews: ModelVersion[] = [
    {
      id: 1,
      name: 'v1',
      files: [],
      images: [
        { url: 'https://civitai.com/img1.jpg', nsfw: false },
        { url: 'https://civitai.com/img2.jpg', nsfw: true, nsfwLevel: 5 },
        { url: 'https://civitai.com/video1.mp4', type: 'video' },
      ],
    },
    {
      id: 2,
      name: 'v2',
      files: [],
      images: [
        { url: 'https://civitai.com/img1.jpg', nsfw: false }, // Duplicate!
        { url: 'https://civitai.com/img3.jpg', nsfw: false },
      ],
    },
  ]

  describe('collectPreviews', () => {
    it('should collect previews from selected versions', () => {
      const selectedIds = new Set([1])
      const previews = collectPreviews(mockVersionsWithPreviews, selectedIds)

      expect(previews.length).toBe(3)
    })

    it('should deduplicate previews by URL', () => {
      const selectedIds = new Set([1, 2])
      const previews = collectPreviews(mockVersionsWithPreviews, selectedIds)

      // img1.jpg appears in both versions but should only appear once
      const img1Count = previews.filter(p => p.url.includes('img1')).length
      expect(img1Count).toBe(1)
    })

    it('should limit previews to maxPreviews', () => {
      const selectedIds = new Set([1, 2])
      const previews = collectPreviews(mockVersionsWithPreviews, selectedIds, 2)

      expect(previews.length).toBe(2)
    })

    it('should return empty array when no versions selected', () => {
      const selectedIds = new Set<number>()
      const previews = collectPreviews(mockVersionsWithPreviews, selectedIds)

      expect(previews.length).toBe(0)
    })
  })

  describe('NSFW detection', () => {
    it('should detect NSFW from nsfw flag', () => {
      const preview: VersionPreview = { url: 'test.jpg', nsfw: true }
      expect(isPreviewNsfw(preview)).toBe(true)
    })

    it('should detect NSFW from nsfwLevel >= 4', () => {
      const preview: VersionPreview = { url: 'test.jpg', nsfwLevel: 4 }
      expect(isPreviewNsfw(preview)).toBe(true)
    })

    it('should NOT flag as NSFW when nsfwLevel < 4', () => {
      const preview: VersionPreview = { url: 'test.jpg', nsfwLevel: 2 }
      expect(isPreviewNsfw(preview)).toBe(false)
    })

    it('should NOT flag as NSFW when no flags set', () => {
      const preview: VersionPreview = { url: 'test.jpg' }
      expect(isPreviewNsfw(preview)).toBe(false)
    })
  })
})

// ============================================================================
// Thumbnail URL Tests
// ============================================================================

describe('Thumbnail URL Generation', () => {
  describe('getCivitaiThumbnailUrl', () => {
    it('should add anim=false to Civitai URLs', () => {
      const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid/image.jpeg'
      const result = getCivitaiThumbnailUrl(url)

      expect(result).toContain('anim=false')
    })

    it('should use & separator when URL has existing params', () => {
      const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid/image.jpeg?width=450'
      const result = getCivitaiThumbnailUrl(url)

      expect(result).toContain('&anim=false')
    })

    it('should use ? separator when URL has no params', () => {
      const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid/image.jpeg'
      const result = getCivitaiThumbnailUrl(url)

      expect(result).toContain('?anim=false')
    })

    it('should return non-Civitai URLs unchanged', () => {
      const url = 'https://example.com/image.jpg'
      const result = getCivitaiThumbnailUrl(url)

      expect(result).toBe(url)
    })
  })
})

// ============================================================================
// File Size Formatting Tests
// ============================================================================

describe('File Size Formatting', () => {
  describe('formatFileSize', () => {
    it('should return Unknown for undefined', () => {
      expect(formatFileSize(undefined)).toBe('Unknown')
    })

    it('should format KB correctly', () => {
      expect(formatFileSize(500)).toBe('500 KB')
    })

    it('should format MB correctly', () => {
      expect(formatFileSize(5120)).toBe('5.0 MB')
    })

    it('should format GB correctly', () => {
      expect(formatFileSize(5242880)).toBe('5.00 GB')
    })
  })

  describe('formatNumber', () => {
    it('should return 0 for undefined', () => {
      expect(formatNumber(undefined)).toBe('0')
    })

    it('should format small numbers as-is', () => {
      expect(formatNumber(500)).toBe('500')
    })

    it('should format thousands with K suffix', () => {
      expect(formatNumber(5000)).toBe('5.0K')
    })

    it('should format millions with M suffix', () => {
      expect(formatNumber(5000000)).toBe('5.0M')
    })
  })
})

// ============================================================================
// Import Validation Tests
// ============================================================================

describe('Import Validation', () => {
  it('should prevent import when no versions selected', () => {
    const selectedVersionIds = new Set<number>()
    const canImport = selectedVersionIds.size > 0

    expect(canImport).toBe(false)
  })

  it('should allow import when at least one version selected', () => {
    const selectedVersionIds = new Set([1])
    const canImport = selectedVersionIds.size > 0

    expect(canImport).toBe(true)
  })

  it('should include selected version IDs in import payload', () => {
    const selectedVersionIds = new Set([1, 2])
    const payload = {
      url: 'https://civitai.com/models/123',
      version_ids: Array.from(selectedVersionIds),
    }

    expect(payload.version_ids).toEqual([1, 2])
  })
})

// ============================================================================
// Download From All Versions Tests
// ============================================================================

describe('Download From All Versions Option', () => {
  const mockVersionsMultiple: ModelVersion[] = [
    {
      id: 1,
      name: 'v1.0',
      files: [],
      images: [
        { url: 'https://civitai.com/v1_img1.jpg' },
        { url: 'https://civitai.com/v1_img2.jpg' },
        { url: 'https://civitai.com/v1_video1.mp4', type: 'video' },
      ],
    },
    {
      id: 2,
      name: 'v2.0',
      files: [],
      images: [
        { url: 'https://civitai.com/v2_img1.jpg' },
        { url: 'https://civitai.com/v2_img2.jpg' },
        { url: 'https://civitai.com/v2_video1.mp4', type: 'video' },
      ],
    },
    {
      id: 3,
      name: 'v3.0',
      files: [],
      images: [
        { url: 'https://civitai.com/v3_img1.jpg' },
        { url: 'https://civitai.com/v3_video1.mp4', type: 'video' },
      ],
    },
  ]

  describe('collectAllPreviews', () => {
    it('should collect all previews from ALL versions', () => {
      const allPreviews = collectAllPreviews(mockVersionsMultiple)

      // Total: v1(3) + v2(3) + v3(2) = 8
      expect(allPreviews.length).toBe(8)
    })

    it('should deduplicate by URL across all versions', () => {
      const versionsWithDuplicates: ModelVersion[] = [
        {
          id: 1,
          name: 'v1',
          files: [],
          images: [
            { url: 'https://civitai.com/shared.jpg' },
            { url: 'https://civitai.com/v1_unique.jpg' },
          ],
        },
        {
          id: 2,
          name: 'v2',
          files: [],
          images: [
            { url: 'https://civitai.com/shared.jpg' }, // Duplicate
            { url: 'https://civitai.com/v2_unique.jpg' },
          ],
        },
      ]

      const allPreviews = collectAllPreviews(versionsWithDuplicates)

      // shared.jpg only counted once
      expect(allPreviews.length).toBe(3)
    })
  })

  describe('Preview stats with downloadFromAllVersions', () => {
    const defaultOptions: ImportOptions = {
      downloadImages: true,
      downloadVideos: true,
      includeNsfw: true,
      downloadFromAllVersions: true,
    }

    it('should count all previews when downloadFromAllVersions is true', () => {
      const selectedIds = new Set([1]) // Only v1 selected
      const allPreviews = collectAllPreviews(mockVersionsMultiple)
      const selectedPreviews = collectPreviews(mockVersionsMultiple, selectedIds)

      const allStats = calculatePreviewStats(allPreviews, defaultOptions)
      const selectedStats = calculatePreviewStats(selectedPreviews, defaultOptions)

      // All versions: 5 images + 3 videos = 8 total
      expect(allStats.imageCount).toBe(5)
      expect(allStats.videoCount).toBe(3)

      // Selected v1 only: 2 images + 1 video = 3 total
      expect(selectedStats.imageCount).toBe(2)
      expect(selectedStats.videoCount).toBe(1)
    })

    it('should use selected version previews when downloadFromAllVersions is false', () => {
      const selectedIds = new Set([1, 2])
      const selectedPreviews = collectPreviews(mockVersionsMultiple, selectedIds)

      const stats = calculatePreviewStats(selectedPreviews, {
        ...defaultOptions,
        downloadFromAllVersions: false,
      })

      // v1(3) + v2(3) = 6 total
      expect(stats.imageCount).toBe(4) // v1(2) + v2(2)
      expect(stats.videoCount).toBe(2) // v1(1) + v2(1)
    })

    it('should respect NSFW filter regardless of version source', () => {
      const versionsWithNsfw: ModelVersion[] = [
        {
          id: 1,
          name: 'v1',
          files: [],
          images: [
            { url: 'https://civitai.com/safe.jpg' },
            { url: 'https://civitai.com/nsfw.jpg', nsfw: true },
          ],
        },
        {
          id: 2,
          name: 'v2',
          files: [],
          images: [
            { url: 'https://civitai.com/v2_safe.jpg' },
            { url: 'https://civitai.com/v2_nsfw.jpg', nsfwLevel: 5 },
          ],
        },
      ]

      const allPreviews = collectAllPreviews(versionsWithNsfw)

      // With NSFW enabled
      const statsWithNsfw = calculatePreviewStats(allPreviews, {
        ...defaultOptions,
        includeNsfw: true,
      })
      expect(statsWithNsfw.imageCount).toBe(4)

      // With NSFW disabled
      const statsWithoutNsfw = calculatePreviewStats(allPreviews, {
        ...defaultOptions,
        includeNsfw: false,
      })
      expect(statsWithoutNsfw.imageCount).toBe(2) // Only safe images
    })

    it('should correctly calculate when toggling downloadFromAllVersions', () => {
      const selectedIds = new Set([1])

      // Simulate what happens in the component
      const allPreviews = collectAllPreviews(mockVersionsMultiple)
      const selectedPreviews = collectPreviews(mockVersionsMultiple, selectedIds)

      // User enables "download from all versions"
      const previewsToUse_AllVersions = allPreviews
      const stats_All = calculatePreviewStats(previewsToUse_AllVersions, defaultOptions)
      expect(stats_All.imageCount + stats_All.videoCount).toBe(8)

      // User disables "download from all versions"
      const previewsToUse_SelectedOnly = selectedPreviews
      const stats_Selected = calculatePreviewStats(previewsToUse_SelectedOnly, defaultOptions)
      expect(stats_Selected.imageCount + stats_Selected.videoCount).toBe(3)
    })
  })

  describe('Import payload with downloadFromAllVersions', () => {
    it('should include download_from_all_versions in API payload', () => {
      const options: ImportOptions = {
        downloadImages: true,
        downloadVideos: true,
        includeNsfw: true,
        downloadFromAllVersions: true,
      }

      const payload = {
        url: 'https://civitai.com/models/123',
        version_ids: [1],
        download_images: options.downloadImages,
        download_videos: options.downloadVideos,
        include_nsfw: options.includeNsfw,
        download_from_all_versions: options.downloadFromAllVersions,
      }

      expect(payload.download_from_all_versions).toBe(true)
    })

    it('should allow setting downloadFromAllVersions to false', () => {
      const options: ImportOptions = {
        downloadImages: true,
        downloadVideos: true,
        includeNsfw: true,
        downloadFromAllVersions: false,
      }

      const payload = {
        url: 'https://civitai.com/models/123',
        version_ids: [1, 2],
        download_from_all_versions: options.downloadFromAllVersions,
      }

      expect(payload.download_from_all_versions).toBe(false)
      expect(payload.version_ids).toEqual([1, 2])
    })
  })
})

// ============================================================================
// Thumbnail Selection Tests (Cover URL)
// ============================================================================

describe('Thumbnail Selection', () => {
  it('should allow selecting any preview as thumbnail', () => {
    const previews: VersionPreview[] = [
      { url: 'https://civitai.com/img1.jpg' },
      { url: 'https://civitai.com/img2.jpg' },
      { url: 'https://civitai.com/video1.mp4', type: 'video' },
    ]

    // Simulate selecting second image as thumbnail
    const selectedThumbnail = previews[1].url

    expect(selectedThumbnail).toBe('https://civitai.com/img2.jpg')
  })

  it('should include thumbnail_url in import payload', () => {
    const selectedThumbnail = 'https://civitai.com/my-selected-thumb.jpg'

    const payload = {
      url: 'https://civitai.com/models/123',
      version_ids: [1],
      thumbnail_url: selectedThumbnail,
    }

    expect(payload.thumbnail_url).toBe(selectedThumbnail)
  })

  it('should allow video as thumbnail', () => {
    const videoThumbnail = 'https://civitai.com/video-preview.mp4'

    const payload = {
      url: 'https://civitai.com/models/123',
      version_ids: [1],
      thumbnail_url: videoThumbnail,
    }

    expect(payload.thumbnail_url).toContain('.mp4')
  })
})
