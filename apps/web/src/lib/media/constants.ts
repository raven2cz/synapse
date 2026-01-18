/**
 * Media Constants
 *
 * Shared constants for media type detection and video playback.
 * 
 * @version 2.1.0 - Updated for Firefox video stability
 */

/** Video file extensions (lowercase, with dot) */
export const VIDEO_EXTENSIONS = new Set([
  '.mp4',
  '.webm',
  '.mov',
  '.avi',
  '.mkv',
  '.m4v',
  '.gif', // Animated GIFs treated as video
  '.webp', // Can be animated
])

/** Image file extensions (lowercase, with dot) */
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

/** Video MIME types */
export const VIDEO_MIME_TYPES = new Set([
  'video/mp4',
  'video/webm',
  'video/quicktime',
  'video/x-msvideo',
  'video/x-matroska',
  'video/ogg',
  'video/mpeg',
  'image/gif', // GIFs can be animated
  'image/webp', // WebP can be animated
])

/** Image MIME types */
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

/** Preview playback settings */
export const PREVIEW_SETTINGS = {
  /** Duration of auto-play preview in milliseconds (0 = infinite) */
  PREVIEW_DURATION_MS: 5000,

  /** Whether to loop preview playback */
  PREVIEW_LOOP: true,

  /** Default muted state for previews */
  PREVIEW_MUTED: true,

  /** Delay before starting hover playback (ms) */
  HOVER_DELAY_MS: 150,

  /** Intersection observer threshold for lazy loading */
  LAZY_LOAD_THRESHOLD: 0.1,

  /** Intersection observer root margin (start loading before visible) */
  LAZY_LOAD_MARGIN: '200px',
} as const

/** Video player settings */
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
} as const

/** Supported video formats for HTML5 video */
export const SUPPORTED_VIDEO_FORMATS = [
  'video/mp4',
  'video/webm',
  'video/ogg',
] as const

/** LocalStorage keys */
export const STORAGE_KEYS = {
  /** Saved volume preference */
  VOLUME: 'synapse-video-volume',
  /** Saved mute preference */
  MUTED: 'synapse-video-muted',
} as const
