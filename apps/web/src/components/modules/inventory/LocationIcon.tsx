/**
 * LocationIcon - Shows where blob is stored with tooltip
 */
import { clsx } from 'clsx'
import { useTranslation } from 'react-i18next'
import {
  CheckCircle2,
  HardDrive,
  Cloud,
  AlertTriangle,
} from 'lucide-react'
import type { BlobLocation } from './types'

const LOCATION_KEYS: Record<BlobLocation, string> = {
  both: 'both',
  local_only: 'localOnly',
  backup_only: 'backupOnly',
  nowhere: 'nowhere',
}

const LOCATION_STYLE: Record<BlobLocation, {
  icon: typeof CheckCircle2
  color: string
  bgColor: string
}> = {
  both: {
    icon: CheckCircle2,
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
  },
  local_only: {
    icon: HardDrive,
    color: 'text-amber-500',
    bgColor: 'bg-amber-500/10',
  },
  backup_only: {
    icon: Cloud,
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
  },
  nowhere: {
    icon: AlertTriangle,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
  },
}

interface LocationIconProps {
  location: BlobLocation
  showLabel?: boolean
  size?: 'sm' | 'md'
}

export function LocationIcon({ location, showLabel = false, size = 'md' }: LocationIconProps) {
  const { t } = useTranslation()
  const style = LOCATION_STYLE[location]
  const key = LOCATION_KEYS[location]
  const Icon = style.icon

  return (
    <div
      className={clsx(
        'inline-flex items-center gap-1 rounded',
        style.bgColor,
        style.color,
        size === 'sm' ? 'p-0.5' : 'p-1',
      )}
      title={t(`inventory.locationTooltip.${key}`)}
    >
      <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'} />
      {showLabel && (
        <span className={clsx('font-medium', size === 'sm' ? 'text-xs' : 'text-sm')}>
          {t(`inventory.locationLabel.${key}`)}
        </span>
      )}
    </div>
  )
}
