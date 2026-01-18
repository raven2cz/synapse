/**
 * ModelCard Component
 *
 * Optimized card for displaying models in browse grid.
 * Designed for maximum performance with thumbnail-first rendering.
 *
 * Key features:
 * - Instant thumbnail display (no blocking)
 * - Video preview on hover only
 * - Minimal re-renders via memoization
 * - Consistent with Civitai's card design
 *
 * @author Synapse Team
 */

import { memo, useCallback, useState, useRef, useEffect } from 'react'
import { clsx } from 'clsx'
import {
  Download,
  Heart,
  MessageSquare,
  Link2,
  ThumbsUp,
  Play,
  Eye,
  EyeOff,
  Volume2,
  VolumeX,
} from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'
import { detectMediaType } from '@/lib/media'
import type { MediaType } from '@/lib/media'

// ============================================================================
// Types
// ============================================================================

export interface ModelPreview {
  url: string
  nsfw: boolean
  width?: number
  height?: number
  media_type?: MediaType
  thumbnail_url?: string
}

export interface ModelCardProps {
  id: number
  name: string
  type: string
  creator?: string
  nsfw: boolean
  preview?: ModelPreview
  baseModel?: string
  stats?: {
    downloadCount?: number
    favoriteCount?: number
    commentCount?: number
    thumbsUpCount?: number
    rating?: number
  }
  width?: number
  onClick?: () => void
  onCopyLink?: () => void
}

// ============================================================================
// Helper: Format number
// ============================================================================

function formatNumber(n?: number): string {
  if (!n) return '0'
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toString()
}

// ============================================================================
// Component
// ============================================================================

export const ModelCard = memo(function ModelCard({
  id,
  name,
  type,
  creator,
  nsfw,
  preview,
  baseModel,
  stats,
  width = 300,
  onClick,
  onCopyLink,
}: ModelCardProps) {
  const { nsfwBlurEnabled } = useSettingsStore()

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const [isHovering, setIsHovering] = useState(false)
  const [isRevealed, setIsRevealed] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [videoLoaded, setVideoLoaded] = useState(false)
  const [isMuted, setIsMuted] = useState(true)

  // ---------------------------------------------------------------------------
  // Refs
  // ---------------------------------------------------------------------------
  const videoRef = useRef<HTMLVideoElement>(null)
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ---------------------------------------------------------------------------
  // Computed
  // ---------------------------------------------------------------------------
  const mediaType = preview?.media_type || detectMediaType(preview?.url || '').type
  const isVideo = mediaType === 'video'
  const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed
  const thumbnailUrl = preview?.thumbnail_url || (isVideo ? '' : preview?.url) || ''
  const videoUrl = preview?.url || ''

  // Show video when hovering AND video is loaded
  const showVideo = isVideo && isHovering && videoLoaded && !shouldBlur

  // ---------------------------------------------------------------------------
  // Effects
  // ---------------------------------------------------------------------------

  // Handle video play/pause
  useEffect(() => {
    const video = videoRef.current
    if (!video || !isVideo) return

    if (showVideo) {
      video.currentTime = 0
      video.play().catch(() => {})
    } else {
      video.pause()
    }
  }, [showVideo, isVideo])

  // Cleanup
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
    // Small delay to prevent accidental triggers
    hoverTimeoutRef.current = setTimeout(() => {
      setIsHovering(true)
    }, 100)
  }, [])

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

  const handleCopyLink = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onCopyLink?.()
    },
    [onCopyLink]
  )

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

  return (
    <div
      onClick={onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="group cursor-pointer"
      style={{ width }}
    >
      {/* Card container */}
      <div className="relative aspect-[3/4] rounded-2xl overflow-hidden bg-slate-dark">
        {/* Loading skeleton */}
        {!imageLoaded && (
          <div className="absolute inset-0 skeleton" />
        )}

        {/* Thumbnail image - ALWAYS rendered first */}
        {thumbnailUrl && (
          <img
            src={thumbnailUrl}
            alt={name}
            loading="lazy"
            decoding="async"
            className={clsx(
              'w-full h-full object-cover transition-all duration-300',
              'group-hover:scale-105',
              !imageLoaded && 'opacity-0',
              imageLoaded && 'opacity-100',
              showVideo && 'opacity-0',
              shouldBlur && 'blur-xl scale-110'
            )}
            onLoad={() => setImageLoaded(true)}
            onError={() => setImageLoaded(true)} // Mark as loaded even on error to hide skeleton
          />
        )}

        {/* Fallback for no thumbnail */}
        {!thumbnailUrl && imageLoaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-mid">
            <span className="text-text-muted text-sm">No preview</span>
          </div>
        )}

        {/* Video element - loads on hover */}
        {isVideo && isHovering && (
          <video
            ref={videoRef}
            src={videoUrl}
            muted={isMuted}
            loop
            playsInline
            preload="metadata"
            className={clsx(
              'absolute inset-0 w-full h-full object-cover transition-opacity duration-300',
              'group-hover:scale-105',
              showVideo ? 'opacity-100' : 'opacity-0 pointer-events-none',
              shouldBlur && 'blur-xl scale-110'
            )}
            onLoadedData={() => setVideoLoaded(true)}
            onError={() => setVideoLoaded(false)}
          />
        )}

        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent pointer-events-none" />

        {/* Top left badges */}
        <div className="absolute top-3 left-3 flex gap-1.5 z-10">
          <span className="px-2 py-1 bg-black/60 backdrop-blur-sm rounded-lg text-xs text-white font-semibold">
            {type}
          </span>
          {baseModel && (
            <span className="px-2 py-1 bg-black/60 backdrop-blur-sm rounded-lg text-xs text-white/80">
              {baseModel.replace('SD ', '').replace('SDXL ', 'XL ')}
            </span>
          )}
        </div>

        {/* Top right actions */}
        <div className="absolute top-3 right-3 flex gap-1.5 z-10">
          {/* Copy link button */}
          {onCopyLink && (
            <button
              className="p-1.5 bg-white/90 hover:bg-white rounded-full transition-colors"
              onClick={handleCopyLink}
            >
              <Link2 className="w-4 h-4 text-slate-700" />
            </button>
          )}
        </div>

        {/* Video play indicator */}
        {isVideo && !isHovering && imageLoaded && !shouldBlur && (
          <div className="absolute bottom-12 left-3 p-1.5 rounded-lg bg-black/60 backdrop-blur-sm pointer-events-none z-10">
            <Play className="w-4 h-4 text-white fill-white" />
          </div>
        )}

        {/* Video mute toggle */}
        {isVideo && isHovering && videoLoaded && !shouldBlur && (
          <button
            onClick={handleToggleMute}
            className="absolute bottom-12 right-3 p-1.5 rounded-lg bg-black/60 backdrop-blur-sm text-white hover:bg-black/80 transition-colors z-10"
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
        )}

        {/* NSFW overlay */}
        {nsfw && nsfwBlurEnabled && !isRevealed && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
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
            className="absolute top-3 right-12 p-1.5 rounded-lg bg-slate-deep/80 backdrop-blur-sm text-text-secondary hover:text-text-primary transition-colors z-20"
          >
            {isRevealed ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}

        {/* Bottom content */}
        <div className="absolute bottom-0 left-0 right-0 p-3 space-y-2 z-10">
          {/* Creator row */}
          {creator && (
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-synapse to-pulse flex items-center justify-center text-white text-xs font-bold">
                {creator.charAt(0).toUpperCase()}
              </div>
              <span className="text-sm text-white/90 font-medium">{creator}</span>
            </div>
          )}

          {/* Title */}
          <h3 className="font-bold text-white text-sm leading-tight line-clamp-2">{name}</h3>

          {/* Stats row */}
          <div className="flex items-center gap-3 text-xs text-white/70">
            <span className="flex items-center gap-1">
              <Download className="w-3.5 h-3.5" />
              {formatNumber(stats?.downloadCount)}
            </span>
            <span className="flex items-center gap-1">
              <MessageSquare className="w-3.5 h-3.5" />
              {formatNumber(stats?.commentCount)}
            </span>
            <span className="flex items-center gap-1">
              <Heart className="w-3.5 h-3.5" />
              {formatNumber(stats?.favoriteCount)}
            </span>
            {(stats?.thumbsUpCount || stats?.rating) && (
              <span className="flex items-center gap-1 ml-auto bg-white/20 px-2 py-0.5 rounded-full">
                <ThumbsUp className="w-3 h-3" />
                {stats.thumbsUpCount || Math.round((stats.rating || 0) * 20)}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
})

export default ModelCard
