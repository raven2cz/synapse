/**
 * Tests for Page Context Store
 *
 * Tests cover:
 * - resolveContext URL → PageId mapping
 * - Parameter extraction (packName)
 * - Trailing slash normalization
 * - Malformed URI handling
 * - setContext deduplication
 * - Previous page tracking (non-avatar, context-bearing only)
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { resolveContext, usePageContextStore } from '../stores/pageContextStore'

// ============================================================================
// resolveContext — URL → PageId mapping
// ============================================================================

describe('resolveContext', () => {
  it('should resolve "/" to packs', () => {
    const ctx = resolveContext('/')
    expect(ctx.pageId).toBe('packs')
    expect(ctx.pathname).toBe('/')
  })

  it('should resolve "/packs" to packs', () => {
    const ctx = resolveContext('/packs')
    expect(ctx.pageId).toBe('packs')
  })

  it('should resolve "/packs/my-lora" to pack-detail with packName', () => {
    const ctx = resolveContext('/packs/my-lora')
    expect(ctx.pageId).toBe('pack-detail')
    expect(ctx.params.packName).toBe('my-lora')
  })

  it('should decode URI-encoded packName', () => {
    const ctx = resolveContext('/packs/My%20Great%20Pack')
    expect(ctx.pageId).toBe('pack-detail')
    expect(ctx.params.packName).toBe('My Great Pack')
  })

  it('should resolve "/inventory" to inventory', () => {
    expect(resolveContext('/inventory').pageId).toBe('inventory')
  })

  it('should resolve "/profiles" to profiles', () => {
    expect(resolveContext('/profiles').pageId).toBe('profiles')
  })

  it('should resolve "/downloads" to downloads', () => {
    expect(resolveContext('/downloads').pageId).toBe('downloads')
  })

  it('should resolve "/browse" to browse', () => {
    expect(resolveContext('/browse').pageId).toBe('browse')
  })

  it('should resolve "/avatar" to avatar', () => {
    expect(resolveContext('/avatar').pageId).toBe('avatar')
  })

  it('should resolve "/settings" to settings', () => {
    expect(resolveContext('/settings').pageId).toBe('settings')
  })

  it('should resolve unknown paths to unknown', () => {
    expect(resolveContext('/some/random/path').pageId).toBe('unknown')
  })

  it('should always include updatedAt timestamp', () => {
    const before = Date.now()
    const ctx = resolveContext('/inventory')
    expect(ctx.updatedAt).toBeGreaterThanOrEqual(before)
    expect(ctx.updatedAt).toBeLessThanOrEqual(Date.now())
  })

  it('should have empty params for non-parameterized routes', () => {
    const ctx = resolveContext('/browse')
    expect(ctx.params).toEqual({})
  })

  // ── Trailing slash normalization ──────────────────────────────

  it('should normalize trailing slash on /inventory/', () => {
    expect(resolveContext('/inventory/').pageId).toBe('inventory')
  })

  it('should normalize trailing slash on /browse/', () => {
    expect(resolveContext('/browse/').pageId).toBe('browse')
  })

  it('should normalize trailing slash on /settings/', () => {
    expect(resolveContext('/settings/').pageId).toBe('settings')
  })

  it('should resolve "/packs/" (trailing slash, no name) as packs', () => {
    const ctx = resolveContext('/packs/')
    expect(ctx.pageId).toBe('packs')
    expect(ctx.params.packName).toBeUndefined()
  })

  it('should resolve "/packs/my-lora/" (trailing slash) as pack-detail', () => {
    const ctx = resolveContext('/packs/my-lora/')
    expect(ctx.pageId).toBe('pack-detail')
    expect(ctx.params.packName).toBe('my-lora')
  })

  // ── Malformed URI encoding ────────────────────────────────────

  it('should not throw on malformed URI encoding and use raw segment', () => {
    // %E0%A4 is incomplete UTF-8 — decodeURIComponent would throw
    const ctx = resolveContext('/packs/%E0%A4')
    expect(ctx.pageId).toBe('pack-detail')
    expect(ctx.params.packName).toBe('%E0%A4')
  })

  it('should handle valid encoding normally', () => {
    const ctx = resolveContext('/packs/%D0%9C%D0%BE%D0%B4%D0%B5%D0%BB%D1%8C')
    expect(ctx.pageId).toBe('pack-detail')
    expect(ctx.params.packName).toBe('Модель')
  })
})

// ============================================================================
// usePageContextStore — setContext + state tracking
// ============================================================================

describe('usePageContextStore', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should start with null current and previous', () => {
    const { current, previous } = usePageContextStore.getState()
    expect(current).toBeNull()
    expect(previous).toBeNull()
  })

  it('should set current context on setContext', () => {
    usePageContextStore.getState().setContext('/inventory')
    const { current } = usePageContextStore.getState()
    expect(current?.pageId).toBe('inventory')
    expect(current?.pathname).toBe('/inventory')
  })

  it('should keep previous null after first navigation', () => {
    usePageContextStore.getState().setContext('/inventory')
    const { previous } = usePageContextStore.getState()
    expect(previous).toBeNull()
  })

  it('should deduplicate same pathname', () => {
    usePageContextStore.getState().setContext('/inventory')
    const first = usePageContextStore.getState().current

    usePageContextStore.getState().setContext('/inventory')
    const second = usePageContextStore.getState().current

    expect(second).toBe(first)
  })

  it('should track previous non-avatar page', () => {
    usePageContextStore.getState().setContext('/inventory')
    usePageContextStore.getState().setContext('/avatar')

    const { current, previous } = usePageContextStore.getState()
    expect(current?.pageId).toBe('avatar')
    expect(previous?.pageId).toBe('inventory')
  })

  it('should NOT overwrite previous when navigating avatar → avatar (dedup)', () => {
    usePageContextStore.getState().setContext('/packs/my-lora')
    usePageContextStore.getState().setContext('/avatar')

    const { previous } = usePageContextStore.getState()
    expect(previous?.pageId).toBe('pack-detail')
  })

  it('should update previous when navigating between non-avatar pages', () => {
    usePageContextStore.getState().setContext('/inventory')
    usePageContextStore.getState().setContext('/browse')

    const { current, previous } = usePageContextStore.getState()
    expect(current?.pageId).toBe('browse')
    expect(previous?.pageId).toBe('inventory')
  })

  it('should preserve previous when going from non-avatar to avatar', () => {
    usePageContextStore.getState().setContext('/')
    usePageContextStore.getState().setContext('/packs/test-pack')
    usePageContextStore.getState().setContext('/avatar')

    const { previous } = usePageContextStore.getState()
    expect(previous?.pageId).toBe('pack-detail')
    expect(previous?.params.packName).toBe('test-pack')
  })

  it('should NOT overwrite previous with avatar page when leaving avatar', () => {
    usePageContextStore.getState().setContext('/inventory')
    usePageContextStore.getState().setContext('/avatar')
    usePageContextStore.getState().setContext('/browse')

    const { current, previous } = usePageContextStore.getState()
    expect(current?.pageId).toBe('browse')
    // Avatar is not context-bearing, so previous stays as inventory
    expect(previous?.pageId).toBe('inventory')
  })

  it('should NOT overwrite previous with unknown route', () => {
    usePageContextStore.getState().setContext('/inventory')
    usePageContextStore.getState().setContext('/some/random/path')

    const { current, previous } = usePageContextStore.getState()
    expect(current?.pageId).toBe('unknown')
    // Unknown is not context-bearing, so previous stays as inventory
    expect(previous?.pageId).toBe('inventory')
  })

  it('should chain multiple context-bearing navigations correctly', () => {
    usePageContextStore.getState().setContext('/inventory')
    usePageContextStore.getState().setContext('/browse')
    usePageContextStore.getState().setContext('/settings')

    const { current, previous } = usePageContextStore.getState()
    expect(current?.pageId).toBe('settings')
    expect(previous?.pageId).toBe('browse')
  })
})
