/**
 * SearchFilters - Floating Chips Component
 *
 * Phase 5: Premium filter UI for BrowsePage with animated chips.
 * Supports search provider selection, sort, period, and base model filters.
 */

import { useState, useEffect, useRef, createContext, useContext } from 'react'
import { Zap, Globe, Archive, ChevronDown, X, Plus, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import type { SearchProvider, SortOption, PeriodOption } from '@/lib/api/searchTypes'
import {
  PROVIDER_CONFIGS,
  SORT_OPTIONS,
  PERIOD_OPTIONS,
  BASE_MODEL_OPTIONS,
} from '@/lib/api/searchTypes'
import { isProviderAvailable } from '@/lib/api/searchAdapters'

// =============================================================================
// Types
// =============================================================================

interface SearchFiltersProps {
  provider: SearchProvider
  onProviderChange: (provider: SearchProvider) => void
  sortBy: SortOption
  onSortChange: (sort: SortOption) => void
  period: PeriodOption
  onPeriodChange: (period: PeriodOption) => void
  baseModel: string
  onBaseModelChange: (model: string) => void
  isLoading?: boolean
  disabled?: boolean
}

// =============================================================================
// Dropdown Component
// =============================================================================

// Context for closing dropdown from items
const DropdownContext = createContext<{ close: () => void } | null>(null)

interface DropdownProps {
  trigger: React.ReactNode
  children: React.ReactNode
  align?: 'left' | 'center' | 'right'
}

function Dropdown({ trigger, children, align = 'center' }: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const alignClass = {
    left: 'left-0',
    center: 'left-1/2 -translate-x-1/2',
    right: 'right-0',
  }[align]

  const close = () => setIsOpen(false)

  return (
    <div className="relative" ref={dropdownRef}>
      <div onClick={() => setIsOpen(!isOpen)}>{trigger}</div>
      {isOpen && (
        <DropdownContext.Provider value={{ close }}>
          <div
            className={clsx(
              'absolute top-full mt-2 min-w-[180px] p-1.5',
              'bg-slate-darker/95 backdrop-blur-xl',
              'border border-slate-mid/30 rounded-xl',
              'shadow-xl shadow-black/30',
              'animate-in fade-in slide-in-from-top-2 duration-150',
              'z-[9999]',
              alignClass
            )}
          >
            {children}
          </div>
        </DropdownContext.Provider>
      )}
    </div>
  )
}

interface DropdownItemProps {
  children: React.ReactNode
  selected?: boolean
  onClick: () => void
}

function DropdownItem({ children, selected, onClick }: DropdownItemProps) {
  const dropdown = useContext(DropdownContext)

  const handleClick = () => {
    onClick()
    dropdown?.close()
  }

  return (
    <button
      onClick={handleClick}
      className={clsx(
        'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-left',
        'transition-colors duration-150',
        selected
          ? 'bg-synapse/20 text-synapse'
          : 'text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary'
      )}
    >
      {children}
      {selected && (
        <svg className="w-4 h-4 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      )}
    </button>
  )
}

// =============================================================================
// Chip Components
// =============================================================================

interface ChipProps {
  children: React.ReactNode
  variant?: 'provider' | 'filter' | 'active' | 'add'
  onClick?: () => void
  className?: string
}

function Chip({ children, variant = 'filter', onClick, className }: ChipProps) {
  const baseClasses = clsx(
    'inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium',
    'cursor-pointer select-none transition-all duration-200',
    'active:scale-[0.97]'
  )

  const variantClasses = {
    provider: clsx(
      'bg-gradient-to-r from-synapse/15 to-pulse/15',
      'border border-synapse/40',
      'text-synapse-light',
      'hover:border-synapse/60 hover:shadow-lg hover:shadow-synapse/20',
      'hover:-translate-y-0.5'
    ),
    filter: clsx(
      'bg-slate-dark/80 border border-slate-mid/50',
      'text-text-secondary',
      'hover:border-slate-light/60 hover:text-text-primary',
      'hover:-translate-y-0.5 hover:shadow-md'
    ),
    active: clsx(
      'bg-synapse/15 border border-synapse/40',
      'text-synapse',
      'hover:bg-synapse/25'
    ),
    add: clsx(
      'bg-transparent border border-dashed border-slate-mid/50',
      'text-text-muted',
      'hover:border-synapse/40 hover:text-synapse hover:border-solid'
    ),
  }

  return (
    <button onClick={onClick} className={clsx(baseClasses, variantClasses[variant], className)}>
      {children}
    </button>
  )
}

// =============================================================================
// Status Badge
// =============================================================================

interface StatusBadgeProps {
  provider: SearchProvider
  isLoading?: boolean
}

function StatusBadge({ provider, isLoading }: StatusBadgeProps) {
  const config = PROVIDER_CONFIGS[provider]

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-synapse/10 border border-synapse/30">
        <Loader2 className="w-3 h-3 animate-spin text-synapse" />
        <span className="text-xs text-synapse font-medium">Loading</span>
      </div>
    )
  }

  const colorMap: Record<SearchProvider, string> = {
    trpc: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    rest: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
    archive: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  }

  const dotColorMap: Record<SearchProvider, string> = {
    trpc: 'bg-emerald-400',
    rest: 'bg-blue-400',
    archive: 'bg-amber-400',
  }

  return (
    <div className={clsx('flex items-center gap-2 px-3 py-1.5 rounded-full border', colorMap[provider])}>
      <span className={clsx('w-1.5 h-1.5 rounded-full animate-pulse', dotColorMap[provider])} />
      <span className="text-xs font-medium">{config.statusLabel}</span>
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function SearchFilters({
  provider,
  onProviderChange,
  sortBy,
  onSortChange,
  period,
  onPeriodChange,
  baseModel,
  onBaseModelChange,
  isLoading,
  disabled,
}: SearchFiltersProps) {
  const config = PROVIDER_CONFIGS[provider]
  const trpcAvailable = isProviderAvailable('trpc')

  // Provider colors
  const providerColorMap: Record<SearchProvider, string> = {
    trpc: 'from-synapse/15 to-pulse/15 border-synapse/40 text-synapse-light',
    rest: 'from-blue-500/15 to-cyan-500/15 border-blue-500/40 text-blue-400',
    archive: 'from-amber-500/15 to-orange-500/15 border-amber-500/40 text-amber-400',
  }

  const providerDotMap: Record<SearchProvider, string> = {
    trpc: 'bg-synapse shadow-synapse/50',
    rest: 'bg-blue-400 shadow-blue-400/50',
    archive: 'bg-amber-400 shadow-amber-400/50',
  }

  return (
    <div className={clsx(
      'relative z-50',
      'flex items-center gap-2 flex-wrap p-3',
      'bg-slate-dark/30 backdrop-blur-sm rounded-2xl',
      'border border-slate-mid/20',
      disabled && 'opacity-50 pointer-events-none'
    )}>
      {/* Provider Chip */}
      <Dropdown
        trigger={
          <Chip
            variant="provider"
            className={clsx(
              'bg-gradient-to-r',
              providerColorMap[provider]
            )}
          >
            <span
              className={clsx(
                'w-2 h-2 rounded-full shadow-lg animate-pulse',
                providerDotMap[provider]
              )}
            />
            <span>{config.shortName}</span>
            <ChevronDown className="w-4 h-4 opacity-60" />
          </Chip>
        }
      >
        <DropdownItem
          selected={provider === 'trpc'}
          onClick={() => trpcAvailable && onProviderChange('trpc')}
        >
          <Zap className="w-4 h-4" />
          <span>Internal tRPC</span>
          {!trpcAvailable && (
            <span className="ml-auto text-xs text-text-muted">Unavailable</span>
          )}
        </DropdownItem>
        <DropdownItem selected={provider === 'rest'} onClick={() => onProviderChange('rest')}>
          <Globe className="w-4 h-4" />
          <span>REST API</span>
        </DropdownItem>
        <DropdownItem
          selected={provider === 'archive'}
          onClick={() => onProviderChange('archive')}
        >
          <Archive className="w-4 h-4" />
          <span>CivArchive</span>
        </DropdownItem>
      </Dropdown>

      {/* Divider */}
      <span className="w-1 h-1 rounded-full bg-slate-mid/50" />

      {/* Sort Chip */}
      <Dropdown
        trigger={
          <Chip variant="filter">
            <span>{sortBy}</span>
            <ChevronDown className="w-4 h-4 opacity-50" />
          </Chip>
        }
      >
        {SORT_OPTIONS.map((opt) => (
          <DropdownItem
            key={opt.value}
            selected={sortBy === opt.value}
            onClick={() => onSortChange(opt.value as SortOption)}
          >
            {opt.label}
          </DropdownItem>
        ))}
      </Dropdown>

      {/* Period Chip */}
      <Dropdown
        trigger={
          <Chip variant="filter">
            <span>{PERIOD_OPTIONS.find((p) => p.value === period)?.label || period}</span>
            <ChevronDown className="w-4 h-4 opacity-50" />
          </Chip>
        }
      >
        {PERIOD_OPTIONS.map((opt) => (
          <DropdownItem
            key={opt.value}
            selected={period === opt.value}
            onClick={() => onPeriodChange(opt.value as PeriodOption)}
          >
            {opt.label}
          </DropdownItem>
        ))}
      </Dropdown>

      {/* Base Model - Active Filter or Add Button */}
      {baseModel ? (
        <Chip variant="active" onClick={() => onBaseModelChange('')}>
          <span>{BASE_MODEL_OPTIONS.find((m) => m.value === baseModel)?.label || baseModel}</span>
          <X className="w-4 h-4 opacity-60 hover:opacity-100" />
        </Chip>
      ) : (
        <Dropdown
          trigger={
            <Chip variant="add">
              <Plus className="w-4 h-4" />
              <span>Base Model</span>
            </Chip>
          }
        >
          {BASE_MODEL_OPTIONS.filter((m) => m.value).map((opt) => (
            <DropdownItem
              key={opt.value}
              selected={baseModel === opt.value}
              onClick={() => onBaseModelChange(opt.value)}
            >
              {opt.label}
            </DropdownItem>
          ))}
        </Dropdown>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Status Badge */}
      <StatusBadge provider={provider} isLoading={isLoading} />
    </div>
  )
}
