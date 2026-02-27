/**
 * AvatarProvider — Context provider wrapping the real @avatar-engine/react hooks.
 *
 * Calls useAvatarChat() ONCE at app root → single persistent WebSocket connection.
 * All chat state (messages, connection, provider, permissions) flows down via context.
 * Provides sendWithContext() that sends page context as structured metadata.
 *
 * Usage:
 *   <AvatarProvider>
 *     <LayoutInner />    ← uses useAvatar() to get chat + providers + compactRef
 *   </AvatarProvider>
 */

import { createContext, useContext, useEffect, useMemo, useRef, useCallback, type ReactNode } from 'react'
import {
  useAvatarChat,
  useAvailableProviders,
  useDynamicModels,
  useModelDiscoveryErrors,
  AVATARS,
} from '@avatar-engine/react'
import type { UseAvatarChatReturn, AvatarConfig, ProviderConfig } from '@avatar-engine/react'
import { usePageContextStore } from '../../stores/pageContextStore'
import { buildContextPayload } from '../../lib/avatar/context'
import { toast } from '../../stores/toastStore'

/** Minimum backend avatar-engine version expected by this frontend. */
const AE_MIN_VERSION = '1.0.0'

/** Compare two semver strings (major.minor.patch). Returns true if a < b. */
function semverLessThan(a: string, b: string): boolean {
  const pa = a.split('.').map(Number)
  const pb = b.split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    if ((pa[i] ?? 0) < (pb[i] ?? 0)) return true
    if ((pa[i] ?? 0) > (pb[i] ?? 0)) return false
  }
  return false
}

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
  /** sendMessage with page context sent as structured metadata */
  sendWithContext: (text: string) => void
  providers: Set<string> | null
  /** Dynamic provider configs with live model lists (scraped from provider docs) */
  dynamicProviders: ProviderConfig[]
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
  const dynamicProviders = useDynamicModels('/api/avatar')
  const modelErrors = useModelDiscoveryErrors()
  const compactRef = useRef<(() => void) | null>(null)

  // Show warning toast when model discovery scraping fails for a provider
  useEffect(() => {
    for (const err of modelErrors) {
      toast.warning(`Model discovery: ${err.message}`)
    }
  }, [modelErrors])

  // Check backend avatar-engine status on first render
  useEffect(() => {
    fetch('/api/avatar/status')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return
        if (data.state === 'no_engine') {
          toast.info('AI assistant unavailable — avatar-engine not installed')
        } else if (data.state === 'no_provider') {
          toast.info('AI assistant unavailable — no AI provider CLI found (gemini/claude/codex)')
        } else if (data.state === 'setup_required') {
          toast.info('AI assistant requires setup — install avatar-engine and a provider CLI')
        } else if (data.state === 'incompatible') {
          toast.warning(`AI engine v${data.engine_version} is incompatible — upgrade to v${data.engine_min_version}+ required`)
        } else if (data.engine_version && data.engine_version !== 'unknown' && semverLessThan(data.engine_version, AE_MIN_VERSION)) {
          toast.warning(`AI engine v${data.engine_version} is outdated — upgrade to v${AE_MIN_VERSION}+ recommended`)
        }
      })
      .catch(() => { /* avatar status not available — non-critical */ })
  }, [])

  // Wrap sendMessage to attach page context as structured metadata
  const sendWithContext = useCallback((text: string) => {
    const { current, previous } = usePageContextStore.getState()
    // Use current page context; fall back to previous only when current
    // has no useful context (e.g. user is on the /avatar page itself)
    const payload = buildContextPayload(current) ?? buildContextPayload(previous)
    chat.sendMessage(text, undefined, payload ? { ...payload } : undefined)
  }, [chat.sendMessage])

  return (
    <AvatarContext.Provider value={{ chat, sendWithContext, providers, dynamicProviders, compactRef }}>
      {children}
    </AvatarContext.Provider>
  )
}

export function useAvatar() {
  const ctx = useContext(AvatarContext)
  if (!ctx) throw new Error('useAvatar must be used within AvatarProvider')
  return ctx
}
