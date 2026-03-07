import { useState, useEffect, useRef, useCallback } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { clsx } from 'clsx'

export interface ThemedSelectProps<T extends string | number> {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
  className?: string
  align?: 'left' | 'right'
}

export function ThemedSelect<T extends string | number>({
  value,
  options,
  onChange,
  className,
  align = 'left',
}: ThemedSelectProps<T>) {
  const [isOpen, setIsOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (ref.current && !ref.current.contains(e.target as Node)) {
      setIsOpen(false)
    }
  }, [])

  useEffect(() => {
    if (!isOpen) return
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen, handleClickOutside])

  useEffect(() => {
    if (!isOpen) return
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false)
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen])

  const selectedLabel = options.find((o) => o.value === value)?.label ?? String(value)

  return (
    <div className={clsx('relative', className)} ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs',
          'bg-slate-dark/80 backdrop-blur border border-slate-mid/50',
          'text-text-primary hover:bg-slate-mid/50 transition-colors duration-150',
          'cursor-pointer select-none'
        )}
      >
        <span className="truncate max-w-[120px]">{selectedLabel}</span>
        <ChevronDown className={clsx('w-3.5 h-3.5 opacity-60 transition-transform duration-150', isOpen && 'rotate-180')} />
      </button>
      {isOpen && (
        <div
          className={clsx(
            'absolute top-full mt-1.5 min-w-[160px] p-1',
            'bg-slate-darker/95 backdrop-blur-xl',
            'border border-slate-mid/30 rounded-xl',
            'shadow-xl shadow-black/30',
            'z-[9999] overflow-y-auto max-h-[240px]',
            align === 'right' && 'right-0'
          )}
        >
          {options.map((opt) => (
            <button
              key={String(opt.value)}
              onClick={() => {
                onChange(opt.value)
                setIsOpen(false)
              }}
              className={clsx(
                'w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-left',
                'transition-colors duration-150',
                opt.value === value
                  ? 'bg-synapse/20 text-synapse'
                  : 'text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary'
              )}
            >
              <span className="flex-1">{opt.label}</span>
              {opt.value === value && <Check className="w-3.5 h-3.5 flex-shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
