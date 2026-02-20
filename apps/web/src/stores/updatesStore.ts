import { create } from 'zustand'

export interface PendingDownloadEntry {
  dependency_id: string
  sha256: string
  download_url: string
  size_bytes?: number | null
}

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
  pending_downloads: PendingDownloadEntry[]
  impacted_packs: string[]
}

export interface UpdateOptions {
  merge_previews: boolean
  update_description: boolean
  update_model_info: boolean
}

// --- Dismissed persistence ---
const DISMISSED_KEY = 'synapse-updates-dismissed'

function loadDismissed(): Record<string, string> {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveDismissed(dismissed: Record<string, string>) {
  try {
    localStorage.setItem(DISMISSED_KEY, JSON.stringify(dismissed))
  } catch {
    // Ignore localStorage errors
  }
}

/** Build a version key from plan changes for dismissed tracking */
function versionKeyFromPlan(plan: UpdatePlanEntry): string {
  const ids = [
    ...plan.changes.map(c => `${c.dependency_id}:${(c.new as Record<string, unknown>)?.provider_version_id ?? '?'}`),
    ...plan.ambiguous.map(a => `${a.dependency_id}:ambiguous`),
  ]
  return ids.sort().join(',')
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

  // Download group tracking
  activeGroupId: string | null

  // Dismissed updates persistence
  dismissedVersions: Record<string, string>

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
  retryDownloads: (packName: string) => Promise<boolean>
  retryAllPending: () => Promise<{ queued: number; failed: number }>
  dismissUpdate: (packName: string) => void
  cancelBatch: () => Promise<void>
  clearAll: () => void
}

/**
 * Queue downloads for changed dependencies via the existing download-asset endpoint.
 * This gives us progress tracking, Downloads tab integration, proper symlinks, etc.
 */
async function queueDownloadsForPack(
  packName: string,
  plan: UpdatePlanEntry,
  groupId?: string,
): Promise<void> {
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
          ...(groupId ? { group_id: groupId, group_label: 'Pack Updates' } : {}),
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
  activeGroupId: null,
  dismissedVersions: loadDismissed(),
  updatesCount: 0,

  checkAll: async () => {
    set(() => ({ isChecking: true, checkError: null }))
    try {
      const res = await fetch('/api/updates/check-all')
      if (!res.ok) throw new Error('Failed to check updates')
      const data = await res.json()

      const plans: Record<string, UpdatePlanEntry> = data.plans || {}
      const dismissed = { ...get().dismissedVersions }

      // Clean up stale dismissed entries for packs no longer in results
      // (pack was deleted, or version changed so the old dismissed key is irrelevant)
      const allCheckedPacks = new Set(Object.keys(plans))
      let dismissedChanged = false
      for (const name of Object.keys(dismissed)) {
        if (!allCheckedPacks.has(name)) {
          delete dismissed[name]
          dismissedChanged = true
        }
      }
      if (dismissedChanged) {
        saveDismissed(dismissed)
      }

      // Filter out dismissed updates (but never dismiss pending downloads)
      const filtered: Record<string, UpdatePlanEntry> = {}
      for (const [name, plan] of Object.entries(plans)) {
        const hasPending = (plan.pending_downloads?.length ?? 0) > 0
        if (hasPending) {
          // Always show packs with pending downloads - can't dismiss missing blobs
          filtered[name] = plan
        } else {
          const key = versionKeyFromPlan(plan)
          if (!dismissed[name] || dismissed[name] !== key) {
            filtered[name] = plan
          }
        }
      }

      const packNames = Object.keys(filtered)

      set(() => ({
        isChecking: false,
        lastChecked: Date.now(),
        availableUpdates: filtered,
        updatesCount: packNames.length,
        selectedPacks: [...packNames],
        dismissedVersions: dismissed,
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
        const groupId = `update-${Date.now()}`
        const plan = get().availableUpdates[packName]
        if (plan) {
          await queueDownloadsForPack(packName, plan, groupId)
        }

        set((state) => {
          const updates = { ...state.availableUpdates }
          delete updates[packName]
          return {
            availableUpdates: updates,
            updatesCount: Object.keys(updates).length,
            selectedPacks: state.selectedPacks.filter(n => n !== packName),
            applyingPacks: state.applyingPacks.filter(n => n !== packName),
            activeGroupId: groupId,
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

    // Generate group ID for all downloads in this batch
    const groupId = `update-${Date.now()}`

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
            await queueDownloadsForPack(packName, plan, groupId)
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
          activeGroupId: appliedPacks.length > 0 ? groupId : null,
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
    const plan = updates[packName]

    // Record dismissed version key for persistence
    const dismissed = { ...state.dismissedVersions }
    if (plan) {
      dismissed[packName] = versionKeyFromPlan(plan)
      saveDismissed(dismissed)
    }

    delete updates[packName]
    return {
      availableUpdates: updates,
      updatesCount: Object.keys(updates).length,
      selectedPacks: state.selectedPacks.filter(n => n !== packName),
      dismissedVersions: dismissed,
    }
  }),

  retryDownloads: async (packName: string) => {
    const plan = get().availableUpdates[packName]
    if (!plan || !plan.pending_downloads?.length) return false

    const groupId = `retry-${Date.now()}`

    set((state) => ({
      applyingPacks: [...state.applyingPacks, packName],
    }))

    try {
      // Queue downloads for each pending dep via download-asset
      // Pass the rebuilt URL from plan to override stale lock URLs
      for (const pending of plan.pending_downloads) {
        try {
          await fetch(`/api/packs/${encodeURIComponent(packName)}/download-asset`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_name: pending.dependency_id,
              ...(pending.download_url ? { url: pending.download_url } : {}),
              group_id: groupId,
              group_label: 'Retry Downloads',
            }),
          })
        } catch {
          // Non-fatal per-dep failure
        }
      }

      // Also queue downloads for regular changes if any
      if (plan.changes.length > 0) {
        await queueDownloadsForPack(packName, plan, groupId)
      }

      set((state) => {
        const updates = { ...state.availableUpdates }
        delete updates[packName]
        return {
          availableUpdates: updates,
          updatesCount: Object.keys(updates).length,
          selectedPacks: state.selectedPacks.filter(n => n !== packName),
          applyingPacks: state.applyingPacks.filter(n => n !== packName),
          activeGroupId: groupId,
        }
      })
      return true
    } catch {
      set((state) => ({
        applyingPacks: state.applyingPacks.filter(n => n !== packName),
      }))
      return false
    }
  },

  retryAllPending: async () => {
    const { selectedPacks, availableUpdates } = get()
    const groupId = `retry-${Date.now()}`
    let queued = 0
    let failed = 0

    // Mark all as applying
    set((state) => ({
      applyingPacks: [...new Set([...state.applyingPacks, ...selectedPacks])],
    }))

    for (const packName of selectedPacks) {
      const plan = availableUpdates[packName]
      if (!plan) continue

      const hasPending = (plan.pending_downloads?.length ?? 0) > 0
      const hasChanges = plan.changes.length > 0 || plan.ambiguous.length > 0

      try {
        if (hasPending) {
          for (const pending of plan.pending_downloads) {
            await fetch(`/api/packs/${encodeURIComponent(packName)}/download-asset`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                asset_name: pending.dependency_id,
                ...(pending.download_url ? { url: pending.download_url } : {}),
                group_id: groupId,
                group_label: 'Retry Downloads',
              }),
            })
          }
        }

        if (hasChanges) {
          // Apply lock changes first, then queue downloads
          const body: Record<string, unknown> = { pack: packName, sync: false }
          const res = await fetch('/api/updates/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          })
          if (res.ok) {
            const result = await res.json()
            if (result.applied) {
              await queueDownloadsForPack(packName, plan, groupId)
            }
          }
        }

        queued++
      } catch {
        failed++
      }
    }

    // Remove processed packs
    set((state) => {
      const updates = { ...state.availableUpdates }
      for (const name of selectedPacks) {
        delete updates[name]
      }
      return {
        availableUpdates: updates,
        updatesCount: Object.keys(updates).length,
        selectedPacks: [],
        applyingPacks: [],
        activeGroupId: queued > 0 ? groupId : null,
      }
    })

    return { queued, failed }
  },

  cancelBatch: async () => {
    const { activeGroupId } = get()
    if (!activeGroupId) return

    try {
      await fetch(`/api/packs/downloads/group/${encodeURIComponent(activeGroupId)}`, {
        method: 'DELETE',
      })
    } catch {
      // Best-effort cancel
    }

    set(() => ({ activeGroupId: null }))
  },

  clearAll: () => set(() => ({
    availableUpdates: {},
    selectedPacks: [],
    applyingPacks: [],
    activeGroupId: null,
    updatesCount: 0,
    lastChecked: null,
    checkError: null,
  })),
}))
