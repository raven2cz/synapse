/**
 * InventoryFilters - Filter controls for inventory table
 * Custom UI dropdowns (not native selects)
 */
import { useState, useRef, useEffect } from 'react'
import { Search, ChevronDown, Check, X } from 'lucide-react'
import { clsx } from 'clsx'
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

// =============================================================================
// Custom Dropdown Component
// =============================================================================

interface DropdownProps<T extends string> {
  value: T
  options: Array<{ value: T; label: string }>
  onChange: (value: T) => void
  placeholder?: string
}

function Dropdown<T extends string>({
  value,
  options,
  onChange,
  placeholder = 'Select...',
}: DropdownProps<T>) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Close on Escape
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  const selectedOption = options.find((opt) => opt.value === value)
  const isFiltered = value !== 'all'

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium',
          'border transition-all duration-200',
          'focus:outline-none',
          isFiltered
            ? 'bg-synapse/15 border-synapse/40 text-synapse'
            : 'bg-slate-dark border-slate-mid hover:border-slate-light text-text-primary',
          isOpen && 'border-synapse ring-1 ring-synapse/30'
        )}
      >
        <span>{selectedOption?.label || placeholder}</span>
        <ChevronDown
          className={clsx(
            'w-4 h-4 transition-transform duration-200',
            isOpen && 'rotate-180'
          )}
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className={clsx(
            'absolute top-full mt-2 left-0 min-w-[180px] py-1.5',
            'bg-slate-darker/95 backdrop-blur-xl',
            'border border-slate-mid/40 rounded-xl',
            'shadow-xl shadow-black/40',
            'z-[100] overflow-hidden',
            'animate-in fade-in slide-in-from-top-2 duration-150'
          )}
        >
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                onChange(option.value)
                setIsOpen(false)
              }}
              className={clsx(
                'w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left',
                'transition-colors duration-150',
                option.value === value
                  ? 'bg-synapse/20 text-synapse'
                  : 'text-text-secondary hover:bg-slate-mid/40 hover:text-text-primary'
              )}
            >
              <span className="flex-1">{option.label}</span>
              {option.value === value && (
                <Check className="w-4 h-4 flex-shrink-0" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Active Filter Chip
// =============================================================================

interface FilterChipProps {
  label: string
  onClear: () => void
}

function FilterChip({ label, onClear }: FilterChipProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm',
        'bg-synapse/15 border border-synapse/40 text-synapse',
        'group cursor-pointer hover:bg-synapse/25 transition-colors'
      )}
      onClick={onClear}
    >
      <span>{label}</span>
      <X className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition-opacity" />
    </span>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function InventoryFilters({ filters, onChange }: InventoryFiltersProps) {
  const hasActiveFilters =
    filters.kind !== 'all' || filters.status !== 'all' || filters.location !== 'all'

  const clearAllFilters = () => {
    onChange({
      ...filters,
      kind: 'all',
      status: 'all',
      location: 'all',
    })
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Main Filter Row */}
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
        <Dropdown<AssetKind | 'all'>
          value={filters.kind}
          options={KIND_OPTIONS}
          onChange={(kind) => onChange({ ...filters, kind })}
          placeholder="All Types"
        />

        {/* Status filter */}
        <Dropdown<BlobStatus | 'all'>
          value={filters.status}
          options={STATUS_OPTIONS}
          onChange={(status) => onChange({ ...filters, status })}
          placeholder="All Status"
        />

        {/* Location filter */}
        <Dropdown<BlobLocation | 'all'>
          value={filters.location}
          options={LOCATION_OPTIONS}
          onChange={(location) => onChange({ ...filters, location })}
          placeholder="All Locations"
        />
      </div>

      {/* Active Filters Row (shown when filters are active) */}
      {hasActiveFilters && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-text-muted mr-1">Active filters:</span>

          {filters.kind !== 'all' && (
            <FilterChip
              label={KIND_OPTIONS.find((o) => o.value === filters.kind)?.label || filters.kind}
              onClear={() => onChange({ ...filters, kind: 'all' })}
            />
          )}

          {filters.status !== 'all' && (
            <FilterChip
              label={STATUS_OPTIONS.find((o) => o.value === filters.status)?.label || filters.status}
              onClear={() => onChange({ ...filters, status: 'all' })}
            />
          )}

          {filters.location !== 'all' && (
            <FilterChip
              label={LOCATION_OPTIONS.find((o) => o.value === filters.location)?.label || filters.location}
              onClear={() => onChange({ ...filters, location: 'all' })}
            />
          )}

          <button
            onClick={clearAllFilters}
            className="text-xs text-red-400 hover:text-red-300 ml-2 hover:underline"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  )
}
