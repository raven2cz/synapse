# Model Types & Architectures

## Base Model Architectures

| Architecture | Key | Resolution | Notes |
|-------------|-----|-----------|-------|
| Stable Diffusion 1.5 | `sd15` | 512×512 | Most LoRAs available, lightweight |
| Stable Diffusion 2.1 | `sd21` | 768×768 | Less popular, some quality issues |
| SDXL 1.0 | `sdxl` | 1024×1024 | Higher quality, larger models |
| Pony Diffusion | `pony` | 1024×1024 | SDXL-based, anime/stylized focus |
| Illustrious | `illustrious` | 1024×1024 | SDXL-based, illustration focus |
| Flux | `flux` | Variable | Latest architecture, very high quality |

## Compatibility Rules

- LoRAs are architecture-specific: an SD 1.5 LoRA does NOT work with SDXL
- VAEs are mostly architecture-specific but some work across architectures
- Embeddings are architecture-specific
- ControlNets are architecture-specific
- Upscalers are generally universal (work with any architecture)

## File Formats

- `.safetensors` — Preferred, safe format (no arbitrary code execution)
- `.ckpt` / `.pt` — Legacy PyTorch format (potential security risk)
- `.bin` — Binary format (HuggingFace models)

## Trigger Words

LoRAs and embeddings often require specific trigger words in the prompt to activate.
These are stored in the pack's `expose.trigger_words` field and should be included
in the generation prompt when using the model.
