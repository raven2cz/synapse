/**
 * PackDependenciesSection
 *
 * Displays pack dependencies with download tracking and management.
 *
 * ⚠️ KRITICKÉ FUNKCE - VŠECHNY ZACHOVÁNY:
 *
 * STATUS ICONS:
 * - downloading (synapse pulse)
 * - installed (green check)
 * - backup-only (sky cloud)
 * - unresolved (amber warning)
 * - pending/ready (blue package)
 *
 * ASSET INFO (VŠECHNA DATA):
 * - name, version_name
 * - asset_type, source, base_model_hint, size
 * - description
 * - source_info (model_name, model_id, creator, repo_id)
 * - filename, sha256, url, local_path
 *
 * AKCE:
 * - Download All (pending assets)
 * - Restore from Backup
 * - Download single asset
 * - Select Model (base model resolver)
 * - Resolve (unresolved deps)
 * - Change base model
 * - Re-download
 * - Delete resource
 *
 * DOWNLOAD PROGRESS:
 * - Progress bar
 * - downloaded_bytes / total_bytes
 * - speed_bps
 * - ETA
 */

import { Loader2, Download, Check, Cloud, AlertTriangle, Package,
  DownloadCloud, ArrowLeftRight, RotateCcw, Trash2, HardDrive,
  Gauge, Timer, FolderOpen, Globe } from 'lucide-react'
import { clsx } from 'clsx'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/ProgressBar'
import type { AssetInfo, DownloadProgress } from '../types'
import type { PackBackupStatusResponse } from '../types'
import { ANIMATION_PRESETS } from '../constants'
import { formatBytes, formatSpeed, formatEta, formatSize } from '../utils'

// =============================================================================
// Types
// =============================================================================

export interface PackDependenciesSectionProps {
  /**
   * Assets/dependencies to display
   */
  assets: AssetInfo[]

  /**
   * Backup status for blob lookup
   */
  backupStatus?: PackBackupStatusResponse

  /**
   * Set of assets currently being downloaded (for immediate UI feedback)
   */
  downloadingAssets: Set<string>

  /**
   * Get download progress for specific asset
   */
  getAssetDownload: (assetName: string) => DownloadProgress | undefined

  /**
   * Handlers for various actions
   */
  onDownloadAll: () => void
  onDownloadAsset: (asset: AssetInfo) => void
  onRestoreFromBackup: (asset: AssetInfo) => Promise<void>
  onDeleteResource: (assetName: string) => void
  onOpenBaseModelResolver: () => void
  onResolvePack: () => void

  /**
   * Loading states
   */
  isDownloadAllPending?: boolean
  isResolvePending?: boolean
  isDeletePending?: boolean

  /**
   * Animation delay
   */
  animationDelay?: number
}

// =============================================================================
// Helper Components
// =============================================================================

interface StatusIconProps {
  isDownloading: boolean
  isInstalled: boolean
  isBackupOnly: boolean
  needsResolve: boolean
}

function StatusIcon({ isDownloading, isInstalled, isBackupOnly, needsResolve }: StatusIconProps) {
  if (isDownloading) {
    return (
      <div className="w-8 h-8 rounded-full bg-synapse/30 flex items-center justify-center flex-shrink-0">
        <Download className="w-5 h-5 text-synapse animate-pulse" />
      </div>
    )
  }
  if (isInstalled) {
    return (
      <div className="w-8 h-8 rounded-full bg-green-500/30 flex items-center justify-center flex-shrink-0">
        <Check className="w-5 h-5 text-green-400" />
      </div>
    )
  }
  if (isBackupOnly) {
    return (
      <div className="w-8 h-8 rounded-full bg-sky-500/30 flex items-center justify-center flex-shrink-0" title="Available on backup storage">
        <Cloud className="w-5 h-5 text-sky-400" />
      </div>
    )
  }
  if (needsResolve) {
    return (
      <div className="w-8 h-8 rounded-full bg-amber-500/30 flex items-center justify-center flex-shrink-0">
        <AlertTriangle className="w-5 h-5 text-amber-400" />
      </div>
    )
  }
  return (
    <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0">
      <Package className="w-5 h-5 text-blue-400" />
    </div>
  )
}

interface DownloadProgressDisplayProps {
  download: DownloadProgress
}

function DownloadProgressDisplay({ download }: DownloadProgressDisplayProps) {
  return (
    <div className="mt-3 space-y-2">
      <ProgressBar progress={download.progress} showLabel={true} />
      <div className="flex items-center justify-between text-xs text-text-muted">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <HardDrive className="w-3 h-3" />
            {formatBytes(download.downloaded_bytes)} / {formatBytes(download.total_bytes)}
          </span>
          <span className="flex items-center gap-1">
            <Gauge className="w-3 h-3" />
            {formatSpeed(download.speed_bps)}
          </span>
        </div>
        <span className="flex items-center gap-1">
          <Timer className="w-3 h-3" />
          ETA: {formatEta(download.eta_seconds)}
        </span>
      </div>
    </div>
  )
}

interface AssetDetailsProps {
  asset: AssetInfo
  isInstalled: boolean
  isBackupOnly: boolean
  isDownloading: boolean
}

function AssetDetails({ asset, isInstalled, isBackupOnly, isDownloading }: AssetDetailsProps) {
  return (
    <div className="mt-3 pt-3 border-t border-white/10 text-xs space-y-1.5">
      {/* File name */}
      {asset.filename && (
        <div className="flex items-center gap-2 text-text-muted">
          <span className="font-medium text-text-secondary w-16">File:</span>
          <code className="bg-slate-mid/50 px-2 py-0.5 rounded flex-1 truncate">{asset.filename}</code>
        </div>
      )}

      {/* Version */}
      {asset.version_name && (
        <div className="flex items-center gap-2 text-text-muted">
          <span className="font-medium text-text-secondary w-16">Version:</span>
          <span className="text-synapse">{asset.version_name}</span>
        </div>
      )}

      {/* Source info */}
      {asset.source_info && (
        <>
          {asset.source_info.model_name && (
            <div className="flex items-center gap-2 text-text-muted">
              <span className="font-medium text-text-secondary w-16">Model:</span>
              <span>{asset.source_info.model_name}</span>
              {asset.source_info.model_id && (
                <span className="text-text-muted/60">(#{asset.source_info.model_id})</span>
              )}
            </div>
          )}
          {asset.source_info.creator && (
            <div className="flex items-center gap-2 text-text-muted">
              <span className="font-medium text-text-secondary w-16">Creator:</span>
              <span className="text-blue-400">{asset.source_info.creator}</span>
            </div>
          )}
          {asset.source_info.repo_id && (
            <div className="flex items-center gap-2 text-text-muted">
              <span className="font-medium text-text-secondary w-16">Repo:</span>
              <span>{asset.source_info.repo_id}</span>
            </div>
          )}
        </>
      )}

      {/* Size */}
      {asset.size && (
        <div className="flex items-center gap-2 text-text-muted">
          <span className="font-medium text-text-secondary w-16">Size:</span>
          <span>{formatBytes(asset.size)}</span>
        </div>
      )}

      {/* SHA256 */}
      {asset.sha256 && (
        <div className="flex items-center gap-2 text-text-muted">
          <span className="font-medium text-text-secondary w-16">SHA256:</span>
          <code className="truncate flex-1 text-green-400/70" title={asset.sha256}>
            {asset.sha256.substring(0, 16)}...
          </code>
        </div>
      )}

      {/* Download URL */}
      {asset.url && !isInstalled && (
        <div className="flex items-center gap-2 text-text-muted">
          <span className="font-medium text-text-secondary w-16">URL:</span>
          <a
            href={asset.url}
            target="_blank"
            rel="noopener noreferrer"
            className="truncate flex-1 text-blue-400 hover:underline"
            title={asset.url}
          >
            {asset.url.length > 60 ? asset.url.substring(0, 60) + '...' : asset.url}
          </a>
        </div>
      )}

      {/* Local path */}
      {asset.local_path && (
        <div className="flex items-center gap-2 text-text-muted">
          <FolderOpen className="w-3 h-3 text-text-secondary" />
          <span className="font-medium text-text-secondary">Path:</span>
          <code className="truncate flex-1" title={asset.local_path}>{asset.local_path}</code>
        </div>
      )}

      {/* Status messages */}
      {!asset.local_path && isBackupOnly && (
        <div className="flex items-center gap-2 text-sky-400">
          <Cloud className="w-3 h-3" />
          <span>Available on backup - click cloud to restore</span>
        </div>
      )}
      {!asset.local_path && asset.url && !isDownloading && !isBackupOnly && (
        <div className="flex items-center gap-2 text-text-muted">
          <Globe className="w-3 h-3" />
          <span className="truncate flex-1" title={asset.url}>Ready to download</span>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function PackDependenciesSection({
  assets,
  backupStatus,
  downloadingAssets,
  getAssetDownload,
  onDownloadAll,
  onDownloadAsset,
  onRestoreFromBackup,
  onDeleteResource,
  onOpenBaseModelResolver,
  onResolvePack,
  isDownloadAllPending = false,
  isResolvePending = false,
  isDeletePending = false,
  animationDelay = 0,
}: PackDependenciesSectionProps) {

  // Check if any asset can be downloaded
  const hasDownloadableAssets = assets?.some(a => a.url && !a.installed && !a.local_path)

  return (
    <div
      className={ANIMATION_PRESETS.sectionEnter}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
    <Card className="p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
          <Package className="w-4 h-4 text-blue-400" />
          Dependencies
          <span className="text-text-muted font-normal">({assets?.length || 0})</span>
        </h3>

        <div className="flex items-center gap-2">
          {/* Download All button */}
          {hasDownloadableAssets && (
            <Button
              size="sm"
              onClick={onDownloadAll}
              disabled={isDownloadAllPending}
              className="transition-all duration-200 hover:scale-105"
            >
              {isDownloadAllPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <DownloadCloud className="w-4 h-4" />
              )}
              Download All
            </Button>
          )}
        </div>
      </div>

      {/* Assets List */}
      {assets?.length > 0 ? (
        <div className="space-y-3">
          {assets.map((asset, idx) => {
            // Determine asset state
            const isBaseModel = asset.asset_type === 'base_model' ||
              asset.asset_type === 'checkpoint' ||
              asset.name.toLowerCase().includes('base model') ||
              asset.name.toLowerCase().includes('base_checkpoint')

            const assetDownload = getAssetDownload(asset.name)
            const isDownloading = assetDownload?.status === 'downloading' || downloadingAssets.has(asset.name)
            const isInstalled = asset.installed || !!asset.local_path
            const canDownload = !!asset.url && !isInstalled && !isDownloading
            const needsResolve = asset.status === 'unresolved'
            const readyToDownload = !!asset.url && !isInstalled

            // Check backup status
            const backupBlob = asset.sha256
              ? backupStatus?.blobs?.find(b => b.sha256 === asset.sha256)
              : undefined
            const isOnBackup = backupBlob && typeof backupBlob === 'object' && backupBlob.on_backup
            const isBackupOnly = isOnBackup && !isInstalled

            return (
              <div
                key={idx}
                className={clsx(
                  "p-4 rounded-xl border transition-all duration-200",
                  // Status-based styling
                  isDownloading
                    ? "bg-synapse/10 border-synapse/50"
                    : isInstalled
                      ? "bg-green-900/30 border-green-500/50"
                      : isBackupOnly
                        ? "bg-sky-900/30 border-sky-500/50"
                        : needsResolve
                          ? "bg-amber-900/30 border-amber-500/50"
                          : readyToDownload
                            ? "bg-blue-900/20 border-blue-500/30"
                            : "bg-slate-dark border-slate-mid",
                  // Hover effect
                  "hover:shadow-lg"
                )}
              >
                {/* Main row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    {/* Status icon */}
                    <StatusIcon
                      isDownloading={isDownloading}
                      isInstalled={isInstalled}
                      isBackupOnly={!!isBackupOnly}
                      needsResolve={needsResolve}
                    />

                    {/* Asset info */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-text-primary font-medium truncate">{asset.name}</p>
                        {asset.version_name && (
                          <span className="px-1.5 py-0.5 bg-slate-mid/50 text-text-muted rounded text-xs">
                            v{asset.version_name}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-text-muted">
                        <span className="uppercase font-medium">{asset.asset_type}</span>
                        <span>•</span>
                        <span>{asset.source}</span>
                        {asset.base_model_hint && (
                          <>
                            <span>•</span>
                            <span className="text-amber-400 font-medium">{asset.base_model_hint}</span>
                          </>
                        )}
                        {asset.size && (
                          <>
                            <span>•</span>
                            <span>{formatSize(asset.size)}</span>
                          </>
                        )}
                      </div>
                      {/* Description */}
                      {asset.description && (
                        <p className="text-xs text-amber-400/80 mt-1 italic">
                          {asset.description}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {/* Restore from Backup */}
                    {isBackupOnly && asset.sha256 && (
                      <button
                        onClick={() => onRestoreFromBackup(asset)}
                        className="p-2 bg-sky-500 text-white rounded-lg hover:bg-sky-400 transition-all duration-200 hover:scale-105"
                        title="Restore from Backup Storage"
                      >
                        <Cloud className="w-4 h-4" />
                      </button>
                    )}

                    {/* Download button */}
                    {canDownload && !isDownloading && !isBackupOnly && (
                      <button
                        onClick={() => onDownloadAsset(asset)}
                        className="p-2 bg-synapse text-white rounded-lg hover:bg-synapse/80 transition-all duration-200 hover:scale-105"
                        title="Download"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    )}

                    {/* Downloading spinner */}
                    {isDownloading && !assetDownload && (
                      <Loader2 className="w-5 h-5 text-synapse animate-spin" />
                    )}

                    {/* Select Model (base model) */}
                    {isBaseModel && !isInstalled && !canDownload && (
                      <button
                        onClick={onOpenBaseModelResolver}
                        className="px-3 py-1.5 bg-amber-500/30 text-amber-300 rounded-lg text-sm font-medium hover:bg-amber-500/40 transition-all duration-200"
                      >
                        Select Model
                      </button>
                    )}

                    {/* Resolve button */}
                    {!isBaseModel && needsResolve && !isResolvePending && (
                      <button
                        onClick={onResolvePack}
                        className="px-3 py-1.5 bg-amber-500/30 text-amber-300 rounded-lg text-sm font-medium hover:bg-amber-500/40 transition-all duration-200"
                        title="Re-resolve dependency to get download URL"
                      >
                        Resolve
                      </button>
                    )}
                    {!isBaseModel && needsResolve && isResolvePending && (
                      <Loader2 className="w-5 h-5 text-amber-400 animate-spin" />
                    )}

                    {/* Change base model */}
                    {isBaseModel && isInstalled && !needsResolve && (
                      <button
                        onClick={onOpenBaseModelResolver}
                        className="p-2 bg-slate-mid text-text-muted rounded-lg hover:text-amber-400 hover:bg-slate-mid/80 transition-all duration-200"
                        title="Change base model"
                      >
                        <ArrowLeftRight className="w-4 h-4" />
                      </button>
                    )}

                    {/* Re-download */}
                    {isInstalled && (
                      <button
                        onClick={() => {
                          if (confirm(`Re-download ${asset.filename || asset.name}? This will replace the existing file.`)) {
                            onDownloadAsset(asset)
                          }
                        }}
                        className="p-2 bg-slate-mid text-text-muted rounded-lg hover:text-synapse hover:bg-slate-mid/80 transition-all duration-200"
                        title="Re-download"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    )}

                    {/* Delete */}
                    {isInstalled && (
                      <button
                        onClick={() => {
                          const deleteChoice = confirm(
                            `Delete downloaded file for "${asset.filename || asset.name}"?\n\n` +
                            `This will remove the file from blob store.\n\n` +
                            `Press OK to delete file only.\n` +
                            `The dependency will remain in pack.json for re-download.`
                          )
                          if (deleteChoice) {
                            onDeleteResource(asset.name)
                          }
                        }}
                        disabled={isDeletePending}
                        className="p-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-all duration-200"
                        title="Delete downloaded file"
                      >
                        {isDeletePending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {/* Download progress */}
                {assetDownload && assetDownload.status === 'downloading' && (
                  <DownloadProgressDisplay download={assetDownload} />
                )}

                {/* Asset details */}
                <AssetDetails
                  asset={asset}
                  isInstalled={isInstalled}
                  isBackupOnly={!!isBackupOnly}
                  isDownloading={isDownloading}
                />
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-center py-8">
          <Package className="w-12 h-12 mx-auto mb-3 text-text-muted/50" />
          <p className="text-text-muted text-sm">No dependencies</p>
        </div>
      )}
    </Card>
    </div>
  )
}

export default PackDependenciesSection
