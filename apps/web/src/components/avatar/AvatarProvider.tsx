/**
 * AvatarProvider — Context provider for avatar-engine integration.
 *
 * Wraps the avatar-engine React hooks when the library is available.
 * When not available, provides a fallback context with `available: false`
 * so downstream components can render appropriate UI (setup guides, etc.)
 *
 * Usage:
 *   <AvatarProvider>
 *     <App />
 *   </AvatarProvider>
 *
 * In components:
 *   const { available, state } = useAvatar()
 */

import { createContext, useContext, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAvatarStatus, avatarKeys, type AvatarStatus } from '../../lib/avatar/api'

interface AvatarContextValue {
  /** Whether the avatar engine is fully ready (engine + provider + enabled) */
  available: boolean
  /** Current state: ready | no_provider | no_engine | setup_required | disabled | loading */
  state: AvatarStatus['state'] | 'loading' | 'error'
  /** Full status response from backend */
  status: AvatarStatus | null
  /** Whether we're still loading the initial status */
  isLoading: boolean
}

const AvatarContext = createContext<AvatarContextValue>({
  available: false,
  state: 'loading',
  status: null,
  isLoading: true,
})

export function useAvatar() {
  return useContext(AvatarContext)
}

interface AvatarProviderProps {
  children: ReactNode
}

export function AvatarProvider({ children }: AvatarProviderProps) {
  const { data: status, isLoading, isError } = useQuery({
    queryKey: avatarKeys.status(),
    queryFn: getAvatarStatus,
    staleTime: 60_000, // Re-check every minute
    retry: 1,
    // Don't refetch aggressively — status changes rarely
    refetchOnWindowFocus: false,
  })

  const value: AvatarContextValue = {
    available: status?.available ?? false,
    state: isLoading ? 'loading' : isError ? 'error' : (status?.state ?? 'disabled'),
    status: status ?? null,
    isLoading,
  }

  return (
    <AvatarContext.Provider value={value}>
      {children}
    </AvatarContext.Provider>
  )
}
