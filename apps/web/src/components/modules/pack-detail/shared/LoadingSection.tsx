/**
 * LoadingSection Component
 *
 * Skeleton loading states for pack detail sections.
 * Matches the final layout for smooth transition.
 */

import { clsx } from 'clsx'

/**
 * Loading variant configurations
 */
export type LoadingVariant =
  | 'header'
  | 'gallery'
  | 'info'
  | 'dependencies'
  | 'workflows'
  | 'parameters'
  | 'section'  // Generic section

export interface LoadingSectionProps {
  /**
   * Loading variant to display
   */
  variant?: LoadingVariant

  /**
   * Number of items to show (for list variants)
   */
  itemCount?: number

  /**
   * Additional className
   */
  className?: string
}

/**
 * Shimmer animation base classes
 */
const shimmerBase = clsx(
  'relative overflow-hidden',
  'bg-white/5 rounded',
  'before:absolute before:inset-0',
  'before:-translate-x-full before:animate-[shimmer_2s_infinite]',
  'before:bg-gradient-to-r',
  'before:from-transparent before:via-white/10 before:to-transparent'
)

/**
 * Skeleton line component
 */
function SkeletonLine({ className }: { className?: string }) {
  return <div className={clsx(shimmerBase, 'h-4', className)} />
}

/**
 * Skeleton box component
 */
function SkeletonBox({ className }: { className?: string }) {
  return <div className={clsx(shimmerBase, className)} />
}

/**
 * Header loading state
 */
function HeaderLoading() {
  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-4">
        {/* Back button */}
        <SkeletonBox className="w-10 h-10 rounded-lg" />
        <div className="flex-1 space-y-2">
          {/* Title */}
          <SkeletonLine className="w-48 h-6" />
          {/* Badges */}
          <div className="flex gap-2">
            <SkeletonBox className="w-16 h-5 rounded-full" />
            <SkeletonBox className="w-20 h-5 rounded-full" />
            <SkeletonBox className="w-14 h-5 rounded-full" />
          </div>
        </div>
        {/* Action buttons */}
        <div className="flex gap-2">
          <SkeletonBox className="w-24 h-9 rounded-lg" />
          <SkeletonBox className="w-20 h-9 rounded-lg" />
        </div>
      </div>
    </div>
  )
}

/**
 * Gallery loading state
 */
function GalleryLoading({ itemCount = 6 }: { itemCount?: number }) {
  return (
    <div className="p-4">
      {/* Section header */}
      <div className="flex items-center justify-between mb-4">
        <SkeletonLine className="w-24" />
        <div className="flex gap-2">
          <SkeletonBox className="w-8 h-8 rounded-lg" />
          <SkeletonBox className="w-8 h-8 rounded-lg" />
        </div>
      </div>
      {/* Grid */}
      <div className="grid grid-cols-6 gap-3">
        {Array.from({ length: itemCount }).map((_, i) => (
          <SkeletonBox
            key={i}
            className="aspect-[3/4] rounded-lg"
          />
        ))}
      </div>
    </div>
  )
}

/**
 * Info section loading state
 */
function InfoLoading() {
  return (
    <div className="p-4 space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-3 pb-3 border-b border-white/5">
        <SkeletonBox className="w-5 h-5 rounded" />
        <SkeletonLine className="w-24" />
      </div>
      {/* Description */}
      <div className="space-y-2">
        <SkeletonLine className="w-full" />
        <SkeletonLine className="w-full" />
        <SkeletonLine className="w-3/4" />
      </div>
      {/* Tags */}
      <div className="flex gap-2 pt-2">
        <SkeletonBox className="w-16 h-6 rounded-full" />
        <SkeletonBox className="w-20 h-6 rounded-full" />
        <SkeletonBox className="w-14 h-6 rounded-full" />
      </div>
    </div>
  )
}

/**
 * Dependencies loading state
 */
function DependenciesLoading({ itemCount = 4 }: { itemCount?: number }) {
  return (
    <div className="p-4 space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-3 pb-3 border-b border-white/5">
        <SkeletonBox className="w-5 h-5 rounded" />
        <SkeletonLine className="w-28" />
        <SkeletonBox className="w-6 h-5 rounded-full" />
      </div>
      {/* List */}
      <div className="space-y-3">
        {Array.from({ length: itemCount }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02]">
            <SkeletonBox className="w-8 h-8 rounded-lg" />
            <div className="flex-1 space-y-1.5">
              <SkeletonLine className="w-32" />
              <SkeletonLine className="w-20 h-3" />
            </div>
            <SkeletonLine className="w-16" />
            <SkeletonBox className="w-8 h-8 rounded-lg" />
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Workflows loading state
 */
function WorkflowsLoading({ itemCount = 2 }: { itemCount?: number }) {
  return (
    <div className="p-4 space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-3 pb-3 border-b border-white/5">
        <SkeletonBox className="w-5 h-5 rounded" />
        <SkeletonLine className="w-24" />
      </div>
      {/* List */}
      <div className="space-y-2">
        {Array.from({ length: itemCount }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02]">
            <SkeletonBox className="w-10 h-10 rounded-lg" />
            <div className="flex-1 space-y-1.5">
              <SkeletonLine className="w-40" />
              <SkeletonLine className="w-24 h-3" />
            </div>
            <SkeletonBox className="w-20 h-7 rounded-lg" />
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Parameters loading state
 */
function ParametersLoading() {
  return (
    <div className="p-4 space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-3 pb-3 border-b border-white/5">
        <SkeletonBox className="w-5 h-5 rounded" />
        <SkeletonLine className="w-24" />
      </div>
      {/* Grid */}
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="p-3 rounded-lg bg-white/[0.02]">
            <SkeletonLine className="w-16 h-3 mb-2" />
            <SkeletonLine className="w-12 h-5" />
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Generic section loading state
 */
function SectionLoading() {
  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-3 pb-3 border-b border-white/5">
        <SkeletonBox className="w-5 h-5 rounded" />
        <SkeletonLine className="w-28" />
      </div>
      <div className="space-y-3">
        <SkeletonLine className="w-full" />
        <SkeletonLine className="w-4/5" />
        <SkeletonLine className="w-3/5" />
      </div>
    </div>
  )
}

export function LoadingSection({
  variant = 'section',
  itemCount,
  className,
}: LoadingSectionProps) {
  const content = {
    header: <HeaderLoading />,
    gallery: <GalleryLoading itemCount={itemCount} />,
    info: <InfoLoading />,
    dependencies: <DependenciesLoading itemCount={itemCount} />,
    workflows: <WorkflowsLoading itemCount={itemCount} />,
    parameters: <ParametersLoading />,
    section: <SectionLoading />,
  }[variant]

  return (
    <div className={clsx('rounded-xl bg-black/20', className)}>
      {content}
    </div>
  )
}

export default LoadingSection
