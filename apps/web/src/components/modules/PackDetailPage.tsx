/**
 * PackDetailPage
 *
 * Integrated pack detail page using modular components from pack-detail/.
 *
 * ARCHITECTURE:
 * - Hooks: usePackData, usePackDownloads, usePackEdit, usePackPlugin
 * - Sections: PackHeader, PackGallery, PackInfoSection, etc.
 * - Modals: EditPackModal, BaseModelResolverModal, etc.
 * - Plugins: CivitaiPlugin, CustomPlugin, InstallPlugin
 *
 * This file is the orchestrator - it connects hooks to components.
 */

import { useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'

import { FullscreenMediaViewer } from '@/components/ui/FullscreenMediaViewer'
import { BreathingOrb } from '@/components/ui/BreathingOrb'
import { Button } from '@/components/ui/Button'

// Modular pack-detail components
import {
  // Hooks
  usePackData,
  usePackDownloads,
  usePackEdit,
  usePackPlugin,
  // Sections
  PackHeader,
  PackGallery,
  PackInfoSection,
  PackDependenciesSection,
  PackWorkflowsSection,
  PackParametersSection,
  PackStorageSection,
  PackUserTagsSection,
  // Modals
  EditPackModal,
  EditParametersModal,
  UploadWorkflowModal,
  BaseModelResolverModal,
  // Shared
  ErrorBoundary,
  SectionErrorBoundary,
  // Types
  type LocalModel,
  type BaseModelSearchResponse,
  type HuggingFaceFile,
  type AssetInfo,
  type ModalState,
  // Constants
  DEFAULT_MODAL_STATE,
  QUERY_KEYS,
} from './pack-detail'

// Legacy components still used
import {
  PullConfirmDialog,
  PushConfirmDialog,
} from './packs'

// =============================================================================
// Component
// =============================================================================

function PackDetailPageContent() {
  const { packName: packNameParam } = useParams<{ packName: string }>()
  const navigate = useNavigate()

  // Decode pack name from URL
  const packName = packNameParam ? decodeURIComponent(packNameParam) : ''

  // ==========================================================================
  // Hooks
  // ==========================================================================

  // Main pack data and mutations
  const packData = usePackData({
    packName,
    onDeleteSuccess: () => navigate('/'),
  })

  // Download progress tracking
  const downloads = usePackDownloads({
    packName,
  })

  // Edit mode state
  const editState = usePackEdit({
    initialPack: packData.pack,
    onSave: async (changes) => {
      if (changes.user_tags) {
        await packData.updatePack({ user_tags: changes.user_tags })
      }
    },
  })

  // ==========================================================================
  // Modal State
  // ==========================================================================

  const [modals, setModals] = useState<ModalState>({ ...DEFAULT_MODAL_STATE })

  const openModal = useCallback((key: keyof ModalState | string) => {
    setModals((prev) => ({ ...prev, [key]: true }))
  }, [])

  const closeModal = useCallback((key: keyof ModalState | string) => {
    setModals((prev) => ({ ...prev, [key]: false }))
  }, [])

  // ==========================================================================
  // Plugin System
  // ==========================================================================

  const { plugin, context: pluginContext } = usePackPlugin({
    pack: packData.pack,
    isEditing: editState.isEditing,
    hasUnsavedChanges: editState.hasUnsavedChanges,
    modals,
    openModal,
    closeModal,
    refetch: packData.refetch,
  })

  // ==========================================================================
  // Fullscreen Gallery
  // ==========================================================================

  const [fullscreenIndex, setFullscreenIndex] = useState<number>(-1)

  const isFullscreenOpen = fullscreenIndex >= 0

  const mediaItems = useMemo(() => {
    return (
      packData.pack?.previews.map((p) => ({
        url: p.url || '',
        type: (p.media_type === 'video' ? 'video' : 'image') as 'video' | 'image',
        thumbnailUrl: p.thumbnail_url,
        nsfw: p.nsfw,
        width: p.width,
        height: p.height,
        meta: p.meta as Record<string, unknown> | undefined,
      })) || []
    )
  }, [packData.pack?.previews])

  // ==========================================================================
  // Base Model Resolver State
  // ==========================================================================

  const [resolverTab, setResolverTab] = useState<'local' | 'civitai' | 'huggingface'>('local')
  const [searchTrigger, setSearchTrigger] = useState('')

  // Local models from ComfyUI
  const { data: localModels = [], isLoading: isLoadingLocalModels } = useQuery<LocalModel[]>({
    queryKey: QUERY_KEYS.localModels('checkpoints'),
    queryFn: async () => {
      const res = await fetch('/api/comfyui/models/checkpoints')
      if (!res.ok) return []
      const data = await res.json()
      return (data || []).map((m: { name: string; path: string; size?: number }) => ({
        name: m.name,
        path: m.path,
        type: 'checkpoint',
        size: m.size,
      }))
    },
    enabled: modals.baseModelResolver,
  })

  // Remote search (Civitai/HuggingFace)
  const { data: searchResponse, isLoading: isSearching } = useQuery<BaseModelSearchResponse>({
    queryKey: QUERY_KEYS.baseModelSearch(resolverTab, searchTrigger),
    queryFn: async () => {
      if (!searchTrigger || searchTrigger.length < 2) {
        return { results: [], total_found: 0, source: resolverTab, search_query: '' }
      }
      if (resolverTab !== 'civitai' && resolverTab !== 'huggingface') {
        return { results: [], total_found: 0, source: resolverTab, search_query: '' }
      }

      const params = new URLSearchParams({
        query: searchTrigger,
        source: resolverTab,
        limit: '30',
        max_batches: '3',
      })
      const res = await fetch(`/api/browse/base-models/search?${params}`)
      if (!res.ok) throw new Error('Search failed')
      return res.json()
    },
    enabled:
      modals.baseModelResolver &&
      (resolverTab === 'civitai' || resolverTab === 'huggingface') &&
      searchTrigger.length >= 2,
    staleTime: 60000,
  })

  const handleBaseModelSearch = useCallback(
    (query: string, source: 'civitai' | 'huggingface') => {
      setResolverTab(source)
      setSearchTrigger(query)
    },
    []
  )

  const handleFetchHfFiles = useCallback(async (repoId: string): Promise<HuggingFaceFile[]> => {
    try {
      const res = await fetch(`/api/browse/huggingface/files?repo_id=${encodeURIComponent(repoId)}`)
      if (!res.ok) return []
      return res.json()
    } catch {
      return []
    }
  }, [])

  // ==========================================================================
  // Handlers
  // ==========================================================================

  // Dependencies section handlers
  const downloadingAssetsSet = useMemo(() => {
    const set = new Set<string>()
    downloads.activeDownloads.forEach((d) => {
      if (d.status === 'downloading' || d.status === 'pending') {
        set.add(d.asset_name)
      }
    })
    return set
  }, [downloads.activeDownloads])

  const handleRestoreFromBackup = useCallback(
    async (_asset: AssetInfo) => {
      // Trigger restore from backup - this would typically call a specific API
      // For now, we can use pullPack which restores all from backup
      packData.pullPack()
    },
    [packData]
  )

  // Push dialog state
  const [pushWithCleanup, setPushWithCleanup] = useState(false)

  // ==========================================================================
  // Render
  // ==========================================================================

  // Loading state
  if (packData.isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <BreathingOrb size="lg" text="Loading pack..." />
      </div>
    )
  }

  // Error state
  if (packData.error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="text-red-400 text-center">
          <p className="text-lg font-medium">Failed to load pack</p>
          <p className="text-sm mt-2">{packData.error.message}</p>
        </div>
        <Button variant="secondary" onClick={() => navigate('/')}>
          <ArrowLeft className="w-4 h-4" />
          Back to Packs
        </Button>
      </div>
    )
  }

  // No pack found
  if (!packData.pack) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <p className="text-text-muted">Pack not found</p>
        <Button variant="secondary" onClick={() => navigate('/')}>
          <ArrowLeft className="w-4 h-4" />
          Back to Packs
        </Button>
      </div>
    )
  }

  const { pack, backupStatus } = packData

  return (
    <div className="space-y-8 pb-12">
      {/* Back Button */}
      <Button
        variant="secondary"
        onClick={() => navigate('/')}
        className="opacity-70 hover:opacity-100 transition-opacity"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Packs
      </Button>

      {/* Header Section */}
      {/*
        Edit mode behavior depends on pack type:
        - Custom packs: Show Edit button, enable inline editing (canEditMetadata = true)
        - Civitai packs: Hide Edit button, use modal-based editing via section buttons
      */}
      <PackHeader
        pack={pack}
        onUsePack={packData.usePack}
        onDelete={packData.deletePack}
        isUsingPack={packData.isUsingPack}
        isDeleting={packData.isDeleting}
        animationDelay={0}
        // Edit mode - only show for plugins that support metadata editing
        isEditing={editState.isEditing}
        hasUnsavedChanges={editState.hasUnsavedChanges}
        isSaving={editState.isSaving}
        onStartEdit={plugin?.features?.canEditMetadata ? () => editState.startEditing() : undefined}
        onSaveChanges={editState.saveChanges}
        onDiscardChanges={editState.discardChanges}
        // Plugin header actions are rendered inside PackHeader via pluginActions prop
        pluginActions={pluginContext && plugin?.renderHeaderActions?.(pluginContext)}
      />

      {/* Gallery Section */}
      {pack.previews && pack.previews.length > 0 && (
        <SectionErrorBoundary sectionName="Gallery" onRetry={packData.refetch}>
          <PackGallery
            previews={pack.previews}
            onPreviewClick={(index) => setFullscreenIndex(index)}
            animationDelay={50}
          />
        </SectionErrorBoundary>
      )}

      {/* Info Section */}
      <SectionErrorBoundary sectionName="Information" onRetry={packData.refetch}>
        <PackInfoSection pack={pack} animationDelay={100} />
      </SectionErrorBoundary>

      {/* User Tags Section - always editable even for Civitai packs */}
      <SectionErrorBoundary sectionName="User Tags" onRetry={packData.refetch}>
        <PackUserTagsSection
          tags={pack.user_tags || []}
          onEdit={() => openModal('editPack')}
          animationDelay={125}
        />
      </SectionErrorBoundary>

      {/* Dependencies Section */}
      <SectionErrorBoundary sectionName="Dependencies" onRetry={packData.refetch}>
        <PackDependenciesSection
          assets={pack.assets}
          backupStatus={backupStatus}
          downloadingAssets={downloadingAssetsSet}
          getAssetDownload={downloads.getAssetDownload}
          onDownloadAll={downloads.downloadAll}
          onDownloadAsset={downloads.downloadAsset}
          onRestoreFromBackup={handleRestoreFromBackup}
          onDeleteResource={packData.deleteResource}
          onOpenBaseModelResolver={() => openModal('baseModelResolver')}
          onResolvePack={packData.resolvePack}
          isDownloadAllPending={downloads.isDownloadingAll}
          isResolvePending={packData.isResolvingPack}
          animationDelay={150}
        />
      </SectionErrorBoundary>

      {/* Workflows Section */}
      <SectionErrorBoundary sectionName="Workflows" onRetry={packData.refetch}>
        <PackWorkflowsSection
          workflows={pack.workflows}
          packName={pack.name}
          needsBaseModel={pack.has_unresolved}
          onCreateSymlink={packData.createSymlink}
          onRemoveSymlink={packData.removeSymlink}
          onDeleteWorkflow={packData.deleteWorkflow}
          onGenerateWorkflow={packData.generateWorkflow}
          onOpenUploadModal={() => openModal('uploadWorkflow')}
          isCreateSymlinkPending={packData.isCreatingSymlink}
          isRemoveSymlinkPending={packData.isRemovingSymlink}
          isDeletePending={packData.isDeletingWorkflow}
          isGeneratePending={packData.isGeneratingWorkflow}
          animationDelay={200}
        />
      </SectionErrorBoundary>

      {/* Parameters Section */}
      <SectionErrorBoundary sectionName="Parameters" onRetry={packData.refetch}>
        <PackParametersSection
          parameters={pack.parameters}
          modelInfo={pack.model_info}
          onEdit={() => openModal('editParameters')}
          animationDelay={250}
        />
      </SectionErrorBoundary>

      {/* Storage Section */}
      <SectionErrorBoundary sectionName="Storage" onRetry={packData.refetch}>
        <PackStorageSection
          backupStatus={backupStatus}
          isLoading={packData.isBackupStatusLoading}
          onPull={() => openModal('pullConfirm')}
          onPush={() => {
            setPushWithCleanup(false)
            openModal('pushConfirm')
          }}
          onPushAndFree={() => {
            setPushWithCleanup(true)
            openModal('pushConfirm')
          }}
          isPulling={packData.isPullingPack}
          isPushing={packData.isPushingPack}
          animationDelay={300}
        />
      </SectionErrorBoundary>

      {/* =====================================================================
          PLUGIN SECTIONS
          ===================================================================== */}

      {/* Plugin Extra Sections (CivitaiPlugin: updates, CustomPlugin: pack deps, etc.) */}
      {pluginContext && plugin?.renderExtraSections && (
        <SectionErrorBoundary
          sectionName={`${plugin.name || 'Plugin'} Sections`}
          onRetry={packData.refetch}
        >
          {plugin.renderExtraSections(pluginContext)}
        </SectionErrorBoundary>
      )}

      {/* Plugin Modals - wrapped in error boundary for safety */}
      <ErrorBoundary
        onError={(error) => {
          console.error('[PackDetailPage] Plugin modal error:', error)
        }}
      >
        {pluginContext && plugin?.renderModals?.(pluginContext)}
      </ErrorBoundary>

      {/* =====================================================================
          MODALS
          ===================================================================== */}

      {/* Fullscreen Gallery Viewer */}
      <FullscreenMediaViewer
        isOpen={isFullscreenOpen}
        items={mediaItems}
        initialIndex={fullscreenIndex}
        onClose={() => setFullscreenIndex(-1)}
      />

      {/* Edit Pack Modal (User Tags) */}
      <EditPackModal
        isOpen={modals.editPack}
        initialTags={pack.user_tags}
        onSave={(tags) => {
          packData.updatePack({ user_tags: tags })
          closeModal('editPack')
        }}
        onClose={() => closeModal('editPack')}
        isSaving={packData.isUpdatingPack}
      />

      {/* Edit Parameters Modal */}
      <EditParametersModal
        isOpen={modals.editParameters}
        initialParameters={
          pack.parameters
            ? Object.fromEntries(
                Object.entries(pack.parameters).map(([k, v]) => [k, String(v ?? '')])
              )
            : {}
        }
        onSave={(params) => {
          packData.updateParameters(params as Record<string, unknown>)
          closeModal('editParameters')
        }}
        onClose={() => closeModal('editParameters')}
        isSaving={packData.isUpdatingParameters}
      />

      {/* Upload Workflow Modal */}
      <UploadWorkflowModal
        isOpen={modals.uploadWorkflow}
        onUpload={(data) => {
          packData.uploadWorkflow(data)
          closeModal('uploadWorkflow')
        }}
        onClose={() => closeModal('uploadWorkflow')}
        isUploading={packData.isUploadingWorkflow}
      />

      {/* Base Model Resolver Modal */}
      <BaseModelResolverModal
        isOpen={modals.baseModelResolver}
        packDescription={pack.description}
        localModels={localModels}
        isLoadingLocalModels={isLoadingLocalModels}
        searchResponse={searchResponse}
        isSearching={isSearching}
        onSearch={handleBaseModelSearch}
        onFetchHfFiles={handleFetchHfFiles}
        onResolve={(data) => {
          packData.resolveBaseModel(data)
          closeModal('baseModelResolver')
        }}
        onClose={() => closeModal('baseModelResolver')}
        isResolving={packData.isResolvingBaseModel}
      />

      {/* Pull Confirm Dialog */}
      <PullConfirmDialog
        isOpen={modals.pullConfirm}
        onConfirm={() => {
          packData.pullPack()
          closeModal('pullConfirm')
        }}
        onClose={() => closeModal('pullConfirm')}
        isLoading={packData.isPullingPack}
        packName={pack.name}
        blobs={backupStatus?.blobs?.filter(b => b.location === 'backup_only') || []}
      />

      {/* Push Confirm Dialog */}
      <PushConfirmDialog
        isOpen={modals.pushConfirm}
        onConfirm={(cleanup) => {
          packData.pushPack(cleanup)
          closeModal('pushConfirm')
        }}
        onClose={() => closeModal('pushConfirm')}
        isLoading={packData.isPushingPack}
        packName={pack.name}
        blobs={backupStatus?.blobs?.filter(b => b.location === 'local_only') || []}
        initialCleanup={pushWithCleanup}
      />
    </div>
  )
}

// =============================================================================
// Exported Component with Error Boundary
// =============================================================================

export function PackDetailPage() {
  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        console.error('[PackDetailPage] Error caught by boundary:', error)
        console.error('[PackDetailPage] Component stack:', errorInfo.componentStack)
      }}
    >
      <PackDetailPageContent />
    </ErrorBoundary>
  )
}

export default PackDetailPage
