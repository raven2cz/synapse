# PLAN: Global NSFW Filter System

**Status:** 🚧 Phase 1 COMPLETE, Phases 2-6 PENDING
**Created:** 2026-03-04
**Version:** 1.0.0

---

## Overview

Multi-level NSFW filtering system replacing the simple boolean `nsfwBlurEnabled`.

**Components:**
- `NsfwFilterMode`: `show` | `blur` | `hide`
- `NsfwMaxLevel`: `pg` | `pg13` | `r` | `x` | `all` (maps to Civitai browsing level bitmask)

---

## Phase 1: Store + Backward Compat ✅ IMPL+INTEG

**Files:**
- `apps/web/src/stores/nsfwStore.ts` — NEW, Zustand store with persist
- `apps/web/src/stores/settingsStore.ts` — MODIFIED, delegates to nsfwStore

**Implementation:**
- `useNsfwStore` with `filterMode`, `maxLevel`, `getBrowsingLevel()`, `shouldBlur()`, `shouldHide()`
- Persistence key: `synapse-nsfw-settings`
- Auto-migration from legacy `synapse-settings.nsfwBlurEnabled`
- `settingsStore.nsfwBlurEnabled` getter/setter delegates to `nsfwStore`
- Subscribe sync: nsfwStore changes propagate to settingsStore

---

## Phase 2: Settings UI ❌ PENDING

- Add 3-way toggle (Show / Blur / Hide) replacing simple on/off
- Add `maxLevel` dropdown (PG / PG-13 / R / X / All)
- Location: `SettingsPage.tsx` NSFW section

---

## Phase 3: MediaPreview / ModelCard / FullscreenViewer ❌ PENDING

- Replace `nsfwBlurEnabled` usage with `shouldBlur()` / `shouldHide()`
- `shouldHide()` → don't render component at all
- `shouldBlur()` → existing blur behavior

---

## Phase 4: PacksPage ❌ PENDING

- Use `shouldHide()` to filter packs from list
- Replace current `nsfwBlurEnabled` check

---

## Phase 5: BrowsePage ❌ PENDING

- Pass `browsingLevel` to search queries
- Filter search results with `shouldHide()`

---

## Phase 6: Header Toggle Upgrade ❌ PENDING

- Upgrade header button from 2-state to 3-state (show/blur/hide)
- Visual indicator for current mode

---

*Last updated: 2026-03-04*
