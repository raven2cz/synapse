# Synapse Basics

Synapse is a **Pack-First Model Manager** for AI image generation.
It manages model files (checkpoints, LoRAs, VAEs, embeddings, ControlNets, upscalers)
as organized packs with metadata, previews, generation parameters, and dependencies.

## Core Concepts

- **Pack**: A collection of model files + metadata. Can be imported from Civitai or created manually.
- **Blob**: A content-addressed model file stored by SHA-256 hash in `~/.synapse/store/data/blobs/sha256/`.
- **Dependency**: A pack can depend on model files (asset dependencies) or other packs (pack dependencies).
- **Profile**: A named configuration for a UI target (ComfyUI, Forge, A1111, SD.Next) that symlinks
  pack blobs into the UI's model directories.

## Pack Types

| Type | Description | Typical Size |
|------|-------------|-------------|
| `checkpoint` | Base model (SD 1.5, SDXL, Flux, etc.) | 2-7 GB |
| `lora` | Low-Rank Adaptation fine-tune | 10-250 MB |
| `vae` | Variational Autoencoder | 300-800 MB |
| `embedding` | Textual inversion embedding | 10-100 KB |
| `controlnet` | ControlNet model | 700 MB - 2.5 GB |
| `upscaler` | Super-resolution model | 60-200 MB |
| `other` | Miscellaneous | Varies |

## Architecture

```
~/.synapse/store/
├── state/          # Git-versioned metadata
│   ├── packs/      # Pack definitions (pack.json, lock.json, previews)
│   └── profiles/   # Profile configurations
└── data/           # Local runtime data
    ├── blobs/sha256/  # Content-addressed model files
    ├── cache/         # AI extraction cache, API cache
    └── views/         # Symlinked model directories per profile
```

## Key Operations

- **Import**: Fetch a model from Civitai → create pack → download blobs
- **Resolve**: Find and download missing dependency files
- **Update**: Check Civitai for newer versions → plan changes → apply
- **Backup**: Sync blobs to external storage for disaster recovery
- **Install**: Link pack blobs into a UI directory (ComfyUI, Forge, etc.)
