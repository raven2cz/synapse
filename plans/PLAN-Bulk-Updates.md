# PLAN: Bulk Updates System

**Status:** 📋 PLANNED (not started)
**Priority:** Medium
**Depends on:** Pack Edit (✅ done), Downloads infrastructure
**Created:** 2026-01-31

---

## 1. Overview

Implement a comprehensive bulk update system for Civitai packs with:
- One-click "Check All Updates" from PacksPage
- Visual progress tracking in Downloads tab
- Batch apply with selective updates
- Background update checking (optional)

---

## 2. User Stories

### 2.1 Primary Flow
```
User opens Packs page
  → Sees "Check Updates" button in header
  → Clicks it
  → Progress spinner shows "Checking 10 packs..."
  → Badge appears: "3 updates available"
  → User clicks badge or "Updates" tab
  → Sees list of packs with available updates
  → Can select which to update
  → Clicks "Update Selected" or "Update All"
  → Downloads start, visible in Downloads tab
  → Toast: "3 packs updated successfully"
```

### 2.2 Background Checking (Future)
```
App starts
  → Background check runs every 24h (configurable)
  → If updates found, notification badge in sidebar
  → User can dismiss or review updates
```

---

## 3. Architecture

### 3.1 Backend (Already Exists)

```
src/store/update_service.py
├── check_all_updates() → Dict[str, UpdatePlan]  ✅ EXISTS
├── plan_update(pack_name) → UpdatePlan          ✅ EXISTS
├── apply_update(pack_name, plan, choose) → PackLock  ✅ EXISTS
└── update_pack(pack_name, sync=True) → UpdateResult  ✅ EXISTS

src/store/api.py
├── GET /api/updates/check-all              ✅ EXISTS
├── GET /api/updates/check/{pack_name}      ✅ EXISTS
├── POST /api/updates/apply                 ✅ EXISTS
└── POST /api/updates/apply-batch           ❌ NEW (optional)
```

### 3.2 Frontend Components

```
apps/web/src/
├── components/
│   ├── layout/
│   │   └── Header.tsx
│   │       └── UpdatesBadge                    ❌ NEW
│   │
│   └── modules/
│       ├── PacksPage.tsx
│       │   └── CheckUpdatesButton              ❌ NEW
│       │
│       ├── updates/                            ❌ NEW FOLDER
│       │   ├── UpdatesPanel.tsx                ❌ NEW
│       │   ├── UpdatesList.tsx                 ❌ NEW
│       │   ├── UpdateItem.tsx                  ❌ NEW
│       │   └── BulkUpdateDialog.tsx            ❌ NEW
│       │
│       └── downloads/
│           └── DownloadsPage.tsx               (extend for updates)
│
├── stores/
│   └── updatesStore.ts                         ❌ NEW
│
└── hooks/
    └── useUpdates.ts                           ❌ NEW
```

### 3.3 State Management

```typescript
// stores/updatesStore.ts
interface UpdatesState {
  // Check status
  isChecking: boolean
  lastChecked: Date | null
  checkError: string | null

  // Results
  availableUpdates: Map<string, UpdatePlan>
  totalUpdatesCount: number

  // Apply status
  applyingPacks: Set<string>
  appliedPacks: Set<string>
  applyErrors: Map<string, string>

  // Actions
  checkAllUpdates: () => Promise<void>
  applyUpdate: (packName: string) => Promise<void>
  applyAllUpdates: () => Promise<void>
  applySelectedUpdates: (packNames: string[]) => Promise<void>
  dismissUpdate: (packName: string) => void
  clearAll: () => void
}
```

---

## 4. UI Design

### 4.1 PacksPage Header Addition

```
┌─────────────────────────────────────────────────────────────────┐
│  Packs                                          [Check Updates] │
│  10 packs installed                              ↓              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Pack Cards Grid...]                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

After check:

┌─────────────────────────────────────────────────────────────────┐
│  Packs                              [3 updates] [Check Updates] │
│  10 packs installed                      ↓                      │
├─────────────────────────────────────────────────────────────────┤
```

### 4.2 Updates Panel (Slide-out or Modal)

```
┌─────────────────────────────────────────────────────────────────┐
│  Available Updates                                    [×] Close │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ☑ Juggernaut XL                                                │
│    v11 → v13 (Ragnarok)                                         │
│    [View Changes]                                    [Update]   │
│                                                                 │
│  ☑ Some LoRA Pack                                               │
│    v2.1 → v2.3                                                  │
│    [View Changes]                                    [Update]   │
│                                                                 │
│  ☐ Another Pack (skipped)                                       │
│    v1.0 → v1.1                                                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [Select All] [Deselect All]              [Update Selected (2)] │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Downloads Tab Integration

```
┌─────────────────────────────────────────────────────────────────┐
│  Downloads                                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⬢ Pack Updates                                    [2/3 done]  │
│  ├── Juggernaut XL          ████████████░░░░  67%  2.3 GB      │
│  ├── Some LoRA Pack         ████████████████  100% ✓           │
│  └── Another Pack           ░░░░░░░░░░░░░░░░  Pending          │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ⬢ Manual Downloads                                             │
│  └── ...                                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 Sidebar Badge

```
┌──────────────┐
│  ⬢ Synapse   │
├──────────────┤
│  Browse      │
│  Packs    (3)│  ← Updates badge
│  Profiles    │
│  Downloads   │
│  Inventory   │
└──────────────┘
```

---

## 5. API Contracts

### 5.1 Check All Updates

```typescript
// GET /api/updates/check-all
interface CheckAllUpdatesResponse {
  checked_at: string
  packs_checked: number
  updates_available: number
  plans: Record<string, UpdatePlan>
}

interface UpdatePlan {
  pack: string
  already_up_to_date: boolean
  changes: UpdateChange[]
  ambiguous: AmbiguousUpdate[]
}

interface UpdateChange {
  dependency_id: string
  old: {
    provider: string
    provider_version_id: number
    version_name?: string
    sha256?: string
  }
  new: {
    provider: string
    provider_version_id: number
    version_name?: string
    sha256?: string
  }
}
```

### 5.2 Apply Batch Updates (New Endpoint)

```typescript
// POST /api/updates/apply-batch
interface ApplyBatchRequest {
  packs: string[]           // Pack names to update
  sync: boolean             // Download blobs immediately
  ui_targets?: string[]     // UIs to rebuild views for
}

interface ApplyBatchResponse {
  results: Record<string, UpdateResult>
  total_applied: number
  total_failed: number
  download_task_id?: string  // For tracking in Downloads
}
```

---

## 6. Implementation Phases

### Phase 1: Basic Bulk Check
- [ ] `updatesStore.ts` - State management
- [ ] `useUpdates.ts` hook
- [ ] "Check Updates" button on PacksPage
- [ ] Simple badge showing count
- [ ] Toast notifications

### Phase 2: Updates Panel
- [ ] `UpdatesPanel.tsx` - Slide-out panel
- [ ] `UpdatesList.tsx` - List with checkboxes
- [ ] `UpdateItem.tsx` - Single update row
- [ ] Select/deselect functionality
- [ ] "Update Selected" action

### Phase 3: Downloads Integration
- [ ] Extend Downloads tab for update tasks
- [ ] Progress tracking for batch updates
- [ ] Group updates visually
- [ ] Cancel support

### Phase 4: Polish
- [ ] Sidebar badge
- [ ] Keyboard shortcuts (u = check updates)
- [ ] Remember dismissed updates
- [ ] "What's new" info from Civitai

### Phase 5: Background Checking (Future)
- [ ] Configurable interval
- [ ] Service worker or polling
- [ ] Desktop notifications (optional)
- [ ] Auto-dismiss old notifications

---

## 7. Edge Cases

### 7.1 Ambiguous Updates
- Some models have multiple files (FP16/FP32, pruned/full)
- Show selection UI before applying
- Remember user preference per pack

### 7.2 Partial Failures
- If 1/3 updates fail, show partial success
- Allow retry for failed ones
- Don't block others

### 7.3 Concurrent Operations
- Disable "Check Updates" while checking
- Disable pack cards while updating
- Show clear status indicators

### 7.4 Large Updates
- Show estimated download size before applying
- Warn if > 10GB total
- Support pause/resume (future)

---

## 8. Testing

### 8.1 Unit Tests
- [ ] updatesStore actions
- [ ] useUpdates hook
- [ ] UpdatesList component

### 8.2 Integration Tests
- [ ] Check all → Apply selected flow
- [ ] Error handling
- [ ] Downloads integration

### 8.3 E2E Tests
- [ ] Full update flow with mock Civitai
- [ ] Multiple packs update
- [ ] Cancel mid-update

---

## 9. Notes

### 9.1 What Changes on Update
```
pack.json     → UNCHANGED (metadata stays)
lock.json     → UPDATED (new version_id, sha256)
blobs/        → NEW BLOB downloaded
views/        → SYMLINKS rebuilt
previews/     → UNCHANGED (original from import)
```

### 9.2 Performance
- Check is fast (just API calls, no downloads)
- Apply is slow (downloads + view rebuild)
- Consider parallel downloads (max 3?)

### 9.3 Existing Infrastructure
- UpdateService already has all backend logic
- Downloads tab already handles progress
- Just need to connect the pieces

---

## 10. Related Files

- `src/store/update_service.py` - Backend service
- `src/store/api.py` - API endpoints (lines 3986-4030)
- `apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx` - Single pack updates
- `plans/PLAN-Pack-Edit.md` - CivitaiPlugin implementation details

---

*Last updated: 2026-01-31*
