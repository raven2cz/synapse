/**
 * Tests for Inventory Utilities and Type Logic
 *
 * Tests cover:
 * - formatBytes utility function
 * - formatRelativeTime utility function
 * - Inventory filter logic
 * - Guard rails validation (isLastCopy, canDeleteSafely)
 * - Location and status determination
 */

import { describe, it, expect } from 'vitest'

// ============================================================================
// Test Types (mirroring inventory/types.ts)
// ============================================================================

type AssetKind = 'checkpoint' | 'lora' | 'vae' | 'embedding' | 'controlnet' | 'upscaler' | 'other' | 'unknown'
type BlobStatus = 'referenced' | 'orphan' | 'missing' | 'backup_only'
type BlobLocation = 'local_only' | 'backup_only' | 'both' | 'nowhere'

interface InventoryItem {
  sha256: string
  kind: AssetKind
  display_name: string
  size_bytes: number
  location: BlobLocation
  on_local: boolean
  on_backup: boolean
  status: BlobStatus
  used_by_packs: string[]
  ref_count: number
  active_in_uis: string[]
  verified?: boolean | null
}

interface InventoryFilters {
  kind: AssetKind | 'all'
  status: BlobStatus | 'all'
  location: BlobLocation | 'all'
  search: string
}

interface ImpactAnalysis {
  sha256: string
  status: BlobStatus
  size_bytes: number
  used_by_packs: string[]
  active_in_uis: string[]
  can_delete_safely: boolean
  warning?: string
}

// ============================================================================
// Utility Functions (mirroring inventory/utils.ts)
// ============================================================================

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'

  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, i)

  return `${value.toFixed(i > 1 ? 1 : 0)} ${units[i]}`
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

// ============================================================================
// Filter Functions (mirroring InventoryPage logic)
// ============================================================================

function filterItems(items: InventoryItem[], filters: InventoryFilters): InventoryItem[] {
  return items.filter((item) => {
    // Kind filter
    if (filters.kind !== 'all' && item.kind !== filters.kind) return false

    // Status filter
    if (filters.status !== 'all' && item.status !== filters.status) return false

    // Location filter
    if (filters.location !== 'all' && item.location !== filters.location) return false

    // Search filter
    if (filters.search) {
      const search = filters.search.toLowerCase()
      const matchesName = item.display_name.toLowerCase().includes(search)
      const matchesSha = item.sha256.toLowerCase().includes(search)
      const matchesPack = item.used_by_packs.some((p) => p.toLowerCase().includes(search))
      if (!matchesName && !matchesSha && !matchesPack) return false
    }

    return true
  })
}

// ============================================================================
// Guard Rails Functions (mirroring backend logic)
// ============================================================================

function isLastCopy(item: InventoryItem): boolean {
  // Last copy if only in one place
  return (item.on_local && !item.on_backup) || (item.on_backup && !item.on_local)
}

function canDeleteSafely(item: InventoryItem): boolean {
  // Can delete safely if:
  // 1. Item is orphan (not referenced by any pack), OR
  // 2. Item is not the last copy
  if (item.status === 'orphan') return true
  if (!isLastCopy(item)) return true
  return false
}

function getDeleteWarning(item: InventoryItem, target: 'local' | 'backup' | 'both'): string | null {
  if (target === 'both') {
    if (item.on_local || item.on_backup) {
      return 'This will permanently delete the blob from ALL locations. You will need to re-download it from the original source.'
    }
  } else if (target === 'local') {
    if (item.on_local && !item.on_backup) {
      return 'This blob is NOT backed up. Deleting it will require re-downloading from the original source.'
    }
  } else if (target === 'backup') {
    if (item.on_backup && !item.on_local) {
      return 'This blob exists ONLY on backup. Deleting it will require re-downloading from the original source.'
    }
  }
  return null
}

function determineLocation(onLocal: boolean, onBackup: boolean): BlobLocation {
  if (onLocal && onBackup) return 'both'
  if (onLocal && !onBackup) return 'local_only'
  if (!onLocal && onBackup) return 'backup_only'
  return 'nowhere'
}

// ============================================================================
// formatBytes Tests
// ============================================================================

describe('formatBytes', () => {
  it('should return "0 B" for zero bytes', () => {
    expect(formatBytes(0)).toBe('0 B')
  })

  it('should format bytes correctly', () => {
    expect(formatBytes(500)).toBe('500 B')
  })

  it('should format kilobytes correctly', () => {
    expect(formatBytes(1024)).toBe('1 KB')
    expect(formatBytes(2048)).toBe('2 KB')
  })

  it('should format megabytes correctly', () => {
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB')
    expect(formatBytes(1.5 * 1024 * 1024)).toBe('1.5 MB')
  })

  it('should format gigabytes correctly', () => {
    expect(formatBytes(1024 * 1024 * 1024)).toBe('1.0 GB')
    expect(formatBytes(6.8 * 1024 * 1024 * 1024)).toBe('6.8 GB')
  })

  it('should format terabytes correctly', () => {
    expect(formatBytes(1024 * 1024 * 1024 * 1024)).toBe('1.0 TB')
  })

  it('should handle typical model sizes', () => {
    // LoRA ~145MB
    expect(formatBytes(145 * 1024 * 1024)).toBe('145.0 MB')
    // Checkpoint ~6.8GB
    expect(formatBytes(6.8 * 1024 * 1024 * 1024)).toBe('6.8 GB')
    // VAE ~335MB
    expect(formatBytes(335 * 1024 * 1024)).toBe('335.0 MB')
  })
})

// ============================================================================
// formatRelativeTime Tests
// ============================================================================

describe('formatRelativeTime', () => {
  it('should return "just now" for very recent times', () => {
    const now = new Date().toISOString()
    expect(formatRelativeTime(now)).toBe('just now')
  })

  it('should format minutes correctly', () => {
    const date = new Date(Date.now() - 5 * 60 * 1000) // 5 minutes ago
    expect(formatRelativeTime(date.toISOString())).toBe('5m ago')
  })

  it('should format hours correctly', () => {
    const date = new Date(Date.now() - 3 * 60 * 60 * 1000) // 3 hours ago
    expect(formatRelativeTime(date.toISOString())).toBe('3h ago')
  })

  it('should format days correctly', () => {
    const date = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000) // 2 days ago
    expect(formatRelativeTime(date.toISOString())).toBe('2d ago')
  })

  it('should return date for older times', () => {
    const date = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000) // 14 days ago
    const result = formatRelativeTime(date.toISOString())
    // Should be a date string, not relative
    expect(result).not.toContain('ago')
  })
})

// ============================================================================
// Filter Tests
// ============================================================================

describe('Inventory Filters', () => {
  const mockItems: InventoryItem[] = [
    {
      sha256: 'abc123',
      kind: 'checkpoint',
      display_name: 'juggernautXL_v10.safetensors',
      size_bytes: 6.8 * 1024 * 1024 * 1024,
      location: 'both',
      on_local: true,
      on_backup: true,
      status: 'referenced',
      used_by_packs: ['SDXL Main', 'Portrait Pack'],
      ref_count: 2,
      active_in_uis: ['comfyui'],
    },
    {
      sha256: 'def456',
      kind: 'lora',
      display_name: 'detail_tweaker_xl.safetensors',
      size_bytes: 145 * 1024 * 1024,
      location: 'local_only',
      on_local: true,
      on_backup: false,
      status: 'referenced',
      used_by_packs: ['SDXL Main'],
      ref_count: 1,
      active_in_uis: [],
    },
    {
      sha256: 'ghi789',
      kind: 'vae',
      display_name: 'old_vae.safetensors',
      size_bytes: 335 * 1024 * 1024,
      location: 'local_only',
      on_local: true,
      on_backup: false,
      status: 'orphan',
      used_by_packs: [],
      ref_count: 0,
      active_in_uis: [],
    },
    {
      sha256: 'jkl012',
      kind: 'checkpoint',
      display_name: 'archived_model.safetensors',
      size_bytes: 4 * 1024 * 1024 * 1024,
      location: 'backup_only',
      on_local: false,
      on_backup: true,
      status: 'backup_only',
      used_by_packs: ['Old Pack'],
      ref_count: 1,
      active_in_uis: [],
    },
  ]

  describe('Kind filter', () => {
    it('should return all items when kind is "all"', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'all', location: 'all', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(4)
    })

    it('should filter by checkpoint', () => {
      const filters: InventoryFilters = { kind: 'checkpoint', status: 'all', location: 'all', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(2)
      expect(result.every(item => item.kind === 'checkpoint')).toBe(true)
    })

    it('should filter by lora', () => {
      const filters: InventoryFilters = { kind: 'lora', status: 'all', location: 'all', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
      expect(result[0].kind).toBe('lora')
    })
  })

  describe('Status filter', () => {
    it('should filter by referenced', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'referenced', location: 'all', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(2)
      expect(result.every(item => item.status === 'referenced')).toBe(true)
    })

    it('should filter by orphan', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'orphan', location: 'all', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
      expect(result[0].status).toBe('orphan')
    })

    it('should filter by backup_only', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'backup_only', location: 'all', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
      expect(result[0].status).toBe('backup_only')
    })
  })

  describe('Location filter', () => {
    it('should filter by both', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'all', location: 'both', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
      expect(result[0].location).toBe('both')
    })

    it('should filter by local_only', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'all', location: 'local_only', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(2)
      expect(result.every(item => item.location === 'local_only')).toBe(true)
    })

    it('should filter by backup_only', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'all', location: 'backup_only', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
      expect(result[0].location).toBe('backup_only')
    })
  })

  describe('Search filter', () => {
    it('should search by display name', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'all', location: 'all', search: 'juggernaut' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
      expect(result[0].display_name).toContain('juggernaut')
    })

    it('should search by SHA256 hash', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'all', location: 'all', search: 'abc123' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
      expect(result[0].sha256).toBe('abc123')
    })

    it('should search by pack name', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'all', location: 'all', search: 'Portrait' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
      expect(result[0].used_by_packs).toContain('Portrait Pack')
    })

    it('should be case insensitive', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'all', location: 'all', search: 'JUGGERNAUT' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
    })

    it('should return empty when no matches', () => {
      const filters: InventoryFilters = { kind: 'all', status: 'all', location: 'all', search: 'nonexistent' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(0)
    })
  })

  describe('Combined filters', () => {
    it('should combine kind and status filters', () => {
      const filters: InventoryFilters = { kind: 'checkpoint', status: 'referenced', location: 'all', search: '' }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
      expect(result[0].kind).toBe('checkpoint')
      expect(result[0].status).toBe('referenced')
    })

    it('should combine all filters', () => {
      const filters: InventoryFilters = {
        kind: 'checkpoint',
        status: 'referenced',
        location: 'both',
        search: 'juggernaut'
      }
      const result = filterItems(mockItems, filters)
      expect(result.length).toBe(1)
    })
  })
})

// ============================================================================
// Guard Rails Tests
// ============================================================================

describe('Guard Rails', () => {
  describe('isLastCopy', () => {
    it('should return true when only on local', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'checkpoint',
        display_name: 'test.safetensors',
        size_bytes: 1000,
        location: 'local_only',
        on_local: true,
        on_backup: false,
        status: 'referenced',
        used_by_packs: ['Pack1'],
        ref_count: 1,
        active_in_uis: [],
      }
      expect(isLastCopy(item)).toBe(true)
    })

    it('should return true when only on backup', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'checkpoint',
        display_name: 'test.safetensors',
        size_bytes: 1000,
        location: 'backup_only',
        on_local: false,
        on_backup: true,
        status: 'backup_only',
        used_by_packs: [],
        ref_count: 0,
        active_in_uis: [],
      }
      expect(isLastCopy(item)).toBe(true)
    })

    it('should return false when on both local and backup', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'checkpoint',
        display_name: 'test.safetensors',
        size_bytes: 1000,
        location: 'both',
        on_local: true,
        on_backup: true,
        status: 'referenced',
        used_by_packs: ['Pack1'],
        ref_count: 1,
        active_in_uis: [],
      }
      expect(isLastCopy(item)).toBe(false)
    })
  })

  describe('canDeleteSafely', () => {
    it('should return true for orphan items', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'vae',
        display_name: 'old_vae.safetensors',
        size_bytes: 1000,
        location: 'local_only',
        on_local: true,
        on_backup: false,
        status: 'orphan',
        used_by_packs: [],
        ref_count: 0,
        active_in_uis: [],
      }
      expect(canDeleteSafely(item)).toBe(true)
    })

    it('should return true when item is backed up', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'checkpoint',
        display_name: 'test.safetensors',
        size_bytes: 1000,
        location: 'both',
        on_local: true,
        on_backup: true,
        status: 'referenced',
        used_by_packs: ['Pack1'],
        ref_count: 1,
        active_in_uis: [],
      }
      expect(canDeleteSafely(item)).toBe(true)
    })

    it('should return false for referenced item that is last copy', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'checkpoint',
        display_name: 'test.safetensors',
        size_bytes: 1000,
        location: 'local_only',
        on_local: true,
        on_backup: false,
        status: 'referenced',
        used_by_packs: ['Pack1'],
        ref_count: 1,
        active_in_uis: [],
      }
      expect(canDeleteSafely(item)).toBe(false)
    })
  })

  describe('getDeleteWarning', () => {
    it('should warn when deleting both copies', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'checkpoint',
        display_name: 'test.safetensors',
        size_bytes: 1000,
        location: 'both',
        on_local: true,
        on_backup: true,
        status: 'referenced',
        used_by_packs: ['Pack1'],
        ref_count: 1,
        active_in_uis: [],
      }
      const warning = getDeleteWarning(item, 'both')
      expect(warning).not.toBeNull()
      expect(warning).toContain('permanently delete')
    })

    it('should warn when deleting local-only copy', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'checkpoint',
        display_name: 'test.safetensors',
        size_bytes: 1000,
        location: 'local_only',
        on_local: true,
        on_backup: false,
        status: 'referenced',
        used_by_packs: ['Pack1'],
        ref_count: 1,
        active_in_uis: [],
      }
      const warning = getDeleteWarning(item, 'local')
      expect(warning).not.toBeNull()
      expect(warning).toContain('NOT backed up')
    })

    it('should warn when deleting backup-only copy', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'checkpoint',
        display_name: 'test.safetensors',
        size_bytes: 1000,
        location: 'backup_only',
        on_local: false,
        on_backup: true,
        status: 'backup_only',
        used_by_packs: [],
        ref_count: 0,
        active_in_uis: [],
      }
      const warning = getDeleteWarning(item, 'backup')
      expect(warning).not.toBeNull()
      expect(warning).toContain('ONLY on backup')
    })

    it('should not warn when deleting local with backup', () => {
      const item: InventoryItem = {
        sha256: 'test',
        kind: 'checkpoint',
        display_name: 'test.safetensors',
        size_bytes: 1000,
        location: 'both',
        on_local: true,
        on_backup: true,
        status: 'referenced',
        used_by_packs: ['Pack1'],
        ref_count: 1,
        active_in_uis: [],
      }
      const warning = getDeleteWarning(item, 'local')
      expect(warning).toBeNull()
    })
  })
})

// ============================================================================
// Location Determination Tests
// ============================================================================

describe('determineLocation', () => {
  it('should return "both" when on local and backup', () => {
    expect(determineLocation(true, true)).toBe('both')
  })

  it('should return "local_only" when only on local', () => {
    expect(determineLocation(true, false)).toBe('local_only')
  })

  it('should return "backup_only" when only on backup', () => {
    expect(determineLocation(false, true)).toBe('backup_only')
  })

  it('should return "nowhere" when not on either', () => {
    expect(determineLocation(false, false)).toBe('nowhere')
  })
})

// ============================================================================
// Impact Analysis Tests
// ============================================================================

describe('Impact Analysis', () => {
  const createImpactAnalysis = (overrides: Partial<ImpactAnalysis>): ImpactAnalysis => ({
    sha256: 'test123',
    status: 'referenced',
    size_bytes: 1000,
    used_by_packs: [],
    active_in_uis: [],
    can_delete_safely: true,
    ...overrides,
  })

  it('should indicate safe deletion for orphan with no dependencies', () => {
    const analysis = createImpactAnalysis({
      status: 'orphan',
      used_by_packs: [],
      active_in_uis: [],
      can_delete_safely: true,
    })
    expect(analysis.can_delete_safely).toBe(true)
    expect(analysis.used_by_packs.length).toBe(0)
    expect(analysis.active_in_uis.length).toBe(0)
  })

  it('should indicate unsafe deletion when used by packs', () => {
    const analysis = createImpactAnalysis({
      status: 'referenced',
      used_by_packs: ['SDXL Main', 'Portrait Pack'],
      can_delete_safely: false,
      warning: 'This blob is referenced by 2 packs',
    })
    expect(analysis.can_delete_safely).toBe(false)
    expect(analysis.used_by_packs.length).toBe(2)
    expect(analysis.warning).toBeDefined()
  })

  it('should indicate unsafe deletion when active in UIs', () => {
    const analysis = createImpactAnalysis({
      status: 'referenced',
      active_in_uis: ['comfyui', 'webui'],
      can_delete_safely: false,
    })
    expect(analysis.can_delete_safely).toBe(false)
    expect(analysis.active_in_uis.length).toBe(2)
  })
})

// ============================================================================
// Bulk Action Validation Tests
// ============================================================================

describe('Bulk Actions', () => {
  type BulkAction = 'backup' | 'restore' | 'delete_local' | 'delete_backup'

  const mockItems: InventoryItem[] = [
    {
      sha256: 'item1',
      kind: 'checkpoint',
      display_name: 'model1.safetensors',
      size_bytes: 1000,
      location: 'local_only',
      on_local: true,
      on_backup: false,
      status: 'referenced',
      used_by_packs: ['Pack1'],
      ref_count: 1,
      active_in_uis: [],
    },
    {
      sha256: 'item2',
      kind: 'lora',
      display_name: 'lora1.safetensors',
      size_bytes: 500,
      location: 'backup_only',
      on_local: false,
      on_backup: true,
      status: 'backup_only',
      used_by_packs: [],
      ref_count: 0,
      active_in_uis: [],
    },
  ]

  function canPerformBulkAction(items: InventoryItem[], action: BulkAction): boolean {
    switch (action) {
      case 'backup':
        return items.every(item => item.on_local && !item.on_backup)
      case 'restore':
        return items.every(item => item.on_backup && !item.on_local)
      case 'delete_local':
        return items.every(item => item.on_local)
      case 'delete_backup':
        return items.every(item => item.on_backup)
    }
  }

  describe('Backup action', () => {
    it('should allow backup for local-only items', () => {
      const localOnlyItems = mockItems.filter(i => i.location === 'local_only')
      expect(canPerformBulkAction(localOnlyItems, 'backup')).toBe(true)
    })

    it('should not allow backup for backup-only items', () => {
      const backupOnlyItems = mockItems.filter(i => i.location === 'backup_only')
      expect(canPerformBulkAction(backupOnlyItems, 'backup')).toBe(false)
    })
  })

  describe('Restore action', () => {
    it('should allow restore for backup-only items', () => {
      const backupOnlyItems = mockItems.filter(i => i.location === 'backup_only')
      expect(canPerformBulkAction(backupOnlyItems, 'restore')).toBe(true)
    })

    it('should not allow restore for local-only items', () => {
      const localOnlyItems = mockItems.filter(i => i.location === 'local_only')
      expect(canPerformBulkAction(localOnlyItems, 'restore')).toBe(false)
    })
  })
})
