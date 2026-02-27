/**
 * AI Services API Client
 */

import type {
  AIExtractionResponse,
  AICacheStats,
} from './types'

const API_BASE = '/api/ai'

/**
 * Extract parameters from description using AI
 */
export async function extractParameters(
  description: string,
  useCache = true
): Promise<AIExtractionResponse> {
  const response = await fetch(`${API_BASE}/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description, use_cache: useCache }),
  })
  if (!response.ok) {
    throw new Error(`Failed to extract parameters: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Get cache statistics
 */
export async function getCacheStats(): Promise<AICacheStats> {
  const response = await fetch(`${API_BASE}/cache/stats`)
  if (!response.ok) {
    throw new Error(`Failed to get cache stats: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Clear all cache entries
 */
export async function clearCache(): Promise<{ cleared: number }> {
  const response = await fetch(`${API_BASE}/cache`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to clear cache: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Cleanup expired cache entries
 */
export async function cleanupCache(): Promise<{ cleaned: number }> {
  const response = await fetch(`${API_BASE}/cache/cleanup`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to cleanup cache: ${response.statusText}`)
  }
  return response.json()
}
