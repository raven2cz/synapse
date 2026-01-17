# Synapse Store v2

Content-addressable storage with multi-UI support for ComfyUI asset management.

## Features

- **Blob Store** - SHA256 deduplication with atomic downloads
- **Multi-UI Support** - ComfyUI, Forge, A1111, SD.Next
- **Profile System** - `use/back` workflow with work profiles
- **Update Detection** - Automatic update checking with ambiguous selection handling
- **View Builder** - Symlink trees for each UI with last_wins conflict resolution

## Installation

```bash
pip install synapse-store
```

## Quick Start

### Python API

```python
from src.store import Store

store = Store()
store.init()

# Import from Civitai
pack = store.import_civitai("https://civitai.com/models/12345")

# Install blobs
store.install(pack.name)

# Activate work profile
result = store.use(pack.name)  # → work__<pack>

# Go back to global
store.back()

# Check status
status = store.status()
```

### CLI

```bash
# Initialize store
synapse store init

# Import from Civitai
synapse import https://civitai.com/models/12345

# List packs
synapse list

# Use a pack (activate work profile)
synapse use MyPack --sync

# Go back
synapse back

# Check status
synapse status --json

# Check for updates
synapse check-updates

# Update a pack
synapse update MyPack --sync

# Run diagnostics
synapse doctor --verify-blobs
```

### FastAPI

```python
from fastapi import FastAPI
from src.store.api import create_store_routers

app = FastAPI()
for router in create_store_routers():
    app.include_router(router, prefix="/api")
```

## Storage Layout

```
~/.synapse/
├── state/                          # Git-versioned
│   ├── config.json                 # Store configuration
│   ├── ui_sets.json                # UI set definitions
│   ├── packs/
│   │   └── <Pack>/
│   │       ├── pack.json           # Pack definition
│   │       ├── lock.json           # Resolved dependencies
│   │       └── resources/previews/ # Preview images
│   └── profiles/
│       ├── global/profile.json
│       └── work__<Pack>/profile.json
└── data/                           # Local, rebuildable
    ├── blobs/sha256/<2>/<sha256>   # Deduplicated model files
    ├── views/<ui>/
    │   ├── profiles/<profile>/     # Symlink trees
    │   └── active -> profiles/...  # Active profile symlink
    ├── tmp/
    └── runtime.json                # UI stack state
```

## Architecture

| Module | Description |
|--------|-------------|
| `Store` | Main facade - high-level API |
| `StoreLayout` | Path management, JSON I/O, locking |
| `BlobStore` | Content-addressable storage |
| `ViewBuilder` | Symlink tree builder |
| `PackService` | Pack CRUD, Civitai import |
| `ProfileService` | Profile management, use/back |
| `UpdateService` | Update detection and application |

## Key Concepts

### Profiles

- **global** - Default profile containing all packs
- **work__\<Pack\>** - Work profile = global + pack at end (last wins)

### Last Wins

When multiple packs expose the same filename, the pack appearing later in the profile wins.
Shadowed entries are tracked and reported.

### Runtime Stack (The Holy Trinity)

The system maintains consistency across three synchronized components:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         THE HOLY TRINITY                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. data/runtime.json           Per-UI stacks                           │
│     {                                                                   │
│       "ui": {                                                           │
│         "comfyui": {"stack": ["global", "work__MyPack"]},               │
│         "forge":   {"stack": ["global"]}                                │
│       }                                                                 │
│     }                                                                   │
│                                                                         │
│  2. data/views/<ui>/profiles/<profile>/                                 │
│     Symlink trees pointing to blobs                                     │
│     └── models/loras/my_model.safetensors → ../../blobs/sha256/ab/...   │
│                                                                         │
│  3. data/views/<ui>/active                                              │
│     Symlink to current profile directory                                │
│     active → profiles/work__MyPack                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Invariants:**
- `active` symlink MUST point to `profiles/{top-of-stack}`
- Runtime stack and view state MUST be consistent
- If any component gets out of sync, `doctor --rebuild-views` can fix it

### use/back Commands

```
use PackA:
  1. Create work__PackA profile (global + PackA at end)
  2. Build view symlinks for work__PackA
  3. Update active symlink → profiles/work__PackA
  4. Push "work__PackA" onto runtime stack

back:
  1. Pop stack → get previous profile
  2. Update active symlink → profiles/{previous}
  3. (optionally rebuild views)
```

### Updates

Packs with `follow_latest` policy can be updated:
1. `check-updates` - Plan what would change
2. `update --dry-run` - Preview changes
3. `update --sync` - Apply and rebuild views

Ambiguous updates (multiple file candidates) require explicit selection via `--choose`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/store/init | Initialize store |
| GET | /api/store/status | Get current status |
| POST | /api/store/doctor | Run diagnostics |
| GET | /api/packs/ | List all packs |
| POST | /api/packs/import | Import from Civitai |
| POST | /api/packs/{name}/install | Install blobs |
| POST | /api/profiles/use | Activate work profile |
| POST | /api/profiles/back | Go back to previous |
| GET | /api/updates/plan | Get update plan |
| POST | /api/updates/apply | Apply update |
| GET | /api/search | Search packs |

## Testing

```bash
pytest tests/store/ -v
```

## License

MIT
