/**
 * CustomPlugin
 *
 * Plugin for custom (locally created) packs.
 *
 * FEATURES:
 * - Full editability of all fields
 * - Pack dependencies management (dependencies on other packs)
 * - Support for 7+ asset dependencies
 * - Markdown description editor
 * - Preview management
 *
 * This is the DEFAULT plugin - used as fallback when no other plugin matches.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Package,
  Plus,
  Link2,
  Unlink,
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  Layers,
  Edit3,
  Search,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import type { PackDetail, PackDependencyRef } from '../types'
import type {
  PackPlugin,
  PluginContext,
  PluginBadge,
  PackDependencyStatus,
} from './types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Pack Dependencies Section
// =============================================================================

interface PackDependenciesSectionProps {
  context: PluginContext
}

function PackDependenciesSection({ context }: PackDependenciesSectionProps) {
  const { pack, isEditing, openModal } = context
  const [expanded, setExpanded] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  // Get pack dependencies from pack data
  const packDependencies: PackDependencyRef[] = pack.pack?.pack_dependencies ?? []

  // Query to check status of each pack dependency
  const { data: dependencyStatuses = [] } = useQuery<PackDependencyStatus[]>({
    queryKey: ['pack-dependencies-status', pack.name, packDependencies],
    queryFn: async () => {
      // Check each dependency's status
      const statuses: PackDependencyStatus[] = await Promise.all(
        packDependencies.map(async (dep) => {
          try {
            const res = await fetch(`/api/packs/${encodeURIComponent(dep.pack_name)}`)
            if (res.ok) {
              const data = await res.json()
              return {
                ...dep,
                installed: true,
                current_version: data.version,
                version_match: !dep.version_constraint || true, // TODO: semantic version check
              }
            } else {
              return {
                ...dep,
                installed: false,
                version_match: false,
                error: 'Pack not found',
              }
            }
          } catch (e) {
            return {
              ...dep,
              installed: false,
              version_match: false,
              error: 'Failed to check status',
            }
          }
        })
      )
      return statuses
    },
    enabled: packDependencies.length > 0,
    staleTime: 30000,
  })

  // Filter dependencies by search
  const filteredDependencies = dependencyStatuses.filter(dep =>
    dep.pack_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (packDependencies.length === 0) {
    return (
      <Card className={clsx('p-4', ANIMATION_PRESETS.fadeIn)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-slate-mid/50 rounded-lg">
              <Layers className="w-5 h-5 text-text-muted" />
            </div>
            <div>
              <h3 className="font-medium text-text-primary">Pack Dependencies</h3>
              <p className="text-sm text-text-muted">
                No dependencies on other packs
              </p>
            </div>
          </div>

          {isEditing && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => openModal('addPackDependency')}
            >
              <Plus className="w-4 h-4" />
              Add
            </Button>
          )}
        </div>
      </Card>
    )
  }

  const installedCount = dependencyStatuses.filter(d => d.installed).length
  const missingCount = dependencyStatuses.filter(d => !d.installed).length

  return (
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
            <h3 className="font-medium text-text-primary">Pack Dependencies</h3>
            <p className="text-sm text-text-muted">
              {installedCount} installed
              {missingCount > 0 && (
                <span className="text-amber-400 ml-1">
                  • {missingCount} missing
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
                openModal('addPackDependency')
              }}
            >
              <Plus className="w-4 h-4" />
              Add
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
          {/* Search (if many dependencies) */}
          {packDependencies.length > 3 && (
            <div className="p-3 border-b border-slate-mid">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search dependencies..."
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

          {/* Dependency List */}
          <div className="divide-y divide-slate-mid max-h-96 overflow-y-auto">
            {filteredDependencies.map((dep) => (
              <PackDependencyRow
                key={dep.pack_name}
                dependency={dep}
                isEditing={isEditing}
                onRemove={() => {
                  // TODO: implement remove
                  context.toast.info('Remove pack dependency: ' + dep.pack_name)
                }}
                onNavigate={() => {
                  // Navigate to pack
                  window.location.href = `/pack/${encodeURIComponent(dep.pack_name)}`
                }}
              />
            ))}

            {filteredDependencies.length === 0 && searchQuery && (
              <div className="p-4 text-center text-text-muted">
                No dependencies match "{searchQuery}"
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}

// =============================================================================
// Pack Dependency Row
// =============================================================================

interface PackDependencyRowProps {
  dependency: PackDependencyStatus
  isEditing: boolean
  onRemove: () => void
  onNavigate: () => void
}

function PackDependencyRow({ dependency, isEditing, onRemove, onNavigate }: PackDependencyRowProps) {
  return (
    <div
      className={clsx(
        'p-4 flex items-center gap-4',
        'hover:bg-slate-mid/20 transition-colors'
      )}
    >
      {/* Status Icon */}
      <div className={clsx(
        'p-2 rounded-lg',
        dependency.installed
          ? dependency.version_match
            ? 'bg-green-500/20'
            : 'bg-amber-500/20'
          : 'bg-red-500/20'
      )}>
        {dependency.installed ? (
          dependency.version_match ? (
            <Link2 className="w-4 h-4 text-green-400" />
          ) : (
            <AlertCircle className="w-4 h-4 text-amber-400" />
          )
        ) : (
          <Unlink className="w-4 h-4 text-red-400" />
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <button
          onClick={onNavigate}
          className="font-medium text-text-primary hover:text-synapse transition-colors text-left"
        >
          {dependency.pack_name}
        </button>
        <div className="flex items-center gap-2 text-sm text-text-muted">
          {dependency.installed ? (
            <>
              <span className="text-green-400">Installed</span>
              {dependency.current_version && (
                <span>v{dependency.current_version}</span>
              )}
            </>
          ) : (
            <span className="text-red-400">{dependency.error || 'Not installed'}</span>
          )}
          {dependency.required && (
            <span className="text-amber-400">• Required</span>
          )}
          {dependency.version_constraint && (
            <span className="font-mono">{dependency.version_constraint}</span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {!dependency.installed && (
          <Button
            variant="primary"
            size="sm"
            onClick={onNavigate}
          >
            <Package className="w-4 h-4" />
            Find
          </Button>
        )}
        {isEditing && (
          <Button
            variant="secondary"
            size="sm"
            onClick={onRemove}
            className="text-red-400 hover:bg-red-500/20"
          >
            Remove
          </Button>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Edit Capabilities Info
// =============================================================================

interface EditCapabilitiesInfoProps {
  context: PluginContext
}

function EditCapabilitiesInfo({ context }: EditCapabilitiesInfoProps) {
  const { isEditing } = context

  if (!isEditing) return null

  return (
    <Card className={clsx('p-4 bg-synapse/10 border-synapse/30', ANIMATION_PRESETS.fadeIn)}>
      <div className="flex items-start gap-3">
        <div className="p-2 bg-synapse/20 rounded-lg">
          <Edit3 className="w-5 h-5 text-synapse" />
        </div>
        <div>
          <h3 className="font-medium text-text-primary">Full Edit Mode</h3>
          <p className="text-sm text-text-muted mt-1">
            This is a custom pack. You can edit all fields:
          </p>
          <ul className="text-sm text-text-muted mt-2 space-y-1">
            <li className="flex items-center gap-2">
              <Check className="w-3 h-3 text-synapse" />
              Name, description, and metadata
            </li>
            <li className="flex items-center gap-2">
              <Check className="w-3 h-3 text-synapse" />
              Previews (add, remove, reorder)
            </li>
            <li className="flex items-center gap-2">
              <Check className="w-3 h-3 text-synapse" />
              Dependencies and pack dependencies
            </li>
            <li className="flex items-center gap-2">
              <Check className="w-3 h-3 text-synapse" />
              Workflows and parameters
            </li>
          </ul>
        </div>
      </div>
    </Card>
  )
}

// =============================================================================
// Plugin Definition
// =============================================================================

export const CustomPlugin: PackPlugin = {
  id: 'custom',
  name: 'Custom Pack',
  priority: 0, // Lowest - fallback

  appliesTo: (pack: PackDetail) => {
    // Match custom packs or use as fallback
    return pack.pack?.pack_category === 'custom' || true
  },

  getBadge: (pack: PackDetail): PluginBadge | null => {
    // Only show badge for explicitly custom packs
    if (pack.pack?.pack_category === 'custom') {
      return {
        label: 'Custom',
        variant: 'success',
        icon: 'Package',
        tooltip: 'Locally created pack',
      }
    }
    return null
  },

  features: {
    canEditMetadata: true,
    canEditPreviews: true,
    canEditDependencies: true,
    canEditWorkflows: true,
    canEditParameters: true,
    canCheckUpdates: false,
    canManagePackDependencies: true,
    canRunScripts: false,
    canDelete: true,
  },

  renderHeaderActions: (_context: PluginContext) => {
    // Custom packs don't need extra header actions
    // Edit button is already provided by the main header
    return null
  },

  renderExtraSections: (context: PluginContext) => {
    const { pack } = context
    const hasPackDependencies = (pack.pack?.pack_dependencies?.length ?? 0) > 0

    return (
      <div className="space-y-4">
        <EditCapabilitiesInfo context={context} />
        {hasPackDependencies && <PackDependenciesSection context={context} />}
      </div>
    )
  },

  onPackLoad: (pack: PackDetail) => {
    console.log('[CustomPlugin] Loaded pack:', pack.name, 'category:', pack.pack?.pack_category)
  },

  validateChanges: (_pack, changes) => {
    const errors: Record<string, string> = {}

    // Validate name if changed
    if (changes.name !== undefined) {
      if (!changes.name || changes.name.trim() === '') {
        errors.name = 'Pack name is required'
      } else if (changes.name.length > 100) {
        errors.name = 'Pack name must be 100 characters or less'
      }
    }

    // Validate version if changed
    if (changes.version !== undefined) {
      const versionRegex = /^\d+\.\d+\.\d+$/
      if (changes.version && !versionRegex.test(changes.version)) {
        errors.version = 'Version must be in format X.Y.Z'
      }
    }

    return {
      valid: Object.keys(errors).length === 0,
      errors,
    }
  },

  onBeforeSave: (_pack, changes) => {
    // Clean up changes before save
    const cleanedChanges = { ...changes }

    // Trim strings
    if (cleanedChanges.name) {
      cleanedChanges.name = cleanedChanges.name.trim()
    }
    if (cleanedChanges.description) {
      cleanedChanges.description = cleanedChanges.description.trim()
    }

    return { changes: cleanedChanges }
  },
}

export default CustomPlugin
