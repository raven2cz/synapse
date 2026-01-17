/**
 * MediaPreview Component - OPTIMIZED v3
 *
 * CRITICAL PERFORMANCE OPTIMIZATIONS:
 * 1. Video element stays in DOM - no mounting/unmounting on NSFW toggle
 * 2. Video src set only once when first entering viewport (true lazy loading)
 * 3. Uses VideoPlaybackManager to limit concurrent playback (max 3)
 * 4. NSFW is purely visual overlay - doesn't affect video loading/playback
 * 5. Staggered playback prevents thread blocking
 * 
 * This solves:
 * - "Sekání" (stuttering) when multiple videos play
 * - "Failed to Load" appearing on NSFW toggle
 * - Videos not loading at all
 */

import { useState, useRef, useEffect, useCallback, memo, useMemo } from 'react'
import { clsx } from 'clsx'
import { Eye, EyeOff, AlertTriangle, Play, Volume2, VolumeX, Film } from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'
import { VideoPlaybackManager } from '@/lib/media/VideoPlaybackManager'
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

// Generate unique ID for video management
let videoIdCounter = 0
function generateVideoId(): string {
  return `video-${++videoIdCounter}-${Date.now()}`
}

export const MediaPreview = memo(function MediaPreview({
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

  // Stable unique ID for this video instance
  const videoId = useMemo(() => generateVideoId(), [])

  // State
  const [mediaType, setMediaType] = useState<MediaType>(explicitType || 'unknown')
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [isRevealed, setIsRevealed] = useState(false)
  const [isHovering, setIsHovering] = useState(false)
  const [isMuted, setIsMuted] = useState(muted)
  const [hasAudio, setHasAudio] = useState(false)
  const [videoError, setVideoError] = useState(false)
  // Track if video src has been set (lazy loading - only set once)
  const [videoSrcLoaded, setVideoSrcLoaded] = useState(false)

  // Refs
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const hasBeenInViewRef = useRef(false)

  // Computed - NSFW is purely visual
  const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed
  const isVideo = mediaType === 'video' && !videoError

  // Detect media type on mount or src change
  useEffect(() => {
    // Reset state on src change
    setLoadState('idle')
    setVideoError(false)
    setVideoSrcLoaded(false)
    hasBeenInViewRef.current = false

    if (explicitType && explicitType !== 'unknown') {
      setMediaType(explicitType)
      onTypeDetected?.(explicitType)
      return
    }

    const detected = detectMediaType(src)
    setMediaType(detected.type)
    onTypeDetected?.(detected.type)
  }, [src, explicitType, onTypeDetected])

  // Register video with playback manager
  useEffect(() => {
    if (isVideo && videoRef.current) {
      VideoPlaybackManager.register(videoId, videoRef.current)
    }

    return () => {
      VideoPlaybackManager.unregister(videoId)
    }
  }, [videoId, isVideo])

  // Intersection observer for lazy loading AND play/pause
  useEffect(() => {
    if (!containerRef.current) return

    // Clean up previous observer
    if (observerRef.current) {
      observerRef.current.disconnect()
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const isInView = entry.isIntersecting
          const ratio = entry.intersectionRatio

          if (isInView) {
            // Mark as having been in view (for lazy loading)
            if (!hasBeenInViewRef.current) {
              hasBeenInViewRef.current = true
              // Set video src now (lazy loading)
              if (isVideo) {
                setVideoSrcLoaded(true)
              }
            }

            // Request playback with priority based on visibility
            if (isVideo && autoPlay) {
              VideoPlaybackManager.requestPlay(videoId, Math.round(ratio * 100))
            }
          } else {
            // Out of view - pause
            if (isVideo) {
              VideoPlaybackManager.requestPause(videoId)
            }
          }
        })
      },
      {
        threshold: [0, 0.25, 0.5, 0.75, 1.0],
        rootMargin: '100px', // Start loading slightly before visible
      }
    )

    observer.observe(containerRef.current)
    observerRef.current = observer

    return () => {
      observer.disconnect()
    }
  }, [videoId, isVideo, autoPlay])

  // Handle video preview timing (5 second loop unless hovering)
  useEffect(() => {
    if (!isVideo || !videoRef.current) return

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
  }, [isVideo, isHovering, previewDuration])

  // Handlers
  const handleReveal = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsRevealed(!isRevealed)
    // Don't stop video - just toggle visual blur
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
    setVideoError(false)

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
    console.warn(`[MediaPreview] Video failed to load: ${src}`)
    setVideoError(true)
    // Show thumbnail/image fallback
    if (thumbnailSrc) {
      setLoadState('loaded')
    }
  }, [src, thumbnailSrc])

  const handleImageLoad = useCallback(() => {
    setLoadState('loaded')
    if (!isVideo) {
      onMediaLoad?.({
        type: 'image',
      })
    }
  }, [onMediaLoad, isVideo])

  const handleImageError = useCallback(() => {
    if (!isVideo) {
      setLoadState('error')
      onError?.(new Error(`Failed to load media: ${src}`))
    }
  }, [src, onError, isVideo])

  const handleToggleMute = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    const newMuted = !isMuted
    setIsMuted(newMuted)
    if (videoRef.current) {
      videoRef.current.muted = newMuted
    }
  }, [isMuted])

  // Determine what image source to show
  const imageSrc = thumbnailSrc || src

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
      {/* Loading skeleton - only show when truly loading and no content yet */}
      {loadState === 'idle' && !videoSrcLoaded && (
        <div className="absolute inset-0 skeleton" />
      )}

      {/* Error state - only show if not video or video completely failed */}
      {loadState === 'error' && !isVideo && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-deep/50 gap-2">
          <AlertTriangle className="w-8 h-8 text-text-muted" />
          <span className="text-xs text-text-muted">Failed to load</span>
        </div>
      )}

      {/* 
        VIDEO ELEMENT - ALWAYS in DOM when it's a video
        This is critical - don't conditionally mount/unmount based on NSFW or visibility
        Just control src and playback
      */}
      {isVideo && (
        <video
          ref={videoRef}
          // Only set src when has been in view (lazy loading)
          src={videoSrcLoaded ? src : undefined}
          poster={thumbnailSrc}
          muted={isMuted}
          loop={loop}
          playsInline
          preload="none"
          className={clsx(
            'w-full h-full object-cover transition-all duration-200',
            // Blur is purely visual - video keeps playing underneath
            shouldBlur && 'blur-xl scale-110',
          )}
          onLoadedData={handleVideoLoad}
          onError={handleVideoError}
        />
      )}

      {/* Image/thumbnail - show when not a video OR as fallback */}
      {(!isVideo || videoError) && loadState !== 'error' && (
        <img
          src={imageSrc}
          alt={alt}
          loading="lazy"
          className={clsx(
            'w-full h-full object-cover transition-all duration-200',
            loadState === 'idle' && 'opacity-0',
            loadState === 'loaded' && 'opacity-100',
            shouldBlur && 'blur-xl scale-110',
          )}
          onLoad={handleImageLoad}
          onError={handleImageError}
        />
      )}

      {/* Video indicator icon - bottom left */}
      {isVideo && !isHovering && loadState === 'loaded' && !shouldBlur && (
        <div className="absolute bottom-2 left-2 p-1.5 rounded-lg bg-black/60 backdrop-blur-sm">
          {videoError ? (
            <Film className="w-4 h-4 text-white/70" />
          ) : (
            <Play className="w-4 h-4 text-white fill-white" />
          )}
        </div>
      )}

      {/* Audio indicator - only when video has audio and is not blurred */}
      {isVideo && hasAudio && showAudioIndicator && !shouldBlur && !videoError && (
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

      {/* NSFW overlay - purely visual, sits ON TOP of video */}
      {nsfw && nsfwBlurEnabled && !isRevealed && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 backdrop-blur-sm z-10 pointer-events-none">
          <div className="bg-slate-deep/80 backdrop-blur-sm p-3 rounded-xl text-center">
            <EyeOff className="w-6 h-6 text-text-muted mx-auto mb-1" />
            <span className="text-xs text-text-muted">NSFW</span>
          </div>
        </div>
      )}

      {/* NSFW toggle button - always clickable */}
      {nsfw && nsfwBlurEnabled && (
        <button
          onClick={handleReveal}
          className={clsx(
            'absolute top-2 right-2 p-1.5 rounded-lg',
            'bg-slate-deep/80 backdrop-blur-sm',
            'text-text-secondary hover:text-text-primary',
            'transition-colors duration-200',
            'z-20',
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
})

export default MediaPreview
