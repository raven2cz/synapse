/**
 * AI Services React Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getCacheStats,
  clearCache,
  cleanupCache,
} from './api'

/**
 * Query key factory for AI services
 */
export const aiKeys = {
  all: ['ai'] as const,
  cacheStats: () => [...aiKeys.all, 'cache', 'stats'] as const,
}

/**
 * Hook to get cache statistics
 */
export function useAICacheStats() {
  return useQuery({
    queryKey: aiKeys.cacheStats(),
    queryFn: getCacheStats,
    staleTime: 30_000,
  })
}

/**
 * Hook to clear cache
 */
export function useClearAICache() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: clearCache,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiKeys.cacheStats() })
    },
  })
}

/**
 * Hook to cleanup expired cache
 */
export function useCleanupAICache() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: cleanupCache,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiKeys.cacheStats() })
    },
  })
}
