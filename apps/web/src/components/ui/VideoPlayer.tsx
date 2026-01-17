/**
 * VideoPlayer Component
 *
 * Full-featured video player with custom controls.
 * Used in fullscreen viewer and modal dialogs.
 *
 * Features:
 * - Custom control bar with gradient background
 * - Progress bar with seek and buffer indicator
 * - Play/pause with center button
 * - Mute/unmute with volume slider
 * - Fullscreen toggle
 * - Keyboard shortcuts
 * - Time display
 * - Loading and error states
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { clsx } from 'clsx'
import {
  Play,
  Pause,
  Volume2,
  Volume1,
  VolumeX,
  Maximize,
  Minimize,
  SkipBack,
  SkipForward,
  Loader2,
  AlertTriangle,
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
    const saved = localStorage.getItem(STORAGE_KEYS.VOLUME)
    return saved ? parseFloat(saved) : PLAYER_SETTINGS.DEFAULT_VOLUME
  })
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [buffered, setBuffered] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showControlsOverlay, setShowControlsOverlay] = useState(true)
  const [isDraggingProgress, setIsDraggingProgress] = useState(false)
  const [showVolumeSlider, setShowVolumeSlider] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [showCenterPlay, setShowCenterPlay] = useState(!autoPlay)

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const controlsTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Progress percentage
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0
  const bufferedPercent = duration > 0 ? (buffered / duration) * 100 : 0

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

    const handlePlay = () => {
      setIsPlaying(true)
      setShowCenterPlay(false)
    }
    const handlePause = () => {
      setIsPlaying(false)
      setShowCenterPlay(true)
    }
    const handleTimeUpdate = () => setCurrentTime(video.currentTime)
    const handleDurationChange = () => setDuration(video.duration)
    const handleProgress = () => {
      if (video.buffered.length > 0) {
        setBuffered(video.buffered.end(video.buffered.length - 1))
      }
    }
    const handleEnded = () => {
      setIsPlaying(false)
      setShowCenterPlay(true)
      onEnded?.()
    }
    const handleError = () => {
      setHasError(true)
      setIsLoading(false)
      onError?.(new Error(`Failed to load video: ${src}`))
    }
    const handleLoadStart = () => {
      setIsLoading(true)
      setHasError(false)
    }
    const handleCanPlay = () => {
      setIsLoading(false)
    }
    const handleWaiting = () => {
      setIsLoading(true)
    }
    const handlePlaying = () => {
      setIsLoading(false)
    }

    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)
    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('durationchange', handleDurationChange)
    video.addEventListener('progress', handleProgress)
    video.addEventListener('ended', handleEnded)
    video.addEventListener('error', handleError)
    video.addEventListener('loadstart', handleLoadStart)
    video.addEventListener('canplay', handleCanPlay)
    video.addEventListener('waiting', handleWaiting)
    video.addEventListener('playing', handlePlaying)

    return () => {
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('durationchange', handleDurationChange)
      video.removeEventListener('progress', handleProgress)
      video.removeEventListener('ended', handleEnded)
      video.removeEventListener('error', handleError)
      video.removeEventListener('loadstart', handleLoadStart)
      video.removeEventListener('canplay', handleCanPlay)
      video.removeEventListener('waiting', handleWaiting)
      video.removeEventListener('playing', handlePlaying)
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
    if (!isDraggingProgress) return
    handleProgressClick(e)
  }, [isDraggingProgress, handleProgressClick])

  const handleProgressMouseUp = useCallback(() => {
    setIsDraggingProgress(false)
  }, [])

  const handleCenterClick = useCallback(() => {
    togglePlay()
  }, [togglePlay])

  // Volume icon based on level
  const VolumeIcon = isMuted || volume === 0 ? VolumeX : volume < 0.5 ? Volume1 : Volume2

  return (
    <div
      ref={containerRef}
      className={clsx(
        'relative bg-black overflow-hidden group',
        className
      )}
      onMouseMove={resetControlsTimeout}
      onMouseLeave={() => {
        if (isPlaying) setShowControlsOverlay(false)
      }}
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
        onClick={handleCenterClick}
      />

      {/* Loading overlay */}
      {isLoading && !hasError && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/30">
          <Loader2 className="w-12 h-12 text-white animate-spin" />
        </div>
      )}

      {/* Error overlay */}
      {hasError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 gap-2">
          <AlertTriangle className="w-12 h-12 text-red-500" />
          <span className="text-white/70">Failed to load video</span>
        </div>
      )}

      {/* Center play button */}
      {showCenterPlay && !isLoading && !hasError && (
        <button
          onClick={handleCenterClick}
          className={clsx(
            'absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2',
            'w-20 h-20 rounded-full bg-white/20 backdrop-blur-sm',
            'flex items-center justify-center',
            'hover:bg-white/30 hover:scale-110 transition-all duration-200',
          )}
        >
          <Play className="w-10 h-10 text-white ml-1" fill="white" />
        </button>
      )}

      {/* Controls */}
      {showControls && !hasError && (
        <div
          className={clsx(
            'absolute bottom-0 left-0 right-0 px-4 pb-4 pt-12',
            'bg-gradient-to-t from-black/80 via-black/40 to-transparent',
            'transition-opacity duration-300',
            showControlsOverlay ? 'opacity-100' : 'opacity-0 pointer-events-none'
          )}
        >
          {/* Progress bar */}
          <div
            ref={progressRef}
            className="relative h-1.5 bg-white/30 rounded-full mb-3 cursor-pointer group/progress hover:h-2 transition-all"
            onClick={handleProgressClick}
            onMouseDown={handleProgressMouseDown}
            onMouseMove={handleProgressMouseMove}
            onMouseUp={handleProgressMouseUp}
            onMouseLeave={handleProgressMouseUp}
          >
            {/* Buffer indicator */}
            <div
              className="absolute inset-y-0 left-0 bg-white/30 rounded-full"
              style={{ width: `${bufferedPercent}%` }}
            />
            {/* Progress fill */}
            <div
              className="absolute inset-y-0 left-0 bg-synapse rounded-full"
              style={{ width: `${progress}%` }}
            />
            {/* Progress handle */}
            <div
              className={clsx(
                'absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-lg',
                'opacity-0 group-hover/progress:opacity-100 transition-opacity',
                isDraggingProgress && 'opacity-100'
              )}
              style={{ left: `calc(${progress}% - 8px)` }}
            />
          </div>

          {/* Control buttons */}
          <div className="flex items-center gap-2">
            {/* Play/Pause */}
            <button
              onClick={togglePlay}
              className="p-2 text-white hover:text-synapse hover:bg-white/10 rounded-lg transition-colors"
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
              className="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
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
              className="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
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
                className="p-2 text-white hover:text-synapse hover:bg-white/10 rounded-lg transition-colors"
              >
                <VolumeIcon className="w-5 h-5" />
              </button>

              {/* Volume slider */}
              <div
                className={clsx(
                  'absolute left-full ml-1 flex items-center px-2 py-1 bg-black/80 backdrop-blur-sm rounded-lg',
                  'transition-all duration-200',
                  showVolumeSlider ? 'opacity-100 w-24' : 'opacity-0 w-0 overflow-hidden pointer-events-none'
                )}
              >
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={isMuted ? 0 : volume}
                  onChange={(e) => changeVolume(parseFloat(e.target.value))}
                  className="w-full h-1 accent-synapse cursor-pointer"
                />
              </div>
            </div>

            {/* Time display */}
            <div className="ml-2 text-sm text-white/70 font-mono tabular-nums">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Fullscreen */}
            <button
              onClick={toggleFullscreen}
              className="p-2 text-white hover:text-synapse hover:bg-white/10 rounded-lg transition-colors"
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
