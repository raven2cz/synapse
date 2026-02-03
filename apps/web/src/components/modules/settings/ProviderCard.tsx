/**
 * ProviderCard Component - Premium AI Provider UI
 *
 * Implements PLAN spec 3.1 and 3.4 with premium Synapse styling.
 * Features gradient borders, glow effects, custom dropdowns, smooth animations.
 */

import { useState, useRef, useEffect, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import {
  CheckCircle2,
  XCircle,
  Circle,
  RefreshCw,
  ChevronDown,
  ExternalLink,
  Zap,
  Server,
  Check,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '../../ui/Button'
import type { ProviderStatus, ProviderConfig } from '../../../lib/ai/types'
import { PROVIDER_INFO, RECOMMENDED_MODELS } from '../../../lib/ai/types'

interface ProviderCardProps {
  providerId: string
  status?: ProviderStatus
  config?: ProviderConfig
  isLoading?: boolean
  onChange?: (providerId: string, changes: Partial<ProviderConfig>) => void
  onRedetect?: () => void
}

/**
 * Premium color schemes for each provider
 */
const PROVIDER_COLORS: Record<string, {
  gradient: string
  border: string
  glow: string
  icon: string
  badge: string
}> = {
  ollama: {
    gradient: 'from-emerald-500/20 via-teal-500/15 to-cyan-500/20',
    border: 'border-emerald-500/40',
    glow: 'shadow-emerald-500/20',
    icon: 'text-emerald-400',
    badge: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  },
  gemini: {
    gradient: 'from-blue-500/20 via-indigo-500/15 to-violet-500/20',
    border: 'border-blue-500/40',
    glow: 'shadow-blue-500/20',
    icon: 'text-blue-400',
    badge: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
  },
  claude: {
    gradient: 'from-amber-500/20 via-orange-500/15 to-rose-500/20',
    border: 'border-amber-500/40',
    glow: 'shadow-amber-500/20',
    icon: 'text-amber-400',
    badge: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
  },
  rule_based: {
    gradient: 'from-slate-500/20 via-slate-400/15 to-slate-500/20',
    border: 'border-slate-500/40',
    glow: 'shadow-slate-500/10',
    icon: 'text-slate-400',
    badge: 'bg-slate-500/20 text-slate-400 border-slate-500/40',
  },
}

/**
 * Installation instructions for each provider (spec 3.4)
 */
const INSTALL_INSTRUCTIONS: Record<
  string,
  { platforms: { name: string; command: string }[]; postInstall?: string; docUrl?: string }
> = {
  ollama: {
    platforms: [
      { name: 'Arch Linux', command: 'yay -S ollama-cuda' },
      { name: 'Ubuntu/Debian', command: 'curl -fsSL https://ollama.com/install.sh | sh' },
      { name: 'macOS', command: 'brew install ollama' },
      { name: 'Windows', command: 'winget install ollama' },
    ],
    postInstall: 'ollama pull qwen2.5:14b',
    docUrl: 'https://ollama.com/docs',
  },
  gemini: {
    platforms: [{ name: 'npm', command: 'npm install -g @anthropic-ai/gemini-cli' }],
    postInstall: 'gemini auth login',
    docUrl: 'https://github.com/google-gemini/gemini-cli',
  },
  claude: {
    platforms: [{ name: 'npm', command: 'npm install -g @anthropic-ai/claude-code' }],
    postInstall: 'claude auth',
    docUrl: 'https://claude.ai/claude-code',
  },
}

/**
 * Model Selector - Editable input with dropdown suggestions
 * Uses React Portal to render dropdown outside container (prevents clipping)
 */
function ModelSelector({
  value,
  options,
  onChange,
  disabled,
  placeholder = 'Enter or select model...',
}: {
  value: string
  options: string[]
  onChange: (value: string) => void
  disabled?: boolean
  placeholder?: string
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [inputValue, setInputValue] = useState(value)
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, width: 0 })
  const containerRef = useRef<HTMLDivElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Sync input value when prop changes
  useEffect(() => {
    setInputValue(value)
  }, [value])

  // Update dropdown position when opened
  useLayoutEffect(() => {
    if (isOpen && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      setDropdownPosition({
        top: rect.bottom + window.scrollY + 4,
        left: rect.left + window.scrollX,
        width: rect.width,
      })
    }
  }, [isOpen])

  // Close on click outside (check both container and portal dropdown)
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node
      const clickedContainer = containerRef.current?.contains(target)
      const clickedDropdown = dropdownRef.current?.contains(target)

      if (!clickedContainer && !clickedDropdown) {
        setIsOpen(false)
        // Apply value on blur if changed
        if (inputValue !== value && inputValue.trim()) {
          onChange(inputValue.trim())
        }
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [inputValue, value, onChange])

  // Close on scroll OUTSIDE dropdown (page scroll would make position stale)
  // But allow scrolling INSIDE the dropdown list
  useEffect(() => {
    if (!isOpen) return
    const handleScroll = (e: Event) => {
      // Don't close if scrolling inside the dropdown
      if (dropdownRef.current?.contains(e.target as Node)) {
        return
      }
      setIsOpen(false)
    }
    window.addEventListener('scroll', handleScroll, true)
    return () => window.removeEventListener('scroll', handleScroll, true)
  }, [isOpen])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value)
    if (!isOpen) setIsOpen(true)
  }

  const handleInputFocus = () => {
    if (!disabled && options.length > 0) {
      setIsOpen(true)
    }
  }

  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      onChange(inputValue.trim())
      setIsOpen(false)
      inputRef.current?.blur()
    }
    if (e.key === 'Escape') {
      setIsOpen(false)
      setInputValue(value)
      inputRef.current?.blur()
    }
  }

  const handleSelectOption = (option: string) => {
    setInputValue(option)
    onChange(option)
    setIsOpen(false)
  }

  // Filter options based on input - but show ALL options if input matches current value
  // This allows user to see all options when opening dropdown, and filter only when typing
  const isFilterActive = inputValue !== value && inputValue.trim() !== ''
  const filteredOptions = isFilterActive
    ? options.filter((opt) => opt.toLowerCase().includes(inputValue.toLowerCase()))
    : options

  // Check if current input is a custom value (not in options)
  const isCustomValue = inputValue && !options.includes(inputValue)

  // Dropdown content (rendered via portal)
  const dropdownContent = isOpen && (
    <div
      ref={dropdownRef}
      style={{
        position: 'absolute',
        top: dropdownPosition.top,
        left: dropdownPosition.left,
        width: dropdownPosition.width,
        zIndex: 9999,
      }}
      className={clsx(
        'bg-slate-darker/98 backdrop-blur-xl',
        'border border-slate-mid/40 rounded-xl',
        'shadow-2xl shadow-black/50',
        'animate-in fade-in slide-in-from-top-2 duration-150',
        'max-h-[280px] overflow-y-auto',
        'p-1'
      )}
    >
      {/* Custom value option */}
      {isCustomValue && inputValue.trim() && (
        <button
          type="button"
          onClick={() => handleSelectOption(inputValue.trim())}
          className={clsx(
            'w-full px-3 py-2 flex items-center gap-2 rounded-lg',
            'text-sm text-left transition-colors duration-150',
            'bg-pulse/10 text-pulse hover:bg-pulse/20',
            'border-b border-slate-mid/30 mb-1'
          )}
        >
          <span className="text-xs">Use custom:</span>
          <span className="font-mono text-xs font-semibold flex-1">{inputValue}</span>
        </button>
      )}

      {/* Suggested models */}
      {filteredOptions.length > 0 ? (
        <>
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider text-text-muted">
            Available models
          </div>
          {filteredOptions.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => handleSelectOption(option)}
              className={clsx(
                'w-full px-3 py-2 flex items-center gap-2 rounded-lg',
                'text-sm text-left transition-colors duration-150',
                value === option
                  ? 'bg-synapse/20 text-synapse'
                  : 'text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary'
              )}
            >
              <span className="font-mono text-xs flex-1">{option}</span>
              {value === option && <Check className="w-4 h-4" />}
            </button>
          ))}
        </>
      ) : (
        <div className="px-3 py-4 text-center text-xs text-text-muted">
          No matching models. Type to use a custom model name.
        </div>
      )}
    </div>
  )

  return (
    <div className="relative flex-1" ref={containerRef}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onKeyDown={handleInputKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          className={clsx(
            'w-full h-9 pl-3 pr-8 font-mono text-xs',
            'bg-slate-dark/80 backdrop-blur-sm',
            'border border-slate-mid/50 rounded-lg',
            'text-text-primary placeholder-text-muted',
            'transition-all duration-200',
            !disabled && 'hover:border-synapse/40 hover:bg-slate-mid/50',
            'focus:outline-none focus:border-synapse/50 focus:ring-2 focus:ring-synapse/20',
            disabled && 'opacity-50 cursor-not-allowed',
            isCustomValue && 'border-pulse/50 bg-pulse/5'
          )}
        />
        <button
          type="button"
          onClick={() => !disabled && setIsOpen(!isOpen)}
          disabled={disabled}
          className={clsx(
            'absolute right-1 top-1/2 -translate-y-1/2 p-1.5 rounded-md',
            'text-text-muted hover:text-text-secondary hover:bg-slate-mid/50',
            'transition-all duration-150',
            disabled && 'pointer-events-none'
          )}
        >
          <ChevronDown
            className={clsx(
              'w-4 h-4 transition-transform duration-200',
              isOpen && 'rotate-180'
            )}
          />
        </button>
      </div>

      {/* Render dropdown via portal to body */}
      {dropdownContent && createPortal(dropdownContent, document.body)}
    </div>
  )
}

/**
 * Status Badge with glow effect
 */
function StatusBadge({ status }: { status?: ProviderStatus }) {
  if (!status) {
    return (
      <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-mid/50 border border-slate-mid/50">
        <Circle className="w-2.5 h-2.5 text-text-muted" />
        <span className="text-xs font-medium text-text-muted">Unknown</span>
      </span>
    )
  }

  if (status.running) {
    return (
      <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-success/15 border border-success/40">
        <span
          className="w-2 h-2 rounded-full bg-success"
          style={{
            boxShadow: '0 0 8px rgba(34, 197, 94, 0.8)',
            animation: 'pulse 2s ease-in-out infinite',
          }}
        />
        <span className="text-xs font-semibold text-success uppercase tracking-wide">Running</span>
      </span>
    )
  }

  if (status.available) {
    return (
      <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-warning/15 border border-warning/40">
        <Circle className="w-2.5 h-2.5 text-warning fill-warning" />
        <span className="text-xs font-semibold text-warning uppercase tracking-wide">Available</span>
      </span>
    )
  }

  return (
    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-error/15 border border-error/40">
      <XCircle className="w-2.5 h-2.5 text-error" />
      <span className="text-xs font-semibold text-error uppercase tracking-wide">Not Installed</span>
    </span>
  )
}

/**
 * Premium Installation Guide (spec 3.4)
 */
function InstallationGuide({
  providerId,
  onRedetect,
}: {
  providerId: string
  onRedetect?: () => void
}) {
  const instructions = INSTALL_INSTRUCTIONS[providerId]
  if (!instructions) return null

  return (
    <div className="mt-4 pt-4 border-t border-slate-mid/30 space-y-4">
      <div className="flex items-center gap-2">
        <Server className="w-4 h-4 text-text-muted" />
        <span className="text-sm font-medium text-text-secondary">Installation Required</span>
      </div>

      <div className="space-y-2">
        {instructions.platforms.map((platform) => (
          <div
            key={platform.name}
            className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-dark/60 border border-slate-mid/30"
          >
            <span className="text-xs text-text-muted min-w-[90px]">{platform.name}</span>
            <code className="flex-1 text-[11px] font-mono text-neural bg-slate-darker/80 px-2 py-1 rounded">
              {platform.command}
            </code>
          </div>
        ))}
      </div>

      {instructions.postInstall && (
        <div className="p-3 rounded-lg bg-synapse/5 border border-synapse/20">
          <span className="text-xs text-text-muted">After installation:</span>
          <code className="block mt-1 text-xs font-mono text-synapse">{instructions.postInstall}</code>
        </div>
      )}

      <div className="flex items-center gap-2 pt-2">
        {instructions.docUrl && (
          <a
            href={instructions.docUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={clsx(
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg',
              'bg-slate-dark/80 border border-slate-mid/50',
              'text-xs font-medium text-text-secondary',
              'hover:border-synapse/40 hover:text-text-primary',
              'transition-all duration-200'
            )}
          >
            <ExternalLink className="w-3 h-3" />
            Documentation
          </a>
        )}
        {onRedetect && (
          <Button variant="secondary" size="sm" onClick={onRedetect}>
            <RefreshCw className="w-3 h-3 mr-1.5" />
            Re-detect
          </Button>
        )}
      </div>
    </div>
  )
}

/**
 * Premium Checkbox Toggle - High visibility for both states
 */
function ToggleCheckbox({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean
  onChange: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      disabled={disabled}
      className={clsx(
        'w-6 h-6 rounded-lg flex items-center justify-center',
        'border-2 transition-all duration-200',
        checked
          ? 'bg-gradient-to-r from-synapse to-pulse border-synapse shadow-lg shadow-synapse/30'
          : 'bg-slate-mid/50 border-slate-light/60 hover:border-text-muted hover:bg-slate-mid',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
      aria-label={checked ? 'Disable' : 'Enable'}
    >
      {checked ? (
        <Check className="w-3.5 h-3.5 text-white" strokeWidth={3} />
      ) : (
        <div className="w-2 h-2 rounded-sm bg-slate-light/40" />
      )}
    </button>
  )
}

export function ProviderCard({
  providerId,
  status,
  config,
  isLoading,
  onChange,
  onRedetect,
}: ProviderCardProps) {
  const [showEndpoint, setShowEndpoint] = useState(false)
  const [isRefreshingModels, setIsRefreshingModels] = useState(false)

  const handleRefreshModels = async () => {
    if (!onRedetect || isRefreshingModels) return
    setIsRefreshingModels(true)
    try {
      await onRedetect()
    } finally {
      // Small delay to show the animation
      setTimeout(() => setIsRefreshingModels(false), 500)
    }
  }

  const info = PROVIDER_INFO[providerId] || {
    id: providerId,
    name: providerId,
    type: 'local',
    icon: '?',
    description: 'Unknown provider',
  }

  const colors = PROVIDER_COLORS[providerId] || PROVIDER_COLORS.rule_based

  const isEnabled = config?.enabled ?? false
  const isAvailable = status?.available ?? false
  const isRuleBased = providerId === 'rule_based'
  const currentModel = config?.model || status?.models?.[0] || ''

  // Combine API-detected models with recommended models (unique, detected first)
  const apiModels = status?.models || config?.availableModels || []
  const recommendedModels = RECOMMENDED_MODELS[providerId] || []
  const availableModels = [
    ...apiModels,
    ...recommendedModels.filter((m) => !apiModels.includes(m)),
  ]

  const endpoint = config?.endpoint || 'http://localhost:11434'

  const effectiveEnabled = isRuleBased ? true : isEnabled
  const effectiveAvailable = isRuleBased ? true : isAvailable

  const handleToggle = () => {
    if (!onChange || isRuleBased || !isAvailable) return
    onChange(providerId, { enabled: !isEnabled })
  }

  const handleModelChange = (model: string) => {
    if (!onChange) return
    onChange(providerId, { model })
  }

  const handleEndpointChange = (newEndpoint: string) => {
    if (!onChange) return
    onChange(providerId, { endpoint: newEndpoint })
  }

  return (
    <div
      className={clsx(
        'relative rounded-2xl overflow-hidden',
        'transition-all duration-300',
        effectiveEnabled && effectiveAvailable && [
          `bg-gradient-to-r ${colors.gradient}`,
          `border ${colors.border}`,
          `shadow-lg ${colors.glow}`,
          'hover:shadow-xl',
        ],
        (!effectiveEnabled || !effectiveAvailable) && [
          'bg-slate-dark/50',
          'border border-slate-mid/30',
        ],
        !effectiveAvailable && !isRuleBased && 'opacity-75'
      )}
    >
      {/* Gradient overlay for enabled state */}
      {effectiveEnabled && effectiveAvailable && (
        <div className="absolute inset-0 bg-gradient-to-br from-white/5 via-transparent to-black/10 pointer-events-none" />
      )}

      <div className="relative p-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            {/* Toggle Checkbox */}
            {!isRuleBased ? (
              <ToggleCheckbox
                checked={effectiveEnabled && isAvailable}
                onChange={handleToggle}
                disabled={!isAvailable || !onChange}
              />
            ) : (
              <div className="w-5 h-5 rounded-full bg-slate-mid/50 border border-slate-mid flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-slate-light" />
              </div>
            )}

            {/* Icon & Name */}
            <div className="flex items-center gap-2.5">
              <span className="text-2xl">{info.icon}</span>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-text-primary">{info.name}</span>
                  <span
                    className={clsx(
                      'text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border',
                      info.type === 'local'
                        ? 'bg-neural/10 text-neural border-neural/30'
                        : 'bg-pulse/10 text-pulse border-pulse/30'
                    )}
                  >
                    {info.type === 'local' ? 'Local' : 'Cloud'}
                  </span>
                </div>
                <p className="text-sm text-text-muted mt-0.5">{info.description}</p>
              </div>
            </div>
          </div>

          <StatusBadge status={status} />
        </div>

        {/* Configuration (when available) */}
        {effectiveAvailable && !isRuleBased && (
          <div className="mt-4 pt-4 border-t border-slate-mid/30 space-y-3">
            {/* Model Selection - Editable with suggestions */}
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-text-muted min-w-[50px]">Model</span>
              <ModelSelector
                value={currentModel}
                options={availableModels}
                onChange={handleModelChange}
                disabled={!onChange}
                placeholder="Enter or select model..."
              />
              {/* Refresh Models Button */}
              {onRedetect && (
                <button
                  type="button"
                  onClick={handleRefreshModels}
                  disabled={isRefreshingModels || isLoading}
                  title="Refresh available models from service"
                  className={clsx(
                    'flex items-center justify-center w-9 h-9 rounded-lg',
                    'bg-slate-dark/80 border border-slate-mid/50',
                    'text-text-muted hover:text-synapse hover:border-synapse/40',
                    'hover:bg-synapse/10 active:scale-95',
                    'transition-all duration-200',
                    (isRefreshingModels || isLoading) && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  <RefreshCw
                    className={clsx(
                      'w-4 h-4',
                      (isRefreshingModels || isLoading) && 'animate-spin'
                    )}
                  />
                </button>
              )}
            </div>

            {/* Endpoint (Ollama only) */}
            {providerId === 'ollama' && (
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => setShowEndpoint(!showEndpoint)}
                  className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-secondary transition-colors"
                >
                  <ChevronDown
                    className={clsx('w-3 h-3 transition-transform duration-200', showEndpoint && 'rotate-180')}
                  />
                  <Zap className="w-3 h-3" />
                  Endpoint settings
                </button>

                {showEndpoint && (
                  <div className="flex items-center gap-3 animate-in fade-in slide-in-from-top-1 duration-200">
                    <span className="text-xs font-medium text-text-muted min-w-[50px]">URL</span>
                    <input
                      type="text"
                      value={endpoint}
                      onChange={(e) => handleEndpointChange(e.target.value)}
                      disabled={!onChange}
                      placeholder="http://localhost:11434"
                      className={clsx(
                        'flex-1 h-9 px-3 text-xs font-mono',
                        'bg-slate-dark/80 border border-slate-mid/50 rounded-lg',
                        'text-text-primary placeholder-text-muted',
                        'focus:outline-none focus:border-synapse/50 focus:ring-2 focus:ring-synapse/20',
                        'transition-all duration-200',
                        !onChange && 'opacity-50'
                      )}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Version & Models count */}
            <div className="flex items-center gap-4 text-xs text-text-muted">
              {status?.version && (
                <span>
                  Version: <span className="font-mono text-text-secondary">{status.version}</span>
                </span>
              )}
              {availableModels.length > 1 && (
                <span>{availableModels.length} models available</span>
              )}
            </div>
          </div>
        )}

        {/* Rule-based info */}
        {isRuleBased && (
          <div className="mt-4 pt-4 border-t border-slate-mid/30">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-success" />
              <span className="text-sm text-text-secondary">Always available as fallback</span>
            </div>
            <p className="mt-2 text-xs text-text-muted">
              Pattern matching extraction. No AI providers required.
            </p>
          </div>
        )}

        {/* Installation Guide (spec 3.4) */}
        {!effectiveAvailable && !isRuleBased && (
          <InstallationGuide providerId={providerId} onRedetect={onRedetect} />
        )}

        {/* Error display */}
        {status?.error && (
          <div className="mt-3 p-2.5 rounded-lg bg-error/10 border border-error/30">
            <span className="text-xs text-error">{status.error}</span>
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="mt-3 flex items-center gap-2">
            <RefreshCw className="w-3.5 h-3.5 text-synapse animate-spin" />
            <span className="text-xs text-text-muted">Detecting provider...</span>
          </div>
        )}
      </div>
    </div>
  )
}
