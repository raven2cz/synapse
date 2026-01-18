// ============================================================================
// BrowsePage.tsx - CivArchive transformation fix
// ============================================================================
//
// INSTRUCTIONS: Find the CivArchive transformation section in BrowsePage.tsx
// (inside the useQuery queryFn, after "// Transform CivArchive results to CivitaiModel format")
// and replace the transformedItems mapping with this code.
//
// Key change: Use r.previews directly instead of constructing from r.preview_url
// This preserves media_type, thumbnail_url, and other fields for proper video support.
// ============================================================================

// OLD CODE (replace this):
/*
          // Transform CivArchive results to CivitaiModel format
          const transformedItems = (civarchiveData.results || []).map((r: any) => ({
            id: r.model_id,
            name: r.model_name,
            type: r.model_type || 'Unknown',
            nsfw: r.nsfw || false,
            tags: [],
            creator: r.creator,
            stats: {
              downloadCount: r.download_count,
              rating: r.rating,
            },
            versions: [{
              id: r.version_id,
              name: r.version_name || 'Default',
              base_model: r.base_model,
              download_url: r.download_url,
              file_size: r.file_size,
              trained_words: [],
              files: r.file_name ? [{
                id: 0,
                name: r.file_name,
                size_kb: r.file_size ? r.file_size / 1024 : undefined,
                download_url: r.download_url,
              }] : [],
            }],
            // Include preview from CivArchive response
            previews: r.preview_url ? [{
              url: r.preview_url,
              nsfw: r.nsfw || false,
            }] : [],
          }))
*/

// NEW CODE (use this instead):
          // Transform CivArchive results to CivitaiModel format
          const transformedItems = (civarchiveData.results || []).map((r: any) => ({
            id: r.model_id,
            name: r.model_name,
            type: r.model_type || 'Unknown',
            nsfw: r.nsfw || false,
            tags: [],
            creator: r.creator,
            stats: {
              downloadCount: r.download_count,
              rating: r.rating,
            },
            versions: [{
              id: r.version_id,
              name: r.version_name || 'Default',
              base_model: r.base_model,
              download_url: r.download_url,
              file_size: r.file_size,
              trained_words: [],
              files: r.file_name ? [{
                id: 0,
                name: r.file_name,
                size_kb: r.file_size ? r.file_size / 1024 : undefined,
                download_url: r.download_url,
              }] : [],
            }],
            // CHANGED: Use previews array directly from backend
            // This preserves media_type, thumbnail_url, and other fields for video support
            previews: r.previews || [],
          }))
