/**
 * AvatarProvider — Context provider wrapping the real @avatar-engine/react hooks.
 *
 * Calls useAvatarChat() ONCE at app root → single persistent WebSocket connection.
 * All chat state (messages, connection, provider, permissions) flows down via context.
 * Provides sendWithContext() that prepends page context to messages.
 *
 * Usage:
 *   <AvatarProvider>
 *     <LayoutInner />    ← uses useAvatar() to get chat + providers + compactRef
 *   </AvatarProvider>
 */

import { createContext, useContext, useMemo, useRef, useCallback, type ReactNode } from 'react'
import { useAvatarChat, useAvailableProviders, AVATARS } from '@avatar-engine/react'
import type { UseAvatarChatReturn, AvatarConfig } from '@avatar-engine/react'
import { usePageContextStore } from '../../stores/pageContextStore'
import { buildContextPayload, formatContextForMessage } from '../../lib/avatar/context'

/** Custom Synapse avatar with individual pose files (no sprite sheet). */
const SYNAPSE_AVATAR: AvatarConfig = {
  id: 'synapse',
  name: 'Synapse',
  poses: {
    idle: 'idle.webp',
    thinking: 'thinking.webp',
    speaking: 'speaking.webp',
  },
  speakingFrames: 0,
  speakingFps: 0,
}

/** All avatars: custom Synapse first, then built-in library avatars. */
export const ALL_AVATARS: AvatarConfig[] = [SYNAPSE_AVATAR, ...AVATARS]

interface AvatarContextValue {
  chat: UseAvatarChatReturn
  /** sendMessage with page context prefix injected automatically */
  sendWithContext: (text: string) => void
  providers: Set<string> | null
  compactRef: React.MutableRefObject<(() => void) | null>
}

const AvatarContext = createContext<AvatarContextValue | null>(null)

export function AvatarProvider({ children }: { children: ReactNode }) {
  const wsUrl = useMemo(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${location.host}/api/avatar/ws`
  }, [])

  const chat = useAvatarChat(wsUrl, { apiBase: '/api/avatar' })
  const providers = useAvailableProviders()
  const compactRef = useRef<(() => void) | null>(null)

  // Wrap sendMessage to prepend page context
  const sendWithContext = useCallback((text: string) => {
    const { current, previous } = usePageContextStore.getState()
    // Use previous page context (where user came from) — more useful for avatar
    const payload = buildContextPayload(previous ?? current)
    const prefix = formatContextForMessage(payload)
    const fullMessage = prefix ? `${prefix}\n\n${text}` : text
    chat.sendMessage(fullMessage)
  }, [chat.sendMessage])

  return (
    <AvatarContext.Provider value={{ chat, sendWithContext, providers, compactRef }}>
      {children}
    </AvatarContext.Provider>
  )
}

export function useAvatar() {
  const ctx = useContext(AvatarContext)
  if (!ctx) throw new Error('useAvatar must be used within AvatarProvider')
  return ctx
}
