/**
 * Media Constants
 *
 * Shared constants for media handling and video playback.
 *
 * @author Synapse Team
 */

// ============================================================================
// Preview Settings
// ============================================================================

export const PREVIEW_SETTINGS = {
  /** Duration of auto-play preview in milliseconds */
  PREVIEW_DURATION_MS: 5000,

  /** Whether to loop preview playback */
  PREVIEW_LOOP: true,

  /** Default muted state for previews */
  PREVIEW_MUTED: true,

  /** Delay before starting hover playback (ms) */
  HOVER_DELAY_MS: 100,

  /** Intersection observer threshold for lazy loading */
  LAZY_LOAD_THRESHOLD: 0.1,

  /** Intersection observer root margin for preloading */
  LAZY_LOAD_MARGIN: '200px',
} as const

// ============================================================================
// Video Player Settings
// ============================================================================

export const PLAYER_SETTINGS = {
  /** Keyboard shortcuts */
  SHORTCUTS: {
    PLAY_PAUSE: ' ', // Space
    MUTE: 'm',
    FULLSCREEN: 'f',
    ESCAPE: 'Escape',
    VOLUME_UP: 'ArrowUp',
    VOLUME_DOWN: 'ArrowDown',
    SEEK_FORWARD: 'ArrowRight',
    SEEK_BACKWARD: 'ArrowLeft',
  },

  /** Seek step in seconds */
  SEEK_STEP_SECONDS: 5,

  /** Volume step (0-1) */
  VOLUME_STEP: 0.1,

  /** Default volume (0-1) */
  DEFAULT_VOLUME: 0.7,

  /** Controls auto-hide delay (ms) */
  CONTROLS_HIDE_DELAY: 3000,
} as const

// ============================================================================
// File Extensions
// ============================================================================

export const VIDEO_EXTENSIONS = new Set([
  '.mp4',
  '.webm',
  '.mov',
  '.avi',
  '.mkv',
  '.m4v',
  '.gif',
  '.webp',
])

export const IMAGE_EXTENSIONS = new Set([
  '.jpg',
  '.jpeg',
  '.png',
  '.bmp',
  '.tiff',
  '.tif',
  '.svg',
  '.ico',
  '.heic',
  '.heif',
  '.avif',
])

// ============================================================================
// MIME Types
// ============================================================================

export const VIDEO_MIME_TYPES = new Set([
  'video/mp4',
  'video/webm',
  'video/quicktime',
  'video/x-msvideo',
  'video/x-matroska',
  'video/ogg',
  'video/mpeg',
  'image/gif',
  'image/webp',
])

export const IMAGE_MIME_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/bmp',
  'image/tiff',
  'image/svg+xml',
  'image/x-icon',
  'image/heic',
  'image/heif',
  'image/avif',
])

// ============================================================================
// Supported Formats
// ============================================================================

export const SUPPORTED_VIDEO_FORMATS = [
  'video/mp4',
  'video/webm',
  'video/ogg',
] as const

// ============================================================================
// LocalStorage Keys
// ============================================================================

export const STORAGE_KEYS = {
  /** Saved volume preference */
  VOLUME: 'synapse-video-volume',
  /** Saved mute preference */
  MUTED: 'synapse-video-muted',
} as const
