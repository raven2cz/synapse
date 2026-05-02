# PLAN: Custom Pack — Release 1 Stabilization

**Verze:** v0.3.0 (cross-cutting concerns: rename, backup, i18n, rate limiting)
**Status:** 🟡 PLANNING — vlastník odpověděl 2026-05-02, plán napsán Claude Opus 4.7, auditováno Codex GPT-5.5 high, rozšířeno o integration concerns
**Vytvořeno:** 2026-05-02
**Branch:** `stabilization/release-1`
**Autor:** raven2cz + Claude Opus 4.7 + Codex GPT-5.5 (audit)

---

## ⚠️ Před implementací

1. **Zítra (2026-05-03)** přepnout na `feat/resolve-model-redesign` a ověřit, že nálezy v tomto plánu nejsou už vyřešené.
2. **Codex audit** tohoto plánu PŘED commitem implementace.
3. **3-model review** po každé fázi (Claude + Gemini + Codex).
4. **Multi-model komunikace** — viz `MEMORY.md` pravidlo #8.

---

## 1. Cíl

Dotáhnout **Custom Pack** pro Release 1 podle vlastníkových use-cases a oprav nálezů
z duálního auditu (`plans/audits/CONSOLIDATED-FINDINGS.md` Bod 2 + `DOMAIN-AUDIT.md`).

Tento plán **navazuje** na `PLAN-Pack-Edit.md` (status "complete") — ale ten plán
má díry, které tento plán řeší.

---

## 2. Use Cases (od vlastníka 2026-05-02)

> *"Custom packs v podstate je takovy agregator a hlavne je dosti svobodny, protoze
> neni vazan na zadny online zdroj, takze uzivatel si jej muze velmi customizovat."*

### Co custom pack umí být

1. **Aggregator** — sdružuje věci, které logicky patří k sobě.
2. **Volný popis** — žádný online zdroj, user kontroluje vše.
3. **Multiple model dependencies** — checkpoint, LoRA, VAE, embeddings, atd. (různé providery).
4. **Pack dependencies** — referencuje jiné packy jako celky (např. base SDXL pack + 3 LoRA packy).
5. **Workflow attachment** — připojí existující workflow které vše používá.
6. **User-vytvořený obsah** — videa a obrázky, které user vytvořil pomocí packu.
7. **Import/export** — sdílení s ostatními uživateli, **decodable i bez aplikace** (částečně).
8. **Parametry** — primárně skrze sub-models a workflow, custom pack jen agreguje.

---

## 3. Korekce předchozích claims (KRITICKÉ!)

`CONSOLIDATED-FINDINGS.md` Bod 2 v původní verzi obsahuje **chybný claim**:

> ❌ "Modaly EXISTUJÍ ale jsou ukryté: EditDependenciesModal, DescriptionEditorModal,
>    EditPreviewsModal, EditPackModal. Komponenty jsou napsané, ale PackDetailPage
>    je nerendruje (edit mode není zapojen)."

### Co je realita podle kódu (verifikováno 2026-05-02)

| Modal | Stav | Trigger v UI |
|-------|------|--------------|
| `EditPackModal` | ✅ rendered `PackDetailPage.tsx:468` | Per-section "Edit" button (User Tags) |
| `EditPreviewsModal` | ✅ rendered `PackDetailPage.tsx:527` | Gallery edit button |
| `DescriptionEditorModal` | ✅ rendered `PackDetailPage.tsx:571` | Description edit button |
| `AddPackDependencyModal` | ✅ rendered `PackDepsSection.tsx:541` | "Add pack dep" button |
| `BaseModelResolverModal` | ✅ rendered, použit i v Civitai packs | Resolve flow |
| `EditDependenciesModal` (asset-level) | ❌ exportován, **nikde nepoužíván** | — |

`PackDetailPage.tsx:309-314` má v kódu **explicitní komentář** o per-section edit
designu (modaly otevřené z konkrétních sekcí, ne globální edit toggle).

**Co je SKUTEČNĚ rozbité:**

1. ❌ `EditDependenciesModal` (asset-level) je orphan (řešení: čekat na BOD 1 → nahradit `DependencyResolverModal`).
2. ❌ Empty state CTAs chybí — sekce s prázdným obsahem se nerendrují.
3. ❌ Pack-to-pack deps není rekurzivně expandované do view planu (DOMAIN-AUDIT H4).
4. ❌ Pack dep nav link `/pack/{name}` místo `/packs/{name}`.
5. ❌ Custom pack export/import flow neexistuje (je to nová feature).
6. ❌ Update flow pro custom packy s online deps není definovaný.

**Tento plán řeší body 1-6 + nové use-cases (user gallery, workflow attach).**

---

## 4. Decision Table — odpovědi vlastníka (2026-05-02)

| # | Otázka | Volba | Implementace |
|---|--------|-------|--------------|
| Q1 | Arbitrary model deps v R1? | **A — Ano** | Phase 4 (čeká na BOD 1) |
| Q2 | Create wizard rovnou s deps? | **B — jednoduchý wizard, ad-hoc edit** | Phase 1 — empty state CTAs |
| Q3 | Auto-add do globálního profilu? | **A — Ano** (`use(pack)` recursive) | Phase 3 |
| Q4 | `pack_dependencies` operational? | **A required / B optional** | Phase 3 |
| Q5 | `use(pack)` recursive expansion? | **per Q4 — required ano, optional ne** | Phase 3 |
| Q6 | Optional deps automatic? | **per Q4 — banner only** | Phase 3 + UI |
| Q7 | `version_constraint` enforce? | **B — UI info only, žádné enforcement** | Phase 8 (cleanup) |
| Q8 | `FOLLOW_LATEST` Civitai deps? | **A — Ano** | Phase 5 (per-dep update) |
| Q9 | Custom pack updatable? | **A — per-dep, ne pack-level** | Phase 5 |
| Q10 | Export bundle scope? | **C2 default, C3 opt-in (--include-weights)** | Phase 6 |
| Q11 | `EditDependenciesModal`? | **B — wait for BOD 1, replace with `DependencyResolverModal`** | Phase 4 (deferred) |
| Q12 | Empty sekce vždy renderovat? | **A — Ano pro editable** | Phase 1 |
| Qx-A | User gallery? | **A2 — separátní `pack.user_gallery` + ikona** | Phase 2 |
| Qx-B | Embedded workflow? | **B1 — copy** | Phase 7 |
| Qx-C | Export scope? | **C2 + opt C3** | Phase 6 |
| Qx-D | Delete cascade? | **D4 — dumb delete (jen metadata)** | Phase 8 |
| Qx-E | Version bump? | **E1 — manual only** | Phase 8 |

---

## 5. Implementační fáze

### Phase 0 — Preflight: `pack_path` → `pack_dir` rename (DOMAIN-AUDIT H1)

**Status:** 🔴 BLOCKER — bez tohoto fixu `create_pack` a další API endpointy
crashnou. **MUSÍ být první**, blokuje všechny ostatní fáze.

**Files:** `src/store/api.py` lines 3334, 3424, 4078, 4581, 4739, 4790, 4859, 4958.

**Akce:**
1. Find/replace `store.layout.pack_path(` → `store.layout.pack_dir(` (mechanický rename).
2. Verifikace: `rg "pack_path\(" src/store` musí vrátit **0 hits**.
3. Spustit existující test suite — žádné regrese.

**Akceptační kritéria:**
- [ ] `rg "pack_path\(" src/store/` = 0 výsledků
- [ ] `./scripts/verify.sh --backend --quick` projde
- [ ] Manual smoke: vytvořit nový custom pack přes API, ověřit že neselhává

**Risk:** LOW (mechanický rename), ale **CRITICAL severity** — blokuje vše ostatní.

**Codex audit:** [Finding #1] povýšeno z Phase 8.5 sem na základě konsekvencí.

---

### Phase 1 — Empty State CTAs (must-have foundation)

**Cíl:** Editable custom packs zobrazují empty state s "Add first X" CTA, aby user
měl odkud začít.

**Backend changes:** 0 (pure frontend).

**Frontend changes:**

| Soubor | Co změnit |
|--------|-----------|
| `apps/web/src/components/modules/pack-detail/sections/PackInfoSection.tsx:315` | Místo `return null` render empty state s `onEditDescription` CTA pokud je `editable` |
| `apps/web/src/components/modules/pack-detail/sections/PackInfoSection.tsx:99,134,219` | Stejný pattern pro TriggerWords, ModelInfo, Description sub-cards |
| `apps/web/src/components/modules/PackDetailPage.tsx:327` | Odstranit `pack.previews?.length > 0` gate, render `PackGallery` vždy s onEdit |
| `apps/web/src/components/modules/pack-detail/sections/PackGallery.tsx` | Přidat empty state UI s "Add first preview" |
| `apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:281` | Empty state pro params |
| `apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx` (TreeView) | Empty state pro pack-deps tree |

**Plugin gate (Codex Finding #10):** Empty state CTA viditelná pouze když:
```ts
const canShowCta =
  pack.pack_category === 'custom'
  && plugin.id === 'custom'
  && plugin.features.canEditX === true;
```

**Důvod:** Současný `CivitaiPlugin` má `canEditMetadata`/`canEditPreviews`/`canEditWorkflows`/
`canEditParameters = true`, a `CustomPlugin` slouží i jako fallback pro neznámé packy.
Pouhé spoléhání na `plugin.features` by aktivovalo CTAs i pro Civitai packy nebo
fallback packy s neznámým category.

**Akceptační kritéria:**
- Empty state CTA se renderuje jen pro `pack.pack_category === 'custom'` packy.
- Civitai packy (`pack_category === 'external'`, `plugin.id === 'civitai'`) zůstávají
  beze změny — žádné nové CTAs.
- Fallback packy bez explicitního pluginu **nedostanou** CTAs.
- Přidán nový feature flag `canEditUserGallery` do `PluginFeatures` interface,
  default `false`, pro `CustomPlugin` `true`.

**Codex audit:** [Finding #10] HIGH — gating přepsán z `plugin.features` only na
explicit `pack_category + plugin.id + features` triple-check.

**Komponenta:** Vytvořit reusable `<EmptySectionState>` komponentu:
```tsx
<EmptySectionState
  icon={<Plus />}
  title={t('pack.empty.description.title')}
  description={t('pack.empty.description.body')}
  ctaLabel={t('pack.empty.description.cta')}
  onCta={onEditDescription}
/>
```
(NEW: `apps/web/src/components/modules/pack-detail/sections/EmptySectionState.tsx`)

**i18n:** Přidat empty.* klíče do `apps/web/src/i18n/locales/{cs,en}/translation.json`.

**Testy:**
- Vitest: `EmptySectionState` render variants
- Vitest: `PackInfoSection` empty state s `onEditDescription` propem
- Vitest: `PackGallery` empty state visibility podle plugin features
- Manual UX test: vytvořit nový custom pack, ověřit všechny empty state CTAs

**Risk:** LOW (pure UI, žádné backend změny).

---

### Phase 2 — User Gallery (`pack.user_gallery` field)

**Cíl:** Separátní field `Pack.user_gallery` pro user-vytvořené images/videa
(distinct od `Pack.previews` které jsou Civitai-imported).

**Schema strategy (Codex Finding #3) — Pack v3 BUMP s read backward compat:**
- Nové writes: `schema: synapse.pack.v3` (nový default).
- Existing reads: `synapse.pack.v2` packs jsou **stále akceptované** přes
  `Field(default_factory=list)` na `user_gallery`. Pydantic je naloaduje s prázdným
  galery a po prvním save se přepíšou na v3.
- Žádný migration script v této fázi — declarative-only, jako u v1→v2.
- Tests:
  - `test_load_v2_pack_without_user_gallery_field` — load v2 JSON, expect `user_gallery == []`
  - `test_save_v2_pack_writes_v3` — load v2, save, re-read → `schema == "synapse.pack.v3"`
  - `test_load_v3_pack_with_user_gallery` — load v3 JSON s itemy, expect správné objekty

**Backend changes:**

```python
# src/store/models.py — nová třída

class UserMedia(BaseModel):
    """User-uploaded media for a custom pack (videos / images created by user)."""
    schema_: str = Field(default="synapse.user_media.v1", alias="schema")
    id: str  # UUID4 (server-generated, NEVER trusted from imports)
    filename: str  # sanitized: alnum + . - _ only, no /, \, ..
    media_type: Literal["image", "video"]
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: int
    sha256: str
    caption: Optional[str] = None
    created_at: datetime
    nsfw_level: NsfwLevel = NsfwLevel.NONE
    # NOTE: NO `relative_path` field — path is DERIVED, not persisted.
    # See Codex Finding #4 below.

class Pack(BaseModel):
    schema_: str = Field(default="synapse.pack.v3", alias="schema")
    # ... existing fields ...
    user_gallery: List[UserMedia] = Field(default_factory=list)
    # v2 reads accepted (defaults to []), writes always v3
```

**Codex Finding #4 — Path je DERIVED, ne persisted:**
- `relative_path` field **odstraněn** z `UserMedia` modelu.
- Cesta se počítá runtime: `state/packs/<pack-name>/user_media/<id>/<sanitized_filename>`.
- Důvod: persistovat path znamená trust user input napříč boundaries (export/import bundle).
  Útočník by mohl podvrhnout `relative_path: "../../../etc/passwd"`.
- Helper: `UserMediaService.get_path(pack_name, item) -> Path` — vždy reconstructed.
- Validace na `filename`: regex `^[a-zA-Z0-9._-]+$`, max 255 chars, no leading dot.

**File storage:** `state/packs/<pack-name>/user_media/<id>/<filename>` —
ID-prefixed adresář aby se předešlo filename kolizím.

**API endpointy (NOVÉ):**

| Endpoint | Metoda | Popis |
|----------|--------|-------|
| `/api/packs/{pack}/user-media` | POST | Upload single file (multipart) |
| `/api/packs/{pack}/user-media/{id}` | DELETE | Smaž jeden item |
| `/api/packs/{pack}/user-media/{id}` | PATCH | Upravit caption / nsfw_level |
| `/api/packs/{pack}/user-media/{id}/file` | GET | Stream file content |
| `/api/packs/{pack}/user-media/reorder` | POST | Změnit pořadí (`{ids: [...]}`) |

**Backend služba:** `src/store/user_media_service.py` (NEW):
- `upload(pack_name, file, caption=None) -> UserMedia` — sha256, store, append to pack
- `delete(pack_name, id) -> None`
- `update(pack_name, id, **fields) -> UserMedia`
- `reorder(pack_name, ids) -> None`
- `get_path(pack_name, item) -> Path` — derived path, always reconstructed
- Validace (Codex Finding #6 — content-based MIME):
  - file size: max 100 MB per file, max 5 GB per pack soft limit
  - **Magic-byte sniffing**: použít `python-magic` (libmagic) NEBO custom check signatur
  - whitelist content types: `image/jpeg`, `image/png`, `image/webp`, `image/gif`,
    `video/mp4`, `video/webm`, `video/quicktime`
  - **Extension agreement**: detekovaný MIME musí matchovat příponě (`.jpg` → `image/jpeg`)
  - Decode dimensions (PIL pro images, ffprobe pro videa) — odmítnout pokud decode fails
  - filename sanitization: regex `^[a-zA-Z0-9._-]+$`, leading dot rejected, max 255 chars
  - reject polyglot files (např. file který je validní zip i jpeg)

**Frontend changes:**

| Soubor | Co změnit |
|--------|-----------|
| `apps/web/src/components/modules/pack-detail/sections/PackUserGallerySection.tsx` (NEW) | Distinct sekce, vlastní header "My Gallery" |
| `apps/web/src/components/modules/pack-detail/modals/AddUserMediaModal.tsx` (NEW) | Upload modal s drag-and-drop |
| `apps/web/src/components/modules/pack-detail/sections/PackGallery.tsx` | Přidat ikonku rozdílu "uploaded by me" pro `Pack.user_gallery` items (pokud chce vlastník zobrazit dohromady — viz UX rozhodnutí) |
| `apps/web/src/components/modules/PackDetailPage.tsx` | Wire `PackUserGallerySection` |
| `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts` | Add `uploadUserMedia`, `deleteUserMedia`, `updateUserMedia` mutations |

**UX:** Sekce je zobrazena pod `PackGallery` (Civitai previews), s vlastním headerem
"Co jsem vytvořil" / "What I made" + upload button. Distinct vizuální styl
(border accent, ikona kamery).

**Plugin gate:** Sekce viditelná jen pokud `plugin.features.canEditUserGallery === true`
(přidat nový feature flag do `CustomPlugin.tsx`).

**Testy:**
- Unit: `UserMediaService.upload()` — sha256 dedup, file validation, error paths
- Unit: `UserMediaService.delete()` — file removed from disk + pack updated
- Integration: full upload → list → delete cycle přes API
- Smoke: real file upload, served via GET endpoint
- Vitest: `PackUserGallerySection` render with empty state + with items
- Vitest: `AddUserMediaModal` upload flow

**Risk:** MEDIUM (file I/O, security — filename sanitization, MIME validation,
zip slip prevention pokud někdo uploaduje archive).

---

### Phase 2.5 — Cross-cutting Integration (rename, backup, inventory, rate limiting)

**Cíl:** User-facing chování `pack.user_gallery` musí být **identické** jako Civitai
`pack.previews` z perspektivy persistence, backup, inventory a rename.

**Vlastníkův záměr (2026-05-02):**

> *"porad se to chova stejne jako images a videos, co je git!"*

User media je **git-versioned content** v `state/packs/<pack>/`, NE content-addressed
blob. Tato fáze tu identitu explicitně zafixuje.

#### 2.5.1 Pack rename support

**Behavior:**
- `PATCH /api/packs/{pack}` rename → adresář `state/packs/<old>/` přejmenovat na
  `state/packs/<new>/`. User media files **putují s ním**, žádný kopír.
- `pack.user_gallery[].id` (UUID4) zůstává **immutable** přes rename — žádné
  field updates v JSON.
- `UserMediaService.get_path(pack_name, item)` rekonstruuje cestu z **aktuálního**
  `pack.name`, takže rename je transparent.
- Frontend cache invalidation: po rename invalidovat user-media query keys
  (`['userMedia', oldName]` → `['userMedia', newName]`).

**Verifikace existing logiky:**
- [ ] `PackService.rename_pack()` už dělá adresář move (existing — verify)
- [ ] Test: rename custom pack s 3 user_media items → all 3 files dostupné na new path
- [ ] Test: pack.json `user_gallery` items zachovají id, sha256, filename

#### 2.5.2 Backup integration — git/state path

**Behavior identické s `pack.previews`:**
- User media files v `state/packs/<pack>/user_media/<id>/<filename>` jsou
  **git-tracked** (jako `state/packs/<pack>/previews/`).
- `backup_service` (blob backup) je **NEvidí ani neupravuje** — backup blob
  storage scope = `data/blob_store/`.
- State backup = git remote push (existing workflow).
- `.gitignore` user media **NEvylučuje** (default state include).

**Důsledky:**
- Restore z git → user media obnoveny automaticky (jako previews).
- Disaster recovery scope: blob backup (data/) + git push (state/).
- Žádný separátní backup endpoint pro user media.

**Verifikace:**
- [ ] Test: vytvořit user_media → `git status` ukazuje untracked file → `git add`
      funguje → commit → file je in repo
- [ ] Test: clone fresh repo → user_media files restored

#### 2.5.3 Inventory page scope clarification

**Behavior:**
- Inventory page (BlobsTable) = **content-addressed blob storage view**.
- User media (state-versioned) **NENÍ v Inventory scope** — stejně jako Civitai
  previews tam nejsou.
- Pokud user chce vidět user media, používá `PackUserGallerySection` na pack detail
  page (per-pack view).

**Důvod:** Inventory řeší disk space + dedup pro velké model weights, ne user content.
User media jsou typicky řádově menší (do 100 MB per file) a per-pack semanticky.

**Documentation:** `docs/inventory.md` (pokud existuje) explicitně uvést že "user
media + previews jsou git-versioned content v state/, mimo Inventory scope".

#### 2.5.4 Rate limiting / concurrency control

**Decision:** Synapse je single-user lokální aplikace bez multi-tenant scenarios.
**Globální HTTP rate limiting NEPOTŘEBUJEME**. Stačí per-pack upload concurrency
control:

```python
# src/store/user_media_service.py
class UserMediaService:
    def __init__(self, ...):
        self._upload_locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _get_pack_lock(self, pack_name: str) -> threading.Lock:
        with self._locks_guard:
            if pack_name not in self._upload_locks:
                self._upload_locks[pack_name] = threading.Lock()
            return self._upload_locks[pack_name]

    def upload(self, pack_name: str, file: UploadFile) -> UserMedia:
        with self._get_pack_lock(pack_name):
            # ... validate, sha256, write file, append to pack ...
```

**Důvod:**
- Per-pack lock chrání před race conditions na `pack.json` save.
- Žádný globální limit — uživatel sám určuje rychlost.
- Jiné enpointy (read endpoints) nelocknuté.

**Risks tabulka update:** "rate limiting" → "per-pack upload lock".

#### 2.5.5 i18n coverage (CRITICAL — vlastníkův explicit požadavek)

> *"pozor preklady nutne musime spravne podporovat v cele aplikaci!"*

**Pravidlo:** Každý nový user-facing string MUSÍ projít přes `t()` helper. Žádné
hardcoded English/Czech strings v komponentách.

**Pokrytí per fáze:**

| Fáze | i18n key namespace | Soubory |
|------|-------------------|---------|
| 1 | `pack.empty.*` | `EmptySectionState`, všechny section empty states |
| 2 | `pack.userGallery.*` | `PackUserGallerySection`, `AddUserMediaModal`, error messages |
| 2 | `pack.userGallery.upload.*` | upload progress, validation errors, file size errors |
| 3 | `pack.deps.optionalBanner.*` | banner pro optional deps |
| 5 | `pack.updates.*` | per-dep update badges, "Update available" labels |
| 6 | `pack.export.*` | ExportPackModal — title, options, "Include weights" checkbox |
| 6 | `pack.import.*` | ImportPackModal — drag-drop, manifest preview, errors |
| 6 | `pack.import.errors.*` | zip slip rejection, hash mismatch, MIME validation errors |
| 7 | `pack.attachWorkflow.*` | attach workflow flow |
| 8.3 | `pack.delete.*` | delete confirmation modal text |

**Implementace:**
1. Přidat klíče do **OBOU** `apps/web/src/i18n/locales/cs/translation.json`
   a `apps/web/src/i18n/locales/en/translation.json`.
2. Linting check: žádný hardcoded string v JSX > 3 chars (existující ESLint plugin?).
3. Test: každý PR musí přidat klíče do obou locales (CI check).

**Verifikační tooling:**
- `pnpm test:i18n` script (NEW): checkne že všechny `t('key')` calls mají odpovídající
  klíč v obou locales.
- Failure mode: PR blocked dokud i18n keys missing.

**Risk:** MEDIUM (i18n typicky retro-dělaný, snadné přehlédnout). Lock předmětně
v Phase 9 acceptance criteria.

---

### Phase 3 — Pack Dependencies Operational (Q4: required → expand, optional → banner)

**Cíl:** `ViewBuilder.compute_plan()` rekurzivně expanduje **required** pack
dependencies. Optional zůstává jen UI banner.

**Codex Findings #7, #8, #9 — opravený code snippet:**
- Field je `pack_name`, ne `name` (viz `models.py:438`).
- Existující signature `compute_plan(self, ui, profile, packs)` zachována.
- Order: dependency-first DFS (deps před parentem) → parent assets mohou override base.
- Cycle detection: `visiting` (in-progress) + `visited` (done) — detekce a hlášení cyklu.
- Max depth/nodes limit pro deep tree safety.

**Backend changes:**

```python
# src/store/view_builder.py
class ViewBuilder:
    MAX_PACK_DEPTH = 32
    MAX_EXPANDED_NODES = 256

    def compute_plan(
        self,
        ui: UIKind,
        profile: Profile,
        packs: Dict[str, Tuple[Pack, Optional[PackLock]]],
    ) -> ViewPlan:
        # Expand each profile entry (preserving profile order) into ordered closure
        expanded: List[Tuple[str, Pack, Optional[PackLock]]] = []
        visited: Set[str] = set()
        for pack_entry in profile.packs:
            try:
                self._expand_pack_recursively(
                    pack_entry.pack_name,
                    packs=packs,
                    visiting=set(),
                    visited=visited,
                    out=expanded,
                    depth=0,
                )
            except PackDependencyCycle as exc:
                # surfaced in StatusReport.errors, not silently swallowed
                self._record_cycle_error(exc)

        # ... rest of plan compute consumes `expanded` instead of profile.packs ...

    def _expand_pack_recursively(
        self,
        pack_name: str,
        packs: Dict[str, Tuple[Pack, Optional[PackLock]]],
        visiting: Set[str],
        visited: Set[str],
        out: List[Tuple[str, Pack, Optional[PackLock]]],
        depth: int,
    ) -> None:
        if pack_name in visited:
            return  # already expanded earlier
        if pack_name in visiting:
            cycle = list(visiting) + [pack_name]
            raise PackDependencyCycle(f"Cycle detected: {' -> '.join(cycle)}")
        if depth > self.MAX_PACK_DEPTH:
            raise PackDependencyTooDeep(f"Depth > {self.MAX_PACK_DEPTH} at {pack_name}")
        if len(out) > self.MAX_EXPANDED_NODES:
            raise PackDependencyTooMany(f"Expanded > {self.MAX_EXPANDED_NODES} packs")

        if pack_name not in packs:
            # Surfaced as plan error, not silent skip
            raise MissingPackDependency(f"Pack {pack_name} not found in store")

        visiting.add(pack_name)
        pack, lock = packs[pack_name]

        # Dependency-first DFS — deps appended BEFORE parent
        for dep_ref in pack.pack_dependencies:
            if dep_ref.required:  # optional handled separately as UI banner
                self._expand_pack_recursively(
                    dep_ref.pack_name,  # ← pack_name field, NOT name
                    packs=packs, visiting=visiting, visited=visited,
                    out=out, depth=depth + 1,
                )
        # Parent appended AFTER deps → parent assets win override merge
        out.append((pack_name, pack, lock))
        visiting.discard(pack_name)
        visited.add(pack_name)
```

**Profile auto-add (Q3) — clear semantic split (Codex Finding #13):**

| Operace | Semantika |
|---------|-----------|
| `Store.use_pack(name)` | **PERSISTS closure** — přidá pack + required transitive deps do profilu. UX: user vidí celou skupinu v profilu. |
| `ViewBuilder.compute_plan()` | **VIRTUAL expansion** — pro každý profile entry expanduje required pack_deps in-memory. **NEMUTUJE profile**. |
| Optional deps | **NEAUTO-přidává** ani v `use_pack`, ani v `compute_plan`. Pouze UI banner. |

**Důvod:** Existující profily (před deployem) nemusí mít všechny deps. `compute_plan`
**vždy** expanduje virtually, takže staré profily fungují bez migrace. `use_pack`
naopak persistuje pro UX consistency u nových akcí.

**Migration log (M-class):**
- Při prvním rebuild po deployi `compute_plan` **loguje** warning: 
  `"Pack X required dep Y missing from profile (virtually expanded)"`.
- UI může nabídnout "1-click add to profile" CTA pro každý logged pack.

**API endpointy (rozšíření existujících):**
- `POST /api/use/{pack}` — backend rozšíří o auto-add logiku
- Response zahrnuje nové pole `auto_added_deps: List[str]` pro UI feedback

**Frontend:**

| Soubor | Co změnit |
|--------|-----------|
| `apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx` | Přidat banner "Doporučené (optional) deps:" pro `required: false` items s "Add to profile" button |
| `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts` | `usePack` mutation handler — toast zobrazí "Pack X + Y, Z added to profile" |

**Testy:**
- Unit: `ViewBuilder._expand_pack_recursively()` — happy path, cycle, missing pack
- Integration: `Store.use_pack()` — auto-add of required deps
- Smoke: full lifecycle import → use → view contains expanded deps' assets
- Regression: existing tests (none use pack_deps) musí stále projít

**Risk:** MEDIUM (mění runtime chování, riziko regrese pro existující profily).

**Migration concern:** Existující profily, které mají `pack A` v profilu, ale ne
`pack B` (kterou A.required pack_deps obsahuje). Po deployi se rebuild view a
najednou se objeví B assety. **Doporučuju** notification/log při prvním rebuild:
"Auto-added 3 packs to profile X based on pack_dependencies."

---

### Phase 4 — `EditDependenciesModal` (DEFERRED, čeká na BOD 1)

**Status:** ⏸️ BLOKOVÁNO BOD 1 (Resolve Model Redesign).

**Plán:** Po dokončení BOD 1 nahradit `EditDependenciesModal` univerzálním
`DependencyResolverModal`. Do té doby:

**Stub UI:**
```tsx
// V PackDependenciesSection
<Button disabled tooltip="Available after Resolve redesign">
  Add asset dependency
</Button>
```

**Důvod:** Asset-level dep CRUD vyžaduje resolveer, který je předmětem BOD 1.
Wireup teď by znamenalo dvojí práci (jednou starý modal, jednou nový).

---

### Phase 5 — Per-dep Update Flow pro Custom Packy (Q9 přepracovaný)

**Cíl:** Custom pack s online deps (Civitai/HF) **per-dep updatable**.
Pack metadata (description, version) se update **NEMĚNÍ**.

**Backend changes:**

```python
# src/store/update_service.py
def scan_for_updates(self) -> List[UpdateAvailable]:
    """Scan all packs (including custom) for available dep updates."""
    all_packs = self.pack_service.list_packs()  # includes custom
    updates = []
    for pack in all_packs:
        for asset in pack.assets:
            if asset.selector.strategy in (FOLLOW_LATEST, FOLLOW_BRANCH):
                latest = self._check_latest(asset)
                if latest and latest != asset.locked_version:
                    updates.append(UpdateAvailable(
                        pack_name=pack.name,
                        asset_name=asset.name,
                        current_version=asset.locked_version,
                        latest_version=latest,
                    ))
    return updates

def update_dep(self, pack_name: str, asset_name: str) -> UpdateResult:
    """Update single dependency, leaving pack.version unchanged."""
    # ... resolve new version, update lock.json, download blob ...
    # Pack.version is NOT touched
```

**API endpointy:**
- `GET /api/packs/{pack}/updates` — list updates available
- `POST /api/packs/{pack}/updates/{asset_name}` — update single asset

**Frontend:**

| Soubor | Co změnit |
|--------|-----------|
| `apps/web/src/components/modules/UpdatesPage.tsx` | Show custom packs in scan results (currently jen Civitai) |
| `apps/web/src/components/modules/pack-detail/sections/PackDependenciesSection.tsx` | Per-dep "Update available" badge + button |
| `apps/web/src/components/modules/pack-detail/plugins/CustomPlugin.tsx` | Enable update checks (currently disabled) |

**Testy:**
- Unit: `UpdateService.scan_for_updates()` — custom pack with online dep
- Integration: full scan → update single dep → verify lock.json updated, pack.version unchanged
- Smoke: custom pack with FOLLOW_LATEST Civitai LoRA, simulate version bump on Civitai mock

**Risk:** LOW (extending existing UpdateService, pack.version intact).

---

### Phase 6 — Export/Import Bundle (Q10/Qx-C: C2 default, C3 opt-in)

**Cíl:** Portable `.synapse-pack.zip` bundle pro sdílení mezi uživateli, **decodable
i bez Synapse aplikace**.

**Codex Finding #2 — ordering vůči Phase 7:**
- Phase 6 R1 export dělá pouze **existing `pack.workflows`** soubory (které Phase 7
  později rozšíří o "attach from other pack").
- Workflow attach UI z Phase 7 přijde **později**, ale export R1 cesty pro
  workflows/ jsou připravené (jen současný stav `pack.workflows`).
- Phase 7 backend MŮŽE běžet paralelně/před Phase 6 — viz upravené pořadí níže.

**Bundle struktura (C2 default):**

```
my-flux-bundle.synapse-pack.zip
├── pack.json              # Pack metadata
├── lock.json              # Resolved deps (URLs, sha256)
├── README.md              # AUTO-GENERATED at import time (NOT trusted from bundle)
├── previews/              # Civitai previews
│   ├── 0.jpg
│   └── 1.mp4
├── workflows/             # pack.workflows files (Phase 7 may extend semantics)
│   └── flux-portrait.json
├── user_media/            # User gallery
│   ├── <uuid1>/img.png
│   └── <uuid2>/vid.mp4
└── manifest.json          # Bundle manifest (version, scope, sha256s)
```

**C3 opt-in (`--include-weights`):** Přidá `blobs/<sha256>` directory s
.safetensors soubory. Bundle může mít gigabytes.

**Auto-generated README.md** — render Pack metadata jako čitelnou stránku:
```markdown
# My Flux Bundle

**Author:** username
**Version:** 1.0
**Created:** 2026-05-02

## Description
[pack.description as plaintext]

## Dependencies
- LoRA: [name](civitai_url)
- Checkpoint: [name](civitai_url)

## Pack Dependencies
- [base-sdxl](synapse://packs/base-sdxl)

## Workflows
- flux-portrait.json

## Trigger Words
keyword1, keyword2
```

**Backend služba:** `src/store/pack_export_service.py` (NEW):

```python
class PackExportService:
    def export_pack(
        self,
        pack_name: str,
        output_path: Path,
        include_weights: bool = False,
    ) -> Path:
        """Export pack to .synapse-pack.zip bundle."""

    def import_pack(
        self,
        bundle_path: Path,
        target_name: Optional[str] = None,
        on_conflict: ConflictMode = ConflictMode.RENAME,
    ) -> Pack:
        """Import .synapse-pack.zip bundle.

        Security: validate paths (no zip slip), validate sha256s, sanitize names.
        """
```

**API endpointy:**
- `POST /api/packs/{pack}/export?include_weights=false` — returns ZIP file (streaming)
- `POST /api/packs/import` — upload ZIP, parse, import (multipart)

**Security considerations (CRITICAL — Codex Findings #5, #11):**

**Zip slip mitigation (Codex Finding #5 — comprehensive):**
Validovat každý `ZipInfo` z `zipfile.infolist()`:
- Použít `PurePosixPath` (nikoli `Path`) na zip entries.
- **Reject:** absolute paths (`p.is_absolute()`), `..` v parts, empty parts, leading `/`.
- **Reject:** backslashes (`\` v `info.filename` → potenciální Windows path).
- **Reject:** drive prefixes (`C:`, `D:`).
- **Reject:** duplicate normalized names (collision attack).
- **Reject:** symlinks a special files: `info.external_attr & 0xA000 == 0xA000` (S_IFLNK).
- **Reject:** soubory mimo allowlist top-level dirs (`pack.json`, `lock.json`, `manifest.json`,
  `README.md`, `previews/`, `workflows/`, `user_media/`, `blobs/` — pokud `--include-weights`).
- **Reject:** počet souborů > 1000 (počítat předem z `infolist()`).
- **Reject:** total uncompressed size > 5 GB (default; > 50 GB s `--include-weights`).
- **Reject:** compression ratio > 100:1 per soubor (compression bomb).
- Po validaci: streamovat každý soubor do temp dir, ověřit
  `target.resolve().is_relative_to(extract_root.resolve())`.

**JSON / metadata trust boundary (Codex Finding #11):**
- `pack.json` validovat strict Pydantic schema → odmítnout neznámá pole
  (`model_config.extra = "forbid"`).
- `lock.json` — validovat všechny URL:
  - **Schema whitelist:** jen `https://` (odmítnout `http://`, `file://`, `ftp://`, `data:`).
  - **Host whitelist:** `civitai.com`, `huggingface.co`, podpora user-defined seznamu
    v config. Odmítnout `localhost`, `127.0.0.1`, IP literály v privátních rozsazích.
- `manifest.json` — validovat sha256 formát (`^[a-f0-9]{64}$`) per blob.
- **Sanitize pack name:** přijmout jen `^[a-zA-Z0-9_-]+$`, max 64 chars (collision
  s adresáři).
- **NEVĚŘIT** bundle `README.md` — ignorovat existující soubor, vždy regenerovat
  z importovaných metadata po importu.
- **Filename sanitization:** všechny content soubory (previews/, workflows/,
  user_media/) projdou stejnou validací jako Phase 2 upload (regex, MIME sniff).

**Hash verification:**
- `lock.json` sha256 musí matchovat actual blob soubor (pokud `--include-weights`).
- Mismatch = HARD reject, ne warning.
- SHA256 počítat **streamingly** — nečíst 5 GB do paměti.

**Resource limits:**
- Max bundle size: 5 GB (C2), 50 GB (C3 with weights).
- Max import time: 300 sec timeout, kill if exceeds.
- Concurrency: jen 1 import najednou (lock per store).

**Frontend:**

| Soubor | Co změnit |
|--------|-----------|
| `apps/web/src/components/modules/pack-detail/sections/PackHeader.tsx` | Add "Export" button (opens ExportPackModal) |
| `apps/web/src/components/modules/pack-detail/modals/ExportPackModal.tsx` (NEW) | Volby: include weights ano/ne, target path |
| `apps/web/src/components/modules/PacksPage.tsx` | Add "Import Pack" button v hlavičce |
| `apps/web/src/components/modules/pack-detail/modals/ImportPackModal.tsx` (NEW) | Drag-and-drop zip + preview manifest + import button |

**Testy:**
- Unit: `PackExportService.export_pack()` — bundle struktura, sha256 v manifestu
- Unit: zip slip detection, hash verification
- Integration: export → import roundtrip, verify pack identity
- Smoke: export pack with user_media, import to fresh store, verify all files
- Security tests: malicious zip with `../../../etc/passwd` rejection

**Risk:** HIGH (file I/O, security-sensitive, requires careful path handling).

---

### Phase 7 — Workflow Copy on Attach (Qx-B: B1 copy)

**Cíl:** "Attach workflow z packu X do custom packu A" → **kopíruje** workflow
soubor do `state/packs/<custom-pack>/workflows/`. Custom pack je samostatný.

**Codex Finding #12 — žádné arbitrary paths v API:**

```python
# src/store/pack_service.py
def attach_workflow_from_pack(
    self,
    target_pack_name: str,
    source_pack_name: str,
    source_workflow_id: str,  # Workflow.id, ne path
) -> Workflow:
    """Copy workflow from another pack into target's workflows/.

    Resolves source path internally — caller cannot supply arbitrary filesystem path.
    """
    # 1. Validate target is editable (pack_category=CUSTOM, plugin canEditWorkflows)
    # 2. Load source pack, find workflow by id
    # 3. Resolve source path: state/packs/<source_pack_name>/workflows/<wf.filename>
    # 4. Validate resolved path is_relative_to(state/packs/<source_pack_name>/workflows/)
    # 5. Copy to state/packs/<target_pack_name>/workflows/<sanitized_filename>
    # 6. Append to target.workflows, save pack

def attach_workflow_from_upload(
    self,
    target_pack_name: str,
    upload_file: UploadFile,
) -> Workflow:
    """Copy workflow from multipart upload into target's workflows/.

    Validation: filename sanitized, content is valid JSON, max size 10 MB.
    """
```

**API endpoint:**
- `POST /api/packs/{pack}/attach-workflow` — body: `{source_pack: str, workflow_id: str}`
  (NEpřijímá `source_path` ani arbitrary file paths!)
- `POST /api/packs/{pack}/attach-workflow-file` — multipart upload (alternativa)

**Filename collision:** Pokud workflow se stejným názvem už existuje, suffix `_1`, `_2`
(nikdy NEpřepisovat).

**UX (čeká na BOD 4 Workflow Wizard):**
- BOD 4 dodá UI pro "browse workflows from other packs / from filesystem".
- Pro Release 1 stačí backend API + jednoduchý drag-and-drop upload v PackWorkflowsSection.

**Testy:**
- Unit: `PackService.attach_workflow()` — copy semantics, collision handling
- Integration: attach z packu A do B, verify nezávislost
- Smoke: delete original workflow, attached copy in B stále funguje

**Risk:** LOW (file copy, isolated logic).

---

### Phase 8 — Polish (small fixes)

#### 8.1 Pack dep nav link fix

**File:** `apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx`
Search/replace: `'/pack/' + pack.name` → `'/packs/' + pack.name`

#### 8.2 `version_constraint` — UI info only

**Backend:** Pole zůstane v modelu (zpětně kompatibilní). **NEenforce v `pack_service`,
`update_service`, `view_builder`.**

**Frontend:** Zobrazit constraint v `PackDepsSection` pack-deps tree jako badge
("requires ≥ 2.0"), ale žádný validation gate.

**Testy:** Smoke test — pack with version_constraint není rejected, jen displayed.

#### 8.3 Delete custom pack — D4 dumb delete

**Backend:** `Store.delete_pack(name)` smaže jen `state/packs/<name>/` directory.
**NESmaže** referenced asset deps ani pack_deps. Pokud orphan, detekuje Inventory cleanup.

**Confirmation UI:** Modal text "Tento pack obsahuje N pack dependencies. Smazáním
custom packu **NEsmažete** dependencies — ty zůstanou v ostatních pack-konfiguracích."

#### 8.4 `Pack.version` — manual bump only

**Frontend:** EditPackModal má text input pro `version` (free-form string).
Žádný auto-bump při změnách. Žádný semver suggestion.

#### 8.5 ~~`pack_path` → `pack_dir` rename~~ — **PŘESUNUTO do Phase 0**

Codex Finding #1: kvůli severity tato úprava blokuje zbytek a běží jako Phase 0
preflight. Viz sekce **Phase 0** výše.

---

### Phase 9 — Tests Comprehensive

**Cíl:** Test pyramid — unit + integration + smoke pro celý custom pack lifecycle.

**Pokrytí:**
- Phase 1 frontend tests (Vitest)
- Phase 2 backend unit (UserMediaService) + integration + smoke
- Phase 3 backend unit (ViewBuilder expansion) + integration + smoke
- Phase 5 backend integration (UpdateService scope)
- Phase 6 backend security tests (zip slip, malicious payloads)
- Phase 7 backend smoke (workflow attach)
- Phase 8 regression tests pro všechny opravené body

**E2E (Playwright):**
- Create custom pack → empty state CTAs visible
- Add description, preview, workflow, dep
- Upload user media → visible in dedicated section
- Export → import roundtrip
- Use custom pack with required pack_deps → verify view contains expanded assets

---

## 6. Soubory které se mění (per phase)

### Backend

| Phase | File | Type |
|-------|------|------|
| 0 | `src/store/api.py` | `pack_path` → `pack_dir` (DOMAIN-AUDIT H1, Codex #1) |
| 2 | `src/store/models.py` | Add `UserMedia`, extend `Pack.user_gallery`, schema v3 default |
| 2 | `src/store/user_media_service.py` | NEW |
| 2 | `src/store/api.py` | Add user-media endpoints |
| 2.5 | `src/store/user_media_service.py` | Per-pack `threading.Lock` (concurrency) |
| 2.5 | `src/store/pack_service.py` | Verify `rename_pack()` moves user_media dir |
| 2.5 | `apps/web/src/i18n/locales/{cs,en}/translation.json` | i18n keys (per-phase) |
| 2.5 | `apps/web/scripts/test-i18n.ts` (NEW) | i18n key parity check |
| 2.5 | `apps/web/package.json` | `test:i18n` script |
| 3 | `src/store/view_builder.py` | Recursive expansion s `visiting+visited+max_depth` |
| 3 | `src/store/exceptions.py` | NEW: `PackDependencyCycle`, `PackDependencyTooDeep`, `MissingPackDependency` |
| 3 | `src/store/__init__.py` | `Store.use_pack()` persist closure |
| 5 | `src/store/update_service.py` | Custom pack scope |
| 5 | `src/store/api.py` | Add update endpoints |
| 6 | `src/store/pack_export_service.py` | NEW + zip-slip hardening |
| 6 | `src/store/api.py` | Add export/import endpoints, URL whitelist config |
| 7 | `src/store/pack_service.py` | `attach_workflow_from_pack()`, `attach_workflow_from_upload()` |
| 7 | `src/store/api.py` | Add attach-workflow endpoint (žádné arbitrary paths) |

### Frontend

| Phase | File | Type |
|-------|------|------|
| 1 | `apps/web/src/components/modules/pack-detail/sections/EmptySectionState.tsx` | NEW |
| 1 | `apps/web/src/components/modules/pack-detail/sections/PackInfoSection.tsx` | Modify |
| 1 | `apps/web/src/components/modules/PackDetailPage.tsx` | Remove `previews.length > 0` gate |
| 1 | `apps/web/src/components/modules/pack-detail/sections/PackGallery.tsx` | Empty state |
| 1 | `apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx` | Empty state |
| 2 | `apps/web/src/components/modules/pack-detail/sections/PackUserGallerySection.tsx` | NEW |
| 2 | `apps/web/src/components/modules/pack-detail/modals/AddUserMediaModal.tsx` | NEW |
| 2 | `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts` | Add user-media mutations |
| 3 | `apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx` | Optional banner |
| 5 | `apps/web/src/components/modules/UpdatesPage.tsx` | Custom pack scope |
| 5 | `apps/web/src/components/modules/pack-detail/sections/PackDependenciesSection.tsx` | Update badges |
| 5 | `apps/web/src/components/modules/pack-detail/plugins/CustomPlugin.tsx` | Enable updates |
| 6 | `apps/web/src/components/modules/pack-detail/modals/ExportPackModal.tsx` | NEW |
| 6 | `apps/web/src/components/modules/pack-detail/modals/ImportPackModal.tsx` | NEW |
| 6 | `apps/web/src/components/modules/PacksPage.tsx` | Import button |
| 7 | TBD (waits for BOD 4) | — |
| 8.1 | `apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx` | Nav link fix |

---

## 7. Test Strategy

Per CLAUDE.md test pyramid:

**Unit (≥ 60 testů):**
- UserMediaService: upload/delete/update/reorder happy paths + error paths + validation
- ViewBuilder._expand_pack_recursively: cycle, missing pack, optional vs required
- UpdateService.scan_for_updates: custom pack inclusion
- PackExportService: bundle struktura, sha256 v manifestu, zip slip detection
- PackService.attach_workflow: copy, collision, validation
- All resolver code from existing (regression)

**Integration (≥ 18 testů):**
- API endpoints: user-media upload → list → delete
- Auto-add deps: use_pack → view contains expanded
- Update flow: scan → update single dep → verify lock unchanged for other deps
- Export/import roundtrip
- Workflow attach: cross-pack copy
- **Phase 2.5: pack rename → user_media files dostupné na new path**
- **Phase 2.5: concurrent uploads na stejný pack — per-pack lock nebrekuje pack.json**
- **Phase 2.5: backup roundtrip — git push/pull preservuje user_media files**

**Smoke / E2E (≥ 7 testů):**
- Full custom pack lifecycle: create → edit description → upload preview → upload user media → add dep → use → verify view
- Export → import full roundtrip with binary integrity
- Pack-deps recursive expansion with 3-level chain
- Update single Civitai dep in custom pack, verify pack.version unchanged

**Frontend Vitest (≥ 25 testů):**
- EmptySectionState renders with correct CTA
- PackInfoSection empty vs filled states
- PackUserGallerySection upload flow
- ImportPackModal manifest preview
- All modal triggers from per-section buttons

**E2E Playwright (≥ 5 testů):**
- Create custom pack flow
- Add all section content via empty state CTAs
- Export pack
- Import pack
- Use pack triggers auto-add of pack_deps

**i18n CI check (`pnpm test:i18n`):**
- Parita klíčů mezi `cs/translation.json` a `en/translation.json`
- Žádné chybějící klíče volané přes `t()`
- Žádné nepoužité klíče v locale files (warning, ne error)

---

## 8. Open Questions

✅ **All custom-pack specific questions answered by owner 2026-05-02.**
✅ **Cross-cutting concerns answered 2026-05-02 (rename, backup, inventory, rate limiting, i18n) — viz Phase 2.5.**

**Není open question — explicit out-of-scope nebo deferred:**

1. **Schema migration framework (M6) — OUT OF SCOPE.**
   Co to je: jak migrovat existující v2 packy když v budoucnu změníme schema na
   v4 (přidáme breaking change, ne jen optional field). Dnes řešíme jen
   `default_factory` pro optional fields (Pack v3 user_gallery field), což
   automaticky funguje. Ale když někdy v budoucnu potřebujeme rename nebo type
   change, budeme potřebovat proper migration system (`alembic`-style versioned
   scripts). **Patří do samostatného infra plánu.** Tento plán to neřeší.

2. **Phase 4 (`EditDependenciesModal`) — DEFERRED na BOD 1.**
   Není to question, jen dependency. Asset-level dep CRUD vyžaduje resolveer,
   který je předmětem BOD 1 Resolve Model Redesign. Po dokončení BOD 1 tento
   modal nahradí `DependencyResolverModal` (univerzální).

---

## 9. Dependencies on Other Plans

| Phase | Závisí na | Stav závislosti |
|-------|-----------|-----------------|
| Phase 0 | **BLOKUJE všechny ostatní** | Preflight rename |
| Phase 1 | Phase 0 | Independent jinak |
| Phase 2 | Phase 0 | Independent jinak |
| Phase 2.5 | Phase 2 | Cross-cutting (rename, backup, i18n, locks) — paralelně s 2 |
| Phase 3 | Phase 0 | Independent jinak |
| Phase 4 | BOD 1 (Resolve redesign) | DEFERRED |
| Phase 5 | Phase 0 | Independent jinak |
| Phase 6 | Phase 0 + Phase 7 backend | viz Codex #2 — Phase 7 backend musí předbíhat |
| Phase 7 | Phase 0 (UX čeká BOD 4) | Backend dělat před Phase 6 |
| Phase 8 | Phase 0 | Cleanup |
| Phase 9 | All previous | Tests run continuously |

**Doporučené pořadí (po Codex #1, #2 + cross-cutting concerns):**
1. **Phase 0** — `pack_path` → `pack_dir` preflight (BLOCKER)
2. **Phase 1** — Empty State CTAs (i18n keys)
3. **Phase 2** — User Gallery (Pack v3 schema bump, i18n)
4. **Phase 2.5** — Cross-cutting: rename, backup, i18n CI check, per-pack locks
5. **Phase 3** — Pack Dependencies Operational
6. **Phase 5** — Per-dep Update Flow
7. **Phase 7 backend** — `attach_workflow_from_pack` (musí být hotové před exportem)
8. **Phase 6** — Export/Import Bundle (security-hardened)
9. **Phase 8** — Polish (8.1-8.4 — 8.5 už je v Phase 0)
10. **Phase 9** — Final comprehensive test pass

**Pozn.:** Phase 2.5 je "compliance fáze" — nejde o feature work, ale o zajištění
že feature work z Phase 1+2 splňuje požadavky vlastníka (rename, backup parity
s previews, i18n coverage, concurrency safety).

---

## 10. Audit & Review Plan

**Před implementací:**
- [x] Plán napsán Claude Opus 4.7 (2026-05-02)
- [x] Codex GPT-5.5 high audit (2026-05-02 evening) — 14 findings, all resolved v0.2.0
- [ ] Vlastník verifikuje na resolve-redesign branchi (2026-05-03)
- [ ] Update plánu podle nálezů
- [ ] Final approval vlastníkem

**Po každé fázi:**
- Claude review všech změněných souborů
- Codex review (`codex review --commit <SHA>`)
- Gemini review (`gemini -p "..." --yolo`)
- Test suite pass (`./scripts/verify.sh`)
- Update PLANu (aditivně)

**Před mergem do main:**
- User testing na `stabilization/release-1` branchi
- All phases complete + tested
- Final 3-model review

---

## 11. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Phase 6 zip slip / malicious bundle** | **CRITICAL** | Comprehensive ZipInfo validation, symlinks rejected, compression bomb limits, allowlist top-level dirs, hash verify, security test suite (Codex #5) |
| **Phase 6 imported lock URL SSRF / file://** | **CRITICAL** | Strict URL whitelist (https only, host allowlist, reject localhost/private IPs) (Codex #11) |
| **Phase 7 arbitrary file read přes source_path** | **HIGH** | API přijímá jen `{source_pack, workflow_id}`, nikdy raw paths (Codex #12) |
| Phase 6 README.md trust | HIGH | NEVĚŘIT bundle README, vždy regenerovat z metadata |
| Phase 6 polyglot / MIME spoofing | HIGH | Magic-byte sniff + extension match (libmagic) (Codex #6) |
| Phase 6 schema injection (unknown fields) | HIGH | Pydantic `extra = "forbid"` na všech imported JSON modelech |
| Phase 3 regression (existing profiles) | MEDIUM | Virtual expansion v `compute_plan` zachovává backward compat, log "auto-expanded" pro UX (Codex #13) |
| Phase 3 deep tree DoS | MEDIUM | `MAX_PACK_DEPTH=32`, `MAX_EXPANDED_NODES=256`, iterative DFS, perf test |
| Phase 3 cycle detection diagnostic | MEDIUM | `visiting+visited` + cyklus se hlásí s celou cestou `A → B → A` (Codex #9) |
| Phase 2 persisted relative_path tampering | MEDIUM | Path je DERIVED, ne persisted; filename sanitization (Codex #4) |
| Phase 2 file storage corruption | MEDIUM | sha256 verify on read, atomic write (temp + rename) |
| User uploaded media size DoS | MEDIUM | 100 MB per file, 5 GB per pack soft limit; per-pack `threading.Lock` (Phase 2.5.4) — single-user app, no global HTTP rate limit needed |
| i18n coverage chybí | MEDIUM | Phase 2.5.5 explicit pokrytí všech nových strings, `pnpm test:i18n` CI check, blok PR dokud klíče v cs+en (vlastník explicit požadavek) |
| Pack rename × user_media path drift | MEDIUM | UUID-immutable items, path je derived; existing `PackService.rename_pack()` move directory, test coverage v Phase 2.5.1 |
| Inventory page misleads o user_media scope | LOW | Phase 2.5.3 documentation: state-versioned mimo Inventory scope, viz `PackUserGallerySection` |
| Phase 6 collision/duplicate paths in zip | MEDIUM | Reject duplicate normalized names před extrakcí |
| Phase 6 concurrent metadata write | MEDIUM | Per-store import lock, jen 1 import at a time |
| Phase 5 update breaks pack.version | LOW | Test pack.version unchanged after dep update |
| Phase 0 `pack_path` rename misses call site | LOW | `rg "pack_path\(" src/store` = 0 verify |
| `--include-weights` accidental private export | LOW | Default false, UI warning, opt-in confirmation modal |

---

## 12. Codex Audit Findings (2026-05-02)

Codex GPT-5.5 high effort review běžel na v0.1.0 plánu. **14 nálezů, všechny
zapracované do v0.2.0**. Tabulka mapování nálezů → změna v plánu:

| # | Severity | Finding (zkráceně) | Resolution |
|---|----------|---------------------|------------|
| 1 | HIGH | Phase 8.5 critical, ale v cleanu sekci | **Phase 0 preflight** — blokuje vše |
| 2 | HIGH | Phase 6 závisí na Phase 7, ale je před | Reordered: Phase 7 backend → Phase 6 |
| 3 | HIGH | Schema strategy contradicted Pack v3 | Pack v3 bump explicit, v2 reads accepted |
| 4 | MEDIUM | UserMedia `relative_path` trust | Pole **odstraněno**, path je derived |
| 5 | CRITICAL | Zip slip mitigation shallow | Comprehensive ZipInfo validation |
| 6 | HIGH | MIME validation extension-based | Magic-byte sniff + extension match |
| 7 | CRITICAL | Phase 3 snippet broken (`dep_ref.name`) | `pack_name`, dependency-first DFS |
| 8 | HIGH | Phase 3 ignored `compute_plan` contract | Existing signature `(ui, profile, packs)` zachována |
| 9 | HIGH | Cycle prev. nedostačující pro diag | `visiting+visited+max_depth+max_nodes`, hlášení cyklu |
| 10 | HIGH | Empty state CTA gating wrong | `pack_category=='custom' && plugin.id=='custom' && features` |
| 11 | HIGH | Import bundle trust boundary incomplete | JSON schema strict, URL whitelist, sanitize names, regen README |
| 12 | MEDIUM | Phase 7 dangerous source paths | API přijímá `{source_pack, workflow_id}`, nikdy raw paths |
| 13 | MEDIUM | Profile auto-add vs virtual expansion | `use_pack` persists closure, `compute_plan` virtual expansion |
| 14 | LOW | Risk table under-rated | Phase 6 → CRITICAL, přidány nové risks |

---

## 13. Changelog

### 2026-05-02 — v0.3.0 (cross-cutting concerns)
- **Phase 2.5 přidaná** — řeší 5 integration concerns identifikovaných po v0.2.0:
  - **2.5.1 Pack rename** — adresář move + UUID-immutable user_media items, derived path
  - **2.5.2 Backup integration** — user_media je git/state-versioned (jako Civitai previews),
    blob backup je nevidí, restore přes git
  - **2.5.3 Inventory page scope** — Inventory = blob storage view, user_media mimo scope
  - **2.5.4 Rate limiting decision** — single-user app, žádný globální HTTP rate limit;
    per-pack `threading.Lock` na uploads
  - **2.5.5 i18n coverage** — explicit požadavek vlastníka, klíče per phase, `pnpm test:i18n`
    CI check, blok PR dokud cs+en kompletní
- Section 8 Open Questions vyčištěna — bod 1 (M6 schema migration) explicit OUT OF SCOPE,
  bod 2 (Phase 4) explicit DEFERRED.
- Risks tabulka rozšířena: i18n coverage, pack rename drift, inventory scope mislead.
- Backend tabulka přidává: per-pack lock v UserMediaService, i18n test script.
- Recommended order updatován: Phase 2.5 hned po Phase 2.

### 2026-05-02 — v0.2.0
- **Codex GPT-5.5 high effort audit** — 14 findings (3 CRITICAL, 8 HIGH, 3 MEDIUM, 1 LOW).
- Phase 8.5 → **Phase 0 preflight** (blokuje vše).
- Pack schema **explicit v3 bump** s v2 read backward compat.
- UserMedia: `relative_path` field **odstraněn** (path je derived, nikoliv persisted).
- Phase 3 code snippet **přepsán** (správný `dep_ref.pack_name`, dependency-first DFS,
  `visiting+visited` cycle detection, `max_depth=32`, `max_nodes=256`, exception types).
- Phase 6 zip slip **comprehensive** (ZipInfo validation, symlinks, compression bombs,
  duplicates, allowlist top-level dirs).
- Phase 6 import **JSON schema validation** (`extra = "forbid"`), **URL whitelist**
  (https only, host allowlist), **README regen** at import time.
- Phase 6 MIME **magic-byte sniffing** (libmagic), **extension agreement**.
- Phase 7 API **bez raw paths** — `{source_pack, workflow_id}` only.
- Phase 1 empty state CTA gating **upřesněn**: `pack_category + plugin.id + features`.
- Profile auto-add **clear semantic split**: `use_pack` persists, `compute_plan`
  virtually expands (backward compat).
- Risks tabulka přepracována — Phase 6 zip slip i URL SSRF povýšeny na CRITICAL.

### 2026-05-02 — v0.1.0
- Initial plan based on owner's answers to 12 + 5 questions (Bod 2 deep audit).
- Corrected wrong claim "modals are hidden" — verified per-section edit design.
- 9 phases defined, dependencies mapped, security risks identified.
- Awaiting codex audit + tomorrow's verification on resolve-redesign branch.

---

*Tento plán je living document. Aktualizuje se po codex auditu, verifikaci na
resolve-redesign branchi, a po každé implementační fázi.*
