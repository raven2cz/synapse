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
import type { MediaType } from '@/lib/media'

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
  /** Autoplay video (default: false). If true, plays for previewDuration. */
  autoPlay?: boolean
  /** Duration to play in autoplay mode (seconds). 0 = loop forever. Default: 10s */
  previewDuration?: number
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
 * For videos: Thumbnail-first, video loads on hover OR when autoPlay is true.
 *             Falls back to video element as poster if no thumbnail provided.
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
  autoPlay = false,
  previewDuration = 10,
  showPlayIcon = true,
  onClick,
  onTypeDetected,
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
  const [isPlaying, setIsPlaying] = useState(false)

  // ---------------------------------------------------------------------------
  // Refs
  // ---------------------------------------------------------------------------
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const previewTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ---------------------------------------------------------------------------
  // Computed values
  // ---------------------------------------------------------------------------
  const isVideo = mediaType === 'video'
  const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed

  // Determine if we need to load the video content
  // Load if:
  // 1. Hovering (and playOnHover)
  // 2. Autoplay enabled
  // 3. NO thumbnail available (need video frame as poster)
  const shouldLoadVideo = isVideo && isInView && (
    (playOnHover && isHovering) ||
    autoPlay ||
    !thumbnailSrc
  )

  // Determine if we should actually be PLAYING
  const shouldPlay = isVideo && isInView && !shouldBlur && (
    (playOnHover && isHovering) ||
    (autoPlay && !isHovering) // Autoplay, but pause on hover (optional style, or keep playing?) -> Let's keep playing
  )

  // Thumbnail logic
  // If video and we have a thumbnailSrc -> use it.
  // If video and NO thumbnailSrc -> use '' (img tag won't render, video will serve as poster)
  // If image -> use src
  const thumbnailUrl = isVideo ? (thumbnailSrc || '') : src
  const hasThumbnail = !!thumbnailUrl

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

  // Intersection Observer
  useEffect(() => {
    if (!containerRef.current) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          setIsInView(entry.isIntersecting)
        })
      },
      {
        threshold: 0.1,
        rootMargin: '50px', // Tighter margin to save resources on Firefox
      }
    )

    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  // Video Playback Control
  useEffect(() => {
    const video = videoRef.current
    if (!video || !isVideo) return

    if (shouldPlay && hasLoadedVideo) {
      // Start playing
      const playPromise = video.play()
      playPromise
        .then(() => {
          setIsPlaying(true)

          // Handle preview duration limit
          if (autoPlay && !isHovering && previewDuration > 0) {
            // Clear existing timeout
            if (previewTimeoutRef.current) clearTimeout(previewTimeoutRef.current)

            // Set new timeout to pause after duration
            previewTimeoutRef.current = setTimeout(() => {
              video.pause()
              setIsPlaying(false)
            }, previewDuration * 1000)
          }
        })
        .catch(() => {
          // Autoplay often blocked
          setIsPlaying(false)
        })
    } else {
      // Pause
      video.pause()
      setIsPlaying(false)
      if (previewTimeoutRef.current) clearTimeout(previewTimeoutRef.current)
    }

    return () => {
      if (previewTimeoutRef.current) clearTimeout(previewTimeoutRef.current)
    }
  }, [shouldPlay, hasLoadedVideo, isVideo, autoPlay, isHovering, previewDuration])

  // Cleanup hover timeout
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleMouseEnter = useCallback(() => {
    // AGGRESSIVE RECOVERY Logic for "stuck" videos
    const video = videoRef.current
    if (video) {
      // Recovery conditions:
      // 1. Error state
      // 2. Network State = NO_SOURCE (3)
      // 3. Ready State < HAVE_CURRENT_DATA (2) -> stuck loading
      const isStuck =
        videoLoadState === 'error' ||
        video.error ||
        video.networkState === 3 ||
        (video.readyState < 2 && !video.ended)

      if (isStuck) {
        setVideoLoadState('idle')
        // Add a cache-busting param to force browser to drop the cached failed request? 
        // Maybe safer just to reload() for now.
        video.load()

        const playPromise = video.play()
        playPromise.catch(() => { })
      }
      // If it's just paused but looks healthy
      else if (video.paused) {
        video.play().catch(() => { })
      }
    }

    if (!playOnHover && !autoPlay) return

    // Small delay to prevent accidental triggers/flicker
    hoverTimeoutRef.current = setTimeout(() => {
      setIsHovering(true)
    }, 50)
  }, [playOnHover, autoPlay, videoLoadState])

  const handleMouseLeave = useCallback(() => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
      hoverTimeoutRef.current = null
    }
    setIsHovering(false)

    // If we were autoplaying, ensure we reset to autoplay state (logic handled in effect)
  }, [])

  const handleReveal = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsRevealed((prev) => !prev)
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
      {/* Loading skeleton - visible until something loads */}
      {imageLoadState !== 'loaded' && !hasLoadedVideo && imageLoadState !== 'error' && (
        <div className="absolute inset-0 skeleton" />
      )}

      {/* Error state - only if BOTH fail */}
      {imageLoadState === 'error' && videoLoadState === 'error' && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-deep/50">
          <AlertTriangle className="w-8 h-8 text-text-muted" />
        </div>
      )}

      {/* Thumbnail/Image - ALWAYS rendered if available */}
      {hasThumbnail && (
        <img
          src={thumbnailUrl}
          alt={alt}
          loading="lazy"
          decoding="async"
          className={clsx(
            'w-full h-full object-cover transition-all duration-300',
            imageLoadState !== 'loaded' && 'opacity-0',
            imageLoadState === 'loaded' && 'opacity-100',
            // Hide when video is playing
            isPlaying && 'opacity-0',
            shouldBlur && 'blur-xl scale-110'
          )}
          onLoad={() => setImageLoadState('loaded')}
          onError={() => setImageLoadState('error')}
        />
      )}

      {/* Video element - content */}
      {isVideo && shouldLoadVideo && (
        <video
          ref={videoRef}
          src={src}
          poster={thumbnailSrc} // Browser native poster handling
          muted={isMuted}
          loop
          playsInline
          preload="metadata" // Important for gathering dimensions/first frame
          className={clsx(
            'absolute inset-0 w-full h-full object-cover transition-opacity duration-300',
            // Visible if playing OR (no thumbnail and loaded)
            (isPlaying || (!hasThumbnail && hasLoadedVideo)) ? 'opacity-100' : 'opacity-0',
            shouldBlur && 'blur-xl scale-110',
            // Pointer events allowed if controls needed (future), else none
          )}
          onLoadedData={() => setVideoLoadState('loaded')}
          onError={() => setVideoLoadState('error')}
        />
      )}

      {/* Play indicators */}
      {isVideo && showPlayIcon && !isPlaying && !shouldBlur && (
        <div className={clsx(
          "absolute bottom-2 left-2 p-1.5 rounded-lg bg-black/60 backdrop-blur-sm pointer-events-none transition-opacity",
          imageLoadState === 'loaded' || hasLoadedVideo ? 'opacity-100' : 'opacity-0'
        )}>
          <Play className="w-4 h-4 text-white fill-white" />
        </div>
      )}

      {/* Mute toggle */}
      {isVideo && (isPlaying || isHovering) && hasLoadedVideo && !shouldBlur && (
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
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-20">
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
            'absolute top-2 right-2 p-1.5 rounded-lg z-30',
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
