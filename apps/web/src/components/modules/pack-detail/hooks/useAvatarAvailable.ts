/**
 * useAvatarAvailable Hook
 *
 * Checks whether the AI avatar is available for dependency resolution.
 * Used to conditionally show the "AI Resolve" tab in DependencyResolverModal.
 */

import { useQuery } from '@tanstack/react-query'
import { avatarKeys, getAvatarStatus } from '@/lib/avatar/api'

export function useAvatarAvailable() {
  const { data: status } = useQuery({
    queryKey: avatarKeys.status(),
    queryFn: getAvatarStatus,
    staleTime: 60_000, // Cache for 1 minute
    retry: 1,
  })

  return {
    avatarAvailable: status?.available ?? false,
    activeProvider: status?.active_provider ?? null,
  }
}

export default useAvatarAvailable
