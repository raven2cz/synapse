# Dependency Resolution

## AssetDependency Model

Each pack dependency has:
- **asset_type**: `checkpoint`, `lora`, `vae`, `controlnet`, `upscaler`, `clip`, `text_encoder`, `diffusion_model`, `embedding`, `custom_node`, `workflow`, `base_model`, `unknown`
- **source**: Where to fetch — `civitai`, `huggingface`, `local`, `url`, `unresolved`, `unknown`
- **status**: `resolved` (hash known), `unresolved`, `installed` (on disk), `missing`, `pending`

## Source Types

### Civitai Source
```
civitai: { model_id, model_version_id, file_id, model_name, version_name }
```
Downloads via `https://civitai.com/api/download/models/{version_id}?type=Model&format=SafeTensor`

### HuggingFace Source
```
huggingface: { repo_id, filename, revision, subfolder }
```
Downloads via `https://huggingface.co/{repo_id}/resolve/{revision}/{filename}`

### Local Source
File already present on disk, referenced by `local_path`.

## Resolution Process

1. Pack is imported with unresolved dependencies
2. `resolve_pack()` iterates each dependency
3. For each: check local blob store by hash → check Civitai API → check HuggingFace
4. Resolved deps get download URL + verified hash → written to `lock.json`
5. `install_pack()` downloads resolved blobs and creates symlinks

## Compatibility

- Dependencies carry `base_model_hint` (e.g., "SDXL 1.0", "SD 1.5")
- LoRAs, embeddings, ControlNets are architecture-specific
- Upscalers are generally universal
- Mismatched base models produce warnings, not errors
