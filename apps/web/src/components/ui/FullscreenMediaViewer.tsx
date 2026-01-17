/**
 * FullscreenMediaViewer Component
 *
 * Modal overlay for viewing media in fullscreen.
 * Supports both images and videos with navigation.
 *
 * Features:
 * - Image zoom and pan
 * - Video player with full controls and audio
 * - Keyboard navigation (arrows, escape)
 * - Previous/Next navigation
 * - NSFW blur support
 */

import { useState, useEffect, useCallback } from 'react'
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
} from 'lucide-react'
import { useSettingsStore } from '@/stores/settingsStore'
import { detectMediaType } from '@/lib/media'
import type { MediaType } from '@/lib/media'
import { VideoPlayer } from './VideoPlayer'

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
  /** Currently selected index */
  initialIndex?: number
  /** Whether viewer is open */
  isOpen: boolean
  /** Close handler */
  onClose: () => void
  /** Optional callback when index changes */
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
  
  // Current item
  const currentItem = items[currentIndex]
  const mediaType = currentItem?.type || detectMediaType(currentItem?.url || '').type
  const isVideo = mediaType === 'video'
  const shouldBlur = currentItem?.nsfw && nsfwBlurEnabled && !isRevealed
  
  // Reset state when opening or changing item
  useEffect(() => {
    if (isOpen) {
      setCurrentIndex(initialIndex)
      setIsRevealed(false)
      setImageZoom(1)
      setImagePosition({ x: 0, y: 0 })
    }
  }, [isOpen, initialIndex])
  
  // Reset reveal state when changing items
  useEffect(() => {
    setIsRevealed(false)
    setImageZoom(1)
    setImagePosition({ x: 0, y: 0 })
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
          setImageZoom((z) => Math.min(4, z + 0.25))
          break
        case '-':
          setImageZoom((z) => Math.max(0.5, z - 0.25))
          break
        case '0':
          setImageZoom(1)
          setImagePosition({ x: 0, y: 0 })
          break
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose, goToPrevious, goToNext])
  
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
  
  if (!isOpen || !currentItem) return null
  
  return (
    <div
      className="fixed inset-0 z-50 bg-black/95 backdrop-blur-sm"
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
          
          {/* Zoom controls (images only) */}
          {!isVideo && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setImageZoom((z) => Math.max(0.5, z - 0.25))
                }}
                className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                title="Zoom out"
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
                title="Zoom in"
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
          
          {/* Open external */}
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
          {/* Previous */}
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
          
          {/* Next */}
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
            <VideoPlayer
              src={currentItem.url}
              poster={currentItem.thumbnailUrl}
              autoPlay
              showControls
              enableShortcuts
              className="w-full h-full"
            />
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
      
      {/* Metadata panel (optional - show on hover or always) */}
      {currentItem.meta && Object.keys(currentItem.meta).length > 0 && (
        <div className="absolute bottom-0 left-0 right-0 z-10 p-4 bg-gradient-to-t from-black/80 to-transparent">
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
