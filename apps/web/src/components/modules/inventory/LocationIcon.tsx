/**
 * LocationIcon - Shows where blob is stored with tooltip
 */
import { clsx } from 'clsx'
import {
  CheckCircle2,
  HardDrive,
  Cloud,
  AlertTriangle,
} from 'lucide-react'
import type { BlobLocation } from './types'

const LOCATION_CONFIG: Record<BlobLocation, {
  icon: typeof CheckCircle2
  color: string
  bgColor: string
  tooltip: string
  label: string
}> = {
  both: {
    icon: CheckCircle2,
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
    tooltip: 'Backed up (safe)',
    label: 'Both',
  },
  local_only: {
    icon: HardDrive,
    color: 'text-amber-500',
    bgColor: 'bg-amber-500/10',
    tooltip: 'Local only - NOT BACKED UP!',
    label: 'Local',
  },
  backup_only: {
    icon: Cloud,
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
    tooltip: 'Backup only - can restore',
    label: 'Backup',
  },
  nowhere: {
    icon: AlertTriangle,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
    tooltip: 'Missing everywhere!',
    label: 'Missing',
  },
}

interface LocationIconProps {
  location: BlobLocation
  showLabel?: boolean
  size?: 'sm' | 'md'
}

export function LocationIcon({ location, showLabel = false, size = 'md' }: LocationIconProps) {
  const config = LOCATION_CONFIG[location]
  const Icon = config.icon

  return (
    <div
      className={clsx(
        'inline-flex items-center gap-1 rounded',
        config.bgColor,
        config.color,
        size === 'sm' ? 'p-0.5' : 'p-1',
      )}
      title={config.tooltip}
    >
      <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'} />
      {showLabel && (
        <span className={clsx('font-medium', size === 'sm' ? 'text-xs' : 'text-sm')}>
          {config.label}
        </span>
      )}
    </div>
  )
}
