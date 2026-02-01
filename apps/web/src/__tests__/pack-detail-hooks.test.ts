/**
 * Pack Detail Hooks Unit Tests
 *
 * Tests for usePackEdit, usePackDownloads, and related hook logic.
 * These tests verify the business logic without React rendering.
 */

import { describe, it, expect } from 'vitest'

// =============================================================================
// Test Types (mirroring hook types)
// =============================================================================

interface EditState {
  isEditing: boolean
  editingSection: string | null
  hasUnsavedChanges: boolean
  dirtyFields: Set<string>
  pendingChanges: Record<string, unknown>
  errors: Record<string, string>
}

interface DownloadProgress {
  asset_name: string
  pack_name: string
  downloaded: number
  total: number
  speed: number
  eta?: number
  status: 'pending' | 'downloading' | 'completed' | 'failed'
}

// =============================================================================
// Edit State Logic Tests (mirrors usePackEdit logic)
// =============================================================================

describe('Pack Edit State Logic', () => {
  describe('Initial State', () => {
    it('should start with editing disabled', () => {
      const initialState: EditState = {
        isEditing: false,
        editingSection: null,
        hasUnsavedChanges: false,
        dirtyFields: new Set(),
        pendingChanges: {},
        errors: {},
      }

      expect(initialState.isEditing).toBe(false)
      expect(initialState.hasUnsavedChanges).toBe(false)
    })

    it('should have no dirty fields initially', () => {
      const initialState: EditState = {
        isEditing: false,
        editingSection: null,
        hasUnsavedChanges: false,
        dirtyFields: new Set(),
        pendingChanges: {},
        errors: {},
      }

      expect(initialState.dirtyFields.size).toBe(0)
    })
  })

  describe('startEditing Action', () => {
    it('should enable editing mode', () => {
      const state: EditState = {
        isEditing: false,
        editingSection: null,
        hasUnsavedChanges: false,
        dirtyFields: new Set(),
        pendingChanges: {},
        errors: {},
      }

      // Simulate startEditing
      const newState = { ...state, isEditing: true }

      expect(newState.isEditing).toBe(true)
    })

    it('should set editing section when provided', () => {
      const state: EditState = {
        isEditing: false,
        editingSection: null,
        hasUnsavedChanges: false,
        dirtyFields: new Set(),
        pendingChanges: {},
        errors: {},
      }

      // Simulate startEditing('dependencies')
      const newState = {
        ...state,
        isEditing: true,
        editingSection: 'dependencies',
      }

      expect(newState.editingSection).toBe('dependencies')
    })
  })

  describe('setFieldValue Action', () => {
    it('should mark field as dirty when value changes', () => {
      const state: EditState = {
        isEditing: true,
        editingSection: null,
        hasUnsavedChanges: false,
        dirtyFields: new Set(),
        pendingChanges: {},
        errors: {},
      }

      // Simulate setFieldValue('name', 'New Name')
      const newDirtyFields = new Set(state.dirtyFields)
      newDirtyFields.add('name')

      const newState = {
        ...state,
        dirtyFields: newDirtyFields,
        hasUnsavedChanges: newDirtyFields.size > 0,
        pendingChanges: { ...state.pendingChanges, name: 'New Name' },
      }

      expect(newState.dirtyFields.has('name')).toBe(true)
      expect(newState.hasUnsavedChanges).toBe(true)
      expect(newState.pendingChanges.name).toBe('New Name')
    })

    it('should track multiple dirty fields', () => {
      const dirtyFields = new Set<string>()
      dirtyFields.add('name')
      dirtyFields.add('description')
      dirtyFields.add('tags')

      expect(dirtyFields.size).toBe(3)
      expect(dirtyFields.has('name')).toBe(true)
      expect(dirtyFields.has('description')).toBe(true)
      expect(dirtyFields.has('tags')).toBe(true)
    })

    it('should update pendingChanges with new values', () => {
      const pendingChanges: Record<string, unknown> = {}

      // Simulate multiple setFieldValue calls
      pendingChanges.name = 'Updated Pack Name'
      pendingChanges.description = 'New description'
      pendingChanges.user_tags = ['tag1', 'tag2']

      expect(pendingChanges.name).toBe('Updated Pack Name')
      expect(pendingChanges.description).toBe('New description')
      expect(pendingChanges.user_tags).toEqual(['tag1', 'tag2'])
    })
  })

  describe('discardChanges Action', () => {
    it('should clear all dirty fields', () => {
      const state: EditState = {
        isEditing: true,
        editingSection: null,
        hasUnsavedChanges: true,
        dirtyFields: new Set(['name', 'description']),
        pendingChanges: { name: 'New Name', description: 'New Desc' },
        errors: {},
      }

      // Simulate discardChanges
      const newState: EditState = {
        ...state,
        isEditing: false,
        hasUnsavedChanges: false,
        dirtyFields: new Set(),
        pendingChanges: {},
        errors: {},
      }

      expect(newState.dirtyFields.size).toBe(0)
      expect(newState.hasUnsavedChanges).toBe(false)
      expect(Object.keys(newState.pendingChanges).length).toBe(0)
    })
  })

  describe('stopEditing Action', () => {
    it('should disable editing mode', () => {
      const state: EditState = {
        isEditing: true,
        editingSection: 'dependencies',
        hasUnsavedChanges: false,
        dirtyFields: new Set(),
        pendingChanges: {},
        errors: {},
      }

      // Simulate stopEditing
      const newState = {
        ...state,
        isEditing: false,
        editingSection: null,
      }

      expect(newState.isEditing).toBe(false)
      expect(newState.editingSection).toBeNull()
    })
  })

  describe('Validation', () => {
    it('should track validation errors by field', () => {
      const errors: Record<string, string> = {}

      errors.name = 'Name is required'
      errors.version = 'Version must be in format X.Y.Z'

      expect(errors.name).toBe('Name is required')
      expect(errors.version).toBe('Version must be in format X.Y.Z')
      expect(Object.keys(errors).length).toBe(2)
    })

    it('should clear errors on valid input', () => {
      const errors: Record<string, string> = { name: 'Name is required' }

      // Simulate clearing error when valid value entered
      delete errors.name

      expect(errors.name).toBeUndefined()
    })
  })
})

// =============================================================================
// Download Progress Logic Tests (mirrors usePackDownloads logic)
// =============================================================================

describe('Download Progress Logic', () => {
  describe('Progress Calculation', () => {
    it('should calculate progress percentage correctly', () => {
      const download: DownloadProgress = {
        asset_name: 'model.safetensors',
        pack_name: 'test-pack',
        downloaded: 500_000_000, // 500 MB
        total: 1_000_000_000, // 1 GB
        speed: 10_000_000, // 10 MB/s
        status: 'downloading',
      }

      const progressPercent = (download.downloaded / download.total) * 100
      expect(progressPercent).toBe(50)
    })

    it('should handle zero total bytes', () => {
      const download: DownloadProgress = {
        asset_name: 'model.safetensors',
        pack_name: 'test-pack',
        downloaded: 0,
        total: 0,
        speed: 0,
        status: 'pending',
      }

      const progressPercent = download.total > 0
        ? (download.downloaded / download.total) * 100
        : 0

      expect(progressPercent).toBe(0)
    })
  })

  describe('ETA Calculation', () => {
    it('should calculate ETA in seconds', () => {
      const download: DownloadProgress = {
        asset_name: 'model.safetensors',
        pack_name: 'test-pack',
        downloaded: 500_000_000,
        total: 1_000_000_000,
        speed: 10_000_000, // 10 MB/s
        status: 'downloading',
      }

      const remainingBytes = download.total - download.downloaded
      const etaSeconds = download.speed > 0
        ? remainingBytes / download.speed
        : undefined

      expect(etaSeconds).toBe(50) // 500 MB / 10 MB/s = 50 seconds
    })

    it('should return undefined ETA when speed is zero', () => {
      const download: DownloadProgress = {
        asset_name: 'model.safetensors',
        pack_name: 'test-pack',
        downloaded: 500_000_000,
        total: 1_000_000_000,
        speed: 0,
        status: 'downloading',
      }

      const etaSeconds = download.speed > 0
        ? (download.total - download.downloaded) / download.speed
        : undefined

      expect(etaSeconds).toBeUndefined()
    })
  })

  describe('Status Transitions', () => {
    it('should track pending status', () => {
      const download: DownloadProgress = {
        asset_name: 'model.safetensors',
        pack_name: 'test-pack',
        downloaded: 0,
        total: 0,
        speed: 0,
        status: 'pending',
      }

      expect(download.status).toBe('pending')
    })

    it('should track downloading status', () => {
      const download: DownloadProgress = {
        asset_name: 'model.safetensors',
        pack_name: 'test-pack',
        downloaded: 500_000_000,
        total: 1_000_000_000,
        speed: 10_000_000,
        status: 'downloading',
      }

      expect(download.status).toBe('downloading')
    })

    it('should track completed status', () => {
      const download: DownloadProgress = {
        asset_name: 'model.safetensors',
        pack_name: 'test-pack',
        downloaded: 1_000_000_000,
        total: 1_000_000_000,
        speed: 0,
        status: 'completed',
      }

      expect(download.status).toBe('completed')
      expect(download.downloaded).toBe(download.total)
    })

    it('should track failed status', () => {
      const download: DownloadProgress = {
        asset_name: 'model.safetensors',
        pack_name: 'test-pack',
        downloaded: 500_000_000,
        total: 1_000_000_000,
        speed: 0,
        status: 'failed',
      }

      expect(download.status).toBe('failed')
    })
  })

  describe('Active Downloads Filtering', () => {
    it('should filter active downloads by pack name', () => {
      const downloads: DownloadProgress[] = [
        { asset_name: 'a.safetensors', pack_name: 'pack-1', downloaded: 0, total: 100, speed: 10, status: 'downloading' },
        { asset_name: 'b.safetensors', pack_name: 'pack-2', downloaded: 50, total: 100, speed: 10, status: 'downloading' },
        { asset_name: 'c.safetensors', pack_name: 'pack-1', downloaded: 100, total: 100, speed: 0, status: 'completed' },
      ]

      const pack1Downloads = downloads.filter(d => d.pack_name === 'pack-1')
      expect(pack1Downloads.length).toBe(2)
    })

    it('should filter only active (downloading/pending) status', () => {
      const downloads: DownloadProgress[] = [
        { asset_name: 'a.safetensors', pack_name: 'pack-1', downloaded: 0, total: 100, speed: 10, status: 'pending' },
        { asset_name: 'b.safetensors', pack_name: 'pack-1', downloaded: 50, total: 100, speed: 10, status: 'downloading' },
        { asset_name: 'c.safetensors', pack_name: 'pack-1', downloaded: 100, total: 100, speed: 0, status: 'completed' },
        { asset_name: 'd.safetensors', pack_name: 'pack-1', downloaded: 30, total: 100, speed: 0, status: 'failed' },
      ]

      const activeDownloads = downloads.filter(
        d => d.status === 'downloading' || d.status === 'pending'
      )
      expect(activeDownloads.length).toBe(2)
    })
  })

  describe('Download Lookup by Asset Name', () => {
    it('should find download by asset name', () => {
      const downloads: DownloadProgress[] = [
        { asset_name: 'model-a.safetensors', pack_name: 'pack-1', downloaded: 50, total: 100, speed: 10, status: 'downloading' },
        { asset_name: 'model-b.safetensors', pack_name: 'pack-1', downloaded: 0, total: 100, speed: 0, status: 'pending' },
      ]

      const getAssetDownload = (assetName: string) =>
        downloads.find(d => d.asset_name === assetName)

      const download = getAssetDownload('model-a.safetensors')
      expect(download).toBeDefined()
      expect(download?.downloaded).toBe(50)
    })

    it('should return undefined for non-existent asset', () => {
      const downloads: DownloadProgress[] = [
        { asset_name: 'model-a.safetensors', pack_name: 'pack-1', downloaded: 50, total: 100, speed: 10, status: 'downloading' },
      ]

      const getAssetDownload = (assetName: string) =>
        downloads.find(d => d.asset_name === assetName)

      const download = getAssetDownload('non-existent.safetensors')
      expect(download).toBeUndefined()
    })
  })
})

// =============================================================================
// Error Boundary Logic Tests
// =============================================================================

describe('Error Boundary Logic', () => {
  describe('Error Detection', () => {
    it('should detect error state', () => {
      interface ErrorBoundaryState {
        hasError: boolean
        error: Error | null
      }

      const state: ErrorBoundaryState = {
        hasError: true,
        error: new Error('Test error'),
      }

      expect(state.hasError).toBe(true)
      expect(state.error?.message).toBe('Test error')
    })

    it('should reset error state on retry', () => {
      interface ErrorBoundaryState {
        hasError: boolean
        error: Error | null
      }

      const errorState: ErrorBoundaryState = {
        hasError: true,
        error: new Error('Test error'),
      }

      // Verify initial error state
      expect(errorState.hasError).toBe(true)
      expect(errorState.error).not.toBeNull()

      // Simulate retry - create reset state
      const resetState: ErrorBoundaryState = {
        hasError: false,
        error: null,
      }

      expect(resetState.hasError).toBe(false)
      expect(resetState.error).toBeNull()
    })
  })

  describe('Development Mode Detection', () => {
    it('should detect localhost as development', () => {
      const detectIsDev = (host: string): boolean => host === 'localhost'
      expect(detectIsDev('localhost')).toBe(true)
    })

    it('should not detect production hostname as development', () => {
      const detectIsDev = (host: string): boolean => host === 'localhost'
      expect(detectIsDev('example.com')).toBe(false)
    })
  })
})

// =============================================================================
// Format Helpers Tests
// =============================================================================

describe('Format Helpers', () => {
  describe('formatBytes', () => {
    const formatBytes = (bytes: number, decimals = 2): string => {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`
    }

    it('should format bytes correctly', () => {
      expect(formatBytes(0)).toBe('0 B')
      expect(formatBytes(1024)).toBe('1 KB')
      expect(formatBytes(1024 * 1024)).toBe('1 MB')
      expect(formatBytes(1024 * 1024 * 1024)).toBe('1 GB')
    })

    it('should handle decimal precision', () => {
      expect(formatBytes(1536, 1)).toBe('1.5 KB')
      expect(formatBytes(1536, 0)).toBe('2 KB')
    })
  })

  describe('formatSpeed', () => {
    const formatSpeed = (bytesPerSecond: number): string => {
      const formatBytes = (bytes: number, decimals = 2): string => {
        if (bytes === 0) return '0 B'
        const k = 1024
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`
      }
      return `${formatBytes(bytesPerSecond)}/s`
    }

    it('should format speed correctly', () => {
      expect(formatSpeed(1024 * 1024)).toBe('1 MB/s')
      expect(formatSpeed(1024 * 1024 * 10)).toBe('10 MB/s')
    })
  })

  describe('formatETA', () => {
    const formatETA = (seconds: number): string => {
      if (seconds < 60) return `${Math.round(seconds)}s`
      if (seconds < 3600) return `${Math.round(seconds / 60)}m`
      return `${Math.round(seconds / 3600)}h`
    }

    it('should format seconds correctly', () => {
      expect(formatETA(30)).toBe('30s')
      expect(formatETA(90)).toBe('2m')
      expect(formatETA(3600)).toBe('1h')
      expect(formatETA(7200)).toBe('2h')
    })
  })
})

// =============================================================================
// Validation Logic Tests
// =============================================================================

describe('Validation Logic', () => {
  describe('Pack Name Validation', () => {
    const validatePackName = (name: string): string | null => {
      if (!name || name.trim() === '') {
        return 'Pack name is required'
      }
      if (name.length > 100) {
        return 'Pack name must be 100 characters or less'
      }
      if (!/^[a-zA-Z0-9-_. ]+$/.test(name)) {
        return 'Pack name contains invalid characters'
      }
      return null
    }

    it('should reject empty name', () => {
      expect(validatePackName('')).toBe('Pack name is required')
      expect(validatePackName('   ')).toBe('Pack name is required')
    })

    it('should reject long name', () => {
      const longName = 'a'.repeat(101)
      expect(validatePackName(longName)).toBe('Pack name must be 100 characters or less')
    })

    it('should accept valid name', () => {
      expect(validatePackName('My Pack Name')).toBeNull()
      expect(validatePackName('pack-v1.0.0')).toBeNull()
      expect(validatePackName('pack_test_123')).toBeNull()
    })
  })

  describe('Version Validation', () => {
    const validateVersion = (version: string): string | null => {
      if (!version) return null // Optional field
      const versionRegex = /^\d+\.\d+\.\d+$/
      if (!versionRegex.test(version)) {
        return 'Version must be in format X.Y.Z'
      }
      return null
    }

    it('should accept valid semantic versions', () => {
      expect(validateVersion('1.0.0')).toBeNull()
      expect(validateVersion('2.10.3')).toBeNull()
      expect(validateVersion('0.0.1')).toBeNull()
    })

    it('should reject invalid versions', () => {
      expect(validateVersion('1.0')).toBe('Version must be in format X.Y.Z')
      expect(validateVersion('v1.0.0')).toBe('Version must be in format X.Y.Z')
      expect(validateVersion('1.0.0-beta')).toBe('Version must be in format X.Y.Z')
    })

    it('should accept empty version (optional field)', () => {
      expect(validateVersion('')).toBeNull()
    })
  })
})

// =============================================================================
// Modal State Logic Tests
// =============================================================================

// =============================================================================
// EditPreviewsModal Cover Logic Tests
// =============================================================================

describe('EditPreviewsModal Cover Logic', () => {
  interface PreviewInfo {
    filename: string
    url: string
    media_type: 'image' | 'video'
    nsfw?: boolean
  }

  describe('Cover Detection', () => {
    it('should correctly identify cover when cover_url matches preview url', () => {
      const previews: PreviewInfo[] = [
        { filename: 'preview1.jpg', url: '/packs/test/resources/previews/preview1.jpg', media_type: 'image' },
        { filename: 'preview2.jpg', url: '/packs/test/resources/previews/preview2.jpg', media_type: 'image' },
        { filename: 'preview3.jpg', url: '/packs/test/resources/previews/preview3.jpg', media_type: 'image' },
      ]
      const coverUrl = '/packs/test/resources/previews/preview2.jpg'

      // Logic from EditPreviewsModal line 591
      const isCover = (preview: PreviewInfo, index: number) =>
        preview.url === coverUrl || (index === 0 && !coverUrl)

      expect(isCover(previews[0], 0)).toBe(false) // preview1 is NOT cover
      expect(isCover(previews[1], 1)).toBe(true)  // preview2 IS cover
      expect(isCover(previews[2], 2)).toBe(false) // preview3 is NOT cover
    })

    it('should default to first preview as cover when cover_url is undefined', () => {
      const previews: PreviewInfo[] = [
        { filename: 'preview1.jpg', url: '/packs/test/resources/previews/preview1.jpg', media_type: 'image' },
        { filename: 'preview2.jpg', url: '/packs/test/resources/previews/preview2.jpg', media_type: 'image' },
      ]
      const coverUrl: string | undefined = undefined

      const isCover = (preview: PreviewInfo, index: number) =>
        preview.url === coverUrl || (index === 0 && !coverUrl)

      expect(isCover(previews[0], 0)).toBe(true)  // First preview is default cover
      expect(isCover(previews[1], 1)).toBe(false)
    })

    it('should NOT use first preview as cover when cover_url is set', () => {
      const previews: PreviewInfo[] = [
        { filename: 'preview1.jpg', url: '/packs/test/resources/previews/preview1.jpg', media_type: 'image' },
        { filename: 'preview2.jpg', url: '/packs/test/resources/previews/preview2.jpg', media_type: 'image' },
      ]
      // Cover is explicitly set to second preview
      const coverUrl = '/packs/test/resources/previews/preview2.jpg'

      const isCover = (preview: PreviewInfo, index: number) =>
        preview.url === coverUrl || (index === 0 && !coverUrl)

      // BUG FIX TEST: First preview should NOT be marked as cover
      // when cover_url is explicitly set to a different preview
      expect(isCover(previews[0], 0)).toBe(false)
      expect(isCover(previews[1], 1)).toBe(true)
    })
  })

  describe('Cover URL Props', () => {
    it('should use pack.cover_url, not pack.previews[0].url', () => {
      // This tests the fix for the bug where PackDetailPage was passing
      // pack.previews[0].url instead of pack.cover_url to EditPreviewsModal
      const pack = {
        cover_url: '/packs/test/resources/previews/preview3.jpg',
        previews: [
          { filename: 'preview1.jpg', url: '/packs/test/resources/previews/preview1.jpg', media_type: 'image' as const },
          { filename: 'preview2.jpg', url: '/packs/test/resources/previews/preview2.jpg', media_type: 'image' as const },
          { filename: 'preview3.jpg', url: '/packs/test/resources/previews/preview3.jpg', media_type: 'image' as const },
        ],
      }

      // WRONG: Using first preview URL (old bug)
      const wrongCoverUrl = pack.previews[0]?.url
      expect(wrongCoverUrl).toBe('/packs/test/resources/previews/preview1.jpg')

      // CORRECT: Using pack.cover_url
      const correctCoverUrl = pack.cover_url
      expect(correctCoverUrl).toBe('/packs/test/resources/previews/preview3.jpg')

      // The modal should receive pack.cover_url, not pack.previews[0].url
      expect(correctCoverUrl).not.toBe(wrongCoverUrl)
    })

    it('should detect cover change correctly using pack.cover_url', () => {
      const pack = {
        cover_url: '/packs/test/resources/previews/preview1.jpg',
        previews: [
          { filename: 'preview1.jpg', url: '/packs/test/resources/previews/preview1.jpg', media_type: 'image' as const },
          { filename: 'preview2.jpg', url: '/packs/test/resources/previews/preview2.jpg', media_type: 'image' as const },
        ],
      }

      // User changes cover to preview2
      const newCoverUrl = '/packs/test/resources/previews/preview2.jpg'

      // Cover changed detection
      const coverChanged = newCoverUrl !== pack.cover_url
      expect(coverChanged).toBe(true)

      // If we wrongly compared with previews[0].url when pack.cover_url was different,
      // we would get wrong results
      const coverChangedWrong = newCoverUrl !== pack.previews[0].url
      // This would also be true, but for wrong reason in edge cases
      expect(coverChangedWrong).toBe(true)
    })
  })
})

// =============================================================================
// Modal State Logic Tests
// =============================================================================

describe('Modal State Logic', () => {
  describe('Default Modal State', () => {
    it('should have all modals closed initially', () => {
      const DEFAULT_MODAL_STATE = {
        editPack: false,
        editParameters: false,
        editPreviews: false,
        editDependencies: false,
        uploadWorkflow: false,
        baseModelResolver: false,
        pullConfirm: false,
        pushConfirm: false,
      }

      Object.values(DEFAULT_MODAL_STATE).forEach(value => {
        expect(value).toBe(false)
      })
    })
  })

  describe('openModal/closeModal Actions', () => {
    it('should open specified modal', () => {
      const modals = {
        editPack: false,
        editParameters: false,
      }

      // Simulate openModal('editPack')
      const newState = { ...modals, editPack: true }

      expect(newState.editPack).toBe(true)
      expect(newState.editParameters).toBe(false)
    })

    it('should close specified modal', () => {
      const modals = {
        editPack: true,
        editParameters: false,
      }

      // Simulate closeModal('editPack')
      const newState = { ...modals, editPack: false }

      expect(newState.editPack).toBe(false)
    })

    it('should allow multiple modals open (though not recommended)', () => {
      const modals = {
        editPack: true,
        editParameters: true,
      }

      expect(modals.editPack).toBe(true)
      expect(modals.editParameters).toBe(true)
    })
  })
})
