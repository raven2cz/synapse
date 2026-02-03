/**
 * CivitaiPlugin
 *
 * Plugin for packs imported from Civitai.
 *
 * FEATURES:
 * - Check for updates (calls /api/updates/check/{pack_name})
 * - View on Civitai (opens source URL)
 * - Apply updates with UI feedback
 * - Show Civitai metadata (model_id, version_id)
 * - Update notification badge
 *
 * EDIT RESTRICTIONS:
 * - Metadata is read-only (synced from Civitai)
 * - User tags are editable
 * - Parameters are editable
 * - Previews are read-only (from Civitai)
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  RefreshCw,
  ExternalLink,
  AlertTriangle,
  Check,
  Loader2,
  Download,
  Info,
  Globe,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import type { PackDetail } from '../types'
import type {
  PackPlugin,
  PluginContext,
  PluginBadge,
  UpdateCheckResponse,
  UpdateResult,
} from './types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Update Check Component
// =============================================================================

interface UpdateCheckSectionProps {
  context: PluginContext
}

function UpdateCheckSection({ context }: UpdateCheckSectionProps) {
  const { pack, toast, refetch } = context
  const queryClient = useQueryClient()
  const [showDetails, setShowDetails] = useState(false)

  // Query for update check
  const {
    data: updateCheck,
    isLoading: isChecking,
    refetch: checkUpdates,
    isFetched,
  } = useQuery<UpdateCheckResponse>({
    queryKey: ['update-check', pack.name],
    queryFn: async () => {
      const res = await fetch(`/api/updates/check/${encodeURIComponent(pack.name)}`)
      if (!res.ok) {
        const error = await res.text()
        throw new Error(error || 'Failed to check updates')
      }
      return res.json()
    },
    enabled: false, // Manual trigger only
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Mutation for applying updates
  const applyUpdateMutation = useMutation({
    mutationFn: async (options?: { choose?: Record<string, number> }) => {
      const res = await fetch('/api/updates/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pack: pack.name,
          dry_run: false,
          sync: true,
          ...options,
        }),
      })
      if (!res.ok) {
        const error = await res.text()
        throw new Error(error || 'Failed to apply updates')
      }
      return res.json() as Promise<UpdateResult>
    },
    onSuccess: (result) => {
      if (result.applied) {
        toast.success(`Pack updated successfully`)
        queryClient.invalidateQueries({ queryKey: ['pack', pack.name] })
        queryClient.invalidateQueries({ queryKey: ['update-check', pack.name] })
        refetch()
      } else if (result.already_up_to_date) {
        toast.info('Pack is already up to date')
      }
    },
    onError: (error: Error) => {
      toast.error(`Update failed: ${error.message}`)
    },
  })

  const hasUpdates = updateCheck?.has_updates ?? false
  const changesCount = updateCheck?.changes_count ?? 0
  const ambiguousCount = updateCheck?.ambiguous_count ?? 0

  return (
    <Card className={clsx('p-4', ANIMATION_PRESETS.fadeIn)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'p-2 rounded-lg',
            hasUpdates ? 'bg-amber-500/20' : 'bg-synapse/20'
          )}>
            {hasUpdates ? (
              <AlertTriangle className="w-5 h-5 text-amber-400" />
            ) : (
              <Check className="w-5 h-5 text-synapse" />
            )}
          </div>
          <div>
            <h3 className="font-medium text-text-primary">Civitai Updates</h3>
            <p className="text-sm text-text-muted">
              {!isFetched ? (
                'Click to check for updates'
              ) : hasUpdates ? (
                `${changesCount} update${changesCount !== 1 ? 's' : ''} available`
              ) : (
                'Pack is up to date'
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hasUpdates && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => applyUpdateMutation.mutate({})}
              disabled={applyUpdateMutation.isPending}
            >
              {applyUpdateMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              Apply Updates
            </Button>
          )}

          <Button
            variant="secondary"
            size="sm"
            onClick={() => checkUpdates()}
            disabled={isChecking}
          >
            {isChecking ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            Check
          </Button>
        </div>
      </div>

      {/* Update Details */}
      {hasUpdates && updateCheck?.plan && (
        <div className="mt-4 pt-4 border-t border-slate-mid">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-2 text-sm text-text-muted hover:text-text-primary transition-colors"
          >
            <Info className="w-4 h-4" />
            {showDetails ? 'Hide details' : 'Show details'}
          </button>

          {showDetails && (
            <div className="mt-3 space-y-2">
              {updateCheck.plan.changes.map((change, idx) => (
                <div
                  key={idx}
                  className="p-3 bg-slate-dark rounded-lg text-sm"
                >
                  <p className="font-mono text-synapse">{change.dependency_id}</p>
                  <div className="flex items-center gap-2 mt-1 text-text-muted">
                    <span>{String(change.old?.version_name || 'unknown')}</span>
                    <span>→</span>
                    <span className="text-pulse">{String(change.new?.version_name || 'new')}</span>
                  </div>
                </div>
              ))}

              {ambiguousCount > 0 && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                  <p className="text-sm text-amber-400">
                    {ambiguousCount} update{ambiguousCount !== 1 ? 's' : ''} require manual selection
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// =============================================================================
// Civitai Info Section
// =============================================================================

interface CivitaiInfoSectionProps {
  context: PluginContext
}

function CivitaiInfoSection({ context }: CivitaiInfoSectionProps) {
  const { pack } = context
  const source = pack.pack?.source

  if (!source) return null

  return (
    <Card className={clsx('p-4', ANIMATION_PRESETS.fadeIn)}>
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-pulse/20 rounded-lg">
          <Globe className="w-5 h-5 text-pulse" />
        </div>
        <h3 className="font-medium text-text-primary">Civitai Source</h3>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-text-muted">Provider</p>
          <p className="font-mono text-text-primary">{source.provider}</p>
        </div>
        {source.model_id && (
          <div>
            <p className="text-text-muted">Model ID</p>
            <p className="font-mono text-synapse">{source.model_id}</p>
          </div>
        )}
        {source.version_id && (
          <div>
            <p className="text-text-muted">Version ID</p>
            <p className="font-mono text-pulse">{source.version_id}</p>
          </div>
        )}
        {pack.source_url && (
          <div className="col-span-2">
            <p className="text-text-muted">Source URL</p>
            <a
              href={pack.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-synapse hover:underline truncate block"
            >
              {pack.source_url}
            </a>
          </div>
        )}
      </div>
    </Card>
  )
}

// =============================================================================
// Plugin Definition
// =============================================================================

export const CivitaiPlugin: PackPlugin = {
  id: 'civitai',
  name: 'Civitai Integration',
  priority: 50,

  appliesTo: (pack: PackDetail) => {
    return pack.pack?.source?.provider === 'civitai'
  },

  getBadge: (): PluginBadge => ({
    label: 'Civitai',
    variant: 'info',
    icon: 'Globe',
    tooltip: 'Imported from Civitai',
  }),

  features: {
    // After import, pack is YOUR local copy - you can customize it
    // Updates only change the blob (model file), not metadata/previews
    canEditMetadata: true,       // Edit name, description, tags
    canEditPreviews: true,       // Add/remove preview images/videos
    canEditDependencies: false,  // Managed by Civitai (version tracking)
    canEditWorkflows: true,
    canEditParameters: true,
    canCheckUpdates: true,
    canManagePackDependencies: false,
    canRunScripts: false,
    canDelete: true,
  },

  renderHeaderActions: (context: PluginContext) => {
    const { pack } = context

    return (
      <>
        {/* View on Civitai */}
        {pack.source_url && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => window.open(pack.source_url, '_blank')}
            className="hover:bg-pulse/20 hover:text-pulse transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
            Civitai
          </Button>
        )}
      </>
    )
  },

  renderExtraSections: (context: PluginContext) => {
    return (
      <div className="space-y-4">
        <UpdateCheckSection context={context} />
        <CivitaiInfoSection context={context} />
      </div>
    )
  },

  onPackLoad: (pack: PackDetail) => {
    console.log('[CivitaiPlugin] Loaded pack:', pack.name)
  },

  validateChanges: (_pack, _changes) => {
    // All changes are allowed - pack is user's local copy
    // Updates only change the blob (model file), user changes are preserved
    return {
      valid: true,
      errors: {},
    }
  },
}

export default CivitaiPlugin
