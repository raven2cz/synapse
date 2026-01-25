import { clsx } from 'clsx'
import { HardDrive, Cloud, CheckCircle2, AlertTriangle } from 'lucide-react'
import { formatBytes } from '@/lib/utils/format'
import type { PackBlobStatus, BlobLocation } from '../inventory/types'

interface PackBlobsTableProps {
  blobs: PackBlobStatus[]
  className?: string
}

function LocationBadge({ location }: { location: BlobLocation }) {
  const config = {
    both: {
      icon: CheckCircle2,
      label: 'BOTH',
      color: 'text-green-400 bg-green-500/20',
    },
    local_only: {
      icon: HardDrive,
      label: 'LOCAL',
      color: 'text-amber-400 bg-amber-500/20',
    },
    backup_only: {
      icon: Cloud,
      label: 'BACKUP',
      color: 'text-blue-400 bg-blue-500/20',
    },
    nowhere: {
      icon: AlertTriangle,
      label: 'MISSING',
      color: 'text-red-400 bg-red-500/20',
    },
  }[location]

  const Icon = config.icon

  return (
    <span className={clsx(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
      config.color
    )}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  )
}

function KindBadge({ kind }: { kind: string }) {
  return (
    <span className="px-2 py-0.5 bg-slate-mid/50 text-text-muted rounded text-xs uppercase">
      {kind}
    </span>
  )
}

/**
 * Mini table showing blobs in a pack with their storage status.
 */
export function PackBlobsTable({ blobs, className }: PackBlobsTableProps) {
  if (blobs.length === 0) {
    return (
      <div className={clsx('text-sm text-text-muted italic text-center py-4', className)}>
        No blobs in this pack
      </div>
    )
  }

  return (
    <div className={clsx('overflow-x-auto', className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-text-muted border-b border-slate-mid">
            <th className="pb-2 pr-4 font-medium">Name</th>
            <th className="pb-2 pr-4 font-medium text-right">Size</th>
            <th className="pb-2 pr-4 font-medium">Location</th>
            <th className="pb-2 font-medium">Kind</th>
          </tr>
        </thead>
        <tbody>
          {blobs.map(blob => (
            <tr key={blob.sha256} className="border-b border-slate-mid/50 hover:bg-slate-mid/20">
              <td className="py-2 pr-4">
                <span className="text-text-primary truncate block max-w-xs" title={blob.display_name}>
                  {blob.display_name}
                </span>
              </td>
              <td className="py-2 pr-4 text-right text-text-muted whitespace-nowrap">
                {formatBytes(blob.size_bytes)}
              </td>
              <td className="py-2 pr-4">
                <LocationBadge location={blob.location} />
              </td>
              <td className="py-2">
                <KindBadge kind={blob.kind} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
