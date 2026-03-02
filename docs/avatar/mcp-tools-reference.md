# MCP Tools Reference

The AI assistant has access to 21 MCP (Model Context Protocol) tools organized into 4 groups. These tools let the AI read and manage your Synapse store, search Civitai, analyze ComfyUI workflows, and resolve dependencies.

## Overview

| Group | Tools | Description |
|-------|-------|-------------|
| [Store](#store-tools-10) | 10 | Read/manage packs, inventory, backup, storage stats |
| [Civitai](#civitai-tools-4) | 4 | Search, analyze, compare, import models from Civitai |
| [Workflow](#workflow-tools-4) | 4 | Scan ComfyUI workflows, check asset availability |
| [Dependencies](#dependency-resolution-tools-3) | 3 | Resolve model sources, find by hash, suggest downloads |

All tools are registered via the `synapse-store` FastMCP server and are available automatically when the AI assistant is enabled.

---

## Store Tools (10)

### `list_packs`

List all packs in your store with optional filtering.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name_filter` | string | `""` | Filter packs by name (substring match) |
| `limit` | int | `20` | Maximum number of results |

**Example prompts:**
- "List my packs"
- "Show me all SDXL packs"
- "What LoRAs do I have?"

---

### `get_pack_details`

Get full details for a specific pack including dependencies, parameters, and metadata.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pack_name` | string | Yes | Exact pack name |

**Returns:** Type, base model, version, author, description, source URL, trigger words, tags, and all dependencies (filename + kind).

**Example prompts:**
- "Tell me about JuggernautXL"
- "What files does the Pony pack include?"

---

### `search_packs`

Search packs by name or metadata content.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |

**Example prompts:**
- "Search for anime models"
- "Find packs with trigger word 'masterpiece'"

---

### `get_pack_parameters`

Get recommended generation parameters for a pack.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pack_name` | string | Yes | Exact pack name |

**Returns:** Sampler, scheduler, steps, CFG scale, clip skip, denoise, dimensions, hi-res fix settings.

**Example prompts:**
- "What settings should I use for JuggernautXL?"
- "Show me the generation parameters for this pack"

---

### `get_inventory_summary`

Get a high-level overview of your blob inventory.

**Returns:** Total/referenced/orphan/missing/backup-only blob counts, disk usage, bytes by asset kind.

**Example prompts:**
- "How much disk space am I using?"
- "Give me an inventory overview"
- "How many orphan blobs do I have?"

---

### `find_orphan_blobs`

Find blobs that exist on disk but are not referenced by any pack.

**Returns:** List of orphan blobs with display name, kind, size, and SHA256 prefix.

**Example prompts:**
- "Find orphan blobs"
- "What files can I safely clean up?"

---

### `find_missing_blobs`

Find blobs referenced by packs but not present on local disk.

**Returns:** List of missing blobs with display name, kind, which packs use them, and SHA256 prefix.

**Example prompts:**
- "Are any of my pack files missing?"
- "Which blobs need to be downloaded?"

---

### `get_backup_status`

Check the status of your backup storage.

**Returns:** Enabled state, connection status, path, blob count, size, free space, last sync time, auto-backup and warn-on-last-copy flags.

**Example prompts:**
- "Is my backup connected?"
- "How much backup space is used?"

---

### `check_pack_updates`

Check if Civitai has newer versions for one or all packs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pack_name` | string | `""` | Check specific pack (empty = check all) |

**Returns:** Available updates with old/new version details and dependency changes.

**Example prompts:**
- "Check for updates"
- "Is there a newer version of JuggernautXL?"

---

### `get_storage_stats`

Get detailed storage statistics.

**Returns:** Total blobs/size, disk usage percentage, per-kind breakdown, top 5 largest packs.

**Example prompts:**
- "Show storage breakdown by type"
- "What are my largest packs?"

---

## Civitai Tools (4)

### `search_civitai`

Search models on Civitai.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | Required | Search query |
| `types` | string | `""` | Comma-separated types: `LORA`, `Checkpoint`, `TextualInversion`, etc. |
| `sort` | string | `"Most Downloaded"` | Sort order: `Most Downloaded`, `Newest`, `Highest Rated` |
| `limit` | int | `10` | Maximum results |

**Example prompts:**
- "Search Civitai for SDXL checkpoints"
- "Find the most popular anime LoRAs"
- "Search for 'realistic' on Civitai, show newest first"

---

### `analyze_civitai_model`

Get full analysis of a Civitai model by URL.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | Civitai model URL |

**Returns:** Name, type, creator, tags, description, all versions with file details and trigger words.

**Example prompts:**
- "Analyze this model: https://civitai.com/models/133005"
- "What versions does this Civitai model have?"

---

### `compare_model_versions`

Side-by-side comparison of all versions of a Civitai model.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | Civitai model URL |

**Returns:** Comparison table (max 5 versions) with base model, files, total size, trigger word count, and publish date.

**Example prompts:**
- "Compare versions of this model"
- "Which version should I download?"

---

### `import_civitai_model`

Import a model from Civitai into your store.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | Required | Civitai model URL |
| `pack_name` | string | `""` | Custom pack name (auto-generated if empty) |
| `download_previews` | bool | `true` | Download preview images |

> **Write operation**: This tool creates a pack directory and may download large files (potentially several GB). In `safe` mode, the AI will refuse this operation. In `ask` mode, you'll see a confirmation dialog first.

**Example prompts:**
- "Import this model: https://civitai.com/models/133005"
- "Download JuggernautXL from Civitai"

---

## Workflow Tools (4)

### `scan_workflow`

Analyze a ComfyUI workflow JSON string.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workflow_json` | string | Yes | Complete workflow JSON content |

**Returns:** Node count, asset count, custom node types, model dependencies with kind and node type.

**Example prompts:**
- "Scan this workflow: {paste JSON}"
- "What models does this workflow need?"

---

### `scan_workflow_file`

Analyze a ComfyUI workflow from a `.json` file on disk.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Path to `.json` workflow file |

**Returns:** Same structure as `scan_workflow`.

**Example prompts:**
- "Scan the workflow at ~/workflows/my-workflow.json"

---

### `check_workflow_availability`

Cross-reference workflow assets against your local inventory.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workflow_json` | string | Yes | Complete workflow JSON content |

**Returns:** List of available and missing assets with their kind.

**Example prompts:**
- "Do I have all the models for this workflow?"
- "Check which assets I'm missing for this workflow"

---

### `list_custom_nodes`

List custom ComfyUI node packages required by a workflow.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workflow_json` | string | Yes | Complete workflow JSON content |

**Returns:** Required packages with git URL and pip requirements. Shows unresolved node types.

**Example prompts:**
- "What custom nodes does this workflow need?"
- "List the ComfyUI extensions for this workflow"

---

## Dependency Resolution Tools (3)

### `resolve_workflow_dependencies`

Full dependency resolution: models + custom nodes for a workflow.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workflow_json` | string | Yes | Complete workflow JSON content |

**Returns:** Model assets with source (Civitai/HuggingFace/local) and custom node packages with git URLs.

**Example prompts:**
- "Resolve all dependencies for this workflow"
- "Where can I download the models this workflow needs?"

---

### `find_model_by_hash`

Find a model on Civitai by its file hash.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `hash_value` | string | Yes | SHA256 or AutoV2 hash |

**Returns:** Version name, version ID, model ID, base model, model name, file list.

**Example prompts:**
- "Find the model with hash abc123..."
- "What model does this hash belong to?"

---

### `suggest_asset_sources`

Suggest download sources for model files by filename.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `asset_names` | string | Yes | Comma-separated filenames |

**Returns:** For each file, the likely source (HuggingFace repo/file for known models, or "not found").

**Example prompts:**
- "Where can I download v1-5-pruned-emaonly.safetensors?"
- "Find download links for these models: model1.safetensors, model2.safetensors"

---

## Running as Standalone MCP Server

The synapse-store MCP server can also run independently (e.g., for use with other MCP clients):

```bash
python -m src.avatar.mcp
```

This starts a stdio-based MCP server that any MCP-compatible client can connect to.

## See Also

- [Getting Started](getting-started.md) — Setup and first chat
- [Configuration](configuration.md) — MCP server configuration
- [Skills & Avatars](skills-and-avatars.md) — Customize the AI's knowledge
