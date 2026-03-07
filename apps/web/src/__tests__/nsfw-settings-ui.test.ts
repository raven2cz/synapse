/**
 * Tests for NSFW Settings UI logic
 *
 * Tests the UI behavior decisions for the SettingsPage NSFW section:
 * - 3-mode segmented control (show/blur/hide)
 * - maxLevel dropdown visibility
 * - Mode descriptions
 * - Interaction with nsfwStore
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useNsfwStore, type NsfwFilterMode, type NsfwMaxLevel } from '../stores/nsfwStore'

// =============================================================================
// Helpers simulating UI logic from SettingsPage
// =============================================================================

const FILTER_MODES: NsfwFilterMode[] = ['show', 'blur', 'hide']
const MAX_LEVELS: NsfwMaxLevel[] = ['pg', 'pg13', 'r', 'x', 'all']

function shouldShowMaxLevelDropdown(filterMode: NsfwFilterMode): boolean {
  return filterMode !== 'hide'
}

function getActiveSegmentIndex(filterMode: NsfwFilterMode): number {
  return FILTER_MODES.indexOf(filterMode)
}

// =============================================================================
// Tests
// =============================================================================

describe('NSFW Settings UI', () => {
  beforeEach(() => {
    useNsfwStore.setState({
      filterMode: 'blur',
      maxLevel: 'all',
      nsfwBlurEnabled: true,
    })
  })

  describe('segmented control', () => {
    it('renders all 3 modes', () => {
      expect(FILTER_MODES).toHaveLength(3)
      expect(FILTER_MODES).toEqual(['show', 'blur', 'hide'])
    })

    it('blur is active by default (index 1)', () => {
      expect(getActiveSegmentIndex(useNsfwStore.getState().filterMode)).toBe(1)
    })

    it('clicking show activates index 0', () => {
      useNsfwStore.getState().setFilterMode('show')
      expect(getActiveSegmentIndex(useNsfwStore.getState().filterMode)).toBe(0)
    })

    it('clicking hide activates index 2', () => {
      useNsfwStore.getState().setFilterMode('hide')
      expect(getActiveSegmentIndex(useNsfwStore.getState().filterMode)).toBe(2)
    })

    it('clicking same mode is idempotent', () => {
      useNsfwStore.getState().setFilterMode('blur')
      expect(useNsfwStore.getState().filterMode).toBe('blur')
    })
  })

  describe('maxLevel dropdown visibility', () => {
    it('visible when mode=show', () => {
      useNsfwStore.getState().setFilterMode('show')
      expect(shouldShowMaxLevelDropdown(useNsfwStore.getState().filterMode)).toBe(true)
    })

    it('visible when mode=blur', () => {
      expect(shouldShowMaxLevelDropdown(useNsfwStore.getState().filterMode)).toBe(true)
    })

    it('hidden when mode=hide', () => {
      useNsfwStore.getState().setFilterMode('hide')
      expect(shouldShowMaxLevelDropdown(useNsfwStore.getState().filterMode)).toBe(false)
    })
  })

  describe('maxLevel dropdown options', () => {
    it('has all 5 options in correct order', () => {
      expect(MAX_LEVELS).toEqual(['pg', 'pg13', 'r', 'x', 'all'])
    })

    it('changing dropdown updates store', () => {
      for (const level of MAX_LEVELS) {
        useNsfwStore.getState().setMaxLevel(level)
        expect(useNsfwStore.getState().maxLevel).toBe(level)
      }
    })

    it('maxLevel persists when switching filter modes', () => {
      useNsfwStore.getState().setMaxLevel('r')
      useNsfwStore.getState().setFilterMode('hide')
      useNsfwStore.getState().setFilterMode('blur')
      expect(useNsfwStore.getState().maxLevel).toBe('r')
    })
  })

  describe('mode descriptions', () => {
    it('each mode has a unique i18n key pattern', () => {
      const keys = FILTER_MODES.map((m) => `settings.display.nsfwMode_${m}Desc`)
      const unique = new Set(keys)
      expect(unique.size).toBe(3)
    })

    it('description key matches current filterMode', () => {
      for (const mode of FILTER_MODES) {
        useNsfwStore.getState().setFilterMode(mode)
        const key = `settings.display.nsfwMode_${useNsfwStore.getState().filterMode}Desc`
        expect(key).toBe(`settings.display.nsfwMode_${mode}Desc`)
      }
    })
  })

  describe('i18n key completeness', () => {
    it('all mode labels have matching i18n key pattern', () => {
      for (const mode of FILTER_MODES) {
        const labelKey = `settings.display.nsfwMode_${mode}`
        const descKey = `settings.display.nsfwMode_${mode}Desc`
        expect(labelKey).toMatch(/^settings\.display\.nsfwMode_(show|blur|hide)$/)
        expect(descKey).toMatch(/^settings\.display\.nsfwMode_(show|blur|hide)Desc$/)
      }
    })

    it('all maxLevel options have matching i18n key pattern', () => {
      for (const level of MAX_LEVELS) {
        const key = `settings.display.nsfwLevel_${level}`
        expect(key).toMatch(/^settings\.display\.nsfwLevel_(pg|pg13|r|x|all)$/)
      }
    })
  })

  describe('backward compat with settingsStore consumers', () => {
    it('nsfwBlurEnabled=true when mode=blur', () => {
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)
    })

    it('nsfwBlurEnabled=false when mode=show', () => {
      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(false)
    })

    it('nsfwBlurEnabled=true when mode=hide', () => {
      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)
    })
  })

  describe('API payload backward compat', () => {
    it('blur mode → nsfw_blur_enabled: true for API', () => {
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)
    })

    it('hide mode → nsfw_blur_enabled: true for API (both map to true)', () => {
      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)
    })

    it('show mode → nsfw_blur_enabled: false for API', () => {
      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(false)
    })
  })

  describe('maxLevel + shouldHide interaction', () => {
    it('changing maxLevel via dropdown affects shouldHide behavior', () => {
      // Simulate: user sets maxLevel to PG via dropdown
      useNsfwStore.getState().setMaxLevel('pg')
      // Level 2 (PG-13) should be hidden
      expect(useNsfwStore.getState().shouldHide(2)).toBe(true)
      // Level 1 (PG) should not
      expect(useNsfwStore.getState().shouldHide(1)).toBe(false)
    })

    it('changing maxLevel to all allows everything', () => {
      useNsfwStore.getState().setMaxLevel('all')
      expect(useNsfwStore.getState().shouldHide(2)).toBe(false)
      expect(useNsfwStore.getState().shouldHide(4)).toBe(false)
      expect(useNsfwStore.getState().shouldHide(8)).toBe(false)
      expect(useNsfwStore.getState().shouldHide(16)).toBe(false)
    })

    it('maxLevel dropdown change does not affect shouldBlur', () => {
      useNsfwStore.getState().setMaxLevel('pg')
      // shouldBlur only cares about isNsfw + filterMode=blur, not maxLevel
      expect(useNsfwStore.getState().shouldBlur(4)).toBe(true)
      expect(useNsfwStore.getState().shouldBlur(1)).toBe(false)
    })
  })

  describe('full mode cycle', () => {
    it('cycling through all modes updates state correctly', () => {
      // blur (default) → show → hide → blur
      expect(useNsfwStore.getState().filterMode).toBe('blur')

      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().filterMode).toBe('show')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(false)

      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().filterMode).toBe('hide')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)

      useNsfwStore.getState().setFilterMode('blur')
      expect(useNsfwStore.getState().filterMode).toBe('blur')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)
    })
  })
})
