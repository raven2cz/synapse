/**
 * FullscreenMediaViewer Component
 *
 * Modal overlay for viewing media in fullscreen.
 * Supports both images and videos with navigation.
 *
 * Features:
 * - Image zoom and pan
 * - Video player with full controls and audio
 * - Loop toggle for videos
 * - Keyboard navigation (arrows, escape)
 * - Previous/Next navigation
 * - NSFW blur support
 */

import { useState, useEffect, useCallback, useRef } from 'react'
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
  Repeat,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
} from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'

// URL transformation utilities (same as MediaPreview)
function getCivitaiVideoUrl(url: string, width: number = 1080): string {
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

    // Ensure .mp4 extension
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

function isLikelyVideo(url: string): boolean {
  if (!url) return false
  const lowerUrl = url.toLowerCase()
  if (/\.(mp4|webm|mov|avi|mkv|gif)(\?|$)/i.test(url)) return true
  if (lowerUrl.includes('civitai.com') && lowerUrl.includes('transcode=true') && !lowerUrl.includes('anim=false')) return true
  return false
}

export interface MediaItem {
  url: string
  type?: 'image' | 'video' | 'unknown'
  thumbnailUrl?: string
  nsfw?: boolean
  width?: number
  height?: number
  meta?: Record<string, any>
}

export interface FullscreenMediaViewerProps {
  items: MediaItem[]
  initialIndex?: number
  isOpen: boolean
  onClose: () => void
  onIndexChange?: (index: number) => void
}

export function FullscreenMediaViewer({
  items,
  initialIndex = 0,
  isOpen,
  onClose,
  onIndexChange,
}: FullscreenMediaViewerProps) {
  const { nsfwBlurEnabled } = useSettingsStore()

  // State
  const [currentIndex, setCurrentIndex] = useState(initialIndex)
  const [isRevealed, setIsRevealed] = useState(false)
  const [imageZoom, setImageZoom] = useState(1)
  const [imagePosition, setImagePosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

  // Video state
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLooping, setIsLooping] = useState(true)
  const [isMuted, setIsMuted] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null)

  // Current item
  const currentItem = items[currentIndex]
  const isVideo = currentItem?.type === 'video' || isLikelyVideo(currentItem?.url || '')
  const shouldBlur = currentItem?.nsfw && nsfwBlurEnabled && !isRevealed

  // Get optimized video URL
  const videoUrl = isVideo && currentItem?.url.includes('civitai.com')
    ? getCivitaiVideoUrl(currentItem.url)
    : currentItem?.url

  // Reset state when opening or changing item
  useEffect(() => {
    if (isOpen) {
      setCurrentIndex(initialIndex)
      setIsRevealed(false)
      setImageZoom(1)
      setImagePosition({ x: 0, y: 0 })
      setIsPlaying(false)
      setCurrentTime(0)
      setDuration(0)
    }
  }, [isOpen, initialIndex])

  // Reset reveal state when changing items
  useEffect(() => {
    setIsRevealed(false)
    setImageZoom(1)
    setImagePosition({ x: 0, y: 0 })
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
  }, [currentIndex])

  // Auto-play video when item changes
  useEffect(() => {
    if (isVideo && videoRef.current && !shouldBlur) {
      const playTimer = setTimeout(() => {
        videoRef.current?.play().catch(() => {})
      }, 100)
      return () => clearTimeout(playTimer)
    }
  }, [currentIndex, isVideo, shouldBlur])

  // Video event handlers
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)
    const handleTimeUpdate = () => setCurrentTime(video.currentTime)
    const handleDurationChange = () => setDuration(video.duration)

    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)
    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('durationchange', handleDurationChange)

    return () => {
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('durationchange', handleDurationChange)
    }
  }, [currentIndex])

  // Navigation handlers
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

  // Keyboard handlers
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          onClose()
          break
        case 'ArrowLeft':
          goToPrevious()
          break
        case 'ArrowRight':
          goToNext()
          break
        case '+':
        case '=':
          if (!isVideo) setImageZoom((z) => Math.min(4, z + 0.25))
          break
        case '-':
          if (!isVideo) setImageZoom((z) => Math.max(0.5, z - 0.25))
          break
        case '0':
          setImageZoom(1)
          setImagePosition({ x: 0, y: 0 })
          break
        case ' ':
          e.preventDefault()
          if (isVideo && videoRef.current) {
            if (isPlaying) videoRef.current.pause()
            else videoRef.current.play()
          }
          break
        case 'm':
        case 'M':
          if (isVideo) setIsMuted(m => !m)
          break
        case 'l':
        case 'L':
          if (isVideo) setIsLooping(l => !l)
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose, goToPrevious, goToNext, isVideo, isPlaying])

  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  // Image drag handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!isVideo && imageZoom > 1) {
      setIsDragging(true)
      setDragStart({ x: e.clientX - imagePosition.x, y: e.clientY - imagePosition.y })
    }
  }, [isVideo, imageZoom, imagePosition])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging) {
      setImagePosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      })
    }
  }, [isDragging, dragStart])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (!isVideo) {
      e.preventDefault()
      const delta = e.deltaY > 0 ? -0.1 : 0.1
      setImageZoom((z) => Math.max(0.5, Math.min(4, z + delta)))
    }
  }, [isVideo])

  // Download handler
  const handleDownload = useCallback(() => {
    if (currentItem?.url) {
      const a = document.createElement('a')
      a.href = currentItem.url
      a.download = currentItem.url.split('/').pop() || 'download'
      a.target = '_blank'
      a.click()
    }
  }, [currentItem])

  // Open in new tab
  const handleOpenExternal = useCallback(() => {
    if (currentItem?.url) {
      window.open(currentItem.url, '_blank')
    }
  }, [currentItem])

  // Video controls
  const togglePlay = useCallback(() => {
    if (videoRef.current) {
      if (isPlaying) videoRef.current.pause()
      else videoRef.current.play()
    }
  }, [isPlaying])

  const toggleMute = useCallback(() => {
    setIsMuted(m => !m)
    if (videoRef.current) {
      videoRef.current.muted = !isMuted
    }
  }, [isMuted])

  const toggleLoop = useCallback(() => {
    setIsLooping(l => !l)
  }, [])

  // Progress bar click
  const handleProgressClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoRef.current || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pos = (e.clientX - rect.left) / rect.width
    videoRef.current.currentTime = pos * duration
  }, [duration])

  // Format time
  const formatTime = (seconds: number): string => {
    if (!isFinite(seconds)) return '0:00'
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  if (!isOpen || !currentItem) return null

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/95"
      onClick={onClose}
    >
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-4 bg-gradient-to-b from-black/80 to-transparent">
        {/* Left: Counter */}
        <div className="text-white/70 text-sm">
          {currentIndex + 1} / {items.length}
        </div>

        {/* Right: Actions */}
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

          {/* Loop toggle (videos only) */}
          {isVideo && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                toggleLoop()
              }}
              className={clsx(
                'p-2 rounded-lg transition-colors',
                isLooping
                  ? 'bg-synapse/30 text-synapse hover:bg-synapse/40'
                  : 'bg-white/10 text-white/50 hover:bg-white/20 hover:text-white'
              )}
              title={isLooping ? 'Loop ON (L)' : 'Loop OFF (L)'}
            >
              <Repeat className="w-5 h-5" />
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
                title="Zoom out (-)"
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
                title="Zoom in (+)"
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
            title="Download"
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
            title="Open in new tab"
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
            title="Close (Esc)"
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
          <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10">
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
          <div className="relative w-full h-full max-w-6xl max-h-full flex flex-col">
            {/* Video element */}
            <div className="flex-1 flex items-center justify-center min-h-0">
              <video
                ref={videoRef}
                src={videoUrl}
                poster={currentItem.thumbnailUrl}
                loop={isLooping}
                muted={isMuted}
                playsInline
                className="max-w-full max-h-full object-contain"
                onClick={(e) => {
                  e.stopPropagation()
                  togglePlay()
                }}
              />
            </div>

            {/* Video controls bar */}
            <div
              className="mt-4 p-3 bg-black/60 rounded-xl"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Progress bar */}
              <div
                className="h-1.5 bg-white/20 rounded-full cursor-pointer mb-3 group"
                onClick={handleProgressClick}
              >
                <div
                  className="h-full bg-synapse rounded-full relative transition-all"
                  style={{ width: `${progress}%` }}
                >
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>

              {/* Controls */}
              <div className="flex items-center gap-3">
                {/* Play/Pause */}
                <button
                  onClick={togglePlay}
                  className="p-2 text-white hover:text-synapse transition-colors"
                  title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
                >
                  {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 fill-current" />}
                </button>

                {/* Mute */}
                <button
                  onClick={toggleMute}
                  className="p-2 text-white hover:text-synapse transition-colors"
                  title={isMuted ? 'Unmute (M)' : 'Mute (M)'}
                >
                  {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                </button>

                {/* Time */}
                <div className="text-white/70 text-sm font-mono">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </div>

                <div className="flex-1" />

                {/* Loop indicator */}
                <span className={clsx(
                  'text-xs px-2 py-1 rounded',
                  isLooping ? 'bg-synapse/30 text-synapse' : 'bg-white/10 text-white/50'
                )}>
                  {isLooping ? 'LOOP' : 'ONCE'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Image viewer */}
        {!isVideo && !shouldBlur && (
          <img
            src={currentItem.url}
            alt="Preview"
            className={clsx(
              'max-w-full max-h-full object-contain transition-transform duration-200',
              isDragging && 'cursor-grabbing',
              imageZoom > 1 && !isDragging && 'cursor-grab'
            )}
            style={{
              transform: `scale(${imageZoom}) translate(${imagePosition.x / imageZoom}px, ${imagePosition.y / imageZoom}px)`,
            }}
            draggable={false}
          />
        )}
      </div>

      {/* Metadata panel */}
      {currentItem.meta && Object.keys(currentItem.meta).length > 0 && (
        <div className="absolute bottom-0 left-0 right-0 z-10 p-4 bg-gradient-to-t from-black/80 to-transparent pointer-events-none">
          <div className="max-w-2xl mx-auto">
            {currentItem.meta.prompt && (
              <p className="text-white/70 text-sm line-clamp-2">
                {currentItem.meta.prompt}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default FullscreenMediaViewer
