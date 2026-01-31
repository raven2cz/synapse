/**
 * AnimatedSection Component
 *
 * Wrapper component for pack detail sections with consistent
 * enter/exit animations and Card styling.
 */

import { type ReactNode } from 'react'
import { Card } from '@/components/ui/Card'
import { clsx } from 'clsx'
import { ANIMATION_PRESETS } from '../constants'
import { SectionHeader, type SectionHeaderProps } from './SectionHeader'

export interface AnimatedSectionProps {
  /**
   * Section header configuration (optional, for built-in header)
   */
  header?: SectionHeaderProps

  /**
   * Section content
   */
  children: ReactNode

  /**
   * Whether to animate entrance
   */
  animate?: boolean

  /**
   * Animation delay in ms (for staggered sections)
   */
  animationDelay?: number

  /**
   * Whether section is collapsed
   */
  collapsed?: boolean

  /**
   * Whether section is loading
   */
  isLoading?: boolean

  /**
   * Loading content to show
   */
  loadingContent?: ReactNode

  /**
   * Whether section is empty
   */
  isEmpty?: boolean

  /**
   * Empty state content to show
   */
  emptyContent?: ReactNode

  /**
   * Additional className for the card
   */
  className?: string

  /**
   * Additional className for the content wrapper
   */
  contentClassName?: string

  /**
   * Render without Card wrapper
   */
  noPadding?: boolean

  /**
   * HTML id attribute for linking
   */
  id?: string
}

export function AnimatedSection({
  header,
  children,
  animate = true,
  animationDelay = 0,
  collapsed = false,
  isLoading = false,
  loadingContent,
  isEmpty = false,
  emptyContent,
  className,
  contentClassName,
  noPadding = false,
  id,
}: AnimatedSectionProps) {
  // Animation styles
  const animationStyle = animate
    ? {
        animationDelay: `${animationDelay}ms`,
        animationFillMode: 'both' as const,
      }
    : undefined

  // Determine what to render in content area
  const renderContent = () => {
    if (isLoading && loadingContent) {
      return loadingContent
    }
    if (isEmpty && emptyContent) {
      return emptyContent
    }
    if (collapsed) {
      return null
    }
    return children
  }

  // Base content with optional header
  const content = (
    <>
      {header && (
        <SectionHeader
          {...header}
          collapsible={header.collapsible}
          collapsed={collapsed}
        />
      )}
      {!collapsed && (
        <div
          className={clsx(
            'transition-all duration-300',
            collapsed ? 'opacity-0 max-h-0 overflow-hidden' : 'opacity-100',
            contentClassName
          )}
        >
          {renderContent()}
        </div>
      )}
    </>
  )

  // Wrapper with animation
  if (noPadding) {
    return (
      <div
        id={id}
        className={clsx(
          animate && ANIMATION_PRESETS.sectionEnter,
          className
        )}
        style={animationStyle}
      >
        {content}
      </div>
    )
  }

  return (
    <div
      id={id}
      className={clsx(
        animate && ANIMATION_PRESETS.sectionEnter,
        className
      )}
      style={animationStyle}
    >
      <Card
        className="overflow-hidden"
        padding="none"
      >
        {content}
      </Card>
    </div>
  )
}

/**
 * Hook for staggered section animations
 */
export function useSectionStagger(sectionCount: number, baseDelay = 50): number[] {
  return Array.from({ length: sectionCount }, (_, i) => i * baseDelay)
}

export default AnimatedSection
