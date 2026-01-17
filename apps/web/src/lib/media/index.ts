/**
 * Media Library
 *
 * Utilities for media type detection and video playback.
 */

// Detection utilities
export {
  detectMediaType,
  detectByExtension,
  detectByUrlPattern,
  detectFromApiResponse,
  isVideoUrl,
  isLikelyAnimated,
  getVideoThumbnailUrl,
  getUrlExtension,
  canPlayVideoType,
  getBestVideoUrl,
  probeMediaType,
} from './detection'

export type { MediaType, MediaInfo } from './detection'

// Constants
export {
  VIDEO_EXTENSIONS,
  IMAGE_EXTENSIONS,
  VIDEO_MIME_TYPES,
  IMAGE_MIME_TYPES,
  PREVIEW_SETTINGS,
  PLAYER_SETTINGS,
  SUPPORTED_VIDEO_FORMATS,
  STORAGE_KEYS,
} from './constants'

// Video Playback Manager (for optimized concurrent video playback)
export { VideoPlaybackManager, useManagedVideo } from './VideoPlaybackManager'
