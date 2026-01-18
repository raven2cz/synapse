/**
 * FullscreenMediaViewer Component - v3.0.0
 * 
 * FIXED: Animation uses direct CSS classes (no CSS variables)
 * FIXED: Image error handling with fallback
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { clsx } from 'clsx'
import {
  X, ChevronLeft, ChevronRight, Download, ExternalLink, Eye, EyeOff,
  ZoomIn, ZoomOut, RotateCcw, Repeat, Play, Pause, Volume2, VolumeX,
  Maximize, SkipBack, SkipForward, Loader2,
} from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'

// ============================================================================
// Types & Constants
// ============================================================================
const SLIDE_DURATION = 300

type VideoQuality = 'sd' | 'hd' | 'fhd'
type VideoFit = 'fit' | 'fill' | 'original'

const QUALITY_WIDTHS: Record<VideoQuality, number> = { sd: 450, hd: 720, fhd: 1080 }
const FIT_LABELS: Record<VideoFit, string> = { fit: 'FIT', fill: 'FILL', original: 'ORIG' }

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
function getCivitaiVideoUrl(url: string, quality: VideoQuality = 'sd'): string {
  if (!url?.includes('civitai.com')) return url
  try {
    const urlObj = new URL(url)
    const parts = urlObj.pathname.split('/')
    const idx = parts.findIndex(p => p.includes('=') || p.startsWith('width'))
    const params = `transcode=true,width=${QUALITY_WIDTHS[quality]},optimized=true`
    if (idx >= 0) parts[idx] = params
    else if (parts.length >= 3) parts.splice(-1, 0, params)
    const lastIdx = parts.length - 1
    if (lastIdx >= 0) parts[lastIdx] = parts[lastIdx].replace(/\.[^.]+$/, '') + '.mp4'
    urlObj.pathname = parts.join('/')
    return urlObj.toString()
  } catch { return url }
}

function getCivitaiThumbnailUrl(url: string, width = 450): string {
  if (!url?.includes('civitai.com')) return url
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
    (lower.includes('civitai.com') && lower.includes('transcode=true') && !lower.includes('anim=false'))
}

// ============================================================================
// CSS Animation Styles - embedded directly to ensure they work
// ============================================================================
const ANIMATION_STYLES = `
  .fmv-enter-from-right {
    animation: fmvEnterFromRight ${SLIDE_DURATION}ms ease-out forwards;
  }
  .fmv-enter-from-left {
    animation: fmvEnterFromLeft ${SLIDE_DURATION}ms ease-out forwards;
  }
  .fmv-exit-to-left {
    animation: fmvExitToLeft ${SLIDE_DURATION}ms ease-out forwards;
  }
  .fmv-exit-to-right {
    animation: fmvExitToRight ${SLIDE_DURATION}ms ease-out forwards;
  }
  @keyframes fmvEnterFromRight {
    0% { transform: translateX(100%); }
    100% { transform: translateX(0%); }
  }
  @keyframes fmvEnterFromLeft {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(0%); }
  }
  @keyframes fmvExitToLeft {
    0% { transform: translateX(0%); }
    100% { transform: translateX(-100%); }
  }
  @keyframes fmvExitToRight {
    0% { transform: translateX(0%); }
    100% { transform: translateX(100%); }
  }
`

// ============================================================================
// Component
// ============================================================================
export function FullscreenMediaViewer({
  items, initialIndex = 0, isOpen, onClose, onIndexChange,
}: FullscreenMediaViewerProps) {
  const nsfwBlurEnabled = useSettingsStore((s) => s.nsfwBlurEnabled)

  // Navigation & animation state
  const [currentIndex, setCurrentIndex] = useState(initialIndex)
  const [displayIndex, setDisplayIndex] = useState(initialIndex) // What's actually shown
  const [animationState, setAnimationState] = useState<{
    isAnimating: boolean
    direction: 'left' | 'right' | null
    fromIndex: number | null
  }>({ isAnimating: false, direction: null, fromIndex: null })
  
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

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const controlsTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const thumbnailsRef = useRef<HTMLDivElement>(null)
  const thumbRefs = useRef<Map<number, HTMLButtonElement>>(new Map())

  // Derived
  const currentItem = items[displayIndex]
  const isVideo = currentItem?.type === 'video' || isLikelyVideo(currentItem?.url || '')
  const shouldBlur = currentItem?.nsfw && nsfwBlurEnabled && !isRevealed

  const videoUrl = useMemo(() => {
    if (!currentItem?.url || !isVideo) return ''
    return currentItem.url.includes('civitai.com') ? getCivitaiVideoUrl(currentItem.url, videoQuality) : currentItem.url
  }, [currentItem?.url, isVideo, videoQuality])

  const downloadUrl = useMemo(() => {
    if (!currentItem?.url) return ''
    return currentItem.url.includes('civitai.com') && isVideo ? getCivitaiVideoUrl(currentItem.url, 'fhd') : currentItem.url
  }, [currentItem?.url, isVideo])

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  // Helpers
  const getThumbUrl = useCallback((item: MediaItem) => {
    if (!item) return ''
    if (item.thumbnailUrl) return item.thumbnailUrl
    if (item.url?.includes('civitai.com')) return getCivitaiThumbnailUrl(item.url, 450)
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
      setDisplayIndex(initialIndex)
      setAnimationState({ isAnimating: false, direction: null, fromIndex: null })
      setIsRevealed(false)
      setImageZoom(1)
      setImagePosition({ x: 0, y: 0 })
      setIsPlaying(false)
      setCurrentTime(0)
      setDuration(0)
      setShowControls(true)
      setVideoQuality('sd')
      setVideoFit('fit')
      setTimeout(() => scrollToThumb(initialIndex), 100)
    }
  }, [isOpen, initialIndex, scrollToThumb])

  // Reset media on display index change (when not animating)
  useEffect(() => {
    if (!animationState.isAnimating) {
      setIsRevealed(false)
      setImageZoom(1)
      setImagePosition({ x: 0, y: 0 })
      setIsPlaying(false)
      setCurrentTime(0)
      setDuration(0)
    }
  }, [displayIndex, animationState.isAnimating])

  // Autoplay
  useEffect(() => {
    if (!isOpen || !isVideo || shouldBlur || animationState.isAnimating) return
    const v = videoRef.current
    if (!v) return
    const t = setTimeout(() => v.play().catch(() => {}), 100)
    return () => clearTimeout(t)
  }, [isOpen, isVideo, shouldBlur, displayIndex, videoUrl, animationState.isAnimating])

  // Auto-hide controls
  const resetControlsTimeout = useCallback(() => {
    if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
    setShowControls(true)
    controlsTimeoutRef.current = setTimeout(() => { if (isPlaying) setShowControls(false) }, 3000)
  }, [isPlaying])

  useEffect(() => () => { if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current) }, [])

  // ============================================================================
  // NAVIGATION - Fixed animation logic
  // ============================================================================
  const navigateTo = useCallback((newIdx: number) => {
    if (newIdx < 0 || newIdx >= items.length || newIdx === currentIndex || animationState.isAnimating) return
    
    const goingNext = newIdx > currentIndex
    const direction = goingNext ? 'left' : 'right'
    
    // Start animation - keep showing old content, prepare new
    setAnimationState({
      isAnimating: true,
      direction,
      fromIndex: currentIndex,
    })
    setCurrentIndex(newIdx)
    
    // Immediately update display to new index (for entering slide)
    // The exiting slide shows fromIndex
    setDisplayIndex(newIdx)
    onIndexChange?.(newIdx)

    // After animation, clean up
    setTimeout(() => {
      setAnimationState({ isAnimating: false, direction: null, fromIndex: null })
      scrollToThumb(newIdx)
    }, SLIDE_DURATION)
  }, [currentIndex, items.length, onIndexChange, animationState.isAnimating, scrollToThumb])

  const goToPrevious = useCallback(() => { if (currentIndex > 0) navigateTo(currentIndex - 1) }, [currentIndex, navigateTo])
  const goToNext = useCallback(() => { if (currentIndex < items.length - 1) navigateTo(currentIndex + 1) }, [currentIndex, items.length, navigateTo])

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
    if (thumbnailsRef.current) thumbnailsRef.current.scrollLeft += e.deltaY
  }, [])

  // Download
  const handleDownload = useCallback(async () => {
    try {
      const res = await fetch(downloadUrl)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `synapse_${displayIndex + 1}.${isVideo ? 'mp4' : 'jpg'}`
      a.click()
      URL.revokeObjectURL(url)
    } catch { window.open(downloadUrl, '_blank') }
  }, [downloadUrl, isVideo, displayIndex])

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
      }
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [isOpen, isVideo, goToPrevious, goToNext, togglePlay, toggleMute, toggleLoop, toggleFullscreen, cycleVideoFit, zoomIn, zoomOut, resetZoom, volume, skip, onClose])

  const formatTime = (s: number) => !isFinite(s) ? '0:00' : `${Math.floor(s / 60)}:${Math.floor(s % 60).toString().padStart(2, '0')}`

  // ============================================================================
  // Render slide content
  // ============================================================================
  const renderSlide = useCallback((item: MediaItem, isExitingSlide: boolean) => {
    const itemIsVideo = item.type === 'video' || isLikelyVideo(item.url)
    const itemBlur = item.nsfw && nsfwBlurEnabled && !isRevealed
    const thumb = getThumbUrl(item)
    const useThumb = isExitingSlide || animationState.isAnimating

    if (itemBlur) {
      return (
        <div className="w-full h-full flex items-center justify-center">
          <div className="text-center">
            <div className="w-24 h-24 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center mx-auto mb-6">
              <EyeOff className="w-12 h-12 text-white/60" />
            </div>
            <p className="text-white/80 text-xl mb-6">NSFW Content</p>
            {!isExitingSlide && !animationState.isAnimating && (
              <button onClick={() => setIsRevealed(true)} className="px-8 py-3 rounded-xl bg-indigo-500 hover:bg-indigo-400 text-white font-medium transition-colors">
                Click to reveal
              </button>
            )}
          </div>
        </div>
      )
    }

    if (itemIsVideo) {
      if (useThumb) {
        return (
          <div className="relative w-full h-full flex items-center justify-center">
            <img src={thumb} alt="" className="max-w-full max-h-full object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-16 h-16 rounded-full bg-black/40 flex items-center justify-center">
                <Play className="w-8 h-8 text-white fill-white ml-1" />
              </div>
            </div>
          </div>
        )
      }
      const vUrl = item.url.includes('civitai.com') ? getCivitaiVideoUrl(item.url, videoQuality) : item.url
      return (
        <div className="relative w-full h-full flex items-center justify-center">
          <video ref={videoRef} src={vUrl} poster={thumb} loop={isLooping} muted={isMuted} playsInline
            className={clsx('transition-all duration-300', getVideoClass())} onClick={togglePlay}
            onPlay={() => setIsPlaying(true)} onPause={() => setIsPlaying(false)}
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
            onDurationChange={(e) => setDuration(e.currentTarget.duration)}
            onWaiting={() => setIsBuffering(true)} onCanPlay={() => setIsBuffering(false)} onLoadedData={() => setIsBuffering(false)} />
          {isBuffering && <div className="absolute inset-0 flex items-center justify-center bg-black/20"><Loader2 className="w-12 h-12 text-white animate-spin" /></div>}
          {!isPlaying && !isBuffering && (
            <button onClick={togglePlay} className="absolute inset-0 flex items-center justify-center group">
              <div className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center transition-all group-hover:bg-white/30 group-hover:scale-110">
                <Play className="w-10 h-10 text-white fill-white ml-1" />
              </div>
            </button>
          )}
        </div>
      )
    }

    // Image
    const imgSrc = useThumb ? thumb : item.url
    return (
      <img src={imgSrc} alt=""
        className={clsx('max-w-full max-h-full object-contain select-none', !isExitingSlide && !animationState.isAnimating && !isDragging && 'transition-transform duration-150 ease-out')}
        style={!isExitingSlide && !animationState.isAnimating ? { transform: `scale(${imageZoom}) translate(${imagePosition.x / imageZoom}px, ${imagePosition.y / imageZoom}px)`, cursor: isDragging ? 'grabbing' : 'grab' } : undefined}
        draggable={false}
        onError={(e) => { 
          const img = e.target as HTMLImageElement
          if (img.src !== item.url) img.src = item.url 
        }}
      />
    )
  }, [nsfwBlurEnabled, isRevealed, animationState.isAnimating, videoQuality, isLooping, isMuted, getVideoClass, togglePlay, isBuffering, isPlaying, imageZoom, imagePosition, isDragging, getThumbUrl])

  if (!isOpen || !currentItem) return null

  // Determine animation classes
  const { isAnimating, direction, fromIndex } = animationState
  const exitingItem = fromIndex !== null ? items[fromIndex] : null

  // Animation classes based on direction
  let enterClass = ''
  let exitClass = ''
  if (isAnimating && direction) {
    // Going left (next): enter from right, exit to left
    // Going right (prev): enter from left, exit to right
    enterClass = direction === 'left' ? 'fmv-enter-from-right' : 'fmv-enter-from-left'
    exitClass = direction === 'left' ? 'fmv-exit-to-left' : 'fmv-exit-to-right'
  }

  return (
    <div ref={containerRef} className="fixed inset-0 z-[100] bg-black flex flex-col overflow-hidden"
      onClick={onClose} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>
      
      {/* Embedded CSS for animations */}
      <style dangerouslySetInnerHTML={{ __html: ANIMATION_STYLES }} />

      {/* Top bar */}
      <div className={clsx('absolute top-0 left-0 right-0 z-30 transition-all duration-300', showControls ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-full')} onClick={e => e.stopPropagation()}>
        <div className="p-4 bg-gradient-to-b from-black/80 to-transparent">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-white/80 font-medium px-3 py-1.5 rounded-lg bg-white/10 backdrop-blur-sm">{displayIndex + 1} / {items.length}</span>
              {isVideo && !isAnimating && <span className="text-white/60 text-sm px-2 py-1 rounded bg-indigo-500/30 text-indigo-300">{FIT_LABELS[videoFit]}</span>}
            </div>
            <div className="flex items-center gap-2">
              {currentItem.nsfw && nsfwBlurEnabled && (
                <button onClick={e => { e.stopPropagation(); setIsRevealed(!isRevealed) }}
                  className={clsx('p-2.5 rounded-xl backdrop-blur-sm transition-all', isRevealed ? 'bg-red-500/30 text-red-300' : 'bg-white/10 text-white/60 hover:bg-white/20')}>
                  {isRevealed ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              )}
              {isVideo && !isAnimating && (
                <button onClick={e => { e.stopPropagation(); toggleLoop() }}
                  className={clsx('p-2.5 rounded-xl backdrop-blur-sm transition-all', isLooping ? 'bg-indigo-500/30 text-indigo-300' : 'bg-white/10 text-white/60')}>
                  <Repeat className="w-5 h-5" />
                </button>
              )}
              {!isVideo && !isAnimating && (
                <>
                  <button onClick={e => { e.stopPropagation(); zoomOut() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white"><ZoomOut className="w-5 h-5" /></button>
                  <span className="text-white/80 text-sm min-w-[4rem] text-center font-medium">{Math.round(imageZoom * 100)}%</span>
                  <button onClick={e => { e.stopPropagation(); zoomIn() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white"><ZoomIn className="w-5 h-5" /></button>
                  <button onClick={e => { e.stopPropagation(); resetZoom() }} className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white"><RotateCcw className="w-5 h-5" /></button>
                </>
              )}
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

      {/* Main content area */}
      <div ref={contentRef} className="absolute inset-0 overflow-hidden" style={{ paddingTop: '64px', paddingBottom: '160px' }}
        onClick={e => e.stopPropagation()} onMouseDown={!isAnimating ? handleMouseDown : undefined}
        onDoubleClick={!isAnimating ? handleDoubleClick : undefined} onWheel={!isAnimating ? handleWheel : undefined}>
        
        {/* EXITING slide (old) - only during animation */}
        {isAnimating && exitingItem && (
          <div className={clsx('absolute inset-0 flex items-center justify-center px-4', exitClass)}>
            {renderSlide(exitingItem, true)}
          </div>
        )}

        {/* CURRENT slide (new/active) */}
        <div className={clsx('absolute inset-0 flex items-center justify-center px-4', isAnimating ? enterClass : '')}>
          {renderSlide(currentItem, false)}
        </div>
      </div>

      {/* Video controls */}
      {isVideo && !shouldBlur && !isAnimating && (
        <div className={clsx('absolute left-0 right-0 bottom-[160px] z-30 transition-all duration-300', showControls ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-full')} onClick={e => e.stopPropagation()}>
          <div className="px-6 py-4 bg-gradient-to-t from-black/80 to-transparent">
            <div className="group mb-4">
              <div className="h-1.5 bg-white/20 rounded-full cursor-pointer relative group-hover:h-2.5 transition-all" onClick={handleProgressClick}>
                <div className="absolute inset-y-0 left-0 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full" style={{ width: `${progress}%` }} />
                <div className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-lg opacity-0 group-hover:opacity-100 transition-opacity" style={{ left: `calc(${progress}% - 8px)` }} />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button onClick={togglePlay} className="p-2 rounded-lg hover:bg-white/10 text-white">{isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 fill-white" />}</button>
                <button onClick={() => skip(-10)} className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white"><SkipBack className="w-5 h-5" /></button>
                <button onClick={() => skip(10)} className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white"><SkipForward className="w-5 h-5" /></button>
                <div className="flex items-center gap-2 group/vol">
                  <button onClick={toggleMute} className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white">{isMuted || volume === 0 ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}</button>
                  <input type="range" min="0" max="1" step="0.05" value={volume} onChange={handleVolumeChange} className="w-0 group-hover/vol:w-20 transition-all accent-indigo-500 opacity-0 group-hover/vol:opacity-100" />
                </div>
                <span className="text-white/70 text-sm font-mono ml-2">{formatTime(currentTime)} / {formatTime(duration)}</span>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={cycleVideoFit} className="px-3 py-1.5 rounded-lg text-sm font-medium bg-indigo-500/30 text-indigo-300 hover:bg-indigo-500/40">{FIT_LABELS[videoFit]}</button>
                <span className={clsx('px-2 py-1 rounded text-xs font-medium cursor-pointer', isLooping ? 'bg-indigo-500/30 text-indigo-300' : 'bg-white/10 text-white/50')} onClick={() => setIsLooping(l => !l)}>{isLooping ? 'LOOP' : 'ONCE'}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Thumbnails */}
      {items.length > 1 && (
        <div className={clsx('absolute bottom-0 left-0 right-0 z-20 transition-all duration-300', showControls ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-full')} onClick={e => e.stopPropagation()}>
          <div className="bg-gradient-to-t from-black/90 via-black/70 to-transparent">
            <div ref={thumbnailsRef} className="flex gap-3 px-4 overflow-x-auto scrollbar-thin scrollbar-thumb-white/20" onWheel={handleThumbWheel} style={{ paddingTop: 20, paddingBottom: 16, scrollBehavior: 'smooth' }}>
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
                        if (img.src !== item.url) img.src = item.url 
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
    </div>
  )
}

export default FullscreenMediaViewer
