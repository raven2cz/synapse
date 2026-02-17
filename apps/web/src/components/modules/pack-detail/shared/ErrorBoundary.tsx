/**
 * ErrorBoundary Component
 *
 * React Error Boundary for gracefully handling errors in the pack detail page.
 * Catches JavaScript errors and displays a friendly fallback UI.
 *
 * FEATURES:
 * - Catches render errors in child components
 * - Shows friendly error message with recovery actions
 * - Logs errors for debugging
 * - Integrates with existing design system
 */

import { Component, type ReactNode, type ErrorInfo } from 'react'
import { t } from 'i18next'
import { AlertTriangle, RefreshCw, Home, ChevronDown, ChevronUp } from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface ErrorBoundaryProps {
  /**
   * Child components to render
   */
  children: ReactNode

  /**
   * Optional fallback UI to show instead of default error UI
   */
  fallback?: ReactNode

  /**
   * Callback when error occurs
   */
  onError?: (error: Error, errorInfo: ErrorInfo) => void

  /**
   * Whether to show detailed error info (dev mode)
   */
  showDetails?: boolean
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  showStack: boolean
}

// =============================================================================
// Error Boundary Class Component
// =============================================================================

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showStack: false,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo })

    // Log error for debugging
    console.error('[ErrorBoundary] Caught error:', error)
    console.error('[ErrorBoundary] Component stack:', errorInfo.componentStack)

    // Call optional error handler
    this.props.onError?.(error, errorInfo)
  }

  handleRetry = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      showStack: false,
    })
  }

  handleGoHome = (): void => {
    window.location.href = '/'
  }

  toggleStack = (): void => {
    this.setState(prev => ({ showStack: !prev.showStack }))
  }

  render(): ReactNode {
    const { hasError, error, errorInfo, showStack } = this.state
    // Show details in development mode (localhost or explicit prop)
    const isDev = typeof window !== 'undefined' && window.location.hostname === 'localhost'
    const { children, fallback, showDetails = isDev } = this.props

    if (hasError) {
      // Use custom fallback if provided
      if (fallback) {
        return fallback
      }

      // Default error UI
      return (
        <div
          className={clsx(
            'flex flex-col items-center justify-center min-h-[50vh] p-8',
            ANIMATION_PRESETS.fadeIn
          )}
        >
          <Card className="max-w-lg w-full p-8 text-center">
            {/* Error Icon */}
            <div className="flex justify-center mb-6">
              <div className={clsx(
                'p-4 rounded-2xl',
                'bg-red-500/10 border border-red-500/30'
              )}>
                <AlertTriangle className="w-12 h-12 text-red-400" />
              </div>
            </div>

            {/* Error Message */}
            <h2 className="text-2xl font-bold text-text-primary mb-3">
              {t('pack.shared.errorBoundary.somethingWentWrong')}
            </h2>
            <p className="text-text-muted mb-6">
              {t('pack.shared.errorBoundary.unexpectedError')}{' '}
              {t('pack.shared.errorBoundary.tryAgainHint')}
            </p>

            {/* Error Details (Dev Mode) */}
            {showDetails && error && (
              <div className="mb-6 text-left">
                <button
                  onClick={this.toggleStack}
                  className={clsx(
                    'flex items-center gap-2 text-sm text-text-muted',
                    'hover:text-text-primary transition-colors'
                  )}
                >
                  {showStack ? (
                    <ChevronUp className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                  {showStack ? t('pack.shared.errorBoundary.hideErrors') : t('pack.shared.errorBoundary.showErrors')}
                </button>

                {showStack && (
                  <div className={clsx(
                    'mt-3 p-4 rounded-lg',
                    'bg-obsidian border border-slate-mid',
                    'overflow-auto max-h-48',
                    ANIMATION_PRESETS.fadeIn
                  )}>
                    <p className="text-red-400 font-mono text-sm mb-2">
                      {error.name}: {error.message}
                    </p>
                    {errorInfo?.componentStack && (
                      <pre className="text-text-muted text-xs whitespace-pre-wrap font-mono">
                        {errorInfo.componentStack}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3 justify-center">
              <Button
                variant="secondary"
                onClick={this.handleGoHome}
                className="flex items-center gap-2"
              >
                <Home className="w-4 h-4" />
                {t('pack.shared.errorBoundary.goHome')}
              </Button>
              <Button
                variant="primary"
                onClick={this.handleRetry}
                className="flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                {t('pack.shared.errorBoundary.tryAgain')}
              </Button>
            </div>
          </Card>
        </div>
      )
    }

    return children
  }
}

// =============================================================================
// Hook for functional component error handling
// =============================================================================

/**
 * Hook to create error fallback content
 */
export function useErrorFallback(error: Error | null): ReactNode {
  if (!error) return null

  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <AlertTriangle className="w-12 h-12 text-red-400 mb-4" />
      <h3 className="text-lg font-bold text-text-primary mb-2">{t('pack.shared.errorBoundary.error')}</h3>
      <p className="text-text-muted text-sm">{error.message}</p>
    </div>
  )
}

// =============================================================================
// Specialized Error Boundaries
// =============================================================================

/**
 * Section-level error boundary with compact display and proper retry support
 */
export interface SectionErrorBoundaryProps {
  children: ReactNode
  sectionName?: string
  onRetry?: () => void
}

interface SectionErrorBoundaryState {
  hasError: boolean
  error: Error | null
  retryCount: number
}

/**
 * Section-level error boundary that properly resets on retry
 */
export class SectionErrorBoundary extends Component<
  SectionErrorBoundaryProps,
  SectionErrorBoundaryState
> {
  constructor(props: SectionErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      retryCount: 0,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<SectionErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error(`[SectionErrorBoundary:${this.props.sectionName}] Error:`, error)
    console.error(`[SectionErrorBoundary:${this.props.sectionName}] Stack:`, errorInfo.componentStack)
  }

  handleRetry = (): void => {
    // Reset error state first, then call onRetry
    this.setState(
      { hasError: false, error: null, retryCount: this.state.retryCount + 1 },
      () => {
        // Call onRetry after state reset to trigger re-render with fresh data
        this.props.onRetry?.()
      }
    )
  }

  render(): ReactNode {
    const { hasError, error } = this.state
    const { children, sectionName = 'section' } = this.props

    if (hasError) {
      return (
        <Card className={clsx('p-6 text-center', ANIMATION_PRESETS.fadeIn)}>
          <div className="flex items-center justify-center gap-3 text-amber-400 mb-3">
            <AlertTriangle className="w-5 h-5" />
            <span className="font-medium">{t('pack.shared.errorBoundary.failedToLoad', { section: sectionName })}</span>
          </div>
          <p className="text-text-muted text-sm mb-4">
            {t('pack.shared.errorBoundary.sectionError')}
          </p>
          {/* Show error message in dev mode */}
          {error && typeof window !== 'undefined' && window.location.hostname === 'localhost' && (
            <p className="text-red-400 text-xs font-mono mb-4 truncate">
              {error.message}
            </p>
          )}
          <Button variant="secondary" size="sm" onClick={this.handleRetry}>
            <RefreshCw className="w-4 h-4" />
            {t('pack.shared.errorBoundary.retry')}
          </Button>
        </Card>
      )
    }

    return children
  }
}

export default ErrorBoundary
