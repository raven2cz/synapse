# Pack Management

## Pack Lifecycle

1. **Import** — Fetch model from Civitai → create `pack.json` → download blobs
2. **Resolve** — Find missing dependency files → produce `lock.json`
3. **Install** — Symlink pack blobs into UI model directories (via profiles)
4. **Update** — Check Civitai for newer versions → plan changes → apply

## pack.json Structure

```json
{
  "metadata": {
    "name": "PackName",
    "version": "1.0.0",
    "description": "...",
    "author": "username",
    "tags": ["sdxl", "photorealistic"],
    "source_url": "https://civitai.com/models/12345"
  },
  "dependencies": [
    {
      "name": "model_file",
      "asset_type": "checkpoint|lora|vae|controlnet|...",
      "source": "civitai|huggingface|local|url",
      "filename": "model.safetensors",
      "hash": { "sha256": "..." },
      "status": "resolved|unresolved|installed|missing|pending"
    }
  ],
  "previews": [
    {
      "filename": "preview.jpg",
      "media_type": "image|video|unknown",
      "meta": { "prompt": "...", "seed": 12345 }
    }
  ],
  "parameters": { "sampler": "Euler a", "steps": 20, "cfg_scale": 7.0 },
  "model_info": { "base_model": "SDXL 1.0", "trigger_words": ["keyword"] }
}
```

## Import Options

- `download_previews`: Download preview images/videos (default: true)
- `max_previews`: Limit preview count (default: 100)
- `pack_name`: Override auto-detected name
- `selected_version_ids`: Import specific versions only
- `cover_url`: Override cover image

## Storage

- Packs stored in `~/.synapse/store/state/packs/<pack_name>/`
- Each pack has `pack.json` (metadata) and optional `lock.json` (resolved deps)
- Model files (blobs) stored separately in content-addressed blob store
- Previews stored alongside pack metadata
