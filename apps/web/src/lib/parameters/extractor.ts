/**
 * Parameter Extractor
 *
 * Extracts applicable generation parameters from image metadata,
 * filtering out non-parameter data like prompts and resources.
 */

import { normalizeParamKey, normalizeParams } from './normalizer'

/**
 * Keys that are known generation parameters (case-insensitive matching).
 * These are the parameters we want to extract from image metadata.
 */
const GENERATION_PARAM_PATTERNS = [
  'seed', 'steps', 'cfg', 'cfgScale', 'cfg_scale', 'guidance',
  'sampler', 'scheduler', 'denoise', 'denoising',
  'width', 'height', 'size',
  'clipSkip', 'clip_skip', 'clip',
  'strength', 'lora_strength',
  'hires', 'highres', 'upscale',
  'vae', 'eta',
]

/**
 * Keys to explicitly exclude from extraction.
 * These are metadata fields that are NOT generation parameters.
 */
const EXCLUDE_KEYS = new Set([
  // Prompts
  'prompt', 'negativePrompt', 'negative_prompt', 'positivePrompt', 'positive_prompt',
  // Resources/Models
  'resources', 'civitaiResources', 'civitai_resources',
  'Model', 'model', 'model_name', 'modelName', 'checkpoint',
  // Hashes
  'hash', 'hashes', 'model_hash', 'modelHash',
  // Other metadata
  'comfy', 'comfyWorkflow', 'A1111', 'software',
])

/**
 * Check if a key looks like a generation parameter.
 *
 * @param key - Metadata key to check
 * @returns True if it's likely a generation parameter
 */
export function isGenerationParam(key: string): boolean {
  if (!key) return false

  // Check exclusion list first
  if (EXCLUDE_KEYS.has(key)) {
    return false
  }

  const lowerKey = key.toLowerCase()

  // Check exclusion patterns
  if (lowerKey.includes('prompt') || lowerKey.includes('resource')) {
    return false
  }

  // Check inclusion patterns
  return GENERATION_PARAM_PATTERNS.some(pattern =>
    lowerKey.includes(pattern.toLowerCase())
  )
}

/**
 * Extract applicable generation parameters from image metadata.
 *
 * Filters the metadata to only include parameters that can be
 * applied to a pack's generation settings. Excludes prompts,
 * resources, and other non-applicable data.
 *
 * @param meta - Full image metadata object
 * @returns Object with only generation parameters (normalized keys)
 *
 * @example
 * const meta = {
 *   prompt: 'beautiful landscape...',
 *   negativePrompt: 'ugly...',
 *   cfgScale: 7,
 *   steps: 25,
 *   seed: 12345,
 *   resources: [...],
 * }
 * extractApplicableParams(meta)
 * // { cfg_scale: 7, steps: 25, seed: 12345 }
 */
export function extractApplicableParams(meta: Record<string, unknown>): Record<string, unknown> {
  if (!meta || typeof meta !== 'object') {
    return {}
  }

  const applicable: Record<string, unknown> = {}

  for (const [key, value] of Object.entries(meta)) {
    // Skip null/undefined values
    if (value === null || value === undefined || value === '') {
      continue
    }

    // Skip excluded keys
    if (EXCLUDE_KEYS.has(key)) {
      continue
    }

    // Check if it's a generation parameter
    if (isGenerationParam(key)) {
      applicable[key] = value
    }
  }

  // Normalize keys and convert values
  return normalizeParams(applicable)
}

/**
 * Get list of extractable parameters from metadata.
 *
 * Returns array of { key, value, normalizedKey } for UI display.
 *
 * @param meta - Image metadata
 * @returns Array of parameter info objects
 */
export function getExtractableParams(
  meta: Record<string, unknown>
): Array<{ key: string; value: unknown; normalizedKey: string }> {
  if (!meta || typeof meta !== 'object') {
    return []
  }

  const result: Array<{ key: string; value: unknown; normalizedKey: string }> = []

  for (const [key, value] of Object.entries(meta)) {
    if (value === null || value === undefined || value === '') {
      continue
    }

    if (EXCLUDE_KEYS.has(key)) {
      continue
    }

    if (isGenerationParam(key)) {
      result.push({
        key,
        value,
        normalizedKey: normalizeParamKey(key),
      })
    }
  }

  return result
}

/**
 * Check if metadata has any extractable generation parameters.
 *
 * @param meta - Image metadata
 * @returns True if there are parameters to extract
 */
export function hasExtractableParams(meta: Record<string, unknown>): boolean {
  if (!meta || typeof meta !== 'object') {
    return false
  }

  for (const [key, value] of Object.entries(meta)) {
    if (value === null || value === undefined || value === '') {
      continue
    }

    if (EXCLUDE_KEYS.has(key)) {
      continue
    }

    if (isGenerationParam(key)) {
      return true
    }
  }

  return false
}
