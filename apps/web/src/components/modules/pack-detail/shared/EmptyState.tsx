/**
 * EmptyState Component
 *
 * Consistent empty state display with icon, title, description,
 * and optional action button.
 */

import {
  Image,
  Package,
  GitBranch,
  FileJson,
  Sliders,
  Plus,
  type LucideIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { clsx } from 'clsx'
import { ANIMATION_PRESETS } from '../constants'

/**
 * Preset empty state configurations
 */
export type EmptyStatePreset =
  | 'gallery'
  | 'dependencies'
  | 'workflows'
  | 'parameters'
  | 'custom'

/**
 * Icon mapping for presets
 */
const presetConfig: Record<EmptyStatePreset, {
  icon: LucideIcon
  title: string
  description: string
  actionLabel?: string
}> = {
  gallery: {
    icon: Image,
    title: 'No Previews',
    description: 'Add preview images or videos to showcase this pack.',
    actionLabel: 'Add Preview',
  },
  dependencies: {
    icon: Package,
    title: 'No Dependencies',
    description: 'Add models, LoRAs, or other assets to this pack.',
    actionLabel: 'Add Dependency',
  },
  workflows: {
    icon: GitBranch,
    title: 'No Workflows',
    description: 'Add ComfyUI workflows to enable generation.',
    actionLabel: 'Add Workflow',
  },
  parameters: {
    icon: Sliders,
    title: 'No Parameters',
    description: 'Set recommended generation parameters for this pack.',
    actionLabel: 'Set Parameters',
  },
  custom: {
    icon: FileJson,
    title: 'No Data',
    description: 'Nothing to display here.',
  },
}

export interface EmptyStateProps {
  /**
   * Preset configuration to use
   */
  preset?: EmptyStatePreset

  /**
   * Custom icon (overrides preset)
   */
  icon?: LucideIcon

  /**
   * Title text (overrides preset)
   */
  title?: string

  /**
   * Description text (overrides preset)
   */
  description?: string

  /**
   * Action button label (overrides preset)
   */
  actionLabel?: string

  /**
   * Callback when action button is clicked
   */
  onAction?: () => void

  /**
   * Whether to show the action button
   */
  showAction?: boolean

  /**
   * Size variant
   */
  size?: 'sm' | 'md' | 'lg'

  /**
   * Whether to animate entrance
   */
  animate?: boolean

  /**
   * Additional className
   */
  className?: string
}

export function EmptyState({
  preset = 'custom',
  icon: customIcon,
  title: customTitle,
  description: customDescription,
  actionLabel: customActionLabel,
  onAction,
  showAction = true,
  size = 'md',
  animate = true,
  className,
}: EmptyStateProps) {
  const config = presetConfig[preset]

  // Resolve values (custom overrides preset)
  const Icon = customIcon ?? config.icon
  const title = customTitle ?? config.title
  const description = customDescription ?? config.description
  const actionLabel = customActionLabel ?? config.actionLabel

  // Size classes
  const sizeClasses = {
    sm: {
      padding: 'py-6 px-4',
      icon: 'w-8 h-8',
      title: 'text-sm',
      description: 'text-xs',
    },
    md: {
      padding: 'py-10 px-6',
      icon: 'w-12 h-12',
      title: 'text-base',
      description: 'text-sm',
    },
    lg: {
      padding: 'py-16 px-8',
      icon: 'w-16 h-16',
      title: 'text-lg',
      description: 'text-base',
    },
  }[size]

  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center text-center',
        sizeClasses.padding,
        animate && ANIMATION_PRESETS.fadeIn,
        className
      )}
    >
      {/* Icon with subtle background */}
      <div className={clsx(
        'mb-4 p-4 rounded-2xl',
        'bg-white/5',
        'transition-colors duration-300'
      )}>
        <Icon className={clsx(
          sizeClasses.icon,
          'text-white/30'
        )} />
      </div>

      {/* Title */}
      <h4 className={clsx(
        sizeClasses.title,
        'font-medium text-white/70 mb-2'
      )}>
        {title}
      </h4>

      {/* Description */}
      <p className={clsx(
        sizeClasses.description,
        'text-white/40 max-w-xs mb-4'
      )}>
        {description}
      </p>

      {/* Action button */}
      {showAction && actionLabel && onAction && (
        <Button
          variant="secondary"
          size={size === 'lg' ? 'md' : 'sm'}
          onClick={onAction}
          className="mt-2"
        >
          <Plus className="w-4 h-4 mr-1.5" />
          {actionLabel}
        </Button>
      )}
    </div>
  )
}

export default EmptyState
