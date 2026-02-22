/**
 * FullscreenMediaViewer Component - v4.0.0
 * 
 * NEW: Google Photos-style sliding transition
 * FIXED: Thumbnail scroll sensitivity
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { clsx } from 'clsx'
import {
  X, ChevronLeft, ChevronRight, Download, ExternalLink, Eye, EyeOff,
  ZoomIn, ZoomOut, RotateCcw, Repeat, Play, Pause, Volume2, VolumeX,
  Maximize, SkipBack, SkipForward, Loader2, Info, Copy, Check,
} from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'

// ============================================================================
// Types & Constants
// ============================================================================
const SLIDE_DURATION = 300 // ms
// Easing derived from standard material/iOS curves for smooth sliding
const SLIDE_EASING = 'cubic-bezier(0.2, 0.0, 0.0, 1.0)'

type VideoQuality = 'sd' | 'hd' | 'fhd'
type VideoFit = 'fit' | 'fill' | 'original'

const QUALITY_WIDTHS: Record<VideoQuality, number> = { sd: 450, hd: 720, fhd: 1080 }
const FIT_LABELS: Record<VideoFit, string> = { fit: 'FIT', fill: 'FILL', original: 'ORIG' }

export const QUALITY_LABELS: Record<VideoQuality, string> = {
  sd: 'SD',
  hd: 'HD',
  fhd: 'FHD',
}

export function getQualityBadge(q: VideoQuality): string | null {
  if (q === 'sd') return 'viewer.qualityFast'
  if (q === 'hd') return 'viewer.qualityStandard'
  if (q === 'fhd') return 'viewer.qualityBest'
  return null
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

// ============================================================================
// URL helpers
// ============================================================================

/** Check if URL is a direct Civitai CDN URL (not a proxy URL). */
function isCivitaiDirectUrl(url: string): boolean {
  if (!url) return false
  if (url.includes('/api/browse/image-proxy')) return false
  return url.includes('civitai.com')
}

function getCivitaiVideoUrl(url: string, quality: VideoQuality = 'sd'): string {
  if (!url || !isCivitaiDirectUrl(url)) return url
  try {
    const urlObj = new URL(url)
    const parts = urlObj.pathname.split('/')
    const idx = parts.findIndex(p => p.includes('=') || p.startsWith('width'))
    const params = `transcode=true,width=${QUALITY_WIDTHS[quality]},optimized=true`
    if (idx >= 0) parts[idx] = params
    else if (parts.length >= 3) parts.splice(-1, 0, params)
    const lastIdx = parts.length - 1
    if (lastIdx >= 0) parts.splice(lastIdx, 1, parts[lastIdx].replace(/\.[^.]+$/, '') + '.mp4')
    urlObj.pathname = parts.join('/')
    return urlObj.toString()
  } catch { return url }
}

function getCivitaiThumbnailUrl(url: string, width = 450): string {
  if (!url || !isCivitaiDirectUrl(url)) return url
  try {
    const urlObj = new URL(url)
    const parts = urlObj.pathname.split('/')
    const idx = parts.findIndex(p => p.includes('=') || p.startsWith('width'))
    const params = `anim=false,transcode=true,width=${width},optimized=true`
    if (idx >= 0) parts[idx] = params
    else if (parts.length >= 3) parts.splice(-1, 0, params)
    urlObj.pathname = parts.join('/')
    return urlObj.toString()
  } catch { return url }
}

function isLikelyVideo(url: string): boolean {
  if (!url) return false
  const lower = url.toLowerCase()
  return /\.(mp4|webm|mov|avi|mkv|gif)(\?|$)/i.test(url) ||
    (isCivitaiDirectUrl(lower) && lower.includes('transcode=true') && !lower.includes('anim=false'))
}

// ============================================================================
// Component
// ============================================================================
export function FullscreenMediaViewer({
  items, initialIndex = 0, isOpen, onClose, onIndexChange,
}: FullscreenMediaViewerProps) {
  const { t } = useTranslation()
  const nsfwBlurEnabled = useSettingsStore((s) => s.nsfwBlurEnabled)

  // Navigation & animation state
  const [currentIndex, setCurrentIndex] = useState(initialIndex)
  // Animation offset: 0 = center, -1 = showing next (partial), 1 = showing prev (partial)
  // We use translateX pixels/percent for the container
  const [slideOffset, setSlideOffset] = useState(0)
  const [isAnimating, setIsAnimating] = useState(false)

  const [isRevealed, setIsRevealed] = useState(false)

  // Video state
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLooping, setIsLooping] = useState(true)
  const [isMuted, setIsMuted] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isBuffering, setIsBuffering] = useState(false)
  const [volume, setVolume] = useState(1)
  const [videoQuality, setVideoQuality] = useState<VideoQuality>('sd')
  const [videoFit, setVideoFit] = useState<VideoFit>('fit')

  // Image state
  const [imageZoom, setImageZoom] = useState(1)
  const [imagePosition, setImagePosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

  const [showControls, setShowControls] = useState(true)
  const [showQualityMenu, setShowQualityMenu] = useState(false)

  // Metadata panel state
  const [showMetadata, setShowMetadata] = useState(false)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const controlsTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const thumbnailsRef = useRef<HTMLDivElement>(null)
  const thumbRefs = useRef<Map<number, HTMLButtonElement>>(new Map())

  // Derived
  const currentItem = items[currentIndex]
  const isVideo = currentItem?.type === 'video' || isLikelyVideo(currentItem?.url || '')
  const shouldBlur = currentItem?.nsfw && nsfwBlurEnabled && !isRevealed

  // Pre-calculate adjacent indices for the sliding window
  const prevIndex = currentIndex > 0 ? currentIndex - 1 : null
  const nextIndex = currentIndex < items.length - 1 ? currentIndex + 1 : null

  const videoUrl = useMemo(() => {
    if (!currentItem?.url || !isVideo) return ''
    return isCivitaiDirectUrl(currentItem.url) ? getCivitaiVideoUrl(currentItem.url, videoQuality) : currentItem.url
  }, [currentItem?.url, isVideo, videoQuality])

  const downloadUrl = useMemo(() => {
    if (!currentItem?.url) return ''
    return isCivitaiDirectUrl(currentItem.url) && isVideo ? getCivitaiVideoUrl(currentItem.url, 'fhd') : currentItem.url
  }, [currentItem?.url, isVideo])

  // Check if current item has metadata
  const currentHasMeta = useMemo(() => {
    return currentItem?.meta && Object.keys(currentItem.meta).length > 0
  }, [currentItem])

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  // Helpers
  const getThumbUrl = useCallback((item: MediaItem) => {
    if (!item) return ''
    if (item.thumbnailUrl) return item.thumbnailUrl
    if (isCivitaiDirectUrl(item.url || '')) return getCivitaiThumbnailUrl(item.url, 450)
    return item.url || ''
  }, [])

  const getVideoClass = useCallback(() => {
    switch (videoFit) {
      case 'fill': return 'w-full h-full object-cover'
      case 'original': return 'max-w-none max-h-none object-none'
      default: return 'w-full h-full object-contain'
    }
  }, [videoFit])

  const scrollToThumb = useCallback((idx: number) => {
    thumbRefs.current.get(idx)?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }, [])

  // Reset on open
  useEffect(() => {
    if (isOpen) {
      setCurrentIndex(initialIndex)
      setSlideOffset(0)
      setIsAnimating(false)
      setIsRevealed(false)
      setImageZoom(1)
      setImagePosition({ x: 0, y: 0 })
      setIsPlaying(false)
      setCurrentTime(0)
      setDuration(0)
      setShowControls(true)
      setVideoQuality('sd')
      setVideoFit('fit')
      setShowMetadata(false)
      setTimeout(() => scrollToThumb(initialIndex), 100)
    }
  }, [isOpen, initialIndex, scrollToThumb])

  // Reset media state when index changes (but not during animation start, only after)
  // Actually we handle this naturally because the "Active" slide changes
  useEffect(() => {
    // When the index settles, reset image zoom if we changed items
    setImageZoom(1)
    setImagePosition({ x: 0, y: 0 })
  }, [currentIndex])

  // Auto-hide metadata panel when navigating to item without meta
  useEffect(() => {
    if (!currentHasMeta && showMetadata) {
      setShowMetadata(false)
    }
  }, [currentIndex, currentHasMeta, showMetadata])

  // Autoplay
  useEffect(() => {
    if (!isOpen || !isVideo || shouldBlur || isAnimating) return
    const v = videoRef.current
    if (!v) return
    // Small timeout to ensure DOM is ready
    const t = setTimeout(() => {
      if (v.paused) v.play().catch(() => { })
    }, 100)
    return () => clearTimeout(t)
  }, [isOpen, isVideo, shouldBlur, currentIndex, videoUrl, isAnimating])

  // Auto-hide controls
  const resetControlsTimeout = useCallback(() => {
    if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
    setShowControls(true)
    if (isPlaying) {
      controlsTimeoutRef.current = setTimeout(() => setShowControls(false), 3000)
    }
  }, [isPlaying])

  useEffect(() => {
    if (isPlaying) resetControlsTimeout()
    return () => { if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current) }
  }, [isPlaying, resetControlsTimeout])


  // ============================================================================
  // NAVIGATION - Google Photos Style
  // ============================================================================
  const navigateTo = useCallback((newIdx: number) => {
    if (newIdx < 0 || newIdx >= items.length || newIdx === currentIndex || isAnimating) return

    const direction = newIdx > currentIndex ? 'next' : 'prev'
    const diff = newIdx - currentIndex

    // For immediate neighbors, we slide. For jumps, we might just cut or fast slide?
    // Let's implement smooth sliding for neighbors, and maybe fast slide for jumps.
    // Simpler: Just handle neighbors strictly for the "slide" effect.
    // If jumping far, we can just switch instantly or do a fade.
    // But the user asked for "animace pro prechod", implying next/prev usually.

    if (Math.abs(diff) === 1) {
      setIsAnimating(true)
      // If going NEXT, we want to slide everything to LEFT (-100%)
      // If going PREV, we want to slide everything to RIGHT (+100%)
      setSlideOffset(direction === 'next' ? -100 : 100)

      // Wait for animation, then reset
      setTimeout(() => {
        setIsAnimating(false)
        setCurrentIndex(newIdx)
        setSlideOffset(0)
        onIndexChange?.(newIdx)
        scrollToThumb(newIdx)
      }, SLIDE_DURATION)
    } else {
      // Jump
      setCurrentIndex(newIdx)
      onIndexChange?.(newIdx)
      scrollToThumb(newIdx)
    }

  }, [currentIndex, items.length, onIndexChange, isAnimating, scrollToThumb])

  const goToPrevious = useCallback(() => {
    if (currentIndex > 0) navigateTo(currentIndex - 1)
  }, [currentIndex, navigateTo])

  const goToNext = useCallback(() => {
    if (currentIndex < items.length - 1) navigateTo(currentIndex + 1)
  }, [currentIndex, items.length, navigateTo])

  // Video controls
  const togglePlay = useCallback(() => { if (videoRef.current) isPlaying ? videoRef.current.pause() : videoRef.current.play() }, [isPlaying])
  const toggleMute = useCallback(() => { setIsMuted(m => !m); if (videoRef.current) videoRef.current.muted = !isMuted }, [isMuted])
  const toggleLoop = useCallback(() => setIsLooping(l => !l), [])
  const skip = useCallback((s: number) => { if (videoRef.current) videoRef.current.currentTime = Math.max(0, Math.min(duration, videoRef.current.currentTime + s)) }, [duration])
  const handleProgressClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoRef.current || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    videoRef.current.currentTime = ((e.clientX - rect.left) / rect.width) * duration
  }, [duration])
  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const v = parseFloat(e.target.value)
    setVolume(v)
    if (videoRef.current) videoRef.current.volume = v
    setIsMuted(v === 0)
  }, [])
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) containerRef.current?.requestFullscreen()
    else document.exitFullscreen()
  }, [])
  const cycleVideoFit = useCallback(() => setVideoFit(c => c === 'fit' ? 'fill' : c === 'fill' ? 'original' : 'fit'), [])

  // Image controls
  const zoomIn = useCallback(() => setImageZoom(z => Math.min(5, z + 0.5)), [])
  const zoomOut = useCallback(() => setImageZoom(z => Math.max(0.25, z - 0.5)), [])
  const resetZoom = useCallback(() => { setImageZoom(1); setImagePosition({ x: 0, y: 0 }) }, [])

  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (isVideo || !contentRef.current) return
    e.preventDefault()
    const rect = contentRef.current.getBoundingClientRect()
    const mx = e.clientX - rect.left - rect.width / 2
    const my = e.clientY - rect.top - rect.height / 2
    const delta = e.deltaY > 0 ? -0.25 : 0.25
    const newZ = Math.max(0.25, Math.min(5, imageZoom + delta))
    if (newZ !== imageZoom) {
      const ratio = newZ / imageZoom
      setImagePosition(p => ({ x: mx - (mx - p.x) * ratio, y: my - (my - p.y) * ratio }))
      setImageZoom(newZ)
    }
  }, [isVideo, imageZoom])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (isVideo) return
    e.preventDefault()
    setIsDragging(true)
    setDragStart({ x: e.clientX - imagePosition.x, y: e.clientY - imagePosition.y })
  }, [isVideo, imagePosition])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    resetControlsTimeout()
    if (isDragging) setImagePosition({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y })
  }, [isDragging, dragStart, resetControlsTimeout])

  const handleMouseUp = useCallback(() => setIsDragging(false), [])

  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    if (isVideo || !contentRef.current) return
    if (imageZoom === 1) {
      const rect = contentRef.current.getBoundingClientRect()
      const mx = e.clientX - rect.left - rect.width / 2
      const my = e.clientY - rect.top - rect.height / 2
      setImagePosition({ x: mx - mx * 2.5, y: my - my * 2.5 })
      setImageZoom(2.5)
    } else {
      setImageZoom(1)
      setImagePosition({ x: 0, y: 0 })
    }
  }, [isVideo, imageZoom])

  const handleThumbWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    // INCREASED SENSITIVITY: Multiplier added here
    if (thumbnailsRef.current) thumbnailsRef.current.scrollLeft += (e.deltaY * 3.0)
  }, [])

  // Download
  const handleDownload = useCallback(async () => {
    try {
      const res = await fetch(downloadUrl)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `synapse_${currentIndex + 1}.${isVideo ? 'mp4' : 'jpg'}`
      a.click()
      URL.revokeObjectURL(url)
    } catch { window.open(downloadUrl, '_blank') }
  }, [downloadUrl, isVideo, currentIndex])

  const handleOpenExternal = useCallback(() => { if (currentItem?.url) window.open(currentItem.url, '_blank') }, [currentItem])

  // Keyboard
  useEffect(() => {
    if (!isOpen) return
    const handle = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      switch (e.key) {
        case 'Escape': onClose(); break
        case 'ArrowLeft': e.preventDefault(); goToPrevious(); break
        case 'ArrowRight': e.preventDefault(); goToNext(); break
        case ' ': e.preventDefault(); if (isVideo) togglePlay(); break
        case 'm': case 'M': if (isVideo) toggleMute(); break
        case 'l': case 'L': if (isVideo) toggleLoop(); break
        case 'f': case 'F': toggleFullscreen(); break
        case 'v': case 'V': if (isVideo) cycleVideoFit(); break
        case '+': case '=': if (!isVideo) zoomIn(); break
        case '-': if (!isVideo) zoomOut(); break
        case '0': if (!isVideo) resetZoom(); break
        case 'ArrowUp': if (isVideo) { e.preventDefault(); setVolume(v => Math.min(1, v + 0.1)); if (videoRef.current) videoRef.current.volume = Math.min(1, volume + 0.1) } break
        case 'ArrowDown': if (isVideo) { e.preventDefault(); setVolume(v => Math.max(0, v - 0.1)); if (videoRef.current) videoRef.current.volume = Math.max(0, volume - 0.1) } break
        case 'j': case 'J': if (isVideo) skip(-10); break
        case 'k': case 'K': if (isVideo) togglePlay(); break
        case ';': if (isVideo) skip(10); break
        case 'i': case 'I': if (currentHasMeta) setShowMetadata(prev => !prev); break
      }
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [isOpen, isVideo, goToPrevious, goToNext, togglePlay, toggleMute, toggleLoop, toggleFullscreen, cycleVideoFit, zoomIn, zoomOut, resetZoom, volume, skip, onClose, currentHasMeta])

  const formatTime = (s: number) => !isFinite(s) ? '0:00' : `${Math.floor(s / 60)}:${Math.floor(s % 60).toString().padStart(2, '0')}`

  // Copy text to clipboard - MUST be before early return!
  const copyToClipboard = useCallback(async (text: string, fieldName: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(fieldName)
      setTimeout(() => setCopiedField(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }, [])

  // ============================================================================
  // Render slide content helper
  // ============================================================================
  const renderSlideContent = useCallback((item: MediaItem, isActive: boolean) => {
    const itemIsVideo = item.type === 'video' || isLikelyVideo(item.url)
    const itemBlur = item.nsfw && nsfwBlurEnabled && !isRevealed
    const thumb = getThumbUrl(item)

    if (itemBlur) {
      return (
        <div className="w-full h-full flex items-center justify-center select-none">
          <div className="text-center">
            <div className="w-24 h-24 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center mx-auto mb-6">
              <EyeOff className="w-12 h-12 text-white/60" />
            </div>
            <p className="text-white/80 text-xl mb-6">{t('media.nsfwContent')}</p>
            {isActive && (
              <button onClick={() => setIsRevealed(true)} className="px-8 py-3 rounded-xl bg-indigo-500 hover:bg-indigo-400 text-white font-medium transition-colors">
                {t('media.clickToReveal')}
              </button>
            )}
          </div>
        </div>
      )
    }

    if (itemIsVideo) {
      if (!isActive) {
        // Inactive slides just show audio/play placeholder or poster
        return (
          <div className="relative w-full h-full flex items-center justify-center select-none">
            {/* If we have a thumbnail, show it with correct sizing */}
            <img src={thumb} alt="" className={clsx('transition-all duration-300', getVideoClass())} />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-16 h-16 rounded-full bg-black/40 flex items-center justify-center">
                <Play className="w-8 h-8 text-white fill-white ml-1" />
              </div>
            </div>
          </div>
        )
      }

      const vUrl = isCivitaiDirectUrl(item.url) ? getCivitaiVideoUrl(item.url, videoQuality) : item.url
      return (
        <div className="relative w-full h-full flex items-center justify-center select-none">
          <video ref={videoRef} src={vUrl} poster={thumb} loop={isLooping} muted={isMuted} playsInline
            className={clsx('transition-all duration-300', getVideoClass())} onClick={togglePlay}
            onPlay={() => setIsPlaying(true)} onPause={() => setIsPlaying(false)}
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
            onDurationChange={(e) => setDuration(e.currentTarget.duration)}
            onWaiting={() => setIsBuffering(true)} onCanPlay={() => setIsBuffering(false)} onLoadedData={() => setIsBuffering(false)} />
          {isBuffering && <div className="absolute inset-0 flex items-center justify-center bg-black/20"><Loader2 className="w-12 h-12 text-white animate-spin" /></div>}
        </div>
      )
    }

    // Image
    // Only apply zoom transforms if active
    const style = isActive ? {
      transform: `scale(${imageZoom}) translate(${imagePosition.x / imageZoom}px, ${imagePosition.y / imageZoom}px)`,
      cursor: isDragging ? 'grabbing' : 'grab'
    } : undefined

    // Only apply transition if NOT dragging (for smooth zoom/reset) and is active
    const classes = clsx(
      'max-w-full max-h-full object-contain select-none',
      isActive && !isDragging && 'transition-transform duration-150 ease-out'
    )

    return (
      <img src={item.url} alt=""
        className={classes}
        style={style}
        draggable={false}
        onError={(e) => {
          const img = e.target as HTMLImageElement
          if (img.src !== item.url) img.src = item.url
          else if (item.thumbnailUrl && img.src !== item.thumbnailUrl) img.src = item.thumbnailUrl
        }}
      />
    )
  }, [nsfwBlurEnabled, isRevealed, videoQuality, isLooping, isMuted, getThumbUrl, getVideoClass, togglePlay, isBuffering, imageZoom, imagePosition, isDragging, t])


  if (!isOpen || !currentItem) return null

  return (
    <div ref={containerRef} className="fixed inset-0 z-[100] bg-black flex flex-col overflow-hidden"
      onClick={onClose} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>

      {/* Top bar */}
      <div className={clsx('absolute top-0 left-0 right-0 z-30 transition-all duration-300', showControls ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-full')} onClick={e => e.stopPropagation()}>
        <div className="p-4 bg-gradient-to-b from-black/80 to-transparent">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-white/80 font-medium px-3 py-1.5 rounded-lg bg-white/10 backdrop-blur-sm">{currentIndex + 1} / {items.length}</span>
              {isVideo && <span className="text-white/60 text-sm px-2 py-1 rounded bg-indigo-500/30 text-indigo-300">{FIT_LABELS[videoFit]}</span>}
            </div>
            <div className="flex items-center gap-2">
              {currentItem.nsfw && nsfwBlurEnabled && (
                <button onClick={e => { e.stopPropagation(); setIsRevealed(!isRevealed) }}
                  className={clsx('p-2.5 rounded-xl backdrop-blur-sm transition-all', isRevealed ? 'bg-red-500/30 text-red-300' : 'bg-white/10 text-white/60 hover:bg-white/20')}>
                  {isRevealed ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              )}
              {isVideo && (
                <button onClick={e => { e.stopPropagation(); toggleLoop() }}
                  className={clsx('p-2.5 rounded-xl backdrop-blur-sm transition-all', isLooping ? 'bg-indigo-500/30 text-indigo-300' : 'bg-white/10 text-white/60')}>
                  <Repeat className="w-5 h-5" />
                </button>
              )}
              {!isVideo && (
                <>
                  <button onClick={e => { e.stopPropagation(); zoomOut() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white"><ZoomOut className="w-5 h-5" /></button>
                  <span className="text-white/80 text-sm min-w-[4rem] text-center font-medium">{Math.round(imageZoom * 100)}%</span>
                  <button onClick={e => { e.stopPropagation(); zoomIn() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white"><ZoomIn className="w-5 h-5" /></button>
                  <button onClick={e => { e.stopPropagation(); resetZoom() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white"><RotateCcw className="w-5 h-5" /></button>
                </>
              )}
              {/* Metadata panel toggle */}
              <button
                onClick={e => { e.stopPropagation(); if (currentHasMeta) setShowMetadata(prev => !prev) }}
                disabled={!currentHasMeta}
                className={clsx(
                  'p-2.5 rounded-xl backdrop-blur-sm transition-all',
                  showMetadata && currentHasMeta ? 'bg-indigo-500/30 text-indigo-300' : 'bg-white/10 text-white/60 hover:bg-white/20',
                  !currentHasMeta && 'opacity-30 cursor-not-allowed'
                )}
                title={currentHasMeta ? (showMetadata ? t('viewer.hideInfo') : t('viewer.showInfo')) : t('viewer.noMetadata')}
              >
                <Info className="w-5 h-5" />
              </button>
              <div className="w-px h-6 bg-white/20 mx-1" />
              <button onClick={e => { e.stopPropagation(); handleDownload() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white"><Download className="w-5 h-5" /></button>
              <button onClick={e => { e.stopPropagation(); handleOpenExternal() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white"><ExternalLink className="w-5 h-5" /></button>
              <button onClick={e => { e.stopPropagation(); toggleFullscreen() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white"><Maximize className="w-5 h-5" /></button>
              <button onClick={e => { e.stopPropagation(); onClose() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-red-500/50 text-white ml-2"><X className="w-5 h-5" /></button>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation arrows */}
      {items.length > 1 && (
        <>
          <button onClick={e => { e.stopPropagation(); goToPrevious() }} disabled={currentIndex === 0 || isAnimating}
            className={clsx('absolute left-4 top-1/2 -translate-y-1/2 z-20 p-3 rounded-full bg-black/40 backdrop-blur-sm text-white transition-all hover:bg-black/60 hover:scale-110',
              showControls ? 'opacity-100' : 'opacity-0', (currentIndex === 0 || isAnimating) && 'opacity-30 cursor-not-allowed hover:scale-100')}>
            <ChevronLeft className="w-8 h-8" />
          </button>
          <button onClick={e => { e.stopPropagation(); goToNext() }} disabled={currentIndex === items.length - 1 || isAnimating}
            className={clsx('absolute right-4 top-1/2 -translate-y-1/2 z-20 p-3 rounded-full bg-black/40 backdrop-blur-sm text-white transition-all hover:bg-black/60 hover:scale-110',
              showControls ? 'opacity-100' : 'opacity-0', (currentIndex === items.length - 1 || isAnimating) && 'opacity-30 cursor-not-allowed hover:scale-100')}>
            <ChevronRight className="w-8 h-8" />
          </button>
        </>
      )}

      {/* Main content area - Sliding Window */}
      <div className="absolute inset-0 overflow-hidden" style={{ paddingTop: '64px', paddingBottom: '160px' }}>
        <div ref={contentRef}
          className="relative w-full h-full"
          style={{
            transform: `translateX(${slideOffset}%)`,
            transition: isAnimating ? `transform ${SLIDE_DURATION}ms ${SLIDE_EASING}` : 'none'
          }}
          onClick={e => e.stopPropagation()}
          onMouseDown={handleMouseDown}
          onDoubleClick={handleDoubleClick}
          onWheel={handleWheel}
        >
          {/* PREVIOUS SLIDE */}
          {prevIndex !== null && (
            <div key={`slide-${prevIndex}`} className="absolute inset-y-0 w-full flex items-center justify-center px-4" style={{ left: '-100%' }}>
              {renderSlideContent(items[prevIndex], false)}
            </div>
          )}

          {/* CURRENT SLIDE */}
          <div key={`slide-${currentIndex}`} className="absolute inset-y-0 w-full flex items-center justify-center px-4" style={{ left: '0' }}>
            {renderSlideContent(currentItem, true)}

            {/* Big Play Button Overlay (when paused and controls visible) */}
            {isVideo && !isPlaying && !isBuffering && showControls && !shouldBlur && (
              <button onClick={togglePlay} className="absolute inset-0 flex items-center justify-center group z-10">
                <div className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center transition-all group-hover:bg-white/30 group-hover:scale-110">
                  <Play className="w-10 h-10 text-white fill-white ml-1" />
                </div>
              </button>
            )}
          </div>

          {/* NEXT SLIDE */}
          {nextIndex !== null && (
            <div key={`slide-${nextIndex}`} className="absolute inset-y-0 w-full flex items-center justify-center px-4" style={{ left: '100%' }}>
              {renderSlideContent(items[nextIndex], false)}
            </div>
          )}
        </div>
      </div>

      {/* Video controls */}
      {isVideo && !shouldBlur && (
        <div className={clsx('absolute left-0 right-0 bottom-[160px] z-30 transition-all duration-300', showControls ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-full')} onClick={e => e.stopPropagation()}>
          <div className="px-6 py-4 bg-gradient-to-t from-black/80 to-transparent">
            {/* Seek Bar */}
            <div className="group mb-4">
              <div className="h-1.5 bg-white/20 rounded-full cursor-pointer relative group-hover:h-2.5 transition-all" onClick={handleProgressClick}>
                <div className="absolute inset-y-0 left-0 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full" style={{ width: `${progress}%` }} />
                <div className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-lg opacity-0 group-hover:opacity-100 transition-opacity" style={{ left: `calc(${progress}% - 8px)` }} />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button onClick={togglePlay} className="p-2 rounded-lg hover:bg-white/10 text-white" title={isPlaying ? 'Pause (K/Space)' : 'Play (K/Space)'}>{isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 fill-white" />}</button>
                <button onClick={() => skip(-10)} className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white" title={t('viewer.backSeconds')}><SkipBack className="w-5 h-5" /></button>
                <button onClick={() => skip(10)} className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white" title={t('viewer.forwardSeconds')}><SkipForward className="w-5 h-5" /></button>
                <div className="flex items-center gap-2 group/vol">
                  <button onClick={toggleMute} className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white" title={isMuted ? 'Unmute (M)' : 'Mute (M)'}>{isMuted || volume === 0 ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}</button>
                  <input type="range" min="0" max="1" step="0.05" value={volume} onChange={handleVolumeChange} className="w-0 group-hover/vol:w-20 transition-all accent-indigo-500 opacity-0 group-hover/vol:opacity-100" />
                </div>
                <span className="text-white/70 text-sm font-mono ml-2">{formatTime(currentTime)} / {formatTime(duration)}</span>
              </div>
              <div className="flex items-center gap-2">
                {/* Quality Selector */}
                <div className="relative">
                  <button
                    onClick={() => setShowQualityMenu(!showQualityMenu)}
                    className={clsx(
                      'px-2.5 py-1 rounded-lg text-xs font-bold transition-all uppercase',
                      videoQuality !== 'sd'
                        ? 'bg-indigo-500/30 text-indigo-300 hover:bg-indigo-500/40'
                        : 'bg-white/10 text-white/80 hover:bg-white/20'
                    )}
                    title={t('viewer.videoQuality')}
                  >
                    {QUALITY_LABELS[videoQuality]}
                  </button>
                  {showQualityMenu && (
                    <div className="absolute bottom-full right-0 mb-2 p-1 bg-black/90 backdrop-blur-xl rounded-xl min-w-[120px] shadow-xl border border-white/10">
                      {(['sd', 'hd', 'fhd'] as const).map((q) => (
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
                          {getQualityBadge(q) && <span className="text-xs text-white/40">{q === 'sd' ? t('viewer.qualityFast') : q === 'hd' ? t('viewer.qualityStandard') : t('viewer.qualityBest')}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <button onClick={cycleVideoFit} className="px-3 py-1.5 rounded-lg text-sm font-medium bg-indigo-500/30 text-indigo-300 hover:bg-indigo-500/40" title={videoFit === 'fit' ? t('viewer.fitToScreen') : videoFit === 'fill' ? t('viewer.fillScreen') : t('viewer.originalSize')}>{FIT_LABELS[videoFit]}</button>
                <span className={clsx('px-2 py-1 rounded text-xs font-medium cursor-pointer', isLooping ? 'bg-indigo-500/30 text-indigo-300' : 'bg-white/10 text-white/50')} onClick={() => setIsLooping(l => !l)} title={t('viewer.toggleLoop')}>{isLooping ? t('viewer.loop') : t('viewer.once')}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Thumbnails */}
      {items.length > 1 && (
        <div className={clsx('absolute bottom-0 left-0 right-0 z-20 transition-all duration-300', showControls ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-full')} onClick={e => e.stopPropagation()}>
          <div className="bg-gradient-to-t from-black/90 via-black/70 to-transparent">
            {/* Added scroll sensitivity in handleThumbWheel */}
            <div ref={thumbnailsRef} className="flex gap-3 px-4 overflow-x-auto scrollbar-thin scrollbar-thumb-white/20 scroll-smooth" onWheel={handleThumbWheel} style={{ paddingTop: 20, paddingBottom: 16 }}>
              {items.map((item, idx) => {
                const itemIsVideo = item.type === 'video' || isLikelyVideo(item.url)
                const thumb = getThumbUrl(item)
                return (
                  <button key={idx} ref={el => { if (el) thumbRefs.current.set(idx, el); else thumbRefs.current.delete(idx) }}
                    onClick={() => navigateTo(idx)} disabled={isAnimating}
                    className={clsx('relative flex-shrink-0 rounded-lg overflow-hidden transition-all duration-200 w-24 h-24',
                      idx === currentIndex ? 'ring-2 ring-indigo-500 ring-offset-2 ring-offset-black scale-110' : 'opacity-60 hover:opacity-100 hover:scale-105',
                      isAnimating && 'pointer-events-none')}>
                    <img src={thumb} alt="" className={clsx('w-full h-full object-cover', item.nsfw && nsfwBlurEnabled && 'blur-md')}
                      onError={(e) => {
                        const img = e.target as HTMLImageElement
                        // For videos, fallback to transformed thumbnail URL (not raw video URL)
                        // For images, fallback to original URL
                        const fallbackUrl = itemIsVideo && isCivitaiDirectUrl(item.url || '')
                          ? getCivitaiThumbnailUrl(item.url, 450)
                          : item.url
                        if (img.src !== fallbackUrl) img.src = fallbackUrl
                      }}
                    />
                    {itemIsVideo && <div className="absolute inset-0 flex items-center justify-center bg-black/30"><Play className="w-5 h-5 text-white fill-white" /></div>}
                    <div className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/60 text-white/80 text-xs font-medium">{idx + 1}</div>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Metadata panel - right side overlay with click-outside backdrop */}
      {showMetadata && currentHasMeta && (
        <>
          {/* Invisible backdrop for click-outside-closes - only covers content area */}
          <div
            className="absolute left-0 right-[340px] z-35 transition-opacity duration-300"
            style={{ top: '64px', bottom: '160px' }}
            onClick={(e) => { e.stopPropagation(); setShowMetadata(false) }}
          />

          {/* Panel - glassmorphism design with fade animation */}
          <div
            className={clsx(
              "absolute right-0 w-[340px] z-40 flex flex-col overflow-hidden",
              "bg-black/50 backdrop-blur-2xl border-l border-white/10",
              "transition-all duration-300 ease-out",
              "animate-in slide-in-from-right-4 fade-in"
            )}
            style={{ top: '64px', bottom: '160px' }}
            onClick={e => e.stopPropagation()}
          >
            {/* Panel header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 shrink-0 bg-black/20">
              <h3 className="text-white font-semibold flex items-center gap-2">
                <Info className="w-4 h-4 text-indigo-400" />
                {t('genData.title')}
              </h3>
              <button
                onClick={() => setShowMetadata(false)}
                className="p-1.5 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-all"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Panel content - scrollable with smart rendering */}
            <div className="flex-1 overflow-y-auto p-4 space-y-5 custom-scrollbar">
              {(() => {
                const meta = currentItem.meta!
                const prompt = meta.prompt as string | undefined
                const negativePrompt = meta.negativePrompt as string | undefined
                const resources = meta.resources as Array<{ name: string; type: string; weight?: number }> | undefined
                const hashes = meta.hashes as Record<string, string> | undefined

                // Grid metadata fields
                const gridFields = [
                  { label: t('genData.model'), value: meta.Model || meta.model_name },
                  { label: t('genData.sampler'), value: meta.sampler },
                  { label: t('genData.steps'), value: meta.steps },
                  { label: t('genData.cfgScale'), value: meta.cfgScale || meta.cfg_scale },
                  { label: t('genData.seed'), value: meta.seed },
                  { label: t('genData.clipSkip'), value: meta.clipSkip || meta.clip_skip },
                  { label: t('genData.size'), value: meta.Size || (meta.width && meta.height ? `${meta.width}×${meta.height}` : undefined) },
                ].filter(f => f.value !== undefined && f.value !== null && f.value !== '')

                // Fields we've handled specially
                const handledKeys = new Set(['prompt', 'negativePrompt', 'resources', 'hashes', 'Model', 'model_name', 'sampler', 'steps', 'cfgScale', 'cfg_scale', 'seed', 'clipSkip', 'clip_skip', 'Size', 'width', 'height'])

                // Other fields (fallback)
                const otherFields = Object.entries(meta).filter(([key, value]) =>
                  !handledKeys.has(key) && value !== null && value !== undefined && value !== ''
                )

                return (
                  <>
                    {/* Resources Section */}
                    {resources && resources.length > 0 && (
                      <section className="space-y-2 group/section">
                        <div className="flex items-center justify-between">
                          <h4 className="text-[10px] font-bold text-white/40 uppercase tracking-widest">{t('genData.resources')}</h4>
                          <button
                            onClick={() => copyToClipboard(JSON.stringify(resources, null, 2), 'resources')}
                            className="opacity-0 group-hover/section:opacity-100 p-1 rounded hover:bg-white/10 text-white/40 hover:text-white transition-all"
                            title={t('genData.copyResources')}
                          >
                            {copiedField === 'resources' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                          </button>
                        </div>
                        <div className="space-y-1.5">
                          {resources.map((res, i) => (
                            <div key={i} className="flex items-center gap-2 bg-white/5 hover:bg-white/10 px-2.5 py-1.5 rounded-lg transition-colors group">
                              <span className={clsx(
                                "text-[9px] px-1.5 py-0.5 rounded font-bold uppercase shrink-0",
                                res.type === 'model' ? "bg-blue-500/20 text-blue-400" : "bg-indigo-500/20 text-indigo-400"
                              )}>
                                {res.type}
                              </span>
                              <span className="text-xs text-white/80 truncate flex-1" title={res.name}>{res.name}</span>
                              {res.weight && (
                                <span className="text-[10px] font-mono text-white/40">{res.weight}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </section>
                    )}

                    {/* Prompt Section */}
                    {prompt && (
                      <section className="space-y-2 group">
                        <div className="flex items-center justify-between">
                          <h4 className="text-[10px] font-bold text-white/40 uppercase tracking-widest">{t('genData.prompt')}</h4>
                          <button
                            onClick={() => copyToClipboard(prompt, 'prompt')}
                            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 text-white/40 hover:text-white transition-all"
                            title={t('genData.copyPrompt')}
                          >
                            {copiedField === 'prompt' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                          </button>
                        </div>
                        <div className="bg-white/5 p-2.5 rounded-lg text-xs leading-relaxed text-white/80 font-mono whitespace-pre-wrap break-words max-h-40 overflow-y-auto custom-scrollbar">
                          {prompt}
                        </div>
                      </section>
                    )}

                    {/* Negative Prompt Section */}
                    {negativePrompt && (
                      <section className="space-y-2 group">
                        <div className="flex items-center justify-between">
                          <h4 className="text-[10px] font-bold text-red-400/60 uppercase tracking-widest">{t('genData.negativePrompt')}</h4>
                          <button
                            onClick={() => copyToClipboard(negativePrompt, 'negativePrompt')}
                            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/10 text-white/40 hover:text-red-400 transition-all"
                            title={t('genData.copyNegativePrompt')}
                          >
                            {copiedField === 'negativePrompt' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                          </button>
                        </div>
                        <div className="bg-red-500/5 border border-red-500/10 p-2.5 rounded-lg text-xs leading-relaxed text-red-200/70 font-mono whitespace-pre-wrap break-words max-h-32 overflow-y-auto custom-scrollbar">
                          {negativePrompt}
                        </div>
                      </section>
                    )}

                    {/* Grid Params */}
                    {gridFields.length > 0 && (
                      <section className="space-y-2 group/section">
                        <div className="flex items-center justify-between">
                          <h4 className="text-[10px] font-bold text-white/40 uppercase tracking-widest">{t('genData.parameters')}</h4>
                          <button
                            onClick={() => copyToClipboard(JSON.stringify(Object.fromEntries(gridFields.map(f => [f.label, f.value])), null, 2), 'parameters')}
                            className="opacity-0 group-hover/section:opacity-100 p-1 rounded hover:bg-white/10 text-white/40 hover:text-white transition-all"
                            title={t('genData.copyParameters')}
                          >
                            {copiedField === 'parameters' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                          </button>
                        </div>
                        <div className="grid grid-cols-2 gap-1.5">
                          {gridFields.map((field, i) => (
                            <div key={i} className="bg-white/5 px-2.5 py-1.5 rounded-lg group hover:bg-white/10 transition-colors overflow-hidden">
                              <span className="text-[9px] text-white/40 uppercase block">{field.label}</span>
                              <span className="text-xs text-white/90 font-mono break-words line-clamp-3" title={String(field.value)}>{String(field.value)}</span>
                            </div>
                          ))}
                        </div>
                      </section>
                    )}

                    {/* Hashes Section */}
                    {hashes && Object.keys(hashes).length > 0 && (
                      <section className="space-y-2 group/section">
                        <div className="flex items-center justify-between">
                          <h4 className="text-[10px] font-bold text-white/40 uppercase tracking-widest">{t('genData.hashes')}</h4>
                          <button
                            onClick={() => copyToClipboard(JSON.stringify(hashes, null, 2), 'hashes')}
                            className="opacity-0 group-hover/section:opacity-100 p-1 rounded hover:bg-white/10 text-white/40 hover:text-white transition-all"
                            title={t('genData.copyHashes')}
                          >
                            {copiedField === 'hashes' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                          </button>
                        </div>
                        <div className="space-y-1">
                          {Object.entries(hashes).map(([key, value]) => (
                            <div key={key} className="flex items-center justify-between bg-white/5 px-2.5 py-1.5 rounded-lg group hover:bg-white/10 transition-colors">
                              <span className="text-[10px] text-white/50">{key}</span>
                              <span className="text-[10px] font-mono text-white/70 truncate max-w-[140px]" title={value}>{value}</span>
                            </div>
                          ))}
                        </div>
                      </section>
                    )}

                    {/* Other Fields (fallback) */}
                    {otherFields.length > 0 && (
                      <section className="space-y-2">
                        <h4 className="text-[10px] font-bold text-white/40 uppercase tracking-widest">{t('genData.other')}</h4>
                        <div className="space-y-2">
                          {otherFields.map(([key, value]) => {
                            const displayKey = key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())
                            const isObject = typeof value === 'object'
                            const displayValue = isObject ? JSON.stringify(value, null, 2) : String(value)

                            return (
                              <div key={key} className="group">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-[9px] text-white/40 uppercase">{displayKey}</span>
                                  <button
                                    onClick={() => copyToClipboard(displayValue, key)}
                                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 text-white/40 hover:text-white transition-all"
                                  >
                                    {copiedField === key ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                                  </button>
                                </div>
                                <div className="bg-white/5 p-2 rounded-lg text-xs text-white/80 break-words">
                                  {isObject ? (
                                    <pre className="whitespace-pre-wrap font-mono text-[10px] max-h-24 overflow-y-auto">{displayValue}</pre>
                                  ) : (
                                    <span>{displayValue}</span>
                                  )}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </section>
                    )}

                  </>
                )
              })()}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default FullscreenMediaViewer
