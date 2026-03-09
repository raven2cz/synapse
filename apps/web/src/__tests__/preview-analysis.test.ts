/**
 * Preview Analysis Tab Logic Tests
 *
 * Tests for type contracts, hint matching logic, and data transformation.
 * Pure logic tests — no React rendering.
 */

import { describe, it, expect } from 'vitest'

// =============================================================================
// Types (mirroring PreviewAnalysisTab types)
// =============================================================================

interface PreviewModelHintInfo {
  filename: string
  kind: string | null
  source_type: 'api_meta' | 'png_embedded'
  raw_value: string
  resolvable: boolean
  hash?: string | null
  weight?: number | null
}

interface PreviewAnalysisItem {
  filename: string
  url?: string | null
  thumbnail_url?: string | null
  media_type: 'image' | 'video' | 'unknown'
  width?: number | null
  height?: number | null
  nsfw: boolean
  hints: PreviewModelHintInfo[]
  generation_params?: Record<string, any> | null
}

interface PreviewAnalysisResponse {
  pack_name: string
  previews: PreviewAnalysisItem[]
  total_hints: number
}

interface ResolutionCandidate {
  candidate_id: string
  display_name: string
  provider: string
  confidence: number
  tier: number
  evidence_groups: {
    provenance: string
    items: {
      source: string
      description: string
      confidence: number
      raw_value?: string
    }[]
  }[]
  selector_strategy: string
  compatibility_warnings: string[]
}

// =============================================================================
// Hint matching logic (mirroring PreviewAnalysisTab.findCandidateForHint)
// =============================================================================

function findCandidateForHint(
  hint: PreviewModelHintInfo,
  candidates: ResolutionCandidate[]
): string | null {
  for (const c of candidates) {
    for (const g of c.evidence_groups) {
      if (g.provenance.startsWith('preview:')) {
        for (const item of g.items) {
          if (
            item.raw_value &&
            (item.raw_value === hint.raw_value || item.raw_value === hint.filename)
          ) {
            return c.candidate_id
          }
        }
      }
    }
    const normalized = hint.filename.replace(/\.safetensors$|\.ckpt$|\.pt$/i, '').toLowerCase()
    if (c.display_name.toLowerCase().includes(normalized)) {
      return c.candidate_id
    }
  }
  return null
}

// =============================================================================
// Tests
// =============================================================================

describe('Preview Analysis Types', () => {
  it('PreviewAnalysisResponse type contract', () => {
    const response: PreviewAnalysisResponse = {
      pack_name: 'TestPack',
      previews: [
        {
          filename: '001.jpeg',
          url: 'https://example.com/001.jpeg',
          media_type: 'image',
          width: 832,
          height: 1216,
          nsfw: false,
          hints: [
            {
              filename: 'Juggernaut_XL.safetensors',
              kind: 'checkpoint',
              source_type: 'api_meta',
              raw_value: 'Juggernaut_XL',
              resolvable: true,
              hash: 'd91d35736d',
              weight: null,
            },
          ],
          generation_params: {
            sampler: 'DPM++ 2M',
            steps: 35,
          },
        },
      ],
      total_hints: 1,
    }

    expect(response.pack_name).toBe('TestPack')
    expect(response.previews).toHaveLength(1)
    expect(response.total_hints).toBe(1)
    expect(response.previews[0].hints[0].hash).toBe('d91d35736d')
  })

  it('handles video preview with no hints', () => {
    const item: PreviewAnalysisItem = {
      filename: '001.mp4',
      url: 'https://example.com/001.mp4',
      thumbnail_url: 'https://example.com/001_thumb.jpg',
      media_type: 'video',
      width: 1920,
      height: 1080,
      nsfw: false,
      hints: [],
      generation_params: null,
    }

    expect(item.media_type).toBe('video')
    expect(item.hints).toHaveLength(0)
    expect(item.thumbnail_url).toBeDefined()
  })

  it('handles preview with null optional fields', () => {
    const item: PreviewAnalysisItem = {
      filename: '001.jpeg',
      url: null,
      media_type: 'image',
      nsfw: false,
      hints: [],
    }

    expect(item.url).toBeNull()
    expect(item.width).toBeUndefined()
    expect(item.generation_params).toBeUndefined()
  })
})

describe('Hint Matching Logic', () => {
  const mockCandidates: ResolutionCandidate[] = [
    {
      candidate_id: 'c1',
      display_name: 'Juggernaut XL v10',
      provider: 'civitai',
      confidence: 0.95,
      tier: 1,
      evidence_groups: [
        {
          provenance: 'preview:001.jpeg',
          items: [
            {
              source: 'preview_api_meta',
              description: 'Model name from preview sidecar',
              confidence: 0.8,
              raw_value: 'Juggernaut_XL',
            },
          ],
        },
      ],
      selector_strategy: 'civitai',
      compatibility_warnings: [],
    },
    {
      candidate_id: 'c2',
      display_name: 'DreamShaper 8',
      provider: 'civitai',
      confidence: 0.6,
      tier: 3,
      evidence_groups: [
        {
          provenance: 'hash:sha256',
          items: [
            {
              source: 'hash_match',
              description: 'SHA256 match',
              confidence: 0.6,
            },
          ],
        },
      ],
      selector_strategy: 'civitai',
      compatibility_warnings: [],
    },
  ]

  it('matches hint by raw_value in preview evidence', () => {
    const hint: PreviewModelHintInfo = {
      filename: 'Juggernaut_XL.safetensors',
      kind: 'checkpoint',
      source_type: 'api_meta',
      raw_value: 'Juggernaut_XL',
      resolvable: true,
    }

    const result = findCandidateForHint(hint, mockCandidates)
    expect(result).toBe('c1')
  })

  it('matches hint by display_name fallback', () => {
    // "dreamshaper" (without extension) is a substring of "DreamShaper 8"
    const candidatesWithName: ResolutionCandidate[] = [
      {
        ...mockCandidates[1],
        display_name: 'dreamshaper_8 v1',
      },
    ]

    const hint: PreviewModelHintInfo = {
      filename: 'dreamshaper_8.safetensors',
      kind: 'checkpoint',
      source_type: 'api_meta',
      raw_value: 'DreamShaper_8_Original',
      resolvable: true,
    }

    const result = findCandidateForHint(hint, candidatesWithName)
    expect(result).toBe('c2') // "dreamshaper_8" included in "dreamshaper_8 v1"
  })

  it('returns null when no candidate matches', () => {
    const hint: PreviewModelHintInfo = {
      filename: 'unknown_model.safetensors',
      kind: 'checkpoint',
      source_type: 'api_meta',
      raw_value: 'UnknownModel',
      resolvable: true,
    }

    const result = findCandidateForHint(hint, mockCandidates)
    expect(result).toBeNull()
  })

  it('returns null for empty candidates', () => {
    const hint: PreviewModelHintInfo = {
      filename: 'test.safetensors',
      kind: 'checkpoint',
      source_type: 'api_meta',
      raw_value: 'test',
      resolvable: true,
    }

    const result = findCandidateForHint(hint, [])
    expect(result).toBeNull()
  })

  it('strips extension for display_name matching', () => {
    const candidatesWithName: ResolutionCandidate[] = [
      {
        ...mockCandidates[0],
        display_name: 'Juggernaut_XL v10',
      },
    ]

    const hint: PreviewModelHintInfo = {
      filename: 'juggernaut_xl.safetensors',
      kind: 'checkpoint',
      source_type: 'api_meta',
      raw_value: 'juggernaut_xl',
      resolvable: true,
    }

    // "juggernaut_xl" (no ext) is substring of "juggernaut_xl v10" (lowered)
    const result = findCandidateForHint(hint, candidatesWithName)
    expect(result).toBe('c1')
  })
})

describe('Kind Display Logic', () => {
  const KIND_MAP: Record<string, string> = {
    checkpoint: 'Checkpoint',
    lora: 'LoRA',
    vae: 'VAE',
    controlnet: 'ControlNet',
    embedding: 'Embedding',
    upscaler: 'Upscaler',
  }

  it('maps all known kinds to labels', () => {
    for (const [_kind, label] of Object.entries(KIND_MAP)) {
      expect(label).toBeDefined()
      expect(typeof label).toBe('string')
    }
  })

  it('kind matching: hint kind matches dep kind', () => {
    const depKind = 'checkpoint'
    const hint: PreviewModelHintInfo = {
      filename: 'test.safetensors',
      kind: 'checkpoint',
      source_type: 'api_meta',
      raw_value: 'test',
      resolvable: true,
    }

    const isMatchingKind = hint.kind === depKind || hint.kind === null
    expect(isMatchingKind).toBe(true)
  })

  it('kind matching: null kind matches any dep kind', () => {
    const depKind = 'lora'
    const hint: PreviewModelHintInfo = {
      filename: 'test.safetensors',
      kind: null,
      source_type: 'api_meta',
      raw_value: 'test',
      resolvable: true,
    }

    const isMatchingKind = hint.kind === depKind || hint.kind === null
    expect(isMatchingKind).toBe(true)
  })

  it('kind matching: different kind does not match', () => {
    const depKind = 'checkpoint'
    const hint: PreviewModelHintInfo = {
      filename: 'test.safetensors',
      kind: 'lora',
      source_type: 'api_meta',
      raw_value: 'test',
      resolvable: true,
    }

    const isMatchingKind = hint.kind === depKind || hint.kind === null
    expect(isMatchingKind).toBe(false)
  })
})
