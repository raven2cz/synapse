import { clsx } from 'clsx'

interface ProgressBarProps {
  progress: number
  showLabel?: boolean
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'success' | 'warning' | 'error'
  label?: string
}

export function ProgressBar({
  progress,
  showLabel = true,
  size = 'md',
  variant = 'default',
  label = 'Progress',
}: ProgressBarProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress))
  
  return (
    <div className="w-full">
      {showLabel && (
        <div className="flex justify-between mb-1">
          <span className="text-sm text-text-secondary">{label}</span>
          <span className={clsx(
            'text-sm font-medium',
            variant === 'default' && 'text-synapse',
            variant === 'success' && 'text-success',
            variant === 'warning' && 'text-warning',
            variant === 'error' && 'text-error',
          )}>
            {Math.round(clampedProgress)}%
          </span>
        </div>
      )}
      <div
        className={clsx(
          'bg-slate-deep rounded-full overflow-hidden',
          size === 'sm' && 'h-1',
          size === 'md' && 'h-2',
          size === 'lg' && 'h-3',
        )}
      >
        <div
          className={clsx(
            'h-full transition-all duration-300 ease-out rounded-full',
            variant === 'default' && 'bg-gradient-to-r from-synapse to-pulse',
            variant === 'success' && 'bg-success',
            variant === 'warning' && 'bg-warning',
            variant === 'error' && 'bg-error',
          )}
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
    </div>
  )
}
