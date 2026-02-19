# PLAN: Synapse Updates System

**Status:** ✅ v1.0.0 DOKONČENO - kompletní update flow (check → select → options → apply)
**Priority:** 🔴 HIGH - klíčová feature celého balíčkovacího systému
**Depends on:** Pack Edit (✅ done), Downloads infrastructure
**Created:** 2026-01-31
**Updated:** 2026-02-17

---

## 1. Overview & Motivation

### 1.1 Why We Need This

Civitai models get updated frequently:
- **Bug fixes** - Authors fix issues in their models
- **New versions** - Better training, improved quality
- **Multi-version releases** - WAN releases HIGH/LOW variants together

**Problem:** After importing a pack, users lose connection to Civitai updates.

**Solution:** Comprehensive update system that:
1. Checks for new versions on Civitai
2. Updates model files (blobs) while preserving user customizations
3. Optionally syncs new previews/metadata
4. Supports bulk operations across all packs

### 1.2 Key Principle: Your Pack, Your Rules

```
┌─────────────────────────────────────────────────────────────────┐
│  CIVITAI                           YOUR LOCAL PACK              │
│  ═══════                           ═══════════════              │
│                                                                 │
│  Model File v1.0  ──── Import ────►  blob (sha256)              │
│  Description      ──── Import ────►  pack.json:description      │
│  Previews         ──── Import ────►  pack.json:previews         │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Model File v2.0  ──── Update ────►  NEW blob (new sha256)      │
│  Description v2   ──── ???    ────►  YOUR description preserved │
│  New Previews     ──── ???    ────►  YOUR previews preserved    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

After import, pack is YOUR local copy.
Updates change the MODEL FILE, not your customizations.
```

---

## 2. Current Implementation (Single Pack Update)

### 2.1 Backend Architecture

```
src/store/update_service.py (✅ EXISTS, ~550 lines)
├── is_updatable(pack) → bool
├── plan_update(pack_name) → UpdatePlan
├── apply_update(pack_name, plan, choose) → PackLock
├── update_pack(pack_name, dry_run, sync) → UpdateResult
├── check_all_updates() → Dict[str, UpdatePlan]
└── _check_dependency_update(dep, current) → update_info

src/store/api.py (✅ EXISTS)
├── GET  /api/updates/check/{pack_name}  → UpdatePlan
├── GET  /api/updates/check-all          → Dict[str, UpdatePlan]
└── POST /api/updates/apply              → UpdateResult
```

### 2.2 Update Flow (Current)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CHECK PHASE                                                  │
│                                                                 │
│    User clicks "Check" in CivitaiPlugin                         │
│    ↓                                                            │
│    GET /api/updates/check/{pack_name}                           │
│    ↓                                                            │
│    UpdateService.plan_update():                                 │
│    ├── Load pack.json                                           │
│    ├── For each dependency:                                     │
│    │   ├── Check selector.strategy == civitai_model_latest?     │
│    │   ├── Check update_policy.mode == follow_latest?           │
│    │   ├── Call Civitai API: GET /models/{model_id}             │
│    │   ├── Compare current version_id vs latest version_id      │
│    │   └── If different → add to changes[]                      │
│    └── Return UpdatePlan { changes, ambiguous }                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. APPLY PHASE                                                  │
│                                                                 │
│    User clicks "Apply Updates"                                  │
│    ↓                                                            │
│    POST /api/updates/apply { pack, sync: true }                 │
│    ↓                                                            │
│    UpdateService.apply_update():                                │
│    ├── Update lock.json:                                        │
│    │   ├── version_id → new version_id                          │
│    │   ├── sha256 → new sha256                                  │
│    │   └── download_url → new URL                               │
│    │                                                            │
│    ├── If sync=true:                                            │
│    │   ├── Download new blob to blobs/sha256/XX/XXXX...         │
│    │   └── Rebuild views (symlinks) for active UIs              │
│    │                                                            │
│    └── Return UpdateResult { applied: true }                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 What Gets Updated vs Preserved

```
┌──────────────────────────┬─────────────┬─────────────────────────┐
│ File                     │ Updated?    │ Notes                   │
├──────────────────────────┼─────────────┼─────────────────────────┤
│ lock.json                │ ✅ YES      │ version_id, sha256      │
│ blobs/sha256/...         │ ✅ YES      │ New model file          │
│ views/                   │ ✅ YES      │ Symlinks rebuilt        │
├──────────────────────────┼─────────────┼─────────────────────────┤
│ pack.json:name           │ ❌ NO       │ User's name preserved   │
│ pack.json:description    │ ❌ NO       │ User's edits preserved  │
│ pack.json:previews       │ ❌ NO       │ User's selection kept   │
│ pack.json:user_tags      │ ❌ NO       │ User's tags preserved   │
│ pack.json:parameters     │ ❌ NO       │ User's settings kept    │
│ pack.json:workflows      │ ❌ NO       │ User's workflows kept   │
└──────────────────────────┴─────────────┴─────────────────────────┘
```

### 2.4 Dependency Update Policy

Each dependency in `pack.json` has:

```json
{
  "dependencies": [
    {
      "id": "main_checkpoint",
      "selector": {
        "strategy": "civitai_model_latest",
        "civitai": {
          "model_id": 133005,
          "version_id": 1759168
        }
      },
      "update_policy": {
        "mode": "follow_latest"  // or "pinned"
      }
    }
  ]
}
```

- **`follow_latest`** → Checks for updates, can be updated
- **`pinned`** → Never updated, stays on original version

### 2.5 Frontend (CivitaiPlugin)

```typescript
// apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx

// Check for updates (manual trigger)
const { data: updateCheck } = useQuery({
  queryKey: ['update-check', pack.name],
  queryFn: () => fetch(`/api/updates/check/${pack.name}`).then(r => r.json()),
  enabled: false, // Manual only
})

// Apply updates
const applyMutation = useMutation({
  mutationFn: () => fetch('/api/updates/apply', {
    method: 'POST',
    body: JSON.stringify({ pack: pack.name, sync: true })
  })
})
```

---

## 3. PLANNED: Update Options Dialog

### 3.1 Problem

Currently, updates ONLY change the blob. But users might want to:
- Get new preview images from the latest version
- Sync updated description (author added new info)
- Keep their customizations in some areas but not others

### 3.2 Solution: Update Options

```
┌─────────────────────────────────────────────────────────────────┐
│  Update Available: Juggernaut XL                                │
│  v11 (XI) → v13 (Ragnarok)                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  What to update:                                                │
│                                                                 │
│  ☑ Model files (blobs)              [Required]                  │
│    Downloads new model file (2.3 GB)                            │
│                                                                 │
│  ☐ Fetch new previews               [Optional]                  │
│    Merge with existing (adds 12 new images)                     │
│    Your added/removed previews will be preserved                │
│                                                                 │
│  ☐ Update description               [Optional]                  │
│    Replace with Civitai description                             │
│    ⚠️ Your edits will be lost                                   │
│                                                                 │
│  ☐ Update model info                [Optional]                  │
│    Sync trigger words, base model, etc.                         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Cancel]                              [Apply Update]           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Preview Merge Strategy

```
MERGE (recommended):
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Your current previews:    [A] [B] [C] [D]  (4 images)          │
│                             ↓   ↓       ↓                       │
│  Civitai previews:         [A] [B] [E] [F] [G]  (5 images)      │
│                             ↓   ↓   ↓   ↓   ↓                   │
│  After merge:              [A] [B] [C] [D] [E] [F] [G]          │
│                                                                 │
│  - Duplicates detected by URL                                   │
│  - [C] kept (you added it)                                      │
│  - [E] [F] [G] added (new from Civitai)                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Backend Changes Needed

```python
# src/store/update_service.py

class UpdateOptions(BaseModel):
    """Options for what to update."""
    update_blobs: bool = True        # Always true (required)
    merge_previews: bool = False     # Fetch & merge new previews
    update_description: bool = False # Replace description
    update_model_info: bool = False  # Sync model_info fields

def apply_update_with_options(
    self,
    pack_name: str,
    plan: UpdatePlan,
    options: UpdateOptions,
    choose: Optional[Dict[str, int]] = None,
) -> UpdateResult:
    """Apply update with user-selected options."""

    # 1. Always update lock.json
    lock = self._apply_lock_changes(pack_name, plan, choose)

    # 2. Optionally merge previews
    if options.merge_previews:
        self._merge_previews_from_civitai(pack_name)

    # 3. Optionally update description
    if options.update_description:
        self._update_description_from_civitai(pack_name)

    # 4. Optionally sync model_info
    if options.update_model_info:
        self._sync_model_info_from_civitai(pack_name)

    return UpdateResult(...)
```

### 3.5 API Changes

```typescript
// POST /api/updates/apply
interface ApplyUpdateRequest {
  pack: string
  sync: boolean

  // NEW: Update options
  options?: {
    merge_previews?: boolean
    update_description?: boolean
    update_model_info?: boolean
  }

  // For ambiguous file selection
  choose?: Record<string, number>
}
```

---

## 4. PLANNED: Multi-Version Sync

### 4.1 Problem

Some packs have multiple versions (e.g., WAN with HIGH/LOW quality):

```json
{
  "dependencies": [
    {
      "id": "wan_high",
      "selector": { "civitai": { "model_id": 123, "version_id": 100 } }
    },
    {
      "id": "wan_low",
      "selector": { "civitai": { "model_id": 123, "version_id": 101 } }
    }
  ]
}
```

When author releases v2.0:
- HIGH: version_id 100 → 200
- LOW: version_id 101 → 201

**Current behavior:** Each dependency checked/updated separately.
**Desired:** Update both together as a cohesive release.

### 4.2 UI for Multi-Version Updates

```
┌─────────────────────────────────────────────────────────────────┐
│  WAN Video Model - 2 updates available                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ☑ wan_high (Checkpoint)                                        │
│    v1.0 → v2.0                                    6.2 GB        │
│                                                                 │
│  ☑ wan_low (Checkpoint)                                         │
│    v1.0 → v2.0                                    3.1 GB        │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  Total download: 9.3 GB                                         │
│                                                                 │
│  [Cancel]                    [Update All] [Update Selected]     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. PLANNED: Bulk Updates

### 5.1 User Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. User opens Packs page                                        │
│ 2. Clicks "Check Updates" button                                │
│ 3. Spinner: "Checking 10 packs..."                              │
│ 4. Badge appears: "3 updates available"                         │
│ 5. User clicks badge → Opens Updates Panel                      │
│ 6. Selects which packs to update                                │
│ 7. Clicks "Update Selected"                                     │
│ 8. Downloads tracked in Downloads tab                           │
│ 9. Toast: "3 packs updated successfully"                        │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 PacksPage Header

```
┌─────────────────────────────────────────────────────────────────┐
│  Packs                                          [Check Updates] │
│  10 packs installed                                             │
├─────────────────────────────────────────────────────────────────┤

After check:

┌─────────────────────────────────────────────────────────────────┐
│  Packs                         [3 updates ▾] [Check Updates]    │
│  10 packs installed                  │                          │
│                          ┌───────────┴───────────┐              │
│                          │ ☑ Juggernaut XL       │              │
│                          │   v11 → v13           │              │
│                          │                       │              │
│                          │ ☑ WAN Model           │              │
│                          │   2 deps need update  │              │
│                          │                       │              │
│                          │ ☑ Some LoRA           │              │
│                          │   v2.1 → v2.3         │              │
│                          ├───────────────────────┤              │
│                          │ [Update All (3)]      │              │
│                          └───────────────────────┘              │
├─────────────────────────────────────────────────────────────────┤
```

### 5.3 Updates Panel (Full View)

```
┌─────────────────────────────────────────────────────────────────┐
│  Available Updates                                    [×] Close │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ☑ Juggernaut XL                                                │
│    Checkpoint • v11 → v13 (Ragnarok) • 2.3 GB                   │
│    [View on Civitai] [Update Options...]           [Update]     │
│                                                                 │
│  ───────────────────────────────────────────────────────────    │
│                                                                 │
│  ☑ WAN Video Model                                              │
│    2 dependencies need update                                   │
│    ├── wan_high: v1.0 → v2.0 • 6.2 GB                          │
│    └── wan_low: v1.0 → v2.0 • 3.1 GB                           │
│    [View on Civitai] [Update Options...]           [Update]     │
│                                                                 │
│  ───────────────────────────────────────────────────────────    │
│                                                                 │
│  ☐ Some LoRA (skipped)                                          │
│    LoRA • v2.1 → v2.3 • 145 MB                                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Total: 11.7 GB                                                 │
│                                                                 │
│  [Select All] [Deselect All]              [Update Selected (2)] │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 Downloads Tab Integration

```
┌─────────────────────────────────────────────────────────────────┐
│  Downloads                                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⬢ Pack Updates (batch-1706745600)              [2/3 done]     │
│  │                                                              │
│  ├── Juggernaut XL                                              │
│  │   ████████████████████████░░░░░░  67%  1.5/2.3 GB           │
│  │                                                              │
│  ├── WAN Model (wan_high)                                       │
│  │   ████████████████████████████████  100% ✓                  │
│  │                                                              │
│  ├── WAN Model (wan_low)                                        │
│  │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Pending                   │
│  │                                                              │
│  └── Some LoRA                                                  │
│      ████████████████████████████████  100% ✓                  │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ⬢ Manual Downloads                                             │
│  └── (empty)                                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.5 Sidebar Badge

```
┌──────────────┐
│  ⬢ Synapse   │
├──────────────┤
│  Browse      │
│  Packs    (3)│  ← Red badge = updates available
│  Profiles    │
│  Downloads (2)│  ← Blue badge = active downloads
│  Inventory   │
└──────────────┘
```

---

## 6. Frontend Components (Planned)

### 6.1 New Files

```
apps/web/src/
├── components/
│   └── modules/
│       └── updates/                         ❌ NEW FOLDER
│           ├── index.ts                     ❌ exports
│           ├── UpdatesPanel.tsx             ❌ Main slide-out panel
│           ├── UpdatesList.tsx              ❌ List with checkboxes
│           ├── UpdateItem.tsx               ❌ Single pack update row
│           ├── UpdateOptionsDialog.tsx      ❌ Options for single update
│           └── BulkUpdateProgress.tsx       ❌ Batch progress display
│
├── stores/
│   └── updatesStore.ts                      ❌ Zustand store
│
└── hooks/
    └── useUpdates.ts                        ❌ React Query wrapper
```

### 6.2 State Management

```typescript
// stores/updatesStore.ts
import { create } from 'zustand'

interface UpdatesState {
  // Check status
  isChecking: boolean
  lastChecked: Date | null
  checkError: string | null

  // Results
  availableUpdates: Map<string, UpdatePlan>
  totalUpdatesCount: number

  // Selection
  selectedPacks: Set<string>

  // Apply status
  applyingPacks: Set<string>
  appliedPacks: Set<string>
  applyErrors: Map<string, string>

  // Actions
  checkAllUpdates: () => Promise<void>
  checkSinglePack: (packName: string) => Promise<void>

  selectPack: (packName: string) => void
  deselectPack: (packName: string) => void
  selectAll: () => void
  deselectAll: () => void

  applyUpdate: (packName: string, options?: UpdateOptions) => Promise<void>
  applySelectedUpdates: (options?: UpdateOptions) => Promise<void>

  dismissUpdate: (packName: string) => void
  clearAll: () => void
}

export const useUpdatesStore = create<UpdatesState>((set, get) => ({
  // ... implementation
}))
```

### 6.3 useUpdates Hook

```typescript
// hooks/useUpdates.ts
export function useUpdates() {
  const store = useUpdatesStore()

  // Auto-refresh on mount (optional)
  useEffect(() => {
    if (store.lastChecked === null) {
      store.checkAllUpdates()
    }
  }, [])

  return {
    // State
    isChecking: store.isChecking,
    updates: Array.from(store.availableUpdates.values()),
    updatesCount: store.totalUpdatesCount,
    selectedCount: store.selectedPacks.size,

    // Actions
    checkAll: store.checkAllUpdates,
    selectPack: store.selectPack,
    applySelected: store.applySelectedUpdates,

    // Computed
    hasUpdates: store.totalUpdatesCount > 0,
    allSelected: store.selectedPacks.size === store.totalUpdatesCount,
  }
}
```

---

## 7. API Contracts

### 7.1 Existing Endpoints

```typescript
// GET /api/updates/check/{pack_name}
interface UpdatePlan {
  pack: string
  already_up_to_date: boolean
  changes: UpdateChange[]
  ambiguous: AmbiguousUpdate[]
}

// GET /api/updates/check-all
interface CheckAllResponse {
  checked_at: string
  packs_checked: number
  updates_available: number
  plans: Record<string, UpdatePlan>
}

// POST /api/updates/apply
interface ApplyRequest {
  pack: string
  dry_run?: boolean
  sync?: boolean
  choose?: Record<string, number>  // For ambiguous selections
}
```

### 7.2 New/Modified Endpoints

```typescript
// POST /api/updates/apply (MODIFIED)
interface ApplyRequest {
  pack: string
  dry_run?: boolean
  sync?: boolean
  choose?: Record<string, number>

  // NEW: Update options
  options?: UpdateOptions
}

interface UpdateOptions {
  merge_previews?: boolean      // Fetch & merge new previews
  update_description?: boolean  // Replace description
  update_model_info?: boolean   // Sync model_info fields
}

// POST /api/updates/apply-batch (NEW)
interface ApplyBatchRequest {
  packs: string[]
  sync?: boolean
  options?: UpdateOptions  // Apply to all
  choose?: Record<string, Record<string, number>>  // pack -> dep -> file_id
}

interface ApplyBatchResponse {
  results: Record<string, UpdateResult>
  total_applied: number
  total_failed: number
  download_task_id?: string
}
```

---

## 8. Implementation Phases

### Phase 1: Update Options Dialog ✅ DONE (v1.0.0)
- [x] Add `UpdateOptions` model to backend (`src/store/models.py`)
- [x] Modify `apply_update` to accept options (`update_service.py:update_pack()`)
- [x] Add preview merge logic (`_merge_previews_from_civitai` - URL dedup, preserves user changes)
- [x] Add description sync logic (`_update_description_from_civitai`)
- [x] Add model info sync logic (`_update_model_info_from_civitai` - base_model, trigger_words)
- [x] Create `UpdateOptionsDialog.tsx` (`apps/web/src/components/modules/packs/`)
- [x] Integrate into CivitaiPlugin (Apply button → opens options dialog → apply with options)
- [x] Backend tests: 26 tests in `test_update_options.py`

### Phase 2: Basic Bulk Check ✅ DONE (v1.0.0)
- [x] Create `updatesStore.ts` (Zustand store with check/select/apply state)
- [x] ~~Create `useUpdates.ts` hook~~ → Integrated directly into updatesStore (simpler)
- [x] Add "Check Updates" button to PacksPage header
- [x] Add updates count badge (amber badge on button + sidebar)
- [x] Toast notifications for check completion

### Phase 3: Updates Panel ✅ DONE (v1.0.0)
- [x] Create `UpdatesPanel.tsx` (slide-out panel with portal)
- [x] ~~Create `UpdatesList.tsx` / `UpdateItem.tsx`~~ → Combined into UpdatesPanel (simpler)
- [x] Per-pack update cards with checkboxes and expandable details
- [x] Implement select/deselect all functionality
- [x] "Update Selected" action calls apply-batch endpoint
- [x] Impacted packs warning per pack
- [x] Ambiguous count warning

### Phase 4: Downloads Integration ✅ PARTIAL (v1.0.0)
- [x] Add `apply-batch` endpoint (`POST /api/updates/apply-batch`)
- [x] `BatchUpdateResult` model with per-pack results
- [ ] ~~Extend Downloads tab for batch updates~~ → FUTURE: needs download queue refactoring
- [ ] ~~Group update downloads visually~~ → FUTURE
- [ ] ~~Progress tracking per pack~~ → FUTURE: needs WebSocket/SSE
- [ ] ~~Cancel support~~ → FUTURE

### Phase 5: Polish & UX ✅ PARTIAL (v1.0.0)
- [x] Sidebar badge for updates (amber badge on Packs nav item)
- [ ] ~~Keyboard shortcuts~~ → FUTURE
- [ ] ~~Remember dismissed updates~~ → FUTURE
- [ ] ~~"What's new" link~~ → FUTURE
- [ ] ~~Estimated download time~~ → FUTURE

### Phase 6: Background Checking (Future)
- [ ] Configurable auto-check interval
- [ ] Service worker or polling approach
- [ ] Desktop notifications (optional)
- [ ] Auto-dismiss old notifications

> **Note:** Phases 4-6 remaining items are tracked as FUTURE enhancements.
> The core update flow (check → select → configure options → apply) is complete.

---

## 9. Edge Cases

### 9.1 Ambiguous File Selection
- Some models have multiple files (FP16/FP32, pruned/full)
- Show selection UI before applying
- Remember user preference per pack/dependency

### 9.2 Multi-Version Packs
- Group related dependencies visually
- Show total download size for all versions
- Option to update subset of versions

### 9.3 Partial Failures
- If 1/3 updates fail, show partial success
- Allow retry for failed ones
- Don't block others

### 9.4 Concurrent Operations
- Disable "Check Updates" while checking
- Disable pack cards while updating
- Show clear status indicators
- Queue updates if multiple triggered

### 9.5 Large Updates
- Show estimated download size before applying
- Warn if total > 10GB
- Support pause/resume (future)

### 9.6 Preview Merge Conflicts
- User deleted a preview that Civitai still has → Keep deleted
- User added custom preview → Keep added
- Same URL in both → Deduplicate by URL

---

## 10. Testing

### 10.1 Backend Unit Tests ✅ DONE
- [x] `test_update_options.py` - 49 tests:
  - UpdateOptions model (4 tests: defaults, individual, all, serialization)
  - BatchUpdateResult model (3 tests: defaults, with results, serialization)
  - UpdateResult enriched fields (3 tests: defaults, set, backward compat)
  - Preview merge (7 tests: adds, dedup, preserves, no source, API failure, empty, video type)
  - Description update (3 tests: updates, no change, no source)
  - Model info update (2 tests: base model, trigger words)
  - Batch apply (3 tests: empty list, serialization, error handling)
  - update_pack with options (1 test: parameter accepted)
  - URL canonicalization (6 tests: query params, fragment, both, unchanged, empty, dedup variants)
  - Full plan→apply flow (5 tests: detect update, up-to-date, apply lock, is_updatable, not updatable)
  - Description preservation (2 tests: preserved without option, updated with option)
  - Reverse dependencies (3 tests: finds deps, no deps, load errors)
  - Batch apply mixed (3 tests: success+failure, all up-to-date, options passthrough)
  - Check all updates (2 tests: skips non-updatable, handles errors)
  - Apply edge cases (2 tests: missing dep warning, no lock raises)
- [x] `test_update_impact.py` - 20 tests (existing, Phase 3)

### 10.2 Frontend Unit Tests
- [ ] FUTURE: Store/component tests

### 10.3 Integration Tests
- [x] Preview merge with existing customizations (in test_update_options.py)
- [x] Error handling and partial failures (in test_update_options.py)
- [x] Full plan→apply cycle with mocked Civitai (in test_update_options.py)
- [x] Description preservation logic (in test_update_options.py)
- [x] Batch apply with mixed outcomes (in test_update_options.py)
- [ ] FUTURE: Full E2E with real file downloads

### 10.4 E2E Tests
- [ ] FUTURE: Full update flow with download integration
- [ ] FUTURE: Bulk update multiple packs with Downloads tab tracking

---

## 11. Related Files

### Backend
- `src/store/update_service.py` - Core update logic (✅ ~700 lines, UpdateOptions, batch, preview merge)
- `src/store/api.py` - API endpoints (✅ /check, /check-all, /apply, /apply-batch)
- `src/store/models.py` - Models (✅ UpdatePlan, UpdateResult, UpdateOptions, BatchUpdateResult)
- `src/store/__init__.py` - Store facade (✅ update(), update_batch())

### Frontend
- `apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx` - Single pack UI (✅ with options dialog)
- `apps/web/src/components/modules/PacksPage.tsx` - ✅ Check Updates button + badge
- `apps/web/src/components/modules/packs/UpdatesPanel.tsx` - ✅ Bulk updates slide-out panel
- `apps/web/src/components/modules/packs/UpdateOptionsDialog.tsx` - ✅ Update options dialog
- `apps/web/src/stores/updatesStore.ts` - ✅ Zustand store for updates state
- `apps/web/src/components/layout/Sidebar.tsx` - ✅ Amber badge for updates count

### Tests
- `tests/store/test_update_options.py` - ✅ 26 tests for UpdateOptions, preview merge, batch
- `tests/store/test_update_impact.py` - ✅ 20 tests for impact analysis

### Plans
- `plans/PLAN-Pack-Edit.md` - Pack editing features (✅ done)
- `plans/PLAN-Model-Inventory.md` - Blob/backup management (✅ done)
- **🔗 `plans/PLAN-Dependencies.md`** - ✅ Provázáno a DOKONČENO
  - ✅ Dependency impact analysis při updatu (impacted_packs in UpdatePlan)
  - ~~Kaskádový update~~ → FUTURE: needs careful design
  - ~~Version constraint validace~~ → FUTURE
  - ✅ Upozornění uživatele na breaking changes (impacted packs shown in UI)

---

## 12. Open Questions

1. ~~**Auto-check frequency?**~~ → FUTURE (Phase 6)
2. ~~**Notification persistence?**~~ → Badge clears when updates are applied/dismissed
3. ~~**Default options?**~~ → All options default to OFF (safe default, user opts in)
4. **Undo support?** - FUTURE: Could keep old blob as backup before update

---

## 13. ⚠️ Known Gap: Download Integration

### 13.1 Problem (pre-existing, NOT introduced by v1.0.0)

`_sync_after_update()` (update_service.py, existed on main since first commit) does
**synchronous** `blob_store.download()` directly in the API request handler. This is a
**parallel download path** that bypasses the existing download infrastructure.

### 13.2 Two Download Paths Exist (BAD — must be unified)

```
PATH A: Existing download system (CORRECT, used by UI "Download" button)
═══════════════════════════════════════════════════════════════════════
  POST /api/packs/{name}/download-asset
  → Background thread (threading.Thread)
  → blob_store.download(url, progress_callback=...)
  → _active_downloads dict tracks state
  → GET /api/packs/downloads/{id}/progress ← Frontend polls this
  → downloadsStore.ts updates UI
  → Downloads tab shows: progress bar, speed, ETA
  → Validates downloaded file (HTML check, min size)
  → Creates symlink to ComfyUI models folder
  → Updates lock.json with verified SHA256

PATH B: _sync_after_update (BROKEN, used by updates apply)
═══════════════════════════════════════════════════════════
  POST /api/updates/apply { sync: true }
  → _sync_after_update() called synchronously
  → blob_store.download(url) ← NO progress callback
  → BLOCKS the HTTP request for entire download (2-10 GB!)
  → _active_downloads NOT updated → Downloads tab shows NOTHING
  → NO HTML validation
  → NO symlink creation to ComfyUI
  → NO proper error handling (was silent `except: pass` before v1.0.1)
```

### 13.3 Correct Fix

After `apply_update()` updates lock.json, the frontend should call the **existing**
`download-asset` endpoint for each changed dependency — NOT rely on `sync: true`.

```
STEP 1: Apply (lock only, no download)
  POST /api/updates/apply { sync: false }
  → Updates lock.json with new version_id, sha256, URLs
  → Returns immediately: { applied: true, changes: [...] }

STEP 2: Download via existing system
  For each change in result.changes:
    POST /api/packs/{name}/download-asset
      { asset_name: change.dependency_id, url: change.download_url }
    → Background thread, progress tracking, Downloads tab ✅

STEP 3: Frontend bridges the two
  updatesStore.applyUpdate() {
    // 1. Apply lock changes
    const result = await fetch('/api/updates/apply', { sync: false })
    // 2. Queue downloads via existing download system
    for (const change of result.changes) {
      await fetch(`/api/packs/${packName}/download-asset`, {
        body: { asset_name: change.dep_id, ... }
      })
    }
    // 3. Downloads tab picks up automatically
  }
```

### 13.4 What Needs to Change

| Change | File | Description |
|--------|------|-------------|
| Frontend: `sync: false` | `updatesStore.ts` | Stop using sync:true, call download-asset instead |
| Frontend: bridge to downloads | `updatesStore.ts` | After apply, call download-asset per changed dep |
| Backend: return download URLs | `api.py /apply` | Return changed dep URLs in response for frontend |
| Backend: ~~remove~~ deprecate `_sync_after_update` | `update_service.py` | Keep for CLI use, but frontend should not use it |
| Backend: apply response enrichment | `update_service.py` | `UpdateResult` should include changed dep download info |

### 13.5 Interim: `_sync_after_update` kept for CLI

The CLI (`synapse update <pack> --sync`) can still use `_sync_after_update` because
CLI doesn't have a Downloads tab. But the web frontend MUST use Path A (download-asset).

> **Priority:** HIGH. This is the NEXT task before updates are production-ready.
> Without this fix, applying updates with `sync: true` from the web UI will either
> timeout (large files) or download without any progress tracking.

---

## 14. Changelog

### v1.0.1 (2026-02-19) - Stabilization
- 🔧 Fix Zustand Set<string> → string[] for reliable React re-renders
- 🔧 Add URL canonicalization for preview dedup (strips query params/fragments)
- 🔧 Add logging for all exception handlers (was silent)
- 🔧 Add dep_id validation in apply_update (warns on missing dep)
- ✅ 49 backend tests (was 26): +URL canonicalization, full plan→apply flow,
  description preservation, reverse deps, batch mixed results, edge cases
- 📝 Document download integration gap (Section 13)
- Reviews: Gemini (architecture), Codex (security/robustness) - analyzed and incorporated

### v1.0.0 (2026-02-19)
- ✅ Phase 1: UpdateOptions model, preview merge, description/model_info sync
- ✅ Phase 2: Zustand store, Check Updates button, badge
- ✅ Phase 3: UpdatesPanel slide-out, bulk select/apply
- ✅ Phase 4 (partial): apply-batch endpoint
- ✅ Phase 5 (partial): Sidebar badge
- ✅ UpdateOptionsDialog for single pack updates in CivitaiPlugin
- ✅ i18n: EN + CS translations for all new UI
- ✅ 26 backend tests for new features

---

*Last updated: 2026-02-19 - v1.0.1 stabilizace, download gap zdokumentován*
