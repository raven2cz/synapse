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
  shouldBlur: (nsfw: boolean) => boolean
  shouldHide: (nsfw: boolean) => boolean

  /** Backward compat — equals filterMode !== 'show' */
  nsfwBlurEnabled: boolean
}

// =============================================================================
// Browsing level bitmask mapping (Civitai convention)
// =============================================================================

const LEVEL_BITMASK: Record<NsfwMaxLevel, number> = {
  pg: 1,
  pg13: 3,
  r: 7,
  x: 15,
  all: 31,
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

        getBrowsingLevel: () => LEVEL_BITMASK[get().maxLevel],

        shouldBlur: (nsfw: boolean) => nsfw && get().filterMode === 'blur',
        shouldHide: (nsfw: boolean) => nsfw && get().filterMode === 'hide',

        nsfwBlurEnabled: (migrated?.filterMode ?? 'blur') !== 'show',
      }
    },
    {
      name: 'synapse-nsfw-settings',
      partialize: (state) => ({
        filterMode: state.filterMode,
        maxLevel: state.maxLevel,
        nsfwBlurEnabled: state.filterMode !== 'show',
      }),
    }
  )
)
