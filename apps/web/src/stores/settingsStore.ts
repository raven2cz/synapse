import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SettingsState {
  nsfwBlurEnabled: boolean
  toggleNsfwBlur: () => void
  setNsfwBlur: (enabled: boolean) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      nsfwBlurEnabled: true,
      
      toggleNsfwBlur: () => set((state) => ({ 
        nsfwBlurEnabled: !state.nsfwBlurEnabled 
      })),
      
      setNsfwBlur: (enabled) => set({ nsfwBlurEnabled: enabled }),
    }),
    {
      name: 'synapse-settings',
    }
  )
)
