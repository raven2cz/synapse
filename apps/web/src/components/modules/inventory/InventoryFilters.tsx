/**
 * InventoryFilters - Filter controls for inventory table
 */
import { Search } from 'lucide-react'
import type { InventoryFilters as Filters, AssetKind, BlobStatus, BlobLocation } from './types'

interface InventoryFiltersProps {
  filters: Filters
  onChange: (filters: Filters) => void
}

const KIND_OPTIONS: Array<{ value: AssetKind | 'all'; label: string }> = [
  { value: 'all', label: 'All Types' },
  { value: 'checkpoint', label: 'Checkpoint' },
  { value: 'lora', label: 'LoRA' },
  { value: 'vae', label: 'VAE' },
  { value: 'embedding', label: 'Embedding' },
  { value: 'controlnet', label: 'ControlNet' },
  { value: 'upscaler', label: 'Upscaler' },
  { value: 'other', label: 'Other' },
]

const STATUS_OPTIONS: Array<{ value: BlobStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All Status' },
  { value: 'referenced', label: 'Referenced' },
  { value: 'orphan', label: 'Orphan' },
  { value: 'missing', label: 'Missing' },
  { value: 'backup_only', label: 'Backup Only' },
]

const LOCATION_OPTIONS: Array<{ value: BlobLocation | 'all'; label: string }> = [
  { value: 'all', label: 'All Locations' },
  { value: 'both', label: 'Both (synced)' },
  { value: 'local_only', label: 'Local Only' },
  { value: 'backup_only', label: 'Backup Only' },
  { value: 'nowhere', label: 'Missing' },
]

export function InventoryFilters({ filters, onChange }: InventoryFiltersProps) {
  return (
    <div className="flex flex-wrap gap-4 items-center">
      {/* Search */}
      <div className="flex-1 min-w-[250px] relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          type="text"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search by name or SHA256..."
          className="w-full pl-10 pr-4 py-2.5 bg-slate-dark border border-slate-mid rounded-xl text-text-primary placeholder-text-muted focus:outline-none focus:border-synapse transition-colors text-sm"
        />
      </div>

      {/* Kind filter */}
      <select
        value={filters.kind}
        onChange={(e) => onChange({ ...filters, kind: e.target.value as AssetKind | 'all' })}
        className="px-4 py-2.5 bg-slate-dark border border-slate-mid rounded-xl text-text-primary focus:outline-none focus:border-synapse cursor-pointer text-sm"
      >
        {KIND_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {/* Status filter */}
      <select
        value={filters.status}
        onChange={(e) => onChange({ ...filters, status: e.target.value as BlobStatus | 'all' })}
        className="px-4 py-2.5 bg-slate-dark border border-slate-mid rounded-xl text-text-primary focus:outline-none focus:border-synapse cursor-pointer text-sm"
      >
        {STATUS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {/* Location filter */}
      <select
        value={filters.location}
        onChange={(e) => onChange({ ...filters, location: e.target.value as BlobLocation | 'all' })}
        className="px-4 py-2.5 bg-slate-dark border border-slate-mid rounded-xl text-text-primary focus:outline-none focus:border-synapse cursor-pointer text-sm"
      >
        {LOCATION_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
