# PLAN: Global NSFW Filter System

**Status:** 🚧 Phase 1 COMPLETE, Phases 2-6 PENDING
**Created:** 2026-03-04
**Version:** 2.0.0

---

## Overview

Multi-level NSFW filtering system replacing the simple boolean `nsfwBlurEnabled`.

**Components:**
- `NsfwFilterMode`: `show` | `blur` | `hide`
- `NsfwMaxLevel`: `pg` | `pg13` | `r` | `x` | `all` (maps to Civitai browsing level bitmask)

**Civitai nsfwLevel bitmask:**
```
PG=1, PG-13=2, R=4, X=8, Blocked=16
Combos: pg=1, pg13=3, r=7, x=15, all=31
```

---

## Aktuální stav (audit)

### Co existuje (Phase 1) ✅
- `nsfwStore.ts` — Zustand store s `filterMode`, `maxLevel`, `shouldBlur()`, `shouldHide()`, `getBrowsingLevel()`
- `settingsStore.ts` — deleguje na nsfwStore, sync subscription
- Persistence + auto-migrace z legacy `nsfwBlurEnabled`

### Co chybí (Gaps)
1. **Komponenty nepoužívají store metody** — počítají blur inline: `nsfw && nsfwBlurEnabled && !isRevealed`
2. **`shouldHide()` nikde implementován** — žádná komponenta nic neschová
3. **`getBrowsingLevel()` se nepředává** — bridge má hardcoded `config.nsfw ? 31 : 1`
4. **Settings UI je binární** — jen on/off toggle, žádný 3-way nebo maxLevel
5. **Header toggle je binární** — jen show/blur, žádný hide
6. **`useNsfwStore` importován ale nepoužit** v CommunityGalleryPanel

### Dotčené soubory (16)
| Soubor | Aktuální NSFW logika |
|--------|---------------------|
| `MediaPreview.tsx` | `nsfw && nsfwBlurEnabled && !isRevealed` inline, blur overlay, reveal button |
| `FullscreenMediaViewer.tsx` | Stejné inline pattern, blur overlay, reveal v thumbnailech |
| `ModelCard.tsx` | `nsfw && nsfwBlurEnabled && !isRevealed` inline |
| `ImagePreview.tsx` | Stejné inline pattern |
| `BrowsePage.tsx` | `includeNsfw=true` hardcoded, `nsfw` prop na MediaPreview |
| `PacksPage.tsx` | `nsfwBlurEnabled` + `is_nsfw_hidden` tag check |
| `CommunityGalleryPanel.tsx` | Import `useNsfwStore` ale nepoužit |
| `Header.tsx` | 2-state toggle (show/blur) |
| `SettingsPage.tsx` | Simple on/off toggle |
| `settingsStore.ts` | Legacy delegace |
| `nsfwStore.ts` | Store (hotový) |

---

## Phase 1: Store + Backward Compat ✅ IMPL+INTEG

**Files:**
- `apps/web/src/stores/nsfwStore.ts` — Zustand store with persist
- `apps/web/src/stores/settingsStore.ts` — delegates to nsfwStore

**Implementation:**
- `useNsfwStore` with `filterMode`, `maxLevel`, `getBrowsingLevel()`, `shouldBlur()`, `shouldHide()`
- Persistence key: `synapse-nsfw-settings`
- Auto-migration from legacy `synapse-settings.nsfwBlurEnabled`
- `settingsStore.nsfwBlurEnabled` getter/setter delegates to `nsfwStore`
- Subscribe sync: nsfwStore changes propagate to settingsStore

---

## Phase 2: Settings UI ❌ PENDING

### Cíl
Nahradit binární toggle v SettingsPage za 3-way toggle + maxLevel dropdown.

### Aktuální stav
`SettingsPage.tsx:241-256` — simple on/off switch (`setNsfwBlur(!nsfwBlurEnabled)`).

### Změny

**Soubor:** `apps/web/src/components/modules/SettingsPage.tsx`

1. **Import `useNsfwStore`** místo `useSettingsStore` pro NSFW sekci
2. **3-way SegmentedControl** pro `filterMode`:
   ```
   ┌──────────┬──────────┬──────────┐
   │  👁 Show  │  🔳 Blur  │  🚫 Hide │
   └──────────┴──────────┴──────────┘
   ```
   - `show` — vše viditelné, NSFW badge na obsahu
   - `blur` — rozmazání s click-to-reveal (současné chování)
   - `hide` — NSFW obsah se vůbec nerenderuje
   - Použít existující button group pattern z UI

3. **maxLevel dropdown** pod segmented control:
   ```
   NSFW Level: [PG ▾]
   ```
   Options: PG (safest) → PG-13 → R → X → All (vše)
   - Popisek: "Maximum NSFW content level to display"
   - Zobrazovat POUZE když `filterMode !== 'hide'` (pokud je hide, level je irrelevantní)

4. **Popis** aktualizovat:
   - Show: "All content visible with NSFW badges"
   - Blur: "NSFW content is blurred until clicked"
   - Hide: "NSFW content is completely hidden"

### i18n klíče (nové)
```json
"settings.display.nsfwMode": "NSFW Filter Mode",
"settings.display.nsfwModeDesc": "How to handle NSFW content",
"settings.display.nsfwMode.show": "Show",
"settings.display.nsfwMode.blur": "Blur",
"settings.display.nsfwMode.hide": "Hide",
"settings.display.nsfwMode.showDesc": "All content visible with NSFW badges",
"settings.display.nsfwMode.blurDesc": "NSFW content is blurred until clicked",
"settings.display.nsfwMode.hideDesc": "NSFW content is completely hidden",
"settings.display.nsfwMaxLevel": "Maximum NSFW Level",
"settings.display.nsfwMaxLevelDesc": "Maximum content rating to display",
"settings.display.nsfwLevel.pg": "PG (Safe)",
"settings.display.nsfwLevel.pg13": "PG-13",
"settings.display.nsfwLevel.r": "R (Mature)",
"settings.display.nsfwLevel.x": "X (Explicit)",
"settings.display.nsfwLevel.all": "All"
```

### Testy
- Unit: SettingsPage renderuje 3 režimy, maxLevel dropdown, ukazuje/skrývá level dle mode
- Stav: kliknutí na segment změní `filterMode` v nsfwStore

---

## Phase 3: Komponenty — shouldBlur/shouldHide ❌ PENDING

### Cíl
Nahradit všechny inline `nsfw && nsfwBlurEnabled && !isRevealed` patterny voláním store metod. Přidat `shouldHide()` logiku.

### Strategie

Zavést **helper hook** aby se neopakoval boilerplate:

```typescript
// apps/web/src/hooks/useNsfwFilter.ts
export function useNsfwFilter(nsfw: boolean) {
  const { shouldBlur, shouldHide } = useNsfwStore()
  const [isRevealed, setIsRevealed] = useState(false)

  // Reset revealed when mode changes to blur
  const filterMode = useNsfwStore((s) => s.filterMode)
  useEffect(() => {
    if (filterMode === 'blur') setIsRevealed(false)
  }, [filterMode])

  return {
    isBlurred: shouldBlur(nsfw) && !isRevealed,
    isHidden: shouldHide(nsfw),
    isRevealed,
    reveal: () => setIsRevealed(true),
    hide: () => setIsRevealed(false),
    toggle: () => setIsRevealed(prev => !prev),
    showBadge: nsfw && filterMode === 'show',
  }
}
```

### Změny po souborech

#### 3.1 MediaPreview.tsx
- Import `useNsfwFilter` místo `useSettingsStore`
- Odstranit `nsfwBlurEnabled` prop (BREAKING — ale je optional, fallback na store)
- `const { isBlurred, isHidden, isRevealed, toggle, showBadge } = useNsfwFilter(nsfw)`
- `if (isHidden) return null` — nerender vůbec
- Nahradit `shouldBlur` → `isBlurred`
- Nahradit `nsfw && !nsfwBlurEnabled` badge → `showBadge`
- Odstranit interní `isRevealed` state (přesun do hooku)
- Zachovat `nsfwBlurEnabled` prop pro zpětnou kompatibilitu (override store)

#### 3.2 FullscreenMediaViewer.tsx
- Import `useNsfwFilter`
- `const { isBlurred, isHidden, toggle } = useNsfwFilter(currentItem?.nsfw ?? false)`
- `if (isHidden)` → ukázat placeholder "NSFW content hidden" místo média
- Thumbnail strip: skrýt hidden items nebo ukázat placeholder icon
- Blur overlay: nahradit inline logiku za `isBlurred`

#### 3.3 ModelCard.tsx
- Import `useNsfwFilter`
- `const { isBlurred, isHidden, toggle, showBadge } = useNsfwFilter(nsfw)`
- `if (isHidden) return null`
- Nahradit inline blur pattern

#### 3.4 ImagePreview.tsx
- Import `useNsfwFilter`
- Stejný pattern jako ModelCard
- `if (isHidden) return null`

#### 3.5 CommunityGalleryPanel.tsx
- Již importuje `useNsfwStore` — použít `shouldHide` pro filtrování preview items
- `const previews = allPreviews.filter(p => !shouldHide(p.nsfw))`

### Zpětná kompatibilita
- `nsfwBlurEnabled` prop na MediaPreview zachovat ale označit `@deprecated`
- Pokud je prop explicitně předán, použít ho (override store)
- Pokud ne, použít hook

### Testy
- Unit: `useNsfwFilter` hook — isBlurred/isHidden/reveal/toggle pro každý filterMode
- Unit: MediaPreview s mode=hide vrátí null
- Unit: ModelCard s mode=hide vrátí null
- Unit: CommunityGalleryPanel filtruje hidden previews
- Integration: přepnutí mode → všechny komponenty reagují

---

## Phase 4: PacksPage ❌ PENDING

### Cíl
Nahradit manuální `is_nsfw_hidden` tag check za `shouldHide()` ze store.

### Aktuální stav
`PacksPage.tsx:136-139`:
```typescript
if (nsfwBlurEnabled && (pack.is_nsfw_hidden || pack.user_tags?.includes('nsfw-pack-hide'))) {
  return false
}
```
Problém: Filtruje pouze v blur mode, ne v hide mode. A logika je invertovaná — `nsfw-pack-hide` tag by měl fungovat nezávisle.

### Změny

**Soubor:** `apps/web/src/components/modules/PacksPage.tsx`

1. Import `useNsfwStore` místo `useSettingsStore`
2. Filtrování:
   ```typescript
   const { shouldHide, shouldBlur } = useNsfwStore()

   // Pack filtering
   const filteredPacks = packs.filter(pack => {
     const isNsfw = pack.is_nsfw || pack.user_tags?.includes('nsfw-pack') || pack.nsfw_previews_count > 0

     // Hide mode: skip NSFW packs entirely
     if (shouldHide(isNsfw)) return false

     // User-tagged packs to hide (always respect, independent of mode)
     if (pack.is_nsfw_hidden || pack.user_tags?.includes('nsfw-pack-hide')) return false

     return true
   })
   ```
3. Pack card thumbnails: použít `useNsfwFilter(isNsfwPack)` pro blur/badge

### Testy
- Unit: mode=hide filtruje NSFW packy
- Unit: mode=blur zobrazuje packy s blur
- Unit: mode=show zobrazuje vše
- Unit: `nsfw-pack-hide` tag funguje ve všech režimech

---

## Phase 5: BrowsePage + Bridge browsingLevel ❌ PENDING

### Cíl
Předávat `browsingLevel` z nsfwStore do bridge/adapter, filtrovat výsledky na klientu.

### Aktuální stav
- `BrowsePage.tsx:120`: `const [includeNsfw] = useState(true)` — hardcoded true
- Bridge: `browsingLevel: config.nsfw ? 31 : 1` — bridge-level config, nezávislé na frontendu
- Adapter `search()` interface nemá `browsingLevel` param

### Změny

#### 5.1 SearchParams rozšíření
**Soubor:** `apps/web/src/lib/api/searchTypes.ts`

```typescript
interface SearchParams {
  // ... existing
  browsingLevel?: number  // Civitai browsing level bitmask (1-31)
}
```

#### 5.2 BrowsePage
**Soubor:** `apps/web/src/components/modules/BrowsePage.tsx`

1. Odstranit `const [includeNsfw] = useState(true)`
2. Import `useNsfwStore`
3. Použít store:
   ```typescript
   const { getBrowsingLevel, shouldHide, filterMode } = useNsfwStore()
   ```
4. V adapter.search():
   ```typescript
   await adapter.search({
     // ...existing
     browsingLevel: getBrowsingLevel(),
     // odstranit: nsfw: includeNsfw,
   })
   ```
5. Filtrování výsledků na klientu (hide mode):
   ```typescript
   const visibleModels = filterMode === 'hide'
     ? allModels.filter(m => !m.nsfw)
     : allModels
   ```
6. QueryKey: přidat `browsingLevel` místo statického `includeNsfw`

#### 5.3 trpcBridgeAdapter
**Soubor:** `apps/web/src/lib/api/adapters/trpcBridgeAdapter.ts`

1. Předat `browsingLevel` do bridge:
   ```typescript
   bridge.search({
     // ...existing
     browsingLevel: params.browsingLevel,
   })
   ```
2. Aktualizovat bridge interface — přidat `browsingLevel?: number` do search request

#### 5.4 Bridge script
**Soubor:** `scripts/tampermonkey/synapse-civitai-bridge.user.js`

1. `buildSearchUrl` — použít `params.browsingLevel` pokud existuje, jinak fallback na config:
   ```javascript
   browsingLevel: params.browsingLevel ?? (config.nsfw ? 31 : 1),
   ```
2. `buildMeilisearchRequest` — přidat nsfwLevel filtr dle browsingLevel:
   ```javascript
   // Translate browsingLevel bitmask to nsfwLevel filter
   const allowedLevels = []
   if (browsingLevel & 1) allowedLevels.push(1)   // PG
   if (browsingLevel & 2) allowedLevels.push(2)   // PG-13
   if (browsingLevel & 4) allowedLevels.push(4)   // R
   if (browsingLevel & 8) allowedLevels.push(8)   // X
   if (browsingLevel & 16) allowedLevels.push(16) // Blocked
   nsfwFilter = `(${allowedLevels.map(l => `nsfwLevel=${l}`).join(' OR ')})`
   ```
3. Všechny image endpointy (`buildModelImagesUrl`, `buildModelImagesAsPostsUrl`) — akceptovat a předat `browsingLevel`

#### 5.5 REST adapter fallback
**Soubor:** `apps/web/src/lib/api/adapters/restAdapter.ts` (pokud existuje)
- Předat `browsingLevel` jako query param do `/api/browse/search`

### Testy
- Unit: `getBrowsingLevel()` vrací správný bitmask pro každý maxLevel
- Unit: BrowsePage předává browsingLevel do adapteru
- Integration: adapter → bridge — browsingLevel se propaguje
- Unit: Meilisearch filter builder generuje správný nsfwLevel filter
- Unit: Hide mode filtruje NSFW výsledky na klientu

---

## Phase 6: Header Toggle Upgrade ❌ PENDING

### Cíl
Upgradovat header button z 2-state na 3-state cycle.

### Aktuální stav
`Header.tsx:46-65` — toggle mezi show/blur s Eye/EyeOff ikonami.

### Změny

**Soubor:** `apps/web/src/components/layout/Header.tsx`

1. Import `useNsfwStore` místo `useSettingsStore`
2. 3-state cycle: `show → blur → hide → show`
3. Vizuální stavy:
   ```
   Show:  🟢 zelená border, Eye icon,    "NSFW: Show"
   Blur:  🟡 indigo border, EyeOff icon, "NSFW: Blur"
   Hide:  🔴 red border,    Ban icon,     "NSFW: Hide"
   ```
4. Click handler:
   ```typescript
   const cycleMode = () => {
     const next = { show: 'blur', blur: 'hide', hide: 'show' } as const
     setFilterMode(next[filterMode])
   }
   ```
5. Tooltip: aktuální režim + "Click to cycle"

### i18n klíče (nové)
```json
"header.nsfwShow": "NSFW: Show",
"header.nsfwBlur": "NSFW: Blur",
"header.nsfwHide": "NSFW: Hide"
```

### Testy
- Unit: 3 stavy renderují správnou ikonu, barvu, text
- Unit: click cykluje show→blur→hide→show
- Unit: stav se synchronizuje s nsfwStore

---

## Pořadí implementace

```
Phase 2 (Settings UI)          — základ, uživatel může nastavit režim
    ↓
Phase 3 (Komponenty)           — shouldBlur/shouldHide hook, hide mode
    ↓
Phase 4 (PacksPage)            — filtrace packů
    ↓
Phase 5 (BrowsePage + Bridge)  — browsingLevel propagace, server-side filtr
    ↓
Phase 6 (Header Toggle)        — quick access, 3-state cycle
```

Phase 2 a 3 jsou nezávislé a mohou jít paralelně (ale 3 závisí na tom, že store API je stabilní z Phase 1).

---

## Soubory ke změně (souhrn)

| Soubor | Phase | Změny |
|--------|-------|-------|
| `SettingsPage.tsx` | 2 | 3-way toggle, maxLevel dropdown |
| `useNsfwFilter.ts` | 3 | NEW — shared hook |
| `MediaPreview.tsx` | 3 | useNsfwFilter, isHidden→null, deprecate nsfwBlurEnabled prop |
| `FullscreenMediaViewer.tsx` | 3 | useNsfwFilter, hidden placeholder |
| `ModelCard.tsx` | 3 | useNsfwFilter, isHidden→null |
| `ImagePreview.tsx` | 3 | useNsfwFilter, isHidden→null |
| `CommunityGalleryPanel.tsx` | 3 | shouldHide filter na previews |
| `PacksPage.tsx` | 4 | shouldHide pro pack filtering |
| `searchTypes.ts` | 5 | +browsingLevel do SearchParams |
| `BrowsePage.tsx` | 5 | getBrowsingLevel(), odstranit includeNsfw |
| `trpcBridgeAdapter.ts` | 5 | Předat browsingLevel do bridge |
| `synapse-civitai-bridge.user.js` | 5 | browsingLevel param, Meilisearch nsfwLevel filter |
| `Header.tsx` | 6 | 3-state cycle toggle |
| `en.json` | 2,6 | Nové i18n klíče |
| `cs.json` | 2,6 | České překlady |

---

## Verifikace (po každé fázi)

1. `cd apps/web && npx tsc --noEmit` — 0 chyb
2. `cd apps/web && npx vitest run` — všechny testy
3. `./scripts/verify.sh --quick` — plná verifikace
4. Manual: přepínat režimy, ověřit vizuální chování

---

*Last updated: 2026-03-04*
