/**
 * MediaPreview Component
 *
 * Unified component for displaying image or video previews.
 *
 * Features:
 * - Auto-detection of media type from URL
 * - Auto-play for videos (first 5 seconds, looped)
 * - Full playback on hover
 * - NSFW blur support
 * - Fallback handling (video as image, etc.)
 * - Lazy loading with intersection observer
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { clsx } from 'clsx'
import { Eye, EyeOff, AlertTriangle, Play, Volume2, VolumeX } from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'
import {
  detectMediaType,
  PREVIEW_SETTINGS,
} from '@/lib/media'
import type { MediaType, MediaInfo } from '@/lib/media'

export interface MediaPreviewProps {
  /** Media URL */
  src: string
  /** Explicit media type (overrides detection) */
  type?: MediaType
  /** Thumbnail URL for video (first frame) */
  thumbnailSrc?: string
  /** Alt text */
  alt?: string
  /** NSFW content flag */
  nsfw?: boolean
  /** CSS class name */
  className?: string
  /** Aspect ratio */
  aspectRatio?: 'square' | 'video' | 'portrait' | 'auto'

  // Video specific
  /** Enable auto-play for videos (default: true) */
  autoPlay?: boolean
  /** Preview duration in ms before looping (default: 5000) */
  previewDuration?: number
  /** Play full video on hover (default: true) */
  playFullOnHover?: boolean
  /** Muted state (default: true for preview) */
  muted?: boolean
  /** Loop playback (default: true) */
  loop?: boolean
  /** Show audio indicator for videos with sound */
  showAudioIndicator?: boolean

  // Callbacks
  /** Click handler */
  onClick?: () => void
  /** Called when media loads successfully */
  onMediaLoad?: (info: MediaInfo) => void
  /** Called on load error */
  onError?: (error: Error) => void
  /** Called when media type is detected */
  onTypeDetected?: (type: MediaType) => void
}

type LoadState = 'idle' | 'loading' | 'loaded' | 'error'

export function MediaPreview({
  src,
  type: explicitType,
  thumbnailSrc,
  alt = 'Preview',
  nsfw = false,
  className,
  aspectRatio = 'square',
  autoPlay = true,
  previewDuration = PREVIEW_SETTINGS.PREVIEW_DURATION_MS,
  playFullOnHover = true,
  muted = true,
  loop = true,
  showAudioIndicator = true,
  onClick,
  onMediaLoad,
  onError,
  onTypeDetected,
}: MediaPreviewProps) {
  const { nsfwBlurEnabled } = useSettingsStore()

  // State
  const [mediaType, setMediaType] = useState<MediaType>(explicitType || 'unknown')
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [isRevealed, setIsRevealed] = useState(false)
  const [isHovering, setIsHovering] = useState(false)
  const [isMuted, setIsMuted] = useState(muted)
  const [hasAudio, setHasAudio] = useState(false)
  const [isInView, setIsInView] = useState(false)
  const [fallbackToImage, setFallbackToImage] = useState(false)

  // Refs
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)

  // Computed
  const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed
  const isVideo = mediaType === 'video' && !fallbackToImage
  const showVideo = isVideo && isInView && !shouldBlur

  // Detect media type on mount or src change
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

  // Intersection observer for lazy loading
  useEffect(() => {
    if (!containerRef.current) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          setIsInView(entry.isIntersecting)
        })
      },
      {
        threshold: PREVIEW_SETTINGS.LAZY_LOAD_THRESHOLD,
        rootMargin: PREVIEW_SETTINGS.LAZY_LOAD_MARGIN,
      }
    )

    observer.observe(containerRef.current)

    return () => observer.disconnect()
  }, [])

  // Handle video preview timing
  useEffect(() => {
    if (!showVideo || !videoRef.current || !autoPlay) return

    const video = videoRef.current

    const handleTimeUpdate = () => {
      // If not hovering and past preview duration, restart
      if (!isHovering && video.currentTime * 1000 >= previewDuration) {
        video.currentTime = 0
      }
    }

    video.addEventListener('timeupdate', handleTimeUpdate)

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate)
    }
  }, [showVideo, autoPlay, isHovering, previewDuration])

  // Play/pause video based on visibility and hover
  useEffect(() => {
    if (!videoRef.current || !isVideo) return

    const video = videoRef.current

    if (showVideo && (autoPlay || isHovering)) {
      video.play().catch(() => {
        // Autoplay blocked, that's okay
      })
    } else {
      video.pause()
    }
  }, [showVideo, autoPlay, isHovering, isVideo])

  // Handlers
  const handleReveal = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsRevealed(!isRevealed)
  }, [isRevealed])

  const handleMouseEnter = useCallback(() => {
    if (playFullOnHover) {
      setIsHovering(true)
      // Reset to beginning when starting hover playback
      if (videoRef.current) {
        videoRef.current.currentTime = 0
      }
    }
  }, [playFullOnHover])

  const handleMouseLeave = useCallback(() => {
    setIsHovering(false)
  }, [])

  const handleVideoLoad = useCallback(() => {
    setLoadState('loaded')

    if (videoRef.current) {
      const video = videoRef.current
      // Check if video has audio track
      // @ts-ignore - audioTracks may not be available in all browsers
      const audioTracks = video.audioTracks || video.mozAudioTracks || video.webkitAudioTracks
      if (audioTracks && audioTracks.length > 0) {
        setHasAudio(true)
      }

      onMediaLoad?.({
        type: 'video',
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
        hasAudio: hasAudio,
      })
    }
  }, [onMediaLoad, hasAudio])

  const handleVideoError = useCallback(() => {
    // Video failed to load - fall back to image
    console.warn(`Video failed to load: ${src}, falling back to image`)
    setFallbackToImage(true)
    setMediaType('image')
  }, [src])

  const handleImageLoad = useCallback(() => {
    setLoadState('loaded')
    onMediaLoad?.({
      type: 'image',
    })
  }, [onMediaLoad])

  const handleImageError = useCallback(() => {
    setLoadState('error')
    onError?.(new Error(`Failed to load media: ${src}`))
  }, [src, onError])

  const handleToggleMute = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsMuted(!isMuted)
    if (videoRef.current) {
      videoRef.current.muted = !isMuted
    }
  }, [isMuted])

  // Render
  return (
    <div
      ref={containerRef}
      className={clsx(
        'relative overflow-hidden rounded-xl bg-slate-mid/50 group',
        aspectRatio === 'square' && 'aspect-square',
        aspectRatio === 'video' && 'aspect-video',
        aspectRatio === 'portrait' && 'aspect-[3/4]',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Loading skeleton */}
      {loadState === 'idle' || loadState === 'loading' && (
        <div className="absolute inset-0 skeleton" />
      )}

      {/* Error state */}
      {loadState === 'error' && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-deep/50">
          <AlertTriangle className="w-8 h-8 text-text-muted" />
        </div>
      )}

      {/* Video element */}
      {isVideo && (
        <video
          ref={videoRef}
          src={showVideo ? src : undefined}
          poster={thumbnailSrc}
          muted={isMuted}
          loop={loop}
          playsInline
          preload="metadata"
          className={clsx(
            'w-full h-full object-cover transition-all duration-300',
            loadState !== 'loaded' && 'opacity-0',
            loadState === 'loaded' && 'opacity-100',
            shouldBlur && 'blur-xl scale-110',
          )}
          onLoadedData={handleVideoLoad}
          onError={handleVideoError}
        />
      )}

      {/* Image element (for images or video fallback) */}
      {(!isVideo || !showVideo) && (
        <img
          src={thumbnailSrc || src}
          alt={alt}
          className={clsx(
            'w-full h-full object-cover transition-all duration-300',
            loadState !== 'loaded' && !isVideo && 'opacity-0',
            loadState === 'loaded' && 'opacity-100',
            isVideo && showVideo && 'hidden', // Hide when video is playing
            shouldBlur && 'blur-xl scale-110',
          )}
          onLoad={handleImageLoad}
          onError={handleImageError}
        />
      )}

      {/* Video indicator icon */}
      {isVideo && !isHovering && loadState === 'loaded' && !shouldBlur && (
        <div className="absolute bottom-2 left-2 p-1.5 rounded-lg bg-black/60 backdrop-blur-sm">
          <Play className="w-4 h-4 text-white fill-white" />
        </div>
      )}

      {/* Audio indicator */}
      {isVideo && hasAudio && showAudioIndicator && loadState === 'loaded' && !shouldBlur && (
        <button
          onClick={handleToggleMute}
          className={clsx(
            'absolute bottom-2 right-2 p-1.5 rounded-lg',
            'bg-black/60 backdrop-blur-sm',
            'text-white hover:bg-black/80',
            'transition-all duration-200',
            'opacity-0 group-hover:opacity-100',
          )}
        >
          {isMuted ? (
            <VolumeX className="w-4 h-4" />
          ) : (
            <Volume2 className="w-4 h-4" />
          )}
        </button>
      )}

      {/* NSFW overlay */}
      {nsfw && nsfwBlurEnabled && (
        <div
          className={clsx(
            'absolute inset-0 flex flex-col items-center justify-center',
            'transition-opacity duration-300',
            isRevealed ? 'opacity-0 pointer-events-none' : 'opacity-100'
          )}
        >
          <div className="bg-slate-deep/80 backdrop-blur-sm p-3 rounded-xl text-center">
            <EyeOff className="w-6 h-6 text-text-muted mx-auto mb-1" />
            <span className="text-xs text-text-muted">NSFW</span>
          </div>
        </div>
      )}

      {/* NSFW toggle button */}
      {nsfw && nsfwBlurEnabled && (
        <button
          onClick={handleReveal}
          className={clsx(
            'absolute top-2 right-2 p-1.5 rounded-lg',
            'bg-slate-deep/80 backdrop-blur-sm',
            'text-text-secondary hover:text-text-primary',
            'transition-colors duration-200',
            'z-10',
          )}
        >
          {isRevealed ? (
            <EyeOff className="w-4 h-4" />
          ) : (
            <Eye className="w-4 h-4" />
          )}
        </button>
      )}
    </div>
  )
}

export default MediaPreview
