# PLAN: Synapse Updates System

**Status:** 📋 PLANNED (partially implemented)
**Priority:** Medium-High
**Depends on:** Pack Edit (✅ done), Downloads infrastructure
**Created:** 2026-01-31
**Updated:** 2026-01-31

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

### Phase 1: Update Options Dialog
- [ ] Add `UpdateOptions` model to backend
- [ ] Modify `apply_update` to accept options
- [ ] Add preview merge logic (`_merge_previews_from_civitai`)
- [ ] Add description/model_info sync logic
- [ ] Create `UpdateOptionsDialog.tsx` component
- [ ] Integrate into CivitaiPlugin

### Phase 2: Basic Bulk Check
- [ ] Create `updatesStore.ts`
- [ ] Create `useUpdates.ts` hook
- [ ] Add "Check Updates" button to PacksPage header
- [ ] Add updates count badge
- [ ] Toast notifications for check completion

### Phase 3: Updates Panel
- [ ] Create `UpdatesPanel.tsx` (slide-out)
- [ ] Create `UpdatesList.tsx` with checkboxes
- [ ] Create `UpdateItem.tsx` with details
- [ ] Implement select/deselect functionality
- [ ] "Update Selected" action with options

### Phase 4: Downloads Integration
- [ ] Add `apply-batch` endpoint
- [ ] Extend Downloads tab for batch updates
- [ ] Group update downloads visually
- [ ] Progress tracking per pack
- [ ] Cancel support

### Phase 5: Polish & UX
- [ ] Sidebar badge for updates
- [ ] Keyboard shortcuts (u = check updates)
- [ ] Remember dismissed updates (localStorage)
- [ ] "What's new" link to Civitai changelog
- [ ] Estimated download time

### Phase 6: Background Checking (Future)
- [ ] Configurable auto-check interval
- [ ] Service worker or polling approach
- [ ] Desktop notifications (optional)
- [ ] Auto-dismiss old notifications

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

### 10.1 Backend Unit Tests
- [ ] `test_update_options.py` - UpdateOptions model
- [ ] `test_preview_merge.py` - Preview merge logic
- [ ] `test_batch_apply.py` - Batch operations

### 10.2 Frontend Unit Tests
- [ ] `updatesStore.test.ts` - Store actions
- [ ] `useUpdates.test.ts` - Hook behavior
- [ ] `UpdatesList.test.tsx` - Component rendering

### 10.3 Integration Tests
- [ ] Check all → Apply selected flow
- [ ] Preview merge with existing customizations
- [ ] Multi-version update
- [ ] Error handling and partial failures

### 10.4 E2E Tests
- [ ] Full update flow with mock Civitai
- [ ] Bulk update multiple packs
- [ ] Cancel mid-download

---

## 11. Related Files

### Backend
- `src/store/update_service.py` - Core update logic (✅ exists)
- `src/store/api.py` - API endpoints, lines 3986-4030 (✅ exists)
- `src/store/models.py` - UpdatePlan, UpdateResult models (✅ exists)

### Frontend
- `apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx` - Single pack UI (✅ exists)
- `apps/web/src/components/modules/PacksPage.tsx` - Will add Check Updates button
- `apps/web/src/components/modules/downloads/` - Downloads integration

### Plans
- `plans/PLAN-Pack-Edit.md` - Pack editing features (✅ done)
- `plans/PLAN-Model-Inventory.md` - Blob/backup management (✅ done)

---

## 12. Open Questions

1. **Auto-check frequency?** - 24h? On app start? User configurable?
2. **Notification persistence?** - How long to show update badge?
3. **Default options?** - Should "merge previews" be on by default?
4. **Undo support?** - Can user rollback an update? (Keep old blob?)

---

*Last updated: 2026-01-31*
