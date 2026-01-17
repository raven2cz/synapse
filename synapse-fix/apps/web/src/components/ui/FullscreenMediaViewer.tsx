/**
 * FullscreenMediaViewer Component - Optimized Version
 *
 * Modal viewer for images and videos in fullscreen.
 * Designed for seamless navigation and immediate response.
 *
 * Key features:
 * - Image zoom and pan
 * - Video player with full controls
 * - Keyboard navigation
 * - NSFW content handling
 * - Preloading adjacent items
 *
 * @author Synapse Team
 */

import { useState, useEffect, useCallback, useRef, memo } from 'react'
import { createPortal } from 'react-dom'
import { clsx } from 'clsx'
import {
  X,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Eye,
  EyeOff,
  ZoomIn,
  ZoomOut,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  SkipBack,
  SkipForward,
} from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'
import { detectMediaType } from '@/lib/media'
import type { MediaType } from '@/lib/media'

// ============================================================================
// Types
// ============================================================================

export interface MediaItem {
  url: string
  type?: MediaType
  thumbnailUrl?: string
  nsfw?: boolean
  width?: number
  height?: number
  meta?: Record<string, any>
}

export interface FullscreenMediaViewerProps {
  /** Array of media items */
  items: MediaItem[]
  /** Initial index to display */
  initialIndex?: number
  /** Whether viewer is open */
  isOpen: boolean
  /** Close handler */
  onClose: () => void
  /** Callback when index changes */
  onIndexChange?: (index: number) => void
}

// ============================================================================
// Helper: Format time
// ============================================================================

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ============================================================================
// Inline Video Player (simplified for fullscreen)
// ============================================================================

interface InlineVideoPlayerProps {
  src: string
  poster?: string
  className?: string
}

const InlineVideoPlayer = memo(function InlineVideoPlayer({
  src,
  poster,
  className,
}: InlineVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)

  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [showControls, setShowControls] = useState(true)
  const [isLoaded, setIsLoaded] = useState(false)

  const controlsTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  // Auto-hide controls
  const resetControlsTimeout = useCallback(() => {
    if (controlsTimeoutRef.current) {
      clearTimeout(controlsTimeoutRef.current)
    }
    setShowControls(true)
    if (isPlaying) {
      controlsTimeoutRef.current = setTimeout(() => setShowControls(false), 3000)
    }
  }, [isPlaying])

  // Video event listeners
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const onPlay = () => setIsPlaying(true)
    const onPause = () => setIsPlaying(false)
    const onTimeUpdate = () => setCurrentTime(video.currentTime)
    const onDurationChange = () => setDuration(video.duration)
    const onLoadedData = () => setIsLoaded(true)

    video.addEventListener('play', onPlay)
    video.addEventListener('pause', onPause)
    video.addEventListener('timeupdate', onTimeUpdate)
    video.addEventListener('durationchange', onDurationChange)
    video.addEventListener('loadeddata', onLoadedData)

    return () => {
      video.removeEventListener('play', onPlay)
      video.removeEventListener('pause', onPause)
      video.removeEventListener('timeupdate', onTimeUpdate)
      video.removeEventListener('durationchange', onDurationChange)
      video.removeEventListener('loadeddata', onLoadedData)
    }
  }, [])

  // Cleanup
  useEffect(() => {
    return () => {
      if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
    }
  }, [])

  const togglePlay = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    if (isPlaying) {
      video.pause()
    } else {
      video.play().catch(() => {})
    }
    resetControlsTimeout()
  }, [isPlaying, resetControlsTimeout])

  const toggleMute = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    video.muted = !isMuted
    setIsMuted(!isMuted)
  }, [isMuted])

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const video = videoRef.current
    const bar = progressRef.current
    if (!video || !bar) return

    const rect = bar.getBoundingClientRect()
    const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    video.currentTime = pos * video.duration
  }, [])

  const skip = useCallback((seconds: number) => {
    const video = videoRef.current
    if (!video) return
    video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + seconds))
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      switch (e.key) {
        case ' ':
          e.preventDefault()
          togglePlay()
          break
        case 'm':
          toggleMute()
          break
        case 'ArrowLeft':
          skip(-5)
          break
        case 'ArrowRight':
          skip(5)
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [togglePlay, toggleMute, skip])

  return (
    <div
      className={clsx('relative bg-black group', className)}
      onMouseMove={resetControlsTimeout}
      onMouseLeave={() => isPlaying && setShowControls(false)}
    >
      {/* Video */}
      <video
        ref={videoRef}
        src={src}
        poster={poster}
        autoPlay
        playsInline
        className="w-full h-full object-contain"
        onClick={togglePlay}
      />

      {/* Loading indicator */}
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-white/30 border-t-white rounded-full animate-spin" />
        </div>
      )}

      {/* Play button overlay (when paused) */}
      {!isPlaying && isLoaded && (
        <div
          className="absolute inset-0 flex items-center justify-center cursor-pointer"
          onClick={togglePlay}
        >
          <div className="p-4 rounded-full bg-black/50 backdrop-blur-sm hover:bg-black/70 transition-colors">
            <Play className="w-12 h-12 text-white fill-white" />
          </div>
        </div>
      )}

      {/* Controls overlay */}
      <div
        className={clsx(
          'absolute bottom-0 left-0 right-0 p-4',
          'bg-gradient-to-t from-black/80 to-transparent',
          'transition-opacity duration-300',
          showControls ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
      >
        {/* Progress bar */}
        <div
          ref={progressRef}
          className="relative h-1 bg-white/30 rounded-full mb-3 cursor-pointer group/progress"
          onClick={handleSeek}
        >
          <div
            className="absolute inset-y-0 left-0 bg-synapse rounded-full"
            style={{ width: `${progress}%` }}
          />
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full opacity-0 group-hover/progress:opacity-100 transition-opacity"
            style={{ left: `calc(${progress}% - 6px)` }}
          />
        </div>

        {/* Control buttons */}
        <div className="flex items-center gap-3">
          <button onClick={togglePlay} className="p-1.5 text-white hover:text-synapse transition-colors">
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
          </button>

          <button onClick={() => skip(-5)} className="p-1.5 text-white/70 hover:text-white transition-colors">
            <SkipBack className="w-4 h-4" />
          </button>

          <button onClick={() => skip(5)} className="p-1.5 text-white/70 hover:text-white transition-colors">
            <SkipForward className="w-4 h-4" />
          </button>

          <button onClick={toggleMute} className="p-1.5 text-white hover:text-synapse transition-colors">
            {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
          </button>

          <span className="text-white/70 text-sm ml-2">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
        </div>
      </div>
    </div>
  )
})

// ============================================================================
// Main Component
// ============================================================================

export const FullscreenMediaViewer = memo(function FullscreenMediaViewer({
  items,
  initialIndex = 0,
  isOpen,
  onClose,
  onIndexChange,
}: FullscreenMediaViewerProps) {
  const { nsfwBlurEnabled } = useSettingsStore()

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const [currentIndex, setCurrentIndex] = useState(initialIndex)
  const [isRevealed, setIsRevealed] = useState(false)
  const [imageZoom, setImageZoom] = useState(1)
  const [imagePosition, setImagePosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [imageLoaded, setImageLoaded] = useState(false)

  // Current item
  const currentItem = items[currentIndex]
  const mediaType = currentItem?.type || detectMediaType(currentItem?.url || '').type
  const isVideo = mediaType === 'video'
  const shouldBlur = currentItem?.nsfw && nsfwBlurEnabled && !isRevealed

  // ---------------------------------------------------------------------------
  // Effects
  // ---------------------------------------------------------------------------

  // Reset state when opening or changing initial index
  useEffect(() => {
    if (isOpen) {
      setCurrentIndex(initialIndex)
      setIsRevealed(false)
      setImageZoom(1)
      setImagePosition({ x: 0, y: 0 })
      setImageLoaded(false)
    }
  }, [isOpen, initialIndex])

  // Reset when changing items
  useEffect(() => {
    setIsRevealed(false)
    setImageZoom(1)
    setImagePosition({ x: 0, y: 0 })
    setImageLoaded(false)
  }, [currentIndex])

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          onClose()
          break
        case 'ArrowLeft':
          if (!isVideo) goToPrevious()
          break
        case 'ArrowRight':
          if (!isVideo) goToNext()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isVideo, currentIndex, items.length])

  // Preload adjacent images
  useEffect(() => {
    if (!isOpen) return

    const preloadIndices = [currentIndex - 1, currentIndex + 1].filter(
      (i) => i >= 0 && i < items.length
    )

    preloadIndices.forEach((i) => {
      const item = items[i]
      const type = item?.type || detectMediaType(item?.url || '').type
      if (type !== 'video' && item?.url) {
        const img = new Image()
        img.src = item.url
      }
    })
  }, [isOpen, currentIndex, items])

  // ---------------------------------------------------------------------------
  // Navigation
  // ---------------------------------------------------------------------------

  const goToPrevious = useCallback(() => {
    if (currentIndex > 0) {
      const newIndex = currentIndex - 1
      setCurrentIndex(newIndex)
      onIndexChange?.(newIndex)
    }
  }, [currentIndex, onIndexChange])

  const goToNext = useCallback(() => {
    if (currentIndex < items.length - 1) {
      const newIndex = currentIndex + 1
      setCurrentIndex(newIndex)
      onIndexChange?.(newIndex)
    }
  }, [currentIndex, items.length, onIndexChange])

  // ---------------------------------------------------------------------------
  // Image drag handlers
  // ---------------------------------------------------------------------------

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (isVideo || imageZoom <= 1) return
      e.preventDefault()
      setIsDragging(true)
      setDragStart({ x: e.clientX - imagePosition.x, y: e.clientY - imagePosition.y })
    },
    [isVideo, imageZoom, imagePosition]
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) return
      setImagePosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      })
    },
    [isDragging, dragStart]
  )

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      if (isVideo) return
      e.preventDefault()
      const delta = e.deltaY > 0 ? -0.1 : 0.1
      setImageZoom((z) => Math.max(0.5, Math.min(4, z + delta)))
    },
    [isVideo]
  )

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  const handleDownload = useCallback(() => {
    if (!currentItem?.url) return
    const a = document.createElement('a')
    a.href = currentItem.url
    a.download = currentItem.url.split('/').pop() || 'download'
    a.target = '_blank'
    a.click()
  }, [currentItem])

  const handleOpenExternal = useCallback(() => {
    if (!currentItem?.url) return
    window.open(currentItem.url, '_blank')
  }, [currentItem])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!isOpen || !currentItem) return null

  const content = (
    <div className="fixed inset-0 z-50 bg-black/95 backdrop-blur-sm" onClick={onClose}>
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between p-4 bg-gradient-to-b from-black/80 to-transparent">
        {/* Counter */}
        <div className="text-white/70 text-sm">{currentIndex + 1} / {items.length}</div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* NSFW toggle */}
          {currentItem.nsfw && nsfwBlurEnabled && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                setIsRevealed(!isRevealed)
              }}
              className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
              title={isRevealed ? 'Hide content' : 'Reveal content'}
            >
              {isRevealed ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          )}

          {/* Zoom controls (images only) */}
          {!isVideo && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setImageZoom((z) => Math.max(0.5, z - 0.25))
                }}
                className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
              >
                <ZoomOut className="w-5 h-5" />
              </button>
              <span className="text-white/70 text-sm min-w-[3rem] text-center">
                {Math.round(imageZoom * 100)}%
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setImageZoom((z) => Math.min(4, z + 0.25))
                }}
                className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
              >
                <ZoomIn className="w-5 h-5" />
              </button>
            </>
          )}

          {/* Download */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              handleDownload()
            }}
            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
          >
            <Download className="w-5 h-5" />
          </button>

          {/* External link */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              handleOpenExternal()
            }}
            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
          >
            <ExternalLink className="w-5 h-5" />
          </button>

          {/* Close */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              onClose()
            }}
            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Navigation arrows */}
      {items.length > 1 && (
        <>
          <button
            onClick={(e) => {
              e.stopPropagation()
              goToPrevious()
            }}
            disabled={currentIndex === 0}
            className={clsx(
              'absolute left-4 top-1/2 -translate-y-1/2 z-10',
              'p-3 rounded-full bg-white/10 hover:bg-white/20 text-white',
              'transition-all duration-200',
              currentIndex === 0 && 'opacity-30 cursor-not-allowed'
            )}
          >
            <ChevronLeft className="w-8 h-8" />
          </button>

          <button
            onClick={(e) => {
              e.stopPropagation()
              goToNext()
            }}
            disabled={currentIndex === items.length - 1}
            className={clsx(
              'absolute right-4 top-1/2 -translate-y-1/2 z-10',
              'p-3 rounded-full bg-white/10 hover:bg-white/20 text-white',
              'transition-all duration-200',
              currentIndex === items.length - 1 && 'opacity-30 cursor-not-allowed'
            )}
          >
            <ChevronRight className="w-8 h-8" />
          </button>
        </>
      )}

      {/* Content area */}
      <div
        className="absolute inset-0 flex items-center justify-center pt-16 pb-4 px-16"
        onClick={(e) => e.stopPropagation()}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        {/* NSFW blur overlay */}
        {shouldBlur && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50 backdrop-blur-2xl z-10">
            <div className="text-center">
              <EyeOff className="w-16 h-16 text-white/50 mx-auto mb-4" />
              <p className="text-white/70 text-lg mb-4">NSFW Content</p>
              <button
                onClick={() => setIsRevealed(true)}
                className="px-6 py-2 rounded-lg bg-synapse hover:bg-synapse/80 text-white transition-colors"
              >
                Click to reveal
              </button>
            </div>
          </div>
        )}

        {/* Video player */}
        {isVideo && !shouldBlur && (
          <div className="w-full h-full max-w-6xl max-h-full">
            <InlineVideoPlayer
              src={currentItem.url}
              poster={currentItem.thumbnailUrl}
              className="w-full h-full"
            />
          </div>
        )}

        {/* Image viewer */}
        {!isVideo && !shouldBlur && (
          <>
            {/* Loading indicator */}
            {!imageLoaded && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-12 h-12 border-4 border-white/30 border-t-white rounded-full animate-spin" />
              </div>
            )}
            <img
              src={currentItem.url}
              alt="Preview"
              className={clsx(
                'max-w-full max-h-full object-contain transition-all duration-200',
                isDragging && 'cursor-grabbing',
                imageZoom > 1 && !isDragging && 'cursor-grab',
                !imageLoaded && 'opacity-0'
              )}
              style={{
                transform: `scale(${imageZoom}) translate(${imagePosition.x / imageZoom}px, ${imagePosition.y / imageZoom}px)`,
              }}
              draggable={false}
              onLoad={() => setImageLoaded(true)}
            />
          </>
        )}
      </div>

      {/* Metadata panel */}
      {currentItem.meta && Object.keys(currentItem.meta).length > 0 && (
        <div className="absolute bottom-0 left-0 right-0 z-10 p-4 bg-gradient-to-t from-black/80 to-transparent pointer-events-none">
          <div className="max-w-2xl mx-auto">
            {currentItem.meta.prompt && (
              <p className="text-white/70 text-sm line-clamp-2">{currentItem.meta.prompt}</p>
            )}
          </div>
        </div>
      )}
    </div>
  )

  // Render via portal for proper z-index stacking
  return createPortal(content, document.body)
})

export default FullscreenMediaViewer
