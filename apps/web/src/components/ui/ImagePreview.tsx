import { useState } from 'react'
import { clsx } from 'clsx'
import { Eye, EyeOff, AlertTriangle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useSettingsStore } from '@/stores/settingsStore'

interface ImagePreviewProps {
  src: string
  alt?: string
  nsfw?: boolean
  className?: string
  aspectRatio?: 'square' | 'video' | 'portrait' | 'auto'
  onClick?: () => void
}

export function ImagePreview({
  src,
  alt = 'Preview',
  nsfw = false,
  className,
  aspectRatio = 'square',
  onClick,
}: ImagePreviewProps) {
  const { nsfwBlurEnabled } = useSettingsStore()
  const { t } = useTranslation()
  const [isRevealed, setIsRevealed] = useState(false)
  const [isLoaded, setIsLoaded] = useState(false)
  const [hasError, setHasError] = useState(false)
  
  const shouldBlur = nsfw && nsfwBlurEnabled && !isRevealed
  
  const handleReveal = (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsRevealed(!isRevealed)
  }
  
  return (
    <div
      className={clsx(
        'relative overflow-hidden rounded-xl bg-slate-mid/50',
        aspectRatio === 'square' && 'aspect-square',
        aspectRatio === 'video' && 'aspect-video',
        aspectRatio === 'portrait' && 'aspect-[3/4]',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      {/* Loading skeleton */}
      {!isLoaded && !hasError && (
        <div className="absolute inset-0 skeleton" />
      )}
      
      {/* Error state */}
      {hasError && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-deep/50">
          <AlertTriangle className="w-8 h-8 text-text-muted" />
        </div>
      )}
      
      {/* Image */}
      <img
        src={src}
        alt={alt}
        className={clsx(
          'w-full h-full object-cover transition-all duration-300',
          !isLoaded && 'opacity-0',
          isLoaded && 'opacity-100',
          shouldBlur && 'blur-xl scale-110',
        )}
        onLoad={() => setIsLoaded(true)}
        onError={() => setHasError(true)}
      />
      
      {/* NSFW overlay */}
      {nsfw && nsfwBlurEnabled && (
        <div
          className={clsx(
            'absolute inset-0 flex flex-col items-center justify-center',
            'transition-opacity duration-300',
            isRevealed ? 'opacity-0 pointer-events-none' : 'opacity-100'
          )}
        >
          <div className="bg-slate-deep/80 backdrop-blur-sm p-3 rounded-xl text-center">
            <EyeOff className="w-6 h-6 text-text-muted mx-auto mb-1" />
            <span className="text-xs text-text-muted">{t('media.nsfw')}</span>
          </div>
        </div>
      )}
      
      {/* NSFW toggle button */}
      {nsfw && nsfwBlurEnabled && (
        <button
          onClick={handleReveal}
          className={clsx(
            'absolute top-2 right-2 p-1.5 rounded-lg',
            'bg-slate-deep/80 backdrop-blur-sm',
            'text-text-secondary hover:text-text-primary',
            'transition-colors duration-200',
          )}
        >
          {isRevealed ? (
            <EyeOff className="w-4 h-4" />
          ) : (
            <Eye className="w-4 h-4" />
          )}
        </button>
      )}
      
      {/* NSFW badge */}
      {nsfw && !nsfwBlurEnabled && (
        <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-error/80 text-white text-xs font-medium">
          {t('media.nsfw')}
        </div>
      )}
    </div>
  )
}
