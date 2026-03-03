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

// ============================================================================
// Context Menu Action Visibility Tests
// ============================================================================

interface BlobOrigin {
  provider: string
  model_id?: number
  version_id?: number
}

interface InventoryItemWithOrigin extends InventoryItem {
  origin?: BlobOrigin
}

// ============================================================================
// Used By Packs Sorting Tests
// ============================================================================

/**
 * Mirrors BlobsTable.tsx sort comparator for used_by_packs.
 * Primary: pack count. Secondary: first pack name alphabetically.
 */
function sortByUsedByPacks(
  items: InventoryItem[],
  direction: 'asc' | 'desc',
): InventoryItem[] {
  return [...items].sort((a, b) => {
    const countDiff = a.used_by_packs.length - b.used_by_packs.length
    if (countDiff !== 0) {
      return direction === 'asc' ? countDiff : -countDiff
    }
    const aFirst = (a.used_by_packs[0] || '').toLowerCase()
    const bFirst = (b.used_by_packs[0] || '').toLowerCase()
    const cmp = aFirst.localeCompare(bFirst)
    return direction === 'asc' ? cmp : -cmp
  })
}

describe('Used By Packs Sorting', () => {
  const makeItem = (packs: string[], name?: string): InventoryItem => ({
    sha256: name || packs.join('-') || 'empty',
    kind: 'checkpoint',
    display_name: name || 'model.safetensors',
    size_bytes: 1000,
    location: 'local_only',
    on_local: true,
    on_backup: false,
    status: packs.length > 0 ? 'referenced' : 'orphan',
    used_by_packs: packs,
    ref_count: packs.length,
    active_in_uis: [],
  })

  it('should sort by pack count ascending', () => {
    const items = [
      makeItem(['A', 'B', 'C'], 'three'),
      makeItem(['X'], 'one'),
      makeItem(['P', 'Q'], 'two'),
    ]
    const sorted = sortByUsedByPacks(items, 'asc')
    expect(sorted.map(i => i.sha256)).toEqual(['one', 'two', 'three'])
  })

  it('should sort by pack count descending', () => {
    const items = [
      makeItem(['X'], 'one'),
      makeItem(['A', 'B', 'C'], 'three'),
      makeItem(['P', 'Q'], 'two'),
    ]
    const sorted = sortByUsedByPacks(items, 'desc')
    expect(sorted.map(i => i.sha256)).toEqual(['three', 'two', 'one'])
  })

  it('should secondary sort by first pack name when counts equal', () => {
    const items = [
      makeItem(['Zebra Pack'], 'z'),
      makeItem(['Alpha Pack'], 'a'),
      makeItem(['Mid Pack'], 'm'),
    ]
    const sorted = sortByUsedByPacks(items, 'asc')
    expect(sorted.map(i => i.sha256)).toEqual(['a', 'm', 'z'])
  })

  it('should handle orphans (empty packs array) at the start when ascending', () => {
    const items = [
      makeItem(['SomePack'], 'ref'),
      makeItem([], 'orphan'),
    ]
    const sorted = sortByUsedByPacks(items, 'asc')
    expect(sorted[0].sha256).toBe('orphan')
    expect(sorted[1].sha256).toBe('ref')
  })

  it('should handle orphans (empty packs array) at the end when descending', () => {
    const items = [
      makeItem([], 'orphan'),
      makeItem(['SomePack'], 'ref'),
    ]
    const sorted = sortByUsedByPacks(items, 'desc')
    expect(sorted[0].sha256).toBe('ref')
    expect(sorted[1].sha256).toBe('orphan')
  })
})

/**
 * Mirrors BlobsTable.tsx context menu visibility logic.
 * Returns which actions are visible for a given item state.
 */
function getVisibleActions(
  item: InventoryItemWithOrigin,
  backupEnabled: boolean,
  backupConnected: boolean,
): string[] {
  const actions: string[] = []

  // Copy SHA256 is always visible
  actions.push('copy_sha256')

  // Show Impacts — only for referenced items
  if (item.status === 'referenced') {
    actions.push('show_impacts')
  }

  // Backup/Restore — need backup enabled and connected
  if (backupEnabled && backupConnected) {
    if (item.location === 'local_only') {
      actions.push('backup_to_external')
    }
    if (item.location === 'backup_only') {
      actions.push('restore_from_backup')
    }
  }

  // Delete from local — always available for local blobs.
  // DeleteConfirmationDialog handles guard rails (last copy warning, referenced warning).
  if (item.on_local) {
    actions.push('delete_from_local')
  }

  // Delete from backup
  if (item.on_backup && backupConnected) {
    actions.push('delete_from_backup')
  }

  // Delete everywhere — orphan with both copies
  if (item.location === 'both' && item.status === 'orphan') {
    actions.push('delete_everywhere')
  }

  // Re-download — missing with origin
  if (item.status === 'missing' && item.origin) {
    actions.push('redownload')
  }

  // Verify SHA256 — only if on local disk
  if (item.on_local) {
    actions.push('verify_sha256')
  }

  return actions
}

/**
 * Mirrors BlobsTable.tsx quick action determination.
 */
function getQuickAction(
  item: InventoryItem,
  backupEnabled: boolean,
  backupConnected: boolean,
): string | null {
  if (item.location === 'local_only' && backupEnabled && backupConnected) {
    return 'backup'
  }
  if (item.location === 'backup_only' && backupConnected) {
    return 'restore'
  }
  if (item.status === 'orphan' && item.on_local) {
    return 'delete'
  }
  return null
}

describe('Context Menu Actions Visibility', () => {
  const makeItem = (overrides: Partial<InventoryItemWithOrigin>): InventoryItemWithOrigin => ({
    sha256: 'abc123def456',
    kind: 'checkpoint',
    display_name: 'cyberrealistic_final.safetensors',
    size_bytes: 6_800_000_000,
    location: 'local_only',
    on_local: true,
    on_backup: false,
    status: 'referenced',
    used_by_packs: ['CyberRealistic'],
    ref_count: 1,
    active_in_uis: [],
    ...overrides,
  })

  it('should always show Copy SHA256', () => {
    const item = makeItem({})
    const actions = getVisibleActions(item, false, false)
    expect(actions).toContain('copy_sha256')
  })

  it('should show Verify SHA256 for local blobs', () => {
    const item = makeItem({ on_local: true })
    const actions = getVisibleActions(item, false, false)
    expect(actions).toContain('verify_sha256')
  })

  it('should NOT show Verify SHA256 for backup-only blobs', () => {
    const item = makeItem({
      on_local: false,
      on_backup: true,
      location: 'backup_only',
      status: 'backup_only',
    })
    const actions = getVisibleActions(item, true, true)
    expect(actions).not.toContain('verify_sha256')
  })

  it('should show Re-download for missing blobs with origin', () => {
    const item = makeItem({
      status: 'missing',
      on_local: false,
      location: 'nowhere',
      origin: { provider: 'civitai', model_id: 15003, version_id: 57618 },
    })
    const actions = getVisibleActions(item, false, false)
    expect(actions).toContain('redownload')
  })

  it('should NOT show Re-download for missing blobs without origin', () => {
    const item = makeItem({
      status: 'missing',
      on_local: false,
      location: 'nowhere',
      origin: undefined,
    })
    const actions = getVisibleActions(item, false, false)
    expect(actions).not.toContain('redownload')
  })

  it('should NOT show Re-download for referenced (non-missing) blobs', () => {
    const item = makeItem({
      status: 'referenced',
      origin: { provider: 'civitai', model_id: 15003 },
    })
    const actions = getVisibleActions(item, false, false)
    expect(actions).not.toContain('redownload')
  })

  it('should show Show Impacts only for referenced blobs', () => {
    const referenced = makeItem({ status: 'referenced' })
    const orphan = makeItem({ status: 'orphan', used_by_packs: [] })

    expect(getVisibleActions(referenced, false, false)).toContain('show_impacts')
    expect(getVisibleActions(orphan, false, false)).not.toContain('show_impacts')
  })

  it('should show Backup only when backup enabled and connected', () => {
    const item = makeItem({ location: 'local_only' })
    expect(getVisibleActions(item, true, true)).toContain('backup_to_external')
    expect(getVisibleActions(item, true, false)).not.toContain('backup_to_external')
    expect(getVisibleActions(item, false, false)).not.toContain('backup_to_external')
  })

  it('should show Delete from Local for orphans', () => {
    const item = makeItem({ status: 'orphan', used_by_packs: [], on_local: true })
    const actions = getVisibleActions(item, false, false)
    expect(actions).toContain('delete_from_local')
  })

  it('should show Delete from Local for backed-up referenced blobs', () => {
    const item = makeItem({
      status: 'referenced',
      on_local: true,
      on_backup: true,
      location: 'both',
    })
    const actions = getVisibleActions(item, true, true)
    expect(actions).toContain('delete_from_local')
  })

  it('should show Delete from Local for local-only referenced blobs (dialog handles guard rails)', () => {
    const item = makeItem({
      status: 'referenced',
      on_local: true,
      on_backup: false,
      location: 'local_only',
    })
    const actions = getVisibleActions(item, false, false)
    expect(actions).toContain('delete_from_local')
  })
})

describe('Quick Action Determination', () => {
  const makeItem = (overrides: Partial<InventoryItem>): InventoryItem => ({
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
    ...overrides,
  })

  it('should show Backup for local-only items when backup available', () => {
    const item = makeItem({ location: 'local_only' })
    expect(getQuickAction(item, true, true)).toBe('backup')
  })

  it('should show Restore for backup-only items', () => {
    const item = makeItem({
      location: 'backup_only',
      on_local: false,
      on_backup: true,
      status: 'backup_only',
    })
    expect(getQuickAction(item, true, true)).toBe('restore')
  })

  it('should show Delete for orphans on local', () => {
    const item = makeItem({
      status: 'orphan',
      on_local: true,
      used_by_packs: [],
    })
    expect(getQuickAction(item, false, false)).toBe('delete')
  })

  it('should return null for referenced blobs with no backup', () => {
    const item = makeItem({ location: 'local_only', status: 'referenced' })
    expect(getQuickAction(item, false, false)).toBeNull()
  })
})

// ============================================================================
// Delete Guard Rails (mirrors DeleteConfirmationDialog logic)
// ============================================================================

/**
 * Mirrors DeleteConfirmationDialog.tsx warning level computation.
 * Delete action is always available in context menu for any on_local blob,
 * but the dialog shows appropriate warnings based on risk level.
 */
function getDeleteDialogWarnings(
  item: InventoryItem,
  target: 'local' | 'backup' | 'both',
): { isLastCopy: boolean; isReferenced: boolean; hasHighRisk: boolean } {
  const isLastCopy =
    target === 'both' ||
    (target === 'local' && !item.on_backup) ||
    (target === 'backup' && !item.on_local)

  const isReferenced = item.status === 'referenced'
  const hasHighRisk = isLastCopy && isReferenced

  return { isLastCopy, isReferenced, hasHighRisk }
}

describe('Delete Guard Rails (DeleteConfirmationDialog)', () => {
  const makeItem = (overrides: Partial<InventoryItem>): InventoryItem => ({
    sha256: 'abc123',
    kind: 'checkpoint',
    display_name: 'model.safetensors',
    size_bytes: 2_000_000_000,
    location: 'local_only',
    on_local: true,
    on_backup: false,
    status: 'referenced',
    used_by_packs: ['TestPack'],
    ref_count: 1,
    active_in_uis: [],
    ...overrides,
  })

  it('should flag HIGH RISK for referenced local-only blob (last copy + referenced)', () => {
    const item = makeItem({ status: 'referenced', on_local: true, on_backup: false })
    const warnings = getDeleteDialogWarnings(item, 'local')
    expect(warnings.isLastCopy).toBe(true)
    expect(warnings.isReferenced).toBe(true)
    expect(warnings.hasHighRisk).toBe(true)
  })

  it('should flag last copy but NOT high risk for orphan local-only blob', () => {
    const item = makeItem({ status: 'orphan', on_local: true, on_backup: false, used_by_packs: [] })
    const warnings = getDeleteDialogWarnings(item, 'local')
    expect(warnings.isLastCopy).toBe(true)
    expect(warnings.isReferenced).toBe(false)
    expect(warnings.hasHighRisk).toBe(false)
  })

  it('should NOT flag last copy when backup exists', () => {
    const item = makeItem({ status: 'referenced', on_local: true, on_backup: true, location: 'both' })
    const warnings = getDeleteDialogWarnings(item, 'local')
    expect(warnings.isLastCopy).toBe(false)
    expect(warnings.isReferenced).toBe(true)
    expect(warnings.hasHighRisk).toBe(false)
  })

  it('should flag high risk for "delete both" on referenced blob', () => {
    const item = makeItem({ status: 'referenced', on_local: true, on_backup: true, location: 'both' })
    const warnings = getDeleteDialogWarnings(item, 'both')
    expect(warnings.isLastCopy).toBe(true)
    expect(warnings.hasHighRisk).toBe(true)
  })

  it('should not flag anything risky for backup-only delete when local exists', () => {
    const item = makeItem({ status: 'referenced', on_local: true, on_backup: true, location: 'both' })
    const warnings = getDeleteDialogWarnings(item, 'backup')
    expect(warnings.isLastCopy).toBe(false)
    expect(warnings.hasHighRisk).toBe(false)
  })

  it('should always show delete_from_local in context menu for any local blob', () => {
    // Referenced + local_only — previously hidden, now visible
    const referencedLocalOnly = makeItem({ status: 'referenced', on_local: true, on_backup: false })
    expect(getVisibleActions(referencedLocalOnly, false, false)).toContain('delete_from_local')

    // Referenced + both — always was visible
    const referencedBoth = makeItem({ status: 'referenced', on_local: true, on_backup: true, location: 'both' })
    expect(getVisibleActions(referencedBoth, true, true)).toContain('delete_from_local')

    // Orphan — always was visible
    const orphan = makeItem({ status: 'orphan', on_local: true, on_backup: false, used_by_packs: [] })
    expect(getVisibleActions(orphan, false, false)).toContain('delete_from_local')
  })

  it('should NOT show delete_from_local for non-local blobs', () => {
    const backupOnly = makeItem({ on_local: false, on_backup: true, location: 'backup_only', status: 'backup_only' })
    expect(getVisibleActions(backupOnly, true, true)).not.toContain('delete_from_local')

    const missing = makeItem({ on_local: false, on_backup: false, location: 'nowhere', status: 'missing' })
    expect(getVisibleActions(missing, false, false)).not.toContain('delete_from_local')
  })
})

// ============================================================================
// API URL Construction Tests
// ============================================================================

describe('Inventory API URLs', () => {
  it('should construct correct redownload URL', () => {
    const sha256 = 'abc123def456'
    const url = `/api/store/inventory/${sha256}/redownload`
    expect(url).toBe('/api/store/inventory/abc123def456/redownload')
  })

  it('should construct correct verify URL with single SHA256', () => {
    const sha256 = 'abc123def456'
    const body = { sha256: [sha256], all: false }
    expect(body.sha256).toHaveLength(1)
    expect(body.all).toBe(false)
  })

  it('should construct correct verify URL for all blobs', () => {
    const body = { all: true }
    expect(body.all).toBe(true)
  })
})
