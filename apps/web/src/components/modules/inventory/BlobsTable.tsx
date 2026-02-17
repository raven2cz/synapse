/**
 * BlobsTable - MAIN COMPONENT for inventory display
 *
 * Features:
 * - Sortable columns (Name, Size, Status, Location)
 * - Row selection with bulk actions
 * - Quick actions (Backup, Restore, Delete)
 * - Context menu with full action set
 */
import { useState, useMemo, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { clsx } from 'clsx'
import {
  Upload,
  Download,
  Trash2,
  MoreHorizontal,
  Copy,
  Info,
  RefreshCw,
  ChevronUp,
  ChevronDown,
  Loader2,
  AlertTriangle,
  Check,
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { LocationIcon } from './LocationIcon'
import { StatusBadge } from './StatusBadge'
import { AssetKindIcon, getKindLabel } from './AssetKindIcon'
import { formatBytes, copyToClipboard } from './utils'
import type { InventoryItem, BulkAction } from './types'

interface BlobsTableProps {
  items: InventoryItem[]
  backupEnabled: boolean
  backupConnected: boolean
  onBackup: (sha256: string) => Promise<void>
  onRestore: (sha256: string) => Promise<void>
  onDelete: (sha256: string, target: 'local' | 'backup' | 'both') => void
  onShowImpacts: (item: InventoryItem) => void
  onBulkAction: (sha256s: string[], action: BulkAction) => void
  isLoading?: boolean
}

type SortKey = 'display_name' | 'size_bytes' | 'status' | 'location' | 'kind'
type SortDirection = 'asc' | 'desc'

export function BlobsTable({
  items,
  backupEnabled,
  backupConnected,
  onBackup,
  onRestore,
  onDelete,
  onShowImpacts,
  onBulkAction,
  isLoading,
}: BlobsTableProps) {
  const { t } = useTranslation()
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())
  const [sortConfig, setSortConfig] = useState<{ key: SortKey; direction: SortDirection }>({
    key: 'size_bytes',
    direction: 'desc',
  })
  // Track which row's context menu is open (exclusive - only one at a time)
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)

  // Sorting
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const { key, direction } = sortConfig
      let aVal: string | number = a[key] as string | number
      let bVal: string | number = b[key] as string | number

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return direction === 'asc' ? aVal - bVal : bVal - aVal
      }

      const aStr = String(aVal).toLowerCase()
      const bStr = String(bVal).toLowerCase()
      const cmp = aStr.localeCompare(bStr)
      return direction === 'asc' ? cmp : -cmp
    })
  }, [items, sortConfig])

  // Selection helpers
  const allSelected = selectedItems.size === items.length && items.length > 0
  const someSelected = selectedItems.size > 0 && !allSelected

  const toggleAll = () => {
    if (allSelected) {
      setSelectedItems(new Set())
    } else {
      setSelectedItems(new Set(items.map((i) => i.sha256)))
    }
  }

  const toggleItem = (sha256: string) => {
    const newSet = new Set(selectedItems)
    if (newSet.has(sha256)) {
      newSet.delete(sha256)
    } else {
      newSet.add(sha256)
    }
    setSelectedItems(newSet)
  }

  // Selected items summary
  const selectedSummary = useMemo(() => {
    const selected = items.filter((i) => selectedItems.has(i.sha256))
    return {
      count: selected.length,
      totalBytes: selected.reduce((sum, i) => sum + i.size_bytes, 0),
      canBackup: selected.filter((i) => i.location === 'local_only').length,
      canRestore: selected.filter((i) => i.location === 'backup_only').length,
      canDelete: selected.filter((i) => i.status === 'orphan').length,
      // Blobs that can have local deleted safely (backup exists)
      canFreeLocal: selected.filter((i) => i.on_local && i.on_backup).length,
      canFreeLocalBytes: selected.filter((i) => i.on_local && i.on_backup).reduce((sum, i) => sum + i.size_bytes, 0),
    }
  }, [items, selectedItems])

  const handleSort = (key: SortKey) => {
    if (sortConfig.key === key) {
      setSortConfig({
        key,
        direction: sortConfig.direction === 'asc' ? 'desc' : 'asc',
      })
    } else {
      setSortConfig({ key, direction: 'desc' })
    }
  }

  if (isLoading) {
    return (
      <Card padding="lg" className="flex items-center justify-center py-16">
        <Loader2 className="w-8 h-8 animate-spin text-synapse" />
      </Card>
    )
  }

  if (items.length === 0) {
    return (
      <Card padding="lg" className="text-center py-16">
        <p className="text-text-muted">{t('inventory.table.noItemsFound')}</p>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Bulk Actions Bar */}
      {selectedItems.size > 0 && (
        <Card padding="sm" className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="font-medium text-text-primary">
              {t('inventory.table.selected', { count: selectedSummary.count })}
            </span>
            <span className="text-text-muted">
              ({formatBytes(selectedSummary.totalBytes)})
            </span>
          </div>

          <div className="flex items-center gap-2">
            {backupEnabled && backupConnected && selectedSummary.canBackup > 0 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onBulkAction([...selectedItems], 'backup')}
                leftIcon={<Upload className="w-4 h-4" />}
              >
                {t('inventory.table.backupCount', { count: selectedSummary.canBackup })}
              </Button>
            )}

            {backupEnabled && backupConnected && selectedSummary.canRestore > 0 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onBulkAction([...selectedItems], 'restore')}
                leftIcon={<Download className="w-4 h-4" />}
              >
                {t('inventory.table.restoreCount', { count: selectedSummary.canRestore })}
              </Button>
            )}

            {selectedSummary.canDelete > 0 && (
              <Button
                variant="danger"
                size="sm"
                onClick={() => onBulkAction([...selectedItems], 'delete_local')}
                leftIcon={<Trash2 className="w-4 h-4" />}
              >
                {t('inventory.table.deleteOrphansCount', { count: selectedSummary.canDelete })}
              </Button>
            )}

            {/* Free local space for synced blobs (backup exists, safe to delete local) */}
            {selectedSummary.canFreeLocal > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onBulkAction([...selectedItems], 'delete_local')}
                leftIcon={<Trash2 className="w-4 h-4" />}
                className="text-amber-500 hover:text-amber-400 hover:bg-amber-500/10"
                title={t('inventory.table.freeLocalTitle', { size: formatBytes(selectedSummary.canFreeLocalBytes) })}
              >
                {t('inventory.table.freeLocal', { count: selectedSummary.canFreeLocal })}
              </Button>
            )}

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedItems(new Set())}
            >
              {t('inventory.table.clearSelection')}
            </Button>
          </div>
        </Card>
      )}

      {/* Main Table */}
      <Card padding="none" className="overflow-visible">
        <div className="overflow-x-auto overflow-y-visible">
          <table className="w-full min-w-[900px]">
            <thead>
              <tr className="border-b border-slate-mid/50 bg-slate-deep/50">
                {/* Checkbox */}
                <th className="w-[40px] px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected
                    }}
                    onChange={toggleAll}
                    className="w-4 h-4 rounded border-slate-mid bg-slate-dark text-synapse focus:ring-synapse cursor-pointer"
                  />
                </th>

                {/* Icon */}
                <th className="w-[40px] px-2 py-3"></th>

                {/* Name */}
                <th className="px-4 py-3 text-left">
                  <SortableHeader
                    label={t('inventory.table.name')}
                    sortKey="display_name"
                    currentSort={sortConfig}
                    onSort={handleSort}
                  />
                </th>

                {/* Type */}
                <th className="w-[80px] px-4 py-3 text-left">
                  <SortableHeader
                    label={t('inventory.table.type')}
                    sortKey="kind"
                    currentSort={sortConfig}
                    onSort={handleSort}
                  />
                </th>

                {/* Size */}
                <th className="w-[100px] px-4 py-3 text-right">
                  <SortableHeader
                    label={t('inventory.table.size')}
                    sortKey="size_bytes"
                    currentSort={sortConfig}
                    onSort={handleSort}
                    align="right"
                  />
                </th>

                {/* Status */}
                <th className="w-[110px] px-4 py-3 text-left">
                  <SortableHeader
                    label={t('inventory.table.status')}
                    sortKey="status"
                    currentSort={sortConfig}
                    onSort={handleSort}
                  />
                </th>

                {/* Location */}
                <th className="w-[90px] px-4 py-3 text-left">
                  <SortableHeader
                    label={t('inventory.table.location')}
                    sortKey="location"
                    currentSort={sortConfig}
                    onSort={handleSort}
                  />
                </th>

                {/* Used By */}
                <th className="w-[220px] px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">
                  {t('inventory.table.usedBy')}
                </th>

                {/* Actions - sticky */}
                <th className="w-[130px] px-4 py-3 text-right text-xs font-medium text-text-muted uppercase sticky right-0 bg-slate-deep/95 backdrop-blur-sm shadow-[-8px_0_16px_-8px_rgba(0,0,0,0.3)]">
                  {t('inventory.table.actions')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.map((item) => (
                <BlobRow
                  key={item.sha256}
                  item={item}
                  selected={selectedItems.has(item.sha256)}
                  onToggle={() => toggleItem(item.sha256)}
                  backupEnabled={backupEnabled}
                  backupConnected={backupConnected}
                  onBackup={onBackup}
                  onRestore={onRestore}
                  onDelete={onDelete}
                  onShowImpacts={onShowImpacts}
                  isMenuOpen={openMenuId === item.sha256}
                  onMenuToggle={(open) => setOpenMenuId(open ? item.sha256 : null)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Footer */}
      <div className="flex items-center justify-between text-sm text-text-muted">
        <span>{t('inventory.table.showingItems', { count: items.length })}</span>
        {selectedItems.size > 0 && (
          <span>
            {t('inventory.table.selectedSummary', { count: selectedItems.size, size: formatBytes(selectedSummary.totalBytes) })}
          </span>
        )}
      </div>
    </div>
  )
}

// Sortable header component
function SortableHeader({
  label,
  sortKey,
  currentSort,
  onSort,
  align = 'left',
}: {
  label: string
  sortKey: SortKey
  currentSort: { key: SortKey; direction: SortDirection }
  onSort: (key: SortKey) => void
  align?: 'left' | 'right'
}) {
  const isActive = currentSort.key === sortKey

  return (
    <button
      className={clsx(
        'flex items-center gap-1 text-xs font-medium uppercase',
        isActive ? 'text-synapse' : 'text-text-muted hover:text-text-secondary',
        align === 'right' && 'ml-auto'
      )}
      onClick={() => onSort(sortKey)}
    >
      {label}
      {isActive && (
        currentSort.direction === 'asc' ? (
          <ChevronUp className="w-3 h-3" />
        ) : (
          <ChevronDown className="w-3 h-3" />
        )
      )}
    </button>
  )
}

// Individual row component
function BlobRow({
  item,
  selected,
  onToggle,
  backupEnabled,
  backupConnected,
  onBackup,
  onRestore,
  onDelete,
  onShowImpacts,
  isMenuOpen,
  onMenuToggle,
}: {
  item: InventoryItem
  selected: boolean
  onToggle: () => void
  backupEnabled: boolean
  backupConnected: boolean
  onBackup: (sha256: string) => Promise<void>
  onRestore: (sha256: string) => Promise<void>
  onDelete: (sha256: string, target: 'local' | 'backup' | 'both') => void
  onShowImpacts: (item: InventoryItem) => void
  isMenuOpen: boolean
  onMenuToggle: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const [isLoading, setIsLoading] = useState(false)
  const [copiedSha, setCopiedSha] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 })

  // Update menu position when opening
  useEffect(() => {
    if (isMenuOpen && menuButtonRef.current) {
      const rect = menuButtonRef.current.getBoundingClientRect()
      const menuWidth = 192 // w-48 = 12rem = 192px
      const menuHeight = 200 // approximate height
      const viewportHeight = window.innerHeight

      // Check if menu would go off bottom of viewport
      const wouldOverflowBottom = rect.bottom + menuHeight > viewportHeight

      setMenuPosition({
        top: wouldOverflowBottom ? rect.top - menuHeight : rect.bottom + 4,
        left: rect.right - menuWidth,
      })
    }
  }, [isMenuOpen])

  const handleAction = async (action: () => void | Promise<void>) => {
    setIsLoading(true)
    onMenuToggle(false)
    try {
      await action()
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = (target: 'local' | 'backup' | 'both') => {
    onMenuToggle(false)
    onDelete(item.sha256, target)
  }

  const handleCopySha = async () => {
    await copyToClipboard(item.sha256)
    setCopiedSha(true)
    setTimeout(() => setCopiedSha(false), 2000)
    onMenuToggle(false)
  }

  // Determine quick action button
  const quickAction = useMemo(() => {
    if (item.location === 'local_only' && backupEnabled && backupConnected) {
      return {
        label: t('inventory.table.backup'),
        icon: <Upload className="w-3 h-3" />,
        className: 'text-amber-500 border-amber-500/30 hover:bg-amber-500/10',
        action: () => onBackup(item.sha256),
      }
    }
    if (item.location === 'backup_only' && backupConnected) {
      return {
        label: t('inventory.table.restore'),
        icon: <Download className="w-3 h-3" />,
        className: 'text-blue-500 border-blue-500/30 hover:bg-blue-500/10',
        action: () => onRestore(item.sha256),
      }
    }
    if (item.status === 'orphan' && item.on_local) {
      return {
        label: t('inventory.table.delete'),
        icon: <Trash2 className="w-3 h-3" />,
        className: 'text-red-500 border-red-500/30 hover:bg-red-500/10',
        action: () => onDelete(item.sha256, 'local'),
      }
    }
    return null
  }, [item, backupEnabled, backupConnected, onBackup, onRestore, onDelete])

  return (
    <tr
      className={clsx(
        'border-b border-slate-mid/30 hover:bg-slate-deep/50 transition-colors',
        selected && 'bg-synapse/5'
      )}
    >
      {/* Checkbox */}
      <td className="px-4 py-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          className="w-4 h-4 rounded border-slate-mid bg-slate-dark text-synapse focus:ring-synapse cursor-pointer"
        />
      </td>

      {/* Icon */}
      <td className="px-2 py-3">
        <AssetKindIcon kind={item.kind} />
      </td>

      {/* Name */}
      <td className="px-4 py-3">
        <div className="flex flex-col gap-0.5">
          <span className="font-medium text-text-primary">
            {item.display_name}
          </span>
          {/* Original filename from origin */}
          {item.origin?.filename && item.origin.filename !== item.display_name && (
            <span className="text-xs text-text-secondary">
              {item.origin.filename}
            </span>
          )}
          {/* SHA256 + Civitai link */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted font-mono">
              {item.sha256.slice(0, 12)}...
            </span>
            {item.origin?.provider === 'civitai' && item.origin.model_id && (
              <a
                href={`https://civitai.com/models/${item.origin.model_id}${item.origin.version_id ? `?modelVersionId=${item.origin.version_id}` : ''}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-synapse hover:text-synapse-light hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                Civitai
              </a>
            )}
            {item.origin?.provider === 'huggingface' && item.origin.repo_id && (
              <a
                href={`https://huggingface.co/${item.origin.repo_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-synapse hover:text-synapse-light hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                HuggingFace
              </a>
            )}
          </div>
        </div>
      </td>

      {/* Type */}
      <td className="px-4 py-3">
        <span className="text-xs text-text-secondary px-2 py-0.5 bg-slate-mid/30 rounded">
          {getKindLabel(item.kind)}
        </span>
      </td>

      {/* Size */}
      <td className="px-4 py-3 text-right font-mono text-sm text-text-secondary">
        {item.size_bytes > 0 ? formatBytes(item.size_bytes) : '-'}
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <StatusBadge status={item.status} size="sm" />
      </td>

      {/* Location */}
      <td className="px-4 py-3">
        <LocationIcon location={item.location} size="sm" />
      </td>

      {/* Used By */}
      <td className="px-4 py-3">
        {item.used_by_packs.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {item.used_by_packs.map((pack) => (
              <span
                key={pack}
                className="text-xs px-1.5 py-0.5 bg-slate-mid/30 rounded text-text-secondary whitespace-nowrap"
              >
                {pack}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-text-muted text-sm">-</span>
        )}
      </td>

      {/* Actions - sticky */}
      <td className="px-4 py-3 sticky right-0 bg-slate-dark/95 backdrop-blur-sm shadow-[-8px_0_16px_-8px_rgba(0,0,0,0.3)]">
        <div className="flex items-center justify-end gap-1">
          {/* Quick Action Button */}
          {quickAction && (
            <button
              className={clsx(
                'inline-flex items-center gap-1 px-2 py-1 text-xs rounded border transition-colors',
                quickAction.className,
                isLoading && 'opacity-50 cursor-not-allowed'
              )}
              disabled={isLoading}
              onClick={() => handleAction(quickAction.action)}
            >
              {isLoading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <>
                  {quickAction.icon}
                  {quickAction.label}
                </>
              )}
            </button>
          )}

          {/* Context Menu Button */}
          <button
            ref={menuButtonRef}
            className="p-1.5 rounded hover:bg-slate-mid/50 text-text-muted hover:text-text-primary transition-colors"
            onClick={() => onMenuToggle(!isMenuOpen)}
          >
            <MoreHorizontal className="w-4 h-4" />
          </button>

          {/* Context Menu - rendered via portal for proper z-index */}
          {isMenuOpen && createPortal(
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-[100]"
                onClick={() => onMenuToggle(false)}
              />

              {/* Menu */}
              <div
                className="fixed z-[101] w-48 py-1 bg-slate-dark border border-slate-mid rounded-lg shadow-xl"
                style={{ top: menuPosition.top, left: menuPosition.left }}
              >
                {/* Copy SHA256 */}
                <button
                  className="w-full px-3 py-2 text-left text-sm text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary flex items-center gap-2"
                  onClick={handleCopySha}
                >
                  {copiedSha ? (
                    <Check className="w-4 h-4 text-green-500" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                  {copiedSha ? t('inventory.table.copied') : t('inventory.table.copySha256')}
                </button>

                {/* Show Impacts */}
                {item.status === 'referenced' && (
                  <button
                    className="w-full px-3 py-2 text-left text-sm text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary flex items-center gap-2"
                    onClick={() => {
                      onShowImpacts(item)
                      onMenuToggle(false)
                    }}
                  >
                    <Info className="w-4 h-4" />
                    {t('inventory.table.showImpacts')}
                  </button>
                )}

                <div className="border-t border-slate-mid/50 my-1" />

                {/* Backup/Restore actions */}
                {backupEnabled && backupConnected && (
                  <>
                    {item.location === 'local_only' && (
                      <button
                        className="w-full px-3 py-2 text-left text-sm text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary flex items-center gap-2"
                        onClick={() => handleAction(() => onBackup(item.sha256))}
                      >
                        <Upload className="w-4 h-4" />
                        {t('inventory.table.backupToExternal')}
                      </button>
                    )}

                    {item.location === 'backup_only' && (
                      <button
                        className="w-full px-3 py-2 text-left text-sm text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary flex items-center gap-2"
                        onClick={() => handleAction(() => onRestore(item.sha256))}
                      >
                        <Download className="w-4 h-4" />
                        {t('inventory.table.restoreFromBackup')}
                      </button>
                    )}
                  </>
                )}

                {/* Delete actions */}
                {/* Delete from Local: allowed for orphans OR if backup exists (safe - copy remains) */}
                {item.on_local && (item.status === 'orphan' || item.on_backup) && (
                  <button
                    className="w-full px-3 py-2 text-left text-sm text-red-500 hover:bg-red-500/10 flex items-center gap-2"
                    onClick={() => handleDelete('local')}
                  >
                    <Trash2 className="w-4 h-4" />
                    {t('inventory.table.deleteFromLocal')}
                  </button>
                )}

                {item.on_backup && backupConnected && (
                  <button
                    className="w-full px-3 py-2 text-left text-sm text-red-500 hover:bg-red-500/10 flex items-center gap-2"
                    onClick={() => handleDelete('backup')}
                  >
                    <Trash2 className="w-4 h-4" />
                    {t('inventory.table.deleteFromBackup')}
                  </button>
                )}

                {item.location === 'both' && item.status === 'orphan' && (
                  <button
                    className="w-full px-3 py-2 text-left text-sm text-red-500 hover:bg-red-500/10 flex items-center gap-2"
                    onClick={() => handleDelete('both')}
                  >
                    <AlertTriangle className="w-4 h-4" />
                    {t('inventory.table.deleteEverywhere')}
                  </button>
                )}

                {/* Re-download for missing */}
                {item.status === 'missing' && item.origin && (
                  <button
                    className="w-full px-3 py-2 text-left text-sm text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary flex items-center gap-2"
                    onClick={() => onMenuToggle(false)}
                  >
                    <RefreshCw className="w-4 h-4" />
                    {t('inventory.table.redownloadFrom', { provider: item.origin.provider })}
                  </button>
                )}
              </div>
            </>,
            document.body
          )}
        </div>
      </td>
    </tr>
  )
}
