/**
 * BrowsePage.tsx - PATCH FILE
 * 
 * This file shows the specific changes needed in BrowsePage.tsx
 * Apply these changes to your existing file.
 */

// =============================================================================
// CHANGE 1: Add new imports at the top of the file
// =============================================================================

// ADD these imports:
import { ModelCard } from '@/components/ui/ModelCard'
import { DetailPreviewGallery } from '@/components/ui/DetailPreviewGallery'

// REMOVE or keep (ModelCard replaces inline usage):
// import { MediaPreview } from '@/components/ui/MediaPreview'  // Still needed for detail modal if not using DetailPreviewGallery


// =============================================================================
// CHANGE 2: Replace the Results Grid section (around line 350-420)
// =============================================================================

// FIND this section and REPLACE:
/*
      <div
        className="flex flex-wrap gap-4"
        style={{ '--card-width': `${cardWidth}px` } as React.CSSProperties}
      >
        {allModels.map(model => (
          <div
            key={model.id}
            onClick={() => setSelectedModel(model.id)}
            className="group cursor-pointer"
            style={{ width: cardWidth }}
          >
            <div className="relative aspect-[3/4] rounded-2xl overflow-hidden bg-slate-dark">
              <MediaPreview
                src={model.previews[0]?.url || ''}
                type={model.previews[0]?.media_type}
                thumbnailSrc={model.previews[0]?.thumbnail_url}
                nsfw={model.nsfw}
                aspectRatio="portrait"
                className="w-full h-full"
                autoPlay={true}
                playFullOnHover={true}
              />
              ... rest of card content ...
            </div>
          </div>
        ))}
      </div>
*/

// WITH this cleaner version:
const ResultsGrid = () => (
  <div className="flex flex-wrap gap-4">
    {allModels.map(model => (
      <ModelCard
        key={model.id}
        id={model.id}
        name={model.name}
        type={model.type}
        creator={model.creator}
        nsfw={model.nsfw}
        preview={model.previews[0]}
        baseModel={model.versions[0]?.base_model}
        stats={model.stats}
        width={cardWidth}
        onClick={() => setSelectedModel(model.id)}
        onCopyLink={() => {
          navigator.clipboard.writeText(`https://civitai.com/models/${model.id}`)
          addToast('info', 'Link copied')
        }}
      />
    ))}
  </div>
)


// =============================================================================
// CHANGE 3: Replace Preview Gallery in Model Detail Modal (around line 480-510)
// =============================================================================

// FIND this section:
/*
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-text-primary">
                      Preview Images ({modelDetail.previews.length})
                    </h3>
                    <div className="grid grid-cols-6 gap-3 max-h-[360px] overflow-y-auto p-1">
                      {modelDetail.previews.map((preview, idx) => (
                        <MediaPreview
                          key={idx}
                          src={preview.url}
                          type={preview.media_type}
                          thumbnailSrc={preview.thumbnail_url}
                          nsfw={preview.nsfw}
                          aspectRatio="portrait"
                          className="cursor-pointer hover:ring-2 ring-synapse"
                          onClick={() => setFullscreenIndex(idx)}
                        />
                      ))}
                    </div>
                  </div>
*/

// REPLACE WITH:
const PreviewGallerySection = () => (
  <DetailPreviewGallery
    items={modelDetail.previews.map(p => ({
      url: p.url,
      thumbnailUrl: p.thumbnail_url,
      type: p.media_type,
      nsfw: p.nsfw,
      width: p.width,
      height: p.height,
      meta: p.meta,
    }))}
    onItemClick={setFullscreenIndex}
    maxHeight={360}
    columns={6}
  />
)


// =============================================================================
// CHANGE 4: Update FullscreenMediaViewer items mapping (around line 200)
// =============================================================================

// FIND:
/*
      <FullscreenMediaViewer
        items={modelDetail.previews.map(p => ({
          url: p.url,
          type: p.media_type,
          thumbnailUrl: p.thumbnail_url,
          nsfw: p.nsfw,
          width: p.width,
          height: p.height,
          meta: p.meta
        }))}
        ...
      />
*/

// This is fine, no changes needed - just ensure the mapping is correct


// =============================================================================
// OPTIONAL CHANGE 5: Remove CSS variable since ModelCard handles its own width
// =============================================================================

// The style={{ '--card-width': `${cardWidth}px` }} is no longer needed
// ModelCard accepts width as a prop directly


// =============================================================================
// FULL REPLACEMENT FOR RESULTS GRID SECTION
// =============================================================================

// Replace the entire grid rendering section with this:

/*
      {/* Results grid - Using ModelCard for optimized rendering *//*}
      <div className="flex flex-wrap gap-4">
        {allModels.map(model => (
          <ModelCard
            key={model.id}
            id={model.id}
            name={model.name}
            type={model.type}
            creator={model.creator}
            nsfw={model.nsfw}
            preview={model.previews[0]}
            baseModel={model.versions[0]?.base_model}
            stats={model.stats}
            width={cardWidth}
            onClick={() => setSelectedModel(model.id)}
            onCopyLink={() => {
              navigator.clipboard.writeText(`https://civitai.com/models/${model.id}`)
              addToast('info', 'Link copied')
            }}
          />
        ))}
      </div>

      {/* Loading more indicator *//*}
      {(isLoading || isFetching) && allModels.length > 0 && (
        <div className="flex justify-center py-4">
          <Loader2 className="w-6 h-6 animate-spin text-synapse" />
        </div>
      )}

      {/* Load more button *//*}
      {nextCursor && !isLoading && !isFetching && (
        <div className="flex justify-center pt-4">
          <Button
            onClick={() => {
              isLoadingMore.current = true
              setCurrentCursor(nextCursor)
            }}
            variant="outline"
          >
            Load More
          </Button>
        </div>
      )}
*/
