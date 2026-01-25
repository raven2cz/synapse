import { clsx } from 'clsx'
import { HardDrive, Cloud, CloudOff, CheckCircle2, AlertTriangle } from 'lucide-react'
import type { PackBackupSummary } from '../inventory/types'

interface PackStorageStatusProps {
  summary: PackBackupSummary
  backupEnabled: boolean
  backupConnected: boolean
  className?: string
}

/**
 * Mini status indicator for pack storage/backup status.
 * Shows sync status at a glance.
 */
export function PackStorageStatus({
  summary,
  backupEnabled,
  backupConnected,
  className,
}: PackStorageStatusProps) {
  // Determine overall status
  const allSynced = summary.total > 0 && summary.both === summary.total
  const allLocalOnly = summary.total > 0 && summary.local_only === summary.total
  const allBackupOnly = summary.total > 0 && summary.backup_only === summary.total
  const hasMissing = summary.nowhere > 0
  const isMixed = !allSynced && !allLocalOnly && !allBackupOnly && summary.total > 0

  // Status text and styling
  let statusText: string
  let statusColor: string
  let StatusIcon: React.ElementType

  if (!backupEnabled) {
    statusText = 'Backup disabled'
    statusColor = 'text-text-muted'
    StatusIcon = CloudOff
  } else if (!backupConnected) {
    statusText = 'Backup offline'
    statusColor = 'text-amber-400'
    StatusIcon = CloudOff
  } else if (hasMissing) {
    statusText = `${summary.nowhere} missing`
    statusColor = 'text-red-400'
    StatusIcon = AlertTriangle
  } else if (allSynced) {
    statusText = `${summary.total}/${summary.total} synced`
    statusColor = 'text-green-400'
    StatusIcon = CheckCircle2
  } else if (allLocalOnly) {
    statusText = `${summary.local_only} local only`
    statusColor = 'text-amber-400'
    StatusIcon = HardDrive
  } else if (allBackupOnly) {
    statusText = `${summary.backup_only} backup only`
    statusColor = 'text-blue-400'
    StatusIcon = Cloud
  } else if (isMixed) {
    statusText = `${summary.both}/${summary.total} synced`
    statusColor = 'text-amber-400'
    StatusIcon = Cloud
  } else {
    statusText = 'No blobs'
    statusColor = 'text-text-muted'
    StatusIcon = HardDrive
  }

  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <StatusIcon className={clsx('w-4 h-4', statusColor)} />
      <span className={clsx('text-sm font-medium', statusColor)}>
        {statusText}
      </span>
    </div>
  )
}
