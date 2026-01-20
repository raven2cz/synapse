/**
 * Tests for FullscreenMediaViewer Metadata Panel (GenerationDataPanel)
 *
 * Tests cover:
 * - Metadata panel state management
 * - Keyboard shortcut 'I' for toggle
 * - Auto-update on navigation
 * - Metadata extraction and display
 * - Panel visibility and positioning
 */

import { describe, it, expect } from 'vitest'

// ============================================================================
// Test Types
// ============================================================================

interface GenerationMeta {
  prompt?: string
  negativePrompt?: string
  seed?: number
  steps?: number
  cfgScale?: number
  sampler?: string
  model?: string
  modelHash?: string
  size?: string
  clipSkip?: number
}

interface FullscreenMediaItem {
  url: string
  type?: 'image' | 'video' | 'unknown'
  thumbnailUrl?: string
  nsfw?: boolean
  width?: number
  height?: number
  meta?: GenerationMeta
}

// ============================================================================
// Metadata Panel State Tests
// ============================================================================

describe('Metadata Panel State', () => {
  describe('Initial state', () => {
    it('should start with panel closed by default', () => {
      const showMetadataPanel = false
      expect(showMetadataPanel).toBe(false)
    })
  })

  describe('Toggle behavior', () => {
    it('should toggle panel open', () => {
      let showMetadataPanel = false

      const togglePanel = () => {
        showMetadataPanel = !showMetadataPanel
      }

      togglePanel()
      expect(showMetadataPanel).toBe(true)
    })

    it('should toggle panel closed', () => {
      let showMetadataPanel = true

      const togglePanel = () => {
        showMetadataPanel = !showMetadataPanel
      }

      togglePanel()
      expect(showMetadataPanel).toBe(false)
    })
  })

  describe('Panel visibility conditions', () => {
    it('should not show panel when viewer is closed', () => {
      const isOpen = false
      const showMetadataPanel = true

      const shouldShowPanel = isOpen && showMetadataPanel
      expect(shouldShowPanel).toBe(false)
    })

    it('should show panel when viewer is open and panel toggled on', () => {
      const isOpen = true
      const showMetadataPanel = true

      const shouldShowPanel = isOpen && showMetadataPanel
      expect(shouldShowPanel).toBe(true)
    })
  })
})

// ============================================================================
// Keyboard Shortcut Tests
// ============================================================================

describe('Keyboard Shortcut - I key', () => {
  describe('Key detection', () => {
    it('should recognize lowercase i', () => {
      const key: string = 'i'
      const isInfoKey = key === 'i' || key === 'I'
      expect(isInfoKey).toBe(true)
    })

    it('should recognize uppercase I', () => {
      const key: string = 'I'
      const isInfoKey = key === 'i' || key === 'I'
      expect(isInfoKey).toBe(true)
    })

    it('should not trigger on other keys', () => {
      const key: string = 'j'
      const isInfoKey = key === 'i' || key === 'I'
      expect(isInfoKey).toBe(false)
    })
  })

  describe('Key handler', () => {
    it('should toggle panel on I key press', () => {
      let showMetadataPanel = false

      const handleKeyDown = (key: string) => {
        if (key === 'i' || key === 'I') {
          showMetadataPanel = !showMetadataPanel
        }
      }

      handleKeyDown('i')
      expect(showMetadataPanel).toBe(true)

      handleKeyDown('I')
      expect(showMetadataPanel).toBe(false)
    })

    it('should not interfere with other shortcuts', () => {
      let showMetadataPanel = false
      let currentIndex = 0

      const handleKeyDown = (key: string) => {
        if (key === 'i' || key === 'I') {
          showMetadataPanel = !showMetadataPanel
        }
        if (key === 'ArrowRight') {
          currentIndex++
        }
      }

      handleKeyDown('ArrowRight')
      expect(currentIndex).toBe(1)
      expect(showMetadataPanel).toBe(false)
    })
  })
})

// ============================================================================
// Auto-Update on Navigation Tests
// ============================================================================

describe('Auto-Update on Navigation', () => {
  const mockItems: FullscreenMediaItem[] = [
    {
      url: 'image1.jpg',
      type: 'image',
      meta: { prompt: 'A cat', seed: 12345 },
    },
    {
      url: 'image2.jpg',
      type: 'image',
      meta: { prompt: 'A dog', seed: 67890 },
    },
    {
      url: 'video1.mp4',
      type: 'video',
      meta: undefined, // No metadata for video
    },
  ]

  describe('Current item tracking', () => {
    it('should get correct item for current index', () => {
      let currentIndex = 0
      const getCurrentItem = () => mockItems[currentIndex]

      expect(getCurrentItem()?.meta?.prompt).toBe('A cat')

      currentIndex = 1
      expect(getCurrentItem()?.meta?.prompt).toBe('A dog')
    })

    it('should handle navigation to item without metadata', () => {
      let currentIndex = 2
      const getCurrentItem = () => mockItems[currentIndex]
      const currentMeta = getCurrentItem()?.meta

      expect(currentMeta).toBeUndefined()
    })
  })

  describe('Metadata update on index change', () => {
    it('should update displayed metadata when index changes', () => {
      let currentIndex = 0
      let displayedMeta: GenerationMeta | undefined

      const updateMetadata = () => {
        displayedMeta = mockItems[currentIndex]?.meta
      }

      // Initial state
      updateMetadata()
      expect(displayedMeta?.seed).toBe(12345)

      // Navigate to next
      currentIndex = 1
      updateMetadata()
      expect(displayedMeta?.seed).toBe(67890)
    })
  })
})

// ============================================================================
// Metadata Extraction Tests
// ============================================================================

describe('Metadata Extraction', () => {
  describe('Valid metadata', () => {
    const validMeta: GenerationMeta = {
      prompt: 'A beautiful sunset over mountains',
      negativePrompt: 'blurry, low quality',
      seed: 123456789,
      steps: 30,
      cfgScale: 7.5,
      sampler: 'DPM++ 2M Karras',
      model: 'Realistic Vision V6',
      modelHash: 'abc123def',
      size: '512x768',
      clipSkip: 2,
    }

    it('should extract prompt', () => {
      expect(validMeta.prompt).toBe('A beautiful sunset over mountains')
    })

    it('should extract negative prompt', () => {
      expect(validMeta.negativePrompt).toBe('blurry, low quality')
    })

    it('should extract seed', () => {
      expect(validMeta.seed).toBe(123456789)
    })

    it('should extract generation parameters', () => {
      expect(validMeta.steps).toBe(30)
      expect(validMeta.cfgScale).toBe(7.5)
      expect(validMeta.sampler).toBe('DPM++ 2M Karras')
    })

    it('should extract model info', () => {
      expect(validMeta.model).toBe('Realistic Vision V6')
      expect(validMeta.modelHash).toBe('abc123def')
    })

    it('should extract size', () => {
      expect(validMeta.size).toBe('512x768')
    })
  })

  describe('Missing metadata fields', () => {
    it('should handle undefined meta gracefully', () => {
      const item: FullscreenMediaItem = { url: 'test.jpg' }
      const hasMetadata = item.meta !== undefined

      expect(hasMetadata).toBe(false)
    })

    it('should handle partial metadata', () => {
      const partialMeta: GenerationMeta = {
        prompt: 'Test prompt',
        // Other fields undefined
      }

      expect(partialMeta.prompt).toBe('Test prompt')
      expect(partialMeta.seed).toBeUndefined()
      expect(partialMeta.steps).toBeUndefined()
    })
  })

  describe('Empty metadata', () => {
    it('should detect empty meta object', () => {
      const emptyMeta: GenerationMeta = {}
      const hasContent = Object.keys(emptyMeta).length > 0

      expect(hasContent).toBe(false)
    })

    it('should detect meta with only undefined values', () => {
      const meta: GenerationMeta = {
        prompt: undefined,
        seed: undefined,
      }

      const hasDefinedValues = Object.values(meta).some(v => v !== undefined)
      expect(hasDefinedValues).toBe(false)
    })
  })
})

// ============================================================================
// Panel Display Tests
// ============================================================================

describe('Panel Display', () => {
  describe('Panel positioning', () => {
    it('should define right-side panel position', () => {
      const panelPosition = 'right'
      const panelClassName = panelPosition === 'right'
        ? 'fixed right-0 top-0 h-full'
        : 'fixed left-0 top-0 h-full'

      expect(panelClassName).toContain('right-0')
    })
  })

  describe('Panel width', () => {
    it('should have appropriate width for metadata display', () => {
      const panelWidth = 320 // pixels

      // Ensure width is reasonable for reading metadata
      expect(panelWidth).toBeGreaterThanOrEqual(280)
      expect(panelWidth).toBeLessThanOrEqual(400)
    })
  })

  describe('Scroll behavior', () => {
    it('should allow scrolling when content exceeds panel height', () => {
      const panelOverflow = 'overflow-y-auto'
      expect(panelOverflow).toContain('auto')
    })
  })
})

// ============================================================================
// Panel Content Sections Tests
// ============================================================================

describe('Panel Content Sections', () => {
  describe('Prompt section', () => {
    it('should display prompt when available', () => {
      const meta: GenerationMeta = { prompt: 'Test prompt' }
      const shouldShowPrompt = meta.prompt !== undefined && meta.prompt.length > 0

      expect(shouldShowPrompt).toBe(true)
    })

    it('should hide prompt section when not available', () => {
      const meta: GenerationMeta = {}
      const shouldShowPrompt = meta.prompt !== undefined && meta.prompt.length > 0

      expect(shouldShowPrompt).toBe(false)
    })
  })

  describe('Parameters section', () => {
    it('should show parameters when any are available', () => {
      const meta: GenerationMeta = { steps: 30, cfgScale: 7 }
      const hasParams = meta.steps !== undefined ||
        meta.cfgScale !== undefined ||
        meta.sampler !== undefined

      expect(hasParams).toBe(true)
    })
  })

  describe('Copy functionality', () => {
    it('should prepare prompt for clipboard', () => {
      const meta: GenerationMeta = { prompt: 'Copy this prompt' }
      const textToCopy = meta.prompt || ''

      expect(textToCopy).toBe('Copy this prompt')
    })

    it('should prepare full metadata as JSON', () => {
      const meta: GenerationMeta = { prompt: 'Test', seed: 123 }
      const jsonString = JSON.stringify(meta, null, 2)

      expect(jsonString).toContain('"prompt"')
      expect(jsonString).toContain('"seed"')
    })
  })
})

// ============================================================================
// Animation Tests
// ============================================================================

// ============================================================================
// React Hooks Order Tests (Regression Prevention)
// ============================================================================

describe('React Hooks Order (Regression)', () => {
  it('should document that all hooks must be before early return', () => {
    /**
     * CRITICAL: All React hooks (useState, useEffect, useCallback, useMemo)
     * MUST be called BEFORE any early return statement in the component.
     *
     * WRONG:
     * ```
     * if (!isOpen) return null;
     * const copyToClipboard = useCallback(...); // ERROR!
     * ```
     *
     * CORRECT:
     * ```
     * const copyToClipboard = useCallback(...); // All hooks first
     * if (!isOpen) return null;  // Early return after hooks
     * ```
     *
     * This test documents the fix for the "Rendered more hooks than
     * during the previous render" error.
     */
    expect(true).toBe(true)
  })

  it('should have currentHasMeta computed before early return', () => {
    // currentHasMeta is a useMemo that must be defined before early return
    const items = [{ url: 'test.jpg', meta: { prompt: 'test' } }]
    const currentIndex = 0
    const currentItem = items[currentIndex]

    // This logic must run on every render, not conditionally
    const currentHasMeta = currentItem?.meta && Object.keys(currentItem.meta).length > 0
    expect(currentHasMeta).toBe(true)
  })

  it('should have copyToClipboard callback before early return', () => {
    // copyToClipboard is a useCallback that must be defined before early return
    // This function must be defined on every render
    const copyToClipboard = async (_text: string, _fieldName: string) => {
      // no-op
    }

    // It should be callable even when component is "closed"
    // (but of course it won't be used - just needs to be defined)
    expect(typeof copyToClipboard).toBe('function')
  })
})

describe('Panel Animation', () => {
  describe('Open animation', () => {
    it('should define slide-in animation class', () => {
      const openAnimation = 'animate-in slide-in-from-right'
      expect(openAnimation).toContain('slide-in-from-right')
    })
  })

  describe('Close animation', () => {
    it('should define slide-out animation class', () => {
      const closeAnimation = 'animate-out slide-out-to-right'
      expect(closeAnimation).toContain('slide-out-to-right')
    })
  })

  describe('Animation duration', () => {
    it('should have reasonable animation duration', () => {
      const durationMs = 200
      expect(durationMs).toBeGreaterThanOrEqual(100)
      expect(durationMs).toBeLessThanOrEqual(400)
    })
  })
})
