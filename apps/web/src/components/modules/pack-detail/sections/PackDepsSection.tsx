/**
 * PackDepsSection - Pack-to-pack dependencies management
 *
 * Extracted from CustomPlugin.tsx and redesigned with:
 * - Rich cards with status-colored borders (matching AssetRow style)
 * - Expandable details with trigger words, asset summary
 * - Dependency tree visualization
 * - Full CRUD support (add/remove via PluginContext)
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Package,
  Plus,
  Layers,
  Search,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Unlink,
  Check,
  AlertTriangle,
  Copy,
  GitBranch,
  Loader2,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import type { PackDependencyRef } from '../types'
import type { PluginContext, PackDependencyStatus } from '../plugins/types'
import { AddPackDependencyModal } from '../modals/AddPackDependencyModal'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Pack Dep Card
// =============================================================================

interface PackDepCardProps {
  dep: PackDependencyStatus
  isEditing: boolean
  onRemove: () => void
  onNavigate: () => void
}

function PackDepCard({ dep, isEditing, onRemove, onNavigate }: PackDepCardProps) {
  const { t } = useTranslation()
  const [detailsOpen, setDetailsOpen] = useState(false)

  // Determine status state
  const isInstalled = dep.installed
  const allReady = isInstalled && dep.all_installed && !dep.has_unresolved
  const partialReady = isInstalled && (!dep.all_installed || dep.has_unresolved)
  const isMissing = !isInstalled

  // Status colors matching AssetRow pattern
  const cardClass = allReady
    ? 'bg-green-900/30 border-green-500/50'
    : partialReady
      ? 'bg-amber-900/30 border-amber-500/50'
      : isMissing
        ? 'bg-red-900/20 border-red-500/30'
        : 'bg-blue-900/20 border-blue-500/30'

  // Status icon
  const StatusIcon = () => {
    if (allReady) return <Check className="w-4 h-4 text-green-400" />
    if (partialReady) return <AlertTriangle className="w-4 h-4 text-amber-400" />
    return <Unlink className="w-4 h-4 text-red-400" />
  }

  const hasDetails = (dep.trigger_words && dep.trigger_words.length > 0) ||
    dep.description ||
    (dep.asset_count && dep.asset_count > 0)

  return (
    <div className={clsx('p-4 rounded-xl border transition-all duration-200 hover:shadow-lg', cardClass)}>
      {/* Main row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Status icon */}
          <div className={clsx(
            'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
            allReady ? 'bg-green-500/20' : partialReady ? 'bg-amber-500/20' : 'bg-red-500/20'
          )}>
            <StatusIcon />
          </div>

          {/* Info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <button
                onClick={onNavigate}
                className="font-medium text-text-primary hover:text-synapse transition-colors text-left truncate"
              >
                {dep.pack_name}
              </button>
              {dep.current_version && (
                <span className="px-1.5 py-0.5 bg-slate-mid/50 text-text-muted rounded text-xs flex-shrink-0">
                  v{dep.current_version}
                </span>
              )}
              {dep.required && (
                <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-300 rounded text-xs flex-shrink-0">
                  {t('pack.packDependencies.status.required', 'Required')}
                </span>
              )}
              {!dep.required && (
                <span className="px-1.5 py-0.5 bg-slate-mid/30 text-text-muted rounded text-xs flex-shrink-0">
                  {t('pack.dependencies.optional', 'Optional')}
                </span>
              )}
            </div>
            {/* Metadata line */}
            <div className="flex items-center gap-2 text-xs text-text-muted mt-0.5">
              {dep.pack_type && (
                <span className="uppercase font-medium">{dep.pack_type}</span>
              )}
              {dep.asset_count != null && dep.asset_count > 0 && (
                <>
                  {dep.pack_type && <span>·</span>}
                  <span>{t('pack.packDependencies.assetSummary', '{{count}} assets', { count: dep.asset_count })}</span>
                </>
              )}
              {dep.base_model && (
                <>
                  <span>·</span>
                  <span className="text-amber-400 font-medium">{dep.base_model}</span>
                </>
              )}
              {isInstalled && allReady && (
                <>
                  <span>·</span>
                  <span className="text-green-400">{t('pack.packDependencies.allInstalled', 'All installed')}</span>
                </>
              )}
              {isInstalled && dep.has_unresolved && (
                <>
                  <span>·</span>
                  <span className="text-amber-400">{t('pack.packDependencies.someUnresolved', 'Some unresolved')}</span>
                </>
              )}
            </div>
            {/* Description */}
            {dep.description && !detailsOpen && (
              <p className="text-xs text-text-muted/70 mt-1 truncate">{dep.description}</p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {hasDetails && (
            <button
              onClick={() => setDetailsOpen(!detailsOpen)}
              className="p-1.5 text-text-muted hover:text-text-primary transition-colors"
              title={detailsOpen ? 'Collapse' : 'Expand'}
            >
              {detailsOpen
                ? <ChevronDown className="w-4 h-4" />
                : <ChevronRight className="w-4 h-4" />
              }
            </button>
          )}
          <button
            onClick={onNavigate}
            className="p-2 bg-slate-mid/50 text-text-muted rounded-lg hover:text-synapse hover:bg-slate-mid/80 transition-all duration-200"
            title={t('pack.packDependencies.navigate', 'Go to pack')}
          >
            <ExternalLink className="w-4 h-4" />
          </button>
          {!isInstalled && (
            <Button
              variant="primary"
              size="sm"
              onClick={onNavigate}
            >
              <Package className="w-4 h-4" />
              {t('pack.plugins.custom.find')}
            </Button>
          )}
          {isEditing && (
            <button
              onClick={onRemove}
              className="p-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-all duration-200"
              title={t('common.remove')}
            >
              <Unlink className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Expandable details */}
      {detailsOpen && (
        <div className="mt-3 pt-3 border-t border-white/10 space-y-2">
          {/* Description */}
          {dep.description && (
            <p className="text-sm text-text-muted">{dep.description}</p>
          )}

          {/* Trigger words */}
          {dep.trigger_words && dep.trigger_words.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-xs text-text-secondary font-medium w-16 pt-1 flex-shrink-0">
                {t('pack.packDependencies.triggerWords', 'Triggers')}
              </span>
              <div className="flex flex-wrap gap-1">
                {dep.trigger_words.map((w, i) => (
                  <button
                    key={i}
                    className="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs hover:bg-purple-500/30 transition-colors flex items-center gap-1"
                    onClick={() => navigator.clipboard.writeText(w)}
                    title={t('pack.dependencies.detail.copyTrigger', 'Copy to clipboard')}
                  >
                    {w}
                    <Copy className="w-2.5 h-2.5 opacity-50" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Asset count and status */}
          {dep.asset_count != null && dep.asset_count > 0 && (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <Package className="w-3 h-3" />
              <span>{t('pack.packDependencies.assetSummary', '{{count}} assets', { count: dep.asset_count })}</span>
              {dep.all_installed && <span className="text-green-400">✓</span>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Dependency Tree
// =============================================================================

interface TreeNodeData {
  pack_name: string
  installed: boolean
  version?: string | null
  pack_type?: string | null
  description?: string | null
  asset_count: number
  trigger_words: string[]
  children: TreeNodeData[]
  circular: boolean
  depth: number
}

interface DependencyTreeProps {
  packName: string
}

function DependencyTree({ packName }: DependencyTreeProps) {
  const { t } = useTranslation()

  const { data, isLoading } = useQuery<{ tree: TreeNodeData; max_depth: number }>({
    queryKey: ['dependency-tree', packName],
    queryFn: async () => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/dependency-tree?max_depth=5`)
      if (!res.ok) throw new Error('Failed to fetch dependency tree')
      return res.json()
    },
    staleTime: 60000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-text-muted p-3">
        <Loader2 className="w-4 h-4 animate-spin" />
        {t('common.loading', 'Loading...')}
      </div>
    )
  }

  if (!data?.tree?.children?.length) return null

  return (
    <div className="mt-4 pt-4 border-t border-slate-mid/50">
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-text-muted" />
        <h4 className="text-sm font-medium text-text-secondary">
          {t('pack.packDependencies.tree.title', 'Dependency Tree')}
        </h4>
      </div>
      <div className="pl-2">
        {data.tree.children.map((child, i) => (
          <TreeNode
            key={child.pack_name}
            node={child}
            isLast={i === data.tree.children.length - 1}
            autoExpand={child.depth < 2}
          />
        ))}
      </div>
    </div>
  )
}

interface TreeNodeProps {
  node: TreeNodeData
  isLast: boolean
  autoExpand?: boolean
}

function TreeNode({ node, isLast, autoExpand = false }: TreeNodeProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(autoExpand)
  const hasChildren = node.children.length > 0 && !node.circular

  return (
    <div className="relative">
      {/* Vertical line from parent */}
      {!isLast && (
        <div className="absolute left-0 top-0 bottom-0 w-px bg-slate-mid/50" />
      )}
      {isLast && (
        <div className="absolute left-0 top-0 h-4 w-px bg-slate-mid/50" />
      )}

      {/* Horizontal connector */}
      <div className="flex items-center gap-0">
        <div className="w-4 h-px bg-slate-mid/50 flex-shrink-0" />

        {/* Node content */}
        <div className="flex items-center gap-2 py-1 pl-1 min-w-0 flex-1">
          {/* Expand/collapse */}
          {hasChildren ? (
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-0.5 text-text-muted hover:text-text-primary transition-colors flex-shrink-0"
            >
              {expanded
                ? <ChevronDown className="w-3 h-3" />
                : <ChevronRight className="w-3 h-3" />
              }
            </button>
          ) : (
            <div className="w-4" />
          )}

          {/* Status dot */}
          <div className={clsx(
            'w-2 h-2 rounded-full flex-shrink-0',
            node.circular ? 'bg-orange-400' : node.installed ? 'bg-green-400' : 'bg-red-400'
          )} />

          {/* Pack name (clickable) */}
          <a
            href={`/pack/${encodeURIComponent(node.pack_name)}`}
            className={clsx(
              'text-sm hover:text-synapse transition-colors truncate',
              node.installed ? 'text-text-primary' : 'text-text-muted'
            )}
          >
            {node.pack_name}
          </a>

          {/* Badges */}
          {node.pack_type && (
            <span className="px-1 py-0.5 bg-slate-mid/40 text-text-muted rounded text-[10px] uppercase flex-shrink-0">
              {node.pack_type}
            </span>
          )}
          {node.asset_count > 0 && (
            <span className="text-[10px] text-text-muted flex-shrink-0">
              {node.asset_count} {t('pack.packDependencies.tree.assets', 'assets')}
            </span>
          )}
          {node.trigger_words.length > 0 && (
            <span className="text-[10px] text-purple-400 flex-shrink-0">
              {node.trigger_words.length} {t('pack.packDependencies.tree.triggers', 'triggers')}
            </span>
          )}
          {node.circular && (
            <span className="px-1.5 py-0.5 bg-orange-500/20 text-orange-400 rounded text-[10px] flex-shrink-0">
              {t('pack.packDependencies.tree.circular', 'circular')}
            </span>
          )}
        </div>
      </div>

      {/* Children */}
      {hasChildren && expanded && (
        <div className="pl-4 relative">
          {node.children.map((child, i) => (
            <TreeNode
              key={child.pack_name}
              node={child}
              isLast={i === node.children.length - 1}
              autoExpand={child.depth < 2}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main PackDepsSection
// =============================================================================

interface PackDepsSectionProps {
  context: PluginContext
}

export function PackDepsSection({ context }: PackDepsSectionProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { pack, isEditing } = context
  const [expanded, setExpanded] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)

  const packDependencies: PackDependencyRef[] = pack.pack?.pack_dependencies ?? []

  // Batch status query with enriched fields
  const { data: dependencyStatuses = [] } = useQuery<PackDependencyStatus[]>({
    queryKey: ['pack-dependencies-status', pack.name],
    queryFn: async () => {
      const res = await fetch(`/api/packs/${encodeURIComponent(pack.name)}/pack-dependencies/status`)
      if (!res.ok) throw new Error('Failed to fetch status')
      const data = await res.json()
      return data.map((s: Record<string, unknown>) => ({
        pack_name: s.pack_name as string,
        required: s.required as boolean,
        installed: s.installed as boolean,
        current_version: s.version as string | undefined,
        version_match: s.installed as boolean,
        pack_type: s.pack_type as string | undefined,
        description: s.description as string | undefined,
        asset_count: s.asset_count as number | undefined,
        trigger_words: s.trigger_words as string[] | undefined,
        base_model: s.base_model as string | undefined,
        has_unresolved: s.has_unresolved as boolean | undefined,
        all_installed: s.all_installed as boolean | undefined,
      }))
    },
    enabled: packDependencies.length > 0,
    staleTime: 30000,
  })

  // Add mutation
  const addMutation = useMutation({
    mutationFn: async ({ packName, required }: { packName: string; required: boolean }) => {
      const res = await fetch(`/api/packs/${encodeURIComponent(pack.name)}/pack-dependencies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack_name: packName, required }),
      })
      if (!res.ok) {
        const err = await res.text()
        throw new Error(err)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pack', pack.name] })
      queryClient.invalidateQueries({ queryKey: ['pack-dependencies-status', pack.name] })
      queryClient.invalidateQueries({ queryKey: ['dependency-tree', pack.name] })
      context.toast.success(t('pack.plugins.custom.depAdded', 'Dependency added'))
      setShowAddModal(false)
    },
    onError: (err: Error) => {
      context.toast.error(err.message)
    },
  })

  // Remove mutation
  const removeMutation = useMutation({
    mutationFn: async (depPackName: string) => {
      const res = await fetch(
        `/api/packs/${encodeURIComponent(pack.name)}/pack-dependencies/${encodeURIComponent(depPackName)}`,
        { method: 'DELETE' }
      )
      if (!res.ok) {
        const err = await res.text()
        throw new Error(err)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pack', pack.name] })
      queryClient.invalidateQueries({ queryKey: ['pack-dependencies-status', pack.name] })
      queryClient.invalidateQueries({ queryKey: ['dependency-tree', pack.name] })
      context.toast.success(t('pack.plugins.custom.depRemoved', 'Dependency removed'))
    },
    onError: (err: Error) => {
      context.toast.error(err.message)
    },
  })

  // Filter
  const filteredDependencies = dependencyStatuses.filter(dep =>
    dep.pack_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const existingDepNames = packDependencies.map(d => d.pack_name)
  const installedCount = dependencyStatuses.filter(d => d.installed).length
  const missingCount = dependencyStatuses.filter(d => !d.installed).length

  // Empty state
  if (packDependencies.length === 0) {
    return (
      <>
        <Card className={clsx('p-4', ANIMATION_PRESETS.fadeIn)}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-slate-mid/50 rounded-lg">
                <Layers className="w-5 h-5 text-text-muted" />
              </div>
              <div>
                <h3 className="font-medium text-text-primary">{t('pack.plugins.custom.packDependencies')}</h3>
                <p className="text-sm text-text-muted">
                  {t('pack.plugins.custom.noDeps')}
                </p>
              </div>
            </div>

            {isEditing && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowAddModal(true)}
              >
                <Plus className="w-4 h-4" />
                {t('common.add')}
              </Button>
            )}
          </div>
        </Card>

        <AddPackDependencyModal
          isOpen={showAddModal}
          currentPackName={pack.name}
          existingDependencies={existingDepNames}
          onAdd={(packName, required) => addMutation.mutate({ packName, required })}
          onClose={() => setShowAddModal(false)}
          isAdding={addMutation.isPending}
        />
      </>
    )
  }

  return (
    <>
      <Card className={clsx('overflow-hidden', ANIMATION_PRESETS.fadeIn)}>
        {/* Header */}
        <div
          className="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-mid/30 transition-colors"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-3">
            <div className={clsx(
              'p-2 rounded-lg',
              missingCount > 0 ? 'bg-amber-500/20' : 'bg-synapse/20'
            )}>
              <Layers className={clsx(
                'w-5 h-5',
                missingCount > 0 ? 'text-amber-400' : 'text-synapse'
              )} />
            </div>
            <div>
              <h3 className="font-medium text-text-primary">{t('pack.plugins.custom.packDependencies')}</h3>
              <p className="text-sm text-text-muted">
                {t('pack.plugins.custom.installedCount', { count: installedCount })}
                {missingCount > 0 && (
                  <span className="text-amber-400 ml-1">
                    · {t('pack.plugins.custom.missingCount', { count: missingCount })}
                  </span>
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isEditing && (
              <Button
                variant="secondary"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  setShowAddModal(true)
                }}
              >
                <Plus className="w-4 h-4" />
                {t('common.add')}
              </Button>
            )}
            {expanded ? (
              <ChevronDown className="w-5 h-5 text-text-muted" />
            ) : (
              <ChevronRight className="w-5 h-5 text-text-muted" />
            )}
          </div>
        </div>

        {/* Content */}
        {expanded && (
          <div className="border-t border-slate-mid">
            {/* Search */}
            {packDependencies.length > 3 && (
              <div className="p-3 border-b border-slate-mid">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={t('pack.plugins.custom.searchPlaceholder')}
                    className={clsx(
                      'w-full pl-9 pr-4 py-2 rounded-lg',
                      'bg-slate-dark border border-slate-mid',
                      'text-text-primary placeholder:text-text-muted',
                      'focus:outline-none focus:ring-2 focus:ring-synapse/50'
                    )}
                  />
                </div>
              </div>
            )}

            {/* Card-based dependency list */}
            <div className="p-4 space-y-3 max-h-[600px] overflow-y-auto">
              {filteredDependencies.map((dep) => (
                <PackDepCard
                  key={dep.pack_name}
                  dep={dep}
                  isEditing={isEditing}
                  onRemove={() => {
                    if (confirm(t('pack.plugins.custom.confirmRemove', {
                      name: dep.pack_name,
                      defaultValue: `Remove pack dependency "${dep.pack_name}"?`,
                    }))) {
                      removeMutation.mutate(dep.pack_name)
                    }
                  }}
                  onNavigate={() => {
                    window.location.href = `/pack/${encodeURIComponent(dep.pack_name)}`
                  }}
                />
              ))}

              {filteredDependencies.length === 0 && searchQuery && (
                <div className="p-4 text-center text-text-muted">
                  {t('pack.plugins.custom.noMatch', { query: searchQuery })}
                </div>
              )}
            </div>

            {/* Dependency tree */}
            {packDependencies.length > 0 && (
              <div className="px-4 pb-4">
                <DependencyTree packName={pack.name} />
              </div>
            )}
          </div>
        )}
      </Card>

      <AddPackDependencyModal
        isOpen={showAddModal}
        currentPackName={pack.name}
        existingDependencies={existingDepNames}
        onAdd={(packName, required) => addMutation.mutate({ packName, required })}
        onClose={() => setShowAddModal(false)}
        isAdding={addMutation.isPending}
      />
    </>
  )
}

export default PackDepsSection
