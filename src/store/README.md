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
~/.synapse/store/
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

## Model Inventory

The Model Inventory provides a complete view of all blobs (model files) in the store.

### Blob Status

| Status | Description |
|--------|-------------|
| `referenced` | Used by at least one pack |
| `orphan` | Not referenced by any pack (safe to delete) |
| `missing` | Referenced but file doesn't exist |
| `backup_only` | Exists only on backup storage |

### Blob Location

| Location | Description |
|----------|-------------|
| `local_only` | Only on local disk |
| `backup_only` | Only on backup storage |
| `both` | Synced on both locations |
| `nowhere` | Missing from both (error state) |

### CLI Commands

```bash
# List all blobs with filters
synapse inventory list [--kind checkpoint|lora|vae] [--status referenced|orphan]

# Show orphan blobs only
synapse inventory orphans

# Show missing blobs
synapse inventory missing

# Cleanup orphan blobs (dry run)
synapse inventory cleanup --dry-run

# Cleanup orphan blobs (execute)
synapse inventory cleanup --execute

# Impact analysis - what depends on a blob?
synapse inventory impacts <sha256>

# Verify blob integrity
synapse inventory verify [--all]
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/store/inventory | Get full inventory |
| GET | /api/store/inventory/{sha256} | Get blob details |
| GET | /api/store/inventory/{sha256}/impact | Impact analysis |
| DELETE | /api/store/inventory/{sha256} | Delete blob |
| POST | /api/store/inventory/cleanup-orphans | Cleanup orphans |
| POST | /api/store/inventory/verify | Verify integrity |

---

## Backup Storage

External backup storage for offloading models while keeping them recoverable.

### Why Backup?

- Models are **large** (checkpoints 6-12GB, LoRAs 100-500MB)
- Local disk space is limited
- Delete locally → restore from backup when needed
- **No re-download** required!

### Configuration

```json
// In config.json
{
  "backup": {
    "enabled": true,
    "path": "/mnt/external/synapse-backup",
    "auto_backup_new": false,
    "warn_before_delete_last_copy": true
  }
}
```

### Backup Structure

Mirrors local storage exactly:
```
/mnt/external/synapse-backup/
└── .synapse/
    └── store/
        └── data/
            └── blobs/
                └── sha256/
                    └── ab/
                        └── abc123...
```

### CLI Commands

```bash
# Check backup status
synapse backup status

# Backup a specific blob (local → backup)
synapse backup blob <sha256>

# Restore a blob from backup (backup → local)
synapse backup restore <sha256>

# Delete from backup only
synapse backup delete <sha256> --force

# Configure backup path
synapse backup config --path /mnt/external/synapse-backup --enable
```

### Pack-Level Operations

Pull and push entire packs between local and backup storage:

```
Granularity:

  BLOB:   synapse backup blob/restore <sha256>    (single file)
  PACK:   synapse backup pull/push <pack>         (all pack blobs)
  ALL:    synapse backup sync                     (entire store)
```

```bash
# Preview what would be restored for a pack (dry run - default)
synapse backup pull MyPack

# Actually restore all pack blobs from backup
synapse backup pull MyPack --execute

# Preview what would be backed up for a pack
synapse backup push MyPack

# Actually backup all pack blobs
synapse backup push MyPack --execute

# Backup pack and delete local copies (free disk space)
synapse backup push MyPack --execute --cleanup
```

**Use case:** Stay on global profile but restore specific pack models when needed:
```bash
# Delete local models to save space (keeps backup)
synapse backup push MyPack --execute --cleanup

# Later: restore when needed, WITHOUT activating work profile
synapse backup pull MyPack --execute

# Models are available locally, you're still on global profile
synapse status  # → profile: global
```

### Bulk Sync Operations

```
Direction:

  to_backup:    LOCAL  ──────►  BACKUP
                (copies all local-only blobs to external drive)

  from_backup:  LOCAL  ◄──────  BACKUP
                (restores all backup-only blobs to local disk)
```

```bash
# Preview what would be backed up (dry run - default)
synapse backup sync --direction to_backup

# Actually backup all local-only blobs
synapse backup sync --direction to_backup --execute

# Preview what would be restored
synapse backup sync --direction from_backup

# Actually restore all backup-only blobs to local
synapse backup sync --direction from_backup --execute
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/store/backup/status | Get backup status |
| POST | /api/store/backup/blob/{sha256} | Backup blob |
| POST | /api/store/backup/restore/{sha256} | Restore blob |
| DELETE | /api/store/backup/{sha256} | Delete from backup |
| POST | /api/store/backup/sync | Sync operations |

### Guard Rails

Before deleting a blob, the system checks:

1. **Is it the last copy?** - Warning if only in one location
2. **Is it referenced?** - Warning if used by packs
3. **Is it active in UIs?** - Warning if currently symlinked

### Auto-Restore

When you run `synapse use MyPack` and a required blob is:
- Missing locally
- Present on backup

The system **automatically restores** it from backup before building views.

---

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
| GET | /api/store/inventory | Full inventory listing |
| GET | /api/store/backup/status | Backup storage status |

## Testing

```bash
pytest tests/store/ -v
```

## License

MIT
