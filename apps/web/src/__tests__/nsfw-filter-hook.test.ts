/**
 * Tests for useNsfwFilter hook — centralized NSFW filtering logic
 *
 * Tests the hook's behavior as a pure composition of nsfwStore methods.
 * Since useNsfwFilter is a React hook, we test via the underlying store
 * methods and the hook's composition logic.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useNsfwStore, normalizeLevel } from '../stores/nsfwStore'
import type { NsfwFilterMode, NsfwMaxLevel } from '../stores/nsfwStore'

// =============================================================================
// Helpers — simulate hook logic without React rendering
// =============================================================================

/**
 * Simulates useNsfwFilter output for a given nsfwLevel and store state.
 * This avoids needing renderHook while testing the same composition logic.
 */
function simulateFilter(
  nsfwLevel: number | boolean,
  opts: { isRevealed?: boolean } = {}
) {
  const { isRevealed = false } = opts
  const state = useNsfwStore.getState()
  const isHidden = state.shouldHide(nsfwLevel)
  const isBlurred = !isHidden && state.shouldBlur(nsfwLevel) && !isRevealed
  const isNsfw = normalizeLevel(nsfwLevel).isNsfw
  const filterMode = state.filterMode
  const showBadge = isNsfw && (filterMode === 'show' || isRevealed)

  return { isBlurred, isHidden, isRevealed, isNsfw, showBadge }
}

function setMode(mode: NsfwFilterMode, maxLevel: NsfwMaxLevel = 'all') {
  useNsfwStore.getState().setFilterMode(mode)
  useNsfwStore.getState().setMaxLevel(maxLevel)
}

// =============================================================================
// Tests
// =============================================================================

describe('useNsfwFilter (simulated)', () => {
  beforeEach(() => {
    useNsfwStore.setState({
      filterMode: 'blur',
      maxLevel: 'all',
      nsfwBlurEnabled: true,
    })
  })

  // ---------------------------------------------------------------------------
  // isBlurred
  // ---------------------------------------------------------------------------

  describe('isBlurred', () => {
    it('true for NSFW content in blur mode', () => {
      setMode('blur')
      expect(simulateFilter(true).isBlurred).toBe(true)
      expect(simulateFilter(8).isBlurred).toBe(true)
    })

    it('false for safe content in blur mode', () => {
      setMode('blur')
      expect(simulateFilter(false).isBlurred).toBe(false)
      expect(simulateFilter(1).isBlurred).toBe(false)
    })

    it('false in show mode', () => {
      setMode('show')
      expect(simulateFilter(true).isBlurred).toBe(false)
      expect(simulateFilter(8).isBlurred).toBe(false)
    })

    it('false in hide mode (hidden takes priority)', () => {
      setMode('hide')
      expect(simulateFilter(true).isBlurred).toBe(false)
      expect(simulateFilter(8).isBlurred).toBe(false)
    })

    it('false when revealed', () => {
      setMode('blur')
      expect(simulateFilter(8, { isRevealed: true }).isBlurred).toBe(false)
    })

    it('false for safe content even when not revealed', () => {
      setMode('blur')
      expect(simulateFilter(false, { isRevealed: false }).isBlurred).toBe(false)
    })
  })

  // ---------------------------------------------------------------------------
  // isHidden
  // ---------------------------------------------------------------------------

  describe('isHidden', () => {
    it('true for NSFW in hide mode', () => {
      setMode('hide')
      expect(simulateFilter(true).isHidden).toBe(true)
      expect(simulateFilter(8).isHidden).toBe(true)
    })

    it('false for safe content in hide mode', () => {
      setMode('hide')
      expect(simulateFilter(false).isHidden).toBe(false)
      expect(simulateFilter(1).isHidden).toBe(false)
    })

    it('false in blur mode', () => {
      setMode('blur')
      expect(simulateFilter(true).isHidden).toBe(false)
      expect(simulateFilter(8).isHidden).toBe(false)
    })

    it('false in show mode', () => {
      setMode('show')
      expect(simulateFilter(true).isHidden).toBe(false)
      expect(simulateFilter(8).isHidden).toBe(false)
    })

    it('true when level exceeds maxLevel', () => {
      setMode('blur', 'r') // maxLevel=r → bitmask 7
      expect(simulateFilter(8).isHidden).toBe(true) // X exceeds R
      expect(simulateFilter(16).isHidden).toBe(true) // XXX exceeds R
    })

    it('false when level within maxLevel', () => {
      setMode('blur', 'r') // maxLevel=r → bitmask 7
      expect(simulateFilter(4).isHidden).toBe(false) // R within R
      expect(simulateFilter(2).isHidden).toBe(false) // PG13 within R
    })
  })

  // ---------------------------------------------------------------------------
  // isNsfw
  // ---------------------------------------------------------------------------

  describe('isNsfw', () => {
    it('boolean true → isNsfw', () => {
      expect(simulateFilter(true).isNsfw).toBe(true)
    })

    it('boolean false → not isNsfw', () => {
      expect(simulateFilter(false).isNsfw).toBe(false)
    })

    it('level > 1 → isNsfw', () => {
      expect(simulateFilter(2).isNsfw).toBe(true)
      expect(simulateFilter(4).isNsfw).toBe(true)
      expect(simulateFilter(8).isNsfw).toBe(true)
      expect(simulateFilter(16).isNsfw).toBe(true)
    })

    it('level 1 → not isNsfw (PG)', () => {
      expect(simulateFilter(1).isNsfw).toBe(false)
    })
  })

  // ---------------------------------------------------------------------------
  // showBadge
  // ---------------------------------------------------------------------------

  describe('showBadge', () => {
    it('true in show mode for NSFW content', () => {
      setMode('show')
      expect(simulateFilter(true).showBadge).toBe(true)
      expect(simulateFilter(8).showBadge).toBe(true)
    })

    it('false in show mode for safe content', () => {
      setMode('show')
      expect(simulateFilter(false).showBadge).toBe(false)
      expect(simulateFilter(1).showBadge).toBe(false)
    })

    it('false in blur mode when not revealed', () => {
      setMode('blur')
      expect(simulateFilter(8).showBadge).toBe(false)
    })

    it('true in blur mode when revealed', () => {
      setMode('blur')
      expect(simulateFilter(8, { isRevealed: true }).showBadge).toBe(true)
    })

    it('false in hide mode (hidden, never shown)', () => {
      setMode('hide')
      expect(simulateFilter(8).showBadge).toBe(false)
    })
  })

  // ---------------------------------------------------------------------------
  // Mutual exclusivity: hidden items are never blurred
  // ---------------------------------------------------------------------------

  describe('mutual exclusivity', () => {
    it('hidden items are never blurred', () => {
      setMode('hide')
      const result = simulateFilter(8)
      expect(result.isHidden).toBe(true)
      expect(result.isBlurred).toBe(false)
    })

    it('items exceeding maxLevel are hidden, not blurred', () => {
      setMode('blur', 'pg13') // bitmask 3
      const result = simulateFilter(8) // X exceeds PG13
      expect(result.isHidden).toBe(true)
      expect(result.isBlurred).toBe(false)
    })

    it('items within maxLevel are blurred in blur mode', () => {
      setMode('blur', 'r') // bitmask 7
      const result = simulateFilter(4) // R within R
      expect(result.isHidden).toBe(false)
      expect(result.isBlurred).toBe(true)
    })
  })

  // ---------------------------------------------------------------------------
  // Boolean backward compatibility
  // ---------------------------------------------------------------------------

  describe('backward compat (boolean input)', () => {
    it('shouldBlur(true) in blur mode = blurred', () => {
      setMode('blur')
      expect(simulateFilter(true).isBlurred).toBe(true)
    })

    it('shouldBlur(false) in blur mode = not blurred', () => {
      setMode('blur')
      expect(simulateFilter(false).isBlurred).toBe(false)
    })

    it('shouldHide(true) in hide mode = hidden', () => {
      setMode('hide')
      expect(simulateFilter(true).isHidden).toBe(true)
    })

    it('shouldHide(true) in blur mode with restricted maxLevel = hidden (fail-closed)', () => {
      setMode('blur', 'r')
      // boolean true → UNKNOWN_NSFW_LEVEL (-1), fail-closed: hidden when restricted
      expect(simulateFilter(true).isHidden).toBe(true)
    })

    it('shouldHide(true) in blur mode with maxLevel=all = not hidden', () => {
      setMode('blur', 'all')
      // boolean true → UNKNOWN_NSFW_LEVEL (-1), passes at maxLevel=all
      expect(simulateFilter(true).isHidden).toBe(false)
    })
  })

  // ---------------------------------------------------------------------------
  // Edge cases: all modes × all level types
  // ---------------------------------------------------------------------------

  describe('mode × level matrix', () => {
    const modes: NsfwFilterMode[] = ['show', 'blur', 'hide']
    const levels: Array<{ input: number | boolean; label: string; nsfw: boolean }> = [
      { input: false, label: 'boolean false', nsfw: false },
      { input: true, label: 'boolean true', nsfw: true },
      { input: 1, label: 'PG (1)', nsfw: false },
      { input: 2, label: 'PG13 (2)', nsfw: true },
      { input: 4, label: 'R (4)', nsfw: true },
      { input: 8, label: 'X (8)', nsfw: true },
      { input: 16, label: 'XXX (16)', nsfw: true },
    ]

    for (const mode of modes) {
      for (const { input, label, nsfw } of levels) {
        it(`${mode} + ${label}: consistent isNsfw=${nsfw}`, () => {
          setMode(mode)
          expect(simulateFilter(input).isNsfw).toBe(nsfw)
        })
      }
    }

    it('safe content is never blurred or hidden in any mode', () => {
      for (const mode of modes) {
        setMode(mode)
        expect(simulateFilter(false).isBlurred).toBe(false)
        expect(simulateFilter(false).isHidden).toBe(false)
        expect(simulateFilter(1).isBlurred).toBe(false)
        expect(simulateFilter(1).isHidden).toBe(false)
      }
    })
  })

  // ---------------------------------------------------------------------------
  // maxLevel filtering across modes
  // ---------------------------------------------------------------------------

  describe('maxLevel filtering', () => {
    const levelTests: Array<{ maxLevel: NsfwMaxLevel; blockedLevels: number[]; allowedLevels: number[] }> = [
      { maxLevel: 'pg', blockedLevels: [2, 4, 8, 16], allowedLevels: [1] },
      { maxLevel: 'pg13', blockedLevels: [4, 8, 16], allowedLevels: [1, 2] },
      { maxLevel: 'r', blockedLevels: [8, 16], allowedLevels: [1, 2, 4] },
      { maxLevel: 'x', blockedLevels: [16], allowedLevels: [1, 2, 4, 8] },
      { maxLevel: 'all', blockedLevels: [], allowedLevels: [1, 2, 4, 8, 16] },
    ]

    for (const { maxLevel, blockedLevels, allowedLevels } of levelTests) {
      it(`maxLevel=${maxLevel}: blocks ${blockedLevels.join(',')} in blur mode`, () => {
        setMode('blur', maxLevel)
        for (const level of blockedLevels) {
          expect(simulateFilter(level).isHidden).toBe(true)
        }
        for (const level of allowedLevels) {
          expect(simulateFilter(level).isHidden).toBe(false)
        }
      })

      it(`maxLevel=${maxLevel}: blocks ${blockedLevels.join(',')} in show mode`, () => {
        setMode('show', maxLevel)
        for (const level of blockedLevels) {
          expect(simulateFilter(level).isHidden).toBe(true)
        }
        for (const level of allowedLevels) {
          expect(simulateFilter(level).isHidden).toBe(false)
        }
      })
    }
  })

  // ---------------------------------------------------------------------------
  // Reveal state isolation (Fix A: reveal should not leak across items)
  // ---------------------------------------------------------------------------

  describe('reveal state isolation', () => {
    it('revealing one item should not affect another item query', () => {
      setMode('blur')
      // Item A revealed
      const itemA = simulateFilter(8, { isRevealed: true })
      expect(itemA.isBlurred).toBe(false)
      // Item B not revealed — must still be blurred
      const itemB = simulateFilter(4, { isRevealed: false })
      expect(itemB.isBlurred).toBe(true)
    })

    it('different nsfwLevel values produce independent results', () => {
      setMode('blur')
      expect(simulateFilter(8).isBlurred).toBe(true)
      expect(simulateFilter(1).isBlurred).toBe(false)
      expect(simulateFilter(16).isBlurred).toBe(true)
    })
  })

  // ---------------------------------------------------------------------------
  // Adjacent slide blur (Fix B: non-active slides should still blur)
  // ---------------------------------------------------------------------------

  describe('adjacent slide blur logic', () => {
    it('shouldBlurFn returns true for NSFW items regardless of reveal state', () => {
      setMode('blur')
      const state = useNsfwStore.getState()
      // shouldBlurFn is stateless — always returns based on mode + level
      expect(state.shouldBlur(8)).toBe(true)
      expect(state.shouldBlur(4)).toBe(true)
      expect(state.shouldBlur(1)).toBe(false)
    })

    it('shouldBlurFn is independent from isRevealed (store-level)', () => {
      setMode('blur')
      const state = useNsfwStore.getState()
      // Store method doesn't know about reveal state — that's the hook's job
      expect(state.shouldBlur(8)).toBe(true)
      // So adjacent slides can use shouldBlurFn directly for blur
    })
  })

  // ---------------------------------------------------------------------------
  // Index mapping: visible vs original
  // ---------------------------------------------------------------------------

  describe('visible filtering for collections', () => {
    it('shouldHide filters NSFW items in hide mode', () => {
      setMode('hide')
      const state = useNsfwStore.getState()
      const items = [
        { nsfw: false, level: 1 },
        { nsfw: true, level: 8 },
        { nsfw: false, level: 1 },
        { nsfw: true, level: 16 },
      ]
      const visible = items.filter((item) => !state.shouldHide(item.level))
      expect(visible).toHaveLength(2)
      expect(visible[0].level).toBe(1)
      expect(visible[1].level).toBe(1)
    })

    it('shouldHide filters items exceeding maxLevel', () => {
      setMode('blur', 'r') // bitmask 7
      const state = useNsfwStore.getState()
      const items = [
        { level: 1 },  // PG — visible
        { level: 2 },  // PG13 — visible
        { level: 4 },  // R — visible
        { level: 8 },  // X — hidden
        { level: 16 }, // XXX — hidden
      ]
      const visible = items.filter((item) => !state.shouldHide(item.level))
      expect(visible).toHaveLength(3)
      expect(visible.map((i) => i.level)).toEqual([1, 2, 4])
    })

    it('original index mapping after filtering', () => {
      setMode('blur', 'r')
      const state = useNsfwStore.getState()
      const items = [
        { id: 'a', level: 1 },
        { id: 'b', level: 8 },  // hidden
        { id: 'c', level: 4 },
        { id: 'd', level: 16 }, // hidden
        { id: 'e', level: 2 },
      ]
      const visible = items.filter((item) => !state.shouldHide(item.level))
      // visible = [a, c, e]
      expect(visible.map((i) => i.id)).toEqual(['a', 'c', 'e'])

      // Mapping visible[1] (c) back to original index
      const originalIdx = items.indexOf(visible[1])
      expect(originalIdx).toBe(2) // items[2] = c
    })
  })

  // ---------------------------------------------------------------------------
  // Round 1 review fixes: isNsfw consistency with normalizeLevel
  // ---------------------------------------------------------------------------

  describe('isNsfw consistency with normalizeLevel (round 1 fix)', () => {
    it('malformed level 0 treated as NSFW (fail-closed)', () => {
      setMode('show')
      const result = simulateFilter(0)
      // normalizeLevel(0) returns isNsfw: true — fail-closed for invalid input
      expect(result.isNsfw).toBe(true)
    })

    it('negative level treated as NSFW (fail-closed)', () => {
      setMode('show')
      const result = simulateFilter(-5)
      expect(result.isNsfw).toBe(true)
    })

    it('NaN treated as NSFW (fail-closed)', () => {
      setMode('show')
      const result = simulateFilter(NaN)
      expect(result.isNsfw).toBe(true)
    })

    it('level 1 (PG) is NOT nsfw', () => {
      setMode('show')
      expect(simulateFilter(1).isNsfw).toBe(false)
    })

    it('level 2 (PG-13) IS nsfw', () => {
      setMode('show')
      expect(simulateFilter(2).isNsfw).toBe(true)
    })

    it('boolean false is NOT nsfw', () => {
      setMode('show')
      expect(simulateFilter(false).isNsfw).toBe(false)
    })

    it('boolean true IS nsfw', () => {
      setMode('show')
      expect(simulateFilter(true).isNsfw).toBe(true)
    })

    it('showBadge uses consistent isNsfw for malformed input', () => {
      setMode('show')
      // Level 0 is malformed → isNsfw=true → badge should show in "show" mode
      const result = simulateFilter(0)
      expect(result.showBadge).toBe(true)
    })
  })

  // ---------------------------------------------------------------------------
  // Round 1 review fixes: currentIndex clamping simulation
  // ---------------------------------------------------------------------------

  describe('currentIndex clamping for filtered arrays (round 1 fix)', () => {
    it('clamp to last visible when items shrink', () => {
      setMode('blur', 'all')
      const items = [
        { nsfwLevel: 1 }, { nsfwLevel: 4 }, { nsfwLevel: 8 },
      ]
      const state = useNsfwStore.getState()
      let visible = items.filter((i) => !state.shouldHide(i.nsfwLevel))
      expect(visible).toHaveLength(3)

      // User is viewing index 2 (last item)
      let currentIndex = 2

      // Now change maxLevel to r (bitmask 7) — hides level 8
      setMode('blur', 'r')
      visible = useNsfwStore.getState().shouldHide
        ? items.filter((i) => !useNsfwStore.getState().shouldHide(i.nsfwLevel))
        : items
      expect(visible).toHaveLength(2)

      // Clamp: currentIndex should not exceed visible.length - 1
      if (currentIndex >= visible.length) currentIndex = visible.length - 1
      expect(currentIndex).toBe(1)
      expect(visible[currentIndex].nsfwLevel).toBe(4)
    })

    it('clamp handles all items hidden gracefully', () => {
      setMode('hide')
      const items = [
        { nsfwLevel: 4 }, { nsfwLevel: 8 },
      ]
      const visible = items.filter((i) => !useNsfwStore.getState().shouldHide(i.nsfwLevel))
      expect(visible).toHaveLength(0)
      // When all hidden, clamp should go to 0 (or trigger close)
      const clamped = Math.min(0, Math.max(0, visible.length - 1))
      expect(clamped).toBe(0)
    })
  })
})
