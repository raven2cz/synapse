/**
 * Integration Tests: Page Context → Avatar Context → Suggestions
 *
 * Tests the full wiring between:
 * - pageContextStore (route tracking)
 * - context.ts (payload builder)
 * - suggestions.ts (suggestion resolution)
 *
 * All three modules work together as a pipeline:
 *   URL → resolveContext → PageContext → buildContextPayload → AvatarPageContextPayload
 *   URL → resolveContext → PageContext → resolveSuggestions → keys + params
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { resolveContext, usePageContextStore } from '../stores/pageContextStore'
import { buildContextPayload, formatContextForMessage } from '../lib/avatar/context'
import { resolveSuggestions, PAGE_SUGGESTIONS, FALLBACK_SUGGESTIONS } from '../lib/avatar/suggestions'

// ============================================================================
// Pipeline: resolveContext → buildContextPayload → formatContextForMessage
// ============================================================================

describe('Context Pipeline Integration', () => {
  it('should produce formatted context from raw URL', () => {
    const ctx = resolveContext('/inventory')
    const payload = buildContextPayload(ctx)
    const msg = formatContextForMessage(payload)

    expect(msg).toBe('[Context: Viewing model inventory]')
  })

  it('should produce pack entity context from pack URL', () => {
    const ctx = resolveContext('/packs/Illustrious-XL')
    const payload = buildContextPayload(ctx)
    const msg = formatContextForMessage(payload)

    expect(msg).toBe('[Context: Viewing pack detail, pack: Illustrious-XL]')
  })

  it('should produce null payload for unknown URL', () => {
    const ctx = resolveContext('/unknown/route')
    const payload = buildContextPayload(ctx)

    expect(payload).toBeNull()
    expect(formatContextForMessage(payload)).toBe('')
  })

  it('should produce null payload for avatar URL', () => {
    const ctx = resolveContext('/avatar')
    const payload = buildContextPayload(ctx)

    expect(payload).toBeNull()
  })

  it('should handle encoded pack names through full pipeline', () => {
    const ctx = resolveContext('/packs/My%20LoRA%20Pack')
    const payload = buildContextPayload(ctx)

    expect(payload!.entity).toBe('My LoRA Pack')
    expect(formatContextForMessage(payload)).toBe(
      '[Context: Viewing pack detail, pack: My LoRA Pack]',
    )
  })
})

// ============================================================================
// Pipeline: resolveContext → resolveSuggestions
// ============================================================================

describe('Suggestions Pipeline Integration', () => {
  it('should resolve inventory suggestions from raw URL', () => {
    const ctx = resolveContext('/inventory')
    const { keys } = resolveSuggestions(ctx, null)

    expect(keys).toEqual(PAGE_SUGGESTIONS['inventory'])
  })

  it('should resolve pack-detail suggestions with packName from URL', () => {
    const ctx = resolveContext('/packs/Test-Pack')
    const { keys, params } = resolveSuggestions(ctx, null)

    expect(keys).toEqual(PAGE_SUGGESTIONS['pack-detail'])
    expect(params.packName).toBe('Test-Pack')
  })

  it('should fallback for unknown URL', () => {
    const ctx = resolveContext('/random')
    const { keys } = resolveSuggestions(ctx, null)

    expect(keys).toEqual(FALLBACK_SUGGESTIONS)
  })

  it('should resolve suggestions from trailing-slash URL', () => {
    const ctx = resolveContext('/browse/')
    const { keys } = resolveSuggestions(ctx, null)

    expect(keys).toEqual(PAGE_SUGGESTIONS['browse'])
  })
})

// ============================================================================
// Store → Context → Suggestions full wiring
// ============================================================================

describe('Store-Context-Suggestions Wiring', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should wire store state to context payload', () => {
    usePageContextStore.getState().setContext('/inventory')
    const { current } = usePageContextStore.getState()
    const payload = buildContextPayload(current)

    expect(payload!.page).toBe('inventory')
    expect(payload!.description).toBe('Viewing model inventory')
  })

  it('should wire store previous to avatar context', () => {
    usePageContextStore.getState().setContext('/packs/my-lora')
    usePageContextStore.getState().setContext('/avatar')

    const { current, previous } = usePageContextStore.getState()

    // Current is avatar → should be filtered
    expect(buildContextPayload(current)).toBeNull()

    // Previous is pack-detail → should produce payload
    const payload = buildContextPayload(previous)
    expect(payload!.page).toBe('pack-detail')
    expect(payload!.entity).toBe('my-lora')
  })

  it('should wire store to suggestions for avatar page', () => {
    usePageContextStore.getState().setContext('/inventory')
    usePageContextStore.getState().setContext('/avatar')

    const { current, previous } = usePageContextStore.getState()
    const { keys } = resolveSuggestions(current, previous)

    expect(keys).toEqual(PAGE_SUGGESTIONS['inventory'])
  })

  it('should wire store to suggestions with pack params', () => {
    usePageContextStore.getState().setContext('/packs/Pony-XL')
    usePageContextStore.getState().setContext('/avatar')

    const { current, previous } = usePageContextStore.getState()
    const { keys, params } = resolveSuggestions(current, previous)

    expect(keys).toEqual(PAGE_SUGGESTIONS['pack-detail'])
    expect(params.packName).toBe('Pony-XL')
  })

  it('should fall back to generic when no previous context', () => {
    usePageContextStore.getState().setContext('/avatar')

    const { current, previous } = usePageContextStore.getState()
    const { keys } = resolveSuggestions(current, previous)

    expect(keys).toEqual(FALLBACK_SUGGESTIONS)
  })
})
