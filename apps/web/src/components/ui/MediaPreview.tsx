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
 */

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { Volume2, VolumeX } from 'lucide-react'

// Simple className merge utility (inline to avoid dependency)
function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ')
}

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
    // Parse URL and reconstruct with correct params
    const urlObj = new URL(url)
    const pathParts = urlObj.pathname.split('/')

    // Find and replace params segment (contains = signs)
    // Format: /{uuid}/{params}/{filename}
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
      // Insert before filename
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

    // Find params segment
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
      // Replace extension with .mp4
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

  /** Aspect ratio */
  aspectRatio?: 'square' | 'portrait' | 'landscape' | 'auto'

  /** Additional CSS classes */
  className?: string

  /** Alt text for image */
  alt?: string

  /** Auto-play video when in viewport (default: false for stability) */
  autoPlay?: boolean

  /** Play full video on hover */
  playFullOnHover?: boolean

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
  aspectRatio = 'auto',
  className,
  alt = '',
  autoPlay = false,
  playFullOnHover = true,
  onClick,
  onLoad,
  onError,
}: MediaPreviewProps) {
  // State
  const [isHovering, setIsHovering] = useState(false)
  const [showNsfw, setShowNsfw] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageError, setImageError] = useState(false)
  const [videoError, setVideoError] = useState(false)
  const [isMuted, setIsMuted] = useState(true)

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

    // For Civitai, always get static thumbnail with anim=false
    if (src.includes('civitai.com')) {
      return getCivitaiThumbnailUrl(src)
    }

    return src
  }, [src, providedThumbnailSrc])

  const videoUrl = useMemo(() => {
    if (!src || !isVideo) return ''

    // For Civitai, get proper MP4 URL
    if (src.includes('civitai.com')) {
      return getCivitaiVideoUrl(src)
    }

    return src
  }, [src, isVideo])

  // Should we show video element?
  const showVideo = isVideo && (autoPlay || (playFullOnHover && isHovering)) && !videoError

  // Handle hover
  const handleMouseEnter = useCallback(() => {
    setIsHovering(true)
  }, [])

  const handleMouseLeave = useCallback(() => {
    setIsHovering(false)
  }, [])

  // Handle video play/pause based on hover
  useEffect(() => {
    if (!videoRef.current || !isVideo) return

    const video = videoRef.current

    if (showVideo && imageLoaded) {
      // Small delay to let video element mount
      const playTimer = setTimeout(() => {
        video.play().catch((err) => {
          if (err.name !== 'AbortError') {
            console.debug('Video play failed:', err.message)
          }
        })
      }, 50)
      return () => clearTimeout(playTimer)
    } else {
      video.pause()
      video.currentTime = 0
    }
  }, [showVideo, isVideo, imageLoaded])

  // Handle image load
  const handleImageLoad = useCallback(() => {
    setImageLoaded(true)
    setImageError(false)
    onLoad?.()
  }, [onLoad])

  // Handle image error
  const handleImageError = useCallback(() => {
    setImageError(true)
    onError?.()
  }, [onError])

  // Handle video error - fallback to image only
  const handleVideoError = useCallback(() => {
    console.debug('Video failed to load, showing thumbnail only:', videoUrl)
    setVideoError(true)
  }, [videoUrl])

  // Handle NSFW reveal
  const handleNsfwReveal = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setShowNsfw(true)
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
      className={cn(
        'group relative overflow-hidden bg-slate-800',
        aspectClasses[aspectRatio],
        className
      )}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
    >
      {/* Thumbnail Image - Always rendered for stability */}
      <img
        src={thumbnailUrl}
        alt={alt}
        className={cn(
          'absolute inset-0 w-full h-full object-cover transition-all duration-300',
          showVideo && !videoError ? 'opacity-0' : 'opacity-100',
          !showVideo && 'group-hover:scale-105'
        )}
        loading="lazy"
        onLoad={handleImageLoad}
        onError={handleImageError}
      />

      {/* Video Element - Only rendered when needed */}
      {isVideo && !videoError && (
        <video
          ref={videoRef}
          src={showVideo ? videoUrl : undefined}
          className={cn(
            'absolute inset-0 w-full h-full object-cover transition-opacity duration-200',
            showVideo ? 'opacity-100' : 'opacity-0'
          )}
          loop
          muted={isMuted}
          playsInline
          preload="none"
          onError={handleVideoError}
        />
      )}

      {/* Loading placeholder */}
      {!imageLoaded && !imageError && (
        <div className="absolute inset-0 bg-slate-700 animate-pulse" />
      )}

      {/* Error state */}
      {imageError && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-800 text-slate-500">
          <span className="text-sm">Failed to load</span>
        </div>
      )}

      {/* NSFW Blur Overlay */}
      {nsfw && !showNsfw && (
        <div
          className="absolute inset-0 backdrop-blur-xl bg-black/30 flex items-center justify-center cursor-pointer z-10"
          onClick={handleNsfwReveal}
        >
          <span className="text-white/80 text-sm font-medium px-3 py-1.5 rounded-full bg-black/40">
            NSFW - Click to reveal
          </span>
        </div>
      )}

      {/* Video indicator badge */}
      {isVideo && !showVideo && !videoError && (
        <div className="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded-md z-5">
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
