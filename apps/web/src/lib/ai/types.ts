/**
 * AI Services Types
 *
 * TypeScript types for AI extraction and caching.
 */

/**
 * Response for parameter extraction
 */
export interface AIExtractionResponse {
  success: boolean
  parameters?: Record<string, unknown>
  error?: string
  providerId?: string
  model?: string
  cached: boolean
  executionTimeMs: number
}

/**
 * Cache statistics (snake_case from API)
 */
export interface AICacheStats {
  cache_dir: string
  entry_count: number
  total_size_bytes: number
  total_size_mb: number
  ttl_days: number
}
