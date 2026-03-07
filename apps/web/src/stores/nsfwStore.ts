import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// =============================================================================
// Types
// =============================================================================

export type NsfwFilterMode = 'show' | 'blur' | 'hide'
export type NsfwMaxLevel = 'pg' | 'pg13' | 'r' | 'x' | 'all'

interface NsfwState {
  filterMode: NsfwFilterMode
  maxLevel: NsfwMaxLevel

  setFilterMode: (mode: NsfwFilterMode) => void
  setMaxLevel: (level: NsfwMaxLevel) => void
  getBrowsingLevel: () => number
  shouldBlur: (nsfwLevel: number | boolean) => boolean
  shouldHide: (nsfwLevel: number | boolean) => boolean

  /** Backward compat — equals filterMode !== 'show' */
  nsfwBlurEnabled: boolean
}

// =============================================================================
// Constants
// =============================================================================

const STORAGE_KEY = 'synapse-nsfw-settings'

// =============================================================================
// Browsing level bitmask mapping (Civitai convention)
// =============================================================================

export const LEVEL_BITMASK: Record<NsfwMaxLevel, number> = {
  pg: 1,
  pg13: 3,
  r: 7,
  x: 15,
  all: 31,
}

// =============================================================================
// Level helpers
// =============================================================================

/** Sentinel for unknown NSFW level (legacy boolean=true with no numeric info) */
export const UNKNOWN_NSFW_LEVEL = -1

/** Check if an item's level exceeds the allowed bitmask ceiling */
export function exceedsMaxLevel(itemLevel: number, maxBitmask: number): boolean {
  const safeBitmask = maxBitmask ?? 1
  if (itemLevel === UNKNOWN_NSFW_LEVEL) {
    // Fail closed: if user restricts level (maxBitmask < 31), hide unknown NSFW items
    return safeBitmask !== 31
  }
  // Check if item has ANY bit set that is NOT in the safe bitmask
  // This securely handles spoofed multi-bit values (like MAX_SAFE_INTEGER or 63)
  return (itemLevel & ~safeBitmask) !== 0
}

/** Normalize boolean or numeric NSFW level to a consistent shape.
 *  Invalid/malformed inputs (NaN, 0, negative, floats) are treated as unknown NSFW (fail closed). */
export function normalizeLevel(nsfwLevel: number | boolean): { isNsfw: boolean; level: number } {
  if (typeof nsfwLevel === 'boolean') {
    return { isNsfw: nsfwLevel, level: nsfwLevel ? UNKNOWN_NSFW_LEVEL : 1 }
  }
  if (!Number.isFinite(nsfwLevel) || nsfwLevel < 1 || !Number.isInteger(nsfwLevel)) {
    return { isNsfw: true, level: UNKNOWN_NSFW_LEVEL }
  }
  return { isNsfw: nsfwLevel > 1, level: nsfwLevel }
}

// =============================================================================
// Migration from legacy settingsStore
// =============================================================================

function migrateFromSettingsStore(): { filterMode: NsfwFilterMode; maxLevel: NsfwMaxLevel } | null {
  try {
    const raw = localStorage.getItem('synapse-settings')
    if (!raw) return null
    const parsed = JSON.parse(raw)
    const legacy = parsed?.state?.nsfwBlurEnabled
    if (typeof legacy !== 'boolean') return null

    return {
      filterMode: legacy ? 'blur' : 'show',
      maxLevel: 'all',
    }
  } catch {
    return null
  }
}

// =============================================================================
// Store
// =============================================================================

export const useNsfwStore = create<NsfwState>()(
  persist(
    (set, get) => {
      const migrated = migrateFromSettingsStore()

      return {
        filterMode: migrated?.filterMode ?? 'blur',
        maxLevel: migrated?.maxLevel ?? 'all',

        setFilterMode: (mode) => set({ filterMode: mode, nsfwBlurEnabled: mode !== 'show' }),
        setMaxLevel: (level) => set({ maxLevel: level }),

        getBrowsingLevel: () => LEVEL_BITMASK[get().maxLevel] ?? 1,

        shouldBlur: (nsfwLevel: number | boolean) => {
          const { isNsfw } = normalizeLevel(nsfwLevel)
          return get().filterMode === 'blur' && isNsfw
        },

        shouldHide: (nsfwLevel: number | boolean) => {
          const { isNsfw, level } = normalizeLevel(nsfwLevel)
          if (!isNsfw) return false
          if (get().filterMode === 'hide') return true
          return exceedsMaxLevel(level, LEVEL_BITMASK[get().maxLevel])
        },

        nsfwBlurEnabled: (migrated?.filterMode ?? 'blur') !== 'show',
      }
    },
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        filterMode: state.filterMode,
        maxLevel: state.maxLevel,
        nsfwBlurEnabled: state.filterMode !== 'show',
      }),
      // Guard against localStorage tampering: only merge validated data fields
      merge: (persisted, current) => {
        const p = persisted as Record<string, unknown> | undefined
        if (!p || typeof p !== 'object') return current
        const validModes: NsfwFilterMode[] = ['show', 'blur', 'hide']
        const validLevels: NsfwMaxLevel[] = ['pg', 'pg13', 'r', 'x', 'all']
        return {
          ...current,
          filterMode: validModes.includes(p.filterMode as NsfwFilterMode) ? (p.filterMode as NsfwFilterMode) : current.filterMode,
          maxLevel: validLevels.includes(p.maxLevel as NsfwMaxLevel) ? (p.maxLevel as NsfwMaxLevel) : current.maxLevel,
          nsfwBlurEnabled: validModes.includes(p.filterMode as NsfwFilterMode) ? (p.filterMode as NsfwFilterMode) !== 'show' : current.nsfwBlurEnabled,
        }
      },
    }
  )
)

// =============================================================================
// Cross-tab sync
// =============================================================================

const NSFW_DEFAULTS = { filterMode: 'blur' as const, maxLevel: 'all' as const }

let _storageListenerAttached = false
if (typeof window !== 'undefined' && !_storageListenerAttached) {
  _storageListenerAttached = true
  window.addEventListener('storage', (e) => {
    if (e.key !== STORAGE_KEY) return
    if (e.newValue === null) {
      useNsfwStore.setState({ ...NSFW_DEFAULTS, nsfwBlurEnabled: true })
      return
    }
    try {
      const { state } = JSON.parse(e.newValue)
      const validModes: NsfwFilterMode[] = ['show', 'blur', 'hide']
      const validLevels: NsfwMaxLevel[] = ['pg', 'pg13', 'r', 'x', 'all']
      if (!validModes.includes(state?.filterMode) || !validLevels.includes(state?.maxLevel)) return
      // Prevent oscillation: skip if already in sync (avoids persist write-back loop)
      const current = useNsfwStore.getState()
      if (current.filterMode === state.filterMode && current.maxLevel === state.maxLevel) return
      useNsfwStore.setState({
        filterMode: state.filterMode,
        maxLevel: state.maxLevel,
        nsfwBlurEnabled: state.filterMode !== 'show',
      })
    } catch { /* ignore malformed JSON */ }
  })
}
