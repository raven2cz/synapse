/**
 * Pack Detail Plugins
 *
 * Type-specific plugins for pack behavior customization.
 *
 * AVAILABLE PLUGINS:
 * - CivitaiPlugin: For packs imported from Civitai (update checking, view on Civitai)
 * - CustomPlugin: For locally created packs (full editability)
 * - InstallPlugin: For installation packs (PROTOTYPE - script management)
 *
 * USAGE:
 * ```tsx
 * import { usePackPlugin } from './pack-detail'
 *
 * function PackDetailPage() {
 *   const { plugin, context } = usePackPlugin({ pack, isEditing, ... })
 *
 *   return (
 *     <>
 *       {plugin?.renderHeaderActions?.(context)}
 *       {plugin?.renderExtraSections?.(context)}
 *     </>
 *   )
 * }
 * ```
 */

// Types
export type {
  PackPlugin,
  PluginContext,
  PluginBadge,
  PluginFeatures,
  PluginRegistration,
  PluginRegistryConfig,
  UsePackPluginReturn,
  // Update types (Civitai)
  UpdateCheckResponse,
  UpdatePlan,
  UpdateChange,
  UpdateCandidate,
  AmbiguousUpdate,
  UpdateResult,
  // Pack dependency types (Custom)
  PackDependencyStatus,
} from './types'

// Hook
export {
  usePackPlugin,
  PLUGIN_REGISTRY,
  type UsePackPluginOptions,
} from './usePackPlugin'

// Plugins
export { CivitaiPlugin } from './CivitaiPlugin'
export { CustomPlugin } from './CustomPlugin'
export { InstallPlugin } from './InstallPlugin'
