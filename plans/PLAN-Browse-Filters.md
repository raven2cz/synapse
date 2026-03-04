# Browse Filters Stabilization — Verified from Civitai Source Code

**Status:** ✅ DOKONČENO (2026-03-04)
**Commit:** `4622801` feat: browse filters stabilization — verified from Civitai source

## Context

Browse Civitai filtry měly více problémů: duplicitní "All Types" dropdown, chybějící/nefunkční filtry, špatné enum hodnoty, kritické bugy v bridge scriptu. S přístupem k Civitai open source (`~/git/github/civitai`) opraveno VŠECHNO podle skutečných tRPC schemat a enumů.

**Zdroj pravdy:** `~/git/github/civitai/src/` — tRPC routery, Prisma schema, konstanty, UI komponenty.

---

## FÁZE 1: Kritické bugy a cleanup ✅

### 1.1 ✅ Odstranit duplicitní "All Types" native `<select>`

**Problém:** `BrowsePage.tsx` — native `<select>` se 7 typy byl DUPLICITNÍ s `SearchFilters` chip systémem (všech 16 typů, multi-select).

**Řešení:**
- Smazána `MODEL_TYPES` konstanta
- Smazán `selectedType` state
- Smazán `<select>` element
- Smazána `effectiveModelTypes` merge logika — použit přímo `modelTypes`
- Aktualizován `queryKey` — odstraněn `selectedType`

**Soubor:** `apps/web/src/components/modules/BrowsePage.tsx`

### 1.2 ✅ Opravit CRITICAL array nesting bug v bridge

**Problém:** `synapse-civitai-bridge.user.js` — `[params.filters.types]` vytvářel nested array `[['LORA', 'Checkpoint']]`.

**Řešení (buildSearchUrl):**
```javascript
types: params.filters?.types
  ? (Array.isArray(params.filters.types) ? params.filters.types : [params.filters.types])
  : undefined,
baseModels: params.filters?.baseModel
  ? (Array.isArray(params.filters.baseModel) ? params.filters.baseModel : [params.filters.baseModel])
  : undefined,
```

**Soubor:** `scripts/tampermonkey/synapse-civitai-bridge.user.js`

### 1.3 ✅ Opravit baseModel — posílat celý array

**Problém:** `trpcBridgeAdapter.ts` — `params.baseModels[0]` ignoroval více base modelů.

**Řešení:** `baseModel: params.baseModels?.length ? params.baseModels : undefined`

**Soubor:** `apps/web/src/lib/api/adapters/trpcBridgeAdapter.ts`

---

## FÁZE 2: Enum opravy dle Civitai source ✅

### 2.1 ✅ Sort options — doplněny chybějící

**Zdroj:** `civitai/src/server/common/enums.ts` (ModelSort enum)

| Bylo (5) | Nyní (8) |
|---|---|
| Most Downloaded | Most Downloaded |
| Highest Rated | Highest Rated |
| Newest | Newest |
| Most Discussed | Most Discussed |
| Most Collected | Most Collected |
| ~~Most Buzz~~ | **Most Liked** ✅ |
| — | **Most Images** ✅ |
| — | **Oldest** ✅ |

### 2.2 ✅ Base models — aktualizováno + multi-select

**Zdroj:** `civitai/src/shared/constants/base-model.constants.ts`

Přidané base modely:
- **SD 3.5:** SD 3.5 Large, SD 3.5 Medium, SD 3.5 Large Turbo
- **Wan Video 2.x:** Wan Video 2.2 TI2V-5B, Wan Video 2.2 I2V-A14B, Wan Video 2.2 T2V-A14B, Wan Video 2.5 T2V, Wan Video 2.5 I2V
- **Další:** Anima, Seedance, Kling, Vidu Q1

Multi-select: `baseModel: string` → `baseModels: string[]` v SearchFilters i BrowsePage

### 2.3 ✅ CheckpointType — nový podmíněný filtr

**Zdroj:** `civitai/src/shared/utils/prisma/enums.ts`

- `CHECKPOINT_TYPE_OPTIONS`: Trained, Merge
- Zobrazí se POUZE když `modelTypes.includes('Checkpoint')`
- Auto-clear při odebrání Checkpoint z typů

### 2.4 ✅ File format — ověřeno a integrováno

**Zdroj:** `civitai/src/server/common/constants.ts`

- Odstraněn `Pt` z `FILE_FORMAT_OPTIONS` (není v Civitai constants)
- 7 formátů: SafeTensor, PickleTensor, GGUF, Diffusers, Core ML, ONNX, Other

### 2.5 ✅ Category — integrováno

- Meilisearch: `category.name = 'character'`
- tRPC: `tagname: 'character'`

---

## FÁZE 3: Propagace nových filtrů ✅

### 3.1 ✅ BrowsePage state
- `baseModels: string[]` (bylo: `baseModel: string`)
- Nové: `fileFormat`, `category`, `checkpointType`

### 3.2 ✅ SearchFilters props
- `baseModels` / `onBaseModelsChange` (multi-select)
- `checkpointType` / `onCheckpointTypeChange` (podmíněný)

### 3.3 ✅ trpcBridgeAdapter → bridge
- `filters.types`, `filters.baseModel` (array), `filters.fileFormats`, `filters.category`, `filters.checkpointType`

### 3.4 ✅ Bridge — buildSearchUrl (tRPC)
- `checkpointType`, `fileFormats`, `tagname` parametry

### 3.5 ✅ Bridge — buildMeilisearchRequest
- `fileFormats IN [...]`, `checkpointType = '...'`, `category.name = '...'` filtry
- `escapeFilterValue()` pro prevenci filter injection

---

## FÁZE 4: i18n ✅

- `en.json`: `"filterCheckpointType": "Checkpoint Type"`
- `cs.json`: `"filterCheckpointType": "Typ Checkpointu"`

---

## Bezpečnostní opravy (z review) ✅

### Meilisearch filter injection
- Přidán `escapeFilterValue()` helper — escapuje jednoduché uvozovky ve VŠECH filter hodnotách
- Aplikováno na types, baseModel, fileFormats, checkpointType, category

### hasMore false positive
- Opraveno: `currentOffset + hits.length < totalHits` (místo `hits.length >= limit`)
- Využívá `estimatedTotalHits` z Meilisearch response

---

## Změněné soubory

| Soubor | Změny |
|--------|-------|
| `apps/web/src/lib/api/searchTypes.ts` | Sort +3, BaseModel aktualizace, +CHECKPOINT_TYPE, fix FILE_FORMAT, SearchParams +3 pole |
| `apps/web/src/components/modules/BrowsePage.tsx` | Smazán native select + selectedType, baseModel→baseModels[], +fileFormat/category/checkpointType state |
| `apps/web/src/components/ui/SearchFilters.tsx` | baseModel→baseModels multi-select, +checkpointType podmíněný filtr |
| `apps/web/src/lib/api/adapters/trpcBridgeAdapter.ts` | baseModel array fix, +fileFormats/category/checkpointType |
| `scripts/tampermonkey/synapse-civitai-bridge.user.js` | Fix array nesting, +filtry, escapeFilterValue, hasMore fix |
| `apps/web/src/i18n/locales/en.json` | +filterCheckpointType |
| `apps/web/src/i18n/locales/cs.json` | +filterCheckpointType |

---

## Testy ✅

| Soubor | Typ | Počet | Pokrytí |
|--------|-----|-------|---------|
| `search-filters.test.ts` | Unit | 41 | Enum konstanty, typy, multi-select logika, conditional visibility |
| `browse-filter-propagation.test.ts` | Integration | 10 | Adapter → bridge filter mapping, SearchParams interface |
| `browse-filter-smoke.test.ts` | Smoke | 9 | Full pipeline, edge cases, contract tests |

**Celkem: 60 testů (41 unit + 10 integration + 9 smoke)**

## Verifikace ✅

- TypeScript: 0 chyb
- Frontend testy: všechny prochází
- Backend testy: 1597 passed
- `./scripts/verify.sh --quick`: All checks passed

## Review ✅

- **Claude review:** Žádné kritické problémy
- **Gemini review:** 4 nálezy → 2 opraveny (filter injection, hasMore)
- **Codex review:** 6 nálezů → validovány, 2 opraveny (shodné s Gemini)
