/**
 * AdvancedAISettings Component
 *
 * Advanced settings accordion for AI services.
 * Implements PLAN spec 3.2 (Advanced Settings) with premium Synapse design.
 */

import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronUp, Settings2, Timer, Database, Shield, FileText, Minus, Plus } from 'lucide-react'
import clsx from 'clsx'
import type { AIServicesSettings } from '../../../lib/ai/types'

// =============================================================================
// Premium Toggle Switch
// =============================================================================

interface ToggleSwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  label: string
  description?: string
}

function ToggleSwitch({ checked, onChange, disabled, label, description }: ToggleSwitchProps) {
  return (
    <label
      className={clsx(
        'flex items-center gap-3 p-3 rounded-xl transition-all duration-200 cursor-pointer group',
        'hover:bg-slate-mid/50',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => !disabled && onChange(!checked)}
        disabled={disabled}
        className={clsx(
          'relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0',
          'focus:outline-none focus:ring-2 focus:ring-synapse/50 focus:ring-offset-2 focus:ring-offset-slate-dark',
          checked
            ? 'bg-gradient-to-r from-synapse to-pulse shadow-lg shadow-synapse/30'
            : 'bg-slate-light'
        )}
      >
        <span
          className={clsx(
            'absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-md transition-all duration-300',
            checked ? 'left-[22px]' : 'left-0.5'
          )}
        />
      </button>
      <div className="flex-1 min-w-0">
        <span className="text-sm font-medium text-text-primary">{label}</span>
        {description && (
          <p className="text-xs text-text-muted mt-0.5">{description}</p>
        )}
      </div>
    </label>
  )
}

// =============================================================================
// Premium Number Input (without native arrows)
// =============================================================================

interface NumberInputProps {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  disabled?: boolean
  label: string
  unit?: string
}

function NumberInput({ value, onChange, min = 0, max = 999, disabled, label, unit }: NumberInputProps) {
  const handleIncrement = () => {
    if (!disabled && value < max) {
      onChange(value + 1)
    }
  }

  const handleDecrement = () => {
    if (!disabled && value > min) {
      onChange(value - 1)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = parseInt(e.target.value, 10)
    if (!isNaN(newValue)) {
      onChange(Math.min(max, Math.max(min, newValue)))
    }
  }

  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-text-secondary">{label}</label>
      <div className="relative flex items-center">
        <button
          type="button"
          onClick={handleDecrement}
          disabled={disabled || value <= min}
          className={clsx(
            'w-8 h-10 flex items-center justify-center rounded-l-xl',
            'bg-slate-light/30 border border-r-0 border-slate-light/50',
            'text-text-secondary hover:text-text-primary hover:bg-slate-light/50',
            'transition-all duration-150',
            (disabled || value <= min) && 'opacity-50 cursor-not-allowed'
          )}
        >
          <Minus className="w-3 h-3" />
        </button>
        <input
          type="text"
          inputMode="numeric"
          value={value}
          onChange={handleInputChange}
          disabled={disabled}
          className={clsx(
            'w-full h-10 px-3 text-sm text-center bg-slate-dark/50',
            'border-y border-slate-light/50 text-text-primary',
            'focus:outline-none focus:border-synapse/50',
            'placeholder:text-text-muted',
            disabled && 'opacity-50 cursor-not-allowed',
            '[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none'
          )}
        />
        <button
          type="button"
          onClick={handleIncrement}
          disabled={disabled || value >= max}
          className={clsx(
            'w-8 h-10 flex items-center justify-center rounded-r-xl',
            'bg-slate-light/30 border border-l-0 border-slate-light/50',
            'text-text-secondary hover:text-text-primary hover:bg-slate-light/50',
            'transition-all duration-150',
            (disabled || value >= max) && 'opacity-50 cursor-not-allowed'
          )}
        >
          <Plus className="w-3 h-3" />
        </button>
        {unit && (
          <span className="absolute right-12 top-1/2 -translate-y-1/2 text-xs text-text-muted pointer-events-none">
            {unit}
          </span>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Premium Select Dropdown
// =============================================================================

interface SelectOption {
  value: string
  label: string
  description?: string
}

interface SelectDropdownProps {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  disabled?: boolean
  label: string
}

function SelectDropdown({ value, onChange, options, disabled, label }: SelectDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selectedOption = options.find((opt) => opt.value === value)

  return (
    <div className="space-y-2" ref={dropdownRef}>
      <label className="text-xs font-medium text-text-secondary">{label}</label>
      <div className="relative">
        <button
          type="button"
          onClick={() => !disabled && setIsOpen(!isOpen)}
          disabled={disabled}
          className={clsx(
            'w-full h-10 px-3 text-sm bg-slate-dark/50 rounded-xl transition-all duration-200',
            'border border-slate-light/50 text-text-primary text-left',
            'flex items-center justify-between',
            'focus:outline-none focus:border-synapse/50 focus:ring-2 focus:ring-synapse/20',
            disabled && 'opacity-50 cursor-not-allowed',
            isOpen && 'border-synapse/50 ring-2 ring-synapse/20'
          )}
        >
          <span>{selectedOption?.label || value}</span>
          <ChevronDown
            className={clsx(
              'w-4 h-4 text-text-muted transition-transform duration-200',
              isOpen && 'rotate-180'
            )}
          />
        </button>

        {isOpen && (
          <div
            className={clsx(
              'absolute z-50 top-full left-0 right-0 mt-2',
              'bg-slate-dark/95 backdrop-blur-xl rounded-xl',
              'border border-slate-light/30 shadow-xl shadow-black/50',
              'overflow-hidden',
              'animate-in fade-in slide-in-from-top-2 duration-200'
            )}
          >
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value)
                  setIsOpen(false)
                }}
                className={clsx(
                  'w-full px-3 py-2.5 text-left transition-all duration-150',
                  'hover:bg-synapse/10',
                  value === option.value && 'bg-synapse/20 text-synapse'
                )}
              >
                <div className="text-sm font-medium">{option.label}</div>
                {option.description && (
                  <div className="text-xs text-text-muted mt-0.5">{option.description}</div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Section Header
// =============================================================================

interface SectionHeaderProps {
  icon: React.ElementType
  title: string
  color?: 'synapse' | 'pulse' | 'neural' | 'success' | 'warning'
}

const SECTION_COLORS = {
  synapse: 'text-synapse',
  pulse: 'text-pulse',
  neural: 'text-neural',
  success: 'text-success',
  warning: 'text-warning',
}

function SectionHeader({ icon: Icon, title, color = 'synapse' }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <div
        className={clsx(
          'w-8 h-8 rounded-lg flex items-center justify-center',
          'bg-gradient-to-br from-slate-mid to-slate-dark',
          'border border-slate-light/30'
        )}
      >
        <Icon className={clsx('w-4 h-4', SECTION_COLORS[color])} />
      </div>
      <h4 className="text-sm font-semibold text-text-primary">{title}</h4>
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

interface AdvancedAISettingsProps {
  settings?: AIServicesSettings
  onChange?: (changes: Partial<AIServicesSettings>) => void
}

export function AdvancedAISettings({ settings, onChange }: AdvancedAISettingsProps) {
  const { t } = useTranslation()
  const [isExpanded, setIsExpanded] = useState(false)

  const handleChange = <K extends keyof AIServicesSettings>(
    key: K,
    value: AIServicesSettings[K]
  ) => {
    if (onChange) {
      onChange({ [key]: value })
    }
  }

  const LOG_LEVEL_OPTIONS: SelectOption[] = [
    { value: 'DEBUG', label: t('settingsAi.advanced.logLevels.debug'), description: t('settingsAi.advanced.logLevels.debugDesc') },
    { value: 'INFO', label: t('settingsAi.advanced.logLevels.info'), description: t('settingsAi.advanced.logLevels.infoDesc') },
    { value: 'WARNING', label: t('settingsAi.advanced.logLevels.warning'), description: t('settingsAi.advanced.logLevels.warningDesc') },
    { value: 'ERROR', label: t('settingsAi.advanced.logLevels.error'), description: t('settingsAi.advanced.logLevels.errorDesc') },
  ]

  // Use snake_case field names matching API
  const cacheEnabled = settings?.cache_enabled ?? true

  return (
    <div className="border-t border-slate-light/30 pt-4 mt-4">
      {/* Accordion Header */}
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
            'group-hover:border-synapse/30 group-hover:shadow-lg group-hover:shadow-synapse/10'
          )}
        >
          <Settings2 className="w-4 h-4 text-synapse" />
        </div>
        <span className="text-sm font-semibold text-text-primary">{t('settingsAi.advanced.title')}</span>
        <div
          className={clsx(
            'ml-auto w-6 h-6 rounded-lg flex items-center justify-center',
            'bg-slate-light/30 transition-all duration-200',
            isExpanded && 'bg-synapse/20'
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
        <div className="mt-4 space-y-6 animate-in fade-in slide-in-from-top-2 duration-300">
          {/* Timeouts & Retries */}
          <section className="p-4 rounded-xl bg-slate-dark/30 border border-slate-light/20">
            <SectionHeader icon={Timer} title={t('settingsAi.advanced.timeoutsRetries')} color="synapse" />
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <NumberInput
                label={t('settingsAi.advanced.cliTimeout')}
                value={settings?.cli_timeout_seconds ?? 60}
                onChange={(v) => handleChange('cli_timeout_seconds', v)}
                min={10}
                max={300}
                unit="sec"
                disabled={!onChange}
              />
              <NumberInput
                label={t('settingsAi.advanced.maxRetries')}
                value={settings?.max_retries ?? 2}
                onChange={(v) => handleChange('max_retries', v)}
                min={0}
                max={5}
                disabled={!onChange}
              />
              <NumberInput
                label={t('settingsAi.advanced.retryDelay')}
                value={settings?.retry_delay_seconds ?? 1}
                onChange={(v) => handleChange('retry_delay_seconds', v)}
                min={0}
                max={10}
                unit="sec"
                disabled={!onChange}
              />
            </div>
          </section>

          {/* Caching */}
          <section className="p-4 rounded-xl bg-slate-dark/30 border border-slate-light/20">
            <SectionHeader icon={Database} title={t('settingsAi.advanced.caching')} color="neural" />
            <div className="space-y-4">
              <ToggleSwitch
                checked={cacheEnabled}
                onChange={(v) => handleChange('cache_enabled', v)}
                disabled={!onChange}
                label={t('settingsAi.advanced.cacheResults')}
                description={t('settingsAi.advanced.cacheResultsDesc')}
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pl-2">
                <NumberInput
                  label={t('settingsAi.advanced.cacheTtl')}
                  value={settings?.cache_ttl_days ?? 30}
                  onChange={(v) => handleChange('cache_ttl_days', v)}
                  min={1}
                  max={365}
                  unit="days"
                  disabled={!onChange || !cacheEnabled}
                />
              </div>

              {settings?.cache_directory && (
                <div className="mt-3 p-3 rounded-lg bg-slate-mid/30 border border-slate-light/10">
                  <span className="text-xs text-text-muted">{t('settingsAi.advanced.cacheLocation')}</span>
                  <code className="ml-2 text-xs font-mono text-neural">
                    {settings.cache_directory}
                  </code>
                </div>
              )}
            </div>
          </section>

          {/* Fallback Behavior */}
          <section className="p-4 rounded-xl bg-slate-dark/30 border border-slate-light/20">
            <SectionHeader icon={Shield} title={t('settingsAi.advanced.fallbackBehavior')} color="success" />
            <div className="space-y-1">
              <ToggleSwitch
                checked={settings?.always_fallback_to_rule_based ?? true}
                onChange={(v) => handleChange('always_fallback_to_rule_based', v)}
                disabled={!onChange}
                label={t('settingsAi.advanced.alwaysFallback')}
                description={t('settingsAi.advanced.alwaysFallbackDesc')}
              />
              <ToggleSwitch
                checked={settings?.show_provider_in_results ?? true}
                onChange={(v) => handleChange('show_provider_in_results', v)}
                disabled={!onChange}
                label={t('settingsAi.advanced.showProvider')}
                description={t('settingsAi.advanced.showProviderDesc')}
              />
            </div>
          </section>

          {/* Logging */}
          <section className="p-4 rounded-xl bg-slate-dark/30 border border-slate-light/20">
            <SectionHeader icon={FileText} title={t('settingsAi.advanced.logging')} color="warning" />
            <div className="space-y-4">
              <ToggleSwitch
                checked={settings?.log_requests ?? true}
                onChange={(v) => handleChange('log_requests', v)}
                disabled={!onChange}
                label={t('settingsAi.advanced.logRequests')}
                description={t('settingsAi.advanced.logRequestsDesc')}
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pl-2">
                <SelectDropdown
                  label={t('settingsAi.advanced.logLevel')}
                  value={settings?.log_level ?? 'INFO'}
                  onChange={(v) => handleChange('log_level', v as AIServicesSettings['log_level'])}
                  options={LOG_LEVEL_OPTIONS}
                  disabled={!onChange}
                />
              </div>

              <div className="border-t border-slate-light/20 pt-4 mt-4">
                <p className="text-xs text-text-muted mb-3">{t('settingsAi.advanced.debugOptions')}</p>
                <div className="space-y-1">
                  <ToggleSwitch
                    checked={settings?.log_prompts ?? false}
                    onChange={(v) => handleChange('log_prompts', v)}
                    disabled={!onChange}
                    label={t('settingsAi.advanced.logFullPrompts')}
                    description={t('settingsAi.advanced.logFullPromptsDesc')}
                  />
                  <ToggleSwitch
                    checked={settings?.log_responses ?? false}
                    onChange={(v) => handleChange('log_responses', v)}
                    disabled={!onChange}
                    label={t('settingsAi.advanced.logRawResponses')}
                    description={t('settingsAi.advanced.logRawResponsesDesc')}
                  />
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
