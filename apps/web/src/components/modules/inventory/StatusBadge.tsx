/**
 * StatusBadge - Shows blob status with color coding
 */
import { clsx } from 'clsx'
import { useTranslation } from 'react-i18next'
import {
  CheckCircle,
  CircleDashed,
  AlertCircle,
  Cloud,
} from 'lucide-react'
import type { BlobStatus } from './types'

const STATUS_CONFIG: Record<BlobStatus, {
  icon: typeof CheckCircle
  labelKey: string
  className: string
}> = {
  referenced: {
    icon: CheckCircle,
    labelKey: 'inventory.statusBadge.referenced',
    className: 'bg-green-500/10 text-green-600 border-green-500/20',
  },
  orphan: {
    icon: CircleDashed,
    labelKey: 'inventory.statusBadge.orphan',
    className: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
  },
  missing: {
    icon: AlertCircle,
    labelKey: 'inventory.statusBadge.missing',
    className: 'bg-red-500/10 text-red-500 border-red-500/20',
  },
  backup_only: {
    icon: Cloud,
    labelKey: 'inventory.statusBadge.backupOnly',
    className: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  },
}

interface StatusBadgeProps {
  status: BlobStatus
  size?: 'sm' | 'md'
}

export function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const { t } = useTranslation()
  const config = STATUS_CONFIG[status]
  const Icon = config.icon

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded border font-medium',
        config.className,
        size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-xs',
      )}
    >
      <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />
      {t(config.labelKey)}
    </span>
  )
}
