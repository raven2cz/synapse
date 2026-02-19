/**
 * usePackData Hook
 *
 * Centralized data management for pack detail page.
 * Handles all pack queries and mutations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from '@/stores/toastStore'
import type {
  PackDetail,
  PackBackupStatusResponse,
} from '../types'
import { QUERY_KEYS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface UsePackDataOptions {
  /**
   * Pack name to load
   */
  packName: string

  /**
   * Callback after successful deletion
   */
  onDeleteSuccess?: () => void
}

export interface UsePackDataReturn {
  // Queries
  pack: PackDetail | undefined
  isLoading: boolean
  error: Error | null
  backupStatus: PackBackupStatusResponse | undefined
  isBackupStatusLoading: boolean

  // Mutations
  deletePack: () => void
  isDeleting: boolean

  usePack: () => void
  isUsingPack: boolean

  updatePack: (data: { user_tags: string[] }) => void
  isUpdatingPack: boolean

  updateParameters: (data: Record<string, unknown>) => void
  isUpdatingParameters: boolean

  resolveBaseModel: (data: {
    model_path?: string
    download_url?: string
    source?: string
    file_name?: string
    size_kb?: number
  }) => void
  isResolvingBaseModel: boolean

  resolvePack: () => void
  isResolvingPack: boolean

  generateWorkflow: () => void
  isGeneratingWorkflow: boolean

  createSymlink: (filename: string) => void
  isCreatingSymlink: boolean

  removeSymlink: (filename: string) => void
  isRemovingSymlink: boolean

  deleteWorkflow: (filename: string) => void
  isDeletingWorkflow: boolean

  uploadWorkflow: (data: { file: File; name: string; description?: string }) => void
  isUploadingWorkflow: boolean

  deleteResource: (depId: string, deleteDependency?: boolean) => void
  isDeletingResource: boolean

  setAsBaseModel: (depId: string) => void
  isSettingBaseModel: boolean

  pullPack: () => void
  isPullingPack: boolean

  pushPack: (cleanup: boolean) => void
  isPushingPack: boolean

  // Preview & Description Mutations (Phase 6)
  updateDescription: (description: string) => void
  isUpdatingDescription: boolean

  // Batch update - preferred method for EditPreviewsModal
  batchUpdatePreviews: (data: {
    files?: File[]
    order?: string[]
    coverFilename?: string
    deleted?: string[]
  }) => Promise<unknown>
  isBatchUpdatingPreviews: boolean

  // Individual mutations (kept for backwards compatibility)
  uploadPreview: (data: { file: File; position?: number; nsfw?: boolean }) => void
  uploadPreviewAsync: (data: { file: File; position?: number; nsfw?: boolean }) => Promise<unknown>
  isUploadingPreview: boolean

  deletePreview: (filename: string) => void
  deletePreviewAsync: (filename: string) => Promise<unknown>
  isDeletingPreview: boolean

  reorderPreviews: (order: string[]) => void
  reorderPreviewsAsync: (order: string[]) => Promise<unknown>
  isReorderingPreviews: boolean

  setCoverPreview: (filename: string) => void
  setCoverPreviewAsync: (filename: string) => Promise<unknown>
  isSettingCover: boolean

  // Refetch
  refetch: () => void
  refetchBackupStatus: () => void
}

// =============================================================================
// Hook Implementation
// =============================================================================

export function usePackData({
  packName,
  onDeleteSuccess,
}: UsePackDataOptions): UsePackDataReturn {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  // =========================================================================
  // Pack Detail Query
  // =========================================================================

  const {
    data: pack,
    isLoading,
    error,
    refetch,
  } = useQuery<PackDetail, Error>({
    queryKey: QUERY_KEYS.pack(packName),
    queryFn: async () => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`)
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to fetch pack: ${res.status} - ${errText}`)
      }
      return res.json()
    },
    enabled: !!packName,
  })

  // =========================================================================
  // Backup Status Query
  // =========================================================================

  const {
    data: backupStatus,
    isLoading: isBackupStatusLoading,
    refetch: refetchBackupStatus,
  } = useQuery<PackBackupStatusResponse>({
    queryKey: QUERY_KEYS.packBackup(packName),
    queryFn: async () => {
      const res = await fetch(`/api/store/backup/pack-status/${encodeURIComponent(packName)}`)
      if (!res.ok) {
        return {
          pack: packName,
          backup_enabled: false,
          backup_connected: false,
          blobs: [],
          summary: { total: 0, local_only: 0, backup_only: 0, both: 0, nowhere: 0, total_bytes: 0 },
        }
      }
      return res.json()
    },
    enabled: !!packName,
    staleTime: 30000,
  })

  // =========================================================================
  // Delete Pack Mutation
  // =========================================================================

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`, { method: 'DELETE' })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to delete pack: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      toast.success('Pack deleted')
      onDeleteSuccess?.()
      navigate('/')
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete pack: ${error.message}`)
    },
  })

  // =========================================================================
  // Use Pack Mutation
  // =========================================================================

  const usePackMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/profiles/use', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pack: packName,
          ui_set: 'local',
          sync: true,
        }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to activate pack: ${errText}`)
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
      const profileName = data?.new_profile || `work__${packName}`
      toast.success(`Activated: ${profileName}`)
    },
    onError: (error: Error) => {
      toast.error(`Failed to activate: ${error.message}`)
    },
  })

  // =========================================================================
  // Update Pack Mutation
  // =========================================================================

  const updatePackMutation = useMutation({
    mutationFn: async (data: { user_tags: string[] }) => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to update pack: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      toast.success('Pack updated')
    },
    onError: (error: Error) => {
      toast.error(`Failed to update pack: ${error.message}`)
    },
  })

  // =========================================================================
  // Update Parameters Mutation
  // =========================================================================

  const updateParametersMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/parameters`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to update parameters: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Parameters updated')
    },
    onError: (error: Error) => {
      toast.error(`Failed to update parameters: ${error.message}`)
    },
  })

  // =========================================================================
  // Resolve Base Model Mutation
  // =========================================================================

  const resolveBaseModelMutation = useMutation({
    mutationFn: async (data: {
      model_path?: string
      download_url?: string
      source?: string
      file_name?: string
      size_kb?: number
    }) => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/resolve-base-model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack_name: packName, ...data }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to resolve base model: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      toast.success('Base model resolved')
    },
    onError: (error: Error) => {
      toast.error(`Failed to resolve base model: ${error.message}`)
    },
  })

  // =========================================================================
  // Resolve Pack Mutation
  // =========================================================================

  const resolvePackMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/resolve`, {
        method: 'POST',
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to resolve: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.packBackup(packName) })
      toast.success('Dependencies resolved')
    },
    onError: (error: Error) => {
      toast.error(`Failed to resolve: ${error.message}`)
    },
  })

  // =========================================================================
  // Workflow Mutations
  // =========================================================================

  const generateWorkflowMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/generate-workflow`, {
        method: 'POST',
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to generate workflow: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Workflow generated')
    },
    onError: (error: Error) => {
      toast.error(`Failed to generate workflow: ${error.message}`)
    },
  })

  const createSymlinkMutation = useMutation({
    mutationFn: async (filename: string) => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/workflow/symlink`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to create symlink: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Workflow symlink created')
    },
    onError: (error: Error) => {
      toast.error(`Failed to create symlink: ${error.message}`)
    },
  })

  const removeSymlinkMutation = useMutation({
    mutationFn: async (filename: string) => {
      const res = await fetch(
        `/api/packs/${encodeURIComponent(packName)}/workflow/${encodeURIComponent(filename)}/symlink`,
        { method: 'DELETE' }
      )
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to remove symlink: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Workflow symlink removed')
    },
    onError: (error: Error) => {
      toast.error(`Failed to remove symlink: ${error.message}`)
    },
  })

  const deleteWorkflowMutation = useMutation({
    mutationFn: async (filename: string) => {
      const res = await fetch(
        `/api/packs/${encodeURIComponent(packName)}/workflow/${encodeURIComponent(filename)}`,
        { method: 'DELETE' }
      )
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to delete workflow: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Workflow deleted')
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete workflow: ${error.message}`)
    },
  })

  const uploadWorkflowMutation = useMutation({
    mutationFn: async (data: { file: File; name: string; description?: string }) => {
      const formData = new FormData()
      formData.append('file', data.file)
      formData.append('name', data.name)
      if (data.description) formData.append('description', data.description)

      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/workflow/upload-file`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to upload workflow: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Workflow uploaded')
    },
    onError: (error: Error) => {
      toast.error(`Failed to upload workflow: ${error.message}`)
    },
  })

  // =========================================================================
  // Delete Resource Mutation
  // =========================================================================

  const deleteResourceMutation = useMutation({
    mutationFn: async ({ depId, deleteDependency = false }: { depId: string; deleteDependency?: boolean }) => {
      const res = await fetch(
        `/api/packs/${encodeURIComponent(packName)}/dependencies/${encodeURIComponent(depId)}/resource?delete_dependency=${deleteDependency}`,
        { method: 'DELETE' }
      )
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to delete resource: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Resource deleted')
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete resource: ${error.message}`)
    },
  })

  // =========================================================================
  // Set As Base Model Mutation
  // =========================================================================

  const setAsBaseModelMutation = useMutation({
    mutationFn: async (depId: string) => {
      const res = await fetch(
        `/api/packs/${encodeURIComponent(packName)}/dependencies/${encodeURIComponent(depId)}/set-base-model`,
        { method: 'POST' }
      )
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to set as base model: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Base model updated')
    },
    onError: (error: Error) => {
      toast.error(`Failed to set as base model: ${error.message}`)
    },
  })

  // =========================================================================
  // Backup Mutations
  // =========================================================================

  const pullPackMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/store/backup/pull-pack/${encodeURIComponent(packName)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run: false }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(errText)
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.packBackup(packName) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success(`Restored ${data.blobs_synced} blob${data.blobs_synced !== 1 ? 's' : ''} from backup`)
    },
    onError: (error: Error) => {
      toast.error(`Pull failed: ${error.message}`)
    },
  })

  const pushPackMutation = useMutation({
    mutationFn: async (cleanup: boolean) => {
      const res = await fetch(`/api/store/backup/push-pack/${encodeURIComponent(packName)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run: false, cleanup }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(errText)
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.packBackup(packName) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      if (data.cleanup) {
        toast.success(`Backed up ${data.blobs_synced} blob${data.blobs_synced !== 1 ? 's' : ''} and freed local space`)
      } else {
        toast.success(`Backed up ${data.blobs_synced} blob${data.blobs_synced !== 1 ? 's' : ''}`)
      }
    },
    onError: (error: Error) => {
      toast.error(`Push failed: ${error.message}`)
    },
  })

  // =========================================================================
  // Preview & Description Mutations (Phase 6)
  // =========================================================================

  const updateDescriptionMutation = useMutation({
    mutationFn: async (description: string) => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to update description: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Description updated')
    },
    onError: (error: Error) => {
      toast.error(`Failed to update description: ${error.message}`)
    },
  })

  const batchUpdatePreviewsMutation = useMutation({
    mutationFn: async (data: {
      files?: File[]
      order?: string[]
      coverFilename?: string
      deleted?: string[]
    }) => {
      const formData = new FormData()

      // Add files
      if (data.files?.length) {
        for (const file of data.files) {
          formData.append('files', file)
        }
      }

      // Add order as JSON
      if (data.order?.length) {
        formData.append('order', JSON.stringify(data.order))
      }

      // Add cover filename
      if (data.coverFilename) {
        formData.append('cover_filename', data.coverFilename)
      }

      // Add deleted as JSON
      if (data.deleted?.length) {
        formData.append('deleted', JSON.stringify(data.deleted))
      }

      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/previews`, {
        method: 'PATCH',
        body: formData,
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to update previews: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      toast.success('Previews updated')
    },
    onError: (error: Error) => {
      toast.error(`Failed to update previews: ${error.message}`)
    },
  })

  const uploadPreviewMutation = useMutation({
    mutationFn: async (data: { file: File; position?: number; nsfw?: boolean }) => {
      const formData = new FormData()
      formData.append('file', data.file)
      formData.append('position', String(data.position ?? -1))
      formData.append('nsfw', String(data.nsfw ?? false))

      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/previews/upload`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to upload preview: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Preview uploaded')
    },
    onError: (error: Error) => {
      toast.error(`Failed to upload preview: ${error.message}`)
    },
  })

  const deletePreviewMutation = useMutation({
    mutationFn: async (filename: string) => {
      const res = await fetch(
        `/api/packs/${encodeURIComponent(packName)}/previews/${encodeURIComponent(filename)}`,
        { method: 'DELETE' }
      )
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to delete preview: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Preview deleted')
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete preview: ${error.message}`)
    },
  })

  const reorderPreviewsMutation = useMutation({
    mutationFn: async (order: string[]) => {
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/previews/order`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to reorder previews: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      toast.success('Preview order updated')
    },
    onError: (error: Error) => {
      toast.error(`Failed to reorder previews: ${error.message}`)
    },
  })

  const setCoverPreviewMutation = useMutation({
    mutationFn: async (filename: string) => {
      const res = await fetch(
        `/api/packs/${encodeURIComponent(packName)}/previews/${encodeURIComponent(filename)}/cover`,
        { method: 'PATCH' }
      )
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to set cover: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      toast.success('Cover image updated')
    },
    onError: (error: Error) => {
      toast.error(`Failed to set cover: ${error.message}`)
    },
  })

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // Queries
    pack,
    isLoading,
    error,
    backupStatus,
    isBackupStatusLoading,

    // Mutations
    deletePack: () => deleteMutation.mutate(),
    isDeleting: deleteMutation.isPending,

    usePack: () => usePackMutation.mutate(),
    isUsingPack: usePackMutation.isPending,

    updatePack: (data) => updatePackMutation.mutate(data),
    isUpdatingPack: updatePackMutation.isPending,

    updateParameters: (data) => updateParametersMutation.mutate(data),
    isUpdatingParameters: updateParametersMutation.isPending,

    resolveBaseModel: (data) => resolveBaseModelMutation.mutate(data),
    isResolvingBaseModel: resolveBaseModelMutation.isPending,

    resolvePack: () => resolvePackMutation.mutate(),
    isResolvingPack: resolvePackMutation.isPending,

    generateWorkflow: () => generateWorkflowMutation.mutate(),
    isGeneratingWorkflow: generateWorkflowMutation.isPending,

    createSymlink: (filename) => createSymlinkMutation.mutate(filename),
    isCreatingSymlink: createSymlinkMutation.isPending,

    removeSymlink: (filename) => removeSymlinkMutation.mutate(filename),
    isRemovingSymlink: removeSymlinkMutation.isPending,

    deleteWorkflow: (filename) => deleteWorkflowMutation.mutate(filename),
    isDeletingWorkflow: deleteWorkflowMutation.isPending,

    uploadWorkflow: (data) => uploadWorkflowMutation.mutate(data),
    isUploadingWorkflow: uploadWorkflowMutation.isPending,

    deleteResource: (depId, deleteDependency) =>
      deleteResourceMutation.mutate({ depId, deleteDependency }),
    isDeletingResource: deleteResourceMutation.isPending,

    setAsBaseModel: (depId) => setAsBaseModelMutation.mutate(depId),
    isSettingBaseModel: setAsBaseModelMutation.isPending,

    pullPack: () => pullPackMutation.mutate(),
    isPullingPack: pullPackMutation.isPending,

    pushPack: (cleanup) => pushPackMutation.mutate(cleanup),
    isPushingPack: pushPackMutation.isPending,

    // Preview & Description (Phase 6)
    updateDescription: (description) => updateDescriptionMutation.mutate(description),
    isUpdatingDescription: updateDescriptionMutation.isPending,

    batchUpdatePreviews: (data) => batchUpdatePreviewsMutation.mutateAsync(data),
    isBatchUpdatingPreviews: batchUpdatePreviewsMutation.isPending,

    uploadPreview: (data) => uploadPreviewMutation.mutate(data),
    uploadPreviewAsync: (data) => uploadPreviewMutation.mutateAsync(data),
    isUploadingPreview: uploadPreviewMutation.isPending,

    deletePreview: (filename) => deletePreviewMutation.mutate(filename),
    deletePreviewAsync: (filename) => deletePreviewMutation.mutateAsync(filename),
    isDeletingPreview: deletePreviewMutation.isPending,

    reorderPreviews: (order) => reorderPreviewsMutation.mutate(order),
    reorderPreviewsAsync: (order) => reorderPreviewsMutation.mutateAsync(order),
    isReorderingPreviews: reorderPreviewsMutation.isPending,

    setCoverPreview: (filename) => setCoverPreviewMutation.mutate(filename),
    setCoverPreviewAsync: (filename) => setCoverPreviewMutation.mutateAsync(filename),
    isSettingCover: setCoverPreviewMutation.isPending,

    // Refetch
    refetch: () => refetch(),
    refetchBackupStatus: () => refetchBackupStatus(),
  }
}

export default usePackData
