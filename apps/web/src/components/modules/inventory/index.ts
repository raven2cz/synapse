/**
 * Model Inventory Module
 * Exports all inventory components
 */

// Page and main components
export { InventoryPage } from './InventoryPage'
export { InventoryStats } from './InventoryStats'
export { InventoryFilters } from './InventoryFilters'
export { BlobsTable } from './BlobsTable'

// Icon and badge components
export { LocationIcon } from './LocationIcon'
export { StatusBadge } from './StatusBadge'
export { AssetKindIcon, getKindLabel } from './AssetKindIcon'

// Dialogs and wizards
export { DeleteConfirmationDialog } from './DeleteConfirmationDialog'
export { CleanupWizard } from './CleanupWizard'
export { BackupSyncWizard } from './BackupSyncWizard'
export { ImpactsDialog } from './ImpactsDialog'
export { VerifyProgressDialog } from './VerifyProgressDialog'
export type { VerifyResult } from './VerifyProgressDialog'

export * from './types'
export * from './utils'
