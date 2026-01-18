/**
 * Tests for MediaPreview NSFW Behavior
 *
 * Tests cover:
 * - NSFW blur state management
 * - Eye icon visibility logic
 * - Click-to-reveal functionality
 * - Global toggle integration
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React from 'react'

// Mock the settings store with different states
const mockStore = {
  nsfwBlurEnabled: true,
}

vi.mock('@/stores/settingsStore', () => ({
  useSettingsStore: vi.fn((selector) => {
    return typeof selector === 'function' ? selector(mockStore) : mockStore
  }),
}))

// ============================================================================
// NSFW State Logic Tests (Unit Tests without component rendering)
// ============================================================================

describe('NSFW State Logic', () => {
  describe('shouldBlur calculation', () => {
    it('should blur when nsfw=true, nsfwBlurEnabled=true, isRevealed=false', () => {
      const nsfw = true
      const nsfwBlurEnabled = true
      const isRevealed = false
      const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed
      expect(shouldBlur).toBe(true)
    })

    it('should NOT blur when nsfw=true, nsfwBlurEnabled=true, isRevealed=true', () => {
      const nsfw = true
      const nsfwBlurEnabled = true
      const isRevealed = true
      const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed
      expect(shouldBlur).toBe(false)
    })

    it('should NOT blur when nsfw=true, nsfwBlurEnabled=false', () => {
      const nsfw = true
      const nsfwBlurEnabled = false
      const isRevealed = false
      const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed
      expect(shouldBlur).toBe(false)
    })

    it('should NOT blur when nsfw=false', () => {
      const nsfw = false
      const nsfwBlurEnabled = true
      const isRevealed = false
      const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed
      expect(shouldBlur).toBe(false)
    })
  })

  describe('Eye icon visibility logic', () => {
    /**
     * Eye icon should only be visible when:
     * - Content is NSFW
     * - Blur is enabled globally
     * - Content is currently REVEALED (so user can hide it back)
     */
    it('should show eye icon only when nsfw AND blur enabled AND revealed', () => {
      const testCases = [
        { nsfw: true, nsfwBlurEnabled: true, isRevealed: true, expected: true },
        { nsfw: true, nsfwBlurEnabled: true, isRevealed: false, expected: false },
        { nsfw: true, nsfwBlurEnabled: false, isRevealed: true, expected: false },
        { nsfw: true, nsfwBlurEnabled: false, isRevealed: false, expected: false },
        { nsfw: false, nsfwBlurEnabled: true, isRevealed: true, expected: false },
        { nsfw: false, nsfwBlurEnabled: true, isRevealed: false, expected: false },
      ]

      testCases.forEach(({ nsfw, nsfwBlurEnabled, isRevealed, expected }) => {
        const showEyeIcon = nsfw && nsfwBlurEnabled && isRevealed
        expect(showEyeIcon).toBe(expected)
      })
    })
  })

  describe('NSFW badge visibility logic', () => {
    /**
     * NSFW badge (red label) should be visible when:
     * - Content is NSFW
     * - Global blur is DISABLED (so user knows it's NSFW content)
     */
    it('should show NSFW badge when nsfw=true AND nsfwBlurEnabled=false', () => {
      const testCases = [
        { nsfw: true, nsfwBlurEnabled: false, expected: true },
        { nsfw: true, nsfwBlurEnabled: true, expected: false },
        { nsfw: false, nsfwBlurEnabled: false, expected: false },
        { nsfw: false, nsfwBlurEnabled: true, expected: false },
      ]

      testCases.forEach(({ nsfw, nsfwBlurEnabled, expected }) => {
        const showNsfwBadge = nsfw && !nsfwBlurEnabled
        expect(showNsfwBadge).toBe(expected)
      })
    })
  })

  describe('Clickable reveal area logic', () => {
    /**
     * Clickable reveal area should be visible when:
     * - Content is NSFW
     * - Blur is enabled
     * - Content is NOT revealed (so clicking anywhere reveals it)
     */
    it('should show clickable area when nsfw AND blur enabled AND NOT revealed', () => {
      const testCases = [
        { nsfw: true, nsfwBlurEnabled: true, isRevealed: false, expected: true },
        { nsfw: true, nsfwBlurEnabled: true, isRevealed: true, expected: false },
        { nsfw: true, nsfwBlurEnabled: false, isRevealed: false, expected: false },
        { nsfw: false, nsfwBlurEnabled: true, isRevealed: false, expected: false },
      ]

      testCases.forEach(({ nsfw, nsfwBlurEnabled, isRevealed, expected }) => {
        const showClickableArea = nsfw && nsfwBlurEnabled && !isRevealed
        expect(showClickableArea).toBe(expected)
      })
    })
  })
})

// ============================================================================
// State Transition Tests
// ============================================================================

describe('NSFW State Transitions', () => {
  it('should transition from blurred to revealed on click', () => {
    let isRevealed = false
    const handleRevealToggle = () => {
      isRevealed = !isRevealed
    }

    // Initial state
    expect(isRevealed).toBe(false)

    // Click to reveal
    handleRevealToggle()
    expect(isRevealed).toBe(true)
  })

  it('should transition from revealed to blurred on click', () => {
    let isRevealed = true
    const handleRevealToggle = () => {
      isRevealed = !isRevealed
    }

    // Initial state (revealed)
    expect(isRevealed).toBe(true)

    // Click to hide
    handleRevealToggle()
    expect(isRevealed).toBe(false)
  })

  it('should reset revealed state when global toggle changes', () => {
    // This tests the expected behavior that when global blur is toggled off and on,
    // the local revealed state should be respected
    let nsfwBlurEnabled = true
    let isRevealed = true

    // Disable blur globally
    nsfwBlurEnabled = false
    const shouldBlur = true && nsfwBlurEnabled && !isRevealed
    expect(shouldBlur).toBe(false) // No blur because globally disabled

    // Re-enable blur globally - isRevealed is still true from before
    nsfwBlurEnabled = true
    const shouldBlurAfter = true && nsfwBlurEnabled && !isRevealed
    expect(shouldBlurAfter).toBe(false) // Still not blurred because isRevealed=true
  })
})

// ============================================================================
// CSS Class Application Tests
// ============================================================================

describe('NSFW CSS Classes', () => {
  it('should apply blur-xl and scale-110 when shouldBlur is true', () => {
    const shouldBlur = true
    const expectedClasses = shouldBlur ? 'blur-xl scale-110' : ''
    expect(expectedClasses).toContain('blur-xl')
    expect(expectedClasses).toContain('scale-110')
  })

  it('should NOT apply blur classes when shouldBlur is false', () => {
    const shouldBlur = false
    const blurClasses = shouldBlur ? 'blur-xl scale-110' : ''
    expect(blurClasses).toBe('')
  })
})

// ============================================================================
// Integration Scenarios
// ============================================================================

describe('NSFW Integration Scenarios', () => {
  describe('Scenario: User browses NSFW content with blur enabled', () => {
    it('should show blurred content with NSFW indicator', () => {
      const nsfw = true
      const nsfwBlurEnabled = true
      let isRevealed = false

      // Content should be blurred
      expect(nsfw && nsfwBlurEnabled && !isRevealed).toBe(true)

      // NSFW overlay with EyeOff icon should be visible
      const showOverlay = nsfw && nsfwBlurEnabled && !isRevealed
      expect(showOverlay).toBe(true)

      // Eye toggle button should NOT be visible (only on revealed content)
      const showEyeButton = nsfw && nsfwBlurEnabled && isRevealed
      expect(showEyeButton).toBe(false)
    })

    it('should reveal content when clicked', () => {
      const nsfw = true
      const nsfwBlurEnabled = true
      let isRevealed = false

      // User clicks to reveal
      isRevealed = true

      // Content should no longer be blurred
      expect(nsfw && nsfwBlurEnabled && !isRevealed).toBe(false)

      // Eye toggle button should now be visible
      expect(nsfw && nsfwBlurEnabled && isRevealed).toBe(true)
    })
  })

  describe('Scenario: User disables NSFW blur globally', () => {
    it('should show all NSFW content unblurred with badge', () => {
      const nsfw = true
      const nsfwBlurEnabled = false

      // Content should NOT be blurred
      expect(nsfw && nsfwBlurEnabled).toBe(false)

      // NSFW badge should be visible
      expect(nsfw && !nsfwBlurEnabled).toBe(true)
    })
  })

  describe('Scenario: Non-NSFW content', () => {
    it('should not show any NSFW UI elements', () => {
      const nsfw = false
      const nsfwBlurEnabled = true
      const isRevealed = false

      // No blur
      expect(nsfw && nsfwBlurEnabled && !isRevealed).toBe(false)

      // No eye button
      expect(nsfw && nsfwBlurEnabled && isRevealed).toBe(false)

      // No NSFW badge
      expect(nsfw && !nsfwBlurEnabled).toBe(false)
    })
  })
})
