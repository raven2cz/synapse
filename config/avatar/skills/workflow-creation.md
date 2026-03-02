# Workflow Creation

## Supported UI Targets

| Target | Format | Notes |
|--------|--------|-------|
| ComfyUI | JSON workflow | Node-based, most flexible |
| Forge (WebUI Forge) | A1111-compatible | SD-focused, optimized VRAM |
| A1111 (Automatic1111) | Settings-based | Classic WebUI |
| SD.Next | A1111-compatible | Extended A1111 fork |

## ComfyUI Workflow Format

ComfyUI workflows are JSON files with node definitions:

```json
{
  "nodes": [
    { "id": 1, "type": "CheckpointLoaderSimple", "inputs": { "ckpt_name": "model.safetensors" } },
    { "id": 2, "type": "CLIPTextEncode", "inputs": { "text": "prompt", "clip": ["1", 0] } },
    { "id": 3, "type": "KSampler", "inputs": { "seed": 0, "steps": 20, "cfg": 7.0 } }
  ],
  "links": [[1, 0, 3, 0], [2, 0, 3, 1]]
}
```

## Common Node Types

- **CheckpointLoaderSimple**: Load base model
- **LoraLoader**: Apply LoRA to model + CLIP
- **CLIPTextEncode**: Convert text prompt to conditioning
- **KSampler**: Main denoising sampler
- **VAEDecode**: Decode latent to pixel image
- **SaveImage**: Output final image
- **ControlNetLoader** + **ControlNetApply**: Apply ControlNet conditioning

## Workflow in Packs

Workflows are stored in `pack.json` under `workflows`:
```json
{
  "name": "basic_generation",
  "filename": "workflow.json",
  "description": "Basic txt2img workflow",
  "is_default": true
}
```

## Best Practices

- Reference model files by filename (must match dependency filenames)
- Include seed=0 for random seed in KSampler
- Set resolution matching the base model architecture
- LoRA strength typically 0.5-1.0 (lower for subtle effects)
