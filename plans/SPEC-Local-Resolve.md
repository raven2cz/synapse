# SPEC: Local Resolve — Import local files as resolved dependencies

**Version:** 0.1.0
**Status:** DRAFT — pending Gemini review
**Branch:** `feat/resolve-model-redesign`
**Parent PLAN:** `PLAN-Resolve-Model.md` Phase 3

---

## 1. Problem

Users have hundreds of GB of model files on disk (e.g., `/home/user/.synapse/repo-legacy/`,
ComfyUI `models/` folder, or any custom structure). When a pack dependency needs to be resolved,
downloading the same 6 GB checkpoint again is unacceptable.

The Local Resolve feature lets users point to a local file or browse a directory, and the system
imports it into the blob store — same result as a download, but from local disk.

## 2. User Stories

**US1:** I have a pack with an unresolved checkpoint dependency. I know the file is in my
old models folder. I open Local tab, paste the directory path, see the file listed, click it,
and it gets imported into my blob store.

**US2:** The dependency already has a Civitai selector (known SHA256). When I browse a directory,
the system highlights which file matches the expected hash — I just confirm.

**US3:** I import a file the system doesn't recognize. It hashes it, looks it up on Civitai
(by hash), finds the model, and enriches the dependency with canonical_source for future updates.

**US4:** Hash lookup fails. The system extracts the filename stem, searches Civitai/HF by name,
and finds a match. Now I have canonical_source even though the hash wasn't in their DB.

## 3. Three Scenarios

### Scenario A: Dep has known remote source
- Dep already resolved to `civitai_file(model_id=X, sha256=Y)` but blob not downloaded
- System knows WHAT to look for → can recommend files by SHA256 or filename match
- User confirms → copy to blob store, done

### Scenario B: Unknown file, enrichment via hash
- Custom pack, dep has only a name hint
- User selects file → system hashes → Civitai by-hash API / HF lookup
- If found: enrich with canonical_source, model_id, version_id
- Copy to blob store with full metadata

### Scenario C: Hash miss, enrichment via filename
- Hash not found on Civitai/HF
- Filename stem → name search (Civitai Meilisearch + HF)
- If found: enrich with canonical_source
- If not found: store as LOCAL_FILE with display_name from filename
- Always: sha256 + file size + display_name preserved

## 4. Architecture

### 4.1 New Service: `LocalFileService`

```
src/store/local_file_service.py
```

**Why a separate service?**
- Single Responsibility: file browsing, validation, hashing, enrichment are distinct from resolve/download
- Testable: can unit test with mocked filesystem and Civitai client
- Extensible: future features (batch import, auto-scan) plug into same service
- Follows Store facade pattern: 10th service in Store constructor

**Dependencies (injected):**
- `layout: StoreLayout` — for blob paths
- `hash_cache: HashCache` — persistent hash cache
- `blob_store: BlobStore` — for `_copy_local_file()` and `blob_exists()`
- `pack_service_getter: Callable` — lazy access to PackService for Civitai/HF clients

**Public API:**

```python
class LocalFileService:
    """Service for browsing, validating, and importing local model files."""

    def browse(self, directory: str, kind: Optional[AssetKind] = None) -> BrowseResult:
        """List model files in a directory, optionally filtered by kind."""

    def recommend(self, directory: str, dep: PackDependency) -> List[FileRecommendation]:
        """Scan directory and rank files by match likelihood to a dependency."""

    def import_file(
        self,
        file_path: str,
        pack_name: str,
        dep_id: str,
        *,
        progress_callback: Optional[Callable] = None,
    ) -> LocalImportResult:
        """Hash, copy to blob store, enrich metadata, resolve dependency."""
```

### 4.2 Data Models

```python
# In resolve_models.py or local_file_service.py

@dataclass
class LocalFileInfo:
    """A single file found during directory browsing."""
    name: str           # "ponyDiffusionV6XL.safetensors"
    path: str           # "/home/user/models/checkpoints/ponyDiffusionV6XL.safetensors"
    size: int           # bytes
    mtime: float        # modification time
    extension: str      # ".safetensors"
    cached_hash: Optional[str] = None  # SHA256 if already in hash cache

@dataclass
class FileRecommendation:
    """A file with a match score for a specific dependency."""
    file: LocalFileInfo
    match_type: Literal["sha256_exact", "filename_exact", "filename_stem", "none"]
    confidence: float   # 0.0 - 1.0
    reason: str         # Human-readable: "SHA256 matches expected hash"

class BrowseResult(BaseModel):
    """Result of browsing a local directory."""
    directory: str
    files: List[LocalFileInfo]
    total_count: int
    error: Optional[str] = None

class LocalImportResult(BaseModel):
    """Result of importing a local file."""
    success: bool
    sha256: Optional[str] = None
    file_size: Optional[int] = None
    display_name: Optional[str] = None
    enrichment: Optional[EnrichmentResult] = None
    error: Optional[str] = None

class EnrichmentResult(BaseModel):
    """What we learned about the file from remote lookups."""
    source: Literal["civitai_hash", "civitai_name", "huggingface", "filename_only"]
    canonical_source: Optional[CanonicalSource] = None
    civitai_model_id: Optional[int] = None
    civitai_version_id: Optional[int] = None
    display_name: Optional[str] = None
    base_model: Optional[str] = None
```

### 4.3 Security

```python
# Allowlisted extensions (case-insensitive)
ALLOWED_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".bin", ".pth", ".onnx", ".sft"}

def validate_path(path: str) -> tuple[bool, str]:
    """Validate a local file path for security.

    Checks:
    1. Path is absolute (no relative paths)
    2. No '..' components (path traversal)
    3. Path resolves to same location (no symlink tricks)
    4. File has allowlisted extension
    5. File is a regular file (not device, socket, etc.)
    """
```

### 4.4 Enrichment Pipeline

Enrichment is a best-effort pipeline that runs after hashing:

```
1. Hash lookup (Civitai by-hash API)
   ├── Found → CivitaiSelector + CanonicalSource ✓ DONE
   └── Miss ↓
2. Hash lookup (HuggingFace — if applicable)
   ├── Found → HuggingFaceSelector + CanonicalSource ✓ DONE
   └── Miss ↓
3. Name search (Civitai Meilisearch/REST)
   ├── Found → CivitaiSelector + CanonicalSource ✓ DONE
   └── Miss ↓
4. Name search (HuggingFace)
   ├── Found → HuggingFaceSelector + CanonicalSource ✓ DONE
   └── Miss ↓
5. Filename only → display_name from stem, no canonical_source
```

**Reuse:** Steps 1 and 3 are already implemented in `PreviewMetaEvidenceProvider._lookup_by_hash()`
and `._search_by_name()`. Extract these into shared utility functions in a new module
`src/store/enrichment.py` so both providers and LocalFileService can reuse them.

### 4.5 API Endpoints

```python
# In api.py — under v2_packs_router or new v2_local_router

@router.get("/browse-local")
def browse_local_directory(
    path: str = Query(..., description="Directory path to browse"),
    kind: Optional[str] = Query(None, description="Filter by AssetKind"),
    store=Depends(require_initialized),
) -> BrowseResult:
    """List model files in a local directory."""

@router.get("/{pack_name}/recommend-local")
def recommend_local_files(
    pack_name: str,
    dep_id: str = Query(...),
    directory: str = Query(...),
    store=Depends(require_initialized),
) -> List[FileRecommendation]:
    """Scan directory and recommend files matching a dependency."""

@router.post("/{pack_name}/import-local")
def import_local_file(
    pack_name: str,
    request: ImportLocalRequest,
    store=Depends(require_initialized),
) -> LocalImportResult:
    """Import a local file into blob store and resolve dependency."""

class ImportLocalRequest(BaseModel):
    dep_id: str
    file_path: str
    skip_enrichment: bool = False  # For testing or user preference
```

### 4.6 Frontend: LocalResolveTab

New component: `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx`

**States:**
1. **Empty** — path input, "Browse" button, recent paths (from localStorage)
2. **Loading** — scanning directory (Loader2 spinner)
3. **File list** — files with recommendations highlighted
4. **Importing** — progress bar (hashing + copying)
5. **Done** — success message, enrichment info shown

**UX Flow:**
```
┌─────────────────────────────────────────────────┐
│ 📁 Local File                                    │
│                                                  │
│ ┌──────────────────────────────────┐ ┌────────┐ │
│ │ /home/user/models/checkpoints    │ │ Browse │ │
│ └──────────────────────────────────┘ └────────┘ │
│                                                  │
│ Recent:  repo-legacy/checkpoints                 │
│          ComfyUI/models/loras                    │
│                                                  │
│ ─────────────────────────────────────────────── │
│                                                  │
│ ⭐ ponyDiffusionV6XL.safetensors    6.5 GB      │
│    SHA256 matches expected hash                  │
│                                                  │
│ ○ sd_xl_turbo_1.0_fp16.safetensors  6.5 GB      │
│                                                  │
│ ○ anything-v4.5-pruned.safetensors  4.0 GB      │
│                                                  │
│ ○ v1-5-pruned-emaonly.safetensors   4.0 GB      │
│                                                  │
└─────────────────────────────────────────────────┘
│                              │ Use This File │   │
└──────────────────────────────┴───────────────┘   │

After clicking "Use This File":
┌─────────────────────────────────────────────────┐
│ 📁 Local File                                    │
│                                                  │
│ Importing ponyDiffusionV6XL.safetensors...       │
│                                                  │
│ ████████████████░░░░░░░░  68%                    │
│ Hashing file (4.4 / 6.5 GB)                     │
│                                                  │
│ Then: Copy to blob store                         │
│ Then: Enrich metadata (Civitai/HF lookup)        │
└─────────────────────────────────────────────────┘

After completion:
┌─────────────────────────────────────────────────┐
│ 📁 Local File                                    │
│                                                  │
│ ✅ Successfully imported!                        │
│                                                  │
│ ponyDiffusionV6XL.safetensors                    │
│ SHA256: a1b2c3d4...                              │
│ Size: 6.5 GB                                     │
│                                                  │
│ 🔗 Enrichment:                                   │
│ Found on Civitai: Pony Diffusion V6 XL           │
│ Model #290640 → Version #357609                  │
│ Canonical source saved for future updates        │
│                                                  │
│                           ┌──────────────────┐  │
│                           │   ✓ Done         │  │
│                           └──────────────────┘  │
└─────────────────────────────────────────────────┘
```

**Props interface:**
```typescript
interface LocalResolveTabProps {
  packName: string
  depId: string
  depName: string
  kind: AssetType
  // Known selector data (for Scenario A recommendations)
  expectedSha256?: string
  expectedFilename?: string
  // Callbacks
  onResolved: () => void  // Notify parent that dep was resolved
}
```

### 4.7 Shared Enrichment Module

Extract from `PreviewMetaEvidenceProvider` into reusable module:

```python
# src/store/enrichment.py

@dataclass
class EnrichmentResult:
    source: str
    canonical_source: Optional[CanonicalSource]
    civitai: Optional[CivitaiSelector]
    huggingface: Optional[HuggingFaceSelector]
    display_name: Optional[str]
    base_model: Optional[str]

def enrich_by_hash(
    sha256: str,
    civitai_client: Optional[CivitaiClient],
    kind: Optional[AssetKind] = None,
) -> Optional[EnrichmentResult]:
    """Look up a SHA256 hash on Civitai (and later HF). Returns enrichment or None."""

def enrich_by_name(
    filename_stem: str,
    civitai_client: Optional[CivitaiClient],
    kind: Optional[AssetKind] = None,
) -> Optional[EnrichmentResult]:
    """Search by filename stem on Civitai/HF. Returns enrichment or None."""

def enrich_file(
    sha256: str,
    filename: str,
    civitai_client: Optional[CivitaiClient],
    kind: Optional[AssetKind] = None,
) -> EnrichmentResult:
    """Full enrichment pipeline: hash → name → filename-only fallback."""
```

This module is then used by:
- `LocalFileService.import_file()` — primary use case
- `PreviewMetaEvidenceProvider._resolve_hint()` — refactored to use shared code
- Future: batch import, auto-scan

## 5. Store Integration

```python
# In Store.__init__()
self.local_file_service = LocalFileService(
    layout=self.layout,
    hash_cache=self.hash_cache,
    blob_store=self.blob_store,
    pack_service_getter=lambda: self.pack_service,
)
```

**Follows existing patterns:**
- Lazy client access via `pack_service_getter` (same as ResolveService)
- Service added to Store facade (same as all other services)
- No circular dependencies (LocalFileService → BlobStore, HashCache; not vice versa)

## 6. File Structure

```
src/store/
├── local_file_service.py     # NEW: browsing, validation, import
├── enrichment.py             # NEW: shared hash/name lookup utilities
├── hash_cache.py             # EXISTING: used by local_file_service
├── blob_store.py             # EXISTING: _copy_local_file() reused
├── resolve_service.py        # EXISTING: no changes needed
├── api.py                    # MODIFIED: 3 new endpoints
└── __init__.py               # MODIFIED: wire LocalFileService

apps/web/src/components/modules/pack-detail/
├── modals/
│   ├── DependencyResolverModal.tsx  # MODIFIED: add 'local' tab
│   └── LocalResolveTab.tsx          # NEW: Local tab component
├── types.ts                         # MODIFIED: add local types
└── constants.ts                     # MODIFIED: add query key
```

## 7. Test Plan

### Unit Tests (`tests/unit/store/test_local_file_service.py`)
- `test_browse_lists_model_files` — filters by extension
- `test_browse_ignores_non_model_files` — .txt, .json, .py excluded
- `test_browse_filters_by_kind` — checkpoint vs lora extensions
- `test_browse_nonexistent_directory` — returns error
- `test_validate_path_rejects_relative` — "../../../etc/passwd"
- `test_validate_path_rejects_traversal` — "/home/user/models/../../etc/passwd"
- `test_validate_path_rejects_symlink_escape` — symlink to /etc
- `test_validate_path_rejects_bad_extension` — .exe, .sh, .py
- `test_validate_path_accepts_valid` — .safetensors, .ckpt, .pt
- `test_recommend_sha256_match` — exact hash match = confidence 1.0
- `test_recommend_filename_match` — exact filename = confidence 0.8
- `test_recommend_stem_match` — stem similarity = confidence 0.5
- `test_recommend_no_match` — no files match

### Unit Tests (`tests/unit/store/test_enrichment.py`)
- `test_enrich_by_hash_civitai_found` — hash lookup succeeds
- `test_enrich_by_hash_civitai_miss` — returns None
- `test_enrich_by_name_found` — name search succeeds
- `test_enrich_by_name_no_match` — returns None
- `test_enrich_by_name_kind_filter` — filters by AssetKind
- `test_enrich_file_hash_first` — hash lookup takes priority
- `test_enrich_file_fallback_to_name` — hash miss → name search
- `test_enrich_file_all_miss` — returns filename_only result

### Integration Tests (`tests/integration/test_local_resolve.py`)
- `test_import_copies_to_blob_store` — file ends up in correct blob path
- `test_import_with_enrichment` — Civitai lookup enriches metadata
- `test_import_resolves_dependency` — dep gets LOCAL_FILE selector
- `test_import_with_existing_blob` — dedup: blob exists → skip copy
- `test_import_updates_hash_cache` — hash cached for future use

### API Tests (`tests/store/test_local_api.py`)
- `test_browse_local_endpoint` — returns file list
- `test_browse_local_security` — rejects path traversal
- `test_import_local_endpoint` — full flow via API
- `test_recommend_local_endpoint` — returns ranked recommendations

## 8. Extensibility Points

- **New enrichment sources**: Add to `enrichment.py` pipeline (e.g., CivitAI v3 API, ModelScope)
- **Batch import**: `LocalFileService.import_directory()` → iterate + import_file()
- **Auto-scan**: Background task that scans configured directories periodically
- **File watchers**: inotify-based watchers for configured directories
- **New file types**: Add to `ALLOWED_EXTENSIONS` set

## 9. Implementation Order

1. `enrichment.py` — extract shared code from PreviewMetaEvidenceProvider
2. `local_file_service.py` — browse, validate, recommend, import
3. API endpoints in `api.py`
4. Wire into Store.__init__
5. Frontend: `LocalResolveTab.tsx`
6. Frontend: integrate tab into DependencyResolverModal
7. Tests (unit + integration + API)
8. Refactor PreviewMetaEvidenceProvider to use enrichment.py
