/**
 * VideoPlayer Component
 *
 * Full-featured video player with custom controls.
 * Used in fullscreen viewer and modal dialogs.
 *
 * Features:
 * - Custom control bar
 * - Progress bar with seek
 * - Play/pause
 * - Mute/unmute with volume slider
 * - Fullscreen toggle
 * - Keyboard shortcuts
 * - Time display
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { clsx } from 'clsx'
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Minimize,
  SkipBack,
  SkipForward,
} from 'lucide-react'
import { PLAYER_SETTINGS, STORAGE_KEYS } from '@/lib/media'

export interface VideoPlayerProps {
  /** Video URL */
  src: string
  /** Poster image URL */
  poster?: string
  /** CSS class name */
  className?: string
  /** Auto-play on mount */
  autoPlay?: boolean
  /** Loop playback */
  loop?: boolean
  /** Initial muted state */
  muted?: boolean
  /** Show controls */
  showControls?: boolean
  /** Enable keyboard shortcuts */
  enableShortcuts?: boolean
  /** Called when video ends */
  onEnded?: () => void
  /** Called on error */
  onError?: (error: Error) => void
}

/**
 * Format seconds to mm:ss or hh:mm:ss
 */
function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '0:00'

  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)

  if (h > 0) {
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function VideoPlayer({
  src,
  poster,
  className,
  autoPlay = false,
  loop = false,
  muted: initialMuted = false,
  showControls = true,
  enableShortcuts = true,
  onEnded,
  onError,
}: VideoPlayerProps) {
  // State
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(initialMuted)
  const [volume, setVolume] = useState(() => {
    // Load saved volume from localStorage
    const saved = localStorage.getItem(STORAGE_KEYS.VOLUME)
    return saved ? parseFloat(saved) : PLAYER_SETTINGS.DEFAULT_VOLUME
  })
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showControlsOverlay, setShowControlsOverlay] = useState(true)
  const [isDraggingProgress, setIsDraggingProgress] = useState(false)
  const [showVolumeSlider, setShowVolumeSlider] = useState(false)

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const controlsTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Progress percentage
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  // Hide controls after inactivity
  const resetControlsTimeout = useCallback(() => {
    if (controlsTimeoutRef.current) {
      clearTimeout(controlsTimeoutRef.current)
    }
    setShowControlsOverlay(true)

    if (isPlaying) {
      controlsTimeoutRef.current = setTimeout(() => {
        setShowControlsOverlay(false)
      }, 3000)
    }
  }, [isPlaying])

  // Video event handlers
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)
    const handleTimeUpdate = () => setCurrentTime(video.currentTime)
    const handleDurationChange = () => setDuration(video.duration)
    const handleEnded = () => {
      setIsPlaying(false)
      onEnded?.()
    }
    const handleError = () => {
      onError?.(new Error(`Failed to load video: ${src}`))
    }

    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)
    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('durationchange', handleDurationChange)
    video.addEventListener('ended', handleEnded)
    video.addEventListener('error', handleError)

    return () => {
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('durationchange', handleDurationChange)
      video.removeEventListener('ended', handleEnded)
      video.removeEventListener('error', handleError)
    }
  }, [src, onEnded, onError])

  // Fullscreen change handler
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
    }
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    if (!enableShortcuts) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      const video = videoRef.current
      if (!video) return

      switch (e.key) {
        case PLAYER_SETTINGS.SHORTCUTS.PLAY_PAUSE:
          e.preventDefault()
          if (isPlaying) {
            video.pause()
          } else {
            video.play()
          }
          break

        case PLAYER_SETTINGS.SHORTCUTS.MUTE:
          e.preventDefault()
          toggleMute()
          break

        case PLAYER_SETTINGS.SHORTCUTS.FULLSCREEN:
          e.preventDefault()
          toggleFullscreen()
          break

        case PLAYER_SETTINGS.SHORTCUTS.ESCAPE:
          if (isFullscreen) {
            document.exitFullscreen()
          }
          break

        case PLAYER_SETTINGS.SHORTCUTS.SEEK_FORWARD:
          e.preventDefault()
          video.currentTime = Math.min(video.duration, video.currentTime + PLAYER_SETTINGS.SEEK_STEP_SECONDS)
          break

        case PLAYER_SETTINGS.SHORTCUTS.SEEK_BACKWARD:
          e.preventDefault()
          video.currentTime = Math.max(0, video.currentTime - PLAYER_SETTINGS.SEEK_STEP_SECONDS)
          break

        case PLAYER_SETTINGS.SHORTCUTS.VOLUME_UP:
          e.preventDefault()
          changeVolume(Math.min(1, volume + PLAYER_SETTINGS.VOLUME_STEP))
          break

        case PLAYER_SETTINGS.SHORTCUTS.VOLUME_DOWN:
          e.preventDefault()
          changeVolume(Math.max(0, volume - PLAYER_SETTINGS.VOLUME_STEP))
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enableShortcuts, isPlaying, isFullscreen, volume])

  // Control handlers
  const togglePlay = useCallback(() => {
    const video = videoRef.current
    if (!video) return

    if (isPlaying) {
      video.pause()
    } else {
      video.play()
    }
  }, [isPlaying])

  const toggleMute = useCallback(() => {
    const video = videoRef.current
    if (!video) return

    const newMuted = !isMuted
    video.muted = newMuted
    setIsMuted(newMuted)
    localStorage.setItem(STORAGE_KEYS.MUTED, String(newMuted))
  }, [isMuted])

  const changeVolume = useCallback((newVolume: number) => {
    const video = videoRef.current
    if (!video) return

    video.volume = newVolume
    setVolume(newVolume)
    localStorage.setItem(STORAGE_KEYS.VOLUME, String(newVolume))

    if (newVolume > 0 && isMuted) {
      video.muted = false
      setIsMuted(false)
    }
  }, [isMuted])

  const toggleFullscreen = useCallback(async () => {
    if (!containerRef.current) return

    try {
      if (isFullscreen) {
        await document.exitFullscreen()
      } else {
        await containerRef.current.requestFullscreen()
      }
    } catch (err) {
      console.error('Fullscreen error:', err)
    }
  }, [isFullscreen])

  const handleProgressClick = useCallback((e: React.MouseEvent) => {
    const video = videoRef.current
    const progressBar = progressRef.current
    if (!video || !progressBar) return

    const rect = progressBar.getBoundingClientRect()
    const pos = (e.clientX - rect.left) / rect.width
    video.currentTime = pos * video.duration
  }, [])

  const handleProgressMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDraggingProgress(true)
    handleProgressClick(e)
  }, [handleProgressClick])

  const handleProgressMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDraggingProgress) {
      handleProgressClick(e)
    }
  }, [isDraggingProgress, handleProgressClick])

  const handleProgressMouseUp = useCallback(() => {
    setIsDraggingProgress(false)
  }, [])

  // Render
  return (
    <div
      ref={containerRef}
      className={clsx(
        'relative bg-black group',
        isFullscreen && 'fixed inset-0 z-50',
        className
      )}
      onMouseMove={resetControlsTimeout}
      onMouseLeave={() => isPlaying && setShowControlsOverlay(false)}
    >
      {/* Video element */}
      <video
        ref={videoRef}
        src={src}
        poster={poster}
        autoPlay={autoPlay}
        loop={loop}
        muted={isMuted}
        playsInline
        className="w-full h-full object-contain"
        onClick={togglePlay}
      />

      {/* Play overlay (center) */}
      {!isPlaying && (
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
      {showControls && (
        <div
          className={clsx(
            'absolute bottom-0 left-0 right-0 p-4',
            'bg-gradient-to-t from-black/80 to-transparent',
            'transition-opacity duration-300',
            showControlsOverlay ? 'opacity-100' : 'opacity-0 pointer-events-none'
          )}
        >
          {/* Progress bar */}
          <div
            ref={progressRef}
            className="relative h-1 bg-white/30 rounded-full mb-3 cursor-pointer group/progress"
            onClick={handleProgressClick}
            onMouseDown={handleProgressMouseDown}
            onMouseMove={handleProgressMouseMove}
            onMouseUp={handleProgressMouseUp}
            onMouseLeave={handleProgressMouseUp}
          >
            {/* Progress fill */}
            <div
              className="absolute inset-y-0 left-0 bg-synapse rounded-full"
              style={{ width: `${progress}%` }}
            />
            {/* Progress handle */}
            <div
              className={clsx(
                'absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full',
                'opacity-0 group-hover/progress:opacity-100 transition-opacity',
                isDraggingProgress && 'opacity-100'
              )}
              style={{ left: `calc(${progress}% - 6px)` }}
            />
          </div>

          {/* Control buttons */}
          <div className="flex items-center gap-3">
            {/* Play/Pause */}
            <button
              onClick={togglePlay}
              className="p-1.5 text-white hover:text-synapse transition-colors"
            >
              {isPlaying ? (
                <Pause className="w-5 h-5" />
              ) : (
                <Play className="w-5 h-5" />
              )}
            </button>

            {/* Skip backward */}
            <button
              onClick={() => {
                if (videoRef.current) {
                  videoRef.current.currentTime -= PLAYER_SETTINGS.SEEK_STEP_SECONDS
                }
              }}
              className="p-1.5 text-white/70 hover:text-white transition-colors"
            >
              <SkipBack className="w-4 h-4" />
            </button>

            {/* Skip forward */}
            <button
              onClick={() => {
                if (videoRef.current) {
                  videoRef.current.currentTime += PLAYER_SETTINGS.SEEK_STEP_SECONDS
                }
              }}
              className="p-1.5 text-white/70 hover:text-white transition-colors"
            >
              <SkipForward className="w-4 h-4" />
            </button>

            {/* Volume */}
            <div
              className="relative flex items-center"
              onMouseEnter={() => setShowVolumeSlider(true)}
              onMouseLeave={() => setShowVolumeSlider(false)}
            >
              <button
                onClick={toggleMute}
                className="p-1.5 text-white hover:text-synapse transition-colors"
              >
                {isMuted || volume === 0 ? (
                  <VolumeX className="w-5 h-5" />
                ) : (
                  <Volume2 className="w-5 h-5" />
                )}
              </button>

              {/* Volume slider */}
              <div
                className={clsx(
                  'absolute left-full ml-2 flex items-center',
                  'transition-all duration-200',
                  showVolumeSlider ? 'opacity-100 w-20' : 'opacity-0 w-0 overflow-hidden'
                )}
              >
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={isMuted ? 0 : volume}
                  onChange={(e) => changeVolume(parseFloat(e.target.value))}
                  className="w-full h-1 accent-synapse"
                />
              </div>
            </div>

            {/* Time display */}
            <div className="ml-2 text-sm text-white/70 font-mono">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Fullscreen */}
            <button
              onClick={toggleFullscreen}
              className="p-1.5 text-white hover:text-synapse transition-colors"
            >
              {isFullscreen ? (
                <Minimize className="w-5 h-5" />
              ) : (
                <Maximize className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default VideoPlayer
