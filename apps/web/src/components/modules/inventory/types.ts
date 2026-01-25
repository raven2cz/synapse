/**
 * Inventory Types - matches backend models
 */

export type AssetKind = 'checkpoint' | 'lora' | 'vae' | 'embedding' | 'controlnet' | 'upscaler' | 'other' | 'unknown'

export type BlobStatus = 'referenced' | 'orphan' | 'missing' | 'backup_only'

export type BlobLocation = 'local_only' | 'backup_only' | 'both' | 'nowhere'

export interface BlobOrigin {
  provider: string
  model_id?: number
  version_id?: number
  file_id?: number
  filename?: string
  repo_id?: string
}

export interface InventoryItem {
  sha256: string
  kind: AssetKind
  display_name: string
  size_bytes: number
  location: BlobLocation
  on_local: boolean
  on_backup: boolean
  status: BlobStatus
  used_by_packs: string[]
  ref_count: number
  origin?: BlobOrigin
  active_in_uis: string[]
  verified?: boolean | null
}

export interface BackupStats {
  enabled: boolean
  connected: boolean
  path?: string
  blobs_local_only: number
  blobs_backup_only: number
  blobs_both: number
  bytes_local_only: number
  bytes_backup_only: number
  bytes_synced: number
  free_space?: number
  total_space?: number
  last_sync?: string
  error?: string
}

export interface InventorySummary {
  blobs_total: number
  blobs_referenced: number
  blobs_orphan: number
  blobs_missing: number
  blobs_backup_only: number
  bytes_total: number
  bytes_referenced: number
  bytes_orphan: number
  bytes_by_kind: Record<string, number>
  disk_total?: number
  disk_free?: number
  backup?: BackupStats
}

export interface InventoryResponse {
  generated_at: string
  summary: InventorySummary
  items: InventoryItem[]
}

export interface CleanupResult {
  dry_run: boolean
  orphans_found: number
  orphans_deleted: number
  bytes_freed: number
  deleted: InventoryItem[]
  errors: string[]
}

export interface ImpactAnalysis {
  sha256: string
  status: BlobStatus
  size_bytes: number
  used_by_packs: string[]
  active_in_uis: string[]
  can_delete_safely: boolean
  warning?: string
}

export interface BackupStatus {
  enabled: boolean
  connected: boolean
  path?: string
  total_blobs?: number
  total_bytes?: number
  total_space?: number
  free_space?: number
  last_sync?: string
  error?: string
}

export interface SyncItem {
  sha256: string
  display_name: string
  kind: AssetKind
  size_bytes: number
}

export interface SyncResult {
  dry_run: boolean
  direction: 'to_backup' | 'from_backup'
  blobs_to_sync: number
  bytes_to_sync: number
  blobs_synced: number
  bytes_synced: number
  items: SyncItem[]
  space_warning?: string
  errors?: string[]
}

export type BulkAction = 'backup' | 'restore' | 'delete_local' | 'delete_backup'

export interface InventoryFilters {
  kind: AssetKind | 'all'
  status: BlobStatus | 'all'
  location: BlobLocation | 'all'
  search: string
}

// Pack-level backup types

export interface PackBlobStatus {
  sha256: string
  display_name: string
  kind: AssetKind
  size_bytes: number
  location: BlobLocation
  on_local: boolean
  on_backup: boolean
}

export interface PackBackupSummary {
  total: number
  local_only: number
  backup_only: number
  both: number
  nowhere: number
  total_bytes: number
}

export interface PackBackupStatusResponse {
  pack: string
  backup_enabled: boolean
  backup_connected: boolean
  blobs: PackBlobStatus[]
  summary: PackBackupSummary
}

export interface PackSyncResultItem {
  sha256: string
  display_name: string
  kind: AssetKind
  size_bytes: number
}

export interface PackPullPushResponse {
  success: boolean
  pack: string
  dry_run: boolean
  direction: 'to_backup' | 'from_backup'
  blobs_to_sync: number
  bytes_to_sync: number
  blobs_synced: number
  bytes_synced: number
  cleanup?: boolean
  items: PackSyncResultItem[]
  errors: string[]
}
