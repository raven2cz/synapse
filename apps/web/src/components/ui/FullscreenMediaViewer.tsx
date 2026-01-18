/**
 * FullscreenMediaViewer Component
 *
 * Professional fullscreen media viewer inspired by Netflix, YouTube, and PhotoSwipe.
 *
 * Features:
 * - Netflix-style video controls with glassmorphism
 * - PhotoSwipe-style image zoom/pan with cursor-based zoom
 * - Thumbnail strip navigation
 * - Auto-hide controls
 * - Keyboard shortcuts
 * - Fast loading (uses same URL as preview)
 * - Video fit modes: FIT (default), FILL, ORIGINAL
 * - Smooth transitions between images
 *
 * @author Synapse Team
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
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
  RotateCcw,
  Repeat,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  SkipBack,
  SkipForward,
  Loader2,
} from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'

// ============================================================================
// URL Transformation - Support multiple quality levels
// ============================================================================

type VideoQuality = 'sd' | 'hd' | 'fhd'

const QUALITY_WIDTHS: Record<VideoQuality, number> = {
  sd: 450,    // Same as preview - instant playback
  hd: 720,    // HD
  fhd: 1080,  // Full HD
}

const QUALITY_LABELS: Record<VideoQuality, string> = {
  sd: 'SD',
  hd: 'HD',
  fhd: 'FHD',
}

// ============================================================================
// Video Fit Modes
// ============================================================================

type VideoFit = 'fit' | 'fill' | 'original'

const FIT_LABELS: Record<VideoFit, string> = {
  fit: 'FIT',       // Stretch to fill window, preserve aspect ratio (default)
  fill: 'FILL',     // Fill entire window, may crop
  original: 'ORIG', // Original size, centered
}

function getCivitaiVideoUrl(url: string, quality: VideoQuality = 'sd'): string {
  if (!url || !url.includes('civitai.com')) return url

  const width = QUALITY_WIDTHS[quality]

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

function getCivitaiThumbnailUrl(url: string, width: number = 450): string {
  if (!url || !url.includes('civitai.com')) return url

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

function isLikelyVideo(url: string): boolean {
  if (!url) return false
  const lowerUrl = url.toLowerCase()
  if (/\.(mp4|webm|mov|avi|mkv|gif)(\?|$)/i.test(url)) return true
  if (lowerUrl.includes('civitai.com') && lowerUrl.includes('transcode=true') && !lowerUrl.includes('anim=false')) return true
  return false
}

// ============================================================================
// Types
// ============================================================================

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

// ============================================================================
// Component
// ============================================================================

export function FullscreenMediaViewer({
  items,
  initialIndex = 0,
  isOpen,
  onClose,
  onIndexChange,
}: FullscreenMediaViewerProps) {
  const nsfwBlurEnabled = useSettingsStore((state) => state.nsfwBlurEnabled)

  // Navigation state
  const [currentIndex, setCurrentIndex] = useState(initialIndex)
  const [isRevealed, setIsRevealed] = useState(false)
  const [isTransitioning, setIsTransitioning] = useState(false)

  // Video state
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLooping, setIsLooping] = useState(true)
  const [isMuted, setIsMuted] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isBuffering, setIsBuffering] = useState(false)
  const [volume, setVolume] = useState(1)
  const [videoQuality, setVideoQuality] = useState<VideoQuality>('sd')
  const [showQualityMenu, setShowQualityMenu] = useState(false)
  const [videoFit, setVideoFit] = useState<VideoFit>('fit')
  const [showFitMenu, setShowFitMenu] = useState(false)

  // Image state
  const [imageZoom, setImageZoom] = useState(1)
  const [imagePosition, setImagePosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

  // UI state
  const [showControls, setShowControls] = useState(true)
  const [showThumbnails] = useState(true)

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const controlsTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Current item
  const currentItem = items[currentIndex]
  const isVideo = currentItem?.type === 'video' || isLikelyVideo(currentItem?.url || '')
  const shouldBlur = currentItem?.nsfw && nsfwBlurEnabled && !isRevealed

  // Video URL with selected quality
  const videoUrl = useMemo(() => {
    if (!currentItem?.url || !isVideo) return ''
    if (currentItem.url.includes('civitai.com')) {
      return getCivitaiVideoUrl(currentItem.url, videoQuality)
    }
    return currentItem.url
  }, [currentItem?.url, isVideo, videoQuality])

  const thumbnailUrl = useMemo(() => {
    if (currentItem?.thumbnailUrl) return currentItem.thumbnailUrl
    if (!currentItem?.url) return ''
    if (currentItem.url.includes('civitai.com')) {
      return getCivitaiThumbnailUrl(currentItem.url)
    }
    return currentItem.url
  }, [currentItem?.url, currentItem?.thumbnailUrl])

  // High quality URL for download only
  const downloadUrl = useMemo(() => {
    if (!currentItem?.url) return ''
    if (currentItem.url.includes('civitai.com') && isVideo) {
      return getCivitaiVideoUrl(currentItem.url, 'fhd')
    }
    return currentItem.url
  }, [currentItem?.url, isVideo])

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  // Reset state on open/change
  useEffect(() => {
    if (isOpen) {
      setCurrentIndex(initialIndex)
      setIsRevealed(false)
      setImageZoom(1)
      setImagePosition({ x: 0, y: 0 })
      setIsPlaying(false)
      setCurrentTime(0)
      setDuration(0)
      setShowControls(true)
      setVideoQuality('sd')
      setVideoFit('fit')
    }
  }, [isOpen, initialIndex])

  // Reset on index change with transition
  useEffect(() => {
    setIsRevealed(false)
    setImageZoom(1)
    setImagePosition({ x: 0, y: 0 })
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
  }, [currentIndex])

  // Autoplay video when opened or item changes (if not NSFW blurred)
  useEffect(() => {
    if (!isOpen || !isVideo || shouldBlur) return

    const video = videoRef.current
    if (!video) return

    const playTimer = setTimeout(() => {
      video.play().catch((err) => {
        if (err.name !== 'AbortError') {
          console.debug('Autoplay blocked:', err.message)
        }
      })
    }, 100)

    return () => clearTimeout(playTimer)
  }, [isOpen, isVideo, shouldBlur, currentIndex, videoUrl])

  // Auto-hide controls
  const resetControlsTimeout = useCallback(() => {
    if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
    setShowControls(true)
    controlsTimeoutRef.current = setTimeout(() => {
      if (isPlaying) setShowControls(false)
    }, 3000)
  }, [isPlaying])

  useEffect(() => {
    return () => {
      if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
    }
  }, [])

  // Navigation with transition animation
  const goToPrevious = useCallback(() => {
    if (currentIndex > 0 && !isTransitioning) {
      setIsTransitioning(true)
      setTimeout(() => {
        const newIndex = currentIndex - 1
        setCurrentIndex(newIndex)
        onIndexChange?.(newIndex)
        setTimeout(() => setIsTransitioning(false), 50)
      }, 150)
    }
  }, [currentIndex, onIndexChange, isTransitioning])

  const goToNext = useCallback(() => {
    if (currentIndex < items.length - 1 && !isTransitioning) {
      setIsTransitioning(true)
      setTimeout(() => {
        const newIndex = currentIndex + 1
        setCurrentIndex(newIndex)
        onIndexChange?.(newIndex)
        setTimeout(() => setIsTransitioning(false), 50)
      }, 150)
    }
  }, [currentIndex, items.length, onIndexChange, isTransitioning])

  const goToIndex = useCallback((index: number) => {
    if (index >= 0 && index < items.length && index !== currentIndex && !isTransitioning) {
      setIsTransitioning(true)
      setTimeout(() => {
        setCurrentIndex(index)
        onIndexChange?.(index)
        setTimeout(() => setIsTransitioning(false), 50)
      }, 150)
    }
  }, [items.length, currentIndex, onIndexChange, isTransitioning])

  // Video controls
  const togglePlay = useCallback(() => {
    if (videoRef.current) {
      if (isPlaying) videoRef.current.pause()
      else videoRef.current.play()
    }
  }, [isPlaying])

  const toggleMute = useCallback(() => {
    setIsMuted(m => !m)
    if (videoRef.current) videoRef.current.muted = !isMuted
  }, [isMuted])

  const toggleLoop = useCallback(() => setIsLooping(l => !l), [])

  const skip = useCallback((seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(0, Math.min(duration, videoRef.current.currentTime + seconds))
    }
  }, [duration])

  const handleProgressClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoRef.current || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pos = (e.clientX - rect.left) / rect.width
    videoRef.current.currentTime = pos * duration
  }, [duration])

  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(e.target.value)
    setVolume(newVolume)
    if (videoRef.current) videoRef.current.volume = newVolume
    setIsMuted(newVolume === 0)
  }, [])

  const toggleNativeFullscreen = useCallback(() => {
    if (!document.fullscreenElement) containerRef.current?.requestFullscreen()
    else document.exitFullscreen()
  }, [])

  // Cycle through video fit modes
  const cycleVideoFit = useCallback(() => {
    setVideoFit(current => {
      if (current === 'fit') return 'fill'
      if (current === 'fill') return 'original'
      return 'fit'
    })
  }, [])

  // Image controls
  const zoomIn = useCallback(() => setImageZoom(z => Math.min(5, z + 0.5)), [])
  const zoomOut = useCallback(() => setImageZoom(z => Math.max(0.5, z - 0.5)), [])
  const resetZoom = useCallback(() => {
    setImageZoom(1)
    setImagePosition({ x: 0, y: 0 })
  }, [])

  // Zoom towards cursor position
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (!isVideo && contentRef.current) {
      e.preventDefault()

      const rect = contentRef.current.getBoundingClientRect()
      // Mouse position relative to center of container
      const mouseX = e.clientX - rect.left - rect.width / 2
      const mouseY = e.clientY - rect.top - rect.height / 2

      const delta = e.deltaY > 0 ? -0.25 : 0.25
      const newZoom = Math.max(0.5, Math.min(5, imageZoom + delta))

      if (newZoom !== imageZoom) {
        const zoomRatio = newZoom / imageZoom

        // Adjust position to zoom towards mouse cursor
        setImagePosition(pos => ({
          x: mouseX - (mouseX - pos.x) * zoomRatio,
          y: mouseY - (mouseY - pos.y) * zoomRatio,
        }))
        setImageZoom(newZoom)
      }
    }
  }, [isVideo, imageZoom])

  // Drag/pan image - NO transition, immediate response
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!isVideo && imageZoom > 1) {
      e.preventDefault()
      setIsDragging(true)
      setDragStart({ x: e.clientX - imagePosition.x, y: e.clientY - imagePosition.y })
    }
  }, [isVideo, imageZoom, imagePosition])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    resetControlsTimeout()
    if (isDragging) {
      // Direct position update - no smoothing, immediate response
      setImagePosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      })
    }
  }, [isDragging, dragStart, resetControlsTimeout])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    if (!isVideo && contentRef.current) {
      if (imageZoom === 1) {
        // Zoom in towards click position
        const rect = contentRef.current.getBoundingClientRect()
        const mouseX = e.clientX - rect.left - rect.width / 2
        const mouseY = e.clientY - rect.top - rect.height / 2
        const newZoom = 2.5
        const zoomRatio = newZoom / imageZoom

        setImagePosition({
          x: mouseX - (mouseX) * zoomRatio,
          y: mouseY - (mouseY) * zoomRatio,
        })
        setImageZoom(newZoom)
      } else {
        setImageZoom(1)
        setImagePosition({ x: 0, y: 0 })
      }
    }
  }, [isVideo, imageZoom])

  const handleDownload = useCallback(async () => {
    try {
      const response = await fetch(downloadUrl)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `synapse_${currentIndex + 1}.${isVideo ? 'mp4' : 'jpg'}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      window.open(downloadUrl, '_blank')
    }
  }, [currentItem?.url, downloadUrl, isVideo, currentIndex])

  const handleOpenExternal = useCallback(() => {
    if (currentItem?.url) window.open(currentItem.url, '_blank')
  }, [currentItem])

  // Keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return

      switch (e.key) {
        case 'Escape': onClose(); break
        case 'ArrowLeft': e.preventDefault(); goToPrevious(); break
        case 'ArrowRight': e.preventDefault(); goToNext(); break
        case ' ': e.preventDefault(); if (isVideo) togglePlay(); break
        case 'm': case 'M': if (isVideo) toggleMute(); break
        case 'l': case 'L': if (isVideo) toggleLoop(); break
        case 'f': case 'F': toggleNativeFullscreen(); break
        case 'v': case 'V': if (isVideo) cycleVideoFit(); break
        case '+': case '=': if (!isVideo) zoomIn(); break
        case '-': if (!isVideo) zoomOut(); break
        case '0': if (!isVideo) resetZoom(); break
        case 'ArrowUp':
          if (isVideo) {
            e.preventDefault()
            setVolume(v => Math.min(1, v + 0.1))
            if (videoRef.current) videoRef.current.volume = Math.min(1, volume + 0.1)
          }
          break
        case 'ArrowDown':
          if (isVideo) {
            e.preventDefault()
            setVolume(v => Math.max(0, v - 0.1))
            if (videoRef.current) videoRef.current.volume = Math.max(0, volume - 0.1)
          }
          break
        case 'j': case 'J': if (isVideo) skip(-10); break
        case 'k': case 'K': if (isVideo) togglePlay(); break
        case ';': if (isVideo) skip(10); break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isVideo, goToPrevious, goToNext, togglePlay, toggleMute, toggleLoop, toggleNativeFullscreen, cycleVideoFit, zoomIn, zoomOut, resetZoom, volume, skip, onClose])

  const formatTime = (seconds: number): string => {
    if (!isFinite(seconds)) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // Get video CSS class based on fit mode
  const getVideoClassName = () => {
    switch (videoFit) {
      case 'fit':
        // Stretch to fill container while preserving aspect ratio
        return 'w-full h-full object-contain'
      case 'fill':
        // Fill entire container, may crop
        return 'w-full h-full object-cover'
      case 'original':
        // Original size, centered
        return 'max-w-none max-h-none object-none'
      default:
        return 'w-full h-full object-contain'
    }
  }

  if (!isOpen || !currentItem) return null

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-[100] bg-black select-none"
      onClick={onClose}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Top bar - glassmorphism */}
      <div className={clsx(
        'absolute top-0 left-0 right-0 z-30 transition-all duration-300',
        showControls ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-full'
      )}>
        <div className="flex items-center justify-between p-4 bg-gradient-to-b from-black/80 via-black/40 to-transparent">
          <div className="flex items-center gap-4">
            <span className="text-white/90 text-sm font-medium">{currentIndex + 1} / {items.length}</span>
            {currentItem.nsfw && <span className="px-2 py-0.5 rounded bg-red-500/80 text-white text-xs font-medium">NSFW</span>}
          </div>

          <div className="flex items-center gap-1">
            {currentItem.nsfw && nsfwBlurEnabled && (
              <button onClick={(e) => { e.stopPropagation(); setIsRevealed(!isRevealed) }}
                className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white transition-all"
                title={isRevealed ? 'Hide' : 'Reveal'}>
                {isRevealed ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            )}

            {isVideo && (
              <button onClick={(e) => { e.stopPropagation(); toggleLoop() }}
                className={clsx('p-2.5 rounded-xl backdrop-blur-sm transition-all',
                  isLooping ? 'bg-indigo-500/30 text-indigo-300 hover:bg-indigo-500/40' : 'bg-white/10 text-white/60 hover:bg-white/20 hover:text-white')}
                title={isLooping ? 'Loop ON (L)' : 'Loop OFF (L)'}>
                <Repeat className="w-5 h-5" />
              </button>
            )}

            {!isVideo && (
              <>
                <button onClick={(e) => { e.stopPropagation(); zoomOut() }}
                  className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white transition-all" title="Zoom out (-)">
                  <ZoomOut className="w-5 h-5" />
                </button>
                <span className="text-white/80 text-sm min-w-[4rem] text-center font-medium">{Math.round(imageZoom * 100)}%</span>
                <button onClick={(e) => { e.stopPropagation(); zoomIn() }}
                  className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white transition-all" title="Zoom in (+)">
                  <ZoomIn className="w-5 h-5" />
                </button>
                <button onClick={(e) => { e.stopPropagation(); resetZoom() }}
                  className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white transition-all" title="Reset zoom (0)">
                  <RotateCcw className="w-5 h-5" />
                </button>
              </>
            )}

            <div className="w-px h-6 bg-white/20 mx-1" />

            <button onClick={(e) => { e.stopPropagation(); handleDownload() }}
              className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white transition-all" title="Download">
              <Download className="w-5 h-5" />
            </button>

            <button onClick={(e) => { e.stopPropagation(); handleOpenExternal() }}
              className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white transition-all" title="Open original">
              <ExternalLink className="w-5 h-5" />
            </button>

            <button onClick={(e) => { e.stopPropagation(); toggleNativeFullscreen() }}
              className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white transition-all" title="Fullscreen (F)">
              <Maximize className="w-5 h-5" />
            </button>

            <button onClick={(e) => { e.stopPropagation(); onClose() }}
              className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-red-500/50 text-white transition-all ml-2" title="Close (Esc)">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Navigation arrows */}
      {items.length > 1 && (
        <>
          <button onClick={(e) => { e.stopPropagation(); goToPrevious() }} disabled={currentIndex === 0}
            className={clsx('absolute left-4 top-1/2 -translate-y-1/2 z-20 p-3 rounded-full bg-black/40 backdrop-blur-sm text-white transition-all duration-200 hover:bg-black/60 hover:scale-110',
              showControls ? 'opacity-100' : 'opacity-0', currentIndex === 0 && 'opacity-30 cursor-not-allowed hover:scale-100')}>
            <ChevronLeft className="w-8 h-8" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); goToNext() }} disabled={currentIndex === items.length - 1}
            className={clsx('absolute right-4 top-1/2 -translate-y-1/2 z-20 p-3 rounded-full bg-black/40 backdrop-blur-sm text-white transition-all duration-200 hover:bg-black/60 hover:scale-110',
              showControls ? 'opacity-100' : 'opacity-0', currentIndex === items.length - 1 && 'opacity-30 cursor-not-allowed hover:scale-100')}>
            <ChevronRight className="w-8 h-8" />
          </button>
        </>
      )}

      {/* Main content area */}
      <div
        ref={contentRef}
        className="absolute inset-0 flex items-center justify-center overflow-hidden"
        style={{ paddingTop: '64px', paddingBottom: showThumbnails ? '120px' : '80px' }}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={handleMouseDown}
        onDoubleClick={handleDoubleClick}
        onWheel={handleWheel}
      >
        {/* NSFW blur overlay */}
        {shouldBlur && (
          <div className="absolute inset-0 flex items-center justify-center z-20">
            <div className="text-center">
              <div className="w-24 h-24 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center mx-auto mb-6">
                <EyeOff className="w-12 h-12 text-white/60" />
              </div>
              <p className="text-white/80 text-xl mb-6">NSFW Content</p>
              <button onClick={() => setIsRevealed(true)}
                className="px-8 py-3 rounded-xl bg-indigo-500 hover:bg-indigo-400 text-white font-medium transition-colors">
                Click to reveal
              </button>
            </div>
          </div>
        )}

        {/* Video content */}
        {isVideo && !shouldBlur && (
          <div className={clsx(
            'relative w-full h-full flex items-center justify-center transition-opacity duration-150',
            isTransitioning ? 'opacity-0' : 'opacity-100'
          )}>
            <video
              ref={videoRef}
              src={videoUrl}
              poster={thumbnailUrl}
              loop={isLooping}
              muted={isMuted}
              playsInline
              className={clsx('transition-all duration-300', getVideoClassName())}
              onClick={togglePlay}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
              onDurationChange={(e) => setDuration(e.currentTarget.duration)}
              onWaiting={() => setIsBuffering(true)}
              onCanPlay={() => setIsBuffering(false)}
              onLoadedData={() => setIsBuffering(false)}
            />

            {isBuffering && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/20">
                <Loader2 className="w-12 h-12 text-white animate-spin" />
              </div>
            )}

            {!isPlaying && !isBuffering && (
              <button onClick={togglePlay} className="absolute inset-0 flex items-center justify-center group">
                <div className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center transition-all group-hover:bg-white/30 group-hover:scale-110">
                  <Play className="w-10 h-10 text-white fill-white ml-1" />
                </div>
              </button>
            )}
          </div>
        )}

        {/* Image content */}
        {!isVideo && !shouldBlur && (
          <img
            src={currentItem.url}
            alt=""
            className={clsx(
              'max-w-full max-h-full object-contain',
              // Only apply transition when NOT dragging - immediate response during drag
              !isDragging && 'transition-all duration-200',
              // Fade transition for image switching
              isTransitioning ? 'opacity-0 scale-95' : 'opacity-100 scale-100'
            )}
            style={{
              transform: `scale(${imageZoom}) translate(${imagePosition.x / imageZoom}px, ${imagePosition.y / imageZoom}px)`,
              cursor: imageZoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'zoom-in',
            }}
            draggable={false}
          />
        )}
      </div>

      {/* Video controls bar - Netflix style */}
      {isVideo && !shouldBlur && (
        <div className={clsx('absolute left-0 right-0 z-30 transition-all duration-300',
          showThumbnails ? 'bottom-[100px]' : 'bottom-4',
          showControls ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-full')}
          onClick={(e) => e.stopPropagation()}>
          <div className="px-4 pb-2">
            {/* Progress bar */}
            <div className="group relative h-1 bg-white/20 rounded-full cursor-pointer mb-3 hover:h-1.5 transition-all"
              onClick={handleProgressClick}>
              <div className="absolute inset-y-0 left-0 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all"
                style={{ width: `${progress}%` }} />
              <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ left: `${progress}%`, marginLeft: '-6px' }} />
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button onClick={togglePlay} className="p-2 rounded-lg hover:bg-white/10 text-white transition-colors">
                  {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 fill-white" />}
                </button>

                <button onClick={() => skip(-10)} className="p-2 rounded-lg hover:bg-white/10 text-white/80 transition-colors" title="Back 10s (J)">
                  <SkipBack className="w-5 h-5" />
                </button>
                <button onClick={() => skip(10)} className="p-2 rounded-lg hover:bg-white/10 text-white/80 transition-colors" title="Forward 10s (;)">
                  <SkipForward className="w-5 h-5" />
                </button>

                <div className="group flex items-center gap-1">
                  <button onClick={toggleMute} className="p-2 rounded-lg hover:bg-white/10 text-white/80 transition-colors" title={isMuted ? 'Unmute (M)' : 'Mute (M)'}>
                    {isMuted || volume === 0 ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                  </button>
                  <input type="range" min="0" max="1" step="0.05" value={isMuted ? 0 : volume} onChange={handleVolumeChange}
                    className="w-20 h-1 bg-white/20 rounded-full appearance-none cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white" />
                </div>

                <span className="text-white/60 text-sm ml-2 tabular-nums">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </span>
              </div>

              <div className="flex items-center gap-2">
                {/* Quality selector */}
                <div className="relative">
                  <button
                    onClick={() => { setShowQualityMenu(!showQualityMenu); setShowFitMenu(false) }}
                    className={clsx(
                      'px-2.5 py-1 rounded-lg text-xs font-bold transition-all',
                      videoQuality !== 'sd'
                        ? 'bg-indigo-500/30 text-indigo-300 hover:bg-indigo-500/40'
                        : 'bg-white/10 text-white/80 hover:bg-white/20'
                    )}
                    title="Video quality"
                  >
                    {QUALITY_LABELS[videoQuality]}
                  </button>
                  {showQualityMenu && (
                    <div className="absolute bottom-full right-0 mb-2 p-1 bg-black/90 backdrop-blur-xl rounded-xl min-w-[120px] shadow-xl border border-white/10">
                      {(['sd', 'hd', 'fhd'] as VideoQuality[]).map((q) => (
                        <button
                          key={q}
                          onClick={() => {
                            setVideoQuality(q)
                            setShowQualityMenu(false)
                          }}
                          className={clsx(
                            'w-full px-3 py-2 text-left text-sm rounded-lg transition-colors flex items-center justify-between',
                            videoQuality === q
                              ? 'bg-indigo-500/30 text-indigo-300'
                              : 'text-white/80 hover:bg-white/10'
                          )}
                        >
                          <span>{QUALITY_LABELS[q]}</span>
                          {q === 'sd' && <span className="text-xs text-white/40">Fast</span>}
                          {q === 'fhd' && <span className="text-xs text-white/40">Best</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Fit mode selector */}
                <div className="relative">
                  <button
                    onClick={() => { setShowFitMenu(!showFitMenu); setShowQualityMenu(false) }}
                    className={clsx(
                      'px-2.5 py-1 rounded-lg text-xs font-bold transition-all',
                      videoFit === 'fit'
                        ? 'bg-indigo-500/30 text-indigo-300 hover:bg-indigo-500/40'
                        : 'bg-white/10 text-white/80 hover:bg-white/20'
                    )}
                    title="Video fit mode (V)"
                  >
                    {FIT_LABELS[videoFit]}
                  </button>
                  {showFitMenu && (
                    <div className="absolute bottom-full right-0 mb-2 p-1 bg-black/90 backdrop-blur-xl rounded-xl min-w-[140px] shadow-xl border border-white/10">
                      {(['fit', 'fill', 'original'] as VideoFit[]).map((f) => (
                        <button
                          key={f}
                          onClick={() => {
                            setVideoFit(f)
                            setShowFitMenu(false)
                          }}
                          className={clsx(
                            'w-full px-3 py-2 text-left text-sm rounded-lg transition-colors flex items-center justify-between',
                            videoFit === f
                              ? 'bg-indigo-500/30 text-indigo-300'
                              : 'text-white/80 hover:bg-white/10'
                          )}
                        >
                          <span>{FIT_LABELS[f]}</span>
                          {f === 'fit' && <span className="text-xs text-white/40">Default</span>}
                          {f === 'fill' && <span className="text-xs text-white/40">Crop</span>}
                          {f === 'original' && <span className="text-xs text-white/40">1:1</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Loop indicator */}
                <span className={clsx('px-2 py-1 rounded text-xs font-medium transition-colors cursor-pointer hover:bg-white/10',
                  isLooping ? 'bg-indigo-500/30 text-indigo-300' : 'bg-white/10 text-white/50')}
                  onClick={() => setIsLooping(l => !l)} title="Toggle loop (L)">
                  {isLooping ? 'LOOP' : 'ONCE'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Thumbnail strip */}
      {items.length > 1 && showThumbnails && (
        <div className={clsx('absolute bottom-0 left-0 right-0 z-20 transition-all duration-300',
          showControls ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-full')}
          onClick={(e) => e.stopPropagation()}>
          <div className="p-3 bg-gradient-to-t from-black/80 to-transparent">
            <div className="flex gap-2 justify-center overflow-x-auto scrollbar-thin">
              {items.map((item, idx) => {
                const itemIsVideo = item.type === 'video' || isLikelyVideo(item.url)
                const thumbUrl = item.thumbnailUrl || (item.url.includes('civitai.com') ? getCivitaiThumbnailUrl(item.url, 150) : item.url)

                return (
                  <button key={idx} onClick={() => goToIndex(idx)}
                    className={clsx('relative flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden transition-all',
                      idx === currentIndex ? 'ring-2 ring-indigo-500 ring-offset-2 ring-offset-black scale-110' : 'opacity-60 hover:opacity-100')}>
                    <img src={thumbUrl} alt="" className={clsx('w-full h-full object-cover', item.nsfw && nsfwBlurEnabled && 'blur-md')} />
                    {itemIsVideo && (
                      <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                        <Play className="w-4 h-4 text-white fill-white" />
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Keyboard shortcuts hint */}
      <div className={clsx('absolute bottom-2 left-1/2 -translate-x-1/2 z-10 transition-opacity duration-300',
        showControls ? 'opacity-50' : 'opacity-0')}>
        <p className="text-white/50 text-xs">
          {isVideo ? 'Space: Play · J/;: Skip · M: Mute · L: Loop · V: Fit · F: Fullscreen · Esc: Close' : '+/-: Zoom · 0: Reset · F: Fullscreen · Esc: Close'}
        </p>
      </div>
    </div>
  )
}

export default FullscreenMediaViewer
