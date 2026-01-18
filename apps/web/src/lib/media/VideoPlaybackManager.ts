/**
 * VideoPlaybackManager - Global singleton for optimized video playback
 * 
 * CRITICAL PERFORMANCE OPTIMIZATION:
 * - Limits concurrent playing videos to MAX_CONCURRENT (3)
 * - Uses queue system for staggered playback
 * - Prioritizes videos by visibility (intersection ratio)
 * - Prevents browser thread blocking from too many decode operations
 * 
 * This solves the "sekání" (stuttering) issue when multiple videos
 * try to play simultaneously.
 */

type VideoEntry = {
  element: HTMLVideoElement
  priority: number // Higher = more visible
  isPlaying: boolean
}

class VideoPlaybackManagerClass {
  private static instance: VideoPlaybackManagerClass
  private videos: Map<string, VideoEntry> = new Map()
  private MAX_CONCURRENT = 3
  private STAGGER_DELAY = 100 // ms between starting videos
  private isProcessing = false

  private constructor() {
    // Singleton
  }

  static getInstance(): VideoPlaybackManagerClass {
    if (!VideoPlaybackManagerClass.instance) {
      VideoPlaybackManagerClass.instance = new VideoPlaybackManagerClass()
    }
    return VideoPlaybackManagerClass.instance
  }

  /**
   * Register a video element for managed playback
   */
  register(id: string, element: HTMLVideoElement): void {
    if (!this.videos.has(id)) {
      this.videos.set(id, {
        element,
        priority: 0,
        isPlaying: false
      })
    }
  }

  /**
   * Unregister a video element
   */
  unregister(id: string): void {
    const entry = this.videos.get(id)
    if (entry) {
      // Pause before removing
      try {
        entry.element.pause()
      } catch (e) {
        // Ignore
      }
      this.videos.delete(id)
    }
  }

  /**
   * Request playback - called when video enters viewport
   * @param id - Unique video ID
   * @param priority - Higher number = higher priority (e.g., intersection ratio * 100)
   */
  requestPlay(id: string, priority: number = 50): void {
    const entry = this.videos.get(id)
    if (!entry) return

    entry.priority = priority
    this.processQueue()
  }

  /**
   * Request pause - called when video leaves viewport
   */
  requestPause(id: string): void {
    const entry = this.videos.get(id)
    if (!entry) return

    entry.priority = -1 // Mark as not wanting to play
    
    if (entry.isPlaying) {
      try {
        entry.element.pause()
        entry.isPlaying = false
      } catch (e) {
        // Ignore
      }
    }

    // Re-process queue to potentially start other videos
    this.processQueue()
  }

  /**
   * Process the playback queue - ensure only MAX_CONCURRENT videos are playing
   */
  private async processQueue(): Promise<void> {
    if (this.isProcessing) return
    this.isProcessing = true

    try {
      // Get all entries sorted by priority (highest first)
      const entries = Array.from(this.videos.entries())
        .filter(([_, e]) => e.priority >= 0) // Only those wanting to play
        .sort((a, b) => b[1].priority - a[1].priority)

      // Count currently playing
      let playingCount = 0
      const shouldPlay: string[] = []
      const shouldPause: string[] = []

      for (const [id, entry] of entries) {
        if (playingCount < this.MAX_CONCURRENT) {
          shouldPlay.push(id)
          playingCount++
        } else if (entry.isPlaying) {
          shouldPause.push(id)
        }
      }

      // Pause videos that shouldn't be playing
      for (const id of shouldPause) {
        const entry = this.videos.get(id)
        if (entry && entry.isPlaying) {
          try {
            entry.element.pause()
            entry.isPlaying = false
          } catch (e) {
            // Ignore
          }
        }
      }

      // Start videos with staggered delay
      for (let i = 0; i < shouldPlay.length; i++) {
        const id = shouldPlay[i]
        const entry = this.videos.get(id)
        
        if (entry && !entry.isPlaying) {
          // Stagger start
          await this.delay(this.STAGGER_DELAY * i)
          
          try {
            const playPromise = entry.element.play()
            if (playPromise !== undefined) {
              await playPromise
            }
            entry.isPlaying = true
          } catch (e) {
            // Autoplay blocked or other error - ignore
            entry.isPlaying = false
          }
        }
      }
    } finally {
      this.isProcessing = false
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * Get stats for debugging
   */
  getStats(): { total: number; playing: number; maxConcurrent: number } {
    const playing = Array.from(this.videos.values()).filter(e => e.isPlaying).length
    return {
      total: this.videos.size,
      playing,
      maxConcurrent: this.MAX_CONCURRENT
    }
  }

  /**
   * Pause all videos (e.g., when leaving page)
   */
  pauseAll(): void {
    for (const entry of this.videos.values()) {
      if (entry.isPlaying) {
        try {
          entry.element.pause()
          entry.isPlaying = false
        } catch (e) {
          // Ignore
        }
      }
    }
  }
}

// Export singleton instance
export const VideoPlaybackManager = VideoPlaybackManagerClass.getInstance()

// React hook for easy use
import { useEffect, useRef, useCallback } from 'react'

/**
 * Hook for managed video playback
 * 
 * Usage:
 * ```tsx
 * const { videoRef, requestPlay, requestPause } = useManagedVideo('unique-id')
 * 
 * // In IntersectionObserver callback:
 * if (entry.isIntersecting) {
 *   requestPlay(entry.intersectionRatio * 100)
 * } else {
 *   requestPause()
 * }
 * ```
 */
export function useManagedVideo(id: string) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const registeredRef = useRef(false)

  useEffect(() => {
    const video = videoRef.current
    if (video && !registeredRef.current) {
      VideoPlaybackManager.register(id, video)
      registeredRef.current = true
    }

    return () => {
      VideoPlaybackManager.unregister(id)
      registeredRef.current = false
    }
  }, [id])

  const requestPlay = useCallback((priority: number = 50) => {
    VideoPlaybackManager.requestPlay(id, priority)
  }, [id])

  const requestPause = useCallback(() => {
    VideoPlaybackManager.requestPause(id)
  }, [id])

  return { videoRef, requestPlay, requestPause }
}
