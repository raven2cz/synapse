import { clsx } from 'clsx'
import { ReactNode } from 'react'

interface CardProps {
  children?: ReactNode
  className?: string
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
  onClick?: () => void
}

export function Card({ 
  children, 
  className, 
  hover = false, 
  padding = 'md',
  onClick,
}: CardProps) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        'bg-slate-deep/50 rounded-2xl',
        'border border-slate-mid/50',
        
        hover && [
          'transition-all duration-200 cursor-pointer',
          'hover:border-synapse/30',
          'hover:shadow-lg hover:shadow-synapse/5',
        ],
        
        padding === 'none' && '',
        padding === 'sm' && 'p-3',
        padding === 'md' && 'p-4',
        padding === 'lg' && 'p-6',
        
        className
      )}
    >
      {children}
    </div>
  )
}

export function CardHeader({ 
  children, 
  className 
}: { 
  children: ReactNode
  className?: string 
}) {
  return (
    <div className={clsx('mb-4', className)}>
      {children}
    </div>
  )
}

export function CardTitle({ 
  children, 
  className 
}: { 
  children: ReactNode
  className?: string 
}) {
  return (
    <h3 className={clsx('text-lg font-semibold text-text-primary', className)}>
      {children}
    </h3>
  )
}

export function CardDescription({ 
  children, 
  className 
}: { 
  children: ReactNode
  className?: string 
}) {
  return (
    <p className={clsx('text-sm text-text-secondary mt-1', className)}>
      {children}
    </p>
  )
}
