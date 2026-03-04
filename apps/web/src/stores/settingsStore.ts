import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useNsfwStore } from './nsfwStore'

export type AutoCheckInterval = 'off' | '1h' | '6h' | '24h'

interface SettingsState {
  /** @deprecated Use useNsfwStore instead. Kept for backward compatibility. */
  nsfwBlurEnabled: boolean
  autoCheckUpdates: AutoCheckInterval
  toggleNsfwBlur: () => void
  setNsfwBlur: (enabled: boolean) => void
  setAutoCheckUpdates: (interval: AutoCheckInterval) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      // Delegated to nsfwStore — initial value synced from nsfwStore
      nsfwBlurEnabled: useNsfwStore.getState().nsfwBlurEnabled,
      autoCheckUpdates: 'off' as AutoCheckInterval,

      toggleNsfwBlur: () => {
        const nsfw = useNsfwStore.getState()
        const newMode = nsfw.filterMode === 'show' ? 'blur' : 'show'
        nsfw.setFilterMode(newMode)
        set({ nsfwBlurEnabled: newMode !== 'show' })
      },

      setNsfwBlur: (enabled) => {
        useNsfwStore.getState().setFilterMode(enabled ? 'blur' : 'show')
        set({ nsfwBlurEnabled: enabled })
      },

      setAutoCheckUpdates: (interval) => set({ autoCheckUpdates: interval }),
    }),
    {
      name: 'synapse-settings',
    }
  )
)

// Keep settingsStore in sync when nsfwStore changes externally
useNsfwStore.subscribe((state) => {
  const current = useSettingsStore.getState().nsfwBlurEnabled
  const newVal = state.filterMode !== 'show'
  if (current !== newVal) {
    useSettingsStore.setState({ nsfwBlurEnabled: newVal })
  }
})
