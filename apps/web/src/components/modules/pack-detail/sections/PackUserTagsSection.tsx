/**
 * PackUserTagsSection
 *
 * Displays user-defined tags with edit capability.
 *
 * FUNKCE ZACHOVÁNY:
 * - Tag chips display
 * - Special styling for 'nsfw-pack' tag
 * - Edit button to open tag editor modal
 * - Empty state with prompt
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium tag chip design with hover effects
 * - Enhanced color scheme
 * - Staggered animation
 */

import { Tag, Edit3 } from 'lucide-react'
import { clsx } from 'clsx'
import { Card } from '@/components/ui/Card'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface PackUserTagsSectionProps {
  /**
   * User-defined tags
   */
  tags: string[]

  /**
   * Handler for edit button
   */
  onEdit: () => void

  /**
   * Animation delay
   */
  animationDelay?: number
}

// =============================================================================
// Sub-components
// =============================================================================

interface TagChipProps {
  tag: string
  index: number
}

function TagChip({ tag, index }: TagChipProps) {
  const isNsfw = tag === 'nsfw-pack'

  return (
    <span
      className={clsx(
        "px-3 py-1.5 rounded-lg text-sm font-medium",
        "transition-all duration-200",
        "hover:scale-105",
        isNsfw
          ? "bg-red-500/20 text-red-400 border border-red-500/30 hover:border-red-500/50"
          : "bg-pulse/20 text-pulse border border-pulse/30 hover:border-pulse/50"
      )}
      style={{
        animationDelay: `${index * 50}ms`,
      }}
    >
      {tag}
    </span>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function PackUserTagsSection({
  tags,
  onEdit,
  animationDelay = 0,
}: PackUserTagsSectionProps) {
  const hasTags = tags && tags.length > 0

  return (
    <div
      className={ANIMATION_PRESETS.sectionEnter}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
      <Card className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <Tag className="w-4 h-4 text-pulse" />
            User Tags
            {hasTags && (
              <span className="text-text-muted font-normal">({tags.length})</span>
            )}
          </h3>
          <button
            onClick={onEdit}
            className={clsx(
              "text-xs text-synapse flex items-center gap-1",
              "hover:text-synapse/80 transition-colors duration-200"
            )}
          >
            <Edit3 className="w-3 h-3" />
            Edit
          </button>
        </div>

        {/* Tags */}
        {hasTags ? (
          <div className="flex flex-wrap gap-2">
            {tags.map((tag, idx) => (
              <TagChip key={idx} tag={tag} index={idx} />
            ))}
          </div>
        ) : (
          <div className="text-center py-4">
            <Tag className="w-8 h-8 mx-auto mb-2 text-text-muted/50" />
            <p className="text-text-muted text-sm">
              No user tags. Click Edit to add some.
            </p>
          </div>
        )}
      </Card>
    </div>
  )
}

export default PackUserTagsSection
