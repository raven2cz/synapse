# ⬢ Synapse (Store v2)

**⬢ Synapse** is a **pack-first model manager** for generative UIs like **ComfyUI, Forge, Automatic1111 (A1111), and SD.Next**.

It helps you:

- import packs from **Civitai** and **Hugging Face**
- keep **pack.json as the source of truth**
- deduplicate downloads via a **content-addressed blob store (SHA256)**
- switch between packs instantly via **profiles** and **views**
- detect and apply **updates** (for providers that support “follow latest”)
- optionally index everything with **SQLite FTS** for fast search (DB is optional and rebuildable)

This repository ships:

- a **web UI** (Vite + React) for browsing packs, profiles, updates, and UI attachment
- a **FastAPI backend** used by the UI
- a **CLI** (`synapse`) for scripting and power use


## Why Store v2

Store v2 splits storage into two parts:

- **state/**: versionable, reproducible, rebuildable
- **data/**: local machine cache and blobs, safe to delete and rebuild

This makes the system **robust**: if your DB breaks or you delete local caches, you can rebuild views and indexes from state.


## Core concepts

### Packs
A **pack** is a portable bundle defined by `state/packs/<PackName>/pack.json`.

It typically contains:

- preview images and their metadata (prompt, sampler, seed, etc.)
- dependencies (models, LoRAs, UNets, VAEs, upscalers, embeddings, etc.)
- optional workflows and related resources

### Lock
`state/packs/<PackName>/lock.json` stores **resolved, pinned** versions (exact files, hashes, download URLs).

### Blob store
Downloaded files live under `data/blobs/` as **deduplicated SHA256 blobs**. Multiple packs can reference the same file without duplicating storage.

### Profiles and “last wins”
A **profile** is a stack of packs (and optional overrides). The effective view is built by applying packs in order:

- earlier packs provide defaults
- later packs override conflicts (**last wins**)

Synapse also reports **shadowed** files (things overridden by later packs).

### Views
A **view** is a filesystem tree (usually symlinks) that mirrors how a target UI expects models on disk.

Example: `views/comfyui/active/models/loras/...`

### Attach and detach
Synapse can attach views to UIs by:

- creating a `synapse` link under the UI’s model folders, and/or
- patching a UI config file (for ComfyUI: `extra_model_paths.yaml`) with a **backup + restore** flow

Attachment is managed from the **Profiles** tab in the web UI (and via API/CLI).


## Supported UIs and default install paths

By default, Synapse expects these folders in your home directory:

- **ComfyUI**: `~/ComfyUI`
- **Forge**: `~/stable-diffusion-webui-forge`
- **A1111**: `~/stable-diffusion-webui`
- **SD.Next**: `~/sdnext`

You can override these in `~/.synapse/config.json`.


## Providers

- **Civitai**: import, previews, rich preview metadata, downloads, updates (where applicable)
- **Hugging Face**: download supported (follow-latest policies may vary by provider and may expand over time)

Planned: more providers and workflow-first pack authoring.


## Install

### Requirements

- **Python 3.11+**
- **Node.js 18+**
- Git
- Recommended: **uv** (fast Python dependency manager)

### Quick install (recommended)

From repo root:

```bash
./scripts/install.sh
```

This will:
- create or sync the Python environment using `uv`
- install web dependencies (`npm install`)

If you do not use `uv`, you can still set up a normal venv and install dependencies manually, but the scripts assume `uv`.


## Configure

Synapse stores config at:

- `~/.synapse/store/config.json`

Tokens are read from config or environment:

- `CIVITAI_API_TOKEN` (or `CIVITAI_API_KEY`)
- `HF_TOKEN` (or `HUGGINGFACE_TOKEN`)


## Run (dev)

### Start backend + frontend together

```bash
./scripts/start-all.sh
```

- Web UI: `http://localhost:5173`
- API: `http://localhost:8000`

### Run backend only

```bash
uv run uvicorn apps.api.src.main:app --reload --host 0.0.0.0 --port 8000
```

### Run web only

```bash
cd apps/web
npm run dev
```


## CLI

The CLI entrypoint is `synapse`.

Examples:

```bash
# Initialize store directories
synapse store init

# Import a pack from Civitai
synapse packs import "https://civitai.com/models/12345"

# Inspect packs and status
synapse packs list
synapse store status

# Resolve and install dependencies for a pack
synapse packs resolve MyPack
synapse packs install MyPack

# Activate pack as a work profile for a UI set
synapse profiles use MyPack --ui-set local --sync

# Go back (pop profile stack)
synapse profiles back --ui-set local --sync

# Updates
synapse updates plan
synapse updates apply MyPack --sync

# Repair, rebuild, verify
synapse store doctor --rebuild-views --verify-blobs
```

Run `synapse --help` (and subcommand `--help`) for the full command set.


## Web UI

Key pages:

- **Packs**: browse local packs, import, resolve, install, update status
- **Pack detail**: preview gallery, rich generation metadata panel
- **Profiles**:
  - active runtime stack per UI
  - attach/detach status per UI
  - shadowed file warnings
  - quick actions: “Back to global”, sync views
- **Settings**: store root and UI roots, init and doctor actions


## Store layout

Default store root:

- `~/.synapse/store`

Simplified layout:

```text
~/.synapse/store/
  state/
    config.json
    packs/
      MyPack/
        pack.json
        lock.json
        resources/
          previews/
            <preview-id>.jpg
            <preview-id>.json   # rich meta for that preview
        workflows/
          ...
    profiles/
      global.json
      work__MyPack.json
  data/
    blobs/
      sha256/
        ab/
          abcd...<sha256>        # actual file contents
    views/
      comfyui/
        active/                  # generated view for active profile stack
      forge/
      a1111/
      sdnext/
    db/
      fts.sqlite                 # optional, rebuildable
    tmp/
```

Notes:

- **State is the source of truth**. Data is a cache and can be rebuilt.
- The **DB is optional**. If deleted, Synapse falls back to scanning state and can rebuild indexes.
- Views can always be rebuilt via `synapse store doctor --rebuild-views`.


## Testing and verification

### Fast verification gate

```bash
./scripts/verify.sh
```

Typical checks:
- Python tests
- web build
- basic hygiene checks (for example, node_modules rules)

### Python tests

```bash
uv run pytest
```

### Web build

```bash
cd apps/web
npm run build
```


## Roadmap

- richer workflow-first packs
- more providers and update policies
- improved model inventory view (sizes, pack usage, safe cleanup planning)
- stronger multi-UI mapping for niche model kinds


## License

MIT License. See `LICENSE`.
