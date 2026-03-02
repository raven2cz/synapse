/**
 * Tests for Suggestion Chips Logic
 *
 * Tests cover:
 * - Per-page suggestion key resolution (imported from real module)
 * - Fallback to generic suggestions
 * - packName interpolation for pack-detail
 * - Context selection (current vs previous for avatar page)
 */

import { describe, it, expect } from 'vitest'
import {
  resolveSuggestions,
  PAGE_SUGGESTIONS,
  FALLBACK_SUGGESTIONS,
} from '../lib/avatar/suggestions'
import type { PageContext } from '../stores/pageContextStore'

// ============================================================================
// resolveSuggestions — per-page suggestions
// ============================================================================

describe('resolveSuggestions', () => {
  describe('Per-page suggestions', () => {
    it('should return packs suggestions for packs page', () => {
      const ctx: PageContext = { pageId: 'packs', pathname: '/', params: {}, updatedAt: 0 }
      const { keys } = resolveSuggestions(ctx, null)
      expect(keys).toHaveLength(3)
      expect(keys).toEqual(PAGE_SUGGESTIONS['packs'])
    })

    it('should return inventory suggestions for inventory page', () => {
      const ctx: PageContext = { pageId: 'inventory', pathname: '/inventory', params: {}, updatedAt: 0 }
      const { keys } = resolveSuggestions(ctx, null)
      expect(keys).toHaveLength(3)
      expect(keys).toEqual(PAGE_SUGGESTIONS['inventory'])
    })

    it('should return browse suggestions for browse page', () => {
      const ctx: PageContext = { pageId: 'browse', pathname: '/browse', params: {}, updatedAt: 0 }
      const { keys } = resolveSuggestions(ctx, null)
      expect(keys).toHaveLength(3)
      expect(keys).toEqual(PAGE_SUGGESTIONS['browse'])
    })

    it('should return downloads suggestions (2 items)', () => {
      const ctx: PageContext = { pageId: 'downloads', pathname: '/downloads', params: {}, updatedAt: 0 }
      const { keys } = resolveSuggestions(ctx, null)
      expect(keys).toHaveLength(2)
      expect(keys).toEqual(PAGE_SUGGESTIONS['downloads'])
    })

    it('should return profiles suggestions (2 items)', () => {
      const ctx: PageContext = { pageId: 'profiles', pathname: '/profiles', params: {}, updatedAt: 0 }
      const { keys } = resolveSuggestions(ctx, null)
      expect(keys).toHaveLength(2)
      expect(keys).toEqual(PAGE_SUGGESTIONS['profiles'])
    })

    it('should return settings suggestions (2 items)', () => {
      const ctx: PageContext = { pageId: 'settings', pathname: '/settings', params: {}, updatedAt: 0 }
      const { keys } = resolveSuggestions(ctx, null)
      expect(keys).toHaveLength(2)
      expect(keys).toEqual(PAGE_SUGGESTIONS['settings'])
    })

    it('should return pack-detail suggestions with packName param', () => {
      const ctx: PageContext = {
        pageId: 'pack-detail',
        pathname: '/packs/Illustrious-XL',
        params: { packName: 'Illustrious-XL' },
        updatedAt: 0,
      }
      const { keys, params } = resolveSuggestions(ctx, null)
      expect(keys).toEqual(PAGE_SUGGESTIONS['pack-detail'])
      expect(params.packName).toBe('Illustrious-XL')
    })
  })

  describe('Fallback suggestions', () => {
    it('should fallback for null context', () => {
      const { keys } = resolveSuggestions(null, null)
      expect(keys).toEqual(FALLBACK_SUGGESTIONS)
    })

    it('should fallback for unknown page', () => {
      const ctx: PageContext = { pageId: 'unknown', pathname: '/xyz', params: {}, updatedAt: 0 }
      const { keys } = resolveSuggestions(ctx, null)
      expect(keys).toEqual(FALLBACK_SUGGESTIONS)
    })

    it('should fallback for avatar page with no previous', () => {
      const ctx: PageContext = { pageId: 'avatar', pathname: '/avatar', params: {}, updatedAt: 0 }
      const { keys } = resolveSuggestions(ctx, null)
      expect(keys).toEqual(FALLBACK_SUGGESTIONS)
    })
  })

  describe('Avatar page uses previous context', () => {
    it('should use previous page context when on avatar', () => {
      const current: PageContext = { pageId: 'avatar', pathname: '/avatar', params: {}, updatedAt: 2 }
      const previous: PageContext = { pageId: 'inventory', pathname: '/inventory', params: {}, updatedAt: 1 }
      const { keys } = resolveSuggestions(current, previous)
      expect(keys).toEqual(PAGE_SUGGESTIONS['inventory'])
    })

    it('should use previous pack-detail context with packName when on avatar', () => {
      const current: PageContext = { pageId: 'avatar', pathname: '/avatar', params: {}, updatedAt: 2 }
      const previous: PageContext = { pageId: 'pack-detail', pathname: '/packs/my-lora', params: { packName: 'my-lora' }, updatedAt: 1 }
      const { keys, params } = resolveSuggestions(current, previous)
      expect(keys).toEqual(PAGE_SUGGESTIONS['pack-detail'])
      expect(params.packName).toBe('my-lora')
    })
  })

  describe('Pack-detail packName params', () => {
    it('should include packName in params', () => {
      const ctx: PageContext = {
        pageId: 'pack-detail',
        pathname: '/packs/test',
        params: { packName: 'test' },
        updatedAt: 0,
      }
      const { params } = resolveSuggestions(ctx, null)
      expect(params).toEqual({ packName: 'test' })
    })

    it('should have empty params when packName is missing', () => {
      const ctx: PageContext = {
        pageId: 'pack-detail',
        pathname: '/packs/x',
        params: {},
        updatedAt: 0,
      }
      const { params } = resolveSuggestions(ctx, null)
      expect(params).toEqual({})
    })
  })
})
