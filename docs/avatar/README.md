# Avatar Engine - AI Assistant for Synapse

Synapse integrates [avatar-engine](https://github.com/anthropics/avatar-engine) to provide an AI assistant that understands your model library, can search Civitai, analyze workflows, and manage your store — all through natural language.

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Installation, first chat, keyboard shortcuts |
| [Configuration](configuration.md) | `avatar.yaml` reference, providers, safety modes |
| [MCP Tools Reference](mcp-tools-reference.md) | All 21 MCP tools the AI can use |
| [Skills & Avatars](skills-and-avatars.md) | Built-in skills, custom skills, avatar customization |
| [Theming](theming.md) | CSS custom properties, theme overrides |
| [Architecture](architecture.md) | System diagram, backend/frontend internals, testing |
| [Troubleshooting](troubleshooting.md) | Common issues, status states, debug commands |

## Prerequisites

- Python 3.11+
- `avatar-engine[web]` Python package
- At least one AI CLI provider: `gemini`, `claude`, or `codex`
- Synapse backend running (`uv run uvicorn src.store.api:app`)

## Quick Version Check

```bash
# Check if avatar-engine is installed and compatible
curl -s http://localhost:8000/api/avatar/status | python -m json.tool

# Expected: "state": "ready", "engine_installed": true
```

## Feature Highlights

- **Natural language queries** — "What LoRAs do I have for SDXL?" or "Show me orphan blobs"
- **21 MCP tools** — Store management, Civitai search, workflow analysis, dependency resolution
- **9 domain skills** — Built-in knowledge about model types, generation parameters, pack management
- **3 chat modes** — FAB (floating button), Compact (slide-up drawer), Fullscreen (dedicated UI)
- **Per-page suggestions** — Context-aware suggestion chips based on current page
- **Multiple providers** — Switch between Gemini, Claude, and Codex mid-conversation
- **Custom avatars** — Create your own AI persona with custom images and personality
