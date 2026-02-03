/**
 * AIServicesSettings Component
 *
 * Main settings panel for AI services configuration.
 * Implements PLAN spec 3.1 (Main Settings Panel) with premium Synapse design.
 */

import { useState, useCallback, useEffect, forwardRef, useImperativeHandle } from 'react'
import { RefreshCw, Trash2, Sparkles, Database, Power, Zap, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react'
import clsx from 'clsx'
import { ProviderCard } from './ProviderCard'
import { AdvancedAISettings } from './AdvancedAISettings'
import { TaskPriorityConfigPanel } from './TaskPriorityConfig'
import {
  useAIProviders,
  useAISettings,
  useAICacheStats,
  useClearAICache,
  useCleanupAICache,
  useRefreshAIProviders,
  useUpdateAISettings,
} from '../../../lib/ai/hooks'
import type {
  AIServicesSettings as AISettingsType,
  ProviderConfig,
  TaskPriorityConfig,
} from '../../../lib/ai/types'
import { formatBytes } from '../../../lib/utils/format'
import { toast } from '../../../stores/toastStore'

// AI-only providers (without rule_based)
const AI_PROVIDERS = ['ollama', 'gemini', 'claude'] as const

// =============================================================================
// Stat Card Component
// =============================================================================

interface StatCardProps {
  label: string
  value: string | number
  color?: 'synapse' | 'success' | 'neural' | 'pulse'
  icon?: React.ReactNode
}

const STAT_COLORS = {
  synapse: 'text-synapse',
  success: 'text-success',
  neural: 'text-neural',
  pulse: 'text-pulse',
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
// Types
// =============================================================================

export interface AIServicesSettingsHandle {
  save: () => Promise<void>
  hasChanges: () => boolean
}

// =============================================================================
// Main Component
// =============================================================================

export const AIServicesSettings = forwardRef<AIServicesSettingsHandle>(function AIServicesSettings(_props, ref) {
  // Local state for uncommitted changes
  const [localSettings, setLocalSettings] = useState<Partial<AISettingsType> | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const { data: providers, isLoading: isLoadingProviders } = useAIProviders()
  const { data: settings, isLoading: isLoadingSettings } = useAISettings()
  const { data: cacheStats, refetch: refetchCacheStats } = useAICacheStats()

  const clearCacheMutation = useClearAICache()
  const cleanupCacheMutation = useCleanupAICache()
  const refreshProvidersMutation = useRefreshAIProviders()
  const updateSettingsMutation = useUpdateAISettings()

  // Save changes - called from parent or internal Save Now button
  const handleSaveInternal = useCallback(async () => {
    if (!localSettings) return

    try {
      await updateSettingsMutation.mutateAsync(localSettings)
      setLocalSettings(null)
      setHasChanges(false)
      setSaveSuccess(true)
      toast.success('AI settings saved')
    } catch {
      toast.error('Failed to save AI settings')
      throw new Error('Failed to save AI settings')
    }
  }, [localSettings, updateSettingsMutation])

  // Expose save function for parent component
  useImperativeHandle(ref, () => ({
    save: handleSaveInternal,
    hasChanges: () => hasChanges,
  }), [handleSaveInternal, hasChanges])

  // Auto-hide success message after 3 seconds
  useEffect(() => {
    if (saveSuccess) {
      const timer = setTimeout(() => setSaveSuccess(false), 3000)
      return () => clearTimeout(timer)
    }
  }, [saveSuccess])

  // Merged settings (server + local changes)
  const mergedSettings = {
    ...settings,
    ...localSettings,
  } as AISettingsType | undefined

  // Handle changes to settings
  const handleSettingsChange = useCallback((changes: Partial<AISettingsType>) => {
    setLocalSettings((prev) => ({ ...prev, ...changes }))
    setHasChanges(true)
  }, [])

  // Handle provider config changes
  const handleProviderChange = useCallback(
    (providerId: string, changes: Partial<ProviderConfig>) => {
      const currentProviders = mergedSettings?.providers || {}
      const currentConfig = currentProviders[providerId] || {
        providerId,
        enabled: false,
        model: '',
        availableModels: [],
      }

      setLocalSettings((prev) => ({
        ...prev,
        providers: {
          ...currentProviders,
          [providerId]: { ...currentConfig, ...changes },
        },
      }))
      setHasChanges(true)
    },
    [mergedSettings?.providers]
  )

  // Handle task priority changes
  const handleTaskPriorityChange = useCallback(
    (taskType: string, config: TaskPriorityConfig) => {
      const currentPriorities = mergedSettings?.task_priorities || {}

      setLocalSettings((prev) => ({
        ...prev,
        task_priorities: {
          ...currentPriorities,
          [taskType]: config,
        },
      }))
      setHasChanges(true)
    },
    [mergedSettings?.task_priorities]
  )

  const handleRefreshProviders = async () => {
    try {
      await refreshProvidersMutation.mutateAsync()
      toast.success('Providers refreshed')
    } catch {
      toast.error('Failed to refresh providers')
    }
  }

  const handleClearCache = async () => {
    try {
      const result = await clearCacheMutation.mutateAsync()
      toast.success(`Cleared ${result.cleared} cache entries`)
      refetchCacheStats()
    } catch {
      toast.error('Failed to clear cache')
    }
  }

  const handleCleanupCache = async () => {
    try {
      const result = await cleanupCacheMutation.mutateAsync()
      toast.success(`Cleaned ${result.cleaned} expired entries`)
      refetchCacheStats()
    } catch {
      toast.error('Failed to cleanup cache')
    }
  }

  const isLoading = isLoadingProviders || isLoadingSettings
  const isEnabled = mergedSettings?.enabled ?? true

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
          'bg-gradient-to-r from-synapse/5 via-transparent to-pulse/5'
        )}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={clsx(
                'w-12 h-12 rounded-xl flex items-center justify-center',
                'bg-gradient-to-br from-synapse/20 to-pulse/20',
                'border border-synapse/30 shadow-lg shadow-synapse/20'
              )}
            >
              <Sparkles className="w-6 h-6 text-synapse" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-text-primary">AI Services</h2>
              <p className="text-sm text-text-muted mt-0.5">
                Configure AI providers for intelligent automation
              </p>
            </div>
          </div>
          <button
            onClick={handleRefreshProviders}
            disabled={refreshProvidersMutation.isPending}
            className={clsx(
              'px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200',
              'bg-slate-light/20 text-text-secondary',
              'hover:bg-synapse/20 hover:text-synapse',
              'flex items-center gap-2',
              refreshProvidersMutation.isPending && 'opacity-50 cursor-not-allowed'
            )}
          >
            <RefreshCw
              className={clsx('w-4 h-4', refreshProvidersMutation.isPending && 'animate-spin')}
            />
            Refresh
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Success message after save */}
        {saveSuccess && (
          <div
            className={clsx(
              'p-3 rounded-xl flex items-center gap-3',
              'bg-success/10 border border-success/30',
              'animate-in fade-in slide-in-from-top-2 duration-200'
            )}
          >
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
            <span className="text-sm text-success font-medium">
              AI settings saved successfully!
            </span>
          </div>
        )}

        {/* Unsaved changes warning */}
        {hasChanges && !saveSuccess && (
          <div
            className={clsx(
              'p-3 rounded-xl flex items-center gap-3',
              'bg-warning/10 border border-warning/30'
            )}
          >
            <AlertCircle className="w-5 h-5 text-warning flex-shrink-0" />
            <div className="flex-1">
              <span className="text-sm text-warning">
                You have unsaved AI settings changes. Save them using the main Save button below.
              </span>
            </div>
            <button
              onClick={handleSaveInternal}
              disabled={updateSettingsMutation.isPending}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-xs font-medium',
                'bg-warning/20 text-warning hover:bg-warning/30',
                'transition-colors duration-200',
                updateSettingsMutation.isPending && 'opacity-50 cursor-not-allowed'
              )}
            >
              {updateSettingsMutation.isPending ? 'Saving...' : 'Save Now'}
            </button>
          </div>
        )}

        {/* Master Switch */}
        <div
          className={clsx(
            'p-4 rounded-xl transition-all duration-300',
            'border',
            isEnabled
              ? 'bg-gradient-to-r from-success/10 to-success/5 border-success/30'
              : 'bg-slate-dark/50 border-slate-light/20'
          )}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div
                className={clsx(
                  'w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-300',
                  isEnabled
                    ? 'bg-success/20 border border-success/30'
                    : 'bg-slate-light/20 border border-slate-light/30'
                )}
              >
                <Power
                  className={clsx(
                    'w-5 h-5 transition-colors duration-300',
                    isEnabled ? 'text-success' : 'text-text-muted'
                  )}
                />
              </div>
              <div>
                <div className="font-semibold text-text-primary">Enable AI-powered features</div>
                <div className="text-sm text-text-muted">
                  {isEnabled
                    ? 'AI providers are active and will be used for supported tasks'
                    : 'AI disabled - using rule-based fallback only'}
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => handleSettingsChange({ enabled: !isEnabled })}
              className={clsx(
                'relative w-14 h-7 rounded-full transition-all duration-300',
                isEnabled
                  ? 'bg-gradient-to-r from-success to-emerald-400 shadow-lg shadow-success/30'
                  : 'bg-slate-light/50'
              )}
            >
              <span
                className={clsx(
                  'absolute top-1 w-5 h-5 bg-white rounded-full shadow-md transition-all duration-300',
                  isEnabled ? 'left-8' : 'left-1'
                )}
              />
            </button>
          </div>
        </div>

        {/* Provider Status Summary */}
        {providers && (
          <div className="grid grid-cols-2 gap-4">
            <StatCard
              label="Available Providers"
              value={providers.available_count}
              color="success"
              icon={<Zap className="w-4 h-4 text-success" />}
            />
            <StatCard
              label="Running"
              value={providers.running_count}
              color="neural"
              icon={<Power className="w-4 h-4 text-neural" />}
            />
          </div>
        )}

        {/* Provider Cards - AI providers only (not rule_based) */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
            <span>AI Providers</span>
            <div className="flex-1 h-px bg-slate-light/30" />
          </h3>

          {AI_PROVIDERS.map((providerId) => (
            <ProviderCard
              key={providerId}
              providerId={providerId}
              status={providers?.providers[providerId]}
              config={mergedSettings?.providers?.[providerId]}
              isLoading={isLoading}
              onChange={isEnabled ? handleProviderChange : undefined}
              onRedetect={handleRefreshProviders}
            />
          ))}
        </div>

        {/* Priority Order Summary */}
        {mergedSettings?.task_priorities?.parameter_extraction && (
          <div
            className={clsx(
              'p-4 rounded-xl',
              'bg-slate-dark/30 border border-slate-light/20'
            )}
          >
            <h4 className="text-sm font-semibold text-text-secondary mb-3">Extraction Priority</h4>
            <div className="flex items-center gap-2 text-sm flex-wrap">
              {mergedSettings.task_priorities.parameter_extraction.provider_order.map((id, i, arr) => (
                <span key={id} className="flex items-center gap-2">
                  <span
                    className={clsx(
                      'px-3 py-1.5 rounded-lg font-mono text-xs',
                      'bg-synapse/10 text-synapse border border-synapse/30'
                    )}
                  >
                    {id}
                  </span>
                  {i < arr.length - 1 && <ArrowRight className="w-4 h-4 text-text-muted" />}
                </span>
              ))}
              <ArrowRight className="w-4 h-4 text-text-muted" />
              <span
                className={clsx(
                  'px-3 py-1.5 rounded-lg font-mono text-xs',
                  'bg-slate-light/20 text-text-muted border border-slate-light/30'
                )}
              >
                rule_based
              </span>
            </div>
          </div>
        )}

        {/* Task Priority Configuration */}
        <TaskPriorityConfigPanel
          taskPriorities={mergedSettings?.task_priorities}
          providers={providers?.providers}
          onChange={isEnabled ? handleTaskPriorityChange : undefined}
        />

        {/* Advanced Settings */}
        <AdvancedAISettings
          settings={mergedSettings}
          onChange={isEnabled ? handleSettingsChange : undefined}
        />

        {/* Cache Section */}
        <div className="border-t border-slate-light/30 pt-6">
          <div className="flex items-center gap-3 mb-4">
            <div
              className={clsx(
                'w-8 h-8 rounded-lg flex items-center justify-center',
                'bg-gradient-to-br from-neural/20 to-neural/10',
                'border border-neural/30'
              )}
            >
              <Database className="w-4 h-4 text-neural" />
            </div>
            <h4 className="text-sm font-semibold text-text-primary">Cache</h4>
          </div>

          {cacheStats && (
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="p-3 rounded-xl bg-slate-dark/30 border border-slate-light/20">
                <div className="text-xs text-text-muted">Entries</div>
                <div className="text-lg font-bold text-text-primary">{cacheStats.entry_count}</div>
              </div>
              <div className="p-3 rounded-xl bg-slate-dark/30 border border-slate-light/20">
                <div className="text-xs text-text-muted">Size</div>
                <div className="text-lg font-bold text-neural">
                  {typeof cacheStats.total_size_bytes === 'number'
                    ? formatBytes(cacheStats.total_size_bytes)
                    : '0 B'}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-dark/30 border border-slate-light/20">
                <div className="text-xs text-text-muted">TTL</div>
                <div className="text-lg font-bold text-text-primary">{cacheStats.ttl_days} days</div>
              </div>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={handleCleanupCache}
              disabled={cleanupCacheMutation.isPending}
              className={clsx(
                'px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200',
                'bg-slate-light/20 text-text-secondary',
                'hover:bg-neural/20 hover:text-neural',
                'flex items-center gap-2',
                cleanupCacheMutation.isPending && 'opacity-50 cursor-not-allowed'
              )}
            >
              <RefreshCw
                className={clsx('w-4 h-4', cleanupCacheMutation.isPending && 'animate-spin')}
              />
              Cleanup Expired
            </button>
            <button
              onClick={handleClearCache}
              disabled={clearCacheMutation.isPending}
              className={clsx(
                'px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200',
                'bg-slate-light/20 text-text-secondary',
                'hover:bg-red-500/20 hover:text-red-400',
                'flex items-center gap-2',
                clearCacheMutation.isPending && 'opacity-50 cursor-not-allowed'
              )}
            >
              {clearCacheMutation.isPending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              Clear All
            </button>
          </div>
        </div>

        {/* Settings Summary */}
        {mergedSettings && (
          <div className="border-t border-slate-light/30 pt-6">
            <h4 className="text-sm font-semibold text-text-secondary mb-3">Configuration Summary</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-xl bg-slate-dark/30 border border-slate-light/20">
                <div className="text-xs text-text-muted">Timeout</div>
                <div className="text-sm font-mono text-text-primary">{mergedSettings.cli_timeout_seconds}s</div>
              </div>
              <div className="p-3 rounded-xl bg-slate-dark/30 border border-slate-light/20">
                <div className="text-xs text-text-muted">Max Retries</div>
                <div className="text-sm font-mono text-text-primary">{mergedSettings.max_retries}</div>
              </div>
              <div className="p-3 rounded-xl bg-slate-dark/30 border border-slate-light/20">
                <div className="text-xs text-text-muted">Cache</div>
                <div
                  className={clsx(
                    'text-sm font-mono',
                    mergedSettings.cache_enabled ? 'text-success' : 'text-text-muted'
                  )}
                >
                  {mergedSettings.cache_enabled ? 'Enabled' : 'Disabled'}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-dark/30 border border-slate-light/20">
                <div className="text-xs text-text-muted">Fallback</div>
                <div
                  className={clsx(
                    'text-sm font-mono',
                    mergedSettings.always_fallback_to_rule_based ? 'text-success' : 'text-text-muted'
                  )}
                >
                  {mergedSettings.always_fallback_to_rule_based ? 'Always' : 'Disabled'}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
})
