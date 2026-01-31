/**
 * PackGallery Section
 *
 * Preview media grid with zoom controls and fullscreen support.
 *
 * ⚠️ KRITICKÉ FUNKCE ZACHOVÁNY:
 * - MediaPreview props: autoPlay, playFullOnHover, thumbnailSrc
 *   (Tyto algoritmy byly laděny dlouho - neměnit!)
 * - FullscreenMediaViewer integrace přes onPreviewClick
 * - Civitai URL transformace (jsou v datech, ne zde)
 * - Zoom controls (xs, sm, md, lg, xl)
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Smooth animace grid items
 * - Premium hover efekty
 * - Lepší video badge
 * - Staggered entrance animace
 */

import { useState } from 'react'
import { ZoomIn, ZoomOut, Play, Image as ImageIcon } from 'lucide-react'
import { clsx } from 'clsx'
import { MediaPreview } from '@/components/ui/MediaPreview'
import type { PreviewInfo, CardSize } from '../types'
import { ANIMATION_PRESETS, GRID_CLASSES } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface PackGalleryProps {
  /**
   * Preview items to display
   */
  previews: PreviewInfo[]

  /**
   * Handler when preview is clicked (opens fullscreen)
   */
  onPreviewClick: (index: number) => void

  /**
   * Initial card size (default: 'sm')
   */
  initialSize?: CardSize

  /**
   * Animation delay for staggered entrance
   */
  animationDelay?: number
}

// =============================================================================
// Component
// =============================================================================

export function PackGallery({
  previews,
  onPreviewClick,
  initialSize = 'sm',
  animationDelay = 0,
}: PackGalleryProps) {
  const [cardSize, setCardSize] = useState<CardSize>(initialSize)

  // Zoom functions
  const zoomIn = () => {
    const sizes: CardSize[] = ['xs', 'sm', 'md', 'lg', 'xl']
    const currentIndex = sizes.indexOf(cardSize)
    if (currentIndex < sizes.length - 1) {
      setCardSize(sizes[currentIndex + 1])
    }
  }

  const zoomOut = () => {
    const sizes: CardSize[] = ['xs', 'sm', 'md', 'lg', 'xl']
    const currentIndex = sizes.indexOf(cardSize)
    if (currentIndex > 0) {
      setCardSize(sizes[currentIndex - 1])
    }
  }

  // Empty state
  if (!previews?.length) {
    return (
      <div
        className={clsx(
          'flex flex-col items-center justify-center py-12 px-6',
          'bg-slate-dark/50 rounded-2xl border border-dashed border-slate-mid/50',
          ANIMATION_PRESETS.fadeIn
        )}
        style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
      >
        <ImageIcon className="w-12 h-12 text-text-muted/50 mb-3" />
        <p className="text-text-muted text-sm">No previews available</p>
        <p className="text-text-muted/60 text-xs mt-1">
          Import from Civitai or add previews manually
        </p>
      </div>
    )
  }

  return (
    <div
      className={ANIMATION_PRESETS.fadeIn}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
      {/* Header with count and zoom controls */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-synapse animate-pulse" />
          Previews
          <span className="text-text-muted font-normal">({previews.length})</span>
        </h3>

        {/* Zoom Controls - Premium styling */}
        <div className={clsx(
          'flex items-center gap-1',
          'bg-slate-dark/80 backdrop-blur-sm rounded-xl p-1',
          'border border-slate-mid/50',
          'shadow-lg shadow-black/20'
        )}>
          <button
            onClick={zoomOut}
            disabled={cardSize === 'xs'}
            className={clsx(
              'p-2 rounded-lg transition-all duration-200',
              'hover:bg-slate-mid hover:text-synapse',
              'disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent'
            )}
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <div className="w-px h-4 bg-slate-mid" />
          <button
            onClick={zoomIn}
            disabled={cardSize === 'xl'}
            className={clsx(
              'p-2 rounded-lg transition-all duration-200',
              'hover:bg-slate-mid hover:text-synapse',
              'disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent'
            )}
            title="Zoom in"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Grid - uses constants for responsive sizing */}
      <div className={clsx('grid', GRID_CLASSES[cardSize])}>
        {previews.map((preview, idx) => (
          <div
            key={idx}
            className={clsx(
              'group/card relative rounded-xl overflow-hidden cursor-pointer',
              'bg-slate-dark',
              // Smooth transitions for all hover effects
              'transition-all duration-300 ease-out',
              // Hover effects - Civitai style (premium)
              'hover:ring-2 hover:ring-synapse/60',
              'hover:shadow-xl hover:shadow-synapse/20',
              'hover:scale-[1.02]',
              'hover:-translate-y-1',
              // Staggered animation
              ANIMATION_PRESETS.fadeIn
            )}
            style={{
              animationDelay: `${animationDelay + (idx * 30)}ms`,
              animationFillMode: 'both'
            }}
            onClick={() => onPreviewClick(idx)}
          >
            {/*
              ⚠️ KRITICKÉ: MediaPreview props - zachovat přesně!
              Tyto props byly laděny pro správné video přehrávání.
            */}
            <MediaPreview
              src={preview.url || ''}
              type={preview.media_type || 'image'}
              thumbnailSrc={preview.thumbnail_url}
              nsfw={preview.nsfw}
              aspectRatio="portrait"
              className="w-full h-full"
              autoPlay={true}
              playFullOnHover={true}
            />

            {/* Video indicator badge - Premium styling */}
            {preview.media_type === 'video' && (
              <div className={clsx(
                'absolute bottom-2 right-2',
                'px-2 py-1 rounded-lg',
                'bg-black/70 backdrop-blur-sm',
                'text-white text-xs font-medium',
                'flex items-center gap-1.5',
                'pointer-events-none',
                'transition-transform duration-200',
                'group-hover/card:scale-105'
              )}>
                <Play className="w-3 h-3" fill="currentColor" />
                Video
              </div>
            )}

            {/* Hover overlay for visual feedback */}
            <div className={clsx(
              'absolute inset-0 bg-gradient-to-t from-black/20 to-transparent',
              'opacity-0 group-hover/card:opacity-100',
              'transition-opacity duration-300',
              'pointer-events-none'
            )} />
          </div>
        ))}
      </div>
    </div>
  )
}

export default PackGallery
