/**
 * Smoke / E2E Tests: Full Navigation Flow
 *
 * Simulates realistic user navigation sequences through the store
 * and validates the complete context pipeline at each step.
 * Tests the full lifecycle of page tracking as a user would experience it.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { usePageContextStore } from '../stores/pageContextStore'
import { buildContextPayload, formatContextForMessage } from '../lib/avatar/context'
import { resolveSuggestions, PAGE_SUGGESTIONS, FALLBACK_SUGGESTIONS } from '../lib/avatar/suggestions'

function navigate(pathname: string) {
  usePageContextStore.getState().setContext(pathname)
}

function getState() {
  return usePageContextStore.getState()
}

// ============================================================================
// Full Navigation Flow
// ============================================================================

describe('Navigation Flow Smoke Tests', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should handle typical user session: packs → pack → avatar → back', () => {
    // User starts on packs list
    navigate('/')
    expect(getState().current?.pageId).toBe('packs')
    expect(getState().previous).toBeNull()

    // User clicks a pack
    navigate('/packs/Anime-LoRA')
    expect(getState().current?.pageId).toBe('pack-detail')
    expect(getState().current?.params.packName).toBe('Anime-LoRA')
    expect(getState().previous?.pageId).toBe('packs')

    // User opens AI assistant
    navigate('/avatar')
    expect(getState().current?.pageId).toBe('avatar')
    expect(getState().previous?.pageId).toBe('pack-detail')
    expect(getState().previous?.params.packName).toBe('Anime-LoRA')

    // Suggestions should be pack-detail specific
    const { keys, params } = resolveSuggestions(getState().current, getState().previous)
    expect(keys).toEqual(PAGE_SUGGESTIONS['pack-detail'])
    expect(params.packName).toBe('Anime-LoRA')

    // Context payload should come from previous
    const payload = buildContextPayload(getState().previous)
    expect(payload!.entity).toBe('Anime-LoRA')
    expect(formatContextForMessage(payload)).toContain('Anime-LoRA')

    // User goes back to inventory
    navigate('/inventory')
    expect(getState().current?.pageId).toBe('inventory')
    // Previous should now be pack-detail (avatar was skipped since it's not context-bearing)
    expect(getState().previous?.pageId).toBe('pack-detail')
  })

  it('should handle browse → avatar → browse cycle', () => {
    navigate('/browse')
    navigate('/avatar')

    const { current, previous } = getState()
    const { keys } = resolveSuggestions(current, previous)
    expect(keys).toEqual(PAGE_SUGGESTIONS['browse'])

    // Go back to browse
    navigate('/browse')
    expect(getState().current?.pageId).toBe('browse')
  })

  it('should handle direct avatar navigation (no previous)', () => {
    navigate('/avatar')

    const { current, previous } = getState()
    expect(current?.pageId).toBe('avatar')
    expect(previous).toBeNull()

    // Should get fallback suggestions
    const { keys } = resolveSuggestions(current, previous)
    expect(keys).toEqual(FALLBACK_SUGGESTIONS)

    // Context should be null
    const payload = buildContextPayload(current)
    expect(payload).toBeNull()
  })

  it('should handle rapid navigation through multiple pages', () => {
    navigate('/')
    navigate('/inventory')
    navigate('/profiles')
    navigate('/browse')
    navigate('/settings')
    navigate('/downloads')

    expect(getState().current?.pageId).toBe('downloads')
    expect(getState().previous?.pageId).toBe('settings')
  })

  it('should handle pack-detail → different pack-detail with correct entity', () => {
    navigate('/packs/Flux-Dev')
    expect(getState().current?.params.packName).toBe('Flux-Dev')

    navigate('/packs/Juggernaut-XL')
    expect(getState().current?.params.packName).toBe('Juggernaut-XL')
    expect(getState().previous?.params.packName).toBe('Flux-Dev')

    // Context payload must reflect the CURRENT pack, not the previous one
    const payload = buildContextPayload(getState().current)
    expect(payload!.entity).toBe('Juggernaut-XL')
    expect(formatContextForMessage(payload)).toBe(
      '[Context: Viewing pack detail, pack: Juggernaut-XL]',
    )
  })

  it('should handle duplicate navigation (same page)', () => {
    navigate('/inventory')
    const first = getState().current

    navigate('/inventory')
    const second = getState().current

    // Should be the same reference (dedup)
    expect(second).toBe(first)
  })

  it('should handle unknown routes without losing previous context', () => {
    navigate('/inventory')
    navigate('/some/unknown/path')

    expect(getState().current?.pageId).toBe('unknown')
    // Previous should still be inventory
    expect(getState().previous?.pageId).toBe('inventory')

    // Going to avatar should still have inventory as previous
    navigate('/avatar')
    expect(getState().previous?.pageId).toBe('inventory')

    // Suggestions should be inventory-specific
    const { keys } = resolveSuggestions(getState().current, getState().previous)
    expect(keys).toEqual(PAGE_SUGGESTIONS['inventory'])
  })

  it('should handle settings page context for avatar', () => {
    navigate('/settings')
    navigate('/avatar')

    const { current, previous } = getState()
    const { keys } = resolveSuggestions(current, previous)
    expect(keys).toEqual(PAGE_SUGGESTIONS['settings'])

    const payload = buildContextPayload(previous)
    expect(payload!.page).toBe('settings')
    expect(payload!.description).toBe('Viewing settings')
  })
})

// ============================================================================
// Resilience Tests
// ============================================================================

describe('Resilience Smoke Tests', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should handle malformed pack URL gracefully', () => {
    navigate('/packs/%E0%A4')

    expect(getState().current?.pageId).toBe('pack-detail')
    // Should use raw segment as fallback
    expect(getState().current?.params.packName).toBe('%E0%A4')
  })

  it('should handle trailing slashes throughout navigation', () => {
    navigate('/inventory/')
    expect(getState().current?.pageId).toBe('inventory')

    navigate('/packs/test/')
    expect(getState().current?.pageId).toBe('pack-detail')
    expect(getState().current?.params.packName).toBe('test')

    navigate('/avatar')
    expect(getState().previous?.pageId).toBe('pack-detail')
  })

  it('should handle empty pack name URL', () => {
    navigate('/packs/')
    expect(getState().current?.pageId).toBe('packs')
    expect(getState().current?.params.packName).toBeUndefined()
  })

  it('should produce valid context through entire pipeline with special chars', () => {
    navigate('/packs/My%20Pack%20(v2)')

    const ctx = getState().current!
    const payload = buildContextPayload(ctx)
    const msg = formatContextForMessage(payload)

    expect(payload!.entity).toBe('My Pack (v2)')
    expect(msg).toBe('[Context: Viewing pack detail, pack: My Pack (v2)]')
  })
})
