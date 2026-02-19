import { create } from 'zustand'

export interface UpdatePlanEntry {
  pack: string
  already_up_to_date: boolean
  changes: Array<{
    dependency_id: string
    old: Record<string, unknown>
    new: Record<string, unknown>
  }>
  ambiguous: Array<{
    dependency_id: string
    candidates: Array<{
      provider: string
      provider_model_id?: number
      provider_version_id?: number
      provider_file_id?: number
      sha256?: string
    }>
  }>
  impacted_packs: string[]
}

export interface UpdateOptions {
  merge_previews: boolean
  update_description: boolean
  update_model_info: boolean
}

interface UpdatesState {
  // Check state
  isChecking: boolean
  lastChecked: number | null
  checkError: string | null

  // Results - only packs with actual updates
  availableUpdates: Record<string, UpdatePlanEntry>

  // Selection for bulk operations (arrays for reliable React re-renders)
  selectedPacks: string[]

  // Apply state
  applyingPacks: string[]

  // Computed
  updatesCount: number

  // Actions
  checkAll: () => Promise<void>
  selectPack: (name: string) => void
  deselectPack: (name: string) => void
  selectAll: () => void
  deselectAll: () => void
  togglePack: (name: string) => void
  applyUpdate: (packName: string, options?: Partial<UpdateOptions>) => Promise<boolean>
  applySelected: (options?: Partial<UpdateOptions>) => Promise<{ applied: number; failed: number }>
  dismissUpdate: (packName: string) => void
  clearAll: () => void
}

/**
 * Queue downloads for changed dependencies via the existing download-asset endpoint.
 * This gives us progress tracking, Downloads tab integration, proper symlinks, etc.
 */
async function queueDownloadsForPack(packName: string, plan: UpdatePlanEntry): Promise<void> {
  const changedDeps = [
    ...plan.changes.map(c => c.dependency_id),
    ...plan.ambiguous.map(a => a.dependency_id),
  ]

  for (const depId of changedDeps) {
    try {
      await fetch(`/api/packs/${encodeURIComponent(packName)}/download-asset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_name: depId,
          // URL and asset_type auto-detected from lock + dependency
        }),
      })
    } catch {
      // Download queue failure is non-fatal - user can retry from Downloads tab
    }
  }
}

export const useUpdatesStore = create<UpdatesState>((set, get) => ({
  isChecking: false,
  lastChecked: null,
  checkError: null,
  availableUpdates: {},
  selectedPacks: [],
  applyingPacks: [],
  updatesCount: 0,

  checkAll: async () => {
    set(() => ({ isChecking: true, checkError: null }))
    try {
      const res = await fetch('/api/updates/check-all')
      if (!res.ok) throw new Error('Failed to check updates')
      const data = await res.json()

      const plans: Record<string, UpdatePlanEntry> = data.plans || {}
      const packNames = Object.keys(plans)

      set(() => ({
        isChecking: false,
        lastChecked: Date.now(),
        availableUpdates: plans,
        updatesCount: packNames.length,
        selectedPacks: [...packNames],
      }))
    } catch (e) {
      set(() => ({
        isChecking: false,
        checkError: e instanceof Error ? e.message : 'Unknown error',
      }))
    }
  },

  selectPack: (name: string) => set((state) => {
    if (state.selectedPacks.includes(name)) return state
    return { selectedPacks: [...state.selectedPacks, name] }
  }),

  deselectPack: (name: string) => set((state) => ({
    selectedPacks: state.selectedPacks.filter(n => n !== name),
  })),

  selectAll: () => set((state) => ({
    selectedPacks: Object.keys(state.availableUpdates),
  })),

  deselectAll: () => set(() => ({
    selectedPacks: [],
  })),

  togglePack: (name: string) => set((state) => {
    if (state.selectedPacks.includes(name)) {
      return { selectedPacks: state.selectedPacks.filter(n => n !== name) }
    }
    return { selectedPacks: [...state.selectedPacks, name] }
  }),

  applyUpdate: async (packName: string, options?: Partial<UpdateOptions>) => {
    set((state) => ({
      applyingPacks: [...state.applyingPacks, packName],
    }))

    try {
      // Step 1: Apply lock changes only (no sync - downloads go through download-asset)
      const body: Record<string, unknown> = {
        pack: packName,
        sync: false,
      }
      if (options) {
        body.options = options
      }

      const res = await fetch('/api/updates/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) throw new Error('Failed to apply update')
      const result = await res.json()

      if (result.applied) {
        // Step 2: Queue downloads via existing download-asset endpoint
        // This gives us progress tracking, Downloads tab, etc.
        const plan = get().availableUpdates[packName]
        if (plan) {
          await queueDownloadsForPack(packName, plan)
        }

        set((state) => {
          const updates = { ...state.availableUpdates }
          delete updates[packName]
          return {
            availableUpdates: updates,
            updatesCount: Object.keys(updates).length,
            selectedPacks: state.selectedPacks.filter(n => n !== packName),
            applyingPacks: state.applyingPacks.filter(n => n !== packName),
          }
        })
        return true
      }

      set((state) => ({
        applyingPacks: state.applyingPacks.filter(n => n !== packName),
      }))
      return false
    } catch {
      set((state) => ({
        applyingPacks: state.applyingPacks.filter(n => n !== packName),
      }))
      return false
    }
  },

  applySelected: async (options?: Partial<UpdateOptions>) => {
    const { selectedPacks, availableUpdates } = get()
    const packs = [...selectedPacks]

    if (packs.length === 0) return { applied: 0, failed: 0 }

    // Mark all as applying
    set((state) => ({
      applyingPacks: [...new Set([...state.applyingPacks, ...packs])],
    }))

    try {
      // Step 1: Apply all lock changes (no sync)
      const body: Record<string, unknown> = {
        packs,
        sync: false,
      }
      if (options) {
        body.options = options
      }

      const res = await fetch('/api/updates/apply-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) throw new Error('Failed to apply batch update')
      const result = await res.json()

      // Step 2: Queue downloads for each successfully applied pack
      const appliedPacks: string[] = []
      for (const [packName, packResult] of Object.entries(result.results || {})) {
        if ((packResult as Record<string, unknown>).applied) {
          appliedPacks.push(packName)
          const plan = availableUpdates[packName]
          if (plan) {
            await queueDownloadsForPack(packName, plan)
          }
        }
      }

      // Remove applied packs from available updates
      set((state) => {
        const updates = { ...state.availableUpdates }
        let selected = [...state.selectedPacks]
        for (const packName of appliedPacks) {
          delete updates[packName]
          selected = selected.filter(n => n !== packName)
        }
        return {
          availableUpdates: updates,
          updatesCount: Object.keys(updates).length,
          selectedPacks: selected,
          applyingPacks: [],
        }
      })

      return {
        applied: result.total_applied || 0,
        failed: result.total_failed || 0,
      }
    } catch {
      set(() => ({ applyingPacks: [] }))
      return { applied: 0, failed: packs.length }
    }
  },

  dismissUpdate: (packName: string) => set((state) => {
    const updates = { ...state.availableUpdates }
    delete updates[packName]
    return {
      availableUpdates: updates,
      updatesCount: Object.keys(updates).length,
      selectedPacks: state.selectedPacks.filter(n => n !== packName),
    }
  }),

  clearAll: () => set(() => ({
    availableUpdates: {},
    selectedPacks: [],
    applyingPacks: [],
    updatesCount: 0,
    lastChecked: null,
    checkError: null,
  })),
}))
