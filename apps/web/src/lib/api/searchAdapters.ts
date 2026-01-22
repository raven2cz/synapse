/**
 * Search Adapters Registry
 *
 * Central registry for all search adapters.
 * Provides helper functions for adapter selection and availability checking.
 */

import type { SearchAdapter, SearchProvider } from './searchTypes'
import { RestSearchAdapter } from './adapters/restAdapter'
import { ArchiveSearchAdapter } from './adapters/archiveAdapter'
import { TrpcBridgeAdapter } from './adapters/trpcBridgeAdapter'

// =============================================================================
// Singleton Adapter Instances
// =============================================================================

const adapters: Record<SearchProvider, SearchAdapter> = {
  rest: new RestSearchAdapter(),
  archive: new ArchiveSearchAdapter(),
  trpc: new TrpcBridgeAdapter(),
}

// =============================================================================
// Public API
// =============================================================================

/**
 * Get adapter by provider name.
 */
export function getAdapter(provider: SearchProvider): SearchAdapter {
  return adapters[provider]
}

/**
 * Get all adapters (for testing/debugging).
 */
export function getAllAdapters(): SearchAdapter[] {
  return Object.values(adapters)
}

/**
 * Get all available adapters (for UI dropdown).
 * Only returns adapters that are currently available.
 */
export function getAvailableAdapters(): SearchAdapter[] {
  return Object.values(adapters).filter((a) => a.isAvailable())
}

/**
 * Check if a specific provider is available.
 */
export function isProviderAvailable(provider: SearchProvider): boolean {
  return adapters[provider]?.isAvailable() ?? false
}

/**
 * Get default provider.
 * Prefers tRPC if available (fastest), otherwise REST.
 */
export function getDefaultProvider(): SearchProvider {
  if (adapters.trpc.isAvailable()) return 'trpc'
  return 'rest'
}

/**
 * Get provider with fallback.
 * If requested provider is unavailable, returns a fallback.
 */
export function getProviderWithFallback(
  preferred: SearchProvider
): SearchProvider {
  if (adapters[preferred]?.isAvailable()) {
    return preferred
  }

  // Fallback chain: trpc → rest
  if (preferred === 'trpc' && adapters.rest.isAvailable()) {
    console.warn('[SearchAdapters] tRPC unavailable, falling back to REST')
    return 'rest'
  }

  // Archive only for search, not general fallback
  return 'rest'
}

// =============================================================================
// Re-exports for convenience
// =============================================================================

export { RestSearchAdapter } from './adapters/restAdapter'
export { ArchiveSearchAdapter } from './adapters/archiveAdapter'
export { TrpcBridgeAdapter } from './adapters/trpcBridgeAdapter'
