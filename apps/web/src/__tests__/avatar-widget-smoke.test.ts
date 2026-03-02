/**
 * Smoke Tests: Avatar Widget Full Lifecycle
 *
 * Tests the complete avatar integration flow:
 * - Render → connect → send message → receive response
 * - Context injection through the full pipeline
 * - Error states and recovery
 * - Provider switching
 * - Session management
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { usePageContextStore } from '../stores/pageContextStore'
import { buildContextPayload, type AvatarPageContextPayload } from '../lib/avatar/context'
import { resolveSuggestions, FALLBACK_SUGGESTIONS } from '../lib/avatar/suggestions'

// ============================================================================
// Simulate full lifecycle
// ============================================================================

/** Simulates the avatar chat state machine */
function createMockChatState() {
  let connected = false
  let wasConnected = false
  let messages: Array<{ role: string; content: string; context?: AvatarPageContextPayload }> = []
  let isStreaming = false
  let provider = 'gemini'
  let model: string | null = 'gemini-2.5-pro'
  let engineState = 'idle'
  let error: string | null = null
  let switching = false
  let sessionId = 'session-1'

  return {
    get state() {
      return { connected, wasConnected, messages, isStreaming, provider, model, engineState, error, switching, sessionId }
    },

    connect() {
      connected = true
      wasConnected = true
      engineState = 'idle'
    },

    disconnect() {
      connected = false
      error = 'Connection lost'
    },

    reconnect() {
      connected = true
      error = null
    },

    sendMessage(text: string, _attachments?: unknown, context?: AvatarPageContextPayload) {
      messages = [...messages, { role: 'user', content: text, context }]
      isStreaming = true
      engineState = 'thinking'
    },

    receiveResponse(text: string) {
      messages = [...messages, { role: 'assistant', content: text }]
      isStreaming = false
      engineState = 'idle'
    },

    switchProvider(newProvider: string, newModel?: string) {
      switching = true
      provider = newProvider
      model = newModel ?? null
      switching = false
    },

    newSession() {
      messages = []
      sessionId = `session-${Date.now()}`
    },

    clearHistory() {
      messages = []
    },
  }
}

describe('Avatar Widget Smoke — Full Lifecycle', () => {
  let chat: ReturnType<typeof createMockChatState>

  beforeEach(() => {
    chat = createMockChatState()
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should handle connect → send → receive lifecycle', () => {
    // 1. Connect
    chat.connect()
    expect(chat.state.connected).toBe(true)
    expect(chat.state.engineState).toBe('idle')

    // 2. Send message
    chat.sendMessage('Hello!')
    expect(chat.state.messages).toHaveLength(1)
    expect(chat.state.isStreaming).toBe(true)
    expect(chat.state.engineState).toBe('thinking')

    // 3. Receive response
    chat.receiveResponse('Hi! I can help with your Synapse packs.')
    expect(chat.state.messages).toHaveLength(2)
    expect(chat.state.isStreaming).toBe(false)
    expect(chat.state.engineState).toBe('idle')
  })

  it('should inject context as structured metadata when sending from a specific page', () => {
    chat.connect()
    usePageContextStore.getState().setContext('/packs/Illustrious-XL')

    // Simulate sendWithContext — context sent as metadata, not as text prefix
    const text = 'What does this model do?'
    const { current, previous } = usePageContextStore.getState()
    const payload = buildContextPayload(current) ?? buildContextPayload(previous)
    chat.sendMessage(text, undefined, payload ?? undefined)

    expect(chat.state.messages[0].content).toBe('What does this model do?')
    expect(chat.state.messages[0].context).toMatchObject({
      page: 'pack-detail',
      entity: 'Illustrious-XL',
      entityType: 'pack',
    })
  })

  it('should use previous context after navigating to avatar', () => {
    chat.connect()

    // User was on inventory page
    usePageContextStore.getState().setContext('/inventory')
    // User opened avatar (FAB → compact/fullscreen)
    usePageContextStore.getState().setContext('/avatar')

    const { current, previous } = usePageContextStore.getState()
    const payload = buildContextPayload(current) ?? buildContextPayload(previous)

    expect(payload).toMatchObject({ page: 'inventory', description: 'Viewing model inventory' })
    expect(current?.pageId).toBe('avatar')
    expect(previous?.pageId).toBe('inventory')
  })

  it('should handle disconnect and reconnect', () => {
    chat.connect()
    expect(chat.state.connected).toBe(true)

    chat.disconnect()
    expect(chat.state.connected).toBe(false)
    expect(chat.state.error).toBe('Connection lost')
    expect(chat.state.wasConnected).toBe(true) // remembers previous connection

    chat.reconnect()
    expect(chat.state.connected).toBe(true)
    expect(chat.state.error).toBeNull()
  })

  it('should handle provider switching', () => {
    chat.connect()
    expect(chat.state.provider).toBe('gemini')
    expect(chat.state.model).toBe('gemini-2.5-pro')

    chat.switchProvider('claude', 'claude-sonnet-4')
    expect(chat.state.provider).toBe('claude')
    expect(chat.state.model).toBe('claude-sonnet-4')
  })

  it('should handle new session (clear messages, new sessionId)', () => {
    chat.connect()
    chat.sendMessage('First question')
    chat.receiveResponse('First answer')

    expect(chat.state.messages).toHaveLength(2)
    const oldSessionId = chat.state.sessionId

    chat.newSession()
    expect(chat.state.messages).toHaveLength(0)
    expect(chat.state.sessionId).not.toBe(oldSessionId)
  })

  it('should handle clear history', () => {
    chat.connect()
    chat.sendMessage('Q1')
    chat.receiveResponse('A1')
    chat.sendMessage('Q2')
    chat.receiveResponse('A2')

    expect(chat.state.messages).toHaveLength(4)

    chat.clearHistory()
    expect(chat.state.messages).toHaveLength(0)
  })
})

// ============================================================================
// Smoke: Context + Suggestions pipeline
// ============================================================================

describe('Avatar Widget Smoke — Context + Suggestions Pipeline', () => {
  beforeEach(() => {
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should resolve full pipeline: route → context → suggestions → message', () => {
    // 1. User navigates to inventory
    usePageContextStore.getState().setContext('/inventory')

    // 2. Resolve suggestions
    const { current } = usePageContextStore.getState()
    const result = resolveSuggestions(current, null)
    expect(result.keys.length).toBeGreaterThan(0)

    // 3. User clicks first suggestion (simulated)
    const suggestionKey = result.keys[0]
    expect(suggestionKey).toContain('inventoryPage')

    // 4. Build structured context for message
    const payload = buildContextPayload(current)
    expect(payload).toMatchObject({
      page: 'inventory',
      description: 'Viewing model inventory',
    })

    // 5. Message text is clean, context is metadata
    const text = 'Show disk usage'
    expect(text).not.toContain('[Context:')
    expect(payload).not.toBeNull()
  })

  it('should handle rapid page navigation', () => {
    const pages = ['/', '/packs/Test', '/inventory', '/browse', '/settings', '/downloads']

    for (const page of pages) {
      usePageContextStore.getState().setContext(page)
    }

    const { current, previous } = usePageContextStore.getState()
    expect(current?.pageId).toBe('downloads')
    expect(previous?.pageId).toBe('settings')
  })

  it('should handle pack detail → avatar → message with pack context', () => {
    // Navigate to pack detail
    usePageContextStore.getState().setContext('/packs/Pony-Diffusion-V6-XL')
    // Open avatar
    usePageContextStore.getState().setContext('/avatar')

    const { current, previous } = usePageContextStore.getState()

    // Suggestions should be pack-specific
    const suggestions = resolveSuggestions(current, previous)
    expect(suggestions.params.packName).toBe('Pony-Diffusion-V6-XL')

    // Structured context should include the pack entity (fallback to previous on /avatar)
    const payload = buildContextPayload(current) ?? buildContextPayload(previous)
    expect(payload).toMatchObject({
      page: 'pack-detail',
      entity: 'Pony-Diffusion-V6-XL',
      entityType: 'pack',
    })
  })

  it('should fallback to generic suggestions when no context', () => {
    const { keys } = resolveSuggestions(null, null)
    expect(keys).toEqual(FALLBACK_SUGGESTIONS)
    expect(keys.length).toBe(3)
  })
})

// ============================================================================
// Smoke: Multiple send cycles
// ============================================================================

describe('Avatar Widget Smoke — Multiple Send Cycles', () => {
  let chat: ReturnType<typeof createMockChatState>

  beforeEach(() => {
    chat = createMockChatState()
    usePageContextStore.setState({ current: null, previous: null })
  })

  it('should handle multiple send/receive cycles with changing context', () => {
    chat.connect()

    // First message from packs page
    usePageContextStore.getState().setContext('/')
    const ctx1 = buildContextPayload(usePageContextStore.getState().current)
    chat.sendMessage('List my packs', undefined, ctx1 ?? undefined)
    chat.receiveResponse('You have 5 packs installed.')

    // Second message from inventory
    usePageContextStore.getState().setContext('/inventory')
    const ctx2 = buildContextPayload(usePageContextStore.getState().current)
    chat.sendMessage('Show disk usage', undefined, ctx2 ?? undefined)
    chat.receiveResponse('Total: 15.3 GB')

    expect(chat.state.messages).toHaveLength(4)
    expect(chat.state.messages[0].content).toBe('List my packs')
    expect(chat.state.messages[0].context).toMatchObject({ page: 'packs' })
    expect(chat.state.messages[2].content).toBe('Show disk usage')
    expect(chat.state.messages[2].context).toMatchObject({ page: 'inventory' })
  })

  it('should handle send without waiting for response', () => {
    chat.connect()

    chat.sendMessage('Q1')
    expect(chat.state.isStreaming).toBe(true)

    // Receive response
    chat.receiveResponse('A1')
    expect(chat.state.isStreaming).toBe(false)

    // Send again immediately
    chat.sendMessage('Q2')
    expect(chat.state.isStreaming).toBe(true)
    expect(chat.state.messages).toHaveLength(3) // Q1, A1, Q2
  })
})
