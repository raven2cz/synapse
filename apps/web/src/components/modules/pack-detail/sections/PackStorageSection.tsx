/**
 * PackStorageSection
 *
 * Displays backup storage status and actions for the pack.
 *
 * FUNKCE ZACHOVÁNY:
 * - PackStorageStatus (sync status indicator)
 * - PackStorageActions (Pull/Push/Push&Free buttons)
 * - PackBlobsTable (individual blob status)
 * - Loading skeletons
 * - Error state display
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium card design
 * - Enhanced status indicator styling
 * - Staggered animation
 */

import { useTranslation } from 'react-i18next'
import { DownloadCloud } from 'lucide-react'
import { clsx } from 'clsx'
import { Card } from '@/components/ui/Card'
import { PackStorageStatus } from '../../packs/PackStorageStatus'
import { PackStorageActions } from '../../packs/PackStorageActions'
import { PackBlobsTable } from '../../packs/PackBlobsTable'
import type { PackBackupStatusResponse } from '../types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface PackStorageSectionProps {
  /**
   * Backup status data from API
   */
  backupStatus?: PackBackupStatusResponse

  /**
   * Whether backup status is loading
   */
  isLoading?: boolean

  /**
   * Handlers for backup operations
   */
  onPull: () => void
  onPush: () => void
  onPushAndFree: () => void

  /**
   * Loading states for operations
   */
  isPulling?: boolean
  isPushing?: boolean

  /**
   * Animation delay
   */
  animationDelay?: number
}

// =============================================================================
// Sub-components
// =============================================================================

function LoadingSkeleton() {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <DownloadCloud className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-semibold text-text-primary">{t('pack.storage.backupStorage')}</h3>
        </div>
        <div className="h-5 w-24 bg-slate-mid/50 rounded animate-pulse" />
      </div>
      <div className="flex gap-2">
        <div className="h-8 w-16 bg-slate-mid/50 rounded animate-pulse" />
        <div className="h-8 w-16 bg-slate-mid/50 rounded animate-pulse" />
        <div className="h-8 w-24 bg-slate-mid/50 rounded animate-pulse" />
      </div>
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function PackStorageSection({
  backupStatus,
  isLoading = false,
  onPull,
  onPush,
  onPushAndFree,
  isPulling = false,
  isPushing = false,
  animationDelay = 0,
}: PackStorageSectionProps) {
  const { t } = useTranslation()

  return (
    <div
      className={ANIMATION_PRESETS.sectionEnter}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
      <Card className="p-4">
        {/* Header with Status and Actions */}
        <div className="flex items-center justify-between mb-3">
          {isLoading ? (
            <LoadingSkeleton />
          ) : backupStatus ? (
            <>
              {/* Left: Title + Status */}
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <DownloadCloud className="w-4 h-4 text-blue-400" />
                  <h3 className="text-sm font-semibold text-text-primary">{t('pack.storage.backupStorage')}</h3>
                </div>
                <PackStorageStatus
                  summary={backupStatus.summary}
                  backupEnabled={backupStatus.backup_enabled}
                  backupConnected={backupStatus.backup_connected}
                />
              </div>

              {/* Right: Actions */}
              <PackStorageActions
                summary={backupStatus.summary}
                backupEnabled={backupStatus.backup_enabled}
                backupConnected={backupStatus.backup_connected}
                onPull={onPull}
                onPush={onPush}
                onPushAndFree={onPushAndFree}
                isPulling={isPulling}
                isPushing={isPushing}
              />
            </>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <DownloadCloud className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-semibold text-text-primary">{t('pack.storage.backupStorage')}</h3>
              </div>
              <span className="text-sm text-red-400">{t('pack.storage.failedToLoad')}</span>
            </>
          )}
        </div>

        {/* Blob table - show only if there are blobs */}
        {backupStatus && backupStatus.blobs.length > 0 && (
          <PackBlobsTable
            blobs={backupStatus.blobs}
            className={clsx(
              "mt-3 pt-3 border-t border-slate-mid/50",
              "transition-all duration-200"
            )}
          />
        )}

        {/* Empty state when no blobs */}
        {backupStatus && backupStatus.blobs.length === 0 && (
          <div className="text-center py-4 text-text-muted text-sm">
            {t('pack.storage.noBlobs')}
          </div>
        )}
      </Card>
    </div>
  )
}

export default PackStorageSection
