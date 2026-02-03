/**
 * Parameter Aggregator
 *
 * Aggregates generation parameters from multiple image previews
 * to find typical/common values used with a model.
 */

import { extractApplicableParams } from './extractor'
import { NUMERIC_PARAMS, INTEGER_PARAMS } from './normalizer'

/**
 * Aggregation result with parameters and confidence scores.
 */
export interface AggregationResult {
  /**
   * Aggregated parameter values
   */
  parameters: Record<string, unknown>

  /**
   * Confidence score for each parameter (0-1)
   * Higher = more consistent values across previews
   */
  confidence: Record<string, number>

  /**
   * Overall confidence (average of individual)
   */
  overallConfidence: number

  /**
   * Number of previews that contributed to aggregation
   */
  previewCount: number
}

/**
 * Preview object with optional metadata.
 */
interface PreviewWithMeta {
  meta?: Record<string, unknown>
  [key: string]: unknown
}

/**
 * Aggregate parameters from multiple preview images.
 *
 * Uses mode (most common value) for all parameters to find
 * typical settings. Calculates confidence based on how
 * consistent values are across previews.
 *
 * @param previews - Array of preview objects with meta field
 * @param strategy - Aggregation strategy ('mode' or 'average')
 * @returns Aggregation result with parameters and confidence
 *
 * @example
 * const previews = [
 *   { meta: { steps: 25, cfgScale: 7 } },
 *   { meta: { steps: 30, cfgScale: 7 } },
 *   { meta: { steps: 25, cfgScale: 7 } },
 * ]
 * aggregateFromPreviews(previews)
 * // { parameters: { steps: 25, cfg_scale: 7 }, confidence: { steps: 0.67, cfg_scale: 1 } }
 */
export function aggregateFromPreviews(
  previews: PreviewWithMeta[],
  strategy: 'mode' | 'average' = 'mode'
): AggregationResult {
  const emptyResult: AggregationResult = {
    parameters: {},
    confidence: {},
    overallConfidence: 0,
    previewCount: 0,
  }

  if (!previews || previews.length === 0) {
    return emptyResult
  }

  // Collect all values for each parameter
  const paramValues: Record<string, unknown[]> = {}
  let validPreviewCount = 0

  for (const preview of previews) {
    const meta = preview.meta
    if (!meta || typeof meta !== 'object') {
      continue
    }

    const extracted = extractApplicableParams(meta)
    if (Object.keys(extracted).length === 0) {
      continue
    }

    validPreviewCount++

    for (const [key, value] of Object.entries(extracted)) {
      if (!paramValues[key]) {
        paramValues[key] = []
      }
      paramValues[key].push(value)
    }
  }

  if (validPreviewCount === 0) {
    return emptyResult
  }

  // Aggregate values
  const parameters: Record<string, unknown> = {}
  const confidence: Record<string, number> = {}

  for (const [key, values] of Object.entries(paramValues)) {
    if (values.length === 0) {
      continue
    }

    if (strategy === 'average' && NUMERIC_PARAMS.has(key)) {
      // Calculate average for numeric params
      const numValues = values.filter(v => typeof v === 'number') as number[]
      if (numValues.length === 0) {
        continue
      }

      const avg = numValues.reduce((a, b) => a + b, 0) / numValues.length

      if (INTEGER_PARAMS.has(key)) {
        parameters[key] = Math.round(avg)
      } else {
        parameters[key] = Math.round(avg * 100) / 100 // 2 decimal places
      }

      // Confidence based on variance (lower variance = higher confidence)
      const variance = numValues.reduce((acc, v) => acc + (v - avg) ** 2, 0) / numValues.length
      const normalizedVariance = variance / (avg + 1) // Normalize by mean to handle scale
      confidence[key] = Math.max(0, Math.min(1, 1 - normalizedVariance))
    } else {
      // Use mode (most common value) for strings and default
      const counts = new Map<string, number>()

      for (const value of values) {
        const strValue = String(value)
        counts.set(strValue, (counts.get(strValue) || 0) + 1)
      }

      let maxCount = 0
      let modeValue: unknown = values[0]

      for (const [strValue, count] of counts.entries()) {
        if (count > maxCount) {
          maxCount = count
          // Find original value with this string representation
          modeValue = values.find(v => String(v) === strValue)
        }
      }

      parameters[key] = modeValue

      // Confidence = ratio of most common to total
      confidence[key] = maxCount / values.length
    }
  }

  // Calculate overall confidence
  const confidenceValues = Object.values(confidence)
  const overallConfidence = confidenceValues.length > 0
    ? confidenceValues.reduce((a, b) => a + b, 0) / confidenceValues.length
    : 0

  return {
    parameters,
    confidence,
    overallConfidence,
    previewCount: validPreviewCount,
  }
}

/**
 * Calculate how consistent parameter values are across previews.
 *
 * Returns a score from 0 (completely different) to 1 (all same).
 *
 * @param previews - Array of preview objects with meta
 * @param paramKey - Parameter key to check
 * @returns Consistency score (0-1)
 */
export function calculateParamConsistency(
  previews: PreviewWithMeta[],
  paramKey: string
): number {
  if (!previews || previews.length === 0) {
    return 0
  }

  const values: unknown[] = []

  for (const preview of previews) {
    const meta = preview.meta
    if (!meta || typeof meta !== 'object') {
      continue
    }

    const extracted = extractApplicableParams(meta)
    if (extracted[paramKey] !== undefined) {
      values.push(extracted[paramKey])
    }
  }

  if (values.length === 0) {
    return 0
  }

  // Count occurrences of most common value
  const counts = new Map<string, number>()
  for (const value of values) {
    const strValue = String(value)
    counts.set(strValue, (counts.get(strValue) || 0) + 1)
  }

  const maxCount = Math.max(...counts.values())
  return maxCount / values.length
}

/**
 * Get all unique parameter keys found across previews.
 *
 * @param previews - Array of preview objects with meta
 * @returns Set of parameter keys
 */
export function getAvailableParamKeys(previews: PreviewWithMeta[]): Set<string> {
  const keys = new Set<string>()

  for (const preview of previews) {
    const meta = preview.meta
    if (!meta || typeof meta !== 'object') {
      continue
    }

    const extracted = extractApplicableParams(meta)
    for (const key of Object.keys(extracted)) {
      keys.add(key)
    }
  }

  return keys
}
