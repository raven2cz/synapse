/**
 * DetailPreviewGallery Component
 *
 * Optimized preview gallery for model detail modal.
 * Displays thumbnails in a grid with lazy loading and video hover preview.
 *
 * Key features:
 * - Thumbnail-first rendering (instant display)
 * - Video on hover only
 * - Virtualized rendering for large galleries (optional)
 * - Click to open fullscreen
 *
 * @author Synapse Team
 */

import { memo, useCallback, useState } from 'react'
import { clsx } from 'clsx'
import { MediaPreview } from './MediaPreview'
import type { MediaType } from '@/lib/media'

// ============================================================================
// Types
// ============================================================================

export interface PreviewItem {
  url: string
  thumbnailUrl?: string
  type?: MediaType
  nsfw?: boolean
  width?: number
  height?: number
  meta?: Record<string, any>
}

export interface DetailPreviewGalleryProps {
  /** Array of preview items */
  items: PreviewItem[]
  /** Called when item is clicked */
  onItemClick?: (index: number) => void
  /** Maximum height of gallery container */
  maxHeight?: number | string
  /** Number of columns */
  columns?: number
  /** Additional CSS classes */
  className?: string
}

// ============================================================================
// Component
// ============================================================================

export const DetailPreviewGallery = memo(function DetailPreviewGallery({
  items,
  onItemClick,
  maxHeight = 360,
  columns = 6,
  className,
}: DetailPreviewGalleryProps) {
  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!items || items.length === 0) {
    return (
      <div className="text-center py-8 text-text-muted">
        No preview images available
      </div>
    )
  }

  return (
    <div className={clsx('space-y-3', className)}>
      <h3 className="text-sm font-semibold text-text-primary">
        Preview Images ({items.length})
      </h3>

      <div
        className={clsx(
          'grid gap-3 overflow-y-auto p-1',
          columns === 4 && 'grid-cols-4',
          columns === 5 && 'grid-cols-5',
          columns === 6 && 'grid-cols-6',
          columns === 8 && 'grid-cols-8'
        )}
        style={{ maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight }}
      >
        {items.map((item, idx) => (
          <MediaPreview
            key={`${item.url}-${idx}`}
            src={item.url}
            type={item.type}
            thumbnailSrc={item.thumbnailUrl}
            nsfw={item.nsfw}
            aspectRatio="portrait"
            playOnHover={true}
            showPlayIcon={true}
            className="cursor-pointer hover:ring-2 ring-synapse transition-all"
            onClick={() => onItemClick?.(idx)}
          />
        ))}
      </div>
    </div>
  )
})

export default DetailPreviewGallery
