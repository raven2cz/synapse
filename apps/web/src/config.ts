/**
 * Application configuration constants
 *
 * SINGLE SOURCE OF TRUTH for app-wide configuration.
 * Import this file instead of hardcoding values.
 */

// Version is imported from package.json to ensure consistency
// When you update package.json version, this updates automatically
import packageJson from '../package.json'

/**
 * Application version - SINGLE SOURCE OF TRUTH
 * Used in Header, About dialogs, API responses, etc.
 */
export const APP_VERSION = packageJson.version

/**
 * Application name
 */
export const APP_NAME = 'Synapse'

/**
 * Application tagline
 */
export const APP_TAGLINE = 'The Pack-First Model Manager'
