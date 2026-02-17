/**
 * TaskPriorityConfig Component
 *
 * Configures provider priority order for each task type.
 * Implements PLAN spec 3.3 (Task Priority Configuration) with premium Synapse design.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { GripVertical, RotateCcw, ChevronDown, ChevronUp, ListOrdered, Sparkles, Check } from 'lucide-react'
import clsx from 'clsx'
import type {
  TaskPriorityConfig as TaskPriorityConfigType,
  ProviderStatus,
} from '../../../lib/ai/types'
import { PROVIDER_INFO, KNOWN_PROVIDERS } from '../../../lib/ai/types'

// =============================================================================
// Provider Colors (matching ProviderCard)
// =============================================================================

const PROVIDER_COLORS = {
  ollama: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    text: 'text-emerald-400',
    glow: 'shadow-emerald-500/20',
    gradient: 'from-emerald-500/20 to-emerald-600/10',
  },
  gemini: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    text: 'text-blue-400',
    glow: 'shadow-blue-500/20',
    gradient: 'from-blue-500/20 to-blue-600/10',
  },
  claude: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    glow: 'shadow-amber-500/20',
    gradient: 'from-amber-500/20 to-amber-600/10',
  },
  rule_based: {
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/30',
    text: 'text-slate-400',
    glow: 'shadow-slate-500/20',
    gradient: 'from-slate-500/20 to-slate-600/10',
  },
} as const

/**
 * Task display configuration
 * name/description keys map to settingsAi.tasks.* translations
 */
const TASK_INFO: Record<string, { nameKey: string; descKey: string; defaultOrder: string[] }> = {
  parameter_extraction: {
    nameKey: 'settingsAi.tasks.extraction',
    descKey: 'settingsAi.tasks.extractionDesc',
    defaultOrder: ['ollama', 'gemini', 'claude'],
  },
  description_translation: {
    nameKey: 'settingsAi.tasks.translation',
    descKey: 'settingsAi.tasks.translationDesc',
    defaultOrder: ['ollama', 'gemini'],
  },
  auto_tagging: {
    nameKey: 'settingsAi.tasks.tagging',
    descKey: 'settingsAi.tasks.taggingDesc',
    defaultOrder: ['ollama', 'gemini'],
  },
  workflow_generation: {
    nameKey: 'settingsAi.tasks.workflow',
    descKey: 'settingsAi.tasks.workflowDesc',
    defaultOrder: ['gemini', 'claude', 'ollama'],
  },
  model_compatibility: {
    nameKey: 'settingsAi.tasks.compatibility',
    descKey: 'settingsAi.tasks.compatibilityDesc',
    defaultOrder: ['ollama', 'gemini', 'claude'],
  },
}

// =============================================================================
// Premium Checkbox
// =============================================================================

interface PremiumCheckboxProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  color?: keyof typeof PROVIDER_COLORS
}

function PremiumCheckbox({ checked, onChange, disabled, color = 'ollama' }: PremiumCheckboxProps) {
  const colors = PROVIDER_COLORS[color] || PROVIDER_COLORS.ollama

  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={clsx(
        'w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200',
        'border-2',
        checked
          ? `${colors.bg} ${colors.border} ${colors.text} shadow-md`
          : 'border-slate-light/70 bg-slate-mid/50 hover:border-text-muted hover:bg-slate-mid',
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
      )}
    >
      {checked ? (
        <Check className="w-3.5 h-3.5" />
      ) : (
        <div className="w-2 h-2 rounded-sm bg-slate-light/40" />
      )}
    </button>
  )
}

// =============================================================================
// Task Priority Editor
// =============================================================================

interface TaskPriorityConfigProps {
  taskType: string
  config?: TaskPriorityConfigType
  providers?: Record<string, ProviderStatus>
  onChange?: (taskType: string, config: TaskPriorityConfigType) => void
}

function TaskPriorityEditor({
  taskType,
  config,
  providers,
  onChange,
}: TaskPriorityConfigProps) {
  const { t } = useTranslation()
  const [isExpanded, setIsExpanded] = useState(taskType === 'parameter_extraction')
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)

  const taskInfo = TASK_INFO[taskType] || {
    nameKey: taskType,
    descKey: '',
    defaultOrder: ['ollama', 'gemini', 'claude'],
  }

  // Current provider order (from config or default)
  const providerOrder = config?.provider_order || taskInfo.defaultOrder

  // Filter to only include actual AI providers (not rule_based)
  const availableProviders = KNOWN_PROVIDERS.filter((p) => p !== 'rule_based')

  // Build ordered list with enabled state
  const orderedItems = providerOrder
    .filter((p) => availableProviders.includes(p as (typeof availableProviders)[number]))
    .map((providerId) => ({
      providerId,
      enabled: config?.provider_order?.includes(providerId) ?? true,
      status: providers?.[providerId],
    }))

  // Add any providers not in the list at the end (disabled)
  availableProviders.forEach((p) => {
    if (!orderedItems.some((item) => item.providerId === p)) {
      orderedItems.push({
        providerId: p,
        enabled: false,
        status: providers?.[p],
      })
    }
  })

  const handleDragStart = (index: number) => {
    setDraggedIndex(index)
  }

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    if (draggedIndex === null || draggedIndex === index) return

    // Reorder
    const newOrder = [...orderedItems]
    const [dragged] = newOrder.splice(draggedIndex, 1)
    newOrder.splice(index, 0, dragged)

    // Update config
    const newProviderOrder = newOrder.filter((item) => item.enabled).map((item) => item.providerId)
    onChange?.(taskType, {
      task_type: taskType,
      provider_order: newProviderOrder,
    })

    setDraggedIndex(index)
  }

  const handleDragEnd = () => {
    setDraggedIndex(null)
  }

  const handleToggleProvider = (providerId: string, enabled: boolean) => {
    const newOrder = enabled
      ? [...providerOrder, providerId]
      : providerOrder.filter((p) => p !== providerId)

    onChange?.(taskType, {
      task_type: taskType,
      provider_order: newOrder,
    })
  }

  const handleReset = () => {
    onChange?.(taskType, {
      task_type: taskType,
      provider_order: taskInfo.defaultOrder,
    })
  }

  return (
    <div
      className={clsx(
        'rounded-xl overflow-hidden transition-all duration-300',
        'border border-slate-light/20',
        isExpanded && 'border-synapse/30 shadow-lg shadow-synapse/5'
      )}
    >
      {/* Task Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className={clsx(
          'flex items-center justify-between w-full p-4 text-left transition-all duration-200',
          'hover:bg-slate-mid/30 group',
          isExpanded && 'bg-slate-mid/20'
        )}
      >
        <div className="flex items-center gap-3">
          <div
            className={clsx(
              'w-8 h-8 rounded-lg flex items-center justify-center',
              'bg-gradient-to-br from-synapse/20 to-pulse/10',
              'border border-synapse/30'
            )}
          >
            <Sparkles className="w-4 h-4 text-synapse" />
          </div>
          <div>
            <div className="font-semibold text-sm text-text-primary">{t(taskInfo.nameKey)}</div>
            {taskInfo.descKey && (
              <div className="text-xs text-text-muted mt-0.5">{t(taskInfo.descKey)}</div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {onChange && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                handleReset()
              }}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
                'bg-slate-light/20 text-text-secondary',
                'hover:bg-synapse/20 hover:text-synapse',
                'flex items-center gap-1.5'
              )}
            >
              <RotateCcw className="w-3 h-3" />
              {t('settingsAi.tasks.reset')}
            </button>
          )}
          <div
            className={clsx(
              'w-6 h-6 rounded-lg flex items-center justify-center transition-all duration-200',
              'bg-slate-light/30',
              isExpanded && 'bg-synapse/20'
            )}
          >
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-text-secondary" />
            ) : (
              <ChevronDown className="w-4 h-4 text-text-secondary" />
            )}
          </div>
        </div>
      </button>

      {/* Provider List */}
      {isExpanded && (
        <div className="border-t border-slate-light/20 p-4 space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="text-xs text-text-muted mb-3 flex items-center gap-2">
            <GripVertical className="w-3 h-3" />
            {t('settingsAi.tasks.dragHint')}
          </div>

          {orderedItems.map((item, index) => {
            const info = PROVIDER_INFO[item.providerId]
            const isAvailable = item.status?.available ?? false
            const colors = PROVIDER_COLORS[item.providerId as keyof typeof PROVIDER_COLORS] || PROVIDER_COLORS.ollama

            return (
              <div
                key={item.providerId}
                draggable={!!onChange}
                onDragStart={() => handleDragStart(index)}
                onDragOver={(e) => handleDragOver(e, index)}
                onDragEnd={handleDragEnd}
                className={clsx(
                  'flex items-center gap-3 p-3 rounded-xl transition-all duration-200',
                  'border bg-gradient-to-r',
                  draggedIndex === index
                    ? 'opacity-50 border-synapse/50 shadow-lg shadow-synapse/20'
                    : item.enabled
                      ? `${colors.border} ${colors.gradient}`
                      : 'border-slate-light/10 from-slate-dark/30 to-slate-dark/20 opacity-60',
                  onChange && 'cursor-grab active:cursor-grabbing'
                )}
              >
                {onChange && (
                  <GripVertical className="w-4 h-4 text-text-muted flex-shrink-0" />
                )}

                <PremiumCheckbox
                  checked={item.enabled && isAvailable}
                  onChange={(checked) => handleToggleProvider(item.providerId, checked)}
                  disabled={!onChange || !isAvailable}
                  color={item.providerId as keyof typeof PROVIDER_COLORS}
                />

                <span className="text-xl">{info?.icon || '?'}</span>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={clsx('text-sm font-medium', colors.text)}>
                      {info?.name || item.providerId}
                    </span>
                    {!isAvailable && (
                      <span
                        className={clsx(
                          'text-[10px] px-2 py-0.5 rounded-full',
                          'bg-red-500/10 text-red-400 border border-red-500/30'
                        )}
                      >
                        {t('settingsAi.tasks.notInstalled')}
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-xs text-text-muted font-mono">
                  {item.status?.models?.[0] || '—'}
                </div>
              </div>
            )
          })}

          {/* Rule-based Fallback */}
          <div
            className={clsx(
              'flex items-center gap-3 p-3 rounded-xl mt-4',
              'bg-gradient-to-r from-slate-mid/30 to-slate-dark/30',
              'border border-dashed border-slate-light/30'
            )}
          >
            <div className="w-4 h-4" /> {/* Spacer for alignment */}
            <div
              className={clsx(
                'w-5 h-5 rounded-full flex items-center justify-center',
                'border-2 border-slate-light/50'
              )}
            >
              <div className="w-2 h-2 rounded-full bg-slate-light/70" />
            </div>
            <span className="text-xl">{PROVIDER_INFO.rule_based?.icon}</span>
            <div className="flex-1">
              <span className="text-sm font-medium text-text-muted">{t('settingsAi.tasks.ruleBased')}</span>
            </div>
            <div className="text-xs text-text-muted italic">{t('settingsAi.tasks.alwaysFallback')}</div>
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Panel
// =============================================================================

interface TaskPriorityConfigPanelProps {
  taskPriorities?: Record<string, TaskPriorityConfigType>
  providers?: Record<string, ProviderStatus>
  onChange?: (taskType: string, config: TaskPriorityConfigType) => void
  onResetAll?: () => void
}

export function TaskPriorityConfigPanel({
  taskPriorities,
  providers,
  onChange,
  onResetAll,
}: TaskPriorityConfigPanelProps) {
  const { t } = useTranslation()
  const [isExpanded, setIsExpanded] = useState(false)

  // For Phase 1, we only show parameter_extraction
  // Other tasks can be added when implemented
  const activeTasks = ['parameter_extraction']

  return (
    <div className="border-t border-slate-light/30 pt-4 mt-4">
      {/* Section Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className={clsx(
          'flex items-center gap-3 w-full p-3 rounded-xl transition-all duration-200',
          'hover:bg-slate-mid/50 group',
          isExpanded && 'bg-slate-mid/30'
        )}
      >
        <div
          className={clsx(
            'w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300',
            'bg-gradient-to-br from-slate-mid to-slate-dark',
            'border border-slate-light/30',
            'group-hover:border-pulse/30 group-hover:shadow-lg group-hover:shadow-pulse/10'
          )}
        >
          <ListOrdered className="w-4 h-4 text-pulse" />
        </div>
        <span className="text-sm font-semibold text-text-primary">{t('settingsAi.tasks.title')}</span>
        <div
          className={clsx(
            'ml-auto w-6 h-6 rounded-lg flex items-center justify-center',
            'bg-slate-light/30 transition-all duration-200',
            isExpanded && 'bg-pulse/20'
          )}
        >
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-text-secondary" />
          ) : (
            <ChevronDown className="w-4 h-4 text-text-secondary" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="mt-4 space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
          <p className="text-xs text-text-muted px-1">
            {t('settingsAi.tasks.description')}
          </p>

          {activeTasks.map((taskType) => (
            <TaskPriorityEditor
              key={taskType}
              taskType={taskType}
              config={taskPriorities?.[taskType]}
              providers={providers}
              onChange={onChange}
            />
          ))}

          {onResetAll && (
            <div className="pt-2">
              <button
                type="button"
                onClick={onResetAll}
                className={clsx(
                  'px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200',
                  'bg-slate-light/20 text-text-secondary',
                  'hover:bg-synapse/20 hover:text-synapse',
                  'flex items-center gap-2'
                )}
              >
                <RotateCcw className="w-4 h-4" />
                {t('settingsAi.tasks.useDefaults')}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
