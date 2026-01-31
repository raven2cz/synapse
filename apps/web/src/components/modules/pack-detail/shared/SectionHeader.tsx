/**
 * SectionHeader Component
 *
 * Reusable header for pack detail sections with edit button support.
 * Features hover-reveal edit button and consistent styling.
 */

import { useState } from 'react'
import {
  Edit3,
  Image,
  Package,
  Info,
  GitBranch,
  Sliders,
  HardDrive,
  Terminal,
  ChevronDown,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { clsx } from 'clsx'
import { t } from '../constants'

/**
 * Icon mapping for sections
 */
const iconMap: Record<string, LucideIcon> = {
  Image,
  Package,
  Info,
  GitBranch,
  Sliders,
  HardDrive,
  Terminal,
}

export interface SectionHeaderProps {
  /**
   * Section title text
   */
  title: string

  /**
   * Icon name or Lucide icon component
   */
  icon?: string | LucideIcon

  /**
   * Whether section is editable (shows edit button on hover)
   */
  editable?: boolean

  /**
   * Callback when edit button is clicked
   */
  onEdit?: () => void

  /**
   * Whether section is collapsible
   */
  collapsible?: boolean

  /**
   * Whether section is currently collapsed
   */
  collapsed?: boolean

  /**
   * Callback when collapse toggle is clicked
   */
  onToggleCollapse?: () => void

  /**
   * Optional badge content (e.g., count)
   */
  badge?: string | number

  /**
   * Additional actions to render on the right side
   */
  actions?: React.ReactNode

  /**
   * Additional className for customization
   */
  className?: string
}

export function SectionHeader({
  title,
  icon,
  editable = false,
  onEdit,
  collapsible = false,
  collapsed = false,
  onToggleCollapse,
  badge,
  actions,
  className,
}: SectionHeaderProps) {
  const [isHovered, setIsHovered] = useState(false)

  // Resolve icon component
  const IconComponent: LucideIcon | null =
    typeof icon === 'string'
      ? iconMap[icon] ?? null
      : icon ?? null

  // Collapse icon
  const CollapseIcon = collapsed ? ChevronRight : ChevronDown

  return (
    <div
      className={clsx(
        'flex items-center justify-between py-3 px-4',
        'border-b border-white/5',
        'transition-colors duration-150',
        isHovered && editable && 'bg-white/[0.02]',
        className
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Left side: Icon, Title, Badge */}
      <div className="flex items-center gap-3">
        {/* Collapse toggle */}
        {collapsible && (
          <button
            onClick={onToggleCollapse}
            className={clsx(
              'p-1 rounded-md',
              'text-white/40 hover:text-white/70',
              'hover:bg-white/5',
              'transition-all duration-150',
              'focus:outline-none focus:ring-2 focus:ring-synapse/50'
            )}
            aria-label={collapsed ? 'Expand section' : 'Collapse section'}
          >
            <CollapseIcon className="w-4 h-4" />
          </button>
        )}

        {/* Section icon */}
        {IconComponent && (
          <IconComponent className="w-5 h-5 text-white/50" />
        )}

        {/* Title */}
        <h3 className="text-sm font-medium text-white/90">
          {title}
        </h3>

        {/* Badge */}
        {badge !== undefined && (
          <span className={clsx(
            'px-2 py-0.5 rounded-full text-xs',
            'bg-white/10 text-white/60'
          )}>
            {badge}
          </span>
        )}
      </div>

      {/* Right side: Actions and Edit button */}
      <div className="flex items-center gap-2">
        {/* Custom actions */}
        {actions}

        {/* Edit button (appears on hover) */}
        {editable && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onEdit}
            className={clsx(
              'transition-all duration-200',
              isHovered
                ? 'opacity-100 translate-x-0'
                : 'opacity-0 translate-x-2 pointer-events-none'
            )}
          >
            <Edit3 className="w-4 h-4 mr-1.5" />
            {t('pack.actions.edit')}
          </Button>
        )}
      </div>
    </div>
  )
}

export default SectionHeader
