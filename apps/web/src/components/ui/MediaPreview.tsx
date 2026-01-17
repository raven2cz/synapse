/**
 * MediaPreview Component (Civitai Architecture)
 *
 * Efficient media preview with thumbnail-first rendering.
 * Refactored to match Civitai's EdgeVideo.tsx playback logic for maximum stability.
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

  // Civitai-style playback state
  const [canPlay, setCanPlay] = useState(false) // Visibility threshold met
  const [isPlaying, setIsPlaying] = useState(false) // Actual playback state
  const [autoplayFailed, setAutoplayFailed] = useState(false)

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

  // Determine if we should attempt playback
  // Criteria: Video + Visible (canPlay) + Not blurred + Policy (Hover or Auto)
  const shouldPlay = isVideo && canPlay && !shouldBlur && (
    (playOnHover && isHovering) ||
    (autoPlay && !isHovering) // Keep playing if autoplay enabled, even if not hovering
  )

  // Thumbnail logic
  const thumbnailUrl = isVideo ? (thumbnailSrc || '') : src
  const hasThumbnail = !!thumbnailUrl

  // Decide if we render the video tag at all (Progressive enhancement)
  // We mirror Civitai: Render video if we intend to play or if wrapping logic requires it.
  // Here we optimize: Render if simple boolean tells us.
  // Ideally, always render video but keep display:none or opacity:0 until needed?
  // Civitai renders video always but uses IntersectionObserver to play/pause.
  // To save memory, we only render if "close" to playing (isInView/canPlay)? 
  // For now, let's keep rendering it if it's a video, but let IO handle loading optionally.
  // But wait, Synapse design was "only render video if hovered/autoplay".
  // Let's stick to: Render if canPlay (visible) or Hovering.
  // Actually, Civitai renders it always in EdgeVideo component.
  // Let's rely on `canPlay` (visibility) to trigger load?
  const shouldLoadVideo = isVideo && (canPlay || isHovering || autoPlay || !hasThumbnail)

  // ---------------------------------------------------------------------------
  // Effects
  // ---------------------------------------------------------------------------

  // Detect media type
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

  // Intersection Observer (Civitai Style)
  // Toggles `canPlay` based on threshold.
  useEffect(() => {
    const element = containerRef.current
    if (!element) return

    const threshold = 0.25 // Civitai default
    const observer = new IntersectionObserver(
      ([{ intersectionRatio, isIntersecting }]) => {
        // Civitai logic: intersectionRatio >= threshold
        // We also check isIntersecting to be safe
        setCanPlay(isIntersecting && intersectionRatio >= threshold)
      },
      {
        threshold: [threshold],
      }
    )

    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // Playback Control Effect (Decoupled)
  useEffect(() => {
    const video = videoRef.current
    if (!video || !isVideo) return

    if (shouldPlay) {
      const playPromise = video.play()
      playPromise
        .then(() => {
          setIsPlaying(true)
          setAutoplayFailed(false)

          // Handle preview duration limit (Synapse specific)
          if (autoPlay && !isHovering && previewDuration > 0) {
            if (previewTimeoutRef.current) clearTimeout(previewTimeoutRef.current)
            previewTimeoutRef.current = setTimeout(() => {
              video.pause()
              setIsPlaying(false)
            }, previewDuration * 1000)
          }
        })
        .catch((e) => {
          console.warn('[MediaPreview] Autoplay failed/interrupted', e)
          setAutoplayFailed(true)
          setIsPlaying(false)
        })
    } else {
      video.pause()
      setIsPlaying(false)
      if (previewTimeoutRef.current) clearTimeout(previewTimeoutRef.current)
    }

    return () => {
      if (previewTimeoutRef.current) clearTimeout(previewTimeoutRef.current)
    }
  }, [shouldPlay, isVideo, autoPlay, isHovering, previewDuration])

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
    if (!playOnHover && !autoPlay) return

    // Check if we need to "wake up" a stuck video (simple version)
    // If we are about to play, the Effect will handle it.

    hoverTimeoutRef.current = setTimeout(() => {
      setIsHovering(true)
    }, 50)
  }, [playOnHover, autoPlay])

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
      {/* Loading skeleton */}
      {imageLoadState !== 'loaded' && !hasThumbnail && imageLoadState !== 'error' && (
        <div className="absolute inset-0 skeleton" />
      )}

      {/* Error state */}
      {imageLoadState === 'error' && videoLoadState === 'error' && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-deep/50">
          <AlertTriangle className="w-8 h-8 text-text-muted" />
        </div>
      )}

      {/* Thumbnail/Image */}
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
            // Simple fade out when video plays
            isPlaying && 'opacity-0',
            shouldBlur && 'blur-xl scale-110'
          )}
          onLoad={() => setImageLoadState('loaded')}
          onError={() => setImageLoadState('error')}
        />
      )}

      {/* Video Element */}
      {shouldLoadVideo && (
        <video
          ref={videoRef}
          // Try to use webm if available? (Future: check if src has alternative)
          // For now, assume backend provides one src.
          src={src}
          poster={thumbnailSrc}
          muted={isMuted}
          loop
          playsInline
          // Civitai Strategy: 'none' if no intent to play, 'metadata' if controls or likely to play.
          // Since we load this conditionally (shouldLoadVideo), we can use 'metadata' or 'auto'.
          preload="metadata"
          className={clsx(
            'absolute inset-0 w-full h-full object-cover transition-opacity duration-300',
            (isPlaying || (!hasThumbnail && videoLoadState === 'loaded')) ? 'opacity-100' : 'opacity-0',
            shouldBlur && 'blur-xl scale-110'
          )}
          onLoadedData={() => setVideoLoadState('loaded')}
          onError={() => setVideoLoadState('error')}
        />
      )}

      {/* Play/Mute Controls */}
      {isVideo && showPlayIcon && !isPlaying && !shouldBlur && (autoplayFailed || !autoPlay) && (
        <div className={clsx(
          "absolute bottom-2 left-2 p-1.5 rounded-lg bg-black/60 backdrop-blur-sm pointer-events-none transition-opacity",
          imageLoadState === 'loaded' || videoLoadState === 'loaded' ? 'opacity-100' : 'opacity-0'
        )}>
          <Play className="w-4 h-4 text-white fill-white" />
        </div>
      )}

      {isVideo && (isPlaying || isHovering) && (videoLoadState === 'loaded' || isPlaying) && !shouldBlur && (
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

      {/* NSFW Overlay */}
      {nsfw && nsfwBlurEnabled && !isRevealed && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-20">
          <div className="bg-slate-deep/80 backdrop-blur-sm p-3 rounded-xl text-center">
            <EyeOff className="w-6 h-6 text-text-muted mx-auto mb-1" />
            <span className="text-xs text-text-muted">NSFW</span>
          </div>
        </div>
      )}

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
