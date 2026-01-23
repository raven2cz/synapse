/**
 * MediaPreview Component
 *
 * Unified preview for images and videos with Civitai URL transformation.
 *
 * Key insight from CivArchive:
 * - Thumbnail: Use `anim=false` param → actual JPEG/WebP image
 * - Video: Use `transcode=true` + `.mp4` → actual MP4 video
 *
 * This avoids Firefox issues with "fake JPEG" videos from Civitai API.
 * 
 * @module components/ui/MediaPreview
 * @version 2.6.0
 */

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { clsx } from 'clsx'
import { Volume2, VolumeX, EyeOff } from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'

// ============================================================================
// URL Transformation Utilities
// ============================================================================

/**
 * Transform Civitai URL to get static thumbnail (first frame).
 * Uses anim=false parameter which returns actual JPEG/WebP.
 */
function getCivitaiThumbnailUrl(url: string, width: number = 450): string {
  if (!url || !url.includes('civitai.com')) {
    return url
  }

  try {
    const urlObj = new URL(url)
    const pathParts = urlObj.pathname.split('/')

    let paramsIndex = -1
    for (let i = 0; i < pathParts.length; i++) {
      if (pathParts[i].includes('=') || pathParts[i].startsWith('width')) {
        paramsIndex = i
        break
      }
    }

    const newParams = `anim=false,transcode=true,width=${width},optimized=true`

    if (paramsIndex >= 0) {
      pathParts[paramsIndex] = newParams
    } else if (pathParts.length >= 3) {
      pathParts.splice(-1, 0, newParams)
    }

    urlObj.pathname = pathParts.join('/')
    return urlObj.toString()
  } catch {
    return url
  }
}

/**
 * Transform Civitai URL to get optimized video (MP4).
 * Uses transcode=true parameter and .mp4 extension.
 */
function getCivitaiVideoUrl(url: string, width: number = 450): string {
  if (!url || !url.includes('civitai.com')) {
    return url
  }

  try {
    const urlObj = new URL(url)
    const pathParts = urlObj.pathname.split('/')

    let paramsIndex = -1
    for (let i = 0; i < pathParts.length; i++) {
      if (pathParts[i].includes('=') || pathParts[i].startsWith('width')) {
        paramsIndex = i
        break
      }
    }

    const newParams = `transcode=true,width=${width},optimized=true`

    if (paramsIndex >= 0) {
      pathParts[paramsIndex] = newParams
    } else if (pathParts.length >= 3) {
      pathParts.splice(-1, 0, newParams)
    }

    // Ensure .mp4 extension on filename
    const lastIndex = pathParts.length - 1
    if (lastIndex >= 0) {
      const filename = pathParts[lastIndex]
      const baseName = filename.replace(/\.[^.]+$/, '')
      pathParts[lastIndex] = `${baseName}.mp4`
    }

    urlObj.pathname = pathParts.join('/')
    return urlObj.toString()
  } catch {
    return url
  }
}

/**
 * Detect if URL is likely a video based on patterns.
 */
function isLikelyVideo(url: string): boolean {
  if (!url) return false

  const lowerUrl = url.toLowerCase()

  // Explicit video extensions
  if (/\.(mp4|webm|mov|avi|mkv|gif)(\?|$)/i.test(url)) {
    return true
  }

  // Civitai transcode pattern (without anim=false)
  if (lowerUrl.includes('civitai.com') && lowerUrl.includes('transcode=true') && !lowerUrl.includes('anim=false')) {
    return true
  }

  return false
}

// ============================================================================
// Component Props
// ============================================================================

interface MediaPreviewProps {
  /** Source URL (from Civitai API or direct) */
  src: string

  /** Media type hint from backend */
  type?: 'image' | 'video' | 'unknown'

  /** Pre-computed thumbnail URL (optional, will be generated if not provided) */
  thumbnailSrc?: string

  /** NSFW content - show blur overlay */
  nsfw?: boolean

  /** NSFW blur enabled setting (passed from parent for performance) */
  nsfwBlurEnabled?: boolean

  /** Aspect ratio */
  aspectRatio?: 'square' | 'portrait' | 'landscape' | 'auto'

  /** Additional CSS classes */
  className?: string

  /** Alt text for image */
  alt?: string

  /** Auto-play video when in viewport (default: false for stability) */
  autoPlay?: boolean

  /** Play full video on hover (alias: playOnHover) */
  playFullOnHover?: boolean

  /** Play video on hover - alias for playFullOnHover for backward compatibility */
  playOnHover?: boolean

  /** Show play icon overlay on videos */
  showPlayIcon?: boolean

  /** Callback when clicked */
  onClick?: () => void

  /** Callback for image load */
  onLoad?: () => void

  /** Callback for load error */
  onError?: () => void
}

// ============================================================================
// Component
// ============================================================================

export function MediaPreview({
  src,
  type,
  thumbnailSrc: providedThumbnailSrc,
  nsfw = false,
  nsfwBlurEnabled: nsfwBlurEnabledProp,
  aspectRatio = 'auto',
  className,
  alt = '',
  autoPlay = false,
  playFullOnHover: playFullOnHoverProp,
  playOnHover,
  showPlayIcon = false,
  onClick,
  onLoad,
  onError,
}: MediaPreviewProps) {
  // Handle alias: playOnHover is alias for playFullOnHover
  const playFullOnHover = playFullOnHoverProp ?? playOnHover ?? true

  // Use prop if provided, otherwise use selector for efficient re-renders
  const nsfwBlurEnabledStore = useSettingsStore((state) => state.nsfwBlurEnabled)
  const nsfwBlurEnabled = nsfwBlurEnabledProp ?? nsfwBlurEnabledStore

  // State
  const [isHovering, setIsHovering] = useState(false)
  const [isRevealed, setIsRevealed] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [videoLoaded, setVideoLoaded] = useState(false) // Track if video has loaded enough to show
  const [imageError, setImageError] = useState(false)
  const [videoError, setVideoError] = useState(false)
  const [isMuted, setIsMuted] = useState(true)
  const [forceVideoDisplay, setForceVideoDisplay] = useState(false) // Fallback when thumbnail fails

  // Computed: should we blur this content?
  const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed

  // Reset revealed state when NSFW blur is re-enabled
  // This ensures all content becomes blurred again when global toggle turns blur ON
  useEffect(() => {
    if (nsfwBlurEnabled) {
      setIsRevealed(false)
    }
  }, [nsfwBlurEnabled])

  // Refs
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)

  // Determine if this is video content
  const isVideo = useMemo(() => {
    if (type === 'video') return true
    if (type === 'image') return false
    return isLikelyVideo(src)
  }, [src, type])

  // Generate proper URLs
  const thumbnailUrl = useMemo(() => {
    if (providedThumbnailSrc) return providedThumbnailSrc
    if (!src) return ''

    if (src.includes('civitai.com')) {
      return getCivitaiThumbnailUrl(src)
    }

    return src
  }, [src, providedThumbnailSrc])

  const videoUrl = useMemo(() => {
    if (!src || !isVideo) return ''

    if (src.includes('civitai.com')) {
      return getCivitaiVideoUrl(src)
    }

    return src
  }, [src, isVideo])

  // Should we show video element (for playback or fallback)?
  const showVideo = isVideo && (autoPlay || (playFullOnHover && isHovering)) && !videoError
  // Should the video ELEMENT be visible (even if not playing, e.g. for fallback)?
  const isVideoVisible = (showVideo || forceVideoDisplay) && !videoError

  // For local video files, skip the thumbnail image and go straight to video display
  // This prevents trying to load a .mp4 file as an image (which fails silently in some browsers)
  useEffect(() => {
    if (isVideo && thumbnailUrl && !thumbnailUrl.includes('civitai.com')) {
      // Check if thumbnail URL is a video file (local video)
      const isVideoFile = /\.(mp4|webm|mov|avi|mkv)/i.test(thumbnailUrl)
      if (isVideoFile && autoPlay) {
        // Skip thumbnail loading, go straight to video
        setForceVideoDisplay(true)
      }
    }
  }, [isVideo, thumbnailUrl, autoPlay])

  // Handle hover
  const handleMouseEnter = useCallback(() => {
    setIsHovering(true)
  }, [])

  const handleMouseLeave = useCallback(() => {
    setIsHovering(false)
  }, [])

  // Handle video play/pause based on hover (but NOT if it's just fallback)
  useEffect(() => {
    if (!videoRef.current || !isVideo) return

    const video = videoRef.current

    // Play video when:
    // 1. showVideo is true (autoPlay or hover active) AND
    // 2. Either: image is loaded, or we're in fallback mode, or autoPlay is enabled
    // Note: With autoPlay, we should start playing immediately without waiting for thumbnail
    // This fixes playback for local video files where thumbnail may not load
    const shouldPlay = showVideo && (imageLoaded || forceVideoDisplay || autoPlay)

    if (shouldPlay) {
      const playTimer = setTimeout(() => {
        video.play().catch((err) => {
          if (err.name !== 'AbortError') {
            console.debug('[MediaPreview] Video play failed:', err.message)
          }
        })
      }, 50)
      return () => clearTimeout(playTimer)
    } else {
      video.pause()
      // Only reset time if we are not in fallback mode (fallback needs to show frame)
      if (!forceVideoDisplay) {
        video.currentTime = 0
      }
    }
  }, [showVideo, isVideo, imageLoaded, forceVideoDisplay, autoPlay])

  // Handle image load
  const handleImageLoad = useCallback(() => {
    setImageLoaded(true)
    setImageError(false)
    onLoad?.()
  }, [onLoad])

  // Handle image error
  const handleImageError = useCallback(() => {
    if (isVideo) {
      console.warn('[MediaPreview] Thumbnail failed for video, using video element fallback')
      setForceVideoDisplay(true)
      // We do NOT set imageError(true) because we are handling it gracefully
      return
    }

    console.warn('[MediaPreview] Image load failed:', thumbnailUrl?.substring(0, 50))
    setImageError(true)
    onError?.()
  }, [onError, thumbnailUrl, isVideo])

  // Handle video loaded data (first frame ready)
  const handleVideoLoadedData = useCallback(() => {
    setVideoLoaded(true)
    setVideoError(false)
  }, [])

  // Handle video error - fallback to image only
  const handleVideoError = useCallback(() => {
    console.debug('[MediaPreview] Video failed to load, showing thumbnail only')
    setVideoError(true)
    // If we were forcing video display, we must stop now or we get nothing
    if (forceVideoDisplay) {
      setForceVideoDisplay(false)
      setImageError(true) // Now it's a real error since both failed
    }
  }, [forceVideoDisplay])

  // Handle NSFW reveal toggle
  const handleRevealToggle = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsRevealed((prev) => !prev)
  }, [])

  // Handle mute toggle
  const handleMuteToggle = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsMuted((prev) => !prev)
    if (videoRef.current) {
      videoRef.current.muted = !isMuted
    }
  }, [isMuted])

  // Aspect ratio classes
  const aspectClasses = {
    square: 'aspect-square',
    portrait: 'aspect-[3/4]',
    landscape: 'aspect-video',
    auto: '',
  }

  return (
    <div
      ref={containerRef}
      className={clsx(
        'group relative overflow-hidden bg-slate-800',
        aspectClasses[aspectRatio],
        className
      )}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
    >
      {/* Thumbnail Image - Always rendered for stability */}
      {thumbnailUrl ? (
        <img
          src={thumbnailUrl}
          alt={alt}
          className={clsx(
            'absolute inset-0 w-full h-full object-cover',
            'transition-all duration-500 ease-out',
            isVideoVisible ? 'opacity-0 scale-105' : 'opacity-100',
            !isVideoVisible && 'group-hover:scale-110 group-hover:brightness-110',
            shouldBlur && 'blur-xl scale-110'
          )}
          loading="lazy"
          onLoad={handleImageLoad}
          onError={handleImageError}
        />
      ) : (
        /* Empty state placeholder when no URL is present */
        <div className={clsx(
          'absolute inset-0 flex items-center justify-center bg-slate-800 text-slate-600',
          shouldBlur && 'blur-xl'
        )}>
          <svg className="w-12 h-12 opacity-20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
      )}

      {/* Video Element - Only rendered when needed */}
      {isVideo && !videoError && (
        <video
          ref={videoRef}
          src={isVideoVisible ? videoUrl : undefined}
          className={clsx(
            'absolute inset-0 w-full h-full object-cover',
            'transition-all duration-500 ease-out',
            isVideoVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-95',
            shouldBlur && 'blur-xl scale-110'
          )}
          loop
          muted={isMuted}
          playsInline
          autoPlay={autoPlay && isVideoVisible}
          preload={isVideoVisible || forceVideoDisplay ? "auto" : "none"}
          onLoadedData={handleVideoLoadedData}
          onError={handleVideoError}
        />
      )}

      {/* Loading placeholder - Shown when image loading or video fallback loading */}
      {(!imageLoaded && !imageError && !forceVideoDisplay) || (forceVideoDisplay && !videoLoaded) ? (
        <div className="absolute inset-0 bg-slate-700" />
      ) : null}

      {/* Error state */}
      {imageError && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-800 text-slate-500">
          <span className="text-sm">Failed to load</span>
        </div>
      )}

      {/* NSFW Blur Overlay - centered indicator */}
      {nsfw && nsfwBlurEnabled && !isRevealed && (
        <div
          className={clsx(
            'absolute inset-0 flex flex-col items-center justify-center',
            'transition-opacity duration-300 pointer-events-none'
          )}
        >
          <div className="bg-slate-900/90 p-3 rounded-xl text-center shadow-lg">
            <EyeOff className="w-6 h-6 text-slate-400 mx-auto mb-1" />
            <span className="text-xs text-slate-400">NSFW</span>
          </div>
        </div>
      )}

      {/* NSFW Toggle Button - ONLY visible when card is revealed */}
      {nsfw && nsfwBlurEnabled && isRevealed && (
        <button
          onClick={handleRevealToggle}
          className={clsx(
            'absolute top-2 right-2 p-1.5 rounded-lg z-20',
            'bg-slate-900/90',
            'text-slate-400 hover:text-white',
            'transition-colors duration-200'
          )}
          title="Hide content"
        >
          <EyeOff className="w-4 h-4" />
        </button>
      )}

      {/* Clickable reveal area when blurred */}
      {nsfw && nsfwBlurEnabled && !isRevealed && (
        <button
          onClick={handleRevealToggle}
          className="absolute inset-0 z-10 cursor-pointer"
          title="Click to reveal"
        />
      )}

      {/* NSFW Badge - shown when blur is disabled globally */}
      {nsfw && !nsfwBlurEnabled && (
        <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-red-500/80 text-white text-xs font-medium z-20">
          NSFW
        </div>
      )}

      {/* Play icon overlay for videos - shown when showPlayIcon is true and not playing */}
      {isVideo && showPlayIcon && !showVideo && !videoError && !shouldBlur && (
        <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
          <div className="w-12 h-12 rounded-full bg-black/50 flex items-center justify-center">
            <svg className="w-6 h-6 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
        </div>
      )}

      {/* Video indicator badge - bottom left */}
      {isVideo && !showVideo && !videoError && (
        <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded-md z-10">
          VIDEO
        </div>
      )}

      {/* Audio control for videos */}
      {isVideo && showVideo && !videoError && (
        <button
          className="absolute bottom-2 right-2 p-1.5 rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors z-10"
          onClick={handleMuteToggle}
          title={isMuted ? 'Unmute' : 'Mute'}
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </button>
      )}
    </div>
  )
}

export default MediaPreview
