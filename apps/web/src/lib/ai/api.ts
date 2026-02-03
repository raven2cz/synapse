/**
 * AI Services API Client
 */

import type {
  AIDetectionResponse,
  AIExtractionResponse,
  AICacheStats,
  AIServicesSettings,
} from './types'

const API_BASE = '/api/ai'

/**
 * Detect available AI providers
 */
export async function detectProviders(): Promise<AIDetectionResponse> {
  const response = await fetch(`${API_BASE}/providers`)
  if (!response.ok) {
    throw new Error(`Failed to detect providers: ${response.statusText}`)
  }
  return response.json()
}

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

/**
 * Get current AI settings
 */
export async function getAISettings(): Promise<AIServicesSettings> {
  const response = await fetch(`${API_BASE}/settings`)
  if (!response.ok) {
    throw new Error(`Failed to get AI settings: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Update AI settings (partial update)
 */
export async function updateAISettings(
  updates: Partial<AIServicesSettings>
): Promise<AIServicesSettings> {
  const response = await fetch(`${API_BASE}/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
  if (!response.ok) {
    throw new Error(`Failed to update AI settings: ${response.statusText}`)
  }
  return response.json()
}
