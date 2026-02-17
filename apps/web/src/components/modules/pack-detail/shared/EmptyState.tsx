/**
 * EmptyState Component
 *
 * Consistent empty state display with icon, title, description,
 * and optional action button.
 */

import { useTranslation } from 'react-i18next'
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
  titleKey: string
  descriptionKey: string
  actionKey?: string
}> = {
  gallery: {
    icon: Image,
    titleKey: 'pack.emptyState.gallery.title',
    descriptionKey: 'pack.emptyState.gallery.description',
    actionKey: 'pack.emptyState.gallery.action',
  },
  dependencies: {
    icon: Package,
    titleKey: 'pack.emptyState.dependencies.title',
    descriptionKey: 'pack.emptyState.dependencies.description',
    actionKey: 'pack.emptyState.dependencies.action',
  },
  workflows: {
    icon: GitBranch,
    titleKey: 'pack.emptyState.workflows.title',
    descriptionKey: 'pack.emptyState.workflows.description',
    actionKey: 'pack.emptyState.workflows.action',
  },
  parameters: {
    icon: Sliders,
    titleKey: 'pack.emptyState.parameters.title',
    descriptionKey: 'pack.emptyState.parameters.description',
    actionKey: 'pack.emptyState.parameters.action',
  },
  custom: {
    icon: FileJson,
    titleKey: 'pack.emptyState.custom.title',
    descriptionKey: 'pack.emptyState.custom.description',
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
  const { t } = useTranslation()
  const config = presetConfig[preset]

  // Resolve values (custom overrides preset)
  const Icon = customIcon ?? config.icon
  const title = customTitle ?? t(config.titleKey)
  const description = customDescription ?? t(config.descriptionKey)
  const actionLabel = customActionLabel ?? (config.actionKey ? t(config.actionKey) : undefined)

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
