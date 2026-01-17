import { create } from 'zustand'

export interface Download {
  id: string
  packName: string
  assetName: string
  filename: string
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'cancelled'
  progress: number  // 0-100
  downloadedBytes: number
  totalBytes: number
  speedBps: number  // bytes per second
  etaSeconds: number | null
  currentFile: string | null
  totalFiles: number
  completedFiles: number
  error: string | null
  startedAt: string
  completedAt: string | null
  targetPath: string | null
}

interface DownloadsState {
  downloads: Download[]
  addDownload: (download: Download) => void
  updateDownload: (id: string, updates: Partial<Download>) => void
  removeDownload: (id: string) => void
  clearCompleted: () => void
  getActiveDownloads: () => Download[]
  getDownloadByAsset: (assetName: string) => Download | undefined
}

export const useDownloadsStore = create<DownloadsState>((set: (fn: (state: DownloadsState) => Partial<DownloadsState>) => void, get: () => DownloadsState) => ({
  downloads: [],
  
  addDownload: (download: Download) => set((state: DownloadsState) => ({
    downloads: [download, ...state.downloads]
  })),
  
  updateDownload: (id: string, updates: Partial<Download>) => set((state: DownloadsState) => ({
    downloads: state.downloads.map((d: Download) => 
      d.id === id ? { ...d, ...updates } : d
    )
  })),
  
  removeDownload: (id: string) => set((state: DownloadsState) => ({
    downloads: state.downloads.filter((d: Download) => d.id !== id)
  })),
  
  clearCompleted: () => set((state: DownloadsState) => ({
    downloads: state.downloads.filter((d: Download) => 
      !['completed', 'failed', 'cancelled'].includes(d.status)
    )
  })),
  
  getActiveDownloads: () => {
    return get().downloads.filter((d: Download) => 
      ['pending', 'downloading'].includes(d.status)
    )
  },
  
  getDownloadByAsset: (assetName: string) => {
    return get().downloads.find((d: Download) => d.assetName === assetName)
  },
}))
