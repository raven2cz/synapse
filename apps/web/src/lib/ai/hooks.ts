/**
 * AI Services React Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  detectProviders,
  getAISettings,
  getCacheStats,
  clearCache,
  cleanupCache,
  updateAISettings,
} from './api'
import type { AIServicesSettings } from './types'

/**
 * Query key factory for AI services
 */
export const aiKeys = {
  all: ['ai'] as const,
  providers: () => [...aiKeys.all, 'providers'] as const,
  settings: () => [...aiKeys.all, 'settings'] as const,
  cacheStats: () => [...aiKeys.all, 'cache', 'stats'] as const,
}

/**
 * Hook to detect available AI providers
 */
export function useAIProviders() {
  return useQuery({
    queryKey: aiKeys.providers(),
    queryFn: detectProviders,
    staleTime: 30_000, // 30 seconds
    refetchInterval: 60_000, // Refresh every minute
  })
}

/**
 * Hook to get AI settings
 */
export function useAISettings() {
  return useQuery({
    queryKey: aiKeys.settings(),
    queryFn: getAISettings,
    staleTime: 60_000, // 1 minute
  })
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

/**
 * Hook to refetch providers
 */
export function useRefreshAIProviders() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: detectProviders,
    onSuccess: (data) => {
      queryClient.setQueryData(aiKeys.providers(), data)
    },
  })
}

/**
 * Hook to update AI settings
 */
export function useUpdateAISettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (updates: Partial<AIServicesSettings>) => updateAISettings(updates),
    onSuccess: (data) => {
      queryClient.setQueryData(aiKeys.settings(), data)
    },
  })
}
