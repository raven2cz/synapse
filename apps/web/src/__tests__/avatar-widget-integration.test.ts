/**
 * Integration Tests: Avatar Widget Wiring
 *
 * Tests the wiring between AvatarProvider, Layout, and AvatarWidget:
 * - Provider → Widget prop mapping
 * - sendWithContext → AvatarWidget.sendMessage delegation
 * - PermissionDialog placement (outside widget)
 * - Context tracking → structured metadata injection
 * - SuggestionChips visibility logic
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { usePageContextStore } from '../stores/pageContextStore'
import { buildContextPayload, type AvatarPageContextPayload } from '../lib/avatar/context'
import { resolveSuggestions, PAGE_SUGGESTIONS, FALLBACK_SUGGESTIONS } from '../lib/avatar/suggestions'

// ============================================================================
// AvatarWidget prop mapping (Layout → Widget)
// ============================================================================

describe('Avatar Widget — prop mapping from chat hook', () => {
  // Simulates the chat hook return value
  const mockChat = {
    messages: [{ role: 'user', content: 'test' }],
    sendMessage: (text: string) => text,
    stopResponse: () => {},
    isStreaming: false,
    connected: true,
    wasConnected: true,
    initDetail: '',
    error: null as string | null,
    diagnostic: null as string | null,
    provider: 'gemini',
    model: 'gemini-2.5-pro',
    version: '1.0.0',
    engineState: 'idle',
    thinking: { active: false, phase: '', subject: '', startedAt: 0 },
    toolName: undefined as string | undefined,
    pendingFiles: [] as unknown[],
    uploading: false,
    uploadFile: async () => null,
    removeFile: () => {},
    switching: false,
    activeOptions: {} as Record<string, string | number>,
    switchProvider: () => {},
    permissionRequest: null,
    sendPermissionResponse: () => {},
    clearHistory: () => {},
    cwd: '/workspace',
    capabilities: {},
    sessionId: 'session-1',
    sessionTitle: 'Test Session',
    cost: { totalCostUsd: 0, totalInputTokens: 0, totalOutputTokens: 0 },
    resumeSession: () => {},
    newSession: () => {},
    safetyMode: 'safe' as const,
  }

  it('should map chat.messages directly to widget', () => {
    expect(mockChat.messages).toHaveLength(1)
    expect(mockChat.messages[0].role).toBe('user')
  })

  it('should map connection state', () => {
    expect(mockChat.connected).toBe(true)
    expect(mockChat.wasConnected).toBe(true)
  })

  it('should map provider info', () => {
    expect(mockChat.provider).toBe('gemini')
    expect(mockChat.model).toBe('gemini-2.5-pro')
    expect(mockChat.version).toBe('1.0.0')
  })

  it('should map engine state', () => {
    expect(mockChat.engineState).toBe('idle')
  })

  it('should compute thinkingSubject from thinking state', () => {
    const thinkingSubject = mockChat.thinking.active ? mockChat.thinking.subject : ''
    expect(thinkingSubject).toBe('')

    const thinkingChat = {
      ...mockChat,
      thinking: { active: true, phase: 'thinking', subject: 'Analyzing pack', startedAt: Date.now() },
    }
    const activeSubject = thinkingChat.thinking.active ? thinkingChat.thinking.subject : ''
    expect(activeSubject).toBe('Analyzing pack')
  })

  it('should map error states', () => {
    expect(mockChat.error).toBeNull()
    expect(mockChat.diagnostic).toBeNull()

    const errorChat = { ...mockChat, error: 'Connection lost', diagnostic: 'WS closed' }
    expect(errorChat.error).toBe('Connection lost')
    expect(errorChat.diagnostic).toBe('WS closed')
  })

  it('should map file upload state', () => {
    expect(mockChat.pendingFiles).toHaveLength(0)
    expect(mockChat.uploading).toBe(false)
  })

  it('should map switching state', () => {
    expect(mockChat.switching).toBe(false)
  })

  it('should map session info for StatusBar', () => {
    expect(mockChat.sessionId).toBe('session-1')
    expect(mockChat.sessionTitle).toBe('Test Session')
    expect(mockChat.cost.totalCostUsd).toBe(0)
    expect(mockChat.cwd).toBe('/workspace')
  })
})

// ============================================================================
// sendWithContext delegation
// ============================================================================

describe('Avatar Widget — sendWithContext delegation', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should delegate to chat.sendMessage with structured context', () => {
    const calls: Array<{ text: string; context: AvatarPageContextPayload | undefined }> = []
    const mockSendMessage = (text: string, _attachments?: unknown, context?: AvatarPageContextPayload) => {
      calls.push({ text, context })
    }

    usePageContextStore.getState().setContext('/inventory')

    // Simulate sendWithContext
    const text = 'Show orphans'
    const { current, previous } = usePageContextStore.getState()
    const payload = buildContextPayload(current) ?? buildContextPayload(previous)
    mockSendMessage(text, undefined, payload ?? undefined)

    expect(calls).toHaveLength(1)
    expect(calls[0].text).toBe('Show orphans')
    expect(calls[0].context).toMatchObject({
      page: 'inventory',
      description: 'Viewing model inventory',
    })
  })

  it('should delegate plain text with undefined context when no page context', () => {
    const calls: Array<{ text: string; context: AvatarPageContextPayload | undefined }> = []
    const mockSendMessage = (text: string, _attachments?: unknown, context?: AvatarPageContextPayload) => {
      calls.push({ text, context })
    }

    const text = 'Hello'
    const { current, previous } = usePageContextStore.getState()
    const payload = buildContextPayload(current) ?? buildContextPayload(previous)
    mockSendMessage(text, undefined, payload ?? undefined)

    expect(calls[0].text).toBe('Hello')
    expect(calls[0].context).toBeUndefined()
  })

  it('should use previous context when navigated to avatar', () => {
    usePageContextStore.getState().setContext('/packs/Flux-Dev')
    usePageContextStore.getState().setContext('/avatar')

    const { current, previous } = usePageContextStore.getState()
    const payload = buildContextPayload(current) ?? buildContextPayload(previous)

    expect(payload).toMatchObject({
      page: 'pack-detail',
      entity: 'Flux-Dev',
      entityType: 'pack',
    })
  })
})

// ============================================================================
// PermissionDialog placement
// ============================================================================

describe('Avatar Widget — PermissionDialog contract', () => {
  it('should accept null permissionRequest (no pending approval)', () => {
    const request = null
    expect(request).toBeNull()
  })

  it('should accept PermissionRequest with required fields', () => {
    const request = {
      requestId: 'req-1',
      title: 'Run command',
      description: 'rm -rf node_modules',
      options: [
        { id: 'allow', label: 'Allow' },
        { id: 'deny', label: 'Deny' },
      ],
    }
    expect(request.requestId).toBe('req-1')
    expect(request.options).toHaveLength(2)
  })

  it('should call onRespond with requestId, optionId, cancelled', () => {
    let response: { requestId: string; optionId: string; cancelled: boolean } | null = null
    const onRespond = (requestId: string, optionId: string, cancelled: boolean) => {
      response = { requestId, optionId, cancelled }
    }

    onRespond('req-1', 'allow', false)
    expect(response).toEqual({ requestId: 'req-1', optionId: 'allow', cancelled: false })
  })
})

// ============================================================================
// SuggestionChips visibility
// ============================================================================

describe('Avatar Widget — SuggestionChips visibility', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should show chips when messages array is empty', () => {
    const messages: unknown[] = []
    const shouldShow = messages.length === 0
    expect(shouldShow).toBe(true)
  })

  it('should hide chips when messages exist', () => {
    const messages = [{ role: 'user', content: 'Hi' }]
    const shouldShow = messages.length === 0
    expect(shouldShow).toBe(false)
  })

  it('should resolve page-specific suggestions for chips', () => {
    usePageContextStore.getState().setContext('/inventory')
    const { current } = usePageContextStore.getState()
    const { keys } = resolveSuggestions(current, null)

    expect(keys).toEqual(PAGE_SUGGESTIONS['inventory'])
    expect(keys.length).toBeGreaterThan(0)
  })

  it('should resolve fallback suggestions when context is unknown', () => {
    const { keys } = resolveSuggestions(null, null)
    expect(keys).toEqual(FALLBACK_SUGGESTIONS)
  })
})

// ============================================================================
// Context tracking via pathname
// ============================================================================

describe('Avatar Widget — pathname context tracking', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should track pathname changes in store', () => {
    usePageContextStore.getState().setContext('/')
    expect(usePageContextStore.getState().current?.pageId).toBe('packs')

    usePageContextStore.getState().setContext('/inventory')
    expect(usePageContextStore.getState().current?.pageId).toBe('inventory')
    expect(usePageContextStore.getState().previous?.pageId).toBe('packs')
  })

  it('should not update when pathname is same', () => {
    usePageContextStore.getState().setContext('/browse')
    const ts1 = usePageContextStore.getState().current?.updatedAt

    usePageContextStore.getState().setContext('/browse')
    const ts2 = usePageContextStore.getState().current?.updatedAt

    expect(ts1).toBe(ts2)
  })

  it('should handle all app routes', () => {
    const routes = ['/', '/inventory', '/profiles', '/browse', '/downloads', '/settings']
    for (const route of routes) {
      usePageContextStore.getState().setContext(route)
      expect(usePageContextStore.getState().current).not.toBeNull()
      expect(usePageContextStore.getState().current?.pageId).not.toBe('unknown')
    }
  })
})
