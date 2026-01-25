# PLAN: Blob Manifest - Persistent Metadata for Orphan Blobs

**Version:** v2.2.0
**Status:** 🚧 AKTIVNÍ
**Created:** 2026-01-25

---

## Problem Statement

When a pack is deleted, its blobs become orphans. Currently, orphan blobs lose all metadata:
- Original filename (display name)
- Asset kind (checkpoint, lora, vae, etc.)
- Origin provider (Civitai, HuggingFace)
- Model/version IDs for re-identification

This makes orphans appear as cryptic SHA256 hashes with no way to identify what they are.

---

## Solution: Write-Once Blob Manifest

### Design Principles

1. **Single Source of Truth**: `pack.lock` remains THE authoritative source for active blob references
2. **Immutable Manifests**: `.meta` files are write-once, never updated after creation
3. **Fallback Only**: Manifest data is used ONLY when blob has no pack references
4. **Minimal Footprint**: Store only essential identification data

### File Structure

```
blobs/
├── aa/
│   └── aabbcc...sha256/
│       ├── blob              # The actual file
│       └── blob.meta         # NEW: Immutable manifest (JSON)
```

### Manifest Format (blob.meta)

```json
{
  "version": 1,
  "created_at": "2026-01-25T12:00:00Z",
  "original_filename": "epicrealism_naturalSin.safetensors",
  "kind": "checkpoint",
  "origin": {
    "provider": "civitai",
    "model_id": 25694,
    "version_id": 143906,
    "file_id": 123456
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | int | ✅ | Schema version (currently 1) |
| `created_at` | string | ✅ | ISO timestamp of first adoption |
| `original_filename` | string | ✅ | Display name from first pack |
| `kind` | string | ✅ | Asset kind (checkpoint, lora, etc.) |
| `origin` | object | ❌ | Provider info if available |
| `origin.provider` | string | ❌ | "civitai" or "huggingface" |
| `origin.model_id` | int | ❌ | Civitai model ID |
| `origin.version_id` | int | ❌ | Civitai version ID |
| `origin.file_id` | int | ❌ | Civitai file ID |
| `origin.repo_id` | string | ❌ | HuggingFace repo ID |

---

## Behavior Rules

### When to Create Manifest

1. **On blob adoption** (first time blob is added to any pack)
2. **Only if manifest doesn't exist** (write-once)
3. **Never update existing manifest** (immutable)

### When to Read Manifest

1. **Building inventory** - for orphan blobs only
2. **Displaying blob info** - when no pack.lock reference exists
3. **Never for referenced blobs** - pack.lock is authoritative

### Data Priority

```
Referenced blob → pack.lock data (authoritative)
Orphan blob → blob.meta data (fallback)
No manifest → SHA256 hash only (degraded)
```

---

## Implementation Plan

### Iteration 1: Core Manifest Support ✅ IMPL+INTEG

**Files modified:**
- `src/store/models.py` - Added `BlobManifest` model
- `src/store/layout.py` - Added `blob_manifest_path()` method
- `src/store/blob_store.py` - Added manifest CRUD methods

**Implemented:**
- [x] Create `BlobManifest` Pydantic model with version, created_at, original_filename, kind, origin
- [x] Add `manifest_path()`, `manifest_exists()`, `read_manifest()`, `write_manifest()`, `delete_manifest()` to BlobStore
- [x] Write-once behavior (never overwrites existing manifest)
- [x] Atomic writes via temp file
- [x] `remove_blob()` now also deletes manifest
- [x] `list_blobs()` and `verify_all()` exclude .meta files
- [x] Unit tests: 10 new tests in `tests/store/test_blob_store.py`

### Iteration 1b: Pack Installation Integration ✅ IMPL+INTEG

**Files modified:**
- `src/store/pack_service.py` - Added `_ensure_blob_manifest()` method

**Implemented:**
- [x] `install_pack()` now creates manifests for each downloaded blob
- [x] Manifests created for pre-existing blobs too (idempotent)
- [x] Extracts metadata from pack.json (expose filename) and lock.json (provider info)

### Iteration 2: Inventory Integration ✅ IMPL+INTEG

**Files modified:**
- `src/store/inventory_service.py` - Updated `_build_item()` to read manifests

**Implemented:**
- [x] Orphan blobs (no refs) now read metadata from manifest
- [x] Populates `display_name`, `kind`, `origin` from manifest
- [x] Graceful fallback: manifest → SHA256 prefix
- [x] Integration tests: 2 new tests in `tests/store/test_inventory.py`

### Iteration 3: Migration for Existing Blobs ❌ CHYBÍ

**Files to modify:**
- `src/store/cli.py` - Add migration command
- `src/store/store.py` - Add migration logic

**Tasks:**
- [ ] Add `synapse inventory migrate-manifests` CLI command
- [ ] Scan all blobs with pack references
- [ ] Create missing manifests from pack.lock data
- [ ] Progress reporting
- [ ] Dry-run support

### Iteration 4: UI Display ❌ CHYBÍ

**Files to modify:**
- `apps/web/src/components/modules/inventory/BlobsTable.tsx`

**Tasks:**
- [ ] Verify orphan blobs show manifest data
- [ ] Add visual indicator for "manifest-sourced" vs "pack-sourced" data
- [ ] Test with orphan blobs

---

## API Changes

### InventoryItem (existing model)

No changes needed - `display_name`, `kind`, `origin` fields already exist.
Backend will populate them from manifest when blob is orphan.

---

## Migration Strategy

### For Existing Stores

1. **Automatic**: New blobs get manifests automatically
2. **Manual**: Run `synapse inventory migrate-manifests` to backfill
3. **Graceful degradation**: Orphans without manifests show SHA256

### Backwards Compatibility

- Manifests are optional - absence doesn't break anything
- Old stores work without manifests
- New features degrade gracefully

---

## Testing Strategy

### Unit Tests
- [ ] `test_blob_manifest_creation.py` - Manifest CRUD
- [ ] `test_blob_manifest_immutability.py` - Write-once behavior

### Integration Tests
- [ ] `test_inventory_with_manifests.py` - Orphan display
- [ ] `test_manifest_migration.py` - Backfill command

---

## Version Changelog

### v2.2.0 (this release)
- **NEW**: Blob manifest files (`.meta`) for metadata persistence
- **NEW**: `synapse inventory migrate-manifests` command
- **IMPROVED**: Orphan blobs now show original filename and kind

---

## Notes

- Manifests are ~200-500 bytes each (minimal overhead)
- JSON format for human readability and debugging
- Version field allows future schema evolution
- Created atomically to prevent partial writes
