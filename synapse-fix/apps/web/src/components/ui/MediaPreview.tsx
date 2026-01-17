/**
 * MediaPreview Component - Optimized Version
 *
 * Professional-grade media preview with thumbnail-first rendering.
 * Designed for maximum performance in grid layouts.
 *
 * Key principles:
 * 1. Thumbnail-first: Always show image immediately, never wait
 * 2. Progressive enhancement: Video loads lazily in background
 * 3. No blocking: UI renders instantly, media loads async
 * 4. Hover-to-play: Videos only play on user interaction
 *
 * @author Synapse Team
 */

import { useState, useRef, useEffect, useCallback, memo } from 'react'
import { clsx } from 'clsx'
import { Eye, EyeOff, AlertTriangle, Play, Volume2, VolumeX } from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'
import { detectMediaType } from '@/lib/media'
import type { MediaType, MediaInfo } from '@/lib/media'

// ============================================================================
// Types
// ============================================================================

export interface MediaPreviewProps {
  /** Media URL (image or video) */
  src: string
  /** Explicit media type (skips auto-detection) */
  type?: MediaType
  /** Thumbnail URL for video poster */
  thumbnailSrc?: string
  /** Alt text for accessibility */
  alt?: string
  /** NSFW content flag */
  nsfw?: boolean
  /** Additional CSS classes */
  className?: string
  /** Aspect ratio preset */
  aspectRatio?: 'square' | 'video' | 'portrait' | 'auto'
  /** Play video on hover (default: true) */
  playOnHover?: boolean
  /** Show play icon for videos */
  showPlayIcon?: boolean
  /** Click handler */
  onClick?: () => void
  /** Called when media type is detected */
  onTypeDetected?: (type: MediaType) => void
  /** Called on load error */
  onError?: (error: Error) => void
}

type LoadState = 'idle' | 'loading' | 'loaded' | 'error'

// ============================================================================
// Component
// ============================================================================

/**
 * MediaPreview displays images and videos with optimal loading strategy.
 *
 * For images: Native lazy loading, instant display
 * For videos: Thumbnail-first, video loads on hover only
 */
export const MediaPreview = memo(function MediaPreview({
  src,
  type: explicitType,
  thumbnailSrc,
  alt = 'Preview',
  nsfw = false,
  className,
  aspectRatio = 'square',
  playOnHover = true,
  showPlayIcon = true,
  onClick,
  onTypeDetected,
  onError,
}: MediaPreviewProps) {
  const { nsfwBlurEnabled } = useSettingsStore()

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const [mediaType, setMediaType] = useState<MediaType>(() => {
    if (explicitType && explicitType !== 'unknown') return explicitType
    return detectMediaType(src).type
  })
  const [imageLoadState, setImageLoadState] = useState<LoadState>('idle')
  const [videoLoadState, setVideoLoadState] = useState<LoadState>('idle')
  const [isRevealed, setIsRevealed] = useState(false)
  const [isHovering, setIsHovering] = useState(false)
  const [isMuted, setIsMuted] = useState(true)
  const [isInView, setIsInView] = useState(false)

  // ---------------------------------------------------------------------------
  // Refs
  // ---------------------------------------------------------------------------
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ---------------------------------------------------------------------------
  // Computed values
  // ---------------------------------------------------------------------------
  const isVideo = mediaType === 'video'
  const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed
  // Video is visible when: hovering OR (in view and no thumbnail available)
  const shouldShowVideo = isVideo && isHovering && isInView && !shouldBlur
  // Thumbnail to show (for videos, use thumbnailSrc or fallback to src for images)
  const thumbnailUrl = isVideo ? (thumbnailSrc || '') : src
  const hasLoadedImage = imageLoadState === 'loaded'
  const hasLoadedVideo = videoLoadState === 'loaded'

  // ---------------------------------------------------------------------------
  // Effects
  // ---------------------------------------------------------------------------

  // Detect media type on src change
  useEffect(() => {
    if (explicitType && explicitType !== 'unknown') {
      setMediaType(explicitType)
      onTypeDetected?.(explicitType)
      return
    }
    const detected = detectMediaType(src)
    setMediaType(detected.type)
    onTypeDetected?.(detected.type)
  }, [src, explicitType, onTypeDetected])

  // Intersection Observer for lazy video loading
  useEffect(() => {
    if (!containerRef.current || !isVideo) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          setIsInView(entry.isIntersecting)
        })
      },
      {
        threshold: 0.1,
        rootMargin: '200px', // Preload slightly before visible
      }
    )

    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [isVideo])

  // Handle video play/pause based on hover state
  useEffect(() => {
    const video = videoRef.current
    if (!video || !isVideo) return

    if (shouldShowVideo && hasLoadedVideo) {
      video.currentTime = 0
      video.play().catch(() => {
        // Autoplay blocked - that's fine
      })
    } else {
      video.pause()
    }
  }, [shouldShowVideo, hasLoadedVideo, isVideo])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current)
      }
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleMouseEnter = useCallback(() => {
    if (!playOnHover || !isVideo) return

    // Small delay to prevent accidental triggers
    hoverTimeoutRef.current = setTimeout(() => {
      setIsHovering(true)
    }, 100)
  }, [playOnHover, isVideo])

  const handleMouseLeave = useCallback(() => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
      hoverTimeoutRef.current = null
    }
    setIsHovering(false)
  }, [])

  const handleReveal = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsRevealed((prev) => !prev)
  }, [])

  const handleImageLoad = useCallback(() => {
    setImageLoadState('loaded')
  }, [])

  const handleImageError = useCallback(() => {
    setImageLoadState('error')
    onError?.(new Error(`Failed to load image: ${thumbnailUrl || src}`))
  }, [thumbnailUrl, src, onError])

  const handleVideoLoad = useCallback(() => {
    setVideoLoadState('loaded')
  }, [])

  const handleVideoError = useCallback(() => {
    setVideoLoadState('error')
    // Fallback: just show thumbnail, don't report error
  }, [])

  const handleToggleMute = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsMuted((prev) => !prev)
    if (videoRef.current) {
      videoRef.current.muted = !isMuted
    }
  }, [isMuted])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const aspectRatioClass = {
    square: 'aspect-square',
    video: 'aspect-video',
    portrait: 'aspect-[3/4]',
    auto: '',
  }[aspectRatio]

  return (
    <div
      ref={containerRef}
      className={clsx(
        'relative overflow-hidden rounded-xl bg-slate-mid/50 group',
        aspectRatioClass,
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Loading skeleton - always visible until image loads */}
      {imageLoadState !== 'loaded' && imageLoadState !== 'error' && (
        <div className="absolute inset-0 skeleton" />
      )}

      {/* Error state */}
      {imageLoadState === 'error' && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-deep/50">
          <AlertTriangle className="w-8 h-8 text-text-muted" />
        </div>
      )}

      {/* Thumbnail/Image - ALWAYS rendered for instant display */}
      {(thumbnailUrl || !isVideo) && (
        <img
          src={thumbnailUrl || src}
          alt={alt}
          loading="lazy"
          decoding="async"
          className={clsx(
            'w-full h-full object-cover transition-all duration-300',
            imageLoadState !== 'loaded' && 'opacity-0',
            imageLoadState === 'loaded' && 'opacity-100',
            // Hide when video is playing
            shouldShowVideo && hasLoadedVideo && 'opacity-0',
            shouldBlur && 'blur-xl scale-110'
          )}
          onLoad={handleImageLoad}
          onError={handleImageError}
        />
      )}

      {/* Video element - only loads when in view AND hovering */}
      {isVideo && isInView && (
        <video
          ref={videoRef}
          // Only set src when hovering to trigger load
          src={isHovering ? src : undefined}
          poster={thumbnailSrc}
          muted={isMuted}
          loop
          playsInline
          preload="none"
          className={clsx(
            'absolute inset-0 w-full h-full object-cover transition-opacity duration-300',
            shouldShowVideo && hasLoadedVideo ? 'opacity-100' : 'opacity-0 pointer-events-none',
            shouldBlur && 'blur-xl scale-110'
          )}
          onLoadedData={handleVideoLoad}
          onError={handleVideoError}
        />
      )}

      {/* Play icon indicator for videos */}
      {isVideo && showPlayIcon && !isHovering && hasLoadedImage && !shouldBlur && (
        <div className="absolute bottom-2 left-2 p-1.5 rounded-lg bg-black/60 backdrop-blur-sm pointer-events-none">
          <Play className="w-4 h-4 text-white fill-white" />
        </div>
      )}

      {/* Mute toggle for videos with audio */}
      {isVideo && isHovering && hasLoadedVideo && !shouldBlur && (
        <button
          onClick={handleToggleMute}
          className={clsx(
            'absolute bottom-2 right-2 p-1.5 rounded-lg',
            'bg-black/60 backdrop-blur-sm',
            'text-white hover:bg-black/80',
            'transition-all duration-200 z-10'
          )}
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </button>
      )}

      {/* NSFW blur overlay */}
      {nsfw && nsfwBlurEnabled && !isRevealed && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="bg-slate-deep/80 backdrop-blur-sm p-3 rounded-xl text-center">
            <EyeOff className="w-6 h-6 text-text-muted mx-auto mb-1" />
            <span className="text-xs text-text-muted">NSFW</span>
          </div>
        </div>
      )}

      {/* NSFW reveal button */}
      {nsfw && nsfwBlurEnabled && (
        <button
          onClick={handleReveal}
          className={clsx(
            'absolute top-2 right-2 p-1.5 rounded-lg z-10',
            'bg-slate-deep/80 backdrop-blur-sm',
            'text-text-secondary hover:text-text-primary',
            'transition-colors duration-200'
          )}
        >
          {isRevealed ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      )}
    </div>
  )
})

export default MediaPreview
