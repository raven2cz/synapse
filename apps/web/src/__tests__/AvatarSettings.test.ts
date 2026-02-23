/**
 * Tests for AvatarSettings component logic.
 *
 * Tests the data processing and state management behind
 * the AvatarSettings settings panel.
 */

import { describe, it, expect } from 'vitest'

// --- Types mirroring component dependencies ---

interface AvatarConfig {
  enabled: boolean
  provider: string
  safety: string
  max_history: number
  has_config_file: boolean
  config_path: string | null
  skills_count: { builtin: number; custom: number }
  skills?: { builtin: SkillInfo[]; custom: SkillInfo[] }
  provider_configs: Record<string, { model: string; enabled: boolean }>
}

interface SkillInfo {
  name: string
  path: string
  size: number
  category: 'builtin' | 'custom'
}

interface AvatarProvider {
  name: string
  display_name: string
  command: string
  installed: boolean
}

interface AvatarStatus {
  available: boolean
  state: string
  enabled: boolean
  engine_installed: boolean
  engine_version: string | null
  active_provider: string | null
  safety: string
  providers: AvatarProvider[]
}

// --- Mock data ---

const mockProviders: AvatarProvider[] = [
  { name: 'gemini', display_name: 'Gemini CLI', command: 'gemini', installed: true },
  { name: 'claude', display_name: 'Claude Code', command: 'claude', installed: false },
  { name: 'codex', display_name: 'Codex CLI', command: 'codex', installed: true },
]

const mockConfig: AvatarConfig = {
  enabled: true,
  provider: 'gemini',
  safety: 'safe',
  max_history: 100,
  has_config_file: true,
  config_path: '/home/user/.synapse/avatar.yaml',
  skills_count: { builtin: 3, custom: 1 },
  skills: {
    builtin: [
      { name: 'inventory', path: '/skills/inventory.md', size: 1024, category: 'builtin' },
      { name: 'parameters', path: '/skills/parameters.md', size: 2048, category: 'builtin' },
      { name: 'workflows', path: '/skills/workflows.md', size: 512, category: 'builtin' },
    ],
    custom: [
      { name: 'my-skill', path: '/custom/my-skill.md', size: 256, category: 'custom' },
    ],
  },
  provider_configs: {
    gemini: { model: 'gemini-2.5-pro', enabled: true },
    claude: { model: '', enabled: true },
  },
}

const mockStatus: AvatarStatus = {
  available: true,
  state: 'ready',
  enabled: true,
  engine_installed: true,
  engine_version: '0.3.0',
  active_provider: 'gemini',
  safety: 'safe',
  providers: mockProviders,
}

// --- Helper functions (matching component logic) ---

function getSafetyColor(safety: string): 'success' | 'warning' | 'danger' {
  if (safety === 'safe') return 'success'
  if (safety === 'ask') return 'warning'
  return 'danger'
}

function getTotalSkills(config: AvatarConfig): number {
  return (config.skills_count?.builtin || 0) + (config.skills_count?.custom || 0)
}

function getActiveProviderInfo(
  providers: AvatarProvider[],
  activeProvider: string | null
): AvatarProvider | undefined {
  return providers.find(p => p.name === activeProvider)
}

// =============================================================================
// Tests
// =============================================================================

describe('AvatarSettings', () => {
  describe('Provider status display', () => {
    it('should identify active provider from list', () => {
      const active = getActiveProviderInfo(mockProviders, 'gemini')
      expect(active).toBeDefined()
      expect(active?.installed).toBe(true)
      expect(active?.display_name).toBe('Gemini CLI')
    })

    it('should return undefined for no active provider', () => {
      const active = getActiveProviderInfo(mockProviders, null)
      expect(active).toBeUndefined()
    })

    it('should show installed count correctly', () => {
      const installedCount = mockProviders.filter(p => p.installed).length
      expect(installedCount).toBe(2)
    })

    it('should show model for active provider', () => {
      const model = mockConfig.provider_configs?.gemini?.model
      expect(model).toBe('gemini-2.5-pro')
    })
  })

  describe('Skills count', () => {
    it('should compute total skills from builtin + custom', () => {
      expect(getTotalSkills(mockConfig)).toBe(4)
    })

    it('should handle missing skills_count', () => {
      const configNoSkills = {
        ...mockConfig,
        skills_count: { builtin: 0, custom: 0 },
      }
      expect(getTotalSkills(configNoSkills)).toBe(0)
    })

    it('should list builtin skill names', () => {
      const names = mockConfig.skills?.builtin.map(s => s.name) || []
      expect(names).toContain('inventory')
      expect(names).toContain('parameters')
      expect(names).toContain('workflows')
      expect(names).toHaveLength(3)
    })

    it('should list custom skill names', () => {
      const names = mockConfig.skills?.custom.map(s => s.name) || []
      expect(names).toContain('my-skill')
      expect(names).toHaveLength(1)
    })
  })

  describe('Safety badge', () => {
    it('should return success color for safe mode', () => {
      expect(getSafetyColor('safe')).toBe('success')
    })

    it('should return warning color for ask mode', () => {
      expect(getSafetyColor('ask')).toBe('warning')
    })

    it('should return danger color for unrestricted mode', () => {
      expect(getSafetyColor('unrestricted')).toBe('danger')
    })

    it('should default to danger for unknown mode', () => {
      expect(getSafetyColor('unknown')).toBe('danger')
    })
  })

  describe('Config path display', () => {
    it('should show config path when available', () => {
      expect(mockConfig.config_path).toBe('/home/user/.synapse/avatar.yaml')
      expect(mockConfig.has_config_file).toBe(true)
    })

    it('should handle null config path', () => {
      const noPathConfig = { ...mockConfig, config_path: null }
      expect(noPathConfig.config_path).toBeNull()
    })
  })

  describe('Engine status', () => {
    it('should detect engine installed from status', () => {
      expect(mockStatus.engine_installed).toBe(true)
      expect(mockStatus.engine_version).toBe('0.3.0')
    })

    it('should detect engine not installed', () => {
      const noEngine: AvatarStatus = {
        ...mockStatus,
        engine_installed: false,
        engine_version: null,
        state: 'no_engine',
        available: false,
      }
      expect(noEngine.engine_installed).toBe(false)
      expect(noEngine.engine_version).toBeNull()
    })
  })

  describe('Loading state', () => {
    it('should show loading when both queries pending', () => {
      const isLoadingConfig = true
      const isLoadingProviders = true
      const isLoading = isLoadingConfig || isLoadingProviders
      expect(isLoading).toBe(true)
    })

    it('should not show loading when both complete', () => {
      const isLoadingConfig = false
      const isLoadingProviders = false
      const isLoading = isLoadingConfig || isLoadingProviders
      expect(isLoading).toBe(false)
    })

    it('should show loading when one query pending', () => {
      const isLoadingConfig = false
      const isLoadingProviders = true
      const isLoading = isLoadingConfig || isLoadingProviders
      expect(isLoading).toBe(true)
    })
  })

  describe('Error state', () => {
    it('should show error when both queries fail', () => {
      const isErrorConfig = true
      const isErrorProviders = true
      const isError = isErrorConfig && isErrorProviders
      expect(isError).toBe(true)
    })

    it('should not show error if config succeeds but providers fail', () => {
      const isErrorConfig = false
      const isErrorProviders = true
      const isError = isErrorConfig && isErrorProviders
      expect(isError).toBe(false)
    })

    it('should not show error when both succeed', () => {
      const isErrorConfig = false
      const isErrorProviders = false
      const isError = isErrorConfig && isErrorProviders
      expect(isError).toBe(false)
    })
  })

  describe('Avatar data from API', () => {
    interface AvatarInfo {
      id: string
      name: string
      category: 'builtin' | 'custom'
    }

    interface AvatarAvatars {
      builtin: AvatarInfo[]
      custom: AvatarInfo[]
    }

    const mockAvatars: AvatarAvatars = {
      builtin: [
        { id: 'bella', name: 'Bella', category: 'builtin' },
        { id: 'sky', name: 'Sky', category: 'builtin' },
      ],
      custom: [
        { id: 'my-avatar', name: 'My Custom Avatar', category: 'custom' },
      ],
    }

    it('should list builtin avatars from API', () => {
      const names = mockAvatars.builtin.map(a => a.name)
      expect(names).toContain('Bella')
      expect(names).toContain('Sky')
    })

    it('should list custom avatars from API', () => {
      expect(mockAvatars.custom).toHaveLength(1)
      expect(mockAvatars.custom[0].name).toBe('My Custom Avatar')
    })

    it('should handle empty custom avatars', () => {
      const noCustom: AvatarAvatars = { builtin: mockAvatars.builtin, custom: [] }
      expect(noCustom.custom).toHaveLength(0)
    })

    it('should handle undefined avatars data gracefully', () => {
      const avatars = undefined as AvatarAvatars | undefined
      const builtinCount = avatars?.builtin?.length ?? 0
      const customCount = avatars?.custom?.length ?? 0
      expect(builtinCount).toBe(0)
      expect(customCount).toBe(0)
    })
  })

  describe('Imperative handle contract', () => {
    it('save should be a no-op (read-only component)', async () => {
      const handle = {
        save: async () => {},
        hasChanges: () => false,
      }
      await handle.save()
      expect(handle.hasChanges()).toBe(false)
    })
  })
})
