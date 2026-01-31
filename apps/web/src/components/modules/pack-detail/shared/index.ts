/**
 * Shared Components
 *
 * Reusable UI components for pack detail sections.
 */

export { SectionHeader, type SectionHeaderProps } from './SectionHeader'
export { EmptyState, type EmptyStateProps, type EmptyStatePreset } from './EmptyState'
export { LoadingSection, type LoadingSectionProps, type LoadingVariant } from './LoadingSection'
export { AnimatedSection, type AnimatedSectionProps, useSectionStagger } from './AnimatedSection'
export {
  UnsavedChangesDialog,
  useBeforeUnload,
  type UnsavedChangesDialogProps,
} from './UnsavedChangesDialog'
export { EditableText, type EditableTextProps } from './EditableText'
export { EditableTags, type EditableTagsProps } from './EditableTags'
export {
  ErrorBoundary,
  SectionErrorBoundary,
  useErrorFallback,
  type ErrorBoundaryProps,
  type SectionErrorBoundaryProps,
} from './ErrorBoundary'
