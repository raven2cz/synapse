/**
 * Parameters Module
 *
 * Utilities for extracting, normalizing, and aggregating
 * generation parameters from various sources.
 */

// Normalizer
export {
  normalizeParamKey,
  convertParamValue,
  normalizeParams,
  PARAM_KEY_ALIASES,
  NUMERIC_PARAMS,
  INTEGER_PARAMS,
  BOOLEAN_PARAMS,
} from './normalizer'

// Extractor
export {
  isGenerationParam,
  extractApplicableParams,
  getExtractableParams,
  hasExtractableParams,
} from './extractor'

// Aggregator
export {
  aggregateFromPreviews,
  calculateParamConsistency,
  getAvailableParamKeys,
  type AggregationResult,
} from './aggregator'
