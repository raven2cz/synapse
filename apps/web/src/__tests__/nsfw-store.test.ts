/**
 * Tests for NSFW Store — level-aware logic, cross-tab sync, backward compat
 */

import { describe, it, expect, beforeEach } from 'vitest'
import {
  normalizeLevel,
  exceedsMaxLevel,
  UNKNOWN_NSFW_LEVEL,
  LEVEL_BITMASK,
  useNsfwStore,
} from '../stores/nsfwStore'

// =============================================================================
// Pure helper tests
// =============================================================================

describe('normalizeLevel', () => {
  it('boolean true → isNsfw=true, level=UNKNOWN', () => {
    expect(normalizeLevel(true)).toEqual({ isNsfw: true, level: UNKNOWN_NSFW_LEVEL })
  })

  it('boolean false → isNsfw=false, level=1', () => {
    expect(normalizeLevel(false)).toEqual({ isNsfw: false, level: 1 })
  })

  it('number > 1 → isNsfw=true', () => {
    expect(normalizeLevel(4)).toEqual({ isNsfw: true, level: 4 })
  })

  it('number 1 → isNsfw=false (PG is safe)', () => {
    expect(normalizeLevel(1)).toEqual({ isNsfw: false, level: 1 })
  })

  it('number 2 → isNsfw=true', () => {
    expect(normalizeLevel(2)).toEqual({ isNsfw: true, level: 2 })
  })

  // Malformed input tests (fail closed — treat as unknown NSFW)
  it('number 0 → fail closed (isNsfw=true, unknown level)', () => {
    expect(normalizeLevel(0)).toEqual({ isNsfw: true, level: UNKNOWN_NSFW_LEVEL })
  })

  it('negative number → fail closed', () => {
    expect(normalizeLevel(-5)).toEqual({ isNsfw: true, level: UNKNOWN_NSFW_LEVEL })
  })

  it('NaN → fail closed', () => {
    expect(normalizeLevel(NaN)).toEqual({ isNsfw: true, level: UNKNOWN_NSFW_LEVEL })
  })

  it('Infinity → fail closed', () => {
    expect(normalizeLevel(Infinity)).toEqual({ isNsfw: true, level: UNKNOWN_NSFW_LEVEL })
  })

  // All valid Civitai single-bit levels
  it('all Civitai levels: 1=safe, 2/4/8/16=nsfw', () => {
    expect(normalizeLevel(1).isNsfw).toBe(false)
    expect(normalizeLevel(2).isNsfw).toBe(true)
    expect(normalizeLevel(4).isNsfw).toBe(true)
    expect(normalizeLevel(8).isNsfw).toBe(true)
    expect(normalizeLevel(16).isNsfw).toBe(true)
  })
})

describe('exceedsMaxLevel', () => {
  it('UNKNOWN_NSFW_LEVEL fail-closed: hidden when restricted, visible at maxLevel=all', () => {
    // maxBitmask=31 (all): unknown items pass through (user accepts everything)
    expect(exceedsMaxLevel(UNKNOWN_NSFW_LEVEL, 31)).toBe(false)
    // maxBitmask<31: unknown items are hidden (fail-closed for safety)
    expect(exceedsMaxLevel(UNKNOWN_NSFW_LEVEL, 1)).toBe(true)
    expect(exceedsMaxLevel(UNKNOWN_NSFW_LEVEL, 7)).toBe(true)
    expect(exceedsMaxLevel(UNKNOWN_NSFW_LEVEL, 15)).toBe(true)
  })

  it('level 8 exceeds mask 7 (r)', () => {
    expect(exceedsMaxLevel(8, 7)).toBe(true)
  })

  it('level 4 does not exceed mask 7 (r)', () => {
    expect(exceedsMaxLevel(4, 7)).toBe(false)
  })

  it('level 2 does not exceed mask 3 (pg13)', () => {
    expect(exceedsMaxLevel(2, 3)).toBe(false)
  })

  it('level 4 exceeds mask 3 (pg13)', () => {
    expect(exceedsMaxLevel(4, 3)).toBe(true)
  })

  it('level 16 exceeds mask 15 (x)', () => {
    expect(exceedsMaxLevel(16, 15)).toBe(true)
  })

  it('level 1 (PG) never exceeds any mask', () => {
    expect(exceedsMaxLevel(1, 1)).toBe(false)
  })
})

describe('LEVEL_BITMASK', () => {
  it('has correct values for all levels', () => {
    expect(LEVEL_BITMASK.pg).toBe(1)
    expect(LEVEL_BITMASK.pg13).toBe(3)
    expect(LEVEL_BITMASK.r).toBe(7)
    expect(LEVEL_BITMASK.x).toBe(15)
    expect(LEVEL_BITMASK.all).toBe(31)
  })
})

// =============================================================================
// Store integration tests
// =============================================================================

describe('useNsfwStore', () => {
  beforeEach(() => {
    // Reset store to defaults
    useNsfwStore.setState({
      filterMode: 'blur',
      maxLevel: 'all',
      nsfwBlurEnabled: true,
    })
  })

  describe('shouldBlur', () => {
    it('boolean true in blur mode → true', () => {
      expect(useNsfwStore.getState().shouldBlur(true)).toBe(true)
    })

    it('boolean false in blur mode → false', () => {
      expect(useNsfwStore.getState().shouldBlur(false)).toBe(false)
    })

    it('numeric nsfw level in blur mode → true', () => {
      expect(useNsfwStore.getState().shouldBlur(4)).toBe(true)
    })

    it('level 1 (PG) in blur mode → false', () => {
      expect(useNsfwStore.getState().shouldBlur(1)).toBe(false)
    })

    it('in show mode → always false', () => {
      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().shouldBlur(true)).toBe(false)
      expect(useNsfwStore.getState().shouldBlur(8)).toBe(false)
    })

    it('in hide mode → false (shouldHide handles hiding)', () => {
      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().shouldBlur(true)).toBe(false)
    })

    it('malformed input (NaN) in blur mode → true (fail closed)', () => {
      expect(useNsfwStore.getState().shouldBlur(NaN)).toBe(true)
    })

    it('malformed input (0) in blur mode → true (fail closed)', () => {
      expect(useNsfwStore.getState().shouldBlur(0)).toBe(true)
    })
  })

  describe('shouldHide', () => {
    it('hide mode → true for any nsfw content', () => {
      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().shouldHide(true)).toBe(true)
      expect(useNsfwStore.getState().shouldHide(4)).toBe(true)
    })

    it('hide mode → false for non-nsfw', () => {
      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().shouldHide(false)).toBe(false)
      expect(useNsfwStore.getState().shouldHide(1)).toBe(false)
    })

    it('blur mode + boolean true → false (unknown level, no ceiling)', () => {
      expect(useNsfwStore.getState().shouldHide(true)).toBe(false)
    })

    it('blur mode + level exceeding maxLevel → true', () => {
      useNsfwStore.getState().setMaxLevel('r')
      // level 8 (bit 3) is not in mask 7 (bits 0-2)
      expect(useNsfwStore.getState().shouldHide(8)).toBe(true)
    })

    it('blur mode + level within maxLevel → false', () => {
      useNsfwStore.getState().setMaxLevel('r')
      expect(useNsfwStore.getState().shouldHide(2)).toBe(false)
      expect(useNsfwStore.getState().shouldHide(4)).toBe(false)
    })

    it('show mode + boolean true → false', () => {
      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().shouldHide(true)).toBe(false)
    })

    it('show mode + level exceeding maxLevel → true', () => {
      useNsfwStore.getState().setFilterMode('show')
      useNsfwStore.getState().setMaxLevel('pg13')
      expect(useNsfwStore.getState().shouldHide(4)).toBe(true)
    })

    it('malformed input (NaN) in hide mode → true', () => {
      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().shouldHide(NaN)).toBe(true)
    })

    it('malformed input (0) in blur mode → false (unknown level passes ceiling)', () => {
      expect(useNsfwStore.getState().shouldHide(0)).toBe(false)
    })

    it('all maxLevel thresholds work correctly with each Civitai level', () => {
      const levels = [2, 4, 8, 16] as const
      const thresholds: Array<{ max: 'pg' | 'pg13' | 'r' | 'x' | 'all'; allowedUpTo: number }> = [
        { max: 'pg', allowedUpTo: 1 },
        { max: 'pg13', allowedUpTo: 2 },
        { max: 'r', allowedUpTo: 4 },
        { max: 'x', allowedUpTo: 8 },
        { max: 'all', allowedUpTo: 16 },
      ]
      for (const { max, allowedUpTo } of thresholds) {
        useNsfwStore.getState().setMaxLevel(max)
        for (const lvl of levels) {
          const expected = lvl > allowedUpTo
          expect(useNsfwStore.getState().shouldHide(lvl)).toBe(expected)
        }
      }
    })
  })

  describe('getBrowsingLevel', () => {
    it('hide mode uses maxLevel (does not force API filtering)', () => {
      useNsfwStore.getState().setFilterMode('hide')
      useNsfwStore.getState().setMaxLevel('all')
      expect(useNsfwStore.getState().getBrowsingLevel()).toBe(31)
    })

    it('blur + maxLevel=r → 7', () => {
      useNsfwStore.getState().setMaxLevel('r')
      expect(useNsfwStore.getState().getBrowsingLevel()).toBe(7)
    })

    it('show + maxLevel=all → 31', () => {
      useNsfwStore.getState().setFilterMode('show')
      useNsfwStore.getState().setMaxLevel('all')
      expect(useNsfwStore.getState().getBrowsingLevel()).toBe(31)
    })

    it('all maxLevel values produce correct bitmasks', () => {
      const expected: Array<[string, number]> = [
        ['pg', 1], ['pg13', 3], ['r', 7], ['x', 15], ['all', 31],
      ]
      for (const [level, bitmask] of expected) {
        useNsfwStore.getState().setMaxLevel(level as any)
        expect(useNsfwStore.getState().getBrowsingLevel()).toBe(bitmask)
      }
    })

    it('hide mode respects maxLevel (no API override)', () => {
      useNsfwStore.getState().setFilterMode('hide')
      useNsfwStore.getState().setMaxLevel('all')
      expect(useNsfwStore.getState().getBrowsingLevel()).toBe(31)
      useNsfwStore.getState().setMaxLevel('x')
      expect(useNsfwStore.getState().getBrowsingLevel()).toBe(15)
    })
  })

  describe('state transitions', () => {
    it('setFilterMode updates nsfwBlurEnabled', () => {
      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(false)
      useNsfwStore.getState().setFilterMode('blur')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)
      useNsfwStore.getState().setFilterMode('hide')
      expect(useNsfwStore.getState().nsfwBlurEnabled).toBe(true)
    })

    it('setMaxLevel does not affect filterMode', () => {
      useNsfwStore.getState().setMaxLevel('pg')
      expect(useNsfwStore.getState().filterMode).toBe('blur')
      expect(useNsfwStore.getState().maxLevel).toBe('pg')
    })
  })

  describe('backward compatibility', () => {
    it('shouldBlur(true) in blur mode = true', () => {
      expect(useNsfwStore.getState().shouldBlur(true)).toBe(true)
    })

    it('shouldBlur(false) = false regardless of mode', () => {
      expect(useNsfwStore.getState().shouldBlur(false)).toBe(false)
      useNsfwStore.getState().setFilterMode('show')
      expect(useNsfwStore.getState().shouldBlur(false)).toBe(false)
    })

    it('shouldHide(true) in blur+maxLevel=all → false (unknown level passes)', () => {
      expect(useNsfwStore.getState().shouldHide(true)).toBe(false)
    })
  })
})

// =============================================================================
// Cross-tab sync tests
// =============================================================================

describe('cross-tab sync', () => {
  beforeEach(() => {
    useNsfwStore.setState({
      filterMode: 'blur',
      maxLevel: 'all',
      nsfwBlurEnabled: true,
    })
  })

  it('storage event updates store state', () => {
    const event = new StorageEvent('storage', {
      key: 'synapse-nsfw-settings',
      newValue: JSON.stringify({
        state: { filterMode: 'show', maxLevel: 'r' },
      }),
    })
    window.dispatchEvent(event)

    const state = useNsfwStore.getState()
    expect(state.filterMode).toBe('show')
    expect(state.maxLevel).toBe('r')
    expect(state.nsfwBlurEnabled).toBe(false)
  })

  it('null storage event resets to defaults', () => {
    // First change away from defaults
    useNsfwStore.getState().setFilterMode('show')

    const event = new StorageEvent('storage', {
      key: 'synapse-nsfw-settings',
      newValue: null,
    })
    window.dispatchEvent(event)

    const state = useNsfwStore.getState()
    expect(state.filterMode).toBe('blur')
    expect(state.maxLevel).toBe('all')
    expect(state.nsfwBlurEnabled).toBe(true)
  })

  it('ignores storage events for other keys', () => {
    useNsfwStore.getState().setFilterMode('hide')

    const event = new StorageEvent('storage', {
      key: 'some-other-key',
      newValue: JSON.stringify({ state: { filterMode: 'show', maxLevel: 'pg' } }),
    })
    window.dispatchEvent(event)

    expect(useNsfwStore.getState().filterMode).toBe('hide')
  })

  it('ignores malformed JSON', () => {
    const event = new StorageEvent('storage', {
      key: 'synapse-nsfw-settings',
      newValue: 'not valid json{{{',
    })
    // Should not throw
    window.dispatchEvent(event)

    // State unchanged
    expect(useNsfwStore.getState().filterMode).toBe('blur')
  })

  it('ignores valid JSON with invalid filterMode', () => {
    const event = new StorageEvent('storage', {
      key: 'synapse-nsfw-settings',
      newValue: JSON.stringify({ state: { filterMode: 'invalid', maxLevel: 'all' } }),
    })
    window.dispatchEvent(event)
    expect(useNsfwStore.getState().filterMode).toBe('blur')
  })

  it('ignores valid JSON with invalid maxLevel', () => {
    const event = new StorageEvent('storage', {
      key: 'synapse-nsfw-settings',
      newValue: JSON.stringify({ state: { filterMode: 'show', maxLevel: 'ultra' } }),
    })
    window.dispatchEvent(event)
    expect(useNsfwStore.getState().filterMode).toBe('blur')
  })

  it('ignores valid JSON with missing state object', () => {
    const event = new StorageEvent('storage', {
      key: 'synapse-nsfw-settings',
      newValue: JSON.stringify({ version: 1 }),
    })
    window.dispatchEvent(event)
    expect(useNsfwStore.getState().filterMode).toBe('blur')
  })

  it('skips update when state already matches (prevents oscillation)', () => {
    // Set store to 'show' + 'r'
    useNsfwStore.getState().setFilterMode('show')
    useNsfwStore.getState().setMaxLevel('r')

    // Simulate storage event with the SAME values
    const event = new StorageEvent('storage', {
      key: 'synapse-nsfw-settings',
      newValue: JSON.stringify({ state: { filterMode: 'show', maxLevel: 'r' } }),
    })

    // Spy on setState to verify it's NOT called
    const originalSetState = useNsfwStore.setState
    let setStateCalled = false
    useNsfwStore.setState = (...args: Parameters<typeof originalSetState>) => {
      setStateCalled = true
      return originalSetState(...args)
    }

    window.dispatchEvent(event)
    expect(setStateCalled).toBe(false)

    // Restore
    useNsfwStore.setState = originalSetState
  })
})
