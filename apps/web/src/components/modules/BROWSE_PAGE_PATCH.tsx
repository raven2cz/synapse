/**
 * BrowsePage Import Wizard Integration Patch
 * 
 * This file contains the exact code changes needed to integrate
 * ImportWizardModal into BrowsePage.tsx.
 * 
 * INSTALLATION STEPS:
 * 
 * 1. Add ImportWizardModal.tsx to: apps/web/src/components/ui/
 * 2. Follow the steps below to modify BrowsePage.tsx
 * 
 * @version 2.6.0
 */

// =============================================================================
// STEP 1: ADD IMPORTS
// =============================================================================
// Add these imports at the TOP of BrowsePage.tsx, with other imports:

// ADD THIS LINE:
import { ImportWizardModal, type ModelVersion, type ImportOptions } from '@/components/ui/ImportWizardModal'

// ADD 'Sparkles' to the lucide-react import:
// BEFORE: import { Search, Loader2, X, ... } from 'lucide-react'
// AFTER:  import { Search, Loader2, X, Sparkles, ... } from 'lucide-react'


// =============================================================================
// STEP 2: ADD TYPES
// =============================================================================
// Add this interface AFTER the existing interfaces (ModelVersion, ModelDetail, etc.)

interface WizardModelData {
  modelId: number
  modelName: string
  versions: ModelVersion[]
}


// =============================================================================
// STEP 3: ADD STATE VARIABLES
// =============================================================================
// Add these state variables INSIDE the BrowsePage function, near other useState calls:

// Import Wizard state
const [showImportWizard, setShowImportWizard] = useState(false)
const [wizardModelData, setWizardModelData] = useState<WizardModelData | null>(null)
const [isLoadingWizardPreview, setIsLoadingWizardPreview] = useState(false)


// =============================================================================
// STEP 4: ADD WIZARD FUNCTIONS
// =============================================================================
// Add these functions AFTER the existing handlers (handleSearch, handleImport, etc.)

/**
 * Opens Import Wizard by fetching model preview data.
 * Falls back to direct import if wizard data fetch fails.
 */
const openImportWizard = useCallback(async (modelId: number, modelName: string) => {
  setIsLoadingWizardPreview(true)
  
  try {
    // Fetch model preview data for wizard
    const res = await fetch(`/api/packs/import/preview?url=https://civitai.com/models/${modelId}`)
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Failed to fetch model data')
    }
    
    const data = await res.json()
    
    // Transform API response to wizard format
    const versions: ModelVersion[] = (data.versions || []).map((v: any) => ({
      id: v.id,
      name: v.name,
      baseModel: v.base_model,
      downloadCount: v.download_count,
      createdAt: v.created_at,
      files: (v.files || []).map((f: any) => ({
        id: f.id || 0,
        name: f.name || 'unknown',
        sizeKB: f.sizeKB || f.size_kb,
        type: f.type,
        primary: f.primary || false,
      })),
      // Collect images from thumbnail_options for this version
      images: (data.thumbnail_options || [])
        .filter((t: any) => t.version_id === v.id)
        .map((t: any) => ({
          url: t.url,
          nsfw: t.nsfw || false,
          nsfwLevel: t.nsfw ? 4 : 1,
          width: t.width,
          height: t.height,
          type: (t.type === 'video' ? 'video' : 'image') as 'image' | 'video',
        })),
    }))
    
    // If first version has no images, assign all thumbnails to it
    if (versions.length > 0 && versions[0].images.length === 0) {
      versions[0].images = (data.thumbnail_options || []).slice(0, 20).map((t: any) => ({
        url: t.url,
        nsfw: t.nsfw || false,
        nsfwLevel: t.nsfw ? 4 : 1,
        width: t.width,
        height: t.height,
        type: (t.type === 'video' ? 'video' : 'image') as 'image' | 'video',
      }))
    }
    
    setWizardModelData({
      modelId: data.model_id,
      modelName: data.model_name || modelName,
      versions,
    })
    setShowImportWizard(true)
    
  } catch (error) {
    console.error('[BrowsePage] Failed to load wizard data:', error)
    addToast('error', 'Failed to load model data', (error as Error).message)
    
    // Offer fallback to direct import
    if (window.confirm('Failed to load wizard. Import directly with default settings?')) {
      importMutation.mutate(`https://civitai.com/models/${modelId}`)
    }
  } finally {
    setIsLoadingWizardPreview(false)
  }
}, [addToast, importMutation])

/**
 * Handles import from wizard with user-selected options.
 */
const handleWizardImport = useCallback(async (
  selectedVersionIds: number[],
  options: ImportOptions,
  thumbnailUrl?: string
): Promise<void> => {
  if (!wizardModelData) return
  
  try {
    const res = await fetch('/api/packs/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: `https://civitai.com/models/${wizardModelData.modelId}`,
        version_ids: selectedVersionIds,
        download_images: options.downloadImages,
        download_videos: options.downloadVideos,
        include_nsfw: options.includeNsfw,
        thumbnail_url: thumbnailUrl,
      }),
    })
    
    const data = await res.json()
    
    if (!res.ok || !data.success) {
      throw new Error(data.message || data.detail || 'Import failed')
    }
    
    addToast('success', data.message || `Successfully imported '${data.pack_name}'`)
    queryClient.invalidateQueries({ queryKey: ['packs'] })
    
    // Close everything
    setShowImportWizard(false)
    setWizardModelData(null)
    setSelectedModel(null)
    
  } catch (error) {
    console.error('[BrowsePage] Wizard import failed:', error)
    addToast('error', 'Import failed', (error as Error).message)
    throw error // Re-throw so wizard shows error state
  }
}, [wizardModelData, addToast, queryClient])

/**
 * Closes the import wizard.
 */
const closeImportWizard = useCallback(() => {
  setShowImportWizard(false)
  setWizardModelData(null)
}, [])


// =============================================================================
// STEP 5: REPLACE IMPORT BUTTON
// =============================================================================
// Find the import button in the model detail modal. It looks like this:
//
// <Button
//   size="sm"
//   onClick={(e) => {
//     e.stopPropagation()
//     handleImport(modelDetail.id)
//   }}
//   disabled={importMutation.isPending}
// >
//   {importMutation.isPending ? <Loader2 ... /> : <Download ... />}
// </Button>
//
// REPLACE it with this enhanced button:

/*
<Button
  size="sm"
  onClick={(e) => {
    e.stopPropagation()
    openImportWizard(modelDetail.id, modelDetail.name)
  }}
  disabled={isLoadingWizardPreview || importMutation.isPending}
  className="flex items-center gap-1"
>
  {isLoadingWizardPreview ? (
    <>
      <Loader2 className="w-4 h-4 animate-spin" />
      <span className="hidden sm:inline">Loading...</span>
    </>
  ) : importMutation.isPending ? (
    <>
      <Loader2 className="w-4 h-4 animate-spin" />
      <span className="hidden sm:inline">Importing...</span>
    </>
  ) : (
    <>
      <Sparkles className="w-4 h-4" />
      <span className="hidden sm:inline">Import...</span>
    </>
  )}
</Button>
*/


// =============================================================================
// STEP 6: ADD WIZARD MODAL TO JSX
// =============================================================================
// Add this at the END of the return statement, just BEFORE the closing </div>:

/*
      {/* Import Wizard Modal */}
      {wizardModelData && (
        <ImportWizardModal
          isOpen={showImportWizard}
          onClose={closeImportWizard}
          onImport={handleWizardImport}
          modelName={wizardModelData.modelName}
          versions={wizardModelData.versions}
          isLoading={importMutation.isPending}
        />
      )}
*/


// =============================================================================
// COMPLETE INTEGRATION EXAMPLE
// =============================================================================
// Here's a minimal complete example of how BrowsePage should look after changes:

/*
import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Sparkles, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ImportWizardModal, type ModelVersion, type ImportOptions } from '@/components/ui/ImportWizardModal'

// ... other imports ...

interface WizardModelData {
  modelId: number
  modelName: string
  versions: ModelVersion[]
}

export function BrowsePage() {
  const queryClient = useQueryClient()
  
  // ... existing state ...
  
  // Wizard state
  const [showImportWizard, setShowImportWizard] = useState(false)
  const [wizardModelData, setWizardModelData] = useState<WizardModelData | null>(null)
  const [isLoadingWizardPreview, setIsLoadingWizardPreview] = useState(false)
  
  // ... existing mutations ...
  
  // Wizard functions
  const openImportWizard = useCallback(async (modelId: number, modelName: string) => {
    setIsLoadingWizardPreview(true)
    try {
      const res = await fetch(`/api/packs/import/preview?url=https://civitai.com/models/${modelId}`)
      const data = await res.json()
      // ... transform data ...
      setWizardModelData({ modelId, modelName, versions: [] })
      setShowImportWizard(true)
    } finally {
      setIsLoadingWizardPreview(false)
    }
  }, [])
  
  const handleWizardImport = useCallback(async (
    versionIds: number[],
    options: ImportOptions,
    thumbnailUrl?: string
  ) => {
    const res = await fetch('/api/packs/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: `https://civitai.com/models/${wizardModelData?.modelId}`,
        version_ids: versionIds,
        download_images: options.downloadImages,
        download_videos: options.downloadVideos,
        include_nsfw: options.includeNsfw,
        thumbnail_url: thumbnailUrl,
      }),
    })
    // ... handle response ...
  }, [wizardModelData])
  
  return (
    <div>
      {/* ... existing content ... */}
      
      {/* Model detail modal with updated button */}
      {selectedModel && modelDetail && (
        <Button onClick={() => openImportWizard(modelDetail.id, modelDetail.name)}>
          <Sparkles className="w-4 h-4" /> Import...
        </Button>
      )}
      
      {/* Import Wizard */}
      {wizardModelData && (
        <ImportWizardModal
          isOpen={showImportWizard}
          onClose={() => setShowImportWizard(false)}
          onImport={handleWizardImport}
          modelName={wizardModelData.modelName}
          versions={wizardModelData.versions}
          isLoading={importMutation.isPending}
        />
      )}
    </div>
  )
}
*/

export {}
