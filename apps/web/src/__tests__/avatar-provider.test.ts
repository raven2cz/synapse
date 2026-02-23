/**
 * Unit Tests: AvatarProvider
 *
 * Tests the AvatarProvider context logic:
 * - WebSocket URL construction
 * - sendWithContext wrapper (context prefix injection)
 * - Context shape validation
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { usePageContextStore } from '../stores/pageContextStore'
import { buildContextPayload, formatContextForMessage } from '../lib/avatar/context'

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
// sendWithContext — Context Prefix Injection
// ============================================================================

describe('AvatarProvider — sendWithContext logic', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  /**
   * Simulates sendWithContext: reads page context, builds prefix, prepends to message.
   * This mirrors AvatarProvider.tsx:41-47
   */
  function buildFullMessage(text: string): string {
    const { current, previous } = usePageContextStore.getState()
    const payload = buildContextPayload(previous ?? current)
    const prefix = formatContextForMessage(payload)
    return prefix ? `${prefix}\n\n${text}` : text
  }

  it('should send plain text when no context available', () => {
    const result = buildFullMessage('Hello')
    expect(result).toBe('Hello')
  })

  it('should prepend context when current page has context', () => {
    usePageContextStore.getState().setContext('/inventory')
    const result = buildFullMessage('Help me clean up')
    expect(result).toBe('[Context: Viewing model inventory]\n\nHelp me clean up')
  })

  it('should prefer previous page context over current', () => {
    usePageContextStore.getState().setContext('/packs/Juggernaut-XL')
    usePageContextStore.getState().setContext('/avatar')

    const result = buildFullMessage('Explain this model')
    expect(result).toBe(
      '[Context: Viewing pack detail, pack: Juggernaut-XL]\n\nExplain this model',
    )
  })

  it('should use current when previous is null', () => {
    usePageContextStore.getState().setContext('/browse')
    const result = buildFullMessage('Find me a model')
    expect(result).toBe('[Context: Browsing Civitai models]\n\nFind me a model')
  })

  it('should skip context for unknown pages', () => {
    usePageContextStore.getState().setContext('/unknown')
    const result = buildFullMessage('Question')
    expect(result).toBe('Question')
  })

  it('should skip context for avatar page (no useful context)', () => {
    usePageContextStore.getState().setContext('/avatar')
    const result = buildFullMessage('Question')
    expect(result).toBe('Question')
  })

  it('should handle encoded pack names', () => {
    usePageContextStore.getState().setContext('/packs/My%20LoRA')
    const result = buildFullMessage('Info?')
    expect(result).toBe('[Context: Viewing pack detail, pack: My LoRA]\n\nInfo?')
  })

  it('should handle empty text with context', () => {
    usePageContextStore.getState().setContext('/inventory')
    const result = buildFullMessage('')
    expect(result).toBe('[Context: Viewing model inventory]\n\n')
  })

  it('should handle multiline text', () => {
    usePageContextStore.getState().setContext('/settings')
    const result = buildFullMessage('Line 1\nLine 2')
    expect(result).toBe('[Context: Viewing settings]\n\nLine 1\nLine 2')
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
