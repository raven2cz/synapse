/**
 * usePackDownloads Hook
 *
 * Manages download progress tracking for pack assets.
 * Handles active downloads polling and state synchronization.
 */

import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/stores/toastStore'
import type { DownloadProgress, AssetInfo } from '../types'
import { QUERY_KEYS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface UsePackDownloadsOptions {
  /**
   * Pack name to track downloads for
   */
  packName: string
}

export interface UsePackDownloadsReturn {
  /**
   * List of active downloads for this pack
   */
  activeDownloads: DownloadProgress[]

  /**
   * Get download progress for a specific asset
   */
  getAssetDownload: (assetName: string) => DownloadProgress | undefined

  /**
   * Check if an asset is currently downloading
   */
  isDownloading: (assetName: string) => boolean

  /**
   * Check if any asset is downloading
   */
  hasActiveDownloads: boolean

  /**
   * Start downloading a single asset
   */
  downloadAsset: (asset: AssetInfo) => void

  /**
   * Check if download mutation is pending for an asset
   */
  isDownloadingAsset: boolean

  /**
   * Start downloading all pending assets
   */
  downloadAll: () => void

  /**
   * Check if download all mutation is pending
   */
  isDownloadingAll: boolean

  /**
   * Total progress (0-100) for all active downloads
   */
  totalProgress: number

  /**
   * Refresh active downloads
   */
  refetchDownloads: () => void
}

// =============================================================================
// Hook Implementation
// =============================================================================

export function usePackDownloads({
  packName,
}: UsePackDownloadsOptions): UsePackDownloadsReturn {
  const queryClient = useQueryClient()

  // Track assets we've started downloading (for immediate UI feedback)
  const [downloadingAssets, setDownloadingAssets] = useState<Set<string>>(new Set())

  // =========================================================================
  // Active Downloads Query
  // =========================================================================

  const {
    data: allActiveDownloads = [],
    refetch: refetchDownloads,
  } = useQuery<DownloadProgress[]>({
    queryKey: ['downloads-active'],
    queryFn: async () => {
      try {
        const res = await fetch('/api/packs/downloads/active')
        if (!res.ok) return []
        return res.json()
      } catch {
        return []
      }
    },
    // Always fetch fresh data when component mounts
    refetchOnMount: 'always',
    staleTime: 0,
    // Poll when there are active downloads for THIS pack
    refetchInterval: (query) => {
      const downloads = query.state.data as DownloadProgress[] | undefined
      const hasActiveForPack = downloads?.some(
        d => d.pack_name === packName && (d.status === 'downloading' || d.status === 'pending')
      )
      return (hasActiveForPack || downloadingAssets.size > 0) ? 1000 : false
    },
  })

  // Filter to only this pack's downloads
  const activeDownloads = allActiveDownloads.filter(d => d.pack_name === packName)

  // =========================================================================
  // Sync Local State with Server State
  // =========================================================================

  // Sync downloadingAssets with activeDownloads (for when page is revisited)
  useEffect(() => {
    const activeForPack = allActiveDownloads.filter(
      d => d.pack_name === packName && (d.status === 'downloading' || d.status === 'pending')
    )
    if (activeForPack.length > 0) {
      const newSet = new Set(activeForPack.map(d => d.asset_name))
      setDownloadingAssets(prev => {
        // Only update if different to avoid infinite loops
        if (prev.size !== newSet.size || [...prev].some(x => !newSet.has(x))) {
          return newSet
        }
        return prev
      })
    }
  }, [allActiveDownloads, packName])

  // =========================================================================
  // Handle Completed Downloads
  // =========================================================================

  useEffect(() => {
    if (allActiveDownloads.length === 0) return

    // Find completed downloads for this pack
    const completed = allActiveDownloads.filter(
      d => d.pack_name === packName && (d.status === 'completed' || d.status === 'failed')
    )

    if (completed.length > 0) {
      // Show toast for failed downloads
      const failed = completed.filter(d => d.status === 'failed')
      failed.forEach(d => {
        const errorMsg = d.error || 'Download failed'
        toast.error(`Failed to download ${d.filename}: ${errorMsg}`)
      })

      // Show toast for successful downloads
      const successful = completed.filter(d => d.status === 'completed')
      successful.forEach(d => {
        toast.success(`Downloaded ${d.filename}`)
      })

      // Remove completed from downloadingAssets
      setDownloadingAssets(prev => {
        const next = new Set(prev)
        completed.forEach(d => next.delete(d.asset_name))
        return next
      })

      // Refresh pack data and backup status
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.packBackup(packName) })
    }
  }, [allActiveDownloads, packName, queryClient])

  // =========================================================================
  // Download Single Asset Mutation
  // =========================================================================

  const downloadAssetMutation = useMutation({
    mutationFn: async (asset: AssetInfo) => {
      setDownloadingAssets(prev => new Set(prev).add(asset.name))

      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/download-asset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_name: asset.name,
          asset_type: asset.asset_type,
          url: asset.url,
          filename: asset.filename,
        }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to start download: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      // Refetch active downloads to show progress
      refetchDownloads()
    },
    onError: (error: Error, asset) => {
      setDownloadingAssets(prev => {
        const next = new Set(prev)
        next.delete(asset.name)
        return next
      })
      toast.error(`Download failed for ${asset.name}: ${error.message}`)
    },
  })

  // =========================================================================
  // Download All Mutation
  // =========================================================================

  const downloadAllMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/download-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      const text = await res.text()
      if (!res.ok) {
        throw new Error(`Failed to start downloads: ${text}`)
      }
      return JSON.parse(text)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success(`Started downloading ${data?.download_count || 'all'} assets`)
      refetchDownloads()
    },
    onError: (err: Error) => {
      toast.error(`Download failed: ${err.message}`)
    },
  })

  // =========================================================================
  // Helper Functions
  // =========================================================================

  const getAssetDownload = useCallback(
    (assetName: string): DownloadProgress | undefined => {
      return activeDownloads.find(d => d.asset_name === assetName)
    },
    [activeDownloads]
  )

  const isDownloading = useCallback(
    (assetName: string): boolean => {
      const download = activeDownloads.find(d => d.asset_name === assetName)
      return (
        downloadingAssets.has(assetName) ||
        (download?.status === 'downloading' || download?.status === 'pending')
      )
    },
    [activeDownloads, downloadingAssets]
  )

  // Calculate total progress
  const totalProgress = activeDownloads.length > 0
    ? activeDownloads.reduce((sum, d) => sum + (d.progress || 0), 0) / activeDownloads.length
    : 0

  const hasActiveDownloads = activeDownloads.some(
    d => d.status === 'downloading' || d.status === 'pending'
  )

  // =========================================================================
  // Return
  // =========================================================================

  return {
    activeDownloads,
    getAssetDownload,
    isDownloading,
    hasActiveDownloads,
    downloadAsset: (asset) => downloadAssetMutation.mutate(asset),
    isDownloadingAsset: downloadAssetMutation.isPending,
    downloadAll: () => downloadAllMutation.mutate(),
    isDownloadingAll: downloadAllMutation.isPending,
    totalProgress,
    refetchDownloads: () => refetchDownloads(),
  }
}

export default usePackDownloads
