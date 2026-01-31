/**
 * Pack Detail Sections
 *
 * Main content sections for PackDetailPage.
 * Each section handles its own rendering with preserved functionality
 * and enhanced visuals.
 */

// Header - pack identity and actions
export { PackHeader, type PackHeaderProps } from './PackHeader'

// Gallery - preview grid with MediaPreview (video algorithms preserved)
// Note: CardSize is exported from ../types, not re-exported here
export { PackGallery, type PackGalleryProps } from './PackGallery'

// Info - trigger words, model info, description (HTML rendering preserved)
export { PackInfoSection, type PackInfoSectionProps } from './PackInfoSection'

// Dependencies - asset management (ALL data and features preserved)
export { PackDependenciesSection, type PackDependenciesSectionProps } from './PackDependenciesSection'

// Workflows - ComfyUI workflow management
export { PackWorkflowsSection, type PackWorkflowsSectionProps } from './PackWorkflowsSection'

// Parameters - generation settings
export { PackParametersSection, type PackParametersSectionProps } from './PackParametersSection'

// Storage - backup/restore operations
export { PackStorageSection, type PackStorageSectionProps } from './PackStorageSection'

// User Tags - custom user-defined tags
export { PackUserTagsSection, type PackUserTagsSectionProps } from './PackUserTagsSection'
