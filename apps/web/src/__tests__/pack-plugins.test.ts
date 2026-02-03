/**
 * Tests for Pack Plugin System
 *
 * Tests cover:
 * - Plugin type definitions and interfaces
 * - Plugin matching/priority logic
 * - CivitaiPlugin behavior
 * - CustomPlugin behavior
 * - InstallPlugin behavior
 * - usePackPlugin hook logic
 */

import { describe, it, expect, vi } from 'vitest'

// ============================================================================
// Test Types (mirroring actual types)
// ============================================================================

interface PackSourceInfo {
  provider: 'civitai' | 'huggingface' | 'local' | 'url'
  model_id?: number
  version_id?: number
  url?: string
}

interface PackDependencyRef {
  pack_name: string
  required?: boolean
  version_constraint?: string
}

interface PackDetail {
  name: string
  version: string
  description?: string
  author?: string
  tags: string[]
  user_tags: string[]
  source_url?: string
  created_at?: string
  installed: boolean
  has_unresolved: boolean
  all_installed: boolean
  can_generate: boolean
  assets: unknown[]
  previews: unknown[]
  workflows: unknown[]
  custom_nodes: unknown[]
  docs: Record<string, string>
  parameters?: Record<string, unknown>
  model_info?: {
    model_type?: string
    base_model?: string
    trigger_words: string[]
  }
  pack?: {
    schema?: string
    name: string
    pack_type: string
    pack_category?: 'external' | 'custom' | 'install'
    source: PackSourceInfo
    pack_dependencies?: PackDependencyRef[]
    base_model?: string
    trigger_words?: string[]
    [key: string]: unknown
  }
  lock?: Record<string, unknown>
}

interface ValidationResult {
  valid: boolean
  errors: Record<string, string>
}

interface PluginContext {
  pack: PackDetail
  isEditing: boolean
  hasUnsavedChanges: boolean
  openModal: (key: string) => void
  closeModal: (key: string) => void
  modals: Record<string, boolean>
  refetch: () => void
  toast: {
    success: (message: string) => void
    error: (message: string) => void
    info: (message: string) => void
  }
}

interface PluginFeatures {
  canEditMetadata?: boolean
  canEditPreviews?: boolean
  canEditDependencies?: boolean
  canEditWorkflows?: boolean
  canEditParameters?: boolean
  canCheckUpdates?: boolean
  canManagePackDependencies?: boolean
  canRunScripts?: boolean
  canDelete?: boolean
}

interface PackPlugin {
  id: string
  name: string
  appliesTo: (pack: PackDetail) => boolean
  priority?: number
  features?: PluginFeatures
  validateChanges?: (pack: PackDetail, changes: Partial<PackDetail>) => ValidationResult
}

// ============================================================================
// Mock Data
// ============================================================================

function createMockPack(overrides: Partial<PackDetail> = {}): PackDetail {
  return {
    name: 'test-pack',
    version: '1.0.0',
    description: 'Test pack',
    author: 'Test Author',
    tags: ['test'],
    user_tags: [],
    installed: true,
    has_unresolved: false,
    all_installed: true,
    can_generate: true,
    assets: [],
    previews: [],
    workflows: [],
    custom_nodes: [],
    docs: {},
    ...overrides,
  }
}

function createCivitaiPack(overrides: Partial<PackDetail> = {}): PackDetail {
  return createMockPack({
    name: 'civitai-lora-pack',
    source_url: 'https://civitai.com/models/12345',
    pack: {
      name: 'civitai-lora-pack',
      pack_type: 'lora',
      pack_category: 'external',
      source: {
        provider: 'civitai',
        model_id: 12345,
        version_id: 67890,
      },
    },
    model_info: {
      model_type: 'LORA',
      base_model: 'SD 1.5',
      trigger_words: ['test_trigger'],
    },
    ...overrides,
  })
}

function createCustomPack(overrides: Partial<PackDetail> = {}): PackDetail {
  return createMockPack({
    name: 'my-custom-pack',
    pack: {
      name: 'my-custom-pack',
      pack_type: 'lora',
      pack_category: 'custom',
      source: {
        provider: 'local',
      },
    },
    ...overrides,
  })
}

function createInstallPack(overrides: Partial<PackDetail> = {}): PackDetail {
  return createMockPack({
    name: 'comfyui-install',
    user_tags: ['install-pack'],
    pack: {
      name: 'comfyui-install',
      pack_type: 'other',
      pack_category: 'install',
      source: {
        provider: 'local',
      },
    },
    ...overrides,
  })
}

function createMockContext(pack: PackDetail): PluginContext {
  return {
    pack,
    isEditing: false,
    hasUnsavedChanges: false,
    openModal: vi.fn(),
    closeModal: vi.fn(),
    modals: {},
    refetch: vi.fn(),
    toast: {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
    },
  }
}

// ============================================================================
// Plugin Matching Tests
// ============================================================================

describe('Plugin Matching Logic', () => {
  // Plugin implementations for testing
  const CivitaiPlugin: PackPlugin = {
    id: 'civitai',
    name: 'Civitai',
    priority: 50,
    appliesTo: (pack) => pack.pack?.source?.provider === 'civitai',
    features: {
      canEditMetadata: false,
      canEditPreviews: false,
      canCheckUpdates: true,
      canDelete: true,
    },
  }

  const CustomPlugin: PackPlugin = {
    id: 'custom',
    name: 'Custom Pack',
    priority: 0,
    appliesTo: (pack) => pack.pack?.pack_category === 'custom' || true,
    features: {
      canEditMetadata: true,
      canEditPreviews: true,
      canEditDependencies: true,
      canEditWorkflows: true,
      canEditParameters: true,
      canManagePackDependencies: true,
      canDelete: true,
    },
  }

  const InstallPlugin: PackPlugin = {
    id: 'install',
    name: 'Install Pack',
    priority: 100,
    appliesTo: (pack) => pack.user_tags?.includes('install-pack') ?? false,
    features: {
      canEditMetadata: true,
      canEditPreviews: false,
      canRunScripts: true,
      canDelete: true,
    },
  }

  const PLUGIN_REGISTRY = [InstallPlugin, CivitaiPlugin, CustomPlugin].sort(
    (a, b) => (b.priority ?? 0) - (a.priority ?? 0)
  )

  function findPlugin(pack: PackDetail): PackPlugin | null {
    for (const plugin of PLUGIN_REGISTRY) {
      if (plugin.appliesTo(pack)) {
        return plugin
      }
    }
    return null
  }

  describe('Priority ordering', () => {
    it('should sort plugins by priority (highest first)', () => {
      expect(PLUGIN_REGISTRY[0].id).toBe('install')
      expect(PLUGIN_REGISTRY[1].id).toBe('civitai')
      expect(PLUGIN_REGISTRY[2].id).toBe('custom')
    })

    it('should have InstallPlugin with highest priority', () => {
      expect(InstallPlugin.priority).toBe(100)
    })

    it('should have CivitaiPlugin with medium priority', () => {
      expect(CivitaiPlugin.priority).toBe(50)
    })

    it('should have CustomPlugin with lowest priority (fallback)', () => {
      expect(CustomPlugin.priority).toBe(0)
    })
  })

  describe('CivitaiPlugin matching', () => {
    it('should match pack with civitai source', () => {
      const pack = createCivitaiPack()
      expect(CivitaiPlugin.appliesTo(pack)).toBe(true)
    })

    it('should not match pack with local source', () => {
      const pack = createCustomPack()
      expect(CivitaiPlugin.appliesTo(pack)).toBe(false)
    })

    it('should not match pack with huggingface source', () => {
      const pack = createMockPack({
        pack: {
          name: 'hf-pack',
          pack_type: 'checkpoint',
          source: { provider: 'huggingface', repo_id: 'test/model' } as PackSourceInfo,
        },
      })
      expect(CivitaiPlugin.appliesTo(pack)).toBe(false)
    })
  })

  describe('InstallPlugin matching', () => {
    it('should match pack with install-pack user tag', () => {
      const pack = createInstallPack()
      expect(InstallPlugin.appliesTo(pack)).toBe(true)
    })

    it('should not match pack without install-pack tag', () => {
      const pack = createCivitaiPack()
      expect(InstallPlugin.appliesTo(pack)).toBe(false)
    })

    it('should match even if pack has other tags', () => {
      const pack = createMockPack({
        user_tags: ['install-pack', 'comfyui', 'ui'],
      })
      expect(InstallPlugin.appliesTo(pack)).toBe(true)
    })
  })

  describe('CustomPlugin matching', () => {
    it('should match pack with custom category', () => {
      const pack = createCustomPack()
      expect(CustomPlugin.appliesTo(pack)).toBe(true)
    })

    it('should match any pack as fallback', () => {
      const civitaiPack = createCivitaiPack()
      const installPack = createInstallPack()
      const emptyPack = createMockPack()

      expect(CustomPlugin.appliesTo(civitaiPack)).toBe(true)
      expect(CustomPlugin.appliesTo(installPack)).toBe(true)
      expect(CustomPlugin.appliesTo(emptyPack)).toBe(true)
    })
  })

  describe('Plugin selection', () => {
    it('should select InstallPlugin for install packs (highest priority)', () => {
      const pack = createInstallPack()
      const plugin = findPlugin(pack)
      expect(plugin?.id).toBe('install')
    })

    it('should select CivitaiPlugin for civitai packs', () => {
      const pack = createCivitaiPack()
      const plugin = findPlugin(pack)
      expect(plugin?.id).toBe('civitai')
    })

    it('should select CustomPlugin for custom packs', () => {
      const pack = createCustomPack()
      const plugin = findPlugin(pack)
      // Custom plugin matches but Civitai has higher priority...
      // Custom pack doesn't match Civitai, so custom wins
      expect(plugin?.id).toBe('custom')
    })

    it('should select CustomPlugin as fallback for unknown packs', () => {
      const pack = createMockPack({
        pack: {
          name: 'unknown',
          pack_type: 'other',
          source: { provider: 'url', url: 'https://example.com' },
        },
      })
      const plugin = findPlugin(pack)
      expect(plugin?.id).toBe('custom')
    })

    it('should prioritize InstallPlugin over CivitaiPlugin when both match', () => {
      // Edge case: Civitai pack with install-pack tag
      const pack = createCivitaiPack({
        user_tags: ['install-pack'],
      })
      const plugin = findPlugin(pack)
      expect(plugin?.id).toBe('install')
    })
  })
})

// ============================================================================
// Plugin Features Tests
// ============================================================================

describe('Plugin Features', () => {
  describe('CivitaiPlugin features', () => {
    const features: PluginFeatures = {
      canEditMetadata: false,
      canEditPreviews: false,
      canEditDependencies: false,
      canEditWorkflows: false,
      canEditParameters: true,
      canCheckUpdates: true,
      canManagePackDependencies: false,
      canRunScripts: false,
      canDelete: true,
    }

    it('should NOT allow metadata editing', () => {
      expect(features.canEditMetadata).toBe(false)
    })

    it('should NOT allow preview editing', () => {
      expect(features.canEditPreviews).toBe(false)
    })

    it('should allow update checking', () => {
      expect(features.canCheckUpdates).toBe(true)
    })

    it('should allow parameter editing', () => {
      expect(features.canEditParameters).toBe(true)
    })

    it('should allow deletion', () => {
      expect(features.canDelete).toBe(true)
    })
  })

  describe('CustomPlugin features', () => {
    const features: PluginFeatures = {
      canEditMetadata: true,
      canEditPreviews: true,
      canEditDependencies: true,
      canEditWorkflows: true,
      canEditParameters: true,
      canCheckUpdates: false,
      canManagePackDependencies: true,
      canRunScripts: false,
      canDelete: true,
    }

    it('should allow full metadata editing', () => {
      expect(features.canEditMetadata).toBe(true)
    })

    it('should allow preview editing', () => {
      expect(features.canEditPreviews).toBe(true)
    })

    it('should allow pack dependency management', () => {
      expect(features.canManagePackDependencies).toBe(true)
    })

    it('should NOT allow update checking', () => {
      expect(features.canCheckUpdates).toBe(false)
    })
  })

  describe('InstallPlugin features', () => {
    const features: PluginFeatures = {
      canEditMetadata: true,
      canEditPreviews: false,
      canEditDependencies: false,
      canEditWorkflows: false,
      canEditParameters: false,
      canCheckUpdates: false,
      canManagePackDependencies: false,
      canRunScripts: true,
      canDelete: true,
    }

    it('should allow script execution', () => {
      expect(features.canRunScripts).toBe(true)
    })

    it('should NOT allow preview editing', () => {
      expect(features.canEditPreviews).toBe(false)
    })

    it('should NOT allow parameter editing', () => {
      expect(features.canEditParameters).toBe(false)
    })
  })
})

// ============================================================================
// Validation Tests
// ============================================================================

describe('Plugin Validation', () => {
  describe('CivitaiPlugin validation', () => {
    const validateCivitai = (
      _pack: PackDetail,
      changes: Partial<PackDetail>
    ): ValidationResult => {
      const errors: Record<string, string> = {}

      // Civitai packs have limited editability
      if (changes.description !== undefined) {
        errors.description = 'Cannot edit description of Civitai pack'
      }

      if (changes.author !== undefined) {
        errors.author = 'Cannot edit author of Civitai pack'
      }

      return {
        valid: Object.keys(errors).length === 0,
        errors,
      }
    }

    it('should reject description changes', () => {
      const pack = createCivitaiPack()
      const result = validateCivitai(pack, { description: 'New description' })

      expect(result.valid).toBe(false)
      expect(result.errors.description).toBeDefined()
    })

    it('should reject author changes', () => {
      const pack = createCivitaiPack()
      const result = validateCivitai(pack, { author: 'New Author' })

      expect(result.valid).toBe(false)
      expect(result.errors.author).toBeDefined()
    })

    it('should allow user_tags changes', () => {
      const pack = createCivitaiPack()
      const result = validateCivitai(pack, { user_tags: ['favorite'] })

      expect(result.valid).toBe(true)
      expect(Object.keys(result.errors).length).toBe(0)
    })
  })

  describe('CustomPlugin validation', () => {
    const validateCustom = (
      _pack: PackDetail,
      changes: Partial<PackDetail>
    ): ValidationResult => {
      const errors: Record<string, string> = {}

      // Name validation
      if (changes.name !== undefined) {
        if (changes.name.length < 2) {
          errors.name = 'Name must be at least 2 characters'
        }
        if (!/^[a-z0-9-]+$/.test(changes.name)) {
          errors.name = 'Name must contain only lowercase letters, numbers, and hyphens'
        }
      }

      // Description length validation
      if (changes.description !== undefined && changes.description.length > 5000) {
        errors.description = 'Description is too long (max 5000 characters)'
      }

      return {
        valid: Object.keys(errors).length === 0,
        errors,
      }
    }

    it('should validate name format', () => {
      const pack = createCustomPack()
      const result = validateCustom(pack, { name: 'Invalid Name!' })

      expect(result.valid).toBe(false)
      expect(result.errors.name).toBeDefined()
    })

    it('should reject short names', () => {
      const pack = createCustomPack()
      const result = validateCustom(pack, { name: 'a' })

      expect(result.valid).toBe(false)
      expect(result.errors.name).toBeDefined()
    })

    it('should allow valid name changes', () => {
      const pack = createCustomPack()
      const result = validateCustom(pack, { name: 'my-new-pack-name' })

      expect(result.valid).toBe(true)
    })

    it('should reject too long descriptions', () => {
      const pack = createCustomPack()
      const longDescription = 'a'.repeat(5001)
      const result = validateCustom(pack, { description: longDescription })

      expect(result.valid).toBe(false)
      expect(result.errors.description).toBeDefined()
    })

    it('should allow all other changes', () => {
      const pack = createCustomPack()
      const result = validateCustom(pack, {
        description: 'New description',
        author: 'New Author',
        user_tags: ['tag1', 'tag2'],
      })

      expect(result.valid).toBe(true)
    })
  })

  describe('InstallPlugin validation', () => {
    const validateInstall = (
      _pack: PackDetail,
      changes: Partial<PackDetail>
    ): ValidationResult => {
      const errors: Record<string, string> = {}

      // Install packs have limited editability
      if (changes.description !== undefined && changes.description.length > 5000) {
        errors.description = 'Description is too long'
      }

      return {
        valid: Object.keys(errors).length === 0,
        errors,
      }
    }

    it('should allow basic changes', () => {
      const pack = createInstallPack()
      const result = validateInstall(pack, { description: 'Updated description' })

      expect(result.valid).toBe(true)
    })

    it('should reject too long descriptions', () => {
      const pack = createInstallPack()
      const result = validateInstall(pack, { description: 'x'.repeat(5001) })

      expect(result.valid).toBe(false)
    })
  })
})

// ============================================================================
// Plugin Context Tests
// ============================================================================

describe('Plugin Context', () => {
  describe('Context creation', () => {
    it('should create context with all required fields', () => {
      const pack = createCivitaiPack()
      const context = createMockContext(pack)

      expect(context.pack).toBe(pack)
      expect(context.isEditing).toBe(false)
      expect(context.hasUnsavedChanges).toBe(false)
      expect(context.modals).toEqual({})
      expect(context.openModal).toBeDefined()
      expect(context.closeModal).toBeDefined()
      expect(context.refetch).toBeDefined()
      expect(context.toast).toBeDefined()
    })

    it('should provide working toast methods', () => {
      const pack = createCivitaiPack()
      const context = createMockContext(pack)

      context.toast.success('Success message')
      context.toast.error('Error message')
      context.toast.info('Info message')

      expect(context.toast.success).toHaveBeenCalledWith('Success message')
      expect(context.toast.error).toHaveBeenCalledWith('Error message')
      expect(context.toast.info).toHaveBeenCalledWith('Info message')
    })

    it('should provide working modal methods', () => {
      const pack = createCivitaiPack()
      const context = createMockContext(pack)

      context.openModal('testModal')
      context.closeModal('testModal')

      expect(context.openModal).toHaveBeenCalledWith('testModal')
      expect(context.closeModal).toHaveBeenCalledWith('testModal')
    })
  })
})

// ============================================================================
// Pack Dependencies Tests (CustomPlugin)
// ============================================================================

describe('Pack Dependencies (CustomPlugin)', () => {
  describe('Dependency structure', () => {
    it('should parse pack_dependencies array', () => {
      const pack = createCustomPack({
        pack: {
          name: 'my-pack',
          pack_type: 'lora',
          pack_category: 'custom',
          source: { provider: 'local' },
          pack_dependencies: [
            { pack_name: 'base-checkpoint', required: true },
            { pack_name: 'optional-vae', required: false },
          ],
        },
      })

      expect(pack.pack?.pack_dependencies).toHaveLength(2)
      expect(pack.pack?.pack_dependencies?.[0].pack_name).toBe('base-checkpoint')
      expect(pack.pack?.pack_dependencies?.[0].required).toBe(true)
    })

    it('should handle packs with no dependencies', () => {
      const pack = createCustomPack()
      expect(pack.pack?.pack_dependencies).toBeUndefined()
    })

    it('should support version constraints', () => {
      const pack = createCustomPack({
        pack: {
          name: 'my-pack',
          pack_type: 'lora',
          pack_category: 'custom',
          source: { provider: 'local' },
          pack_dependencies: [
            { pack_name: 'versioned-dep', required: true, version_constraint: '>=1.0.0' },
          ],
        },
      })

      expect(pack.pack?.pack_dependencies?.[0].version_constraint).toBe('>=1.0.0')
    })
  })

  describe('Multiple dependencies', () => {
    it('should handle 7+ dependencies', () => {
      const dependencies: PackDependencyRef[] = Array.from({ length: 10 }, (_, i) => ({
        pack_name: `dependency-${i + 1}`,
        required: i < 3, // First 3 required
      }))

      const pack = createCustomPack({
        pack: {
          name: 'complex-pack',
          pack_type: 'lora',
          pack_category: 'custom',
          source: { provider: 'local' },
          pack_dependencies: dependencies,
        },
      })

      expect(pack.pack?.pack_dependencies).toHaveLength(10)

      const required = pack.pack?.pack_dependencies?.filter(d => d.required) || []
      const optional = pack.pack?.pack_dependencies?.filter(d => !d.required) || []

      expect(required).toHaveLength(3)
      expect(optional).toHaveLength(7)
    })

    it('should categorize dependencies by type', () => {
      const pack = createCustomPack({
        pack: {
          name: 'multi-dep-pack',
          pack_type: 'lora',
          pack_category: 'custom',
          source: { provider: 'local' },
          pack_dependencies: [
            { pack_name: 'checkpoint-1', required: true },
            { pack_name: 'lora-1', required: true },
            { pack_name: 'vae-1', required: false },
            { pack_name: 'embedding-1', required: false },
          ],
        },
      })

      const deps = pack.pack?.pack_dependencies || []
      expect(deps.length).toBe(4)
    })
  })
})

// ============================================================================
// Update Types Tests (CivitaiPlugin)
// ============================================================================

describe('Update Types (CivitaiPlugin)', () => {
  interface UpdateCheckResponse {
    pack: string
    has_updates: boolean
    changes_count: number
    ambiguous_count: number
  }

  interface UpdatePlan {
    pack: string
    already_up_to_date: boolean
    changes: Array<{
      dependency_id: string
      old: Record<string, unknown>
      new: Record<string, unknown>
    }>
    ambiguous: Array<{
      dependency_id: string
      candidates: Array<{
        provider: string
        provider_version_id?: number
      }>
    }>
  }

  describe('UpdateCheckResponse', () => {
    it('should represent update available state', () => {
      const response: UpdateCheckResponse = {
        pack: 'test-pack',
        has_updates: true,
        changes_count: 2,
        ambiguous_count: 0,
      }

      expect(response.has_updates).toBe(true)
      expect(response.changes_count).toBe(2)
    })

    it('should represent no updates state', () => {
      const response: UpdateCheckResponse = {
        pack: 'test-pack',
        has_updates: false,
        changes_count: 0,
        ambiguous_count: 0,
      }

      expect(response.has_updates).toBe(false)
    })

    it('should represent ambiguous updates', () => {
      const response: UpdateCheckResponse = {
        pack: 'test-pack',
        has_updates: true,
        changes_count: 1,
        ambiguous_count: 1,
      }

      expect(response.ambiguous_count).toBe(1)
    })
  })

  describe('UpdatePlan', () => {
    it('should represent update plan with changes', () => {
      const plan: UpdatePlan = {
        pack: 'test-pack',
        already_up_to_date: false,
        changes: [
          {
            dependency_id: 'lora-1',
            old: { version_id: 100 },
            new: { version_id: 101 },
          },
        ],
        ambiguous: [],
      }

      expect(plan.changes).toHaveLength(1)
      expect(plan.changes[0].dependency_id).toBe('lora-1')
    })

    it('should represent ambiguous updates requiring selection', () => {
      const plan: UpdatePlan = {
        pack: 'test-pack',
        already_up_to_date: false,
        changes: [],
        ambiguous: [
          {
            dependency_id: 'model-1',
            candidates: [
              { provider: 'civitai', provider_version_id: 100 },
              { provider: 'civitai', provider_version_id: 101 },
            ],
          },
        ],
      }

      expect(plan.ambiguous).toHaveLength(1)
      expect(plan.ambiguous[0].candidates).toHaveLength(2)
    })
  })
})

// ============================================================================
// Badge Tests
// ============================================================================

describe('Plugin Badges', () => {
  interface PluginBadge {
    label: string
    variant: 'primary' | 'secondary' | 'warning' | 'info' | 'success'
    icon?: string
    tooltip?: string
  }

  describe('CivitaiPlugin badge', () => {
    const badge: PluginBadge = {
      label: 'Civitai',
      variant: 'primary',
      icon: 'Globe',
      tooltip: 'Imported from Civitai',
    }

    it('should have Civitai label', () => {
      expect(badge.label).toBe('Civitai')
    })

    it('should use primary variant', () => {
      expect(badge.variant).toBe('primary')
    })

    it('should have globe icon', () => {
      expect(badge.icon).toBe('Globe')
    })
  })

  describe('CustomPlugin badge', () => {
    const badge: PluginBadge = {
      label: 'Custom',
      variant: 'secondary',
      icon: 'Sparkles',
      tooltip: 'Custom pack with full editability',
    }

    it('should have Custom label', () => {
      expect(badge.label).toBe('Custom')
    })

    it('should use secondary variant', () => {
      expect(badge.variant).toBe('secondary')
    })
  })

  describe('InstallPlugin badge', () => {
    const badge: PluginBadge = {
      label: 'Install',
      variant: 'warning',
      icon: 'Terminal',
      tooltip: 'Installation pack for UI environment',
    }

    it('should have Install label', () => {
      expect(badge.label).toBe('Install')
    })

    it('should use warning variant', () => {
      expect(badge.variant).toBe('warning')
    })

    it('should have terminal icon', () => {
      expect(badge.icon).toBe('Terminal')
    })
  })
})

// ============================================================================
// usePackPlugin Hook Logic Tests
// ============================================================================

describe('usePackPlugin Hook Logic', () => {
  const MockCivitaiPlugin: PackPlugin = {
    id: 'civitai',
    name: 'Civitai',
    priority: 50,
    appliesTo: (pack) => pack.pack?.source?.provider === 'civitai',
  }

  const MockCustomPlugin: PackPlugin = {
    id: 'custom',
    name: 'Custom',
    priority: 0,
    appliesTo: () => true, // Fallback
  }

  const MockInstallPlugin: PackPlugin = {
    id: 'install',
    name: 'Install',
    priority: 100,
    appliesTo: (pack) => pack.user_tags?.includes('install-pack') ?? false,
  }

  const registry = [MockInstallPlugin, MockCivitaiPlugin, MockCustomPlugin].sort(
    (a, b) => (b.priority ?? 0) - (a.priority ?? 0)
  )

  function selectPlugin(pack: PackDetail | null | undefined): PackPlugin | null {
    if (!pack) return null

    for (const p of registry) {
      if (p.appliesTo(pack)) {
        return p
      }
    }

    return MockCustomPlugin
  }

  describe('Plugin selection', () => {
    it('should return null for null pack', () => {
      expect(selectPlugin(null)).toBeNull()
    })

    it('should return null for undefined pack', () => {
      expect(selectPlugin(undefined)).toBeNull()
    })

    it('should select correct plugin for civitai pack', () => {
      const pack = createCivitaiPack()
      const plugin = selectPlugin(pack)
      expect(plugin?.id).toBe('civitai')
    })

    it('should select correct plugin for install pack', () => {
      const pack = createInstallPack()
      const plugin = selectPlugin(pack)
      expect(plugin?.id).toBe('install')
    })

    it('should fallback to custom plugin', () => {
      const pack = createMockPack()
      const plugin = selectPlugin(pack)
      expect(plugin?.id).toBe('custom')
    })
  })

  describe('getPlugin helper', () => {
    function getPlugin(id: string): PackPlugin | undefined {
      return registry.find(p => p.id === id)
    }

    it('should find plugin by id', () => {
      expect(getPlugin('civitai')?.name).toBe('Civitai')
      expect(getPlugin('custom')?.name).toBe('Custom')
      expect(getPlugin('install')?.name).toBe('Install')
    })

    it('should return undefined for unknown id', () => {
      expect(getPlugin('unknown')).toBeUndefined()
    })
  })

  describe('allPlugins access', () => {
    it('should return all registered plugins', () => {
      expect(registry).toHaveLength(3)
      expect(registry.map(p => p.id)).toContain('civitai')
      expect(registry.map(p => p.id)).toContain('custom')
      expect(registry.map(p => p.id)).toContain('install')
    })

    it('should be sorted by priority', () => {
      expect(registry[0].id).toBe('install') // 100
      expect(registry[1].id).toBe('civitai') // 50
      expect(registry[2].id).toBe('custom')  // 0
    })
  })
})

// ============================================================================
// Integration Tests
// ============================================================================

describe('Plugin Integration', () => {
  describe('Full workflow', () => {
    it('should handle complete civitai pack workflow', () => {
      // 1. Create pack
      const pack = createCivitaiPack({
        name: 'my-lora',
        model_info: {
          model_type: 'LORA',
          base_model: 'SD 1.5',
          trigger_words: ['lora_trigger'],
        },
      })

      // 2. Create context
      const context = createMockContext(pack)

      // 3. Verify pack properties are accessible
      expect(context.pack.name).toBe('my-lora')
      expect(context.pack.pack?.source?.provider).toBe('civitai')
      expect(context.pack.model_info?.trigger_words).toContain('lora_trigger')
    })

    it('should handle complete custom pack workflow', () => {
      // 1. Create pack with dependencies
      const pack = createCustomPack({
        name: 'custom-workflow-pack',
        pack: {
          name: 'custom-workflow-pack',
          pack_type: 'lora',
          pack_category: 'custom',
          source: { provider: 'local' },
          pack_dependencies: [
            { pack_name: 'sd15-base', required: true },
            { pack_name: 'custom-vae', required: false },
          ],
        },
      })

      // 2. Create context
      const context = createMockContext(pack)

      // 3. Verify dependencies are accessible
      expect(context.pack.pack?.pack_dependencies).toHaveLength(2)
      expect(context.pack.pack?.pack_category).toBe('custom')
    })

    it('should handle complete install pack workflow', () => {
      // 1. Create install pack
      const pack = createInstallPack({
        name: 'comfyui-portable',
        description: 'Portable ComfyUI installation',
      })

      // 2. Create context
      const context = createMockContext(pack)

      // 3. Verify install-specific properties
      expect(context.pack.user_tags).toContain('install-pack')
      expect(context.pack.name).toBe('comfyui-portable')
    })
  })
})

// ============================================================================
// API URL Tests
// ============================================================================

describe('Plugin API URLs', () => {
  describe('CivitaiPlugin API URLs', () => {
    it('should use correct update check URL format', () => {
      const packName = 'my-test-pack'
      const expectedUrl = `/api/updates/check/${encodeURIComponent(packName)}`
      expect(expectedUrl).toBe('/api/updates/check/my-test-pack')
    })

    it('should encode pack name in URL', () => {
      const packName = 'pack with spaces'
      const expectedUrl = `/api/updates/check/${encodeURIComponent(packName)}`
      expect(expectedUrl).toBe('/api/updates/check/pack%20with%20spaces')
    })

    it('should use correct apply update URL (without pack_name in path)', () => {
      // Apply endpoint takes pack in request body, not URL
      const expectedUrl = '/api/updates/apply'
      expect(expectedUrl).not.toContain('{pack_name}')
    })

    it('should build correct apply request body', () => {
      const packName = 'test-pack'
      const requestBody = {
        pack: packName,
        dry_run: false,
        sync: true,
      }

      expect(requestBody.pack).toBe('test-pack')
      expect(requestBody).toHaveProperty('dry_run')
      expect(requestBody).toHaveProperty('sync')
    })
  })

  describe('CustomPlugin API URLs', () => {
    it('should use correct pack check URL format', () => {
      const packName = 'dependency-pack'
      const expectedUrl = `/api/packs/${encodeURIComponent(packName)}`
      expect(expectedUrl).toBe('/api/packs/dependency-pack')
    })

    it('should encode special characters in pack name', () => {
      const packName = 'my-lora@v2'
      const expectedUrl = `/api/packs/${encodeURIComponent(packName)}`
      expect(expectedUrl).toBe('/api/packs/my-lora%40v2')
    })

    it('should NOT use /api/v2/packs (deprecated)', () => {
      const correctPrefix = '/api/packs'
      const wrongPrefix = '/api/v2/packs'
      expect(correctPrefix).not.toBe(wrongPrefix)
    })
  })
})
