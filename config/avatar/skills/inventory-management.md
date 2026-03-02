# Inventory Management

## Blob Storage

All model files are stored as content-addressed blobs:
```
~/.synapse/store/data/blobs/sha256/<full_sha256_hash>
```

Each blob has a `.manifest.json` sidecar with origin metadata (source URL, filename, kind).

## BlobStatus

| Status | Meaning |
|--------|---------|
| `referenced` | Blob is used by at least one pack |
| `orphan` | Blob exists locally but no pack references it |
| `missing` | Pack references this blob but file is not on local disk |
| `backup_only` | Blob exists only in backup storage, not locally |

## BlobLocation

| Location | Local | Backup |
|----------|-------|--------|
| `local_only` | Yes | No |
| `backup_only` | No | Yes |
| `both` | Yes | Yes |
| `nowhere` | No | No |

## Inventory Operations

- **build_inventory()**: Scan all blobs, cross-reference with packs, return InventoryItem list
- **cleanup_orphans(dry_run)**: Remove unreferenced blobs (supports dry-run)
- **get_impacts(sha256)**: Show which packs use a specific blob
- **verify_blobs()**: Check file integrity via SHA-256 hash verification
- **delete_blob(sha256, target)**: Remove from local, backup, or both

## Backup Storage

Backup is an external directory (USB, NAS, cloud mount) mirroring blob layout.

Key operations:
- **sync**: Copy all local blobs → backup (incremental, skip existing)
- **backup blob**: Copy single blob to backup
- **restore blob**: Copy single blob from backup to local
- **delete backup**: Remove blob from backup only

Safety guard: `warn_before_delete_last_copy` prevents deleting a blob's only remaining copy.

## InventorySummary

Reports: total blobs, referenced count, orphan count, missing count,
backup-only count, total bytes, bytes by asset kind, disk usage stats.
