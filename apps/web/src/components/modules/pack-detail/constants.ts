/**
 * Pack Detail Constants
 *
 * Animation configurations, default values, and shared constants
 * for the pack-detail module.
 */

import type { CardSize, AssetType } from './types'

// =============================================================================
// Animation Configuration
// =============================================================================

/**
 * Animation durations in milliseconds
 */
export const ANIMATION_DURATION = {
  fast: 150,      // Hover, press feedback
  normal: 300,    // Section transitions
  slow: 500,      // Page transitions, modals
} as const

/**
 * CSS easing functions
 */
export const ANIMATION_EASING = {
  easeOut: 'cubic-bezier(0.0, 0.0, 0.2, 1)',
  easeIn: 'cubic-bezier(0.4, 0.0, 1, 1)',
  easeInOut: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
  spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
} as const

/**
 * Tailwind animation presets
 * Use these directly in className for consistent animations
 */
export const ANIMATION_PRESETS = {
  // Fade animations
  fadeIn: 'animate-in fade-in duration-300',
  fadeOut: 'animate-out fade-out duration-200',

  // Slide animations
  slideUp: 'animate-in slide-in-from-bottom-4 duration-300',
  slideDown: 'animate-in slide-in-from-top-4 duration-300',
  slideRight: 'animate-in slide-in-from-left-4 duration-300',
  slideLeft: 'animate-in slide-in-from-right-4 duration-300',

  // Combined animations
  fadeSlideUp: 'animate-in fade-in slide-in-from-bottom-4 duration-300',
  fadeSlideDown: 'animate-in fade-in slide-in-from-top-4 duration-300',

  // Scale animations
  scaleIn: 'animate-in zoom-in-95 duration-200',
  scaleOut: 'animate-out zoom-out-95 duration-150',

  // Section entrance (staggered)
  sectionEnter: 'animate-in fade-in slide-in-from-bottom-2 duration-300',

  // Modal animations
  modalEnter: 'animate-in fade-in zoom-in-95 duration-300',
  modalExit: 'animate-out fade-out zoom-out-95 duration-200',

  // Backdrop
  backdropEnter: 'animate-in fade-in duration-200',
  backdropExit: 'animate-out fade-out duration-150',
} as const

// =============================================================================
// Gallery Grid Configuration
// =============================================================================

/**
 * Grid classes for different card sizes
 */
export const GRID_CLASSES: Record<CardSize, string> = {
  xs: 'grid-cols-10 gap-1',
  sm: 'grid-cols-8 gap-2',
  md: 'grid-cols-6 gap-3',
  lg: 'grid-cols-4 gap-4',
  xl: 'grid-cols-3 gap-5',
}

/**
 * Default card size
 */
export const DEFAULT_CARD_SIZE: CardSize = 'sm'

// =============================================================================
// Asset Type Configuration
// =============================================================================

/**
 * Asset type icons (Lucide icon names)
 */
export const ASSET_TYPE_ICONS: Record<AssetType | string, string> = {
  checkpoint: 'Database',
  lora: 'Sparkles',
  vae: 'Palette',
  embedding: 'Tag',
  controlnet: 'GitBranch',
  upscaler: 'ZoomIn',
  other: 'File',
}

/**
 * Asset type display names
 */
export const ASSET_TYPE_LABELS: Record<AssetType | string, string> = {
  checkpoint: 'Checkpoint',
  lora: 'LoRA',
  vae: 'VAE',
  embedding: 'Embedding',
  controlnet: 'ControlNet',
  upscaler: 'Upscaler',
  other: 'Other',
}

/**
 * Asset type colors (Tailwind classes)
 */
export const ASSET_TYPE_COLORS: Record<AssetType | string, string> = {
  checkpoint: 'text-blue-400 bg-blue-500/10',
  lora: 'text-purple-400 bg-purple-500/10',
  vae: 'text-green-400 bg-green-500/10',
  embedding: 'text-yellow-400 bg-yellow-500/10',
  controlnet: 'text-pink-400 bg-pink-500/10',
  upscaler: 'text-cyan-400 bg-cyan-500/10',
  other: 'text-gray-400 bg-gray-500/10',
}

// =============================================================================
// Status Configuration
// =============================================================================

/**
 * Asset status icons
 */
export const STATUS_ICONS = {
  installed: 'CheckCircle',
  pending: 'Clock',
  downloading: 'Loader2',
  error: 'AlertCircle',
  unresolved: 'HelpCircle',
} as const

/**
 * Asset status colors
 */
export const STATUS_COLORS = {
  installed: 'text-green-400',
  pending: 'text-yellow-400',
  downloading: 'text-blue-400',
  error: 'text-red-400',
  unresolved: 'text-gray-400',
} as const

// =============================================================================
// Edit Mode Styling
// =============================================================================

/**
 * Editable element styling classes
 */
export const EDITABLE_CLASSES = {
  idle: 'cursor-pointer hover:bg-white/5 transition-colors rounded-lg',
  hover: 'ring-1 ring-synapse/30',
  editing: 'ring-2 ring-synapse bg-synapse/5',
  error: 'ring-2 ring-red-500 bg-red-500/5',
  disabled: 'opacity-50 cursor-not-allowed',
} as const

// =============================================================================
// Section Configuration
// =============================================================================

/**
 * Section identifiers and their display names
 */
export const SECTION_CONFIG = {
  header: {
    id: 'header',
    title: 'Pack Header',
    icon: 'Package',
  },
  gallery: {
    id: 'gallery',
    title: 'Previews',
    icon: 'Image',
  },
  info: {
    id: 'info',
    title: 'Information',
    icon: 'Info',
  },
  dependencies: {
    id: 'dependencies',
    title: 'Dependencies',
    icon: 'Package',
  },
  workflows: {
    id: 'workflows',
    title: 'Workflows',
    icon: 'GitBranch',
  },
  parameters: {
    id: 'parameters',
    title: 'Parameters',
    icon: 'Sliders',
  },
  storage: {
    id: 'storage',
    title: 'Storage & Backup',
    icon: 'HardDrive',
  },
  scripts: {
    id: 'scripts',
    title: 'Scripts',
    icon: 'Terminal',
  },
} as const

// =============================================================================
// i18n Preparation
// =============================================================================

/**
 * Translation keys for pack detail
 * This is a placeholder for future i18n integration.
 * Currently returns the key as-is.
 */
const translations: Record<string, string> = {
  // Headers
  'pack.header.title': 'Pack Details',
  'pack.gallery.title': 'Previews',
  'pack.gallery.empty': 'No previews available',
  'pack.dependencies.title': 'Dependencies',
  'pack.dependencies.empty': 'No dependencies',
  'pack.dependencies.count': '{count} dependencies',
  'pack.workflows.title': 'Workflows',
  'pack.workflows.empty': 'No workflows',
  'pack.parameters.title': 'Parameters',
  'pack.parameters.empty': 'No parameters set',
  'pack.info.title': 'Information',
  'pack.storage.title': 'Storage & Backup',
  'pack.scripts.title': 'Scripts',

  // Actions
  'pack.actions.edit': 'Edit',
  'pack.actions.save': 'Save',
  'pack.actions.cancel': 'Cancel',
  'pack.actions.delete': 'Delete',
  'pack.actions.download': 'Download',
  'pack.actions.downloadAll': 'Download All',
  'pack.actions.use': 'Use Pack',
  'pack.actions.checkUpdates': 'Check Updates',

  // Status
  'pack.status.installed': 'Installed',
  'pack.status.pending': 'Pending',
  'pack.status.downloading': 'Downloading...',
  'pack.status.error': 'Error',

  // Empty states
  'pack.empty.gallery.title': 'No Previews',
  'pack.empty.gallery.description': 'Add preview images or videos to showcase this pack.',
  'pack.empty.dependencies.title': 'No Dependencies',
  'pack.empty.dependencies.description': 'Add models, LoRAs, or other assets to this pack.',
  'pack.empty.workflows.title': 'No Workflows',
  'pack.empty.workflows.description': 'Add ComfyUI workflows to this pack.',
}

/**
 * Translation function placeholder
 * Will be replaced with proper i18n library later
 */
export function t(key: string, params?: Record<string, string | number>): string {
  let text = translations[key] ?? key

  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(`{${k}}`, String(v))
    })
  }

  return text
}

// =============================================================================
// Defaults
// =============================================================================

/**
 * Default modal state (all closed)
 */
export const DEFAULT_MODAL_STATE = {
  editPack: false,
  editParameters: false,
  editPreviews: false,
  editDependencies: false,
  editWorkflows: false,
  uploadWorkflow: false,
  baseModelResolver: false,
  importModel: false,
  markdownEditor: false,
  scriptConsole: false,
  confirmDelete: false,
  pullConfirm: false,
  pushConfirm: false,
} as const

/**
 * Default edit state
 */
export const DEFAULT_EDIT_STATE = {
  isEditing: false,
  editingSection: null,
  hasUnsavedChanges: false,
  pendingChanges: {},
  errors: {},
} as const

// =============================================================================
// Query Keys
// =============================================================================

/**
 * TanStack Query keys for pack data
 */
export const QUERY_KEYS = {
  pack: (name: string) => ['pack', name] as const,
  packLock: (name: string) => ['pack-lock', name] as const,
  packBackup: (name: string) => ['pack-backup-status', name] as const,
  localModels: (type: string) => ['local-models', type] as const,
  baseModelSearch: (source: string, query: string) => ['base-model-search', source, query] as const,
  downloads: ['downloads'] as const,
} as const
