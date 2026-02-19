/**
 * AddPackDependencyModal
 *
 * Simple modal for adding pack-to-pack dependencies.
 * Shows searchable list of available packs, with required/optional toggle.
 */

import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { X, Loader2, Package, Search, Plus } from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

interface PackSummary {
  name: string
  version?: string
  pack_type?: string
  description?: string
}

export interface AddPackDependencyModalProps {
  isOpen: boolean
  currentPackName: string
  existingDependencies: string[]
  onAdd: (packName: string, required: boolean) => void
  onClose: () => void
  isAdding?: boolean
}

// =============================================================================
// Main Component
// =============================================================================

export function AddPackDependencyModal({
  isOpen,
  currentPackName,
  existingDependencies,
  onAdd,
  onClose,
  isAdding = false,
}: AddPackDependencyModalProps) {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [selectedPack, setSelectedPack] = useState<string | null>(null)
  const [required, setRequired] = useState(true)

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setSearch('')
      setSelectedPack(null)
      setRequired(true)
    }
  }, [isOpen])

  // Fetch available packs
  const { data: allPacks = [], isLoading } = useQuery<PackSummary[]>({
    queryKey: ['packs'],
    queryFn: async () => {
      const res = await fetch('/api/packs/')
      if (!res.ok) throw new Error('Failed to fetch packs')
      const data = await res.json()
      return data.packs || data || []
    },
    enabled: isOpen,
    staleTime: 30000,
  })

  // Filter out current pack and already-added packs
  const availablePacks = useMemo(() => {
    const excluded = new Set([currentPackName, ...existingDependencies])
    return allPacks
      .filter((p) => !excluded.has(p.name))
      .filter((p) => {
        if (!search) return true
        const q = search.toLowerCase()
        return p.name.toLowerCase().includes(q) ||
          p.description?.toLowerCase().includes(q)
      })
  }, [allPacks, currentPackName, existingDependencies, search])

  const handleAdd = () => {
    if (selectedPack) {
      onAdd(selectedPack, required)
    }
  }

  if (!isOpen) return null

  return (
    <div
      className={clsx(
        "fixed inset-0 bg-black/70 z-50",
        "flex items-center justify-center p-4",
        ANIMATION_PRESETS.fadeIn
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={clsx(
          "bg-slate-deep rounded-2xl p-6 max-w-lg w-full max-h-[80vh] flex flex-col",
          "border border-slate-mid/50",
          "shadow-2xl",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
            <Package className="w-5 h-5 text-blue-400" />
            {t('pack.packDependencies.add', 'Add Pack Dependency')}
          </h3>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-mid transition-colors duration-200"
          >
            <X className="w-5 h-5 text-text-muted" />
          </button>
        </div>

        {/* Search */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('pack.packDependencies.searchPlaceholder', 'Search packs...')}
            className={clsx(
              "w-full pl-10 pr-4 py-2.5 rounded-xl",
              "bg-slate-dark border border-slate-mid/50",
              "text-text-primary text-sm placeholder:text-text-muted",
              "focus:border-synapse/50 focus:outline-none focus:ring-1 focus:ring-synapse/30",
              "transition-colors duration-200"
            )}
            autoFocus
          />
        </div>

        {/* Pack list */}
        <div className="flex-1 overflow-y-auto min-h-0 space-y-1 mb-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-synapse animate-spin" />
            </div>
          ) : availablePacks.length === 0 ? (
            <div className="text-center py-8 text-text-muted text-sm">
              {search
                ? t('pack.packDependencies.noMatch', 'No packs match "{{query}}"', { query: search })
                : t('pack.packDependencies.noPacks', 'No packs available')
              }
            </div>
          ) : (
            availablePacks.map((pack) => (
              <button
                key={pack.name}
                onClick={() => setSelectedPack(pack.name === selectedPack ? null : pack.name)}
                className={clsx(
                  "w-full text-left p-3 rounded-xl border transition-all duration-200",
                  pack.name === selectedPack
                    ? "bg-synapse/10 border-synapse/50"
                    : "bg-slate-dark/50 border-transparent hover:border-slate-mid/50 hover:bg-slate-dark"
                )}
              >
                <div className="flex items-center gap-2">
                  <Package className={clsx(
                    "w-4 h-4",
                    pack.name === selectedPack ? "text-synapse" : "text-text-muted"
                  )} />
                  <span className={clsx(
                    "font-medium text-sm",
                    pack.name === selectedPack ? "text-synapse" : "text-text-primary"
                  )}>
                    {pack.name}
                  </span>
                  {pack.version && (
                    <span className="text-xs text-text-muted">v{pack.version}</span>
                  )}
                  {pack.pack_type && (
                    <span className="text-xs px-1.5 py-0.5 bg-slate-mid/50 text-text-muted rounded">
                      {pack.pack_type}
                    </span>
                  )}
                </div>
                {pack.description && (
                  <p className="text-xs text-text-muted mt-1 truncate pl-6">
                    {pack.description}
                  </p>
                )}
              </button>
            ))
          )}
        </div>

        {/* Required toggle */}
        {selectedPack && (
          <div className="flex items-center gap-3 mb-4 p-3 bg-slate-dark/50 rounded-xl">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={required}
                onChange={(e) => setRequired(e.target.checked)}
                className="rounded border-slate-mid text-synapse focus:ring-synapse/30"
              />
              <span className="text-sm text-text-secondary">
                {t('pack.packDependencies.required', 'Required dependency')}
              </span>
            </label>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-mid/30">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={isAdding}
          >
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button
            onClick={handleAdd}
            disabled={!selectedPack || isAdding}
          >
            {isAdding ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            {t('pack.packDependencies.addButton', 'Add')}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default AddPackDependencyModal
