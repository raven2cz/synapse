/**
 * EditParametersModal
 *
 * Modal for editing generation parameters with comprehensive category support.
 *
 * FEATURES:
 * - Categorized parameters (Generation, Resolution, HiRes, Model, ControlNet, etc.)
 * - Per-category "+" dropdown to add known parameters
 * - Type-aware inputs (boolean switch, number with custom +/- buttons, text)
 * - Custom parameter with type selection
 * - Save/Cancel with loading state
 */

import { useState, useEffect, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { createPortal } from 'react-dom'
import {
  X, Loader2, ChevronDown, ChevronRight, Sliders, Maximize2, Sparkles,
  Settings2, Layers, Zap, Paintbrush, Grid3X3, Cpu, Box, Image, Plus, Minus, Check,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Portal Dropdown Menu - Renders outside modal DOM to avoid overflow clipping
// =============================================================================

interface PortalDropdownMenuProps {
  isOpen: boolean
  triggerRef: React.RefObject<HTMLElement | null>
  children: React.ReactNode
  className?: string
  /** Menu height for position calculation */
  menuHeight?: number
  /** Alignment: 'left' | 'right' */
  align?: 'left' | 'right'
}

function PortalDropdownMenu({
  isOpen,
  triggerRef,
  children,
  className,
  menuHeight = 240,
  align = 'left',
}: PortalDropdownMenuProps) {
  const [position, setPosition] = useState<{
    top?: number
    bottom?: number
    left?: number
    right?: number
  }>({})
  const [opensUp, setOpensUp] = useState(false)

  useEffect(() => {
    if (isOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      const spaceBelow = window.innerHeight - rect.bottom
      const spaceAbove = rect.top

      const shouldOpenUp = spaceBelow < menuHeight && spaceAbove > spaceBelow

      if (shouldOpenUp) {
        setOpensUp(true)
        setPosition({
          bottom: window.innerHeight - rect.top + 4,
          ...(align === 'right'
            ? { right: window.innerWidth - rect.right }
            : { left: rect.left }),
        })
      } else {
        setOpensUp(false)
        setPosition({
          top: rect.bottom + 4,
          ...(align === 'right'
            ? { right: window.innerWidth - rect.right }
            : { left: rect.left }),
        })
      }
    }
  }, [isOpen, triggerRef, menuHeight, align])

  if (!isOpen) return null

  return createPortal(
    <div
      style={{
        position: 'fixed',
        ...position,
        zIndex: 9999,
      }}
      className={clsx(
        "bg-slate-darker/95 backdrop-blur-xl",
        "border border-slate-mid/60 rounded-xl",
        "shadow-xl shadow-black/40",
        opensUp
          ? "animate-in fade-in slide-in-from-bottom-2 duration-150"
          : "animate-in fade-in slide-in-from-top-2 duration-150",
        className
      )}
    >
      {children}
    </div>,
    document.body
  )
}

// =============================================================================
// Types
// =============================================================================

export interface EditParametersModalProps {
  isOpen: boolean
  initialParameters: Record<string, string>
  onSave: (parameters: Record<string, unknown>) => void
  onClose: () => void
  isSaving?: boolean
}

type ParamType = 'string' | 'number' | 'boolean'
/**
 * Available parameter categories.
 *
 * HOW TO ADD A NEW CATEGORY:
 * 1. Add category key to this CategoryKey type
 * 2. Add entry in PARAM_CATEGORIES with list of parameter keys
 * 3. Add entry in CATEGORY_META with label, icon, and color
 * 4. Add entry in CATEGORY_OPTIONS (for dropdown selector)
 * 5. Add parameter definitions in PARAM_DEFINITIONS
 *
 * The system is fully dynamic - parameters are auto-categorized based on these definitions.
 */
type CategoryKey = 'generation' | 'resolution' | 'hires' | 'model' | 'controlnet' | 'inpainting' | 'batch' | 'advanced' | 'sdxl' | 'freeu' | 'ipadapter' | 'custom'

interface ParamDefinition {
  key: string
  labelKey: string
  type: ParamType
  default: string
  category: CategoryKey
  step?: number
  min?: number
  max?: number
}

// =============================================================================
// Parameter Definitions - Comprehensive List
// =============================================================================

const PARAM_DEFINITIONS: ParamDefinition[] = [
  // Generation
  { key: 'sampler', labelKey: 'sampler', type: 'string', default: 'euler', category: 'generation' },
  { key: 'scheduler', labelKey: 'scheduler', type: 'string', default: 'normal', category: 'generation' },
  { key: 'steps', labelKey: 'steps', type: 'number', default: '20', category: 'generation', step: 1, min: 1, max: 150 },
  { key: 'cfg_scale', labelKey: 'cfg_scale', type: 'number', default: '7', category: 'generation', step: 0.5, min: 1, max: 30 },
  { key: 'clip_skip', labelKey: 'clip_skip', type: 'number', default: '2', category: 'generation', step: 1, min: 1, max: 12 },
  { key: 'denoise', labelKey: 'denoise', type: 'number', default: '1.0', category: 'generation', step: 0.05, min: 0, max: 1 },
  { key: 'seed', labelKey: 'seed', type: 'number', default: '-1', category: 'generation', step: 1 },
  { key: 'eta', labelKey: 'eta', type: 'number', default: '0', category: 'generation', step: 0.1, min: 0, max: 1 },

  // Resolution
  { key: 'width', labelKey: 'width', type: 'number', default: '512', category: 'resolution', step: 64, min: 64, max: 4096 },
  { key: 'height', labelKey: 'height', type: 'number', default: '512', category: 'resolution', step: 64, min: 64, max: 4096 },
  { key: 'aspect_ratio', labelKey: 'aspect_ratio', type: 'string', default: '1:1', category: 'resolution' },

  // HiRes Fix
  { key: 'hires_fix', labelKey: 'hires_fix', type: 'boolean', default: 'false', category: 'hires' },
  { key: 'hires_upscaler', labelKey: 'hires_upscaler', type: 'string', default: 'Latent', category: 'hires' },
  { key: 'hires_steps', labelKey: 'hires_steps', type: 'number', default: '15', category: 'hires', step: 1, min: 1, max: 150 },
  { key: 'hires_denoise', labelKey: 'hires_denoise', type: 'number', default: '0.5', category: 'hires', step: 0.05, min: 0, max: 1 },
  { key: 'hires_scale', labelKey: 'hires_scale', type: 'number', default: '2.0', category: 'hires', step: 0.25, min: 1, max: 4 },
  { key: 'hires_width', labelKey: 'hires_width', type: 'number', default: '1024', category: 'hires', step: 64, min: 64, max: 4096 },
  { key: 'hires_height', labelKey: 'hires_height', type: 'number', default: '1024', category: 'hires', step: 64, min: 64, max: 4096 },

  // Model Settings
  { key: 'strength', labelKey: 'strength', type: 'number', default: '1.0', category: 'model', step: 0.05, min: -2, max: 2 },
  { key: 'vae', labelKey: 'vae', type: 'string', default: 'Automatic', category: 'model' },
  { key: 'base_model', labelKey: 'base_model', type: 'string', default: '', category: 'model' },
  { key: 'model_hash', labelKey: 'model_hash', type: 'string', default: '', category: 'model' },

  // ControlNet
  { key: 'controlnet_enabled', labelKey: 'controlnet_enabled', type: 'boolean', default: 'false', category: 'controlnet' },
  { key: 'controlnet_strength', labelKey: 'controlnet_strength', type: 'number', default: '1.0', category: 'controlnet', step: 0.05, min: 0, max: 2 },
  { key: 'controlnet_start', labelKey: 'controlnet_start', type: 'number', default: '0', category: 'controlnet', step: 0.05, min: 0, max: 1 },
  { key: 'controlnet_end', labelKey: 'controlnet_end', type: 'number', default: '1', category: 'controlnet', step: 0.05, min: 0, max: 1 },
  { key: 'controlnet_model', labelKey: 'controlnet_model', type: 'string', default: '', category: 'controlnet' },
  { key: 'control_mode', labelKey: 'control_mode', type: 'string', default: 'balanced', category: 'controlnet' },

  // Inpainting
  { key: 'inpaint_full_res', labelKey: 'inpaint_full_res', type: 'boolean', default: 'true', category: 'inpainting' },
  { key: 'inpaint_full_res_padding', labelKey: 'inpaint_full_res_padding', type: 'number', default: '32', category: 'inpainting', step: 8, min: 0, max: 256 },
  { key: 'mask_blur', labelKey: 'mask_blur', type: 'number', default: '4', category: 'inpainting', step: 1, min: 0, max: 64 },
  { key: 'inpainting_fill', labelKey: 'inpainting_fill', type: 'string', default: 'original', category: 'inpainting' },

  // Batch
  { key: 'batch_size', labelKey: 'batch_size', type: 'number', default: '1', category: 'batch', step: 1, min: 1, max: 16 },
  { key: 'batch_count', labelKey: 'batch_count', type: 'number', default: '1', category: 'batch', step: 1, min: 1, max: 100 },
  { key: 'n_iter', labelKey: 'n_iter', type: 'number', default: '1', category: 'batch', step: 1, min: 1, max: 100 },

  // Advanced
  { key: 's_noise', labelKey: 's_noise', type: 'number', default: '1.0', category: 'advanced', step: 0.01, min: 0, max: 2 },
  { key: 's_churn', labelKey: 's_churn', type: 'number', default: '0', category: 'advanced', step: 0.1, min: 0, max: 100 },
  { key: 's_tmin', labelKey: 's_tmin', type: 'number', default: '0', category: 'advanced', step: 0.1, min: 0, max: 10 },
  { key: 's_tmax', labelKey: 's_tmax', type: 'number', default: 'inf', category: 'advanced', step: 0.1 },
  { key: 'noise_offset', labelKey: 'noise_offset', type: 'number', default: '0', category: 'advanced', step: 0.01, min: 0, max: 1 },
  { key: 'tiling', labelKey: 'tiling', type: 'boolean', default: 'false', category: 'advanced' },
  { key: 'ensd', labelKey: 'ensd', type: 'number', default: '31337', category: 'advanced', step: 1 },

  // SDXL
  { key: 'refiner_checkpoint', labelKey: 'refiner_checkpoint', type: 'string', default: '', category: 'sdxl' },
  { key: 'refiner_switch', labelKey: 'refiner_switch', type: 'number', default: '0.8', category: 'sdxl', step: 0.05, min: 0, max: 1 },
  { key: 'aesthetic_score', labelKey: 'aesthetic_score', type: 'number', default: '6.0', category: 'sdxl', step: 0.5, min: 1, max: 10 },
  { key: 'negative_aesthetic_score', labelKey: 'negative_aesthetic_score', type: 'number', default: '2.5', category: 'sdxl', step: 0.5, min: 1, max: 10 },

  // FreeU
  { key: 'freeu_enabled', labelKey: 'freeu_enabled', type: 'boolean', default: 'false', category: 'freeu' },
  { key: 'freeu_b1', labelKey: 'freeu_b1', type: 'number', default: '1.3', category: 'freeu', step: 0.05, min: 0, max: 2 },
  { key: 'freeu_b2', labelKey: 'freeu_b2', type: 'number', default: '1.4', category: 'freeu', step: 0.05, min: 0, max: 2 },
  { key: 'freeu_s1', labelKey: 'freeu_s1', type: 'number', default: '0.9', category: 'freeu', step: 0.05, min: 0, max: 2 },
  { key: 'freeu_s2', labelKey: 'freeu_s2', type: 'number', default: '0.2', category: 'freeu', step: 0.05, min: 0, max: 2 },

  // IP-Adapter
  { key: 'ip_adapter_enabled', labelKey: 'ip_adapter_enabled', type: 'boolean', default: 'false', category: 'ipadapter' },
  { key: 'ip_adapter_weight', labelKey: 'ip_adapter_weight', type: 'number', default: '1.0', category: 'ipadapter', step: 0.05, min: 0, max: 2 },
  { key: 'ip_adapter_noise', labelKey: 'ip_adapter_noise', type: 'number', default: '0', category: 'ipadapter', step: 0.05, min: 0, max: 1 },
  { key: 'ip_adapter_model', labelKey: 'ip_adapter_model', type: 'string', default: '', category: 'ipadapter' },
]

// Category metadata
const CATEGORY_META: Record<CategoryKey, { labelKey: string; icon: React.ElementType; color: string }> = {
  generation: { labelKey: 'generation', icon: Sliders, color: 'text-synapse' },
  resolution: { labelKey: 'resolution', icon: Maximize2, color: 'text-blue-400' },
  hires: { labelKey: 'hires', icon: Sparkles, color: 'text-amber-400' },
  model: { labelKey: 'modelSettings', icon: Layers, color: 'text-green-400' },
  controlnet: { labelKey: 'controlnet', icon: Zap, color: 'text-cyan-400' },
  inpainting: { labelKey: 'inpainting', icon: Paintbrush, color: 'text-pink-400' },
  batch: { labelKey: 'batch', icon: Grid3X3, color: 'text-orange-400' },
  advanced: { labelKey: 'advanced', icon: Cpu, color: 'text-red-400' },
  sdxl: { labelKey: 'sdxl', icon: Box, color: 'text-violet-400' },
  freeu: { labelKey: 'freeu', icon: Image, color: 'text-teal-400' },
  ipadapter: { labelKey: 'ipadapter', icon: Image, color: 'text-indigo-400' },
  custom: { labelKey: 'custom', icon: Settings2, color: 'text-purple-400' },
}

// Build lookup maps
const PARAM_BY_KEY = new Map(PARAM_DEFINITIONS.map(p => [p.key, p]))
const PARAMS_BY_CATEGORY = PARAM_DEFINITIONS.reduce((acc, p) => {
  if (!acc[p.category]) acc[p.category] = []
  acc[p.category].push(p)
  return acc
}, {} as Record<CategoryKey, ParamDefinition[]>)

// =============================================================================
// Utility Functions
// =============================================================================

function toSnakeCase(str: string): string {
  return str.replace(/([A-Z])/g, '_$1').toLowerCase()
}

function normalizeKey(key: string): string {
  if (/[A-Z]/.test(key)) {
    return toSnakeCase(key)
  }
  return key
}

function getParamDef(key: string): ParamDefinition | undefined {
  return PARAM_BY_KEY.get(normalizeKey(key))
}

function getParamCategory(key: string): CategoryKey {
  const def = getParamDef(key)
  return def?.category ?? 'custom'
}

function getParamType(key: string): ParamType {
  const def = getParamDef(key)
  return def?.type ?? 'string'
}

function getParamLabel(key: string, t: (key: string, opts?: Record<string, unknown>) => string): string {
  const def = getParamDef(key)
  if (!def) {
    return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  }
  return t('pack.parameters.editLabels.' + def.labelKey, {
    defaultValue: t('pack.parameters.labels.' + def.labelKey, {
      defaultValue: def.labelKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    }),
  })
}

// =============================================================================
// Sub-components
// =============================================================================

interface BooleanSwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}

function BooleanSwitch({ checked, onChange, disabled }: BooleanSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full",
        "border-2 border-transparent transition-colors duration-200 ease-in-out",
        "focus:outline-none focus:ring-2 focus:ring-synapse focus:ring-offset-2 focus:ring-offset-slate-dark",
        checked ? "bg-synapse" : "bg-slate-mid",
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <span
        className={clsx(
          "pointer-events-none inline-block h-5 w-5 transform rounded-full",
          "bg-white shadow ring-0 transition duration-200 ease-in-out",
          checked ? "translate-x-5" : "translate-x-0"
        )}
      />
    </button>
  )
}

interface NumberInputProps {
  value: string
  onChange: (value: string) => void
  step?: number
  min?: number
  max?: number
}

function NumberInput({ value, onChange, step = 1, min, max }: NumberInputProps) {
  const handleIncrement = () => {
    const num = parseFloat(value) || 0
    let newVal = num + step
    if (max !== undefined && newVal > max) newVal = max
    onChange(formatNumber(newVal, step))
  }

  const handleDecrement = () => {
    const num = parseFloat(value) || 0
    let newVal = num - step
    if (min !== undefined && newVal < min) newVal = min
    onChange(formatNumber(newVal, step))
  }

  // Format number with appropriate decimal places based on step
  function formatNumber(num: number, stp: number): string {
    if (stp >= 1) return Math.round(num).toString()
    const decimals = Math.max(0, Math.ceil(-Math.log10(stp)))
    return num.toFixed(decimals)
  }

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={handleDecrement}
        className={clsx(
          "w-8 h-8 flex items-center justify-center rounded-lg",
          "bg-obsidian border border-slate-mid",
          "hover:bg-slate-mid hover:border-synapse/50",
          "transition-all duration-150",
          "text-text-muted hover:text-synapse"
        )}
      >
        <Minus className="w-3.5 h-3.5" />
      </button>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={clsx(
          "w-24 px-3 py-2 rounded-lg text-center",
          "bg-obsidian border border-slate-mid",
          "text-text-primary text-sm font-medium",
          "focus:outline-none focus:border-synapse",
          "transition-colors duration-200"
        )}
      />
      <button
        type="button"
        onClick={handleIncrement}
        className={clsx(
          "w-8 h-8 flex items-center justify-center rounded-lg",
          "bg-obsidian border border-slate-mid",
          "hover:bg-slate-mid hover:border-synapse/50",
          "transition-all duration-150",
          "text-text-muted hover:text-synapse"
        )}
      >
        <Plus className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

interface ParameterRowProps {
  paramKey: string
  value: string
  onChange: (value: string) => void
  onRemove: () => void
  customType?: ParamType
}

function ParameterRow({ paramKey, value, onChange, onRemove, customType }: ParameterRowProps) {
  const { t } = useTranslation()
  const label = getParamLabel(paramKey, t)
  const def = getParamDef(paramKey)
  const type = customType ?? def?.type ?? 'string'

  return (
    <div
      className={clsx(
        "flex items-center gap-3",
        "bg-obsidian/50 p-3 rounded-xl",
        "transition-all duration-200",
        "hover:bg-obsidian/70"
      )}
    >
      <span className="text-sm text-synapse font-medium min-w-[130px]">
        {label}
      </span>

      <div className="flex-1 flex items-center">
        {type === 'boolean' ? (
          <div className="flex items-center gap-3">
            <BooleanSwitch
              checked={value === 'true'}
              onChange={(checked) => onChange(checked ? 'true' : 'false')}
            />
            <span className="text-sm text-text-muted">
              {value === 'true' ? t('pack.modals.parameters.enabled') : t('pack.modals.parameters.disabled')}
            </span>
          </div>
        ) : type === 'number' ? (
          <NumberInput
            value={value}
            onChange={onChange}
            step={def?.step}
            min={def?.min}
            max={def?.max}
          />
        ) : (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className={clsx(
              "flex-1 px-3 py-2 rounded-lg",
              "bg-obsidian border border-slate-mid",
              "text-text-primary text-sm",
              "focus:outline-none focus:border-synapse",
              "transition-colors duration-200"
            )}
          />
        )}
      </div>

      <button
        onClick={onRemove}
        className={clsx(
          "p-1.5 rounded-lg",
          "hover:bg-red-500/20 transition-colors duration-200"
        )}
        title={t('pack.modals.parameters.removeParam')}
      >
        <X className="w-4 h-4 text-red-400" />
      </button>
    </div>
  )
}

interface AddParamDropdownProps {
  category: CategoryKey
  existingKeys: Set<string>
  onAdd: (key: string, defaultValue: string) => void
}

function AddParamDropdown({ category, existingKeys, onAdd }: AddParamDropdownProps) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const availableParams = PARAMS_BY_CATEGORY[category]?.filter(p => !existingKeys.has(p.key)) ?? []

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node) &&
          buttonRef.current && !buttonRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false)
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  if (availableParams.length === 0) return null

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          "px-2.5 py-1.5 rounded-lg text-xs font-medium",
          "bg-synapse/20 hover:bg-synapse/30 text-synapse",
          "border border-synapse/30 hover:border-synapse/50",
          "transition-all duration-200 flex items-center gap-1.5"
        )}
      >
        <Plus className="w-3 h-3" />
        Add
      </button>

      <PortalDropdownMenu
        isOpen={isOpen}
        triggerRef={buttonRef}
        menuHeight={240}
        align="right"
        className="py-1.5 min-w-[220px] max-h-[240px] overflow-y-auto"
      >
        <div ref={menuRef}>
          {availableParams.map(p => (
            <button
              key={p.key}
              onClick={() => {
                onAdd(p.key, p.default)
                setIsOpen(false)
              }}
              className={clsx(
                "w-full px-4 py-2.5 text-left text-sm",
                "text-text-secondary hover:bg-slate-mid/40 hover:text-text-primary",
                "transition-colors duration-150",
                "flex items-center justify-between gap-3"
              )}
            >
              <span>{getParamLabel(p.key, t)}</span>
              <span className="text-xs text-text-muted/70 px-1.5 py-0.5 bg-slate-mid/30 rounded">
                {p.type}
              </span>
            </button>
          ))}
        </div>
      </PortalDropdownMenu>
    </div>
  )
}

// =============================================================================
// Type Selector Dropdown (styled, not native select)
// =============================================================================

interface TypeSelectorProps {
  value: ParamType
  onChange: (value: ParamType) => void
  /** Force dropdown to open upward (useful when at bottom of modal) */
  forceUp?: boolean
}

const TYPE_OPTIONS: Array<{ value: ParamType; label: string }> = [
  { value: 'string', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'boolean', label: 'Boolean' },
]

function TypeSelector({ value, onChange, forceUp: _forceUp = false }: TypeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node) &&
          buttonRef.current && !buttonRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false)
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  const selectedOption = TYPE_OPTIONS.find(opt => opt.value === value)

  return (
    <div className="relative min-w-[90px]">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          "w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg",
          "bg-obsidian border border-slate-mid",
          "text-text-primary text-sm",
          "hover:border-slate-light",
          "focus:outline-none focus:border-synapse",
          "transition-colors duration-200",
          isOpen && "border-synapse"
        )}
      >
        <span>{selectedOption?.label}</span>
        <ChevronDown className={clsx(
          "w-4 h-4 text-text-muted transition-transform duration-200",
          isOpen && "rotate-180"
        )} />
      </button>

      <PortalDropdownMenu
        isOpen={isOpen}
        triggerRef={buttonRef}
        menuHeight={150}
        align="left"
        className="py-1.5 min-w-[90px] overflow-hidden"
      >
        <div ref={menuRef}>
          {TYPE_OPTIONS.map(option => (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                onChange(option.value)
                setIsOpen(false)
              }}
              className={clsx(
                "w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left",
                "transition-colors duration-150",
                option.value === value
                  ? "bg-synapse/20 text-synapse"
                  : "text-text-secondary hover:bg-slate-mid/40 hover:text-text-primary"
              )}
            >
              <span className="flex-1">{option.label}</span>
              {option.value === value && (
                <Check className="w-4 h-4 flex-shrink-0" />
              )}
            </button>
          ))}
        </div>
      </PortalDropdownMenu>
    </div>
  )
}

// =============================================================================
// Category Selector Dropdown (for custom params)
// =============================================================================

interface CategorySelectorProps {
  value: CategoryKey
  onChange: (value: CategoryKey) => void
  /** Force dropdown to open upward (useful when at bottom of modal) */
  forceUp?: boolean
}

/**
 * Available parameter categories.
 * To add a new category:
 * 1. Add it to CategoryKey type above
 * 2. Add entry here with value, label, and color
 * 3. Add corresponding entry in CATEGORY_META
 * 4. Add parameter definitions in PARAM_DEFINITIONS
 */
const CATEGORY_OPTIONS: Array<{ value: CategoryKey; label: string; color: string }> = [
  { value: 'generation', label: 'Generation', color: 'text-synapse' },
  { value: 'resolution', label: 'Resolution', color: 'text-blue-400' },
  { value: 'hires', label: 'HiRes Fix', color: 'text-amber-400' },
  { value: 'model', label: 'Model', color: 'text-green-400' },
  { value: 'controlnet', label: 'ControlNet', color: 'text-cyan-400' },
  { value: 'inpainting', label: 'Inpainting', color: 'text-pink-400' },
  { value: 'batch', label: 'Batch', color: 'text-orange-400' },
  { value: 'advanced', label: 'Advanced', color: 'text-red-400' },
  { value: 'sdxl', label: 'SDXL', color: 'text-violet-400' },
  { value: 'freeu', label: 'FreeU', color: 'text-teal-400' },
  { value: 'ipadapter', label: 'IP-Adapter', color: 'text-indigo-400' },
  { value: 'custom', label: 'Custom', color: 'text-purple-400' },
]

function CategorySelector({ value, onChange, forceUp: _forceUp = false }: CategorySelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node) &&
          buttonRef.current && !buttonRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false)
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  const selectedOption = CATEGORY_OPTIONS.find(opt => opt.value === value)

  return (
    <div className="relative min-w-[110px]">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          "w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg",
          "bg-obsidian border border-slate-mid",
          "text-text-primary text-sm",
          "hover:border-slate-light",
          "focus:outline-none focus:border-synapse",
          "transition-colors duration-200",
          isOpen && "border-synapse"
        )}
      >
        <span className={selectedOption?.color}>{selectedOption?.label}</span>
        <ChevronDown className={clsx(
          "w-4 h-4 text-text-muted transition-transform duration-200",
          isOpen && "rotate-180"
        )} />
      </button>

      <PortalDropdownMenu
        isOpen={isOpen}
        triggerRef={buttonRef}
        menuHeight={280}
        align="left"
        className="py-1.5 min-w-[150px] max-h-[280px] overflow-y-auto"
      >
        <div ref={menuRef}>
          {CATEGORY_OPTIONS.map(option => (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                onChange(option.value)
                setIsOpen(false)
              }}
              className={clsx(
                "w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left",
                "transition-colors duration-150",
                option.value === value
                  ? "bg-synapse/20"
                  : "hover:bg-slate-mid/40"
              )}
            >
              <span className={clsx("flex-1", option.color)}>{option.label}</span>
              {option.value === value && (
                <Check className="w-4 h-4 flex-shrink-0 text-synapse" />
              )}
            </button>
          ))}
        </div>
      </PortalDropdownMenu>
    </div>
  )
}

// =============================================================================
// Add Section Dropdown
// =============================================================================

interface AddSectionDropdownProps {
  visibleSections: Set<CategoryKey>
  onAdd: (category: CategoryKey) => void
}

function AddSectionDropdown({ visibleSections, onAdd }: AddSectionDropdownProps) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // Available sections = all sections not currently visible
  const availableSections = CATEGORY_OPTIONS.filter(opt => !visibleSections.has(opt.value))

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node) &&
          buttonRef.current && !buttonRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false)
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  if (availableSections.length === 0) return null

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          "flex items-center gap-2 px-4 py-2.5 rounded-xl",
          "bg-slate-mid/30 hover:bg-slate-mid/50",
          "border border-dashed border-slate-mid hover:border-synapse/50",
          "text-text-muted hover:text-synapse",
          "transition-all duration-200"
        )}
      >
        <Plus className="w-4 h-4" />
        <span className="text-sm font-medium">{t('pack.modals.parameters.addSection')}</span>
      </button>

      <PortalDropdownMenu
        isOpen={isOpen}
        triggerRef={buttonRef}
        menuHeight={320}
        align="left"
        className="py-1.5 min-w-[200px] max-h-[320px] overflow-y-auto"
      >
        <div ref={menuRef}>
          {availableSections.map(option => {
            const meta = CATEGORY_META[option.value]
            const Icon = meta.icon
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onAdd(option.value)
                  setIsOpen(false)
                }}
                className={clsx(
                  "w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left",
                  "transition-colors duration-150",
                  "hover:bg-slate-mid/40"
                )}
              >
                <Icon className={clsx("w-4 h-4", option.color)} />
                <span className={clsx("flex-1", option.color)}>{option.label}</span>
              </button>
            )
          })}
        </div>
      </PortalDropdownMenu>
    </div>
  )
}

interface CategorySectionProps {
  category: CategoryKey
  parameters: [string, string][]
  customTypes?: Map<string, ParamType>
  onUpdate: (key: string, value: string) => void
  onRemove: (key: string) => void
  onAdd: (key: string, defaultValue: string) => void
  existingKeys: Set<string>
  collapsible?: boolean
  defaultExpanded?: boolean
}

function CategorySection({
  category,
  parameters,
  customTypes,
  onUpdate,
  onRemove,
  onAdd,
  existingKeys,
  collapsible = false,
  defaultExpanded = true,
}: CategorySectionProps) {
  const { t } = useTranslation()
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const meta = CATEGORY_META[category]
  const Icon = meta.icon

  // Section is shown when it has parameters or was explicitly added
  return (
    <div className="mb-4">
      {collapsible ? (
        <div className="flex items-center gap-2 w-full mb-2 p-2 rounded-lg hover:bg-slate-mid/50 transition-colors duration-200">
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-2 flex-1 text-left"
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-text-muted" />
            ) : (
              <ChevronRight className="w-4 h-4 text-text-muted" />
            )}
            <Icon className={clsx("w-4 h-4", meta.color)} />
            <span className="text-sm font-semibold text-text-primary">{t('pack.parameters.categories.' + meta.labelKey)}</span>
            <span className="text-xs text-text-muted ml-1">({parameters.length})</span>
          </button>
          <div className="ml-auto">
            <AddParamDropdown category={category} existingKeys={existingKeys} onAdd={onAdd} />
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-2 mb-2 px-2">
          <Icon className={clsx("w-4 h-4", meta.color)} />
          <span className="text-sm font-semibold text-text-primary">{t('pack.parameters.categories.' + meta.labelKey)}</span>
          <div className="ml-auto">
            <AddParamDropdown category={category} existingKeys={existingKeys} onAdd={onAdd} />
          </div>
        </div>
      )}

      {(!collapsible || isExpanded) && (
        <div className="space-y-2">
          {parameters.length === 0 ? (
            <p className="text-xs text-text-muted px-2 py-3">{t('pack.modals.parameters.noParamsInCategory')}</p>
          ) : (
            parameters.map(([key, value]) => (
              <ParameterRow
                key={key}
                paramKey={key}
                value={value}
                onChange={(val) => onUpdate(key, val)}
                onRemove={() => onRemove(key)}
                customType={customTypes?.get(key)}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function EditParametersModal({
  isOpen,
  initialParameters,
  onSave,
  onClose,
  isSaving = false,
}: EditParametersModalProps) {
  const { t } = useTranslation()
  const [parameters, setParameters] = useState<Record<string, string>>(initialParameters)
  const [customTypes, setCustomTypes] = useState<Map<string, ParamType>>(new Map())
  const [customCategories, setCustomCategories] = useState<Map<string, CategoryKey>>(new Map())
  const [activeSections, setActiveSections] = useState<Set<CategoryKey>>(new Set())
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')
  const [newType, setNewType] = useState<ParamType>('string')
  const [newCategory, setNewCategory] = useState<CategoryKey>('custom')

  // Reset when modal opens
  // IMPORTANT: Filter out AI-extracted fields - they are read-only in AI Insights section
  useEffect(() => {
    if (isOpen) {
      const stringified: Record<string, string> = {}
      // Get list of AI-extracted field names (not user-added custom fields)
      const aiFields = (initialParameters._ai_fields as unknown as string[] | undefined) ?? []

      for (const [key, value] of Object.entries(initialParameters)) {
        // Skip internal fields (start with _)
        if (key.startsWith('_')) continue

        // Skip AI-extracted unknown fields - they belong to AI Insights, not editable params
        // BUT keep user-added custom fields (they're NOT in _ai_fields array)
        const isAiField = aiFields.includes(key)
        const isKnownParam = Boolean(getParamDef(key))
        if (isAiField && !isKnownParam) continue

        stringified[key] = String(value ?? '')
      }
      setParameters(stringified)
      setCustomTypes(new Map())
      setCustomCategories(new Map())
      setActiveSections(new Set())
      setNewKey('')
      setNewValue('')
      setNewType('string')
      setNewCategory('custom')
    }
  }, [isOpen, initialParameters])

  // Categorize parameters
  const categorizedParams = useMemo(() => {
    const entries = Object.entries(parameters)
    const result: Record<CategoryKey, [string, string][]> = {
      generation: [],
      resolution: [],
      hires: [],
      model: [],
      controlnet: [],
      inpainting: [],
      batch: [],
      advanced: [],
      sdxl: [],
      freeu: [],
      ipadapter: [],
      custom: [],
    }

    for (const [key, value] of entries) {
      // Check if this key has a custom category assignment
      const customCategory = customCategories.get(key)
      const category = customCategory ?? getParamCategory(key)
      result[category].push([key, value])
    }

    return result
  }, [parameters, customCategories])

  const existingKeys = useMemo(() => new Set(Object.keys(parameters)), [parameters])

  const handleAddParam = (key: string, defaultValue: string) => {
    setParameters(prev => ({ ...prev, [key]: defaultValue }))
  }

  const handleUpdateParam = (key: string, value: string) => {
    setParameters(prev => ({ ...prev, [key]: value }))
  }

  const handleRemoveParam = (key: string) => {
    const newParams = { ...parameters }
    delete newParams[key]
    setParameters(newParams)

    // Also remove custom type and category if exists
    const newTypes = new Map(customTypes)
    newTypes.delete(key)
    setCustomTypes(newTypes)

    const newCats = new Map(customCategories)
    newCats.delete(key)
    setCustomCategories(newCats)
  }

  const handleAddCustomParam = () => {
    if (newKey.trim()) {
      const normalizedKey = normalizeKey(newKey.trim())
      setParameters(prev => ({ ...prev, [normalizedKey]: newValue }))

      // Store custom type if not string (default)
      if (newType !== 'string') {
        setCustomTypes(prev => new Map(prev).set(normalizedKey, newType))
      }

      // Store custom category if not 'custom' (the default)
      if (newCategory !== 'custom') {
        setCustomCategories(prev => new Map(prev).set(normalizedKey, newCategory))
      }

      // Make sure the target section is visible
      setActiveSections(prev => new Set(prev).add(newCategory))

      setNewKey('')
      setNewValue('')
      setNewType('string')
      setNewCategory('custom')
    }
  }

  const handleAddSection = (category: CategoryKey) => {
    setActiveSections(prev => new Set(prev).add(category))
  }

  const handleSave = () => {
    const converted: Record<string, unknown> = {}

    for (const [key, value] of Object.entries(parameters)) {
      if (value === '') continue

      const normalizedKey = normalizeKey(key)
      const paramType = customTypes.get(normalizedKey) ?? getParamType(normalizedKey)

      let convertedValue: unknown
      if (paramType === 'boolean') {
        convertedValue = value === 'true'
      } else if (paramType === 'number') {
        const numValue = parseFloat(value)
        if (!isNaN(numValue)) {
          convertedValue = numValue
        } else {
          convertedValue = value
        }
      } else {
        convertedValue = value
      }

      converted[normalizedKey] = convertedValue
    }

    onSave(converted)
  }

  if (!isOpen) return null

  const hasAnyParams = Object.keys(parameters).length > 0

  // Categories to show (ordered)
  const categoryOrder: CategoryKey[] = [
    'generation', 'resolution', 'hires', 'model', 'controlnet',
    'inpainting', 'batch', 'advanced', 'sdxl', 'freeu', 'ipadapter', 'custom'
  ]

  // Visible sections: sections with parameters OR explicitly added sections
  const visibleSections = new Set<CategoryKey>()
  for (const category of categoryOrder) {
    if (categorizedParams[category].length > 0 || activeSections.has(category)) {
      visibleSections.add(category)
    }
  }

  return (
    <div
      className={clsx(
        "fixed inset-0 bg-black/80 backdrop-blur-sm z-[80]",
        "flex items-center justify-center p-4",
        ANIMATION_PRESETS.fadeIn
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={clsx(
          "bg-slate-dark rounded-2xl p-6 max-w-4xl w-full",
          "border border-slate-mid",
          "max-h-[90vh] flex flex-col",
          "shadow-2xl",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Sliders className="w-5 h-5 text-synapse" />
            {t('pack.modals.parameters.title')}
          </h2>
          <button
            onClick={onClose}
            className={clsx(
              "p-2 rounded-lg",
              "hover:bg-slate-mid transition-colors duration-200"
            )}
          >
            <X className="w-5 h-5 text-text-muted" />
          </button>
        </div>

        {/* Parameters List - Categorized */}
        <div className="flex-1 overflow-y-auto mb-4 min-h-[200px]">
          {!hasAnyParams && visibleSections.size === 0 ? (
            <div className="text-center py-8">
              <Sliders className="w-10 h-10 mx-auto mb-3 text-text-muted/50" />
              <p className="text-sm text-text-muted mb-2">{t('pack.modals.parameters.noParams')}</p>
              <p className="text-xs text-text-muted">
                {t('pack.modals.parameters.noParamsHint')}
              </p>
            </div>
          ) : null}

          {categoryOrder.map(category => {
            // Only show sections that are visible (have params or explicitly added)
            if (!visibleSections.has(category)) return null

            const params = categorizedParams[category]
            return (
              <CategorySection
                key={category}
                category={category}
                parameters={params}
                customTypes={customTypes}
                onUpdate={handleUpdateParam}
                onRemove={handleRemoveParam}
                onAdd={handleAddParam}
                existingKeys={existingKeys}
                collapsible={!['generation', 'resolution'].includes(category)}
                defaultExpanded={params.length > 0 || activeSections.has(category)}
              />
            )
          })}

          {/* Add Section Button */}
          <div className="mt-4 pt-4 border-t border-slate-mid/50">
            <AddSectionDropdown
              visibleSections={visibleSections}
              onAdd={handleAddSection}
            />
          </div>
        </div>

        {/* Add Custom Parameter */}
        <div className="border-t border-slate-mid pt-4 mb-4">
          <p className="text-xs text-text-muted mb-3 flex items-center gap-2">
            <Settings2 className="w-3.5 h-3.5 text-purple-400" />
            {t('pack.modals.parameters.addCustomHint')}
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder={t('pack.modals.parameters.paramName')}
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              className={clsx(
                "flex-1 px-3 py-2.5 rounded-lg",
                "bg-obsidian border border-slate-mid",
                "text-text-primary text-sm",
                "focus:outline-none focus:border-synapse",
                "transition-colors duration-200"
              )}
            />
            <input
              type="text"
              placeholder={t('pack.modals.parameters.value')}
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newKey.trim()) {
                  handleAddCustomParam()
                }
              }}
              className={clsx(
                "flex-1 px-3 py-2.5 rounded-lg",
                "bg-obsidian border border-slate-mid",
                "text-text-primary text-sm",
                "focus:outline-none focus:border-synapse",
                "transition-colors duration-200"
              )}
            />
            <TypeSelector
              value={newType}
              onChange={setNewType}
              forceUp
            />
            <CategorySelector
              value={newCategory}
              onChange={setNewCategory}
              forceUp
            />
            <button
              onClick={handleAddCustomParam}
              disabled={!newKey.trim()}
              className={clsx(
                "px-6 py-2.5 rounded-lg font-semibold whitespace-nowrap",
                "bg-synapse hover:bg-synapse/80 text-obsidian",
                "disabled:bg-slate-mid disabled:text-text-muted",
                "transition-colors duration-200"
              )}
            >
              {t('pack.modals.parameters.addCustom')}
            </button>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <Button
            variant="secondary"
            className="flex-1"
            onClick={onClose}
          >
            {t('common.cancel')}
          </Button>
          <Button
            className="flex-1"
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              t('common.save')
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default EditParametersModal
