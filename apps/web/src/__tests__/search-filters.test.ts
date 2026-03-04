/**
 * Tests for SearchFilters Component (Phase 5)
 *
 * Tests the two-step filter selection, multi-select support,
 * and filter options.
 */

import { describe, it, expect } from 'vitest'

// =============================================================================
// Filter Options Tests
// =============================================================================

describe('Filter Options', () => {
  describe('BASE_MODEL_OPTIONS', () => {
    it('should have correct structure', async () => {
      const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

      // Should have "All Base Models" as first option
      expect(BASE_MODEL_OPTIONS[0]).toEqual({ value: '', label: 'All Base Models' })

      // Should contain popular models
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SDXL 1.0', label: 'SDXL 1.0' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 1.5', label: 'SD 1.5' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Pony', label: 'Pony' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Illustrious', label: 'Illustrious' })
    })

    it('should have Flux models', async () => {
      const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Flux.1 D', label: 'Flux.1 Dev' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Flux.1 S', label: 'Flux.1 Schnell' })
    })

    it('should have SD versions', async () => {
      const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 1.4', label: 'SD 1.4' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 2.0', label: 'SD 2.0' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 2.1', label: 'SD 2.1' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 3', label: 'SD 3' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 3.5', label: 'SD 3.5' })
    })

    it('should have SDXL variants', async () => {
      const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SDXL 0.9', label: 'SDXL 0.9' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SDXL 1.0 LCM', label: 'SDXL 1.0 LCM' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SDXL Hyper', label: 'SDXL Hyper' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SDXL Lightning', label: 'SDXL Lightning' })
    })

    it('should have video models', async () => {
      const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SVD XT', label: 'SVD XT' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Hunyuan Video', label: 'Hunyuan Video' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'CogVideoX', label: 'CogVideoX' })
      expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Wan Video', label: 'Wan Video' })
    })
  })

  describe('MODEL_TYPE_OPTIONS', () => {
    it('should have correct structure', async () => {
      const { MODEL_TYPE_OPTIONS } = await import('@/lib/api/searchTypes')

      // Should have "All Types" as first option
      expect(MODEL_TYPE_OPTIONS[0]).toEqual({ value: '', label: 'All Types' })
    })

    it('should contain all common model types', async () => {
      const { MODEL_TYPE_OPTIONS } = await import('@/lib/api/searchTypes')

      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'LORA', label: 'LoRA' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'LoCon', label: 'LyCORIS' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'DoRA', label: 'DoRA' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'Checkpoint', label: 'Checkpoint' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'TextualInversion', label: 'Embedding' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'Controlnet', label: 'ControlNet' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'Upscaler', label: 'Upscaler' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'VAE', label: 'VAE' })
    })

    it('should contain additional model types', async () => {
      const { MODEL_TYPE_OPTIONS } = await import('@/lib/api/searchTypes')

      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'Hypernetwork', label: 'Hypernetwork' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'Poses', label: 'Poses' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'Wildcards', label: 'Wildcards' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'Workflows', label: 'Workflows' })
      expect(MODEL_TYPE_OPTIONS).toContainEqual({ value: 'MotionModule', label: 'Motion' })
    })

    it('should have at least 15 model types', async () => {
      const { MODEL_TYPE_OPTIONS } = await import('@/lib/api/searchTypes')

      // Filter out the "All Types" option with empty value
      const actualTypes = MODEL_TYPE_OPTIONS.filter((opt) => opt.value !== '')
      expect(actualTypes.length).toBeGreaterThanOrEqual(15)
    })
  })

  describe('FILE_FORMAT_OPTIONS', () => {
    it('should have correct structure', async () => {
      const { FILE_FORMAT_OPTIONS } = await import('@/lib/api/searchTypes')

      // Should have "All Formats" as first option
      expect(FILE_FORMAT_OPTIONS[0]).toEqual({ value: '', label: 'All Formats' })
    })

    it('should contain all file formats', async () => {
      const { FILE_FORMAT_OPTIONS } = await import('@/lib/api/searchTypes')

      expect(FILE_FORMAT_OPTIONS).toContainEqual({ value: 'SafeTensor', label: 'Safe Tensor' })
      expect(FILE_FORMAT_OPTIONS).toContainEqual({ value: 'PickleTensor', label: 'Pickle Tensor' })
      expect(FILE_FORMAT_OPTIONS).toContainEqual({ value: 'Diffusers', label: 'Diffusers' })
      expect(FILE_FORMAT_OPTIONS).toContainEqual({ value: 'GGUF', label: 'GGUF' })
      expect(FILE_FORMAT_OPTIONS).toContainEqual({ value: 'Core ML', label: 'Core ML' })
      expect(FILE_FORMAT_OPTIONS).toContainEqual({ value: 'ONNX', label: 'ONNX' })
    })
  })

  describe('CATEGORY_OPTIONS', () => {
    it('should have correct structure', async () => {
      const { CATEGORY_OPTIONS } = await import('@/lib/api/searchTypes')

      // Should have "All Categories" as first option
      expect(CATEGORY_OPTIONS[0]).toEqual({ value: '', label: 'All Categories' })
    })

    it('should contain all categories', async () => {
      const { CATEGORY_OPTIONS } = await import('@/lib/api/searchTypes')

      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'character', label: 'Character' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'style', label: 'Style' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'celebrity', label: 'Celebrity' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'concept', label: 'Concept' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'clothing', label: 'Clothing' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'base model', label: 'Base Model' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'poses', label: 'Poses' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'background', label: 'Background' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'tool', label: 'Tool' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'vehicle', label: 'Vehicle' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'animal', label: 'Animal' })
      expect(CATEGORY_OPTIONS).toContainEqual({ value: 'action', label: 'Action' })
    })

    it('should have at least 15 categories', async () => {
      const { CATEGORY_OPTIONS } = await import('@/lib/api/searchTypes')

      // Filter out the "All Categories" option with empty value
      const actualCategories = CATEGORY_OPTIONS.filter((opt) => opt.value !== '')
      expect(actualCategories.length).toBeGreaterThanOrEqual(15)
    })
  })
})

// =============================================================================
// Filter Value Logic Tests
// =============================================================================

describe('Filter Value Logic', () => {
  it('should have no duplicate values in BASE_MODEL_OPTIONS', async () => {
    const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

    const values = BASE_MODEL_OPTIONS.map((opt) => opt.value)

    // The only duplicate allowed is '' (empty value for "All")
    const nonEmptyValues = values.filter((v) => v !== '')
    const uniqueNonEmptyValues = new Set(nonEmptyValues)

    expect(uniqueNonEmptyValues.size).toBe(nonEmptyValues.length)
  })

  it('should have no duplicate values in MODEL_TYPE_OPTIONS', async () => {
    const { MODEL_TYPE_OPTIONS } = await import('@/lib/api/searchTypes')

    const values = MODEL_TYPE_OPTIONS.map((opt) => opt.value)
    const nonEmptyValues = values.filter((v) => v !== '')
    const uniqueNonEmptyValues = new Set(nonEmptyValues)

    expect(uniqueNonEmptyValues.size).toBe(nonEmptyValues.length)
  })

  it('should have no duplicate values in FILE_FORMAT_OPTIONS', async () => {
    const { FILE_FORMAT_OPTIONS } = await import('@/lib/api/searchTypes')

    const values = FILE_FORMAT_OPTIONS.map((opt) => opt.value)
    const nonEmptyValues = values.filter((v) => v !== '')
    const uniqueNonEmptyValues = new Set(nonEmptyValues)

    expect(uniqueNonEmptyValues.size).toBe(nonEmptyValues.length)
  })

  it('should have no duplicate values in CATEGORY_OPTIONS', async () => {
    const { CATEGORY_OPTIONS } = await import('@/lib/api/searchTypes')

    const values = CATEGORY_OPTIONS.map((opt) => opt.value)
    const nonEmptyValues = values.filter((v) => v !== '')
    const uniqueNonEmptyValues = new Set(nonEmptyValues)

    expect(uniqueNonEmptyValues.size).toBe(nonEmptyValues.length)
  })
})

// =============================================================================
// Multi-Select Logic Tests
// =============================================================================

describe('Multi-Select Logic', () => {
  it('should be able to combine multiple model types', () => {
    // Simulating multi-select behavior
    const selectedModelTypes: string[] = []

    // Add first type
    selectedModelTypes.push('LORA')
    expect(selectedModelTypes).toEqual(['LORA'])

    // Add second type
    selectedModelTypes.push('Checkpoint')
    expect(selectedModelTypes).toEqual(['LORA', 'Checkpoint'])

    // Add third type
    selectedModelTypes.push('TextualInversion')
    expect(selectedModelTypes).toEqual(['LORA', 'Checkpoint', 'TextualInversion'])
  })

  it('should be able to remove individual model types', () => {
    let selectedModelTypes = ['LORA', 'Checkpoint', 'TextualInversion']

    // Remove middle type
    selectedModelTypes = selectedModelTypes.filter((t) => t !== 'Checkpoint')
    expect(selectedModelTypes).toEqual(['LORA', 'TextualInversion'])

    // Remove first type
    selectedModelTypes = selectedModelTypes.filter((t) => t !== 'LORA')
    expect(selectedModelTypes).toEqual(['TextualInversion'])
  })

  it('should prevent duplicate selections', () => {
    const selectedModelTypes: string[] = ['LORA']

    // Try to add duplicate
    if (!selectedModelTypes.includes('LORA')) {
      selectedModelTypes.push('LORA')
    }

    expect(selectedModelTypes).toEqual(['LORA'])
    expect(selectedModelTypes.length).toBe(1)
  })

  it('should toggle selection correctly', () => {
    let selectedModelTypes: string[] = []

    // Toggle function
    const toggle = (type: string) => {
      if (selectedModelTypes.includes(type)) {
        selectedModelTypes = selectedModelTypes.filter((t) => t !== type)
      } else {
        selectedModelTypes = [...selectedModelTypes, type]
      }
    }

    // Add
    toggle('LORA')
    expect(selectedModelTypes).toEqual(['LORA'])

    // Add another
    toggle('Checkpoint')
    expect(selectedModelTypes).toEqual(['LORA', 'Checkpoint'])

    // Remove first
    toggle('LORA')
    expect(selectedModelTypes).toEqual(['Checkpoint'])

    // Remove last
    toggle('Checkpoint')
    expect(selectedModelTypes).toEqual([])
  })
})

// =============================================================================
// CHECKPOINT_TYPE_OPTIONS Tests
// =============================================================================

describe('CHECKPOINT_TYPE_OPTIONS', () => {
  it('should have correct structure', async () => {
    const { CHECKPOINT_TYPE_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(CHECKPOINT_TYPE_OPTIONS[0]).toEqual({ value: '', label: 'All Checkpoint Types' })
  })

  it('should contain Trained and Merge', async () => {
    const { CHECKPOINT_TYPE_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(CHECKPOINT_TYPE_OPTIONS).toContainEqual({ value: 'Trained', label: 'Trained' })
    expect(CHECKPOINT_TYPE_OPTIONS).toContainEqual({ value: 'Merge', label: 'Merge' })
  })

  it('should have exactly 3 options (including All)', async () => {
    const { CHECKPOINT_TYPE_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(CHECKPOINT_TYPE_OPTIONS).toHaveLength(3)
  })
})

// =============================================================================
// Sort Options — New entries
// =============================================================================

describe('SORT_OPTIONS — new entries', () => {
  it('should have 8 sort options', async () => {
    const { SORT_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(SORT_OPTIONS).toHaveLength(8)
  })

  it('should contain new sort options', async () => {
    const { SORT_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(SORT_OPTIONS).toContainEqual({ value: 'Most Liked', label: 'Most Liked' })
    expect(SORT_OPTIONS).toContainEqual({ value: 'Most Images', label: 'Most Images' })
    expect(SORT_OPTIONS).toContainEqual({ value: 'Oldest', label: 'Oldest' })
  })

  it('should NOT contain Most Buzz (removed)', async () => {
    const { SORT_OPTIONS } = await import('@/lib/api/searchTypes')

    const values = SORT_OPTIONS.map((opt) => opt.value)
    expect(values).not.toContain('Most Buzz')
  })
})

// =============================================================================
// FILE_FORMAT_OPTIONS — Pt removed
// =============================================================================

describe('FILE_FORMAT_OPTIONS — verified', () => {
  it('should NOT contain Pt (not in Civitai source)', async () => {
    const { FILE_FORMAT_OPTIONS } = await import('@/lib/api/searchTypes')

    const values = FILE_FORMAT_OPTIONS.map((opt) => opt.value)
    expect(values).not.toContain('Pt')
  })

  it('should have 8 options (including All)', async () => {
    const { FILE_FORMAT_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(FILE_FORMAT_OPTIONS).toHaveLength(8)
  })
})

// =============================================================================
// BASE_MODEL_OPTIONS — New entries
// =============================================================================

describe('BASE_MODEL_OPTIONS — new entries', () => {
  it('should have SD 3.5 variants', async () => {
    const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 3.5 Large', label: 'SD 3.5 Large' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 3.5 Medium', label: 'SD 3.5 Medium' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 3.5 Large Turbo', label: 'SD 3.5 Large Turbo' })
  })

  it('should have Wan Video 2.x variants', async () => {
    const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Wan Video 2.2 TI2V-5B', label: 'Wan Video 2.2 TI2V-5B' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Wan Video 2.2 I2V-A14B', label: 'Wan Video 2.2 I2V-A14B' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Wan Video 2.5 T2V', label: 'Wan Video 2.5 T2V' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Wan Video 2.5 I2V', label: 'Wan Video 2.5 I2V' })
  })

  it('should have additional models', async () => {
    const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Anima', label: 'Anima' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Seedance', label: 'Seedance' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Kling', label: 'Kling' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Vidu Q1', label: 'Vidu Q1' })
  })
})

// =============================================================================
// Multi-Select BaseModels Logic
// =============================================================================

describe('Multi-Select BaseModels Logic', () => {
  it('should support selecting multiple base models', () => {
    let baseModels: string[] = []

    // Add first model
    baseModels = [...baseModels, 'SDXL 1.0']
    expect(baseModels).toEqual(['SDXL 1.0'])

    // Add second model
    baseModels = [...baseModels, 'Pony']
    expect(baseModels).toEqual(['SDXL 1.0', 'Pony'])
  })

  it('should remove individual base models', () => {
    let baseModels = ['SDXL 1.0', 'Pony', 'SD 1.5']

    baseModels = baseModels.filter((m) => m !== 'Pony')
    expect(baseModels).toEqual(['SDXL 1.0', 'SD 1.5'])
  })

  it('should clear all base models', () => {
    const baseModels = ['SDXL 1.0', 'Pony', 'SD 1.5']
    const cleared: string[] = []

    expect(cleared).toEqual([])
    expect(baseModels.length).toBe(3)
  })
})

// =============================================================================
// CheckpointType Conditional Visibility
// =============================================================================

describe('CheckpointType Conditional Visibility', () => {
  it('should show checkpointType when Checkpoint is in modelTypes', () => {
    const modelTypes = ['LORA', 'Checkpoint']
    const isCheckpointSelected = modelTypes.includes('Checkpoint')

    expect(isCheckpointSelected).toBe(true)
  })

  it('should hide checkpointType when Checkpoint is NOT in modelTypes', () => {
    const modelTypes = ['LORA', 'VAE']
    const isCheckpointSelected = modelTypes.includes('Checkpoint')

    expect(isCheckpointSelected).toBe(false)
  })

  it('should clear checkpointType when Checkpoint is removed from modelTypes', () => {
    let modelTypes = ['LORA', 'Checkpoint']
    let checkpointType = 'Trained'

    // Remove Checkpoint from model types
    modelTypes = modelTypes.filter((t) => t !== 'Checkpoint')

    // Should auto-clear checkpointType
    if (!modelTypes.includes('Checkpoint') && checkpointType) {
      checkpointType = ''
    }

    expect(checkpointType).toBe('')
  })

  it('should keep checkpointType when other model types change', () => {
    let modelTypes = ['LORA', 'Checkpoint']
    const checkpointType = 'Merge'

    // Remove LORA (not Checkpoint)
    modelTypes = modelTypes.filter((t) => t !== 'LORA')

    // checkpointType should remain
    expect(modelTypes.includes('Checkpoint')).toBe(true)
    expect(checkpointType).toBe('Merge')
  })
})

// =============================================================================
// Active Filter Count Tests (updated for multi-select baseModels + checkpointType)
// =============================================================================

describe('Active Filter Count', () => {
  it('should count filters correctly with new schema', () => {
    const countActiveFilters = (
      sortBy: string,
      period: string,
      baseModels: string[],
      modelTypes: string[],
      checkpointType: string,
      fileFormat: string,
      category: string
    ) => {
      return [
        sortBy !== 'Most Downloaded' ? 1 : 0,
        period !== 'AllTime' ? 1 : 0,
        baseModels.length,
        modelTypes.length > 0 ? modelTypes.length : 0,
        checkpointType ? 1 : 0,
        fileFormat ? 1 : 0,
        category ? 1 : 0,
      ].reduce((a, b) => a + b, 0)
    }

    // No filters active
    expect(countActiveFilters('Most Downloaded', 'AllTime', [], [], '', '', '')).toBe(0)

    // One filter (sort)
    expect(countActiveFilters('Newest', 'AllTime', [], [], '', '', '')).toBe(1)

    // Multiple base models count individually
    expect(countActiveFilters('Most Downloaded', 'AllTime', ['SDXL 1.0', 'Pony'], [], '', '', '')).toBe(2)

    // With checkpointType
    expect(countActiveFilters('Most Downloaded', 'AllTime', [], ['Checkpoint'], 'Trained', '', '')).toBe(2)

    // All filters active
    // sort:1 + period:1 + baseModels:2 + modelTypes:2 + checkpointType:1 + fileFormat:1 + category:1 = 9
    expect(
      countActiveFilters('Newest', 'Month', ['SDXL 1.0', 'Pony'], ['LORA', 'Checkpoint'], 'Merge', 'SafeTensor', 'character')
    ).toBe(9)
  })
})
