import { create } from 'zustand'

interface PacksState {
    searchQuery: string
    selectedTag: string

    setSearchQuery: (query: string) => void
    setSelectedTag: (tag: string) => void
    resetFilters: () => void
}

export const usePacksStore = create<PacksState>((set) => ({
    searchQuery: '',
    selectedTag: '',

    setSearchQuery: (query) => set({ searchQuery: query }),
    setSelectedTag: (tag) => set({ selectedTag: tag }),
    resetFilters: () => set({ searchQuery: '', selectedTag: '' }),
}))
