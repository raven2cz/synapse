/**
 * Pack Detail Modals
 *
 * Extracted modal components for pack editing operations.
 * Each modal handles its own internal state and UI.
 */

// Edit Pack - user tags editor
export { EditPackModal, type EditPackModalProps } from './EditPackModal'

// Edit Parameters - generation settings editor
export { EditParametersModal, type EditParametersModalProps } from './EditParametersModal'

// Upload Workflow - ComfyUI workflow upload
export { UploadWorkflowModal, type UploadWorkflowModalProps } from './UploadWorkflowModal'

// Base Model Resolver - multi-source base model selection
export { BaseModelResolverModal, type BaseModelResolverModalProps } from './BaseModelResolverModal'

// Edit Previews - drag & drop preview management (Phase 2)
export { EditPreviewsModal, type EditPreviewsModalProps } from './EditPreviewsModal'

// Edit Dependencies - dependency management (Phase 2)
export { EditDependenciesModal, type EditDependenciesModalProps } from './EditDependenciesModal'

// Description Editor - Markdown/HTML editor (Phase 2)
export {
  DescriptionEditorModal,
  type DescriptionEditorModalProps,
  type ContentFormat,
} from './DescriptionEditorModal'

// Create Pack - new pack wizard (Phase 3)
export {
  CreatePackModal,
  type CreatePackModalProps,
  type CreatePackData,
} from './CreatePackModal'
