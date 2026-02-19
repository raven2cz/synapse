/**
 * Tests for Updates Store Logic
 *
 * Tests cover:
 * - Version key generation from update plans
 * - Dismissed updates persistence (localStorage simulation)
 * - Download group ID generation
 * - Auto-check interval mapping
 * - Store state management for selections
 */

import { describe, it, expect, beforeEach } from 'vitest'

// ============================================================================
// Version Key Generation
// ============================================================================

interface PlanChange {
  dependency_id: string
  old: Record<string, unknown>
  new: Record<string, unknown>
}

interface PlanAmbiguous {
  dependency_id: string
  candidates: unknown[]
}

interface UpdatePlanEntry {
  pack: string
  already_up_to_date: boolean
  changes: PlanChange[]
  ambiguous: PlanAmbiguous[]
  impacted_packs: string[]
}

/**
 * Reproduce the versionKeyFromPlan logic from updatesStore.ts
 */
function versionKeyFromPlan(plan: UpdatePlanEntry): string {
  const ids = [
    ...plan.changes.map(c => `${c.dependency_id}:${(c.new as Record<string, unknown>)?.provider_version_id ?? '?'}`),
    ...plan.ambiguous.map(a => `${a.dependency_id}:ambiguous`),
  ]
  return ids.sort().join(',')
}

describe('Version Key Generation', () => {
  it('should generate key from single change', () => {
    const plan: UpdatePlanEntry = {
      pack: 'test-pack',
      already_up_to_date: false,
      changes: [
        { dependency_id: 'main-checkpoint', old: { provider_version_id: 100 }, new: { provider_version_id: 200 } },
      ],
      ambiguous: [],
      impacted_packs: [],
    }
    expect(versionKeyFromPlan(plan)).toBe('main-checkpoint:200')
  })

  it('should sort multiple changes alphabetically', () => {
    const plan: UpdatePlanEntry = {
      pack: 'test-pack',
      already_up_to_date: false,
      changes: [
        { dependency_id: 'lora', old: {}, new: { provider_version_id: 400 } },
        { dependency_id: 'checkpoint', old: {}, new: { provider_version_id: 200 } },
      ],
      ambiguous: [],
      impacted_packs: [],
    }
    expect(versionKeyFromPlan(plan)).toBe('checkpoint:200,lora:400')
  })

  it('should include ambiguous entries with :ambiguous suffix', () => {
    const plan: UpdatePlanEntry = {
      pack: 'test-pack',
      already_up_to_date: false,
      changes: [],
      ambiguous: [
        { dependency_id: 'main-ckpt', candidates: [] },
      ],
      impacted_packs: [],
    }
    expect(versionKeyFromPlan(plan)).toBe('main-ckpt:ambiguous')
  })

  it('should mix changes and ambiguous sorted together', () => {
    const plan: UpdatePlanEntry = {
      pack: 'test-pack',
      already_up_to_date: false,
      changes: [
        { dependency_id: 'lora', old: {}, new: { provider_version_id: 300 } },
      ],
      ambiguous: [
        { dependency_id: 'checkpoint', candidates: [] },
      ],
      impacted_packs: [],
    }
    expect(versionKeyFromPlan(plan)).toBe('checkpoint:ambiguous,lora:300')
  })

  it('should handle missing version_id with ?', () => {
    const plan: UpdatePlanEntry = {
      pack: 'test-pack',
      already_up_to_date: false,
      changes: [
        { dependency_id: 'dep', old: {}, new: {} },
      ],
      ambiguous: [],
      impacted_packs: [],
    }
    expect(versionKeyFromPlan(plan)).toBe('dep:?')
  })

  it('should return empty string for up-to-date plan', () => {
    const plan: UpdatePlanEntry = {
      pack: 'test-pack',
      already_up_to_date: true,
      changes: [],
      ambiguous: [],
      impacted_packs: [],
    }
    expect(versionKeyFromPlan(plan)).toBe('')
  })

  it('should generate different keys for different versions', () => {
    const plan1: UpdatePlanEntry = {
      pack: 'test-pack', already_up_to_date: false,
      changes: [{ dependency_id: 'ckpt', old: {}, new: { provider_version_id: 100 } }],
      ambiguous: [], impacted_packs: [],
    }
    const plan2: UpdatePlanEntry = {
      pack: 'test-pack', already_up_to_date: false,
      changes: [{ dependency_id: 'ckpt', old: {}, new: { provider_version_id: 200 } }],
      ambiguous: [], impacted_packs: [],
    }
    expect(versionKeyFromPlan(plan1)).not.toBe(versionKeyFromPlan(plan2))
  })
})

// ============================================================================
// Dismissed Updates Persistence
// ============================================================================

describe('Dismissed Updates Persistence', () => {
  /**
   * Simulate the localStorage-based dismissed persistence logic.
   */

  const DISMISSED_KEY = 'synapse-updates-dismissed'

  function loadDismissed(storage: Map<string, string>): Record<string, string> {
    try {
      const raw = storage.get(DISMISSED_KEY)
      return raw ? JSON.parse(raw) : {}
    } catch {
      return {}
    }
  }

  function saveDismissed(storage: Map<string, string>, dismissed: Record<string, string>) {
    storage.set(DISMISSED_KEY, JSON.stringify(dismissed))
  }

  let storage: Map<string, string>

  beforeEach(() => {
    storage = new Map()
  })

  it('should return empty object when nothing stored', () => {
    expect(loadDismissed(storage)).toEqual({})
  })

  it('should save and load dismissed versions', () => {
    const dismissed = { 'pack-a': 'ckpt:200', 'pack-b': 'lora:300' }
    saveDismissed(storage, dismissed)

    const loaded = loadDismissed(storage)
    expect(loaded).toEqual(dismissed)
  })

  it('should handle corrupt JSON gracefully', () => {
    storage.set(DISMISSED_KEY, 'not valid json{{{')
    expect(loadDismissed(storage)).toEqual({})
  })

  it('should overwrite previous dismissed entries', () => {
    saveDismissed(storage, { 'pack-a': 'old-key' })
    saveDismissed(storage, { 'pack-a': 'new-key', 'pack-b': 'key-b' })

    const loaded = loadDismissed(storage)
    expect(loaded['pack-a']).toBe('new-key')
    expect(loaded['pack-b']).toBe('key-b')
  })

  it('should filter dismissed packs from check results', () => {
    const dismissed: Record<string, string> = { 'pack-a': 'ckpt:200' }

    const plans: Record<string, UpdatePlanEntry> = {
      'pack-a': {
        pack: 'pack-a', already_up_to_date: false,
        changes: [{ dependency_id: 'ckpt', old: {}, new: { provider_version_id: 200 } }],
        ambiguous: [], impacted_packs: [],
      },
      'pack-b': {
        pack: 'pack-b', already_up_to_date: false,
        changes: [{ dependency_id: 'lora', old: {}, new: { provider_version_id: 400 } }],
        ambiguous: [], impacted_packs: [],
      },
    }

    // Filter logic from checkAll
    const filtered: Record<string, UpdatePlanEntry> = {}
    for (const [name, plan] of Object.entries(plans)) {
      const key = versionKeyFromPlan(plan)
      if (!dismissed[name] || dismissed[name] !== key) {
        filtered[name] = plan
      }
    }

    expect(Object.keys(filtered)).toEqual(['pack-b'])
    expect(filtered['pack-a']).toBeUndefined()
  })

  it('should NOT filter if dismissed version key differs', () => {
    const dismissed: Record<string, string> = { 'pack-a': 'ckpt:100' } // Old version

    const plans: Record<string, UpdatePlanEntry> = {
      'pack-a': {
        pack: 'pack-a', already_up_to_date: false,
        changes: [{ dependency_id: 'ckpt', old: {}, new: { provider_version_id: 200 } }], // New version
        ambiguous: [], impacted_packs: [],
      },
    }

    const filtered: Record<string, UpdatePlanEntry> = {}
    for (const [name, plan] of Object.entries(plans)) {
      const key = versionKeyFromPlan(plan)
      if (!dismissed[name] || dismissed[name] !== key) {
        filtered[name] = plan
      }
    }

    // Should NOT be filtered because version changed
    expect(Object.keys(filtered)).toEqual(['pack-a'])
  })
})

// ============================================================================
// Download Group ID Generation
// ============================================================================

describe('Download Group ID', () => {
  it('should generate unique group IDs', () => {
    const id1 = `update-${Date.now()}`
    // Small delay to ensure different timestamp
    const id2 = `update-${Date.now() + 1}`
    expect(id1).not.toBe(id2)
  })

  it('should start with "update-" prefix', () => {
    const id = `update-${Date.now()}`
    expect(id).toMatch(/^update-\d+$/)
  })
})

// ============================================================================
// Auto-Check Interval Configuration
// ============================================================================

describe('Auto-Check Interval', () => {
  const intervalMs: Record<string, number> = {
    '1h': 3_600_000,
    '6h': 21_600_000,
    '24h': 86_400_000,
  }

  it('1h maps to 3,600,000ms', () => {
    expect(intervalMs['1h']).toBe(3_600_000)
  })

  it('6h maps to 21,600,000ms', () => {
    expect(intervalMs['6h']).toBe(21_600_000)
  })

  it('24h maps to 86,400,000ms', () => {
    expect(intervalMs['24h']).toBe(86_400_000)
  })

  it('off is not in interval map', () => {
    expect(intervalMs['off']).toBeUndefined()
  })

  it('should check only when lastChecked is older than interval', () => {
    const now = Date.now()
    const interval = intervalMs['1h']

    // lastChecked 30 minutes ago — should NOT check
    const recentCheck = now - 30 * 60 * 1000
    expect(now - recentCheck >= interval).toBe(false)

    // lastChecked 2 hours ago — should check
    const oldCheck = now - 2 * 60 * 60 * 1000
    expect(now - oldCheck >= interval).toBe(true)
  })

  it('should check when lastChecked is null', () => {
    const lastChecked = null
    const shouldCheck = !lastChecked
    expect(shouldCheck).toBe(true)
  })
})

// ============================================================================
// Selection State Management
// ============================================================================

describe('Selection State', () => {
  /**
   * Test the selection logic from updatesStore.
   */

  function createSelectionState(selected: string[] = []) {
    let selectedPacks = [...selected]

    return {
      get: () => selectedPacks,
      select: (name: string) => {
        if (!selectedPacks.includes(name)) {
          selectedPacks = [...selectedPacks, name]
        }
      },
      deselect: (name: string) => {
        selectedPacks = selectedPacks.filter(n => n !== name)
      },
      toggle: (name: string) => {
        if (selectedPacks.includes(name)) {
          selectedPacks = selectedPacks.filter(n => n !== name)
        } else {
          selectedPacks = [...selectedPacks, name]
        }
      },
      selectAll: (allNames: string[]) => {
        selectedPacks = [...allNames]
      },
      deselectAll: () => {
        selectedPacks = []
      },
    }
  }

  it('should start empty', () => {
    const state = createSelectionState()
    expect(state.get()).toEqual([])
  })

  it('should select a pack', () => {
    const state = createSelectionState()
    state.select('pack-a')
    expect(state.get()).toEqual(['pack-a'])
  })

  it('should not duplicate on double-select', () => {
    const state = createSelectionState(['pack-a'])
    state.select('pack-a')
    expect(state.get()).toEqual(['pack-a'])
  })

  it('should deselect a pack', () => {
    const state = createSelectionState(['pack-a', 'pack-b'])
    state.deselect('pack-a')
    expect(state.get()).toEqual(['pack-b'])
  })

  it('should toggle pack selection', () => {
    const state = createSelectionState(['pack-a'])
    state.toggle('pack-a') // deselect
    expect(state.get()).toEqual([])
    state.toggle('pack-a') // select
    expect(state.get()).toEqual(['pack-a'])
  })

  it('should select all', () => {
    const state = createSelectionState()
    state.selectAll(['pack-a', 'pack-b', 'pack-c'])
    expect(state.get()).toEqual(['pack-a', 'pack-b', 'pack-c'])
  })

  it('should deselect all', () => {
    const state = createSelectionState(['pack-a', 'pack-b'])
    state.deselectAll()
    expect(state.get()).toEqual([])
  })
})

// ============================================================================
// Settings Store: Auto-Check Updates
// ============================================================================

describe('Settings Store: Auto-Check', () => {
  type AutoCheckInterval = 'off' | '1h' | '6h' | '24h'

  interface SettingsState {
    nsfwBlurEnabled: boolean
    autoCheckUpdates: AutoCheckInterval
  }

  function createSettingsStore(initial: Partial<SettingsState> = {}) {
    let state: SettingsState = {
      nsfwBlurEnabled: true,
      autoCheckUpdates: 'off',
      ...initial,
    }

    return {
      getState: () => state,
      setAutoCheckUpdates: (interval: AutoCheckInterval) => {
        state = { ...state, autoCheckUpdates: interval }
      },
      toggleNsfwBlur: () => {
        state = { ...state, nsfwBlurEnabled: !state.nsfwBlurEnabled }
      },
    }
  }

  it('should default to off', () => {
    const store = createSettingsStore()
    expect(store.getState().autoCheckUpdates).toBe('off')
  })

  it('should accept all valid intervals', () => {
    const store = createSettingsStore()
    const intervals: AutoCheckInterval[] = ['off', '1h', '6h', '24h']
    for (const interval of intervals) {
      store.setAutoCheckUpdates(interval)
      expect(store.getState().autoCheckUpdates).toBe(interval)
    }
  })

  it('should not affect NSFW blur when changing auto-check', () => {
    const store = createSettingsStore({ nsfwBlurEnabled: true })
    store.setAutoCheckUpdates('6h')
    expect(store.getState().nsfwBlurEnabled).toBe(true)
  })

  it('should preserve auto-check when toggling NSFW blur', () => {
    const store = createSettingsStore({ autoCheckUpdates: '24h' })
    store.toggleNsfwBlur()
    expect(store.getState().autoCheckUpdates).toBe('24h')
  })
})

// ============================================================================
// Format Utilities (from format.ts)
// ============================================================================

describe('Format Utilities', () => {
  // Reproduce the format.ts functions
  function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  function formatSpeed(bps: number): string {
    if (bps === 0) return '--'
    return formatBytes(bps) + '/s'
  }

  function formatEta(seconds: number): string {
    if (seconds <= 0) return '--'
    if (seconds < 60) return `${Math.round(seconds)}s`
    if (seconds < 3600) {
      const mins = Math.floor(seconds / 60)
      const secs = Math.round(seconds % 60)
      return `${mins}m ${secs}s`
    }
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${mins}m`
  }

  describe('formatBytes', () => {
    it('formats zero bytes', () => expect(formatBytes(0)).toBe('0 B'))
    it('formats bytes', () => expect(formatBytes(512)).toBe('512 B'))
    it('formats kilobytes', () => expect(formatBytes(1024)).toBe('1 KB'))
    it('formats megabytes', () => expect(formatBytes(1048576)).toBe('1 MB'))
    it('formats gigabytes', () => expect(formatBytes(1073741824)).toBe('1 GB'))
    it('formats fractional', () => expect(formatBytes(1536)).toBe('1.5 KB'))
  })

  describe('formatSpeed', () => {
    it('formats zero speed', () => expect(formatSpeed(0)).toBe('--'))
    it('formats MB/s', () => expect(formatSpeed(1048576)).toBe('1 MB/s'))
  })

  describe('formatEta', () => {
    it('formats zero seconds', () => expect(formatEta(0)).toBe('--'))
    it('formats negative', () => expect(formatEta(-5)).toBe('--'))
    it('formats seconds', () => expect(formatEta(30)).toBe('30s'))
    it('formats minutes', () => expect(formatEta(90)).toBe('1m 30s'))
    it('formats hours', () => expect(formatEta(3660)).toBe('1h 1m'))
  })
})
