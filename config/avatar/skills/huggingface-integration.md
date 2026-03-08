# HuggingFace Integration

## HuggingFace Hub API

Base URL: `https://huggingface.co/api`

### Search Models

```
GET /api/models?search=<query>&limit=10
```

Returns list of repos. Each repo has: `id` (repo_id), `modelId`, `tags`, `pipeline_tag`, `library_name`, `downloads`, `lastModified`.

### List Files in Repo

```
GET /api/models/<repo_id>/tree/<revision>
```

Returns files and folders. Each entry: `type` (file/directory), `path`, `size`, `lfs` (if LFS-managed).

### Download URL Pattern

```
https://huggingface.co/<repo_id>/resolve/<revision>/[subfolder/]<filename>
```

Default revision: `main`.

## HuggingFace Source Identifier

```
huggingface: { repo_id, filename, revision, subfolder }
```

- `repo_id`: "owner/repo" (e.g., "stabilityai/stable-diffusion-xl-base-1.0")
- `filename`: file path within repo (e.g., "sd_xl_base_1.0.safetensors")
- `revision`: branch or tag (default "main")
- `subfolder`: nested folder path (optional)

## Repository Types

### Single-file repos
Contain one or a few `.safetensors`/`.ckpt` files directly in root.
Example: `stabilityai/stable-diffusion-xl-base-1.0` → `sd_xl_base_1.0.safetensors`

### Diffusers-format repos
Structured as a diffusers pipeline with subdirectories:
```
model_index.json
unet/diffusion_pytorch_model.safetensors
vae/diffusion_pytorch_model.safetensors
text_encoder/model.safetensors
```
These are NOT single-file downloads — they require the entire repo structure.

### Single-file in subfolder
Some repos have single files nested in subdirectories:
```
checkpoints/model_v2.safetensors
```

## File Format Detection

| Extension | Default Type | Notes |
|-----------|-------------|-------|
| `.safetensors` | checkpoint | Preferred format, safe |
| `.ckpt` | checkpoint | Legacy PyTorch |
| `.bin` | varies | HuggingFace native format |
| `*lora*` | lora | Filename pattern |
| `*vae*` | vae | Filename pattern |
| `*controlnet*` | controlnet | Filename pattern |
| `*upscale*` | upscaler | Filename pattern |

## Hash Verification

HuggingFace uses Git LFS for large files. The SHA256 hash is stored in the LFS pointer,
NOT in the regular file metadata. To get the hash:

1. Check file entry in tree listing for `lfs.sha256` field
2. Or download the LFS pointer and parse the SHA256 from it

**Important:** HF hashes may differ from Civitai hashes for the same model
if the files were uploaded separately (not copied).

## Common Model Repos

| Model | Repo ID | Key File |
|-------|---------|----------|
| SDXL Base | `stabilityai/stable-diffusion-xl-base-1.0` | `sd_xl_base_1.0.safetensors` |
| SDXL VAE | `stabilityai/sdxl-vae` | `sdxl_vae.safetensors` |
| SD 1.5 | `stable-diffusion-v1-5/stable-diffusion-v1-5` | `v1-5-pruned-emaonly.safetensors` |
| FLUX.1 dev | `black-forest-labs/FLUX.1-dev` | `flux1-dev.safetensors` |
| FLUX.1 schnell | `black-forest-labs/FLUX.1-schnell` | `flux1-schnell.safetensors` |

## Auth

Gated models require `Authorization: Bearer <HF_TOKEN>` header.
Token sourced from `HF_TOKEN` environment variable.

## Eligibility per Asset Kind

| AssetKind | Search HF? | Why |
|-----------|-----------|-----|
| checkpoint | Yes | Many base checkpoints hosted on HF |
| vae | Yes | Common VAEs (kl-f8, mse) on HF |
| controlnet | Yes | ControlNet repos on HF |
| lora | No | Minimal HF LoRA ecosystem |
| embedding | No | Primarily on Civitai |
| upscaler | Limited | Some upscalers on HF |
