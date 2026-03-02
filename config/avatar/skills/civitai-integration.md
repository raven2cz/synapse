# Civitai & HuggingFace Integration

## Civitai API

Base URL: `https://civitai.com/api/v1`

### Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /models/{id}` | Fetch model details + all versions |
| `GET /model-versions/{id}` | Fetch specific version |
| `GET /model-versions/by-hash/{hash}` | Find model by file hash |
| `GET /models?query=...` | Search models |

### Model Response Structure

```
model.modelVersions[].files[] → { id, name, downloadUrl, sizeKB, hashes: { SHA256, AutoV2 } }
model.modelVersions[].images[] → { url, width, height, nsfw, nsfwLevel, meta }
model.modelVersions[].trainedWords[] → trigger words for LoRA/embeddings
```

### Download URL Pattern

```
https://civitai.com/api/download/models/{version_id}?type=Model&format=SafeTensor
```

Auth: `Authorization: Bearer <api_key>` header (preferred). Query param `?token=<api_key>` also works but is discouraged (token may leak via logs/referrers).

### Type Mapping

| Civitai Type | Synapse AssetKind |
|-------------|-------------------|
| Checkpoint | `checkpoint` |
| LORA | `lora` |
| TextualInversion | `embedding` |
| VAE | `vae` |
| ControlNet | `controlnet` |
| Upscaler | `upscaler` |

## Civitai CDN URL Patterns

Image/video URLs use transform parameters:
```
https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/<uuid>/width=450/<filename>
```

Transform params: `anim=true|false`, `transcode=true`, `width=N`, `quality=N`

- **Thumbnail** (static): `anim=false,transcode=true,width=450`
- **Video** (playable): `anim=true,transcode=true,width=450` + `.mp4` extension
- Civitai returns videos with `.jpeg` extension — must transform to `.mp4`

## HuggingFace Integration

Download URL pattern:
```
https://huggingface.co/{repo_id}/resolve/{revision}/{subfolder/}{filename}
```

Used for models not available on Civitai (e.g., official CLIP models, some VAEs).

## Import Parameters

- `url`: Civitai model URL (e.g., `https://civitai.com/models/12345`)
- `selected_version_ids`: Import only specific versions
- `download_previews`: Download preview images/videos
- `cover_url`: Override cover image selection
