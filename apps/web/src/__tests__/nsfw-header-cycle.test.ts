/**
 * Header NSFW toggle tests
 *
 * Tests the ON/OFF toggle: show ↔ blur
 * When filterMode=hide (set in Settings), the button is hidden entirely.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useNsfwStore } from '@/stores/nsfwStore'

describe('Header NSFW toggle', () => {
  beforeEach(() => {
    useNsfwStore.setState({ filterMode: 'blur', maxLevel: 'all' })
  })

  // =========================================================================
  // Toggle logic (show ↔ blur)
  // =========================================================================

  describe('toggle behavior', () => {
    it('toggles from blur to show', () => {
      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().filterMode).toBe('show')
    })

    it('toggles from show to blur', () => {
      useNsfwStore.getState().setFilterMode('show')
      useNsfwStore.getState().setFilterMode('blur')
      expect(useNsfwStore.getState().filterMode).toBe('blur')
    })

    it('nsfwBlurEnabled syncs: blur=true, show=false', () => {
      useNsfwStore.getState().setFilterMode('blur')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)

      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(false)
    })
  })

  // =========================================================================
  // Hide mode — button not shown
  // =========================================================================

  describe('hide mode', () => {
    it('hide mode is only set via Settings, not via Header', () => {
      // Header only toggles show ↔ blur; hide is set in Settings
      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().filterMode).toBe('hide')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)
    })

    it('maxLevel is preserved when switching to hide', () => {
      useNsfwStore.setState({ maxLevel: 'r' })
      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().maxLevel).toBe('r')
    })

    it('getBrowsingLevel returns maxLevel bitmask even in hide mode', () => {
      useNsfwStore.setState({ maxLevel: 'all' })
      useNsfwStore.getState().setFilterMode('hide')
      // hide mode does NOT change API browsing level
      expect(useNsfwStore.getState().getBrowsingLevel()).toBe(31)
    })
  })

  // =========================================================================
  // Edge cases
  // =========================================================================

  describe('edge cases', () => {
    it('rapid toggle preserves consistency', () => {
      for (let i = 0; i < 10; i++) {
        const current = useNsfwStore.getState().filterMode
        useNsfwStore.getState().setFilterMode(current === 'blur' ? 'show' : 'blur')
      }
      // 10 toggles from blur → show (even count = back to blur)
      expect(useNsfwStore.getState().filterMode).toBe('blur')
    })

    it('maxLevel preserved across toggles', () => {
      useNsfwStore.setState({ maxLevel: 'r' })
      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().maxLevel).toBe('r')
      useNsfwStore.getState().setFilterMode('blur')
      expect(useNsfwStore.getState().maxLevel).toBe('r')
    })
  })
})
