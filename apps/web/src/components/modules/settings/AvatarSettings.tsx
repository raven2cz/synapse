/**
 * AvatarSettings — Unified AI Settings Component
 *
 * Replaces both the deprecated AIServicesSettings and the old read-only AvatarSettings.
 * Provides: master toggle, status overview, provider checkboxes with default-for-services
 * radio, skills list, avatar picker, cache maintenance, and config file path.
 */

import { forwardRef, useImperativeHandle, useRef, useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  Bot,
  Shield,
  Zap,
  FileText,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Info,
  Trash2,
  Wind,
  Database,
} from 'lucide-react'
import clsx from 'clsx'
import { AvatarPicker, useAvatarThumb, getModelsForProvider, DEFAULT_AVATAR_ID, LS_SELECTED_AVATAR } from '@avatar-engine/react'
import { ALL_AVATARS } from '../../avatar/AvatarProvider'
import {
  getAvatarConfig,
  getAvatarProviders,
  getAvatarAvatars,
  getAvatarStatus,
  patchAvatarConfig,
  avatarKeys,
  type AvatarConfig,
  type AvatarProvider as AvatarProviderType,
  type AvatarAvatars,
} from '../../../lib/avatar/api'
import { useAICacheStats, useClearAICache, useCleanupAICache } from '../../../lib/ai/hooks'
import { formatBytes } from '../../../lib/utils/format'
import { toast } from '../../../stores/toastStore'

// =============================================================================
// Types
// =============================================================================

export interface AvatarSettingsHandle {
  save: () => Promise<void>
  hasChanges: () => boolean
}

// Provider display info
const PROVIDER_DISPLAY: Record<string, { icon: string; displayName: string }> = {
  gemini: { icon: '✨', displayName: 'Gemini CLI' },
  claude: { icon: '🤖', displayName: 'Claude Code' },
  codex: { icon: '💻', displayName: 'Codex CLI' },
}

// =============================================================================
// Stat Card
// =============================================================================

interface StatCardProps {
  label: string
  value: string | number
  color?: 'synapse' | 'success' | 'warning' | 'danger' | 'neural'
  icon?: React.ReactNode
}

const STAT_COLORS = {
  synapse: 'text-synapse',
  success: 'text-success',
  warning: 'text-amber-400',
  danger: 'text-red-400',
  neural: 'text-neural',
}

function StatCard({ label, value, color = 'synapse', icon }: StatCardProps) {
  return (
    <div
      className={clsx(
        'px-4 py-3 rounded-xl',
        'bg-slate-dark/30 border border-slate-light/20',
        'flex items-center gap-3'
      )}
    >
      {icon && (
        <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', 'bg-slate-mid/50')}>
          {icon}
        </div>
      )}
      <div>
        <div className="text-xs text-text-muted">{label}</div>
        <div className={clsx('text-lg font-bold', STAT_COLORS[color])}>{value}</div>
      </div>
    </div>
  )
}

// =============================================================================
// Model Select — custom themed dropdown with free-text input
// =============================================================================

interface ModelSelectProps {
  value: string
  models: string[]
  placeholder: string
  disabled?: boolean
  onChange: (model: string) => void
}

function ModelSelect({ value, models, placeholder, disabled, onChange }: ModelSelectProps) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [inputValue, setInputValue] = useState(value)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Sync input value when prop changes externally
  useEffect(() => { setInputValue(value) }, [value])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
        setEditing(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleSelect = (m: string) => {
    onChange(m)
    setInputValue(m)
    setOpen(false)
    setEditing(false)
  }

  const handleInputBlur = () => {
    // Commit typed value on blur (small delay so click on option registers first)
    setTimeout(() => {
      if (inputValue !== value) onChange(inputValue)
      setEditing(false)
    }, 150)
  }

  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      onChange(inputValue)
      setOpen(false)
      setEditing(false)
      inputRef.current?.blur()
    } else if (e.key === 'Escape') {
      setInputValue(value)
      setOpen(false)
      setEditing(false)
      inputRef.current?.blur()
    }
  }

  return (
    <div ref={containerRef} className="relative w-56">
      {/* Display / Input */}
      {editing ? (
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onBlur={handleInputBlur}
          onKeyDown={handleInputKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          autoFocus
          className={clsx(
            'w-full px-3 py-1.5 pr-7 rounded-lg text-sm font-mono',
            'bg-slate-dark/50 border border-purple-500/50',
            'text-text-secondary placeholder:text-text-muted/40',
            'focus:outline-none',
            disabled && 'opacity-40 cursor-not-allowed'
          )}
        />
      ) : (
        <button
          type="button"
          onClick={() => {
            if (disabled) return
            setOpen(!open)
          }}
          onDoubleClick={() => {
            if (disabled) return
            setEditing(true)
            setOpen(false)
          }}
          disabled={disabled}
          className={clsx(
            'w-full px-3 py-1.5 pr-7 rounded-lg text-sm font-mono text-left',
            'bg-slate-dark/50 border border-slate-light/20',
            'text-text-secondary',
            disabled ? 'opacity-40 cursor-not-allowed' : 'hover:border-purple-500/30 cursor-pointer',
            !value && 'text-text-muted/40'
          )}
        >
          {value || placeholder}
        </button>
      )}

      {/* Chevron */}
      {!editing && !disabled && (
        <ChevronDown className={clsx(
          'absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted/50 pointer-events-none transition-transform',
          open && 'rotate-180'
        )} />
      )}

      {/* Dropdown */}
      {open && !disabled && models.length > 0 && (
        <div className={clsx(
          'absolute z-50 mt-1 w-full py-1 rounded-lg',
          'bg-slate-dark border border-slate-light/30',
          'shadow-xl shadow-black/40',
          'max-h-48 overflow-y-auto'
        )}>
          {models.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => handleSelect(m)}
              className={clsx(
                'w-full px-3 py-1.5 text-left text-sm font-mono',
                'hover:bg-purple-500/15 transition-colors',
                m === value
                  ? 'text-purple-400 bg-purple-500/10'
                  : 'text-text-secondary'
              )}
            >
              {m}
            </button>
          ))}
          {/* Edit hint */}
          <div className="border-t border-slate-light/10 px-3 py-1.5 text-[10px] text-text-muted/50">
            Double-click to type custom model
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export const AvatarSettings = forwardRef<AvatarSettingsHandle>(function AvatarSettings(_props, ref) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [skillsExpanded, setSkillsExpanded] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [selectedAvatarId, setSelectedAvatarId] = useState(() => {
    try { return localStorage.getItem(LS_SELECTED_AVATAR) || DEFAULT_AVATAR_ID } catch { return DEFAULT_AVATAR_ID }
  })
  const selectedAvatar = ALL_AVATARS.find(a => a.id === selectedAvatarId)
  const thumbUrl = useAvatarThumb(selectedAvatar, '/avatars')

  const { data: status } = useQuery<import('../../../lib/avatar/api').AvatarStatus>({
    queryKey: avatarKeys.status(),
    queryFn: getAvatarStatus,
    staleTime: 60_000,
    retry: 1,
  })

  const { data: config, isLoading: isLoadingConfig, isError: isErrorConfig } = useQuery<AvatarConfig>({
    queryKey: avatarKeys.config(),
    queryFn: getAvatarConfig,
    staleTime: 60_000,
    retry: 1,
  })

  const { data: providers, isLoading: isLoadingProviders, isError: isErrorProviders } = useQuery<AvatarProviderType[]>({
    queryKey: avatarKeys.providers(),
    queryFn: getAvatarProviders,
    staleTime: 60_000,
    retry: 1,
  })

  const { data: avatars } = useQuery<AvatarAvatars>({
    queryKey: avatarKeys.avatars(),
    queryFn: getAvatarAvatars,
    staleTime: 60_000,
    retry: 1,
  })

  // Cache hooks
  const { data: cacheStats } = useAICacheStats()
  const clearCacheMutation = useClearAICache()
  const cleanupCacheMutation = useCleanupAICache()

  // Config mutation
  const patchConfigMutation = useMutation({
    mutationFn: patchAvatarConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: avatarKeys.all })
    },
  })

  // No local changes to track — all mutations are immediate
  useImperativeHandle(ref, () => ({
    save: async () => {},
    hasChanges: () => false,
  }), [])

  const isLoading = isLoadingConfig || isLoadingProviders
  const isError = isErrorConfig || isErrorProviders

  if (isLoading) {
    return (
      <div
        className={clsx(
          'rounded-2xl overflow-hidden',
          'bg-gradient-to-br from-slate-dark to-slate-base',
          'border border-slate-light/20',
          'shadow-xl shadow-black/20',
          'p-6'
        )}
      >
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-slate-light/20 animate-pulse" />
          <div className="space-y-2 flex-1">
            <div className="h-5 w-48 bg-slate-light/20 rounded animate-pulse" />
            <div className="h-4 w-32 bg-slate-light/10 rounded animate-pulse" />
          </div>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div
        className={clsx(
          'rounded-2xl overflow-hidden',
          'bg-gradient-to-br from-slate-dark to-slate-base',
          'border border-slate-light/20',
          'shadow-xl shadow-black/20',
          'p-6'
        )}
      >
        <div className="flex items-center gap-3">
          <div
            className={clsx(
              'w-12 h-12 rounded-xl flex items-center justify-center',
              'bg-red-500/10 border border-red-500/30'
            )}
          >
            <AlertCircle className="w-6 h-6 text-red-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-text-primary">
              {t('settingsAvatar.title')}
            </h2>
            <p className="text-sm text-red-400 mt-0.5">
              {t('settingsAvatar.loadFailed')}
            </p>
          </div>
        </div>
      </div>
    )
  }

  const aiEnabled = config?.enabled !== false
  const engineVersion = status?.engine_version
  const activeProvider = config?.provider
  const skillsCount = config?.skills_count
  const totalSkills = (skillsCount?.builtin || 0) + (skillsCount?.custom || 0)
  const skills = config?.skills
  const providerConfigs = config?.provider_configs || {}

  // Build installed providers map
  const installedMap = new Map<string, boolean>()
  if (providers) {
    for (const p of providers) {
      installedMap.set(p.name, p.installed)
    }
  }

  const handleToggleEnabled = () => {
    patchConfigMutation.mutate({ enabled: !aiEnabled })
  }

  const handleSetDefaultProvider = (provName: string) => {
    patchConfigMutation.mutate({ provider: provName })
  }

  const handleToggleProviderEnabled = (provName: string, currentEnabled: boolean) => {
    patchConfigMutation.mutate({
      providers: { [provName]: { enabled: !currentEnabled } },
    })
  }

  const handleModelChange = (provName: string, model: string) => {
    patchConfigMutation.mutate({
      providers: { [provName]: { model } },
    })
  }

  // Service default display string
  const defaultProviderModel = activeProvider
    ? `${PROVIDER_DISPLAY[activeProvider]?.displayName || activeProvider}${providerConfigs[activeProvider]?.model ? ` / ${providerConfigs[activeProvider].model}` : ''}`
    : t('settingsAvatar.none')

  return (
    <div
      className={clsx(
        'rounded-2xl overflow-hidden',
        'bg-gradient-to-br from-slate-dark to-slate-base',
        'border border-slate-light/20',
        'shadow-xl shadow-black/20'
      )}
    >
      {/* Header with avatar thumbnail */}
      <div
        className={clsx(
          'p-6 border-b border-slate-light/20',
          'bg-gradient-to-r from-purple-500/5 via-transparent to-synapse/5'
        )}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-[72px] h-[72px] rounded-full overflow-hidden border-2 border-purple-500/30 shadow-lg shadow-purple-500/20 bg-gradient-to-br from-purple-500/10 to-synapse/10 flex-shrink-0">
              {thumbUrl ? (
                <img src={thumbUrl} alt="Avatar" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Bot className="w-8 h-8 text-purple-400/50" />
                </div>
              )}
            </div>
            <div>
              <h2 className="text-xl font-bold text-text-primary">
                {t('settingsAvatar.title')}
              </h2>
              <p className="text-sm text-text-muted mt-0.5">
                {t('settingsAvatar.subtitle')}
              </p>
            </div>
          </div>
          {engineVersion && (
            <span
              className={clsx(
                'px-3 py-1.5 rounded-lg text-xs font-mono',
                'bg-purple-500/10 text-purple-400 border border-purple-500/30'
              )}
            >
              v{engineVersion}
            </span>
          )}
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Master Toggle */}
        <div className="flex items-center justify-between p-4 rounded-xl bg-slate-dark/30 border border-slate-light/20">
          <div>
            <span className="text-text-primary font-medium">{t('settingsAvatar.masterToggle')}</span>
            <p className="text-xs text-text-muted mt-0.5">
              {t('settingsAvatar.masterToggleDesc')}
            </p>
          </div>
          <button
            onClick={handleToggleEnabled}
            disabled={patchConfigMutation.isPending}
            className={clsx(
              'relative w-12 h-6 rounded-full transition-all duration-200',
              aiEnabled ? 'bg-purple-500 shadow-lg shadow-purple-500/40' : 'bg-slate-700',
              patchConfigMutation.isPending && 'opacity-50 cursor-wait'
            )}
            data-testid="ai-master-toggle"
          >
            <span
              className={clsx(
                'absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-200',
                aiEnabled ? 'left-7' : 'left-1'
              )}
            />
          </button>
        </div>

        {/* Everything below is dimmed when disabled */}
        <div className={clsx(!aiEnabled && 'opacity-40 pointer-events-none')}>
          {/* Status Overview */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <StatCard
              label={t('settingsAvatar.stats.engine')}
              value={status?.engine_installed ? t('settingsAvatar.installed') : t('settingsAvatar.notInstalled')}
              color={status?.engine_installed ? 'success' : 'warning'}
              icon={<Bot className="w-4 h-4 text-text-muted" />}
            />
            <StatCard
              label={t('settingsAvatar.stats.serviceDefault')}
              value={defaultProviderModel}
              color={activeProvider ? 'synapse' : 'warning'}
              icon={<Zap className="w-4 h-4 text-text-muted" />}
            />
            <StatCard
              label={t('settingsAvatar.stats.safety')}
              value={config?.safety || 'safe'}
              color={config?.safety === 'safe' ? 'success' : config?.safety === 'ask' ? 'warning' : 'danger'}
              icon={<Shield className="w-4 h-4 text-text-muted" />}
            />
            <StatCard
              label={t('settingsAvatar.stats.skills')}
              value={totalSkills}
              color="neural"
              icon={<FileText className="w-4 h-4 text-text-muted" />}
            />
          </div>

          {/* Providers Section */}
          <div className="space-y-3 mb-6">
            <h3 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <span>{t('settingsAvatar.providersTitle')}</span>
              <div className="flex-1 h-px bg-slate-light/30" />
            </h3>

            <div className="rounded-xl bg-slate-dark/30 border border-slate-light/20 divide-y divide-slate-light/10">
              {(['gemini', 'claude', 'codex'] as const).map((provName) => {
                const display = PROVIDER_DISPLAY[provName]
                const installed = installedMap.get(provName) ?? false
                const provConfig = providerConfigs[provName]
                const isEnabled = provConfig?.enabled !== false
                const isDefault = activeProvider === provName
                const model = provConfig?.model || ''

                return (
                  <div key={provName} className="p-4 flex items-center gap-4">
                    {/* Default radio */}
                    <button
                      onClick={() => handleSetDefaultProvider(provName)}
                      disabled={!installed || !isEnabled || patchConfigMutation.isPending}
                      className={clsx(
                        'w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors',
                        isDefault
                          ? 'border-purple-500 bg-purple-500'
                          : installed && isEnabled
                            ? 'border-slate-light/40 hover:border-purple-400'
                            : 'border-slate-light/20 cursor-not-allowed'
                      )}
                      title={t('settingsAvatar.providerDefault')}
                    >
                      {isDefault && <div className="w-2 h-2 rounded-full bg-white" />}
                    </button>

                    {/* Enable checkbox */}
                    <button
                      onClick={() => handleToggleProviderEnabled(provName, isEnabled)}
                      disabled={!installed || (isDefault && isEnabled) || patchConfigMutation.isPending}
                      className={clsx(
                        'w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 transition-colors',
                        isEnabled && installed
                          ? 'border-synapse bg-synapse/20 text-synapse'
                          : installed
                            ? 'border-slate-light/30 hover:border-synapse/50'
                            : 'border-slate-light/20 cursor-not-allowed'
                      )}
                      title={t('settingsAvatar.providerEnabled')}
                    >
                      {isEnabled && installed && (
                        <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                          <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </button>

                    {/* Provider info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-base">{display.icon}</span>
                        <span className={clsx(
                          'text-sm font-medium',
                          installed ? 'text-text-primary' : 'text-text-muted'
                        )}>
                          {display.displayName}
                        </span>
                        {!installed && (
                          <span className="text-xs text-amber-400/70 italic">
                            ({t('settingsAvatar.providerNotInstalled')})
                          </span>
                        )}
                        {isDefault && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-purple-500/20 text-purple-400 border border-purple-500/30">
                            default
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Model selector */}
                    <ModelSelect
                      value={model}
                      models={getModelsForProvider(provName)}
                      placeholder={t('settingsAvatar.modelPlaceholder')}
                      disabled={!installed || !isEnabled}
                      onChange={(m) => handleModelChange(provName, m)}
                    />
                  </div>
                )
              })}
            </div>

            <div className="flex items-start gap-2 px-1">
              <Info className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" />
              <p className="text-xs text-text-muted">
                {t('settingsAvatar.providerDefaultHint')}
              </p>
            </div>
          </div>

          {/* Skills Summary */}
          <div className="space-y-3 mb-6">
            <h3 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <span>{t('settingsAvatar.skillsTitle')}</span>
              <div className="flex-1 h-px bg-slate-light/30" />
            </h3>

            <div
              className={clsx(
                'rounded-xl',
                'bg-slate-dark/30 border border-slate-light/20'
              )}
            >
              <button
                onClick={() => setSkillsExpanded(!skillsExpanded)}
                className="w-full p-4 flex items-center justify-between text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-text-primary">
                      {t('settingsAvatar.builtinSkills', { count: skillsCount?.builtin || 0 })}
                    </span>
                    {(skillsCount?.custom || 0) > 0 && (
                      <>
                        <span className="text-text-muted">+</span>
                        <span className="text-sm text-purple-400">
                          {t('settingsAvatar.customSkills', { count: skillsCount?.custom || 0 })}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                {skillsExpanded
                  ? <ChevronDown className="w-4 h-4 text-text-muted" />
                  : <ChevronRight className="w-4 h-4 text-text-muted" />}
              </button>

              {skillsExpanded && skills && (
                <div className="px-4 pb-4 border-t border-slate-light/10">
                  {skills.builtin?.length > 0 && (
                    <div className="mt-3">
                      <div className="text-xs text-text-muted font-semibold uppercase mb-2">
                        {t('settingsAvatar.builtinLabel')}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {skills.builtin.map((s) => (
                          <span
                            key={s.name}
                            className="px-2 py-1 rounded-md bg-slate-light/10 text-xs text-text-secondary font-mono"
                          >
                            {s.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {skills.custom?.length > 0 && (
                    <div className="mt-3">
                      <div className="text-xs text-purple-400 font-semibold uppercase mb-2">
                        {t('settingsAvatar.customLabel')}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {skills.custom.map((s) => (
                          <span
                            key={s.name}
                            className="px-2 py-1 rounded-md bg-purple-500/10 text-xs text-purple-400 font-mono"
                          >
                            {s.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Avatar Selection */}
          <div className="space-y-3 mb-6">
            <h3 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <span>{t('settingsAvatar.avatarsTitle')}</span>
              <div className="flex-1 h-px bg-slate-light/30" />
            </h3>

            <div
              className={clsx(
                'p-4 rounded-xl relative',
                'bg-slate-dark/30 border border-slate-light/20'
              )}
            >
              <div className="flex items-center gap-4 mb-4">
                <div className="w-16 h-16 rounded-full overflow-hidden border border-slate-light/30 bg-slate-mid/30 flex-shrink-0">
                  {thumbUrl ? (
                    <img src={thumbUrl} alt="Avatar" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Bot className="w-6 h-6 text-text-muted/30" />
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-text-primary">
                    {selectedAvatar?.name || selectedAvatarId}
                  </div>
                  <div className="text-xs text-text-muted mt-0.5">
                    {t('settingsAvatar.avatarCount', { builtin: ALL_AVATARS.length, custom: avatars?.custom?.length || 0 })}
                  </div>
                  <button
                    onClick={() => setPickerOpen(true)}
                    className={clsx(
                      'mt-2 px-3 py-1.5 rounded-lg text-xs font-medium',
                      'bg-synapse/10 text-synapse border border-synapse/30',
                      'hover:bg-synapse/20 transition-colors'
                    )}
                  >
                    {t('settingsAvatar.changeAvatar')}
                  </button>
                </div>
              </div>

              {pickerOpen && (
                <AvatarPicker
                  selectedId={selectedAvatarId}
                  onSelect={(id) => {
                    setSelectedAvatarId(id)
                    try {
                      localStorage.setItem(LS_SELECTED_AVATAR, id)
                      // Notify AvatarWidget within same tab (StorageEvent only fires cross-tab)
                      window.dispatchEvent(new Event('avatar-change'))
                    } catch {}
                    setPickerOpen(false)
                  }}
                  onClose={() => setPickerOpen(false)}
                  avatars={ALL_AVATARS}
                  avatarBasePath="/avatars"
                />
              )}

              <p className="text-xs text-text-muted">
                {t('settingsAvatar.avatarsHint')}
              </p>
            </div>
          </div>

          {/* Cache Maintenance */}
          <div className="space-y-3 mb-6">
            <h3 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <span>{t('settingsAvatar.cacheTitle')}</span>
              <div className="flex-1 h-px bg-slate-light/30" />
            </h3>

            <div className="rounded-xl bg-slate-dark/30 border border-slate-light/20 p-4">
              {/* Stats row */}
              <div className="flex items-center gap-6 mb-4">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-text-muted" />
                  <span className="text-xs text-text-muted">{t('settingsAvatar.cacheEntries')}:</span>
                  <span className="text-sm font-mono text-text-primary">{cacheStats?.entry_count ?? '—'}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-muted">{t('settingsAvatar.cacheSize')}:</span>
                  <span className="text-sm font-mono text-text-primary">
                    {cacheStats ? formatBytes(cacheStats.total_size_bytes) : '—'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-muted">{t('settingsAvatar.cacheTTL')}:</span>
                  <span className="text-sm font-mono text-text-primary">
                    {cacheStats ? t('settingsAvatar.cacheDays', { count: cacheStats.ttl_days }) : '—'}
                  </span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    cleanupCacheMutation.mutate(undefined, {
                      onSuccess: (data) => {
                        toast.success(t('settingsAvatar.cacheCleaned', { count: data.cleaned }))
                      },
                    })
                  }}
                  disabled={cleanupCacheMutation.isPending}
                  className={clsx(
                    'px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5',
                    'bg-amber-500/10 text-amber-400 border border-amber-500/30',
                    'hover:bg-amber-500/20 transition-colors',
                    cleanupCacheMutation.isPending && 'opacity-50 cursor-wait'
                  )}
                >
                  <Wind className="w-3.5 h-3.5" />
                  {t('settingsAvatar.cacheCleanup')}
                </button>
                <button
                  onClick={() => {
                    clearCacheMutation.mutate(undefined, {
                      onSuccess: (data) => {
                        toast.success(t('settingsAvatar.cacheCleared', { count: data.cleared }))
                      },
                    })
                  }}
                  disabled={clearCacheMutation.isPending}
                  className={clsx(
                    'px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5',
                    'bg-red-500/10 text-red-400 border border-red-500/30',
                    'hover:bg-red-500/20 transition-colors',
                    clearCacheMutation.isPending && 'opacity-50 cursor-wait'
                  )}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  {t('settingsAvatar.cacheClearAll')}
                </button>
              </div>
            </div>
          </div>

          {/* Config File Path */}
          {config?.config_path && (
            <div className="border-t border-slate-light/30 pt-6">
              <div className="flex items-center gap-3 mb-2">
                <FileText className="w-4 h-4 text-text-muted" />
                <h4 className="text-sm font-semibold text-text-secondary">
                  {t('settingsAvatar.configFile')}
                </h4>
              </div>
              <div className="p-3 rounded-xl bg-slate-dark/50 border border-slate-light/10">
                <code className="text-xs text-text-secondary font-mono break-all">
                  {config.config_path}
                </code>
              </div>
              <p className="text-xs text-text-muted mt-2">
                {t('settingsAvatar.configFileHint')}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
})
