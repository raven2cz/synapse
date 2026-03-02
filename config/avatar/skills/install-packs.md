# Installing Packs

## Profiles

A **profile** is a named configuration that maps packs to a UI target directory.
Profiles define where model files are symlinked for a specific UI installation.

Structure:
```
~/.synapse/store/state/profiles/<profile_name>/
├── profile.json     # Profile config (target UI, model dirs)
└── views/           # Symlinked model directories
    ├── checkpoints/ # → UI's models/Stable-diffusion/
    ├── loras/       # → UI's models/Lora/
    ├── vae/         # → UI's models/VAE/
    └── ...
```

## UI Target Directory Layouts

### ComfyUI
```
ComfyUI/models/
├── checkpoints/    # Base models
├── loras/          # LoRA files
├── vae/            # VAE models
├── controlnet/     # ControlNet models
├── upscale_models/ # Upscaler models
├── embeddings/     # Textual inversion
└── clip/           # CLIP models
```

### Forge / A1111 / SD.Next
```
stable-diffusion-webui/models/
├── Stable-diffusion/ # Base models
├── Lora/             # LoRA files
├── VAE/              # VAE models
├── ControlNet/       # ControlNet models
├── ESRGAN/           # Upscaler models
└── embeddings/       # Textual inversion (in webui root)
```

## Install Flow

1. User creates/selects a profile targeting a UI directory
2. `install_pack(pack_name)` resolves all blob hashes
3. For each blob: create symlink from `views/<kind>/filename` → blob store
4. UI reads symlinked files as if they were local models

## Views

Views are the symlink directories that UIs read from.
A single blob can be linked into multiple profiles simultaneously.
Blobs are never copied — only symlinked from the content-addressed store.
