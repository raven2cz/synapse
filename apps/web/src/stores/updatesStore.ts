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

  // Selection for bulk operations
  selectedPacks: Set<string>

  // Apply state
  applyingPacks: Set<string>

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

export const useUpdatesStore = create<UpdatesState>((set: (fn: (state: UpdatesState) => Partial<UpdatesState>) => void, get: () => UpdatesState) => ({
  isChecking: false,
  lastChecked: null,
  checkError: null,
  availableUpdates: {},
  selectedPacks: new Set<string>(),
  applyingPacks: new Set<string>(),
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
        // Auto-select all packs with updates
        selectedPacks: new Set(packNames),
      }))
    } catch (e) {
      set(() => ({
        isChecking: false,
        checkError: e instanceof Error ? e.message : 'Unknown error',
      }))
    }
  },

  selectPack: (name: string) => set((state: UpdatesState) => {
    const next = new Set(state.selectedPacks)
    next.add(name)
    return { selectedPacks: next }
  }),

  deselectPack: (name: string) => set((state: UpdatesState) => {
    const next = new Set(state.selectedPacks)
    next.delete(name)
    return { selectedPacks: next }
  }),

  selectAll: () => set((state: UpdatesState) => ({
    selectedPacks: new Set(Object.keys(state.availableUpdates)),
  })),

  deselectAll: () => set(() => ({
    selectedPacks: new Set<string>(),
  })),

  togglePack: (name: string) => set((state: UpdatesState) => {
    const next = new Set(state.selectedPacks)
    if (next.has(name)) {
      next.delete(name)
    } else {
      next.add(name)
    }
    return { selectedPacks: next }
  }),

  applyUpdate: async (packName: string, options?: Partial<UpdateOptions>) => {
    set((state: UpdatesState) => {
      const next = new Set(state.applyingPacks)
      next.add(packName)
      return { applyingPacks: next }
    })

    try {
      const body: Record<string, unknown> = {
        pack: packName,
        sync: true,
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
        // Remove from available updates
        set((state: UpdatesState) => {
          const updates = { ...state.availableUpdates }
          delete updates[packName]
          const selected = new Set(state.selectedPacks)
          selected.delete(packName)
          const applying = new Set(state.applyingPacks)
          applying.delete(packName)
          return {
            availableUpdates: updates,
            updatesCount: Object.keys(updates).length,
            selectedPacks: selected,
            applyingPacks: applying,
          }
        })
        return true
      }

      set((state: UpdatesState) => {
        const applying = new Set(state.applyingPacks)
        applying.delete(packName)
        return { applyingPacks: applying }
      })
      return false
    } catch {
      set((state: UpdatesState) => {
        const applying = new Set(state.applyingPacks)
        applying.delete(packName)
        return { applyingPacks: applying }
      })
      return false
    }
  },

  applySelected: async (options?: Partial<UpdateOptions>) => {
    const { selectedPacks } = get()
    const packs = Array.from(selectedPacks)

    if (packs.length === 0) return { applied: 0, failed: 0 }

    // Mark all as applying
    set((state: UpdatesState) => {
      const applying = new Set(state.applyingPacks)
      packs.forEach(p => applying.add(p))
      return { applyingPacks: applying }
    })

    try {
      const body: Record<string, unknown> = {
        packs,
        sync: true,
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

      // Remove applied packs from available updates
      set((state: UpdatesState) => {
        const updates = { ...state.availableUpdates }
        const selected = new Set(state.selectedPacks)
        for (const [packName, packResult] of Object.entries(result.results || {})) {
          if ((packResult as Record<string, unknown>).applied) {
            delete updates[packName]
            selected.delete(packName)
          }
        }
        return {
          availableUpdates: updates,
          updatesCount: Object.keys(updates).length,
          selectedPacks: selected,
          applyingPacks: new Set<string>(),
        }
      })

      return {
        applied: result.total_applied || 0,
        failed: result.total_failed || 0,
      }
    } catch {
      set(() => ({ applyingPacks: new Set<string>() }))
      return { applied: 0, failed: packs.length }
    }
  },

  dismissUpdate: (packName: string) => set((state: UpdatesState) => {
    const updates = { ...state.availableUpdates }
    delete updates[packName]
    const selected = new Set(state.selectedPacks)
    selected.delete(packName)
    return {
      availableUpdates: updates,
      updatesCount: Object.keys(updates).length,
      selectedPacks: selected,
    }
  }),

  clearAll: () => set(() => ({
    availableUpdates: {},
    selectedPacks: new Set<string>(),
    applyingPacks: new Set<string>(),
    updatesCount: 0,
    lastChecked: null,
    checkError: null,
  })),
}))
