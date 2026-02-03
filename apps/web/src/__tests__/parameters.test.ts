/**
 * Tests for Parameters Module (Phase 7)
 *
 * Tests for parameter extraction, normalization, and aggregation utilities.
 * These functions convert Civitai image metadata into normalized pack parameters.
 */

import { describe, it, expect } from 'vitest'
import {
  normalizeParamKey,
  convertParamValue,
  normalizeParams,
  extractApplicableParams,
  hasExtractableParams,
  isGenerationParam,
  getExtractableParams,
  aggregateFromPreviews,
} from '@/lib/parameters'

// =============================================================================
// normalizeParamKey Tests
// =============================================================================

describe('normalizeParamKey', () => {
  describe('camelCase to snake_case', () => {
    it('should convert cfgScale to cfg_scale', () => {
      expect(normalizeParamKey('cfgScale')).toBe('cfg_scale')
    })

    it('should convert clipSkip to clip_skip', () => {
      expect(normalizeParamKey('clipSkip')).toBe('clip_skip')
    })

    it('should convert hiresUpscaler to hires_upscaler', () => {
      expect(normalizeParamKey('hiresUpscaler')).toBe('hires_upscaler')
    })
  })

  describe('alias mapping', () => {
    it('should map cfg to cfg_scale', () => {
      expect(normalizeParamKey('cfg')).toBe('cfg_scale')
    })

    it('should map guidance to cfg_scale', () => {
      expect(normalizeParamKey('guidance')).toBe('cfg_scale')
    })

    it('should map clip to clip_skip', () => {
      expect(normalizeParamKey('clip')).toBe('clip_skip')
    })

    it('should map lora_strength to strength', () => {
      expect(normalizeParamKey('lora_strength')).toBe('strength')
    })
  })

  describe('already normalized', () => {
    it('should preserve cfg_scale', () => {
      expect(normalizeParamKey('cfg_scale')).toBe('cfg_scale')
    })

    it('should preserve steps', () => {
      expect(normalizeParamKey('steps')).toBe('steps')
    })
  })

  describe('edge cases', () => {
    it('should handle empty string', () => {
      expect(normalizeParamKey('')).toBe('')
    })

    it('should handle kebab-case', () => {
      expect(normalizeParamKey('clip-skip')).toBe('clip_skip')
    })
  })
})

// =============================================================================
// convertParamValue Tests
// =============================================================================

describe('convertParamValue', () => {
  describe('integer conversion', () => {
    it('should convert string "25" to number 25 for steps', () => {
      expect(convertParamValue('steps', '25')).toBe(25)
    })

    it('should convert string "2" to number 2 for clip_skip', () => {
      expect(convertParamValue('clip_skip', '2')).toBe(2)
    })

    it('should pass through existing integers', () => {
      expect(convertParamValue('steps', 25)).toBe(25)
    })
  })

  describe('float conversion', () => {
    it('should convert string "7.5" to number 7.5 for cfg_scale', () => {
      expect(convertParamValue('cfg_scale', '7.5')).toBe(7.5)
    })

    it('should convert string "0.8" to number 0.8 for denoise', () => {
      expect(convertParamValue('denoise', '0.8')).toBe(0.8)
    })
  })

  describe('boolean conversion', () => {
    it('should convert "true" to true for hires_fix', () => {
      expect(convertParamValue('hires_fix', 'true')).toBe(true)
    })

    it('should convert "false" to false for hires_fix', () => {
      expect(convertParamValue('hires_fix', 'false')).toBe(false)
    })

    it('should convert "yes" to true for hires_fix', () => {
      expect(convertParamValue('hires_fix', 'yes')).toBe(true)
    })
  })

  describe('string preservation', () => {
    it('should preserve sampler strings', () => {
      expect(convertParamValue('sampler', 'euler')).toBe('euler')
    })

    it('should trim whitespace', () => {
      expect(convertParamValue('sampler', '  euler  ')).toBe('euler')
    })
  })

  describe('null handling', () => {
    it('should return null for null input', () => {
      expect(convertParamValue('steps', null)).toBeNull()
    })

    it('should return null for undefined input', () => {
      expect(convertParamValue('steps', undefined)).toBeNull()
    })
  })
})

// =============================================================================
// normalizeParams Tests
// =============================================================================

describe('normalizeParams', () => {
  it('should normalize keys and convert values', () => {
    const input = {
      cfgScale: '7',
      clipSkip: '2',
      steps: '25',
      sampler: 'euler',
    }

    const result = normalizeParams(input)

    expect(result.cfg_scale).toBe(7)
    expect(result.clip_skip).toBe(2)
    expect(result.steps).toBe(25)
    expect(result.sampler).toBe('euler')
  })

  it('should filter out null values', () => {
    const input = {
      steps: '25',
      cfg_scale: '',
      sampler: null,
    }

    const result = normalizeParams(input)

    expect(result.steps).toBe(25)
    expect(result.cfg_scale).toBeUndefined()
    expect(result.sampler).toBeUndefined()
  })

  it('should not have camelCase keys in result', () => {
    const input = { cfgScale: 7, clipSkip: 2 }
    const result = normalizeParams(input)

    expect(result.cfgScale).toBeUndefined()
    expect(result.clipSkip).toBeUndefined()
    expect(result.cfg_scale).toBe(7)
    expect(result.clip_skip).toBe(2)
  })
})

// =============================================================================
// extractApplicableParams Tests
// =============================================================================

describe('extractApplicableParams', () => {
  it('should extract generation parameters from Civitai meta', () => {
    const meta = {
      prompt: 'beautiful landscape',
      negativePrompt: 'ugly, blurry',
      cfgScale: 7,
      steps: 25,
      seed: 12345,
      sampler: 'euler',
      clipSkip: 2,
    }

    const result = extractApplicableParams(meta)

    expect(result.cfg_scale).toBe(7)
    expect(result.steps).toBe(25)
    expect(result.seed).toBe(12345)
    expect(result.sampler).toBe('euler')
    expect(result.clip_skip).toBe(2)
  })

  it('should exclude prompts', () => {
    const meta = {
      prompt: 'test prompt',
      negativePrompt: 'bad quality',
      steps: 20,
    }

    const result = extractApplicableParams(meta)

    expect(result.prompt).toBeUndefined()
    expect(result.negativePrompt).toBeUndefined()
    expect(result.steps).toBe(20)
  })

  it('should exclude resources', () => {
    const meta = {
      resources: [{ name: 'lora', type: 'lora' }],
      civitaiResources: [{ id: 123 }],
      steps: 20,
    }

    const result = extractApplicableParams(meta)

    expect(result.resources).toBeUndefined()
    expect(result.civitaiResources).toBeUndefined()
    expect(result.steps).toBe(20)
  })

  it('should handle empty meta', () => {
    expect(extractApplicableParams({})).toEqual({})
  })

  it('should handle null/undefined meta', () => {
    expect(extractApplicableParams(null as any)).toEqual({})
    expect(extractApplicableParams(undefined as any)).toEqual({})
  })
})

// =============================================================================
// hasExtractableParams Tests
// =============================================================================

describe('hasExtractableParams', () => {
  it('should return true when meta has generation params', () => {
    const meta = { cfgScale: 7, steps: 25 }
    expect(hasExtractableParams(meta)).toBe(true)
  })

  it('should return false when meta only has prompts', () => {
    const meta = { prompt: 'test', negativePrompt: 'bad' }
    expect(hasExtractableParams(meta)).toBe(false)
  })

  it('should return false for empty meta', () => {
    expect(hasExtractableParams({})).toBe(false)
  })

  it('should return false for null/undefined', () => {
    expect(hasExtractableParams(null as any)).toBe(false)
    expect(hasExtractableParams(undefined as any)).toBe(false)
  })
})

// =============================================================================
// isGenerationParam Tests
// =============================================================================

describe('isGenerationParam', () => {
  it('should return true for known generation params', () => {
    expect(isGenerationParam('steps')).toBe(true)
    expect(isGenerationParam('cfgScale')).toBe(true)
    expect(isGenerationParam('sampler')).toBe(true)
    expect(isGenerationParam('seed')).toBe(true)
    expect(isGenerationParam('clipSkip')).toBe(true)
  })

  it('should return false for prompts', () => {
    expect(isGenerationParam('prompt')).toBe(false)
    expect(isGenerationParam('negativePrompt')).toBe(false)
  })

  it('should return false for resources', () => {
    expect(isGenerationParam('resources')).toBe(false)
    expect(isGenerationParam('civitaiResources')).toBe(false)
  })
})

// =============================================================================
// getExtractableParams Tests
// =============================================================================

describe('getExtractableParams', () => {
  it('should return array of extractable params with normalized keys', () => {
    const meta = {
      cfgScale: 7,
      steps: 25,
      prompt: 'test', // should be excluded
    }

    const result = getExtractableParams(meta)

    expect(result.length).toBe(2)
    expect(result.find(p => p.normalizedKey === 'cfg_scale')).toBeTruthy()
    expect(result.find(p => p.normalizedKey === 'steps')).toBeTruthy()
    expect(result.find(p => p.normalizedKey === 'prompt')).toBeFalsy()
  })
})

// =============================================================================
// aggregateFromPreviews Tests
// =============================================================================

describe('aggregateFromPreviews', () => {
  it('should aggregate parameters using mode strategy', () => {
    const previews = [
      { meta: { steps: 25, cfgScale: 7 } },
      { meta: { steps: 30, cfgScale: 7 } },
      { meta: { steps: 25, cfgScale: 7 } },
    ]

    const result = aggregateFromPreviews(previews)

    // Mode of steps is 25 (appears twice)
    expect(result.parameters.steps).toBe(25)
    // CFG is same in all, so 7
    expect(result.parameters.cfg_scale).toBe(7)
  })

  it('should calculate confidence for consistent values', () => {
    const previews = [
      { meta: { cfgScale: 7 } },
      { meta: { cfgScale: 7 } },
      { meta: { cfgScale: 7 } },
    ]

    const result = aggregateFromPreviews(previews)

    // All same value = 100% confidence for that param
    expect(result.confidence.cfg_scale).toBe(1)
    expect(result.overallConfidence).toBe(1)
  })

  it('should skip previews without meta', () => {
    const previews = [
      { url: 'test1.jpg' }, // no meta
      { meta: { steps: 25 } },
      { meta: undefined }, // undefined meta
    ]

    const result = aggregateFromPreviews(previews)

    expect(result.parameters.steps).toBe(25)
    expect(result.previewCount).toBe(1)
  })

  it('should handle empty previews array', () => {
    const result = aggregateFromPreviews([])

    expect(result.parameters).toEqual({})
    expect(result.previewCount).toBe(0)
    expect(result.overallConfidence).toBe(0)
  })

  it('should calculate average for numeric params when strategy is average', () => {
    const previews = [
      { meta: { steps: 20, cfgScale: 6 } },
      { meta: { steps: 30, cfgScale: 8 } },
    ]

    const result = aggregateFromPreviews(previews, 'average')

    // Average of 20 and 30 = 25
    expect(result.parameters.steps).toBe(25)
    // Average of 6 and 8 = 7
    expect(result.parameters.cfg_scale).toBe(7)
  })
})

// =============================================================================
// Integration Tests
// =============================================================================

describe('Parameter Extraction Integration', () => {
  it('should handle real Civitai-style metadata', () => {
    const civitaiMeta = {
      prompt: 'masterpiece, best quality, 1girl, solo',
      negativePrompt: 'worst quality, low quality, bad anatomy',
      cfgScale: 7,
      steps: 30,
      sampler: 'DPM++ 2M Karras',
      seed: 1234567890,
      clipSkip: 2,
      Size: '512x768',
      Model: 'dreamshaper_8',
      'Model hash': 'abc123',
      resources: [
        { name: 'dreamshaper_8', type: 'model' },
        { name: 'detail_tweaker', type: 'lora', weight: 0.8 },
      ],
    }

    const result = extractApplicableParams(civitaiMeta)

    // Generation params should be extracted
    expect(result.cfg_scale).toBe(7)
    expect(result.steps).toBe(30)
    expect(result.sampler).toBe('DPM++ 2M Karras')
    expect(result.seed).toBe(1234567890)
    expect(result.clip_skip).toBe(2)

    // Non-generation data should be excluded
    expect(result.prompt).toBeUndefined()
    expect(result.negativePrompt).toBeUndefined()
    expect(result.Model).toBeUndefined()
    expect(result.resources).toBeUndefined()
  })

  it('should normalize and extract in single flow', () => {
    const rawMeta = {
      cfgScale: '7.5',
      steps: '25',
      clipSkip: '2',
      hiresSteps: '10',
      sampler: 'euler',
    }

    const result = extractApplicableParams(rawMeta)

    // All keys should be snake_case
    expect(Object.keys(result).every(k => !k.includes('Scale'))).toBe(true)
    expect(Object.keys(result).every(k => !k.includes('Skip'))).toBe(true)

    // Values should be properly typed
    expect(typeof result.cfg_scale).toBe('number')
    expect(typeof result.steps).toBe('number')
    expect(typeof result.clip_skip).toBe('number')
    expect(typeof result.sampler).toBe('string')
  })
})
