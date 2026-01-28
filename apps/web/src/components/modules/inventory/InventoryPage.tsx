/**
 * InventoryPage - Main Inventory page
 *
 * Features:
 * - Dashboard with stats cards
 * - Filtering and search
 * - BlobsTable with all CRUD actions
 * - Cleanup wizard for orphan removal
 * - Backup sync wizard for bulk operations
 * - Delete confirmation with guard rails
 * - Impact analysis dialog
 * - Verify integrity dialog
 */
import { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { HardDrive, RefreshCw } from 'lucide-react'
import { Button } from '../../ui/Button'
import { toast } from '../../../stores/toastStore'
import { BreathingOrb } from '../../ui/BreathingOrb'
import { InventoryStats } from './InventoryStats'
import { InventoryFilters } from './InventoryFilters'
import { BlobsTable } from './BlobsTable'
import { DeleteConfirmationDialog } from './DeleteConfirmationDialog'
import { CleanupWizard } from './CleanupWizard'
import { BackupSyncWizard } from './BackupSyncWizard'
import { ImpactsDialog } from './ImpactsDialog'
import { VerifyProgressDialog } from './VerifyProgressDialog'
import type { VerifyResult } from './VerifyProgressDialog'
import type {
  InventoryResponse,
  BackupStatus,
  InventoryFilters as Filters,
  InventoryItem,
  BulkAction,
  CleanupResult,
  SyncResult,
  ImpactAnalysis,
} from './types'

// API functions
const api = {
  async getInventory(): Promise<InventoryResponse> {
    const res = await fetch('/api/store/inventory')
    if (!res.ok) throw new Error('Failed to fetch inventory')
    return res.json()
  },

  async getBackupStatus(): Promise<BackupStatus> {
    const res = await fetch('/api/store/backup/status')
    if (!res.ok) throw new Error('Failed to fetch backup status')
    return res.json()
  },

  async backupBlob(sha256: string): Promise<void> {
    const res = await fetch(`/api/store/backup/blob/${sha256}`, { method: 'POST' })
    if (!res.ok) {
      const errorText = await res.text()
      throw new Error(errorText || 'Failed to backup blob')
    }
  },

  async restoreBlob(sha256: string): Promise<void> {
    const res = await fetch(`/api/store/backup/restore/${sha256}`, { method: 'POST' })
    if (!res.ok) {
      const errorText = await res.text()
      throw new Error(errorText || 'Failed to restore blob')
    }
  },

  async deleteBlob(sha256: string, target: 'local' | 'backup' | 'both'): Promise<void> {
    const res = await fetch(`/api/store/inventory/${sha256}?target=${target}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      // Handle 409 Conflict (blob is referenced by packs)
      if (res.status === 409) {
        try {
          const data = await res.json()
          // FastAPI wraps HTTPException detail in "detail" key
          const impacts = data.detail?.impacts || data.impacts
          const packs = impacts?.used_by_packs || []
          if (packs.length > 0) {
            throw new Error(`Cannot delete: blob is used by ${packs.length} pack(s): ${packs.slice(0, 3).join(', ')}${packs.length > 3 ? '...' : ''}`)
          }
        } catch (e) {
          if (e instanceof Error && e.message.startsWith('Cannot delete:')) throw e
        }
        throw new Error('Cannot delete: blob is referenced by other packs')
      }
      const errorText = await res.text()
      throw new Error(errorText || 'Failed to delete blob')
    }
  },

  async cleanupOrphans(dryRun: boolean): Promise<CleanupResult> {
    const res = await fetch('/api/store/inventory/cleanup-orphans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: dryRun, max_items: 0 }),
    })
    if (!res.ok) {
      const errorText = await res.text()
      console.error('[Inventory] Cleanup failed:', res.status, errorText)
      throw new Error(`Failed to cleanup orphans: ${res.status}`)
    }
    return res.json()
  },

  async syncBackup(direction: 'to_backup' | 'from_backup', dryRun: boolean): Promise<SyncResult> {
    const res = await fetch('/api/store/backup/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        direction,
        dry_run: dryRun,
        only_missing: true,
      }),
    })
    if (!res.ok) {
      const errorText = await res.text()
      console.error('[Inventory] Sync backup failed:', res.status, errorText)
      throw new Error(`Failed to sync backup: ${res.status}`)
    }
    return res.json()
  },

  async getImpactAnalysis(sha256: string): Promise<ImpactAnalysis> {
    const res = await fetch(`/api/store/inventory/${sha256}/impact`)
    if (!res.ok) {
      const errorText = await res.text()
      throw new Error(errorText || 'Failed to get impact analysis')
    }
    return res.json()
  },

  async verifyIntegrity(): Promise<VerifyResult> {
    const res = await fetch('/api/store/inventory/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ all: true }),
    })
    if (!res.ok) {
      const errorText = await res.text()
      console.error('[Inventory] Verify failed:', res.status, errorText)
      throw new Error(`Failed to verify integrity: ${res.status}`)
    }
    // Transform API response to match VerifyResult interface
    // API returns: { verified, valid: string[], invalid: string[], duration_ms }
    // UI expects: { total, verified, failed, bytes_verified, errors: Array<{sha256, error}> }
    const data = await res.json()
    return {
      total: data.verified || 0,
      verified: (data.valid || []).length,
      failed: (data.invalid || []).length,
      bytes_verified: 0, // API doesn't provide this
      errors: (data.invalid || []).map((sha256: string) => ({
        sha256,
        error: 'Hash mismatch',
      })),
    }
  },
}

export function InventoryPage() {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<Filters>({
    kind: 'all',
    status: 'all',
    location: 'all',
    search: '',
  })

  // Dialog states
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<{
    item: InventoryItem | null
    target: 'local' | 'backup' | 'both'
  }>({ item: null, target: 'local' })

  const [cleanupWizardOpen, setCleanupWizardOpen] = useState(false)
  const [syncWizardOpen, setSyncWizardOpen] = useState(false)
  const [syncDirection, setSyncDirection] = useState<'to_backup' | 'from_backup'>('to_backup')
  const [impactsDialogOpen, setImpactsDialogOpen] = useState(false)
  const [impactAnalysis, setImpactAnalysis] = useState<ImpactAnalysis | null>(null)
  const [impactLoading, setImpactLoading] = useState(false)
  const [impactError, setImpactError] = useState<string | null>(null)
  const [verifyDialogOpen, setVerifyDialogOpen] = useState(false)

  // Fetch inventory
  const {
    data: inventory,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['inventory'],
    queryFn: api.getInventory,
    refetchInterval: 30000, // Refresh every 30s
  })

  // Fetch backup status - dynamic check for connection state
  const { data: backupStatus } = useQuery({
    queryKey: ['backup-status'],
    queryFn: api.getBackupStatus,
    refetchInterval: 10000, // Check connection every 10s
    refetchOnWindowFocus: true, // Immediate check when tab becomes active
    staleTime: 5000, // Consider fresh for 5s to avoid flicker
  })

  // Mutations
  const backupMutation = useMutation({
    mutationFn: api.backupBlob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      toast.success('Blob backed up successfully')
    },
    onError: (error: Error) => {
      toast.error(`Backup failed: ${error.message}`)
    },
  })

  const restoreMutation = useMutation({
    mutationFn: api.restoreBlob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      toast.success('Blob restored successfully')
    },
    onError: (error: Error) => {
      toast.error(`Restore failed: ${error.message}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: ({ sha256, target }: { sha256: string; target: 'local' | 'backup' | 'both' }) =>
      api.deleteBlob(sha256, target),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      setDeleteDialogOpen(false)
      toast.success('Blob deleted successfully')
    },
    onError: (error: Error) => {
      setDeleteDialogOpen(false)
      toast.error(`Delete failed: ${error.message}`)
    },
  })

  // Filter items
  const filteredItems = useMemo(() => {
    if (!inventory?.items) return []

    return inventory.items.filter((item) => {
      // Kind filter
      if (filters.kind !== 'all' && item.kind !== filters.kind) return false

      // Status filter
      if (filters.status !== 'all' && item.status !== filters.status) return false

      // Location filter
      if (filters.location !== 'all' && item.location !== filters.location) return false

      // Search filter
      if (filters.search) {
        const search = filters.search.toLowerCase()
        const matchesName = item.display_name.toLowerCase().includes(search)
        const matchesSha = item.sha256.toLowerCase().includes(search)
        const matchesPack = item.used_by_packs.some((p) => p.toLowerCase().includes(search))
        if (!matchesName && !matchesSha && !matchesPack) return false
      }

      return true
    })
  }, [inventory?.items, filters])

  // Handlers
  const handleBackup = useCallback(async (sha256: string) => {
    await backupMutation.mutateAsync(sha256)
  }, [backupMutation])

  const handleRestore = useCallback(async (sha256: string) => {
    await restoreMutation.mutateAsync(sha256)
  }, [restoreMutation])

  const handleDeleteRequest = useCallback(
    (sha256: string, target: 'local' | 'backup' | 'both') => {
      const item = inventory?.items.find((i) => i.sha256 === sha256) || null
      setDeleteTarget({ item, target })
      setDeleteDialogOpen(true)
    },
    [inventory?.items]
  )

  const handleDeleteConfirm = useCallback(async () => {
    if (deleteTarget.item) {
      await deleteMutation.mutateAsync({
        sha256: deleteTarget.item.sha256,
        target: deleteTarget.target,
      })
    }
  }, [deleteTarget, deleteMutation])

  const handleShowImpacts = useCallback(async (item: InventoryItem) => {
    setImpactAnalysis(null)
    setImpactError(null)
    setImpactsDialogOpen(true)
    setImpactLoading(true)

    try {
      const analysis = await api.getImpactAnalysis(item.sha256)
      setImpactAnalysis(analysis)
    } catch (err) {
      setImpactError(err instanceof Error ? err.message : 'Failed to load impact analysis')
    } finally {
      setImpactLoading(false)
    }
  }, [])

  const handleBulkAction = useCallback(
    async (sha256s: string[], action: BulkAction) => {
      try {
        // Process sequentially for now
        for (const sha256 of sha256s) {
          switch (action) {
            case 'backup':
              await handleBackup(sha256)
              break
            case 'restore':
              await handleRestore(sha256)
              break
            case 'delete_local':
              await api.deleteBlob(sha256, 'local')
              break
            case 'delete_backup':
              await api.deleteBlob(sha256, 'backup')
              break
          }
        }
        queryClient.invalidateQueries({ queryKey: ['inventory'] })
        toast.success(`Bulk ${action} completed for ${sha256s.length} blob(s)`)
      } catch (error) {
        toast.error(`Bulk action failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
      }
    },
    [handleBackup, handleRestore, queryClient]
  )

  const handleCleanup = useCallback(() => {
    setCleanupWizardOpen(true)
  }, [])

  const handleVerify = useCallback(() => {
    setVerifyDialogOpen(true)
  }, [])

  const handleSyncToBackup = useCallback(() => {
    setSyncDirection('to_backup')
    setSyncWizardOpen(true)
  }, [])

  const handleDoctor = useCallback(async () => {
    try {
      const res = await fetch('/api/store/doctor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rebuild_views: true }),
      })
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ['inventory'] })
        toast.success('Doctor completed successfully')
      } else {
        const err = await res.text()
        toast.error(`Doctor failed: ${err}`)
      }
    } catch (err) {
      console.error('Doctor failed:', err)
      toast.error('Doctor failed')
    }
  }, [queryClient])

  // Cleanup wizard handlers
  const handleCleanupScan = useCallback(async () => {
    return api.cleanupOrphans(true)
  }, [])

  const handleCleanupExecute = useCallback(async () => {
    return api.cleanupOrphans(false)
  }, [])

  const handleCleanupComplete = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['inventory'] })
  }, [queryClient])

  // Sync wizard handlers
  const handleSyncPreview = useCallback(async () => {
    return api.syncBackup(syncDirection, true)
  }, [syncDirection])

  const handleSyncExecute = useCallback(async () => {
    return api.syncBackup(syncDirection, false)
  }, [syncDirection])

  const handleSyncComplete = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['inventory'] })
  }, [queryClient])

  // Verify handlers
  const handleVerifyStart = useCallback(async () => {
    return api.verifyIntegrity()
  }, [])

  const handleVerifyComplete = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['inventory'] })
  }, [queryClient])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-3">
            <HardDrive className="w-7 h-7 text-synapse" />
            Inventory
          </h1>
          <p className="text-text-muted mt-1">
            Manage your model storage and backups
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => refetch()}
          leftIcon={<RefreshCw className="w-4 h-4" />}
          isLoading={isLoading}
        >
          Refresh
        </Button>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-4 text-red-400">
          <p className="font-medium">Error loading inventory</p>
          <p className="text-sm mt-1">{(error as Error).message}</p>
        </div>
      )}

      {/* Loading state */}
      {isLoading && !inventory && (
        <BreathingOrb size="lg" text="Loading inventory..." className="py-16" />
      )}

      {/* Content */}
      {inventory && (
        <>
          {/* Stats Dashboard */}
          <InventoryStats
            summary={inventory.summary}
            backupStatus={backupStatus}
            onCleanup={handleCleanup}
            onVerify={handleVerify}
            onSyncToBackup={handleSyncToBackup}
            onDoctor={handleDoctor}
          />

          {/* Filters */}
          <InventoryFilters filters={filters} onChange={setFilters} />

          {/* Blobs Table */}
          <BlobsTable
            items={filteredItems}
            backupEnabled={backupStatus?.enabled || false}
            backupConnected={backupStatus?.connected || false}
            onBackup={handleBackup}
            onRestore={handleRestore}
            onDelete={handleDeleteRequest}
            onShowImpacts={handleShowImpacts}
            onBulkAction={handleBulkAction}
          />
        </>
      )}

      {/* Dialogs */}
      <DeleteConfirmationDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        item={deleteTarget.item}
        target={deleteTarget.target}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />

      <CleanupWizard
        open={cleanupWizardOpen}
        onOpenChange={setCleanupWizardOpen}
        onScan={handleCleanupScan}
        onExecute={handleCleanupExecute}
        onComplete={handleCleanupComplete}
      />

      <BackupSyncWizard
        open={syncWizardOpen}
        onOpenChange={setSyncWizardOpen}
        direction={syncDirection}
        onPreview={handleSyncPreview}
        onExecute={handleSyncExecute}
        onExecuteBlob={syncDirection === 'to_backup' ? api.backupBlob : api.restoreBlob}
        onComplete={handleSyncComplete}
      />

      <ImpactsDialog
        open={impactsDialogOpen}
        onOpenChange={setImpactsDialogOpen}
        analysis={impactAnalysis}
        isLoading={impactLoading}
        error={impactError}
      />

      <VerifyProgressDialog
        open={verifyDialogOpen}
        onOpenChange={setVerifyDialogOpen}
        onStart={handleVerifyStart}
        onComplete={handleVerifyComplete}
      />
    </div>
  )
}
