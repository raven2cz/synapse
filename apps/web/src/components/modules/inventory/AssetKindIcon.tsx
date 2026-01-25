/**
 * AssetKindIcon - Icon for different asset types
 */
import {
  Box,
  Layers,
  Cpu,
  Type,
  GitBranch,
  Maximize2,
  FileQuestion,
} from 'lucide-react'
import type { AssetKind } from './types'

const KIND_CONFIG: Record<AssetKind, {
  icon: typeof Box
  color: string
  label: string
}> = {
  checkpoint: {
    icon: Box,
    color: 'text-purple-500',
    label: 'Checkpoint',
  },
  lora: {
    icon: Layers,
    color: 'text-blue-500',
    label: 'LoRA',
  },
  vae: {
    icon: Cpu,
    color: 'text-green-500',
    label: 'VAE',
  },
  embedding: {
    icon: Type,
    color: 'text-orange-500',
    label: 'Embedding',
  },
  controlnet: {
    icon: GitBranch,
    color: 'text-pink-500',
    label: 'ControlNet',
  },
  upscaler: {
    icon: Maximize2,
    color: 'text-cyan-500',
    label: 'Upscaler',
  },
  other: {
    icon: FileQuestion,
    color: 'text-gray-500',
    label: 'Other',
  },
  unknown: {
    icon: FileQuestion,
    color: 'text-gray-500',
    label: 'Unknown',
  },
}

interface AssetKindIconProps {
  kind: AssetKind
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export function AssetKindIcon({ kind, size = 'md', showLabel = false }: AssetKindIconProps) {
  const config = KIND_CONFIG[kind] || KIND_CONFIG.unknown
  const Icon = config.icon

  const sizeClass = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  }[size]

  return (
    <div className="inline-flex items-center gap-1.5" title={config.label}>
      <Icon className={`${sizeClass} ${config.color}`} />
      {showLabel && (
        <span className="text-xs text-text-secondary">{config.label}</span>
      )}
    </div>
  )
}

export function getKindLabel(kind: AssetKind): string {
  return KIND_CONFIG[kind]?.label || 'Unknown'
}
