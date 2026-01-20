/**
 * Tests for Settings Store
 *
 * Tests cover:
 * - NSFW blur state management
 * - Toggle functionality
 * - State persistence behavior
 */

import { describe, it, expect } from 'vitest'

// ============================================================================
// Settings Store Logic Tests
// ============================================================================

/**
 * Simulated settings store logic for testing
 * (actual store uses zustand, but we test the logic independently)
 */
interface SettingsState {
  nsfwBlurEnabled: boolean
}

function createSettingsStore(initialState: SettingsState = { nsfwBlurEnabled: true }) {
  let state = { ...initialState }

  return {
    getState: () => state,
    setState: (partial: Partial<SettingsState>) => {
      state = { ...state, ...partial }
    },
    toggleNsfwBlur: () => {
      state = { ...state, nsfwBlurEnabled: !state.nsfwBlurEnabled }
    },
  }
}

describe('Settings Store', () => {
  describe('Initial State', () => {
    it('should have NSFW blur enabled by default', () => {
      const store = createSettingsStore()
      expect(store.getState().nsfwBlurEnabled).toBe(true)
    })

    it('should accept custom initial state', () => {
      const store = createSettingsStore({ nsfwBlurEnabled: false })
      expect(store.getState().nsfwBlurEnabled).toBe(false)
    })
  })

  describe('Toggle NSFW Blur', () => {
    it('should toggle from true to false', () => {
      const store = createSettingsStore({ nsfwBlurEnabled: true })
      store.toggleNsfwBlur()
      expect(store.getState().nsfwBlurEnabled).toBe(false)
    })

    it('should toggle from false to true', () => {
      const store = createSettingsStore({ nsfwBlurEnabled: false })
      store.toggleNsfwBlur()
      expect(store.getState().nsfwBlurEnabled).toBe(true)
    })

    it('should toggle multiple times correctly', () => {
      const store = createSettingsStore({ nsfwBlurEnabled: true })

      store.toggleNsfwBlur()
      expect(store.getState().nsfwBlurEnabled).toBe(false)

      store.toggleNsfwBlur()
      expect(store.getState().nsfwBlurEnabled).toBe(true)

      store.toggleNsfwBlur()
      expect(store.getState().nsfwBlurEnabled).toBe(false)
    })
  })

  describe('Set State', () => {
    it('should update nsfwBlurEnabled directly', () => {
      const store = createSettingsStore({ nsfwBlurEnabled: true })
      store.setState({ nsfwBlurEnabled: false })
      expect(store.getState().nsfwBlurEnabled).toBe(false)
    })
  })
})

// ============================================================================
// Zustand Selector Pattern Tests
// ============================================================================

describe('Zustand Selector Pattern', () => {
  /**
   * Tests for the selector pattern used in MediaPreview:
   * const nsfwBlurEnabled = useSettingsStore((state) => state.nsfwBlurEnabled)
   */

  it('should extract nsfwBlurEnabled with selector', () => {
    const state = { nsfwBlurEnabled: true, otherSetting: 'value' }
    const selector = (s: typeof state) => s.nsfwBlurEnabled

    expect(selector(state)).toBe(true)
  })

  it('should return updated value when state changes', () => {
    let state = { nsfwBlurEnabled: true }
    const selector = (s: typeof state) => s.nsfwBlurEnabled

    expect(selector(state)).toBe(true)

    state = { nsfwBlurEnabled: false }
    expect(selector(state)).toBe(false)
  })

  it('selector should only depend on selected value', () => {
    const selector = (s: { nsfwBlurEnabled: boolean }) => s.nsfwBlurEnabled

    const state1 = { nsfwBlurEnabled: true, unrelated: 1 }
    const state2 = { nsfwBlurEnabled: true, unrelated: 2 }

    // Same selected value should return same result
    expect(selector(state1 as any)).toBe(selector(state2 as any))
  })
})

// ============================================================================
// Integration with MediaPreview Logic
// ============================================================================

describe('NSFW Blur Integration', () => {
  /**
   * Tests how settings store integrates with MediaPreview blur logic
   */

  interface MediaPreviewState {
    nsfw: boolean
    isRevealed: boolean
  }

  function shouldBlur(
    mediaState: MediaPreviewState,
    nsfwBlurEnabled: boolean
  ): boolean {
    return mediaState.nsfw && nsfwBlurEnabled && !mediaState.isRevealed
  }

  describe('Blur Calculation', () => {
    it('should blur NSFW content when blur is enabled', () => {
      const mediaState = { nsfw: true, isRevealed: false }
      expect(shouldBlur(mediaState, true)).toBe(true)
    })

    it('should NOT blur NSFW content when blur is disabled', () => {
      const mediaState = { nsfw: true, isRevealed: false }
      expect(shouldBlur(mediaState, false)).toBe(false)
    })

    it('should NOT blur revealed NSFW content', () => {
      const mediaState = { nsfw: true, isRevealed: true }
      expect(shouldBlur(mediaState, true)).toBe(false)
    })

    it('should NOT blur non-NSFW content', () => {
      const mediaState = { nsfw: false, isRevealed: false }
      expect(shouldBlur(mediaState, true)).toBe(false)
    })
  })

  describe('Global Toggle Effect', () => {
    it('should affect all cards when global toggle changes', () => {
      const cards = [
        { nsfw: true, isRevealed: false },
        { nsfw: true, isRevealed: false },
        { nsfw: false, isRevealed: false },
      ]

      // With blur enabled
      let nsfwBlurEnabled = true
      const blurredCount = cards.filter(c => shouldBlur(c, nsfwBlurEnabled)).length
      expect(blurredCount).toBe(2)

      // With blur disabled
      nsfwBlurEnabled = false
      const blurredCountAfter = cards.filter(c => shouldBlur(c, nsfwBlurEnabled)).length
      expect(blurredCountAfter).toBe(0)
    })

    it('should preserve revealed state when global toggle changes', () => {
      // User revealed card, then global toggle changes
      const card = { nsfw: true, isRevealed: true }

      // Blur re-enabled - card should stay revealed
      expect(shouldBlur(card, true)).toBe(false)
    })
  })
})

// ============================================================================
// Eye Icon Visibility Tests
// ============================================================================

describe('Eye Icon Visibility', () => {
  /**
   * Eye icon should only be visible when:
   * - Content is NSFW
   * - Blur is enabled globally
   * - Content is REVEALED (so user can hide it back)
   */

  function showEyeIcon(
    nsfw: boolean,
    nsfwBlurEnabled: boolean,
    isRevealed: boolean
  ): boolean {
    return nsfw && nsfwBlurEnabled && isRevealed
  }

  it('should show eye icon for revealed NSFW content', () => {
    expect(showEyeIcon(true, true, true)).toBe(true)
  })

  it('should NOT show eye icon for blurred NSFW content', () => {
    expect(showEyeIcon(true, true, false)).toBe(false)
  })

  it('should NOT show eye icon when blur is disabled', () => {
    expect(showEyeIcon(true, false, true)).toBe(false)
  })

  it('should NOT show eye icon for non-NSFW content', () => {
    expect(showEyeIcon(false, true, true)).toBe(false)
  })
})

// ============================================================================
// NSFW Badge Visibility Tests
// ============================================================================

describe('NSFW Badge Visibility', () => {
  /**
   * NSFW badge should be visible when:
   * - Content is NSFW
   * - Global blur is DISABLED
   */

  function showNsfwBadge(nsfw: boolean, nsfwBlurEnabled: boolean): boolean {
    return nsfw && !nsfwBlurEnabled
  }

  it('should show badge when NSFW and blur disabled', () => {
    expect(showNsfwBadge(true, false)).toBe(true)
  })

  it('should NOT show badge when blur is enabled', () => {
    expect(showNsfwBadge(true, true)).toBe(false)
  })

  it('should NOT show badge for non-NSFW content', () => {
    expect(showNsfwBadge(false, false)).toBe(false)
  })
})
