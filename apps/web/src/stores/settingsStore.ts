import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type AutoCheckInterval = 'off' | '1h' | '6h' | '24h'

interface SettingsState {
  nsfwBlurEnabled: boolean
  autoCheckUpdates: AutoCheckInterval
  toggleNsfwBlur: () => void
  setNsfwBlur: (enabled: boolean) => void
  setAutoCheckUpdates: (interval: AutoCheckInterval) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      nsfwBlurEnabled: true,
      autoCheckUpdates: 'off' as AutoCheckInterval,

      toggleNsfwBlur: () => set((state) => ({
        nsfwBlurEnabled: !state.nsfwBlurEnabled
      })),

      setNsfwBlur: (enabled) => set({ nsfwBlurEnabled: enabled }),

      setAutoCheckUpdates: (interval) => set({ autoCheckUpdates: interval }),
    }),
    {
      name: 'synapse-settings',
    }
  )
)
