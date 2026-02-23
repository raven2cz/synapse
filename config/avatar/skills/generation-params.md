# Generation Parameters

## Core Parameters

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| `cfg_scale` | 1-30 | 7.0 | Classifier-Free Guidance. Higher = stricter prompt adherence. 5-8 typical for SD 1.5, 3-7 for SDXL |
| `steps` | 1-150 | 20-30 | Denoising steps. More = better quality but slower. Diminishing returns above 40 |
| `sampler` | — | Euler a | Sampling algorithm. Popular: Euler a, DPM++ 2M Karras, DPM++ SDE Karras |
| `scheduler` | — | Normal | Noise schedule. Options: Normal, Karras, Exponential, SGM Uniform |
| `width` / `height` | 64-2048 | 512/1024 | Output resolution. Must match architecture (512 for SD1.5, 1024 for SDXL) |
| `clip_skip` | 1-12 | 1-2 | Skip last N CLIP layers. 2 is common for anime styles |
| `denoise` | 0-1 | 0.7 | Denoising strength for img2img. Lower = closer to input image |

## Hi-Res Fix Parameters

| Parameter | Description |
|-----------|-------------|
| `hires_fix` | Enable two-pass generation for higher resolution |
| `hires_scale` | Upscale factor (1.5-2.0 typical) |
| `hires_denoise` | Denoising strength for hi-res pass (0.3-0.7) |
| `hires_upscaler` | Upscaler model to use (Latent, ESRGAN, etc.) |
| `hires_steps` | Additional steps for hi-res pass |

## Best Practices

- **SD 1.5**: 512×512, CFG 7, 20-30 steps, Euler a or DPM++ 2M Karras
- **SDXL**: 1024×1024, CFG 5-7, 25-40 steps, DPM++ 2M SDE Karras
- **Flux**: Variable resolution, CFG 1-4, 20-30 steps (model-specific)
- **Anime styles**: Often use clip_skip=2, higher CFG (8-12)
- **Photorealistic**: Lower CFG (3-7), more steps (30-50)
