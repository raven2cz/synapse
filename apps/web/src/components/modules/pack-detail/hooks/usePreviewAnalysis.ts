/**
 * usePreviewAnalysis Hook
 *
 * Fetches preview analysis data (model hints + generation params) for a pack.
 */

import { useQuery } from '@tanstack/react-query'
import type { PreviewAnalysisResponse } from '../types'

export function usePreviewAnalysis(packName: string, enabled: boolean) {
  return useQuery<PreviewAnalysisResponse>({
    queryKey: ['pack', packName, 'preview-analysis'],
    queryFn: async () => {
      const res = await fetch(
        `/api/packs/${encodeURIComponent(packName)}/preview-analysis`
      )
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to fetch preview analysis: ${errText}`)
      }
      return res.json()
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 min — data doesn't change until re-import
  })
}
