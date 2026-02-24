# ⬢ Synapse

**The pack-first model manager for Stable Diffusion.**

Synapse organizes your models, LoRAs, and workflows into **packs** - portable bundles that you can import, share, and switch between instantly. No more manual file management.

```
┌─────────────────────────────────────────────────────────────────────┐
│  ⬢ Synapse                                              [Packs ▾]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ Juggernaut│ │ Pony XL  │ │ Illustr. │ │ Flux Dev │               │
│  │    XL    │ │  v6.1    │ │   XL     │ │          │               │
│  │  ┌────┐  │ │  ┌────┐  │ │  ┌────┐  │ │  ┌────┐  │               │
│  │  │ ▶  │  │ │  │    │  │ │  │    │  │ │  │    │  │               │
│  │  └────┘  │ │  └────┘  │ │  └────┘  │ │  └────┘  │               │
│  │ ✓ Synced │ │ ⚠ Local  │ │ ☁ Backup│ │ ↓ Pull   │               │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │
│                                                                     │
│  [Use] activates pack → models appear in ComfyUI instantly         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| **Pack Import** | Import from Civitai or Hugging Face with one click |
| **Deduplication** | SHA256 content-addressed storage - same model, one copy |
| **Instant Switching** | `synapse use MyPack` → models ready in < 1 second |
| **Multi-UI Support** | ComfyUI, Forge, A1111, SD.Next - all from one store |
| **Backup Storage** | Offload to external drive, restore when needed |
| **Preview Gallery** | Browse pack previews with generation metadata |
| **Update Detection** | Know when Civitai has newer versions |
| **AI Assistant** | Natural language model management via [avatar-engine](docs/avatar/README.md) |

## AI Assistant

Synapse includes an AI assistant powered by [avatar-engine](https://github.com/anthropics/avatar-engine) that understands your model library:

```bash
# Install avatar-engine
uv add "avatar-engine[web]"
cd apps/web && pnpm add @avatar-engine/react @avatar-engine/core

# Ensure at least one provider CLI is installed (gemini, claude, or codex)
which gemini || which claude || which codex
```

Ask questions like "What LoRAs do I have for SDXL?", "Find orphan blobs", or "Import this model from Civitai". The AI has access to 21 MCP tools for store management, Civitai search, workflow analysis, and dependency resolution.

See [docs/avatar/](docs/avatar/README.md) for full documentation.

## Quick Start

```bash
# Install
git clone https://github.com/anthropics/synapse.git
cd synapse
./scripts/install.sh

# Configure (optional - for Civitai downloads)
export CIVITAI_API_TOKEN="your-token"

# Start
./scripts/start-all.sh
# Open http://localhost:5173
```

## How It Works

### 1. Import a Pack

```bash
synapse packs import "https://civitai.com/models/133005"
# → Creates pack with model, previews, and metadata
```

Or use the web UI: **Browse** → find model → **Import**

### 2. Install Dependencies

```bash
synapse packs install JuggernautXL
# → Downloads model files to blob store (deduplicated)
```

### 3. Activate

```bash
synapse profiles use JuggernautXL --sync
# → Creates symlinks, models appear in ComfyUI
```

### 4. Work

Your UI sees the models. Generate images. When done:

```bash
synapse profiles back --sync
# → Returns to global profile
```

## Architecture

```
~/.synapse/store/
├── state/                    ← Git-friendly, source of truth
│   ├── packs/
│   │   └── MyPack/
│   │       ├── pack.json     ← Pack definition
│   │       ├── lock.json     ← Resolved versions + hashes
│   │       └── resources/    ← Previews, workflows
│   └── profiles/
│       ├── global.json
│       └── work__MyPack.json
│
└── data/                     ← Cache, rebuildable
    ├── blobs/sha256/         ← Deduplicated model files
    │   └── ab/abc123...
    └── views/                ← Symlink trees per UI
        ├── comfyui/active/
        ├── forge/active/
        └── ...
```

**Key insight:** State is the source of truth. Data can be deleted and rebuilt.

## Backup Storage

Models are large. Synapse lets you offload them to external storage:

```bash
# Push pack to backup (keeps local copy)
synapse backup push MyPack --execute

# Push and free local space
synapse backup push MyPack --execute --cleanup

# Later: restore when needed
synapse backup pull MyPack --execute
# Models are back, still on global profile
```

Configure in Settings or CLI:
```bash
synapse backup config --path /mnt/external/synapse-backup --enable
```

## CLI Reference

```bash
# Store
synapse store init              # Initialize directories
synapse store status            # Current state overview
synapse store doctor            # Repair and verify

# Packs
synapse packs list              # List all packs
synapse packs import <url>      # Import from Civitai/HF
synapse packs install <name>    # Download dependencies
synapse packs resolve <name>    # Resolve without download

# Profiles
synapse profiles use <pack>     # Activate work profile
synapse profiles back           # Return to previous
synapse profiles reset          # Back to global

# Backup
synapse backup status           # Show backup state
synapse backup push <pack>      # Backup pack blobs
synapse backup pull <pack>      # Restore pack blobs
synapse backup sync             # Sync all blobs

# Updates
synapse updates plan            # Check for updates
synapse updates apply <pack>    # Apply update

# Inventory
synapse inventory list          # List all blobs
synapse inventory orphans       # Find unused blobs
synapse inventory cleanup       # Remove orphans
```

## Web UI Pages

| Page | Purpose |
|------|---------|
| **Packs** | Browse packs, see status, quick actions |
| **Pack Detail** | Preview gallery, dependencies, storage actions |
| **Browse** | Search Civitai, import with version selection |
| **Profiles** | Runtime stack, UI attachment, shadowed files |
| **Inventory** | Blob management, disk usage, cleanup |
| **Settings** | Paths, tokens, backup configuration |

## Supported UIs

| UI | Default Path | Status |
|----|--------------|--------|
| ComfyUI | `~/ComfyUI` | Full support |
| Forge | `~/stable-diffusion-webui-forge` | Full support |
| A1111 | `~/stable-diffusion-webui` | Full support |
| SD.Next | `~/sdnext` | Full support |

Override paths in `~/.synapse/store/state/config.json` or Settings page.

## Requirements

- Python 3.11+
- Node.js 18+
- Git
- Recommended: [uv](https://github.com/astral-sh/uv) for fast Python dependency management

## Development

```bash
# Full verification (run before commits)
./scripts/verify.sh

# Quick check (skips slow tests)
./scripts/verify.sh --quick

# Backend only
./scripts/verify.sh --backend

# Run specific tests
uv run pytest tests/store/ -v
```

## Documentation

- [AI Assistant](docs/avatar/README.md) - Avatar-engine integration guide
- [Store Architecture](src/store/README.md) - Technical deep-dive
- [CLAUDE.md](CLAUDE.md) - Project conventions and patterns

## Roadmap

- [ ] Workflow-first pack authoring
- [ ] More providers (local folders, custom URLs, pictures metadata)
- [ ] Pack sharing/export
- [ ] Conflict resolution UI
- [ ] Model comparison tools

## License

MIT License. See [LICENSE](LICENSE).

---

<p align="center">
  <b>⬢ Synapse</b> - Stop managing files. Start creating.
</p>
