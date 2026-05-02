# PLAN: Dependencies - Rework & Updates Integration

**Version:** v0.8.1
**Status:** ✅ DOKONČENO (Phase 1-4). Phase 5 → PLAN-Resolution.md
**Priority:** 🔴 HIGH
**Created:** 2026-02-03
**Updated:** 2026-02-19
**Author:** raven2cz + Claude Opus 4.5/4.6

---

## 1. Cíl

Zprovoznit oba typy závislostí jako jednoduché, srozumitelné koncepty:

1. **Asset Dependencies** - "Tento pack obsahuje tyto soubory" (checkpoint, LoRA, VAE...)
2. **Pack Dependencies** - "Tento pack potřebuje tyto jiné packy" (agregátor)

A opravit chybné chování base modelu při importu.

**Klíčový princip:** Jednoduchost. Systém navrhuje, uživatel rozhoduje. Žádné magické validace.

---

## 2. Co máme a co je špatně

### 2.1 Co funguje ✅

| Oblast | Stav | Kde |
|--------|------|-----|
| Asset dep modely (PackDependency) | ✅ | `src/store/models.py:406-420` |
| Pack dep modely (PackDependencyRef) | ✅ | `src/store/models.py:438-458` |
| Asset dep API (CRUD, download, resolve) | ✅ | `src/store/api.py` |
| Asset dep UI (tabulka, status, download) | ✅ | `PackDependenciesSection.tsx` |
| Base model resolver modal | ✅ | `BaseModelResolverModal.tsx` (~640 řádků) |
| Pack dep UI - zobrazení + CRUD | ✅ | `PackDepsSection.tsx` (Phase 2+4: extracted, rich cards, tree) |
| Import z Civitai | ✅ | `pack_service.py:495-626` |
| Update service (single pack) | ✅ | `update_service.py` (~550 řádků) |
| Base model aliases config | ✅ | `models.py:267-307` (SD1.5, SDXL, Illustrious, Pony) |
| Delete dep endpoint | ✅ | `api.py:2504-2570` (delete_dependency=true query param) |
| EditDependenciesModal | ✅ | `EditDependenciesModal.tsx` (add/remove/filter asset deps, callback) |

### 2.2 ~~Co je špatně~~ ✅ VŠECHNO OPRAVENO (Phase 1-4)

**A) Base model `required: true` při importu**
- `pack_service.py:605` hard-codes `required=True` pro base model dependency (when alias found)
- `pack_service.py:619` má správně `required=False` (fallback when alias NOT found)
- `api.py:2035` resolve_base_model endpoint TAKÉ hard-codes `required=True`
- Důsledek: UI hlásí error když base model chybí, ale ne vždy je potřeba
- Některé packy nemají base model (custom, controlnet, upscaler)
- Někdy jiná dependency v seznamu JE ten base model, ale systém to neví

**B) `required` field se NEPOSÍLÁ na frontend**
- `api.py:1381-1392` builduje `asset_info` dict BEZ `required` fieldu
- Frontend `AssetInfo` type v `types.ts:82-98` NEMÁ `required` field
- → Frontend nemůže rozlišit required vs optional deps

**C) Pack dependencies nemají CRUD**
- "Add" tlačítko volá `openModal('addPackDependency')` ale modal neexistuje
- "Remove" jen zobrazí toast: "Remove pack dependency via Edit modal" (`CustomPlugin.tsx:226-227`)
- Žádný backend endpoint pro přidání/odebrání
- Status se resolvuje per-pack query (N+1 problém, `CustomPlugin.tsx:63-101`)

**D) BUG: `version_match` je vždy TRUE**
- `CustomPlugin.tsx:77`: `version_match: !dep.version_constraint || true` → VŽDY TRUE
- Logická chyba - mělo být `!dep.version_constraint || someCheck`

**E) Pack model nemá duplikát validaci pro pack_dependencies**
- `models.py:892-898` validuje unikátní dep IDs
- ALE žádná validace pro duplicitní `pack_name` v `pack_dependencies`
- Žádná self-reference validace (pack nemůže záviset sám na sobě)

**F) Base model detection je fragile**
- `PackDependenciesSection.tsx:354-358` spoléhá na string matching:
  ```ts
  const isBaseModel = asset.asset_type === 'base_model' ||
    asset.asset_type === 'checkpoint' ||
    asset.name.toLowerCase().includes('base model') ||
    asset.name.toLowerCase().includes('base_checkpoint')
  ```
- Správně by mělo detekovat přes `base_model_hint` field (posílá se z backendu)

**G) resolve_pack() a plan_update() ignorují pack_dependencies**
- `pack_service.py:1080+` iteruje jen `pack.dependencies`
- `update_service.py:132+` iteruje jen `pack.dependencies`
- pack_dependencies nejsou nikde resolvovány na backendu

### 2.3 Domain Entities - Referenční přehled

```python
# === ASSET DEPENDENCY (soubor v packu) ===
class PackDependency(BaseModel):               # models.py:406-420
    id: str                                    # "main_lora", "base_checkpoint"
    kind: AssetKind                            # checkpoint, lora, vae, controlnet...
    required: bool = True                      # ⚠️ mění se v Phase 1
    selector: DependencySelector               # Jak resolvovat/stáhnout
    update_policy: UpdatePolicy                # pinned | follow_latest
    expose: ExposeConfig                       # filename + trigger_words
    description: Optional[str] = None

# === PACK DEPENDENCY (odkaz na jiný pack) ===
class PackDependencyRef(BaseModel):            # models.py:438-458
    pack_name: str                             # Jméno závislého packu
    required: bool = True                      # Povinná závislost?
    version_constraint: Optional[str] = None   # Zatím nepoužíváme

# === SELECTOR (jak najít/stáhnout soubor) ===
class DependencySelector(BaseModel):           # models.py:374-383
    strategy: SelectorStrategy                 # civitai_file, base_model_hint, local_file...
    civitai: Optional[CivitaiSelector]         # model_id, version_id, file_id
    huggingface: Optional[HuggingFaceSelector] # repo_id, filename
    base_model: Optional[str]                  # "SDXL", "SD1.5" (pro base_model_hint)
    url: Optional[str]                         # Pro url_download
    local_path: Optional[str]                  # Pro local_file
    constraints: Optional[SelectorConstraints]

# === V PACK MODELU ===
class Pack(BaseModel):                         # models.py:835-906
    dependencies: List[PackDependency] = []         # Soubory
    pack_dependencies: List[PackDependencyRef] = [] # Odkazy na packy
    base_model: Optional[str] = None                # Pack-level metadata
```

---

## 3. Implementační fáze

### Phase 1: Base Model Fix (backend + frontend) ✅ IMPL+INTEG

**Cíl:** Opravit chybné `required: true` pro base model. Umožnit smazání a přeoznačení. Přidat `required` field na frontend.

#### Backend změny:

**1a) `pack_service.py:605` → `required=False`**
- Řádek 605: změnit `required=True` na `required=False`
- Řádek 619: nechat (už je `required=False`)
- Obě větve `_create_base_model_dependency()` budou mít `required=False`

**1b) `api.py:2035` → `required=False`**
- Řádek 2035 v resolve_base_model endpoint: změnit `required=True` na `required=False`

**1c) `api.py:1381-1392` → přidat `required` field do asset_info**
- Přidat `"required": dep.required` do `asset_info` dict
- Přidat `"is_base_model": dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT`

**1d) Nový endpoint: `POST /api/packs/{name}/dependencies/{dep_id}/set-base-model`**
- Přehodí `dep.selector.strategy` → `BASE_MODEL_HINT`
- Nastaví `dep.selector.base_model` na pack.base_model (nebo parametr)
- Pokud existuje JINÁ dep s `strategy == BASE_MODEL_HINT` → odebere ji z pole (max 1 base model)
- Uloží pack → save_pack()
- Vrátí updated pack detail

**1e) DELETE jakékoliv dep (už funguje)**
- `api.py:2504-2570` už podporuje `delete_dependency=true`
- Žádná validace na required status → OK, to chceme

#### Frontend změny:

**1f) `types.ts:82-98` → přidat fieldy do AssetInfo**
```typescript
export interface AssetInfo {
  // ... existing fields
  required?: boolean          // NEW: Is this a required dependency?
  is_base_model?: boolean     // NEW: Is this the base model dependency?
}
```

**1g) `PackDependenciesSection.tsx` → suggestions UI**
- Rozdělit deps na dvě skupiny:
  - `required === true` nebo `required === undefined` → Required deps (default, nahoře)
  - `required === false` → Suggested deps (dole, jiný styling)
- Suggested deps: lehčí barva, "Suggested" badge, nezorazují error icon
- Detekovat base model přes `is_base_model` field (ne string matching!)
- Přidat "Set as base model" akci pro checkpoint deps (volá nový endpoint)
- Delete funguje na všech deps (včetně base model)

#### Testy:
- [x] Backend: import vytvoří base model s `required: false` (8/8 tests pass)
- [x] Backend: set-base-model přehodí strategy a smaže starou
- [x] Backend: `required` field je v API response
- [x] Frontend: suggestions se zobrazí odděleně (AssetRow, divider, Optional badge)
- [x] `tests/store/test_base_model_fix.py` - 8 testů

**⚠️ Opatrnost:**
- Neměnit chování existujících `required: true` deps (LoRA, VAE atd.)
- Jen base_model_hint deps importované z Civitai
- Existující packy s `required: true` base model → nechat (ne migrace)
- `PackDependenciesSection.tsx` dostává props z parent → změny jen v renderování

---

### Phase 2: Pack Dependencies CRUD (backend + frontend) ✅ IMPL+INTEG

**Cíl:** Zprovoznit přidávání a odebírání pack dependencies. Jednoduché - pack dep je jen agregátor: "potřebuji tento pack".

#### Backend změny:

**2a) `models.py` → validátor pro pack_dependencies** ✅
- Přidán `validate_unique_pack_deps()` model_validator na Pack model (models.py:901-908)
- Kontrola: žádné duplicitní `pack_name` v `pack_dependencies`
- Kontrola: self-reference (pack nemůže záviset sám na sobě)

**2b) `api.py` → 3 nové endpointy:** ✅

```
GET  /api/packs/{name}/pack-dependencies/status   (api.py:2639-2667)
POST /api/packs/{name}/pack-dependencies           (api.py:2681-2715)
DELETE /api/packs/{name}/pack-dependencies/{dep}    (api.py:2725-2758)
```

**GET status:** Batch resolve, vrací `List[{ pack_name, required, installed, version? }]`
**POST add:** Body `{ pack_name, required }`, self-ref + duplicate check
**DELETE remove:** Filter by pack_name, 404 if not found

#### Frontend změny:

**2c) `AddPackDependencyModal.tsx` - NOVÝ soubor** ✅
- Searchable seznam packů, required/optional toggle
- Odfiltruje current pack a already-added packs
- `apps/web/src/components/modules/pack-detail/modals/AddPackDependencyModal.tsx`

**2d) `CustomPlugin.tsx` → napojení** ✅
- Nahrazeny N+1 per-pack queries batch GET endpointem
- Add mutation (POST) s AddPackDependencyModal
- Remove mutation (DELETE) s confirm dialogem
- Opraven bug `version_match: !dep.version_constraint || true` → `version_match: s.installed`
- `renderExtraSections` vždy zobrazí PackDependenciesSection (i bez existujících deps)
- Empty state s Add tlačítkem pro první dependency

**2e) i18n klíče** ✅
- `pack.plugins.custom.depAdded/depRemoved/confirmRemove` (en + cs)
- `pack.packDependencies.searchPlaceholder/noMatch/noPacks/required/addButton` (en + cs)

#### Testy:
- [x] Backend: Pack model validator (unique names, self-reference) - 7 testů
- [x] Backend: CRUD logic (add, remove, status resolution) - 9 testů
- [x] Backend: Save/load roundtrip - 2 testy
- [x] `tests/store/test_pack_dependencies.py` - 18 testů, all passing

**⚠️ Opatrnost:**
- `CustomPlugin.tsx` PackDependenciesSection už funguje pro zobrazení
- Nepřepisovat renderovací logiku, jen napojit na skutečné API
- `PackDependencyRow` component zůstává jak je

---

### Phase 3: Updates + Dependency Impact ✅ IMPL+INTEG

**Cíl:** Při updatu packu ukázat jaké jiné packy na něm závisí. Jednoduchý impact analysis.

#### Backend změny:

**3a) `models.py:1166-1172` → rozšířit UpdatePlan** ✅
- Přidán `impacted_packs: List[str] = Field(default_factory=list)`

**3b) `update_service.py` → `_find_reverse_dependencies()` + scan v `plan_update()`** ✅
- Nová metoda `_find_reverse_dependencies(pack_name)` - O(n) scan všech packů
- Volána v obou return paths `plan_update()` (s lock i bez lock)
- Výsledky sorted alphabetically

#### Frontend změny:

**3c) `CivitaiPlugin.tsx` → impacted packs info box** ✅
- Blue info box v update details section (po changes a ambiguous)
- Layers icon + "N pack(s) depend on this model"
- Clickable pack name links to `/pack/{name}`
- Non-blocking - jen informace

**3d) Frontend types + i18n** ✅
- `plugins/types.ts` UpdatePlan: přidán `impacted_packs: string[]`
- i18n: `pack.plugins.civitai.impactedPacks` (EN + CS s plural forms)

#### Testy:
- [x] Unit: UpdatePlan model (5 testů) - defaults, serialization, backward compat
- [x] Unit: `_find_reverse_dependencies()` (7 testů) - no deps, single, multiple, self-exclude, indirect, sorted
- [x] Integration: `plan_update()` with impacts (4 testy) - includes, empty, multiple, up-to-date
- [x] Smoke: API response format (4 testy) - JSON, empty, full response, backward compat
- [x] `tests/store/test_update_impact.py` - 20 testů, all passing

**⚠️ Opatrnost:** `update_service.py` je 550 řádků fungujícího kódu. Přidáváme, neměníme.

---

### Phase 4: UI Polish & Consistency ✅ IMPL+INTEG

**Cíl:** Sjednotit UX obou typů dependencies. Enriched data, pack dep cards, dependency tree.

#### Backend:
- [x] `asset_info` enriched: `trigger_words`, `update_policy`, `strategy` fields
- [x] `pack-dependencies/status` enriched: `pack_type`, `description`, `asset_count`, `trigger_words`, `base_model`, `has_unresolved`, `all_installed`
- [x] New endpoint: `GET /api/packs/{name}/dependency-tree?max_depth=5` - recursive tree with cycle detection

#### Frontend:
- [x] Extracted `PackDepsSection.tsx` from `CustomPlugin.tsx` inline code
- [x] Rich pack dep cards with status-colored borders (matching AssetRow style)
- [x] `DependencyTree.tsx` - CSS tree visualization with expand/collapse, cycle detection
- [x] Asset deps: trigger words pills (click-to-copy), update policy badge, strategy info
- [x] `CivitaiPlugin.tsx` also renders `PackDepsSection`
- [x] Full i18n coverage (en + cs)

#### Bugfixy nalezené během review:
- [x] `api.py:2663` `store.layout.load_lock()` → `store.layout.load_pack_lock()` (enriched status vracal vždy `installed: False`)
- [x] `models.py:618` přidán `"upscale_by": "hires_scale"` do hires_fix normalizer (AI cache fix)
- [x] `test_inventory_stabilization.py` - 2 code structure testy opraveny pro i18n (hardcoded stringy → i18n klíče)

#### Testy:
- [x] `tests/store/test_dependency_tree.py` - 25 integration testů s reálným Store (tree, enriched status, asset_info)
  - Tree: empty, single child, missing, multiple, circular A→B→A, three-way cycle, diamond, deep chain, max_depth, trigger words, metadata, response shape
  - Enriched status: installed fields, missing defaults, mixed, response shape, trigger aggregation
  - Asset info: trigger words, update policy, strategy, full dict shape
- [x] `tests/store/test_dependencies_integration.py` - 7 nových Phase 4 testů (enriched status, asset info roundtrip, tree smoke)

---

### ~~Phase 5: Smart Resolution~~ → MOVED to PLAN-Resolution.md

**Status:** Moved to dedicated plan. See `plans/PLAN-Resolution.md` for:
- Local model scanning & matching
- Avatar-engine AI recommendations
- Auto-detect dependencies from descriptions
- Download orchestration

---

## 4. Soubory které se mění (per phase)

### Phase 1 (Base Model Fix)
```
MODIFY  src/store/pack_service.py:605         # required=True → required=False
MODIFY  src/store/api.py:2035                 # required=True → required=False (resolve endpoint)
MODIFY  src/store/api.py:1381-1392            # Přidat required + is_base_model do asset_info
MODIFY  src/store/api.py                      # Nový POST endpoint set-base-model
MODIFY  apps/web/.../types.ts:82-98           # Přidat required + is_base_model do AssetInfo
MODIFY  apps/web/.../PackDependenciesSection.tsx  # Suggestions UI, base model detection
ADD     tests/store/test_base_model_fix.py    # Nové testy
```

### Phase 2 (Pack Deps CRUD)
```
MODIFY  src/store/models.py:892+              # validate_unique_pack_deps() validátor
MODIFY  src/store/api.py                      # 3 nové endpointy (GET status, POST, DELETE)
ADD     apps/web/.../AddPackDependencyModal.tsx  # Nový modal
MODIFY  apps/web/.../CustomPlugin.tsx:63-227  # Status batch, Remove akce, version_match fix
ADD     tests/store/test_pack_dependencies.py
```

### Phase 3 (Updates Impact)
```
MODIFY  src/store/models.py:1156-1161         # UpdatePlan + impacted_packs
MODIFY  src/store/update_service.py           # Reverse dependency scan v plan_update()
MODIFY  apps/web/.../CivitaiPlugin.tsx:215+   # Impact info box
ADD     tests/store/test_update_impact.py
```

### Phase 4 (UI Polish & Consistency)
```
MODIFY  src/store/api.py                      # Enrich asset_info, pack-deps/status, new tree endpoint
MODIFY  apps/web/.../pack-detail/types.ts     # AssetInfo new fields
MODIFY  apps/web/.../plugins/types.ts         # PackDependencyStatus new fields
ADD     apps/web/.../sections/PackDepsSection.tsx  # Extracted from CustomPlugin
MODIFY  apps/web/.../plugins/CustomPlugin.tsx  # Use PackDepsSection
MODIFY  apps/web/.../plugins/CivitaiPlugin.tsx # Add PackDepsSection
MODIFY  apps/web/.../sections/PackDependenciesSection.tsx  # Trigger words, badges
ADD     tests/store/test_dependency_tree.py
MODIFY  apps/web/src/i18n/locales/en.json     # New i18n keys
MODIFY  apps/web/src/i18n/locales/cs.json     # New i18n keys
```

---

## 5. Audit Findings Summary (v0.5.0)

### Backend Audit
| Finding | Severity | Phase |
|---------|----------|-------|
| `pack_service.py:605` base model `required=True` | 🔴 HIGH | Phase 1 |
| `api.py:2035` resolve endpoint `required=True` | 🔴 HIGH | Phase 1 |
| `api.py:1381-1392` missing `required` in response | 🔴 HIGH | Phase 1 |
| No pack_dependencies CRUD endpoints | 🔴 HIGH | Phase 2 |
| No `validate_unique_pack_deps()` on Pack model | 🟡 MED | Phase 2 |
| `resolve_pack()` ignores pack_dependencies | 🟡 MED | Phase 2 (info only) |
| `plan_update()` ignores pack_dependencies | 🟡 MED | Phase 3 |
| `UpdatePlan` missing `impacted_packs` | 🟡 MED | Phase 3 |
| `UpdatePackRequest` omits deps fields | ℹ️ OK | Not needed - dedicated endpoints |

### Frontend Audit
| Finding | Severity | Phase |
|---------|----------|-------|
| `AssetInfo` missing `required` field | 🔴 HIGH | Phase 1 |
| Base model detection via string matching | 🟡 MED | Phase 1 |
| `CustomPlugin.tsx:77` version_match always TRUE | 🟡 MED | Phase 2 |
| Pack dep Remove not implemented | 🟡 MED | Phase 2 |
| Pack dep Add modal doesn't exist | 🟡 MED | Phase 2 |
| N+1 per-pack status queries | 🟡 MED | Phase 2 |

---

## 5b. Domain Audit Findings (2026-05-02)

Z `plans/audits/DOMAIN-AUDIT.md` + `plans/audits/codex-domain-audit.md`. Tyto nálezy
**nejsou pokryté** v Phase 1-4 (které jsou DONE) — jsou to **nové body k rozhodnutí
před Release 1**.

### H4 [HIGH] — `pack_dependencies` nikdy expandované do view planu

**Finding:** `Pack.pack_dependencies: List[PackDependencyRef]` (`models.py:837`) deklaruje,
že pack potřebuje jiné packy. Existuje API endpoint pro CRUD, dependency-tree endpoint
(Phase 2), a UI pro ně. Ale **`ViewBuilder.compute_plan()` je úplně ignoruje** — když pak
profile aktivujete, runtime view neobsahuje assety z required pack deps.

**Důsledek:** Uživatel přidá `pack_dependencies: [SDXL-base]` na svůj LoRA pack, deklaruje
"tento LoRA potřebuje SDXL base". Profile s tímto LoRA packem se aktivuje, ale ComfyUI
nedostane SDXL base do `extra_model_paths.yaml`. Uživatel musí přidat SDXL pack do profilu
**zvlášť**, takže `pack_dependencies` slouží pouze jako informace pro UI.

**Recommendation — vyžaduje rozhodnutí majitele (Open Question #1 z auditu):**

Volba A — **operational**: `ViewBuilder.compute_plan()` rekurzivně expanduje
`pack_dependencies` a vloží jejich assety do view planu. Vyřeší cykly přes already-visited
set. Required deps jsou vždy expandované; optional deps jen pokud user explicitně.

Volba B — **informational**: Přejmenovat na `related_packs` nebo `recommended_packs`,
přidat do UI banner "Tento pack doporučuje také: ...". Žádné runtime side-effects.

**Severity:** HIGH (current state je ambivalentní — half-implemented operational behavior)
**Refs:** `models.py:837 Pack.pack_dependencies`, `view_builder.py compute_plan()`,
DOMAIN-AUDIT Section 4 + 6.

### H5 [HIGH] — `version_constraint` nikdy enforcovaný

**Finding:** `PackDependencyRef.version_constraint: Optional[str]` (`models.py:438`) má
nést sémantickou constraint (`>=1.0`, `~2.x`, atd.), ale **žádný kód v `src/store/` ji
nečte ani nevalidate**. `grep -r version_constraint src/store/` vrátí jen modelovou definici
a serializaci.

**Důsledek:** User napíše `version_constraint: ">=2.0"`. Uloží se. Při resolve/install se
ignoruje. Žádný error, žádný warning, žádné vynucení.

**Recommendation:** Buď enforce v `resolve_pack()` (parse constraint, porovnat s lock
version, fail/warn pokud mismatch), nebo **odstranit pole** a deferrovat sémantický
versioning na pozdější release. Aktuální stav ("model říká, že to umíme, kód to neumí") je
horší než žádné pole.

**Severity:** HIGH (silent failure mode)
**Refs:** `models.py:438`, DOMAIN-AUDIT Section 4.

### L2 [LOW] — `DependencySelector` discriminated union

**Finding:** `DependencySelector` má 6 Optional polí (`civitai_*`, `hf_*`, `local_path`, `url`)
+ `strategy: SelectorStrategy` enum. Některé kombinace jsou neplatné (Civitai strategy
+ chybějící civitai_*). Discriminated union per strategy by tohle compile-time vyloučil.

**Recommendation:** Refactorovat na Pydantic discriminated union (Tagged unions s `Literal`
discriminator). Detail v DOMAIN-AUDIT Section 13 → "Make Selectors Self-Validating".

**Severity:** LOW (current Pydantic v2 model_validator pokrývá runtime, ale typecheck
nepomáhá)

---

## 6. Related Plans

- **🔗 PLAN-Updates.md** - Phase 3 propojuje dependency impact s update systémem. Po dokončení Phase 1-3 pokračujeme na Updates UI vylepšení (bulk updates, update options dialog).
- **🔗 PLAN-Resolution.md** - Smart Resolution (extracted from Phase 5). Local scanning, AI recommendations, download orchestration.
- **🔗 PLAN-Release-1-Roadmap.md** — distribuce všech audit findings.
- **🔗 plans/audits/DOMAIN-AUDIT.md + codex-domain-audit.md** — full audit detail.

---

## 7. Open Questions

| Question | Status |
|----------|--------|
| ~~Base model required?~~ | ✅ RESOLVED - `required: false`, smazatelný |
| Version constraints syntax? | ODLOŽENO - zatím nepoužíváme |
| ~~Circular dependency detection?~~ | ✅ RESOLVED - Phase 2: self-reference + duplicity validátor. Phase 4: recursive per-branch cycle detection v dependency-tree endpointu |
| ~~Smart model matching?~~ | ✅ MOVED - viz `PLAN-Resolution.md` |
| Migration starých packů? | ROZHODNUTO - nechat `required: true`, jen nové importy budou `false` |

---

## Changelog

### 2026-02-19 - v0.8.1: Review, bugfixes, integration tests
- ✅ Bugfix: `api.py:2663` `load_lock()` → `load_pack_lock()` - enriched status endpoint vracal vždy `installed: False`
- ✅ Bugfix: `models.py` hires_fix normalizer chyběl `"upscale_by"` mapping (Gemini AI cache)
- ✅ Bugfix: 2 code structure testy opraveny pro i18n migrace
- ✅ Testy přepsány: z 18 unit testů (duplikovaná logika) na 25 integračních testů s reálným Store
- ✅ Přidáno 7 nových Phase 4 integration/smoke testů do test_dependencies_integration.py
- ✅ Celkově: 818 passed, 0 failed, 7 skipped

### 2026-02-19 - v0.8.0: Phase 4 complete + Phase 5 moved
- ✅ Phase 4: UI Polish & Consistency
- ✅ Backend: enriched asset_info (trigger_words, update_policy, strategy), enriched pack-deps/status, dependency-tree endpoint
- ✅ Frontend: PackDepsSection extraction (CustomPlugin ~550→175 lines), rich status-colored cards, DependencyTree (inline in PackDepsSection.tsx), trigger words pills, update policy badges
- ✅ Phase 5 moved to dedicated PLAN-Resolution.md
- ✅ Full i18n coverage (en + cs)

### 2026-02-19 - v0.7.0: Phase 3 complete
- ✅ Phase 3: Updates + Dependency Impact
- ✅ UpdatePlan.impacted_packs field + _find_reverse_dependencies() scan
- ✅ CivitaiPlugin: blue info box with clickable pack links
- ✅ 20 nových testů (unit + integration + smoke), all passing
- ✅ Backward compatible (default=[])

### 2026-02-19 - v0.6.0: Phase 1 + Phase 2 complete
- ✅ Phase 1: Base Model Fix - `required: false`, `is_base_model` field, set-base-model endpoint, suggestions UI
- ✅ Phase 2: Pack Dependencies CRUD - model validator, 3 API endpoints, AddPackDependencyModal, CustomPlugin refactor
- ✅ 26 nových testů (8 base model + 18 pack deps), all passing
- ✅ TypeScript + frontend testy OK

### 2026-02-19 - v0.5.0: Deep audit + implementační detaily
- ✅ Kompletní backend audit: models, pack_service, api, update_service
- ✅ Kompletní frontend audit: types, PackDependenciesSection, CustomPlugin, CivitaiPlugin, modals
- ✅ Nalezeny nové problémy: api.py:2035 (druhé místo s required=True), missing `required` v API response
- ✅ Nalezeny frontend bugy: version_match always true, fragile base model detection
- ✅ Konkrétní řádkové reference pro každou změnu
- ✅ Detailní implementační pokyny per-phase
- ✅ Audit findings summary tabulka
- ✅ Rozhodnuto: žádná migrace starých packů

### 2026-02-19 - v0.4.0: Finální struktura, jasné fáze
- ✅ Zjednodušen přístup: pack deps = jednoduchý agregátor, bez version constraints
- ✅ 5 jasných fází s konkrétními soubory a úkoly
- ✅ Phase 1: Base model fix (nejdříve opravit co je špatně)
- ✅ Phase 2: Pack deps CRUD (zprovoznit základní operace)
- ✅ Phase 3: Updates impact (propojení s update systémem)
- ✅ Phase 4-5: Future (UI polish, smart resolution, avatar-engine)
- ✅ Referenční přehled domain entities
- ✅ Poznámky opatrnosti u každé fáze (co nerozbít)
- ✅ Odloženy version constraints a dependency tree (overengineering pro teď)

### 2026-02-19 - v0.3.0: Base Model Validation
- Popsán zásadní doménový problém base model `required: true`
- Řešení bez nových fieldů

### 2026-02-17 - v0.2.0: Aktualizace na skutečný stav
- Zmapovány skutečné modely, API, frontend

### 2026-02-03 - v0.1.0
- Initial draft

---

*Created: 2026-02-03*
*Last Updated: 2026-02-19*
