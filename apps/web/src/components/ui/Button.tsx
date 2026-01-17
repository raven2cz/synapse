import { clsx } from 'clsx'
import { Loader2 } from 'lucide-react'
import { ButtonHTMLAttributes, ReactNode } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  isLoading,
  leftIcon,
  rightIcon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        // Base
        'inline-flex items-center justify-center gap-2 font-medium',
        'rounded-xl transition-all duration-200',
        'focus:outline-none focus:ring-2 focus:ring-synapse/50',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        
        // Variants
        variant === 'primary' && [
          'bg-gradient-to-r from-synapse to-pulse',
          'text-white shadow-lg shadow-synapse/25',
          'hover:shadow-xl hover:shadow-synapse/30',
          'hover:scale-[1.02] active:scale-[0.98]',
        ],
        variant === 'secondary' && [
          'bg-slate-deep border border-slate-mid/50',
          'text-text-primary',
          'hover:bg-slate-mid/50 hover:border-synapse/30',
        ],
        variant === 'ghost' && [
          'text-text-secondary',
          'hover:bg-slate-mid/30 hover:text-text-primary',
        ],
        variant === 'danger' && [
          'bg-error/10 border border-error/30',
          'text-error',
          'hover:bg-error/20',
        ],
        
        // Sizes
        size === 'sm' && 'px-3 py-1.5 text-sm',
        size === 'md' && 'px-4 py-2.5 text-sm',
        size === 'lg' && 'px-6 py-3 text-base',
        
        className
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : leftIcon}
      {children}
      {!isLoading && rightIcon}
    </button>
  )
}
