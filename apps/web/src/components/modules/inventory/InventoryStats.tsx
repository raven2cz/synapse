/**
 * InventoryStats - Dashboard cards showing inventory summary
 */
import { clsx } from 'clsx'
import {
  HardDrive,
  Cloud,
  Zap,
  Trash2,
  Upload,
  Shield,
  AlertTriangle,
  CheckCircle,
  AlertCircle,
  Wrench,
} from 'lucide-react'
import { Card, CardHeader, CardTitle } from '../../ui/Card'
import { ProgressBar } from '../../ui/ProgressBar'
import { Button } from '../../ui/Button'
import type { InventorySummary, BackupStatus } from './types'
import { formatBytes } from './utils'

interface InventoryStatsProps {
  summary?: InventorySummary
  backupStatus?: BackupStatus
  onCleanup: () => void
  onVerify: () => void
  onSyncToBackup: () => void
  onDoctor: () => void
}

export function InventoryStats({
  summary,
  backupStatus,
  onCleanup,
  onVerify,
  onSyncToBackup,
  onDoctor,
}: InventoryStatsProps) {
  const diskUsagePercent = summary?.disk_total
    ? ((summary.bytes_total || 0) / summary.disk_total) * 100
    : 0

  const localOnlyCount = summary?.backup?.blobs_local_only || 0
  const backupOnlyCount = summary?.blobs_backup_only || 0

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* LOCAL DISK Card */}
      <Card padding="md">
        <CardHeader className="mb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-text-secondary">
            <HardDrive className="w-4 h-4" />
            Local Disk
          </CardTitle>
        </CardHeader>
        <div className="space-y-3">
          <div className="text-2xl font-bold text-text-primary">
            {formatBytes(summary?.bytes_total || 0)}
          </div>
          <ProgressBar
            progress={diskUsagePercent}
            showLabel={false}
            size="sm"
            variant={diskUsagePercent > 90 ? 'warning' : 'default'}
          />
          <div className="flex justify-between text-xs text-text-muted">
            <span>Free: {formatBytes(summary?.disk_free || 0)}</span>
            <span>{summary?.blobs_total || 0} blobs</span>
          </div>

          {localOnlyCount > 0 && (
            <div className="flex items-center gap-1 text-xs text-amber-500">
              <AlertTriangle className="w-3 h-3" />
              {localOnlyCount} not backed up
            </div>
          )}
        </div>
      </Card>

      {/* BACKUP STORAGE Card */}
      <Card
        padding="md"
        className={clsx(
          !backupStatus?.connected && backupStatus?.enabled && 'border-amber-500/50'
        )}
      >
        <CardHeader className="mb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-text-secondary">
            <Cloud className="w-4 h-4" />
            Backup Storage
          </CardTitle>
        </CardHeader>
        <div className="space-y-3">
          {!backupStatus?.enabled ? (
            <div className="text-text-muted text-sm">
              <div>Not configured</div>
              <Button variant="ghost" size="sm" className="p-0 h-auto mt-1 text-synapse">
                Configure in Settings →
              </Button>
            </div>
          ) : !backupStatus?.connected ? (
            <div className="text-amber-500">
              <div className="flex items-center gap-1">
                <AlertCircle className="w-4 h-4" />
                Disconnected
              </div>
              <div className="text-xs mt-1 text-text-muted truncate">
                {backupStatus.path}
              </div>
            </div>
          ) : (
            <>
              <div className="text-2xl font-bold text-text-primary">
                {formatBytes(summary?.backup?.bytes_synced || 0)}
              </div>
              {backupStatus.total_space && (
                <ProgressBar
                  progress={
                    ((backupStatus.total_bytes || 0) /
                      backupStatus.total_space) * 100
                  }
                  showLabel={false}
                  size="sm"
                />
              )}
              <div className="flex justify-between text-xs text-text-muted">
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3 h-3 text-green-500" />
                  Connected
                </span>
                <span>{backupOnlyCount} backup-only</span>
              </div>
            </>
          )}
        </div>
      </Card>

      {/* STATUS Overview Card */}
      <Card padding="md">
        <CardHeader className="mb-2">
          <CardTitle className="text-sm text-text-secondary">
            Status Overview
          </CardTitle>
        </CardHeader>
        <div className="space-y-2">
          <StatusRow
            color="bg-green-500"
            label="Referenced"
            count={summary?.blobs_referenced || 0}
          />
          <StatusRow
            color="bg-gray-500"
            label="Orphan"
            count={summary?.blobs_orphan || 0}
          />
          <StatusRow
            color="bg-blue-500"
            label="Backup-only"
            count={backupOnlyCount}
          />
          {(summary?.blobs_missing || 0) > 0 && (
            <StatusRow
              color="bg-red-500"
              label="Missing"
              count={summary?.blobs_missing || 0}
              highlight
            />
          )}
        </div>
      </Card>

      {/* QUICK ACTIONS Card */}
      <Card padding="md">
        <CardHeader className="mb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-text-secondary">
            <Zap className="w-4 h-4" />
            Quick Actions
          </CardTitle>
        </CardHeader>
        <div className="space-y-2">
          {(summary?.blobs_orphan || 0) > 0 && (
            <Button
              variant="secondary"
              size="sm"
              className="w-full justify-start"
              onClick={onCleanup}
              leftIcon={<Trash2 className="w-4 h-4" />}
            >
              Cleanup {summary?.blobs_orphan} Orphans
            </Button>
          )}

          {backupStatus?.connected && localOnlyCount > 0 && (
            <Button
              variant="secondary"
              size="sm"
              className="w-full justify-start"
              onClick={onSyncToBackup}
              leftIcon={<Upload className="w-4 h-4" />}
            >
              Backup {localOnlyCount} Local-only
            </Button>
          )}

          <Button
            variant="secondary"
            size="sm"
            className="w-full justify-start"
            onClick={onVerify}
            leftIcon={<Shield className="w-4 h-4" />}
          >
            Verify Integrity
          </Button>

          <Button
            variant="secondary"
            size="sm"
            className="w-full justify-start"
            onClick={onDoctor}
            leftIcon={<Wrench className="w-4 h-4" />}
          >
            Run Doctor
          </Button>
        </div>
      </Card>
    </div>
  )
}

function StatusRow({
  color,
  label,
  count,
  highlight = false,
}: {
  color: string
  label: string
  count: number
  highlight?: boolean
}) {
  return (
    <div className={clsx(
      'flex items-center justify-between',
      highlight && 'text-red-500'
    )}>
      <div className="flex items-center gap-2">
        <div className={clsx('w-2 h-2 rounded-full', color)} />
        <span className="text-sm">{label}</span>
      </div>
      <span className="font-mono text-sm">{count}</span>
    </div>
  )
}
