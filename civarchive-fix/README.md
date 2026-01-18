# CivArchive Video Support Fix

## Problem
CivArchive search returns videos as images because:
1. `CivArchiveResult` had only `preview_url: str` - missing `media_type`
2. `_fetch_civitai_model_for_civarchive` didn't use `create_model_preview()`
3. Frontend constructed previews without proper video fields

## Solution
Use the same approach as normal Civitai search - `create_model_preview()` function 
which properly detects media type (image/video) and generates thumbnail URLs.

## Files to Modify

### 1. Backend: `apps/api/src/routers/browse.py`

Find the CivArchive section (starts with comment `# CivArchive.com Search`).
Replace the entire section with the code in `civarchive_section_fix.py`.

Key changes:
- `CivArchiveResult.preview_url` → `CivArchiveResult.previews: List[ModelPreview]`
- `_fetch_civitai_model_for_civarchive` now uses `create_model_preview(img)` for each image

### 2. Frontend: `apps/web/src/components/modules/BrowsePage.tsx`

Find the CivArchive transformation (search for "Transform CivArchive results").
Replace the `transformedItems` mapping as shown in `browsepage_transform_fix.tsx`.

Key change:
- `previews: r.preview_url ? [{...}] : []` → `previews: r.previews || []`

## Testing

1. Enable Archive toggle in Browse page
2. Search for something with video previews (e.g., "LTX workflow", "AnimateDiff")
3. Verify videos play correctly on hover
4. Verify thumbnail shows before hover (for videos)

## Technical Details

The `ModelPreview` class includes:
```python
class ModelPreview(BaseModel):
    url: str
    nsfw: bool
    width: Optional[int] = None
    height: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None
    media_type: Literal['image', 'video', 'unknown'] = 'image'
    duration: Optional[float] = None
    has_audio: Optional[bool] = None
    thumbnail_url: Optional[str] = None
```

`create_model_preview(img)` automatically:
- Detects media type from URL using `detect_media_type()`
- Generates `thumbnail_url` for videos using `get_video_thumbnail_url()`
- Maps NSFW level correctly
