/**
 * AssetKindIcon - Icon for different asset types
 */
import { useTranslation } from 'react-i18next'
import {
  Box,
  Layers,
  Cpu,
  Type,
  GitBranch,
  Maximize2,
  FileQuestion,
} from 'lucide-react'
import i18n from '../../../i18n'
import type { AssetKind } from './types'

const KIND_CONFIG: Record<AssetKind, {
  icon: typeof Box
  color: string
  key: string
}> = {
  checkpoint: {
    icon: Box,
    color: 'text-purple-500',
    key: 'checkpoint',
  },
  lora: {
    icon: Layers,
    color: 'text-blue-500',
    key: 'lora',
  },
  vae: {
    icon: Cpu,
    color: 'text-green-500',
    key: 'vae',
  },
  embedding: {
    icon: Type,
    color: 'text-orange-500',
    key: 'embedding',
  },
  controlnet: {
    icon: GitBranch,
    color: 'text-pink-500',
    key: 'controlnet',
  },
  upscaler: {
    icon: Maximize2,
    color: 'text-cyan-500',
    key: 'upscaler',
  },
  other: {
    icon: FileQuestion,
    color: 'text-gray-500',
    key: 'other',
  },
  unknown: {
    icon: FileQuestion,
    color: 'text-gray-500',
    key: 'unknown',
  },
}

interface AssetKindIconProps {
  kind: AssetKind
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export function AssetKindIcon({ kind, size = 'md', showLabel = false }: AssetKindIconProps) {
  const { t } = useTranslation()
  const config = KIND_CONFIG[kind] || KIND_CONFIG.unknown
  const Icon = config.icon
  const label = t(`inventory.assetKind.${config.key}`)

  const sizeClass = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  }[size]

  return (
    <div className="inline-flex items-center gap-1.5" title={label}>
      <Icon className={`${sizeClass} ${config.color}`} />
      {showLabel && (
        <span className="text-xs text-text-secondary">{label}</span>
      )}
    </div>
  )
}

export function getKindLabel(kind: AssetKind): string {
  const config = KIND_CONFIG[kind]
  return config ? i18n.t(`inventory.assetKind.${config.key}`) : i18n.t('inventory.assetKind.unknown')
}
