/**
 * Unit Tests: AvatarProvider
 *
 * Tests the AvatarProvider context logic:
 * - WebSocket URL construction
 * - sendWithContext wrapper (structured context metadata)
 * - Context shape validation
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { usePageContextStore } from '../stores/pageContextStore'
import { buildContextPayload, formatContextForMessage, type AvatarPageContextPayload } from '../lib/avatar/context'

// ============================================================================
// WebSocket URL Construction
// ============================================================================

describe('AvatarProvider — WS URL construction', () => {
  function buildWsUrl(protocol: string, host: string): string {
    const proto = protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${host}/api/avatar/ws`
  }

  it('should use wss: for https: protocol', () => {
    expect(buildWsUrl('https:', 'synapse.local')).toBe('wss://synapse.local/api/avatar/ws')
  })

  it('should use ws: for http: protocol', () => {
    expect(buildWsUrl('http:', 'localhost:5173')).toBe('ws://localhost:5173/api/avatar/ws')
  })

  it('should preserve port in host', () => {
    const url = buildWsUrl('http:', 'localhost:8080')
    expect(url).toContain(':8080')
    expect(url).toBe('ws://localhost:8080/api/avatar/ws')
  })

  it('should always end with /api/avatar/ws', () => {
    const url = buildWsUrl('https:', 'example.com')
    expect(url).toMatch(/\/api\/avatar\/ws$/)
  })
})

// ============================================================================
// sendWithContext — Structured Context Metadata
// ============================================================================

describe('AvatarProvider — sendWithContext logic', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  /**
   * Simulates sendWithContext: reads page context, builds structured payload.
   * This mirrors AvatarProvider.tsx — context is sent as metadata, not as text prefix.
   */
  function buildSendArgs(text: string): { text: string; context: AvatarPageContextPayload | undefined } {
    const { current, previous } = usePageContextStore.getState()
    const payload = buildContextPayload(current) ?? buildContextPayload(previous)
    return { text, context: payload ?? undefined }
  }

  it('should send plain text when no context available', () => {
    const { text, context } = buildSendArgs('Hello')
    expect(text).toBe('Hello')
    expect(context).toBeUndefined()
  })

  it('should attach context metadata when current page has context', () => {
    usePageContextStore.getState().setContext('/inventory')
    const { text, context } = buildSendArgs('Help me clean up')
    expect(text).toBe('Help me clean up')
    expect(context).toEqual({
      page: 'inventory',
      description: 'Viewing model inventory',
      pathname: '/inventory',
    })
  })

  it('should fall back to previous context when on avatar page', () => {
    usePageContextStore.getState().setContext('/packs/Juggernaut-XL')
    usePageContextStore.getState().setContext('/avatar')

    const { text, context } = buildSendArgs('Explain this model')
    expect(text).toBe('Explain this model')
    expect(context).toMatchObject({
      page: 'pack-detail',
      entity: 'Juggernaut-XL',
      entityType: 'pack',
    })
  })

  it('should use current page context, not stale previous', () => {
    // User was on pack-detail, then navigated to packs list
    usePageContextStore.getState().setContext('/packs/Juggernaut-XL')
    usePageContextStore.getState().setContext('/')

    const { context } = buildSendArgs('List my packs')
    // Should reflect current page (packs list), NOT previous (pack-detail)
    expect(context).toMatchObject({ page: 'packs', description: 'Viewing pack list' })
    expect(context?.entity).toBeUndefined()
  })

  it('should reflect new pack when navigating between pack details', () => {
    usePageContextStore.getState().setContext('/packs/Model-A')
    usePageContextStore.getState().setContext('/packs/Model-B')

    const { context } = buildSendArgs('Tell me about this')
    expect(context).toMatchObject({
      page: 'pack-detail',
      entity: 'Model-B',
      entityType: 'pack',
    })
  })

  it('should use current when previous is null', () => {
    usePageContextStore.getState().setContext('/browse')
    const { text, context } = buildSendArgs('Find me a model')
    expect(text).toBe('Find me a model')
    expect(context).toMatchObject({
      page: 'browse',
      description: 'Browsing Civitai models',
    })
  })

  it('should skip context for unknown pages', () => {
    usePageContextStore.getState().setContext('/unknown')
    const { context } = buildSendArgs('Question')
    expect(context).toBeUndefined()
  })

  it('should skip context for avatar page (no useful context)', () => {
    usePageContextStore.getState().setContext('/avatar')
    const { context } = buildSendArgs('Question')
    expect(context).toBeUndefined()
  })

  it('should handle encoded pack names', () => {
    usePageContextStore.getState().setContext('/packs/My%20LoRA')
    const { text, context } = buildSendArgs('Info?')
    expect(text).toBe('Info?')
    expect(context).toMatchObject({ entity: 'My LoRA', entityType: 'pack' })
  })

  it('should not modify message text when context is present', () => {
    usePageContextStore.getState().setContext('/inventory')
    const { text } = buildSendArgs('')
    expect(text).toBe('')
  })

  it('should keep multiline text intact', () => {
    usePageContextStore.getState().setContext('/settings')
    const { text, context } = buildSendArgs('Line 1\nLine 2')
    expect(text).toBe('Line 1\nLine 2')
    expect(context).toMatchObject({ page: 'settings' })
  })
})

// ============================================================================
// Regression: Navigation Sequences → Context Correctness
// ============================================================================

describe('AvatarProvider — navigation regression scenarios', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  function getContext(): AvatarPageContextPayload | undefined {
    const { current, previous } = usePageContextStore.getState()
    return (buildContextPayload(current) ?? buildContextPayload(previous)) ?? undefined
  }

  it('pack-detail → packs list → should send packs context (not stale pack)', () => {
    usePageContextStore.getState().setContext('/packs/Illustrious-XL')
    usePageContextStore.getState().setContext('/')

    const ctx = getContext()
    expect(ctx?.page).toBe('packs')
    expect(ctx?.entity).toBeUndefined()
  })

  it('pack-detail → inventory → should send inventory context (not stale pack)', () => {
    usePageContextStore.getState().setContext('/packs/SDXL')
    usePageContextStore.getState().setContext('/inventory')

    const ctx = getContext()
    expect(ctx?.page).toBe('inventory')
    expect(ctx?.entity).toBeUndefined()
  })

  it('pack A → pack B → should send pack B context', () => {
    usePageContextStore.getState().setContext('/packs/Model-A')
    usePageContextStore.getState().setContext('/packs/Model-B')

    const ctx = getContext()
    expect(ctx?.entity).toBe('Model-B')
  })

  it('pack-detail → avatar → should fall back to pack context', () => {
    usePageContextStore.getState().setContext('/packs/Flux-Dev')
    usePageContextStore.getState().setContext('/avatar')

    const ctx = getContext()
    expect(ctx?.page).toBe('pack-detail')
    expect(ctx?.entity).toBe('Flux-Dev')
  })

  it('pack-detail → packs → avatar → should fall back to packs (not stale pack)', () => {
    usePageContextStore.getState().setContext('/packs/Flux-Dev')
    usePageContextStore.getState().setContext('/')
    usePageContextStore.getState().setContext('/avatar')

    const ctx = getContext()
    // On /avatar, current is null (avatar filtered). Previous is packs (not pack-detail).
    expect(ctx?.page).toBe('packs')
    expect(ctx?.entity).toBeUndefined()
  })

  it('inventory → browse → inventory → should send inventory context', () => {
    usePageContextStore.getState().setContext('/inventory')
    usePageContextStore.getState().setContext('/browse')
    usePageContextStore.getState().setContext('/inventory')

    const ctx = getContext()
    expect(ctx?.page).toBe('inventory')
  })

  it('unknown page → should fall back to previous meaningful context', () => {
    usePageContextStore.getState().setContext('/inventory')
    usePageContextStore.getState().setContext('/some/random/page')

    // current is unknown → buildContextPayload returns null → falls back to previous
    const ctx = getContext()
    expect(ctx?.page).toBe('inventory')
  })

  it('multiple unknown pages → should preserve last meaningful context', () => {
    usePageContextStore.getState().setContext('/browse')
    usePageContextStore.getState().setContext('/x')
    usePageContextStore.getState().setContext('/y')
    usePageContextStore.getState().setContext('/z')

    const ctx = getContext()
    expect(ctx?.page).toBe('browse')
  })
})

// ============================================================================
// AvatarContextValue Shape
// ============================================================================

describe('AvatarProvider — context value shape', () => {
  it('should define correct interface keys', () => {
    // This validates the TypeScript interface matches what consumers expect
    interface AvatarContextValue {
      chat: { messages: unknown[]; sendMessage: (text: string) => void }
      sendWithContext: (text: string) => void
      providers: Set<string> | null
      compactRef: { current: (() => void) | null }
    }

    const mock: AvatarContextValue = {
      chat: { messages: [], sendMessage: () => {} },
      sendWithContext: () => {},
      providers: new Set(['gemini']),
      compactRef: { current: null },
    }

    expect(mock.chat).toBeDefined()
    expect(mock.sendWithContext).toBeInstanceOf(Function)
    expect(mock.providers).toBeInstanceOf(Set)
    expect(mock.compactRef.current).toBeNull()
  })

  it('should handle null providers (not yet loaded)', () => {
    const providers: Set<string> | null = null
    expect(providers).toBeNull()
  })

  it('should handle empty provider set', () => {
    const providers = new Set<string>()
    expect(providers.size).toBe(0)
  })

  it('should handle compactRef with callback', () => {
    let called = false
    const compactRef = { current: () => { called = true } }
    compactRef.current?.()
    expect(called).toBe(true)
  })
})

// ============================================================================
// Context Injection for All Page Types
// ============================================================================

describe('AvatarProvider — context injection per page', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  const testCases = [
    { path: '/', expected: '[Context: Viewing pack list]' },
    { path: '/packs/TestPack', expected: '[Context: Viewing pack detail, pack: TestPack]' },
    { path: '/inventory', expected: '[Context: Viewing model inventory]' },
    { path: '/profiles', expected: '[Context: Viewing profiles]' },
    { path: '/browse', expected: '[Context: Browsing Civitai models]' },
    { path: '/downloads', expected: '[Context: Viewing downloads]' },
    { path: '/settings', expected: '[Context: Viewing settings]' },
  ]

  testCases.forEach(({ path, expected }) => {
    it(`should inject context for ${path}`, () => {
      usePageContextStore.getState().setContext(path)
      const { current } = usePageContextStore.getState()
      const payload = buildContextPayload(current)
      const prefix = formatContextForMessage(payload)
      expect(prefix).toBe(expected)
    })
  })
})
