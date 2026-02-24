/**
 * AvatarSettings Component
 *
 * Settings panel for Avatar Engine (AI Assistant) configuration.
 * Mostly read-only display — avatar.yaml is the source of truth.
 * Follows the same forwardRef/useImperativeHandle pattern as AIServicesSettings.
 */

import { forwardRef, useImperativeHandle, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
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
} from 'lucide-react'
import clsx from 'clsx'
import { AvatarBust, AvatarPicker, ProviderModelSelector, DEFAULT_AVATAR_ID, LS_SELECTED_AVATAR } from '@avatar-engine/react'
import { useAvatar, ALL_AVATARS } from '../../avatar/AvatarProvider'
import {
  getAvatarConfig,
  getAvatarProviders,
  getAvatarAvatars,
  getAvatarStatus,
  avatarKeys,
  type AvatarConfig,
  type AvatarProvider as AvatarProviderType,
  type AvatarAvatars,
} from '../../../lib/avatar/api'

// =============================================================================
// Types
// =============================================================================

export interface AvatarSettingsHandle {
  save: () => Promise<void>
  hasChanges: () => boolean
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
// Main Component
// =============================================================================

export const AvatarSettings = forwardRef<AvatarSettingsHandle>(function AvatarSettings(_props, ref) {
  const { t } = useTranslation()
  const { chat } = useAvatar()
  const [skillsExpanded, setSkillsExpanded] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [selectedAvatarId, setSelectedAvatarId] = useState(() => {
    try { return localStorage.getItem(LS_SELECTED_AVATAR) || DEFAULT_AVATAR_ID } catch { return DEFAULT_AVATAR_ID }
  })
  const selectedAvatar = ALL_AVATARS.find(a => a.id === selectedAvatarId)

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

  // Read-only component — no local changes to save
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

  const engineVersion = status?.engine_version
  const activeProvider = config?.provider
  const skillsCount = config?.skills_count
  const totalSkills = (skillsCount?.builtin || 0) + (skillsCount?.custom || 0)
  const skills = config?.skills

  return (
    <div
      className={clsx(
        'rounded-2xl overflow-hidden',
        'bg-gradient-to-br from-slate-dark to-slate-base',
        'border border-slate-light/20',
        'shadow-xl shadow-black/20'
      )}
    >
      {/* Header */}
      <div
        className={clsx(
          'p-6 border-b border-slate-light/20',
          'bg-gradient-to-r from-purple-500/5 via-transparent to-synapse/5'
        )}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-16 rounded-xl overflow-hidden border border-purple-500/30 shadow-lg shadow-purple-500/20 bg-gradient-to-br from-purple-500/10 to-synapse/10">
              <AvatarBust
                avatar={selectedAvatar}
                engineState={chat.engineState}
                hasText={false}
                avatarBasePath="/avatars"
              />
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
        {/* Info banner — config is read-only */}
        <div
          className={clsx(
            'p-3 rounded-xl flex items-start gap-3',
            'bg-slate-light/5 border border-slate-light/20'
          )}
        >
          <Info className="w-5 h-5 text-text-muted flex-shrink-0 mt-0.5" />
          <div className="text-sm text-text-muted">
            {t('settingsAvatar.configReadOnly')}
            {config?.config_path && (
              <code className="ml-1 px-1.5 py-0.5 rounded bg-slate-dark/50 text-xs text-text-secondary font-mono break-all">
                {config.config_path}
              </code>
            )}
          </div>
        </div>

        {/* Status Overview — 2×2 grid */}
        <div className="grid grid-cols-2 gap-4">
          <StatCard
            label={t('settingsAvatar.stats.engine')}
            value={status?.engine_installed ? t('settingsAvatar.installed') : t('settingsAvatar.notInstalled')}
            color={status?.engine_installed ? 'success' : 'warning'}
            icon={<Bot className="w-4 h-4 text-text-muted" />}
          />
          <StatCard
            label={t('settingsAvatar.stats.provider')}
            value={activeProvider || t('settingsAvatar.none')}
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

        {/* Provider & Model Selector (live-switching) */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
            <span>{t('settingsAvatar.providersTitle')}</span>
            <div className="flex-1 h-px bg-slate-light/30" />
          </h3>

          <div
            className={clsx(
              'p-4 rounded-xl',
              'bg-slate-dark/30 border border-slate-light/20'
            )}
          >
            <ProviderModelSelector
              currentProvider={chat.provider || activeProvider || ''}
              currentModel={chat.model || null}
              switching={chat.switching}
              activeOptions={chat.activeOptions}
              availableProviders={providers ? new Set(providers.filter(p => p.installed).map(p => p.name)) : undefined}
              onSwitch={chat.switchProvider}
            />
          </div>
        </div>

        {/* Skills Summary */}
        <div className="space-y-3">
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

        {/* Avatar Selection (informational) */}
        <div className="space-y-3">
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
            {/* Avatar preview + info */}
            <div className="flex items-center gap-4 mb-4">
              <div className="w-16 h-24 rounded-xl overflow-hidden border border-slate-light/30 bg-slate-mid/30 flex-shrink-0">
                <AvatarBust
                  avatar={selectedAvatar}
                  engineState={chat.engineState}
                  hasText={false}
                  avatarBasePath="/avatars"
                />
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

            {/* AvatarPicker overlay */}
            {pickerOpen && (
              <AvatarPicker
                selectedId={selectedAvatarId}
                onSelect={(id) => {
                  setSelectedAvatarId(id)
                  try { localStorage.setItem(LS_SELECTED_AVATAR, id) } catch {}
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
  )
})
