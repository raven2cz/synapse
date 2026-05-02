Reading additional input from stdin...
OpenAI Codex v0.128.0 (research preview)
--------
workdir: /home/box/git/github/synapse
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, /home/box/.codex/memories]
reasoning effort: high
reasoning summaries: none
session id: 019de8f3-a0a6-7231-a4cb-bf193c6ccab2
--------
user
DOMAIN MODEL AUDIT — Synapse v2 Store layer.

Goal: Deep design audit of the domain objects in `src/store/models.py` and related modules. We are about to extend/refactor several systems (resolve-model redesign, custom packs, install packs, workflow wizard, profiles extension, AI integration) and want to find DESIGN FLAWS in the domain models BEFORE building on top of them. Any rotten foundations will turn future extensions into nightmares.

READ (give them all serious reading, do not skim):
- src/store/models.py (1573 lines — the core)
- src/store/layout.py (574 lines)
- src/store/__init__.py (Store class, public surface)
- src/store/pack_service.py (Pack CRUD, resolve, install)
- src/store/profile_service.py (Profile lifecycle)
- src/store/view_builder.py (ShadowedEntry, view plan)
- src/store/dependency_resolver.py (resolution strategies)
- src/store/inventory_service.py (inventory model)
- src/store/backup_service.py (backup model)
- src/store/update_service.py (UpdateResult)
- src/store/blob_store.py (blob layer model — content-addressed)
- src/store/ui_attach.py (UIAttacher contract)

Also peek at `plans/audits/CONSOLIDATED-FINDINGS.md` for the 6-point roadmap context (so you understand which extensions are coming).

JOB — produce a markdown audit (~600-1200 lines, file:line refs, NEEDS VERIFICATION marks):

1. INVENTORY OF DOMAIN OBJECTS
   - List every Pydantic/dataclass model in src/store/models.py with: purpose, fields,
     invariants, used-by surface, persistence (which JSON files, lock files, etc.).
   - Group by lifecycle: Pack/blob/lock vs Profile/runtime vs Resolution vs Source vs
     Inventory/backup vs Update vs UI/Attach.

2. ENUMS — are they exhaustive, do they cover all current and near-future use cases?
   - PackCategory (CUSTOM/EXTERNAL/INSTALL) — does this cover what we need? Should there
     be a WORKFLOW pack category (workflow imports want to create custom packs)? Should
     INSTALL be its own enum or a subtype?
   - AssetKind — 12 values; missing CUSTOM_NODES? WORKFLOW? Can one pack mix kinds?
   - ProviderName — does it cover HuggingFace, Civitai, Local, URL, plus future ones?
   - DependencyStrategy / UpdatePolicy / ConflictMode — fully wired? Modeled but ignored?
   - Any string-typed enums hiding as Literal[...] or raw str? Any "TODO" enums?

3. PACK SHAPE
   - Pack has: name, pack_category, source, dependencies, pack_dependencies, parameters,
     workflows, previews, base_model, version, etc. Are these fields cohesive?
   - Is `Pack.source` per-pack or per-dependency the right abstraction? (A custom pack
     can have a Civitai dep + an HF dep + a local dep — does `source` belong on Pack at all?)
   - `pack_dependencies` (pack-to-pack) — how do they compose? Recursive expansion?
     version_constraint enforcement?
   - PackLock vs Pack — is the split clean? Where is each field authoritative?
   - Lock invariants: blob_sha256 in lock, blob_sha256 in resolved dependency, blob in
     blob_store — three places — when do they diverge?
   - Storage: pack.json vs lock.json vs blob_manifest — clear separation?

4. DEPENDENCY MODEL
   - PackDependency, PackDependencyRef, ResolutionCandidate, CanonicalSource — overlap?
     redundancy? missing fields?
   - When dep is resolved, where does it land? Pack JSON? Lock? Both?
   - Is there a way to express "this pack depends on X but X is not yet resolved"
     without polluting normal fields with placeholders (model_id=0, etc.)?
   - Is dependency identity stable across renames/edits? Does dep_id survive across
     suggest/apply rounds?
   - Does the model support multi-source candidate (same dep, multiple matches)?
   - Does it support optional vs required deps? Recommendation level?

5. SOURCE / EVIDENCE / CANDIDATE
   - In resolve-model-redesign branch, candidates have CanonicalSource. Should
     Pack.source also use CanonicalSource? Are they parallel hierarchies?
   - Hash, ID, URL, file path — what is the canonical reference for any model?
   - Civitai modelId vs versionId vs hash — which is source of truth in Pack? in Lock?
   - HF repo + revision + path — modeled?

6. PROFILE / RUNTIME / VIEW
   - Profile.packs vs Profile.pack_dependencies — same thing? different?
   - ProfilePackEntry — has `enabled` field, but ViewBuilder ignores it. Should the
     enabled flag exist if no consumer honors it? Or should we wire it?
   - Runtime push/pop stack — modeled correctly? What invariants? What if the underlying
     profile is deleted while in stack?
   - Profile.conflicts.mode — modeled but only last_wins implemented. Remove or wire?
   - ShadowedEntry — when computed, where stored? StatusReport.shadowed is empty —
     is this a bug or a deliberate omission?
   - Work profile (work__<pack>) lifecycle — when created, when garbage collected,
     when promoted to global?

7. INVENTORY / BLOB / BACKUP MODELS
   - InventoryItem, BlobStatus, BlobLocation — sensible? Missing fields?
   - Active-in-uis tracking — is this derived live, or stored? If stored, who keeps
     it consistent?
   - Backup — is sync semantically push/pull/mirror?

8. RESOLUTION REDESIGN INTEGRATION (read branch with `git show feat/resolve-model-redesign:src/store/resolve_models.py` if you need)
   - How do new ResolutionCandidate / CanonicalSource fit into existing Pack model?
   - Are field names consistent across resolve_models.py and models.py?
   - Will applying a candidate need new fields on PackDependency?

9. CUSTOM/INSTALL/WORKFLOW PACK FUTURES
   - Does Pack model accommodate custom packs without dependencies? install packs with
     scripts? imported workflow packs?
   - Does PackCategory enum need to grow? Or should we keep CUSTOM and use user_tags?
   - Where would script_manifest, install_dir, ui_root, log_paths live?
   - Where would imported workflow JSON live as first-class pack data?

10. UI / ATTACH MODEL
    - UIKindMap fully covers current asset kinds for ComfyUI/Forge/A1111/SD.Next?
    - Is `default_ui_set` stored authoritatively in one place or two (state vs config)?
    - extra_model_paths.yaml schema modeled or ad-hoc strings in ui_attach.py?

11. CROSS-CUTTING CONCERNS
    - Versioning of pack.json schema — is there a schema_version? Migration path for
      existing data?
    - Default factories, frozen models, equality semantics — issues?
    - Pydantic v1 vs v2? Forward refs? Optional vs default None?
    - Naming: `pack` vs `Pack` vs `pack_name` vs `name` — consistent?
    - What about JSON serialization round-trips? Any field aliases that don't serialize
      symmetrically?

12. OBSERVED BUGS / SMELLS
    - ProfilePackEntry.enabled ignored.
    - Profile.conflicts.mode ignored.
    - StatusReport.shadowed always empty.
    - model_id=0 placeholder Civitai candidates.
    - Pack.layout.pack_path() does not exist; layout.pack_dir() does — possible crash
      in custom pack creation.
    - Source-of-truth split between state/ui_sets.json and app config store_ui_sets.

13. DESIGN RECOMMENDATIONS (concrete, refactor-level)
    - Which models should be split? Merged? Removed?
    - Where would type narrowing (Literal, Discriminated unions) help?
    - Where are mutable fields that should be immutable?
    - Where does code re-derive state that should be stored, or store state that
      should be derived?
    - Should Pack/PackLock get a schema_version? Migration helper?

14. OPEN QUESTIONS for owner
    - Hard architectural decisions that need user input.

Output: write directly to `plans/audits/codex-domain-audit.md`. Use file:line refs. Mark NEEDS VERIFICATION where you cannot confirm without running the system.
deprecated: `[features].collab` is deprecated. Use `[features].multi_agent` instead.
Enable it with `--enable multi_agent` or `[features].multi_agent` in config.toml. See https://developers.openai.com/codex/config-basic#feature-flags for details.
codex
I’ll audit the store domain model in the repo and write the findings directly to the requested markdown file. I’m going to start by reading the core model plus adjacent services and the roadmap context, then I’ll trace references so the line citations are grounded.
exec
/bin/bash -lc 'wc -l src/store/models.py src/store/layout.py src/store/__init__.py src/store/pack_service.py src/store/profile_service.py src/store/view_builder.py src/store/dependency_resolver.py src/store/inventory_service.py src/store/backup_service.py src/store/update_service.py src/store/blob_store.py src/store/ui_attach.py plans/audits/CONSOLIDATED-FINDINGS.md' in /home/box/git/github/synapse
 succeeded in 0ms:
  1573 src/store/models.py
   574 src/store/layout.py
  1693 src/store/__init__.py
  1349 src/store/pack_service.py
   539 src/store/profile_service.py
   527 src/store/view_builder.py
   368 src/store/dependency_resolver.py
   945 src/store/inventory_service.py
  1126 src/store/backup_service.py
   698 src/store/update_service.py
   611 src/store/blob_store.py
   585 src/store/ui_attach.py
   657 plans/audits/CONSOLIDATED-FINDINGS.md
 11245 total

exec
/bin/bash -lc "sed -n '1,220p' plans/audits/CONSOLIDATED-FINDINGS.md" in /home/box/git/github/synapse
 succeeded in 0ms:
# Release 1 Finishing — Konsolidované nálezy

**Vytvořeno:** 2026-05-02
**Autoři:** Claude Opus 4.7 + Codex GPT-5.5 high effort (6× nezávislý audit)
**Účel:** Jasný obraz stavu 6 bodů Release 1 Finishing Roadmap — co je hotové, co
chybí, na co se zeptat uživatele, jak se to napojuje na zbytek aplikace.

**Zdrojové soubory** (v `plans/audits/`):
- `codex-audit-1-resolve-model.md` (15k řádků raw + `plans/audit-resolve-model-redesign-local.md` 359 ř. summary)
- `codex-audit-2-custom-pack.md` (29k řádků)
- `codex-audit-3-install-pack.md` (488 ř. — feature je z 95 % budoucí)
- `codex-audit-4-workflow-wizard.md` (442 ř. — feature je převážně chybějící)
- `codex-audit-5-profiles.md` (22k řádků)
- `codex-audit-6-ai-integration.md` (16k řádků)

**Struktura každého bodu:** Kde jsme · Co chybí · Otázky pro uživatele · Napojení do aplikace.

---

## BOD 1 — feat/resolve-model-redesign

**Branch:** `feat/resolve-model-redesign` (lokálně, poslední commit pravděpodobně na druhém stroji).
**Spec:** `plans/PLAN-Resolve-Model.md` (lokálně už **v0.11.0**, Phase 0+1+2+2.5+3+4 COMPLETE, dle plánu).

### Kde jsme
- **Backend core je reálně napsaný a zapojený.** Existuje `ResolveService`, evidence
  providers (E1–E6 + AI), suggest/apply tok, candidate cache, `ResolutionCandidate`
  modely. Není to placeholder.
- **AI integrace přes `DependencyResolutionTask` funguje** — registrovaná, volá
  `avatar.execute_task("dependency_resolution", ...)`, MCP servery připojené přes
  `task_service` na branchi (NOT v mainu).
- **Local Resolve Tab je funkční** — browse + import + polling stavu importu.
- **DependencyResolverModal je primární modal**, kandidáti se vykreslují s confidence,
  evidence groups, raw score, Apply / Apply & Download tlačítky.
- **AI gate funguje na frontu** (skrývá AI tab pokud avatar `available=false`).

### Co chybí
- **Civitai tab a HuggingFace tab v DependencyResolverModal jsou prázdné placeholdery.**
  Žádný search input, žádné API volání, žádný manual apply. Jen popisný text.
- **Preview Analysis tab je display-only.** "Use this model" nevytváří nový kandidát ani
  manual apply; jen vybírá existujícího kandidáta z `candidates`. Pokud žádný neexistuje,
  uživatel dostane hlášku "spusť suggestion první".
- **Preview hints se nepřevádí zpět do `suggestResolution()` z UI.** Backend je umí přijmout
  jako override, ale frontend je neposílá.
- **AI execution policy se rozchází se spec.** Spec říká "AI jen když Tier 1/2 nenajdou
  kandidáta"; kód spouští AI vždy když `include_ai=True`. Větší tokeny + slabší determinismus.
- **Candidate cache nemá pack/dep binding.** Když `request_id` není dodán, hledá se přes
  všechny kešované requesty. Funguje, ale je to už v plánu označené jako deferred bug.
- **`apply_resolution()` aktualizuje JEN `pack.json`, nikdy `pack.lock.json`.** PackService
  doc to říká explicitně, ale spec původně chtěl "jeden write path do pack + lock".
- **`CanonicalSource` model existuje ale většina remote kandidátů ho nepopulu**je. Apply pak
  může vytvořit kandidáta bez canonical reference.
- **`HashEvidenceProvider.supports()` vrací true pro všechno** a no-opuje uvnitř — eligibilita
  není vyjádřená na supports() úrovni.
- **`FileMetaEvidenceProvider` stále emituje `model_id=0` placeholder Civitai kandidáty.**
  Default alias config taky používá placeholder zero IDs.
- **HF MCP search používá přímo `requests`** místo sdíleného `HuggingFaceClient`.
- **HF hash lookup je jen verifikace existujícího selektoru**, ne reverse lookup.
- **`/recommend-local` API endpoint se v spec jmenuje `/dependencies/{dep_id}/suggest`** —
  shape mismatch.
- **`tests/e2e_resolve_real.py` jen `sys.exit(0 if err_count == 0)`** — ignoruje `fail_count`,
  takže špatné top-match nezpůsobí selhání. Není to release gate.
- **Frontend Playwright E2E je plně mockované** (`apps/web/e2e/resolve-dependency.spec.ts`
  + `helpers/resolve.helpers.ts:245` "mock the backend completely"). Ověřuje UI flow, ne
  resolver correctness.
- **Tests heavily use `MagicMock`** — provider unit testy používají `MagicMock` místo reálných
  Pydantic dat (Civitai/HF response shapes).

### Otázky pro uživatele
1. **Je lokální v0.11.0 spec source of truth, nebo se má audit srovnávat s v0.7.1 z druhého stroje?**
2. **Má `apply_resolution()` aktualizovat `pack.lock.json`, nebo zůstává "pack.json only"?**
3. **Mají Civitai/HF manual tabs být implementované před R1, nebo placeholdery stačí?**
4. **Mají preview analysis hints feedback do `suggestResolution()` z UI?**
5. **Jsou placeholder kandidáti (`model_id=0`) přijatelné v UI, nebo je hide/marknout?**
6. **Co je autoritativní HF client atribut na PackService: `hf_client` nebo `huggingface`?**
7. **Má AI běžet souběžně s deterministickými providery, nebo jen jako fallback po E1–E6?**
8. **Má být `canonical_source` POVINNÝ pro všechny remote Civitai/HF kandidáty před apply?**
9. **Je HF reverse hash lookup mimo scope (HF API limitace), nebo je to požadavek?**
10. **Který test command je release gate: full pytest, Playwright E2E, live AI scripts, nebo curated subset?**

### Napojení do aplikace
- **Vstupní bod:** `PackDetailPage` → `PackDependenciesSection` → "Resolve" tlačítko
  → `DependencyResolverModal` (jediný modal pro všechny zdroje).
- **Backend cesta:** `POST /api/packs/{pack}/suggest-resolution` → `ResolveService.suggest()`
  → providers chain (FileMeta, Hash, Civitai, HF, PreviewMeta, AI) → seřazené `ResolutionCandidate[]`
  → cache → frontend.
- **Apply cesta:** `POST /api/packs/{pack}/apply-resolution` (kandidát z cache) nebo
  `apply-manual-resolution` (přímý selektor) → `PackService.resolve_dependency()` → patch
  `pack.json` → uložení.
- **Local Resolve:** `POST /api/store/recommend-local` (browse) + `POST /api/store/import-local`
  (import) → `LocalFileService` → blob copy/symlink → polling `/api/store/imports/{id}`.
- **AI:** `AvatarTaskService.execute_task("dependency_resolution", ...)` → `AvatarEngine`
  s MCP servery (`search_civitai`, `find_model_by_hash`, `search_huggingface`,
  `analyze_civitai_model`, `suggest_asset_sources`).
- **Lock update:** Aktuálně **odděleně** přes `resolve_pack` → `PackService.resolve_pack()`,
  ne v `apply_resolution()`. Toto je rozcestí pro rozhodnutí.

---

## BOD 2 — Custom Pack (deep audit)

**Branch:** `main`.
**Spec:** `plans/PLAN-Pack-Edit.md` (status říká "complete", reálně řada děr).

### Kde jsme
- **`PackCategory.CUSTOM` enum + Pack model jsou kompletní.** Backend zná
  `pack_category`, `source`, `dependencies`, `pack_dependencies`, `parameters`,
  `workflows`, `previews`.
- **Create endpoint `POST /api/packs/create` funguje** a vytvoří validní custom pack se
  správným `pack_category=CUSTOM` a `source.provider=LOCAL`.
- **Backend patch endpoint `PATCH /api/packs/{pack}` podporuje** description, tags,
  cover, author, version, trigger words, base model, user tags, rename.
- **Backend má resolvery pro Civitai, HF, local, URL, base-model strategie.**
- **Modaly EXISTUJÍ ale jsou ukryté:** `EditDependenciesModal`, `DescriptionEditorModal`,
  `EditPreviewsModal`, `EditPackModal`. Komponenty jsou napsané, ale `PackDetailPage`
  je nerendruje (edit mode není zapojen).
- **Frontend `usePackData.updatePack` je typovaný jen jako `{ user_tags: string[] }`**,
  i když runtime by zvládl víc.

### Co chybí
- **Edit mode není reachable z aktivní stránky.** `PackDetailPage:309` neposílá
  `onStartEdit` do `PackHeader`. Bez toho jsou všechny edit modaly nedosažitelné z UI.
- **Generic dependency CRUD endpoint chybí.** Existuje delete-resource a set-base-model,
  ale ne POST/PATCH `PackDependency` pro custom packs. Aktivní backend nemá obecný
  "add model dependency" endpoint.
- **`PackInfoSection` vrací `null`** když pack nemá trigger words / model info / description.
  Custom pack s prázdnou description NEMÁ visible section a žádné "add first description"
  tlačítko.
- **`PackGallery` se renderuje JEN když `pack.previews.length > 0`.** Nový custom pack
  se zero previews → žádná gallery sekce, žádné "add first preview" tlačítko.
- **Pack dependencies (pack-to-pack) backend funguje, ale UI je hidden.** `EditDependenciesModal`
  není importován do `PackDetailPage`.
- **CustomPlugin advertises edit features, ale `getHeaderActions()` returns null.** Extra
  section pouze ukazuje capability flags, které se renderují jen v edit mode (= nikdy).
- **`pack_dependencies` se NESEMANTICKY rekurzivně neexpanduje do profilu.**
  `ProfileService._load_packs_for_profile` načítá jen `profile.packs` přímo;
  `ViewBuilder.compute_plan` taky. Pokud Custom Pack A závisí na Pack B přes
  `pack_dependencies`, použití A NEPŘIDÁ B do view symlinks.
- **Workflow symlink delete URL mismatch:** UI volá DELETE, backend mu nepřijímá
  (`apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:401` vs
  `src/store/api.py:4630`).
- **Custom pack export/import neexistuje.** Žádný portable bundle (pack.json + lock +
  previews + workflows + blobs). Backup je pro state protection, ne export.
- **Update handling pro custom packs je undefined.** CustomPlugin disabluje update checks
  v UI, ale backend `update_service` rozhoduje podle dependency policy — custom pack
  s `FOLLOW_LATEST` Civitai dep je teoreticky updatable, ale UI ho neukáže.
- **Pack dependency navigation používá `/pack/{name}` místo `/packs/{name}`** — broken link.
- **Frontend testy mirror-ují simplified local definitions** místo importu reálných pluginů.

### Otázky pro uživatele
1. **Mají custom packs podporovat libovolné model dependencies v R1, nebo jen base + workflows + previews + params?**
2. **Má "Create Custom Pack" wizard rovnou nabídnout výběr dependencies?**
3. **Má custom pack creation auto-přidat pack do globálního profilu?**
4. **Jsou `pack_dependencies` operační (mění profile/view symlinks), nebo informační?**
5. **Pokud operační — má `use(pack)` rekurzivně zahrnout `pack_dependencies`?**
6. **Mají optional `pack_dependencies` být zahrnuté automaticky, nebo jen warning?**
7. **Má se `version_constraint` enforcovat?**
8. **Mají custom packs povolit `FOLLOW_LATEST` Civitai dependencies?**
9. **Pokud ano — má CustomPlugin exposovat updates? Pokud ne — má backend zakázat follow-latest na custom packs?**
10. **Co je expected export/import artifact — metadata only, +lock, +previews/workflows, +blobs, all?**
11. **Má `EditDependenciesModal` být revived, replaced by `DependencyResolverModal`, nebo removed?**
12. **Mají blank sekce vždy renderovat pro editable custom packs?**

### Napojení do aplikace
- **Vstupní bod:** `PacksPage` → "Create Pack" → `CreatePackModal` → `POST /api/packs/create`
  → `Pack` s `pack_category=CUSTOM` → navigace na `/packs/{name}`.
- **Edit cesta (CHYBÍ TEĎ):** `PackDetailPage` musí dostat `edit mode wired` →
  `PackHeader.onStartEdit` → `usePackEdit` state → buď global modal nebo per-section
  modaly (`EditPackModal`, `DescriptionEditorModal`, `EditPreviewsModal`,
  `EditDependenciesModal`).
- **Plugin priority:** `usePackPlugin.ts:100` má pořadí Install → Civitai → Custom.
  CustomPlugin je fallback (`pack.pack?.pack_category === 'custom' || true`), což
  znamená že **i unknown pack types se chovají jako custom**. To může být úmyslné, ale
  je to past.
- **Resolve napojení:** Custom pack → `PackDependenciesSection` → "Resolve" → použije
  stejný `DependencyResolverModal` jako Civitai packs (BOD 1).
- **Profile napojení:** `use(custom_pack)` vytvoří `work__{name}` profile, vloží do něj
  custom pack + global pack entries. `ViewBuilder.compute_plan` najde direct deps a
  vytvoří symlinks. **Neexpanduje `pack_dependencies` rekurzivně** (kritická díra).

---

## BOD 3 — Install Pack (FUTURE / prototype)

**Branch:** `main`.
**Spec:** Prototype banner v UI explicitně přiznává že je to budoucnost.
**Codex verdikt:** **NOT READY pro Release 1. Primary blocker: chybí security model pro arbitrary script execution.**

### Kde jsme
- **`PackCategory.INSTALL` enum existuje.**
- **InstallPlugin existuje** s prototype banner.
- **Mock skripty + mock environment status v UI** — buttony "Install / Start / Stop"
  vypadají actionable, ale nemají handlers (jen "coming soon" v console).
- **Plugin selection cesta funguje** (Install první v priority).

### Co chybí
- **Backend script execution service NEEXISTUJE.**
- **Žádný script manifest, hash verification, source display, risk warning.**
- **Žádný proces lifecycle (PID, port tracking, health checks, stop, timeout, restart policy).**
- **Žádný log streaming (WebSocket/SSE) ani log persistence.**
- **Žádný environment health monitoring.**
- **Žádné Profiles handoff** (install → write UI root do Profile target).
- **Žádný UI update vs. model update separation** (nejasné semantika v `/api/updates`).
- **Žádné templates pro popular UIs** (ComfyUI installer, Forge installer, atd.).
- **Žádné tests.**

### Otázky pro uživatele (open identity/trust questions)
1. **Co je primární identifikátor: `pack_category=install`, `user_tags=['install-pack']`, nebo oba?**
2. **Kdo autoruje trusted install packs — jen Synapse maintainers, nebo user-provided scripts povoleny?**
3. **Má script přístup k network/files mimo install dir? Jak se redact-ují secrets? Jak Windows skripty?**
4. **Jak se Synapse zotavuje po restartu když běží install proces?**
5. **Může jeden UI kind mít multiple roots (např. dva ComfyUI instance)?**
6. **Mají Profiles cílit na specifický install instance, nebo jen UI kind?**
7. **Patří UI update do `/api/updates` nebo do install pack lifecycle?**

### Napojení do aplikace
**Codex doporučuje:** **NESHIPOVAT spustitelné install packs v R1.**

**Acceptable R1 scope (varianta minimum):**
- Keep Install Pack disabled/prototype.

exec
/bin/bash -lc 'rg -n "''^(class|def) |''^class |''^def |''^(    class|    def) |Enum|BaseModel|dataclass|Literal|TODO|FIXME" src/store/models.py src/store/layout.py src/store/__init__.py src/store/pack_service.py src/store/profile_service.py src/store/view_builder.py src/store/dependency_resolver.py src/store/inventory_service.py src/store/backup_service.py src/store/update_service.py src/store/blob_store.py src/store/ui_attach.py' in /home/box/git/github/synapse
 succeeded in 0ms:
src/store/ui_attach.py:24:from dataclasses import dataclass, field
src/store/ui_attach.py:34:@dataclass
src/store/ui_attach.py:35:class AttachResult:
src/store/ui_attach.py:45:class UIAttacher:
src/store/ui_attach.py:53:    def __init__(
src/store/ui_attach.py:71:    def _get_kind_map(self, ui_name: str) -> UIKindMap:
src/store/ui_attach.py:82:    def get_active_view_path(self, ui_name: str) -> Optional[Path]:
src/store/ui_attach.py:94:    def generate_extra_model_paths_yaml(self, ui_name: str = "comfyui") -> Dict[str, Any]:
src/store/ui_attach.py:142:    def _kind_to_comfyui_name(self, kind: AssetKind) -> Optional[str]:
src/store/ui_attach.py:158:    def attach_comfyui_yaml(self, output_path: Optional[Path] = None) -> AttachResult:
src/store/ui_attach.py:236:    def detach_comfyui_yaml(self) -> AttachResult:
src/store/ui_attach.py:285:    def attach(self, ui_name: str, use_yaml: bool = False) -> AttachResult:
src/store/ui_attach.py:380:    def attach_all(
src/store/ui_attach.py:405:    def detach(self, ui_name: str) -> AttachResult:
src/store/ui_attach.py:454:    def status(self, ui_name: str) -> Dict[str, Any]:
src/store/ui_attach.py:538:    def refresh_attached(self, ui_targets: Optional[List[str]] = None) -> Dict[str, AttachResult]:
src/store/ui_attach.py:575:    def refresh_all_attached(self) -> Dict[str, AttachResult]:
src/store/blob_store.py:33:class BlobStoreError(Exception):
src/store/blob_store.py:38:class HashMismatchError(BlobStoreError):
src/store/blob_store.py:43:class DownloadError(BlobStoreError):
src/store/blob_store.py:52:def compute_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
src/store/blob_store.py:70:def compute_sha256_streaming(
src/store/blob_store.py:88:class BlobStore:
src/store/blob_store.py:104:    def __init__(
src/store/blob_store.py:151:    def blob_path(self, sha256: str) -> Path:
src/store/blob_store.py:155:    def blob_exists(self, sha256: str) -> bool:
src/store/blob_store.py:159:    def blob_size(self, sha256: str) -> Optional[int]:
src/store/blob_store.py:170:    def download(
src/store/blob_store.py:206:    def _copy_local_file(
src/store/blob_store.py:237:    def _download_http(
src/store/blob_store.py:280:    def _finalize_download(self, part_path: Path, sha256: str) -> str:
src/store/blob_store.py:299:    def download_many(
src/store/blob_store.py:359:    def verify(self, sha256: str) -> bool:
src/store/blob_store.py:373:    def verify_all(self) -> Tuple[List[str], List[str]]:
src/store/blob_store.py:405:    def list_blobs(self) -> List[str]:
src/store/blob_store.py:422:    def remove_blob(self, sha256: str) -> bool:
src/store/blob_store.py:442:    def clean_partial(self) -> int:
src/store/blob_store.py:466:    def get_total_size(self) -> int:
src/store/blob_store.py:486:    def adopt(
src/store/blob_store.py:533:    def manifest_path(self, sha256: str) -> Path:
src/store/blob_store.py:537:    def manifest_exists(self, sha256: str) -> bool:
src/store/blob_store.py:541:    def read_manifest(self, sha256: str) -> Optional[BlobManifest]:
src/store/blob_store.py:560:    def write_manifest(self, sha256: str, manifest: BlobManifest) -> bool:
src/store/blob_store.py:597:    def delete_manifest(self, sha256: str) -> bool:
src/store/dependency_resolver.py:32:class DependencyResolver(Protocol):
src/store/dependency_resolver.py:35:    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
src/store/dependency_resolver.py:50:class CivitaiFileResolver:
src/store/dependency_resolver.py:53:    def __init__(self, civitai_client: Any):
src/store/dependency_resolver.py:56:    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
src/store/dependency_resolver.py:102:class CivitaiLatestResolver:
src/store/dependency_resolver.py:105:    def __init__(self, civitai_client: Any):
src/store/dependency_resolver.py:108:    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
src/store/dependency_resolver.py:129:    def _resolve_pinned_version(
src/store/dependency_resolver.py:174:    def _build_artifact(
src/store/dependency_resolver.py:209:class BaseModelHintResolver:
src/store/dependency_resolver.py:212:    def __init__(self, civitai_client: Any, layout: Any):
src/store/dependency_resolver.py:216:    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
src/store/dependency_resolver.py:270:class HuggingFaceResolver:
src/store/dependency_resolver.py:273:    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
src/store/dependency_resolver.py:299:class UrlResolver:
src/store/dependency_resolver.py:302:    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
src/store/dependency_resolver.py:316:class LocalFileResolver:
src/store/dependency_resolver.py:319:    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
src/store/dependency_resolver.py:344:def _select_file(
src/store/backup_service.py:45:class BackupError(Exception):
src/store/backup_service.py:50:class BackupNotEnabledError(BackupError):
src/store/backup_service.py:55:class BackupNotConnectedError(BackupError):
src/store/backup_service.py:60:class BlobNotFoundError(BackupError):
src/store/backup_service.py:65:class InsufficientSpaceError(BackupError):
src/store/backup_service.py:74:class BackupService:
src/store/backup_service.py:88:    def __init__(self, layout: StoreLayout, config: BackupConfig):
src/store/backup_service.py:104:    def update_config(self, config: BackupConfig) -> None:
src/store/backup_service.py:109:    def backup_root(self) -> Optional[Path]:
src/store/backup_service.py:116:    def backup_blobs_path(self) -> Optional[Path]:
src/store/backup_service.py:123:    def backup_blob_path(self, sha256: str) -> Optional[Path]:
src/store/backup_service.py:132:    def backup_state_path(self) -> Optional[Path]:
src/store/backup_service.py:143:    def get_status(self) -> BackupStatus:
src/store/backup_service.py:245:    def is_enabled(self) -> bool:
src/store/backup_service.py:249:    def is_connected(self) -> bool:
src/store/backup_service.py:254:    def _require_connected(self) -> None:
src/store/backup_service.py:267:    def blob_exists_on_backup(self, sha256: str) -> bool:
src/store/backup_service.py:274:    def list_backup_blobs(self) -> List[str]:
src/store/backup_service.py:290:    def get_backup_blob_size(self, sha256: str) -> Optional[int]:
src/store/backup_service.py:301:    def backup_blob(
src/store/backup_service.py:414:    def restore_blob(
src/store/backup_service.py:529:    def delete_from_backup(
src/store/backup_service.py:597:    def sync(
src/store/backup_service.py:688:    def verify_backup_blob(self, sha256: str) -> bool:
src/store/backup_service.py:705:    def verify_all_backup_blobs(self) -> Tuple[List[str], List[str]]:
src/store/backup_service.py:727:    def is_last_copy(self, sha256: str) -> bool:
src/store/backup_service.py:739:    def get_delete_warning(self, sha256: str, target: str) -> Optional[str]:
src/store/backup_service.py:778:    def _copy_file(
src/store/backup_service.py:800:    def _list_local_blobs(self) -> List[str]:
src/store/backup_service.py:816:    def _get_local_blob_size(self, sha256: str) -> Optional[int]:
src/store/backup_service.py:827:    def get_state_sync_status(self) -> StateSyncResult:
src/store/backup_service.py:836:    def sync_state(
src/store/backup_service.py:929:    def _collect_state_files(
src/store/backup_service.py:956:    def _analyze_state_file(
src/store/backup_service.py:1014:    def _sync_state_file(
src/store/backup_service.py:1066:    def backup_state_file(self, relative_path: str) -> bool:
src/store/backup_service.py:1097:    def restore_state_file(self, relative_path: str) -> bool:
src/store/update_service.py:52:class UpdateError(Exception):
src/store/update_service.py:57:class AmbiguousSelectionError(UpdateError):
src/store/update_service.py:60:    def __init__(self, pack: str, ambiguous: List[AmbiguousUpdate]):
src/store/update_service.py:66:class UpdateService:
src/store/update_service.py:74:    def __init__(
src/store/update_service.py:95:    def register_provider(self, strategy: SelectorStrategy, provider: UpdateProvider) -> None:
src/store/update_service.py:99:    def _get_provider(self, strategy: SelectorStrategy) -> Optional[UpdateProvider]:
src/store/update_service.py:107:    def is_updatable(self, pack: Pack) -> bool:
src/store/update_service.py:121:    def plan_update(self, pack_name: str) -> UpdatePlan:
src/store/update_service.py:256:    def _find_reverse_dependencies(self, pack_name: str) -> List[str]:
src/store/update_service.py:280:    def apply_update(
src/store/update_service.py:432:    def _resolve_provider_name(provider_str: Optional[str]) -> ProviderName:
src/store/update_service.py:445:    def update_pack(
src/store/update_service.py:512:    def _apply_options(
src/store/update_service.py:547:    def _get_provider_for_pack(self, pack: Pack) -> Optional[UpdateProvider]:
src/store/update_service.py:555:    def apply_batch(
src/store/update_service.py:602:    def _sync_after_update(
src/store/update_service.py:652:    def check_all_updates(self) -> Dict[str, UpdatePlan]:
src/store/update_service.py:684:    def get_updatable_packs(self) -> List[str]:
src/store/view_builder.py:23:from dataclasses import dataclass, field
src/store/view_builder.py:41:class ViewBuildError(StoreError):
src/store/view_builder.py:46:class SymlinkError(ViewBuildError):
src/store/view_builder.py:51:@dataclass
src/store/view_builder.py:52:class ViewEntry:
src/store/view_builder.py:62:@dataclass
src/store/view_builder.py:63:class ViewPlan:
src/store/view_builder.py:71:    def add_entry(
src/store/view_builder.py:126:@dataclass
src/store/view_builder.py:127:class BuildReport:
src/store/view_builder.py:137:def create_symlink(source: Path, target: Path) -> None:
src/store/view_builder.py:176:class ViewBuilder:
src/store/view_builder.py:183:    def __init__(
src/store/view_builder.py:202:    def config(self) -> StoreConfig:
src/store/view_builder.py:212:    def compute_plan(
src/store/view_builder.py:278:    def build(
src/store/view_builder.py:350:    def build_for_ui_set(
src/store/view_builder.py:375:    def activate(self, ui: str, profile_name: str) -> None:
src/store/view_builder.py:411:    def activate_for_ui_set(self, ui_set_name: str, profile_name: str) -> List[str]:
src/store/view_builder.py:431:    def get_active_profile(self, ui: str) -> Optional[str]:
src/store/view_builder.py:454:    def remove_profile_view(self, ui: str, profile_name: str) -> bool:
src/store/view_builder.py:467:    def clean_orphaned_views(self, ui: str) -> List[str]:
src/store/view_builder.py:492:    def list_view_profiles(self, ui: str) -> List[str]:
src/store/view_builder.py:499:    def get_view_entries(self, ui: str, profile_name: str) -> List[ViewEntry]:
src/store/profile_service.py:39:class ProfileService:
src/store/profile_service.py:46:    def __init__(
src/store/profile_service.py:67:    def set_backup_service(self, backup_service: "BackupService") -> None:
src/store/profile_service.py:75:    def load_profile(self, profile_name: str) -> Profile:
src/store/profile_service.py:79:    def load_global(self) -> Profile:
src/store/profile_service.py:83:    def get_work_profile_name(self, pack_name: str) -> str:
src/store/profile_service.py:87:    def is_work_profile(self, profile_name: str) -> bool:
src/store/profile_service.py:91:    def get_pack_from_work_profile(self, profile_name: str) -> Optional[str]:
src/store/profile_service.py:101:    def ensure_work_profile(
src/store/profile_service.py:147:    def update_work_profile(
src/store/profile_service.py:181:    def use(
src/store/profile_service.py:257:    def use_from_ui_set(
src/store/profile_service.py:275:    def back(
src/store/profile_service.py:353:    def back_from_ui_set(
src/store/profile_service.py:369:    def sync_profile(
src/store/profile_service.py:401:    def sync_profile_from_ui_set(
src/store/profile_service.py:418:    def add_pack_to_global(self, pack_name: str) -> Profile:
src/store/profile_service.py:430:    def remove_pack_from_global(self, pack_name: str) -> Profile:
src/store/profile_service.py:446:    def get_active_profiles(self, ui_names: List[str]) -> Dict[str, str]:
src/store/profile_service.py:456:    def get_runtime_stacks(self, ui_names: List[str]) -> Dict[str, List[str]]:
src/store/profile_service.py:473:    def _load_packs_for_profile(
src/store/profile_service.py:493:    def _install_missing_blobs(
src/store/inventory_service.py:44:class InventoryService:
src/store/inventory_service.py:57:    def __init__(
src/store/inventory_service.py:75:    def set_backup_service(self, backup_service: "BackupService") -> None:
src/store/inventory_service.py:79:    def build_inventory(
src/store/inventory_service.py:221:    def _build_reference_map(self) -> Dict[str, List[PackReference]]:
src/store/inventory_service.py:282:    def _build_item(
src/store/inventory_service.py:377:            active_in_uis=[],  # TODO: Get from runtime
src/store/inventory_service.py:381:    def _build_summary(self, items: List[InventoryItem]) -> InventorySummary:
src/store/inventory_service.py:471:    def cleanup_orphans(self, dry_run: bool = True, max_items: int = 0) -> CleanupResult:
src/store/inventory_service.py:554:    def get_impacts(self, sha256: str) -> ImpactAnalysis:
src/store/inventory_service.py:618:    def delete_blob(
src/store/inventory_service.py:781:    def verify_blobs(
src/store/inventory_service.py:844:    def migrate_manifests(self, dry_run: bool = True) -> MigrateManifestsResult:
src/store/pack_service.py:31:from typing import Any, Callable, Dict, List, Literal, Optional, Tuple
src/store/pack_service.py:34:from pydantic import BaseModel
src/store/pack_service.py:72:class PreviewDownloadConfig(BaseModel):
src/store/pack_service.py:93:class DownloadProgressInfo(BaseModel):
src/store/pack_service.py:115:    status: Literal['downloading', 'completed', 'skipped', 'failed'] = 'downloading'
src/store/pack_service.py:128:class PackService:
src/store/pack_service.py:156:    def __init__(
src/store/pack_service.py:185:    def civitai(self):
src/store/pack_service.py:193:    def huggingface(self):
src/store/pack_service.py:204:    def list_packs(self) -> List[str]:
src/store/pack_service.py:208:    def load_pack(self, pack_name: str) -> Pack:
src/store/pack_service.py:212:    def save_pack(self, pack: Pack) -> None:
src/store/pack_service.py:216:    def delete_pack(self, pack_name: str) -> bool:
src/store/pack_service.py:220:    def pack_exists(self, pack_name: str) -> bool:
src/store/pack_service.py:228:    def _determine_nsfw_status(self, img_data: Dict[str, Any]) -> bool:
src/store/pack_service.py:248:    def _extract_meta_safely(self, img_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
src/store/pack_service.py:267:    def _sanitize_pack_name(self, name: str) -> str:
src/store/pack_service.py:283:    def parse_civitai_url(self, url: str) -> Tuple[int, Optional[int]]:
src/store/pack_service.py:307:    def import_from_civitai(
src/store/pack_service.py:603:    def _create_base_model_dependency(self, base_model: str) -> Optional[PackDependency]:
src/store/pack_service.py:635:    def _create_initial_lock_multi(self, pack: Pack) -> PackLock:
src/store/pack_service.py:768:    def _download_previews(
src/store/pack_service.py:1023:    def _download_additional_previews(
src/store/pack_service.py:1132:    def resolve_pack(
src/store/pack_service.py:1193:    def _ensure_resolvers(self) -> None:
src/store/pack_service.py:1199:            BaseModelHintResolver,
src/store/pack_service.py:1210:            SelectorStrategy.BASE_MODEL_HINT: BaseModelHintResolver(self.civitai, self.layout),
src/store/pack_service.py:1216:    def _resolve_dependency(
src/store/pack_service.py:1236:    def install_pack(
src/store/pack_service.py:1301:    def _ensure_blob_manifest(
src/store/__init__.py:186:class Store:
src/store/__init__.py:193:    def __init__(
src/store/__init__.py:273:    def is_initialized(self) -> bool:
src/store/__init__.py:277:    def init(self, force: bool = False) -> None:
src/store/__init__.py:290:    def get_config(self) -> StoreConfig:
src/store/__init__.py:294:    def save_config(self, config: StoreConfig) -> None:
src/store/__init__.py:298:    def get_ui_sets(self) -> UISets:
src/store/__init__.py:302:    def get_default_ui_set(self) -> str:
src/store/__init__.py:307:    def get_ui_targets(self, ui_set: Optional[str] = None) -> List[str]:
src/store/__init__.py:327:    def list_packs(self) -> List[str]:
src/store/__init__.py:331:    def list_models(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
src/store/__init__.py:382:    def search(self, query: str) -> SearchResult:
src/store/__init__.py:436:    def get_pack(self, pack_name: str) -> Pack:
src/store/__init__.py:440:    def get_pack_lock(self, pack_name: str) -> Optional[PackLock]:
src/store/__init__.py:444:    def delete_pack(self, pack_name: str) -> "DeleteResult":
src/store/__init__.py:510:    def import_civitai(
src/store/__init__.py:576:    def resolve(
src/store/__init__.py:593:    def install(
src/store/__init__.py:614:    def list_profiles(self) -> List[str]:
src/store/__init__.py:618:    def get_profile(self, profile_name: str) -> Profile:
src/store/__init__.py:622:    def get_global_profile(self) -> Profile:
src/store/__init__.py:626:    def sync(
src/store/__init__.py:658:    def use(
src/store/__init__.py:692:    def back(
src/store/__init__.py:724:    def reset(
src/store/__init__.py:792:    def check_updates(self, pack_name: str) -> UpdatePlan:
src/store/__init__.py:804:    def check_all_updates(self) -> Dict[str, UpdatePlan]:
src/store/__init__.py:813:    def update(
src/store/__init__.py:850:    def update_batch(
src/store/__init__.py:884:    def status(
src/store/__init__.py:967:    def doctor(
src/store/__init__.py:1053:    def _get_ui_attacher(self):
src/store/__init__.py:1089:    def attach_uis(
src/store/__init__.py:1124:    def detach_uis(
src/store/__init__.py:1158:    def refresh_attached_uis(
src/store/__init__.py:1196:    def get_attach_status(
src/store/__init__.py:1221:    def clean(
src/store/__init__.py:1255:    def get_inventory(
src/store/__init__.py:1278:    def get_inventory_summary(self) -> "InventorySummary":
src/store/__init__.py:1288:    def cleanup_orphans(self, dry_run: bool = True, max_items: int = 0) -> "CleanupResult":
src/store/__init__.py:1303:    def get_blob_impacts(self, sha256: str) -> "ImpactAnalysis":
src/store/__init__.py:1315:    def delete_blob(
src/store/__init__.py:1334:    def verify_blobs(
src/store/__init__.py:1355:    def get_backup_status(self) -> "BackupStatus":
src/store/__init__.py:1368:    def backup_blob(
src/store/__init__.py:1385:    def restore_blob(
src/store/__init__.py:1402:    def delete_from_backup(
src/store/__init__.py:1419:    def sync_backup(
src/store/__init__.py:1442:    def configure_backup(self, config: "BackupConfig") -> None:
src/store/__init__.py:1457:    def is_backup_connected(self) -> bool:
src/store/__init__.py:1461:    def blob_exists_on_backup(self, sha256: str) -> bool:
src/store/__init__.py:1469:    def pull_pack(
src/store/__init__.py:1573:    def push_pack(
src/store/models.py:20:from enum import Enum
src/store/models.py:22:from typing import Any, Dict, List, Literal, Optional, Union
src/store/models.py:24:from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator
src/store/models.py:28:# Enums
src/store/models.py:31:class AssetKind(str, Enum):
src/store/models.py:47:class ProviderName(str, Enum):
src/store/models.py:55:class SelectorStrategy(str, Enum):
src/store/models.py:65:class UpdatePolicyMode(str, Enum):
src/store/models.py:71:class ConflictMode(str, Enum):
src/store/models.py:78:class PackCategory(str, Enum):
src/store/models.py:95:def validate_safe_name(name: str) -> str:
src/store/models.py:108:def validate_safe_filename(filename: str) -> str:
src/store/models.py:121:class UIKindMap(BaseModel):
src/store/models.py:134:    def get_path(self, kind: AssetKind) -> Optional[str]:
src/store/models.py:139:class UIConfig(BaseModel):
src/store/models.py:145:    def get_default_kind_maps(cls) -> Dict[str, UIKindMap]:
src/store/models.py:199:class ProviderConfig(BaseModel):
src/store/models.py:205:class CivitaiSelectorConfig(BaseModel):
src/store/models.py:214:class BaseModelAliasSelector(BaseModel):
src/store/models.py:220:class BaseModelAlias(BaseModel):
src/store/models.py:224:    selector: BaseModelAliasSelector
src/store/models.py:227:class ConfigDefaults(BaseModel):
src/store/models.py:235:class BackupConfig(BaseModel):
src/store/models.py:243:class StoreConfig(BaseModel):
src/store/models.py:249:    base_model_aliases: Dict[str, BaseModelAlias] = Field(default_factory=dict)
src/store/models.py:255:    def create_default(cls) -> "StoreConfig":
src/store/models.py:271:    def _get_default_base_model_aliases() -> Dict[str, BaseModelAlias]:
src/store/models.py:275:            "SD1.5": BaseModelAlias(
src/store/models.py:278:                selector=BaseModelAliasSelector(
src/store/models.py:283:            "SDXL": BaseModelAlias(
src/store/models.py:286:                selector=BaseModelAliasSelector(
src/store/models.py:291:            "Illustrious": BaseModelAlias(
src/store/models.py:294:                selector=BaseModelAliasSelector(
src/store/models.py:299:            "Pony": BaseModelAlias(
src/store/models.py:302:                selector=BaseModelAliasSelector(
src/store/models.py:314:class UISets(BaseModel):
src/store/models.py:322:    def create_default(cls) -> "UISets":
src/store/models.py:350:class CivitaiSelector(BaseModel):
src/store/models.py:359:class HuggingFaceSelector(BaseModel):
src/store/models.py:367:class SelectorConstraints(BaseModel):
src/store/models.py:374:class DependencySelector(BaseModel):
src/store/models.py:385:class UpdatePolicy(BaseModel):
src/store/models.py:390:    def from_string(cls, value: str) -> "UpdatePolicy":
src/store/models.py:395:class ExposeConfig(BaseModel):
src/store/models.py:402:    def validate_filename(cls, v: str) -> str:
src/store/models.py:406:class PackDependency(BaseModel):
src/store/models.py:418:    def validate_id(cls, v: str) -> str:
src/store/models.py:422:class PackSource(BaseModel):
src/store/models.py:432:class PackResources(BaseModel):
src/store/models.py:438:class PackDependencyRef(BaseModel):
src/store/models.py:456:    def validate_pack_name(cls, v: str) -> str:
src/store/models.py:460:class GenerationParameters(BaseModel):
src/store/models.py:502:    def normalize_ai_response(cls, data: Any) -> Any:
src/store/models.py:764:    def _serialize(self, handler) -> dict:
src/store/models.py:776:class ModelInfo(BaseModel):
src/store/models.py:794:class WorkflowInfo(BaseModel):
src/store/models.py:803:class PreviewInfo(BaseModel):
src/store/models.py:819:    media_type: Literal['image', 'video', 'unknown'] = 'image'
src/store/models.py:827:    def is_video(self) -> bool:
src/store/models.py:832:    def is_image(self) -> bool:
src/store/models.py:837:class Pack(BaseModel):
src/store/models.py:880:    def is_nsfw(self) -> bool:
src/store/models.py:885:    def is_nsfw_hidden(self) -> bool:
src/store/models.py:891:    def validate_name(cls, v: str) -> str:
src/store/models.py:895:    def validate_unique_dep_ids(self) -> "Pack":
src/store/models.py:903:    def validate_unique_pack_deps(self) -> "Pack":
src/store/models.py:912:    def get_dependency(self, dep_id: str) -> Optional[PackDependency]:
src/store/models.py:924:class ArtifactProvider(BaseModel):
src/store/models.py:937:class ArtifactDownload(BaseModel):
src/store/models.py:942:class ArtifactIntegrity(BaseModel):
src/store/models.py:947:class ResolvedArtifact(BaseModel):
src/store/models.py:963:class ResolvedDependency(BaseModel):
src/store/models.py:969:class UnresolvedDependency(BaseModel):
src/store/models.py:976:class PackLock(BaseModel):
src/store/models.py:986:    def get_resolved(self, dep_id: str) -> Optional[ResolvedDependency]:
src/store/models.py:993:    def is_fully_resolved(self) -> bool:
src/store/models.py:1002:class ProfilePackEntry(BaseModel):
src/store/models.py:1008:    def validate_name(cls, v: str) -> str:
src/store/models.py:1012:class ConflictConfig(BaseModel):
src/store/models.py:1017:class Profile(BaseModel):
src/store/models.py:1028:    def validate_name(cls, v: str) -> str:
src/store/models.py:1031:    def add_pack(self, pack_name: str, move_to_end: bool = True) -> None:
src/store/models.py:1038:    def remove_pack(self, pack_name: str) -> bool:
src/store/models.py:1044:    def get_pack_names(self) -> List[str]:
src/store/models.py:1053:class UIRuntimeState(BaseModel):
src/store/models.py:1058:class Runtime(BaseModel):
src/store/models.py:1065:    def get_active_profile(self, ui_name: str) -> str:
src/store/models.py:1071:    def get_stack(self, ui_name: str) -> List[str]:
src/store/models.py:1077:    def push_profile(self, ui_name: str, profile_name: str) -> None:
src/store/models.py:1083:    def pop_profile(self, ui_name: str) -> Optional[str]:
src/store/models.py:1092:    def set_stack(self, ui_name: str, stack: List[str]) -> None:
src/store/models.py:1099:    def create_default(cls, ui_names: List[str]) -> "Runtime":
src/store/models.py:1110:class MissingBlob(BaseModel):
src/store/models.py:1118:class UnresolvedReport(BaseModel):
src/store/models.py:1126:class ShadowedEntry(BaseModel):
src/store/models.py:1134:class StatusReport(BaseModel):
src/store/models.py:1144:class UpdateChange(BaseModel):
src/store/models.py:1151:class UpdateCandidate(BaseModel):
src/store/models.py:1164:class AmbiguousUpdate(BaseModel):
src/store/models.py:1170:class PendingDownload(BaseModel):
src/store/models.py:1178:class UpdatePlan(BaseModel):
src/store/models.py:1188:class UpdateOptions(BaseModel):
src/store/models.py:1195:class UpdateResult(BaseModel):
src/store/models.py:1208:class BatchUpdateResult(BaseModel):
src/store/models.py:1216:class DoctorActions(BaseModel):
src/store/models.py:1223:class DoctorReport(BaseModel):
src/store/models.py:1235:class SearchResultItem(BaseModel):
src/store/models.py:1246:class SearchResult(BaseModel):
src/store/models.py:1253:class UseResult(BaseModel):
src/store/models.py:1264:class BackResult(BaseModel):
src/store/models.py:1273:class ResetResult(BaseModel):
src/store/models.py:1282:class DeleteResult(BaseModel):
src/store/models.py:1296:class BlobStatus(str, Enum):
src/store/models.py:1304:class BlobLocation(str, Enum):
src/store/models.py:1312:class BlobOrigin(BaseModel):
src/store/models.py:1324:class PackReference(BaseModel):
src/store/models.py:1334:class InventoryItem(BaseModel):
src/store/models.py:1359:class BackupStats(BaseModel):
src/store/models.py:1375:class InventorySummary(BaseModel):
src/store/models.py:1391:class InventoryResponse(BaseModel):
src/store/models.py:1398:class CleanupResult(BaseModel):
src/store/models.py:1408:class MigrateManifestsResult(BaseModel):
src/store/models.py:1418:class ImpactAnalysis(BaseModel):
src/store/models.py:1435:class BlobManifest(BaseModel):
src/store/models.py:1454:class BackupStatus(BaseModel):
src/store/models.py:1470:class BackupOperationResult(BaseModel):
src/store/models.py:1480:class BackupDeleteResult(BaseModel):
src/store/models.py:1489:class SyncItem(BaseModel):
src/store/models.py:1497:class SyncResult(BaseModel):
src/store/models.py:1517:class StateSyncStatus(str, Enum):
src/store/models.py:1526:class StateSyncItem(BaseModel):
src/store/models.py:1536:class StateSyncSummary(BaseModel):
src/store/models.py:1547:class StateSyncResult(BaseModel):
src/store/models.py:1561:class APIResponse(BaseModel):
src/store/models.py:1568:    def success(cls, result: Any) -> "APIResponse":
src/store/models.py:1572:    def failure(cls, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> "APIResponse":
src/store/layout.py:40:class StoreError(Exception):
src/store/layout.py:45:class StoreLockError(StoreError):
src/store/layout.py:50:class StoreNotInitializedError(StoreError):
src/store/layout.py:55:class PackNotFoundError(StoreError):
src/store/layout.py:60:class ProfileNotFoundError(StoreError):
src/store/layout.py:65:class StoreLayout:
src/store/layout.py:74:    def __init__(self, root: Optional[Path] = None):
src/store/layout.py:96:    def state_path(self) -> Path:
src/store/layout.py:101:    def data_path(self) -> Path:
src/store/layout.py:106:    def config_path(self) -> Path:
src/store/layout.py:111:    def ui_sets_path(self) -> Path:
src/store/layout.py:116:    def packs_path(self) -> Path:
src/store/layout.py:121:    def profiles_path(self) -> Path:
src/store/layout.py:126:    def blobs_path(self) -> Path:
src/store/layout.py:131:    def views_path(self) -> Path:
src/store/layout.py:136:    def registry_path(self) -> Path:
src/store/layout.py:141:    def db_path(self) -> Path:
src/store/layout.py:146:    def cache_path(self) -> Path:
src/store/layout.py:151:    def tmp_path(self) -> Path:
src/store/layout.py:156:    def runtime_path(self) -> Path:
src/store/layout.py:161:    def lock_file_path(self) -> Path:
src/store/layout.py:169:    def pack_dir(self, pack_name: str) -> Path:
src/store/layout.py:173:    def pack_json_path(self, pack_name: str) -> Path:
src/store/layout.py:177:    def pack_lock_path(self, pack_name: str) -> Path:
src/store/layout.py:181:    def pack_resources_path(self, pack_name: str) -> Path:
src/store/layout.py:185:    def pack_previews_path(self, pack_name: str) -> Path:
src/store/layout.py:189:    def pack_workflows_path(self, pack_name: str) -> Path:
src/store/layout.py:197:    def profile_dir(self, profile_name: str) -> Path:
src/store/layout.py:201:    def profile_json_path(self, profile_name: str) -> Path:
src/store/layout.py:209:    def view_ui_path(self, ui_name: str) -> Path:
src/store/layout.py:213:    def view_profiles_path(self, ui_name: str) -> Path:
src/store/layout.py:217:    def view_profile_path(self, ui_name: str, profile_name: str) -> Path:
src/store/layout.py:221:    def view_active_path(self, ui_name: str) -> Path:
src/store/layout.py:229:    def blob_path(self, sha256: str) -> Path:
src/store/layout.py:235:    def blob_part_path(self, sha256: str) -> Path:
src/store/layout.py:239:    def blob_manifest_path(self, sha256: str) -> Path:
src/store/layout.py:248:    def lock(self, timeout: Optional[float] = None) -> Generator[None, None, None]:
src/store/layout.py:280:    def is_initialized(self) -> bool:
src/store/layout.py:284:    def init_store(self, force: bool = False) -> None:
src/store/layout.py:306:    def _ensure_directories(self) -> None:
src/store/layout.py:322:    def _write_default_config(self) -> None:
src/store/layout.py:328:    def _write_default_ui_sets(self) -> None:
src/store/layout.py:334:    def _write_default_global_profile(self) -> None:
src/store/layout.py:342:    def _write_default_runtime(self) -> None:
src/store/layout.py:357:    def write_json(self, path: Path, data: Dict[str, Any]) -> None:
src/store/layout.py:379:    def read_json(self, path: Path) -> Dict[str, Any]:
src/store/layout.py:388:    def load_config(self) -> StoreConfig:
src/store/layout.py:395:    def save_config(self, config: StoreConfig) -> None:
src/store/layout.py:399:    def load_ui_sets(self) -> UISets:
src/store/layout.py:406:    def save_ui_sets(self, ui_sets: UISets) -> None:
src/store/layout.py:414:    def list_packs(self) -> List[str]:
src/store/layout.py:423:    def pack_exists(self, pack_name: str) -> bool:
src/store/layout.py:427:    def load_pack(self, pack_name: str) -> Pack:
src/store/layout.py:435:    def save_pack(self, pack: Pack) -> None:
src/store/layout.py:441:    def load_pack_lock(self, pack_name: str) -> Optional[PackLock]:
src/store/layout.py:449:    def save_pack_lock(self, lock: PackLock) -> None:
src/store/layout.py:455:    def delete_pack(self, pack_name: str) -> bool:
src/store/layout.py:467:    def list_profiles(self) -> List[str]:
src/store/layout.py:476:    def profile_exists(self, profile_name: str) -> bool:
src/store/layout.py:480:    def load_profile(self, profile_name: str) -> Profile:
src/store/layout.py:488:    def save_profile(self, profile: Profile) -> None:
src/store/layout.py:494:    def delete_profile(self, profile_name: str) -> bool:
src/store/layout.py:508:    def load_runtime(self) -> Runtime:
src/store/layout.py:516:    def save_runtime(self, runtime: Runtime) -> None:
src/store/layout.py:524:    def iter_packs(self) -> Iterator[Tuple[str, Pack]]:
src/store/layout.py:532:    def iter_packs_with_locks(self) -> Iterator[Tuple[str, Pack, Optional[PackLock]]]:
src/store/layout.py:546:    def clean_tmp(self) -> int:
src/store/layout.py:561:    def clean_cache(self) -> int:

codex
The roadmap context confirms the same pressure points the prompt calls out: resolve/apply writes only pack JSON, custom pack edit and pack-to-pack dependency behavior are not fully integrated, install packs are mostly future-facing, and profile/view behavior has some modeled-but-unwired fields. I’m reading the model definitions in line-numbered chunks now so the audit can cite exact foundations instead of just symptoms.
exec
/bin/bash -lc "nl -ba src/store/models.py | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Synapse Store v2 - Data Models
     3	
     4	Pydantic v2 models for pack.json, lock.json, config.json, profile.json, runtime.json.
     5	All models are designed to be JSON-serializable and validated.
     6	
     7	Schema versions:
     8	- synapse.config.v2
     9	- synapse.ui_sets.v1
    10	- synapse.pack.v2
    11	- synapse.lock.v2
    12	- synapse.profile.v1
    13	- synapse.runtime.v1
    14	"""
    15	
    16	from __future__ import annotations
    17	
    18	import re
    19	from datetime import datetime
    20	from enum import Enum
    21	from pathlib import Path
    22	from typing import Any, Dict, List, Literal, Optional, Union
    23	
    24	from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator
    25	
    26	
    27	# =============================================================================
    28	# Enums
    29	# =============================================================================
    30	
    31	class AssetKind(str, Enum):
    32	    """Types of assets that can be managed by Synapse."""
    33	    CHECKPOINT = "checkpoint"
    34	    LORA = "lora"
    35	    VAE = "vae"
    36	    CONTROLNET = "controlnet"
    37	    UPSCALER = "upscaler"
    38	    CLIP = "clip"
    39	    TEXT_ENCODER = "text_encoder"
    40	    DIFFUSION_MODEL = "diffusion_model"
    41	    EMBEDDING = "embedding"
    42	    CUSTOM_NODE = "custom_node"
    43	    UNET = "unet"
    44	    UNKNOWN = "unknown"
    45	
    46	
    47	class ProviderName(str, Enum):
    48	    """Supported asset providers."""
    49	    CIVITAI = "civitai"
    50	    HUGGINGFACE = "huggingface"
    51	    LOCAL = "local"
    52	    URL = "url"
    53	
    54	
    55	class SelectorStrategy(str, Enum):
    56	    """Selector strategies for resolving dependencies."""
    57	    CIVITAI_FILE = "civitai_file"
    58	    CIVITAI_MODEL_LATEST = "civitai_model_latest"
    59	    HUGGINGFACE_FILE = "huggingface_file"
    60	    BASE_MODEL_HINT = "base_model_hint"
    61	    LOCAL_FILE = "local_file"
    62	    URL_DOWNLOAD = "url_download"
    63	
    64	
    65	class UpdatePolicyMode(str, Enum):
    66	    """Update policy modes for dependencies."""
    67	    PINNED = "pinned"
    68	    FOLLOW_LATEST = "follow_latest"
    69	
    70	
    71	class ConflictMode(str, Enum):
    72	    """Conflict resolution modes."""
    73	    LAST_WINS = "last_wins"
    74	    FIRST_WINS = "first_wins"
    75	    STRICT = "strict"
    76	
    77	
    78	class PackCategory(str, Enum):
    79	    """
    80	    Category determines pack's origin and editability.
    81	
    82	    - EXTERNAL: Imported from Civitai, HuggingFace, etc. (metadata read-only)
    83	    - CUSTOM: Created locally from scratch (fully editable)
    84	    - INSTALL: Installation pack for UI environments (script-based management)
    85	    """
    86	    EXTERNAL = "external"
    87	    CUSTOM = "custom"
    88	    INSTALL = "install"
    89	
    90	
    91	# =============================================================================
    92	# Validators
    93	# =============================================================================
    94	
    95	def validate_safe_name(name: str) -> str:
    96	    """Validate name doesn't contain path traversal or dangerous chars."""
    97	    if not name:
    98	        raise ValueError("Name cannot be empty")
    99	    if "/" in name or "\\" in name:
   100	        raise ValueError("Name cannot contain path separators")
   101	    if ".." in name:
   102	        raise ValueError("Name cannot contain path traversal")
   103	    if "\x00" in name:
   104	        raise ValueError("Name cannot contain null bytes")
   105	    return name
   106	
   107	
   108	def validate_safe_filename(filename: str) -> str:
   109	    """Validate filename is safe for filesystem."""
   110	    validate_safe_name(filename)
   111	    # Additional filename-specific checks
   112	    if filename.startswith("."):
   113	        raise ValueError("Filename cannot start with dot")
   114	    return filename
   115	
   116	
   117	# =============================================================================
   118	# Config Models (state/config.json)
   119	# =============================================================================
   120	
   121	class UIKindMap(BaseModel):
   122	    """Mapping of asset kinds to UI-specific folder paths."""
   123	    checkpoint: str = "models/checkpoints"
   124	    lora: str = "models/loras"
   125	    vae: str = "models/vae"
   126	    embedding: str = "models/embeddings"
   127	    controlnet: str = "models/controlnet"
   128	    upscaler: str = "models/upscale_models"
   129	    clip: str = "models/clip"
   130	    text_encoder: str = "models/text_encoders"
   131	    diffusion_model: str = "models/diffusion_models"
   132	    unet: str = "models/unet"
   133	    
   134	    def get_path(self, kind: AssetKind) -> Optional[str]:
   135	        """Get folder path for asset kind."""
   136	        return getattr(self, kind.value, None)
   137	
   138	
   139	class UIConfig(BaseModel):
   140	    """UI configuration section."""
   141	    known: List[str] = Field(default_factory=lambda: ["comfyui", "forge", "a1111", "sdnext"])
   142	    kind_map: Dict[str, UIKindMap] = Field(default_factory=dict)
   143	    
   144	    @classmethod
   145	    def get_default_kind_maps(cls) -> Dict[str, UIKindMap]:
   146	        """Get default kind maps for all known UIs."""
   147	        return {
   148	            "comfyui": UIKindMap(
   149	                checkpoint="models/checkpoints",
   150	                lora="models/loras",
   151	                vae="models/vae",
   152	                embedding="models/embeddings",
   153	                controlnet="models/controlnet",
   154	                upscaler="models/upscale_models",
   155	                clip="models/clip",
   156	                text_encoder="models/text_encoders",
   157	                diffusion_model="models/diffusion_models",
   158	                unet="models/unet",
   159	            ),
   160	            "forge": UIKindMap(
   161	                checkpoint="models/Stable-diffusion",
   162	                lora="models/Lora",
   163	                vae="models/VAE",
   164	                embedding="embeddings",
   165	                controlnet="models/ControlNet",
   166	                upscaler="models/ESRGAN",
   167	                clip="models/CLIP",
   168	                text_encoder="models/text_encoder",
   169	                diffusion_model="models/diffusion_models",
   170	                unet="models/unet",
   171	            ),
   172	            "a1111": UIKindMap(
   173	                checkpoint="models/Stable-diffusion",
   174	                lora="models/Lora",
   175	                vae="models/VAE",
   176	                embedding="embeddings",
   177	                controlnet="models/ControlNet",
   178	                upscaler="models/ESRGAN",
   179	                clip="models/CLIP",
   180	                text_encoder="models/text_encoder",
   181	                diffusion_model="models/diffusion_models",
   182	                unet="models/unet",
   183	            ),
   184	            "sdnext": UIKindMap(
   185	                checkpoint="models/Stable-diffusion",
   186	                lora="models/Lora",
   187	                vae="models/VAE",
   188	                embedding="embeddings",
   189	                controlnet="models/ControlNet",
   190	                upscaler="models/ESRGAN",
   191	                clip="models/CLIP",
   192	                text_encoder="models/text_encoder",
   193	                diffusion_model="models/diffusion_models",
   194	                unet="models/unet",
   195	            ),
   196	        }
   197	
   198	
   199	class ProviderConfig(BaseModel):
   200	    """Provider-specific configuration."""
   201	    primary_file_only_default: bool = True
   202	    preferred_ext: List[str] = Field(default_factory=lambda: [".safetensors"])
   203	
   204	
   205	class CivitaiSelectorConfig(BaseModel):
   206	    """Civitai selector for base model alias."""
   207	    model_config = ConfigDict(protected_namespaces=())
   208	    
   209	    model_id: int
   210	    version_id: int
   211	    file_id: int
   212	
   213	
   214	class BaseModelAliasSelector(BaseModel):
   215	    """Selector configuration for base model alias."""
   216	    strategy: SelectorStrategy = SelectorStrategy.CIVITAI_FILE
   217	    civitai: Optional[CivitaiSelectorConfig] = None
   218	
   219	
   220	class BaseModelAlias(BaseModel):
   221	    """Base model alias definition."""
   222	    kind: AssetKind = AssetKind.CHECKPOINT
   223	    default_expose_filename: str
   224	    selector: BaseModelAliasSelector
   225	
   226	
   227	class ConfigDefaults(BaseModel):
   228	    """Default configuration values."""
   229	    ui_set: str = "local"
   230	    conflicts_mode: ConflictMode = ConflictMode.LAST_WINS
   231	    active_profile: str = "global"
   232	    use_base: str = "global"
   233	
   234	
   235	class BackupConfig(BaseModel):
   236	    """Configuration for backup storage."""
   237	    enabled: bool = False
   238	    path: Optional[str] = None  # e.g., "/mnt/external/synapse-backup" or "D:\\SynapseBackup"
   239	    auto_backup_new: bool = False  # Automatically backup new blobs
   240	    warn_before_delete_last_copy: bool = True  # Warn when deleting last copy
   241	
   242	
   243	class StoreConfig(BaseModel):
   244	    """Main store configuration (state/config.json)."""
   245	    schema_: str = Field(default="synapse.config.v2", alias="schema")
   246	    defaults: ConfigDefaults = Field(default_factory=ConfigDefaults)
   247	    ui: UIConfig = Field(default_factory=UIConfig)
   248	    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)
   249	    base_model_aliases: Dict[str, BaseModelAlias] = Field(default_factory=dict)
   250	    backup: BackupConfig = Field(default_factory=BackupConfig)
   251	
   252	    model_config = {"populate_by_name": True}
   253	    
   254	    @classmethod
   255	    def create_default(cls) -> "StoreConfig":
   256	        """Create default configuration with all defaults populated."""
   257	        config = cls()
   258	        config.ui.kind_map = UIConfig.get_default_kind_maps()
   259	        config.providers = {
   260	            "civitai": ProviderConfig(),

exec
/bin/bash -lc "nl -ba src/store/models.py | sed -n '261,560p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   261	            "huggingface": ProviderConfig(
   262	                primary_file_only_default=False,
   263	                preferred_ext=[".safetensors", ".bin", ".gguf"]
   264	            ),
   265	        }
   266	        # Default base model aliases for common models
   267	        config.base_model_aliases = cls._get_default_base_model_aliases()
   268	        return config
   269	    
   270	    @staticmethod
   271	    def _get_default_base_model_aliases() -> Dict[str, BaseModelAlias]:
   272	        """Get default base model aliases for well-known models."""
   273	        return {
   274	            # These are placeholder values - real IDs should be filled in
   275	            "SD1.5": BaseModelAlias(
   276	                kind=AssetKind.CHECKPOINT,
   277	                default_expose_filename="v1-5-pruned-emaonly.safetensors",
   278	                selector=BaseModelAliasSelector(
   279	                    strategy=SelectorStrategy.CIVITAI_FILE,
   280	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
   281	                )
   282	            ),
   283	            "SDXL": BaseModelAlias(
   284	                kind=AssetKind.CHECKPOINT,
   285	                default_expose_filename="sd_xl_base_1.0.safetensors",
   286	                selector=BaseModelAliasSelector(
   287	                    strategy=SelectorStrategy.CIVITAI_FILE,
   288	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
   289	                )
   290	            ),
   291	            "Illustrious": BaseModelAlias(
   292	                kind=AssetKind.CHECKPOINT,
   293	                default_expose_filename="illustrious_v1.safetensors",
   294	                selector=BaseModelAliasSelector(
   295	                    strategy=SelectorStrategy.CIVITAI_FILE,
   296	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
   297	                )
   298	            ),
   299	            "Pony": BaseModelAlias(
   300	                kind=AssetKind.CHECKPOINT,
   301	                default_expose_filename="ponyDiffusionV6XL.safetensors",
   302	                selector=BaseModelAliasSelector(
   303	                    strategy=SelectorStrategy.CIVITAI_FILE,
   304	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
   305	                )
   306	            ),
   307	        }
   308	
   309	
   310	# =============================================================================
   311	# UI Sets Model (state/ui_sets.json)
   312	# =============================================================================
   313	
   314	class UISets(BaseModel):
   315	    """UI sets configuration (state/ui_sets.json)."""
   316	    schema_: str = Field(default="synapse.ui_sets.v1", alias="schema")
   317	    sets: Dict[str, List[str]] = Field(default_factory=dict)
   318	    
   319	    model_config = {"populate_by_name": True}
   320	    
   321	    @classmethod
   322	    def create_default(cls) -> "UISets":
   323	        """
   324	        Create default UI sets.
   325	        
   326	        Includes:
   327	        - Named sets (local, all)
   328	        - Implicit singleton sets for each UI (comfyui, forge, a1111, sdnext)
   329	          This allows UI to send ui_set="comfyui" and it works.
   330	        """
   331	        return cls(
   332	            sets={
   333	                # Named sets
   334	                "local": ["comfyui", "forge"],
   335	                "comfy_only": ["comfyui"],
   336	                "all": ["comfyui", "forge", "a1111", "sdnext"],
   337	                # Implicit singleton sets - each UI can be targeted directly
   338	                "comfyui": ["comfyui"],
   339	                "forge": ["forge"],
   340	                "a1111": ["a1111"],
   341	                "sdnext": ["sdnext"],
   342	            }
   343	        )
   344	
   345	
   346	# =============================================================================
   347	# Pack Models (state/packs/<Pack>/pack.json)
   348	# =============================================================================
   349	
   350	class CivitaiSelector(BaseModel):
   351	    """Civitai-specific selector data."""
   352	    model_config = ConfigDict(protected_namespaces=())
   353	    
   354	    model_id: int
   355	    version_id: Optional[int] = None
   356	    file_id: Optional[int] = None
   357	
   358	
   359	class HuggingFaceSelector(BaseModel):
   360	    """HuggingFace-specific selector data."""
   361	    repo_id: str
   362	    filename: str
   363	    revision: Optional[str] = None
   364	    subfolder: Optional[str] = None
   365	
   366	
   367	class SelectorConstraints(BaseModel):
   368	    """Constraints for file selection."""
   369	    primary_file_only: bool = True
   370	    file_ext: List[str] = Field(default_factory=lambda: [".safetensors"])
   371	    base_model_hint: Optional[str] = None
   372	
   373	
   374	class DependencySelector(BaseModel):
   375	    """Selector for resolving a dependency."""
   376	    strategy: SelectorStrategy
   377	    civitai: Optional[CivitaiSelector] = None
   378	    huggingface: Optional[HuggingFaceSelector] = None
   379	    base_model: Optional[str] = None  # For base_model_hint strategy
   380	    url: Optional[str] = None  # For url_download strategy
   381	    local_path: Optional[str] = None  # For local_file strategy
   382	    constraints: Optional[SelectorConstraints] = None
   383	
   384	
   385	class UpdatePolicy(BaseModel):
   386	    """Update policy for a dependency."""
   387	    mode: UpdatePolicyMode = UpdatePolicyMode.PINNED
   388	    
   389	    @classmethod
   390	    def from_string(cls, value: str) -> "UpdatePolicy":
   391	        """Create UpdatePolicy from string shorthand."""
   392	        return cls(mode=UpdatePolicyMode(value))
   393	
   394	
   395	class ExposeConfig(BaseModel):
   396	    """Configuration for how an asset is exposed to UI."""
   397	    filename: str
   398	    trigger_words: List[str] = Field(default_factory=list)
   399	    
   400	    @field_validator("filename")
   401	    @classmethod
   402	    def validate_filename(cls, v: str) -> str:
   403	        return validate_safe_filename(v)
   404	
   405	
   406	class PackDependency(BaseModel):
   407	    """A single dependency within a pack."""
   408	    id: str
   409	    kind: AssetKind
   410	    required: bool = True
   411	    selector: DependencySelector
   412	    update_policy: UpdatePolicy = Field(default_factory=UpdatePolicy)
   413	    expose: ExposeConfig
   414	    description: Optional[str] = None  # Optional description for the dependency
   415	    
   416	    @field_validator("id")
   417	    @classmethod
   418	    def validate_id(cls, v: str) -> str:
   419	        return validate_safe_name(v)
   420	
   421	
   422	class PackSource(BaseModel):
   423	    """Source information for a pack."""
   424	    model_config = ConfigDict(protected_namespaces=())
   425	    
   426	    provider: ProviderName
   427	    model_id: Optional[int] = None
   428	    version_id: Optional[int] = None
   429	    url: Optional[str] = None
   430	
   431	
   432	class PackResources(BaseModel):
   433	    """Resource configuration for a pack."""
   434	    previews_keep_in_git: bool = True
   435	    workflows_keep_in_git: bool = True
   436	
   437	
   438	class PackDependencyRef(BaseModel):
   439	    """
   440	    Reference to another pack this pack depends on.
   441	
   442	    This enables pack dependency trees where:
   443	    - A LoRA pack can depend on a Checkpoint pack (its base model)
   444	    - A Workflow pack can depend on all required LoRA/VAE packs
   445	    - An Install pack can depend on another Install pack
   446	
   447	    The dependency is resolved at runtime by checking if the referenced
   448	    pack exists and is installed.
   449	    """
   450	    pack_name: str  # Name of the dependent pack
   451	    required: bool = True  # Is this dependency required?
   452	    version_constraint: Optional[str] = None  # e.g., ">=1.0.0", "latest"
   453	
   454	    @field_validator("pack_name")
   455	    @classmethod
   456	    def validate_pack_name(cls, v: str) -> str:
   457	        return validate_safe_name(v)
   458	
   459	
   460	class GenerationParameters(BaseModel):
   461	    """
   462	    Default generation parameters extracted from Civitai or user-defined.
   463	
   464	    All fields are Optional to avoid "ghost" values in JSON serialization.
   465	    Uses custom serializer to exclude None values automatically.
   466	
   467	    IMPORTANT: extra="allow" permits any additional parameters from the frontend
   468	    (e.g., controlnet, inpainting, batch, SDXL, FreeU, IP-Adapter settings).
   469	
   470	    AI Response Normalization:
   471	    The model_validator normalizes various AI response formats to standard fields:
   472	    - sampler: ['DPM++ 2M'] → 'DPM++ 2M'
   473	    - highres_fix_settings: {upscale_factor: 2} → hires_fix=True, hires_scale=2.0
   474	    - cfg_scale: {min: 5, max: 7, recommended: 7} → 7.0
   475	    - resolution: '512x768' → width=512, height=768
   476	    """
   477	    model_config = ConfigDict(extra="allow")
   478	
   479	    sampler: Optional[str] = None
   480	    scheduler: Optional[str] = None
   481	    steps: Optional[int] = None
   482	    cfg_scale: Optional[float] = None
   483	    clip_skip: Optional[int] = None
   484	    denoise: Optional[float] = None
   485	    width: Optional[int] = None
   486	    height: Optional[int] = None
   487	    seed: Optional[int] = None
   488	    # LoRA strength
   489	    strength: Optional[float] = None
   490	    eta: Optional[float] = None
   491	    # HiRes parameters - all Optional to avoid ghost values
   492	    hires_fix: Optional[bool] = None
   493	    hires_upscaler: Optional[str] = None
   494	    hires_steps: Optional[int] = None
   495	    hires_denoise: Optional[float] = None
   496	    hires_scale: Optional[float] = None
   497	    hires_width: Optional[int] = None
   498	    hires_height: Optional[int] = None
   499	
   500	    @model_validator(mode="before")
   501	    @classmethod
   502	    def normalize_ai_response(cls, data: Any) -> Any:
   503	        """Normalize AI response formats to standard field types.
   504	
   505	        CRITICAL: Never lose data! If normalization fails, preserve as extra field.
   506	
   507	        Handles various AI output formats and converts them to expected types:
   508	        - Lists → first element (e.g., sampler: ['DPM++'] → 'DPM++')
   509	        - Range dicts → recommended/max value (e.g., {min: 5, max: 7} → 7)
   510	        - Resolution string → width/height (e.g., '512x768' → width=512, height=768)
   511	        - Nested hires settings → flat fields
   512	        """
   513	        if not isinstance(data, dict):
   514	            return data
   515	
   516	        result = dict(data)
   517	
   518	        # Helper to safely convert to number, preserving original if fails
   519	        def safe_to_number(value: Any, as_float: bool = False) -> Any:
   520	            """Try to convert to number, return original if fails."""
   521	            if value is None:
   522	                return None
   523	            if isinstance(value, (int, float)):
   524	                return float(value) if as_float else value
   525	            if isinstance(value, str):
   526	                try:
   527	                    return float(value) if as_float else int(value)
   528	                except ValueError:
   529	                    return value  # Keep as string
   530	            return value
   531	
   532	        # Normalize list values to single items (sampler, scheduler)
   533	        for key in ["sampler", "scheduler"]:
   534	            if key in result and isinstance(result[key], list) and result[key]:
   535	                result[key] = result[key][0]
   536	
   537	        # Normalize list values to single items for numeric fields
   538	        # AI sometimes returns [1, 2] instead of just 1
   539	        # IMPORTANT: If list contains non-numeric, keep first element anyway
   540	        numeric_fields = [
   541	            "steps", "cfg_scale", "clip_skip", "denoise", "strength",
   542	            "width", "height", "seed", "eta",
   543	            "hires_steps", "hires_denoise", "hires_scale", "hires_width", "hires_height"
   544	        ]
   545	        for key in numeric_fields:
   546	            if key in result and isinstance(result[key], list) and result[key]:
   547	                # Take first element from list
   548	                first = result[key][0]
   549	                # Try to convert to appropriate type
   550	                if key in ["cfg_scale", "denoise", "strength", "hires_denoise", "hires_scale", "eta"]:
   551	                    result[key] = safe_to_number(first, as_float=True)
   552	                else:
   553	                    result[key] = safe_to_number(first, as_float=False)
   554	
   555	        # Normalize range dicts to single values
   556	        # Format: {min: X, max: Y, recommended: Z} → use recommended, then max
   557	        # IMPORTANT: If can't extract value, preserve as string representation
   558	        for key in ["steps", "cfg_scale", "clip_skip", "denoise", "strength"]:
   559	            if key in result and isinstance(result[key], dict):
   560	                range_dict = result[key]

exec
/bin/bash -lc "nl -ba src/store/models.py | sed -n '561,920p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   561	                extracted = None
   562	                if "recommended" in range_dict:
   563	                    extracted = range_dict["recommended"]
   564	                elif "best" in range_dict:
   565	                    extracted = range_dict["best"]
   566	                elif "max" in range_dict:
   567	                    extracted = range_dict["max"]
   568	                elif "value" in range_dict:
   569	                    extracted = range_dict["value"]
   570	
   571	                if extracted is not None:
   572	                    result[key] = extracted
   573	                else:
   574	                    # Can't extract single value - preserve as string for display
   575	                    # Move to custom field so we don't lose the info
   576	                    result[f"_raw_{key}"] = str(range_dict)
   577	                    del result[key]
   578	
   579	        # Normalize 'cfg' alias to 'cfg_scale'
   580	        if "cfg" in result and "cfg_scale" not in result:
   581	            cfg_val = result.pop("cfg")
   582	            if isinstance(cfg_val, dict):
   583	                if "recommended" in cfg_val:
   584	                    result["cfg_scale"] = cfg_val["recommended"]
   585	                elif "max" in cfg_val:
   586	                    result["cfg_scale"] = cfg_val["max"]
   587	            else:
   588	                result["cfg_scale"] = cfg_val
   589	
   590	        # Parse resolution string to width/height
   591	        if "resolution" in result and isinstance(result["resolution"], str):
   592	            resolution = result.pop("resolution")
   593	            match = re.match(r"(\d+)\s*[xX×]\s*(\d+)", resolution)
   594	            if match:
   595	                if "width" not in result or result["width"] is None:
   596	                    result["width"] = int(match.group(1))
   597	                if "height" not in result or result["height"] is None:
   598	                    result["height"] = int(match.group(2))
   599	
   600	        # Normalize hires_fix when it's a list (AI may return [{upscaler: '2x', denoising: 0.5}])
   601	        if "hires_fix" in result and isinstance(result["hires_fix"], list) and result["hires_fix"]:
   602	            # Take first element from list
   603	            first = result["hires_fix"][0]
   604	            if isinstance(first, dict):
   605	                result["hires_fix"] = first
   606	            elif isinstance(first, bool):
   607	                result["hires_fix"] = first
   608	            else:
   609	                # Something unexpected, try to coerce to bool
   610	                result["hires_fix"] = bool(first)
   611	
   612	        # Normalize hires_fix when it's a dict (AI may return {upscaler: '2x', denoising: 0.5})
   613	        if "hires_fix" in result and isinstance(result["hires_fix"], dict):
   614	            hires = result.pop("hires_fix")
   615	            result["hires_fix"] = True
   616	            # Map nested fields
   617	            field_map = {
   618	                "upscale_factor": "hires_scale",
   619	                "upscale_by": "hires_scale",
   620	                "scale": "hires_scale",
   621	                "upscaler": "hires_scale",  # '2x' will be converted below
   622	                "denoising_strength": "hires_denoise",
   623	                "denoise": "hires_denoise",
   624	                "denoising": "hires_denoise",
   625	                "steps": "hires_steps",
   626	            }
   627	            for src, dst in field_map.items():
   628	                if src in hires and (dst not in result or result[dst] is None):
   629	                    val = hires[src]
   630	                    # Convert '2x' format to float
   631	                    if isinstance(val, str) and val.endswith('x'):
   632	                        try:
   633	                            val = float(val[:-1])
   634	                        except ValueError:
   635	                            pass
   636	                    result[dst] = val
   637	
   638	        # Normalize highres_fix (alternate spelling) to hires_fix
   639	        if "highres_fix" in result:
   640	            highres = result.pop("highres_fix")
   641	            # If it's a dict with settings, extract them
   642	            if isinstance(highres, dict):
   643	                result["hires_fix"] = True
   644	                # Map nested fields
   645	                field_map = {
   646	                    "upscale_factor": "hires_scale",
   647	                    "upscale_by": "hires_scale",
   648	                    "scale": "hires_scale",
   649	                    "upscaler": "hires_upscaler",
   650	                    "denoising_strength": "hires_denoise",
   651	                    "denoise": "hires_denoise",
   652	                    "denoising": "hires_denoise",
   653	                    "steps": "hires_steps",
   654	                }
   655	                for src, dst in field_map.items():
   656	                    if src in highres and (dst not in result or result[dst] is None):
   657	                        val = highres[src]
   658	                        # Convert '2x' format to float
   659	                        if isinstance(val, str) and val.endswith('x'):
   660	                            try:
   661	                                val = float(val[:-1])
   662	                            except ValueError:
   663	                                pass
   664	                        result[dst] = val
   665	            elif isinstance(highres, bool):
   666	                result["hires_fix"] = highres
   667	            elif isinstance(highres, str):
   668	                # Could be "recommended", "required", etc.
   669	                lower = highres.lower()
   670	                if lower in ("true", "yes", "1", "enabled", "on", "recommended", "required", "must"):
   671	                    result["hires_fix"] = True
   672	                elif lower in ("false", "no", "0", "disabled", "off", "optional"):
   673	                    result["hires_fix"] = False
   674	                else:
   675	                    # Store original as note
   676	                    result["_raw_highres_fix"] = highres
   677	                    result["hires_fix"] = True  # Assume True if mentioned
   678	
   679	        # Normalize highres_fix_settings to flat fields
   680	        if "highres_fix_settings" in result and isinstance(result["highres_fix_settings"], dict):
   681	            hires = result.pop("highres_fix_settings")
   682	            # Set hires_fix to True if we have settings
   683	            if result.get("hires_fix") is None:
   684	                result["hires_fix"] = True
   685	            # Map nested fields
   686	            field_map = {
   687	                "upscale_factor": "hires_scale",
   688	                "scale": "hires_scale",
   689	                "upscaler": "hires_upscaler",
   690	                "denoising_strength": "hires_denoise",
   691	                "denoise": "hires_denoise",
   692	                "steps": "hires_steps",
   693	            }
   694	            for src, dst in field_map.items():
   695	                if src in hires and (dst not in result or result[dst] is None):
   696	                    result[dst] = hires[src]
   697	
   698	        # IMPORTANT: Do NOT filter out any fields!
   699	        # AI is instructed to extract ALL information including:
   700	        # - compatibility notes
   701	        # - usage tips
   702	        # - recommended models
   703	        # - warnings
   704	        # - workflow tips
   705	        # These are stored as extra fields (model_config extra="allow")
   706	        # and displayed in the UI's "AI Notes" section.
   707	
   708	        # Final pass: Validate types for known fields, move invalid to _raw_ prefix
   709	        # This ensures Pydantic validation won't fail and lose data
   710	        int_fields = ["steps", "clip_skip", "width", "height", "seed", "hires_steps", "hires_width", "hires_height"]
   711	        float_fields = ["cfg_scale", "denoise", "strength", "eta", "hires_denoise", "hires_scale"]
   712	        bool_fields = ["hires_fix"]
   713	        str_fields = ["sampler", "scheduler", "hires_upscaler"]
   714	
   715	        for key in int_fields:
   716	            if key in result and result[key] is not None:
   717	                val = result[key]
   718	                if not isinstance(val, int):
   719	                    try:
   720	                        result[key] = int(float(val))  # Handle "20.0" -> 20
   721	                    except (ValueError, TypeError):
   722	                        # Can't convert - preserve original in _raw_ field
   723	                        result[f"_raw_{key}"] = str(val) if not isinstance(val, str) else val
   724	                        del result[key]
   725	
   726	        for key in float_fields:
   727	            if key in result and result[key] is not None:
   728	                val = result[key]
   729	                if not isinstance(val, (int, float)):
   730	                    try:
   731	                        result[key] = float(val)
   732	                    except (ValueError, TypeError):
   733	                        result[f"_raw_{key}"] = str(val) if not isinstance(val, str) else val
   734	                        del result[key]
   735	
   736	        for key in bool_fields:
   737	            if key in result and result[key] is not None:
   738	                val = result[key]
   739	                if not isinstance(val, bool):
   740	                    # Try common string representations
   741	                    if isinstance(val, str):
   742	                        lower = val.lower()
   743	                        if lower in ("true", "yes", "1", "enabled", "on"):
   744	                            result[key] = True
   745	                        elif lower in ("false", "no", "0", "disabled", "off"):
   746	                            result[key] = False
   747	                        else:
   748	                            result[f"_raw_{key}"] = val
   749	                            del result[key]
   750	                    else:
   751	                        result[f"_raw_{key}"] = str(val)
   752	                        del result[key]
   753	
   754	        for key in str_fields:
   755	            if key in result and result[key] is not None:
   756	                val = result[key]
   757	                if not isinstance(val, str):
   758	                    # Convert to string - this should always work
   759	                    result[key] = str(val)
   760	
   761	        return result
   762	
   763	    @model_serializer(mode="wrap")
   764	    def _serialize(self, handler) -> dict:
   765	        """Custom serializer that excludes None values to avoid ghost parameters.
   766	
   767	        Includes both defined fields and extra fields (from model_config extra="allow").
   768	        """
   769	        d = handler(self)
   770	        # Include extra fields that were set dynamically
   771	        if hasattr(self, '__pydantic_extra__') and self.__pydantic_extra__:
   772	            d.update(self.__pydantic_extra__)
   773	        return {k: v for k, v in d.items() if v is not None}
   774	
   775	
   776	class ModelInfo(BaseModel):
   777	    """Extended model information table (like Civitai details panel)."""
   778	    model_config = ConfigDict(protected_namespaces=())
   779	    
   780	    model_type: Optional[str] = None
   781	    base_model: Optional[str] = None
   782	    trigger_words: List[str] = Field(default_factory=list)
   783	    trained_words: List[str] = Field(default_factory=list)
   784	    usage_tips: Optional[str] = None
   785	    hash_autov2: Optional[str] = None
   786	    hash_sha256: Optional[str] = None
   787	    civitai_air: Optional[str] = None
   788	    download_count: Optional[int] = None
   789	    rating: Optional[float] = None
   790	    published_at: Optional[str] = None
   791	    strength_recommended: Optional[float] = None
   792	
   793	
   794	class WorkflowInfo(BaseModel):
   795	    """Information about an included ComfyUI workflow."""
   796	    name: str
   797	    filename: str
   798	    description: Optional[str] = None
   799	    source_url: Optional[str] = None
   800	    is_default: bool = False
   801	
   802	
   803	class PreviewInfo(BaseModel):
   804	    """
   805	    Preview media information (image or video).
   806	    
   807	    Supports both images and videos from Civitai and other sources.
   808	    The `media_type` field indicates whether this is an image or video.
   809	    """
   810	    filename: str
   811	    url: Optional[str] = None
   812	    nsfw: bool = False
   813	    width: Optional[int] = None
   814	    height: Optional[int] = None
   815	    meta: Optional[Dict[str, Any]] = None
   816	    
   817	    # Media type: 'image', 'video', or 'unknown'
   818	    # Default is 'image' for backward compatibility
   819	    media_type: Literal['image', 'video', 'unknown'] = 'image'
   820	    
   821	    # Video-specific fields
   822	    duration: Optional[float] = None  # Duration in seconds
   823	    has_audio: Optional[bool] = None  # Whether video has audio track
   824	    thumbnail_url: Optional[str] = None  # Thumbnail/poster image URL for video
   825	    
   826	    @property
   827	    def is_video(self) -> bool:
   828	        """Check if this preview is a video."""
   829	        return self.media_type == 'video'
   830	    
   831	    @property
   832	    def is_image(self) -> bool:
   833	        """Check if this preview is an image."""
   834	        return self.media_type == 'image'
   835	
   836	
   837	class Pack(BaseModel):
   838	    """Main pack structure (state/packs/<Pack>/pack.json)."""
   839	    schema_: str = Field(default="synapse.pack.v2", alias="schema")
   840	    name: str
   841	    pack_type: AssetKind
   842	    pack_category: PackCategory = PackCategory.EXTERNAL  # Default for backwards compat
   843	    source: PackSource
   844	    dependencies: List[PackDependency] = Field(default_factory=list)
   845	    pack_dependencies: List[PackDependencyRef] = Field(default_factory=list)  # Dependencies on other packs
   846	    resources: PackResources = Field(default_factory=PackResources)
   847	
   848	    # Previews with metadata (canonical source of truth)
   849	    previews: List[PreviewInfo] = Field(default_factory=list)
   850	
   851	    # Cover/thumbnail URL - user-selected preview to show as pack cover
   852	    # If not set, falls back to first preview
   853	    cover_url: Optional[str] = None
   854	
   855	    # Optional metadata fields
   856	    version: Optional[str] = None
   857	    description: Optional[str] = None
   858	    base_model: Optional[str] = None
   859	    author: Optional[str] = None
   860	    tags: List[str] = Field(default_factory=list)
   861	    user_tags: List[str] = Field(default_factory=list)
   862	    trigger_words: List[str] = Field(default_factory=list)
   863	    created_at: Optional[datetime] = None
   864	    
   865	    # NSFW flags - managed via user_tags for UI compatibility
   866	    # nsfw-pack: blur previews in list
   867	    # nsfw-pack-hide: completely hide pack when NSFW mode disabled
   868	    
   869	    # Generation parameters and model info
   870	    parameters: Optional[GenerationParameters] = None
   871	    parameters_source: Optional[str] = None  # AI provider that extracted params (e.g., "ollama", "rule_based")
   872	    model_info: Optional[ModelInfo] = None
   873	    
   874	    # ComfyUI workflows
   875	    workflows: List[WorkflowInfo] = Field(default_factory=list)
   876	    
   877	    model_config = {"populate_by_name": True}
   878	    
   879	    @property
   880	    def is_nsfw(self) -> bool:
   881	        """Check if pack is marked NSFW (blur previews)."""
   882	        return "nsfw-pack" in self.user_tags
   883	    
   884	    @property
   885	    def is_nsfw_hidden(self) -> bool:
   886	        """Check if pack should be completely hidden when NSFW disabled."""
   887	        return "nsfw-pack-hide" in self.user_tags
   888	    
   889	    @field_validator("name")
   890	    @classmethod
   891	    def validate_name(cls, v: str) -> str:
   892	        return validate_safe_name(v)
   893	    
   894	    @model_validator(mode="after")
   895	    def validate_unique_dep_ids(self) -> "Pack":
   896	        """Ensure all dependency IDs are unique."""
   897	        ids = [dep.id for dep in self.dependencies]
   898	        if len(ids) != len(set(ids)):
   899	            raise ValueError("Dependency IDs must be unique within a pack")
   900	        return self
   901	
   902	    @model_validator(mode="after")
   903	    def validate_unique_pack_deps(self) -> "Pack":
   904	        """Ensure all pack dependency names are unique and no self-reference."""
   905	        names = [ref.pack_name for ref in self.pack_dependencies]
   906	        if len(names) != len(set(names)):
   907	            raise ValueError("Pack dependency names must be unique")
   908	        if self.name in names:
   909	            raise ValueError("Pack cannot depend on itself")
   910	        return self
   911	    
   912	    def get_dependency(self, dep_id: str) -> Optional[PackDependency]:
   913	        """Get dependency by ID."""
   914	        for dep in self.dependencies:
   915	            if dep.id == dep_id:
   916	                return dep
   917	        return None
   918	
   919	
   920	# =============================================================================

exec
/bin/bash -lc "nl -ba src/store/models.py | sed -n '921,1260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   921	# Lock Models (state/packs/<Pack>/lock.json)
   922	# =============================================================================
   923	
   924	class ArtifactProvider(BaseModel):
   925	    """Provider information for a resolved artifact."""
   926	    model_config = ConfigDict(protected_namespaces=())
   927	    
   928	    name: ProviderName
   929	    model_id: Optional[int] = None
   930	    version_id: Optional[int] = None
   931	    file_id: Optional[int] = None
   932	    repo_id: Optional[str] = None
   933	    filename: Optional[str] = None
   934	    revision: Optional[str] = None
   935	
   936	
   937	class ArtifactDownload(BaseModel):
   938	    """Download information for an artifact."""
   939	    urls: List[str] = Field(default_factory=list)
   940	
   941	
   942	class ArtifactIntegrity(BaseModel):
   943	    """Integrity information for an artifact."""
   944	    sha256_verified: bool = False
   945	
   946	
   947	class ResolvedArtifact(BaseModel):
   948	    """A resolved artifact in the lock file."""
   949	    kind: AssetKind
   950	    sha256: Optional[str] = None
   951	    size_bytes: Optional[int] = None
   952	    provider: ArtifactProvider
   953	    download: ArtifactDownload = Field(default_factory=ArtifactDownload)
   954	    integrity: ArtifactIntegrity = Field(default_factory=ArtifactIntegrity)
   955	
   956	
   957	# Backwards compatibility aliases for API
   958	Artifact = ResolvedArtifact
   959	DownloadInfo = ArtifactDownload
   960	IntegrityInfo = ArtifactIntegrity
   961	
   962	
   963	class ResolvedDependency(BaseModel):
   964	    """A resolved dependency entry in the lock file."""
   965	    dependency_id: str
   966	    artifact: ResolvedArtifact
   967	
   968	
   969	class UnresolvedDependency(BaseModel):
   970	    """An unresolved dependency entry in the lock file."""
   971	    dependency_id: str
   972	    reason: str
   973	    details: Dict[str, Any] = Field(default_factory=dict)
   974	
   975	
   976	class PackLock(BaseModel):
   977	    """Lock file structure (state/packs/<Pack>/lock.json)."""
   978	    schema_: str = Field(default="synapse.lock.v2", alias="schema")
   979	    pack: str
   980	    resolved_at: str = Field(default_factory=lambda: datetime.now().isoformat())
   981	    resolved: List[ResolvedDependency] = Field(default_factory=list)
   982	    unresolved: List[UnresolvedDependency] = Field(default_factory=list)
   983	    
   984	    model_config = {"populate_by_name": True}
   985	    
   986	    def get_resolved(self, dep_id: str) -> Optional[ResolvedDependency]:
   987	        """Get resolved dependency by ID."""
   988	        for r in self.resolved:
   989	            if r.dependency_id == dep_id:
   990	                return r
   991	        return None
   992	    
   993	    def is_fully_resolved(self) -> bool:
   994	        """Check if all dependencies are resolved."""
   995	        return len(self.unresolved) == 0
   996	
   997	
   998	# =============================================================================
   999	# Profile Models (state/profiles/<name>/profile.json)
  1000	# =============================================================================
  1001	
  1002	class ProfilePackEntry(BaseModel):
  1003	    """A pack entry in a profile."""
  1004	    name: str
  1005	    
  1006	    @field_validator("name")
  1007	    @classmethod
  1008	    def validate_name(cls, v: str) -> str:
  1009	        return validate_safe_name(v)
  1010	
  1011	
  1012	class ConflictConfig(BaseModel):
  1013	    """Conflict resolution configuration."""
  1014	    mode: ConflictMode = ConflictMode.LAST_WINS
  1015	
  1016	
  1017	class Profile(BaseModel):
  1018	    """Profile structure (state/profiles/<name>/profile.json)."""
  1019	    schema_: str = Field(default="synapse.profile.v1", alias="schema")
  1020	    name: str
  1021	    conflicts: ConflictConfig = Field(default_factory=ConflictConfig)
  1022	    packs: List[ProfilePackEntry] = Field(default_factory=list)
  1023	    
  1024	    model_config = {"populate_by_name": True}
  1025	    
  1026	    @field_validator("name")
  1027	    @classmethod
  1028	    def validate_name(cls, v: str) -> str:
  1029	        return validate_safe_name(v)
  1030	    
  1031	    def add_pack(self, pack_name: str, move_to_end: bool = True) -> None:
  1032	        """Add a pack to the profile. If move_to_end is True, moves existing pack to end."""
  1033	        # Remove if exists
  1034	        self.packs = [p for p in self.packs if p.name != pack_name]
  1035	        # Add at end
  1036	        self.packs.append(ProfilePackEntry(name=pack_name))
  1037	    
  1038	    def remove_pack(self, pack_name: str) -> bool:
  1039	        """Remove a pack from the profile. Returns True if removed."""
  1040	        original_len = len(self.packs)
  1041	        self.packs = [p for p in self.packs if p.name != pack_name]
  1042	        return len(self.packs) < original_len
  1043	    
  1044	    def get_pack_names(self) -> List[str]:
  1045	        """Get list of pack names in order."""
  1046	        return [p.name for p in self.packs]
  1047	
  1048	
  1049	# =============================================================================
  1050	# Runtime Models (data/runtime.json)
  1051	# =============================================================================
  1052	
  1053	class UIRuntimeState(BaseModel):
  1054	    """Runtime state for a single UI."""
  1055	    stack: List[str] = Field(default_factory=lambda: ["global"])
  1056	
  1057	
  1058	class Runtime(BaseModel):
  1059	    """Runtime state (data/runtime.json)."""
  1060	    schema_: str = Field(default="synapse.runtime.v1", alias="schema")
  1061	    ui: Dict[str, UIRuntimeState] = Field(default_factory=dict)
  1062	    
  1063	    model_config = {"populate_by_name": True}
  1064	    
  1065	    def get_active_profile(self, ui_name: str) -> str:
  1066	        """Get the active profile for a UI (top of stack)."""
  1067	        if ui_name in self.ui and self.ui[ui_name].stack:
  1068	            return self.ui[ui_name].stack[-1]
  1069	        return "global"
  1070	    
  1071	    def get_stack(self, ui_name: str) -> List[str]:
  1072	        """Get the stack for a UI."""
  1073	        if ui_name in self.ui:
  1074	            return self.ui[ui_name].stack.copy()
  1075	        return ["global"]
  1076	    
  1077	    def push_profile(self, ui_name: str, profile_name: str) -> None:
  1078	        """Push a profile onto the stack for a UI."""
  1079	        if ui_name not in self.ui:
  1080	            self.ui[ui_name] = UIRuntimeState()
  1081	        self.ui[ui_name].stack.append(profile_name)
  1082	    
  1083	    def pop_profile(self, ui_name: str) -> Optional[str]:
  1084	        """Pop and return the top profile from the stack. Returns None if at base."""
  1085	        if ui_name not in self.ui:
  1086	            return None
  1087	        stack = self.ui[ui_name].stack
  1088	        if len(stack) <= 1:
  1089	            return None  # Can't pop global
  1090	        return stack.pop()
  1091	    
  1092	    def set_stack(self, ui_name: str, stack: List[str]) -> None:
  1093	        """Set the entire stack for a UI (used for reset operations)."""
  1094	        if ui_name not in self.ui:
  1095	            self.ui[ui_name] = UIRuntimeState()
  1096	        self.ui[ui_name].stack = stack
  1097	    
  1098	    @classmethod
  1099	    def create_default(cls, ui_names: List[str]) -> "Runtime":
  1100	        """Create default runtime with global profile for all UIs."""
  1101	        return cls(
  1102	            ui={name: UIRuntimeState(stack=["global"]) for name in ui_names}
  1103	        )
  1104	
  1105	
  1106	# =============================================================================
  1107	# Report Models (for CLI/API responses)
  1108	# =============================================================================
  1109	
  1110	class MissingBlob(BaseModel):
  1111	    """Report entry for a missing blob."""
  1112	    pack: str
  1113	    dependency_id: str
  1114	    kind: AssetKind
  1115	    sha256: str
  1116	
  1117	
  1118	class UnresolvedReport(BaseModel):
  1119	    """Report entry for an unresolved dependency."""
  1120	    pack: str
  1121	    dependency_id: str
  1122	    reason: str
  1123	    details: Dict[str, Any] = Field(default_factory=dict)
  1124	
  1125	
  1126	class ShadowedEntry(BaseModel):
  1127	    """Report entry for a shadowed file (conflict resolved by last_wins)."""
  1128	    ui: str
  1129	    dst_relpath: str
  1130	    winner_pack: str
  1131	    loser_pack: str
  1132	
  1133	
  1134	class StatusReport(BaseModel):
  1135	    """Status report structure."""
  1136	    profile: str
  1137	    ui_targets: List[str]
  1138	    active: Dict[str, str]
  1139	    missing_blobs: List[MissingBlob] = Field(default_factory=list)
  1140	    unresolved: List[UnresolvedReport] = Field(default_factory=list)
  1141	    shadowed: List[ShadowedEntry] = Field(default_factory=list)
  1142	
  1143	
  1144	class UpdateChange(BaseModel):
  1145	    """A single change in an update plan."""
  1146	    dependency_id: str
  1147	    old: Dict[str, Any]
  1148	    new: Dict[str, Any]
  1149	
  1150	
  1151	class UpdateCandidate(BaseModel):
  1152	    """A candidate for ambiguous update selection."""
  1153	    model_config = ConfigDict(protected_namespaces=())
  1154	
  1155	    provider: str
  1156	    provider_model_id: Optional[int] = None
  1157	    provider_version_id: Optional[int] = None
  1158	    provider_file_id: Optional[int] = None
  1159	    sha256: Optional[str] = None
  1160	    filename: Optional[str] = None
  1161	    size_bytes: Optional[int] = None
  1162	
  1163	
  1164	class AmbiguousUpdate(BaseModel):
  1165	    """Ambiguous update requiring selection."""
  1166	    dependency_id: str
  1167	    candidates: List[UpdateCandidate]
  1168	
  1169	
  1170	class PendingDownload(BaseModel):
  1171	    """A dependency whose lock is updated but blob hasn't been downloaded yet."""
  1172	    dependency_id: str
  1173	    sha256: str
  1174	    download_url: str = ""
  1175	    size_bytes: Optional[int] = None
  1176	
  1177	
  1178	class UpdatePlan(BaseModel):
  1179	    """Update plan structure."""
  1180	    pack: str
  1181	    already_up_to_date: bool = False
  1182	    changes: List[UpdateChange] = Field(default_factory=list)
  1183	    ambiguous: List[AmbiguousUpdate] = Field(default_factory=list)
  1184	    pending_downloads: List[PendingDownload] = Field(default_factory=list)
  1185	    impacted_packs: List[str] = Field(default_factory=list)
  1186	
  1187	
  1188	class UpdateOptions(BaseModel):
  1189	    """Options for what to update beyond blobs."""
  1190	    merge_previews: bool = False
  1191	    update_description: bool = False
  1192	    update_model_info: bool = False
  1193	
  1194	
  1195	class UpdateResult(BaseModel):
  1196	    """Result of applying an update."""
  1197	    pack: str
  1198	    applied: bool
  1199	    lock_updated: bool
  1200	    synced: bool
  1201	    ui_targets: List[str] = Field(default_factory=list)
  1202	    already_up_to_date: bool = False
  1203	    previews_merged: int = 0
  1204	    description_updated: bool = False
  1205	    model_info_updated: bool = False
  1206	
  1207	
  1208	class BatchUpdateResult(BaseModel):
  1209	    """Result of applying updates to multiple packs."""
  1210	    results: Dict[str, Any] = Field(default_factory=dict)
  1211	    total_applied: int = 0
  1212	    total_failed: int = 0
  1213	    total_skipped: int = 0
  1214	
  1215	
  1216	class DoctorActions(BaseModel):
  1217	    """Actions taken by doctor."""
  1218	    views_rebuilt: bool = False
  1219	    db_rebuilt: Optional[str] = None  # "auto", "force", or None
  1220	    blobs_verified: bool = False
  1221	
  1222	
  1223	class DoctorReport(BaseModel):
  1224	    """Doctor report structure."""
  1225	    profile: str
  1226	    ui_targets: List[str]
  1227	    actions: DoctorActions
  1228	    active: Dict[str, str]
  1229	    missing_blobs: List[MissingBlob] = Field(default_factory=list)
  1230	    unresolved: List[UnresolvedReport] = Field(default_factory=list)
  1231	    shadowed: List[ShadowedEntry] = Field(default_factory=list)
  1232	    notes: List[str] = Field(default_factory=list)
  1233	
  1234	
  1235	class SearchResultItem(BaseModel):
  1236	    """A single search result item."""
  1237	    model_config = ConfigDict(protected_namespaces=())
  1238	    
  1239	    pack_name: str
  1240	    pack_type: str
  1241	    provider: Optional[str] = None
  1242	    source_model_id: Optional[int] = None
  1243	    source_url: Optional[str] = None
  1244	
  1245	
  1246	class SearchResult(BaseModel):
  1247	    """Search result structure."""
  1248	    query: str
  1249	    used_db: bool
  1250	    items: List[SearchResultItem] = Field(default_factory=list)
  1251	
  1252	
  1253	class UseResult(BaseModel):
  1254	    """Result of 'use' command."""
  1255	    pack: str
  1256	    created_profile: str
  1257	    ui_targets: List[str]
  1258	    activated_profile: str
  1259	    synced: bool
  1260	    shadowed: List[ShadowedEntry] = Field(default_factory=list)

exec
/bin/bash -lc "nl -ba src/store/models.py | sed -n '1261,1578p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1261	    notes: List[str] = Field(default_factory=list)
  1262	
  1263	
  1264	class BackResult(BaseModel):
  1265	    """Result of 'back' command."""
  1266	    ui_targets: List[str]
  1267	    from_profile: str
  1268	    to_profile: str
  1269	    synced: bool
  1270	    notes: List[str] = Field(default_factory=list)
  1271	
  1272	
  1273	class ResetResult(BaseModel):
  1274	    """Result of 'reset' command."""
  1275	    ui_targets: List[str]
  1276	    from_profiles: Dict[str, str]  # UI -> previous active profile
  1277	    to_profile: str  # Always "global"
  1278	    synced: bool
  1279	    notes: List[str] = Field(default_factory=list)
  1280	
  1281	
  1282	class DeleteResult(BaseModel):
  1283	    """Result of 'delete' command."""
  1284	    pack_name: str
  1285	    deleted: bool
  1286	    cleanup_warnings: List[str] = Field(default_factory=list)
  1287	    removed_from_global: bool = False
  1288	    removed_work_profile: bool = False
  1289	    removed_from_stacks: bool = False
  1290	
  1291	
  1292	# =============================================================================
  1293	# Inventory Models (for Model Inventory feature)
  1294	# =============================================================================
  1295	
  1296	class BlobStatus(str, Enum):
  1297	    """Status of a blob in the inventory."""
  1298	    REFERENCED = "referenced"    # Blob exists locally and is used by at least one pack
  1299	    ORPHAN = "orphan"            # Blob exists locally but no pack references it
  1300	    MISSING = "missing"          # Pack references blob but it doesn't exist anywhere
  1301	    BACKUP_ONLY = "backup_only"  # Blob is only on backup storage (not local)
  1302	
  1303	
  1304	class BlobLocation(str, Enum):
  1305	    """Physical location of a blob."""
  1306	    LOCAL_ONLY = "local_only"    # Only on local disk
  1307	    BACKUP_ONLY = "backup_only"  # Only on backup storage
  1308	    BOTH = "both"                # On both local and backup (synced)
  1309	    NOWHERE = "nowhere"          # Missing everywhere
  1310	
  1311	
  1312	class BlobOrigin(BaseModel):
  1313	    """Origin information for a blob - where it came from."""
  1314	    model_config = ConfigDict(protected_namespaces=())
  1315	
  1316	    provider: ProviderName
  1317	    model_id: Optional[int] = None
  1318	    version_id: Optional[int] = None
  1319	    file_id: Optional[int] = None
  1320	    filename: Optional[str] = None
  1321	    repo_id: Optional[str] = None  # For HuggingFace
  1322	
  1323	
  1324	class PackReference(BaseModel):
  1325	    """Reference from a pack to a blob."""
  1326	    pack_name: str
  1327	    dependency_id: str
  1328	    kind: AssetKind
  1329	    expose_filename: Optional[str] = None
  1330	    size_bytes: Optional[int] = None
  1331	    origin: Optional[BlobOrigin] = None
  1332	
  1333	
  1334	class InventoryItem(BaseModel):
  1335	    """A single item in the blob inventory."""
  1336	    sha256: str
  1337	    kind: AssetKind
  1338	    display_name: str  # Priority: expose.filename > origin.filename > sha256[:12]
  1339	    size_bytes: int
  1340	
  1341	    # Location tracking
  1342	    location: BlobLocation
  1343	    on_local: bool
  1344	    on_backup: bool
  1345	
  1346	    # Status and usage
  1347	    status: BlobStatus
  1348	    used_by_packs: List[str] = Field(default_factory=list)  # Pack names
  1349	    ref_count: int = 0  # Total reference count (can be > len(used_by_packs))
  1350	
  1351	    # Origin and context
  1352	    origin: Optional[BlobOrigin] = None
  1353	    active_in_uis: List[str] = Field(default_factory=list)  # UIs currently using this blob
  1354	
  1355	    # Verification status
  1356	    verified: Optional[bool] = None  # True/False/None (not verified)
  1357	
  1358	
  1359	class BackupStats(BaseModel):
  1360	    """Statistics about backup storage."""
  1361	    enabled: bool = False
  1362	    connected: bool = False
  1363	    path: Optional[str] = None
  1364	    blobs_local_only: int = 0
  1365	    blobs_backup_only: int = 0
  1366	    blobs_both: int = 0
  1367	    bytes_local_only: int = 0
  1368	    bytes_backup_only: int = 0
  1369	    bytes_synced: int = 0
  1370	    total_bytes: int = 0
  1371	    free_space: Optional[int] = None
  1372	    last_sync: Optional[str] = None
  1373	
  1374	
  1375	class InventorySummary(BaseModel):
  1376	    """Summary statistics for the inventory."""
  1377	    blobs_total: int = 0
  1378	    blobs_referenced: int = 0
  1379	    blobs_orphan: int = 0
  1380	    blobs_missing: int = 0
  1381	    blobs_backup_only: int = 0
  1382	    bytes_total: int = 0
  1383	    bytes_referenced: int = 0
  1384	    bytes_orphan: int = 0
  1385	    bytes_by_kind: Dict[str, int] = Field(default_factory=dict)
  1386	    disk_total: Optional[int] = None
  1387	    disk_free: Optional[int] = None
  1388	    backup: Optional[BackupStats] = None
  1389	
  1390	
  1391	class InventoryResponse(BaseModel):
  1392	    """Response from inventory endpoint."""
  1393	    generated_at: str
  1394	    summary: InventorySummary
  1395	    items: List[InventoryItem] = Field(default_factory=list)
  1396	
  1397	
  1398	class CleanupResult(BaseModel):
  1399	    """Result of a cleanup operation."""
  1400	    dry_run: bool
  1401	    orphans_found: int = 0
  1402	    orphans_deleted: int = 0
  1403	    bytes_freed: int = 0
  1404	    deleted: List[InventoryItem] = Field(default_factory=list)
  1405	    errors: List[str] = Field(default_factory=list)
  1406	
  1407	
  1408	class MigrateManifestsResult(BaseModel):
  1409	    """Result of manifest migration operation."""
  1410	    dry_run: bool
  1411	    blobs_scanned: int = 0
  1412	    manifests_existing: int = 0
  1413	    manifests_created: int = 0
  1414	    manifests_skipped: int = 0  # Blobs without pack references
  1415	    errors: List[str] = Field(default_factory=list)
  1416	
  1417	
  1418	class ImpactAnalysis(BaseModel):
  1419	    """Analysis of what would break if a blob is deleted."""
  1420	    sha256: str
  1421	    display_name: str = ""  # Human-readable name (from manifest or pack reference)
  1422	    kind: Optional[AssetKind] = None  # Asset type (checkpoint, lora, etc.)
  1423	    status: BlobStatus
  1424	    size_bytes: int
  1425	    used_by_packs: List[str] = Field(default_factory=list)
  1426	    active_in_uis: List[str] = Field(default_factory=list)
  1427	    can_delete_safely: bool
  1428	    warning: Optional[str] = None
  1429	
  1430	
  1431	# =============================================================================
  1432	# Blob Manifest Model (for orphan metadata persistence)
  1433	# =============================================================================
  1434	
  1435	class BlobManifest(BaseModel):
  1436	    """
  1437	    Write-once manifest for blob metadata persistence.
  1438	
  1439	    Created when a blob is first adopted by any pack.
  1440	    Immutable after creation - never updated.
  1441	    Used as fallback for orphan blob display.
  1442	    """
  1443	    version: int = 1  # Schema version
  1444	    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
  1445	    original_filename: str  # Display name from first pack
  1446	    kind: AssetKind  # Asset kind (checkpoint, lora, etc.)
  1447	    origin: Optional[BlobOrigin] = None  # Provider info if available
  1448	
  1449	
  1450	# =============================================================================
  1451	# Backup Storage Models
  1452	# =============================================================================
  1453	
  1454	class BackupStatus(BaseModel):
  1455	    """Status of the backup storage connection."""
  1456	    enabled: bool
  1457	    connected: bool
  1458	    path: Optional[str] = None
  1459	    total_blobs: int = 0
  1460	    total_bytes: int = 0
  1461	    total_space: Optional[int] = None  # Total space on backup drive
  1462	    free_space: Optional[int] = None
  1463	    last_sync: Optional[str] = None
  1464	    error: Optional[str] = None
  1465	    # Config options (for UI)
  1466	    auto_backup_new: bool = False
  1467	    warn_before_delete_last_copy: bool = True
  1468	
  1469	
  1470	class BackupOperationResult(BaseModel):
  1471	    """Result of a backup/restore operation."""
  1472	    success: bool
  1473	    sha256: str
  1474	    bytes_copied: int = 0
  1475	    duration_ms: int = 0
  1476	    error: Optional[str] = None
  1477	    verified: Optional[bool] = None
  1478	
  1479	
  1480	class BackupDeleteResult(BaseModel):
  1481	    """Result of deleting from backup storage."""
  1482	    success: bool
  1483	    sha256: str
  1484	    bytes_freed: int = 0
  1485	    still_on_local: bool = False
  1486	    error: Optional[str] = None
  1487	
  1488	
  1489	class SyncItem(BaseModel):
  1490	    """An item to be synced."""
  1491	    sha256: str
  1492	    size_bytes: int
  1493	    display_name: Optional[str] = None
  1494	    kind: Optional[str] = None  # AssetKind value (checkpoint, lora, vae, etc.)
  1495	
  1496	
  1497	class SyncResult(BaseModel):
  1498	    """Result of a sync operation."""
  1499	    dry_run: bool
  1500	    direction: str  # "to_backup" or "from_backup"
  1501	    blobs_to_sync: int = 0
  1502	    bytes_to_sync: int = 0
  1503	    blobs_synced: int = 0
  1504	    bytes_synced: int = 0
  1505	    items: List[SyncItem] = Field(default_factory=list)
  1506	    errors: List[str] = Field(default_factory=list)
  1507	
  1508	
  1509	# =============================================================================
  1510	# API Response Wrapper
  1511	# =============================================================================
  1512	
  1513	# =============================================================================
  1514	# State Sync Models (for state/ directory backup)
  1515	# =============================================================================
  1516	
  1517	class StateSyncStatus(str, Enum):
  1518	    """Status of a file in state sync."""
  1519	    SYNCED = "synced"              # Same on both sides
  1520	    LOCAL_ONLY = "local_only"      # Only on local
  1521	    BACKUP_ONLY = "backup_only"    # Only on backup
  1522	    MODIFIED = "modified"          # Different on local vs backup
  1523	    CONFLICT = "conflict"          # Both modified since last sync
  1524	
  1525	
  1526	class StateSyncItem(BaseModel):
  1527	    """A single file in the state sync."""
  1528	    relative_path: str  # e.g., "packs/MyPack/pack.json"
  1529	    status: StateSyncStatus
  1530	    local_mtime: Optional[str] = None
  1531	    backup_mtime: Optional[str] = None
  1532	    local_size: Optional[int] = None
  1533	    backup_size: Optional[int] = None
  1534	
  1535	
  1536	class StateSyncSummary(BaseModel):
  1537	    """Summary of state sync status."""
  1538	    total_files: int = 0
  1539	    synced: int = 0
  1540	    local_only: int = 0
  1541	    backup_only: int = 0
  1542	    modified: int = 0
  1543	    conflicts: int = 0
  1544	    last_sync: Optional[str] = None
  1545	
  1546	
  1547	class StateSyncResult(BaseModel):
  1548	    """Result of a state sync operation."""
  1549	    dry_run: bool
  1550	    direction: str  # "to_backup", "from_backup", "bidirectional"
  1551	    summary: StateSyncSummary
  1552	    items: List[StateSyncItem] = Field(default_factory=list)
  1553	    synced_files: int = 0
  1554	    errors: List[str] = Field(default_factory=list)
  1555	
  1556	
  1557	# =============================================================================
  1558	# API Response Wrapper
  1559	# =============================================================================
  1560	
  1561	class APIResponse(BaseModel):
  1562	    """Standard API response wrapper."""
  1563	    ok: bool
  1564	    result: Optional[Any] = None
  1565	    error: Optional[Dict[str, Any]] = None
  1566	
  1567	    @classmethod
  1568	    def success(cls, result: Any) -> "APIResponse":
  1569	        return cls(ok=True, result=result)
  1570	
  1571	    @classmethod
  1572	    def failure(cls, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> "APIResponse":
  1573	        return cls(ok=False, error={"code": code, "message": message, "details": details or {}})

exec
/bin/bash -lc "nl -ba src/store/layout.py | sed -n '65,230p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    65	class StoreLayout:
    66	    """
    67	    Manages the v2 storage layout.
    68	    
    69	    Provides atomic file operations and proper locking for concurrent access.
    70	    """
    71	    
    72	    LOCK_TIMEOUT = 30.0  # seconds
    73	    
    74	    def __init__(self, root: Optional[Path] = None):
    75	        """
    76	        Initialize store layout.
    77	
    78	        Args:
    79	            root: Root directory for the store. Defaults to SYNAPSE_ROOT env var
    80	                  or ~/.synapse/store
    81	        """
    82	        if root is None:
    83	            root = Path(os.environ.get("SYNAPSE_ROOT", Path.home() / ".synapse" / "store"))
    84	        
    85	        self.root = Path(root).expanduser().resolve()
    86	        
    87	        # Check for separate state/data roots
    88	        self.state_root = Path(os.environ.get("SYNAPSE_STATE_ROOT", self.root / "state"))
    89	        self.data_root = Path(os.environ.get("SYNAPSE_DATA_ROOT", self.root / "data"))
    90	    
    91	    # =========================================================================
    92	    # Path Properties
    93	    # =========================================================================
    94	    
    95	    @property
    96	    def state_path(self) -> Path:
    97	        """Path to state directory (git-versioned)."""
    98	        return self.state_root
    99	    
   100	    @property
   101	    def data_path(self) -> Path:
   102	        """Path to data directory (local runtime)."""
   103	        return self.data_root
   104	    
   105	    @property
   106	    def config_path(self) -> Path:
   107	        """Path to config.json."""
   108	        return self.state_path / "config.json"
   109	    
   110	    @property
   111	    def ui_sets_path(self) -> Path:
   112	        """Path to ui_sets.json."""
   113	        return self.state_path / "ui_sets.json"
   114	    
   115	    @property
   116	    def packs_path(self) -> Path:
   117	        """Path to packs directory."""
   118	        return self.state_path / "packs"
   119	    
   120	    @property
   121	    def profiles_path(self) -> Path:
   122	        """Path to profiles directory."""
   123	        return self.state_path / "profiles"
   124	    
   125	    @property
   126	    def blobs_path(self) -> Path:
   127	        """Path to blob store."""
   128	        return self.data_path / "blobs" / "sha256"
   129	    
   130	    @property
   131	    def views_path(self) -> Path:
   132	        """Path to views directory."""
   133	        return self.data_path / "views"
   134	    
   135	    @property
   136	    def registry_path(self) -> Path:
   137	        """Path to registry directory."""
   138	        return self.data_path / "registry"
   139	    
   140	    @property
   141	    def db_path(self) -> Path:
   142	        """Path to SQLite database."""
   143	        return self.registry_path / "index.sqlite"
   144	    
   145	    @property
   146	    def cache_path(self) -> Path:
   147	        """Path to cache directory."""
   148	        return self.data_path / "cache"
   149	    
   150	    @property
   151	    def tmp_path(self) -> Path:
   152	        """Path to temp directory."""
   153	        return self.data_path / "tmp"
   154	    
   155	    @property
   156	    def runtime_path(self) -> Path:
   157	        """Path to runtime.json."""
   158	        return self.data_path / "runtime.json"
   159	    
   160	    @property
   161	    def lock_file_path(self) -> Path:
   162	        """Path to store lock file."""
   163	        return self.data_path / ".synapse.lock"
   164	    
   165	    # =========================================================================
   166	    # Pack Paths
   167	    # =========================================================================
   168	    
   169	    def pack_dir(self, pack_name: str) -> Path:
   170	        """Get directory for a pack."""
   171	        return self.packs_path / pack_name
   172	    
   173	    def pack_json_path(self, pack_name: str) -> Path:
   174	        """Get path to pack.json for a pack."""
   175	        return self.pack_dir(pack_name) / "pack.json"
   176	    
   177	    def pack_lock_path(self, pack_name: str) -> Path:
   178	        """Get path to lock.json for a pack."""
   179	        return self.pack_dir(pack_name) / "lock.json"
   180	    
   181	    def pack_resources_path(self, pack_name: str) -> Path:
   182	        """Get path to resources directory for a pack."""
   183	        return self.pack_dir(pack_name) / "resources"
   184	    
   185	    def pack_previews_path(self, pack_name: str) -> Path:
   186	        """Get path to previews directory for a pack."""
   187	        return self.pack_resources_path(pack_name) / "previews"
   188	    
   189	    def pack_workflows_path(self, pack_name: str) -> Path:
   190	        """Get path to workflows directory for a pack."""
   191	        return self.pack_dir(pack_name) / "workflows"
   192	    
   193	    # =========================================================================
   194	    # Profile Paths
   195	    # =========================================================================
   196	    
   197	    def profile_dir(self, profile_name: str) -> Path:
   198	        """Get directory for a profile."""
   199	        return self.profiles_path / profile_name
   200	    
   201	    def profile_json_path(self, profile_name: str) -> Path:
   202	        """Get path to profile.json for a profile."""
   203	        return self.profile_dir(profile_name) / "profile.json"
   204	    
   205	    # =========================================================================
   206	    # View Paths
   207	    # =========================================================================
   208	    
   209	    def view_ui_path(self, ui_name: str) -> Path:
   210	        """Get path to views for a specific UI."""
   211	        return self.views_path / ui_name
   212	    
   213	    def view_profiles_path(self, ui_name: str) -> Path:
   214	        """Get path to profiles directory within a UI view."""
   215	        return self.view_ui_path(ui_name) / "profiles"
   216	    
   217	    def view_profile_path(self, ui_name: str, profile_name: str) -> Path:
   218	        """Get path to a specific profile within a UI view."""
   219	        return self.view_profiles_path(ui_name) / profile_name
   220	    
   221	    def view_active_path(self, ui_name: str) -> Path:
   222	        """Get path to active symlink for a UI."""
   223	        return self.view_ui_path(ui_name) / "active"
   224	    
   225	    # =========================================================================
   226	    # Blob Paths
   227	    # =========================================================================
   228	    
   229	    def blob_path(self, sha256: str) -> Path:
   230	        """Get path to a blob by its SHA256 hash."""

exec
/bin/bash -lc "nl -ba src/store/layout.py | sed -n '248,524p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   248	    def lock(self, timeout: Optional[float] = None) -> Generator[None, None, None]:
   249	        """
   250	        Acquire exclusive lock on the store.
   251	        
   252	        Args:
   253	            timeout: Lock timeout in seconds. Defaults to LOCK_TIMEOUT.
   254	        
   255	        Raises:
   256	            StoreLockError: If lock cannot be acquired.
   257	        """
   258	        if timeout is None:
   259	            timeout = self.LOCK_TIMEOUT
   260	        
   261	        # Ensure lock file parent exists
   262	        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
   263	        
   264	        lock = filelock.FileLock(self.lock_file_path)
   265	        try:
   266	            lock.acquire(timeout=timeout)
   267	            yield
   268	        except filelock.Timeout:
   269	            raise StoreLockError(
   270	                f"Could not acquire store lock within {timeout}s. "
   271	                "Another operation may be in progress."
   272	            )
   273	        finally:
   274	            lock.release()
   275	    
   276	    # =========================================================================
   277	    # Initialization
   278	    # =========================================================================
   279	    
   280	    def is_initialized(self) -> bool:
   281	        """Check if store is initialized."""
   282	        return self.config_path.exists() and self.state_path.exists()
   283	    
   284	    def init_store(self, force: bool = False) -> None:
   285	        """
   286	        Initialize the store with default configuration.
   287	        
   288	        Args:
   289	            force: If True, reinitialize even if already initialized.
   290	        
   291	        Raises:
   292	            StoreError: If already initialized and force is False.
   293	        """
   294	        if self.is_initialized() and not force:
   295	            # Already initialized, just ensure all directories exist
   296	            self._ensure_directories()
   297	            return
   298	        
   299	        with self.lock():
   300	            self._ensure_directories()
   301	            self._write_default_config()
   302	            self._write_default_ui_sets()
   303	            self._write_default_global_profile()
   304	            self._write_default_runtime()
   305	    
   306	    def _ensure_directories(self) -> None:
   307	        """Ensure all required directories exist."""
   308	        directories = [
   309	            self.state_path,
   310	            self.packs_path,
   311	            self.profiles_path,
   312	            self.data_path,
   313	            self.blobs_path,
   314	            self.views_path,
   315	            self.registry_path,
   316	            self.cache_path,
   317	            self.tmp_path,
   318	        ]
   319	        for d in directories:
   320	            d.mkdir(parents=True, exist_ok=True)
   321	    
   322	    def _write_default_config(self) -> None:
   323	        """Write default config.json."""
   324	        if not self.config_path.exists():
   325	            config = StoreConfig.create_default()
   326	            self.write_json(self.config_path, config.model_dump(by_alias=True))
   327	    
   328	    def _write_default_ui_sets(self) -> None:
   329	        """Write default ui_sets.json."""
   330	        if not self.ui_sets_path.exists():
   331	            ui_sets = UISets.create_default()
   332	            self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
   333	    
   334	    def _write_default_global_profile(self) -> None:
   335	        """Write default global profile."""
   336	        global_profile_path = self.profile_json_path("global")
   337	        if not global_profile_path.exists():
   338	            profile = Profile(name="global")
   339	            global_profile_path.parent.mkdir(parents=True, exist_ok=True)
   340	            self.write_json(global_profile_path, profile.model_dump(by_alias=True))
   341	    
   342	    def _write_default_runtime(self) -> None:
   343	        """Write default runtime.json."""
   344	        if not self.runtime_path.exists():
   345	            # Get known UIs from config or use defaults
   346	            ui_names = ["comfyui", "forge"]
   347	            if self.config_path.exists():
   348	                config = self.load_config()
   349	                ui_names = config.ui.known
   350	            runtime = Runtime.create_default(ui_names)
   351	            self.write_json(self.runtime_path, runtime.model_dump(by_alias=True))
   352	    
   353	    # =========================================================================
   354	    # JSON I/O (Atomic)
   355	    # =========================================================================
   356	    
   357	    def write_json(self, path: Path, data: Dict[str, Any]) -> None:
   358	        """
   359	        Write JSON file atomically with canonical formatting.
   360	        
   361	        Uses write-to-temp-then-rename pattern for atomicity.
   362	        """
   363	        path.parent.mkdir(parents=True, exist_ok=True)
   364	        
   365	        # Write to temp file first
   366	        tmp_path = path.with_suffix(".tmp")
   367	        try:
   368	            with open(tmp_path, "w", encoding="utf-8") as f:
   369	                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
   370	                f.write("\n")  # Trailing newline
   371	            
   372	            # Atomic rename
   373	            tmp_path.replace(path)
   374	        finally:
   375	            # Clean up temp file if it still exists
   376	            if tmp_path.exists():
   377	                tmp_path.unlink()
   378	    
   379	    def read_json(self, path: Path) -> Dict[str, Any]:
   380	        """Read JSON file."""
   381	        with open(path, "r", encoding="utf-8") as f:
   382	            return json.load(f)
   383	    
   384	    # =========================================================================
   385	    # Config Operations
   386	    # =========================================================================
   387	    
   388	    def load_config(self) -> StoreConfig:
   389	        """Load store configuration."""
   390	        if not self.config_path.exists():
   391	            raise StoreNotInitializedError("Store not initialized. Run 'synapse store init' first.")
   392	        data = self.read_json(self.config_path)
   393	        return StoreConfig.model_validate(data)
   394	    
   395	    def save_config(self, config: StoreConfig) -> None:
   396	        """Save store configuration."""
   397	        self.write_json(self.config_path, config.model_dump(by_alias=True))
   398	    
   399	    def load_ui_sets(self) -> UISets:
   400	        """Load UI sets configuration."""
   401	        if not self.ui_sets_path.exists():
   402	            return UISets.create_default()
   403	        data = self.read_json(self.ui_sets_path)
   404	        return UISets.model_validate(data)
   405	    
   406	    def save_ui_sets(self, ui_sets: UISets) -> None:
   407	        """Save UI sets configuration."""
   408	        self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
   409	    
   410	    # =========================================================================
   411	    # Pack Operations
   412	    # =========================================================================
   413	    
   414	    def list_packs(self) -> List[str]:
   415	        """List all pack names."""
   416	        if not self.packs_path.exists():
   417	            return []
   418	        return [
   419	            d.name for d in self.packs_path.iterdir()
   420	            if d.is_dir() and (d / "pack.json").exists()
   421	        ]
   422	    
   423	    def pack_exists(self, pack_name: str) -> bool:
   424	        """Check if a pack exists."""
   425	        return self.pack_json_path(pack_name).exists()
   426	    
   427	    def load_pack(self, pack_name: str) -> Pack:
   428	        """Load a pack by name."""
   429	        path = self.pack_json_path(pack_name)
   430	        if not path.exists():
   431	            raise PackNotFoundError(f"Pack not found: {pack_name}")
   432	        data = self.read_json(path)
   433	        return Pack.model_validate(data)
   434	    
   435	    def save_pack(self, pack: Pack) -> None:
   436	        """Save a pack."""
   437	        path = self.pack_json_path(pack.name)
   438	        path.parent.mkdir(parents=True, exist_ok=True)
   439	        self.write_json(path, pack.model_dump(by_alias=True))
   440	    
   441	    def load_pack_lock(self, pack_name: str) -> Optional[PackLock]:
   442	        """Load lock file for a pack. Returns None if not exists."""
   443	        path = self.pack_lock_path(pack_name)
   444	        if not path.exists():
   445	            return None
   446	        data = self.read_json(path)
   447	        return PackLock.model_validate(data)
   448	    
   449	    def save_pack_lock(self, lock: PackLock) -> None:
   450	        """Save lock file for a pack."""
   451	        path = self.pack_lock_path(lock.pack)
   452	        path.parent.mkdir(parents=True, exist_ok=True)
   453	        self.write_json(path, lock.model_dump(by_alias=True))
   454	    
   455	    def delete_pack(self, pack_name: str) -> bool:
   456	        """Delete a pack. Returns True if deleted."""
   457	        pack_dir = self.pack_dir(pack_name)
   458	        if pack_dir.exists():
   459	            shutil.rmtree(pack_dir)
   460	            return True
   461	        return False
   462	    
   463	    # =========================================================================
   464	    # Profile Operations
   465	    # =========================================================================
   466	    
   467	    def list_profiles(self) -> List[str]:
   468	        """List all profile names."""
   469	        if not self.profiles_path.exists():
   470	            return []
   471	        return [
   472	            d.name for d in self.profiles_path.iterdir()
   473	            if d.is_dir() and (d / "profile.json").exists()
   474	        ]
   475	    
   476	    def profile_exists(self, profile_name: str) -> bool:
   477	        """Check if a profile exists."""
   478	        return self.profile_json_path(profile_name).exists()
   479	    
   480	    def load_profile(self, profile_name: str) -> Profile:
   481	        """Load a profile by name."""
   482	        path = self.profile_json_path(profile_name)
   483	        if not path.exists():
   484	            raise ProfileNotFoundError(f"Profile not found: {profile_name}")
   485	        data = self.read_json(path)
   486	        return Profile.model_validate(data)
   487	    
   488	    def save_profile(self, profile: Profile) -> None:
   489	        """Save a profile."""
   490	        path = self.profile_json_path(profile.name)
   491	        path.parent.mkdir(parents=True, exist_ok=True)
   492	        self.write_json(path, profile.model_dump(by_alias=True))
   493	    
   494	    def delete_profile(self, profile_name: str) -> bool:
   495	        """Delete a profile. Returns True if deleted. Cannot delete 'global'."""
   496	        if profile_name == "global":
   497	            raise StoreError("Cannot delete global profile")
   498	        profile_dir = self.profile_dir(profile_name)
   499	        if profile_dir.exists():
   500	            shutil.rmtree(profile_dir)
   501	            return True
   502	        return False
   503	    
   504	    # =========================================================================
   505	    # Runtime Operations
   506	    # =========================================================================
   507	    
   508	    def load_runtime(self) -> Runtime:
   509	        """Load runtime state."""
   510	        if not self.runtime_path.exists():
   511	            config = self.load_config() if self.config_path.exists() else StoreConfig.create_default()
   512	            return Runtime.create_default(config.ui.known)
   513	        data = self.read_json(self.runtime_path)
   514	        return Runtime.model_validate(data)
   515	    
   516	    def save_runtime(self, runtime: Runtime) -> None:
   517	        """Save runtime state."""
   518	        self.write_json(self.runtime_path, runtime.model_dump(by_alias=True))
   519	    
   520	    # =========================================================================
   521	    # Iteration Helpers
   522	    # =========================================================================
   523	    
   524	    def iter_packs(self) -> Iterator[Tuple[str, Pack]]:

exec
/bin/bash -lc "nl -ba src/store/__init__.py | sed -n '186,360p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   186	class Store:
   187	    """
   188	    Main facade for Synapse Store v2.
   189	    
   190	    Provides high-level operations for managing packs, profiles, and views.
   191	    """
   192	    
   193	    def __init__(
   194	        self,
   195	        root: Optional[Path] = None,
   196	        civitai_client: Optional[Any] = None,
   197	        huggingface_client: Optional[Any] = None,
   198	        civitai_api_key: Optional[str] = None,
   199	    ):
   200	        """
   201	        Initialize the store.
   202	
   203	        Args:
   204	            root: Root directory for the store. Defaults to SYNAPSE_ROOT env var
   205	                  or ~/.synapse/store
   206	            civitai_client: Optional CivitaiClient instance
   207	            huggingface_client: Optional HuggingFaceClient instance
   208	            civitai_api_key: Optional Civitai API key for authenticated downloads
   209	        """
   210	        self.layout = StoreLayout(root)
   211	
   212	        # Centralized download service with auth providers
   213	        logger.info(
   214	            "[Store] Creating DownloadService: civitai_api_key present=%s, length=%d",
   215	            bool(civitai_api_key),
   216	            len(civitai_api_key) if civitai_api_key else 0,
   217	        )
   218	        auth_providers = [CivitaiAuthProvider(civitai_api_key)]
   219	        self.download_service = DownloadService(auth_providers=auth_providers)
   220	
   221	        self.blob_store = BlobStore(
   222	            self.layout,
   223	            api_key=civitai_api_key,
   224	            download_service=self.download_service,
   225	        )
   226	        self.view_builder = ViewBuilder(self.layout, self.blob_store)
   227	
   228	        # Create authenticated CivitaiClient when API key is provided
   229	        # but no explicit client was given (e.g. from get_store() in API)
   230	        if civitai_client is None and civitai_api_key:
   231	            from src.clients.civitai_client import CivitaiClient
   232	            civitai_client = CivitaiClient(api_key=civitai_api_key)
   233	
   234	        self.pack_service = PackService(
   235	            self.layout,
   236	            self.blob_store,
   237	            civitai_client,
   238	            huggingface_client,
   239	            download_service=self.download_service,
   240	        )
   241	        self.profile_service = ProfileService(
   242	            self.layout,
   243	            self.blob_store,
   244	            self.view_builder,
   245	        )
   246	        civitai_provider = CivitaiUpdateProvider(civitai_client)
   247	        self.update_service = UpdateService(
   248	            self.layout,
   249	            self.blob_store,
   250	            self.view_builder,
   251	            providers={
   252	                SelectorStrategy.CIVITAI_MODEL_LATEST: civitai_provider,
   253	            },
   254	        )
   255	        # BackupService initialized with default config, updated when store loads
   256	        self.backup_service = BackupService(
   257	            self.layout,
   258	            BackupConfig(),
   259	        )
   260	        # InventoryService with backup support
   261	        self.inventory_service = InventoryService(
   262	            self.layout,
   263	            self.blob_store,
   264	            self.backup_service,
   265	        )
   266	        # Set backup service on profile service for auto-restore
   267	        self.profile_service.set_backup_service(self.backup_service)
   268	
   269	    # =========================================================================
   270	    # Initialization
   271	    # =========================================================================
   272	    
   273	    def is_initialized(self) -> bool:
   274	        """Check if store is initialized."""
   275	        return self.layout.is_initialized()
   276	    
   277	    def init(self, force: bool = False) -> None:
   278	        """
   279	        Initialize the store.
   280	        
   281	        Args:
   282	            force: If True, reinitialize even if already initialized.
   283	        """
   284	        self.layout.init_store(force)
   285	    
   286	    # =========================================================================
   287	    # Config
   288	    # =========================================================================
   289	    
   290	    def get_config(self) -> StoreConfig:
   291	        """Get store configuration."""
   292	        return self.layout.load_config()
   293	    
   294	    def save_config(self, config: StoreConfig) -> None:
   295	        """Save store configuration."""
   296	        self.layout.save_config(config)
   297	    
   298	    def get_ui_sets(self) -> UISets:
   299	        """Get UI sets configuration."""
   300	        return self.layout.load_ui_sets()
   301	    
   302	    def get_default_ui_set(self) -> str:
   303	        """Get default UI set name from config."""
   304	        config = self.get_config()
   305	        return config.defaults.ui_set
   306	    
   307	    def get_ui_targets(self, ui_set: Optional[str] = None) -> List[str]:
   308	        """
   309	        Get UI targets for a UI set.
   310	        
   311	        Args:
   312	            ui_set: Name of UI set. Uses default if None.
   313	        
   314	        Returns:
   315	            List of UI names
   316	        """
   317	        if ui_set is None:
   318	            ui_set = self.get_default_ui_set()
   319	        
   320	        ui_sets = self.get_ui_sets()
   321	        return ui_sets.sets.get(ui_set, [])
   322	    
   323	    # =========================================================================
   324	    # Pack Operations
   325	    # =========================================================================
   326	    
   327	    def list_packs(self) -> List[str]:
   328	        """List all pack names."""
   329	        return self.pack_service.list_packs()
   330	    
   331	    def list_models(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
   332	        """
   333	        List all installed models in the store.
   334	        
   335	        Args:
   336	            kind: Optional filter by asset kind (e.g., 'checkpoint', 'lora')
   337	            
   338	        Returns:
   339	            List of model details
   340	        """
   341	        models = []
   342	        for pack_name in self.list_packs():
   343	            try:
   344	                pack = self.get_pack(pack_name)
   345	                lock = self.get_pack_lock(pack_name)
   346	                if not lock:
   347	                    continue
   348	                
   349	                for dep in pack.dependencies:
   350	                    # Filter by kind if specified
   351	                    dep_kind = dep.kind.value if hasattr(dep.kind, 'value') else str(dep.kind)
   352	                    if kind and kind.lower() != dep_kind.lower():
   353	                        continue
   354	                    
   355	                    resolved = lock.get_resolved(dep.id)
   356	                    if resolved and resolved.artifact.sha256:
   357	                        if self.blob_store.blob_exists(resolved.artifact.sha256):
   358	                            # Get preview image if available
   359	                            preview_url = None
   360	                            previews_dir = self.layout.pack_previews_path(pack_name)

exec
/bin/bash -lc "nl -ba src/store/__init__.py | sed -n '884,1045p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   884	    def status(
   885	        self,
   886	        ui_targets: Optional[List[str]] = None,
   887	        ui_set: Optional[str] = None,
   888	    ) -> StatusReport:
   889	        """
   890	        Get current status.
   891	        
   892	        Args:
   893	            ui_targets: List of UI names. If None, uses ui_set.
   894	            ui_set: Name of UI set to use. Uses default if None.
   895	        
   896	        Returns:
   897	            StatusReport with current state
   898	        """
   899	        if ui_targets is None:
   900	            ui_targets = self.get_ui_targets(ui_set)
   901	        
   902	        runtime = self.layout.load_runtime()
   903	        
   904	        # Get active profiles
   905	        active = {ui: runtime.get_active_profile(ui) for ui in ui_targets}
   906	        
   907	        # Determine which profile to report on (use first UI's active)
   908	        if ui_targets:
   909	            profile_name = active.get(ui_targets[0], "global")
   910	        else:
   911	            profile_name = "global"
   912	        
   913	        # Collect missing blobs and unresolved
   914	        missing_blobs = []
   915	        unresolved = []
   916	        
   917	        try:
   918	            profile = self.layout.load_profile(profile_name)
   919	            
   920	            for pack_entry in profile.packs:
   921	                try:
   922	                    pack = self.layout.load_pack(pack_entry.name)
   923	                    lock = self.layout.load_pack_lock(pack_entry.name)
   924	                    
   925	                    if lock:
   926	                        # Check resolved
   927	                        for resolved in lock.resolved:
   928	                            sha256 = resolved.artifact.sha256
   929	                            if sha256 and not self.blob_store.blob_exists(sha256):
   930	                                dep = pack.get_dependency(resolved.dependency_id)
   931	                                missing_blobs.append(MissingBlob(
   932	                                    pack=pack_entry.name,
   933	                                    dependency_id=resolved.dependency_id,
   934	                                    kind=dep.kind if dep else AssetKind.UNKNOWN,
   935	                                    sha256=sha256,
   936	                                ))
   937	                        
   938	                        # Check unresolved
   939	                        for unres in lock.unresolved:
   940	                            unresolved.append(UnresolvedReport(
   941	                                pack=pack_entry.name,
   942	                                dependency_id=unres.dependency_id,
   943	                                reason=unres.reason,
   944	                                details=unres.details,
   945	                            ))
   946	                except Exception:
   947	                    pass
   948	        except Exception:
   949	            pass
   950	        
   951	        # Get shadowed entries (would need to compute view plan for accurate info)
   952	        shadowed: List[ShadowedEntry] = []
   953	        
   954	        return StatusReport(
   955	            profile=profile_name,
   956	            ui_targets=ui_targets,
   957	            active=active,
   958	            missing_blobs=missing_blobs,
   959	            unresolved=unresolved,
   960	            shadowed=shadowed,
   961	        )
   962	    
   963	    # =========================================================================
   964	    # Doctor
   965	    # =========================================================================
   966	    
   967	    def doctor(
   968	        self,
   969	        rebuild_views: bool = True,
   970	        rebuild_db: Optional[str] = None,
   971	        verify_blobs: bool = False,
   972	        ui_targets: Optional[List[str]] = None,
   973	        ui_set: Optional[str] = None,
   974	    ) -> DoctorReport:
   975	        """
   976	        Run diagnostics and repairs.
   977	        
   978	        Args:
   979	            rebuild_views: If True, rebuild all views
   980	            rebuild_db: "auto" or "force" to rebuild DB
   981	            verify_blobs: If True, verify all blob hashes
   982	            ui_targets: List of UI names
   983	            ui_set: Name of UI set
   984	        
   985	        Returns:
   986	            DoctorReport with actions taken
   987	        """
   988	        from .models import DoctorActions
   989	        
   990	        if ui_targets is None:
   991	            ui_targets = self.get_ui_targets(ui_set)
   992	        
   993	        runtime = self.layout.load_runtime()
   994	        profile_name = runtime.get_active_profile(ui_targets[0]) if ui_targets else "global"
   995	        
   996	        actions = DoctorActions()
   997	        notes = []
   998	        
   999	        # Verify blobs if requested
  1000	        if verify_blobs:
  1001	            valid, invalid = self.blob_store.verify_all()
  1002	            actions.blobs_verified = True
  1003	            if invalid:
  1004	                notes.append(f"Found {len(invalid)} invalid blobs")
  1005	        
  1006	        # Rebuild views if requested
  1007	        if rebuild_views:
  1008	            try:
  1009	                profile = self.layout.load_profile(profile_name)
  1010	                
  1011	                # Load packs
  1012	                packs_data = {}
  1013	                for p in profile.packs:
  1014	                    try:
  1015	                        pack = self.layout.load_pack(p.name)
  1016	                        lock = self.layout.load_pack_lock(p.name)
  1017	                        packs_data[p.name] = (pack, lock)
  1018	                    except Exception:
  1019	                        pass
  1020	                
  1021	                # Build for each UI
  1022	                for ui in ui_targets:
  1023	                    self.view_builder.build(ui, profile, packs_data)
  1024	                    self.view_builder.activate(ui, profile_name)
  1025	                
  1026	                actions.views_rebuilt = True
  1027	            except Exception as e:
  1028	                notes.append(f"Failed to rebuild views: {e}")
  1029	        
  1030	        # DB rebuild (placeholder - SQLite not implemented yet)
  1031	        if rebuild_db:
  1032	            actions.db_rebuilt = rebuild_db
  1033	            notes.append("SQLite DB not implemented yet")
  1034	        
  1035	        # Get current status
  1036	        status = self.status(ui_targets)
  1037	        
  1038	        return DoctorReport(
  1039	            profile=profile_name,
  1040	            ui_targets=ui_targets,
  1041	            actions=actions,
  1042	            active=status.active,
  1043	            missing_blobs=status.missing_blobs,
  1044	            unresolved=status.unresolved,
  1045	            shadowed=status.shadowed,

exec
/bin/bash -lc "rg -n \"pack_path\\(|enabled|conflicts\\.mode|conflicts|shadowed|pack_dependencies|default_ui_set|store_ui_sets|ui_sets|active_in_uis\" src/store apps/web plans -g'*.py' -g'*.ts' -g'*.tsx' -g'*.md'" in /home/box/git/github/synapse
 succeeded in 0ms:
plans/PLAN-Release-1-Roadmap.md:152:  na jiný pack (`pack_dependencies`)? Funguje resolving?
plans/PLAN-Internal-Search-trpc.md:462:      getStatus(): { enabled: boolean; nsfw: boolean; version: string }
plans/PLAN-Internal-Search-trpc.md:825:            enabled: GM_getValue('synapse_bridge_enabled', true),
plans/PLAN-Internal-Search-trpc.md:831:        if (updates.enabled !== undefined) GM_setValue('synapse_bridge_enabled', updates.enabled);
plans/PLAN-Internal-Search-trpc.md:968:        isEnabled: () => getConfig().enabled,
plans/PLAN-Internal-Search-trpc.md:973:                enabled: config.enabled,
plans/PLAN-Internal-Search-trpc.md:986:            if (!config.enabled) {
plans/PLAN-Internal-Search-trpc.md:996:            if (!config.enabled) {
plans/PLAN-Internal-Search-trpc.md:1118:  enabled: true,
plans/PLAN-Internal-Search-trpc.md:1314:  it('should be available when bridge is enabled', () => {
plans/PLAN-Internal-Search-trpc.md:1318:      getStatus: () => ({ enabled: true, nsfw: true, version: '8.0.0' }),
plans/audit-resolve-model-redesign-local.md:63:2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
plans/audit-resolve-model-redesign-local.md:134:2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
plans/PLAN-Dependencies.md:68:**E) Pack model nemá duplikát validaci pro pack_dependencies**
plans/PLAN-Dependencies.md:70:- ALE žádná validace pro duplicitní `pack_name` v `pack_dependencies`
plans/PLAN-Dependencies.md:83:**G) resolve_pack() a plan_update() ignorují pack_dependencies**
plans/PLAN-Dependencies.md:86:- pack_dependencies nejsou nikde resolvovány na backendu
plans/PLAN-Dependencies.md:120:    pack_dependencies: List[PackDependencyRef] = [] # Odkazy na packy
plans/PLAN-Dependencies.md:198:**2a) `models.py` → validátor pro pack_dependencies** ✅
plans/PLAN-Dependencies.md:200:- Kontrola: žádné duplicitní `pack_name` v `pack_dependencies`
plans/PLAN-Dependencies.md:238:- [x] `tests/store/test_pack_dependencies.py` - 18 testů, all passing
plans/PLAN-Dependencies.md:344:ADD     tests/store/test_pack_dependencies.py
plans/PLAN-Dependencies.md:379:| No pack_dependencies CRUD endpoints | 🔴 HIGH | Phase 2 |
plans/PLAN-Dependencies.md:381:| `resolve_pack()` ignores pack_dependencies | 🟡 MED | Phase 2 (info only) |
plans/PLAN-Dependencies.md:382:| `plan_update()` ignores pack_dependencies | 🟡 MED | Phase 3 |
src/store/pack_service.py:521:            pack_dependencies=[],  # No pack dependencies by default
src/store/pack_service.py:1038:            start_index: Starting index for numbering (to avoid filename conflicts)
plans/PLAN-i18n.md:268:   - [x] ProfilesPage.tsx hlavní stránka (profiles.* namespace - title, subtitle, activeProfiles, stack, shadowed, toast, table, error)
plans/PLAN-Phase-6-Store-UI.md:27:│   ├── ui_sets.json                # UI set definice (local, all, comfyui, ...)
plans/PLAN-Phase-6-Store-UI.md:213:| GET | `/status` | Kompletní status (stack per UI, shadowed) |
plans/PLAN-Phase-6-Store-UI.md:356:- Tabulka shadowed souborů
plans/PLAN-Phase-6-Store-UI.md:499:7. **Shadowed warning** - UI zobrazuje shadowed pro první UI, ne per-UI? (Low priority)
plans/PLAN-Phase-6-Store-UI.md:623:    shadowed: List[ShadowedEntry]
src/store/models.py:9:- synapse.ui_sets.v1
src/store/models.py:230:    conflicts_mode: ConflictMode = ConflictMode.LAST_WINS
src/store/models.py:237:    enabled: bool = False
src/store/models.py:311:# UI Sets Model (state/ui_sets.json)
src/store/models.py:315:    """UI sets configuration (state/ui_sets.json)."""
src/store/models.py:316:    schema_: str = Field(default="synapse.ui_sets.v1", alias="schema")
src/store/models.py:670:                if lower in ("true", "yes", "1", "enabled", "on", "recommended", "required", "must"):
src/store/models.py:743:                        if lower in ("true", "yes", "1", "enabled", "on"):
src/store/models.py:845:    pack_dependencies: List[PackDependencyRef] = Field(default_factory=list)  # Dependencies on other packs
src/store/models.py:905:        names = [ref.pack_name for ref in self.pack_dependencies]
src/store/models.py:1021:    conflicts: ConflictConfig = Field(default_factory=ConflictConfig)
src/store/models.py:1127:    """Report entry for a shadowed file (conflict resolved by last_wins)."""
src/store/models.py:1141:    shadowed: List[ShadowedEntry] = Field(default_factory=list)
src/store/models.py:1231:    shadowed: List[ShadowedEntry] = Field(default_factory=list)
src/store/models.py:1260:    shadowed: List[ShadowedEntry] = Field(default_factory=list)
src/store/models.py:1353:    active_in_uis: List[str] = Field(default_factory=list)  # UIs currently using this blob
src/store/models.py:1361:    enabled: bool = False
src/store/models.py:1426:    active_in_uis: List[str] = Field(default_factory=list)
src/store/models.py:1456:    enabled: bool
src/store/models.py:1543:    conflicts: int = 0
plans/PLAN-Pack-Edit.md:137:    pack_dependencies: List[PackDependencyRef]  # 🆕 Dependencies on OTHER PACKS
plans/PLAN-Pack-Edit.md:257:- ⚠️ CHYBÍ `pack_dependencies` → nastavit na `[]` (prázdný list)
plans/PLAN-Pack-Edit.md:1498:- [x] Přidat `pack_dependencies` field do `Pack` modelu (default: [])
plans/PLAN-Pack-Edit.md:2529:    pack_dependencies: PackDependencyRef[]
plans/PLAN-Pack-Edit.md:2585:- Added `pack_dependencies: List[PackDependencyRef] = []`
plans/PLAN-Install-Packs.md:253:| How to handle port conflicts? | Open |
plans/PLAN-AI-Services.md:316:    enabled: bool = False
plans/PLAN-AI-Services.md:339:    enabled: bool = True
plans/PLAN-AI-Services.md:353:    cache_enabled: bool = True
plans/PLAN-AI-Services.md:647:            if not provider or not self._is_provider_enabled(provider_type):
plans/PLAN-AI-Services.md:817:  enabled: boolean
plans/PLAN-AI-Services.md:842:  enabled: boolean
src/store/api.py:138:    shadowed: List[Dict[str, Any]]
src/store/api.py:139:    shadowed_count: int
src/store/api.py:344:        # Store config reference for later use (e.g., ui_roots, ui_sets)
src/store/api.py:528:    enabled: bool = False
src/store/api.py:983:    Returns 400 if backup not enabled, 503 if not connected,
src/store/api.py:989:        if "not enabled" in error.lower():
src/store/api.py:1012:    Returns 400 if backup not enabled, 503 if not connected,
src/store/api.py:1018:        if "not enabled" in error.lower():
src/store/api.py:1048:        elif "not enabled" in error.lower():
src/store/api.py:1090:        enabled=request.enabled,
src/store/api.py:1148:    Returns 400 if backup not enabled, 503 if not connected,
src/store/api.py:1176:        raise HTTPException(status_code=400, detail="Backup not enabled")
src/store/api.py:1194:    Returns 400 if backup not enabled, 503 if not connected,
src/store/api.py:1227:        raise HTTPException(status_code=400, detail="Backup not enabled")
src/store/api.py:1247:    backup_enabled = backup_status.enabled
src/store/api.py:1250:    logger.info(f"[pack-status] Called for pack: {pack_name}, backup_enabled={backup_enabled}, backup_connected={backup_connected}")
src/store/api.py:1259:                "backup_enabled": backup_enabled,
src/store/api.py:1323:            "backup_enabled": backup_enabled,
src/store/api.py:1354:            "enabled": store.backup_service.config.enabled,
src/store/api.py:1364:                "conflicts": result.summary.conflicts,
src/store/api.py:1382:            "enabled": False,
src/store/api.py:1390:                "conflicts": 0,
src/store/api.py:1394:            "errors": ["Backup not enabled"],
src/store/api.py:1398:            "enabled": True,
src/store/api.py:1406:                "conflicts": 0,
src/store/api.py:1442:                "conflicts": result.summary.conflicts,
src/store/api.py:1460:        raise HTTPException(status_code=400, detail="Backup not enabled")
src/store/api.py:2964:def get_pack_dependencies_status(
src/store/api.py:2976:        for ref in pack.pack_dependencies:
src/store/api.py:3051:        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
src/store/api.py:3063:        pack.pack_dependencies.append(new_ref)
src/store/api.py:3091:        original_count = len(pack.pack_dependencies)
src/store/api.py:3092:        pack.pack_dependencies = [
src/store/api.py:3093:            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
src/store/api.py:3096:        if len(pack.pack_dependencies) == original_count:
src/store/api.py:3172:            if depth < max_depth and p.pack_dependencies:
src/store/api.py:3173:                for ref in p.pack_dependencies:
src/store/api.py:3334:        pack_path = store.layout.pack_path(request.name)
src/store/api.py:3424:            old_path = store.layout.pack_path(pack_name)
src/store/api.py:4078:        pack_dir = store.layout.pack_path(pack_name)
src/store/api.py:4581:        pack_dir = store.layout.pack_path(pack_name)
src/store/api.py:4602:            # Create symlink with pack prefix to avoid conflicts
src/store/api.py:4739:        pack_dir = store.layout.pack_path(pack_name)
src/store/api.py:4790:        pack_dir = store.layout.pack_path(pack_name)
src/store/api.py:4859:        pack_dir = store.layout.pack_path(pack_name)
src/store/api.py:4958:            pack_dir = store.layout.pack_path(pack_name)
src/store/api.py:5019:    Returns per-UI runtime status, stack visualization, and shadowed files.
src/store/api.py:5039:        # Get status for shadowed info
src/store/api.py:5042:        # Convert shadowed entries to dicts
src/store/api.py:5043:        all_shadowed = []
src/store/api.py:5044:        for entry in status.shadowed:
src/store/api.py:5045:            all_shadowed.append({
src/store/api.py:5057:            shadowed=all_shadowed,
src/store/api.py:5058:            shadowed_count=len(all_shadowed),
src/store/api.py:5113:                "shadowed_count": len(r.shadowed),
apps/web/e2e/avatar-providers.spec.ts:48:    // Each provider config has model and enabled fields
apps/web/e2e/avatar-providers.spec.ts:53:      expect(config).toHaveProperty('enabled')
apps/web/e2e/avatar-providers.spec.ts:54:      expect(typeof config.enabled).toBe('boolean')
apps/web/e2e/avatar-chat.spec.ts:103:    // Check if WS is connected by waiting for textarea to be enabled
src/store/__init__.py:298:    def get_ui_sets(self) -> UISets:
src/store/__init__.py:300:        return self.layout.load_ui_sets()
src/store/__init__.py:302:    def get_default_ui_set(self) -> str:
src/store/__init__.py:318:            ui_set = self.get_default_ui_set()
src/store/__init__.py:320:        ui_sets = self.get_ui_sets()
src/store/__init__.py:321:        return ui_sets.sets.get(ui_set, [])
src/store/__init__.py:951:        # Get shadowed entries (would need to compute view plan for accurate info)
src/store/__init__.py:952:        shadowed: List[ShadowedEntry] = []
src/store/__init__.py:960:            shadowed=shadowed,
src/store/__init__.py:1045:            shadowed=status.shadowed,
apps/web/e2e/avatar-api.spec.ts:32:    expect(typeof data.enabled).toBe('boolean')
apps/web/e2e/avatar-api.spec.ts:37:    expect(typeof data.enabled).toBe('boolean')
apps/web/e2e/avatar-api.spec.ts:108:    expect(typeof data.enabled).toBe('boolean')
apps/web/e2e/avatar-api.spec.ts:111:    expect(typeof data.cache_enabled).toBe('boolean')
src/store/update_service.py:258:        Find all packs that depend on the given pack via pack_dependencies.
src/store/update_service.py:261:            List of pack names that have pack_name in their pack_dependencies.
src/store/update_service.py:269:                dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
plans/PLAN-Phase-4.md:962:| NSFW pack + blur enabled | Thumbnail rozmazaný, video NEHRAJE |
plans/PLAN-Phase-4.md:1866:// Reset revealed state when blur is re-enabled
src/store/profile_service.py:130:            conflicts=base.conflicts,
src/store/profile_service.py:162:            conflicts=base.conflicts,
src/store/profile_service.py:222:            shadowed=[],
src/store/profile_service.py:243:                result.shadowed.extend(report.shadowed)
src/store/profile_service.py:267:        ui_sets = self.layout.load_ui_sets()
src/store/profile_service.py:268:        ui_targets = ui_sets.sets.get(ui_set_name, [])
src/store/profile_service.py:361:        ui_sets = self.layout.load_ui_sets()
src/store/profile_service.py:362:        ui_targets = ui_sets.sets.get(ui_set_name, [])
src/store/profile_service.py:410:        ui_sets = self.layout.load_ui_sets()
src/store/profile_service.py:411:        ui_targets = ui_sets.sets.get(ui_set_name, [])
src/store/layout.py:7:  - ui_sets.json
src/store/layout.py:111:    def ui_sets_path(self) -> Path:
src/store/layout.py:112:        """Path to ui_sets.json."""
src/store/layout.py:113:        return self.state_path / "ui_sets.json"
src/store/layout.py:302:            self._write_default_ui_sets()
src/store/layout.py:328:    def _write_default_ui_sets(self) -> None:
src/store/layout.py:329:        """Write default ui_sets.json."""
src/store/layout.py:330:        if not self.ui_sets_path.exists():
src/store/layout.py:331:            ui_sets = UISets.create_default()
src/store/layout.py:332:            self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
src/store/layout.py:399:    def load_ui_sets(self) -> UISets:
src/store/layout.py:401:        if not self.ui_sets_path.exists():
src/store/layout.py:403:        data = self.read_json(self.ui_sets_path)
src/store/layout.py:406:    def save_ui_sets(self, ui_sets: UISets) -> None:
src/store/layout.py:408:        self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
src/store/inventory_service.py:377:            active_in_uis=[],  # TODO: Get from runtime
src/store/inventory_service.py:454:                enabled=backup_status.enabled,
src/store/inventory_service.py:583:                active_in_uis=[],
src/store/inventory_service.py:613:            active_in_uis=item.active_in_uis,
plans/PLAN-Model-Inventory.md:143:    "enabled": true,
plans/PLAN-Model-Inventory.md:295:    active_in_uis: List[str] = []       # Ktera UI ho prave pouzivaji
plans/PLAN-Model-Inventory.md:330:    active_in_uis: List[str]
plans/PLAN-Model-Inventory.md:368:      "enabled": true,
plans/PLAN-Model-Inventory.md:397:      "active_in_uis": ["comfyui", "forge"],
plans/PLAN-Model-Inventory.md:517:  "enabled": true,
plans/PLAN-Model-Inventory.md:530:  "enabled": true,
plans/PLAN-Model-Inventory.md:559:- 400: Backup not enabled
plans/PLAN-Model-Inventory.md:586:- 400: Backup not enabled
plans/PLAN-Model-Inventory.md:864:                active_in_uis=[],
plans/PLAN-Model-Inventory.md:880:            active_in_uis=item.active_in_uis,
plans/PLAN-Model-Inventory.md:1188:        !backupStatus?.connected && backupStatus?.enabled && 'border-amber-500/50'
plans/PLAN-Model-Inventory.md:1197:          {!backupStatus?.enabled ? (
plans/PLAN-Model-Inventory.md:2145:    enabled: open,
plans/PLAN-Model-Inventory.md:2659:    if not status.enabled:
plans/PLAN-Model-Inventory.md:2812:        config.backup_enabled = True
plans/PLAN-Model-Inventory.md:2815:        config.backup_enabled = False
plans/PLAN-Model-Inventory.md:2821:    console.print(f"  Enabled: {'[green]Yes[/green]' if config.backup_enabled else '[dim]No[/dim]'}")
plans/PLAN-Model-Inventory.md:3013:        assert data["enabled"] is False
plans/PLAN-Model-Inventory.md:3022:        assert data["enabled"] is True
plans/PLAN-Model-Inventory.md:3122:        store.configure_backup(path=str(backup_path), enabled=True)
plans/PLAN-Model-Inventory.md:3224:        assert status.enabled is True
plans/PLAN-Model-Inventory.md:3358:  - Dynamické zobrazení podle backup stavu (enabled/connected/disconnected)
plans/PLAN-Model-Inventory.md:3613:| Mixed | Pull, Push | Obě enabled |
plans/PLAN-Model-Inventory.md:3889:- Test pro error handling (pack not found, backup not enabled)
plans/PLAN-Model-Inventory.md:4081:- Config (config.json, ui_sets.json)
plans/PLAN-Model-Inventory.md:4472:## 19. 🔴 KRITICKÁ CHYBA: is_enabled() metoda neexistovala (2026-01-25)
plans/PLAN-Model-Inventory.md:4482:"backup_enabled": store.backup_service.is_enabled(),  # AttributeError!
plans/PLAN-Model-Inventory.md:4485:`BackupService` měla `is_connected()`, ale NE `is_enabled()`.
plans/PLAN-Model-Inventory.md:4497:def is_enabled(self) -> bool:
plans/PLAN-Model-Inventory.md:4498:    """Quick check if backup is enabled in config."""
plans/PLAN-Model-Inventory.md:4499:    return self.config.enabled
plans/PLAN-Model-Inventory.md:4598:# Vrátí: { "pack": "...", "backup_enabled": true, "backup_connected": true, ... }
src/store/cli.py:403:        if result.shadowed:
src/store/cli.py:404:            output_warning(f"{len(result.shadowed)} shadowed file(s)")
src/store/cli.py:527:                enabled = "[green]✓[/green]" if pack_entry.enabled else "[red]✗[/red]"
src/store/cli.py:528:                console.print(f"  {i}. {enabled} [cyan]{pack_entry.name}[/cyan]")
src/store/cli.py:577:            if status.shadowed:
src/store/cli.py:579:                output_info(f"{len(status.shadowed)} shadowed file(s) (last pack wins)")
src/store/cli.py:879:            if report.shadowed:
src/store/cli.py:880:                console.print(f"\n[dim]Shadowed ({len(report.shadowed)}):[/dim]")
src/store/cli.py:881:                for sh in report.shadowed[:5]:
src/store/cli.py:979:            shadowed = len(report.get("shadowed", []))
src/store/cli.py:980:            console.print(f"  [cyan]{ui}[/cyan]: {entries} entries, {shadowed} shadowed")
src/store/cli.py:1463:            if not status.enabled:
src/store/cli.py:1672:                enabled=enable if enable is not None else current_status.enabled,
src/store/cli.py:1684:                "enabled": status.enabled,
src/store/cli.py:1690:            console.print(f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if status.enabled else '[red]No[/red]'}")
src/store/cli.py:1694:            if not status.enabled:
src/store/cli.py:1877:            if "not enabled" in err.lower():
src/store/cli.py:1878:                output_warning("Backup not enabled")
src/store/cli.py:1898:    if summary.conflicts > 0:
src/store/cli.py:1899:        console.print(f"[red]Conflicts:[/red] {summary.conflicts}")
src/store/cli.py:1959:            if "not enabled" in err.lower():
src/store/cli.py:1960:                output_error("Backup not enabled. Configure with: synapse backup config --enable --path /path")
plans/PLAN-Avatar-TaskService.md:83:- Sdílený `AICache`, TTL a `cache_enabled` z `config.extraction`
plans/PLAN-Avatar-TaskService.md:276:- Test coverage pro MCP-enabled tasky (mock MCP server)
plans/PLAN-Avatar-TaskService.md:299:Všechny tasky sdílejí `config.extraction.cache_enabled` a `cache_ttl_days`. Pro různé tasky může dávat smysl jiný TTL:
src/store/backup_service.py:51:    """Backup is not enabled in config."""
src/store/backup_service.py:152:        if not self.config.enabled:
src/store/backup_service.py:154:                enabled=False,
src/store/backup_service.py:164:                enabled=True,
src/store/backup_service.py:176:                enabled=True,
src/store/backup_service.py:192:                enabled=True,
src/store/backup_service.py:202:                enabled=True,
src/store/backup_service.py:233:            enabled=True,
src/store/backup_service.py:245:    def is_enabled(self) -> bool:
src/store/backup_service.py:246:        """Quick check if backup is enabled in config."""
src/store/backup_service.py:247:        return self.config.enabled
src/store/backup_service.py:252:        return status.enabled and status.connected
src/store/backup_service.py:256:        if not self.config.enabled:
src/store/backup_service.py:257:            logger.warning("[Backup] Operation failed: backup not enabled")
src/store/backup_service.py:258:            raise BackupNotEnabledError("Backup storage is not enabled")
src/store/backup_service.py:269:        if not self.config.enabled:
src/store/backup_service.py:897:                result.summary.conflicts += 1
src/store/README.md:93:│   ├── ui_sets.json                # UI set definitions
src/store/README.md:269:    "enabled": true,
src/store/view_builder.py:68:    shadowed: List[ShadowedEntry] = field(default_factory=list)
src/store/view_builder.py:95:                shadowed = ShadowedEntry(
src/store/view_builder.py:101:                self.shadowed.append(shadowed)
src/store/view_builder.py:112:                return shadowed
src/store/view_builder.py:132:    shadowed: List[ShadowedEntry] = field(default_factory=list)
src/store/view_builder.py:227:            ViewPlan with entries and shadowed info
src/store/view_builder.py:304:            shadowed=plan.shadowed,
src/store/view_builder.py:362:        ui_sets = self.layout.load_ui_sets()
src/store/view_builder.py:363:        ui_names = ui_sets.sets.get(ui_set_name, [])
src/store/view_builder.py:418:        ui_sets = self.layout.load_ui_sets()
src/store/view_builder.py:419:        ui_names = ui_sets.sets.get(ui_set_name, [])
plans/PLAN-Updates.md:190:  enabled: false, // Manual only
plans/PLAN-Updates.md:720:- [x] Desktop notifications via Notification API (auto-requested when auto-check enabled)
plans/PLAN-Updates.md:929:- ✅ Desktop notifications via Notification API (auto-requested when auto-check enabled)
plans/ai_extraction_spec.md:291:    Tries each enabled provider in priority order. Falls back to rule-based
plans/ai_extraction_spec.md:304:        if not provider_cfg.enabled:
plans/audits/codex-domain-audit-raw.md:52:   - Pack has: name, pack_category, source, dependencies, pack_dependencies, parameters,
plans/audits/codex-domain-audit-raw.md:56:   - `pack_dependencies` (pack-to-pack) — how do they compose? Recursive expansion?
plans/audits/codex-domain-audit-raw.md:82:   - Profile.packs vs Profile.pack_dependencies — same thing? different?
plans/audits/codex-domain-audit-raw.md:83:   - ProfilePackEntry — has `enabled` field, but ViewBuilder ignores it. Should the
plans/audits/codex-domain-audit-raw.md:84:     enabled flag exist if no consumer honors it? Or should we wire it?
plans/audits/codex-domain-audit-raw.md:87:   - Profile.conflicts.mode — modeled but only last_wins implemented. Remove or wire?
plans/audits/codex-domain-audit-raw.md:88:   - ShadowedEntry — when computed, where stored? StatusReport.shadowed is empty —
plans/audits/codex-domain-audit-raw.md:113:    - Is `default_ui_set` stored authoritatively in one place or two (state vs config)?
plans/audits/codex-domain-audit-raw.md:126:    - ProfilePackEntry.enabled ignored.
plans/audits/codex-domain-audit-raw.md:127:    - Profile.conflicts.mode ignored.
plans/audits/codex-domain-audit-raw.md:128:    - StatusReport.shadowed always empty.
plans/audits/codex-domain-audit-raw.md:130:    - Pack.layout.pack_path() does not exist; layout.pack_dir() does — possible crash
plans/audits/codex-domain-audit-raw.md:132:    - Source-of-truth split between state/ui_sets.json and app config store_ui_sets.
plans/audits/codex-domain-audit-raw.md:277:  `pack_category`, `source`, `dependencies`, `pack_dependencies`, `parameters`,
plans/audits/codex-domain-audit-raw.md:305:- **`pack_dependencies` se NESEMANTICKY rekurzivně neexpanduje do profilu.**
plans/audits/codex-domain-audit-raw.md:308:  `pack_dependencies`, použití A NEPŘIDÁ B do view symlinks.
plans/audits/codex-domain-audit-raw.md:324:4. **Jsou `pack_dependencies` operační (mění profile/view symlinks), nebo informační?**
plans/audits/codex-domain-audit-raw.md:325:5. **Pokud operační — má `use(pack)` rekurzivně zahrnout `pack_dependencies`?**
plans/audits/codex-domain-audit-raw.md:326:6. **Mají optional `pack_dependencies` být zahrnuté automaticky, nebo jen warning?**
plans/audits/codex-domain-audit-raw.md:349:  vytvoří symlinks. **Neexpanduje `pack_dependencies` rekurzivně** (kritická díra).
plans/audits/codex-domain-audit-raw.md:472:src/store/backup_service.py:245:    def is_enabled(self) -> bool:
plans/audits/codex-domain-audit-raw.md:567:src/store/inventory_service.py:377:            active_in_uis=[],  # TODO: Get from runtime
plans/audits/codex-domain-audit-raw.md:610:src/store/__init__.py:298:    def get_ui_sets(self) -> UISets:
plans/audits/codex-domain-audit-raw.md:611:src/store/__init__.py:302:    def get_default_ui_set(self) -> str:
plans/audits/codex-domain-audit-raw.md:803:src/store/layout.py:111:    def ui_sets_path(self) -> Path:
plans/audits/codex-domain-audit-raw.md:834:src/store/layout.py:328:    def _write_default_ui_sets(self) -> None:
plans/audits/codex-domain-audit-raw.md:841:src/store/layout.py:399:    def load_ui_sets(self) -> UISets:
plans/audits/codex-domain-audit-raw.md:842:src/store/layout.py:406:    def save_ui_sets(self, ui_sets: UISets) -> None:
plans/audits/codex-domain-audit-raw.md:875:     9	- synapse.ui_sets.v1
plans/audits/codex-domain-audit-raw.md:1096:   230	    conflicts_mode: ConflictMode = ConflictMode.LAST_WINS
plans/audits/codex-domain-audit-raw.md:1103:   237	    enabled: bool = False
plans/audits/codex-domain-audit-raw.md:1181:   311	# UI Sets Model (state/ui_sets.json)
plans/audits/codex-domain-audit-raw.md:1185:   315	    """UI sets configuration (state/ui_sets.json)."""
plans/audits/codex-domain-audit-raw.md:1186:   316	    schema_: str = Field(default="synapse.ui_sets.v1", alias="schema")
plans/audits/codex-domain-audit-raw.md:1544:   670	                if lower in ("true", "yes", "1", "enabled", "on", "recommended", "required", "must"):
plans/audits/codex-domain-audit-raw.md:1617:   743	                        if lower in ("true", "yes", "1", "enabled", "on"):
plans/audits/codex-domain-audit-raw.md:1719:   845	    pack_dependencies: List[PackDependencyRef] = Field(default_factory=list)  # Dependencies on other packs
plans/audits/codex-domain-audit-raw.md:1779:   905	        names = [ref.pack_name for ref in self.pack_dependencies]
plans/audits/codex-domain-audit-raw.md:1899:  1021	    conflicts: ConflictConfig = Field(default_factory=ConflictConfig)
plans/audits/codex-domain-audit-raw.md:2005:  1127	    """Report entry for a shadowed file (conflict resolved by last_wins)."""
plans/audits/codex-domain-audit-raw.md:2019:  1141	    shadowed: List[ShadowedEntry] = Field(default_factory=list)
plans/audits/codex-domain-audit-raw.md:2109:  1231	    shadowed: List[ShadowedEntry] = Field(default_factory=list)
plans/audits/codex-domain-audit-raw.md:2138:  1260	    shadowed: List[ShadowedEntry] = Field(default_factory=list)
plans/audits/codex-domain-audit-raw.md:2235:  1353	    active_in_uis: List[str] = Field(default_factory=list)  # UIs currently using this blob
plans/audits/codex-domain-audit-raw.md:2243:  1361	    enabled: bool = False
plans/audits/codex-domain-audit-raw.md:2308:  1426	    active_in_uis: List[str] = Field(default_factory=list)
plans/audits/codex-domain-audit-raw.md:2338:  1456	    enabled: bool
plans/audits/codex-domain-audit-raw.md:2425:  1543	    conflicts: int = 0
plans/audits/codex-domain-audit-raw.md:2506:   111	    def ui_sets_path(self) -> Path:
plans/audits/codex-domain-audit-raw.md:2507:   112	        """Path to ui_sets.json."""
plans/audits/codex-domain-audit-raw.md:2508:   113	        return self.state_path / "ui_sets.json"
plans/audits/codex-domain-audit-raw.md:2684:   302	            self._write_default_ui_sets()
plans/audits/codex-domain-audit-raw.md:2710:   328	    def _write_default_ui_sets(self) -> None:
plans/audits/codex-domain-audit-raw.md:2711:   329	        """Write default ui_sets.json."""
plans/audits/codex-domain-audit-raw.md:2712:   330	        if not self.ui_sets_path.exists():
plans/audits/codex-domain-audit-raw.md:2713:   331	            ui_sets = UISets.create_default()
plans/audits/codex-domain-audit-raw.md:2714:   332	            self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
plans/audits/codex-domain-audit-raw.md:2781:   399	    def load_ui_sets(self) -> UISets:
plans/audits/codex-domain-audit-raw.md:2783:   401	        if not self.ui_sets_path.exists():
plans/audits/codex-domain-audit-raw.md:2785:   403	        data = self.read_json(self.ui_sets_path)
plans/audits/codex-domain-audit-raw.md:2788:   406	    def save_ui_sets(self, ui_sets: UISets) -> None:
plans/audits/codex-domain-audit-raw.md:2790:   408	        self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
plans/audits/CONSOLIDATED-FINDINGS.md:107:  `pack_category`, `source`, `dependencies`, `pack_dependencies`, `parameters`,
plans/audits/CONSOLIDATED-FINDINGS.md:135:- **`pack_dependencies` se NESEMANTICKY rekurzivně neexpanduje do profilu.**
plans/audits/CONSOLIDATED-FINDINGS.md:138:  `pack_dependencies`, použití A NEPŘIDÁ B do view symlinks.
plans/audits/CONSOLIDATED-FINDINGS.md:154:4. **Jsou `pack_dependencies` operační (mění profile/view symlinks), nebo informační?**
plans/audits/CONSOLIDATED-FINDINGS.md:155:5. **Pokud operační — má `use(pack)` rekurzivně zahrnout `pack_dependencies`?**
plans/audits/CONSOLIDATED-FINDINGS.md:156:6. **Mají optional `pack_dependencies` být zahrnuté automaticky, nebo jen warning?**
plans/audits/CONSOLIDATED-FINDINGS.md:179:  vytvoří symlinks. **Neexpanduje `pack_dependencies` rekurzivně** (kritická díra).
plans/audits/CONSOLIDATED-FINDINGS.md:350:- **Settings page má `store_ui_roots`, `store_default_ui_set`, `store_ui_sets`** s
plans/audits/CONSOLIDATED-FINDINGS.md:352:- **`ProfilesPage` zobrazuje:** runtime status, back/reset mutations, shadowed files
plans/audits/CONSOLIDATED-FINDINGS.md:366:- **`StatusReport.shadowed` je VŽDY EMPTY** z `Store.status()` (`src/store/__init__.py:951-960`).
plans/audits/CONSOLIDATED-FINDINGS.md:367:  ProfilesPage shadowed table tedy vždy prázdná.
plans/audits/CONSOLIDATED-FINDINGS.md:371:- **`Profile.conflicts.mode` je modeled, ale `ViewBuilder` ignoruje.** Vždy last-wins.
plans/audits/CONSOLIDATED-FINDINGS.md:373:- **`ProfilePackEntry.enabled` je v CLI viditelné, ale `ViewBuilder.compute_plan` ho
plans/audits/CONSOLIDATED-FINDINGS.md:396:- **Custom pack creation volá `store.layout.pack_path()` (`:3334`)**, ale `StoreLayout`
plans/audits/CONSOLIDATED-FINDINGS.md:410:- **Existing root-level model filename conflicts NEDETEKOVÁNY.**
plans/audits/CONSOLIDATED-FINDINGS.md:418:  ale **store UI targets čte z `state/ui_sets.json`.** Source-of-truth split.
plans/audits/CONSOLIDATED-FINDINGS.md:420:- **Settings UI sets neaktualizují `state/ui_sets.json`.**
plans/audits/CONSOLIDATED-FINDINGS.md:421:- **Store singleton se NERESETUJE když se mění `store_default_ui_set` nebo `store_ui_sets`** —
plans/audits/CONSOLIDATED-FINDINGS.md:431:7. **Mají Settings psát `state/config.json` a `state/ui_sets.json` pro Profile defaults?**
plans/audits/CONSOLIDATED-FINDINGS.md:446:21. **Má `ProfilePackEntry.enabled` ovlivnit view building?**
plans/audits/CONSOLIDATED-FINDINGS.md:457:32. **Má Profile status compute shadowed entries live, cache, nebo persist build reports?**
plans/audits/CONSOLIDATED-FINDINGS.md:490:  - `/api/avatar/config` GET/POST — exposuje a updatuje `enabled`, default provider,
plans/audits/CONSOLIDATED-FINDINGS.md:491:    provider enabled/model.
plans/audits/CONSOLIDATED-FINDINGS.md:493:- **Master AI toggle funguje** v Settings → `enabled=false` → `Layout` schová `AvatarWidget`.
plans/audits/CONSOLIDATED-FINDINGS.md:515:- **`enabled=false` se neenforce-uje na backendu.** UI text říká "all AI features inactive",
plans/audits/CONSOLIDATED-FINDINGS.md:516:  ale `AvatarTaskService` neckontroluje `config.enabled`. Imports + `/api/ai/extract` můžou
plans/audits/CONSOLIDATED-FINDINGS.md:521:- **Pokud `enabled=true` ale engine je unavailable, `Layout` STÁLE rendruje `AvatarWidget`** —
plans/audits/CONSOLIDATED-FINDINGS.md:539:- **`AvatarTaskService` nečte provider `enabled`** — disabled provider může být default.
plans/audits/CONSOLIDATED-FINDINGS.md:540:- **`AvatarConfig.providers` ukládá jen `model` a `enabled`** — žádné priority ani runtime status.
plans/audits/CONSOLIDATED-FINDINGS.md:558:1. **Má `enabled=false` disablovat ALL backend AI service calls, nebo jen user-facing chat?**
plans/audits/CONSOLIDATED-FINDINGS.md:583:  - `enabled=false` → Layout schová widget → BUT backend stále běží AI z `/api/ai/extract`
plans/audits/CONSOLIDATED-FINDINGS.md:610:   pro `pack_dependencies`.
plans/audits/CONSOLIDATED-FINDINGS.md:630:3. **Custom pack create volá `store.layout.pack_path()` který neexistuje** (jen `pack_dir()`).
plans/audits/CONSOLIDATED-FINDINGS.md:633:4. **`StatusReport.shadowed` je vždy empty.** ProfilesPage shadowed table tedy vždy prázdná.
plans/audits/CONSOLIDATED-FINDINGS.md:636:5. **Profile conflict mode + ProfilePackEntry.enabled jsou modeled ale ignored.** Buď
plans/audits/CONSOLIDATED-FINDINGS.md:639:6. **`enabled=false` AI toggle se neenforce-uje na backendu.** Audit už označil jako bug.
plans/audits/codex-audit-3-install-pack.md:303:- A1111/Forge/SD.Next health probe: API ping if enabled, fallback port check.
plans/audits/codex-audit-4-workflow-wizard.md:255:- No flow adds imported workflow dependencies as `pack_dependencies`.
apps/web/src/lib/avatar/api.ts:22:  enabled: boolean
apps/web/src/lib/avatar/api.ts:31:  enabled: boolean
apps/web/src/lib/avatar/api.ts:39:  provider_configs: Record<string, { model: string; enabled: boolean }>
apps/web/src/lib/avatar/api.ts:109:  enabled: boolean
apps/web/src/lib/avatar/api.ts:111:  providers: Record<string, { enabled?: boolean; model?: string }>
apps/web/src/lib/avatar/suggestions.ts:32:    'avatar.suggestions.profilesPage.conflicts',
apps/web/src/components/modules/PackDetailPage.tsx:177:    enabled: modals.baseModelResolver,
apps/web/src/components/modules/PackDetailPage.tsx:201:    enabled:
apps/web/src/components/modules/SettingsPage.tsx:19:  nsfw_blur_enabled: boolean
apps/web/src/components/modules/SettingsPage.tsx:25:  store_default_ui_set: string
apps/web/src/components/modules/SettingsPage.tsx:26:  store_ui_sets: Record<string, string[]>
apps/web/src/components/modules/SettingsPage.tsx:86:      if (settings.store_default_ui_set) setStoreDefaultUiSet(settings.store_default_ui_set)
apps/web/src/components/modules/SettingsPage.tsx:122:      setBackupEnabled(backupStatus.enabled)
apps/web/src/components/modules/SettingsPage.tsx:173:        nsfw_blur_enabled: nsfwBlurEnabled,
apps/web/src/components/modules/SettingsPage.tsx:176:        store_default_ui_set: storeDefaultUiSet,
apps/web/src/components/modules/SettingsPage.tsx:183:        enabled: backupEnabled,
apps/web/src/components/modules/SettingsPage.tsx:384:                options={(settings?.store_ui_sets ? Object.keys(settings.store_ui_sets) : [storeDefaultUiSet]).map((setName) => ({
apps/web/src/components/modules/SettingsPage.tsx:386:                  label: settings?.store_ui_sets
apps/web/src/components/modules/SettingsPage.tsx:387:                    ? `${setName} (${settings.store_ui_sets[setName].join(', ')})`
apps/web/src/components/layout/Layout.tsx:52:  // Check if AI is enabled (master toggle)
apps/web/src/components/layout/Layout.tsx:59:  const aiEnabled = avatarStatus?.enabled !== false
apps/web/src/components/modules/BrowsePage.tsx:249:    enabled: true,
apps/web/src/components/modules/BrowsePage.tsx:292:    enabled: !!selectedModel,
apps/web/src/components/modules/BrowsePage.tsx:319:    enabled: !!selectedModel && !!modelInfo && !modelHasImages,
apps/web/src/components/layout/Sidebar.tsx:109:    // Request notification permission when auto-check is enabled
apps/web/src/components/modules/PacksPage.tsx:136:    // Hide nsfw-pack-hide packs when blur is enabled
apps/web/src/lib/parameters/normalizer.ts:178:    return ['true', 'yes', 'enabled', 'enable', '1', 'on'].includes(strValue)
apps/web/src/components/layout/ProfileDropdown.tsx:23:  shadowed_count: number
apps/web/src/components/layout/ProfileDropdown.tsx:130:        {status?.shadowed_count ? (
apps/web/src/components/layout/ProfileDropdown.tsx:174:          {status?.shadowed_count ? (
apps/web/src/components/layout/ProfileDropdown.tsx:178:                <span>{status.shadowed_count} shadowed file(s)</span>
apps/web/src/__tests__/nsfw-settings-ui.test.ts:155:    it('blur mode → nsfw_blur_enabled: true for API', () => {
apps/web/src/__tests__/nsfw-settings-ui.test.ts:159:    it('hide mode → nsfw_blur_enabled: true for API (both map to true)', () => {
apps/web/src/__tests__/nsfw-settings-ui.test.ts:164:    it('show mode → nsfw_blur_enabled: false for API', () => {
apps/web/src/__tests__/AvatarSettings.test.ts:13:  enabled: boolean
apps/web/src/__tests__/AvatarSettings.test.ts:21:  provider_configs: Record<string, { model: string; enabled: boolean }>
apps/web/src/__tests__/AvatarSettings.test.ts:41:  enabled: boolean
apps/web/src/__tests__/AvatarSettings.test.ts:58:  enabled: true,
apps/web/src/__tests__/AvatarSettings.test.ts:76:    gemini: { model: 'gemini-2.5-pro', enabled: true },
apps/web/src/__tests__/AvatarSettings.test.ts:77:    claude: { model: '', enabled: true },
apps/web/src/__tests__/AvatarSettings.test.ts:84:  enabled: true,
plans/audits/codex-audit-1-resolve-model.md:770:   331	| AI gate `enabled` misto `available` | MED | Layout.tsx:52 | |
plans/audits/codex-audit-1-resolve-model.md:993:   554	### BUG 6: AI gate enabled misto available
plans/audits/codex-audit-1-resolve-model.md:1532:   661	16. ✅ Fix BUG 6: AI gate available — Layout.tsx gates on `available === true` instead of `enabled !== false`
plans/audits/codex-audit-1-resolve-model.md:1606:   735	**Cil:** MCP-enabled AI dependency resolution. DependencyResolverModal s Preview Analysis tabem.
plans/audits/codex-audit-1-resolve-model.md:1741:   870	| D2 | `can_use_ai()` gate funkce | ✅ Phase 6 | `AIEvidenceProvider.supports()` kontroluje `is_ai_enabled(config)` + avatar dostupnost. Config: `resolve.enable_ai: bool`. |
plans/audits/codex-audit-1-resolve-model.md:1772:   901	| F8 | BUG 6: AI gate v UI | ✅ OPRAVENO | Layout.tsx: zmeneno z `enabled !== false` na `available === true`. Koment upraven. |
plans/audits/codex-audit-1-resolve-model.md:1842:   971	- ✅ BUG 5 (TS union + incompatible), BUG 6 (AI gate available vs enabled)
plans/audits/codex-audit-1-resolve-model.md:2108:   153	def is_ai_enabled(config: Any = None) -> bool:
plans/audits/codex-audit-1-resolve-model.md:2109:   154	    """Check if AI-assisted resolution is enabled in config."""
plans/audits/codex-audit-1-resolve-model.md:2193:    21	from .resolve_config import AI_CONFIDENCE_CEILING, get_kind_config, is_ai_enabled
plans/audits/codex-audit-1-resolve-model.md:2691:   514	            if not is_ai_enabled(config):
plans/audits/codex-audit-1-resolve-model.md:4609:   336	        # MCP-enabled tasks get access to MCP servers (e.g., search tools)
plans/audits/codex-audit-1-resolve-model.md:8521:   162	    enabled: !!packName,
plans/audits/codex-audit-1-resolve-model.md:8539:   180	          backup_enabled: false,
plans/audits/codex-audit-1-resolve-model.md:8547:   188	    enabled: !!packName,
plans/audits/codex-audit-1-resolve-model.md:9434:    10	export function usePreviewAnalysis(packName: string, enabled: boolean) {
plans/audits/codex-audit-1-resolve-model.md:9447:    23	    enabled,
plans/audits/codex-audit-1-resolve-model.md:9675:    76	    // Apply button should be enabled
plans/audits/codex-audit-1-resolve-model.md:9833:   234	        body: JSON.stringify({ state: 'ready', available: true, enabled: true }),
plans/audits/codex-audit-1-resolve-model.md:10122:   259	    config.extraction.cache_enabled = False
plans/audits/codex-audit-1-resolve-model.md:10311:    22	from src.store.resolve_config import get_auto_apply_margin, is_ai_enabled
plans/audits/codex-audit-1-resolve-model.md:10484:   195	    def test_is_ai_enabled_from_config(self):
plans/audits/codex-audit-1-resolve-model.md:10487:   198	        assert is_ai_enabled(config) is False
plans/audits/codex-audit-1-resolve-model.md:10489:   200	    def test_is_ai_enabled_default_true(self):
plans/audits/codex-audit-1-resolve-model.md:10490:   201	        assert is_ai_enabled(None) is True
plans/audits/codex-audit-1-resolve-model.md:10506:   217	    def test_ai_provider_enabled_by_default(self):
plans/audits/codex-audit-1-resolve-model.md:11379:  1770	    needs_mcp: bool = False     # NOVY: flag pro MCP-enabled execution
plans/audits/codex-audit-1-resolve-model.md:11941:   237	    enabled: bool = False
plans/audits/codex-audit-1-resolve-model.md:12022:   318	# UI Sets Model (state/ui_sets.json)
plans/audits/codex-audit-1-resolve-model.md:12026:   322	    """UI sets configuration (state/ui_sets.json)."""
plans/audits/codex-audit-1-resolve-model.md:12027:   323	    schema_: str = Field(default="synapse.ui_sets.v1", alias="schema")
plans/audits/codex-audit-1-resolve-model.md:12994:   536	    Only extracts LoRAs that are enabled (on=true).
plans/audits/codex-audit-1-resolve-model.md:13153:   316	      body: JSON.stringify({ state: 'stopped', available: false, enabled: false }),
plans/audits/codex-audit-1-resolve-model.md:13169:   332	    backup_enabled: false,
plans/audits/codex-audit-1-resolve-model.md:13292:+2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
plans/audits/codex-audit-1-resolve-model.md:13363:+2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
plans/audits/codex-audit-1-resolve-model.md:13658:+2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
plans/audits/codex-audit-1-resolve-model.md:13729:+2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
plans/audits/codex-audit-1-resolve-model.md:14036:+2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
plans/audits/codex-audit-1-resolve-model.md:14107:+2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
plans/audits/codex-audit-1-resolve-model.md:14418:+2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
plans/audits/codex-audit-1-resolve-model.md:14489:+2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
apps/web/src/__tests__/browse-filter-smoke.test.ts:35:          enabled: true,
apps/web/src/__tests__/browse-filter-smoke.test.ts:208:          enabled: true,
apps/web/src/components/modules/settings/AvatarSettings.tsx:378:  const aiEnabled = config?.enabled !== false
apps/web/src/components/modules/settings/AvatarSettings.tsx:395:    patchConfigMutation.mutate({ enabled: !aiEnabled })
apps/web/src/components/modules/settings/AvatarSettings.tsx:404:      providers: { [provName]: { enabled: !currentEnabled } },
apps/web/src/components/modules/settings/AvatarSettings.tsx:538:                const isEnabled = provConfig?.enabled !== false
apps/web/src/components/ui/MediaPreview.tsx:156:  /** NSFW blur enabled setting (passed from parent for performance) */
apps/web/src/components/ui/MediaPreview.tsx:244:  // Reset revealed state when NSFW blur is re-enabled
apps/web/src/components/ui/MediaPreview.tsx:339:    // 2. Either: image is loaded, or we're in fallback mode, or autoPlay is enabled
apps/web/src/lib/api/adapters/trpcBridgeAdapter.ts:54:    enabled: boolean
apps/web/src/lib/api/adapters/trpcBridgeAdapter.ts:60:  configure?(updates: { enabled?: boolean; nsfw?: boolean }): void
apps/web/src/__tests__/search-adapters.test.ts:264:  it('should be available when bridge exists and is enabled', async () => {
apps/web/src/__tests__/browse-filter-propagation.test.ts:29:        getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0, features: ['meilisearch', 'trpc'] }),
apps/web/src/__tests__/media-preview-nsfw.test.ts:67:     * - Blur is enabled globally
apps/web/src/__tests__/media-preview-nsfw.test.ts:70:    it('should show eye icon only when nsfw AND blur enabled AND revealed', () => {
apps/web/src/__tests__/media-preview-nsfw.test.ts:112:     * - Blur is enabled
apps/web/src/__tests__/media-preview-nsfw.test.ts:115:    it('should show clickable area when nsfw AND blur enabled AND NOT revealed', () => {
apps/web/src/__tests__/media-preview-nsfw.test.ts:206:  describe('Scenario: User browses NSFW content with blur enabled', () => {
apps/web/src/__tests__/import-wizard.test.ts:645:      // With NSFW enabled
apps/web/src/__tests__/inventory-utils.test.ts:33:  active_in_uis: string[]
apps/web/src/__tests__/inventory-utils.test.ts:49:  active_in_uis: string[]
apps/web/src/__tests__/inventory-utils.test.ts:246:      active_in_uis: ['comfyui'],
apps/web/src/__tests__/inventory-utils.test.ts:259:      active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:272:      active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:285:      active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:432:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:449:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:466:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:485:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:502:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:519:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:538:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:557:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:576:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:595:        active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:635:    active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:644:      active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:649:    expect(analysis.active_in_uis.length).toBe(0)
apps/web/src/__tests__/inventory-utils.test.ts:667:      active_in_uis: ['comfyui', 'webui'],
apps/web/src/__tests__/inventory-utils.test.ts:671:    expect(analysis.active_in_uis.length).toBe(2)
apps/web/src/__tests__/inventory-utils.test.ts:694:      active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:707:      active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:799:    active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:872:  // Backup/Restore — need backup enabled and connected
apps/web/src/__tests__/inventory-utils.test.ts:943:    active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:1009:  it('should show Backup only when backup enabled and connected', () => {
apps/web/src/__tests__/inventory-utils.test.ts:1057:    active_in_uis: [],
apps/web/src/__tests__/inventory-utils.test.ts:1127:    active_in_uis: [],
apps/web/src/components/modules/pack-detail/types.ts:248:    pack_dependencies?: PackDependencyRef[]  // Dependencies on other packs
apps/web/src/__tests__/trpc-bridge-wiring.test.ts:19:    getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0 }),
apps/web/src/__tests__/pack-plugins.test.ts:62:    pack_dependencies?: PackDependencyRef[]
apps/web/src/__tests__/pack-plugins.test.ts:697:    it('should parse pack_dependencies array', () => {
apps/web/src/__tests__/pack-plugins.test.ts:704:          pack_dependencies: [
apps/web/src/__tests__/pack-plugins.test.ts:711:      expect(pack.pack?.pack_dependencies).toHaveLength(2)
apps/web/src/__tests__/pack-plugins.test.ts:712:      expect(pack.pack?.pack_dependencies?.[0].pack_name).toBe('base-checkpoint')
apps/web/src/__tests__/pack-plugins.test.ts:713:      expect(pack.pack?.pack_dependencies?.[0].required).toBe(true)
apps/web/src/__tests__/pack-plugins.test.ts:718:      expect(pack.pack?.pack_dependencies).toBeUndefined()
apps/web/src/__tests__/pack-plugins.test.ts:728:          pack_dependencies: [
apps/web/src/__tests__/pack-plugins.test.ts:734:      expect(pack.pack?.pack_dependencies?.[0].version_constraint).toBe('>=1.0.0')
apps/web/src/__tests__/pack-plugins.test.ts:751:          pack_dependencies: dependencies,
apps/web/src/__tests__/pack-plugins.test.ts:755:      expect(pack.pack?.pack_dependencies).toHaveLength(10)
apps/web/src/__tests__/pack-plugins.test.ts:757:      const required = pack.pack?.pack_dependencies?.filter(d => d.required) || []
apps/web/src/__tests__/pack-plugins.test.ts:758:      const optional = pack.pack?.pack_dependencies?.filter(d => !d.required) || []
apps/web/src/__tests__/pack-plugins.test.ts:771:          pack_dependencies: [
apps/web/src/__tests__/pack-plugins.test.ts:780:      const deps = pack.pack?.pack_dependencies || []
apps/web/src/__tests__/pack-plugins.test.ts:1101:          pack_dependencies: [
apps/web/src/__tests__/pack-plugins.test.ts:1112:      expect(context.pack.pack?.pack_dependencies).toHaveLength(2)
apps/web/src/components/modules/inventory/InventoryPage.tsx:521:            backupEnabled={backupStatus?.enabled || false}
apps/web/src/components/modules/inventory/InventoryStats.tsx:98:    enabled: backupStatus?.enabled && backupStatus?.connected,
apps/web/src/components/modules/inventory/InventoryStats.tsx:287:            !backupStatus?.connected && backupStatus?.enabled
apps/web/src/components/modules/inventory/InventoryStats.tsx:299:                  : backupStatus?.enabled
apps/web/src/components/modules/inventory/InventoryStats.tsx:309:            {backupStatus?.enabled && (
apps/web/src/components/modules/inventory/InventoryStats.tsx:325:          {!backupStatus?.enabled ? (
apps/web/src/components/modules/packs/PushConfirmDialog.tsx:92:      // If cleanup is enabled and we just finished backup phase, start cleanup phase
apps/web/src/components/modules/packs/PushConfirmDialog.tsx:141:  // P2: Can confirm if there's something to backup OR cleanup is enabled and there are local blobs
apps/web/src/stores/settingsStore.ts:12:  setNsfwBlur: (enabled: boolean) => void
apps/web/src/stores/settingsStore.ts:30:      setNsfwBlur: (enabled) => {
apps/web/src/stores/settingsStore.ts:31:        useNsfwStore.getState().setFilterMode(enabled ? 'blur' : 'show')
apps/web/src/stores/settingsStore.ts:32:        set({ nsfwBlurEnabled: enabled })
apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx:80:    enabled: false, // Manual trigger only
apps/web/src/components/modules/inventory/DeleteConfirmationDialog.tsx:203:                {item.active_in_uis.length > 0 && (
apps/web/src/components/modules/inventory/DeleteConfirmationDialog.tsx:205:                    {t('inventory.delete.activeIn')} {item.active_in_uis.join(', ')}
apps/web/src/components/modules/inventory/ImpactsDialog.tsx:200:              {analysis.active_in_uis.length > 0 && (
apps/web/src/components/modules/inventory/ImpactsDialog.tsx:204:                    {t('inventory.impacts.activeInUis', { count: analysis.active_in_uis.length })}
apps/web/src/components/modules/inventory/ImpactsDialog.tsx:207:                    {analysis.active_in_uis.map((ui) => (
apps/web/src/components/modules/inventory/ImpactsDialog.tsx:221:              {analysis.used_by_packs.length === 0 && analysis.active_in_uis.length === 0 && (
plans/audits/codex-audit-6-ai-integration.md:657:- Sdílený `AICache`, TTL a `cache_enabled` z `config.extraction`
plans/audits/codex-audit-6-ai-integration.md:1175:    enabled: bool = False
plans/audits/codex-audit-6-ai-integration.md:1198:    enabled: bool = True
plans/audits/codex-audit-6-ai-integration.md:1212:    cache_enabled: bool = True
plans/audits/codex-audit-6-ai-integration.md:1763:- Test coverage pro MCP-enabled tasky (mock MCP server)
plans/audits/codex-audit-6-ai-integration.md:1786:Všechny tasky sdílejí `config.extraction.cache_enabled` a `cache_ttl_days`. Pro různé tasky může dávat smysl jiný TTL:
plans/audits/codex-audit-6-ai-integration.md:2065:    28	    cache_enabled: bool = True
plans/audits/codex-audit-6-ai-integration.md:2075:    38	    enabled: bool = True
plans/audits/codex-audit-6-ai-integration.md:2083:    46	    enabled: bool = True
plans/audits/codex-audit-6-ai-integration.md:2196:   159	        cache_enabled=extraction_raw.get("cache_enabled", True),
plans/audits/codex-audit-6-ai-integration.md:2208:   171	        enabled=raw_config.get("enabled", True),
plans/audits/codex-audit-6-ai-integration.md:2262:   225	                enabled=prov_data.get("enabled", True),
plans/audits/codex-audit-6-ai-integration.md:2400:    84	    if not config.enabled:
plans/audits/codex-audit-6-ai-integration.md:2416:   100	        "enabled": config.enabled,
plans/audits/codex-audit-6-ai-integration.md:2443:   127	        "enabled": config.enabled,
plans/audits/codex-audit-6-ai-integration.md:2455:   139	            name: {"model": prov.model, "enabled": prov.enabled}
plans/audits/codex-audit-6-ai-integration.md:2463:   147	    """Update avatar configuration (enabled, default provider, provider settings).
plans/audits/codex-audit-6-ai-integration.md:2466:   150	      - enabled (bool): master AI toggle
plans/audits/codex-audit-6-ai-integration.md:2469:   153	            {"gemini": {"enabled": true, "model": "gemini-3-pro-preview"}}
plans/audits/codex-audit-6-ai-integration.md:2494:   178	    if "enabled" in updates:
plans/audits/codex-audit-6-ai-integration.md:2495:   179	        raw["enabled"] = bool(updates["enabled"])
plans/audits/codex-audit-6-ai-integration.md:2509:   193	            if "enabled" in prov_updates:
plans/audits/codex-audit-6-ai-integration.md:2510:   194	                raw[prov_name]["enabled"] = bool(prov_updates["enabled"])
plans/audits/codex-audit-6-ai-integration.md:2618:   302	        if not config.enabled:
plans/audits/codex-audit-6-ai-integration.md:2807:   167	        if use_cache and ext.cache_enabled:
plans/audits/codex-audit-6-ai-integration.md:2831:   191	            if use_cache and ext.cache_enabled:
plans/audits/codex-audit-6-ai-integration.md:2866:   226	                if use_cache and ext.cache_enabled:
plans/audits/codex-audit-6-ai-integration.md:3024:   302	        if not config.enabled:
plans/audits/codex-audit-6-ai-integration.md:3961:src/avatar/routes.py:147:    """Update avatar configuration (enabled, default provider, provider settings).
plans/audits/codex-audit-6-ai-integration.md:4867:apps/web/src/components/layout/Layout.tsx:59:  const aiEnabled = avatarStatus?.enabled !== false
plans/audits/codex-audit-6-ai-integration.md:5161:apps/web/src/lib/avatar/suggestions.ts:32:    'avatar.suggestions.profilesPage.conflicts',
plans/audits/codex-audit-6-ai-integration.md:5486:tests/unit/avatar/test_routes.py:319:            update_avatar_config({"enabled": False})
plans/audits/codex-audit-6-ai-integration.md:5618:plans/audits/codex-audit-1-resolve-model.md:1606:   735	**Cil:** MCP-enabled AI dependency resolution. DependencyResolverModal s Preview Analysis tabem.
plans/audits/codex-audit-6-ai-integration.md:6631:apps/web/src/components/ui/MediaPreview.tsx:339:    // 2. Either: image is loaded, or we're in fallback mode, or autoPlay is enabled
plans/audits/codex-audit-6-ai-integration.md:7025:   378	  const aiEnabled = config?.enabled !== false
plans/audits/codex-audit-6-ai-integration.md:7042:   395	    patchConfigMutation.mutate({ enabled: !aiEnabled })
plans/audits/codex-audit-6-ai-integration.md:7051:   404	      providers: { [provName]: { enabled: !currentEnabled } },
plans/audits/codex-audit-6-ai-integration.md:7185:   538	                const isEnabled = provConfig?.enabled !== false
plans/audits/codex-audit-6-ai-integration.md:7676:    52	  // Check if AI is enabled (master toggle)
plans/audits/codex-audit-6-ai-integration.md:7683:    59	  const aiEnabled = avatarStatus?.enabled !== false
plans/audits/codex-audit-6-ai-integration.md:8412:   521	            pack_dependencies=[],  # No pack dependencies by default
plans/audits/codex-audit-6-ai-integration.md:8892:    22	  enabled: boolean
plans/audits/codex-audit-6-ai-integration.md:8901:    31	  enabled: boolean
plans/audits/codex-audit-6-ai-integration.md:8909:    39	  provider_configs: Record<string, { model: string; enabled: boolean }>
plans/audits/codex-audit-6-ai-integration.md:8979:   109	  enabled: boolean
plans/audits/codex-audit-6-ai-integration.md:8981:   111	  providers: Record<string, { enabled?: boolean; model?: string }>
plans/audits/codex-audit-6-ai-integration.md:9427:apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:179:  if (typeof value === 'boolean') return value ? (translate?.('pack.parameters.enabled') ?? 'Enabled') : (translate?.('pack.parameters.disabled') ?? 'Disabled')
plans/audits/codex-audit-6-ai-integration.md:9454:apps/web/src/components/modules/pack-detail/modals/EditParametersModal.tsx:441:              {value === 'true' ? t('pack.modals.parameters.enabled') : t('pack.modals.parameters.disabled')}
plans/audits/codex-audit-6-ai-integration.md:9490:  1574	    "enabledDesc": "AI providers are active and will be used for supported tasks",
plans/audits/codex-audit-6-ai-integration.md:9508:  1592	    "enabled": "Enabled",
plans/audits/codex-audit-6-ai-integration.md:9691:  1775	    "providerDefaultHint": "Backend services (MCP tools, AI extraction) use the default provider and model. Chat window can switch freely between all enabled providers.",
plans/audits/codex-audit-6-ai-integration.md:9777:  1856	        "conflicts": "Are there any file conflicts between profiles?"
plans/audits/codex-audit-6-ai-integration.md:10439:src/store/api.py:4602:            # Create symlink with pack prefix to avoid conflicts
plans/audits/codex-audit-6-ai-integration.md:10824:apps/web/src/components/modules/ProfilesPage.tsx:231:            {t('profiles.shadowedCount', { count: status.shadowed_count })}
plans/audits/codex-audit-6-ai-integration.md:10828:apps/web/src/components/modules/ProfilesPage.tsx:241:                  <th className="text-left px-4 py-3 text-sm font-medium text-amber-400">{t('profiles.table.shadowed')}</th>
plans/audits/codex-audit-6-ai-integration.md:10829:apps/web/src/components/modules/ProfilesPage.tsx:258:            {t('profiles.shadowedExplanation')}
plans/audits/codex-audit-6-ai-integration.md:11463:apps/web/src/components/modules/pack-detail/types.ts:248:    pack_dependencies?: PackDependencyRef[]  // Dependencies on other packs
plans/audits/codex-audit-6-ai-integration.md:11496:src/store/pack_service.py:521:            pack_dependencies=[],  # No pack dependencies by default
plans/audits/codex-audit-6-ai-integration.md:11541:src/store/models.py:845:    pack_dependencies: List[PackDependencyRef] = Field(default_factory=list)  # Dependencies on other packs
plans/audits/codex-audit-6-ai-integration.md:11544:src/store/models.py:905:        names = [ref.pack_name for ref in self.pack_dependencies]
plans/audits/codex-audit-6-ai-integration.md:11586:apps/web/src/components/modules/pack-detail/types.ts:248:    pack_dependencies?: PackDependencyRef[]  // Dependencies on other packs
plans/audits/codex-audit-6-ai-integration.md:11681:src/store/api.py:2964:def get_pack_dependencies_status(
plans/audits/codex-audit-6-ai-integration.md:11683:src/store/api.py:2976:        for ref in pack.pack_dependencies:
plans/audits/codex-audit-6-ai-integration.md:11687:src/store/api.py:3051:        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
plans/audits/codex-audit-6-ai-integration.md:11688:src/store/api.py:3063:        pack.pack_dependencies.append(new_ref)
plans/audits/codex-audit-6-ai-integration.md:11690:src/store/api.py:3091:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-6-ai-integration.md:11691:src/store/api.py:3092:        pack.pack_dependencies = [
plans/audits/codex-audit-6-ai-integration.md:11692:src/store/api.py:3093:            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
plans/audits/codex-audit-6-ai-integration.md:11693:src/store/api.py:3096:        if len(pack.pack_dependencies) == original_count:
plans/audits/codex-audit-6-ai-integration.md:11696:src/store/api.py:3172:            if depth < max_depth and p.pack_dependencies:
plans/audits/codex-audit-6-ai-integration.md:11697:src/store/api.py:3173:                for ref in p.pack_dependencies:
plans/audits/codex-audit-6-ai-integration.md:11753:apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx:423:  const packDependencies: PackDependencyRef[] = pack.pack?.pack_dependencies ?? []
plans/audits/codex-audit-6-ai-integration.md:11816:src/store/update_service.py:258:        Find all packs that depend on the given pack via pack_dependencies.
plans/audits/codex-audit-6-ai-integration.md:11817:src/store/update_service.py:261:            List of pack names that have pack_name in their pack_dependencies.
plans/audits/codex-audit-6-ai-integration.md:11818:src/store/update_service.py:269:                dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
plans/audits/codex-audit-6-ai-integration.md:11894:apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx:423:  const packDependencies: PackDependencyRef[] = pack.pack?.pack_dependencies ?? []
plans/audits/codex-audit-6-ai-integration.md:12112:  4078	        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-6-ai-integration.md:13034:   203	        service = _make_service(tmp_path, registry=reg, cache_enabled=False)
plans/audits/codex-audit-6-ai-integration.md:13056:   225	        service = _make_service(tmp_path, registry=reg, cache_enabled=True)
plans/audits/codex-audit-6-ai-integration.md:13102:   271	        service = _make_service(tmp_path, registry=reg, cache_enabled=False)
plans/audits/codex-audit-6-ai-integration.md:13145:   559	                                cache_enabled=False)
plans/audits/codex-audit-6-ai-integration.md:13161:   575	        service = _make_service(tmp_path, registry=reg, cache_enabled=False)
plans/audits/codex-audit-6-ai-integration.md:13239:    48	    // Each provider config has model and enabled fields
plans/audits/codex-audit-6-ai-integration.md:13244:    53	      expect(config).toHaveProperty('enabled')
plans/audits/codex-audit-6-ai-integration.md:13245:    54	      expect(typeof config.enabled).toBe('boolean')
plans/audits/codex-audit-6-ai-integration.md:13862:    32	    expect(typeof data.enabled).toBe('boolean')
plans/audits/codex-audit-6-ai-integration.md:13867:    37	    expect(typeof data.enabled).toBe('boolean')
plans/audits/codex-audit-6-ai-integration.md:13938:   108	    expect(typeof data.enabled).toBe('boolean')
plans/audits/codex-audit-6-ai-integration.md:13941:   111	    expect(typeof data.cache_enabled).toBe('boolean')
plans/audits/codex-audit-6-ai-integration.md:14196:   514	            if not is_ai_enabled(config):
plans/audits/codex-audit-6-ai-integration.md:14253:   191	            if use_cache and ext.cache_enabled:
plans/audits/codex-audit-6-ai-integration.md:14288:   226	                if use_cache and ext.cache_enabled:
plans/audits/codex-audit-6-ai-integration.md:14398:   336	        # MCP-enabled tasks get access to MCP servers (e.g., search tools)
plans/audits/codex-audit-6-ai-integration.md:14535:    39	  # acp_enabled: true
plans/audits/codex-audit-6-ai-integration.md:14563:    67	    cache_enabled: true
plans/audits/codex-audit-6-ai-integration.md:15124:    32	    'avatar.suggestions.profilesPage.conflicts',
plans/audits/codex-audit-6-ai-integration.md:15480:   311	# UI Sets Model (state/ui_sets.json)
plans/audits/codex-audit-6-ai-integration.md:15484:   315	    """UI sets configuration (state/ui_sets.json)."""
plans/audits/codex-audit-6-ai-integration.md:15640:| Avatar config API | [src/avatar/routes.py](/home/box/git/github/synapse/src/avatar/routes.py:117) | Exposes enabled/provider/safety/skills/provider configs. | Safe defaults through `_get_cached_config()`. | Settings page. |
plans/audits/codex-audit-6-ai-integration.md:15641:| Avatar config mutation | [src/avatar/routes.py](/home/box/git/github/synapse/src/avatar/routes.py:145) | Updates `enabled`, default provider, provider enabled/model in YAML. | Invalid providers ignored. | Settings UI immediate mutation. |
plans/audits/codex-audit-6-ai-integration.md:15642:| Avatar Engine mount | [src/avatar/routes.py](/home/box/git/github/synapse/src/avatar/routes.py:283) | Mounts real avatar-engine app at `/api/avatar`. | Returns false if unavailable/incompatible/disabled/mount error. | One-shot toast; widget may still render when enabled but not ready. NEEDS VERIFICATION for library rendering. |
plans/audits/codex-audit-6-ai-integration.md:15646:| Avatar widget in app shell | [apps/web/src/components/layout/Layout.tsx](/home/box/git/github/synapse/apps/web/src/components/layout/Layout.tsx:52) | If `enabled=false`, hides widget; otherwise renders `AvatarWidget`, permission dialog, status bar, chat panel. | Disabled state renders normal app without AI. | No widget when disabled. |
plans/audits/codex-audit-6-ai-integration.md:15651:| Master AI toggle | [apps/web/src/components/modules/settings/AvatarSettings.tsx](/home/box/git/github/synapse/apps/web/src/components/modules/settings/AvatarSettings.tsx:394) | Patches `enabled`. | None. | Text says all AI features inactive, but backend task service does not enforce this. |
plans/audits/codex-audit-6-ai-integration.md:15687:- If config `enabled=false`, layout hides AvatarWidget entirely: [apps/web/src/components/layout/Layout.tsx](/home/box/git/github/synapse/apps/web/src/components/layout/Layout.tsx:61).
plans/audits/codex-audit-6-ai-integration.md:15695:- If `enabled=true` but engine is unavailable, `Layout` still renders `AvatarWidget`; the WebSocket behavior is delegated to avatar-engine React. NEEDS VERIFICATION.
plans/audits/codex-audit-6-ai-integration.md:15696:- `settingsAvatar.masterToggleDesc` says all AI features are inactive when disabled: [apps/web/src/i18n/locales/en.json](/home/box/git/github/synapse/apps/web/src/i18n/locales/en.json:1769). Backend `AvatarTaskService` does not check `config.enabled`, so imports and `/api/ai/extract` may still run AI/fallback.
plans/audits/codex-audit-6-ai-integration.md:15746:- Provider enabled checkbox: [apps/web/src/components/modules/settings/AvatarSettings.tsx](/home/box/git/github/synapse/apps/web/src/components/modules/settings/AvatarSettings.tsx:561).
plans/audits/codex-audit-6-ai-integration.md:15753:- `enabled`, `provider`, `safety`, `providers`, `extraction`, `mcp_servers`: [src/avatar/config.py](/home/box/git/github/synapse/src/avatar/config.py:42).
plans/audits/codex-audit-6-ai-integration.md:15801:- AI optionality is not consistently enforced. `enabled=false` hides chat UI, but backend AI extraction path does not check it.
plans/audits/codex-audit-6-ai-integration.md:15824:- `AvatarTaskService` does not read provider `enabled`; disabled provider can still be default if YAML says so.
plans/audits/codex-audit-6-ai-integration.md:15825:- `AvatarConfig.providers` only stores `model` and `enabled`; no provider priority or runtime status models.
plans/audits/codex-audit-6-ai-integration.md:15850:- No clear test that `enabled=false` prevents backend `/api/ai/extract` or import AI use.
plans/audits/codex-audit-6-ai-integration.md:15870:- Should `enabled=false` disable all backend AI service calls, or only user-facing chat?
plans/audits/codex-audit-6-ai-integration.md:15925:| Avatar config API | [src/avatar/routes.py](/home/box/git/github/synapse/src/avatar/routes.py:117) | Exposes enabled/provider/safety/skills/provider configs. | Safe defaults through `_get_cached_config()`. | Settings page. |
plans/audits/codex-audit-6-ai-integration.md:15926:| Avatar config mutation | [src/avatar/routes.py](/home/box/git/github/synapse/src/avatar/routes.py:145) | Updates `enabled`, default provider, provider enabled/model in YAML. | Invalid providers ignored. | Settings UI immediate mutation. |
plans/audits/codex-audit-6-ai-integration.md:15927:| Avatar Engine mount | [src/avatar/routes.py](/home/box/git/github/synapse/src/avatar/routes.py:283) | Mounts real avatar-engine app at `/api/avatar`. | Returns false if unavailable/incompatible/disabled/mount error. | One-shot toast; widget may still render when enabled but not ready. NEEDS VERIFICATION for library rendering. |
plans/audits/codex-audit-6-ai-integration.md:15931:| Avatar widget in app shell | [apps/web/src/components/layout/Layout.tsx](/home/box/git/github/synapse/apps/web/src/components/layout/Layout.tsx:52) | If `enabled=false`, hides widget; otherwise renders `AvatarWidget`, permission dialog, status bar, chat panel. | Disabled state renders normal app without AI. | No widget when disabled. |
plans/audits/codex-audit-6-ai-integration.md:15936:| Master AI toggle | [apps/web/src/components/modules/settings/AvatarSettings.tsx](/home/box/git/github/synapse/apps/web/src/components/modules/settings/AvatarSettings.tsx:394) | Patches `enabled`. | None. | Text says all AI features inactive, but backend task service does not enforce this. |
plans/audits/codex-audit-6-ai-integration.md:15972:- If config `enabled=false`, layout hides AvatarWidget entirely: [apps/web/src/components/layout/Layout.tsx](/home/box/git/github/synapse/apps/web/src/components/layout/Layout.tsx:61).
plans/audits/codex-audit-6-ai-integration.md:15980:- If `enabled=true` but engine is unavailable, `Layout` still renders `AvatarWidget`; the WebSocket behavior is delegated to avatar-engine React. NEEDS VERIFICATION.
plans/audits/codex-audit-6-ai-integration.md:15981:- `settingsAvatar.masterToggleDesc` says all AI features are inactive when disabled: [apps/web/src/i18n/locales/en.json](/home/box/git/github/synapse/apps/web/src/i18n/locales/en.json:1769). Backend `AvatarTaskService` does not check `config.enabled`, so imports and `/api/ai/extract` may still run AI/fallback.
plans/audits/codex-audit-6-ai-integration.md:16031:- Provider enabled checkbox: [apps/web/src/components/modules/settings/AvatarSettings.tsx](/home/box/git/github/synapse/apps/web/src/components/modules/settings/AvatarSettings.tsx:561).
plans/audits/codex-audit-6-ai-integration.md:16038:- `enabled`, `provider`, `safety`, `providers`, `extraction`, `mcp_servers`: [src/avatar/config.py](/home/box/git/github/synapse/src/avatar/config.py:42).
plans/audits/codex-audit-6-ai-integration.md:16086:- AI optionality is not consistently enforced. `enabled=false` hides chat UI, but backend AI extraction path does not check it.
plans/audits/codex-audit-6-ai-integration.md:16109:- `AvatarTaskService` does not read provider `enabled`; disabled provider can still be default if YAML says so.
plans/audits/codex-audit-6-ai-integration.md:16110:- `AvatarConfig.providers` only stores `model` and `enabled`; no provider priority or runtime status models.
plans/audits/codex-audit-6-ai-integration.md:16135:- No clear test that `enabled=false` prevents backend `/api/ai/extract` or import AI use.
plans/audits/codex-audit-6-ai-integration.md:16155:- Should `enabled=false` disable all backend AI service calls, or only user-facing chat?
apps/web/src/components/modules/pack-detail/plugins/types.ts:113:   * What features are enabled for this plugin?
apps/web/src/components/modules/pack-detail/plugins/types.ts:394:  enabled: boolean
apps/web/src/components/modules/inventory/types.ts:32:  active_in_uis: string[]
apps/web/src/components/modules/inventory/types.ts:37:  enabled: boolean
apps/web/src/components/modules/inventory/types.ts:89:  active_in_uis: string[]
apps/web/src/components/modules/inventory/types.ts:95:  enabled: boolean
apps/web/src/components/modules/inventory/types.ts:131:  enabled: boolean
apps/web/src/components/modules/inventory/types.ts:167:  backup_enabled: boolean
apps/web/src/components/modules/inventory/types.ts:213:  conflicts: number
apps/web/src/components/modules/inventory/types.ts:218:  enabled: boolean
apps/web/src/components/modules/ProfilesPage.tsx:31:  shadowed: ShadowedEntry[]
apps/web/src/components/modules/ProfilesPage.tsx:32:  shadowed_count: number
apps/web/src/components/modules/ProfilesPage.tsx:227:      {status && status.shadowed_count > 0 && (
apps/web/src/components/modules/ProfilesPage.tsx:231:            {t('profiles.shadowedCount', { count: status.shadowed_count })}
apps/web/src/components/modules/ProfilesPage.tsx:241:                  <th className="text-left px-4 py-3 text-sm font-medium text-amber-400">{t('profiles.table.shadowed')}</th>
apps/web/src/components/modules/ProfilesPage.tsx:245:                {status.shadowed.map((entry, index) => (
apps/web/src/components/modules/ProfilesPage.tsx:258:            {t('profiles.shadowedExplanation')}
apps/web/src/__tests__/settings-store.test.ts:40:    it('should have NSFW blur enabled by default', () => {
apps/web/src/__tests__/settings-store.test.ts:147:    it('should blur NSFW content when blur is enabled', () => {
apps/web/src/__tests__/settings-store.test.ts:176:      // With blur enabled
apps/web/src/__tests__/settings-store.test.ts:191:      // Blur re-enabled - card should stay revealed
apps/web/src/__tests__/settings-store.test.ts:205:   * - Blur is enabled globally
apps/web/src/__tests__/settings-store.test.ts:253:  it('should NOT show badge when blur is enabled', () => {
apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:158:    enabled: !!packName,
apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:176:          backup_enabled: false,
apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:184:    enabled: !!packName,
apps/web/src/components/modules/pack-detail/shared/EditableTags.tsx:34:   * Whether editing is enabled
apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx:423:  const packDependencies: PackDependencyRef[] = pack.pack?.pack_dependencies ?? []
apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx:447:    enabled: packDependencies.length > 0,
apps/web/src/components/modules/pack-detail/sections/PackStorageSection.tsx:123:                  backupEnabled={backupStatus.backup_enabled}
apps/web/src/components/modules/pack-detail/sections/PackStorageSection.tsx:131:                backupEnabled={backupStatus.backup_enabled}
apps/web/src/components/modules/pack-detail/shared/EditableText.tsx:37:   * Whether editing is enabled
apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:49:  controlnet: ['controlnet_enabled', 'controlnet_strength', 'controlnet_start', 'controlnet_end', 'controlnet_model', 'control_mode'],
apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:54:  freeu: ['freeu_enabled', 'freeu_b1', 'freeu_b2', 'freeu_s1', 'freeu_s2'],
apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:55:  ipadapter: ['ip_adapter_enabled', 'ip_adapter_weight', 'ip_adapter_noise', 'ip_adapter_model'],
apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:179:  if (typeof value === 'boolean') return value ? (translate?.('pack.parameters.enabled') ?? 'Enabled') : (translate?.('pack.parameters.disabled') ?? 'Disabled')
apps/web/src/components/modules/pack-detail/modals/AddPackDependencyModal.tsx:71:    enabled: isOpen,
apps/web/src/components/modules/pack-detail/modals/EditParametersModal.tsx:183:  { key: 'controlnet_enabled', labelKey: 'controlnet_enabled', type: 'boolean', default: 'false', category: 'controlnet' },
apps/web/src/components/modules/pack-detail/modals/EditParametersModal.tsx:217:  { key: 'freeu_enabled', labelKey: 'freeu_enabled', type: 'boolean', default: 'false', category: 'freeu' },
apps/web/src/components/modules/pack-detail/modals/EditParametersModal.tsx:224:  { key: 'ip_adapter_enabled', labelKey: 'ip_adapter_enabled', type: 'boolean', default: 'false', category: 'ipadapter' },
apps/web/src/components/modules/pack-detail/modals/EditParametersModal.tsx:441:              {value === 'true' ? t('pack.modals.parameters.enabled') : t('pack.modals.parameters.disabled')}
plans/audits/codex-audit-5-profiles.md:192:            conflicts=base.conflicts,
plans/audits/codex-audit-5-profiles.md:224:            conflicts=base.conflicts,
plans/audits/codex-audit-5-profiles.md:284:            shadowed=[],
plans/audits/codex-audit-5-profiles.md:305:                result.shadowed.extend(report.shadowed)
plans/audits/codex-audit-5-profiles.md:394:    shadowed: List[ShadowedEntry] = field(default_factory=list)
plans/audits/codex-audit-5-profiles.md:421:                shadowed = ShadowedEntry(
plans/audits/codex-audit-5-profiles.md:427:                self.shadowed.append(shadowed)
plans/audits/codex-audit-5-profiles.md:438:                return shadowed
plans/audits/codex-audit-5-profiles.md:458:    shadowed: List[ShadowedEntry] = field(default_factory=list)
plans/audits/codex-audit-5-profiles.md:553:            ViewPlan with entries and shadowed info
plans/audits/codex-audit-5-profiles.md:597:  - ui_sets.json
plans/audits/codex-audit-5-profiles.md:701:    def ui_sets_path(self) -> Path:
plans/audits/codex-audit-5-profiles.md:702:        """Path to ui_sets.json."""
plans/audits/codex-audit-5-profiles.md:703:        return self.state_path / "ui_sets.json"
plans/audits/codex-audit-5-profiles.md:863:- synapse.ui_sets.v1
plans/audits/codex-audit-5-profiles.md:1084:    conflicts_mode: ConflictMode = ConflictMode.LAST_WINS
plans/audits/codex-audit-5-profiles.md:1091:    enabled: bool = False
plans/audits/codex-audit-5-profiles.md:1165:# UI Sets Model (state/ui_sets.json)
plans/audits/codex-audit-5-profiles.md:1169:    """UI sets configuration (state/ui_sets.json)."""
plans/audits/codex-audit-5-profiles.md:1170:    schema_: str = Field(default="synapse.ui_sets.v1", alias="schema")
plans/audits/codex-audit-5-profiles.md:1188:        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:1189:        ui_targets = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:1282:        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:1283:        ui_targets = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:1331:        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:1332:        ui_targets = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:1509:            shadowed=plan.shadowed,
plans/audits/codex-audit-5-profiles.md:1567:        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:1568:        ui_names = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:1623:        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:1624:        ui_names = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:1779:            self._write_default_ui_sets()
plans/audits/codex-audit-5-profiles.md:1805:    def _write_default_ui_sets(self) -> None:
plans/audits/codex-audit-5-profiles.md:1806:        """Write default ui_sets.json."""
plans/audits/codex-audit-5-profiles.md:1807:        if not self.ui_sets_path.exists():
plans/audits/codex-audit-5-profiles.md:1808:            ui_sets = UISets.create_default()
plans/audits/codex-audit-5-profiles.md:1809:            self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
plans/audits/codex-audit-5-profiles.md:1876:    def load_ui_sets(self) -> UISets:
plans/audits/codex-audit-5-profiles.md:1878:        if not self.ui_sets_path.exists():
plans/audits/codex-audit-5-profiles.md:1880:        data = self.read_json(self.ui_sets_path)
plans/audits/codex-audit-5-profiles.md:1883:    def save_ui_sets(self, ui_sets: UISets) -> None:
plans/audits/codex-audit-5-profiles.md:1885:        self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
plans/audits/codex-audit-5-profiles.md:2406:                if lower in ("true", "yes", "1", "enabled", "on", "recommended", "required", "must"):
plans/audits/codex-audit-5-profiles.md:2479:                        if lower in ("true", "yes", "1", "enabled", "on"):
plans/audits/codex-audit-5-profiles.md:2535:344:        # Store config reference for later use (e.g., ui_roots, ui_sets)
plans/audits/codex-audit-5-profiles.md:2804:5019:    Returns per-UI runtime status, stack visualization, and shadowed files.
plans/audits/codex-audit-5-profiles.md:2994:    """Backup is not enabled in config."""
plans/audits/codex-audit-5-profiles.md:3095:        if not self.config.enabled:
plans/audits/codex-audit-5-profiles.md:3097:                enabled=False,
plans/audits/codex-audit-5-profiles.md:3107:                enabled=True,
plans/audits/codex-audit-5-profiles.md:3119:                enabled=True,
plans/audits/codex-audit-5-profiles.md:3135:                enabled=True,
plans/audits/codex-audit-5-profiles.md:3145:                enabled=True,
plans/audits/codex-audit-5-profiles.md:3176:            enabled=True,
plans/audits/codex-audit-5-profiles.md:3188:    def is_enabled(self) -> bool:
plans/audits/codex-audit-5-profiles.md:3189:        """Quick check if backup is enabled in config."""
plans/audits/codex-audit-5-profiles.md:3190:        return self.config.enabled
plans/audits/codex-audit-5-profiles.md:3195:        return status.enabled and status.connected
plans/audits/codex-audit-5-profiles.md:3199:        if not self.config.enabled:
plans/audits/codex-audit-5-profiles.md:3200:            logger.warning("[Backup] Operation failed: backup not enabled")
plans/audits/codex-audit-5-profiles.md:3201:            raise BackupNotEnabledError("Backup storage is not enabled")
plans/audits/codex-audit-5-profiles.md:3212:        if not self.config.enabled:
plans/audits/codex-audit-5-profiles.md:3322:src/avatar/routes.py:153:            {"gemini": {"enabled": true, "model": "gemini-3-pro-preview"}}
plans/audits/codex-audit-5-profiles.md:3407:apps/api/src/routers/system.py:67:    store_default_ui_set: str
plans/audits/codex-audit-5-profiles.md:3408:apps/api/src/routers/system.py:68:    store_ui_sets: Dict[str, List[str]]
plans/audits/codex-audit-5-profiles.md:3410:apps/api/src/routers/system.py:80:    store_default_ui_set: Optional[str] = None
plans/audits/codex-audit-5-profiles.md:3411:apps/api/src/routers/system.py:81:    store_ui_sets: Optional[Dict[str, List[str]]] = None
plans/audits/codex-audit-5-profiles.md:3433:apps/api/src/routers/system.py:220:        store_default_ui_set=config.store.default_ui_set,
plans/audits/codex-audit-5-profiles.md:3434:apps/api/src/routers/system.py:221:        store_ui_sets=config.store.ui_sets,
plans/audits/codex-audit-5-profiles.md:3437:apps/api/src/routers/system.py:255:    if update.store_default_ui_set is not None:
plans/audits/codex-audit-5-profiles.md:3438:apps/api/src/routers/system.py:256:        config.store.default_ui_set = update.store_default_ui_set
plans/audits/codex-audit-5-profiles.md:3439:apps/api/src/routers/system.py:258:    if update.store_ui_sets is not None:
plans/audits/codex-audit-5-profiles.md:3440:apps/api/src/routers/system.py:259:        config.store.ui_sets = update.store_ui_sets
plans/audits/codex-audit-5-profiles.md:3495:tests/e2e/test_core_workflows.py:431:    Expects: StatusReport with { profile, ui_targets, active, missing_blobs, unresolved, shadowed }
plans/audits/codex-audit-5-profiles.md:3729:    shadowed: List[Dict[str, Any]]
plans/audits/codex-audit-5-profiles.md:3730:    shadowed_count: int
plans/audits/codex-audit-5-profiles.md:3849:    Returns per-UI runtime status, stack visualization, and shadowed files.
plans/audits/codex-audit-5-profiles.md:3869:        # Get status for shadowed info
plans/audits/codex-audit-5-profiles.md:3872:        # Convert shadowed entries to dicts
plans/audits/codex-audit-5-profiles.md:3873:        all_shadowed = []
plans/audits/codex-audit-5-profiles.md:3874:        for entry in status.shadowed:
plans/audits/codex-audit-5-profiles.md:3875:            all_shadowed.append({
plans/audits/codex-audit-5-profiles.md:3887:            shadowed=all_shadowed,
plans/audits/codex-audit-5-profiles.md:3888:            shadowed_count=len(all_shadowed),
plans/audits/codex-audit-5-profiles.md:3943:                "shadowed_count": len(r.shadowed),
plans/audits/codex-audit-5-profiles.md:4038:        if result.shadowed:
plans/audits/codex-audit-5-profiles.md:4039:            output_warning(f"{len(result.shadowed)} shadowed file(s)")
plans/audits/codex-audit-5-profiles.md:4162:                enabled = "[green]✓[/green]" if pack_entry.enabled else "[red]✗[/red]"
plans/audits/codex-audit-5-profiles.md:4163:                console.print(f"  {i}. {enabled} [cyan]{pack_entry.name}[/cyan]")
plans/audits/codex-audit-5-profiles.md:4212:            if status.shadowed:
plans/audits/codex-audit-5-profiles.md:4214:                output_info(f"{len(status.shadowed)} shadowed file(s) (last pack wins)")
plans/audits/codex-audit-5-profiles.md:4441:            shadowed = len(report.get("shadowed", []))
plans/audits/codex-audit-5-profiles.md:4442:            console.print(f"  [cyan]{ui}[/cyan]: {entries} entries, {shadowed} shadowed")
plans/audits/codex-audit-5-profiles.md:4534:apps/api/src/routers/system.py:116:        nsfw_blur_enabled=config.ui.nsfw_blur_enabled,
plans/audits/codex-audit-5-profiles.md:4545:apps/api/src/routers/system.py:215:        nsfw_blur_enabled=config.ui.nsfw_blur_enabled,
plans/audits/codex-audit-5-profiles.md:4551:apps/api/src/routers/system.py:236:        config.ui.nsfw_blur_enabled = update.nsfw_blur_enabled
plans/audits/codex-audit-5-profiles.md:4562:apps/api/src/core/config.py:62:        return config.ui.nsfw_blur_enabled
plans/audits/codex-audit-5-profiles.md:5480:    def get_ui_sets(self) -> UISets:
plans/audits/codex-audit-5-profiles.md:5482:        return self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:5484:    def get_default_ui_set(self) -> str:
plans/audits/codex-audit-5-profiles.md:5500:            ui_set = self.get_default_ui_set()
plans/audits/codex-audit-5-profiles.md:5502:        ui_sets = self.get_ui_sets()
plans/audits/codex-audit-5-profiles.md:5503:        return ui_sets.sets.get(ui_set, [])
plans/audits/codex-audit-5-profiles.md:5523:        return self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:5525:    def get_default_ui_set(self) -> str:
plans/audits/codex-audit-5-profiles.md:5541:            ui_set = self.get_default_ui_set()
plans/audits/codex-audit-5-profiles.md:5543:        ui_sets = self.get_ui_sets()
plans/audits/codex-audit-5-profiles.md:5544:        return ui_sets.sets.get(ui_set, [])
plans/audits/codex-audit-5-profiles.md:6075:        # Get shadowed entries (would need to compute view plan for accurate info)
plans/audits/codex-audit-5-profiles.md:6076:        shadowed: List[ShadowedEntry] = []
plans/audits/codex-audit-5-profiles.md:6084:            shadowed=shadowed,
plans/audits/codex-audit-5-profiles.md:6169:            shadowed=status.shadowed,
plans/audits/codex-audit-5-profiles.md:6405:    nsfw_blur_enabled: bool
plans/audits/codex-audit-5-profiles.md:6434:    nsfw_blur_enabled: bool
plans/audits/codex-audit-5-profiles.md:6440:    store_default_ui_set: str
plans/audits/codex-audit-5-profiles.md:6441:    store_ui_sets: Dict[str, List[str]]
plans/audits/codex-audit-5-profiles.md:6447:    nsfw_blur_enabled: Optional[bool] = None
plans/audits/codex-audit-5-profiles.md:6453:    store_default_ui_set: Optional[str] = None
plans/audits/codex-audit-5-profiles.md:6454:    store_ui_sets: Optional[Dict[str, List[str]]] = None
plans/audits/codex-audit-5-profiles.md:6489:        nsfw_blur_enabled=config.ui.nsfw_blur_enabled,
plans/audits/codex-audit-5-profiles.md:6588:        nsfw_blur_enabled=config.ui.nsfw_blur_enabled,
plans/audits/codex-audit-5-profiles.md:6593:        store_default_ui_set=config.store.default_ui_set,
plans/audits/codex-audit-5-profiles.md:6594:        store_ui_sets=config.store.ui_sets,
plans/audits/codex-audit-5-profiles.md:6608:    if update.nsfw_blur_enabled is not None:
plans/audits/codex-audit-5-profiles.md:6609:        config.ui.nsfw_blur_enabled = update.nsfw_blur_enabled
plans/audits/codex-audit-5-profiles.md:6628:    if update.store_default_ui_set is not None:
plans/audits/codex-audit-5-profiles.md:6629:        config.store.default_ui_set = update.store_default_ui_set
plans/audits/codex-audit-5-profiles.md:6631:    if update.store_ui_sets is not None:
plans/audits/codex-audit-5-profiles.md:6632:        config.store.ui_sets = update.store_ui_sets
plans/audits/codex-audit-5-profiles.md:6719:    def nsfw_blur_enabled(self) -> bool:
plans/audits/codex-audit-5-profiles.md:6721:        return config.ui.nsfw_blur_enabled
plans/audits/codex-audit-5-profiles.md:6819:    nsfw_blur_enabled: bool = True  # DEFAULT = ACTIVE (blur NSFW when toggle OFF)
plans/audits/codex-audit-5-profiles.md:6857:    default_ui_set: str = "local"
plans/audits/codex-audit-5-profiles.md:6858:    ui_sets: dict = field(default_factory=lambda: {
plans/audits/codex-audit-5-profiles.md:6873:            "default_ui_set": self.default_ui_set,
plans/audits/codex-audit-5-profiles.md:6874:            "ui_sets": self.ui_sets,
plans/audits/codex-audit-5-profiles.md:6880:        default_ui_sets = {
plans/audits/codex-audit-5-profiles.md:6891:            default_ui_set=data.get("default_ui_set", "local"),
plans/audits/codex-audit-5-profiles.md:6892:            ui_sets=data.get("ui_sets", default_ui_sets),
plans/audits/codex-audit-5-profiles.md:6980:  shadowed: ShadowedEntry[]
plans/audits/codex-audit-5-profiles.md:6981:  shadowed_count: number
plans/audits/codex-audit-5-profiles.md:7176:      {status && status.shadowed_count > 0 && (
plans/audits/codex-audit-5-profiles.md:7180:            {t('profiles.shadowedCount', { count: status.shadowed_count })}
plans/audits/codex-audit-5-profiles.md:7190:                  <th className="text-left px-4 py-3 text-sm font-medium text-amber-400">{t('profiles.table.shadowed')}</th>
plans/audits/codex-audit-5-profiles.md:7194:                {status.shadowed.map((entry, index) => (
plans/audits/codex-audit-5-profiles.md:7207:            {t('profiles.shadowedExplanation')}
plans/audits/codex-audit-5-profiles.md:7493:            shadowed=status.shadowed,
plans/audits/codex-audit-5-profiles.md:7569:                "nsfw_blur_enabled": self.ui.nsfw_blur_enabled,
plans/audits/codex-audit-5-profiles.md:7612:                    config.ui.nsfw_blur_enabled = ui_data.get(
plans/audits/codex-audit-5-profiles.md:7613:                        "nsfw_blur_enabled", True
plans/audits/codex-audit-5-profiles.md:7672:  nsfw_blur_enabled: boolean
plans/audits/codex-audit-5-profiles.md:7678:  store_default_ui_set: string
plans/audits/codex-audit-5-profiles.md:7679:  store_ui_sets: Record<string, string[]>
plans/audits/codex-audit-5-profiles.md:7739:      if (settings.store_default_ui_set) setStoreDefaultUiSet(settings.store_default_ui_set)
plans/audits/codex-audit-5-profiles.md:7775:      setBackupEnabled(backupStatus.enabled)
plans/audits/codex-audit-5-profiles.md:7826:        nsfw_blur_enabled: nsfwBlurEnabled,
plans/audits/codex-audit-5-profiles.md:7829:        store_default_ui_set: storeDefaultUiSet,
plans/audits/codex-audit-5-profiles.md:7836:        enabled: backupEnabled,
plans/audits/codex-audit-5-profiles.md:8042:                options={(settings?.store_ui_sets ? Object.keys(settings.store_ui_sets) : [storeDefaultUiSet]).map((setName) => ({
plans/audits/codex-audit-5-profiles.md:8044:                  label: settings?.store_ui_sets
plans/audits/codex-audit-5-profiles.md:8045:                    ? `${setName} (${settings.store_ui_sets[setName].join(', ')})`
plans/audits/codex-audit-5-profiles.md:8612:  enabled: false, // Manual only
plans/audits/codex-audit-5-profiles.md:8829:    "enabled": true,
plans/audits/codex-audit-5-profiles.md:8981:    active_in_uis: List[str] = []       # Ktera UI ho prave pouzivaji
plans/audits/codex-audit-5-profiles.md:9343:plans/PLAN-Model-Inventory.md:4081:- Config (config.json, ui_sets.json)
plans/audits/codex-audit-5-profiles.md:9360:/bin/bash -lc "rg -n \"ProfileService|ViewBuilder|UIAttacher|profile_service|view_builder|ui_attach|use\\(|sync_profile|clean_orphaned|attach_uis|extra_model_paths|shadowed|active view|backup\" tests -S" in /home/box/git/github/synapse
plans/audits/codex-audit-5-profiles.md:9382:tests/store/test_pack_dependencies.py
plans/audits/codex-audit-5-profiles.md:9398:tests/e2e/test_core_workflows.py:431:    Expects: StatusReport with { profile, ui_targets, active, missing_blobs, unresolved, shadowed }
plans/audits/codex-audit-5-profiles.md:9399:tests/e2e/test_core_workflows.py:446:            assert "shadowed" in data and isinstance(data["shadowed"], list)
plans/audits/codex-audit-5-profiles.md:9400:tests/e2e/test_core_workflows.py:454:              shadowed: [], shadowed_count, updates_available }
plans/audits/codex-audit-5-profiles.md:9401:tests/e2e/test_core_workflows.py:464:            assert "shadowed" in data and isinstance(data["shadowed"], list)
plans/audits/codex-audit-5-profiles.md:9402:tests/e2e/test_core_workflows.py:465:            assert "shadowed_count" in data
plans/audits/codex-audit-5-profiles.md:9407:tests/integration/test_mcp_smoke.py:225:        assert "not enabled" in _get_backup_status_impl(store=ctx.store).lower() or \
plans/audits/codex-audit-5-profiles.md:9410:tests/integration/test_mcp_store.py:149:    def test_backup_not_enabled(self, store_ctx):
plans/audits/codex-audit-5-profiles.md:9435:tests/unit/avatar/test_mcp_tools.py:587:        status = _make_mock_backup_status(enabled=False)
plans/audits/codex-audit-5-profiles.md:9449:tests/unit/avatar/test_mcp_tools.py:950:    def test_backup_auto_backup_enabled(self):
plans/audits/codex-audit-5-profiles.md:9472:tests/store/test_api_critical.py:297:        # StatusReport has these fields: profile, ui_targets, active, missing_blobs, unresolved, shadowed
plans/audits/codex-audit-5-profiles.md:9541:tests/store/test_api_critical.py:1316:        store.configure_backup(BackupConfig(enabled=True, path=str(backup_path)))
plans/audits/codex-audit-5-profiles.md:9548:tests/store/test_views_profiles.py:41:            assert len(plan.shadowed) == 0
plans/audits/codex-audit-5-profiles.md:9553:tests/store/test_views_profiles.py:192:            # Should have one shadowed entry
plans/audits/codex-audit-5-profiles.md:9554:tests/store/test_views_profiles.py:193:            assert len(plan.shadowed) == 1
plans/audits/codex-audit-5-profiles.md:9555:tests/store/test_views_profiles.py:194:            assert plan.shadowed[0].winner_pack == "Pack2"
plans/audits/codex-audit-5-profiles.md:9556:tests/store/test_views_profiles.py:195:            assert plan.shadowed[0].loser_pack == "Pack1"
plans/audits/codex-audit-5-profiles.md:9589:tests/store/test_inventory_stabilization.py:10:- Bug #22: Clear completed downloads route shadowed by {download_id}
plans/audits/codex-audit-5-profiles.md:9591:tests/store/test_inventory_stabilization.py:145:    Bug #22: Clear completed downloads route shadowed by {download_id}
plans/audits/codex-audit-5-profiles.md:9655:tests/store/test_inventory.py:352:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9669:tests/store/test_inventory.py:387:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9682:tests/store/test_inventory.py:418:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9704:tests/store/test_cli.py:406:    def test_status_enabled_connected(self, mock_store, sample_backup_status):
plans/audits/codex-audit-5-profiles.md:9705:tests/store/test_cli.py:407:        """Test backup status when enabled and connected."""
plans/audits/codex-audit-5-profiles.md:9779:tests/store/test_e2e.py:481:            assert hasattr(status, "shadowed")
plans/audits/codex-audit-5-profiles.md:9792:tests/store/test_e2e.py:1016:            assert len(report.shadowed) == 1, "Should detect one shadowed file"
plans/audits/codex-audit-5-profiles.md:9793:tests/store/test_e2e.py:1017:            assert report.shadowed[0].winner_pack == "PackB"  # Last wins
plans/audits/codex-audit-5-profiles.md:9794:tests/store/test_e2e.py:1018:            assert report.shadowed[0].loser_pack == "PackA"
plans/audits/codex-audit-5-profiles.md:9796:tests/store/test_e2e.py:1040:            assert report2.shadowed[0].winner_pack == "PackA"
plans/audits/codex-audit-5-profiles.md:9797:tests/store/test_e2e.py:1041:            assert report2.shadowed[0].loser_pack == "PackB"
plans/audits/codex-audit-5-profiles.md:9802:tests/store/test_e2e.py:1352:            assert len(report.shadowed) == 2, f"Expected 2 shadowed entries, got {len(report.shadowed)}"
plans/audits/codex-audit-5-profiles.md:9803:tests/store/test_e2e.py:1355:            shadow_pairs = [(e.winner_pack, e.loser_pack) for e in report.shadowed]
plans/audits/codex-audit-5-profiles.md:9805:tests/store/test_e2e.py:1559:            assert len(report.shadowed) == 3, f"Expected 3 shadowed, got {len(report.shadowed)}"
plans/audits/codex-audit-5-profiles.md:9806:tests/store/test_e2e.py:1561:            shadowed_map = {e.dst_relpath: (e.winner_pack, e.loser_pack) for e in report.shadowed}
plans/audits/codex-audit-5-profiles.md:9807:tests/store/test_e2e.py:1568:            assert shadowed_map[style1_path] == ("PackC", "PackA"), f"style1 wrong: {shadowed_map.get(style1_path)}"
plans/audits/codex-audit-5-profiles.md:9808:tests/store/test_e2e.py:1569:            assert shadowed_map[style2_path] == ("PackB", "PackA"), f"style2 wrong: {shadowed_map.get(style2_path)}"
plans/audits/codex-audit-5-profiles.md:9809:tests/store/test_e2e.py:1570:            assert shadowed_map[style3_path] == ("PackC", "PackB"), f"style3 wrong: {shadowed_map.get(style3_path)}"
plans/audits/codex-audit-5-profiles.md:9811:tests/store/test_e2e.py:1613:            assert report1.shadowed[0].winner_pack == "PackB"
plans/audits/codex-audit-5-profiles.md:9813:tests/store/test_e2e.py:1626:            assert report2.shadowed[0].winner_pack == "PackA"
plans/audits/codex-audit-5-profiles.md:9818:tests/store/test_e2e.py:1661:            assert report_global.shadowed[0].winner_pack == "PackB"
plans/audits/codex-audit-5-profiles.md:9838:tests/store/test_e2e.py:2285:            assert len(report.shadowed) == 0
plans/audits/codex-audit-5-profiles.md:9876:tests/store/test_backup.py:43:        assert store.backup_service.is_enabled() is False
plans/audits/codex-audit-5-profiles.md:9879:tests/store/test_backup.py:48:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9881:tests/store/test_backup.py:51:        assert store.backup_service.is_enabled() is True
plans/audits/codex-audit-5-profiles.md:9882:tests/store/test_backup.py:54:        """Status shows disabled when backup not enabled."""
plans/audits/codex-audit-5-profiles.md:9891:tests/store/test_backup.py:100:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9900:tests/store/test_backup.py:123:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9904:tests/store/test_backup.py:135:    def test_backup_blob_not_enabled(self, tmp_path):
plans/audits/codex-audit-5-profiles.md:9912:tests/store/test_backup.py:165:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9921:tests/store/test_backup.py:185:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9931:tests/store/test_backup.py:213:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9939:tests/store/test_backup.py:242:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9943:tests/store/test_backup.py:261:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9950:tests/store/test_backup.py:284:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9955:tests/store/test_backup.py:308:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9962:tests/store/test_backup.py:323:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9971:tests/store/test_backup.py:350:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9978:tests/store/test_backup.py:380:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9985:tests/store/test_backup.py:403:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:9997:tests/store/test_backup.py:431:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10003:tests/store/test_backup.py:456:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10012:tests/store/test_backup.py:485:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10018:tests/store/test_backup.py:512:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10023:tests/store/test_backup.py:537:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10028:tests/store/test_backup.py:555:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10033:tests/store/test_backup.py:570:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10038:tests/store/test_backup.py:591:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10047:tests/store/test_backup.py:616:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10054:tests/store/test_backup.py:636:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10063:tests/store/test_backup.py:662:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10073:tests/store/test_backup.py:695:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10081:tests/store/test_backup.py:721:        assert store.get_backup_status().enabled is False
plans/audits/codex-audit-5-profiles.md:10085:tests/store/test_backup.py:742:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10092:tests/store/test_backup.py:773:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10098:tests/store/test_backup.py:792:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10107:tests/store/test_backup.py:817:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10113:tests/store/test_backup.py:843:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10126:tests/store/test_backup.py:889:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10132:tests/store/test_backup.py:922:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10137:tests/store/test_backup.py:947:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10147:tests/store/test_backup.py:991:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10155:tests/store/test_backup.py:1018:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10161:tests/store/test_backup.py:1041:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10168:tests/store/test_backup.py:1068:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10174:tests/store/test_backup.py:1094:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:10455:    Expects: StatusReport with { profile, ui_targets, active, missing_blobs, unresolved, shadowed }
plans/audits/codex-audit-5-profiles.md:10470:            assert "shadowed" in data and isinstance(data["shadowed"], list)
plans/audits/codex-audit-5-profiles.md:10478:              shadowed: [], shadowed_count, updates_available }
plans/audits/codex-audit-5-profiles.md:10488:            assert "shadowed" in data and isinstance(data["shadowed"], list)
plans/audits/codex-audit-5-profiles.md:10489:            assert "shadowed_count" in data
plans/audits/codex-audit-5-profiles.md:10674:            assert len(plan.shadowed) == 0
plans/audits/codex-audit-5-profiles.md:10825:            # Should have one shadowed entry
plans/audits/codex-audit-5-profiles.md:10826:            assert len(plan.shadowed) == 1
plans/audits/codex-audit-5-profiles.md:10827:            assert plan.shadowed[0].winner_pack == "Pack2"
plans/audits/codex-audit-5-profiles.md:10828:            assert plan.shadowed[0].loser_pack == "Pack1"
plans/audits/codex-audit-5-profiles.md:11881:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:11914:        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:11940:        assert store.get_backup_status().enabled is False
plans/audits/codex-audit-5-profiles.md:12211:src/store/api.py:344:        # Store config reference for later use (e.g., ui_roots, ui_sets)
plans/audits/codex-audit-5-profiles.md:12219:src/store/api.py:1354:            "enabled": store.backup_service.config.enabled,
plans/audits/codex-audit-5-profiles.md:12270:        # Store config reference for later use (e.g., ui_roots, ui_sets)
plans/audits/codex-audit-5-profiles.md:12808:        Find all packs that depend on the given pack via pack_dependencies.
plans/audits/codex-audit-5-profiles.md:12811:            List of pack names that have pack_name in their pack_dependencies.
plans/audits/codex-audit-5-profiles.md:12819:                dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
plans/audits/codex-audit-5-profiles.md:13386:  1021	    conflicts: ConflictConfig = Field(default_factory=ConflictConfig)
plans/audits/codex-audit-5-profiles.md:13487:  1141	    shadowed: List[ShadowedEntry] = Field(default_factory=list)
plans/audits/codex-audit-5-profiles.md:13577:  1231	    shadowed: List[ShadowedEntry] = Field(default_factory=list)
plans/audits/codex-audit-5-profiles.md:13606:  1260	    shadowed: List[ShadowedEntry] = Field(default_factory=list)
plans/audits/codex-audit-5-profiles.md:13765:   130	            conflicts=base.conflicts,
plans/audits/codex-audit-5-profiles.md:13797:   162	            conflicts=base.conflicts,
plans/audits/codex-audit-5-profiles.md:13857:   222	            shadowed=[],
plans/audits/codex-audit-5-profiles.md:13878:   243	                result.shadowed.extend(report.shadowed)
plans/audits/codex-audit-5-profiles.md:13902:   267	        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:13903:   268	        ui_targets = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:13996:   361	        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:13997:   362	        ui_targets = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:14045:   410	        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:14046:   411	        ui_targets = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:14137:    68	    shadowed: List[ShadowedEntry] = field(default_factory=list)
plans/audits/codex-audit-5-profiles.md:14164:    95	                shadowed = ShadowedEntry(
plans/audits/codex-audit-5-profiles.md:14170:   101	                self.shadowed.append(shadowed)
plans/audits/codex-audit-5-profiles.md:14181:   112	                return shadowed
plans/audits/codex-audit-5-profiles.md:14201:   132	    shadowed: List[ShadowedEntry] = field(default_factory=list)
plans/audits/codex-audit-5-profiles.md:14296:   227	            ViewPlan with entries and shadowed info
plans/audits/codex-audit-5-profiles.md:14373:   304	            shadowed=plan.shadowed,
plans/audits/codex-audit-5-profiles.md:14431:   362	        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:14432:   363	        ui_names = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:14487:   418	        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-5-profiles.md:14488:   419	        ui_names = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-5-profiles.md:14756:   111	    def ui_sets_path(self) -> Path:
plans/audits/codex-audit-5-profiles.md:14757:   112	        """Path to ui_sets.json."""
plans/audits/codex-audit-5-profiles.md:14758:   113	        return self.state_path / "ui_sets.json"
plans/audits/codex-audit-5-profiles.md:14878:   302	            self._write_default_ui_sets()
plans/audits/codex-audit-5-profiles.md:14904:   328	    def _write_default_ui_sets(self) -> None:
plans/audits/codex-audit-5-profiles.md:14905:   329	        """Write default ui_sets.json."""
plans/audits/codex-audit-5-profiles.md:14906:   330	        if not self.ui_sets_path.exists():
plans/audits/codex-audit-5-profiles.md:14907:   331	            ui_sets = UISets.create_default()
plans/audits/codex-audit-5-profiles.md:14908:   332	            self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
plans/audits/codex-audit-5-profiles.md:15682:   318	            ui_set = self.get_default_ui_set()
plans/audits/codex-audit-5-profiles.md:15684:   320	        ui_sets = self.get_ui_sets()
plans/audits/codex-audit-5-profiles.md:15685:   321	        return ui_sets.sets.get(ui_set, [])
plans/audits/codex-audit-5-profiles.md:15882:   951	        # Get shadowed entries (would need to compute view plan for accurate info)
plans/audits/codex-audit-5-profiles.md:15883:   952	        shadowed: List[ShadowedEntry] = []
plans/audits/codex-audit-5-profiles.md:15891:   960	            shadowed=shadowed,
plans/audits/codex-audit-5-profiles.md:15904:  1045	            shadowed=status.shadowed,
plans/audits/codex-audit-5-profiles.md:16414:   344	        # Store config reference for later use (e.g., ui_roots, ui_sets)
plans/audits/codex-audit-5-profiles.md:16480:  5019	    Returns per-UI runtime status, stack visualization, and shadowed files.
plans/audits/codex-audit-5-profiles.md:16500:  5039	        # Get status for shadowed info
plans/audits/codex-audit-5-profiles.md:16503:  5042	        # Convert shadowed entries to dicts
plans/audits/codex-audit-5-profiles.md:16504:  5043	        all_shadowed = []
plans/audits/codex-audit-5-profiles.md:16505:  5044	        for entry in status.shadowed:
plans/audits/codex-audit-5-profiles.md:16506:  5045	            all_shadowed.append({
plans/audits/codex-audit-5-profiles.md:16518:  5057	            shadowed=all_shadowed,
plans/audits/codex-audit-5-profiles.md:16519:  5058	            shadowed_count=len(all_shadowed),
plans/audits/codex-audit-5-profiles.md:16574:  5113	                "shadowed_count": len(r.shadowed),
plans/audits/codex-audit-5-profiles.md:16661:    31	  shadowed: ShadowedEntry[]
plans/audits/codex-audit-5-profiles.md:16662:    32	  shadowed_count: number
plans/audits/codex-audit-5-profiles.md:16857:   227	      {status && status.shadowed_count > 0 && (
plans/audits/codex-audit-5-profiles.md:16861:   231	            {t('profiles.shadowedCount', { count: status.shadowed_count })}
plans/audits/codex-audit-5-profiles.md:16871:   241	                  <th className="text-left px-4 py-3 text-sm font-medium text-amber-400">{t('profiles.table.shadowed')}</th>
plans/audits/codex-audit-5-profiles.md:16875:   245	                {status.shadowed.map((entry, index) => (
plans/audits/codex-audit-5-profiles.md:16888:   258	            {t('profiles.shadowedExplanation')}
plans/audits/codex-audit-5-profiles.md:16935:    19	  nsfw_blur_enabled: boolean
plans/audits/codex-audit-5-profiles.md:16941:    25	  store_default_ui_set: string
plans/audits/codex-audit-5-profiles.md:16942:    26	  store_ui_sets: Record<string, string[]>
plans/audits/codex-audit-5-profiles.md:17002:    86	      if (settings.store_default_ui_set) setStoreDefaultUiSet(settings.store_default_ui_set)
plans/audits/codex-audit-5-profiles.md:17038:   122	      setBackupEnabled(backupStatus.enabled)
plans/audits/codex-audit-5-profiles.md:17089:   173	        nsfw_blur_enabled: nsfwBlurEnabled,
plans/audits/codex-audit-5-profiles.md:17092:   176	        store_default_ui_set: storeDefaultUiSet,
plans/audits/codex-audit-5-profiles.md:17099:   183	        enabled: backupEnabled,
plans/audits/codex-audit-5-profiles.md:17131:   384	                options={(settings?.store_ui_sets ? Object.keys(settings.store_ui_sets) : [storeDefaultUiSet]).map((setName) => ({
plans/audits/codex-audit-5-profiles.md:17133:   386	                  label: settings?.store_ui_sets
plans/audits/codex-audit-5-profiles.md:17134:   387	                    ? `${setName} (${settings.store_ui_sets[setName].join(', ')})`
plans/audits/codex-audit-5-profiles.md:17391:    32	    nsfw_blur_enabled: bool
plans/audits/codex-audit-5-profiles.md:17420:    61	    nsfw_blur_enabled: bool
plans/audits/codex-audit-5-profiles.md:17426:    67	    store_default_ui_set: str
plans/audits/codex-audit-5-profiles.md:17427:    68	    store_ui_sets: Dict[str, List[str]]
plans/audits/codex-audit-5-profiles.md:17433:    74	    nsfw_blur_enabled: Optional[bool] = None
plans/audits/codex-audit-5-profiles.md:17439:    80	    store_default_ui_set: Optional[str] = None
plans/audits/codex-audit-5-profiles.md:17440:    81	    store_ui_sets: Optional[Dict[str, List[str]]] = None
plans/audits/codex-audit-5-profiles.md:17475:   116	        nsfw_blur_enabled=config.ui.nsfw_blur_enabled,
plans/audits/codex-audit-5-profiles.md:17576:   215	        nsfw_blur_enabled=config.ui.nsfw_blur_enabled,
plans/audits/codex-audit-5-profiles.md:17581:   220	        store_default_ui_set=config.store.default_ui_set,
plans/audits/codex-audit-5-profiles.md:17582:   221	        store_ui_sets=config.store.ui_sets,
plans/audits/codex-audit-5-profiles.md:17596:   235	    if update.nsfw_blur_enabled is not None:
plans/audits/codex-audit-5-profiles.md:17597:   236	        config.ui.nsfw_blur_enabled = update.nsfw_blur_enabled
plans/audits/codex-audit-5-profiles.md:17616:   255	    if update.store_default_ui_set is not None:
plans/audits/codex-audit-5-profiles.md:17617:   256	        config.store.default_ui_set = update.store_default_ui_set
plans/audits/codex-audit-5-profiles.md:17619:   258	    if update.store_ui_sets is not None:
plans/audits/codex-audit-5-profiles.md:17620:   259	        config.store.ui_sets = update.store_ui_sets
plans/audits/codex-audit-5-profiles.md:17702:    94	    nsfw_blur_enabled: bool = True  # DEFAULT = ACTIVE (blur NSFW when toggle OFF)
plans/audits/codex-audit-5-profiles.md:17740:   132	    default_ui_set: str = "local"
plans/audits/codex-audit-5-profiles.md:17741:   133	    ui_sets: dict = field(default_factory=lambda: {
plans/audits/codex-audit-5-profiles.md:17756:   148	            "default_ui_set": self.default_ui_set,
plans/audits/codex-audit-5-profiles.md:17757:   149	            "ui_sets": self.ui_sets,
plans/audits/codex-audit-5-profiles.md:17764:   155	        default_ui_sets = {
plans/audits/codex-audit-5-profiles.md:17775:   166	            default_ui_set=data.get("default_ui_set", "local"),
plans/audits/codex-audit-5-profiles.md:17776:   167	            ui_sets=data.get("ui_sets", default_ui_sets),
plans/audits/codex-audit-5-profiles.md:17969:   403	        if result.shadowed:
plans/audits/codex-audit-5-profiles.md:17970:   404	            output_warning(f"{len(result.shadowed)} shadowed file(s)")
plans/audits/codex-audit-5-profiles.md:18066:   527	                enabled = "[green]✓[/green]" if pack_entry.enabled else "[red]✗[/red]"
plans/audits/codex-audit-5-profiles.md:18067:   528	                console.print(f"  {i}. {enabled} [cyan]{pack_entry.name}[/cyan]")
plans/audits/codex-audit-5-profiles.md:18263:   979	            shadowed = len(report.get("shadowed", []))
plans/audits/codex-audit-5-profiles.md:18264:   980	            console.print(f"  [cyan]{ui}[/cyan]: {entries} entries, {shadowed} shadowed")
plans/audits/codex-audit-5-profiles.md:18393:   295	    active_in_uis: List[str] = []       # Ktera UI ho prave pouzivaji
plans/audits/codex-audit-5-profiles.md:18467:    41	            assert len(plan.shadowed) == 0
plans/audits/codex-audit-5-profiles.md:18618:   192	            # Should have one shadowed entry
plans/audits/codex-audit-5-profiles.md:18619:   193	            assert len(plan.shadowed) == 1
plans/audits/codex-audit-5-profiles.md:18620:   194	            assert plan.shadowed[0].winner_pack == "Pack2"
plans/audits/codex-audit-5-profiles.md:18621:   195	            assert plan.shadowed[0].loser_pack == "Pack1"
plans/audits/codex-audit-5-profiles.md:19350:   662	        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:19383:   695	        config = BackupConfig(enabled=True, path=str(backup_path))
plans/audits/codex-audit-5-profiles.md:19409:   721	        assert store.get_backup_status().enabled is False
plans/audits/codex-audit-5-profiles.md:20878:  3334	        pack_path = store.layout.pack_path(request.name)
plans/audits/codex-audit-5-profiles.md:20903:  4581	        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-5-profiles.md:20924:  4602	            # Create symlink with pack prefix to avoid conflicts
plans/audits/codex-audit-5-profiles.md:20962:  4739	        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-5-profiles.md:21169:src/store/api.py:3334:        pack_path = store.layout.pack_path(request.name)
plans/audits/codex-audit-5-profiles.md:21172:src/store/api.py:3424:            old_path = store.layout.pack_path(pack_name)
plans/audits/codex-audit-5-profiles.md:21173:src/store/api.py:4078:        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-5-profiles.md:21174:src/store/api.py:4581:        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-5-profiles.md:21175:src/store/api.py:4739:        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-5-profiles.md:21176:src/store/api.py:4790:        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-5-profiles.md:21177:src/store/api.py:4859:        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-5-profiles.md:21178:src/store/api.py:4958:            pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-5-profiles.md:21225:- `config/settings.py` has a separate `StoreSettings.ui_sets` default without `comfy_only` at `config/settings.py:127-142`.
plans/audits/codex-audit-5-profiles.md:21226:- Store runtime targets come from store state `ui_sets.json`, not the app settings object, via `src/store/__init__.py:307-321`.
plans/audits/codex-audit-5-profiles.md:21227:- This means app settings UI-set config and store `state/ui_sets.json` can diverge.
plans/audits/codex-audit-5-profiles.md:21286:- Internal Profile view conflicts are resolved by destination path.
plans/audits/codex-audit-5-profiles.md:21290:- `ProfileService.ensure_work_profile()` deliberately puts the used pack at the end so it wins conflicts at `src/store/profile_service.py:134-140`.
plans/audits/codex-audit-5-profiles.md:21292:- `Profile.conflicts` exists at `src/store/models.py:1017-1022`.
plans/audits/codex-audit-5-profiles.md:21294:- `ViewBuilder` does not actually branch on `profile.conflicts.mode`.
plans/audits/codex-audit-5-profiles.md:21296:- Conflict info is returned in `UseResult.shadowed` after `use()` builds views at `src/store/profile_service.py:240-246`.
plans/audits/codex-audit-5-profiles.md:21297:- Store status currently returns an empty `shadowed` list and says accurate info would require computing a view plan at `src/store/__init__.py:951-960`.
plans/audits/codex-audit-5-profiles.md:21298:- Profiles status reads shadowed entries from `store.status()` at `src/store/api.py:5039-5059`.
plans/audits/codex-audit-5-profiles.md:21299:- Therefore `ProfilesPage` has a shadowed table, but it will normally show none unless `store.status()` is expanded.
plans/audits/codex-audit-5-profiles.md:21300:- For UI installation conflicts:
plans/audits/codex-audit-5-profiles.md:21315:- Singleton UI sets exist, so passing `ui_set: "comfyui"` works when `state/ui_sets.json` contains those singleton sets at `src/store/models.py:337-341`.
plans/audits/codex-audit-5-profiles.md:21317:- It has a shadowed files table at `apps/web/src/components/modules/ProfilesPage.tsx:226-260`.
plans/audits/codex-audit-5-profiles.md:21350:  - store state `state/ui_sets.json`
plans/audits/codex-audit-5-profiles.md:21351:  - app config `config.settings.StoreSettings.ui_sets`
plans/audits/codex-audit-5-profiles.md:21354:  - `config.settings.StoreSettings.default_ui_set`
plans/audits/codex-audit-5-profiles.md:21355:- No clear specification says whether Settings edits should mutate `state/config.json` and `state/ui_sets.json`.
plans/audits/codex-audit-5-profiles.md:21359:- No clear specification defines whether UI-native files should be shadowed, preserved, warned, hidden, or indexed.
plans/audits/codex-audit-5-profiles.md:21396:- `Profile.conflicts.mode` is modeled but ignored by `ViewBuilder`; all conflicts are last-wins.
plans/audits/codex-audit-5-profiles.md:21397:- `StatusReport.shadowed` is always empty from `Store.status()` at `src/store/__init__.py:951-960`.
plans/audits/codex-audit-5-profiles.md:21398:- `ProfilesPage` has a shadowed table that is currently starved by that empty status.
plans/audits/codex-audit-5-profiles.md:21399:- `ProfilePackEntry.enabled` is shown in CLI at `src/store/cli.py:524-528`, but `ViewBuilder.compute_plan()` does not check `pack_entry.enabled` at `src/store/view_builder.py:236-270`.
plans/audits/codex-audit-5-profiles.md:21430:- Existing root-level Forge model filename conflicts are not detected.
plans/audits/codex-audit-5-profiles.md:21439:- Existing A1111 root-level model filename conflicts are not detected.
plans/audits/codex-audit-5-profiles.md:21449:- Existing SD.Next root-level model filename conflicts are not detected.
plans/audits/codex-audit-5-profiles.md:21455:- Store UI targets still come from `state/ui_sets.json` at `src/store/__init__.py:307-321`.
plans/audits/codex-audit-5-profiles.md:21457:- Settings UI sets do not obviously mutate `state/ui_sets.json`.
plans/audits/codex-audit-5-profiles.md:21460:- Store singleton is not reset when only `store_default_ui_set` or `store_ui_sets` change at `apps/api/src/routers/system.py:255-259`.
plans/audits/codex-audit-5-profiles.md:21479:- It calls `store.layout.pack_path()` at `src/store/api.py:3334`.
plans/audits/codex-audit-5-profiles.md:21480:- `StoreLayout` defines `pack_dir()`, not `pack_path()`, in audited code at `src/store/layout.py:169-179`.
plans/audits/codex-audit-5-profiles.md:21512:- Inventory plan models `active_in_uis` at `plans/PLAN-Model-Inventory.md:280-296`.
plans/audits/codex-audit-5-profiles.md:21529:- It may call a nonexistent `StoreLayout.pack_path()` method. NEEDS VERIFICATION.
plans/audits/codex-audit-5-profiles.md:21591:- No test covers divergence between app config UI sets and store `state/ui_sets.json`.
plans/audits/codex-audit-5-profiles.md:21603:- No test covers disabled `ProfilePackEntry.enabled`.
plans/audits/codex-audit-5-profiles.md:21628:- Settings default UI set may not affect store runtime target resolution because store uses `state/ui_sets.json`.
plans/audits/codex-audit-5-profiles.md:21664:- Should Settings write `state/config.json` and `state/ui_sets.json` for Profile defaults?
plans/audits/codex-audit-5-profiles.md:21678:- Should `ProfilePackEntry.enabled` affect view building?
plans/audits/codex-audit-5-profiles.md:21691:- Should Profile status compute shadowed entries live, cache them, or persist build reports?
plans/audits/codex-audit-5-profiles.md:21742:- `config/settings.py` has a separate `StoreSettings.ui_sets` default without `comfy_only` at `config/settings.py:127-142`.
plans/audits/codex-audit-5-profiles.md:21743:- Store runtime targets come from store state `ui_sets.json`, not the app settings object, via `src/store/__init__.py:307-321`.
plans/audits/codex-audit-5-profiles.md:21744:- This means app settings UI-set config and store `state/ui_sets.json` can diverge.
plans/audits/codex-audit-5-profiles.md:21803:- Internal Profile view conflicts are resolved by destination path.
plans/audits/codex-audit-5-profiles.md:21807:- `ProfileService.ensure_work_profile()` deliberately puts the used pack at the end so it wins conflicts at `src/store/profile_service.py:134-140`.
plans/audits/codex-audit-5-profiles.md:21809:- `Profile.conflicts` exists at `src/store/models.py:1017-1022`.
plans/audits/codex-audit-5-profiles.md:21811:- `ViewBuilder` does not actually branch on `profile.conflicts.mode`.
plans/audits/codex-audit-5-profiles.md:21813:- Conflict info is returned in `UseResult.shadowed` after `use()` builds views at `src/store/profile_service.py:240-246`.
plans/audits/codex-audit-5-profiles.md:21814:- Store status currently returns an empty `shadowed` list and says accurate info would require computing a view plan at `src/store/__init__.py:951-960`.
plans/audits/codex-audit-5-profiles.md:21815:- Profiles status reads shadowed entries from `store.status()` at `src/store/api.py:5039-5059`.
plans/audits/codex-audit-5-profiles.md:21816:- Therefore `ProfilesPage` has a shadowed table, but it will normally show none unless `store.status()` is expanded.
plans/audits/codex-audit-5-profiles.md:21817:- For UI installation conflicts:
plans/audits/codex-audit-5-profiles.md:21832:- Singleton UI sets exist, so passing `ui_set: "comfyui"` works when `state/ui_sets.json` contains those singleton sets at `src/store/models.py:337-341`.
plans/audits/codex-audit-5-profiles.md:21834:- It has a shadowed files table at `apps/web/src/components/modules/ProfilesPage.tsx:226-260`.
plans/audits/codex-audit-5-profiles.md:21867:  - store state `state/ui_sets.json`
plans/audits/codex-audit-5-profiles.md:21868:  - app config `config.settings.StoreSettings.ui_sets`
plans/audits/codex-audit-5-profiles.md:21871:  - `config.settings.StoreSettings.default_ui_set`
plans/audits/codex-audit-5-profiles.md:21872:- No clear specification says whether Settings edits should mutate `state/config.json` and `state/ui_sets.json`.
plans/audits/codex-audit-5-profiles.md:21876:- No clear specification defines whether UI-native files should be shadowed, preserved, warned, hidden, or indexed.
plans/audits/codex-audit-5-profiles.md:21913:- `Profile.conflicts.mode` is modeled but ignored by `ViewBuilder`; all conflicts are last-wins.
plans/audits/codex-audit-5-profiles.md:21914:- `StatusReport.shadowed` is always empty from `Store.status()` at `src/store/__init__.py:951-960`.
plans/audits/codex-audit-5-profiles.md:21915:- `ProfilesPage` has a shadowed table that is currently starved by that empty status.
plans/audits/codex-audit-5-profiles.md:21916:- `ProfilePackEntry.enabled` is shown in CLI at `src/store/cli.py:524-528`, but `ViewBuilder.compute_plan()` does not check `pack_entry.enabled` at `src/store/view_builder.py:236-270`.
plans/audits/codex-audit-5-profiles.md:21947:- Existing root-level Forge model filename conflicts are not detected.
plans/audits/codex-audit-5-profiles.md:21956:- Existing A1111 root-level model filename conflicts are not detected.
plans/audits/codex-audit-5-profiles.md:21966:- Existing SD.Next root-level model filename conflicts are not detected.
plans/audits/codex-audit-5-profiles.md:21972:- Store UI targets still come from `state/ui_sets.json` at `src/store/__init__.py:307-321`.
plans/audits/codex-audit-5-profiles.md:21974:- Settings UI sets do not obviously mutate `state/ui_sets.json`.
plans/audits/codex-audit-5-profiles.md:21977:- Store singleton is not reset when only `store_default_ui_set` or `store_ui_sets` change at `apps/api/src/routers/system.py:255-259`.
plans/audits/codex-audit-5-profiles.md:21996:- It calls `store.layout.pack_path()` at `src/store/api.py:3334`.
plans/audits/codex-audit-5-profiles.md:21997:- `StoreLayout` defines `pack_dir()`, not `pack_path()`, in audited code at `src/store/layout.py:169-179`.
plans/audits/codex-audit-5-profiles.md:22029:- Inventory plan models `active_in_uis` at `plans/PLAN-Model-Inventory.md:280-296`.
plans/audits/codex-audit-5-profiles.md:22046:- It may call a nonexistent `StoreLayout.pack_path()` method. NEEDS VERIFICATION.
plans/audits/codex-audit-5-profiles.md:22108:- No test covers divergence between app config UI sets and store `state/ui_sets.json`.
plans/audits/codex-audit-5-profiles.md:22120:- No test covers disabled `ProfilePackEntry.enabled`.
plans/audits/codex-audit-5-profiles.md:22145:- Settings default UI set may not affect store runtime target resolution because store uses `state/ui_sets.json`.
plans/audits/codex-audit-5-profiles.md:22181:- Should Settings write `state/config.json` and `state/ui_sets.json` for Profile defaults?
plans/audits/codex-audit-5-profiles.md:22195:- Should `ProfilePackEntry.enabled` affect view building?
plans/audits/codex-audit-5-profiles.md:22208:- Should Profile status compute shadowed entries live, cache them, or persist build reports?
plans/audits/codex-audit-2-custom-pack.md:43:   - pack_dependencies (deps on OTHER packs — implemented?)
plans/audits/codex-audit-2-custom-pack.md:948:   138	    shadowed: List[Dict[str, Any]]
plans/audits/codex-audit-2-custom-pack.md:949:   139	    shadowed_count: int
plans/audits/codex-audit-2-custom-pack.md:1154:   344	        # Store config reference for later use (e.g., ui_roots, ui_sets)
plans/audits/codex-audit-2-custom-pack.md:1241:     9	- synapse.ui_sets.v1
plans/audits/codex-audit-2-custom-pack.md:1462:   230	    conflicts_mode: ConflictMode = ConflictMode.LAST_WINS
plans/audits/codex-audit-2-custom-pack.md:1469:   237	    enabled: bool = False
plans/audits/codex-audit-2-custom-pack.md:1497:/bin/bash -lc 'rg -n "custom|PackCategory|PackSource|dependencies|pack_dependencies|parameters|workflows|create.*pack|Create.*Pack|export|import|profile|resolve|update" src/store/models.py src/store/pack_service.py src/store/api.py src/core/pack_builder.py plans/PLAN-Pack-Edit.md' in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:1585:src/store/models.py:845:    pack_dependencies: List[PackDependencyRef] = Field(default_factory=list)  # Dependencies on other packs
plans/audits/codex-audit-2-custom-pack.md:1592:src/store/models.py:905:        names = [ref.pack_name for ref in self.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:1624:src/store/models.py:1127:    """Report entry for a shadowed file (conflict resolved by last_wins)."""
plans/audits/codex-audit-2-custom-pack.md:1655:plans/PLAN-Pack-Edit.md:137:    pack_dependencies: List[PackDependencyRef]  # 🆕 Dependencies on OTHER PACKS
plans/audits/codex-audit-2-custom-pack.md:1667:plans/PLAN-Pack-Edit.md:257:- ⚠️ CHYBÍ `pack_dependencies` → nastavit na `[]` (prázdný list)
plans/audits/codex-audit-2-custom-pack.md:1734:plans/PLAN-Pack-Edit.md:1498:- [x] Přidat `pack_dependencies` field do `Pack` modelu (default: [])
plans/audits/codex-audit-2-custom-pack.md:1796:plans/PLAN-Pack-Edit.md:2529:    pack_dependencies: PackDependencyRef[]
plans/audits/codex-audit-2-custom-pack.md:1805:plans/PLAN-Pack-Edit.md:2585:- Added `pack_dependencies: List[PackDependencyRef] = []`
plans/audits/codex-audit-2-custom-pack.md:1970:src/store/pack_service.py:521:            pack_dependencies=[],  # No pack dependencies by default
plans/audits/codex-audit-2-custom-pack.md:2276:src/store/api.py:2964:def get_pack_dependencies_status(
plans/audits/codex-audit-2-custom-pack.md:2278:src/store/api.py:2976:        for ref in pack.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:2286:src/store/api.py:3051:        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
plans/audits/codex-audit-2-custom-pack.md:2287:src/store/api.py:3063:        pack.pack_dependencies.append(new_ref)
plans/audits/codex-audit-2-custom-pack.md:2289:src/store/api.py:3091:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:2290:src/store/api.py:3092:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:2291:src/store/api.py:3093:            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
plans/audits/codex-audit-2-custom-pack.md:2292:src/store/api.py:3096:        if len(pack.pack_dependencies) == original_count:
plans/audits/codex-audit-2-custom-pack.md:2295:src/store/api.py:3172:            if depth < max_depth and p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:2296:src/store/api.py:3173:                for ref in p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:2566:/bin/bash -lc 'rg -n "custom|PackCategory|create.*pack|Create.*Pack|pack_dependencies|parameters|workflows|resolve|source|provider|export|import|profile|update" apps/web/src/components/modules/PacksPage.tsx apps/web/src/components/modules/PackDetailPage.tsx apps/web/src/components/modules/pack-detail/plugins/CustomPlugin.tsx apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx apps/web/src/components/modules/pack-detail/hooks/usePackData.ts apps/web/src/components/modules/pack-detail/hooks/usePackEdit.ts apps/web/src/components/modules/pack-detail/sections' in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:2891:apps/web/src/components/modules/pack-detail/sections/PackDepsSection.tsx:423:  const packDependencies: PackDependencyRef[] = pack.pack?.pack_dependencies ?? []
plans/audits/codex-audit-2-custom-pack.md:2968:apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:179:  if (typeof value === 'boolean') return value ? (translate?.('pack.parameters.enabled') ?? 'Enabled') : (translate?.('pack.parameters.disabled') ?? 'Disabled')
plans/audits/codex-audit-2-custom-pack.md:3168:   137	    pack_dependencies: List[PackDependencyRef]  # 🆕 Dependencies on OTHER PACKS
plans/audits/codex-audit-2-custom-pack.md:3288:   257	- ⚠️ CHYBÍ `pack_dependencies` → nastavit na `[]` (prázdný list)
plans/audits/codex-audit-2-custom-pack.md:3303:tests/store/test_pack_dependencies.py
plans/audits/codex-audit-2-custom-pack.md:3441:   845	    pack_dependencies: List[PackDependencyRef] = Field(default_factory=list)  # Dependencies on other packs
plans/audits/codex-audit-2-custom-pack.md:3501:   905	        names = [ref.pack_name for ref in self.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:3622:  1021	    conflicts: ConflictConfig = Field(default_factory=ConflictConfig)
plans/audits/codex-audit-2-custom-pack.md:3748:  2964	def get_pack_dependencies_status(
plans/audits/codex-audit-2-custom-pack.md:3760:  2976	        for ref in pack.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:3835:  3051	        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
plans/audits/codex-audit-2-custom-pack.md:3847:  3063	        pack.pack_dependencies.append(new_ref)
plans/audits/codex-audit-2-custom-pack.md:3875:  3091	        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:3876:  3092	        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:3877:  3093	            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
plans/audits/codex-audit-2-custom-pack.md:3880:  3096	        if len(pack.pack_dependencies) == original_count:
plans/audits/codex-audit-2-custom-pack.md:3956:  3172	            if depth < max_depth and p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:3957:  3173	                for ref in p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:4118:  3334	        pack_path = store.layout.pack_path(request.name)
plans/audits/codex-audit-2-custom-pack.md:4213:  3424	            old_path = store.layout.pack_path(pack_name)
plans/audits/codex-audit-2-custom-pack.md:4872:  4078	        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-2-custom-pack.md:5380:  4581	        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-2-custom-pack.md:5401:  4602	            # Create symlink with pack prefix to avoid conflicts
plans/audits/codex-audit-2-custom-pack.md:5538:  4739	        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-2-custom-pack.md:5589:  4790	        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-2-custom-pack.md:5658:  4859	        pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-2-custom-pack.md:5757:  4958	            pack_dir = store.layout.pack_path(pack_name)
plans/audits/codex-audit-2-custom-pack.md:5833:  5019	    Returns per-UI runtime status, stack visualization, and shadowed files.
plans/audits/codex-audit-2-custom-pack.md:5853:  5039	        # Get status for shadowed info
plans/audits/codex-audit-2-custom-pack.md:5856:  5042	        # Convert shadowed entries to dicts
plans/audits/codex-audit-2-custom-pack.md:5857:  5043	        all_shadowed = []
plans/audits/codex-audit-2-custom-pack.md:5858:  5044	        for entry in status.shadowed:
plans/audits/codex-audit-2-custom-pack.md:5859:  5045	            all_shadowed.append({
plans/audits/codex-audit-2-custom-pack.md:5871:  5057	            shadowed=all_shadowed,
plans/audits/codex-audit-2-custom-pack.md:5872:  5058	            shadowed_count=len(all_shadowed),
plans/audits/codex-audit-2-custom-pack.md:5927:  5113	                "shadowed_count": len(r.shadowed),
plans/audits/codex-audit-2-custom-pack.md:6237:2964:def get_pack_dependencies_status(
plans/audits/codex-audit-2-custom-pack.md:6239:2976:        for ref in pack.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:6247:3051:        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
plans/audits/codex-audit-2-custom-pack.md:6248:3063:        pack.pack_dependencies.append(new_ref)
plans/audits/codex-audit-2-custom-pack.md:6250:3091:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:6251:3092:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:6252:3093:            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
plans/audits/codex-audit-2-custom-pack.md:6253:3096:        if len(pack.pack_dependencies) == original_count:
plans/audits/codex-audit-2-custom-pack.md:6257:3172:            if depth < max_depth and p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:6258:3173:                for ref in p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:7199:src/store/inventory_service.py:454:                enabled=backup_status.enabled,
plans/audits/codex-audit-2-custom-pack.md:7536:src/store/cli.py:1960:                output_error("Backup not enabled. Configure with: synapse backup config --enable --path /path")
plans/audits/codex-audit-2-custom-pack.md:7817:src/store/backup_service.py:246:        """Quick check if backup is enabled in config."""
plans/audits/codex-audit-2-custom-pack.md:7820:src/store/backup_service.py:257:            logger.warning("[Backup] Operation failed: backup not enabled")
plans/audits/codex-audit-2-custom-pack.md:8036:src/store/api.py:983:    Returns 400 if backup not enabled, 503 if not connected,
plans/audits/codex-audit-2-custom-pack.md:8042:src/store/api.py:1012:    Returns 400 if backup not enabled, 503 if not connected,
plans/audits/codex-audit-2-custom-pack.md:8067:src/store/api.py:1148:    Returns 400 if backup not enabled, 503 if not connected,
plans/audits/codex-audit-2-custom-pack.md:8072:src/store/api.py:1194:    Returns 400 if backup not enabled, 503 if not connected,
plans/audits/codex-audit-2-custom-pack.md:8079:src/store/api.py:1247:    backup_enabled = backup_status.enabled
plans/audits/codex-audit-2-custom-pack.md:8081:src/store/api.py:1250:    logger.info(f"[pack-status] Called for pack: {pack_name}, backup_enabled={backup_enabled}, backup_connected={backup_connected}")
plans/audits/codex-audit-2-custom-pack.md:8082:src/store/api.py:1259:                "backup_enabled": backup_enabled,
plans/audits/codex-audit-2-custom-pack.md:8092:src/store/api.py:1323:            "backup_enabled": backup_enabled,
plans/audits/codex-audit-2-custom-pack.md:8096:src/store/api.py:1354:            "enabled": store.backup_service.config.enabled,
plans/audits/codex-audit-2-custom-pack.md:8241:/bin/bash -lc "rg -n \"class Store|def use\\(|def sync\\(|def install|def update|check_updates|profile|rebuild|view|symlink|pack_dependencies|resolve_pack\" src/store -g '*.py'" in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:8278:src/store/pack_service.py:521:            pack_dependencies=[],  # No pack dependencies by default
plans/audits/codex-audit-2-custom-pack.md:8473:src/store/models.py:845:    pack_dependencies: List[PackDependencyRef] = Field(default_factory=list)  # Dependencies on other packs
plans/audits/codex-audit-2-custom-pack.md:8480:src/store/models.py:905:        names = [ref.pack_name for ref in self.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:8960:src/store/api.py:2964:def get_pack_dependencies_status(
plans/audits/codex-audit-2-custom-pack.md:8961:src/store/api.py:2976:        for ref in pack.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:8962:src/store/api.py:3051:        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
plans/audits/codex-audit-2-custom-pack.md:8963:src/store/api.py:3063:        pack.pack_dependencies.append(new_ref)
plans/audits/codex-audit-2-custom-pack.md:8964:src/store/api.py:3091:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:8965:src/store/api.py:3092:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:8966:src/store/api.py:3093:            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
plans/audits/codex-audit-2-custom-pack.md:8967:src/store/api.py:3096:        if len(pack.pack_dependencies) == original_count:
plans/audits/codex-audit-2-custom-pack.md:8968:src/store/api.py:3172:            if depth < max_depth and p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:8969:src/store/api.py:3173:                for ref in p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:9112:src/store/api.py:4602:            # Create symlink with pack prefix to avoid conflicts
plans/audits/codex-audit-2-custom-pack.md:9293:src/store/__init__.py:951:        # Get shadowed entries (would need to compute view plan for accurate info)
plans/audits/codex-audit-2-custom-pack.md:9327:src/store/update_service.py:258:        Find all packs that depend on the given pack via pack_dependencies.
plans/audits/codex-audit-2-custom-pack.md:9328:src/store/update_service.py:261:            List of pack names that have pack_name in their pack_dependencies.
plans/audits/codex-audit-2-custom-pack.md:9329:src/store/update_service.py:269:                dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:9443:   521	            pack_dependencies=[],  # No pack dependencies by default
plans/audits/codex-audit-2-custom-pack.md:10783:   258	        Find all packs that depend on the given pack via pack_dependencies.
plans/audits/codex-audit-2-custom-pack.md:10786:   261	            List of pack names that have pack_name in their pack_dependencies.
plans/audits/codex-audit-2-custom-pack.md:10794:   269	                dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:11466:   410	        ui_sets = self.layout.load_ui_sets()
plans/audits/codex-audit-2-custom-pack.md:11467:   411	        ui_targets = ui_sets.sets.get(ui_set_name, [])
plans/audits/codex-audit-2-custom-pack.md:11603:   130	            conflicts=base.conflicts,
plans/audits/codex-audit-2-custom-pack.md:11635:   162	            conflicts=base.conflicts,
plans/audits/codex-audit-2-custom-pack.md:11695:   222	            shadowed=[],
plans/audits/codex-audit-2-custom-pack.md:11716:   243	                result.shadowed.extend(report.shadowed)
plans/audits/codex-audit-2-custom-pack.md:11805:    68	    shadowed: List[ShadowedEntry] = field(default_factory=list)
plans/audits/codex-audit-2-custom-pack.md:11832:    95	                shadowed = ShadowedEntry(
plans/audits/codex-audit-2-custom-pack.md:11838:   101	                self.shadowed.append(shadowed)
plans/audits/codex-audit-2-custom-pack.md:11849:   112	                return shadowed
plans/audits/codex-audit-2-custom-pack.md:11869:   132	    shadowed: List[ShadowedEntry] = field(default_factory=list)
plans/audits/codex-audit-2-custom-pack.md:11964:   227	            ViewPlan with entries and shadowed info
plans/audits/codex-audit-2-custom-pack.md:12020:/bin/bash -lc 'rg -n "pack_dependencies|dependencies|lock|resolved|symlink|expose|missing" src/store/view_builder.py src/store/profile_service.py' in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:12169:   304	            shadowed=plan.shadowed,
plans/audits/codex-audit-2-custom-pack.md:12546:   136	    // Hide nsfw-pack-hide packs when blur is enabled
plans/audits/codex-audit-2-custom-pack.md:13071:   177	    enabled: modals.baseModelResolver,
plans/audits/codex-audit-2-custom-pack.md:13095:   201	    enabled:
plans/audits/codex-audit-2-custom-pack.md:14100:    80	    enabled: false, // Manual trigger only
plans/audits/codex-audit-2-custom-pack.md:14535:   113	   * What features are enabled for this plugin?
plans/audits/codex-audit-2-custom-pack.md:15246:   158	    enabled: !!packName,
plans/audits/codex-audit-2-custom-pack.md:15264:   176	          backup_enabled: false,
plans/audits/codex-audit-2-custom-pack.md:15272:   184	    enabled: !!packName,
plans/audits/codex-audit-2-custom-pack.md:16496:   423	  const packDependencies: PackDependencyRef[] = pack.pack?.pack_dependencies ?? []
plans/audits/codex-audit-2-custom-pack.md:16520:   447	    enabled: packDependencies.length > 0,
plans/audits/codex-audit-2-custom-pack.md:16828:    71	    enabled: isOpen,
plans/audits/codex-audit-2-custom-pack.md:18784:src/store/api.py:2964:def get_pack_dependencies_status(
plans/audits/codex-audit-2-custom-pack.md:18786:src/store/api.py:2976:        for ref in pack.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:18790:src/store/api.py:3051:        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
plans/audits/codex-audit-2-custom-pack.md:18791:src/store/api.py:3063:        pack.pack_dependencies.append(new_ref)
plans/audits/codex-audit-2-custom-pack.md:18793:src/store/api.py:3091:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:18794:src/store/api.py:3092:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:18795:src/store/api.py:3093:            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
plans/audits/codex-audit-2-custom-pack.md:18796:src/store/api.py:3096:        if len(pack.pack_dependencies) == original_count:
plans/audits/codex-audit-2-custom-pack.md:18799:src/store/api.py:3172:            if depth < max_depth and p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:18800:src/store/api.py:3173:                for ref in p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:19358:/bin/bash -lc "nl -ba tests/store/test_pack_dependencies.py | sed -n '1,280p'" in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:19389:    30	        """Create a minimal Pack with pack_dependencies."""
plans/audits/codex-audit-2-custom-pack.md:19395:    36	            pack_dependencies=pack_deps or [],
plans/audits/codex-audit-2-custom-pack.md:19398:    39	    def test_empty_pack_dependencies(self):
plans/audits/codex-audit-2-custom-pack.md:19401:    42	        assert len(pack.pack_dependencies) == 0
plans/audits/codex-audit-2-custom-pack.md:19408:    49	        assert len(pack.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:19409:    50	        assert pack.pack_dependencies[0].pack_name == "base-model"
plans/audits/codex-audit-2-custom-pack.md:19418:    59	        assert len(pack.pack_dependencies) == 3
plans/audits/codex-audit-2-custom-pack.md:19461:   102	            pack_dependencies=pack_deps or [],
plans/audits/codex-audit-2-custom-pack.md:19467:   108	        assert len(pack.pack_dependencies) == 0
plans/audits/codex-audit-2-custom-pack.md:19470:   111	        pack.pack_dependencies.append(new_ref)
plans/audits/codex-audit-2-custom-pack.md:19472:   113	        assert len(pack.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:19473:   114	        assert pack.pack_dependencies[0].pack_name == "checkpoint-pack"
plans/audits/codex-audit-2-custom-pack.md:19474:   115	        assert pack.pack_dependencies[0].required is True
plans/audits/codex-audit-2-custom-pack.md:19480:   121	        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-a"))
plans/audits/codex-audit-2-custom-pack.md:19481:   122	        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-b", required=False))
plans/audits/codex-audit-2-custom-pack.md:19483:   124	        assert len(pack.pack_dependencies) == 2
plans/audits/codex-audit-2-custom-pack.md:19484:   125	        assert pack.pack_dependencies[0].pack_name == "dep-a"
plans/audits/codex-audit-2-custom-pack.md:19485:   126	        assert pack.pack_dependencies[1].required is False
plans/audits/codex-audit-2-custom-pack.md:19494:   135	        assert len(pack.pack_dependencies) == 3
plans/audits/codex-audit-2-custom-pack.md:19498:   139	        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:19499:   140	        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:19500:   141	            ref for ref in pack.pack_dependencies if ref.pack_name != dep_to_remove
plans/audits/codex-audit-2-custom-pack.md:19503:   144	        assert len(pack.pack_dependencies) == 2
plans/audits/codex-audit-2-custom-pack.md:19504:   145	        assert len(pack.pack_dependencies) < original_count
plans/audits/codex-audit-2-custom-pack.md:19505:   146	        remaining_names = [ref.pack_name for ref in pack.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:19516:   157	        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:19517:   158	        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:19518:   159	            ref for ref in pack.pack_dependencies if ref.pack_name != "nonexistent"
plans/audits/codex-audit-2-custom-pack.md:19521:   162	        assert len(pack.pack_dependencies) == original_count  # unchanged
plans/audits/codex-audit-2-custom-pack.md:19528:   169	        pack.pack_dependencies.append(PackDependencyRef(pack_name="my-pack"))
plans/audits/codex-audit-2-custom-pack.md:19537:   178	        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-a"))
plans/audits/codex-audit-2-custom-pack.md:19538:   179	        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-a"))
plans/audits/codex-audit-2-custom-pack.md:19586:   227	        assert pack.pack_dependencies[0].version_constraint == ">=1.0.0"
plans/audits/codex-audit-2-custom-pack.md:19608:   249	    def test_save_load_pack_dependencies(self, tmp_path):
plans/audits/codex-audit-2-custom-pack.md:19618:   259	            pack_dependencies=[
plans/audits/codex-audit-2-custom-pack.md:19627:   268	        assert len(loaded.pack_dependencies) == 2
plans/audits/codex-audit-2-custom-pack.md:19628:   269	        assert loaded.pack_dependencies[0].pack_name == "base-model"
plans/audits/codex-audit-2-custom-pack.md:19629:   270	        assert loaded.pack_dependencies[0].required is True
plans/audits/codex-audit-2-custom-pack.md:19630:   271	        assert loaded.pack_dependencies[1].pack_name == "optional-dep"
plans/audits/codex-audit-2-custom-pack.md:19631:   272	        assert loaded.pack_dependencies[1].required is False
plans/audits/codex-audit-2-custom-pack.md:19684:    41	            assert len(plan.shadowed) == 0
plans/audits/codex-audit-2-custom-pack.md:19835:   192	            # Should have one shadowed entry
plans/audits/codex-audit-2-custom-pack.md:19836:   193	            assert len(plan.shadowed) == 1
plans/audits/codex-audit-2-custom-pack.md:19837:   194	            assert plan.shadowed[0].winner_pack == "Pack2"
plans/audits/codex-audit-2-custom-pack.md:19838:   195	            assert plan.shadowed[0].loser_pack == "Pack1"
plans/audits/codex-audit-2-custom-pack.md:19989:    62	    pack_dependencies?: PackDependencyRef[]
plans/audits/codex-audit-2-custom-pack.md:20534:/bin/bash -lc "nl -ba tests/store/test_pack_dependencies.py | sed -n '280,620p'" in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:20545:   289	        pack.pack_dependencies.append(PackDependencyRef(pack_name="some-lora"))
plans/audits/codex-audit-2-custom-pack.md:20550:   294	        assert len(pack.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:20553:   297	        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:20554:   298	            ref for ref in pack.pack_dependencies if ref.pack_name != "some-lora"
plans/audits/codex-audit-2-custom-pack.md:20560:   304	        assert len(pack.pack_dependencies) == 0
plans/audits/codex-audit-2-custom-pack.md:23441:/bin/bash -lc 'rg -n "pack_dependencies|PackDependencyRef|dependency-tree|pack-dependencies|work__|compute_plan" tests/store tests/e2e tests/unit/store' in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:23452:   257	- ⚠️ CHYBÍ `pack_dependencies` → nastavit na `[]` (prázdný list)
plans/audits/codex-audit-2-custom-pack.md:23556:tests/store/test_dependencies_integration.py:91:        pack_dependencies=pack_deps or [],
plans/audits/codex-audit-2-custom-pack.md:23557:tests/store/test_dependencies_integration.py:240:        pack.pack_dependencies.append(
plans/audits/codex-audit-2-custom-pack.md:23559:tests/store/test_dependencies_integration.py:247:        assert len(loaded.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:23560:tests/store/test_dependencies_integration.py:248:        assert loaded.pack_dependencies[0].pack_name == "provider"
plans/audits/codex-audit-2-custom-pack.md:23561:tests/store/test_dependencies_integration.py:249:        assert loaded.pack_dependencies[0].required is True
plans/audits/codex-audit-2-custom-pack.md:23564:tests/store/test_dependencies_integration.py:265:        loaded.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:23565:tests/store/test_dependencies_integration.py:266:            ref for ref in loaded.pack_dependencies if ref.pack_name != "dep-a"
plans/audits/codex-audit-2-custom-pack.md:23566:tests/store/test_dependencies_integration.py:272:        assert len(result.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:23567:tests/store/test_dependencies_integration.py:273:        assert result.pack_dependencies[0].pack_name == "dep-b"
plans/audits/codex-audit-2-custom-pack.md:23570:tests/store/test_dependencies_integration.py:291:        for ref in loaded.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23571:tests/store/test_dependencies_integration.py:324:        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-pack"))
plans/audits/codex-audit-2-custom-pack.md:23572:tests/store/test_dependencies_integration.py:326:        assert len(store.get_pack("main-pack").pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:23573:tests/store/test_dependencies_integration.py:330:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:23574:tests/store/test_dependencies_integration.py:331:            r for r in pack.pack_dependencies if r.pack_name != "dep-pack"
plans/audits/codex-audit-2-custom-pack.md:23575:tests/store/test_dependencies_integration.py:334:        assert len(store.get_pack("main-pack").pack_dependencies) == 0
plans/audits/codex-audit-2-custom-pack.md:23576:tests/store/test_dependencies_integration.py:338:        pack.pack_dependencies.append(
plans/audits/codex-audit-2-custom-pack.md:23578:tests/store/test_dependencies_integration.py:343:        assert len(result.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:23579:tests/store/test_dependencies_integration.py:344:        assert result.pack_dependencies[0].required is False
plans/audits/codex-audit-2-custom-pack.md:23582:tests/store/test_dependencies_integration.py:360:        assert a.pack_dependencies[0].pack_name == "shared-base"
plans/audits/codex-audit-2-custom-pack.md:23583:tests/store/test_dependencies_integration.py:361:        assert b.pack_dependencies[0].pack_name == "shared-base"
plans/audits/codex-audit-2-custom-pack.md:23585:tests/store/test_dependencies_integration.py:486:        existing_names = {ref.pack_name for ref in loaded.pack_dependencies}
plans/audits/codex-audit-2-custom-pack.md:23586:tests/store/test_dependencies_integration.py:498:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:23587:tests/store/test_dependencies_integration.py:499:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:23588:tests/store/test_dependencies_integration.py:500:            ref for ref in pack.pack_dependencies if ref.pack_name != "nonexistent"
plans/audits/codex-audit-2-custom-pack.md:23589:tests/store/test_dependencies_integration.py:503:        assert len(pack.pack_dependencies) == original_count
plans/audits/codex-audit-2-custom-pack.md:23591:tests/store/test_dependencies_integration.py:517:        for ref in loaded.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23592:tests/store/test_dependencies_integration.py:560:        existing = {ref.pack_name for ref in pack.pack_dependencies}
plans/audits/codex-audit-2-custom-pack.md:23593:tests/store/test_dependencies_integration.py:564:        pack.pack_dependencies.append(
plans/audits/codex-audit-2-custom-pack.md:23595:tests/store/test_dependencies_integration.py:571:        assert len(result.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:23596:tests/store/test_dependencies_integration.py:572:        assert result.pack_dependencies[0].pack_name == "new-dep"
plans/audits/codex-audit-2-custom-pack.md:23599:tests/store/test_dependencies_integration.py:589:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:23600:tests/store/test_dependencies_integration.py:590:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:23601:tests/store/test_dependencies_integration.py:591:            ref for ref in pack.pack_dependencies if ref.pack_name != dep_to_remove
plans/audits/codex-audit-2-custom-pack.md:23602:tests/store/test_dependencies_integration.py:593:        assert len(pack.pack_dependencies) < original_count  # found and removed
plans/audits/codex-audit-2-custom-pack.md:23603:tests/store/test_dependencies_integration.py:598:        names = [ref.pack_name for ref in result.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:23605:tests/store/test_dependencies_integration.py:643:        for ref in loaded.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23607:tests/store/test_dependencies_integration.py:677:        for ref in loaded.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23609:tests/store/test_dependencies_integration.py:807:            if depth < 5 and p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23610:tests/store/test_dependencies_integration.py:808:                for ref in p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23613:tests/store/test_dependencies_integration.py:858:            if depth < 5 and p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23614:tests/store/test_dependencies_integration.py:859:                for ref in p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23616:tests/store/test_dependencies_integration.py:900:        ref = loaded.pack_dependencies[0]
plans/audits/codex-audit-2-custom-pack.md:23628:tests/store/test_update_options.py:821:        parent_pack.pack_dependencies = [MagicMock(pack_name="child-pack")]
plans/audits/codex-audit-2-custom-pack.md:23629:tests/store/test_update_options.py:824:        child_pack.pack_dependencies = []
plans/audits/codex-audit-2-custom-pack.md:23630:tests/store/test_update_options.py:844:        pack_a.pack_dependencies = []
plans/audits/codex-audit-2-custom-pack.md:23631:tests/store/test_update_options.py:846:        pack_b.pack_dependencies = []
plans/audits/codex-audit-2-custom-pack.md:23632:tests/store/test_update_options.py:867:            MagicMock(pack_dependencies=[]),
plans/audits/codex-audit-2-custom-pack.md:23634:tests/store/test_update_impact.py:140:        """Create a pack with given pack_dependencies."""
plans/audits/codex-audit-2-custom-pack.md:23635:tests/store/test_update_impact.py:146:            pack_dependencies=[
plans/audits/codex-audit-2-custom-pack.md:23637:tests/store/test_update_impact.py:252:            pack_dependencies=[
plans/audits/codex-audit-2-custom-pack.md:23639:tests/store/test_pack_dependencies.py:15:    PackDependencyRef,
plans/audits/codex-audit-2-custom-pack.md:23640:tests/store/test_pack_dependencies.py:30:        """Create a minimal Pack with pack_dependencies."""
plans/audits/codex-audit-2-custom-pack.md:23641:tests/store/test_pack_dependencies.py:36:            pack_dependencies=pack_deps or [],
plans/audits/codex-audit-2-custom-pack.md:23642:tests/store/test_pack_dependencies.py:39:    def test_empty_pack_dependencies(self):
plans/audits/codex-audit-2-custom-pack.md:23643:tests/store/test_pack_dependencies.py:42:        assert len(pack.pack_dependencies) == 0
plans/audits/codex-audit-2-custom-pack.md:23644:tests/store/test_pack_dependencies.py:47:            PackDependencyRef(pack_name="base-model"),
plans/audits/codex-audit-2-custom-pack.md:23645:tests/store/test_pack_dependencies.py:49:        assert len(pack.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:23646:tests/store/test_pack_dependencies.py:50:        assert pack.pack_dependencies[0].pack_name == "base-model"
plans/audits/codex-audit-2-custom-pack.md:23647:tests/store/test_pack_dependencies.py:55:            PackDependencyRef(pack_name="dep-a"),
plans/audits/codex-audit-2-custom-pack.md:23648:tests/store/test_pack_dependencies.py:56:            PackDependencyRef(pack_name="dep-b"),
plans/audits/codex-audit-2-custom-pack.md:23649:tests/store/test_pack_dependencies.py:57:            PackDependencyRef(pack_name="dep-c"),
plans/audits/codex-audit-2-custom-pack.md:23650:tests/store/test_pack_dependencies.py:59:        assert len(pack.pack_dependencies) == 3
plans/audits/codex-audit-2-custom-pack.md:23651:tests/store/test_pack_dependencies.py:65:                PackDependencyRef(pack_name="dep-a"),
plans/audits/codex-audit-2-custom-pack.md:23652:tests/store/test_pack_dependencies.py:66:                PackDependencyRef(pack_name="dep-a"),
plans/audits/codex-audit-2-custom-pack.md:23653:tests/store/test_pack_dependencies.py:73:                PackDependencyRef(pack_name="my-pack"),
plans/audits/codex-audit-2-custom-pack.md:23654:tests/store/test_pack_dependencies.py:77:        """PackDependencyRef.required defaults to True."""
plans/audits/codex-audit-2-custom-pack.md:23655:tests/store/test_pack_dependencies.py:78:        ref = PackDependencyRef(pack_name="some-dep")
plans/audits/codex-audit-2-custom-pack.md:23656:tests/store/test_pack_dependencies.py:82:        """PackDependencyRef.required can be set to False."""
plans/audits/codex-audit-2-custom-pack.md:23657:tests/store/test_pack_dependencies.py:83:        ref = PackDependencyRef(pack_name="some-dep", required=False)
plans/audits/codex-audit-2-custom-pack.md:23658:tests/store/test_pack_dependencies.py:102:            pack_dependencies=pack_deps or [],
plans/audits/codex-audit-2-custom-pack.md:23659:tests/store/test_pack_dependencies.py:108:        assert len(pack.pack_dependencies) == 0
plans/audits/codex-audit-2-custom-pack.md:23660:tests/store/test_pack_dependencies.py:110:        new_ref = PackDependencyRef(pack_name="checkpoint-pack", required=True)
plans/audits/codex-audit-2-custom-pack.md:23661:tests/store/test_pack_dependencies.py:111:        pack.pack_dependencies.append(new_ref)
plans/audits/codex-audit-2-custom-pack.md:23662:tests/store/test_pack_dependencies.py:113:        assert len(pack.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:23663:tests/store/test_pack_dependencies.py:114:        assert pack.pack_dependencies[0].pack_name == "checkpoint-pack"
plans/audits/codex-audit-2-custom-pack.md:23664:tests/store/test_pack_dependencies.py:115:        assert pack.pack_dependencies[0].required is True
plans/audits/codex-audit-2-custom-pack.md:23665:tests/store/test_pack_dependencies.py:121:        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-a"))
plans/audits/codex-audit-2-custom-pack.md:23666:tests/store/test_pack_dependencies.py:122:        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-b", required=False))
plans/audits/codex-audit-2-custom-pack.md:23667:tests/store/test_pack_dependencies.py:124:        assert len(pack.pack_dependencies) == 2
plans/audits/codex-audit-2-custom-pack.md:23668:tests/store/test_pack_dependencies.py:125:        assert pack.pack_dependencies[0].pack_name == "dep-a"
plans/audits/codex-audit-2-custom-pack.md:23669:tests/store/test_pack_dependencies.py:126:        assert pack.pack_dependencies[1].required is False
plans/audits/codex-audit-2-custom-pack.md:23670:tests/store/test_pack_dependencies.py:131:            PackDependencyRef(pack_name="dep-a"),
plans/audits/codex-audit-2-custom-pack.md:23671:tests/store/test_pack_dependencies.py:132:            PackDependencyRef(pack_name="dep-b"),
plans/audits/codex-audit-2-custom-pack.md:23672:tests/store/test_pack_dependencies.py:133:            PackDependencyRef(pack_name="dep-c"),
plans/audits/codex-audit-2-custom-pack.md:23673:tests/store/test_pack_dependencies.py:135:        assert len(pack.pack_dependencies) == 3
plans/audits/codex-audit-2-custom-pack.md:23674:tests/store/test_pack_dependencies.py:139:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:23675:tests/store/test_pack_dependencies.py:140:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:23676:tests/store/test_pack_dependencies.py:141:            ref for ref in pack.pack_dependencies if ref.pack_name != dep_to_remove
plans/audits/codex-audit-2-custom-pack.md:23677:tests/store/test_pack_dependencies.py:144:        assert len(pack.pack_dependencies) == 2
plans/audits/codex-audit-2-custom-pack.md:23678:tests/store/test_pack_dependencies.py:145:        assert len(pack.pack_dependencies) < original_count
plans/audits/codex-audit-2-custom-pack.md:23679:tests/store/test_pack_dependencies.py:146:        remaining_names = [ref.pack_name for ref in pack.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:23680:tests/store/test_pack_dependencies.py:154:            PackDependencyRef(pack_name="dep-a"),
plans/audits/codex-audit-2-custom-pack.md:23681:tests/store/test_pack_dependencies.py:157:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:23682:tests/store/test_pack_dependencies.py:158:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:23683:tests/store/test_pack_dependencies.py:159:            ref for ref in pack.pack_dependencies if ref.pack_name != "nonexistent"
plans/audits/codex-audit-2-custom-pack.md:23684:tests/store/test_pack_dependencies.py:162:        assert len(pack.pack_dependencies) == original_count  # unchanged
plans/audits/codex-audit-2-custom-pack.md:23685:tests/store/test_pack_dependencies.py:169:        pack.pack_dependencies.append(PackDependencyRef(pack_name="my-pack"))
plans/audits/codex-audit-2-custom-pack.md:23686:tests/store/test_pack_dependencies.py:178:        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-a"))
plans/audits/codex-audit-2-custom-pack.md:23687:tests/store/test_pack_dependencies.py:179:        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-a"))
plans/audits/codex-audit-2-custom-pack.md:23688:tests/store/test_pack_dependencies.py:187:        ref = PackDependencyRef(pack_name="installed-pack", required=True)
plans/audits/codex-audit-2-custom-pack.md:23689:tests/store/test_pack_dependencies.py:203:        ref = PackDependencyRef(pack_name="missing-pack", required=False)
plans/audits/codex-audit-2-custom-pack.md:23690:tests/store/test_pack_dependencies.py:219:        ref = PackDependencyRef(
plans/audits/codex-audit-2-custom-pack.md:23691:tests/store/test_pack_dependencies.py:227:        assert pack.pack_dependencies[0].version_constraint == ">=1.0.0"
plans/audits/codex-audit-2-custom-pack.md:23692:tests/store/test_pack_dependencies.py:249:    def test_save_load_pack_dependencies(self, tmp_path):
plans/audits/codex-audit-2-custom-pack.md:23693:tests/store/test_pack_dependencies.py:259:            pack_dependencies=[
plans/audits/codex-audit-2-custom-pack.md:23694:tests/store/test_pack_dependencies.py:260:                PackDependencyRef(pack_name="base-model", required=True),
plans/audits/codex-audit-2-custom-pack.md:23695:tests/store/test_pack_dependencies.py:261:                PackDependencyRef(pack_name="optional-dep", required=False),
plans/audits/codex-audit-2-custom-pack.md:23696:tests/store/test_pack_dependencies.py:268:        assert len(loaded.pack_dependencies) == 2
plans/audits/codex-audit-2-custom-pack.md:23697:tests/store/test_pack_dependencies.py:269:        assert loaded.pack_dependencies[0].pack_name == "base-model"
plans/audits/codex-audit-2-custom-pack.md:23698:tests/store/test_pack_dependencies.py:270:        assert loaded.pack_dependencies[0].required is True
plans/audits/codex-audit-2-custom-pack.md:23699:tests/store/test_pack_dependencies.py:271:        assert loaded.pack_dependencies[1].pack_name == "optional-dep"
plans/audits/codex-audit-2-custom-pack.md:23700:tests/store/test_pack_dependencies.py:272:        assert loaded.pack_dependencies[1].required is False
plans/audits/codex-audit-2-custom-pack.md:23701:tests/store/test_pack_dependencies.py:289:        pack.pack_dependencies.append(PackDependencyRef(pack_name="some-lora"))
plans/audits/codex-audit-2-custom-pack.md:23702:tests/store/test_pack_dependencies.py:294:        assert len(pack.pack_dependencies) == 1
plans/audits/codex-audit-2-custom-pack.md:23703:tests/store/test_pack_dependencies.py:297:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:23704:tests/store/test_pack_dependencies.py:298:            ref for ref in pack.pack_dependencies if ref.pack_name != "some-lora"
plans/audits/codex-audit-2-custom-pack.md:23705:tests/store/test_pack_dependencies.py:304:        assert len(pack.pack_dependencies) == 0
plans/audits/codex-audit-2-custom-pack.md:23771:tests/store/test_update_e2e.py:911:        pack-child depends on pack-parent via pack_dependencies.
plans/audits/codex-audit-2-custom-pack.md:23772:tests/store/test_update_e2e.py:920:            pack_dependencies=[PackDependencyRef(pack_name="pack-parent")],
plans/audits/codex-audit-2-custom-pack.md:23775:tests/store/test_dependency_tree.py:60:        pack_dependencies=pack_deps or [],
plans/audits/codex-audit-2-custom-pack.md:23776:tests/store/test_dependency_tree.py:134:        if depth < max_depth and p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23777:tests/store/test_dependency_tree.py:135:            for ref in p.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23778:tests/store/test_dependency_tree.py:157:    Mirrors the logic in api.py get_pack_dependencies_status().
plans/audits/codex-audit-2-custom-pack.md:23779:tests/store/test_dependency_tree.py:161:    for ref in pack.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:23798:tests/store/test_dependency_tree.py:346:        # pack-b has pack_dependencies but depth == max_depth so no recursion
plans/audits/codex-audit-2-custom-pack.md:23819:  1498	- [x] Přidat `pack_dependencies` field do `Pack` modelu (default: [])
plans/audits/codex-audit-2-custom-pack.md:24217:    91	        pack_dependencies=pack_deps or [],
plans/audits/codex-audit-2-custom-pack.md:24477:   346	        # pack-b has pack_dependencies but depth == max_depth so no recursion
plans/audits/codex-audit-2-custom-pack.md:25382:/bin/bash -lc "rg -n \"@v2_packs_router\\.(get|patch|post|delete)\\(\\\"/(parameters|previews|workflow|workflows|pack-dependencies|dependency-tree|dependencies|resolve-base-model|resolve\\\"|pack\\.dependencies|pack\\.pack_dependencies|PackDependencyRef|delete_dependency|append|version_constraint\" src/store/api.py" in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:25385:    (?:@v2_packs_router\.(get|patch|post|delete)\("/(parameters|previews|workflow|workflows|pack-dependencies|dependency-tree|dependencies|resolve-base-model|resolve"|pack\.dependencies|pack\.pack_dependencies|PackDependencyRef|delete_dependency|append|version_constraint)
plans/audits/codex-audit-2-custom-pack.md:25390:/bin/bash -lc "rg -n \"pack-dependencies|dependency-tree|PackDependencyRef|pack\\.pack_dependencies|version_constraint|target pack|append\\(dep_ref\" src/store/api.py" in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:25394:2976:        for ref in pack.pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:25396:3051:        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
plans/audits/codex-audit-2-custom-pack.md:25398:3063:        pack.pack_dependencies.append(new_ref)
plans/audits/codex-audit-2-custom-pack.md:25400:3091:        original_count = len(pack.pack_dependencies)
plans/audits/codex-audit-2-custom-pack.md:25401:3092:        pack.pack_dependencies = [
plans/audits/codex-audit-2-custom-pack.md:25402:3093:            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
plans/audits/codex-audit-2-custom-pack.md:25403:3096:        if len(pack.pack_dependencies) == original_count:
plans/audits/codex-audit-2-custom-pack.md:25903:   845	    pack_dependencies: List[PackDependencyRef] = Field(default_factory=list)  # Dependencies on other packs
plans/audits/codex-audit-2-custom-pack.md:25963:   905	        names = [ref.pack_name for ref in self.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:26629:/bin/bash -lc "rg -n \"ensure_work_profile|update_work_profile|_load_packs_for_profile|_install_missing_blobs|pack_dependencies|ProfilePackEntry|use\\(\" src/store/profile_service.py" in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:26651:/bin/bash -lc "rg -n \"compute_plan|profile\\.packs|pack_dependencies|symlink_to|kind_path|entries|LAST_WINS\" src/store/view_builder.py" in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:26666:227:            ViewPlan with entries and shadowed info
plans/audits/codex-audit-2-custom-pack.md:26680:/bin/bash -lc 'rg -n "UPDATABLE_STRATEGIES|is_updatable|pack_category|pack_dependencies|plan_update|_find_reverse_dependencies|update_pack|_get_provider_for_pack" src/store/update_service.py src/store/__init__.py' in /home/box/git/github/synapse
plans/audits/codex-audit-2-custom-pack.md:26690:src/store/update_service.py:258:        Find all packs that depend on the given pack via pack_dependencies.
plans/audits/codex-audit-2-custom-pack.md:26691:src/store/update_service.py:261:            List of pack names that have pack_name in their pack_dependencies.
plans/audits/codex-audit-2-custom-pack.md:26692:src/store/update_service.py:269:                dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
plans/audits/codex-audit-2-custom-pack.md:26783:src/store/backup_service.py:246:        """Quick check if backup is enabled in config."""
plans/audits/codex-audit-2-custom-pack.md:26786:src/store/backup_service.py:257:            logger.warning("[Backup] Operation failed: backup not enabled")
plans/audits/codex-audit-2-custom-pack.md:27047:apps/web/src/i18n/locales/cs.json:973:    "shadowedExplanation": "Překryté soubory vznikají, když více packů exportuje soubory na stejnou cestu. Použije se soubor \"vítězného\" packu, zatímco soubor \"překrytého\" packu je skryt.",
plans/audits/codex-audit-2-custom-pack.md:27135:plans/audits/codex-audit-1-resolve-model.md:9434:    10	export function usePreviewAnalysis(packName: string, enabled: boolean) {
plans/audits/codex-audit-2-custom-pack.md:27678:- Profile integration works for direct pack assets, but does not recursively include `pack_dependencies`.
plans/audits/codex-audit-2-custom-pack.md:27687:- The main `Pack` model has `pack_category`, `source`, `dependencies`, `pack_dependencies`, `parameters`, and `workflows`.
plans/audits/codex-audit-2-custom-pack.md:27827:- pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:27846:- pack_dependencies gap:
plans/audits/codex-audit-2-custom-pack.md:27854:- pack_dependencies gap:
plans/audits/codex-audit-2-custom-pack.md:28070:- `pack_dependencies` are not recursively expanded into the profile.
plans/audits/codex-audit-2-custom-pack.md:28073:- If Custom Pack A depends on Pack B through `pack_dependencies`, using A does not automatically symlink B’s assets unless B is also present in the base/work profile.
plans/audits/codex-audit-2-custom-pack.md:28146:- No profile semantics for `pack_dependencies`.
plans/audits/codex-audit-2-custom-pack.md:28180:- Backend can find reverse dependencies through `pack_dependencies`.
plans/audits/codex-audit-2-custom-pack.md:28190:- Refs: `tests/store/test_pack_dependencies.py:26`, `tests/store/test_pack_dependencies.py:61`, `tests/store/test_pack_dependencies.py:69`.
plans/audits/codex-audit-2-custom-pack.md:28193:- Ref: `tests/store/test_pack_dependencies.py:249`.
plans/audits/codex-audit-2-custom-pack.md:28230:- Test that `pack_dependencies` affect profile/view if that is intended.
plans/audits/codex-audit-2-custom-pack.md:28284:- Should `pack_dependencies` be operational dependencies that alter profile/view symlinks, or informational dependencies only?
plans/audits/codex-audit-2-custom-pack.md:28286:- If operational, should `use(pack)` recursively include required `pack_dependencies`?
plans/audits/codex-audit-2-custom-pack.md:28288:- Should optional `pack_dependencies` be included automatically or only warned about?
plans/audits/codex-audit-2-custom-pack.md:28327:- Decide and implement `pack_dependencies` profile semantics.
plans/audits/codex-audit-2-custom-pack.md:28345:- Profile integration works for direct pack assets, but does not recursively include `pack_dependencies`.
plans/audits/codex-audit-2-custom-pack.md:28354:- The main `Pack` model has `pack_category`, `source`, `dependencies`, `pack_dependencies`, `parameters`, and `workflows`.
plans/audits/codex-audit-2-custom-pack.md:28494:- pack_dependencies:
plans/audits/codex-audit-2-custom-pack.md:28513:- pack_dependencies gap:
plans/audits/codex-audit-2-custom-pack.md:28521:- pack_dependencies gap:
plans/audits/codex-audit-2-custom-pack.md:28737:- `pack_dependencies` are not recursively expanded into the profile.
plans/audits/codex-audit-2-custom-pack.md:28740:- If Custom Pack A depends on Pack B through `pack_dependencies`, using A does not automatically symlink B’s assets unless B is also present in the base/work profile.
plans/audits/codex-audit-2-custom-pack.md:28813:- No profile semantics for `pack_dependencies`.
plans/audits/codex-audit-2-custom-pack.md:28847:- Backend can find reverse dependencies through `pack_dependencies`.
plans/audits/codex-audit-2-custom-pack.md:28857:- Refs: `tests/store/test_pack_dependencies.py:26`, `tests/store/test_pack_dependencies.py:61`, `tests/store/test_pack_dependencies.py:69`.
plans/audits/codex-audit-2-custom-pack.md:28860:- Ref: `tests/store/test_pack_dependencies.py:249`.
plans/audits/codex-audit-2-custom-pack.md:28897:- Test that `pack_dependencies` affect profile/view if that is intended.
plans/audits/codex-audit-2-custom-pack.md:28951:- Should `pack_dependencies` be operational dependencies that alter profile/view symlinks, or informational dependencies only?
plans/audits/codex-audit-2-custom-pack.md:28953:- If operational, should `use(pack)` recursively include required `pack_dependencies`?
plans/audits/codex-audit-2-custom-pack.md:28955:- Should optional `pack_dependencies` be included automatically or only warned about?
plans/audits/codex-audit-2-custom-pack.md:28994:- Decide and implement `pack_dependencies` profile semantics.

codex
I found one prompt assumption already out of sync with the current tree: `ProfilePackEntry` in `src/store/models.py` has only `name`, while `src/store/cli.py` still references `pack_entry.enabled`. I’ll mark that as a model/API drift rather than repeating it as “enabled ignored.”
exec
/bin/bash -lc "nl -ba src/store/pack_service.py | sed -n '72,150p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    72	class PreviewDownloadConfig(BaseModel):
    73	    """
    74	    Configuration for preview download operations.
    75	
    76	    Provides fine-grained control over what types of preview content
    77	    to download during pack import operations.
    78	
    79	    Attributes:
    80	        download_images: Whether to download image previews
    81	        download_videos: Whether to download video previews
    82	        include_nsfw: Whether to include NSFW content
    83	        video_quality: Target video width for optimization
    84	        download_from_all_versions: Whether to download from all versions or just selected
    85	    """
    86	    download_images: bool = True
    87	    download_videos: bool = True
    88	    include_nsfw: bool = True
    89	    video_quality: int = 1080
    90	    download_from_all_versions: bool = True
    91	
    92	
    93	class DownloadProgressInfo(BaseModel):
    94	    """
    95	    Progress information for download operations.
    96	
    97	    Used to track and report download progress through callbacks.
    98	
    99	    Attributes:
   100	        index: Current item index (0-based)
   101	        total: Total number of items
   102	        filename: Current filename
   103	        media_type: Type of media being downloaded
   104	        bytes_downloaded: Bytes downloaded so far
   105	        total_bytes: Total bytes (if known)
   106	        status: Current status
   107	        error: Error message if failed
   108	    """
   109	    index: int
   110	    total: int
   111	    filename: str
   112	    media_type: str
   113	    bytes_downloaded: int = 0
   114	    total_bytes: Optional[int] = None
   115	    status: Literal['downloading', 'completed', 'skipped', 'failed'] = 'downloading'
   116	    error: Optional[str] = None
   117	
   118	
   119	# Type aliases for progress callbacks
   120	ProgressCallback = Callable[[DownloadProgressInfo], None]
   121	ResolveProgressCallback = Callable[[str, str], None]
   122	
   123	
   124	# =============================================================================
   125	# Pack Service Class
   126	# =============================================================================
   127	
   128	class PackService:
   129	    """
   130	    Service for managing packs.
   131	
   132	    Provides methods for importing, managing, and resolving packs
   133	    with full support for video previews and configurable options.
   134	
   135	    Features:
   136	        - Civitai model import with video support
   137	        - Configurable preview downloads (images/videos/NSFW)
   138	        - Progress tracking for large operations
   139	        - Metadata enrichment and merging
   140	        - Dependency resolution
   141	        - Pack installation
   142	    """
   143	
   144	    # Mapping Civitai model types to AssetKind
   145	    CIVITAI_TYPE_MAP = {
   146	        "Checkpoint": AssetKind.CHECKPOINT,
   147	        "LORA": AssetKind.LORA,
   148	        "TextualInversion": AssetKind.EMBEDDING,
   149	        "VAE": AssetKind.VAE,
   150	        "ControlNet": AssetKind.CONTROLNET,

exec
/bin/bash -lc "nl -ba src/store/pack_service.py | sed -n '307,675p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   307	    def import_from_civitai(
   308	        self,
   309	        url: str,
   310	        download_previews: bool = True,
   311	        max_previews: int = 100,
   312	        pack_name: Optional[str] = None,
   313	        download_config: Optional[PreviewDownloadConfig] = None,
   314	        progress_callback: Optional[ProgressCallback] = None,
   315	        cover_url: Optional[str] = None,
   316	        selected_version_ids: Optional[List[int]] = None,
   317	        additional_previews: Optional[List[dict]] = None,
   318	    ) -> Pack:
   319	        """
   320	        Import a pack from Civitai URL.
   321	
   322	        Creates pack.json with:
   323	        - One dependency per selected version (multi-version support)
   324	        - Base model as dependency (if detectable)
   325	        - Preview images downloaded with full metadata
   326	        - Model info extracted from Civitai
   327	
   328	        Args:
   329	            url: Civitai model URL
   330	            download_previews: If True, download preview images
   331	            max_previews: Max number of previews to download
   332	            pack_name: Optional custom pack name
   333	            download_config: Preview download configuration
   334	            progress_callback: Optional progress callback
   335	            cover_url: User-selected thumbnail URL
   336	            selected_version_ids: List of version IDs to import (creates one dependency per version)
   337	            additional_previews: Extra previews with nsfw flags [{url, nsfw}]
   338	
   339	        Returns:
   340	            Created Pack
   341	        """
   342	        from .models import ModelInfo
   343	
   344	        if download_config is None:
   345	            download_config = PreviewDownloadConfig()
   346	
   347	        logger.info(f"[PackService] Importing from: {url}")
   348	
   349	        model_id, version_id = self.parse_civitai_url(url)
   350	
   351	        # Fetch model data
   352	        model_data = self.civitai.get_model(model_id)
   353	
   354	        # Get specific version or latest
   355	        if version_id:
   356	            version_data = self.civitai.get_model_version(version_id)
   357	        else:
   358	            versions = model_data.get("modelVersions", [])
   359	            if not versions:
   360	                raise ValueError(f"No versions found for model {model_id}")
   361	            version_data = versions[0]
   362	            version_id = version_data["id"]
   363	
   364	        # Collect images for preview download
   365	        # If download_from_all_versions is True, collect from ALL versions
   366	        # Otherwise, only use images from the selected version
   367	        detailed_version_images: List[Dict[str, Any]] = []
   368	        all_versions = model_data.get("modelVersions", [])
   369	
   370	        if download_config.download_from_all_versions:
   371	            # Use images already present in model_data (no extra API calls needed).
   372	            # get_model() returns modelVersions[].images with full metadata.
   373	            seen_urls: set = set()
   374	            for ver in all_versions:
   375	                for img in ver.get("images", []):
   376	                    img_url = img.get("url")
   377	                    if img_url and img_url not in seen_urls:
   378	                        seen_urls.add(img_url)
   379	                        detailed_version_images.append(img)
   380	            logger.info(f"[PackService] Collected {len(detailed_version_images)} unique previews from {len(all_versions)} versions")
   381	        else:
   382	            # Only use images from selected version (already fetched)
   383	            detailed_version_images = version_data.get("images", [])
   384	            logger.info(f"[PackService] Collected {len(detailed_version_images)} previews from version {version_id}")
   385	
   386	        # Determine asset type
   387	        civitai_type = model_data.get("type", "LORA")
   388	        asset_kind = self.CIVITAI_TYPE_MAP.get(civitai_type, AssetKind.LORA)
   389	
   390	        # Create pack name (sanitized)
   391	        model_name = model_data.get("name", f"model_{model_id}")
   392	        name = pack_name or self._sanitize_pack_name(model_name)
   393	
   394	        # Determine which versions to import
   395	        # If selected_version_ids provided, use those; otherwise use single version from URL
   396	        versions_to_import: List[int] = []
   397	        if selected_version_ids and len(selected_version_ids) > 0:
   398	            versions_to_import = selected_version_ids
   399	            logger.info(f"[PackService] Multi-version import: {len(versions_to_import)} versions selected")
   400	        else:
   401	            versions_to_import = [version_id]
   402	            logger.info(f"[PackService] Single version import: {version_id}")
   403	
   404	        dependencies: List[PackDependency] = []
   405	        base_model = None
   406	        autov2 = None
   407	        sha256 = None
   408	        first_version_data = None
   409	
   410	        # Create one dependency for each selected version
   411	        for idx, ver_id in enumerate(versions_to_import):
   412	            try:
   413	                # Fetch version data
   414	                ver_data = self.civitai.get_model_version(ver_id)
   415	                if first_version_data is None:
   416	                    first_version_data = ver_data
   417	
   418	                # Get files for this version
   419	                files = ver_data.get("files", [])
   420	                if not files:
   421	                    logger.warning(f"[PackService] No files found for version {ver_id}, skipping")
   422	                    continue
   423	
   424	                # Find primary file (prefer safetensors)
   425	                primary_file = None
   426	                for f in files:
   427	                    if f.get("primary"):
   428	                        primary_file = f
   429	                        break
   430	                if primary_file is None:
   431	                    for f in files:
   432	                        if f.get("name", "").endswith(".safetensors"):
   433	                            primary_file = f
   434	                            break
   435	                if primary_file is None:
   436	                    primary_file = files[0]
   437	
   438	                # Get hash info for first version (for model_info)
   439	                if idx == 0:
   440	                    hashes = primary_file.get("hashes", {})
   441	                    sha256 = hashes.get("SHA256", "").lower() if hashes else None
   442	                    autov2 = hashes.get("AutoV2") if hashes else None
   443	                    base_model = ver_data.get("baseModel")
   444	
   445	                # Create unique dependency ID
   446	                # For single version: main_lora
   447	                # For multi-version: version_{version_id}_lora (with version name if available)
   448	                version_name = ver_data.get("name", str(ver_id))
   449	                if len(versions_to_import) == 1:
   450	                    dep_id = f"main_{asset_kind.value}"
   451	                else:
   452	                    # Sanitize version name for ID
   453	                    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', version_name)[:30]
   454	                    dep_id = f"v{ver_id}_{safe_name}_{asset_kind.value}"
   455	
   456	                dep = PackDependency(
   457	                    id=dep_id,
   458	                    kind=asset_kind,
   459	                    required=True,
   460	                    selector=DependencySelector(
   461	                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
   462	                        civitai=CivitaiSelector(
   463	                            model_id=model_id,
   464	                            version_id=ver_id,
   465	                            file_id=primary_file.get("id"),
   466	                        ),
   467	                    ),
   468	                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
   469	                    expose=ExposeConfig(
   470	                        filename=primary_file.get("name", f"{name}.safetensors"),
   471	                        trigger_words=ver_data.get("trainedWords", []),
   472	                    ),
   473	                )
   474	                dependencies.append(dep)
   475	                logger.info(f"[PackService] Created dependency '{dep_id}' for version {ver_id} ({version_name})")
   476	
   477	            except Exception as e:
   478	                logger.error(f"[PackService] Failed to process version {ver_id}: {e}")
   479	                continue
   480	
   481	        if not dependencies:
   482	            raise ValueError(f"No valid versions could be processed for model {model_id}")
   483	
   484	        # Use first version data for pack metadata if we don't have version_data
   485	        if first_version_data:
   486	            version_data = first_version_data
   487	
   488	        # Add base model dependency if detected
   489	        if base_model:
   490	            base_dep = self._create_base_model_dependency(base_model)
   491	            if base_dep:
   492	                dependencies.insert(0, base_dep)
   493	
   494	        # Extract model info
   495	        stats = model_data.get("stats", {})
   496	        model_info = ModelInfo(
   497	            model_type=civitai_type,
   498	            base_model=base_model,
   499	            trigger_words=version_data.get("trainedWords", []),
   500	            trained_words=version_data.get("trainedWords", []),
   501	            hash_autov2=autov2,
   502	            hash_sha256=sha256,
   503	            civitai_air=f"civitai: {model_id} @ {version_id}",
   504	            download_count=stats.get("downloadCount"),
   505	            rating=stats.get("rating"),
   506	            published_at=version_data.get("publishedAt"),
   507	        )
   508	
   509	        # Create pack with all metadata
   510	        pack = Pack(
   511	            name=name,
   512	            pack_type=asset_kind,
   513	            pack_category=PackCategory.EXTERNAL,  # Imported from Civitai
   514	            source=PackSource(
   515	                provider=ProviderName.CIVITAI,
   516	                model_id=model_id,
   517	                version_id=version_id,
   518	                url=url,
   519	            ),
   520	            dependencies=dependencies,
   521	            pack_dependencies=[],  # No pack dependencies by default
   522	            resources=PackResources(
   523	                previews_keep_in_git=True,
   524	                workflows_keep_in_git=True,
   525	            ),
   526	            cover_url=cover_url,  # User-selected thumbnail
   527	            version=version_data.get("name"),
   528	            description=model_data.get("description"),
   529	            base_model=base_model,
   530	            author=model_data.get("creator", {}).get("username"),
   531	            tags=model_data.get("tags", []),
   532	            trigger_words=version_data.get("trainedWords", []),
   533	            model_info=model_info,
   534	        )
   535	
   536	        # Extract parameters from description using AI (with rule-based fallback)
   537	        if pack.description:
   538	            from src.avatar.ai_service import AvatarAIService
   539	            from .models import GenerationParameters
   540	
   541	            logger.info(f"[parameter-extraction] Extracting from description (length: {len(pack.description)})")
   542	
   543	            try:
   544	                ai_service = AvatarAIService()
   545	                result = ai_service.extract_parameters(pack.description)
   546	
   547	                if result.success and result.output:
   548	                    param_keys = list(result.output.keys())
   549	                    logger.info(
   550	                        f"[parameter-extraction] Found {len(param_keys)} params via {result.provider_id}: {param_keys}"
   551	                    )
   552	
   553	                    # Convert to GenerationParameters model
   554	                    pack.parameters = GenerationParameters(**result.output)
   555	                    pack.parameters_source = result.provider_id  # Track extraction source
   556	                    logger.info(f"[parameter-extraction] Parameters saved to pack (source: {result.provider_id})")
   557	                else:
   558	                    logger.info(f"[parameter-extraction] No parameters found in description")
   559	
   560	            except Exception as e:
   561	                logger.warning(f"[parameter-extraction] AI extraction failed, skipping: {e}")
   562	
   563	        # Save pack
   564	        self.layout.save_pack(pack)
   565	
   566	        # Create initial lock for all dependencies
   567	        lock = self._create_initial_lock_multi(pack)
   568	        self.layout.save_pack_lock(lock)
   569	
   570	        # Download previews and get metadata
   571	        if download_previews:
   572	            previews = self._download_previews(
   573	                pack_name=name,
   574	                version_data=version_data,
   575	                max_count=max_previews,
   576	                detailed_version_images=detailed_version_images,
   577	                download_images=download_config.download_images,
   578	                download_videos=download_config.download_videos,
   579	                include_nsfw=download_config.include_nsfw,
   580	                video_quality=download_config.video_quality,
   581	                progress_callback=progress_callback,
   582	            )
   583	            if previews:
   584	                pack.previews = previews
   585	
   586	            # Download additional previews (e.g. community gallery) with nsfw flags
   587	            if additional_previews:
   588	                additional = self._download_additional_previews(
   589	                    pack_name=name,
   590	                    previews=additional_previews,
   591	                    start_index=len(pack.previews),
   592	                )
   593	                if additional:
   594	                    pack.previews.extend(additional)
   595	                    logger.info(f"[PackService] Downloaded {len(additional)} additional previews")
   596	
   597	            if pack.previews:
   598	                self.layout.save_pack(pack)
   599	
   600	        logger.info(f"[PackService] Import complete: {name}")
   601	        return pack
   602	
   603	    def _create_base_model_dependency(self, base_model: str) -> Optional[PackDependency]:
   604	        """Create a base model dependency from Civitai baseModel string."""
   605	        try:
   606	            config = self.layout.load_config()
   607	            alias = config.base_model_aliases.get(base_model)
   608	            if alias:
   609	                return PackDependency(
   610	                    id="base_checkpoint",
   611	                    kind=alias.kind,
   612	                    required=False,
   613	                    selector=DependencySelector(
   614	                        strategy=SelectorStrategy.BASE_MODEL_HINT,
   615	                        base_model=base_model,
   616	                    ),
   617	                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.PINNED),
   618	                    expose=ExposeConfig(filename=alias.default_expose_filename),
   619	                )
   620	        except Exception:
   621	            pass
   622	
   623	        return PackDependency(
   624	            id="base_checkpoint",
   625	            kind=AssetKind.CHECKPOINT,
   626	            required=False,
   627	            selector=DependencySelector(
   628	                strategy=SelectorStrategy.BASE_MODEL_HINT,
   629	                base_model=base_model,
   630	            ),
   631	            update_policy=UpdatePolicy(mode=UpdatePolicyMode.PINNED),
   632	            expose=ExposeConfig(filename=f"{base_model}.safetensors"),
   633	        )
   634	
   635	    def _create_initial_lock_multi(self, pack: Pack) -> PackLock:
   636	        """
   637	        Create initial lock file from pack with multi-version support.
   638	
   639	        Fetches version data for each Civitai dependency to get correct
   640	        sha256, size, and download URL for each version.
   641	        """
   642	        resolved = []
   643	        unresolved = []
   644	
   645	        for dep in pack.dependencies:
   646	            if dep.selector.strategy == SelectorStrategy.CIVITAI_MODEL_LATEST:
   647	                try:
   648	                    # Fetch version data for this specific dependency
   649	                    civ = dep.selector.civitai
   650	                    if not civ or not civ.version_id:
   651	                        continue
   652	
   653	                    version_data = self.civitai.get_model_version(civ.version_id)
   654	                    files = version_data.get("files", [])
   655	
   656	                    # Find the specific file or primary file
   657	                    target_file = None
   658	                    if civ.file_id:
   659	                        for f in files:
   660	                            if f.get("id") == civ.file_id:
   661	                                target_file = f
   662	                                break
   663	                    if not target_file and files:
   664	                        # Find primary or first safetensors
   665	                        for f in files:
   666	                            if f.get("primary"):
   667	                                target_file = f
   668	                                break
   669	                        if not target_file:
   670	                            for f in files:
   671	                                if f.get("name", "").endswith(".safetensors"):
   672	                                    target_file = f
   673	                                    break
   674	                        if not target_file:
   675	                            target_file = files[0]

exec
/bin/bash -lc "nl -ba src/store/pack_service.py | sed -n '1132,1328p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1132	    def resolve_pack(
  1133	        self,
  1134	        pack_name: str,
  1135	        progress_callback: Optional[ResolveProgressCallback] = None,
  1136	    ) -> PackLock:
  1137	        """
  1138	        Resolve all dependencies in a pack, creating/updating lock file.
  1139	
  1140	        Args:
  1141	            pack_name: Pack to resolve
  1142	            progress_callback: Optional callback for progress updates
  1143	
  1144	        Returns:
  1145	            Updated PackLock
  1146	        """
  1147	        pack = self.layout.load_pack(pack_name)
  1148	        existing_lock = self.layout.load_pack_lock(pack_name)
  1149	
  1150	        resolved = []
  1151	        unresolved = []
  1152	
  1153	        for dep in pack.dependencies:
  1154	            if progress_callback:
  1155	                progress_callback(dep.id, "resolving")
  1156	
  1157	            try:
  1158	                artifact = self._resolve_dependency(pack, dep, existing_lock)
  1159	                if artifact:
  1160	                    resolved.append(ResolvedDependency(
  1161	                        dependency_id=dep.id,
  1162	                        artifact=artifact,
  1163	                    ))
  1164	                    if progress_callback:
  1165	                        progress_callback(dep.id, "resolved")
  1166	                else:
  1167	                    unresolved.append(UnresolvedDependency(
  1168	                        dependency_id=dep.id,
  1169	                        reason="no_artifact_found",
  1170	                        details={},
  1171	                    ))
  1172	                    if progress_callback:
  1173	                        progress_callback(dep.id, "unresolved")
  1174	            except Exception as e:
  1175	                unresolved.append(UnresolvedDependency(
  1176	                    dependency_id=dep.id,
  1177	                    reason="resolution_error",
  1178	                    details={"error": str(e)},
  1179	                ))
  1180	                if progress_callback:
  1181	                    progress_callback(dep.id, f"error: {e}")
  1182	
  1183	        lock = PackLock(
  1184	            pack=pack_name,
  1185	            resolved_at=datetime.now().isoformat(),
  1186	            resolved=resolved,
  1187	            unresolved=unresolved,
  1188	        )
  1189	
  1190	        self.layout.save_pack_lock(lock)
  1191	        return lock
  1192	
  1193	    def _ensure_resolvers(self) -> None:
  1194	        """Lazily initialize default resolvers if none were provided."""
  1195	        if self._resolvers:
  1196	            return
  1197	
  1198	        from .dependency_resolver import (
  1199	            BaseModelHintResolver,
  1200	            CivitaiFileResolver,
  1201	            CivitaiLatestResolver,
  1202	            HuggingFaceResolver,
  1203	            LocalFileResolver,
  1204	            UrlResolver,
  1205	        )
  1206	
  1207	        self._resolvers = {
  1208	            SelectorStrategy.CIVITAI_FILE: CivitaiFileResolver(self.civitai),
  1209	            SelectorStrategy.CIVITAI_MODEL_LATEST: CivitaiLatestResolver(self.civitai),
  1210	            SelectorStrategy.BASE_MODEL_HINT: BaseModelHintResolver(self.civitai, self.layout),
  1211	            SelectorStrategy.HUGGINGFACE_FILE: HuggingFaceResolver(),
  1212	            SelectorStrategy.URL_DOWNLOAD: UrlResolver(),
  1213	            SelectorStrategy.LOCAL_FILE: LocalFileResolver(),
  1214	        }
  1215	
  1216	    def _resolve_dependency(
  1217	        self,
  1218	        pack: Pack,
  1219	        dep: PackDependency,
  1220	        existing_lock: Optional[PackLock],
  1221	    ) -> Optional[ResolvedArtifact]:
  1222	        """Resolve a single dependency via the resolver registry."""
  1223	        self._ensure_resolvers()
  1224	
  1225	        resolver = self._resolvers.get(dep.selector.strategy)
  1226	        if resolver is None:
  1227	            logger.warning("No resolver for strategy %s", dep.selector.strategy)
  1228	            return None
  1229	
  1230	        return resolver.resolve(dep)
  1231	
  1232	    # =========================================================================
  1233	    # Installation
  1234	    # =========================================================================
  1235	
  1236	    def install_pack(
  1237	        self,
  1238	        pack_name: str,
  1239	        progress_callback: Optional[Callable[[str, int, int], None]] = None,
  1240	    ) -> List[str]:
  1241	        """
  1242	        Install all blobs for a pack from its lock file.
  1243	
  1244	        Args:
  1245	            pack_name: Pack to install
  1246	            progress_callback: Optional callback (dep_id, downloaded, total)
  1247	
  1248	        Returns:
  1249	            List of installed SHA256 hashes
  1250	        """
  1251	        lock = self.layout.load_pack_lock(pack_name)
  1252	        if not lock:
  1253	            raise PackNotFoundError(f"No lock file for pack: {pack_name}")
  1254	
  1255	        # Load pack for expose filename lookup
  1256	        pack = self.layout.load_pack(pack_name)
  1257	
  1258	        installed = []
  1259	
  1260	        for resolved in lock.resolved:
  1261	            sha256 = resolved.artifact.sha256
  1262	            urls = resolved.artifact.download.urls
  1263	
  1264	            if not urls:
  1265	                continue
  1266	
  1267	            blob_already_existed = sha256 and self.blob_store.blob_exists(sha256)
  1268	
  1269	            if blob_already_existed:
  1270	                installed.append(sha256)
  1271	                # Ensure manifest exists even for pre-existing blobs
  1272	                self._ensure_blob_manifest(sha256, resolved, pack)
  1273	                continue
  1274	
  1275	            try:
  1276	                def make_callback(dep_id: str):
  1277	                    if progress_callback:
  1278	                        return lambda d, t: progress_callback(dep_id, d, t)
  1279	                    return None
  1280	
  1281	                actual_sha = self.blob_store.download(
  1282	                    urls[0],
  1283	                    sha256,
  1284	                    progress_callback=make_callback(resolved.dependency_id),
  1285	                )
  1286	                installed.append(actual_sha)
  1287	
  1288	                if not sha256:
  1289	                    resolved.artifact.sha256 = actual_sha
  1290	                    resolved.artifact.integrity.sha256_verified = True
  1291	                    self.layout.save_pack_lock(lock)
  1292	
  1293	                # Create manifest for newly downloaded blob
  1294	                self._ensure_blob_manifest(actual_sha, resolved, pack)
  1295	
  1296	            except Exception as e:
  1297	                logger.error(f"[PackService] Failed to install {resolved.dependency_id}: {e}")
  1298	
  1299	        return installed
  1300	
  1301	    def _ensure_blob_manifest(
  1302	        self,
  1303	        sha256: str,
  1304	        resolved: ResolvedDependency,
  1305	        pack: Optional[Pack],
  1306	    ) -> None:
  1307	        """
  1308	        Ensure a manifest exists for a blob (write-once, never overwrites).
  1309	
  1310	        Called during blob installation to persist metadata for orphan recovery.
  1311	        """
  1312	        # Skip if manifest already exists
  1313	        if self.blob_store.manifest_exists(sha256):
  1314	            return
  1315	
  1316	        # Get expose filename from pack dependency, fall back to provider filename
  1317	        expose_filename: Optional[str] = None
  1318	        if pack:
  1319	            dep = pack.get_dependency(resolved.dependency_id)
  1320	            if dep:
  1321	                expose_filename = dep.expose.filename
  1322	
  1323	        # Fall back to provider filename or SHA256 prefix
  1324	        original_filename = (
  1325	            expose_filename
  1326	            or resolved.artifact.provider.filename
  1327	            or f"{sha256[:12]}.bin"
  1328	        )

exec
/bin/bash -lc "nl -ba src/store/dependency_resolver.py | sed -n '1,370p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Dependency Resolver Protocol and Implementations.
     3	
     4	Defines the DependencyResolver protocol for resolving pack dependencies,
     5	with provider-specific implementations for Civitai, HuggingFace, URL, and local files.
     6	
     7	Each resolver is responsible for one or more SelectorStrategy values
     8	and is registered in PackService via a strategy -> resolver registry.
     9	"""
    10	
    11	from __future__ import annotations
    12	
    13	import logging
    14	from pathlib import Path
    15	from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
    16	
    17	from .models import (
    18	    ArtifactDownload,
    19	    ArtifactIntegrity,
    20	    ArtifactProvider,
    21	    AssetKind,
    22	    PackDependency,
    23	    ProviderName,
    24	    ResolvedArtifact,
    25	    SelectorConstraints,
    26	)
    27	
    28	logger = logging.getLogger(__name__)
    29	
    30	
    31	@runtime_checkable
    32	class DependencyResolver(Protocol):
    33	    """Protocol for resolving a pack dependency to a downloadable artifact."""
    34	
    35	    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
    36	        """
    37	        Resolve a dependency to an artifact with download URL(s).
    38	
    39	        Args:
    40	            dep: The dependency to resolve.
    41	            **kwargs: Additional context (e.g., existing_lock, layout).
    42	
    43	        Returns:
    44	            ResolvedArtifact if resolution succeeds, None if this resolver
    45	            cannot handle the dependency.
    46	        """
    47	        ...
    48	
    49	
    50	class CivitaiFileResolver:
    51	    """Resolves pinned Civitai file dependencies (CIVITAI_FILE strategy)."""
    52	
    53	    def __init__(self, civitai_client: Any):
    54	        self._civitai = civitai_client
    55	
    56	    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
    57	        if not dep.selector.civitai:
    58	            return None
    59	
    60	        civ = dep.selector.civitai
    61	        if not civ.version_id:
    62	            return None
    63	
    64	        version_data = self._civitai.get_model_version(civ.version_id)
    65	        files = version_data.get("files", [])
    66	
    67	        target_file = None
    68	        if civ.file_id:
    69	            for f in files:
    70	                if f.get("id") == civ.file_id:
    71	                    target_file = f
    72	                    break
    73	        if not target_file and files:
    74	            target_file = files[0]
    75	
    76	        if not target_file:
    77	            return None
    78	
    79	        hashes = target_file.get("hashes", {})
    80	        sha256 = hashes.get("SHA256", "").lower() if hashes else None
    81	
    82	        download_url = target_file.get("downloadUrl", "")
    83	        if not download_url:
    84	            download_url = f"https://civitai.com/api/download/models/{civ.version_id}"
    85	
    86	        return ResolvedArtifact(
    87	            kind=dep.kind,
    88	            sha256=sha256,
    89	            size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
    90	            provider=ArtifactProvider(
    91	                name=ProviderName.CIVITAI,
    92	                model_id=civ.model_id,
    93	                version_id=civ.version_id,
    94	                file_id=target_file.get("id"),
    95	                filename=target_file.get("name"),
    96	            ),
    97	            download=ArtifactDownload(urls=[download_url]),
    98	            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
    99	        )
   100	
   101	
   102	class CivitaiLatestResolver:
   103	    """Resolves latest Civitai model version (CIVITAI_MODEL_LATEST strategy)."""
   104	
   105	    def __init__(self, civitai_client: Any):
   106	        self._civitai = civitai_client
   107	
   108	    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
   109	        if not dep.selector.civitai:
   110	            return None
   111	
   112	        civ = dep.selector.civitai
   113	
   114	        # If a specific version_id is pinned, fetch that exact version
   115	        # instead of blindly taking versions[0] (latest).
   116	        # Multi-version packs have different version_ids per dependency.
   117	        if civ.version_id:
   118	            return self._resolve_pinned_version(dep, civ)
   119	
   120	        # No pinned version — fall back to latest
   121	        model_data = self._civitai.get_model(civ.model_id)
   122	        versions = model_data.get("modelVersions", [])
   123	        if not versions:
   124	            return None
   125	
   126	        latest = versions[0]
   127	        return self._build_artifact(dep, civ, latest)
   128	
   129	    def _resolve_pinned_version(
   130	        self, dep: PackDependency, civ: Any
   131	    ) -> Optional[ResolvedArtifact]:
   132	        """Resolve a dependency pinned to a specific version_id."""
   133	        version_data = self._civitai.get_model_version(civ.version_id)
   134	        files = version_data.get("files", [])
   135	        if not files:
   136	            return None
   137	
   138	        # If file_id is specified, find that exact file
   139	        target_file = None
   140	        if civ.file_id:
   141	            for f in files:
   142	                if f.get("id") == civ.file_id:
   143	                    target_file = f
   144	                    break
   145	
   146	        # Fall back to file selection by constraints or primary
   147	        if not target_file:
   148	            target_file = _select_file(files, dep.selector.constraints)
   149	        if not target_file:
   150	            return None
   151	
   152	        hashes = target_file.get("hashes", {})
   153	        sha256 = hashes.get("SHA256", "").lower() if hashes else None
   154	
   155	        download_url = target_file.get("downloadUrl", "")
   156	        if not download_url:
   157	            download_url = f"https://civitai.com/api/download/models/{civ.version_id}"
   158	
   159	        return ResolvedArtifact(
   160	            kind=dep.kind,
   161	            sha256=sha256,
   162	            size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
   163	            provider=ArtifactProvider(
   164	                name=ProviderName.CIVITAI,
   165	                model_id=civ.model_id,
   166	                version_id=civ.version_id,
   167	                file_id=target_file.get("id"),
   168	                filename=target_file.get("name"),
   169	            ),
   170	            download=ArtifactDownload(urls=[download_url]),
   171	            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
   172	        )
   173	
   174	    def _build_artifact(
   175	        self, dep: PackDependency, civ: Any, version_data: dict
   176	    ) -> Optional[ResolvedArtifact]:
   177	        """Build a ResolvedArtifact from version data."""
   178	        files = version_data.get("files", [])
   179	        if not files:
   180	            return None
   181	
   182	        target_file = _select_file(files, dep.selector.constraints)
   183	        if not target_file:
   184	            return None
   185	
   186	        hashes = target_file.get("hashes", {})
   187	        sha256 = hashes.get("SHA256", "").lower() if hashes else None
   188	
   189	        download_url = target_file.get("downloadUrl", "")
   190	        if not download_url:
   191	            download_url = f"https://civitai.com/api/download/models/{version_data['id']}"
   192	
   193	        return ResolvedArtifact(
   194	            kind=dep.kind,
   195	            sha256=sha256,
   196	            size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
   197	            provider=ArtifactProvider(
   198	                name=ProviderName.CIVITAI,
   199	                model_id=civ.model_id,
   200	                version_id=version_data["id"],
   201	                file_id=target_file.get("id"),
   202	                filename=target_file.get("name"),
   203	            ),
   204	            download=ArtifactDownload(urls=[download_url]),
   205	            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
   206	        )
   207	
   208	
   209	class BaseModelHintResolver:
   210	    """Resolves base model hints via config aliases (BASE_MODEL_HINT strategy)."""
   211	
   212	    def __init__(self, civitai_client: Any, layout: Any):
   213	        self._civitai = civitai_client
   214	        self._layout = layout
   215	
   216	    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
   217	        if not dep.selector.base_model:
   218	            return None
   219	
   220	        try:
   221	            config = self._layout.load_config()
   222	            alias = config.base_model_aliases.get(dep.selector.base_model)
   223	            if not alias or not alias.selector.civitai:
   224	                return None
   225	
   226	            civ = alias.selector.civitai
   227	            if civ.version_id:
   228	                version_data = self._civitai.get_model_version(civ.version_id)
   229	                files = version_data.get("files", [])
   230	
   231	                target_file = None
   232	                if civ.file_id:
   233	                    for f in files:
   234	                        if f.get("id") == civ.file_id:
   235	                            target_file = f
   236	                            break
   237	                if not target_file:
   238	                    target_file = _select_file(files, dep.selector.constraints if hasattr(dep.selector, 'constraints') else None)
   239	                if not target_file and files:
   240	                    target_file = files[0]
   241	
   242	                if target_file:
   243	                    hashes = target_file.get("hashes", {})
   244	                    sha256 = hashes.get("SHA256", "").lower() if hashes else None
   245	
   246	                    download_url = target_file.get("downloadUrl", "")
   247	                    if not download_url:
   248	                        download_url = f"https://civitai.com/api/download/models/{civ.version_id}"
   249	
   250	                    return ResolvedArtifact(
   251	                        kind=dep.kind,
   252	                        sha256=sha256,
   253	                        size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
   254	                        provider=ArtifactProvider(
   255	                            name=ProviderName.CIVITAI,
   256	                            model_id=civ.model_id,
   257	                            version_id=civ.version_id,
   258	                            file_id=target_file.get("id"),
   259	                            filename=target_file.get("name"),
   260	                        ),
   261	                        download=ArtifactDownload(urls=[download_url]),
   262	                        integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
   263	                    )
   264	        except Exception:
   265	            pass
   266	
   267	        return None
   268	
   269	
   270	class HuggingFaceResolver:
   271	    """Resolves HuggingFace file dependencies (HUGGINGFACE_FILE strategy)."""
   272	
   273	    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
   274	        if not dep.selector.huggingface:
   275	            return None
   276	
   277	        hf = dep.selector.huggingface
   278	
   279	        url = f"https://huggingface.co/{hf.repo_id}/resolve/{hf.revision or 'main'}"
   280	        if hf.subfolder:
   281	            url += f"/{hf.subfolder}"
   282	        url += f"/{hf.filename}"
   283	
   284	        return ResolvedArtifact(
   285	            kind=dep.kind,
   286	            sha256=None,
   287	            size_bytes=None,
   288	            provider=ArtifactProvider(
   289	                name=ProviderName.HUGGINGFACE,
   290	                repo_id=hf.repo_id,
   291	                filename=hf.filename,
   292	                revision=hf.revision,
   293	            ),
   294	            download=ArtifactDownload(urls=[url]),
   295	            integrity=ArtifactIntegrity(sha256_verified=False),
   296	        )
   297	
   298	
   299	class UrlResolver:
   300	    """Resolves direct URL dependencies (URL_DOWNLOAD strategy)."""
   301	
   302	    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
   303	        if not dep.selector.url:
   304	            return None
   305	
   306	        return ResolvedArtifact(
   307	            kind=dep.kind,
   308	            sha256=None,
   309	            size_bytes=None,
   310	            provider=ArtifactProvider(name=ProviderName.URL),
   311	            download=ArtifactDownload(urls=[dep.selector.url]),
   312	            integrity=ArtifactIntegrity(sha256_verified=False),
   313	        )
   314	
   315	
   316	class LocalFileResolver:
   317	    """Resolves local file dependencies (LOCAL_FILE strategy)."""
   318	
   319	    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
   320	        if not dep.selector.local_path:
   321	            return None
   322	
   323	        path = Path(dep.selector.local_path)
   324	        if not path.exists():
   325	            return None
   326	
   327	        from .blob_store import compute_sha256
   328	        sha256 = compute_sha256(path)
   329	
   330	        return ResolvedArtifact(
   331	            kind=dep.kind,
   332	            sha256=sha256,
   333	            size_bytes=path.stat().st_size,
   334	            provider=ArtifactProvider(name=ProviderName.LOCAL),
   335	            download=ArtifactDownload(urls=[path.as_uri()]),
   336	            integrity=ArtifactIntegrity(sha256_verified=True),
   337	        )
   338	
   339	
   340	# =============================================================================
   341	# Shared Helpers
   342	# =============================================================================
   343	
   344	def _select_file(
   345	    files: List[Dict[str, Any]],
   346	    constraints: Optional[SelectorConstraints],
   347	) -> Optional[Dict[str, Any]]:
   348	    """Select best file from list based on constraints."""
   349	    if not files:
   350	        return None
   351	
   352	    candidates = files.copy()
   353	
   354	    if constraints:
   355	        if constraints.primary_file_only:
   356	            primary = [f for f in candidates if f.get("primary")]
   357	            if primary:
   358	                candidates = primary
   359	
   360	        if constraints.file_ext:
   361	            ext_filtered = [
   362	                f for f in candidates
   363	                if any(f.get("name", "").endswith(ext) for ext in constraints.file_ext)
   364	            ]
   365	            if ext_filtered:
   366	                candidates = ext_filtered
   367	
   368	    return candidates[0] if candidates else None

exec
/bin/bash -lc "nl -ba src/store/pack_service.py | sed -n '675,760p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   675	                            target_file = files[0]
   676	
   677	                    if not target_file:
   678	                        unresolved.append(UnresolvedDependency(
   679	                            dependency_id=dep.id,
   680	                            reason="no_file_found",
   681	                            details={"version_id": civ.version_id},
   682	                        ))
   683	                        continue
   684	
   685	                    # Extract file info
   686	                    hashes = target_file.get("hashes", {})
   687	                    sha256 = hashes.get("SHA256", "").lower() if hashes else None
   688	                    file_size = target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None
   689	
   690	                    download_url = target_file.get("downloadUrl", "")
   691	                    if not download_url:
   692	                        download_url = f"https://civitai.com/api/download/models/{civ.version_id}"
   693	
   694	                    resolved.append(ResolvedDependency(
   695	                        dependency_id=dep.id,
   696	                        artifact=ResolvedArtifact(
   697	                            kind=dep.kind,
   698	                            sha256=sha256,
   699	                            size_bytes=file_size,
   700	                            provider=ArtifactProvider(
   701	                                name=ProviderName.CIVITAI,
   702	                                model_id=civ.model_id,
   703	                                version_id=civ.version_id,
   704	                                file_id=target_file.get("id"),
   705	                                filename=target_file.get("name"),
   706	                            ),
   707	                            download=ArtifactDownload(urls=[download_url]),
   708	                            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
   709	                        ),
   710	                    ))
   711	                    logger.debug(f"[PackService] Resolved dependency '{dep.id}' for version {civ.version_id}")
   712	
   713	                except Exception as e:
   714	                    logger.error(f"[PackService] Failed to resolve {dep.id}: {e}")
   715	                    unresolved.append(UnresolvedDependency(
   716	                        dependency_id=dep.id,
   717	                        reason="resolution_error",
   718	                        details={"error": str(e)},
   719	                    ))
   720	
   721	            elif dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT:
   722	                try:
   723	                    config = self.layout.load_config()
   724	                    alias = config.base_model_aliases.get(dep.selector.base_model)
   725	                    if alias and alias.selector.civitai:
   726	                        resolved.append(ResolvedDependency(
   727	                            dependency_id=dep.id,
   728	                            artifact=ResolvedArtifact(
   729	                                kind=dep.kind,
   730	                                sha256=None,
   731	                                size_bytes=None,
   732	                                provider=ArtifactProvider(
   733	                                    name=ProviderName.CIVITAI,
   734	                                    model_id=alias.selector.civitai.model_id,
   735	                                    version_id=alias.selector.civitai.version_id,
   736	                                    file_id=alias.selector.civitai.file_id,
   737	                                ),
   738	                                download=ArtifactDownload(urls=[]),
   739	                                integrity=ArtifactIntegrity(sha256_verified=False),
   740	                            ),
   741	                        ))
   742	                    else:
   743	                        unresolved.append(UnresolvedDependency(
   744	                            dependency_id=dep.id,
   745	                            reason="unknown_base_model_alias",
   746	                            details={"base_model": dep.selector.base_model},
   747	                        ))
   748	                except Exception:
   749	                    unresolved.append(UnresolvedDependency(
   750	                        dependency_id=dep.id,
   751	                        reason="base_model_resolution_failed",
   752	                        details={"base_model": dep.selector.base_model},
   753	                    ))
   754	
   755	        logger.info(f"[PackService] Lock created: {len(resolved)} resolved, {len(unresolved)} unresolved")
   756	
   757	        return PackLock(
   758	            pack=pack.name,
   759	            resolved_at=datetime.now().isoformat(),
   760	            resolved=resolved,

exec
/bin/bash -lc "nl -ba src/store/pack_service.py | sed -n '1329,1360p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1329	
  1330	        # Build origin from provider
  1331	        provider = resolved.artifact.provider
  1332	        origin = BlobOrigin(
  1333	            provider=provider.name,
  1334	            model_id=provider.model_id,
  1335	            version_id=provider.version_id,
  1336	            file_id=provider.file_id,
  1337	            filename=provider.filename,
  1338	            repo_id=provider.repo_id,
  1339	        )
  1340	
  1341	        # Create manifest
  1342	        manifest = BlobManifest(
  1343	            original_filename=original_filename,
  1344	            kind=resolved.artifact.kind,
  1345	            origin=origin,
  1346	        )
  1347	
  1348	        # Write manifest (write-once)
  1349	        self.blob_store.write_manifest(sha256, manifest)

exec
/bin/bash -lc "nl -ba src/store/profile_service.py | sed -n '75,255p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    75	    def load_profile(self, profile_name: str) -> Profile:
    76	        """Load a profile by name."""
    77	        return self.layout.load_profile(profile_name)
    78	    
    79	    def load_global(self) -> Profile:
    80	        """Load the global profile."""
    81	        return self.load_profile("global")
    82	    
    83	    def get_work_profile_name(self, pack_name: str) -> str:
    84	        """Get the work profile name for a pack."""
    85	        return f"{self.WORK_PREFIX}{pack_name}"
    86	    
    87	    def is_work_profile(self, profile_name: str) -> bool:
    88	        """Check if a profile is a work profile."""
    89	        return profile_name.startswith(self.WORK_PREFIX)
    90	    
    91	    def get_pack_from_work_profile(self, profile_name: str) -> Optional[str]:
    92	        """Extract pack name from work profile name."""
    93	        if self.is_work_profile(profile_name):
    94	            return profile_name[len(self.WORK_PREFIX):]
    95	        return None
    96	    
    97	    # =========================================================================
    98	    # Work Profile Management
    99	    # =========================================================================
   100	    
   101	    def ensure_work_profile(
   102	        self,
   103	        pack_name: str,
   104	        base_profile_name: str = "global",
   105	    ) -> Tuple[Profile, bool]:
   106	        """
   107	        Ensure a work profile exists for a pack.
   108	        
   109	        Creates work__<pack> profile based on base profile, with pack moved to end.
   110	        
   111	        Args:
   112	            pack_name: Pack to create work profile for
   113	            base_profile_name: Base profile to copy from (default: global)
   114	        
   115	        Returns:
   116	            Tuple of (profile, created) where created is True if newly created
   117	        """
   118	        work_name = self.get_work_profile_name(pack_name)
   119	        
   120	        # Check if work profile already exists
   121	        if self.layout.profile_exists(work_name):
   122	            return self.layout.load_profile(work_name), False
   123	        
   124	        # Load base profile
   125	        base = self.layout.load_profile(base_profile_name)
   126	        
   127	        # Create work profile with pack at end
   128	        work = Profile(
   129	            name=work_name,
   130	            conflicts=base.conflicts,
   131	            packs=[],
   132	        )
   133	        
   134	        # Copy packs, excluding the target pack
   135	        for p in base.packs:
   136	            if p.name != pack_name:
   137	                work.packs.append(ProfilePackEntry(name=p.name))
   138	        
   139	        # Add target pack at end (last wins)
   140	        work.packs.append(ProfilePackEntry(name=pack_name))
   141	        
   142	        # Save work profile
   143	        self.layout.save_profile(work)
   144	        
   145	        return work, True
   146	    
   147	    def update_work_profile(
   148	        self,
   149	        pack_name: str,
   150	        base_profile_name: str = "global",
   151	    ) -> Profile:
   152	        """
   153	        Update or create a work profile to reflect current base profile.
   154	        
   155	        Always regenerates from base to ensure consistency.
   156	        """
   157	        work_name = self.get_work_profile_name(pack_name)
   158	        base = self.layout.load_profile(base_profile_name)
   159	        
   160	        work = Profile(
   161	            name=work_name,
   162	            conflicts=base.conflicts,
   163	            packs=[],
   164	        )
   165	        
   166	        # Copy packs, excluding the target pack
   167	        for p in base.packs:
   168	            if p.name != pack_name:
   169	                work.packs.append(ProfilePackEntry(name=p.name))
   170	        
   171	        # Add target pack at end
   172	        work.packs.append(ProfilePackEntry(name=pack_name))
   173	        
   174	        self.layout.save_profile(work)
   175	        return work
   176	    
   177	    # =========================================================================
   178	    # Use Command
   179	    # =========================================================================
   180	    
   181	    def use(
   182	        self,
   183	        pack_name: str,
   184	        ui_targets: List[str],
   185	        base_profile: str = "global",
   186	        sync: bool = True,
   187	    ) -> UseResult:
   188	        """
   189	        Execute 'use' command for a pack.
   190	        
   191	        1. Ensure pack exists
   192	        2. Create/update work profile
   193	        3. Build views for target UIs
   194	        4. Activate work profile
   195	        5. Push to runtime stack
   196	        
   197	        Args:
   198	            pack_name: Pack to use
   199	            ui_targets: List of UI names to target
   200	            base_profile: Base profile for work profile
   201	            sync: If True, build views
   202	        
   203	        Returns:
   204	            UseResult with details
   205	        """
   206	        # Verify pack exists
   207	        if not self.layout.pack_exists(pack_name):
   208	            raise ProfileNotFoundError(f"Pack not found: {pack_name}")
   209	        
   210	        # Create/update work profile
   211	        work_profile, created = self.ensure_work_profile(pack_name, base_profile)
   212	        if not created:
   213	            # Update to reflect any changes in base
   214	            work_profile = self.update_work_profile(pack_name, base_profile)
   215	        
   216	        result = UseResult(
   217	            pack=pack_name,
   218	            created_profile=work_profile.name,
   219	            ui_targets=ui_targets,
   220	            activated_profile=work_profile.name,
   221	            synced=sync,
   222	            shadowed=[],
   223	            notes=[],
   224	        )
   225	        
   226	        if created:
   227	            result.notes.append("profile_created")
   228	        else:
   229	            result.notes.append("profile_updated")
   230	        
   231	        # Load packs data for building
   232	        if sync:
   233	            packs_data = self._load_packs_for_profile(work_profile)
   234	
   235	            # Auto-restore missing blobs from backup before building views
   236	            restored = self._install_missing_blobs(packs_data)
   237	            if restored:
   238	                result.notes.append(f"restored_{len(restored)}_blobs_from_backup")
   239	
   240	            # Build and activate for each UI
   241	            for ui in ui_targets:
   242	                report = self.view_builder.build(ui, work_profile, packs_data)
   243	                result.shadowed.extend(report.shadowed)
   244	
   245	                # Activate
   246	                self.view_builder.activate(ui, work_profile.name)
   247	
   248	        # Update runtime stack (atomic operation with lock)
   249	        with self.layout.lock():
   250	            runtime = self.layout.load_runtime()
   251	            for ui in ui_targets:
   252	                runtime.push_profile(ui, work_profile.name)
   253	            self.layout.save_runtime(runtime)
   254	
   255	        return result

exec
/bin/bash -lc "nl -ba src/store/profile_service.py | sed -n '255,520p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   255	        return result
   256	    
   257	    def use_from_ui_set(
   258	        self,
   259	        pack_name: str,
   260	        ui_set_name: str,
   261	        base_profile: str = "global",
   262	        sync: bool = True,
   263	    ) -> UseResult:
   264	        """
   265	        Execute 'use' command using a UI set.
   266	        """
   267	        ui_sets = self.layout.load_ui_sets()
   268	        ui_targets = ui_sets.sets.get(ui_set_name, [])
   269	        return self.use(pack_name, ui_targets, base_profile, sync)
   270	    
   271	    # =========================================================================
   272	    # Back Command
   273	    # =========================================================================
   274	    
   275	    def back(
   276	        self,
   277	        ui_targets: List[str],
   278	        sync: bool = False,
   279	    ) -> BackResult:
   280	        """
   281	        Execute 'back' command.
   282	
   283	        1. Pop current profile from stack
   284	        2. Activate previous profile
   285	
   286	        Args:
   287	            ui_targets: List of UI names to target
   288	            sync: If True, rebuild views
   289	
   290	        Returns:
   291	            BackResult with details
   292	        """
   293	        # Handle empty UI targets
   294	        if not ui_targets:
   295	            return BackResult(
   296	                ui_targets=[],
   297	                from_profile="",
   298	                to_profile="",
   299	                synced=False,
   300	                notes=["no_ui_targets"],
   301	            )
   302	
   303	        # Atomic runtime modification with lock
   304	        with self.layout.lock():
   305	            runtime = self.layout.load_runtime()
   306	
   307	            first_ui = ui_targets[0]
   308	            from_profile = runtime.get_active_profile(first_ui)
   309	
   310	            # Pop from all target UIs
   311	            for ui in ui_targets:
   312	                runtime.pop_profile(ui)
   313	
   314	            to_profile = runtime.get_active_profile(first_ui)
   315	
   316	            # Save runtime immediately
   317	            self.layout.save_runtime(runtime)
   318	
   319	        # Build result
   320	        result = BackResult(
   321	            ui_targets=ui_targets,
   322	            from_profile=from_profile,
   323	            to_profile=to_profile,
   324	            synced=sync,
   325	            notes=[],
   326	        )
   327	
   328	        # Check if already at base
   329	        if from_profile == to_profile:
   330	            result.notes.append("already_at_base")
   331	
   332	        # Rebuild and activate if syncing (outside lock - slow operation)
   333	        if sync and to_profile:
   334	            try:
   335	                profile = self.layout.load_profile(to_profile)
   336	                packs_data = self._load_packs_for_profile(profile)
   337	
   338	                for ui in ui_targets:
   339	                    self.view_builder.build(ui, profile, packs_data)
   340	                    self.view_builder.activate(ui, to_profile)
   341	            except ProfileNotFoundError:
   342	                result.notes.append("profile_not_found")
   343	        else:
   344	            # Just activate without rebuilding
   345	            for ui in ui_targets:
   346	                try:
   347	                    self.view_builder.activate(ui, to_profile)
   348	                except Exception:
   349	                    pass  # View may not exist
   350	
   351	        return result
   352	    
   353	    def back_from_ui_set(
   354	        self,
   355	        ui_set_name: str,
   356	        sync: bool = False,
   357	    ) -> BackResult:
   358	        """
   359	        Execute 'back' command using a UI set.
   360	        """
   361	        ui_sets = self.layout.load_ui_sets()
   362	        ui_targets = ui_sets.sets.get(ui_set_name, [])
   363	        return self.back(ui_targets, sync)
   364	    
   365	    # =========================================================================
   366	    # Sync Operations
   367	    # =========================================================================
   368	    
   369	    def sync_profile(
   370	        self,
   371	        profile_name: str,
   372	        ui_targets: List[str],
   373	        install_missing: bool = True,
   374	    ) -> Dict[str, BuildReport]:
   375	        """
   376	        Sync a profile: install missing blobs and build views.
   377	        
   378	        Args:
   379	            profile_name: Profile to sync
   380	            ui_targets: List of UI names
   381	            install_missing: If True, download missing blobs
   382	        
   383	        Returns:
   384	            Dict mapping ui -> BuildReport
   385	        """
   386	        profile = self.layout.load_profile(profile_name)
   387	        packs_data = self._load_packs_for_profile(profile)
   388	        
   389	        # Install missing blobs if requested
   390	        if install_missing:
   391	            self._install_missing_blobs(packs_data)
   392	        
   393	        # Build views for each UI
   394	        reports = {}
   395	        for ui in ui_targets:
   396	            reports[ui] = self.view_builder.build(ui, profile, packs_data)
   397	            self.view_builder.activate(ui, profile_name)
   398	        
   399	        return reports
   400	    
   401	    def sync_profile_from_ui_set(
   402	        self,
   403	        profile_name: str,
   404	        ui_set_name: str,
   405	        install_missing: bool = True,
   406	    ) -> Dict[str, BuildReport]:
   407	        """
   408	        Sync a profile using a UI set.
   409	        """
   410	        ui_sets = self.layout.load_ui_sets()
   411	        ui_targets = ui_sets.sets.get(ui_set_name, [])
   412	        return self.sync_profile(profile_name, ui_targets, install_missing)
   413	    
   414	    # =========================================================================
   415	    # Global Profile Management
   416	    # =========================================================================
   417	    
   418	    def add_pack_to_global(self, pack_name: str) -> Profile:
   419	        """
   420	        Add a pack to the global profile.
   421	        
   422	        Returns:
   423	            Updated global profile
   424	        """
   425	        global_profile = self.load_global()
   426	        global_profile.add_pack(pack_name)
   427	        self.layout.save_profile(global_profile)
   428	        return global_profile
   429	    
   430	    def remove_pack_from_global(self, pack_name: str) -> Profile:
   431	        """
   432	        Remove a pack from the global profile.
   433	        
   434	        Returns:
   435	            Updated global profile
   436	        """
   437	        global_profile = self.load_global()
   438	        global_profile.remove_pack(pack_name)
   439	        self.layout.save_profile(global_profile)
   440	        return global_profile
   441	    
   442	    # =========================================================================
   443	    # Status
   444	    # =========================================================================
   445	    
   446	    def get_active_profiles(self, ui_names: List[str]) -> Dict[str, str]:
   447	        """
   448	        Get active profile for each UI.
   449	        
   450	        Returns:
   451	            Dict mapping ui_name -> profile_name
   452	        """
   453	        runtime = self.layout.load_runtime()
   454	        return {ui: runtime.get_active_profile(ui) for ui in ui_names}
   455	    
   456	    def get_runtime_stacks(self, ui_names: List[str]) -> Dict[str, List[str]]:
   457	        """
   458	        Get runtime stacks for each UI.
   459	        
   460	        Returns:
   461	            Dict mapping ui_name -> stack (list of profile names)
   462	        """
   463	        runtime = self.layout.load_runtime()
   464	        return {
   465	            ui: runtime.ui.get(ui, Runtime.create_default([ui]).ui[ui]).stack
   466	            for ui in ui_names
   467	        }
   468	    
   469	    # =========================================================================
   470	    # Helpers
   471	    # =========================================================================
   472	    
   473	    def _load_packs_for_profile(
   474	        self,
   475	        profile: Profile,
   476	    ) -> Dict[str, Tuple[Pack, Optional[PackLock]]]:
   477	        """
   478	        Load all packs referenced by a profile.
   479	        
   480	        Returns:
   481	            Dict mapping pack_name -> (pack, lock)
   482	        """
   483	        packs_data = {}
   484	        for pack_entry in profile.packs:
   485	            try:
   486	                pack = self.layout.load_pack(pack_entry.name)
   487	                lock = self.layout.load_pack_lock(pack_entry.name)
   488	                packs_data[pack_entry.name] = (pack, lock)
   489	            except Exception:
   490	                continue
   491	        return packs_data
   492	    
   493	    def _install_missing_blobs(
   494	        self,
   495	        packs_data: Dict[str, Tuple[Pack, Optional[PackLock]]],
   496	    ) -> List[str]:
   497	        """
   498	        Install missing blobs for packs.
   499	
   500	        Tries to restore from backup first, then downloads from URL if needed.
   501	
   502	        Returns:
   503	            List of installed blob SHA256 hashes
   504	        """
   505	        installed = []
   506	
   507	        for pack_name, (pack, lock) in packs_data.items():
   508	            if lock is None:
   509	                continue
   510	
   511	            for resolved in lock.resolved:
   512	                sha256 = resolved.artifact.sha256
   513	                if not sha256:
   514	                    continue
   515	
   516	                if self.blob_store.blob_exists(sha256):
   517	                    continue
   518	
   519	                # Try restore from backup first (auto-restore feature)
   520	                if self.backup_service and self.backup_service.is_connected():

exec
/bin/bash -lc "nl -ba src/store/view_builder.py | sed -n '51,150p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    51	@dataclass
    52	class ViewEntry:
    53	    """A single entry in a view plan."""
    54	    pack_name: str
    55	    dependency_id: str
    56	    kind: AssetKind
    57	    expose_filename: str
    58	    sha256: str
    59	    dst_relpath: str  # Relative path within the view
    60	
    61	
    62	@dataclass
    63	class ViewPlan:
    64	    """Plan for building a view."""
    65	    ui: str
    66	    profile: str
    67	    entries: List[ViewEntry] = field(default_factory=list)
    68	    shadowed: List[ShadowedEntry] = field(default_factory=list)
    69	    missing_blobs: List[Tuple[str, str, str]] = field(default_factory=list)  # (pack, dep_id, sha256)
    70	    
    71	    def add_entry(
    72	        self,
    73	        pack_name: str,
    74	        dependency_id: str,
    75	        kind: AssetKind,
    76	        expose_filename: str,
    77	        sha256: str,
    78	        kind_map: UIKindMap,
    79	    ) -> Optional[ShadowedEntry]:
    80	        """
    81	        Add an entry to the plan.
    82	        
    83	        Returns ShadowedEntry if this entry shadows an existing one.
    84	        """
    85	        kind_path = kind_map.get_path(kind)
    86	        if not kind_path:
    87	            kind_path = f"models/{kind.value}"
    88	        
    89	        dst_relpath = f"{kind_path}/{expose_filename}"
    90	        
    91	        # Check for existing entry with same destination
    92	        for i, existing in enumerate(self.entries):
    93	            if existing.dst_relpath == dst_relpath:
    94	                # Shadow the existing entry
    95	                shadowed = ShadowedEntry(
    96	                    ui=self.ui,
    97	                    dst_relpath=dst_relpath,
    98	                    winner_pack=pack_name,
    99	                    loser_pack=existing.pack_name,
   100	                )
   101	                self.shadowed.append(shadowed)
   102	                
   103	                # Replace with new entry
   104	                self.entries[i] = ViewEntry(
   105	                    pack_name=pack_name,
   106	                    dependency_id=dependency_id,
   107	                    kind=kind,
   108	                    expose_filename=expose_filename,
   109	                    sha256=sha256,
   110	                    dst_relpath=dst_relpath,
   111	                )
   112	                return shadowed
   113	        
   114	        # No conflict, add new entry
   115	        self.entries.append(ViewEntry(
   116	            pack_name=pack_name,
   117	            dependency_id=dependency_id,
   118	            kind=kind,
   119	            expose_filename=expose_filename,
   120	            sha256=sha256,
   121	            dst_relpath=dst_relpath,
   122	        ))
   123	        return None
   124	
   125	
   126	@dataclass
   127	class BuildReport:
   128	    """Report from a view build operation."""
   129	    ui: str
   130	    profile: str
   131	    entries_created: int
   132	    shadowed: List[ShadowedEntry] = field(default_factory=list)
   133	    missing_blobs: List[Tuple[str, str, str]] = field(default_factory=list)
   134	    errors: List[str] = field(default_factory=list)
   135	
   136	
   137	def create_symlink(source: Path, target: Path) -> None:
   138	    """
   139	    Create a symlink, handling platform differences.
   140	    
   141	    On Windows, attempts symlink first, then hardlink, then copy.
   142	    On Linux/Mac, uses symlink.
   143	    
   144	    Args:
   145	        source: The symlink to create
   146	        target: What the symlink should point to
   147	    """
   148	    source.parent.mkdir(parents=True, exist_ok=True)
   149	    
   150	    # Remove existing if present

exec
/bin/bash -lc "nl -ba src/store/view_builder.py | sed -n '202,350p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   202	    def config(self) -> StoreConfig:
   203	        """Get store configuration, loading if necessary."""
   204	        if self._config is None:
   205	            self._config = self.layout.load_config()
   206	        return self._config
   207	    
   208	    # =========================================================================
   209	    # Plan Building
   210	    # =========================================================================
   211	    
   212	    def compute_plan(
   213	        self,
   214	        ui: str,
   215	        profile: Profile,
   216	        packs: Dict[str, Tuple[Pack, Optional[PackLock]]],
   217	    ) -> ViewPlan:
   218	        """
   219	        Compute a view plan for a UI and profile.
   220	        
   221	        Args:
   222	            ui: UI name (e.g., "comfyui")
   223	            profile: Profile to build
   224	            packs: Dict mapping pack_name -> (pack, lock)
   225	        
   226	        Returns:
   227	            ViewPlan with entries and shadowed info
   228	        """
   229	        plan = ViewPlan(ui=ui, profile=profile.name)
   230	        
   231	        # Get kind map for this UI
   232	        kind_map = self.config.ui.kind_map.get(ui)
   233	        if not kind_map:
   234	            kind_map = UIKindMap()  # Use defaults
   235	        
   236	        # Process packs in order (last wins)
   237	        for pack_entry in profile.packs:
   238	            pack_name = pack_entry.name
   239	            if pack_name not in packs:
   240	                continue
   241	            
   242	            pack, lock = packs[pack_name]
   243	            if lock is None:
   244	                continue
   245	            
   246	            # Process each resolved dependency
   247	            for resolved in lock.resolved:
   248	                # Find the dependency definition in pack
   249	                dep = pack.get_dependency(resolved.dependency_id)
   250	                if dep is None:
   251	                    continue
   252	                
   253	                sha256 = resolved.artifact.sha256
   254	                if not sha256:
   255	                    continue
   256	                
   257	                # Check if blob exists
   258	                if not self.blob_store.blob_exists(sha256):
   259	                    plan.missing_blobs.append((pack_name, dep.id, sha256))
   260	                    continue
   261	                
   262	                # Add to plan (handles shadowing)
   263	                plan.add_entry(
   264	                    pack_name=pack_name,
   265	                    dependency_id=dep.id,
   266	                    kind=dep.kind,
   267	                    expose_filename=dep.expose.filename,
   268	                    sha256=sha256,
   269	                    kind_map=kind_map,
   270	                )
   271	        
   272	        return plan
   273	    
   274	    # =========================================================================
   275	    # View Building
   276	    # =========================================================================
   277	    
   278	    def build(
   279	        self,
   280	        ui: str,
   281	        profile: Profile,
   282	        packs: Dict[str, Tuple[Pack, Optional[PackLock]]],
   283	    ) -> BuildReport:
   284	        """
   285	        Build view for a UI and profile.
   286	        
   287	        Uses atomic build: creates in staging directory, then replaces.
   288	        
   289	        Args:
   290	            ui: UI name
   291	            profile: Profile to build
   292	            packs: Dict mapping pack_name -> (pack, lock)
   293	        
   294	        Returns:
   295	            BuildReport with results
   296	        """
   297	        # Compute plan
   298	        plan = self.compute_plan(ui, profile, packs)
   299	        
   300	        report = BuildReport(
   301	            ui=ui,
   302	            profile=profile.name,
   303	            entries_created=0,
   304	            shadowed=plan.shadowed,
   305	            missing_blobs=plan.missing_blobs,
   306	        )
   307	        
   308	        # Build in staging directory
   309	        staging_dir = self.layout.tmp_path / "views" / ui / f"{profile.name}.new"
   310	        final_dir = self.layout.view_profile_path(ui, profile.name)
   311	        
   312	        # Clean staging
   313	        if staging_dir.exists():
   314	            shutil.rmtree(staging_dir)
   315	        staging_dir.mkdir(parents=True, exist_ok=True)
   316	        
   317	        try:
   318	            # Create symlinks
   319	            for entry in plan.entries:
   320	                blob_path = self.blob_store.blob_path(entry.sha256)
   321	                link_path = staging_dir / entry.dst_relpath
   322	                
   323	                try:
   324	                    create_symlink(link_path, blob_path)
   325	                    report.entries_created += 1
   326	                except Exception as e:
   327	                    report.errors.append(f"Failed to create link {entry.dst_relpath}: {e}")
   328	            
   329	            # Atomic replace
   330	            if final_dir.exists():
   331	                # Move old to backup, then replace
   332	                backup_dir = final_dir.with_suffix(".old")
   333	                if backup_dir.exists():
   334	                    shutil.rmtree(backup_dir)
   335	                final_dir.rename(backup_dir)
   336	                staging_dir.rename(final_dir)
   337	                shutil.rmtree(backup_dir)
   338	            else:
   339	                final_dir.parent.mkdir(parents=True, exist_ok=True)
   340	                staging_dir.rename(final_dir)
   341	            
   342	        except Exception as e:
   343	            report.errors.append(f"Failed to finalize build: {e}")
   344	            # Clean up staging
   345	            if staging_dir.exists():
   346	                shutil.rmtree(staging_dir)
   347	        
   348	        return report
   349	    
   350	    def build_for_ui_set(

exec
/bin/bash -lc "nl -ba src/store/view_builder.py | sed -n '350,527p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   350	    def build_for_ui_set(
   351	        self,
   352	        ui_set_name: str,
   353	        profile: Profile,
   354	        packs: Dict[str, Tuple[Pack, Optional[PackLock]]],
   355	    ) -> Dict[str, BuildReport]:
   356	        """
   357	        Build views for all UIs in a set.
   358	        
   359	        Returns:
   360	            Dict mapping ui_name -> BuildReport
   361	        """
   362	        ui_sets = self.layout.load_ui_sets()
   363	        ui_names = ui_sets.sets.get(ui_set_name, [])
   364	        
   365	        reports = {}
   366	        for ui in ui_names:
   367	            reports[ui] = self.build(ui, profile, packs)
   368	        
   369	        return reports
   370	    
   371	    # =========================================================================
   372	    # Activation
   373	    # =========================================================================
   374	    
   375	    def activate(self, ui: str, profile_name: str) -> None:
   376	        """
   377	        Activate a profile for a UI by updating the 'active' symlink.
   378	        
   379	        Args:
   380	            ui: UI name
   381	            profile_name: Profile to activate
   382	        """
   383	        active_path = self.layout.view_active_path(ui)
   384	        profile_path = self.layout.view_profile_path(ui, profile_name)
   385	        
   386	        # Ensure profile view exists
   387	        if not profile_path.exists():
   388	            raise ViewBuildError(f"Profile view not found: {ui}/{profile_name}")
   389	        
   390	        # Create active symlink pointing to profile
   391	        # Use relative path for portability
   392	        active_path.parent.mkdir(parents=True, exist_ok=True)
   393	        
   394	        # Atomic update: create .new, then replace
   395	        active_new = active_path.with_suffix(".new")
   396	        try:
   397	            # Remove if exists
   398	            if active_new.exists() or active_new.is_symlink():
   399	                active_new.unlink()
   400	            
   401	            # Create relative symlink
   402	            rel_target = Path("profiles") / profile_name
   403	            active_new.symlink_to(rel_target)
   404	            
   405	            # Atomic replace
   406	            active_new.replace(active_path)
   407	        except Exception as e:
   408	            active_new.unlink(missing_ok=True)
   409	            raise ViewBuildError(f"Failed to activate profile: {e}") from e
   410	    
   411	    def activate_for_ui_set(self, ui_set_name: str, profile_name: str) -> List[str]:
   412	        """
   413	        Activate a profile for all UIs in a set.
   414	        
   415	        Returns:
   416	            List of UI names that were activated
   417	        """
   418	        ui_sets = self.layout.load_ui_sets()
   419	        ui_names = ui_sets.sets.get(ui_set_name, [])
   420	        
   421	        activated = []
   422	        for ui in ui_names:
   423	            try:
   424	                self.activate(ui, profile_name)
   425	                activated.append(ui)
   426	            except ViewBuildError:
   427	                pass  # Profile may not be built for this UI yet
   428	        
   429	        return activated
   430	    
   431	    def get_active_profile(self, ui: str) -> Optional[str]:
   432	        """
   433	        Get the currently active profile for a UI.
   434	        
   435	        Returns:
   436	            Profile name, or None if no active profile
   437	        """
   438	        active_path = self.layout.view_active_path(ui)
   439	        if not active_path.is_symlink():
   440	            return None
   441	        
   442	        # Read the symlink target
   443	        target = os.readlink(active_path)
   444	        # Extract profile name from "profiles/<name>"
   445	        parts = Path(target).parts
   446	        if len(parts) >= 2 and parts[0] == "profiles":
   447	            return parts[1]
   448	        return None
   449	    
   450	    # =========================================================================
   451	    # Cleanup
   452	    # =========================================================================
   453	    
   454	    def remove_profile_view(self, ui: str, profile_name: str) -> bool:
   455	        """
   456	        Remove a profile view.
   457	        
   458	        Returns:
   459	            True if removed, False if didn't exist
   460	        """
   461	        profile_path = self.layout.view_profile_path(ui, profile_name)
   462	        if profile_path.exists():
   463	            shutil.rmtree(profile_path)
   464	            return True
   465	        return False
   466	    
   467	    def clean_orphaned_views(self, ui: str) -> List[str]:
   468	        """
   469	        Remove views for profiles that no longer exist.
   470	        
   471	        Returns:
   472	            List of removed profile names
   473	        """
   474	        profiles_path = self.layout.view_profiles_path(ui)
   475	        if not profiles_path.exists():
   476	            return []
   477	        
   478	        existing_profiles = set(self.layout.list_profiles())
   479	        removed = []
   480	        
   481	        for profile_dir in profiles_path.iterdir():
   482	            if profile_dir.is_dir() and profile_dir.name not in existing_profiles:
   483	                shutil.rmtree(profile_dir)
   484	                removed.append(profile_dir.name)
   485	        
   486	        return removed
   487	    
   488	    # =========================================================================
   489	    # Status
   490	    # =========================================================================
   491	    
   492	    def list_view_profiles(self, ui: str) -> List[str]:
   493	        """List all built profile views for a UI."""
   494	        profiles_path = self.layout.view_profiles_path(ui)
   495	        if not profiles_path.exists():
   496	            return []
   497	        return [d.name for d in profiles_path.iterdir() if d.is_dir()]
   498	    
   499	    def get_view_entries(self, ui: str, profile_name: str) -> List[ViewEntry]:
   500	        """
   501	        Get all entries in a view.
   502	        
   503	        Note: This reads the filesystem, not a plan.
   504	        """
   505	        profile_path = self.layout.view_profile_path(ui, profile_name)
   506	        if not profile_path.exists():
   507	            return []
   508	        
   509	        entries = []
   510	        for root, dirs, files in os.walk(profile_path):
   511	            for name in files:
   512	                link_path = Path(root) / name
   513	                if link_path.is_symlink():
   514	                    target = link_path.resolve()
   515	                    # Extract sha256 from blob path
   516	                    sha256 = target.name if target.parent.parent.name == "sha256" else ""
   517	                    rel_path = link_path.relative_to(profile_path)
   518	                    entries.append(ViewEntry(
   519	                        pack_name="",  # Unknown from filesystem
   520	                        dependency_id="",  # Unknown from filesystem
   521	                        kind=AssetKind.UNKNOWN,
   522	                        expose_filename=name,
   523	                        sha256=sha256,
   524	                        dst_relpath=str(rel_path),
   525	                    ))
   526	        
   527	        return entries

exec
/bin/bash -lc "nl -ba src/store/ui_attach.py | sed -n '34,180p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    34	@dataclass
    35	class AttachResult:
    36	    """Result of attaching UI to store views."""
    37	    ui: str
    38	    success: bool
    39	    method: str  # "symlink", "extra_model_paths", "skipped", "detach"
    40	    created: List[str] = field(default_factory=list)
    41	    errors: List[str] = field(default_factory=list)
    42	    config_path: Optional[str] = None  # For extra_model_paths method
    43	
    44	
    45	class UIAttacher:
    46	    """
    47	    Attaches Synapse store views to UI installations.
    48	    
    49	    For ComfyUI: Generates extra_model_paths.yaml (recommended)
    50	    For A1111/Forge/SD.Next: Creates symlinks in model directories
    51	    """
    52	    
    53	    def __init__(
    54	        self,
    55	        layout,  # StoreLayout
    56	        ui_roots: Dict[str, Path],
    57	        config: Optional[StoreConfig] = None,
    58	    ):
    59	        """
    60	        Initialize UI attacher.
    61	        
    62	        Args:
    63	            layout: Store layout instance
    64	            ui_roots: Dict mapping ui_name -> installation path
    65	            config: Store configuration (for UIKindMap). If None, uses defaults.
    66	        """
    67	        self.layout = layout
    68	        self.ui_roots = {k: Path(v).expanduser() for k, v in ui_roots.items()}
    69	        self._config = config
    70	    
    71	    def _get_kind_map(self, ui_name: str) -> UIKindMap:
    72	        """Get UIKindMap for a UI (from config or defaults)."""
    73	        if self._config and self._config.ui.kind_map:
    74	            kind_map = self._config.ui.kind_map.get(ui_name)
    75	            if kind_map:
    76	                return kind_map
    77	        
    78	        # Fall back to defaults
    79	        defaults = UIConfig.get_default_kind_maps()
    80	        return defaults.get(ui_name, UIKindMap())
    81	    
    82	    def get_active_view_path(self, ui_name: str) -> Optional[Path]:
    83	        """Get path to active view for a UI (resolved if symlink)."""
    84	        active_path = self.layout.view_active_path(ui_name)
    85	        if active_path.exists():
    86	            # Resolve symlink to get actual path
    87	            return active_path.resolve() if active_path.is_symlink() else active_path
    88	        return None
    89	    
    90	    # =========================================================================
    91	    # ComfyUI: extra_model_paths.yaml method (PREFERRED)
    92	    # =========================================================================
    93	    
    94	    def generate_extra_model_paths_yaml(self, ui_name: str = "comfyui") -> Dict[str, Any]:
    95	        """
    96	        Generate extra_model_paths.yaml content for ComfyUI.
    97	        
    98	        This is the PREFERRED method for ComfyUI because it makes models
    99	        appear at root level (not in subfolder), which is critical for
   100	        Civitai generation data compatibility.
   101	        
   102	        Returns:
   103	            Dict ready to be written as YAML
   104	        """
   105	        ui_name = ui_name.lower()
   106	        active_view = self.get_active_view_path(ui_name)
   107	        
   108	        if active_view is None:
   109	            return {}
   110	        
   111	        kind_map = self._get_kind_map(ui_name)
   112	        
   113	        # Build paths dict
   114	        # ComfyUI extra_model_paths format:
   115	        # synapse:
   116	        #     base_path: /path/to/view
   117	        #     checkpoints: models/checkpoints
   118	        #     loras: models/loras
   119	        #     ...
   120	        
   121	        paths = {}
   122	        
   123	        for kind in AssetKind:
   124	            kind_path = kind_map.get_path(kind)
   125	            if not kind_path:
   126	                continue
   127	            
   128	            view_kind_path = active_view / kind_path
   129	            if view_kind_path.exists():
   130	                # Map kind to ComfyUI folder name
   131	                comfy_name = self._kind_to_comfyui_name(kind)
   132	                if comfy_name:
   133	                    paths[comfy_name] = str(view_kind_path)
   134	        
   135	        if not paths:
   136	            return {}
   137	        
   138	        return {
   139	            "synapse": paths
   140	        }
   141	    
   142	    def _kind_to_comfyui_name(self, kind: AssetKind) -> Optional[str]:
   143	        """Map AssetKind to ComfyUI extra_model_paths key name."""
   144	        mapping = {
   145	            AssetKind.CHECKPOINT: "checkpoints",
   146	            AssetKind.LORA: "loras",
   147	            AssetKind.VAE: "vae",
   148	            AssetKind.EMBEDDING: "embeddings",
   149	            AssetKind.CONTROLNET: "controlnet",
   150	            AssetKind.UPSCALER: "upscale_models",
   151	            AssetKind.CLIP: "clip",
   152	            AssetKind.TEXT_ENCODER: "text_encoders",
   153	            AssetKind.DIFFUSION_MODEL: "diffusion_models",
   154	            AssetKind.UNET: "unet",
   155	        }
   156	        return mapping.get(kind)
   157	    
   158	    def attach_comfyui_yaml(self, output_path: Optional[Path] = None) -> AttachResult:
   159	        """
   160	        Attach ComfyUI by patching extra_model_paths.yaml directly.
   161	        
   162	        This patches ComfyUI's extra_model_paths.yaml in place:
   163	        1. Creates backup (once): extra_model_paths.yaml.synapse.bak
   164	        2. Adds/updates 'synapse:' section with paths to active view
   165	        3. Preserves all other content in the file
   166	        
   167	        Args:
   168	            output_path: Path to extra_model_paths.yaml. If None, uses comfyui_root/extra_model_paths.yaml
   169	        
   170	        Returns:
   171	            AttachResult with config_path set
   172	        """
   173	        result = AttachResult(ui="comfyui", success=True, method="extra_model_paths")
   174	        
   175	        # Get ComfyUI root
   176	        comfyui_root = self.ui_roots.get("comfyui")
   177	        if comfyui_root is None:
   178	            result.success = False
   179	            result.errors.append("No ComfyUI root configured")
   180	            return result

exec
/bin/bash -lc "nl -ba src/store/ui_attach.py | sed -n '180,585p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   180	            return result
   181	        
   182	        if not comfyui_root.exists():
   183	            result.success = False
   184	            result.errors.append(f"ComfyUI root does not exist: {comfyui_root}")
   185	            return result
   186	        
   187	        # Target file path
   188	        if output_path is None:
   189	            output_path = comfyui_root / "extra_model_paths.yaml"
   190	        
   191	        backup_path = output_path.parent / f"{output_path.name}.synapse.bak"
   192	        
   193	        # Generate synapse section content
   194	        synapse_content = self.generate_extra_model_paths_yaml("comfyui")
   195	        
   196	        if not synapse_content:
   197	            result.success = False
   198	            result.errors.append("No active view or no models to attach")
   199	            return result
   200	        
   201	        try:
   202	            # Load existing content or start fresh
   203	            existing_content = {}
   204	            if output_path.exists():
   205	                # Create backup ONLY if it doesn't exist yet (preserve original)
   206	                if not backup_path.exists():
   207	                    import shutil
   208	                    shutil.copy2(output_path, backup_path)
   209	                    result.created.append(f"Backup: {backup_path}")
   210	                    logger.info(f"[comfyui] Created backup: {backup_path}")
   211	                
   212	                # Load existing YAML
   213	                with open(output_path, "r") as f:
   214	                    content = f.read()
   215	                    if content.strip():
   216	                        existing_content = yaml.safe_load(content) or {}
   217	            
   218	            # Merge: update synapse section, preserve everything else
   219	            existing_content["synapse"] = synapse_content["synapse"]
   220	            
   221	            # Write back
   222	            with open(output_path, "w") as f:
   223	                yaml.dump(existing_content, f, default_flow_style=False, sort_keys=False)
   224	            
   225	            result.config_path = str(output_path)
   226	            result.created.append(f"Updated: {output_path}")
   227	            logger.info(f"[comfyui] Patched extra_model_paths.yaml with synapse section")
   228	            
   229	        except Exception as e:
   230	            result.success = False
   231	            result.errors.append(f"Failed to patch YAML: {e}")
   232	            logger.error(f"[comfyui] Failed to patch: {e}")
   233	        
   234	        return result
   235	    
   236	    def detach_comfyui_yaml(self) -> AttachResult:
   237	        """
   238	        Detach ComfyUI by restoring original extra_model_paths.yaml from backup.
   239	        
   240	        Returns:
   241	            AttachResult
   242	        """
   243	        result = AttachResult(ui="comfyui", success=True, method="detach")
   244	        
   245	        comfyui_root = self.ui_roots.get("comfyui")
   246	        if comfyui_root is None:
   247	            return result  # Nothing to detach
   248	        
   249	        yaml_path = comfyui_root / "extra_model_paths.yaml"
   250	        backup_path = yaml_path.parent / f"{yaml_path.name}.synapse.bak"
   251	        
   252	        try:
   253	            if backup_path.exists():
   254	                # Restore from backup (byte-identical)
   255	                import shutil
   256	                shutil.copy2(backup_path, yaml_path)
   257	                backup_path.unlink()
   258	                result.created.append(f"Restored: {yaml_path}")
   259	                logger.info(f"[comfyui] Restored original extra_model_paths.yaml from backup")
   260	            elif yaml_path.exists():
   261	                # No backup but file exists - just remove synapse section
   262	                with open(yaml_path, "r") as f:
   263	                    content = yaml.safe_load(f) or {}
   264	                
   265	                if "synapse" in content:
   266	                    del content["synapse"]
   267	                    
   268	                    with open(yaml_path, "w") as f:
   269	                        if content:
   270	                            yaml.dump(content, f, default_flow_style=False, sort_keys=False)
   271	                        # If empty, just leave empty file
   272	                    
   273	                    result.created.append(f"Removed synapse section from: {yaml_path}")
   274	                    logger.info(f"[comfyui] Removed synapse section (no backup found)")
   275	        except Exception as e:
   276	            result.errors.append(f"Failed to restore: {e}")
   277	            logger.error(f"[comfyui] Detach failed: {e}")
   278	        
   279	        return result
   280	    
   281	    # =========================================================================
   282	    # Symlink method (for A1111/Forge/SD.Next)
   283	    # =========================================================================
   284	    
   285	    def attach(self, ui_name: str, use_yaml: bool = False) -> AttachResult:
   286	        """
   287	        Attach a UI to its Synapse view.
   288	        
   289	        For ComfyUI with use_yaml=True: Uses extra_model_paths.yaml method
   290	        For others: Creates per-kind symlinks: UI/<kind_path>/synapse -> view/active/<kind_path>
   291	        
   292	        Args:
   293	            ui_name: Name of UI (comfyui, forge, a1111, sdnext)
   294	            use_yaml: For ComfyUI, use extra_model_paths.yaml instead of symlinks
   295	        
   296	        Returns:
   297	            AttachResult with status and created symlinks
   298	        """
   299	        ui_name = ui_name.lower()
   300	        
   301	        # For ComfyUI with yaml option
   302	        if ui_name == "comfyui" and use_yaml:
   303	            return self.attach_comfyui_yaml()
   304	        
   305	        result = AttachResult(ui=ui_name, success=True, method="symlink")
   306	        
   307	        # Get UI root
   308	        ui_root = self.ui_roots.get(ui_name)
   309	        if ui_root is None:
   310	            result.success = False
   311	            result.method = "skipped"
   312	            result.errors.append(f"No root configured for {ui_name}")
   313	            return result
   314	        
   315	        if not ui_root.exists():
   316	            result.success = False
   317	            result.method = "skipped"
   318	            result.errors.append(f"UI root does not exist: {ui_root}")
   319	            return result
   320	        
   321	        # Get active view path
   322	        active_view = self.get_active_view_path(ui_name)
   323	        if active_view is None:
   324	            result.success = False
   325	            result.method = "skipped"
   326	            result.errors.append(f"No active view for {ui_name}")
   327	            return result
   328	        
   329	        # Get kind map for this UI
   330	        kind_map = self._get_kind_map(ui_name)
   331	        
   332	        # Create symlinks for each asset kind
   333	        for kind in AssetKind:
   334	            kind_path = kind_map.get_path(kind)
   335	            if not kind_path:
   336	                continue
   337	            
   338	            # Source in view: views/<ui>/active/<kind_path>
   339	            view_kind_path = active_view / kind_path
   340	            
   341	            # Skip if this kind doesn't exist in the view
   342	            if not view_kind_path.exists():
   343	                continue
   344	            
   345	            # Target directory in UI: <ui_root>/<kind_path>
   346	            ui_kind_dir = ui_root / kind_path
   347	            
   348	            # Ensure parent directory exists
   349	            ui_kind_dir.mkdir(parents=True, exist_ok=True)
   350	            
   351	            # Synapse symlink location: <ui_root>/<kind_path>/synapse
   352	            synapse_link = ui_kind_dir / "synapse"
   353	            
   354	            try:
   355	                # Remove existing symlink if present
   356	                if synapse_link.is_symlink():
   357	                    synapse_link.unlink()
   358	                elif synapse_link.exists():
   359	                    # Real directory - don't overwrite
   360	                    result.errors.append(
   361	                        f"Cannot create symlink - real directory exists: {synapse_link}"
   362	                    )
   363	                    continue
   364	                
   365	                # Create symlink
   366	                synapse_link.symlink_to(view_kind_path)
   367	                result.created.append(str(synapse_link))
   368	                logger.info(f"[{ui_name}] Created: {synapse_link} -> {view_kind_path}")
   369	                
   370	            except OSError as e:
   371	                result.errors.append(f"Failed to create {synapse_link}: {e}")
   372	                result.success = False
   373	        
   374	        if not result.created and not result.errors:
   375	            result.errors.append("No kinds found in active view to attach")
   376	            result.success = False
   377	        
   378	        return result
   379	    
   380	    def attach_all(
   381	        self,
   382	        ui_targets: Optional[List[str]] = None,
   383	        comfyui_use_yaml: bool = True,  # Default to YAML for ComfyUI
   384	    ) -> Dict[str, AttachResult]:
   385	        """
   386	        Attach all configured UIs to their views.
   387	        
   388	        Args:
   389	            ui_targets: List of UIs to attach. If None, attach all configured.
   390	            comfyui_use_yaml: Use extra_model_paths.yaml for ComfyUI (recommended)
   391	        
   392	        Returns:
   393	            Dict mapping ui_name -> AttachResult
   394	        """
   395	        if ui_targets is None:
   396	            ui_targets = list(self.ui_roots.keys())
   397	        
   398	        results = {}
   399	        for ui in ui_targets:
   400	            use_yaml = comfyui_use_yaml and ui.lower() == "comfyui"
   401	            results[ui] = self.attach(ui, use_yaml=use_yaml)
   402	        
   403	        return results
   404	    
   405	    def detach(self, ui_name: str) -> AttachResult:
   406	        """
   407	        Detach a UI from Synapse.
   408	        
   409	        For ComfyUI: Restores original extra_model_paths.yaml AND removes symlinks
   410	        For others: Removes synapse symlinks
   411	        
   412	        Args:
   413	            ui_name: Name of UI to detach
   414	        
   415	        Returns:
   416	            AttachResult with status
   417	        """
   418	        ui_name = ui_name.lower()
   419	        result = AttachResult(ui=ui_name, success=True, method="detach")
   420	        
   421	        ui_root = self.ui_roots.get(ui_name)
   422	        if ui_root is None:
   423	            return result  # Nothing to detach
   424	        
   425	        if not ui_root.exists():
   426	            return result  # Nothing to detach
   427	        
   428	        # For ComfyUI, also restore YAML
   429	        if ui_name == "comfyui":
   430	            yaml_result = self.detach_comfyui_yaml()
   431	            result.created.extend(yaml_result.created)
   432	            result.errors.extend(yaml_result.errors)
   433	        
   434	        # Always remove symlinks (for both ComfyUI and others)
   435	        kind_map = self._get_kind_map(ui_name)
   436	        
   437	        for kind in AssetKind:
   438	            kind_path = kind_map.get_path(kind)
   439	            if not kind_path:
   440	                continue
   441	            
   442	            synapse_link = ui_root / kind_path / "synapse"
   443	            
   444	            if synapse_link.is_symlink():
   445	                try:
   446	                    synapse_link.unlink()
   447	                    result.created.append(f"Removed: {synapse_link}")
   448	                    logger.info(f"[{ui_name}] Removed: {synapse_link}")
   449	                except OSError as e:
   450	                    result.errors.append(f"Failed to remove {synapse_link}: {e}")
   451	        
   452	        return result
   453	    
   454	    def status(self, ui_name: str) -> Dict[str, Any]:
   455	        """
   456	        Get attachment status for a UI.
   457	        
   458	        Returns dict with:
   459	        - attached: bool (synapse section in yaml OR symlinks exist)
   460	        - method: "symlink" | "extra_model_paths" | "none"
   461	        - symlinks: list of existing synapse symlinks
   462	        - yaml_config: path to YAML config if exists
   463	        - view_exists: bool
   464	        - has_backup: bool (for ComfyUI - whether backup exists)
   465	        """
   466	        ui_name = ui_name.lower()
   467	        
   468	        status_info = {
   469	            "ui": ui_name,
   470	            "attached": False,
   471	            "method": "none",
   472	            "symlinks": [],
   473	            "yaml_config": None,
   474	            "view_exists": False,
   475	            "has_backup": False,
   476	            "error": None,
   477	        }
   478	        
   479	        ui_root = self.ui_roots.get(ui_name)
   480	        if ui_root is None:
   481	            status_info["error"] = f"No root configured for {ui_name}"
   482	            return status_info
   483	        
   484	        if not ui_root.exists():
   485	            status_info["error"] = f"UI root does not exist: {ui_root}"
   486	            return status_info
   487	        
   488	        # Check view exists
   489	        active_view = self.get_active_view_path(ui_name)
   490	        status_info["view_exists"] = active_view is not None and active_view.exists()
   491	        
   492	        # Check YAML config (for ComfyUI) - check in ComfyUI root, not store root
   493	        if ui_name == "comfyui":
   494	            yaml_path = ui_root / "extra_model_paths.yaml"
   495	            backup_path = yaml_path.parent / f"{yaml_path.name}.synapse.bak"
   496	            
   497	            status_info["has_backup"] = backup_path.exists()
   498	            
   499	            if yaml_path.exists():
   500	                try:
   501	                    with open(yaml_path, "r") as f:
   502	                        content = yaml.safe_load(f) or {}
   503	                    
   504	                    # Check if synapse section exists
   505	                    if "synapse" in content:
   506	                        status_info["yaml_config"] = str(yaml_path)
   507	                        status_info["attached"] = True
   508	                        status_info["method"] = "extra_model_paths"
   509	                except Exception:
   510	                    pass  # Ignore parse errors
   511	        
   512	        # Get kind map for this UI
   513	        kind_map = self._get_kind_map(ui_name)
   514	        
   515	        # Check each possible symlink
   516	        for kind in AssetKind:
   517	            kind_path = kind_map.get_path(kind)
   518	            if not kind_path:
   519	                continue
   520	            
   521	            synapse_link = ui_root / kind_path / "synapse"
   522	            
   523	            if synapse_link.is_symlink():
   524	                target = str(synapse_link.resolve()) if synapse_link.exists() else "broken"
   525	                status_info["symlinks"].append({
   526	                    "kind": kind.value,
   527	                    "path": str(synapse_link),
   528	                    "target": target,
   529	                })
   530	        
   531	        if status_info["symlinks"]:
   532	            status_info["attached"] = True
   533	            if status_info["method"] == "none":
   534	                status_info["method"] = "symlink"
   535	        
   536	        return status_info
   537	    
   538	    def refresh_attached(self, ui_targets: Optional[List[str]] = None) -> Dict[str, AttachResult]:
   539	        """
   540	        Refresh attachment for UIs that are already attached.
   541	        
   542	        This is called after use/back/sync to update paths to match new active view.
   543	        Only updates UIs that are currently attached - does NOT attach detached UIs.
   544	        
   545	        Args:
   546	            ui_targets: List of UIs to check. If None, checks all configured.
   547	        
   548	        Returns:
   549	            Dict mapping ui_name -> AttachResult (only for UIs that were refreshed)
   550	        """
   551	        if ui_targets is None:
   552	            ui_targets = list(self.ui_roots.keys())
   553	        
   554	        results = {}
   555	        
   556	        for ui_name in ui_targets:
   557	            ui_name = ui_name.lower()
   558	            current_status = self.status(ui_name)
   559	            
   560	            # Only refresh if already attached
   561	            if not current_status.get("attached"):
   562	                logger.debug(f"[{ui_name}] Not attached, skipping refresh")
   563	                continue
   564	            
   565	            # Re-attach to update paths
   566	            if ui_name == "comfyui":
   567	                results[ui_name] = self.attach_comfyui_yaml()
   568	            else:
   569	                results[ui_name] = self.attach(ui_name)
   570	            
   571	            logger.info(f"[{ui_name}] Refreshed attachment for active view")
   572	        
   573	        return results
   574	    
   575	    def refresh_all_attached(self) -> Dict[str, AttachResult]:
   576	        """
   577	        Refresh all attached UIs to match current active views.
   578	        
   579	        Convenience method that calls refresh_attached for all configured UIs.
   580	        
   581	        Returns:
   582	            Dict mapping ui_name -> AttachResult (only for UIs that were refreshed)
   583	        """
   584	        return self.refresh_attached()
   585	

exec
/bin/bash -lc "nl -ba src/store/inventory_service.py | sed -n '79,235p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    79	    def build_inventory(
    80	        self,
    81	        kind_filter: Optional[AssetKind] = None,
    82	        status_filter: Optional[BlobStatus] = None,
    83	        include_verification: bool = False,
    84	    ) -> InventoryResponse:
    85	        """
    86	        Build complete inventory by cross-referencing blobs and pack locks.
    87	
    88	        Algorithm:
    89	        1. List all physical blobs (local and backup)
    90	        2. Scan all pack locks for references
    91	        3. Cross-reference to determine status
    92	        4. Optionally verify hashes
    93	
    94	        Args:
    95	            kind_filter: Filter by asset kind
    96	            status_filter: Filter by blob status
    97	            include_verification: If True, verify blob hashes (slow!)
    98	
    99	        Returns:
   100	            Complete inventory response with summary and items
   101	        """
   102	        # NOTE: No routine logging - this is called frequently for UI refresh
   103	        # Only log errors
   104	
   105	        # Step 1: Get all physical blobs (local)
   106	        try:
   107	            local_blobs = set(self.blob_store.list_blobs())
   108	        except Exception as e:
   109	            logger.error("[Inventory] Failed to list local blobs: %s", e, exc_info=True)
   110	            raise
   111	
   112	        # Step 1b: Get backup blobs if backup service is available
   113	        backup_blobs: Set[str] = set()
   114	        if self.backup_service and self.backup_service.is_connected():
   115	            try:
   116	                backup_blobs = set(self.backup_service.list_backup_blobs())
   117	            except Exception as e:
   118	                logger.warning("[Inventory] Failed to list backup blobs: %s", e)
   119	
   120	        # All physical blobs (union of local and backup)
   121	        all_physical_blobs = local_blobs | backup_blobs
   122	
   123	        # Step 2: Build reference map from all pack locks
   124	        ref_map = self._build_reference_map()
   125	
   126	        # Step 3: Determine referenced blobs
   127	        referenced_blobs = set(ref_map.keys())
   128	
   129	        # Step 4: Calculate sets
   130	        # Blobs that exist locally and are referenced
   131	        local_referenced = local_blobs & referenced_blobs
   132	        # Blobs that exist locally but not referenced (orphan)
   133	        orphan_blobs = local_blobs - referenced_blobs
   134	        # Blobs only on backup but referenced (backup_only referenced)
   135	        backup_only_referenced = (backup_blobs - local_blobs) & referenced_blobs
   136	        # Blobs only on backup and not referenced (backup_only orphan)
   137	        backup_only_orphan = (backup_blobs - local_blobs) - referenced_blobs
   138	        # Blobs referenced but don't exist anywhere (truly missing)
   139	        missing_blobs = referenced_blobs - all_physical_blobs
   140	
   141	        # Step 5: Build items
   142	        items: List[InventoryItem] = []
   143	
   144	        # Referenced blobs (exist locally and are referenced)
   145	        for sha256 in local_referenced:
   146	            on_backup = sha256 in backup_blobs
   147	            item = self._build_item(
   148	                sha256=sha256,
   149	                status=BlobStatus.REFERENCED,
   150	                refs=ref_map[sha256],
   151	                verify=include_verification,
   152	                on_local=True,
   153	                on_backup=on_backup,
   154	            )
   155	            items.append(item)
   156	
   157	        # Orphan blobs (exist locally but not referenced)
   158	        for sha256 in orphan_blobs:
   159	            on_backup = sha256 in backup_blobs
   160	            item = self._build_item(
   161	                sha256=sha256,
   162	                status=BlobStatus.ORPHAN,
   163	                refs=[],
   164	                verify=include_verification,
   165	                on_local=True,
   166	                on_backup=on_backup,
   167	            )
   168	            items.append(item)
   169	
   170	        # Backup-only referenced blobs (on backup but not local, and referenced)
   171	        for sha256 in backup_only_referenced:
   172	            item = self._build_item(
   173	                sha256=sha256,
   174	                status=BlobStatus.BACKUP_ONLY,
   175	                refs=ref_map[sha256],
   176	                verify=False,  # Can't verify without local copy
   177	                on_local=False,
   178	                on_backup=True,
   179	            )
   180	            items.append(item)
   181	
   182	        # Backup-only orphan blobs (on backup but not local, not referenced)
   183	        for sha256 in backup_only_orphan:
   184	            item = self._build_item(
   185	                sha256=sha256,
   186	                status=BlobStatus.ORPHAN,  # Still orphan, just on backup
   187	                refs=[],
   188	                verify=False,
   189	                on_local=False,
   190	                on_backup=True,
   191	            )
   192	            items.append(item)
   193	
   194	        # Missing blobs (referenced but don't exist anywhere)
   195	        for sha256 in missing_blobs:
   196	            item = self._build_item(
   197	                sha256=sha256,
   198	                status=BlobStatus.MISSING,
   199	                refs=ref_map[sha256],
   200	                verify=False,  # Can't verify what doesn't exist
   201	                on_local=False,
   202	                on_backup=False,
   203	            )
   204	            items.append(item)
   205	
   206	        # Step 6: Apply filters
   207	        if kind_filter:
   208	            items = [i for i in items if i.kind == kind_filter]
   209	        if status_filter:
   210	            items = [i for i in items if i.status == status_filter]
   211	
   212	        # Step 7: Build summary
   213	        summary = self._build_summary(items)
   214	
   215	        return InventoryResponse(
   216	            generated_at=datetime.now().isoformat(),
   217	            summary=summary,
   218	            items=items,
   219	        )
   220	
   221	    def _build_reference_map(self) -> Dict[str, List[PackReference]]:
   222	        """
   223	        Scan all pack locks and build sha256 -> [references] map.
   224	
   225	        Returns:
   226	            Dict mapping SHA256 hashes to list of pack references
   227	        """
   228	        # NOTE: No routine logging - this is called frequently for UI refresh
   229	        ref_map: Dict[str, List[PackReference]] = {}
   230	        packs = self.layout.list_packs()
   231	
   232	        for pack_name in packs:
   233	            try:
   234	                lock = self.layout.load_pack_lock(pack_name)
   235	                pack = self.layout.load_pack(pack_name)

exec
/bin/bash -lc "nl -ba src/store/inventory_service.py | sed -n '235,390p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   235	                pack = self.layout.load_pack(pack_name)
   236	
   237	                for resolved in lock.resolved:
   238	                    sha256 = resolved.artifact.sha256
   239	                    if not sha256:
   240	                        continue
   241	
   242	                    sha256 = sha256.lower()
   243	                    if sha256 not in ref_map:
   244	                        ref_map[sha256] = []
   245	
   246	                    # Get expose filename from pack dependency
   247	                    expose_filename = None
   248	                    kind = resolved.artifact.kind
   249	                    for dep in pack.dependencies:
   250	                        if dep.id == resolved.dependency_id:
   251	                            expose_filename = dep.expose.filename
   252	                            kind = dep.kind
   253	                            break
   254	
   255	                    # Build origin from artifact provider
   256	                    origin = None
   257	                    if resolved.artifact.provider:
   258	                        prov = resolved.artifact.provider
   259	                        origin = BlobOrigin(
   260	                            provider=prov.name,
   261	                            model_id=prov.model_id,
   262	                            version_id=prov.version_id,
   263	                            file_id=prov.file_id,
   264	                            filename=prov.filename,
   265	                            repo_id=prov.repo_id,
   266	                        )
   267	
   268	                    ref_map[sha256].append(PackReference(
   269	                        pack_name=pack_name,
   270	                        dependency_id=resolved.dependency_id,
   271	                        kind=kind,
   272	                        expose_filename=expose_filename,
   273	                        size_bytes=resolved.artifact.size_bytes,
   274	                        origin=origin,
   275	                    ))
   276	            except Exception as e:
   277	                logger.warning("[Inventory] Error processing pack '%s': %s", pack_name, e)
   278	                continue  # Skip packs with missing/invalid locks
   279	
   280	        return ref_map
   281	
   282	    def _build_item(
   283	        self,
   284	        sha256: str,
   285	        status: BlobStatus,
   286	        refs: List[PackReference],
   287	        verify: bool = False,
   288	        on_local: bool = True,
   289	        on_backup: bool = False,
   290	    ) -> InventoryItem:
   291	        """
   292	        Build an inventory item from blob hash and references.
   293	
   294	        Args:
   295	            sha256: Blob SHA256 hash
   296	            status: Blob status
   297	            refs: List of pack references to this blob
   298	            verify: If True, verify blob hash
   299	            on_local: Whether blob exists locally
   300	            on_backup: Whether blob exists on backup
   301	
   302	        Returns:
   303	            Populated InventoryItem
   304	        """
   305	        # Determine size
   306	        size_bytes = 0
   307	        if on_local:
   308	            size = self.blob_store.blob_size(sha256)
   309	            if size is not None:
   310	                size_bytes = size
   311	        elif on_backup and self.backup_service:
   312	            # Try to get size from backup
   313	            size = self.backup_service.get_backup_blob_size(sha256)
   314	            if size is not None:
   315	                size_bytes = size
   316	
   317	        # If still no size, try to get from reference
   318	        if size_bytes == 0 and refs:
   319	            for ref in refs:
   320	                if ref.size_bytes:
   321	                    size_bytes = ref.size_bytes
   322	                    break
   323	
   324	        # Determine display name (priority: expose > origin filename > manifest > sha256)
   325	        display_name = sha256[:12] + "..."
   326	        kind = AssetKind.UNKNOWN
   327	        origin = None
   328	
   329	        if refs:
   330	            # Use first reference for display info
   331	            first_ref = refs[0]
   332	            kind = first_ref.kind
   333	            origin = first_ref.origin
   334	
   335	            if first_ref.expose_filename:
   336	                display_name = first_ref.expose_filename
   337	            elif first_ref.origin and first_ref.origin.filename:
   338	                display_name = first_ref.origin.filename
   339	        else:
   340	            # No pack references - try to read manifest for orphan blobs
   341	            manifest = self.blob_store.read_manifest(sha256)
   342	            if manifest:
   343	                display_name = manifest.original_filename
   344	                kind = manifest.kind
   345	                origin = manifest.origin
   346	
   347	        # Get unique pack names
   348	        used_by_packs = list(set(ref.pack_name for ref in refs))
   349	
   350	        # Determine location from provided flags
   351	        if on_local and on_backup:
   352	            location = BlobLocation.BOTH
   353	        elif on_local:
   354	            location = BlobLocation.LOCAL_ONLY
   355	        elif on_backup:
   356	            location = BlobLocation.BACKUP_ONLY
   357	        else:
   358	            location = BlobLocation.NOWHERE
   359	
   360	        # Verification
   361	        verified = None
   362	        if verify and on_local:
   363	            verified = self.blob_store.verify(sha256)
   364	
   365	        return InventoryItem(
   366	            sha256=sha256,
   367	            kind=kind,
   368	            display_name=display_name,
   369	            size_bytes=size_bytes,
   370	            location=location,
   371	            on_local=on_local,
   372	            on_backup=on_backup,
   373	            status=status,
   374	            used_by_packs=used_by_packs,
   375	            ref_count=len(refs),
   376	            origin=origin,
   377	            active_in_uis=[],  # TODO: Get from runtime
   378	            verified=verified,
   379	        )
   380	
   381	    def _build_summary(self, items: List[InventoryItem]) -> InventorySummary:
   382	        """
   383	        Build summary statistics from inventory items.
   384	
   385	        Args:
   386	            items: List of inventory items
   387	
   388	        Returns:
   389	            Summary statistics
   390	        """

exec
/bin/bash -lc "nl -ba src/store/inventory_service.py | sed -n '471,620p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   471	    def cleanup_orphans(self, dry_run: bool = True, max_items: int = 0) -> CleanupResult:
   472	        """
   473	        Remove orphan blobs safely.
   474	
   475	        NEVER removes referenced blobs.
   476	
   477	        Args:
   478	            dry_run: If True, don't actually delete anything
   479	            max_items: Maximum number of items to delete (0 = unlimited)
   480	
   481	        Returns:
   482	            Cleanup result with details
   483	        """
   484	        logger.info(
   485	            "[Inventory] Starting cleanup_orphans (dry_run=%s, max_items=%d)",
   486	            dry_run,
   487	            max_items,
   488	        )
   489	
   490	        try:
   491	            inventory = self.build_inventory(status_filter=BlobStatus.ORPHAN)
   492	            logger.info("[Inventory] Found %d orphan blobs", len(inventory.items))
   493	        except Exception as e:
   494	            logger.error("[Inventory] Failed to build inventory for cleanup: %s", e, exc_info=True)
   495	            raise
   496	
   497	        items_to_delete = inventory.items
   498	        if max_items > 0:
   499	            items_to_delete = items_to_delete[:max_items]
   500	            logger.debug("[Inventory] Limited to %d items (max_items=%d)", len(items_to_delete), max_items)
   501	
   502	        result = CleanupResult(
   503	            dry_run=dry_run,
   504	            orphans_found=len(inventory.items),
   505	            orphans_deleted=0,
   506	            bytes_freed=0,
   507	            deleted=[],
   508	        )
   509	
   510	        if dry_run:
   511	            result.deleted = items_to_delete
   512	            result.bytes_freed = sum(i.size_bytes for i in items_to_delete)
   513	            logger.info(
   514	                "[Inventory] Dry run complete: would delete %d blobs (%.2f MB)",
   515	                len(items_to_delete),
   516	                result.bytes_freed / 1024 / 1024,
   517	            )
   518	            return result
   519	
   520	        # Actually delete
   521	        logger.info("[Inventory] Starting deletion of %d orphan blobs", len(items_to_delete))
   522	        for i, item in enumerate(items_to_delete):
   523	            try:
   524	                logger.debug(
   525	                    "[Inventory] Deleting blob %d/%d: %s (%s)",
   526	                    i + 1,
   527	                    len(items_to_delete),
   528	                    item.sha256[:12],
   529	                    item.display_name,
   530	                )
   531	                if self.blob_store.remove_blob(item.sha256):
   532	                    result.orphans_deleted += 1
   533	                    result.bytes_freed += item.size_bytes
   534	                    result.deleted.append(item)
   535	                    logger.debug("[Inventory] Successfully deleted %s", item.sha256[:12])
   536	                else:
   537	                    logger.warning("[Inventory] remove_blob returned False for %s", item.sha256[:12])
   538	            except Exception as e:
   539	                error_msg = f"{item.sha256}: {str(e)}"
   540	                result.errors.append(error_msg)
   541	                logger.error("[Inventory] Failed to delete %s: %s", item.sha256[:12], e, exc_info=True)
   542	
   543	        if result.errors:
   544	            logger.warning("[Inventory] Cleanup completed with %d errors", len(result.errors))
   545	        else:
   546	            logger.info(
   547	                "[Inventory] Cleanup complete: deleted %d blobs, freed %.2f MB",
   548	                result.orphans_deleted,
   549	                result.bytes_freed / 1024 / 1024,
   550	            )
   551	
   552	        return result
   553	
   554	    def get_impacts(self, sha256: str) -> ImpactAnalysis:
   555	        """
   556	        Analyze what would break if a blob is deleted.
   557	
   558	        Args:
   559	            sha256: SHA256 hash of blob to analyze
   560	
   561	        Returns:
   562	            Impact analysis
   563	        """
   564	        logger.debug("[Inventory] Analyzing impacts for blob %s", sha256[:12] if len(sha256) >= 12 else sha256)
   565	
   566	        try:
   567	            inventory = self.build_inventory()
   568	        except Exception as e:
   569	            logger.error("[Inventory] Failed to build inventory for impacts: %s", e, exc_info=True)
   570	            raise
   571	
   572	        item = next((i for i in inventory.items if i.sha256 == sha256.lower()), None)
   573	
   574	        if not item:
   575	            logger.debug("[Inventory] Blob %s not found in inventory", sha256[:12])
   576	            return ImpactAnalysis(
   577	                sha256=sha256,
   578	                display_name=sha256[:12] + "...",
   579	                kind=None,
   580	                status=BlobStatus.MISSING,
   581	                size_bytes=0,
   582	                used_by_packs=[],
   583	                active_in_uis=[],
   584	                can_delete_safely=True,
   585	                warning="Blob does not exist",
   586	            )
   587	
   588	        can_delete = item.status == BlobStatus.ORPHAN
   589	        warning = None
   590	
   591	        if item.status == BlobStatus.REFERENCED:
   592	            pack_count = len(item.used_by_packs)
   593	            warning = (
   594	                f"This blob is used by {pack_count} pack(s). "
   595	                f"Deleting will cause MISSING status."
   596	            )
   597	            logger.debug(
   598	                "[Inventory] Blob %s is REFERENCED by %d packs: %s",
   599	                sha256[:12],
   600	                pack_count,
   601	                item.used_by_packs,
   602	            )
   603	        else:
   604	            logger.debug("[Inventory] Blob %s is %s, can_delete=%s", sha256[:12], item.status, can_delete)
   605	
   606	        return ImpactAnalysis(
   607	            sha256=sha256,
   608	            display_name=item.display_name,
   609	            kind=item.kind,
   610	            status=item.status,
   611	            size_bytes=item.size_bytes,
   612	            used_by_packs=item.used_by_packs,
   613	            active_in_uis=item.active_in_uis,
   614	            can_delete_safely=can_delete,
   615	            warning=warning,
   616	        )
   617	
   618	    def delete_blob(
   619	        self,
   620	        sha256: str,

exec
/bin/bash -lc "nl -ba src/store/blob_store.py | sed -n '88,206p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    88	class BlobStore:
    89	    """
    90	    Content-addressable blob store using SHA256.
    91	    
    92	    Blobs are stored at: data/blobs/sha256/<first2>/<full_hash>
    93	    
    94	    Features:
    95	    - Deduplication: same content = same blob
    96	    - Atomic writes: download to .part, verify, rename
    97	    - Concurrent downloads with worker pool
    98	    """
    99	    
   100	    DEFAULT_CHUNK_SIZE = 8192
   101	    DEFAULT_TIMEOUT = 300
   102	    DEFAULT_MAX_WORKERS = 4
   103	    
   104	    def __init__(
   105	        self,
   106	        layout: StoreLayout,
   107	        chunk_size: int = DEFAULT_CHUNK_SIZE,
   108	        timeout: int = DEFAULT_TIMEOUT,
   109	        max_workers: int = DEFAULT_MAX_WORKERS,
   110	        api_key: Optional[str] = None,
   111	        auth_providers: Optional[List] = None,
   112	        download_service: Optional[DownloadService] = None,
   113	    ):
   114	        """
   115	        Initialize blob store.
   116	
   117	        Args:
   118	            layout: Store layout manager
   119	            chunk_size: Download chunk size
   120	            timeout: Download timeout in seconds
   121	            max_workers: Max concurrent downloads
   122	            api_key: Optional API key (deprecated, use auth_providers)
   123	            auth_providers: List of DownloadAuthProvider instances for URL auth injection
   124	            download_service: Optional shared DownloadService instance
   125	        """
   126	        self.layout = layout
   127	        self.chunk_size = chunk_size
   128	        self.timeout = timeout
   129	        self.max_workers = max_workers
   130	        self.api_key = api_key or os.environ.get("CIVITAI_API_KEY")
   131	
   132	        if auth_providers is not None:
   133	            self._auth_providers = auth_providers
   134	        else:
   135	            # Default: create Civitai auth provider for backward compatibility
   136	            from .download_auth import CivitaiAuthProvider
   137	            self._auth_providers = [CivitaiAuthProvider(self.api_key)]
   138	
   139	        if download_service is not None:
   140	            self._download_service = download_service
   141	        else:
   142	            self._download_service = DownloadService(
   143	                auth_providers=self._auth_providers,
   144	                chunk_size=self.chunk_size,
   145	            )
   146	
   147	    # =========================================================================
   148	    # Blob Path Operations
   149	    # =========================================================================
   150	    
   151	    def blob_path(self, sha256: str) -> Path:
   152	        """Get path to a blob."""
   153	        return self.layout.blob_path(sha256.lower())
   154	    
   155	    def blob_exists(self, sha256: str) -> bool:
   156	        """Check if a blob exists."""
   157	        return self.blob_path(sha256).exists()
   158	    
   159	    def blob_size(self, sha256: str) -> Optional[int]:
   160	        """Get size of a blob in bytes. Returns None if not exists."""
   161	        path = self.blob_path(sha256)
   162	        if path.exists():
   163	            return path.stat().st_size
   164	        return None
   165	    
   166	    # =========================================================================
   167	    # Download Operations
   168	    # =========================================================================
   169	    
   170	    def download(
   171	        self,
   172	        url: str,
   173	        expected_sha256: Optional[str] = None,
   174	        progress_callback: Optional[ProgressCallback] = None,
   175	        force: bool = False,
   176	    ) -> str:
   177	        """
   178	        Download a file to blob store.
   179	        
   180	        Args:
   181	            url: Download URL (http://, https://, or file://)
   182	            expected_sha256: Expected SHA256 hash. If None, hash is computed after download.
   183	            progress_callback: Optional progress callback (downloaded, total)
   184	            force: If True, re-download even if blob exists
   185	        
   186	        Returns:
   187	            SHA256 hash of downloaded file
   188	        
   189	        Raises:
   190	            HashMismatchError: If downloaded hash doesn't match expected
   191	            DownloadError: If download fails
   192	        """
   193	        # If we know the hash and blob exists, skip download
   194	        if expected_sha256 and not force:
   195	            if self.blob_exists(expected_sha256):
   196	                return expected_sha256.lower()
   197	        
   198	        # Handle file:// URLs (for testing)
   199	        parsed = urlparse(url)
   200	        if parsed.scheme == "file":
   201	            return self._copy_local_file(parsed.path, expected_sha256)
   202	        
   203	        # HTTP/HTTPS download
   204	        return self._download_http(url, expected_sha256, progress_callback)
   205	    
   206	    def _copy_local_file(

exec
/bin/bash -lc "nl -ba src/store/blob_store.py | sed -n '486,611p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   486	    def adopt(
   487	        self,
   488	        source_path: Path,
   489	        expected_sha256: Optional[str] = None,
   490	        prefer_hardlink: bool = True,
   491	    ) -> str:
   492	        """
   493	        Adopt an existing file into the blob store.
   494	        
   495	        Args:
   496	            source_path: Path to existing file
   497	            expected_sha256: Optional expected hash (skips computation if provided)
   498	            prefer_hardlink: If True, try hardlink before copy
   499	        
   500	        Returns:
   501	            SHA256 hash of the file
   502	        """
   503	        if not source_path.exists():
   504	            raise BlobStoreError(f"Source file not found: {source_path}")
   505	        
   506	        # Compute or use expected hash
   507	        sha256 = expected_sha256.lower() if expected_sha256 else compute_sha256(source_path)
   508	        
   509	        # Check if already in store
   510	        blob_path = self.blob_path(sha256)
   511	        if blob_path.exists():
   512	            return sha256
   513	        
   514	        # Create parent directory
   515	        blob_path.parent.mkdir(parents=True, exist_ok=True)
   516	        
   517	        # Try hardlink first (same filesystem, no copy)
   518	        if prefer_hardlink:
   519	            try:
   520	                os.link(source_path, blob_path)
   521	                return sha256
   522	            except OSError:
   523	                pass  # Fall through to copy
   524	        
   525	        # Fall back to copy
   526	        shutil.copy2(source_path, blob_path)
   527	        return sha256
   528	
   529	    # =========================================================================
   530	    # Blob Manifest Operations (write-once metadata)
   531	    # =========================================================================
   532	
   533	    def manifest_path(self, sha256: str) -> Path:
   534	        """Get path to the manifest file for a blob."""
   535	        return self.layout.blob_manifest_path(sha256.lower())
   536	
   537	    def manifest_exists(self, sha256: str) -> bool:
   538	        """Check if a manifest exists for this blob."""
   539	        return self.manifest_path(sha256).exists()
   540	
   541	    def read_manifest(self, sha256: str) -> Optional[BlobManifest]:
   542	        """
   543	        Read manifest for a blob.
   544	
   545	        Returns:
   546	            BlobManifest if exists, None otherwise
   547	        """
   548	        path = self.manifest_path(sha256)
   549	        if not path.exists():
   550	            return None
   551	
   552	        try:
   553	            with open(path, "r", encoding="utf-8") as f:
   554	                data = json.load(f)
   555	            return BlobManifest.model_validate(data)
   556	        except Exception as e:
   557	            logger.warning(f"[BlobStore] Failed to read manifest {sha256[:12]}: {e}")
   558	            return None
   559	
   560	    def write_manifest(self, sha256: str, manifest: BlobManifest) -> bool:
   561	        """
   562	        Write manifest for a blob (write-once, never overwrites).
   563	
   564	        Args:
   565	            sha256: Blob hash
   566	            manifest: Manifest data
   567	
   568	        Returns:
   569	            True if written, False if manifest already exists (not an error)
   570	        """
   571	        path = self.manifest_path(sha256)
   572	
   573	        # Write-once: never overwrite existing manifest
   574	        if path.exists():
   575	            logger.debug(f"[BlobStore] Manifest already exists for {sha256[:12]}, skipping")
   576	            return False
   577	
   578	        # Ensure parent directory exists
   579	        path.parent.mkdir(parents=True, exist_ok=True)
   580	
   581	        try:
   582	            # Write atomically via temp file
   583	            temp_path = path.with_suffix(".meta.tmp")
   584	            with open(temp_path, "w", encoding="utf-8") as f:
   585	                json.dump(manifest.model_dump(mode="json"), f, indent=2)
   586	            temp_path.replace(path)
   587	            logger.debug(f"[BlobStore] Created manifest for {sha256[:12]}")
   588	            return True
   589	        except Exception as e:
   590	            logger.error(f"[BlobStore] Failed to write manifest {sha256[:12]}: {e}")
   591	            # Clean up temp file if exists
   592	            temp_path = path.with_suffix(".meta.tmp")
   593	            if temp_path.exists():
   594	                temp_path.unlink()
   595	            return False
   596	
   597	    def delete_manifest(self, sha256: str) -> bool:
   598	        """
   599	        Delete manifest for a blob (used when blob is deleted).
   600	
   601	        Returns:
   602	            True if deleted, False if didn't exist
   603	        """
   604	        path = self.manifest_path(sha256)
   605	        if path.exists():
   606	            try:
   607	                path.unlink()
   608	                return True
   609	            except Exception as e:
   610	                logger.warning(f"[BlobStore] Failed to delete manifest {sha256[:12]}: {e}")
   611	        return False

exec
/bin/bash -lc "nl -ba src/store/backup_service.py | sed -n '143,263p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   143	    def get_status(self) -> BackupStatus:
   144	        """
   145	        Get backup storage status.
   146	
   147	        Returns:
   148	            BackupStatus with connection info and statistics
   149	        """
   150	        # NOTE: No debug logging here - called frequently for polling
   151	
   152	        if not self.config.enabled:
   153	            return BackupStatus(
   154	                enabled=False,
   155	                connected=False,
   156	                path=self.config.path,
   157	                auto_backup_new=self.config.auto_backup_new,
   158	                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
   159	            )
   160	
   161	        if not self.config.path:
   162	            # Log only once when path is missing (error condition)
   163	            return BackupStatus(
   164	                enabled=True,
   165	                connected=False,
   166	                path=None,
   167	                error="Backup path not configured",
   168	                auto_backup_new=self.config.auto_backup_new,
   169	                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
   170	            )
   171	
   172	        backup_path = self.backup_root
   173	        if not backup_path or not backup_path.exists():
   174	            # Path not accessible - don't log (called frequently)
   175	            return BackupStatus(
   176	                enabled=True,
   177	                connected=False,
   178	                path=self.config.path,
   179	                error="Backup path not accessible",
   180	                auto_backup_new=self.config.auto_backup_new,
   181	                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
   182	            )
   183	
   184	        # Check if we can write to the backup
   185	        blobs_path = self.backup_blobs_path
   186	        try:
   187	            if blobs_path:
   188	                blobs_path.mkdir(parents=True, exist_ok=True)
   189	        except PermissionError:
   190	            logger.error("[Backup] No write permission to backup path: %s", self.config.path)
   191	            return BackupStatus(
   192	                enabled=True,
   193	                connected=False,
   194	                path=self.config.path,
   195	                error="No write permission to backup path",
   196	                auto_backup_new=self.config.auto_backup_new,
   197	                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
   198	            )
   199	        except Exception as e:
   200	            logger.error("[Backup] Error accessing backup path: %s", e, exc_info=True)
   201	            return BackupStatus(
   202	                enabled=True,
   203	                connected=False,
   204	                path=self.config.path,
   205	                error=str(e),
   206	                auto_backup_new=self.config.auto_backup_new,
   207	                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
   208	            )
   209	
   210	        # Count blobs and calculate size
   211	        total_blobs = 0
   212	        total_bytes = 0
   213	        if blobs_path and blobs_path.exists():
   214	            for prefix_dir in blobs_path.iterdir():
   215	                if not prefix_dir.is_dir():
   216	                    continue
   217	                for blob_file in prefix_dir.iterdir():
   218	                    if blob_file.is_file():
   219	                        total_blobs += 1
   220	                        total_bytes += blob_file.stat().st_size
   221	
   222	        # Get disk space
   223	        free_space = None
   224	        total_space = None
   225	        try:
   226	            usage = shutil.disk_usage(backup_path)
   227	            free_space = usage.free
   228	            total_space = usage.total
   229	        except Exception:
   230	            pass
   231	
   232	        return BackupStatus(
   233	            enabled=True,
   234	            connected=True,
   235	            path=self.config.path,
   236	            total_blobs=total_blobs,
   237	            total_bytes=total_bytes,
   238	            total_space=total_space,
   239	            free_space=free_space,
   240	            last_sync=self._last_sync,
   241	            auto_backup_new=self.config.auto_backup_new,
   242	            warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
   243	        )
   244	
   245	    def is_enabled(self) -> bool:
   246	        """Quick check if backup is enabled in config."""
   247	        return self.config.enabled
   248	
   249	    def is_connected(self) -> bool:
   250	        """Quick check if backup is connected."""
   251	        status = self.get_status()
   252	        return status.enabled and status.connected
   253	
   254	    def _require_connected(self) -> None:
   255	        """Raise if backup is not connected."""
   256	        if not self.config.enabled:
   257	            logger.warning("[Backup] Operation failed: backup not enabled")
   258	            raise BackupNotEnabledError("Backup storage is not enabled")
   259	        if not self.is_connected():
   260	            logger.warning("[Backup] Operation failed: backup not accessible")
   261	            raise BackupNotConnectedError("Backup storage is not accessible")
   262	
   263	    # =========================================================================

exec
/bin/bash -lc "nl -ba src/store/backup_service.py | sed -n '597,770p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   597	    def sync(
   598	        self,
   599	        direction: str = "to_backup",
   600	        only_missing: bool = True,
   601	        dry_run: bool = True,
   602	        progress_callback: Optional[Callable[[str, int, int], None]] = None,
   603	    ) -> SyncResult:
   604	        """
   605	        Sync blobs between local and backup storage.
   606	
   607	        Args:
   608	            direction: "to_backup" or "from_backup"
   609	            only_missing: Only sync blobs missing from target
   610	            dry_run: If True, don't actually copy anything
   611	            progress_callback: Optional callback (sha256, bytes_done, total_bytes)
   612	
   613	        Returns:
   614	            SyncResult with sync details
   615	        """
   616	        result = SyncResult(
   617	            dry_run=dry_run,
   618	            direction=direction,
   619	        )
   620	
   621	        try:
   622	            self._require_connected()
   623	        except (BackupNotEnabledError, BackupNotConnectedError) as e:
   624	            result.errors.append(str(e))
   625	            return result
   626	
   627	        # Get blob sets
   628	        local_blobs = set(self._list_local_blobs())
   629	        backup_blobs = set(self.list_backup_blobs())
   630	
   631	        # Determine what to sync
   632	        if direction == "to_backup":
   633	            if only_missing:
   634	                to_sync = local_blobs - backup_blobs
   635	            else:
   636	                to_sync = local_blobs
   637	        else:  # from_backup
   638	            if only_missing:
   639	                to_sync = backup_blobs - local_blobs
   640	            else:
   641	                to_sync = backup_blobs
   642	
   643	        # Build items list
   644	        for sha256 in to_sync:
   645	            if direction == "to_backup":
   646	                size = self._get_local_blob_size(sha256) or 0
   647	            else:
   648	                size = self.get_backup_blob_size(sha256) or 0
   649	
   650	            result.items.append(SyncItem(sha256=sha256, size_bytes=size))
   651	            result.bytes_to_sync += size
   652	
   653	        result.blobs_to_sync = len(result.items)
   654	
   655	        # If dry run, we're done
   656	        if dry_run:
   657	            return result
   658	
   659	        # Actually sync
   660	        for item in result.items:
   661	            try:
   662	                if direction == "to_backup":
   663	                    op_result = self.backup_blob(item.sha256, verify_after=True)
   664	                else:
   665	                    op_result = self.restore_blob(item.sha256, verify_after=True)
   666	
   667	                if op_result.success:
   668	                    result.blobs_synced += 1
   669	                    result.bytes_synced += op_result.bytes_copied
   670	                else:
   671	                    result.errors.append(f"{item.sha256}: {op_result.error}")
   672	
   673	                if progress_callback:
   674	                    progress_callback(item.sha256, result.bytes_synced, result.bytes_to_sync)
   675	
   676	            except Exception as e:
   677	                result.errors.append(f"{item.sha256}: {str(e)}")
   678	
   679	        # Update last sync time
   680	        self._last_sync = datetime.now().isoformat()
   681	
   682	        return result
   683	
   684	    # =========================================================================
   685	    # Verification
   686	    # =========================================================================
   687	
   688	    def verify_backup_blob(self, sha256: str) -> bool:
   689	        """
   690	        Verify a blob's integrity on backup storage.
   691	
   692	        Args:
   693	            sha256: SHA256 hash to verify
   694	
   695	        Returns:
   696	            True if blob exists and hash matches
   697	        """
   698	        backup_path = self.backup_blob_path(sha256)
   699	        if not backup_path or not backup_path.exists():
   700	            return False
   701	
   702	        actual_hash = compute_sha256(backup_path)
   703	        return actual_hash == sha256.lower()
   704	
   705	    def verify_all_backup_blobs(self) -> Tuple[List[str], List[str]]:
   706	        """
   707	        Verify all blobs on backup storage.
   708	
   709	        Returns:
   710	            Tuple of (valid_hashes, invalid_hashes)
   711	        """
   712	        valid = []
   713	        invalid = []
   714	
   715	        for sha256 in self.list_backup_blobs():
   716	            if self.verify_backup_blob(sha256):
   717	                valid.append(sha256)
   718	            else:
   719	                invalid.append(sha256)
   720	
   721	        return valid, invalid
   722	
   723	    # =========================================================================
   724	    # Guard Rails
   725	    # =========================================================================
   726	
   727	    def is_last_copy(self, sha256: str) -> bool:
   728	        """
   729	        Check if this is the last copy of a blob.
   730	
   731	        Returns True if blob exists in exactly one location.
   732	        """
   733	        local_exists = self.layout.blob_path(sha256).exists()
   734	        backup_exists = self.blob_exists_on_backup(sha256)
   735	
   736	        # Last copy if only in one place
   737	        return (local_exists and not backup_exists) or (backup_exists and not local_exists)
   738	
   739	    def get_delete_warning(self, sha256: str, target: str) -> Optional[str]:
   740	        """
   741	        Get a warning message if deletion would be dangerous.
   742	
   743	        Args:
   744	            sha256: Blob hash
   745	            target: "local", "backup", or "both"
   746	
   747	        Returns:
   748	            Warning message or None if safe
   749	        """
   750	        local_exists = self.layout.blob_path(sha256).exists()
   751	        backup_exists = self.blob_exists_on_backup(sha256)
   752	
   753	        if target == "both":
   754	            if local_exists or backup_exists:
   755	                return (
   756	                    "This will permanently delete the blob from ALL locations. "
   757	                    "You will need to re-download it from the original source."
   758	                )
   759	        elif target == "local":
   760	            if local_exists and not backup_exists:
   761	                return (
   762	                    "This blob is NOT backed up. "
   763	                    "Deleting it will require re-downloading from the original source."
   764	                )
   765	        elif target == "backup":
   766	            if backup_exists and not local_exists:
   767	                return (
   768	                    "This blob exists ONLY on backup. "
   769	                    "Deleting it will require re-downloading from the original source."
   770	                )

exec
/bin/bash -lc "nl -ba src/store/backup_service.py | sed -n '827,1050p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   827	    def get_state_sync_status(self) -> StateSyncResult:
   828	        """
   829	        Get the current sync status of the state/ directory.
   830	
   831	        Returns:
   832	            StateSyncResult with dry_run=True showing what would be synced
   833	        """
   834	        return self.sync_state(dry_run=True)
   835	
   836	    def sync_state(
   837	        self,
   838	        direction: str = "to_backup",
   839	        dry_run: bool = True,
   840	        progress_callback: Optional[Callable[[str, int, int], None]] = None,
   841	    ) -> StateSyncResult:
   842	        """
   843	        Sync the state/ directory between local and backup.
   844	
   845	        Args:
   846	            direction: "to_backup", "from_backup", or "bidirectional"
   847	            dry_run: If True, don't actually copy files
   848	            progress_callback: Optional callback (file_path, done, total)
   849	
   850	        Returns:
   851	            StateSyncResult with sync details
   852	        """
   853	        result = StateSyncResult(
   854	            dry_run=dry_run,
   855	            direction=direction,
   856	            summary=StateSyncSummary(),
   857	        )
   858	
   859	        try:
   860	            self._require_connected()
   861	        except (BackupNotEnabledError, BackupNotConnectedError) as e:
   862	            result.errors.append(str(e))
   863	            return result
   864	
   865	        state_path = self.layout.state_path
   866	        backup_state = self.backup_state_path
   867	
   868	        if not backup_state:
   869	            result.errors.append("Cannot determine backup state path")
   870	            return result
   871	
   872	        # Collect all files from both sides
   873	        local_files = self._collect_state_files(state_path, state_path)
   874	        backup_files = self._collect_state_files(backup_state, backup_state)
   875	
   876	        all_paths = set(local_files.keys()) | set(backup_files.keys())
   877	        result.summary.total_files = len(all_paths)
   878	
   879	        # Analyze each file
   880	        for rel_path in sorted(all_paths):
   881	            local_info = local_files.get(rel_path)
   882	            backup_info = backup_files.get(rel_path)
   883	
   884	            item = self._analyze_state_file(rel_path, local_info, backup_info)
   885	            result.items.append(item)
   886	
   887	            # Update summary
   888	            if item.status == StateSyncStatus.SYNCED:
   889	                result.summary.synced += 1
   890	            elif item.status == StateSyncStatus.LOCAL_ONLY:
   891	                result.summary.local_only += 1
   892	            elif item.status == StateSyncStatus.BACKUP_ONLY:
   893	                result.summary.backup_only += 1
   894	            elif item.status == StateSyncStatus.MODIFIED:
   895	                result.summary.modified += 1
   896	            elif item.status == StateSyncStatus.CONFLICT:
   897	                result.summary.conflicts += 1
   898	
   899	        # If dry run, we're done
   900	        if dry_run:
   901	            return result
   902	
   903	        # Actually sync files
   904	        done = 0
   905	        total = len([i for i in result.items if i.status != StateSyncStatus.SYNCED])
   906	
   907	        for item in result.items:
   908	            if item.status == StateSyncStatus.SYNCED:
   909	                continue
   910	
   911	            try:
   912	                synced = self._sync_state_file(item, direction, state_path, backup_state)
   913	                if synced:
   914	                    result.synced_files += 1
   915	
   916	                done += 1
   917	                if progress_callback:
   918	                    progress_callback(item.relative_path, done, total)
   919	
   920	            except Exception as e:
   921	                result.errors.append(f"{item.relative_path}: {str(e)}")
   922	
   923	        # Update last sync time
   924	        self._last_sync = datetime.now().isoformat()
   925	        result.summary.last_sync = self._last_sync
   926	
   927	        return result
   928	
   929	    def _collect_state_files(
   930	        self, root: Path, base: Path
   931	    ) -> Dict[str, Tuple[datetime, int]]:
   932	        """
   933	        Collect all files in a state directory.
   934	
   935	        Returns:
   936	            Dict mapping relative paths to (mtime, size)
   937	        """
   938	        files = {}
   939	        if not root.exists():
   940	            return files
   941	
   942	        for path in root.rglob("*"):
   943	            if path.is_file():
   944	                # Skip hidden files and temp files
   945	                if path.name.startswith(".") or path.name.endswith(".tmp"):
   946	                    continue
   947	                rel_path = str(path.relative_to(base))
   948	                stat = path.stat()
   949	                files[rel_path] = (
   950	                    datetime.fromtimestamp(stat.st_mtime),
   951	                    stat.st_size,
   952	                )
   953	
   954	        return files
   955	
   956	    def _analyze_state_file(
   957	        self,
   958	        rel_path: str,
   959	        local_info: Optional[Tuple[datetime, int]],
   960	        backup_info: Optional[Tuple[datetime, int]],
   961	    ) -> StateSyncItem:
   962	        """Analyze a single state file and determine its sync status."""
   963	        if local_info is None and backup_info is None:
   964	            # Should not happen
   965	            return StateSyncItem(
   966	                relative_path=rel_path,
   967	                status=StateSyncStatus.SYNCED,
   968	            )
   969	
   970	        if local_info is None:
   971	            # Only on backup
   972	            return StateSyncItem(
   973	                relative_path=rel_path,
   974	                status=StateSyncStatus.BACKUP_ONLY,
   975	                backup_mtime=backup_info[0].isoformat() if backup_info else None,
   976	                backup_size=backup_info[1] if backup_info else None,
   977	            )
   978	
   979	        if backup_info is None:
   980	            # Only on local
   981	            return StateSyncItem(
   982	                relative_path=rel_path,
   983	                status=StateSyncStatus.LOCAL_ONLY,
   984	                local_mtime=local_info[0].isoformat(),
   985	                local_size=local_info[1],
   986	            )
   987	
   988	        # Both exist - compare
   989	        local_mtime, local_size = local_info
   990	        backup_mtime, backup_size = backup_info
   991	
   992	        # If same size and mtime within 1 second, consider synced
   993	        time_diff = abs((local_mtime - backup_mtime).total_seconds())
   994	        if local_size == backup_size and time_diff < 2:
   995	            return StateSyncItem(
   996	                relative_path=rel_path,
   997	                status=StateSyncStatus.SYNCED,
   998	                local_mtime=local_mtime.isoformat(),
   999	                backup_mtime=backup_mtime.isoformat(),
  1000	                local_size=local_size,
  1001	                backup_size=backup_size,
  1002	            )
  1003	
  1004	        # Files differ - determine which is newer
  1005	        return StateSyncItem(
  1006	            relative_path=rel_path,
  1007	            status=StateSyncStatus.MODIFIED,
  1008	            local_mtime=local_mtime.isoformat(),
  1009	            backup_mtime=backup_mtime.isoformat(),
  1010	            local_size=local_size,
  1011	            backup_size=backup_size,
  1012	        )
  1013	
  1014	    def _sync_state_file(
  1015	        self,
  1016	        item: StateSyncItem,
  1017	        direction: str,
  1018	        state_path: Path,
  1019	        backup_state: Path,
  1020	    ) -> bool:
  1021	        """
  1022	        Sync a single state file.
  1023	
  1024	        Returns:
  1025	            True if file was synced
  1026	        """
  1027	        local_path = state_path / item.relative_path
  1028	        backup_path = backup_state / item.relative_path
  1029	
  1030	        if direction == "to_backup":
  1031	            if item.status in (StateSyncStatus.LOCAL_ONLY, StateSyncStatus.MODIFIED):
  1032	                backup_path.parent.mkdir(parents=True, exist_ok=True)
  1033	                shutil.copy2(local_path, backup_path)
  1034	                return True
  1035	
  1036	        elif direction == "from_backup":
  1037	            if item.status in (StateSyncStatus.BACKUP_ONLY, StateSyncStatus.MODIFIED):
  1038	                local_path.parent.mkdir(parents=True, exist_ok=True)
  1039	                shutil.copy2(backup_path, local_path)
  1040	                return True
  1041	
  1042	        elif direction == "bidirectional":
  1043	            # For bidirectional, newer file wins
  1044	            if item.status == StateSyncStatus.LOCAL_ONLY:
  1045	                backup_path.parent.mkdir(parents=True, exist_ok=True)
  1046	                shutil.copy2(local_path, backup_path)
  1047	                return True
  1048	            elif item.status == StateSyncStatus.BACKUP_ONLY:
  1049	                local_path.parent.mkdir(parents=True, exist_ok=True)
  1050	                shutil.copy2(backup_path, local_path)

exec
/bin/bash -lc "nl -ba src/store/update_service.py | sed -n '74,190p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    74	    def __init__(
    75	        self,
    76	        layout: StoreLayout,
    77	        blob_store: BlobStore,
    78	        view_builder: ViewBuilder,
    79	        providers: Optional[Dict[SelectorStrategy, UpdateProvider]] = None,
    80	    ):
    81	        """
    82	        Initialize update service.
    83	
    84	        Args:
    85	            layout: Store layout manager
    86	            blob_store: Blob store
    87	            view_builder: View builder
    88	            providers: Registry mapping SelectorStrategy -> UpdateProvider
    89	        """
    90	        self.layout = layout
    91	        self.blob_store = blob_store
    92	        self.view_builder = view_builder
    93	        self._providers: Dict[SelectorStrategy, UpdateProvider] = providers or {}
    94	
    95	    def register_provider(self, strategy: SelectorStrategy, provider: UpdateProvider) -> None:
    96	        """Register an update provider for a selector strategy."""
    97	        self._providers[strategy] = provider
    98	
    99	    def _get_provider(self, strategy: SelectorStrategy) -> Optional[UpdateProvider]:
   100	        """Get the provider for a given selector strategy."""
   101	        return self._providers.get(strategy)
   102	
   103	    # =========================================================================
   104	    # Update Planning
   105	    # =========================================================================
   106	
   107	    def is_updatable(self, pack: Pack) -> bool:
   108	        """
   109	        Check if a pack has any updatable dependencies.
   110	
   111	        A pack is updatable if it has at least one dependency with:
   112	        - A registered provider for its selector strategy
   113	        - update_policy.mode = follow_latest
   114	        """
   115	        for dep in pack.dependencies:
   116	            if (dep.update_policy.mode == UpdatePolicyMode.FOLLOW_LATEST and
   117	                    dep.selector.strategy in self._providers):
   118	                return True
   119	        return False
   120	
   121	    def plan_update(self, pack_name: str) -> UpdatePlan:
   122	        """
   123	        Create an update plan for a pack.
   124	
   125	        Checks each updatable dependency for new versions by delegating
   126	        to the appropriate provider.
   127	
   128	        Args:
   129	            pack_name: Pack to check for updates
   130	
   131	        Returns:
   132	            UpdatePlan with changes and ambiguous selections
   133	        """
   134	        pack = self.layout.load_pack(pack_name)
   135	        lock = self.layout.load_pack_lock(pack_name)
   136	
   137	        if not lock:
   138	            return UpdatePlan(
   139	                pack=pack_name,
   140	                already_up_to_date=False,
   141	                changes=[],
   142	                ambiguous=[],
   143	                impacted_packs=self._find_reverse_dependencies(pack_name),
   144	            )
   145	
   146	        changes = []
   147	        ambiguous = []
   148	        lock_modified = False
   149	
   150	        for dep in pack.dependencies:
   151	            # Skip non-updatable dependencies
   152	            if dep.update_policy.mode != UpdatePolicyMode.FOLLOW_LATEST:
   153	                continue
   154	
   155	            # Find provider for this strategy
   156	            provider = self._get_provider(dep.selector.strategy)
   157	            if not provider:
   158	                continue
   159	
   160	            # Get current lock entry
   161	            current = lock.get_resolved(dep.id)
   162	            if not current:
   163	                continue
   164	
   165	            # Check for updates via provider
   166	            try:
   167	                result = provider.check_update(dep, current)
   168	                if result is None:
   169	                    continue
   170	
   171	                if result.ambiguous:
   172	                    ambiguous.append(AmbiguousUpdate(
   173	                        dependency_id=dep.id,
   174	                        candidates=result.candidates,
   175	                    ))
   176	                elif result.has_update:
   177	                    changes.append(UpdateChange(
   178	                        dependency_id=dep.id,
   179	                        old={
   180	                            "provider": current.artifact.provider.name.value
   181	                                if hasattr(current.artifact.provider.name, 'value')
   182	                                else str(current.artifact.provider.name),
   183	                            "provider_model_id": current.artifact.provider.model_id,
   184	                            "provider_version_id": current.artifact.provider.version_id,
   185	                            "provider_file_id": current.artifact.provider.file_id,
   186	                            "sha256": current.artifact.sha256,
   187	                        },
   188	                        new={
   189	                            "provider": current.artifact.provider.name.value
   190	                                if hasattr(current.artifact.provider.name, 'value')

exec
/bin/bash -lc "nl -ba src/store/update_service.py | sed -n '190,360p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   190	                                if hasattr(current.artifact.provider.name, 'value')
   191	                                else str(current.artifact.provider.name),
   192	                            "provider_model_id": result.model_id,
   193	                            "provider_version_id": result.version_id,
   194	                            "provider_file_id": result.file_id,
   195	                            "sha256": result.sha256,
   196	                            "download_url": result.download_url,
   197	                            "filename": result.filename,
   198	                            "size_bytes": result.size_bytes,
   199	                        },
   200	                    ))
   201	                else:
   202	                    # Self-heal: fill missing filename in lock from check result
   203	                    if result.filename and not current.artifact.provider.filename:
   204	                        current.artifact.provider.filename = result.filename
   205	                        lock_modified = True
   206	            except Exception as e:
   207	                logger.warning("Failed to check updates for %s dep %s: %s", pack_name, dep.id, e)
   208	
   209	        # Check for pending downloads (lock updated but blob not on disk)
   210	        # Uses lock metadata only — NO API calls (those were already made above)
   211	        pending_downloads = []
   212	        for dep in pack.dependencies:
   213	            resolved = lock.get_resolved(dep.id)
   214	            if resolved and resolved.artifact.sha256:
   215	                if not self.blob_store.blob_exists(resolved.artifact.sha256):
   216	                    # Get download URL from lock (set during apply_update)
   217	                    urls = resolved.artifact.download.urls if resolved.artifact.download else []
   218	                    download_url = urls[0] if urls else ""
   219	                    # Fallback: build URL from lock provider metadata
   220	                    if not download_url:
   221	                        prov = self._get_provider(dep.selector.strategy)
   222	                        if prov:
   223	                            download_url = prov.build_download_url(
   224	                                resolved.artifact.provider.version_id,
   225	                                resolved.artifact.provider.file_id,
   226	                            )
   227	                    pending_downloads.append(PendingDownload(
   228	                        dependency_id=dep.id,
   229	                        sha256=resolved.artifact.sha256,
   230	                        download_url=download_url,
   231	                        size_bytes=resolved.artifact.size_bytes,
   232	                    ))
   233	
   234	        already_up_to_date = (
   235	            len(changes) == 0
   236	            and len(ambiguous) == 0
   237	            and len(pending_downloads) == 0
   238	        )
   239	
   240	        # Persist self-healed filename metadata in lock
   241	        if lock_modified:
   242	            self.layout.save_pack_lock(lock)
   243	
   244	        # Scan for reverse dependencies (which packs depend on this one)
   245	        impacted_packs = self._find_reverse_dependencies(pack_name)
   246	
   247	        return UpdatePlan(
   248	            pack=pack_name,
   249	            already_up_to_date=already_up_to_date,
   250	            changes=changes,
   251	            ambiguous=ambiguous,
   252	            pending_downloads=pending_downloads,
   253	            impacted_packs=impacted_packs,
   254	        )
   255	
   256	    def _find_reverse_dependencies(self, pack_name: str) -> List[str]:
   257	        """
   258	        Find all packs that depend on the given pack via pack_dependencies.
   259	
   260	        Returns:
   261	            List of pack names that have pack_name in their pack_dependencies.
   262	        """
   263	        reverse_deps = []
   264	        for other_name in self.layout.list_packs():
   265	            if other_name == pack_name:
   266	                continue
   267	            try:
   268	                other_pack = self.layout.load_pack(other_name)
   269	                dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
   270	                if pack_name in dep_names:
   271	                    reverse_deps.append(other_name)
   272	            except Exception:
   273	                continue
   274	        return sorted(reverse_deps)
   275	
   276	    # =========================================================================
   277	    # Update Application
   278	    # =========================================================================
   279	
   280	    def apply_update(
   281	        self,
   282	        pack_name: str,
   283	        plan: UpdatePlan,
   284	        choose: Optional[Dict[str, int]] = None,
   285	    ) -> PackLock:
   286	        """
   287	        Apply an update plan to a pack.
   288	
   289	        Uses the appropriate provider to build download URLs.
   290	
   291	        Args:
   292	            pack_name: Pack to update
   293	            plan: Update plan from plan_update()
   294	            choose: Optional dict mapping dep_id -> file_id for ambiguous selections
   295	
   296	        Returns:
   297	            Updated PackLock
   298	
   299	        Raises:
   300	            AmbiguousSelectionError: If plan has ambiguous entries without choose
   301	        """
   302	        # Handle ambiguous updates: auto-select first candidate when no choice provided
   303	        if plan.ambiguous:
   304	            if choose is None:
   305	                choose = {}
   306	            for amb in plan.ambiguous:
   307	                if amb.dependency_id not in choose:
   308	                    if amb.candidates:
   309	                        auto_file_id = amb.candidates[0].provider_file_id
   310	                        choose[amb.dependency_id] = auto_file_id
   311	                        logger.warning(
   312	                            "[UpdateService] Auto-selected file_id=%s for ambiguous "
   313	                            "dependency %s (pack=%s, %d candidates)",
   314	                            auto_file_id, amb.dependency_id, pack_name,
   315	                            len(amb.candidates),
   316	                        )
   317	
   318	        # Load current lock and pack
   319	        lock = self.layout.load_pack_lock(pack_name)
   320	        if not lock:
   321	            raise UpdateError(f"No lock file for pack: {pack_name}")
   322	
   323	        pack = self.layout.load_pack(pack_name)
   324	
   325	        # Apply changes
   326	        for change in plan.changes:
   327	            dep_id = change.dependency_id
   328	            new_data = change.new
   329	
   330	            # Find the provider for this dependency
   331	            dep = pack.get_dependency(dep_id)
   332	            provider = self._get_provider(dep.selector.strategy) if dep else None
   333	
   334	            # Get download URL - prefer URL from check result, fallback to building
   335	            version_id = new_data.get("provider_version_id")
   336	            file_id = new_data.get("provider_file_id")
   337	            if not provider:
   338	                logger.warning("No provider for dependency %s (strategy=%s), skipping",
   339	                              dep_id, dep.selector.strategy if dep else "unknown")
   340	                continue
   341	            download_url = new_data.get("download_url") or provider.build_download_url(version_id, file_id)
   342	
   343	            # Resolve provider name from current lock entry
   344	            provider_name = self._resolve_provider_name(new_data.get("provider"))
   345	
   346	            # Find and update resolved entry
   347	            found = False
   348	            for i, resolved in enumerate(lock.resolved):
   349	                if resolved.dependency_id == dep_id:
   350	                    lock.resolved[i] = ResolvedDependency(
   351	                        dependency_id=dep_id,
   352	                        artifact=ResolvedArtifact(
   353	                            kind=resolved.artifact.kind,
   354	                            sha256=new_data.get("sha256"),
   355	                            size_bytes=new_data.get("size_bytes") or resolved.artifact.size_bytes,
   356	                            provider=ArtifactProvider(
   357	                                name=provider_name,
   358	                                model_id=new_data.get("provider_model_id"),
   359	                                version_id=version_id,
   360	                                file_id=file_id,

exec
/bin/bash -lc "nl -ba src/store/update_service.py | sed -n '432,555p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   432	    def _resolve_provider_name(provider_str: Optional[str]) -> ProviderName:
   433	        """Resolve a provider string to ProviderName enum."""
   434	        if not provider_str:
   435	            return ProviderName.CIVITAI
   436	        try:
   437	            return ProviderName(provider_str)
   438	        except ValueError:
   439	            return ProviderName.CIVITAI
   440	
   441	    # =========================================================================
   442	    # High-Level Update Command
   443	    # =========================================================================
   444	
   445	    def update_pack(
   446	        self,
   447	        pack_name: str,
   448	        dry_run: bool = False,
   449	        choose: Optional[Dict[str, int]] = None,
   450	        sync: bool = False,
   451	        ui_targets: Optional[List[str]] = None,
   452	        options: Optional[UpdateOptions] = None,
   453	    ) -> UpdateResult:
   454	        """
   455	        High-level update command.
   456	
   457	        Args:
   458	            pack_name: Pack to update
   459	            dry_run: If True, only plan without applying
   460	            choose: Optional file selections for ambiguous updates
   461	            sync: If True, download new blobs and rebuild views
   462	            ui_targets: UI targets for sync (required if sync=True)
   463	            options: Optional update options (merge previews, etc.)
   464	
   465	        Returns:
   466	            UpdateResult with details
   467	        """
   468	        # Create plan
   469	        plan = self.plan_update(pack_name)
   470	
   471	        if plan.already_up_to_date:
   472	            return UpdateResult(
   473	                pack=pack_name,
   474	                applied=False,
   475	                lock_updated=False,
   476	                synced=False,
   477	                ui_targets=[],
   478	                already_up_to_date=True,
   479	            )
   480	
   481	        if dry_run:
   482	            return UpdateResult(
   483	                pack=pack_name,
   484	                applied=False,
   485	                lock_updated=False,
   486	                synced=False,
   487	                ui_targets=[],
   488	                already_up_to_date=False,
   489	            )
   490	
   491	        # Apply update
   492	        lock = self.apply_update(pack_name, plan, choose)
   493	
   494	        result = UpdateResult(
   495	            pack=pack_name,
   496	            applied=True,
   497	            lock_updated=True,
   498	            synced=False,
   499	            ui_targets=ui_targets or [],
   500	        )
   501	
   502	        # Apply options (merge previews, update description, etc.)
   503	        if options:
   504	            self._apply_options(pack_name, options, result)
   505	
   506	        # Sync if requested
   507	        if sync and ui_targets:
   508	            result.synced = self._sync_after_update(pack_name, lock, ui_targets)
   509	
   510	        return result
   511	
   512	    def _apply_options(
   513	        self,
   514	        pack_name: str,
   515	        options: UpdateOptions,
   516	        result: UpdateResult,
   517	    ) -> None:
   518	        """Apply update options by delegating to the pack's provider."""
   519	        pack = self.layout.load_pack(pack_name)
   520	        provider = self._get_provider_for_pack(pack)
   521	        if not provider:
   522	            return
   523	
   524	        changed = False
   525	
   526	        if options.merge_previews:
   527	            merged_count = provider.merge_previews(pack)
   528	            result.previews_merged = merged_count
   529	            if merged_count > 0:
   530	                changed = True
   531	
   532	        if options.update_description:
   533	            updated = provider.update_description(pack)
   534	            result.description_updated = updated
   535	            if updated:
   536	                changed = True
   537	
   538	        if options.update_model_info:
   539	            updated = provider.update_model_info(pack)
   540	            result.model_info_updated = updated
   541	            if updated:
   542	                changed = True
   543	
   544	        if changed:
   545	            self.layout.save_pack(pack)
   546	
   547	    def _get_provider_for_pack(self, pack: Pack) -> Optional[UpdateProvider]:
   548	        """Find the appropriate provider for a pack based on its dependencies."""
   549	        for dep in pack.dependencies:
   550	            provider = self._get_provider(dep.selector.strategy)
   551	            if provider:
   552	                return provider
   553	        return None
   554	
   555	    def apply_batch(

exec
/bin/bash -lc "nl -ba src/store/update_service.py | sed -n '346,431p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   346	            # Find and update resolved entry
   347	            found = False
   348	            for i, resolved in enumerate(lock.resolved):
   349	                if resolved.dependency_id == dep_id:
   350	                    lock.resolved[i] = ResolvedDependency(
   351	                        dependency_id=dep_id,
   352	                        artifact=ResolvedArtifact(
   353	                            kind=resolved.artifact.kind,
   354	                            sha256=new_data.get("sha256"),
   355	                            size_bytes=new_data.get("size_bytes") or resolved.artifact.size_bytes,
   356	                            provider=ArtifactProvider(
   357	                                name=provider_name,
   358	                                model_id=new_data.get("provider_model_id"),
   359	                                version_id=version_id,
   360	                                file_id=file_id,
   361	                                filename=new_data.get("filename") or resolved.artifact.provider.filename,
   362	                            ),
   363	                            download=ArtifactDownload(urls=[download_url]),
   364	                            integrity=ArtifactIntegrity(sha256_verified=new_data.get("sha256") is not None),
   365	                        ),
   366	                    )
   367	                    found = True
   368	                    break
   369	            if not found:
   370	                logger.warning("Dependency %s not found in lock for pack %s, skipping", dep_id, pack_name)
   371	
   372	        # Apply ambiguous selections
   373	        if choose:
   374	            for amb in plan.ambiguous:
   375	                if amb.dependency_id in choose:
   376	                    selected_file_id = choose[amb.dependency_id]
   377	
   378	                    # Find the selected candidate
   379	                    selected = None
   380	                    for cand in amb.candidates:
   381	                        if cand.provider_file_id == selected_file_id:
   382	                            selected = cand
   383	                            break
   384	
   385	                    if selected:
   386	                        # Find provider for this dependency
   387	                        dep = pack.get_dependency(amb.dependency_id)
   388	                        provider = self._get_provider(dep.selector.strategy) if dep else None
   389	
   390	                        if not provider:
   391	                            logger.warning("No provider for dependency %s, skipping ambiguous selection",
   392	                                          amb.dependency_id)
   393	                            continue
   394	                        download_url = provider.build_download_url(
   395	                            selected.provider_version_id,
   396	                            selected.provider_file_id,
   397	                        )
   398	
   399	                        provider_name = self._resolve_provider_name(selected.provider)
   400	
   401	                        # Find and update resolved entry
   402	                        for i, resolved in enumerate(lock.resolved):
   403	                            if resolved.dependency_id == amb.dependency_id:
   404	                                lock.resolved[i] = ResolvedDependency(
   405	                                    dependency_id=amb.dependency_id,
   406	                                    artifact=ResolvedArtifact(
   407	                                        kind=dep.kind if dep else resolved.artifact.kind,
   408	                                        sha256=selected.sha256,
   409	                                        size_bytes=selected.size_bytes or resolved.artifact.size_bytes,
   410	                                        provider=ArtifactProvider(
   411	                                            name=provider_name,
   412	                                            model_id=selected.provider_model_id,
   413	                                            version_id=selected.provider_version_id,
   414	                                            file_id=selected.provider_file_id,
   415	                                            filename=selected.filename or resolved.artifact.provider.filename,
   416	                                        ),
   417	                                        download=ArtifactDownload(urls=[download_url]),
   418	                                        integrity=ArtifactIntegrity(sha256_verified=selected.sha256 is not None),
   419	                                    ),
   420	                                )
   421	                                break
   422	
   423	        # Update timestamp
   424	        lock.resolved_at = datetime.now().isoformat()
   425	
   426	        # Save updated lock
   427	        self.layout.save_pack_lock(lock)
   428	
   429	        return lock
   430	
   431	    @staticmethod

exec
/bin/bash -lc "nl -ba src/store/api.py | sed -n '3310,3350p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  3310	        pack = Pack(
  3311	            name=request.name,
  3312	            pack_type=pack_type,
  3313	            pack_category=PackCategory.CUSTOM,  # Custom packs are fully editable
  3314	            source=PackSource(
  3315	                provider=ProviderName.LOCAL,
  3316	                url=None,
  3317	                model_id=None,
  3318	                version_id=None,
  3319	            ),
  3320	            version=request.version,
  3321	            description=request.description,
  3322	            base_model=request.base_model,
  3323	            author=request.author,
  3324	            tags=request.tags or [],
  3325	            user_tags=request.user_tags or [],
  3326	            trigger_words=request.trigger_words or [],
  3327	            created_at=datetime.now(),
  3328	        )
  3329	
  3330	        # Save the pack
  3331	        store.layout.save_pack(pack)
  3332	
  3333	        # Create pack directories
  3334	        pack_path = store.layout.pack_path(request.name)
  3335	        (pack_path / "resources" / "previews").mkdir(parents=True, exist_ok=True)
  3336	        (pack_path / "resources" / "workflows").mkdir(parents=True, exist_ok=True)
  3337	
  3338	        logger.info(f"[create_pack] Created custom pack: {request.name}")
  3339	
  3340	        return {
  3341	            "success": True,
  3342	            "name": pack.name,
  3343	            "pack_type": pack.pack_type.value,
  3344	            "pack_category": pack.pack_category.value,
  3345	            "created_at": pack.created_at.isoformat() if pack.created_at else None,
  3346	        }
  3347	
  3348	    except HTTPException:
  3349	        raise
  3350	    except Exception as e:

exec
/bin/bash -lc "nl -ba src/store/api.py | sed -n '2958,3102p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  2958	# =============================================================================
  2959	# Pack Dependencies (pack-to-pack) CRUD
  2960	# =============================================================================
  2961	
  2962	
  2963	@v2_packs_router.get("/{pack_name}/pack-dependencies/status", response_model=List[Dict[str, Any]])
  2964	def get_pack_dependencies_status(
  2965	    pack_name: str,
  2966	    store=Depends(require_initialized),
  2967	):
  2968	    """Get status of all pack dependencies (batch resolve).
  2969	
  2970	    Returns installation status for each pack dependency,
  2971	    replacing the N+1 per-pack query pattern.
  2972	    """
  2973	    try:
  2974	        pack = store.get_pack(pack_name)
  2975	        statuses = []
  2976	        for ref in pack.pack_dependencies:
  2977	            try:
  2978	                dep_pack = store.get_pack(ref.pack_name)
  2979	                # Aggregate trigger words from LoRA/embedding deps
  2980	                trigger_words = []
  2981	                for d in dep_pack.dependencies:
  2982	                    if d.expose and d.expose.trigger_words:
  2983	                        trigger_words.extend(d.expose.trigger_words)
  2984	                # Check resolution status
  2985	                dep_lock = store.layout.load_pack_lock(dep_pack.name)
  2986	                has_unresolved = bool(dep_lock and dep_lock.unresolved)
  2987	                # Check if all blobs exist locally
  2988	                all_installed = True
  2989	                if dep_lock:
  2990	                    for rd in dep_lock.resolved:
  2991	                        if rd.artifact.sha256 and not store.blob_store.blob_exists(rd.artifact.sha256):
  2992	                            all_installed = False
  2993	                            break
  2994	                else:
  2995	                    all_installed = False
  2996	                statuses.append({
  2997	                    "pack_name": ref.pack_name,
  2998	                    "required": ref.required,
  2999	                    "installed": True,
  3000	                    "version": dep_pack.version if hasattr(dep_pack, 'version') else None,
  3001	                    "pack_type": dep_pack.pack_type.value if hasattr(dep_pack.pack_type, 'value') else str(dep_pack.pack_type) if dep_pack.pack_type else None,
  3002	                    "description": (dep_pack.description or "")[:200] if dep_pack.description else None,
  3003	                    "asset_count": len(dep_pack.dependencies),
  3004	                    "trigger_words": trigger_words,
  3005	                    "base_model": dep_pack.base_model,
  3006	                    "has_unresolved": has_unresolved,
  3007	                    "all_installed": all_installed,
  3008	                })
  3009	            except Exception:
  3010	                statuses.append({
  3011	                    "pack_name": ref.pack_name,
  3012	                    "required": ref.required,
  3013	                    "installed": False,
  3014	                    "version": None,
  3015	                    "pack_type": None,
  3016	                    "description": None,
  3017	                    "asset_count": 0,
  3018	                    "trigger_words": [],
  3019	                    "base_model": None,
  3020	                    "has_unresolved": False,
  3021	                    "all_installed": False,
  3022	                })
  3023	        return statuses
  3024	    except HTTPException:
  3025	        raise
  3026	    except Exception as e:
  3027	        logger.error(f"[pack-deps-status] Error: {e}")
  3028	        raise HTTPException(status_code=400, detail=str(e))
  3029	
  3030	
  3031	class AddPackDependencyRequest(BaseModel):
  3032	    pack_name: str
  3033	    required: bool = True
  3034	
  3035	
  3036	@v2_packs_router.post("/{pack_name}/pack-dependencies", response_model=Dict[str, Any])
  3037	def add_pack_dependency(
  3038	    pack_name: str,
  3039	    request: AddPackDependencyRequest = Body(...),
  3040	    store=Depends(require_initialized),
  3041	):
  3042	    """Add a pack dependency (pack-to-pack reference)."""
  3043	    try:
  3044	        pack = store.get_pack(pack_name)
  3045	
  3046	        # Self-reference check
  3047	        if request.pack_name == pack_name:
  3048	            raise HTTPException(status_code=400, detail="Pack cannot depend on itself")
  3049	
  3050	        # Duplicate check
  3051	        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
  3052	        if request.pack_name in existing_names:
  3053	            raise HTTPException(
  3054	                status_code=409,
  3055	                detail=f"Pack dependency already exists: {request.pack_name}",
  3056	            )
  3057	
  3058	        # Add the dependency
  3059	        new_ref = PackDependencyRef(
  3060	            pack_name=request.pack_name,
  3061	            required=request.required,
  3062	        )
  3063	        pack.pack_dependencies.append(new_ref)
  3064	        store.layout.save_pack(pack)
  3065	
  3066	        logger.info(f"[pack-deps] Added {request.pack_name} to {pack_name}")
  3067	        return {
  3068	            "success": True,
  3069	            "pack_name": request.pack_name,
  3070	            "required": request.required,
  3071	            "message": f"Added pack dependency: {request.pack_name}",
  3072	        }
  3073	    except HTTPException:
  3074	        raise
  3075	    except Exception as e:
  3076	        logger.error(f"[pack-deps] Error adding: {e}")
  3077	        raise HTTPException(status_code=400, detail=str(e))
  3078	
  3079	
  3080	@v2_packs_router.delete("/{pack_name}/pack-dependencies/{dep_pack_name}", response_model=Dict[str, Any])
  3081	def remove_pack_dependency(
  3082	    pack_name: str,
  3083	    dep_pack_name: str,
  3084	    store=Depends(require_initialized),
  3085	):
  3086	    """Remove a pack dependency."""
  3087	    try:
  3088	        pack = store.get_pack(pack_name)
  3089	
  3090	        # Check if it exists
  3091	        original_count = len(pack.pack_dependencies)
  3092	        pack.pack_dependencies = [
  3093	            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
  3094	        ]
  3095	
  3096	        if len(pack.pack_dependencies) == original_count:
  3097	            raise HTTPException(
  3098	                status_code=404,
  3099	                detail=f"Pack dependency not found: {dep_pack_name}",
  3100	            )
  3101	
  3102	        store.layout.save_pack(pack)

exec
/bin/bash -lc "nl -ba src/store/api.py | sed -n '3160,3195p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  3160	                    "circular": False,
  3161	                    "depth": depth,
  3162	                }
  3163	
  3164	            # Aggregate trigger words
  3165	            trigger_words = []
  3166	            for d in p.dependencies:
  3167	                if d.expose and d.expose.trigger_words:
  3168	                    trigger_words.extend(d.expose.trigger_words)
  3169	
  3170	            # Build children (if not at max depth)
  3171	            children = []
  3172	            if depth < max_depth and p.pack_dependencies:
  3173	                for ref in p.pack_dependencies:
  3174	                    children.append(build_node(ref.pack_name, depth + 1, visited))
  3175	
  3176	            return {
  3177	                "pack_name": name,
  3178	                "installed": True,
  3179	                "version": p.version if hasattr(p, 'version') else None,
  3180	                "pack_type": p.pack_type.value if hasattr(p.pack_type, 'value') else str(p.pack_type) if p.pack_type else None,
  3181	                "description": (p.description or "")[:200] if p.description else None,
  3182	                "asset_count": len(p.dependencies),
  3183	                "trigger_words": trigger_words,
  3184	                "children": children,
  3185	                "circular": False,
  3186	                "depth": depth,
  3187	            }
  3188	
  3189	        tree = build_node(pack_name, 0, set())
  3190	        return {"tree": tree, "max_depth": max_depth}
  3191	
  3192	    except HTTPException:
  3193	        raise
  3194	    except Exception as e:
  3195	        logger.error(f"[dependency-tree] Error: {e}")

exec
/bin/bash -lc "nl -ba src/store/cli.py | sed -n '510,535p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   510	        profile = store.layout.load_profile(profile_name)
   511	    except Exception:
   512	        output_error(f"Profile not found: {profile_name}")
   513	        raise typer.Exit(1)
   514	
   515	    if json:
   516	        output_json(profile.model_dump())
   517	    else:
   518	        console.print(Panel(
   519	            f"[bold cyan]{profile.name}[/bold cyan]",
   520	            title="Profile Details",
   521	            box=box.ROUNDED,
   522	        ))
   523	
   524	        if profile.packs:
   525	            console.print(f"\n[bold]Packs ({len(profile.packs)}):[/bold]")
   526	            for i, pack_entry in enumerate(profile.packs, 1):
   527	                enabled = "[green]✓[/green]" if pack_entry.enabled else "[red]✗[/red]"
   528	                console.print(f"  {i}. {enabled} [cyan]{pack_entry.name}[/cyan]")
   529	        else:
   530	            console.print("\n[dim]No packs in this profile[/dim]")
   531	
   532	
   533	# =============================================================================
   534	# Status Command
   535	# =============================================================================

codex
The adjacent services reinforce a central smell: `pack_dependencies` has CRUD and tree/status endpoints, but profile loading and view planning only load `profile.packs`. That means the field is modeled as if operational, yet not part of runtime composition. Next I’m checking the resolve redesign branch models so the audit can compare current `DependencySelector`/lock shape against the incoming candidate/source shape.
exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_models.py | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Resolve system DTOs — all data transfer objects for dependency resolution.
     3	
     4	Based on PLAN-Resolve-Model.md v0.7.1 sections 2b, 2j, 11c.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from typing import Any, Dict, List, Literal, Optional
    10	from uuid import uuid4
    11	
    12	from pydantic import BaseModel, Field
    13	
    14	from .models import (
    15	    AssetKind,
    16	    CanonicalSource,
    17	    CivitaiSelector,
    18	    DependencySelector,
    19	    HuggingFaceSelector,
    20	    SelectorStrategy,
    21	)
    22	
    23	# --- Evidence source types ---
    24	
    25	EvidenceSource = Literal[
    26	    "hash_match",          # E1: SHA256 lookup (Tier 1)
    27	    "preview_embedded",    # E2: PNG tEXt metadata (Tier 2)
    28	    "preview_api_meta",    # E3: Civitai API sidecar meta (Tier 2)
    29	    "source_metadata",     # E4: Civitai baseModel field (Tier 4)
    30	    "file_metadata",       # E5: Filename patterns (Tier 3)
    31	    "alias_config",        # E6: Configured aliases (Tier 3)
    32	    "ai_analysis",         # E7: AI-assisted analysis (ceiling 0.89)
    33	]
    34	
    35	
    36	# --- Evidence items ---
    37	
    38	class EvidenceItem(BaseModel):
    39	    """A single piece of evidence from one source."""
    40	    source: EvidenceSource
    41	    description: str
    42	    confidence: float  # 0.0 - 1.0, within tier bounds
    43	    raw_value: Optional[str] = None
    44	
    45	
    46	class EvidenceGroup(BaseModel):
    47	    """Evidence items from the same provenance (e.g., one preview image).
    48	
    49	    Within a group: combined_confidence = max(item.confidence).
    50	    Between groups: Noisy-OR combination.
    51	    """
    52	    provenance: str  # "preview:001.png", "hash:sha256", "alias:SDXL"
    53	    items: List[EvidenceItem] = Field(default_factory=list)
    54	    combined_confidence: float = 0.0
    55	
    56	
    57	# --- Candidate models ---
    58	
    59	class CandidateSeed(BaseModel):
    60	    """What an evidence provider found — a candidate with identification."""
    61	    key: str  # Deduplication key: "civitai:model_id:version_id" or "local:/path"
    62	    selector: DependencySelector
    63	    canonical_source: Optional[CanonicalSource] = None
    64	    display_name: str
    65	    display_description: Optional[str] = None
    66	    provider_name: Optional[Literal["civitai", "huggingface", "local", "url"]] = None
    67	    base_model: Optional[str] = None  # e.g. "SDXL", "SD 1.5" — for cross-kind check
    68	
    69	
    70	class EvidenceHit(BaseModel):
    71	    """One finding = candidate + evidence why."""
    72	    candidate: CandidateSeed
    73	    provenance: str  # Which preview/hash/alias produced this
    74	    item: EvidenceItem
    75	
    76	
    77	class ResolutionCandidate(BaseModel):
    78	    """A ranked candidate for dependency resolution."""
    79	    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
    80	    rank: int = 0
    81	    confidence: float = Field(ge=0.0, le=1.0)
    82	    tier: int = Field(ge=1, le=4)  # Confidence tier (1=highest, 4=lowest)
    83	    strategy: SelectorStrategy
    84	    selector_data: Dict[str, Any] = Field(default_factory=dict)
    85	    canonical_source: Optional[CanonicalSource] = None
    86	    evidence_groups: List[EvidenceGroup] = Field(default_factory=list)
    87	    display_name: str = ""
    88	    display_description: Optional[str] = None
    89	    provider: Optional[Literal["civitai", "huggingface", "local", "url"]] = None
    90	    base_model: Optional[str] = None  # e.g. "SDXL", "SD 1.5"
    91	    compatibility_warnings: List[str] = Field(default_factory=list)
    92	
    93	
    94	# --- Preview model hints ---
    95	
    96	class PreviewModelHint(BaseModel):
    97	    """A model reference extracted from a preview image's metadata."""
    98	    filename: str              # "illustriousXL_v060.safetensors"
    99	    kind: Optional[AssetKind] = None  # From ComfyUI node type
   100	    source_image: str          # Which preview image
   101	    source_type: Literal["api_meta", "png_embedded"]
   102	    raw_value: str             # Raw value for debugging
   103	    resolvable: bool = True    # False if private/unknown format
   104	    hash: Optional[str] = None         # Short SHA hash if available
   105	    weight: Optional[float] = None     # LoRA weight if available
   106	
   107	
   108	class PreviewAnalysisResult(BaseModel):
   109	    """Preview image with extracted hints + raw generation params."""
   110	    filename: str
   111	    url: Optional[str] = None
   112	    thumbnail_url: Optional[str] = None
   113	    media_type: Literal["image", "video", "unknown"] = "image"
   114	    width: Optional[int] = None
   115	    height: Optional[int] = None
   116	    nsfw: bool = False
   117	    hints: List[PreviewModelHint] = Field(default_factory=list)
   118	    generation_params: Optional[Dict[str, Any]] = None
   119	
   120	
   121	# --- Provider result ---
   122	
   123	class ProviderResult(BaseModel):
   124	    """Output of one evidence provider's gather() call."""
   125	    hits: List[EvidenceHit] = Field(default_factory=list)
   126	    warnings: List[str] = Field(default_factory=list)
   127	    error: Optional[str] = None
   128	
   129	
   130	# --- Request/Response contracts ---
   131	
   132	class SuggestOptions(BaseModel):
   133	    """Options for suggest_resolution."""
   134	    include_ai: bool = False       # Default OFF for import (R5)
   135	    analyze_previews: bool = True
   136	    max_candidates: int = 10
   137	    preview_hints_override: Optional[List[PreviewModelHint]] = None  # External hints (import pipeline)
   138	
   139	
   140	class SuggestResult(BaseModel):
   141	    """Result of suggest — list of candidates + metadata."""
   142	    request_id: str = Field(default_factory=lambda: str(uuid4()))
   143	    candidates: List[ResolutionCandidate] = Field(default_factory=list)
   144	    pack_fingerprint: str = ""  # SHA hash of pack.json for stale detection
   145	    warnings: List[str] = Field(default_factory=list)
   146	    preview_hints: List[PreviewModelHint] = Field(default_factory=list)
   147	
   148	
   149	class ApplyResult(BaseModel):
   150	    """Result of apply — success/failure."""
   151	    success: bool
   152	    message: str = ""
   153	    compatibility_warnings: List[str] = Field(default_factory=list)
   154	
   155	
   156	class ManualResolveData(BaseModel):
   157	    """Data from manual resolve (Civitai/HF/Local tab)."""
   158	    strategy: SelectorStrategy
   159	    civitai: Optional[CivitaiSelector] = None
   160	    huggingface: Optional[HuggingFaceSelector] = None
   161	    local_path: Optional[str] = None
   162	    url: Optional[str] = None
   163	    canonical_source: Optional[CanonicalSource] = None
   164	    display_name: Optional[str] = None
   165	
   166	
   167	# --- Resolve context (passed to providers) ---
   168	
   169	class ResolveContext(BaseModel):
   170	    """Context passed to evidence providers."""
   171	    pack: Any  # Pack object
   172	    dependency: Any  # PackDependency
   173	    dep_id: str = ""
   174	    kind: AssetKind = AssetKind.UNKNOWN
   175	    preview_hints: List[PreviewModelHint] = Field(default_factory=list)
   176	    layout: Any = None  # StoreLayout (for file-system access)
   177	
   178	    class Config:
   179	        arbitrary_types_allowed = True

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_models.py | nl -ba | sed -n '261,560p'" in /home/box/git/github/synapse
 succeeded in 0ms:
exec
/bin/bash -lc 'git status --short' in /home/box/git/github/synapse
 succeeded in 0ms:
?? plans/PLAN-Release-1-Roadmap.md
?? plans/audit-resolve-model-redesign-local.md
?? plans/audits/

exec
/bin/bash -lc "rg -n \"CanonicalSource|ResolutionCandidate|apply_resolution|model_id=0|model_id.*0|candidate|canonical_source\" src plans -g'*.py' -g'*.md'" in /home/box/git/github/synapse
 succeeded in 0ms:
plans/audit-resolve-model-redesign-local.md:10:2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
plans/audit-resolve-model-redesign-local.md:35:1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
plans/audit-resolve-model-redesign-local.md:36:2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
plans/audit-resolve-model-redesign-local.md:43:9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.
plans/audit-resolve-model-redesign-local.md:65:4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audit-resolve-model-redesign-local.md:69:8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audit-resolve-model-redesign-local.md:83:3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
plans/audit-resolve-model-redesign-local.md:84:4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
plans/audit-resolve-model-redesign-local.md:100:8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.
plans/audit-resolve-model-redesign-local.md:119:1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
plans/audit-resolve-model-redesign-local.md:138:6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
plans/audit-resolve-model-redesign-local.md:149:3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
plans/audit-resolve-model-redesign-local.md:151:5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
plans/audit-resolve-model-redesign-local.md:162:5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
plans/audit-resolve-model-redesign-local.md:184:5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audit-resolve-model-redesign-local.md:186:7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
plans/audit-resolve-model-redesign-local.md:187:8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.
plans/audit-resolve-model-redesign-local.md:197:3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
plans/audit-resolve-model-redesign-local.md:228:1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
plans/audit-resolve-model-redesign-local.md:229:2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
plans/audit-resolve-model-redesign-local.md:230:3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
plans/audit-resolve-model-redesign-local.md:248:4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audit-resolve-model-redesign-local.md:249:5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
plans/audit-resolve-model-redesign-local.md:250:6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
plans/audit-resolve-model-redesign-local.md:312:4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audit-resolve-model-redesign-local.md:314:6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audit-resolve-model-redesign-local.md:317:9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
plans/audit-resolve-model-redesign-local.md:321:13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
plans/audit-resolve-model-redesign-local.md:327:2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
plans/audit-resolve-model-redesign-local.md:328:3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
plans/audit-resolve-model-redesign-local.md:340:2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
plans/audit-resolve-model-redesign-local.md:343:5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
plans/audit-resolve-model-redesign-local.md:346:8. Should canonical source be required for all remote Civitai/HF candidates before apply?
plans/audit-resolve-model-redesign-local.md:358:5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
plans/PLAN-Updates.md:166:          "model_id": 133005,
plans/PLAN-Updates.md:335:      "selector": { "civitai": { "model_id": 123, "version_id": 100 } }
plans/PLAN-Updates.md:339:      "selector": { "civitai": { "model_id": 123, "version_id": 101 } }
plans/audits/codex-domain-audit-raw.md:64:   - PackDependency, PackDependencyRef, ResolutionCandidate, CanonicalSource — overlap?
plans/audits/codex-domain-audit-raw.md:68:     without polluting normal fields with placeholders (model_id=0, etc.)?
plans/audits/codex-domain-audit-raw.md:71:   - Does the model support multi-source candidate (same dep, multiple matches)?
plans/audits/codex-domain-audit-raw.md:75:   - In resolve-model-redesign branch, candidates have CanonicalSource. Should
plans/audits/codex-domain-audit-raw.md:76:     Pack.source also use CanonicalSource? Are they parallel hierarchies?
plans/audits/codex-domain-audit-raw.md:100:   - How do new ResolutionCandidate / CanonicalSource fit into existing Pack model?
plans/audits/codex-domain-audit-raw.md:102:   - Will applying a candidate need new fields on PackDependency?
plans/audits/codex-domain-audit-raw.md:129:    - model_id=0 placeholder Civitai candidates.
plans/audits/codex-domain-audit-raw.md:197:  providers (E1–E6 + AI), suggest/apply tok, candidate cache, `ResolutionCandidate`
plans/audits/codex-domain-audit-raw.md:211:  manual apply; jen vybírá existujícího kandidáta z `candidates`. Pokud žádný neexistuje,
plans/audits/codex-domain-audit-raw.md:219:- **`apply_resolution()` aktualizuje JEN `pack.json`, nikdy `pack.lock.json`.** PackService
plans/audits/codex-domain-audit-raw.md:221:- **`CanonicalSource` model existuje ale většina remote kandidátů ho nepopulu**je. Apply pak
plans/audits/codex-domain-audit-raw.md:225:- **`FileMetaEvidenceProvider` stále emituje `model_id=0` placeholder Civitai kandidáty.**
plans/audits/codex-domain-audit-raw.md:241:2. **Má `apply_resolution()` aktualizovat `pack.lock.json`, nebo zůstává "pack.json only"?**
plans/audits/codex-domain-audit-raw.md:244:5. **Jsou placeholder kandidáti (`model_id=0`) přijatelné v UI, nebo je hide/marknout?**
plans/audits/codex-domain-audit-raw.md:247:8. **Má být `canonical_source` POVINNÝ pro všechny remote Civitai/HF kandidáty před apply?**
plans/audits/codex-domain-audit-raw.md:255:  → providers chain (FileMeta, Hash, Civitai, HF, PreviewMeta, AI) → seřazené `ResolutionCandidate[]`
plans/audits/codex-domain-audit-raw.md:266:  ne v `apply_resolution()`. Toto je rozcestí pro rozhodnutí.
plans/audits/codex-domain-audit-raw.md:1150:   280	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-domain-audit-raw.md:1158:   288	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-domain-audit-raw.md:1166:   296	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-domain-audit-raw.md:1174:   304	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-domain-audit-raw.md:2030:  1152	    """A candidate for ambiguous update selection."""
plans/audits/codex-domain-audit-raw.md:2045:  1167	    candidates: List[UpdateCandidate]
plans/audits/codex-domain-audit-raw.md:5825:   352	    candidates = files.copy()
plans/audits/codex-domain-audit-raw.md:5829:   356	            primary = [f for f in candidates if f.get("primary")]
plans/audits/codex-domain-audit-raw.md:5831:   358	                candidates = primary
plans/audits/codex-domain-audit-raw.md:5835:   362	                f for f in candidates
plans/audits/codex-domain-audit-raw.md:5839:   366	                candidates = ext_filtered
plans/audits/codex-domain-audit-raw.md:5841:   368	    return candidates[0] if candidates else None
plans/audits/codex-domain-audit-raw.md:8775:   174	                        candidates=result.candidates,
plans/audits/codex-domain-audit-raw.md:8908:   302	        # Handle ambiguous updates: auto-select first candidate when no choice provided
plans/audits/codex-domain-audit-raw.md:8914:   308	                    if amb.candidates:
plans/audits/codex-domain-audit-raw.md:8915:   309	                        auto_file_id = amb.candidates[0].provider_file_id
plans/audits/codex-domain-audit-raw.md:8919:   313	                            "dependency %s (pack=%s, %d candidates)",
plans/audits/codex-domain-audit-raw.md:8921:   315	                            len(amb.candidates),
plans/audits/codex-domain-audit-raw.md:9131:   378	                    # Find the selected candidate
plans/audits/codex-domain-audit-raw.md:9133:   380	                    for cand in amb.candidates:
plans/audits/codex-domain-audit-raw.md:9451:The adjacent services reinforce a central smell: `pack_dependencies` has CRUD and tree/status endpoints, but profile loading and view planning only load `profile.packs`. That means the field is modeled as if operational, yet not part of runtime composition. Next I’m checking the resolve redesign branch models so the audit can compare current `DependencySelector`/lock shape against the incoming candidate/source shape.
plans/audits/codex-domain-audit-raw.md:9470:    16	    CanonicalSource,
plans/audits/codex-domain-audit-raw.md:9514:    60	    """What an evidence provider found — a candidate with identification."""
plans/audits/codex-domain-audit-raw.md:9517:    63	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-domain-audit-raw.md:9525:    71	    """One finding = candidate + evidence why."""
plans/audits/codex-domain-audit-raw.md:9526:    72	    candidate: CandidateSeed
plans/audits/codex-domain-audit-raw.md:9531:    77	class ResolutionCandidate(BaseModel):
plans/audits/codex-domain-audit-raw.md:9532:    78	    """A ranked candidate for dependency resolution."""
plans/audits/codex-domain-audit-raw.md:9533:    79	    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
plans/audits/codex-domain-audit-raw.md:9539:    85	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-domain-audit-raw.md:9590:   136	    max_candidates: int = 10
plans/audits/codex-domain-audit-raw.md:9595:   141	    """Result of suggest — list of candidates + metadata."""
plans/audits/codex-domain-audit-raw.md:9597:   143	    candidates: List[ResolutionCandidate] = Field(default_factory=list)
plans/audits/codex-domain-audit-raw.md:9617:   163	    canonical_source: Optional[CanonicalSource] = None
plans/audits/CONSOLIDATED-FINDINGS.md:27:  providers (E1–E6 + AI), suggest/apply tok, candidate cache, `ResolutionCandidate`
plans/audits/CONSOLIDATED-FINDINGS.md:41:  manual apply; jen vybírá existujícího kandidáta z `candidates`. Pokud žádný neexistuje,
plans/audits/CONSOLIDATED-FINDINGS.md:49:- **`apply_resolution()` aktualizuje JEN `pack.json`, nikdy `pack.lock.json`.** PackService
plans/audits/CONSOLIDATED-FINDINGS.md:51:- **`CanonicalSource` model existuje ale většina remote kandidátů ho nepopulu**je. Apply pak
plans/audits/CONSOLIDATED-FINDINGS.md:55:- **`FileMetaEvidenceProvider` stále emituje `model_id=0` placeholder Civitai kandidáty.**
plans/audits/CONSOLIDATED-FINDINGS.md:71:2. **Má `apply_resolution()` aktualizovat `pack.lock.json`, nebo zůstává "pack.json only"?**
plans/audits/CONSOLIDATED-FINDINGS.md:74:5. **Jsou placeholder kandidáti (`model_id=0`) přijatelné v UI, nebo je hide/marknout?**
plans/audits/CONSOLIDATED-FINDINGS.md:77:8. **Má být `canonical_source` POVINNÝ pro všechny remote Civitai/HF kandidáty před apply?**
plans/audits/CONSOLIDATED-FINDINGS.md:85:  → providers chain (FileMeta, Hash, Civitai, HF, PreviewMeta, AI) → seřazené `ResolutionCandidate[]`
plans/audits/CONSOLIDATED-FINDINGS.md:96:  ne v `apply_resolution()`. Toto je rozcestí pro rozhodnutí.
src/avatar/mcp/store_server.py:614:            model_id = model.get("id", 0)
src/avatar/mcp/store_server.py:1246:        """Find blobs not referenced by any pack (candidates for cleanup)."""
plans/PLAN-Model-Inventory.md:393:        "model_id": 133005,
src/clients/civitai_client.py:188:        model_id = data.get("modelId", 0)
src/clients/civitai_client.py:196:            model_id = data.get("modelId", 0)
src/store/models.py:280:                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
src/store/models.py:288:                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
src/store/models.py:296:                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
src/store/models.py:304:                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
src/store/models.py:1152:    """A candidate for ambiguous update selection."""
src/store/models.py:1167:    candidates: List[UpdateCandidate]
plans/audits/codex-audit-5-profiles.md:1134:                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-5-profiles.md:1142:                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-5-profiles.md:1150:                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-5-profiles.md:1158:                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-5-profiles.md:8588:          "model_id": 133005,
plans/audits/codex-audit-5-profiles.md:10293:            id=version_id, model_id=model_id, name="v1.0",
plans/audits/codex-audit-5-profiles.md:10311:                id=new_vid, model_id=model_id, name="v2.0",
plans/audits/codex-audit-5-profiles.md:10318:                id=old_vid, model_id=model_id, name="v1.0",
plans/audits/codex-audit-5-profiles.md:10426:                store, name="TestPack", model_id=100,
plans/audits/codex-audit-5-profiles.md:10571:        _create_pack_with_lock(store, name="ProvInfoPack", model_id=2600,
plans/audits/codex-audit-5-profiles.md:10581:        assert artifact.provider.model_id == 2600
plans/audits/codex-audit-5-profiles.md:10594:            _create_pack_with_lock(store, name="OptTestPack", model_id=2700,
plans/audits/codex-audit-5-profiles.md:12724:                        candidates=result.candidates,
plans/audits/codex-audit-5-profiles.md:12852:        # Handle ambiguous updates: auto-select first candidate when no choice provided
plans/audits/codex-audit-5-profiles.md:12858:                    if amb.candidates:
plans/audits/codex-audit-5-profiles.md:12859:                        auto_file_id = amb.candidates[0].provider_file_id
plans/audits/codex-audit-5-profiles.md:12863:                            "dependency %s (pack=%s, %d candidates)",
plans/audits/codex-audit-5-profiles.md:12865:                            len(amb.candidates),
plans/audits/codex-audit-5-profiles.md:12928:                    # Find the selected candidate
plans/audits/codex-audit-5-profiles.md:12930:                    for cand in amb.candidates:
plans/audits/codex-audit-5-profiles.md:12933:                    for cand in amb.candidates:
plans/audits/codex-audit-5-profiles.md:13498:  1152	    """A candidate for ambiguous update selection."""
plans/audits/codex-audit-5-profiles.md:13513:  1167	    candidates: List[UpdateCandidate]
plans/audits/codex-audit-5-profiles.md:19730:    candidates: Array<{
src/store/api.py:2311:                    civitai=CivitaiSelector(model_id=0, version_id=0) if request.source == "civitai" else None,
src/store/api.py:2401:                model_id = int(match.group(1)) if match else 0
src/store/update_service.py:174:                        candidates=result.candidates,
src/store/update_service.py:302:        # Handle ambiguous updates: auto-select first candidate when no choice provided
src/store/update_service.py:308:                    if amb.candidates:
src/store/update_service.py:309:                        auto_file_id = amb.candidates[0].provider_file_id
src/store/update_service.py:313:                            "dependency %s (pack=%s, %d candidates)",
src/store/update_service.py:315:                            len(amb.candidates),
src/store/update_service.py:378:                    # Find the selected candidate
src/store/update_service.py:380:                    for cand in amb.candidates:
src/store/update_provider.py:38:    """Whether the update requires user selection (multiple file candidates)."""
src/store/update_provider.py:40:    candidates: List[UpdateCandidate] = field(default_factory=list)
src/store/update_provider.py:41:    """File candidates when ambiguous=True."""
plans/audits/codex-audit-1-resolve-model.md:100:    32	    -> List[ResolutionCandidate]
plans/audits/codex-audit-1-resolve-model.md:102:    34	apply_resolution(pack, dep_id, candidate_id)
plans/audits/codex-audit-1-resolve-model.md:108:    40	- Kazdy kandidat ma stabilni `candidate_id` (UUID) — NE index
plans/audits/codex-audit-1-resolve-model.md:109:    41	- Apply prijima `candidate_id`, ne pozici v seznamu (suggestions se mohou zmenit)
plans/audits/codex-audit-1-resolve-model.md:110:    42	- Manualni resolve (Civitai/HF/Local tab) taky produkuje ResolutionCandidate
plans/audits/codex-audit-1-resolve-model.md:250:   182	  -> { candidates: List[ResolutionCandidate], request_id: str }
plans/audits/codex-audit-1-resolve-model.md:253:   185	  Body: { candidate_id: str }   # UUID z suggest response
plans/audits/codex-audit-1-resolve-model.md:258:   190	  Body: { manual: { strategy, selector_data, canonical_source? } }
plans/audits/codex-audit-1-resolve-model.md:263:   195	**candidate_id vs candidate_index (C4):**
plans/audits/codex-audit-1-resolve-model.md:264:   196	- Suggest vraci kandidaty s UUID `candidate_id`
plans/audits/codex-audit-1-resolve-model.md:265:   197	- Backend si drzi candidates v krat. cache (TTL 5min, keyed by request_id)
plans/audits/codex-audit-1-resolve-model.md:266:   198	- Apply pouziva `candidate_id` — stabilni i kdyz se suggestions mezi tim zmenily
plans/audits/codex-audit-1-resolve-model.md:267:   199	- Pokud candidate_id expired → 409 Conflict, frontend znovu zavola suggest
plans/audits/codex-audit-1-resolve-model.md:300:   232	`apply_resolution()` validuje kompatibilitu resolvovane dependency s packem:
plans/audits/codex-audit-1-resolve-model.md:363:    31	    ResolutionCandidate,
plans/audits/codex-audit-1-resolve-model.md:367:    35	from .resolve_scoring import group_by_provenance, score_candidate
plans/audits/codex-audit-1-resolve-model.md:378:    46	    """Abstraction for candidate cache — injectable, testable."""
plans/audits/codex-audit-1-resolve-model.md:382:    50	        candidates: List[ResolutionCandidate],
plans/audits/codex-audit-1-resolve-model.md:386:    54	        self, request_id: str, candidate_id: str,
plans/audits/codex-audit-1-resolve-model.md:387:    55	    ) -> Optional[ResolutionCandidate]: ...
plans/audits/codex-audit-1-resolve-model.md:405:    73	        candidates: List[ResolutionCandidate],
plans/audits/codex-audit-1-resolve-model.md:409:    77	            "candidates": {c.candidate_id: c for c in candidates},
plans/audits/codex-audit-1-resolve-model.md:414:    82	        self, request_id: str, candidate_id: str,
plans/audits/codex-audit-1-resolve-model.md:415:    83	    ) -> Optional[ResolutionCandidate]:
plans/audits/codex-audit-1-resolve-model.md:422:    90	        return entry["candidates"].get(candidate_id)
plans/audits/codex-audit-1-resolve-model.md:439:   107	    def find_by_candidate_id(
plans/audits/codex-audit-1-resolve-model.md:440:   108	        self, candidate_id: str,
plans/audits/codex-audit-1-resolve-model.md:441:   109	    ) -> Optional[ResolutionCandidate]:
plans/audits/codex-audit-1-resolve-model.md:442:   110	        """Search all non-expired requests for a candidate by ID."""
plans/audits/codex-audit-1-resolve-model.md:447:   115	            c = entry["candidates"].get(candidate_id)
plans/audits/codex-audit-1-resolve-model.md:468:   136	        candidate_cache: Optional[CandidateCacheStore] = None,
plans/audits/codex-audit-1-resolve-model.md:475:   143	        self._cache = candidate_cache or InMemoryCandidateCache()
plans/audits/codex-audit-1-resolve-model.md:507:   175	        """Suggest resolution candidates for a dependency.
plans/audits/codex-audit-1-resolve-model.md:511:   179	        3. Merge EvidenceHit by candidate.key
plans/audits/codex-audit-1-resolve-model.md:576:   244	        # Merge by candidate key and score
plans/audits/codex-audit-1-resolve-model.md:577:   245	        candidates = self._merge_and_score(all_hits, kind, pack, options)
plans/audits/codex-audit-1-resolve-model.md:582:   250	            candidates=candidates[:options.max_candidates],
plans/audits/codex-audit-1-resolve-model.md:589:   257	        self._cache.store(result.request_id, fingerprint, result.candidates)
plans/audits/codex-audit-1-resolve-model.md:703:   264	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-audit-1-resolve-model.md:705:   266	class CanonicalSource(BaseModel):
plans/audits/codex-audit-1-resolve-model.md:718:   279	### 2j. ResolutionCandidate model
plans/audits/codex-audit-1-resolve-model.md:721:   282	class ResolutionCandidate(BaseModel):
plans/audits/codex-audit-1-resolve-model.md:722:   283	    candidate_id: str                          # UUID — stabilni identifikator
plans/audits/codex-audit-1-resolve-model.md:728:   289	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-audit-1-resolve-model.md:766:   327	| Chybi CanonicalSource | HIGH | models.py | Zadne remote identity pole. |
plans/audits/codex-audit-1-resolve-model.md:802:   363	- `apply_resolution()` ODMITNE nesplnujici minimum + cross-kind check (2h)
plans/audits/codex-audit-1-resolve-model.md:841:   402	    |       -> List[ResolutionCandidate] s evidence groups a confidence
plans/audits/codex-audit-1-resolve-model.md:874:   435	    |   |-- Pokud candidates list uz ma TIER-1/2 → default = Candidates (zadny tab aktivni)
plans/audits/codex-audit-1-resolve-model.md:875:   436	    |   |-- Pokud prazdne candidates → default = Preview Analysis (nejintuitivnejsi)
plans/audits/codex-audit-1-resolve-model.md:884:   445	    |   |-- "Use this model" → create candidate + apply (pres validaci)
plans/audits/codex-audit-1-resolve-model.md:890:   451	    |   |-- Vysledky se pridaji do candidates list s TIER-AI
plans/audits/codex-audit-1-resolve-model.md:896:   457	    |   |-- AI dohledava canonical_source pokud available
plans/audits/codex-audit-1-resolve-model.md:912:   473	  - "Apply" = resolve only — produkuje metadata (DependencySelector + CanonicalSource)
plans/audits/codex-audit-1-resolve-model.md:964:   525	| `src/store/models.py:374-382` | DependencySelector | ROZSIRIT (canonical_source) |
plans/audits/codex-audit-1-resolve-model.md:983:   544	**Fix:** apply_resolution() NIKDY neprepise filename stemem.
plans/audits/codex-audit-1-resolve-model.md:1008:   569	1. ✅ CanonicalSource model — models.py (s subfolder polem)
plans/audits/codex-audit-1-resolve-model.md:1009:   570	2. ✅ ResolutionCandidate + EvidenceGroup + EvidenceItem modely — `resolve_models.py`
plans/audits/codex-audit-1-resolve-model.md:1015:   576	6. ✅ Validation matrix — `src/store/resolve_validation.py` (STRATEGY_REQUIREMENTS, validate_candidate, validate_before_apply)
plans/audits/codex-audit-1-resolve-model.md:1026:   587	- ✅ `src/store/resolve_service.py` — suggest/apply orchestrace, candidate cache, lazy providers
plans/audits/codex-audit-1-resolve-model.md:1049:   610	       2. Pro kazdy: `store.suggest(pack, dep_id)` → ulozit candidates + confidence
plans/audits/codex-audit-1-resolve-model.md:1056:   617	       # 1. Precision@1: kolik top-1 candidates je spravnych?
plans/audits/codex-audit-1-resolve-model.md:1059:   620	       # 4. False positive rate: kolik T1 candidates je spatnych?
plans/audits/codex-audit-1-resolve-model.md:1069:   265	        candidate_id: str,
plans/audits/codex-audit-1-resolve-model.md:1072:   268	        """Apply a candidate from a previous suggest.
plans/audits/codex-audit-1-resolve-model.md:1074:   270	        1. Find candidate in cache (by request_id + candidate_id)
plans/audits/codex-audit-1-resolve-model.md:1079:   275	        # Find candidate
plans/audits/codex-audit-1-resolve-model.md:1080:   276	        candidate = None
plans/audits/codex-audit-1-resolve-model.md:1082:   278	            candidate = self._cache.get(request_id, candidate_id)
plans/audits/codex-audit-1-resolve-model.md:1084:   280	            # Search all cached requests for this candidate_id
plans/audits/codex-audit-1-resolve-model.md:1085:   281	            candidate = self._find_candidate_in_cache(candidate_id)
plans/audits/codex-audit-1-resolve-model.md:1087:   283	        if candidate is None:
plans/audits/codex-audit-1-resolve-model.md:1093:   289	        # Build selector from candidate
plans/audits/codex-audit-1-resolve-model.md:1094:   290	        selector = self._candidate_to_selector(candidate)
plans/audits/codex-audit-1-resolve-model.md:1120:   316	            candidate_base_model=getattr(candidate, "base_model", None),
plans/audits/codex-audit-1-resolve-model.md:1133:   329	                    canonical_source=candidate.canonical_source,
plans/audits/codex-audit-1-resolve-model.md:1135:   331	                    display_name=candidate.display_name,
plans/audits/codex-audit-1-resolve-model.md:1159:   355	            canonical_source=manual.canonical_source,
plans/audits/codex-audit-1-resolve-model.md:1172:   368	            candidate_base_model=None,
plans/audits/codex-audit-1-resolve-model.md:1184:   380	                    canonical_source=manual.canonical_source,
plans/audits/codex-audit-1-resolve-model.md:1202:   398	    ) -> List[ResolutionCandidate]:
plans/audits/codex-audit-1-resolve-model.md:1203:   399	        """Merge evidence hits by candidate key, score, and rank."""
plans/audits/codex-audit-1-resolve-model.md:1204:   400	        # Group hits by candidate key
plans/audits/codex-audit-1-resolve-model.md:1209:   405	            key = hit.candidate.key
plans/audits/codex-audit-1-resolve-model.md:1212:   408	                seeds[key] = hit.candidate
plans/audits/codex-audit-1-resolve-model.md:1213:   409	            elif hit.candidate.base_model and not seeds[key].base_model:
plans/audits/codex-audit-1-resolve-model.md:1215:   411	                seeds[key] = hit.candidate
plans/audits/codex-audit-1-resolve-model.md:1217:   413	        # Score each candidate
plans/audits/codex-audit-1-resolve-model.md:1218:   414	        candidates: List[ResolutionCandidate] = []
plans/audits/codex-audit-1-resolve-model.md:1225:   421	            confidence = score_candidate(group_list)
plans/audits/codex-audit-1-resolve-model.md:1229:   425	            candidate_base_model = (
plans/audits/codex-audit-1-resolve-model.md:1234:   430	                pack_base_model, candidate_base_model, kind,
plans/audits/codex-audit-1-resolve-model.md:1237:   433	            candidate = ResolutionCandidate(
plans/audits/codex-audit-1-resolve-model.md:1242:   438	                canonical_source=seed.canonical_source,
plans/audits/codex-audit-1-resolve-model.md:1247:   443	                base_model=candidate_base_model,
plans/audits/codex-audit-1-resolve-model.md:1250:   446	            candidates.append(candidate)
plans/audits/codex-audit-1-resolve-model.md:1253:   449	        candidates.sort(key=lambda c: c.confidence, reverse=True)
plans/audits/codex-audit-1-resolve-model.md:1256:   452	        for i, c in enumerate(candidates):
plans/audits/codex-audit-1-resolve-model.md:1259:   455	        return candidates
plans/audits/codex-audit-1-resolve-model.md:1261:   457	    def _candidate_to_selector(
plans/audits/codex-audit-1-resolve-model.md:1262:   458	        self, candidate: ResolutionCandidate,
plans/audits/codex-audit-1-resolve-model.md:1264:   460	        """Reconstruct DependencySelector from a candidate."""
plans/audits/codex-audit-1-resolve-model.md:1266:   462	            k: v for k, v in candidate.selector_data.items()
plans/audits/codex-audit-1-resolve-model.md:1270:   466	    def _find_candidate_in_cache(
plans/audits/codex-audit-1-resolve-model.md:1271:   467	        self, candidate_id: str,
plans/audits/codex-audit-1-resolve-model.md:1272:   468	    ) -> Optional[ResolutionCandidate]:
plans/audits/codex-audit-1-resolve-model.md:1273:   469	        """Search all cached requests for a candidate.
plans/audits/codex-audit-1-resolve-model.md:1280:   476	            return cache.find_by_candidate_id(candidate_id)
plans/audits/codex-audit-1-resolve-model.md:1323:    16	    CanonicalSource,
plans/audits/codex-audit-1-resolve-model.md:1367:    60	    """What an evidence provider found — a candidate with identification."""
plans/audits/codex-audit-1-resolve-model.md:1370:    63	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-audit-1-resolve-model.md:1378:    71	    """One finding = candidate + evidence why."""
plans/audits/codex-audit-1-resolve-model.md:1379:    72	    candidate: CandidateSeed
plans/audits/codex-audit-1-resolve-model.md:1384:    77	class ResolutionCandidate(BaseModel):
plans/audits/codex-audit-1-resolve-model.md:1385:    78	    """A ranked candidate for dependency resolution."""
plans/audits/codex-audit-1-resolve-model.md:1386:    79	    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
plans/audits/codex-audit-1-resolve-model.md:1392:    85	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-audit-1-resolve-model.md:1443:   136	    max_candidates: int = 10
plans/audits/codex-audit-1-resolve-model.md:1448:   141	    """Result of suggest — list of candidates + metadata."""
plans/audits/codex-audit-1-resolve-model.md:1450:   143	    candidates: List[ResolutionCandidate] = Field(default_factory=list)
plans/audits/codex-audit-1-resolve-model.md:1470:   163	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-audit-1-resolve-model.md:1491:   620	       # 4. False positive rate: kolik T1 candidates je spatnych?
plans/audits/codex-audit-1-resolve-model.md:1502:   631	       - Recall > 80% (80%+ deps s BASE_MODEL_HINT musi dostat alespon 1 spravny candidate)
plans/audits/codex-audit-1-resolve-model.md:1503:   632	       - False T1 rate < 3% (max 3% T1 candidates je spatnych)
plans/audits/codex-audit-1-resolve-model.md:1526:   655	- ✅ `Store.suggest_resolution()` / `apply_resolution()` — delegate metody na Store facade
plans/audits/codex-audit-1-resolve-model.md:1556:   685	- ✅ Gemini 3.1 review: 8 issues — 5 opraveno (tier gaps, FD leak, atomic write, broad except, validation), 3 odlozeno (thread safety=CLI app, search phase=Phase 1, TODO candidate_base_model=Phase 1)
plans/audits/codex-audit-1-resolve-model.md:1557:   686	- ✅ Codex 5.4 review: 6 issues — 3 opraveno (model_id=0, fingerprint stale, ensure_providers truthiness), 3 odlozeno (apply no-op=Phase 1, provider field access=Phase 1 adapter, key unification=Phase 1 search)
plans/audits/codex-audit-1-resolve-model.md:1564:   693	- Fix: model_id=0 rejected validaci (Codex 3)
plans/audits/codex-audit-1-resolve-model.md:1637:   766	5. **Output JSON schema** — candidates[] + search_summary, field requirements per provider
plans/audits/codex-audit-1-resolve-model.md:1640:   769	8. **10 pravidel** — ceiling, no hallucination, max 5 candidates, max 5 tool calls, etc.
plans/audits/codex-audit-1-resolve-model.md:1641:   770	9. **3 few-shot priklady** — strong match, no match (private), multiple candidates
plans/audits/codex-audit-1-resolve-model.md:1712:   841	        # - Extrahuje candidates[] z AI vystupu
plans/audits/codex-audit-1-resolve-model.md:1721:   850	        # - output je dict s klicem "candidates" (list)
plans/audits/codex-audit-1-resolve-model.md:1740:   869	| D1 | `src/store/evidence_providers.py` | ✅ HOTOVO | `AIEvidenceProvider` prepsany: `_build_ai_input()` formatuje strukturovany text, `_ai_candidate_to_hit()` mapuje civitai+hf kandidaty na EvidenceHit, spravne pouziva `TaskResult` (ne raw dict) |
plans/audits/codex-audit-1-resolve-model.md:1746:   875	- Podpora Civitai i HuggingFace kandidatu → `_ai_candidate_to_hit()` routi dle `provider`
plans/audits/codex-audit-1-resolve-model.md:1759:   888	| E5 | Cache binding | Chybi | **PRIDAT** apply kontroluje `pack_name+dep_id` v cached candidates (Codex P1 #3) |
plans/audits/codex-audit-1-resolve-model.md:1770:   899	| F6 | TS typy pro resolve | ✅ IMPL+INTEG | **PRIDANO:** ResolutionCandidate, SuggestResult, ApplyResult, EvidenceItemInfo, EvidenceGroupInfo, ConfidenceLevel, HF_ELIGIBLE_KINDS do types.ts. |
plans/audits/codex-audit-1-resolve-model.md:1799:   928	4. ✅ BLOK D: AIEvidenceProvider rewrite (_build_ai_input, _ai_candidate_to_hit, HF support)
plans/audits/codex-audit-1-resolve-model.md:1810:   939	`_ai_candidate_to_hit()` (civitai/hf) → `_merge_and_score()` → `SuggestResult`.
plans/audits/codex-audit-1-resolve-model.md:1895:  1024	**Cil:** Odstranit `model_id=0` placeholder gap — preview/file hinty ted resolvuji skutecne Civitai IDs.
plans/audits/codex-audit-1-resolve-model.md:1898:  1027	- `PreviewMetaEvidenceProvider` a `FileMetaEvidenceProvider` vytvarily kandidaty s `model_id=0`
plans/audits/codex-audit-1-resolve-model.md:1899:  1028	- `resolve_validation.py` odmitalo `model_id=0` jako "invalid zero value"
plans/audits/codex-audit-1-resolve-model.md:1950:  1079	- Hash → Civitai by-hash API → najde model_id, version_id, canonical_source
plans/audits/codex-audit-1-resolve-model.md:2087:   132	# Auto-apply margin: minimum confidence gap between top-1 and top-2 candidate
plans/audits/codex-audit-1-resolve-model.md:2142:   187	    candidate_base_model: Optional[str],
plans/audits/codex-audit-1-resolve-model.md:2145:   190	    """Check if a candidate is compatible with the pack's base model.
plans/audits/codex-audit-1-resolve-model.md:2155:   200	    if not pack_base_model or not candidate_base_model:
plans/audits/codex-audit-1-resolve-model.md:2162:   207	    if candidate_base_model not in pack_compat:
plans/audits/codex-audit-1-resolve-model.md:2165:   210	            f"but candidate is for '{candidate_base_model}'"
plans/audits/codex-audit-1-resolve-model.md:2223:    51	        """Gather evidence. Returns hits with candidates + evidence."""
plans/audits/codex-audit-1-resolve-model.md:2274:   102	                        candidate_base_model = (
plans/audits/codex-audit-1-resolve-model.md:2290:   118	                            base_model=candidate_base_model,
plans/audits/codex-audit-1-resolve-model.md:2293:   121	                            candidate=seed,
plans/audits/codex-audit-1-resolve-model.md:2321:   149	    3. Placeholder (model_id=0) — last resort for AI/manual resolution
plans/audits/codex-audit-1-resolve-model.md:2374:   202	                        civitai=CivitaiSelector(model_id=0),  # Unresolved
plans/audits/codex-audit-1-resolve-model.md:2381:   209	                candidate=seed,
plans/audits/codex-audit-1-resolve-model.md:2565:   388	                    civitai=CivitaiSelector(model_id=0),  # Needs search
plans/audits/codex-audit-1-resolve-model.md:2571:   394	                candidate=seed,
plans/audits/codex-audit-1-resolve-model.md:2658:   481	                candidate=seed,
plans/audits/codex-audit-1-resolve-model.md:2696:   519	        """Build structured input, call AI task, convert candidates to hits."""
plans/audits/codex-audit-1-resolve-model.md:2716:   539	            candidates = output.get("candidates", [])
plans/audits/codex-audit-1-resolve-model.md:2717:   540	            if not isinstance(candidates, list):
plans/audits/codex-audit-1-resolve-model.md:2718:   541	                return ProviderResult(warnings=["AI returned invalid candidates"])
plans/audits/codex-audit-1-resolve-model.md:2721:   544	            for c in candidates:
plans/audits/codex-audit-1-resolve-model.md:2722:   545	                hit = _ai_candidate_to_hit(c, ctx.dep_id)
plans/audits/codex-audit-1-resolve-model.md:2839:   662	                        candidate=seed,
plans/audits/codex-audit-1-resolve-model.md:2908:   731	                candidate=seed,
plans/audits/codex-audit-1-resolve-model.md:2936:   759	                candidate=seed,
plans/audits/codex-audit-1-resolve-model.md:3011:   829	def _ai_candidate_to_hit(
plans/audits/codex-audit-1-resolve-model.md:3012:   830	    candidate: dict, dep_id: str
plans/audits/codex-audit-1-resolve-model.md:3014:   832	    """Convert a single AI candidate dict to an EvidenceHit.
plans/audits/codex-audit-1-resolve-model.md:3018:   836	    if not isinstance(candidate, dict):
plans/audits/codex-audit-1-resolve-model.md:3021:   839	    provider = candidate.get("provider", "")
plans/audits/codex-audit-1-resolve-model.md:3022:   840	    display_name = candidate.get("display_name", "AI suggestion")
plans/audits/codex-audit-1-resolve-model.md:3023:   841	    confidence = candidate.get("confidence", 0.0)
plans/audits/codex-audit-1-resolve-model.md:3024:   842	    reasoning = candidate.get("reasoning", "AI analysis")
plans/audits/codex-audit-1-resolve-model.md:3031:   849	        model_id = candidate.get("model_id")
plans/audits/codex-audit-1-resolve-model.md:3034:   852	        version_id = candidate.get("version_id")
plans/audits/codex-audit-1-resolve-model.md:3035:   853	        file_id = candidate.get("file_id")
plans/audits/codex-audit-1-resolve-model.md:3058:   876	        repo_id = candidate.get("repo_id")
plans/audits/codex-audit-1-resolve-model.md:3059:   877	        filename = candidate.get("filename")
plans/audits/codex-audit-1-resolve-model.md:3070:   888	                    revision=candidate.get("revision", "main"),
plans/audits/codex-audit-1-resolve-model.md:3080:   898	        candidate=seed,
plans/audits/codex-audit-1-resolve-model.md:3086:   904	            raw_value=str(candidate),
plans/audits/codex-audit-1-resolve-model.md:3111:    19	    CanonicalSource,
plans/audits/codex-audit-1-resolve-model.md:3126:    34	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-audit-1-resolve-model.md:3167:    75	            canonical_source=CanonicalSource(
plans/audits/codex-audit-1-resolve-model.md:3236:   144	                canonical_source=CanonicalSource(
plans/audits/codex-audit-1-resolve-model.md:3320:   228	                        canonical_source=CanonicalSource(
plans/audits/codex-audit-1-resolve-model.md:3472:The backend is not purely stubbed: the resolver, DTOs, config, scoring, and most providers exist. The first concrete gap I see is that some providers still emit placeholder `model_id=0` candidates, which can rank as suggestions but fail validation or require enrichment before apply.
plans/audits/codex-audit-1-resolve-model.md:3573:    98	    canonical_source: Optional[dict] = None
plans/audits/codex-audit-1-resolve-model.md:3912:   432	        apply_error = self._apply_resolution(
plans/audits/codex-audit-1-resolve-model.md:3936:   456	            canonical_source=(
plans/audits/codex-audit-1-resolve-model.md:3937:   457	                enrichment.canonical_source.model_dump()
plans/audits/codex-audit-1-resolve-model.md:3938:   458	                if enrichment.canonical_source
plans/audits/codex-audit-1-resolve-model.md:3979:   499	    def _apply_resolution(
plans/audits/codex-audit-1-resolve-model.md:4006:   526	                    canonical_source=enrichment.canonical_source,
plans/audits/codex-audit-1-resolve-model.md:4014:   534	                    canonical_source=enrichment.canonical_source,
plans/audits/codex-audit-1-resolve-model.md:4041:   561	                    canonical_source=selector_data.canonical_source,
plans/audits/codex-audit-1-resolve-model.md:4047:   567	                    canonical_source=selector_data.canonical_source,
plans/audits/codex-audit-1-resolve-model.md:4416:    34	    3. AvatarEngine calls MCP tools (search, analyze) and returns JSON candidates
plans/audits/codex-audit-1-resolve-model.md:4417:    35	    4. parse_result() normalizes candidates and enforces confidence ceiling
plans/audits/codex-audit-1-resolve-model.md:4446:    64	        """Parse AI output into normalized candidate list.
plans/audits/codex-audit-1-resolve-model.md:4449:    67	        - Extracts candidates list from output
plans/audits/codex-audit-1-resolve-model.md:4450:    68	        - Enforces AI_CONFIDENCE_CEILING on each candidate
plans/audits/codex-audit-1-resolve-model.md:4456:    74	            Dict with "candidates" (list) and "search_summary" (str).
plans/audits/codex-audit-1-resolve-model.md:4459:    77	            return {"candidates": [], "search_summary": "Invalid AI output format"}
plans/audits/codex-audit-1-resolve-model.md:4461:    79	        candidates_raw = raw_output.get("candidates", [])
plans/audits/codex-audit-1-resolve-model.md:4462:    80	        if not isinstance(candidates_raw, list):
plans/audits/codex-audit-1-resolve-model.md:4463:    81	            return {"candidates": [], "search_summary": "Missing candidates list"}
plans/audits/codex-audit-1-resolve-model.md:4465:    83	        parsed_candidates: List[Dict[str, Any]] = []
plans/audits/codex-audit-1-resolve-model.md:4467:    85	        for candidate in candidates_raw:
plans/audits/codex-audit-1-resolve-model.md:4468:    86	            if not isinstance(candidate, dict):
plans/audits/codex-audit-1-resolve-model.md:4472:    90	            confidence = candidate.get("confidence", 0.0)
plans/audits/codex-audit-1-resolve-model.md:4475:    93	            candidate["confidence"] = min(float(confidence), AI_CONFIDENCE_CEILING)
plans/audits/codex-audit-1-resolve-model.md:4478:    96	            provider = candidate.get("provider", "")
plans/audits/codex-audit-1-resolve-model.md:4480:    98	                if not _CIVITAI_REQUIRED.issubset(candidate.keys()):
plans/audits/codex-audit-1-resolve-model.md:4481:    99	                    missing = _CIVITAI_REQUIRED - candidate.keys()
plans/audits/codex-audit-1-resolve-model.md:4483:   101	                        "[dep-resolution] Civitai candidate missing fields: %s",
plans/audits/codex-audit-1-resolve-model.md:4488:   106	                if not _HF_REQUIRED.issubset(candidate.keys()):
plans/audits/codex-audit-1-resolve-model.md:4489:   107	                    missing = _HF_REQUIRED - candidate.keys()
plans/audits/codex-audit-1-resolve-model.md:4491:   109	                        "[dep-resolution] HuggingFace candidate missing fields: %s",
plans/audits/codex-audit-1-resolve-model.md:4496:   114	                if not _COMMON_REQUIRED.issubset(candidate.keys()):
plans/audits/codex-audit-1-resolve-model.md:4499:   117	            parsed_candidates.append(candidate)
plans/audits/codex-audit-1-resolve-model.md:4502:   120	        parsed_candidates.sort(key=lambda c: c["confidence"], reverse=True)
plans/audits/codex-audit-1-resolve-model.md:4505:   123	            "candidates": parsed_candidates,
plans/audits/codex-audit-1-resolve-model.md:4513:   131	        - Empty candidates list (valid "no match" result)
plans/audits/codex-audit-1-resolve-model.md:4514:   132	        - Non-empty candidates with valid confidence bounds
plans/audits/codex-audit-1-resolve-model.md:4518:   136	        - Missing "candidates" key
plans/audits/codex-audit-1-resolve-model.md:4524:   142	        candidates = output.get("candidates")
plans/audits/codex-audit-1-resolve-model.md:4525:   143	        if not isinstance(candidates, list):
plans/audits/codex-audit-1-resolve-model.md:4528:   146	        # Empty candidates is a valid "no match" result
plans/audits/codex-audit-1-resolve-model.md:4529:   147	        if not candidates:
plans/audits/codex-audit-1-resolve-model.md:4532:   150	        # Validate each candidate
plans/audits/codex-audit-1-resolve-model.md:4533:   151	        for c in candidates:
plans/audits/codex-audit-1-resolve-model.md:4669:  2251	    max_candidates: int = 10
plans/audits/codex-audit-1-resolve-model.md:4673:  2255	    """Request to apply a resolution candidate."""
plans/audits/codex-audit-1-resolve-model.md:4675:  2257	    candidate_id: str
plans/audits/codex-audit-1-resolve-model.md:4726:  2308	    """Suggest resolution candidates for a dependency."""
plans/audits/codex-audit-1-resolve-model.md:4743:  2325	            max_candidates=min(request.max_candidates or 20, 50),
plans/audits/codex-audit-1-resolve-model.md:4748:  2330	            "candidates": [c.model_dump() for c in result.candidates],
plans/audits/codex-audit-1-resolve-model.md:4761:  2343	def apply_resolution(
plans/audits/codex-audit-1-resolve-model.md:4766:  2348	    """Apply a previously suggested resolution candidate."""
plans/audits/codex-audit-1-resolve-model.md:4775:  2357	            candidate_id=request.candidate_id,
plans/audits/codex-audit-1-resolve-model.md:5464:   630	            model_id = model.get("id", 0)
plans/audits/codex-audit-1-resolve-model.md:6296:  1398	        """Find blobs not referenced by any pack (candidates for cleanup)."""
plans/audits/codex-audit-1-resolve-model.md:6620:    46	  ResolutionCandidate,
plans/audits/codex-audit-1-resolve-model.md:6635:    61	type ResolverTab = 'candidates' | 'preview' | 'local' | 'ai-resolve' | 'civitai' | 'huggingface'
plans/audits/codex-audit-1-resolve-model.md:6647:    73	  candidates: ResolutionCandidate[]
plans/audits/codex-audit-1-resolve-model.md:6653:    79	  onApply: (candidateId: string) => void
plans/audits/codex-audit-1-resolve-model.md:6654:    80	  onApplyAndDownload: (candidateId: string) => void
plans/audits/codex-audit-1-resolve-model.md:6665:    91	function getConfidenceLevel(candidate: ResolutionCandidate): ConfidenceLevel {
plans/audits/codex-audit-1-resolve-model.md:6666:    92	  if (candidate.tier === 1) return 'exact'
plans/audits/codex-audit-1-resolve-model.md:6667:    93	  if (candidate.tier === 2) return 'high'
plans/audits/codex-audit-1-resolve-model.md:6668:    94	  if (candidate.tier === 3) return 'possible'
plans/audits/codex-audit-1-resolve-model.md:6703:   129	  candidates: ResolutionCandidate[],
plans/audits/codex-audit-1-resolve-model.md:6706:   132	  if (candidates.some((c) => c.tier <= 2)) return 'candidates'
plans/audits/codex-audit-1-resolve-model.md:6707:   133	  if (candidates.length === 0) return 'candidates'
plans/audits/codex-audit-1-resolve-model.md:6709:   135	  return 'candidates'
plans/audits/codex-audit-1-resolve-model.md:6768:   194	  candidate,
plans/audits/codex-audit-1-resolve-model.md:6774:   200	  candidate: ResolutionCandidate
plans/audits/codex-audit-1-resolve-model.md:6780:   206	  const level = getConfidenceLevel(candidate)
plans/audits/codex-audit-1-resolve-model.md:6804:   230	                {candidate.display_name}
plans/audits/codex-audit-1-resolve-model.md:6813:   239	              {candidate.provider && (
plans/audits/codex-audit-1-resolve-model.md:6815:   241	                  {candidate.provider}
plans/audits/codex-audit-1-resolve-model.md:6818:   244	              {candidate.base_model && (
plans/audits/codex-audit-1-resolve-model.md:6820:   246	                  {candidate.base_model}
plans/audits/codex-audit-1-resolve-model.md:6826:   252	            {candidate.compatibility_warnings.length > 0 && (
plans/audits/codex-audit-1-resolve-model.md:6830:   256	                  {candidate.compatibility_warnings[0]}
plans/audits/codex-audit-1-resolve-model.md:6859:   280	      {isExpanded && candidate.evidence_groups.length > 0 && (
plans/audits/codex-audit-1-resolve-model.md:6864:   285	          {candidate.evidence_groups.map((group, gi) => (
plans/audits/codex-audit-1-resolve-model.md:6870:   291	              Score: {(candidate.confidence * 100).toFixed(0)}% (Tier {candidate.tier})
plans/audits/codex-audit-1-resolve-model.md:6907:   328	  candidates,
plans/audits/codex-audit-1-resolve-model.md:6919:   340	  const [tab, setTab] = useState<ResolverTab>('candidates')
plans/audits/codex-audit-1-resolve-model.md:6926:   347	    { id: 'candidates', label: 'Candidates', icon: <Search className="w-4 h-4" />, visible: true },
plans/audits/codex-audit-1-resolve-model.md:6938:   359	      setTab(getDefaultTab(candidates, avatarAvailable))
plans/audits/codex-audit-1-resolve-model.md:6945:   366	  // Auto-select top candidate if TIER-1/2
plans/audits/codex-audit-1-resolve-model.md:6947:   368	    if (candidates.length > 0 && candidates[0].tier <= 2) {
plans/audits/codex-audit-1-resolve-model.md:6948:   369	      setSelectedCandidateId(candidates[0].candidate_id)
plans/audits/codex-audit-1-resolve-model.md:6950:   371	  }, [candidates])
plans/audits/codex-audit-1-resolve-model.md:6956:   377	      if (result.candidates.length > 0) {
plans/audits/codex-audit-1-resolve-model.md:6957:   378	        setTab('candidates')
plans/audits/codex-audit-1-resolve-model.md:6966:   387	  const selectedCandidate = candidates.find((c) => c.candidate_id === selectedCandidateId)
plans/audits/codex-audit-1-resolve-model.md:7030:   451	              badge={tabDef.id === 'candidates' ? candidates.length : undefined}
plans/audits/codex-audit-1-resolve-model.md:7038:   459	          {tab === 'candidates' && (
plans/audits/codex-audit-1-resolve-model.md:7047:   468	              ) : candidates.length === 0 ? (
plans/audits/codex-audit-1-resolve-model.md:7051:   472	                    {t('pack.resolve.noCandidates', 'No candidates found.')}
plans/audits/codex-audit-1-resolve-model.md:7065:   486	                candidates.map((candidate) => (
plans/audits/codex-audit-1-resolve-model.md:7067:   488	                    key={candidate.candidate_id}
plans/audits/codex-audit-1-resolve-model.md:7068:   489	                    candidate={candidate}
plans/audits/codex-audit-1-resolve-model.md:7069:   490	                    isSelected={selectedCandidateId === candidate.candidate_id}
plans/audits/codex-audit-1-resolve-model.md:7070:   491	                    onSelect={() => setSelectedCandidateId(candidate.candidate_id)}
plans/audits/codex-audit-1-resolve-model.md:7071:   492	                    isExpanded={expandedCandidateId === candidate.candidate_id}
plans/audits/codex-audit-1-resolve-model.md:7074:   495	                        expandedCandidateId === candidate.candidate_id
plans/audits/codex-audit-1-resolve-model.md:7076:   497	                          : candidate.candidate_id
plans/audits/codex-audit-1-resolve-model.md:7090:   511	              candidates={candidates}
plans/audits/codex-audit-1-resolve-model.md:7091:   512	              onSelectCandidate={(candidateId) => {
plans/audits/codex-audit-1-resolve-model.md:7092:   513	                setSelectedCandidateId(candidateId)
plans/audits/codex-audit-1-resolve-model.md:7093:   514	                setTab('candidates')
plans/audits/codex-audit-1-resolve-model.md:7201:   617	            onClick={() => selectedCandidate && onApply(selectedCandidate.candidate_id)}
plans/audits/codex-audit-1-resolve-model.md:7217:   633	              selectedCandidate && onApplyAndDownload(selectedCandidate.candidate_id)
plans/audits/codex-audit-1-resolve-model.md:7943:    28	  ResolutionCandidate,
plans/audits/codex-audit-1-resolve-model.md:7953:    38	  candidates: ResolutionCandidate[]
plans/audits/codex-audit-1-resolve-model.md:7954:    39	  onSelectCandidate: (candidateId: string) => void
plans/audits/codex-audit-1-resolve-model.md:8175:   260	  candidates,
plans/audits/codex-audit-1-resolve-model.md:8180:   260	  candidates,
plans/audits/codex-audit-1-resolve-model.md:8197:   277	  // Find matching candidate for a hint
plans/audits/codex-audit-1-resolve-model.md:8199:   279	    // Look for a candidate whose evidence references this preview hint
plans/audits/codex-audit-1-resolve-model.md:8200:   280	    for (const c of candidates) {
plans/audits/codex-audit-1-resolve-model.md:8210:   290	              return c.candidate_id
plans/audits/codex-audit-1-resolve-model.md:8218:   298	        return c.candidate_id
plans/audits/codex-audit-1-resolve-model.md:8225:   305	    const candidateId = findCandidateForHint(hint)
plans/audits/codex-audit-1-resolve-model.md:8226:   306	    if (candidateId) {
plans/audits/codex-audit-1-resolve-model.md:8227:   307	      onSelectCandidate(candidateId)
plans/audits/codex-audit-1-resolve-model.md:8230:   310	        t('pack.resolve.previewRunSuggest', 'No matching candidate found. Run suggestion first.')
plans/audits/codex-audit-1-resolve-model.md:8325:   405	                      canUse={candidates.length > 0}
plans/audits/codex-audit-1-resolve-model.md:8423:    64	  applyResolution: (depId: string, candidateId: string, requestId?: string) => Promise<ApplyResult>
plans/audits/codex-audit-1-resolve-model.md:8426:    67	  applyAndDownload: (depId: string, candidateId: string, requestId?: string) => Promise<void>
plans/audits/codex-audit-1-resolve-model.md:8644:   340	            max_candidates: options?.max_candidates ?? 10,
plans/audits/codex-audit-1-resolve-model.md:8666:   362	      candidateId,
plans/audits/codex-audit-1-resolve-model.md:8670:   366	      candidateId: string
plans/audits/codex-audit-1-resolve-model.md:8680:   376	            candidate_id: candidateId,
plans/audits/codex-audit-1-resolve-model.md:8708:   404	      candidateId,
plans/audits/codex-audit-1-resolve-model.md:8712:   408	      candidateId: string
plans/audits/codex-audit-1-resolve-model.md:8723:   419	            candidate_id: candidateId,
plans/audits/codex-audit-1-resolve-model.md:8884:    56	  type ResolutionCandidate,
plans/audits/codex-audit-1-resolve-model.md:8957:   129	  const [resolveCandidates, setResolveCandidates] = useState<ResolutionCandidate[]>([])
plans/audits/codex-audit-1-resolve-model.md:8977:   149	              setResolveCandidates(result.candidates)
plans/audits/codex-audit-1-resolve-model.md:8991:   163	    async (options?: { include_ai?: boolean; max_candidates?: number }) => {
plans/audits/codex-audit-1-resolve-model.md:8994:   166	      setResolveCandidates(result.candidates)
plans/audits/codex-audit-1-resolve-model.md:9002:   174	    (candidateId: string) => {
plans/audits/codex-audit-1-resolve-model.md:9005:   177	        .applyResolution(resolveDepId, candidateId, resolveRequestId)
plans/audits/codex-audit-1-resolve-model.md:9013:   185	    (candidateId: string) => {
plans/audits/codex-audit-1-resolve-model.md:9016:   188	        .applyAndDownload(resolveDepId, candidateId, resolveRequestId)
plans/audits/codex-audit-1-resolve-model.md:9369:   529	        candidates={resolveCandidates}
plans/audits/codex-audit-1-resolve-model.md:9498:feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:256:        """Create mock avatar that returns specific candidates."""
plans/audits/codex-audit-1-resolve-model.md:9510:feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:92:        mock_version.model_id = 100
plans/audits/codex-audit-1-resolve-model.md:9590:feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:844:    def test_gather_skips_invalid_candidates(self):
plans/audits/codex-audit-1-resolve-model.md:9603:     4	 * Tests the full resolve flow: opening modal, viewing candidates,
plans/audits/codex-audit-1-resolve-model.md:9645:    46	  test('modal shows candidates from eager suggest', async ({ page }) => {
plans/audits/codex-audit-1-resolve-model.md:9649:    50	    // Wait for candidates to load (eager suggest fires on modal open)
plans/audits/codex-audit-1-resolve-model.md:9654:    55	  test('modal shows candidate count badge on tab', async ({ page }) => {
plans/audits/codex-audit-1-resolve-model.md:9659:    60	    const candidatesTab = page.getByRole('button', { name: /Candidates/i })
plans/audits/codex-audit-1-resolve-model.md:9660:    61	    await expect(candidatesTab).toBeVisible({ timeout: 10_000 })
plans/audits/codex-audit-1-resolve-model.md:9661:    62	    // Badge with "2" for two candidates
plans/audits/codex-audit-1-resolve-model.md:9662:    63	    await expect(candidatesTab).toContainText('2')
plans/audits/codex-audit-1-resolve-model.md:9667:    68	  test('clicking a candidate selects it', async ({ page }) => {
plans/audits/codex-audit-1-resolve-model.md:9672:    73	    // Click the first candidate
plans/audits/codex-audit-1-resolve-model.md:9728:   129	  test('candidates show confidence tier badges', async ({ page }) => {
plans/audits/codex-audit-1-resolve-model.md:9733:   134	    // Tier 2 candidate should show "High confidence" indicator
plans/audits/codex-audit-1-resolve-model.md:9739:   140	  test('no candidates shows empty state', async ({ page }) => {
plans/audits/codex-audit-1-resolve-model.md:9752:   153	    // Should show empty/no candidates message or default to preview tab
plans/audits/codex-audit-1-resolve-model.md:9753:   154	    const candidatesTab = page.getByRole('button', { name: /Candidates/i })
plans/audits/codex-audit-1-resolve-model.md:9754:   155	    await expect(candidatesTab).toBeVisible({ timeout: 10_000 })
plans/audits/codex-audit-1-resolve-model.md:10048:   185	    candidates: list[CandidateResult]
plans/audits/codex-audit-1-resolve-model.md:10102:   239	def _evaluate_correctness(scenario: TestScenario, candidates: list[dict]) -> bool:
plans/audits/codex-audit-1-resolve-model.md:10103:   240	    """Check if top candidate looks correct based on expected keywords."""
plans/audits/codex-audit-1-resolve-model.md:10104:   241	    if not candidates:
plans/audits/codex-audit-1-resolve-model.md:10106:   243	    top = candidates[0]
plans/audits/codex-audit-1-resolve-model.md:10139:   271	        # Extract candidates from EvidenceHit objects
plans/audits/codex-audit-1-resolve-model.md:10140:   272	        candidates = []
plans/audits/codex-audit-1-resolve-model.md:10142:   274	            candidates.append({
plans/audits/codex-audit-1-resolve-model.md:10143:   275	                "display_name": hit.candidate.display_name or hit.candidate.key,
plans/audits/codex-audit-1-resolve-model.md:10144:   276	                "provider": hit.candidate.provider_name or "unknown",
plans/audits/codex-audit-1-resolve-model.md:10151:   283	        candidates.sort(key=lambda c: c["confidence"], reverse=True)
plans/audits/codex-audit-1-resolve-model.md:10153:   285	        correct = _evaluate_correctness(scenario, candidates)
plans/audits/codex-audit-1-resolve-model.md:10154:   286	        top = candidates[0] if candidates else {}
plans/audits/codex-audit-1-resolve-model.md:10160:   292	            candidates=[
plans/audits/codex-audit-1-resolve-model.md:10168:   300	                for c in candidates[:5]
plans/audits/codex-audit-1-resolve-model.md:10182:   314	            candidates=[],
plans/audits/codex-audit-1-resolve-model.md:10265:   397	        if not r.candidates:
plans/audits/codex-audit-1-resolve-model.md:10268:   400	        for i, c in enumerate(r.candidates[:3], 1):
plans/audits/codex-audit-1-resolve-model.md:10317:    28	    ResolutionCandidate,
plans/audits/codex-audit-1-resolve-model.md:10387:    98	            civitai=CivitaiSelector(model_id=100, version_id=200, file_id=300),
plans/audits/codex-audit-1-resolve-model.md:10393:   104	        candidate=seed,
plans/audits/codex-audit-1-resolve-model.md:10409:   120	    """Integration: suggest produces candidates, apply consumes them."""
plans/audits/codex-audit-1-resolve-model.md:10418:   129	        assert len(result.candidates) == 1
plans/audits/codex-audit-1-resolve-model.md:10419:   130	        assert result.candidates[0].confidence == 0.95
plans/audits/codex-audit-1-resolve-model.md:10421:   132	        # Apply the top candidate
plans/audits/codex-audit-1-resolve-model.md:10423:   134	            "test-pack", "dep-1", result.candidates[0].candidate_id,
plans/audits/codex-audit-1-resolve-model.md:10435:   146	        """Two providers returning same candidate key → merged, higher confidence."""
plans/audits/codex-audit-1-resolve-model.md:10445:   156	        assert len(result.candidates) == 1
plans/audits/codex-audit-1-resolve-model.md:10447:   158	        assert result.candidates[0].confidence > 0.95
plans/audits/codex-audit-1-resolve-model.md:10449:   160	    def test_suggest_returns_multiple_candidates(self):
plans/audits/codex-audit-1-resolve-model.md:10450:   161	        """Different candidate keys → separate candidates, sorted by confidence."""
plans/audits/codex-audit-1-resolve-model.md:10453:   164	        hit2.candidate = CandidateSeed(
plans/audits/codex-audit-1-resolve-model.md:10457:   168	                civitai=CivitaiSelector(model_id=300, version_id=400, file_id=500),
plans/audits/codex-audit-1-resolve-model.md:10465:   176	        assert len(result.candidates) == 2
plans/audits/codex-audit-1-resolve-model.md:10466:   177	        assert result.candidates[0].confidence > result.candidates[1].confidence
plans/audits/codex-audit-1-resolve-model.md:10566:    33	    """Smoke: _post_import_resolve auto-applies dominant candidates."""
plans/audits/codex-audit-1-resolve-model.md:10652:   119	        assert result.candidates == []
plans/audits/codex-audit-1-resolve-model.md:10655:   122	    def test_apply_resolution_method(self, minimal_store):
plans/audits/codex-audit-1-resolve-model.md:10656:   123	        """Store.apply_resolution delegates to resolve_service."""
plans/audits/codex-audit-1-resolve-model.md:10657:   124	        assert hasattr(minimal_store, "apply_resolution")
plans/audits/codex-audit-1-resolve-model.md:10683:  1079	- Hash → Civitai by-hash API → najde model_id, version_id, canonical_source
plans/audits/codex-audit-1-resolve-model.md:10691:  1087	- Pokud najde → doplni canonical_source, metadata
plans/audits/codex-audit-1-resolve-model.md:10746:  1142	- `_apply_resolution()` buduje `ManualResolveData` dle enrichment strategie (CIVITAI_FILE / HUGGINGFACE_FILE / LOCAL_FILE)
plans/audits/codex-audit-1-resolve-model.md:10770:  1166	- `CanonicalSource(type="civitai")` → `provider="civitai"` (Pydantic field je `provider`, ne `type`)
plans/audits/codex-audit-1-resolve-model.md:10808:  1204	   - `suggest-resolution`: validates dep_id exists in pack (404), max_candidates capped at 50
plans/audits/codex-audit-1-resolve-model.md:10847:  1243	#### 5.1 candidate_base_model v apply() — ResolutionCandidate rozsireni
plans/audits/codex-audit-1-resolve-model.md:10848:  1244	- **Problem:** `apply()` line 314: `candidate_base_model=None` — cross-kind check disabled
plans/audits/codex-audit-1-resolve-model.md:10849:  1245	- **Fix:** Pridat `base_model: Optional[str] = None` na `ResolutionCandidate`
plans/audits/codex-audit-1-resolve-model.md:10850:  1246	- **Kde se plni:** `_merge_and_score()` — extrahovat z `canonical_source` nebo `selector_data`
plans/audits/codex-audit-1-resolve-model.md:10851:  1247	- **Evidence providery** uz maji base_model v CandidateSeed — propagovat do candidate
plans/audits/codex-audit-1-resolve-model.md:10881:  1277	- `src/store/resolve_models.py` — ResolutionCandidate.base_model + CandidateSeed.base_model
plans/audits/codex-audit-1-resolve-model.md:10947:  1343	chybejici DTO, candidate cache, test plan.
plans/audits/codex-audit-1-resolve-model.md:11007:  1403	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-audit-1-resolve-model.md:11014:  1410	    candidate: CandidateSeed
plans/audits/codex-audit-1-resolve-model.md:11038:  1434	    max_candidates: int = 10
plans/audits/codex-audit-1-resolve-model.md:11043:  1439	    candidates: List[ResolutionCandidate] = Field(default_factory=list)
plans/audits/codex-audit-1-resolve-model.md:11060:  1456	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-audit-1-resolve-model.md:11198:  1589	        candidate_cache: Optional[CandidateCacheStore] = None,
plans/audits/codex-audit-1-resolve-model.md:11204:  1595	        self._cache = candidate_cache or InMemoryCandidateCache()
plans/audits/codex-audit-1-resolve-model.md:11230:  1621	        3. Merge EvidenceHit po candidate.key
plans/audits/codex-audit-1-resolve-model.md:11232:  1623	        5. Sort, assign UUID candidate_id, cache
plans/audits/codex-audit-1-resolve-model.md:11237:  1628	    def apply(self, pack_name: str, dep_id: str, candidate_id: str) -> ApplyResult:
plans/audits/codex-audit-1-resolve-model.md:11239:  1630	        1. Najde kandidata v cache (dle request_id + candidate_id)
plans/audits/codex-audit-1-resolve-model.md:11261:  1652	    """Abstrakce pro candidate cache — injectable, testable."""
plans/audits/codex-audit-1-resolve-model.md:11263:  1654	              candidates: List[ResolutionCandidate]) -> None: ...
plans/audits/codex-audit-1-resolve-model.md:11264:  1655	    def get(self, request_id: str, candidate_id: str) -> Optional[ResolutionCandidate]: ...
plans/audits/codex-audit-1-resolve-model.md:11285:  1676	    canonical_source: Optional[CanonicalSource],
plans/audits/codex-audit-1-resolve-model.md:11303:  1694	    # Update selector + canonical_source
plans/audits/codex-audit-1-resolve-model.md:11305:  1696	    if canonical_source:
plans/audits/codex-audit-1-resolve-model.md:11306:  1697	        dep.selector.canonical_source = canonical_source
plans/audits/codex-audit-1-resolve-model.md:11336:  1727	def apply_resolution(self, pack_name, dep_id, candidate_id):
plans/audits/codex-audit-1-resolve-model.md:11337:  1728	    return self.resolve_service.apply(pack_name, dep_id, candidate_id)
plans/audits/codex-audit-1-resolve-model.md:11355:  1746	            if result.candidates and result.candidates[0].tier <= 2:
plans/audits/codex-audit-1-resolve-model.md:11356:  1747	                top = result.candidates[0]
plans/audits/codex-audit-1-resolve-model.md:11357:  1748	                margin = (top.confidence - result.candidates[1].confidence
plans/audits/codex-audit-1-resolve-model.md:11358:  1749	                         if len(result.candidates) > 1 else 1.0)
plans/audits/codex-audit-1-resolve-model.md:11360:  1751	                    self.resolve_service.apply(pack.name, dep.id, top.candidate_id)
plans/audits/codex-audit-1-resolve-model.md:11419:  1810	    candidate_id: Optional[str] = None
plans/audits/codex-audit-1-resolve-model.md:11440:  1831	    if request.candidate_id:
plans/audits/codex-audit-1-resolve-model.md:11441:  1832	        return store.apply_resolution(pack_name, dep_id, request.candidate_id)
plans/audits/codex-audit-1-resolve-model.md:11444:  1835	    raise HTTPException(400, "candidate_id or manual required")
plans/audits/codex-audit-1-resolve-model.md:11464:  1855	  mutationFn: async ({ depId, candidateId, manual }: ApplyParams) => {
plans/audits/codex-audit-1-resolve-model.md:11468:  1859	        candidateId ? { candidate_id: candidateId } : { manual }
plans/audits/codex-audit-1-resolve-model.md:11522:   608	        and auto-applies if a dominant TIER-1/2 candidate exists.
plans/audits/codex-audit-1-resolve-model.md:11554:   640	                    if not result.candidates:
plans/audits/codex-audit-1-resolve-model.md:11557:   643	                    top = result.candidates[0]
plans/audits/codex-audit-1-resolve-model.md:11561:   647	                    # Check margin: no other candidate within auto_apply_margin
plans/audits/codex-audit-1-resolve-model.md:11564:   650	                    if len(result.candidates) > 1:
plans/audits/codex-audit-1-resolve-model.md:11565:   651	                        margin = top.confidence - result.candidates[1].confidence
plans/audits/codex-audit-1-resolve-model.md:11571:   657	                            pack.name, dep.id, top.candidate_id,
plans/audits/codex-audit-1-resolve-model.md:11631:   717	        """Suggest resolution candidates for a dependency."""
plans/audits/codex-audit-1-resolve-model.md:11635:   721	    def apply_resolution(
plans/audits/codex-audit-1-resolve-model.md:11639:   725	        candidate_id: str,
plans/audits/codex-audit-1-resolve-model.md:11642:   728	        """Apply a resolution candidate."""
plans/audits/codex-audit-1-resolve-model.md:11643:   729	        return self.resolve_service.apply(pack_name, dep_id, candidate_id, request_id)
plans/audits/codex-audit-1-resolve-model.md:11649:   735	        """Migration helper: suggest resolution for deps without canonical_source.
plans/audits/codex-audit-1-resolve-model.md:11682:   763	                    "candidates": [],
plans/audits/codex-audit-1-resolve-model.md:11690:   771	                    if result.candidates:
plans/audits/codex-audit-1-resolve-model.md:11691:   772	                        top = result.candidates[0]
plans/audits/codex-audit-1-resolve-model.md:11692:   773	                        entry["candidates"] = [
plans/audits/codex-audit-1-resolve-model.md:11694:   775	                            for c in result.candidates[:3]
plans/audits/codex-audit-1-resolve-model.md:11701:   782	                            if len(result.candidates) > 1:
plans/audits/codex-audit-1-resolve-model.md:11702:   783	                                margin = top.confidence - result.candidates[1].confidence
plans/audits/codex-audit-1-resolve-model.md:11710:   791	                                        pack_name, dep.id, top.candidate_id,
plans/audits/codex-audit-1-resolve-model.md:11887:/bin/bash -lc "git grep -n \"class DependencySelector\\|class CanonicalSource\\|class ResolveConfig\\|HUGGINGFACE_FILE\\|LOCAL_FILE\" feat/resolve-model-redesign -- src/store/models.py | sed -n '1,120p'" in /home/box/git/github/synapse
plans/audits/codex-audit-1-resolve-model.md:11892:feat/resolve-model-redesign:src/store/models.py:381:class CanonicalSource(BaseModel):
plans/audits/codex-audit-1-resolve-model.md:11991:   287	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-1-resolve-model.md:11999:   295	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-1-resolve-model.md:12007:   303	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-1-resolve-model.md:12015:   311	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-1-resolve-model.md:12085:   381	class CanonicalSource(BaseModel):
plans/audits/codex-audit-1-resolve-model.md:12111:   407	    canonical_source: Optional[CanonicalSource] = None
plans/audits/codex-audit-1-resolve-model.md:12155:  1222	        canonical_source: Optional[CanonicalSource] = None,
plans/audits/codex-audit-1-resolve-model.md:12162:  1229	        pack.json with the new selector and optionally canonical_source.
plans/audits/codex-audit-1-resolve-model.md:12169:  1236	            canonical_source: Optional canonical source for update tracking.
plans/audits/codex-audit-1-resolve-model.md:12188:  1255	        # Set canonical_source if provided
plans/audits/codex-audit-1-resolve-model.md:12189:  1256	        if canonical_source:
plans/audits/codex-audit-1-resolve-model.md:12190:  1257	            dep.selector.canonical_source = canonical_source
plans/audits/codex-audit-1-resolve-model.md:12308:    76	def validate_candidate(
plans/audits/codex-audit-1-resolve-model.md:12312:    80	    candidate_base_model: Optional[str] = None,
plans/audits/codex-audit-1-resolve-model.md:12326:    94	        pack_base_model, candidate_base_model, kind,
plans/audits/codex-audit-1-resolve-model.md:12340:   108	    candidate_base_model: Optional[str] = None,
plans/audits/codex-audit-1-resolve-model.md:12342:   110	    """Convenience alias for validate_candidate."""
plans/audits/codex-audit-1-resolve-model.md:12343:   111	    return validate_candidate(selector, kind, pack_base_model, candidate_base_model)
plans/audits/codex-audit-1-resolve-model.md:12364:    17	    """Group evidence hits by provenance, per candidate.
plans/audits/codex-audit-1-resolve-model.md:12424:    77	def score_candidate(groups: List[EvidenceGroup]) -> float:
plans/audits/codex-audit-1-resolve-model.md:12425:    78	    """Score a candidate using provenance grouping + Noisy-OR + tier ceiling.
plans/audits/codex-audit-1-resolve-model.md:13239:+2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
plans/audits/codex-audit-1-resolve-model.md:13264:+1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
plans/audits/codex-audit-1-resolve-model.md:13265:+2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
plans/audits/codex-audit-1-resolve-model.md:13272:+9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.
plans/audits/codex-audit-1-resolve-model.md:13294:+4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audits/codex-audit-1-resolve-model.md:13298:+8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audits/codex-audit-1-resolve-model.md:13312:+3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
plans/audits/codex-audit-1-resolve-model.md:13313:+4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
plans/audits/codex-audit-1-resolve-model.md:13329:+8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.
plans/audits/codex-audit-1-resolve-model.md:13348:+1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
plans/audits/codex-audit-1-resolve-model.md:13367:+6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
plans/audits/codex-audit-1-resolve-model.md:13378:+3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
plans/audits/codex-audit-1-resolve-model.md:13380:+5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
plans/audits/codex-audit-1-resolve-model.md:13391:+5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
plans/audits/codex-audit-1-resolve-model.md:13413:+5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audits/codex-audit-1-resolve-model.md:13415:+7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
plans/audits/codex-audit-1-resolve-model.md:13416:+8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.
plans/audits/codex-audit-1-resolve-model.md:13426:+3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
plans/audits/codex-audit-1-resolve-model.md:13457:+1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
plans/audits/codex-audit-1-resolve-model.md:13458:+2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
plans/audits/codex-audit-1-resolve-model.md:13459:+3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
plans/audits/codex-audit-1-resolve-model.md:13477:+4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audits/codex-audit-1-resolve-model.md:13478:+5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
plans/audits/codex-audit-1-resolve-model.md:13479:+6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
plans/audits/codex-audit-1-resolve-model.md:13541:+4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audits/codex-audit-1-resolve-model.md:13543:+6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audits/codex-audit-1-resolve-model.md:13546:+9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
plans/audits/codex-audit-1-resolve-model.md:13550:+13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
plans/audits/codex-audit-1-resolve-model.md:13556:+2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
plans/audits/codex-audit-1-resolve-model.md:13557:+3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
plans/audits/codex-audit-1-resolve-model.md:13569:+2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
plans/audits/codex-audit-1-resolve-model.md:13572:+5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
plans/audits/codex-audit-1-resolve-model.md:13575:+8. Should canonical source be required for all remote Civitai/HF candidates before apply?
plans/audits/codex-audit-1-resolve-model.md:13587:+5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
plans/audits/codex-audit-1-resolve-model.md:13605:+2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
plans/audits/codex-audit-1-resolve-model.md:13630:+1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
plans/audits/codex-audit-1-resolve-model.md:13631:+2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
plans/audits/codex-audit-1-resolve-model.md:13638:+9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.
plans/audits/codex-audit-1-resolve-model.md:13660:+4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audits/codex-audit-1-resolve-model.md:13664:+8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audits/codex-audit-1-resolve-model.md:13678:+3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
plans/audits/codex-audit-1-resolve-model.md:13679:+4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
plans/audits/codex-audit-1-resolve-model.md:13695:+8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.
plans/audits/codex-audit-1-resolve-model.md:13714:+1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
plans/audits/codex-audit-1-resolve-model.md:13733:+6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
plans/audits/codex-audit-1-resolve-model.md:13744:+3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
plans/audits/codex-audit-1-resolve-model.md:13746:+5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
plans/audits/codex-audit-1-resolve-model.md:13757:+5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
plans/audits/codex-audit-1-resolve-model.md:13779:+5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audits/codex-audit-1-resolve-model.md:13781:+7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
plans/audits/codex-audit-1-resolve-model.md:13782:+8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.
plans/audits/codex-audit-1-resolve-model.md:13792:+3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
plans/audits/codex-audit-1-resolve-model.md:13823:+1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
plans/audits/codex-audit-1-resolve-model.md:13824:+2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
plans/audits/codex-audit-1-resolve-model.md:13825:+3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
plans/audits/codex-audit-1-resolve-model.md:13843:+4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audits/codex-audit-1-resolve-model.md:13844:+5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
plans/audits/codex-audit-1-resolve-model.md:13845:+6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
plans/audits/codex-audit-1-resolve-model.md:13907:+4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audits/codex-audit-1-resolve-model.md:13909:+6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audits/codex-audit-1-resolve-model.md:13912:+9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
plans/audits/codex-audit-1-resolve-model.md:13916:+13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
plans/audits/codex-audit-1-resolve-model.md:13922:+2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
plans/audits/codex-audit-1-resolve-model.md:13923:+3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
plans/audits/codex-audit-1-resolve-model.md:13935:+2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
plans/audits/codex-audit-1-resolve-model.md:13938:+5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
plans/audits/codex-audit-1-resolve-model.md:13941:+8. Should canonical source be required for all remote Civitai/HF candidates before apply?
plans/audits/codex-audit-1-resolve-model.md:13953:+5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
plans/audits/codex-audit-1-resolve-model.md:13983:+2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
plans/audits/codex-audit-1-resolve-model.md:14008:+1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
plans/audits/codex-audit-1-resolve-model.md:14009:+2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
plans/audits/codex-audit-1-resolve-model.md:14016:+9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.
plans/audits/codex-audit-1-resolve-model.md:14038:+4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audits/codex-audit-1-resolve-model.md:14042:+8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audits/codex-audit-1-resolve-model.md:14056:+3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
plans/audits/codex-audit-1-resolve-model.md:14057:+4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
plans/audits/codex-audit-1-resolve-model.md:14073:+8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.
plans/audits/codex-audit-1-resolve-model.md:14092:+1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
plans/audits/codex-audit-1-resolve-model.md:14111:+6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
plans/audits/codex-audit-1-resolve-model.md:14122:+3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
plans/audits/codex-audit-1-resolve-model.md:14124:+5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
plans/audits/codex-audit-1-resolve-model.md:14135:+5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
plans/audits/codex-audit-1-resolve-model.md:14157:+5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audits/codex-audit-1-resolve-model.md:14159:+7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
plans/audits/codex-audit-1-resolve-model.md:14160:+8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.
plans/audits/codex-audit-1-resolve-model.md:14170:+3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
plans/audits/codex-audit-1-resolve-model.md:14201:+1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
plans/audits/codex-audit-1-resolve-model.md:14202:+2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
plans/audits/codex-audit-1-resolve-model.md:14203:+3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
plans/audits/codex-audit-1-resolve-model.md:14221:+4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audits/codex-audit-1-resolve-model.md:14222:+5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
plans/audits/codex-audit-1-resolve-model.md:14223:+6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
plans/audits/codex-audit-1-resolve-model.md:14285:+4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audits/codex-audit-1-resolve-model.md:14287:+6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audits/codex-audit-1-resolve-model.md:14290:+9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
plans/audits/codex-audit-1-resolve-model.md:14294:+13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
plans/audits/codex-audit-1-resolve-model.md:14300:+2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
plans/audits/codex-audit-1-resolve-model.md:14301:+3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
plans/audits/codex-audit-1-resolve-model.md:14313:+2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
plans/audits/codex-audit-1-resolve-model.md:14316:+5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
plans/audits/codex-audit-1-resolve-model.md:14319:+8. Should canonical source be required for all remote Civitai/HF candidates before apply?
plans/audits/codex-audit-1-resolve-model.md:14331:+5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
plans/audits/codex-audit-1-resolve-model.md:14337:It is 359 lines and includes branch-local refs, phase coverage, evidence provider wiring, UI/mock status, preview/AI/test assessment, spec gaps, refactor candidates, and owner questions.
plans/audits/codex-audit-1-resolve-model.md:14345:- Most remote candidates do not populate `canonical_source`.
plans/audits/codex-audit-1-resolve-model.md:14365:+2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
plans/audits/codex-audit-1-resolve-model.md:14390:+1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
plans/audits/codex-audit-1-resolve-model.md:14391:+2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
plans/audits/codex-audit-1-resolve-model.md:14398:+9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.
plans/audits/codex-audit-1-resolve-model.md:14420:+4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audits/codex-audit-1-resolve-model.md:14424:+8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audits/codex-audit-1-resolve-model.md:14438:+3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
plans/audits/codex-audit-1-resolve-model.md:14439:+4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
plans/audits/codex-audit-1-resolve-model.md:14455:+8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.
plans/audits/codex-audit-1-resolve-model.md:14474:+1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
plans/audits/codex-audit-1-resolve-model.md:14493:+6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
plans/audits/codex-audit-1-resolve-model.md:14504:+3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
plans/audits/codex-audit-1-resolve-model.md:14506:+5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
plans/audits/codex-audit-1-resolve-model.md:14517:+5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
plans/audits/codex-audit-1-resolve-model.md:14539:+5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
plans/audits/codex-audit-1-resolve-model.md:14541:+7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
plans/audits/codex-audit-1-resolve-model.md:14542:+8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.
plans/audits/codex-audit-1-resolve-model.md:14552:+3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
plans/audits/codex-audit-1-resolve-model.md:14583:+1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
plans/audits/codex-audit-1-resolve-model.md:14584:+2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
plans/audits/codex-audit-1-resolve-model.md:14585:+3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
plans/audits/codex-audit-1-resolve-model.md:14603:+4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audits/codex-audit-1-resolve-model.md:14604:+5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
plans/audits/codex-audit-1-resolve-model.md:14605:+6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
plans/audits/codex-audit-1-resolve-model.md:14667:+4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
plans/audits/codex-audit-1-resolve-model.md:14669:+6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
plans/audits/codex-audit-1-resolve-model.md:14672:+9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
plans/audits/codex-audit-1-resolve-model.md:14676:+13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
plans/audits/codex-audit-1-resolve-model.md:14682:+2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
plans/audits/codex-audit-1-resolve-model.md:14683:+3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
plans/audits/codex-audit-1-resolve-model.md:14695:+2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
plans/audits/codex-audit-1-resolve-model.md:14698:+5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
plans/audits/codex-audit-1-resolve-model.md:14701:+8. Should canonical source be required for all remote Civitai/HF candidates before apply?
plans/audits/codex-audit-1-resolve-model.md:14713:+5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
plans/audits/codex-audit-1-resolve-model.md:14720:It is 359 lines and includes branch-local refs, phase coverage, evidence provider wiring, UI/mock status, preview/AI/test assessment, spec gaps, refactor candidates, and owner questions.
plans/audits/codex-audit-1-resolve-model.md:14728:- Most remote candidates do not populate `canonical_source`.
src/store/dependency_resolver.py:352:    candidates = files.copy()
src/store/dependency_resolver.py:356:            primary = [f for f in candidates if f.get("primary")]
src/store/dependency_resolver.py:358:                candidates = primary
src/store/dependency_resolver.py:362:                f for f in candidates
src/store/dependency_resolver.py:366:                candidates = ext_filtered
src/store/dependency_resolver.py:368:    return candidates[0] if candidates else None
src/store/civitai_update_provider.py:93:                candidates = self._filter_files(files, dep.selector.constraints)
src/store/civitai_update_provider.py:94:                if len(candidates) == 1:
src/store/civitai_update_provider.py:95:                    target = candidates[0]
src/store/civitai_update_provider.py:151:        candidates = self._filter_files(files, dep.selector.constraints)
src/store/civitai_update_provider.py:153:        if not candidates:
src/store/civitai_update_provider.py:156:        if len(candidates) > 1:
src/store/civitai_update_provider.py:161:                candidates=[
src/store/civitai_update_provider.py:171:                    for f in candidates
src/store/civitai_update_provider.py:175:        # Single candidate - update available
src/store/civitai_update_provider.py:176:        target = candidates[0]
src/store/civitai_update_provider.py:396:                candidate_stem = _VERSION_RE.sub('', fparts[0]).strip("_- ").lower()
src/store/civitai_update_provider.py:397:                if candidate_stem == current_stem:
src/store/civitai_update_provider.py:411:        candidates = files.copy()
src/store/civitai_update_provider.py:416:                primary = [f for f in candidates if f.get("primary")]
src/store/civitai_update_provider.py:418:                    candidates = primary
src/store/civitai_update_provider.py:423:                    f for f in candidates
src/store/civitai_update_provider.py:427:                    candidates = ext_filtered
src/store/civitai_update_provider.py:429:        return candidates
src/store/README.md:190:Ambiguous updates (multiple file candidates) require explicit selection via `--choose`.
src/store/cli.py:735:                        console.print(f"  [yellow]{amb.dependency_id}[/yellow]: {len(amb.candidates)} candidates")
plans/audits/codex-audit-6-ai-integration.md:5569:plans/audits/codex-audit-1-resolve-model.md:300:   232	`apply_resolution()` validuje kompatibilitu resolvovane dependency s packem:
plans/audits/codex-audit-6-ai-integration.md:5572:plans/audits/codex-audit-1-resolve-model.md:367:    35	from .resolve_scoring import group_by_provenance, score_candidate
plans/audits/codex-audit-6-ai-integration.md:5574:plans/audits/codex-audit-1-resolve-model.md:507:   175	        """Suggest resolution candidates for a dependency.
plans/audits/codex-audit-6-ai-integration.md:5577:plans/audits/codex-audit-1-resolve-model.md:576:   244	        # Merge by candidate key and score
plans/audits/codex-audit-6-ai-integration.md:5578:plans/audits/codex-audit-1-resolve-model.md:577:   245	        candidates = self._merge_and_score(all_hits, kind, pack, options)
plans/audits/codex-audit-6-ai-integration.md:5603:plans/audits/codex-audit-1-resolve-model.md:1203:   399	        """Merge evidence hits by candidate key, score, and rank."""
plans/audits/codex-audit-6-ai-integration.md:5604:plans/audits/codex-audit-1-resolve-model.md:1225:   421	            confidence = score_candidate(group_list)
plans/audits/codex-audit-6-ai-integration.md:5609:plans/audits/codex-audit-1-resolve-model.md:1385:    78	    """A ranked candidate for dependency resolution."""
plans/audits/codex-audit-6-ai-integration.md:5631:plans/audits/codex-audit-1-resolve-model.md:1810:   939	`_ai_candidate_to_hit()` (civitai/hf) → `_merge_and_score()` → `SuggestResult`.
plans/audits/codex-audit-6-ai-integration.md:6003:src/store/cli.py:735:                        console.print(f"  [yellow]{amb.dependency_id}[/yellow]: {len(amb.candidates)} candidates")
plans/audits/codex-audit-6-ai-integration.md:6059:plans/audits/codex-audit-5-profiles.md:12863:                            "dependency %s (pack=%s, %d candidates)",
plans/audits/codex-audit-6-ai-integration.md:6282:src/store/update_service.py:313:                            "dependency %s (pack=%s, %d candidates)",
plans/audits/codex-audit-6-ai-integration.md:6491:plans/audits/codex-audit-2-custom-pack.md:10838:   313	                            "dependency %s (pack=%s, %d candidates)",
plans/audits/codex-audit-6-ai-integration.md:6541:apps/web/src/__tests__/updates-store.test.ts:82:        { dependency_id: 'main-ckpt', candidates: [] },
plans/audits/codex-audit-6-ai-integration.md:6543:apps/web/src/__tests__/updates-store.test.ts:97:        { dependency_id: 'checkpoint', candidates: [] },
plans/audits/codex-audit-6-ai-integration.md:10558:src/store/update_provider.py:38:    """Whether the update requires user selection (multiple file candidates)."""
plans/audits/codex-audit-6-ai-integration.md:12609:  1246	        """Find blobs not referenced by any pack (candidates for cleanup)."""
plans/audits/codex-audit-6-ai-integration.md:12885:   614	            model_id = model.get("id", 0)
plans/audits/codex-audit-6-ai-integration.md:14025:    34	    3. AvatarEngine calls MCP tools (search, analyze) and returns JSON candidates
plans/audits/codex-audit-6-ai-integration.md:14026:    35	    4. parse_result() normalizes candidates and enforces confidence ceiling
plans/audits/codex-audit-6-ai-integration.md:14055:    64	        """Parse AI output into normalized candidate list.
plans/audits/codex-audit-6-ai-integration.md:14058:    67	        - Extracts candidates list from output
plans/audits/codex-audit-6-ai-integration.md:14059:    68	        - Enforces AI_CONFIDENCE_CEILING on each candidate
plans/audits/codex-audit-6-ai-integration.md:14065:    74	            Dict with "candidates" (list) and "search_summary" (str).
plans/audits/codex-audit-6-ai-integration.md:14068:    77	            return {"candidates": [], "search_summary": "Invalid AI output format"}
plans/audits/codex-audit-6-ai-integration.md:14070:    79	        candidates_raw = raw_output.get("candidates", [])
plans/audits/codex-audit-6-ai-integration.md:14071:    80	        if not isinstance(candidates_raw, list):
plans/audits/codex-audit-6-ai-integration.md:14072:    81	            return {"candidates": [], "search_summary": "Missing candidates list"}
plans/audits/codex-audit-6-ai-integration.md:14074:    83	        parsed_candidates: List[Dict[str, Any]] = []
plans/audits/codex-audit-6-ai-integration.md:14076:    85	        for candidate in candidates_raw:
plans/audits/codex-audit-6-ai-integration.md:14077:    86	            if not isinstance(candidate, dict):
plans/audits/codex-audit-6-ai-integration.md:14081:    90	            confidence = candidate.get("confidence", 0.0)
plans/audits/codex-audit-6-ai-integration.md:14084:    93	            candidate["confidence"] = min(float(confidence), AI_CONFIDENCE_CEILING)
plans/audits/codex-audit-6-ai-integration.md:14087:    96	            provider = candidate.get("provider", "")
plans/audits/codex-audit-6-ai-integration.md:14089:    98	                if not _CIVITAI_REQUIRED.issubset(candidate.keys()):
plans/audits/codex-audit-6-ai-integration.md:14090:    99	                    missing = _CIVITAI_REQUIRED - candidate.keys()
plans/audits/codex-audit-6-ai-integration.md:14092:   101	                        "[dep-resolution] Civitai candidate missing fields: %s",
plans/audits/codex-audit-6-ai-integration.md:14097:   106	                if not _HF_REQUIRED.issubset(candidate.keys()):
plans/audits/codex-audit-6-ai-integration.md:14098:   107	                    missing = _HF_REQUIRED - candidate.keys()
plans/audits/codex-audit-6-ai-integration.md:14100:   109	                        "[dep-resolution] HuggingFace candidate missing fields: %s",
plans/audits/codex-audit-6-ai-integration.md:14105:   114	                if not _COMMON_REQUIRED.issubset(candidate.keys()):
plans/audits/codex-audit-6-ai-integration.md:14108:   117	            parsed_candidates.append(candidate)
plans/audits/codex-audit-6-ai-integration.md:14111:   120	        parsed_candidates.sort(key=lambda c: c["confidence"], reverse=True)
plans/audits/codex-audit-6-ai-integration.md:14114:   123	            "candidates": parsed_candidates,
plans/audits/codex-audit-6-ai-integration.md:14122:   131	        - Empty candidates list (valid "no match" result)
plans/audits/codex-audit-6-ai-integration.md:14123:   132	        - Non-empty candidates with valid confidence bounds
plans/audits/codex-audit-6-ai-integration.md:14127:   136	        - Missing "candidates" key
plans/audits/codex-audit-6-ai-integration.md:14133:   142	        candidates = output.get("candidates")
plans/audits/codex-audit-6-ai-integration.md:14134:   143	        if not isinstance(candidates, list):
plans/audits/codex-audit-6-ai-integration.md:14137:   146	        # Empty candidates is a valid "no match" result
plans/audits/codex-audit-6-ai-integration.md:14138:   147	        if not candidates:
plans/audits/codex-audit-6-ai-integration.md:14141:   150	        # Validate each candidate
plans/audits/codex-audit-6-ai-integration.md:14142:   151	        for c in candidates:
plans/audits/codex-audit-6-ai-integration.md:14163:   481	                candidate=seed,
plans/audits/codex-audit-6-ai-integration.md:14201:   519	        """Build structured input, call AI task, convert candidates to hits."""
plans/audits/codex-audit-6-ai-integration.md:14221:   539	            candidates = output.get("candidates", [])
plans/audits/codex-audit-6-ai-integration.md:14222:   540	            if not isinstance(candidates, list):
plans/audits/codex-audit-6-ai-integration.md:14223:   541	                return ProviderResult(warnings=["AI returned invalid candidates"])
plans/audits/codex-audit-6-ai-integration.md:14226:   544	            for c in candidates:
plans/audits/codex-audit-6-ai-integration.md:14227:   545	                hit = _ai_candidate_to_hit(c, ctx.dep_id)
plans/audits/codex-audit-6-ai-integration.md:15449:   280	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-6-ai-integration.md:15457:   288	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-6-ai-integration.md:15465:   296	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-6-ai-integration.md:15473:   304	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
plans/audits/codex-audit-6-ai-integration.md:15586:  2311	                    civitai=CivitaiSelector(model_id=0, version_id=0) if request.source == "civitai" else None,
plans/audits/codex-audit-2-custom-pack.md:1628:src/store/models.py:1152:    """A candidate for ambiguous update selection."""
plans/audits/codex-audit-2-custom-pack.md:6282:  2311	                    civitai=CivitaiSelector(model_id=0, version_id=0) if request.source == "civitai" else None,
plans/audits/codex-audit-2-custom-pack.md:6372:  2401	                model_id = int(match.group(1)) if match else 0
plans/audits/codex-audit-2-custom-pack.md:10128:   352	    candidates = files.copy()
plans/audits/codex-audit-2-custom-pack.md:10132:   356	            primary = [f for f in candidates if f.get("primary")]
plans/audits/codex-audit-2-custom-pack.md:10134:   358	                candidates = primary
plans/audits/codex-audit-2-custom-pack.md:10694:   174	                        candidates=result.candidates,
plans/audits/codex-audit-2-custom-pack.md:10827:   302	        # Handle ambiguous updates: auto-select first candidate when no choice provided
plans/audits/codex-audit-2-custom-pack.md:10833:   308	                    if amb.candidates:
plans/audits/codex-audit-2-custom-pack.md:10834:   309	                        auto_file_id = amb.candidates[0].provider_file_id
plans/audits/codex-audit-2-custom-pack.md:10838:   313	                            "dependency %s (pack=%s, %d candidates)",
plans/audits/codex-audit-2-custom-pack.md:10840:   315	                            len(amb.candidates),
plans/audits/codex-audit-2-custom-pack.md:11137:    38	    """Whether the update requires user selection (multiple file candidates)."""
plans/audits/codex-audit-2-custom-pack.md:11139:    40	    candidates: List[UpdateCandidate] = field(default_factory=list)
plans/audits/codex-audit-2-custom-pack.md:11140:    41	    """File candidates when ambiguous=True."""
plans/audits/codex-audit-2-custom-pack.md:18216:plans/audits/codex-audit-1-resolve-model.md:1950:  1079	- Hash → Civitai by-hash API → najde model_id, version_id, canonical_source
plans/audits/codex-audit-2-custom-pack.md:22093:   206	                civitai={"model_id": 123, "version_id": 200},
plans/audits/codex-audit-2-custom-pack.md:22173:   286	                civitai={"model_id": 123, "version_id": 200, "file_id": 2002},
plans/audits/codex-audit-2-custom-pack.md:22221:   334	        mock_alias.selector.civitai.model_id = 10
plans/audits/codex-audit-2-custom-pack.md:22357:tests/e2e/test_core_workflows.py:364:            _create_pack_with_lock(store, name="BatchAPack", model_id=400, version_id=401, file_id=4011, sha256="old_a")
plans/audits/codex-audit-2-custom-pack.md:22358:tests/e2e/test_core_workflows.py:365:            _create_pack_with_lock(store, name="BatchBPack", model_id=500, version_id=501, file_id=5011, sha256="old_b")
plans/audits/codex-audit-2-custom-pack.md:22360:tests/e2e/test_core_workflows.py:567:            _create_pack_with_lock(store, name="SinglePack", model_id=800,
plans/audits/codex-audit-2-custom-pack.md:22362:tests/e2e/test_core_workflows.py:719:            _create_pack_with_lock(store, name="UpdateJourneyPack", model_id=1100,
plans/audits/codex-audit-2-custom-pack.md:22363:tests/e2e/test_core_workflows.py:762:        _create_pack_with_lock(store, name="PinnedPack", model_id=1200,
plans/audits/codex-audit-2-custom-pack.md:22364:tests/e2e/test_core_workflows.py:774:        _create_pack_with_lock(store, name="UpToDate", model_id=1300,
plans/audits/codex-audit-2-custom-pack.md:22365:tests/e2e/test_core_workflows.py:792:            _create_pack_with_lock(store, name="BatchAP", model_id=1400, version_id=1401, file_id=14011, sha256="a_old")
plans/audits/codex-audit-2-custom-pack.md:22366:tests/e2e/test_core_workflows.py:793:            _create_pack_with_lock(store, name="BatchBP", model_id=1500, version_id=1501, file_id=15011, sha256="b_old")
plans/audits/codex-audit-2-custom-pack.md:22370:tests/e2e/test_core_workflows.py:1131:            _create_pack_with_lock(store, name="UpdatablePack", model_id=1900,
plans/audits/codex-audit-2-custom-pack.md:22371:tests/e2e/test_core_workflows.py:1133:            _create_pack_with_lock(store, name="CurrentPack", model_id=2000,
plans/audits/codex-audit-2-custom-pack.md:22372:tests/e2e/test_core_workflows.py:1135:            _create_pack_with_lock(store, name="PinnedPack", model_id=2100,
plans/audits/codex-audit-2-custom-pack.md:22375:tests/e2e/test_core_workflows.py:1298:        _create_pack_with_lock(store, name="UrlChainPack", model_id=2200,
plans/audits/codex-audit-2-custom-pack.md:22376:tests/e2e/test_core_workflows.py:1326:            _create_pack_with_lock(store, name="DlAssetPack", model_id=2300,
plans/audits/codex-audit-2-custom-pack.md:22377:tests/e2e/test_core_workflows.py:1625:        _create_pack_with_lock(store, name="ProvInfoPack", model_id=2600,
plans/audits/codex-audit-2-custom-pack.md:22378:tests/e2e/test_core_workflows.py:1648:            _create_pack_with_lock(store, name="OptTestPack", model_id=2700,
plans/audits/codex-audit-2-custom-pack.md:22836:tests/store/test_update_e2e.py:497:        pack = _make_pack("my-pack", model_id=500, description="My custom notes")
plans/audits/codex-audit-2-custom-pack.md:22837:tests/store/test_update_e2e.py:527:        pack = _make_pack("my-pack", model_id=500, description="My custom notes")
plans/audits/codex-audit-2-custom-pack.md:23235:   572	                civitai={"model_id": 1, "version_id": 100, "file_id": 1},
plans/audits/codex-audit-2-custom-pack.md:23299:   676	            source=PackSource(provider=ProviderName.CIVITAI, model_id=1000),
plans/audits/codex-audit-2-custom-pack.md:23305:   682	                        civitai=CivitaiSelector(model_id=1000, version_id=1001, file_id=10011),
plans/audits/codex-audit-2-custom-pack.md:23336:  1298	        _create_pack_with_lock(store, name="UrlChainPack", model_id=2200,
plans/audits/codex-audit-2-custom-pack.md:23364:  1326	            _create_pack_with_lock(store, name="DlAssetPack", model_id=2300,
plans/audits/codex-audit-2-custom-pack.md:24235:   109	                    civitai=CivitaiSelector(model_id=100, version_id=200, file_id=300),
plans/audits/codex-audit-2-custom-pack.md:24544:  2308	    """Suggest resolution candidates for a dependency."""
plans/audits/codex-audit-2-custom-pack.md:24561:  2325	            max_candidates=min(request.max_candidates or 20, 50),
plans/audits/codex-audit-2-custom-pack.md:24566:  2330	            "candidates": [c.model_dump() for c in result.candidates],
plans/audits/codex-audit-2-custom-pack.md:24579:  2343	def apply_resolution(
plans/audits/codex-audit-2-custom-pack.md:24584:  2348	    """Apply a previously suggested resolution candidate."""
plans/audits/codex-audit-2-custom-pack.md:24593:  2357	            candidate_id=request.candidate_id,
plans/audits/codex-audit-2-custom-pack.md:24889:    46	  ResolutionCandidate,
plans/audits/codex-audit-2-custom-pack.md:24904:    61	type ResolverTab = 'candidates' | 'preview' | 'local' | 'ai-resolve' | 'civitai' | 'huggingface'
plans/audits/codex-audit-2-custom-pack.md:24916:    73	  candidates: ResolutionCandidate[]
plans/audits/codex-audit-2-custom-pack.md:24922:    79	  onApply: (candidateId: string) => void
plans/audits/codex-audit-2-custom-pack.md:24923:    80	  onApplyAndDownload: (candidateId: string) => void
plans/audits/codex-audit-2-custom-pack.md:24934:    91	function getConfidenceLevel(candidate: ResolutionCandidate): ConfidenceLevel {
plans/audits/codex-audit-2-custom-pack.md:24935:    92	  if (candidate.tier === 1) return 'exact'
plans/audits/codex-audit-2-custom-pack.md:24936:    93	  if (candidate.tier === 2) return 'high'
plans/audits/codex-audit-2-custom-pack.md:24937:    94	  if (candidate.tier === 3) return 'possible'
plans/audits/codex-audit-2-custom-pack.md:24972:   129	  candidates: ResolutionCandidate[],
plans/audits/codex-audit-2-custom-pack.md:24975:   132	  if (candidates.some((c) => c.tier <= 2)) return 'candidates'
plans/audits/codex-audit-2-custom-pack.md:24976:   133	  if (candidates.length === 0) return 'candidates'
plans/audits/codex-audit-2-custom-pack.md:24978:   135	  return 'candidates'
plans/audits/codex-audit-2-custom-pack.md:25037:   194	  candidate,
plans/audits/codex-audit-2-custom-pack.md:25043:   200	  candidate: ResolutionCandidate
plans/audits/codex-audit-2-custom-pack.md:25049:   206	  const level = getConfidenceLevel(candidate)
plans/audits/codex-audit-2-custom-pack.md:25074:64:    64	  applyResolution: (depId: string, candidateId: string, requestId?: string) => Promise<ApplyResult>
plans/audits/codex-audit-2-custom-pack.md:25083:880:   880	    applyResolution: (depId, candidateId, requestId) =>
plans/audits/codex-audit-2-custom-pack.md:25084:881:   881	      applyResolutionMutation.mutateAsync({ depId, candidateId, requestId }),
plans/audits/codex-audit-2-custom-pack.md:25339:2311:                    civitai=CivitaiSelector(model_id=0, version_id=0) if request.source == "civitai" else None,

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/models.py | rg -n \"CanonicalSource|DependencySelector|PackSource|class Pack\\(|source:|canonical_source|hash_sha256|sha256|HuggingFaceSelector\"" in /home/box/git/github/synapse
 succeeded in 0ms:
366:class HuggingFaceSelector(BaseModel):
381:class CanonicalSource(BaseModel):
395:    sha256: Optional[str] = None
398:class DependencySelector(BaseModel):
402:    huggingface: Optional[HuggingFaceSelector] = None
407:    canonical_source: Optional[CanonicalSource] = None
436:    selector: DependencySelector
447:class PackSource(BaseModel):
811:    hash_sha256: Optional[str] = None
862:class Pack(BaseModel):
868:    source: PackSource
896:    parameters_source: Optional[str] = None  # AI provider that extracted params (e.g., "ollama", "rule_based")
969:    sha256_verified: bool = False
975:    sha256: Optional[str] = None
1140:    sha256: str
1184:    sha256: Optional[str] = None
1198:    sha256: str
1361:    sha256: str
1363:    display_name: str  # Priority: expose.filename > origin.filename > sha256[:12]
1445:    sha256: str
1498:    sha256: str
1508:    sha256: str
1516:    sha256: str

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/models.py | nl -ba | sed -n '350,470p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   350	        )
   351	
   352	
   353	# =============================================================================
   354	# Pack Models (state/packs/<Pack>/pack.json)
   355	# =============================================================================
   356	
   357	class CivitaiSelector(BaseModel):
   358	    """Civitai-specific selector data."""
   359	    model_config = ConfigDict(protected_namespaces=())
   360	    
   361	    model_id: int
   362	    version_id: Optional[int] = None
   363	    file_id: Optional[int] = None
   364	
   365	
   366	class HuggingFaceSelector(BaseModel):
   367	    """HuggingFace-specific selector data."""
   368	    repo_id: str
   369	    filename: str
   370	    revision: Optional[str] = None
   371	    subfolder: Optional[str] = None
   372	
   373	
   374	class SelectorConstraints(BaseModel):
   375	    """Constraints for file selection."""
   376	    primary_file_only: bool = True
   377	    file_ext: List[str] = Field(default_factory=lambda: [".safetensors"])
   378	    base_model_hint: Optional[str] = None
   379	
   380	
   381	class CanonicalSource(BaseModel):
   382	    """Remote identity for update tracking — independent of install strategy.
   383	
   384	    Allows a locally-installed file to track its canonical remote source
   385	    for update checking and re-downloading.
   386	    """
   387	    provider: Literal["civitai", "huggingface"]
   388	    model_id: Optional[int] = None       # Civitai
   389	    version_id: Optional[int] = None     # Civitai
   390	    file_id: Optional[int] = None        # Civitai
   391	    repo_id: Optional[str] = None        # HuggingFace
   392	    filename: Optional[str] = None
   393	    subfolder: Optional[str] = None      # HF repos with multiple subfolders
   394	    revision: Optional[str] = None       # HF commit/tag
   395	    sha256: Optional[str] = None
   396	
   397	
   398	class DependencySelector(BaseModel):
   399	    """Selector for resolving a dependency."""
   400	    strategy: SelectorStrategy
   401	    civitai: Optional[CivitaiSelector] = None
   402	    huggingface: Optional[HuggingFaceSelector] = None
   403	    base_model: Optional[str] = None  # For base_model_hint strategy
   404	    url: Optional[str] = None  # For url_download strategy
   405	    local_path: Optional[str] = None  # For local_file strategy
   406	    constraints: Optional[SelectorConstraints] = None
   407	    canonical_source: Optional[CanonicalSource] = None
   408	
   409	
   410	class UpdatePolicy(BaseModel):
   411	    """Update policy for a dependency."""
   412	    mode: UpdatePolicyMode = UpdatePolicyMode.PINNED
   413	    
   414	    @classmethod
   415	    def from_string(cls, value: str) -> "UpdatePolicy":
   416	        """Create UpdatePolicy from string shorthand."""
   417	        return cls(mode=UpdatePolicyMode(value))
   418	
   419	
   420	class ExposeConfig(BaseModel):
   421	    """Configuration for how an asset is exposed to UI."""
   422	    filename: str
   423	    trigger_words: List[str] = Field(default_factory=list)
   424	    
   425	    @field_validator("filename")
   426	    @classmethod
   427	    def validate_filename(cls, v: str) -> str:
   428	        return validate_safe_filename(v)
   429	
   430	
   431	class PackDependency(BaseModel):
   432	    """A single dependency within a pack."""
   433	    id: str
   434	    kind: AssetKind
   435	    required: bool = True
   436	    selector: DependencySelector
   437	    update_policy: UpdatePolicy = Field(default_factory=UpdatePolicy)
   438	    expose: ExposeConfig
   439	    description: Optional[str] = None  # Optional description for the dependency
   440	    
   441	    @field_validator("id")
   442	    @classmethod
   443	    def validate_id(cls, v: str) -> str:
   444	        return validate_safe_name(v)
   445	
   446	
   447	class PackSource(BaseModel):
   448	    """Source information for a pack."""
   449	    model_config = ConfigDict(protected_namespaces=())
   450	    
   451	    provider: ProviderName
   452	    model_id: Optional[int] = None
   453	    version_id: Optional[int] = None
   454	    url: Optional[str] = None
   455	
   456	
   457	class PackResources(BaseModel):
   458	    """Resource configuration for a pack."""
   459	    previews_keep_in_git: bool = True
   460	    workflows_keep_in_git: bool = True
   461	
   462	
   463	class PackDependencyRef(BaseModel):
   464	    """
   465	    Reference to another pack this pack depends on.
   466	
   467	    This enables pack dependency trees where:
   468	    - A LoRA pack can depend on a Checkpoint pack (its base model)
   469	    - A Workflow pack can depend on all required LoRA/VAE packs
   470	    - An Install pack can depend on another Install pack

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_service.py | nl -ba | sed -n '250,360p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   250	            candidates=candidates[:options.max_candidates],
   251	            pack_fingerprint=fingerprint,
   252	            warnings=warnings,
   253	            preview_hints=preview_hints,
   254	        )
   255	
   256	        # Cache for apply
   257	        self._cache.store(result.request_id, fingerprint, result.candidates)
   258	
   259	        return result
   260	
   261	    def apply(
   262	        self,
   263	        pack_name: str,
   264	        dep_id: str,
   265	        candidate_id: str,
   266	        request_id: Optional[str] = None,
   267	    ) -> ApplyResult:
   268	        """Apply a candidate from a previous suggest.
   269	
   270	        1. Find candidate in cache (by request_id + candidate_id)
   271	        2. Validate: min fields + cross-kind check
   272	        3. Delegate to pack_service.apply_dependency_resolution()
   273	        4. Return ApplyResult
   274	        """
   275	        # Find candidate
   276	        candidate = None
   277	        if request_id:
   278	            candidate = self._cache.get(request_id, candidate_id)
   279	        else:
   280	            # Search all cached requests for this candidate_id
   281	            candidate = self._find_candidate_in_cache(candidate_id)
   282	
   283	        if candidate is None:
   284	            return ApplyResult(
   285	                success=False,
   286	                message="Candidate not found or expired. Please re-run suggest.",
   287	            )
   288	
   289	        # Build selector from candidate
   290	        selector = self._candidate_to_selector(candidate)
   291	
   292	        # Check fingerprint staleness (warn but don't block)
   293	        stale_warnings: List[str] = []
   294	        if request_id and pack_name:
   295	            try:
   296	                pack_for_fp = self._pack_service.layout.load_pack(pack_name) if hasattr(self._pack_service, "layout") else None
   297	                if pack_for_fp:
   298	                    current_fp = _compute_pack_fingerprint(pack_for_fp)
   299	                    if not self._cache.check_fingerprint(request_id, current_fp):
   300	                        stale_warnings.append(
   301	                            "Pack has changed since suggest was run. "
   302	                            "Results may be stale — consider re-running suggest."
   303	                        )
   304	            except Exception:
   305	                pass  # Non-critical check
   306	
   307	        # Validate
   308	        pack = self._pack_service.layout.load_pack(pack_name) if hasattr(self._pack_service, "layout") else None
   309	        dep = _find_dependency(pack, dep_id) if pack else None
   310	        kind = getattr(dep, "kind", AssetKind.UNKNOWN) if dep else AssetKind.UNKNOWN
   311	        pack_base_model = getattr(pack, "base_model", None) if pack else None
   312	
   313	        validation = validate_before_apply(
   314	            selector, kind,
   315	            pack_base_model=pack_base_model,
   316	            candidate_base_model=getattr(candidate, "base_model", None),
   317	        )
   318	
   319	        if not validation.success:
   320	            return validation
   321	
   322	        # Delegate write to pack_service
   323	        try:
   324	            if hasattr(self._pack_service, "apply_dependency_resolution"):
   325	                self._pack_service.apply_dependency_resolution(
   326	                    pack_name=pack_name,
   327	                    dep_id=dep_id,
   328	                    selector=selector,
   329	                    canonical_source=candidate.canonical_source,
   330	                    lock_entry=None,
   331	                    display_name=candidate.display_name,
   332	                )
   333	            all_warnings = stale_warnings + (validation.compatibility_warnings or [])
   334	            return ApplyResult(
   335	                success=True,
   336	                message="Resolution applied",
   337	                compatibility_warnings=all_warnings,
   338	            )
   339	        except Exception as e:
   340	            return ApplyResult(success=False, message=f"Apply failed: {e}")
   341	
   342	    def apply_manual(
   343	        self,
   344	        pack_name: str,
   345	        dep_id: str,
   346	        manual: ManualResolveData,
   347	    ) -> ApplyResult:
   348	        """Apply manual resolve data. Same validation as apply."""
   349	        selector = DependencySelector(
   350	            strategy=manual.strategy,
   351	            civitai=manual.civitai,
   352	            huggingface=manual.huggingface,
   353	            local_path=manual.local_path,
   354	            url=manual.url,
   355	            canonical_source=manual.canonical_source,
   356	        )
   357	
   358	        # Load pack and dep for cross-kind validation
   359	        pack = self._pack_service.layout.load_pack(pack_name) if hasattr(self._pack_service, "layout") else None
   360	        dep = _find_dependency(pack, dep_id) if pack else None

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_service.py | nl -ba | sed -n '430,505p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   430	                pack_base_model, candidate_base_model, kind,
   431	            )
   432	
   433	            candidate = ResolutionCandidate(
   434	                confidence=confidence,
   435	                tier=tier,
   436	                strategy=seed.selector.strategy,
   437	                selector_data=seed.selector.model_dump(exclude_none=True),
   438	                canonical_source=seed.canonical_source,
   439	                evidence_groups=group_list,
   440	                display_name=seed.display_name,
   441	                display_description=seed.display_description,
   442	                provider=seed.provider_name,
   443	                base_model=candidate_base_model,
   444	                compatibility_warnings=compat_warnings,
   445	            )
   446	            candidates.append(candidate)
   447	
   448	        # Sort by confidence descending
   449	        candidates.sort(key=lambda c: c.confidence, reverse=True)
   450	
   451	        # Assign ranks
   452	        for i, c in enumerate(candidates):
   453	            c.rank = i + 1
   454	
   455	        return candidates
   456	
   457	    def _candidate_to_selector(
   458	        self, candidate: ResolutionCandidate,
   459	    ) -> DependencySelector:
   460	        """Reconstruct DependencySelector from a candidate."""
   461	        return DependencySelector(**{
   462	            k: v for k, v in candidate.selector_data.items()
   463	            if k in DependencySelector.model_fields
   464	        })
   465	
   466	    def _find_candidate_in_cache(
   467	        self, candidate_id: str,
   468	    ) -> Optional[ResolutionCandidate]:
   469	        """Search all cached requests for a candidate.
   470	
   471	        Falls back to linear search through known request_ids.
   472	        Only works with InMemoryCandidateCache (known implementation).
   473	        """
   474	        cache = self._cache
   475	        if isinstance(cache, InMemoryCandidateCache):
   476	            return cache.find_by_candidate_id(candidate_id)
   477	        return None
   478	
   479	
   480	# --- Helpers ---
   481	
   482	def _find_dependency(pack: Any, dep_id: str) -> Any:
   483	    """Find a dependency by ID in a pack."""
   484	    deps = getattr(pack, "dependencies", [])
   485	    if not deps:
   486	        return None
   487	    for dep in deps:
   488	        if getattr(dep, "id", None) == dep_id:
   489	            return dep
   490	    return None
   491	
   492	
   493	def _compute_pack_fingerprint(pack: Any) -> str:
   494	    """Compute a fingerprint for stale detection."""
   495	    try:
   496	        data = pack.model_dump() if hasattr(pack, "model_dump") else str(pack)
   497	        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]
   498	    except Exception:
   499	        return ""

exec
/bin/bash -lc 'git show feat/resolve-model-redesign:src/store/pack_service.py | rg -n "apply_dependency_resolution|canonical_source|lock_entry"' in /home/box/git/github/synapse
 succeeded in 0ms:
1217:    def apply_dependency_resolution(
1222:        canonical_source: Optional[CanonicalSource] = None,
1223:        lock_entry: Optional[ResolvedDependency] = None,
1229:        pack.json with the new selector and optionally canonical_source.
1236:            canonical_source: Optional canonical source for update tracking.
1237:            lock_entry: Optional pre-resolved lock entry (not used yet).
1255:        # Set canonical_source if provided
1256:        if canonical_source:
1257:            dep.selector.canonical_source = canonical_source
1260:            "[apply_dependency_resolution] %s/%s → strategy=%s%s",

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/pack_service.py | nl -ba | sed -n '1360,1435p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1360	                installed.append(actual_sha)
  1361	
  1362	                if not sha256:
  1363	                    resolved.artifact.sha256 = actual_sha
  1364	                    resolved.artifact.integrity.sha256_verified = True
  1365	                    self.layout.save_pack_lock(lock)
  1366	
  1367	                # Create manifest for newly downloaded blob
  1368	                self._ensure_blob_manifest(actual_sha, resolved, pack)
  1369	
  1370	            except Exception as e:
  1371	                logger.error(f"[PackService] Failed to install {resolved.dependency_id}: {e}")
  1372	
  1373	        return installed
  1374	
  1375	    def _ensure_blob_manifest(
  1376	        self,
  1377	        sha256: str,
  1378	        resolved: ResolvedDependency,
  1379	        pack: Optional[Pack],
  1380	    ) -> None:
  1381	        """
  1382	        Ensure a manifest exists for a blob (write-once, never overwrites).
  1383	
  1384	        Called during blob installation to persist metadata for orphan recovery.
  1385	        """
  1386	        # Skip if manifest already exists
  1387	        if self.blob_store.manifest_exists(sha256):
  1388	            return
  1389	
  1390	        # Get expose filename from pack dependency, fall back to provider filename
  1391	        expose_filename: Optional[str] = None
  1392	        if pack:
  1393	            dep = pack.get_dependency(resolved.dependency_id)
  1394	            if dep:
  1395	                expose_filename = dep.expose.filename
  1396	
  1397	        # Fall back to provider filename or SHA256 prefix
  1398	        original_filename = (
  1399	            expose_filename
  1400	            or resolved.artifact.provider.filename
  1401	            or f"{sha256[:12]}.bin"
  1402	        )
  1403	
  1404	        # Build origin from provider
  1405	        provider = resolved.artifact.provider
  1406	        origin = BlobOrigin(
  1407	            provider=provider.name,
  1408	            model_id=provider.model_id,
  1409	            version_id=provider.version_id,
  1410	            file_id=provider.file_id,
  1411	            filename=provider.filename,
  1412	            repo_id=provider.repo_id,
  1413	        )
  1414	
  1415	        # Create manifest
  1416	        manifest = BlobManifest(
  1417	            original_filename=original_filename,
  1418	            kind=resolved.artifact.kind,
  1419	            origin=origin,
  1420	        )
  1421	
  1422	        # Write manifest (write-once)
  1423	        self.blob_store.write_manifest(sha256, manifest)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_validation.py | nl -ba | sed -n '1,120p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Resolve validation — per-strategy minimum field checks and cross-kind validation.
     3	
     4	Based on PLAN-Resolve-Model.md v0.7.1 sections 5, 2h.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from typing import Dict, List, Optional, Tuple
    10	
    11	from .models import AssetKind, DependencySelector, SelectorStrategy
    12	from .resolve_config import check_cross_kind_compatibility
    13	from .resolve_models import ApplyResult
    14	
    15	# Per-strategy required fields: (field_path, human_label)
    16	STRATEGY_REQUIREMENTS: Dict[SelectorStrategy, List[Tuple[str, str]]] = {
    17	    SelectorStrategy.CIVITAI_FILE: [
    18	        ("civitai.model_id", "Civitai model ID"),
    19	        ("civitai.version_id", "Civitai version ID"),
    20	        ("civitai.file_id", "Civitai file ID"),
    21	    ],
    22	    SelectorStrategy.CIVITAI_MODEL_LATEST: [
    23	        ("civitai.model_id", "Civitai model ID"),
    24	    ],
    25	    SelectorStrategy.HUGGINGFACE_FILE: [
    26	        ("huggingface.repo_id", "HuggingFace repo ID"),
    27	        ("huggingface.filename", "HuggingFace filename"),
    28	    ],
    29	    SelectorStrategy.LOCAL_FILE: [
    30	        ("local_path", "Local file: requires local_path"),
    31	    ],
    32	    SelectorStrategy.URL_DOWNLOAD: [
    33	        ("url", "Download URL"),
    34	    ],
    35	    SelectorStrategy.BASE_MODEL_HINT: [
    36	        ("base_model", "Base model alias"),
    37	    ],
    38	}
    39	
    40	
    41	def _get_field(selector: DependencySelector, field_path: str) -> object:
    42	    """Get a nested field from selector by dot-separated path."""
    43	    parts = field_path.split(".")
    44	    obj = selector
    45	    for part in parts:
    46	        if obj is None:
    47	            return None
    48	        obj = getattr(obj, part, None)
    49	    return obj
    50	
    51	
    52	def validate_selector_fields(selector: DependencySelector) -> ApplyResult:
    53	    """Validate that a selector has all required fields for its strategy.
    54	
    55	    Returns ApplyResult with success=False if validation fails.
    56	    """
    57	    reqs = STRATEGY_REQUIREMENTS.get(selector.strategy, [])
    58	    missing = []
    59	
    60	    for field_path, label in reqs:
    61	        value = _get_field(selector, field_path)
    62	        if value is None or value == "":
    63	            missing.append(label)
    64	        elif isinstance(value, int) and value == 0:
    65	            missing.append(f"{label} (invalid zero value)")
    66	
    67	    if missing:
    68	        return ApplyResult(
    69	            success=False,
    70	            message=f"Selector validation failed: Missing required field: {missing[0]}",
    71	        )
    72	
    73	    return ApplyResult(success=True, message="Validation passed")
    74	
    75	
    76	def validate_candidate(
    77	    selector: DependencySelector,
    78	    kind: AssetKind,
    79	    pack_base_model: Optional[str] = None,
    80	    candidate_base_model: Optional[str] = None,
    81	) -> ApplyResult:
    82	    """Full validation: field check + cross-kind compatibility.
    83	
    84	    Returns ApplyResult. On success, compatibility_warnings may be non-empty
    85	    (warnings don't block apply, but should be shown to the user).
    86	    """
    87	    # Step 1: Field validation
    88	    field_result = validate_selector_fields(selector)
    89	    if not field_result.success:
    90	        return field_result
    91	
    92	    # Step 2: Cross-kind compatibility
    93	    warnings = check_cross_kind_compatibility(
    94	        pack_base_model, candidate_base_model, kind,
    95	    )
    96	
    97	    return ApplyResult(
    98	        success=True,
    99	        message="Validation passed",
   100	        compatibility_warnings=warnings,
   101	    )
   102	
   103	
   104	def validate_before_apply(
   105	    selector: DependencySelector,
   106	    kind: AssetKind,
   107	    pack_base_model: Optional[str] = None,
   108	    candidate_base_model: Optional[str] = None,
   109	) -> ApplyResult:
   110	    """Convenience alias for validate_candidate."""
   111	    return validate_candidate(selector, kind, pack_base_model, candidate_base_model)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/evidence_providers.py | nl -ba | sed -n '80,115p;185,205p;850,885p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    80	
    81	        if not sha256:
    82	            return ProviderResult()
    83	
    84	        pack_service = self._ps()
    85	        if pack_service is None:
    86	            return ProviderResult(error="PackService not available")
    87	
    88	        # Try Civitai hash lookup
    89	        civitai = getattr(pack_service, "civitai", None)
    90	        if civitai:
    91	            try:
    92	                result = civitai.get_model_by_hash(sha256)
    93	                if result:
    94	                    # CivitaiModelVersion is a dataclass — use getattr, not .get()
    95	                    model_id = getattr(result, "model_id", None) or getattr(result, "modelId", None)
    96	                    version_id = getattr(result, "id", None)
    97	                    file_id = _extract_file_id(result, sha256)
    98	                    display_name = getattr(result, "name", "Unknown")
    99	
   100	                    if model_id and version_id:
   101	                        # Extract base_model from Civitai API response
   102	                        candidate_base_model = (
   103	                            getattr(result, "base_model", None)
   104	                            or getattr(result, "baseModel", None)
   105	                        )
   106	                        seed = CandidateSeed(
   107	                            key=f"civitai:{model_id}:{version_id}",
   108	                            selector=DependencySelector(
   109	                                strategy=SelectorStrategy.CIVITAI_FILE,
   110	                                civitai=CivitaiSelector(
   111	                                    model_id=model_id,
   112	                                    version_id=version_id,
   113	                                    file_id=file_id,
   114	                                ),
   115	                            ),
   185	                        strategy=SelectorStrategy.CIVITAI_FILE,
   186	                        civitai=CivitaiSelector(
   187	                            model_id=model_id,
   188	                            version_id=version_id,
   189	                            file_id=file_id,
   190	                        ),
   191	                    ),
   192	                    display_name=display_name,
   193	                    provider_name="civitai",
   194	                )
   195	                # Boost confidence when we have real IDs
   196	                confidence = min(confidence + 0.05, 0.90)
   197	            else:
   198	                seed = CandidateSeed(
   199	                    key=f"preview:{hint.filename}",
   200	                    selector=DependencySelector(
   201	                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
   202	                        civitai=CivitaiSelector(model_id=0),  # Unresolved
   203	                    ),
   204	                    display_name=hint.filename,
   205	                    provider_name="civitai",
   850	        if not model_id:
   851	            return None
   852	        version_id = candidate.get("version_id")
   853	        file_id = candidate.get("file_id")
   854	
   855	        # Use CIVITAI_FILE if we have version+file, otherwise CIVITAI_MODEL_LATEST
   856	        if version_id and file_id:
   857	            strategy = SelectorStrategy.CIVITAI_FILE
   858	        else:
   859	            strategy = SelectorStrategy.CIVITAI_MODEL_LATEST
   860	
   861	        seed = CandidateSeed(
   862	            key=f"civitai:{model_id}:{version_id or 'latest'}",
   863	            selector=DependencySelector(
   864	                strategy=strategy,
   865	                civitai=CivitaiSelector(
   866	                    model_id=model_id,
   867	                    version_id=version_id,
   868	                    file_id=file_id,
   869	                ),
   870	            ),
   871	            display_name=display_name,
   872	            provider_name="civitai",
   873	        )
   874	    elif provider == "huggingface":
   875	        from .models import HuggingFaceSelector
   876	        repo_id = candidate.get("repo_id")
   877	        filename = candidate.get("filename")
   878	        if not repo_id or not filename:
   879	            return None
   880	
   881	        seed = CandidateSeed(
   882	            key=f"hf:{repo_id}:{filename}",
   883	            selector=DependencySelector(
   884	                strategy=SelectorStrategy.HUGGINGFACE_FILE,
   885	                huggingface=HuggingFaceSelector(

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/pack_service.py | nl -ba | sed -n '1210,1270p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1210	            resolved=resolved,
  1211	            unresolved=unresolved,
  1212	        )
  1213	
  1214	        self.layout.save_pack_lock(lock)
  1215	        return lock
  1216	
  1217	    def apply_dependency_resolution(
  1218	        self,
  1219	        pack_name: str,
  1220	        dep_id: str,
  1221	        selector: DependencySelector,
  1222	        canonical_source: Optional[CanonicalSource] = None,
  1223	        lock_entry: Optional[ResolvedDependency] = None,
  1224	        display_name: Optional[str] = None,
  1225	    ) -> None:
  1226	        """Apply a resolved dependency selector to a pack.
  1227	
  1228	        This is the SINGLE write path for ResolveService — it updates
  1229	        pack.json with the new selector and optionally canonical_source.
  1230	        Does NOT touch pack.lock.json (that's resolve_pack's job).
  1231	
  1232	        Args:
  1233	            pack_name: Pack to update.
  1234	            dep_id: Dependency ID to update.
  1235	            selector: New DependencySelector to apply.
  1236	            canonical_source: Optional canonical source for update tracking.
  1237	            lock_entry: Optional pre-resolved lock entry (not used yet).
  1238	            display_name: Optional display name (logged, not stored).
  1239	        """
  1240	        pack = self.layout.load_pack(pack_name)
  1241	
  1242	        # Find dependency
  1243	        dep = None
  1244	        for d in pack.dependencies:
  1245	            if d.id == dep_id:
  1246	                dep = d
  1247	                break
  1248	
  1249	        if dep is None:
  1250	            raise ValueError(f"Dependency '{dep_id}' not found in pack '{pack_name}'")
  1251	
  1252	        # Update selector
  1253	        dep.selector = selector
  1254	
  1255	        # Set canonical_source if provided
  1256	        if canonical_source:
  1257	            dep.selector.canonical_source = canonical_source
  1258	
  1259	        logger.info(
  1260	            "[apply_dependency_resolution] %s/%s → strategy=%s%s",
  1261	            pack_name, dep_id, selector.strategy.value,
  1262	            f" ({display_name})" if display_name else "",
  1263	        )
  1264	
  1265	        self.layout.save_pack(pack)
  1266	
  1267	    def _ensure_resolvers(self) -> None:
  1268	        """Lazily initialize default resolvers if none were provided."""
  1269	        if self._resolvers:
  1270	            return

exec
/bin/bash -lc "ls -la plans/audits | sed -n '1,80p'" in /home/box/git/github/synapse
 succeeded in 0ms:
total 5108
drwxr-xr-x 1 box box     448 May  2 15:48 .
drwxr-xr-x 1 box box    1344 May  2 12:49 ..
-rw-r--r-- 1 box box   42136 May  2 12:49 CONSOLIDATED-FINDINGS.md
-rw-r--r-- 1 box box  752181 May  2 12:39 codex-audit-1-resolve-model.md
-rw-r--r-- 1 box box 1523337 May  2 12:42 codex-audit-2-custom-pack.md
-rw-r--r-- 1 box box   21728 May  2 12:39 codex-audit-3-install-pack.md
-rw-r--r-- 1 box box   39790 May  2 12:38 codex-audit-4-workflow-wizard.md
-rw-r--r-- 1 box box 1020965 May  2 12:38 codex-audit-5-profiles.md
-rw-r--r-- 1 box box 1098357 May  2 12:39 codex-audit-6-ai-integration.md
-rw-r--r-- 1 box box  712739 May  2 15:51 codex-domain-audit-raw.md

codex
I’ve got enough context to write the audit now. The main design findings are coalescing around four foundations: source identity is split across pack/dependency/lock/manifest, pack-to-pack dependencies are informational in several places but operational in others, UI/profile/runtime state is only partially modeled, and the incoming resolve redesign adds `CanonicalSource` in a branch without a clean merge story for the current `PackSource` and lock models.
apply patch
patch: completed
/home/box/git/github/synapse/plans/audits/codex-domain-audit.md
diff --git a/plans/audits/codex-domain-audit.md b/plans/audits/codex-domain-audit.md
new file mode 100644
index 0000000000000000000000000000000000000000..025f1f027c7782c98a603092a31822a5327609c4
--- /dev/null
+++ b/plans/audits/codex-domain-audit.md
@@ -0,0 +1,1095 @@
+# Synapse v2 Store Domain Model Audit
+
+Date: 2026-05-02
+
+Scope:
+
+- Primary model file: `src/store/models.py`.
+- Related domain/service files: `layout.py`, `__init__.py`, `pack_service.py`,
+  `profile_service.py`, `view_builder.py`, `dependency_resolver.py`,
+  `inventory_service.py`, `backup_service.py`, `update_service.py`,
+  `blob_store.py`, `ui_attach.py`.
+- Roadmap context: `plans/audits/CONSOLIDATED-FINDINGS.md`.
+- Resolve redesign comparison: `feat/resolve-model-redesign:src/store/resolve_models.py`
+  and touched model/write-path shape from that branch.
+
+## Executive Summary
+
+1. The domain model is usable today, but it is carrying several future-facing concepts
+   as partially-wired fields: `pack_dependencies`, `ConflictMode`, install packs,
+   custom nodes, workflows, backup state sync, and active UI inventory.
+2. `Pack` is doing too much: provider origin, dependency manifest, gallery metadata,
+   generation metadata, workflow metadata, editability, update behavior, and future
+   install-pack behavior are all on one object.
+3. Source identity is the biggest foundation risk. There are at least five identity
+   surfaces: `Pack.source`, `DependencySelector`, branch `CanonicalSource`,
+   `ResolvedArtifact.provider`, and `BlobManifest.origin`.
+4. Lock semantics are underspecified. The lock is the only place with resolved hashes
+   and download URLs, but update/apply/installation can mutate lock and blob state
+   independently. Divergence is normal, not exceptional.
+5. `pack_dependencies` is modeled as operational but profile/view composition ignores
+   it. API endpoints can create and show a dependency tree, while `use()` and `sync()`
+   do not recursively include those dependent packs.
+6. `AssetKind.CUSTOM_NODE` exists but is not mapped through `UIKindMap`, ComfyUI YAML
+   generation, or attach symlinks. This is a future workflow/custom-node blocker.
+7. Current `ProfilePackEntry` does not have `enabled`, despite CLI code referencing it.
+   This is model/API drift, not merely an ignored flag.
+8. Schema version strings exist in top-level persisted models, but there is no migration
+   runner, version dispatch, or compatibility policy in layout load paths.
+
+## Persistence Map
+
+- `state/config.json`: `StoreConfig` with `schema=synapse.config.v2`
+  ([models.py:243](../../src/store/models.py#L243), [layout.py:388](../../src/store/layout.py#L388)).
+- `state/ui_sets.json`: `UISets` with `schema=synapse.ui_sets.v1`
+  ([models.py:314](../../src/store/models.py#L314), [layout.py:399](../../src/store/layout.py#L399)).
+- `state/packs/<pack>/pack.json`: `Pack` with `schema=synapse.pack.v2`
+  ([models.py:837](../../src/store/models.py#L837), [layout.py:427](../../src/store/layout.py#L427)).
+- `state/packs/<pack>/lock.json`: `PackLock` with `schema=synapse.lock.v2`
+  ([models.py:976](../../src/store/models.py#L976), [layout.py:441](../../src/store/layout.py#L441)).
+- `state/profiles/<profile>/profile.json`: `Profile` with `schema=synapse.profile.v1`
+  ([models.py:1017](../../src/store/models.py#L1017), [layout.py:480](../../src/store/layout.py#L480)).
+- `data/runtime.json`: `Runtime` with `schema=synapse.runtime.v1`
+  ([models.py:1058](../../src/store/models.py#L1058), [layout.py:508](../../src/store/layout.py#L508)).
+- `data/blobs/sha256/<prefix>/<sha>`: content-addressed blobs
+  ([blob_store.py:88](../../src/store/blob_store.py#L88), [layout.py:229](../../src/store/layout.py#L229)).
+- `data/blobs/sha256/<prefix>/<sha>.meta.json`: `BlobManifest`
+  ([models.py:1435](../../src/store/models.py#L1435), [blob_store.py:533](../../src/store/blob_store.py#L533)).
+- `data/views/<ui>/profiles/<profile>` and `data/views/<ui>/active`: derived view state
+  ([layout.py:209](../../src/store/layout.py#L209), [view_builder.py:375](../../src/store/view_builder.py#L375)).
+- `data/.synapse.lock`: global file lock
+  ([layout.py:160](../../src/store/layout.py#L160), [layout.py:248](../../src/store/layout.py#L248)).
+
+## 1. Inventory Of Domain Objects
+
+### Config And UI Sets
+
+#### `AssetKind`
+
+- Purpose: vocabulary of assets Synapse can expose to UIs
+  ([models.py:31](../../src/store/models.py#L31)).
+- Fields/values: `checkpoint`, `lora`, `vae`, `controlnet`, `upscaler`, `clip`,
+  `text_encoder`, `diffusion_model`, `embedding`, `custom_node`, `unet`, `unknown`
+  ([models.py:33](../../src/store/models.py#L33)).
+- Invariants: enum values are used as serialized strings; no versioning or aliasing.
+- Used by: `Pack.pack_type`, `PackDependency.kind`, `ResolvedArtifact.kind`,
+  inventory, view planning, UI attach mapping.
+- Persistence: pack JSON, lock JSON, blob manifest, inventory/API responses.
+- Design note: `CUSTOM_NODE` is in the enum but missing from `UIKindMap` fields and
+  ComfyUI extra path mapping, so it is not fully operational.
+
+#### `ProviderName`
+
+- Purpose: supported provider identity enum
+  ([models.py:47](../../src/store/models.py#L47)).
+- Fields/values: `civitai`, `huggingface`, `local`, `url`.
+- Invariants: used in Pydantic provider/source models; no `unknown` provider.
+- Used by: `PackSource`, `ArtifactProvider`, `BlobOrigin`, update fallback.
+- Persistence: pack JSON, lock JSON, blob manifest, inventory.
+- Design note: fine for current providers, brittle for AI-discovered/community providers
+  unless the system accepts schema churn for every new provider.
+
+#### `SelectorStrategy`
+
+- Purpose: resolution strategy for a dependency
+  ([models.py:55](../../src/store/models.py#L55)).
+- Fields/values: `civitai_file`, `civitai_model_latest`, `huggingface_file`,
+  `base_model_hint`, `local_file`, `url_download`.
+- Invariants: strategy should imply which selector payload field is populated, but this
+  is not enforced by a discriminated union.
+- Used by: dependency resolvers, update providers, resolve redesign branch.
+- Persistence: pack JSON.
+- Design note: current model permits invalid combinations like `strategy=local_file`
+  with `civitai` data and no `local_path`.
+
+#### `UpdatePolicyMode` and `UpdatePolicy`
+
+- Purpose: choose whether a dependency is fixed or update-following
+  ([models.py:65](../../src/store/models.py#L65), [models.py:385](../../src/store/models.py#L385)).
+- Fields: `mode` defaults to `pinned`.
+- Invariants: `follow_latest` is considered updatable only when a provider is registered
+  for the dependency strategy ([update_service.py:107](../../src/store/update_service.py#L107)).
+- Used by: `UpdateService.plan_update`, `UpdateService.is_updatable`.
+- Persistence: pack JSON.
+- Design note: update behavior is dependency-level, not pack-level. A custom pack with
+  a `follow_latest` Civitai dependency is backend-updatable even if UI considers custom
+  packs non-updatable.
+
+#### `ConflictMode` and `ConflictConfig`
+
+- Purpose: profile conflict policy
+  ([models.py:71](../../src/store/models.py#L71), [models.py:1012](../../src/store/models.py#L1012)).
+- Fields/values: `last_wins`, `first_wins`, `strict`; profile default `last_wins`.
+- Invariants: only `last_wins` is implemented in `ViewPlan.add_entry`, which replaces
+  existing entries with later packs ([view_builder.py:91](../../src/store/view_builder.py#L91)).
+- Used by: stored on `Profile`, copied into work profiles
+  ([profile_service.py:128](../../src/store/profile_service.py#L128)).
+- Persistence: profile JSON.
+- Design note: `FIRST_WINS` and `STRICT` are modeled but ignored by view planning.
+
+#### `PackCategory`
+
+- Purpose: pack origin/editability class
+  ([models.py:78](../../src/store/models.py#L78)).
+- Fields/values: `external`, `custom`, `install`.
+- Invariants: comments imply editability and installation semantics, but services do
+  not enforce most of that.
+- Used by: imported Civitai packs are `external` ([pack_service.py:510](../../src/store/pack_service.py#L510));
+  API-created custom packs are `custom` ([api.py:3310](../../src/store/api.py#L3310)).
+- Persistence: pack JSON.
+- Design note: `INSTALL` is not just a category. It implies scripts, process lifecycle,
+  UI roots, trust, logs, and health state. It should probably be a subtype object.
+
+#### `UIKindMap`
+
+- Purpose: maps asset kinds to UI-specific model folders
+  ([models.py:121](../../src/store/models.py#L121)).
+- Fields: `checkpoint`, `lora`, `vae`, `embedding`, `controlnet`, `upscaler`,
+  `clip`, `text_encoder`, `diffusion_model`, `unet`.
+- Invariants: `get_path()` maps by `AssetKind.value`
+  ([models.py:134](../../src/store/models.py#L134)).
+- Used by: `ViewBuilder.compute_plan`, `UIAttacher`, default UI config.
+- Persistence: config JSON.
+- Design note: missing `custom_node` and `unknown`. ViewBuilder falls back to
+  `models/<kind>`, but `UIAttacher` skips unmapped kinds, so attach is inconsistent
+  ([view_builder.py:85](../../src/store/view_builder.py#L85), [ui_attach.py:333](../../src/store/ui_attach.py#L333)).
+
+#### `UIConfig`
+
+- Purpose: known UI names and per-UI kind maps
+  ([models.py:139](../../src/store/models.py#L139)).
+- Fields: `known`, `kind_map`.
+- Invariants: default known UIs are `comfyui`, `forge`, `a1111`, `sdnext`.
+- Used by: `StoreConfig`, runtime initialization, view planning, attach.
+- Persistence: config JSON.
+- Design note: UI roots live outside this model in app config passed to UIAttacher,
+  producing a split between store state and application config.
+
+#### `ProviderConfig`
+
+- Purpose: provider defaults for file selection
+  ([models.py:199](../../src/store/models.py#L199)).
+- Fields: `primary_file_only_default`, `preferred_ext`.
+- Invariants: default Civitai/HF provider configs are written by `StoreConfig.create_default`
+  ([models.py:257](../../src/store/models.py#L257)).
+- Used by: limited. NEEDS VERIFICATION: current resolver code mostly uses selector
+  constraints rather than provider defaults directly.
+- Persistence: config JSON.
+
+#### `CivitaiSelectorConfig`, `BaseModelAliasSelector`, `BaseModelAlias`
+
+- Purpose: configured aliases for base model hints
+  ([models.py:205](../../src/store/models.py#L205), [models.py:214](../../src/store/models.py#L214),
+  [models.py:220](../../src/store/models.py#L220)).
+- Fields: Civitai `model_id`, `version_id`, `file_id`; alias kind/default filename/selector.
+- Invariants: default aliases currently use placeholder zeros
+  ([models.py:274](../../src/store/models.py#L274)).
+- Used by: `_create_base_model_dependency`, `BaseModelHintResolver`
+  ([pack_service.py:603](../../src/store/pack_service.py#L603), [dependency_resolver.py:209](../../src/store/dependency_resolver.py#L209)).
+- Persistence: config JSON.
+- Design note: placeholder zero IDs are normal config data in main, while resolve
+  redesign validation rejects zero IDs ([resolve_validation.py branch:64]).
+
+#### `ConfigDefaults`, `BackupConfig`, `StoreConfig`
+
+- Purpose: global defaults, backup config, root persisted config
+  ([models.py:227](../../src/store/models.py#L227), [models.py:235](../../src/store/models.py#L235),
+  [models.py:243](../../src/store/models.py#L243)).
+- Fields: default UI set, conflict mode, active/use base defaults, backup path/options,
+  providers, base aliases.
+- Invariants: `schema_` aliases to JSON `schema`; layout writes with aliases
+  ([layout.py:322](../../src/store/layout.py#L322)).
+- Used by: Store facade defaults, runtime init, backup service, UI attach.
+- Persistence: `state/config.json`.
+- Design note: `defaults.active_profile` and `defaults.use_base` do not appear to be
+  authoritative for runtime, which is in `data/runtime.json`.
+
+#### `UISets`
+
+- Purpose: named sets of UI targets
+  ([models.py:314](../../src/store/models.py#L314)).
+- Fields: `schema`, `sets`.
+- Invariants: default sets include named and singleton sets
+  ([models.py:321](../../src/store/models.py#L321)).
+- Used by: Store facade `get_ui_targets`, profile service, view builder.
+- Persistence: `state/ui_sets.json`.
+- Design note: default UI set name lives in `StoreConfig.defaults.ui_set`, while set
+  members live in `UISets`. That split is acceptable but needs migration discipline.
+
+### Pack, Source, Dependencies
+
+#### `CivitaiSelector`
+
+- Purpose: Civitai dependency selector
+  ([models.py:350](../../src/store/models.py#L350)).
+- Fields: `model_id`, optional `version_id`, optional `file_id`.
+- Invariants: current main does not reject `0`; branch validation does.
+- Used by: dependency resolver, import, update, resolve branch.
+- Persistence: pack JSON.
+- Design note: Civitai model/version/file identity is spread across this selector,
+  `PackSource`, `ArtifactProvider`, `BlobOrigin`, and `ModelInfo.civitai_air`.
+
+#### `HuggingFaceSelector`
+
+- Purpose: HuggingFace file selector
+  ([models.py:359](../../src/store/models.py#L359)).
+- Fields: `repo_id`, `filename`, optional `revision`, optional `subfolder`.
+- Invariants: strategy should require repo and filename; not enforced in main.
+- Used by: `HuggingFaceResolver`
+  ([dependency_resolver.py:270](../../src/store/dependency_resolver.py#L270)).
+- Persistence: pack JSON.
+- Design note: HF path can be represented as `subfolder + filename`; lock stores
+  `repo_id`, `filename`, `revision`, but not `subfolder` in `ArtifactProvider`.
+
+#### `SelectorConstraints`
+
+- Purpose: file selection filters
+  ([models.py:367](../../src/store/models.py#L367)).
+- Fields: `primary_file_only`, `file_ext`, `base_model_hint`.
+- Invariants: resolver helper applies primary and extension filters
+  ([dependency_resolver.py:344](../../src/store/dependency_resolver.py#L344)).
+- Used by: Civitai latest/file and base model resolver path.
+- Persistence: pack JSON.
+- Design note: `base_model_hint` duplicates `Pack.base_model`, dependency `selector.base_model`,
+  and branch candidate `base_model`.
+
+#### `DependencySelector`
+
+- Purpose: strategy plus provider-specific selector payload
+  ([models.py:374](../../src/store/models.py#L374)).
+- Fields: `strategy`, optional `civitai`, `huggingface`, `base_model`, `url`,
+  `local_path`, `constraints`.
+- Invariants: no discriminator validation; impossible and incomplete states are allowed.
+- Used by: all dependency resolution and update paths.
+- Persistence: pack JSON.
+- Design note: branch adds `canonical_source` to this object
+  ([branch models.py:381](../../src/store/models.py#L381) via git show). That is a
+  good direction for local/URL deps with remote provenance, but it makes the selector
+  both "how to obtain" and "what this really is".
+
+#### `ExposeConfig`
+
+- Purpose: UI-facing filename and trigger words
+  ([models.py:395](../../src/store/models.py#L395)).
+- Fields: `filename`, `trigger_words`.
+- Invariants: filename cannot start with dot, include path separators, nulls, or `..`
+  ([models.py:108](../../src/store/models.py#L108)).
+- Used by: view paths, inventory display names, blob manifest original filename.
+- Persistence: pack JSON.
+- Design note: `filename` is part of view identity and conflict behavior; changing it
+  changes runtime exposed paths but not the blob.
+
+#### `PackDependency`
+
+- Purpose: one asset dependency inside a pack
+  ([models.py:406](../../src/store/models.py#L406)).
+- Fields: `id`, `kind`, `required`, `selector`, `update_policy`, `expose`, `description`.
+- Invariants: `id` safe-name validation; pack validates unique IDs
+  ([models.py:416](../../src/store/models.py#L416), [models.py:894](../../src/store/models.py#L894)).
+- Used by: import, resolve, install, update, view build, inventory.
+- Persistence: pack JSON.
+- Design note: `required` is ignored by `resolve_pack`, which records unresolved deps
+  without distinguishing required vs optional ([pack_service.py:1153](../../src/store/pack_service.py#L1153)).
+
+#### `PackSource`
+
+- Purpose: source information for the pack as a whole
+  ([models.py:422](../../src/store/models.py#L422)).
+- Fields: `provider`, optional Civitai `model_id`, optional `version_id`, optional `url`.
+- Invariants: required on every `Pack`.
+- Used by: search result/provider display, import/custom creation.
+- Persistence: pack JSON.
+- Design flaw: this is per-pack, but dependencies are per-artifact. A custom pack can
+  contain Civitai, HF, local, and URL dependencies simultaneously. `Pack.source` then
+  becomes either misleading or merely "creation source".
+
+#### `PackResources`
+
+- Purpose: keep-in-git flags for pack resources
+  ([models.py:432](../../src/store/models.py#L432)).
+- Fields: `previews_keep_in_git`, `workflows_keep_in_git`.
+- Used by: stored on `Pack`; NEEDS VERIFICATION for enforcement.
+- Persistence: pack JSON.
+- Design note: flags exist, but resource path conventions are split:
+  previews under `resources/previews`, workflows at `pack_dir/workflows`
+  ([layout.py:181](../../src/store/layout.py#L181)).
+
+#### `PackDependencyRef`
+
+- Purpose: pack-to-pack dependency edge
+  ([models.py:438](../../src/store/models.py#L438)).
+- Fields: `pack_name`, `required`, `version_constraint`.
+- Invariants: safe pack name; `Pack` validates unique names and no self-reference
+  ([models.py:902](../../src/store/models.py#L902)).
+- Used by: API CRUD/status/tree and reverse update impact
+  ([api.py:2963](../../src/store/api.py#L2963), [update_service.py:256](../../src/store/update_service.py#L256)).
+- Persistence: pack JSON.
+- Design flaw: view/profile composition ignores this field. `_load_packs_for_profile`
+  only loads direct `profile.packs` ([profile_service.py:473](../../src/store/profile_service.py#L473)).
+
+#### `GenerationParameters`
+
+- Purpose: generation settings from Civitai or AI
+  ([models.py:460](../../src/store/models.py#L460)).
+- Fields: sampler/scheduler/steps/cfg/size/seed/LoRA strength/hires fields plus extras.
+- Invariants: `extra="allow"` and custom serializer drops `None`
+  ([models.py:477](../../src/store/models.py#L477), [models.py:763](../../src/store/models.py#L763)).
+- Used by: Civitai import AI extraction
+  ([pack_service.py:536](../../src/store/pack_service.py#L536)).
+- Persistence: pack JSON.
+- Design note: this model has a lot of AI normalization logic inside the core domain
+  model. Consider moving normalization to an adapter and keeping the persisted model
+  simpler.
+
+#### `ModelInfo`
+
+- Purpose: extended model metadata
+  ([models.py:776](../../src/store/models.py#L776)).
+- Fields: model type/base model/trigger words/hash fields/AIR/stats/published/strength.
+- Used by: Civitai import metadata, UI details.
+- Persistence: pack JSON.
+- Design note: contains source evidence like hashes and Civitai AIR, overlapping
+  with lock provider/hash identity.
+
+#### `WorkflowInfo`
+
+- Purpose: metadata for included ComfyUI workflows
+  ([models.py:794](../../src/store/models.py#L794)).
+- Fields: `name`, `filename`, optional description/source URL, `is_default`.
+- Used by: pack JSON/UI workflow features.
+- Persistence: pack JSON, with workflow files under pack directories.
+- Design note: workflow JSON is not modeled as first-class content. There is no
+  dependency graph extracted from workflow nodes.
+
+#### `PreviewInfo`
+
+- Purpose: image/video preview metadata
+  ([models.py:803](../../src/store/models.py#L803)).
+- Fields: filename, URL, NSFW, dimensions, metadata dict, media type, video details.
+- Invariants: media type is `Literal['image','video','unknown']`
+  ([models.py:819](../../src/store/models.py#L819)).
+- Used by: import, gallery, resolve preview analysis.
+- Persistence: pack JSON plus files under resources/previews.
+- Design note: preview `meta` is raw `Dict[str, Any]`, which is flexible but hides
+  the evidence contract needed by resolve/workflow import.
+
+#### `Pack`
+
+- Purpose: central persisted pack document
+  ([models.py:837](../../src/store/models.py#L837)).
+- Fields: schema, name, pack type/category/source, dependencies, pack dependencies,
+  resources, previews, cover, version/description/base/author/tags/user tags/trigger
+  words, created timestamp, parameters, model info, workflows.
+- Invariants: safe name; unique dependency IDs; unique pack deps; no self pack dep.
+- Used by: almost every store service.
+- Persistence: `state/packs/<pack>/pack.json`.
+- Design flaw: `Pack` is simultaneously package metadata, model import metadata,
+  dependency manifest, gallery/workflow container, update policy holder, and future
+  installer descriptor. Extensions will add more unrelated optional fields unless
+  it is split into typed facets.
+
+### Lock And Resolution State
+
+#### `ArtifactProvider`
+
+- Purpose: provider information for resolved artifacts
+  ([models.py:924](../../src/store/models.py#L924)).
+- Fields: provider enum; Civitai IDs; HF repo/filename/revision.
+- Used by: lock, inventory origin, blob manifest origin.
+- Persistence: lock JSON.
+- Design note: missing `subfolder`, URL, local original path, and source URL details.
+
+#### `ArtifactDownload`
+
+- Purpose: download URLs for a resolved artifact
+  ([models.py:937](../../src/store/models.py#L937)).
+- Fields: `urls`.
+- Used by: `install_pack`, update pending downloads.
+- Persistence: lock JSON.
+- Design note: no auth requirement, expiry, mirror priority, method, headers, or source
+  evidence. Civitai signed URLs may age out NEEDS VERIFICATION.
+
+#### `ArtifactIntegrity`
+
+- Purpose: integrity verification status
+  ([models.py:942](../../src/store/models.py#L942)).
+- Fields: `sha256_verified`.
+- Used by: lock and install mutation.
+- Persistence: lock JSON.
+- Design note: hash itself lives on `ResolvedArtifact.sha256`; integrity only stores a
+  boolean. It cannot distinguish "provider hash trusted" from "download verified".
+
+#### `ResolvedArtifact`
+
+- Purpose: fully or partially resolved downloadable artifact
+  ([models.py:947](../../src/store/models.py#L947)).
+- Fields: kind, optional SHA256, size, provider, download, integrity.
+- Used by: lock, view build, install, inventory, update.
+- Persistence: lock JSON.
+- Design note: `sha256` can be absent for HF/URL until download; install mutates lock
+  after download when hash was unknown ([pack_service.py:1288](../../src/store/pack_service.py#L1288)).
+
+#### `ResolvedDependency`
+
+- Purpose: lock entry tying dependency ID to artifact
+  ([models.py:963](../../src/store/models.py#L963)).
+- Fields: `dependency_id`, `artifact`.
+- Invariants: no validation that `dependency_id` exists in pack JSON.
+- Used by: lock, view build, inventory, updates.
+- Persistence: lock JSON.
+
+#### `UnresolvedDependency`
+
+- Purpose: lock entry for failed resolution
+  ([models.py:969](../../src/store/models.py#L969)).
+- Fields: `dependency_id`, `reason`, `details`.
+- Used by: resolve/status.
+- Persistence: lock JSON.
+- Design note: does not carry required/optional severity, retry strategy, or candidate
+  evidence.
+
+#### `PackLock`
+
+- Purpose: resolved state for a pack
+  ([models.py:976](../../src/store/models.py#L976)).
+- Fields: schema, pack name, resolved timestamp, resolved and unresolved lists.
+- Invariants: `is_fully_resolved()` only checks no unresolved entries, not that every
+  pack dependency has a resolved entry ([models.py:993](../../src/store/models.py#L993)).
+- Used by: install, view build, inventory, update, status.
+- Persistence: `state/packs/<pack>/lock.json`.
+- Design flaw: no generation/source fingerprint. It does not record which `pack.json`
+  dependency definitions it was resolved against, so stale locks are hard to detect.
+
+### Profiles, Runtime, Reports
+
+#### `ProfilePackEntry`
+
+- Purpose: ordered pack entry in a profile
+  ([models.py:1002](../../src/store/models.py#L1002)).
+- Fields: `name`.
+- Invariants: safe name.
+- Used by: `Profile.packs`, work profile creation, view planning.
+- Persistence: profile JSON.
+- Design note: current model has no `enabled`, but CLI references `pack_entry.enabled`
+  ([cli.py:527](../../src/store/cli.py#L527)). That is a real drift/bug.
+
+#### `Profile`
+
+- Purpose: ordered collection of packs plus conflict config
+  ([models.py:1017](../../src/store/models.py#L1017)).
+- Fields: schema, name, conflicts, packs.
+- Invariants: safe name; `add_pack` deduplicates then appends
+  ([models.py:1031](../../src/store/models.py#L1031)).
+- Used by: global/work profiles, view build, runtime activation.
+- Persistence: profile JSON.
+- Design note: profile has no direct `pack_dependencies` field. Pack-to-pack dependencies
+  are not expanded here.
+
+#### `UIRuntimeState` and `Runtime`
+
+- Purpose: runtime profile stack per UI
+  ([models.py:1053](../../src/store/models.py#L1053), [models.py:1058](../../src/store/models.py#L1058)).
+- Fields: stack defaults to `["global"]`; runtime maps UI name to state.
+- Invariants: pop refuses to remove base stack item; set_stack can set any list.
+- Used by: `use`, `back`, status, profiles page.
+- Persistence: `data/runtime.json`.
+- Design note: runtime stores profile names without referential integrity. If a profile
+  is deleted, stack entries can point to missing profiles until commands handle it.
+
+#### `MissingBlob`, `UnresolvedReport`, `ShadowedEntry`, `StatusReport`
+
+- Purpose: status/diagnostic response models
+  ([models.py:1110](../../src/store/models.py#L1110), [models.py:1118](../../src/store/models.py#L1118),
+  [models.py:1126](../../src/store/models.py#L1126), [models.py:1134](../../src/store/models.py#L1134)).
+- Fields: pack/dependency/blob data, unresolved reason, shadowed winner/loser, active UI map.
+- Used by: Store status/doctor, profile use result, CLI/API.
+- Persistence: response only.
+- Design note: `Store.status()` always returns `shadowed=[]` even though `ViewBuilder`
+  computes shadowed entries ([__init__.py:951](../../src/store/__init__.py#L951)).
+
+#### Update, Doctor, Search, Use/Back/Reset/Delete Models
+
+- `UpdateChange`, `UpdateCandidate`, `AmbiguousUpdate`, `PendingDownload`, `UpdatePlan`,
+  `UpdateOptions`, `UpdateResult`, `BatchUpdateResult`
+  ([models.py:1144](../../src/store/models.py#L1144)).
+- Purpose: update planning/application DTOs.
+- Persistence: response only, except updates mutate lock/pack.
+- Design note: `UpdateCandidate.provider` is raw `str` while providers elsewhere use
+  `ProviderName` ([models.py:1155](../../src/store/models.py#L1155)).
+- `DoctorActions`, `DoctorReport`
+  ([models.py:1216](../../src/store/models.py#L1216)).
+- Purpose: diagnostic/repair response.
+- Design note: DB rebuild is explicitly placeholder in Store doctor
+  ([__init__.py:1030](../../src/store/__init__.py#L1030)).
+- `SearchResultItem`, `SearchResult`
+  ([models.py:1235](../../src/store/models.py#L1235)).
+- Purpose: search response.
+- `UseResult`, `BackResult`, `ResetResult`, `DeleteResult`
+  ([models.py:1253](../../src/store/models.py#L1253)).
+- Purpose: command response DTOs.
+- Design note: `UseResult.shadowed` is populated during `ProfileService.use`, but
+  general status loses it unless views are rebuilt ([profile_service.py:240](../../src/store/profile_service.py#L240)).
+
+### Inventory, Blob, Backup, Sync
+
+#### `BlobStatus`, `BlobLocation`
+
+- Purpose: inventory state enums
+  ([models.py:1296](../../src/store/models.py#L1296), [models.py:1304](../../src/store/models.py#L1304)).
+- Fields: referenced/orphan/missing/backup_only; local_only/backup_only/both/nowhere.
+- Used by: inventory, cleanup, impact analysis.
+- Persistence: response only.
+- Design note: `BlobStatus.BACKUP_ONLY` means referenced but not local in service code;
+  backup-only orphan is emitted as `ORPHAN` with `location=BACKUP_ONLY`
+  ([inventory_service.py:170](../../src/store/inventory_service.py#L170)).
+
+#### `BlobOrigin`, `PackReference`
+
+- Purpose: origin and pack reference metadata
+  ([models.py:1312](../../src/store/models.py#L1312), [models.py:1324](../../src/store/models.py#L1324)).
+- Fields: provider IDs/repo filename; pack/dependency/kind/expose/size/origin.
+- Used by: inventory and blob manifest creation.
+- Persistence: response only and embedded in `BlobManifest`.
+- Design note: mirrors `ArtifactProvider`; should probably be a shared canonical source
+  or derived view.
+
+#### `InventoryItem`, `BackupStats`, `InventorySummary`, `InventoryResponse`
+
+- Purpose: blob inventory response
+  ([models.py:1334](../../src/store/models.py#L1334), [models.py:1359](../../src/store/models.py#L1359),
+  [models.py:1375](../../src/store/models.py#L1375), [models.py:1391](../../src/store/models.py#L1391)).
+- Fields: hash/kind/display/size/location/status/refs/origin/active UIs/verification/summary.
+- Used by: inventory endpoints and cleanup.
+- Persistence: response only.
+- Design note: `active_in_uis` is always `[]` in service construction with TODO
+  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).
+
+#### `CleanupResult`, `MigrateManifestsResult`, `ImpactAnalysis`
+
+- Purpose: inventory mutation/impact responses
+  ([models.py:1398](../../src/store/models.py#L1398), [models.py:1408](../../src/store/models.py#L1408),
+  [models.py:1418](../../src/store/models.py#L1418)).
+- Used by: cleanup, manifest migration, delete guards.
+- Persistence: response only.
+
+#### `BlobManifest`
+
+- Purpose: write-once orphan metadata
+  ([models.py:1435](../../src/store/models.py#L1435)).
+- Fields: integer version, created timestamp, original filename, kind, origin.
+- Invariants: write-once; `BlobStore.write_manifest` never overwrites
+  ([blob_store.py:560](../../src/store/blob_store.py#L560)).
+- Used by: inventory display for orphan blobs, installation manifest creation.
+- Persistence: `data/blobs/sha256/<prefix>/<sha>.meta.json`.
+- Design note: "immutable" is enforced by write path, but no hash/source authority is
+  stored beyond filename/kind/origin.
+
+#### Backup And State Sync Models
+
+- `BackupStatus`, `BackupOperationResult`, `BackupDeleteResult`
+  ([models.py:1454](../../src/store/models.py#L1454)).
+- Purpose: backup connection and operation responses.
+- `SyncItem`, `SyncResult`
+  ([models.py:1489](../../src/store/models.py#L1489)).
+- Purpose: blob backup push/pull result; `direction` is raw string.
+- `StateSyncStatus`, `StateSyncItem`, `StateSyncSummary`, `StateSyncResult`
+  ([models.py:1517](../../src/store/models.py#L1517)).
+- Purpose: state directory backup sync model.
+- Design note: `StateSyncStatus.CONFLICT` exists but `_analyze_state_file` returns
+  `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
+
+#### `APIResponse`
+
+- Purpose: generic API wrapper
+  ([models.py:1561](../../src/store/models.py#L1561)).
+- Fields: `ok`, optional result/error.
+- Used by: API layer where adopted.
+- Persistence: response only.
+
+### Related Dataclasses Outside `models.py`
+
+#### `PreviewDownloadConfig`, `DownloadProgressInfo`
+
+- Purpose: pack import preview/download operation DTOs
+  ([pack_service.py:72](../../src/store/pack_service.py#L72), [pack_service.py:93](../../src/store/pack_service.py#L93)).
+- Design note: service-local Pydantic models with `Literal` status.
+
+#### `ViewEntry`, `ViewPlan`, `BuildReport`
+
+- Purpose: derived view plan/build report
+  ([view_builder.py:51](../../src/store/view_builder.py#L51)).
+- Fields: pack/dependency/kind/expose/hash/destination; shadowed and missing lists.
+- Persistence: not persisted, except symlink filesystem output.
+- Design note: this is where conflict resolution actually happens, not in `Profile`.
+
+#### `AttachResult`
+
+- Purpose: UI attach/detach result DTO
+  ([ui_attach.py:34](../../src/store/ui_attach.py#L34)).
+- Persistence: response only.
+- Design note: method is raw string.
+
+## 2. Enum Audit
+
+### `PackCategory`
+
+- Current values cover origin/editability in a coarse way.
+- `CUSTOM` can cover workflow-imported packs if workflow import is just user-owned
+  metadata plus dependencies.
+- A new `WORKFLOW` category is useful only if workflow packs have distinct lifecycle,
+  e.g. extracted graph, workflow JSON validation, dependency suggestion, and UI wizard
+  state.
+- `INSTALL` should not remain only a category once executable behavior is added.
+  It needs a typed install facet with trust, script manifest, environment state, logs,
+  process controls, and UI root outputs.
+- Recommendation: keep `PackCategory` small as origin/editability, add subtype/facet
+  models: `WorkflowFacet`, `InstallFacet`, possibly `ExternalSourceFacet`.
+
+### `AssetKind`
+
+- Missing or weakly wired: custom node folders, workflows, UI install environments,
+  extensions/plugins, configs.
+- `CUSTOM_NODE` exists but is not covered by `UIKindMap` and `_kind_to_comfyui_name`
+  ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+- `WORKFLOW` is not an asset kind; workflows are separate `WorkflowInfo`.
+- A pack can mix dependency kinds because `Pack.dependencies` is a list of per-dep
+  kinds, while `Pack.pack_type` is one top-level kind. This top-level `pack_type` is
+  therefore descriptive, not exhaustive.
+- Recommendation: rename or document `Pack.pack_type` as `primary_kind`, and add asset
+  kinds only for assets that become blobs/views. Keep workflows separate if they are
+  pack resources, not model files.
+
+### `ProviderName`
+
+- Current provider enum covers Civitai, HuggingFace, local, URL.
+- Future providers can be represented as `URL` only if update/canonical semantics are
+  intentionally lost.
+- Recommendation: use `ProviderName` for known provider integrations, but add
+  `ProviderName.UNKNOWN` or a `provider_id: str` plus typed payload union if plugins
+  can introduce providers.
+
+### `SelectorStrategy`, `UpdatePolicyMode`, `ConflictMode`
+
+- `SelectorStrategy` is fully registered in `PackService._ensure_resolvers`
+  ([pack_service.py:1193](../../src/store/pack_service.py#L1193)).
+- `UpdatePolicyMode` is wired for Civitai latest where provider registered
+  ([__init__.py:246](../../src/store/__init__.py#L246)).
+- `ConflictMode` is not fully wired. `ViewPlan.add_entry` implements last-wins only.
+- Recommendation: either remove `FIRST_WINS`/`STRICT` until implemented or make
+  `ViewBuilder.compute_plan` branch on `profile.conflicts.mode`.
+
+### String-Typed Enums Hiding In Models
+
+- `PreviewInfo.media_type` is `Literal['image','video','unknown']`
+  ([models.py:819](../../src/store/models.py#L819)).
+- `DownloadProgressInfo.status` is a `Literal`
+  ([pack_service.py:115](../../src/store/pack_service.py#L115)).
+- `SyncResult.direction` and `StateSyncResult.direction` are raw strings
+  ([models.py:1500](../../src/store/models.py#L1500), [models.py:1550](../../src/store/models.py#L1550)).
+- `AttachResult.method` is a raw string
+  ([ui_attach.py:39](../../src/store/ui_attach.py#L39)).
+- Recommendation: promote repeated public response literals to enums if clients depend
+  on them.
+
+## 3. Pack Shape Audit
+
+### Cohesion
+
+- `Pack` fields are not cohesive around one lifecycle.
+- External model import fields: `source`, `model_info`, `previews`, `base_model`,
+  provider tags, trigger words.
+- Custom pack fields: `user_tags`, editable description, custom dependencies, workflows.
+- Install pack future fields are absent despite `PackCategory.INSTALL`.
+- Workflow future fields are partial: workflow metadata exists, but not imported workflow
+  JSON as typed graph/source.
+
+### `Pack.source`
+
+- `Pack.source` is required and per-pack ([models.py:843](../../src/store/models.py#L843)).
+- For Civitai imports, it records model/version/url ([pack_service.py:514](../../src/store/pack_service.py#L514)).
+- For custom packs, API writes `provider=LOCAL` even when future dependencies may be
+  remote ([api.py:3314](../../src/store/api.py#L3314)).
+- Design recommendation: reinterpret as `creation_source` or remove as authoritative
+  source. Dependency source identity should live per dependency/candidate/lock.
+
+### `pack_dependencies`
+
+- Model validation prevents duplicate names and self-reference
+  ([models.py:902](../../src/store/models.py#L902)).
+- API can add/remove/status/tree pack dependencies
+  ([api.py:3036](../../src/store/api.py#L3036), [api.py:3170](../../src/store/api.py#L3170)).
+- Update service can find reverse dependency impact
+  ([update_service.py:256](../../src/store/update_service.py#L256)).
+- Profile/view runtime does not compose them
+  ([profile_service.py:483](../../src/store/profile_service.py#L483), [view_builder.py:236](../../src/store/view_builder.py#L236)).
+- `version_constraint` is stored but not enforced.
+- Recommendation: decide whether these are operational. If yes, add dependency expansion
+  service with cycle detection, optional/required policy, version checks, and stable
+  view order.
+
+### Pack vs Lock
+
+- Pack is desired state; lock is resolved artifact state.
+- Pack dependency selector can say "Civitai latest"; lock says exactly which version/file/hash.
+- Lock can be updated without pack selector changing (`UpdateService.apply_update`)
+  ([update_service.py:346](../../src/store/update_service.py#L346)).
+- Pack can be changed without lock changing in resolve redesign apply path
+  ([branch pack_service.py:1217](../../src/store/pack_service.py#L1217) via git show).
+- Recommendation: add a lock `pack_fingerprint` or per-dependency selector fingerprint
+  so stale locks are visible.
+
+### Hash Authority
+
+- SHA256 appears in `ModelInfo.hash_sha256`, `ResolvedArtifact.sha256`,
+  `PendingDownload.sha256`, `InventoryItem.sha256`, `BlobManifest` path, and physical
+  blob path.
+- The authoritative content address should be the blob path/hash and lock artifact hash.
+- `ModelInfo.hash_sha256` should be treated as provider metadata, not runtime authority.
+- Divergence paths:
+  - lock has hash but blob missing;
+  - HF/URL lock has no hash until install mutates it;
+  - manifest exists for old origin after pack dependency renamed;
+  - pack model info hash differs from resolved dependency hash.
+
+### Storage Separation
+
+- `pack.json`: user/provider metadata and desired dependencies.
+- `lock.json`: resolved artifacts and download URLs.
+- `BlobManifest`: orphan fallback display metadata.
+- This separation is conceptually good.
+- Missing piece: explicit derivation metadata tying lock and manifest back to pack
+  dependency version/fingerprint.
+
+## 4. Dependency Model Audit
+
+- `PackDependency` is desired dependency.
+- `PackDependencyRef` is pack-to-pack edge.
+- `ResolvedDependency` is lock result.
+- Branch `ResolutionCandidate` is suggestion DTO
+  ([branch resolve_models.py:77](../../src/store/models.py#L77) via git show).
+- Branch `CanonicalSource` is remote identity independent of install strategy
+  ([branch models.py:381](../../src/store/models.py#L381) via git show).
+
+Design overlaps:
+
+- `DependencySelector.civitai` and `CanonicalSource` both can carry Civitai model/version/file.
+- `HuggingFaceSelector` and `CanonicalSource` both can carry HF repo/path/revision.
+- `ArtifactProvider` and `BlobOrigin` repeat provider identity.
+- `PackSource` overlaps only for external single-source packs.
+
+Unresolved expression:
+
+- Main supports unresolved deps by leaving them in pack JSON and recording lock
+  `UnresolvedDependency`.
+- It does not need placeholders in normal selectors, but current defaults and branch
+  evidence providers do use `model_id=0` placeholders
+  ([models.py:280](../../src/store/models.py#L280), [branch evidence_providers.py:198] via git show).
+- Recommendation: introduce explicit "unresolved candidate" or "hint" objects instead
+  of invalid selectors.
+
+Identity stability:
+
+- `dep.id` is stable unless user edits it. Lock depends on this string.
+- No immutable dependency UUID exists.
+- Rename/edit can orphan lock entries or break update history.
+- Recommendation: add immutable `dependency_uid` or forbid ID rename after lock exists.
+
+Multi-source candidates:
+
+- Branch candidates can represent multiple candidates per dependency.
+- PackDependency stores only one selected selector.
+- There is no first-class "alternatives" field. That is probably correct for pack JSON;
+  alternatives belong in candidate cache or review state.
+
+Required/optional:
+
+- `PackDependency.required` exists.
+- `PackDependencyRef.required` exists.
+- Resolve/install/status do not deeply honor optional severity.
+- Recommendation: optional unresolved deps should not make `PackLock.is_fully_resolved`
+  false unless policy says so, or lock should expose `required_unresolved`.
+
+## 5. Source, Evidence, Candidate
+
+- Current main has no `CanonicalSource`; resolve branch adds it to `DependencySelector`.
+- Branch candidate shape has `selector_data`, `canonical_source`, evidence groups,
+  display fields, provider, and base model ([branch resolve_models.py:77] via git show).
+- Branch apply reconstructs selector from `candidate.selector_data` and passes candidate
+  `canonical_source` to pack service ([branch resolve_service.py:289] via git show).
+- Branch pack service writes selector/canonical source only to `pack.json` and explicitly
+  does not touch lock ([branch pack_service.py:1226] via git show).
+
+Canonical reference proposal:
+
+- For blob identity: SHA256.
+- For Civitai source: `model_id + version_id + file_id` where available, plus SHA256
+  after resolution/download.
+- For HuggingFace source: `repo_id + revision + subfolder + filename`, with SHA256 when
+  available.
+- For local source: blob SHA256 plus optional original path as non-authoritative evidence.
+- For URL source: URL plus resolved SHA256; URL alone is not stable.
+
+Recommendation:
+
+- Keep `DependencySelector` as "how to resolve/download now".
+- Add a separate per-dependency `canonical_source` field or nested `SourceIdentity`
+  next to selector, not inside strategy payload, unless local/URL tracking requires it.
+- Replace `PackSource` with `creation_source` or a `PackOrigin` object that does not
+  pretend to identify every dependency.
+
+## 6. Profile, Runtime, View
+
+- `Profile.packs` is the only profile composition list
+  ([models.py:1022](../../src/store/models.py#L1022)).
+- There is no `Profile.pack_dependencies`.
+- Work profiles are named `work__<pack>` ([profile_service.py:83](../../src/store/profile_service.py#L83)).
+- Work profile creation copies base packs except target, then appends target for
+  last-wins behavior ([profile_service.py:134](../../src/store/profile_service.py#L134)).
+- Work profiles are updated on reuse, but no general garbage collection is evident in
+  the audited service.
+- Runtime stack stores profile names per UI; `use()` pushes, `back()` pops
+  ([profile_service.py:248](../../src/store/profile_service.py#L248), [profile_service.py:303](../../src/store/profile_service.py#L303)).
+- If underlying profile is deleted, runtime can hold stale names. `back(sync=True)` catches
+  `ProfileNotFoundError`; other flows may silently fail or activate stale views.
+- `ShadowedEntry` is computed in `ViewPlan.add_entry`; `BuildReport` carries it; `UseResult`
+  receives it; `Store.status()` does not compute it and returns empty.
+
+Recommendation:
+
+- Add `ProfileEntry.enabled` only if view builder honors it.
+- Implement `ConflictMode` or collapse it.
+- Add a profile stack repair/validation command for deleted profiles.
+- Persist or recompute shadowed entries consistently. Since views are derived, recompute
+  from current profile/locks when status asks for shadowed, or store build reports.
+
+## 7. Inventory, Blob, Backup
+
+- Inventory is derived live from physical blobs, backup blobs, and pack locks
+  ([inventory_service.py:79](../../src/store/inventory_service.py#L79)).
+- Reference map scans all pack locks and maps hash to pack references
+  ([inventory_service.py:221](../../src/store/inventory_service.py#L221)).
+- Orphan display falls back to write-once blob manifest
+  ([inventory_service.py:340](../../src/store/inventory_service.py#L340)).
+- Active UI tracking is modeled but not implemented (`active_in_uis=[]`)
+  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).
+- Backup blob sync is explicitly one-way by raw `direction` string `to_backup` or
+  `from_backup` ([backup_service.py:597](../../src/store/backup_service.py#L597)).
+- State sync claims `bidirectional`, but conflict detection is weak: differing files
+  become `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
+
+Recommendation:
+
+- Treat inventory active UI as derived, not stored.
+- Model sync direction as enum.
+- Define backup as push/pull, not mirror, unless deletion propagation is implemented.
+- For state sync, either remove `CONFLICT` or implement a base/snapshot marker.
+
+## 8. Resolve Redesign Integration
+
+- Branch `ResolutionCandidate` fits as a transient DTO, not as persisted pack state.
+- Branch `CanonicalSource` should become the shared source identity primitive, but it
+  should be reconciled with `PackSource`, `ArtifactProvider`, and `BlobOrigin`.
+- Field naming mismatches:
+  - current `PackSource.provider: ProviderName`;
+  - branch `CanonicalSource.provider: Literal["civitai","huggingface"]`;
+  - update candidate `provider: str`;
+  - candidate `provider` literal.
+- Applying a candidate likely needs:
+  - per-dependency canonical source;
+  - dependency selector update;
+  - optional expose filename/trigger update policy;
+  - lock invalidation or lock update;
+  - candidate evidence audit trail only if product wants explainability.
+- Branch apply currently ignores `lock_entry` and does not update lock
+  ([branch pack_service.py:1222] via git show).
+
+Recommendation:
+
+- Decide now whether apply updates lock. If not, make stale lock an explicit state in UI.
+- Make all candidates either applyable selectors or non-applyable hints. No `model_id=0`.
+- Bind candidate cache to `pack_name` and `dep_id`.
+
+## 9. Custom, Install, Workflow Pack Futures
+
+Custom packs:
+
+- Current `Pack` can represent custom packs without dependencies if source is `LOCAL`
+  and dependencies default empty.
+- API create currently calls `store.layout.pack_path`, which does not exist; layout has
+  `pack_dir` ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
+- Custom packs with mixed sources are poorly represented by per-pack `source`.
+
+Install packs:
+
+- `PackCategory.INSTALL` exists but no domain model for scripts, install dir, UI root,
+  health, ports, logs, trust, or process state.
+- Recommended fields/facets:
+  - `install_manifest`: scripts with hash, interpreter, args, environment policy;
+  - `install_dir`: local path controlled by store;
+  - `ui_roots`: produced UI target roots;
+  - `log_paths`: stdout/stderr/install logs;
+  - `process`: pid/ports/health/restart policy;
+  - `trust`: signer/source/risk acknowledgement.
+
+Workflow packs:
+
+- Current `WorkflowInfo` can list files, but not model workflow JSON as parsed data.
+- Imported workflow JSON should live as a pack resource plus typed extracted metadata:
+  nodes, model references, custom node refs, missing deps, source file hash, and import
+  wizard decisions.
+- `PackCategory.WORKFLOW` is optional if `WorkflowFacet` exists. Without a facet, a new
+  category will become another weak flag.
+
+## 10. UI / Attach Model
+
+- `UIKindMap` covers many model kinds for ComfyUI/Forge/A1111/SD.Next defaults, but not
+  `custom_node`.
+- ComfyUI extra_model_paths generation maps only a subset of kinds
+  ([ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+- Generic symlink attach iterates `AssetKind` but skips any kind with no kind-map path
+  ([ui_attach.py:333](../../src/store/ui_attach.py#L333)).
+- `default_ui_set` authority is split: default name in `StoreConfig.defaults.ui_set`,
+  actual set in `UISets`.
+- UI roots are passed to `UIAttacher` from app config, not persisted in store config
+  ([ui_attach.py:53](../../src/store/ui_attach.py#L53)).
+- `extra_model_paths.yaml` schema is built ad hoc as nested dictionaries, not modeled
+  ([ui_attach.py:94](../../src/store/ui_attach.py#L94)).
+
+Recommendation:
+
+- Add explicit UI attach config model: UI name, root, attach method, supported kind map.
+- Add ComfyUI YAML model if the app will edit and preserve user YAML repeatedly.
+- Decide whether custom nodes are install-pack assets rather than model blobs.
+
+## 11. Cross-Cutting Concerns
+
+Schema versioning:
+
+- Schema strings exist in file models, but load paths call direct `model_validate`
+  without migration dispatch ([layout.py:427](../../src/store/layout.py#L427)).
+- Recommendation: add `load_pack_document`/`migrate_pack` helpers and fail clearly on
+  unsupported future schemas.
+
+Pydantic:
+
+- Uses Pydantic v2 APIs (`field_validator`, `model_validator`, `model_serializer`).
+- No frozen models. Mutable lists are normal. This is convenient but makes accidental
+  in-place mutation common.
+- Recommendation: keep persisted models mutable for service ergonomics, but add command
+  methods for high-risk mutations or central write services.
+
+Validation:
+
+- Safe names prevent path separators and traversal, but dependency selectors are not
+  discriminated.
+- Recommendation: use discriminated unions for selector payloads:
+  `CivitaiFileSelector`, `HuggingFaceFileSelector`, `LocalFileSelector`, etc.
+
+Naming:
+
+- `pack`, `pack_name`, `name`, `pack_type`, `pack_category` are mostly consistent.
+- `pack_type` is misleading because pack can mix asset kinds. Prefer `primary_kind`.
+
+Serialization:
+
+- Aliased schema fields use `populate_by_name=True` and `by_alias=True` when layout
+  writes top-level models.
+- `GenerationParameters` custom serializer drops `None` and preserves extras.
+- NEEDS VERIFICATION: all API responses using `model_dump()` rather than
+  `model_dump(by_alias=True)` may expose `schema_` instead of `schema`.
+
+## 12. Observed Bugs / Smells
+
+1. `ProfilePackEntry.enabled` drift: model has no `enabled`, CLI accesses it
+   ([models.py:1002](../../src/store/models.py#L1002), [cli.py:527](../../src/store/cli.py#L527)).
+2. `Profile.conflicts.mode` ignored: view builder implements only last-wins
+   ([models.py:1012](../../src/store/models.py#L1012), [view_builder.py:91](../../src/store/view_builder.py#L91)).
+3. `StatusReport.shadowed` always empty in Store status
+   ([__init__.py:951](../../src/store/__init__.py#L951)).
+4. Placeholder Civitai IDs exist in default config
+   ([models.py:280](../../src/store/models.py#L280)).
+5. Resolve branch also emits placeholder `model_id=0` candidates in filename fallback
+   ([branch evidence_providers.py:198] via git show).
+6. `StoreLayout.pack_path()` does not exist, but API create pack calls it
+   ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
+7. `custom_node` asset kind is not attachable through current kind maps
+   ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+8. `version_constraint` on `PackDependencyRef` is stored but not enforced
+   ([models.py:452](../../src/store/models.py#L452)).
+9. `PackDependency.required` and `PackDependencyRef.required` are not reflected in
+   lock completeness or runtime composition.
+10. `StateSyncStatus.CONFLICT` is modeled but not produced by current comparison.
+11. `ArtifactProvider` lacks HF `subfolder`, while `HuggingFaceSelector` has it.
+12. `BlobStatus.BACKUP_ONLY` semantics are narrower than the enum name implies.
+
+## 13. Design Recommendations
+
+### Split `Pack`
+
+Keep:
+
+- `PackCore`: schema, name, category/origin, primary kind, version, description, tags.
+- `DependencyManifest`: model dependencies and pack dependencies.
+- `MediaFacet`: previews, cover, resources.
+- `GenerationFacet`: parameters/model info.
+- `WorkflowFacet`: workflow resources and extracted dependency hints.
+- `InstallFacet`: script/process/UI install metadata.
+
+### Merge Source Identity
+
+- Introduce one source identity model, likely evolved from branch `CanonicalSource`.
+- Use it in dependency desired state, lock provider/origin derivation, and blob manifest.
+- Keep provider-specific selector as an acquisition strategy.
+
+### Type-Narrow Selectors
+
+- Replace optional-field `DependencySelector` with a discriminated union.
+- Benefits: no invalid local selector without path, no Civitai strategy without Civitai
+  payload, no zero-ID placeholders.
+
+### Make Locks Staleness-Aware
+
+- Add lock-level `pack_fingerprint`.
+- Add per-resolved-entry `dependency_fingerprint`.
+- Show stale lock state in status and resolve UI.
+
+### Decide Operational Semantics For Pack Dependencies
+
+- If operational: expand required pack deps when building profiles/views.
+- If informational: rename to `related_packs` or `recommended_packs`.
+- Enforce `version_constraint` or remove it.
+
+### Wire Or Remove Modeled Fields
+
+- Implement `ConflictMode`.
+- Implement active UI inventory tracking or drop it from response.
+- Implement state sync conflicts or remove `CONFLICT`.
+- Add `ProfilePackEntry.enabled` intentionally or remove stale callers.
+
+### Schema Migration
+
+- Add migration helpers per persisted document.
+- Use schema version dispatch before Pydantic validation.
+- Keep migration tests with old fixture JSON.
+
+## 14. Open Questions For Owner
+
+1. Should `pack_dependencies` affect runtime composition, or are they advisory metadata?
+2. Should `apply_resolution()` update `lock.json`, invalidate it, or leave stale state
+   until explicit resolve?
+3. Is `Pack.source` meant to mean "creation source" or "all pack content source"?
+4. Do workflow imports deserve `PackCategory.WORKFLOW`, or should they be `CUSTOM` with
+   a workflow facet?
+5. Are install packs trusted first-party objects only, or can users import arbitrary
+   install packs?
+6. Should custom packs be backend-updatable when their dependencies use `FOLLOW_LATEST`?
+7. Should optional dependencies affect `PackLock.is_fully_resolved()`?
+8. Should dependency IDs be user-editable after a lock exists?
+9. Is ComfyUI custom node management part of store assets, install packs, or a separate
+   extension manager?
+10. Should backup state sync be push/pull only, or a true bidirectional merge with
+    conflict resolution?
+11. Should UI roots be persisted in store config or remain application config?
+12. What is the migration policy for existing `synapse.pack.v2` files once canonical
+    source lands?
+

diff --git a/plans/audits/codex-domain-audit.md b/plans/audits/codex-domain-audit.md
new file mode 100644
index 0000000000000000000000000000000000000000..025f1f027c7782c98a603092a31822a5327609c4
--- /dev/null
+++ b/plans/audits/codex-domain-audit.md
@@ -0,0 +1,1095 @@
+# Synapse v2 Store Domain Model Audit
+
+Date: 2026-05-02
+
+Scope:
+
+- Primary model file: `src/store/models.py`.
+- Related domain/service files: `layout.py`, `__init__.py`, `pack_service.py`,
+  `profile_service.py`, `view_builder.py`, `dependency_resolver.py`,
+  `inventory_service.py`, `backup_service.py`, `update_service.py`,
+  `blob_store.py`, `ui_attach.py`.
+- Roadmap context: `plans/audits/CONSOLIDATED-FINDINGS.md`.
+- Resolve redesign comparison: `feat/resolve-model-redesign:src/store/resolve_models.py`
+  and touched model/write-path shape from that branch.
+
+## Executive Summary
+
+1. The domain model is usable today, but it is carrying several future-facing concepts
+   as partially-wired fields: `pack_dependencies`, `ConflictMode`, install packs,
+   custom nodes, workflows, backup state sync, and active UI inventory.
+2. `Pack` is doing too much: provider origin, dependency manifest, gallery metadata,
+   generation metadata, workflow metadata, editability, update behavior, and future
+   install-pack behavior are all on one object.
+3. Source identity is the biggest foundation risk. There are at least five identity
+   surfaces: `Pack.source`, `DependencySelector`, branch `CanonicalSource`,
+   `ResolvedArtifact.provider`, and `BlobManifest.origin`.
+4. Lock semantics are underspecified. The lock is the only place with resolved hashes
+   and download URLs, but update/apply/installation can mutate lock and blob state
+   independently. Divergence is normal, not exceptional.
+5. `pack_dependencies` is modeled as operational but profile/view composition ignores
+   it. API endpoints can create and show a dependency tree, while `use()` and `sync()`
+   do not recursively include those dependent packs.
+6. `AssetKind.CUSTOM_NODE` exists but is not mapped through `UIKindMap`, ComfyUI YAML
+   generation, or attach symlinks. This is a future workflow/custom-node blocker.
+7. Current `ProfilePackEntry` does not have `enabled`, despite CLI code referencing it.
+   This is model/API drift, not merely an ignored flag.
+8. Schema version strings exist in top-level persisted models, but there is no migration
+   runner, version dispatch, or compatibility policy in layout load paths.
+
+## Persistence Map
+
+- `state/config.json`: `StoreConfig` with `schema=synapse.config.v2`
+  ([models.py:243](../../src/store/models.py#L243), [layout.py:388](../../src/store/layout.py#L388)).
+- `state/ui_sets.json`: `UISets` with `schema=synapse.ui_sets.v1`
+  ([models.py:314](../../src/store/models.py#L314), [layout.py:399](../../src/store/layout.py#L399)).
+- `state/packs/<pack>/pack.json`: `Pack` with `schema=synapse.pack.v2`
+  ([models.py:837](../../src/store/models.py#L837), [layout.py:427](../../src/store/layout.py#L427)).
+- `state/packs/<pack>/lock.json`: `PackLock` with `schema=synapse.lock.v2`
+  ([models.py:976](../../src/store/models.py#L976), [layout.py:441](../../src/store/layout.py#L441)).
+- `state/profiles/<profile>/profile.json`: `Profile` with `schema=synapse.profile.v1`
+  ([models.py:1017](../../src/store/models.py#L1017), [layout.py:480](../../src/store/layout.py#L480)).
+- `data/runtime.json`: `Runtime` with `schema=synapse.runtime.v1`
+  ([models.py:1058](../../src/store/models.py#L1058), [layout.py:508](../../src/store/layout.py#L508)).
+- `data/blobs/sha256/<prefix>/<sha>`: content-addressed blobs
+  ([blob_store.py:88](../../src/store/blob_store.py#L88), [layout.py:229](../../src/store/layout.py#L229)).
+- `data/blobs/sha256/<prefix>/<sha>.meta.json`: `BlobManifest`
+  ([models.py:1435](../../src/store/models.py#L1435), [blob_store.py:533](../../src/store/blob_store.py#L533)).
+- `data/views/<ui>/profiles/<profile>` and `data/views/<ui>/active`: derived view state
+  ([layout.py:209](../../src/store/layout.py#L209), [view_builder.py:375](../../src/store/view_builder.py#L375)).
+- `data/.synapse.lock`: global file lock
+  ([layout.py:160](../../src/store/layout.py#L160), [layout.py:248](../../src/store/layout.py#L248)).
+
+## 1. Inventory Of Domain Objects
+
+### Config And UI Sets
+
+#### `AssetKind`
+
+- Purpose: vocabulary of assets Synapse can expose to UIs
+  ([models.py:31](../../src/store/models.py#L31)).
+- Fields/values: `checkpoint`, `lora`, `vae`, `controlnet`, `upscaler`, `clip`,
+  `text_encoder`, `diffusion_model`, `embedding`, `custom_node`, `unet`, `unknown`
+  ([models.py:33](../../src/store/models.py#L33)).
+- Invariants: enum values are used as serialized strings; no versioning or aliasing.
+- Used by: `Pack.pack_type`, `PackDependency.kind`, `ResolvedArtifact.kind`,
+  inventory, view planning, UI attach mapping.
+- Persistence: pack JSON, lock JSON, blob manifest, inventory/API responses.
+- Design note: `CUSTOM_NODE` is in the enum but missing from `UIKindMap` fields and
+  ComfyUI extra path mapping, so it is not fully operational.
+
+#### `ProviderName`
+
+- Purpose: supported provider identity enum
+  ([models.py:47](../../src/store/models.py#L47)).
+- Fields/values: `civitai`, `huggingface`, `local`, `url`.
+- Invariants: used in Pydantic provider/source models; no `unknown` provider.
+- Used by: `PackSource`, `ArtifactProvider`, `BlobOrigin`, update fallback.
+- Persistence: pack JSON, lock JSON, blob manifest, inventory.
+- Design note: fine for current providers, brittle for AI-discovered/community providers
+  unless the system accepts schema churn for every new provider.
+
+#### `SelectorStrategy`
+
+- Purpose: resolution strategy for a dependency
+  ([models.py:55](../../src/store/models.py#L55)).
+- Fields/values: `civitai_file`, `civitai_model_latest`, `huggingface_file`,
+  `base_model_hint`, `local_file`, `url_download`.
+- Invariants: strategy should imply which selector payload field is populated, but this
+  is not enforced by a discriminated union.
+- Used by: dependency resolvers, update providers, resolve redesign branch.
+- Persistence: pack JSON.
+- Design note: current model permits invalid combinations like `strategy=local_file`
+  with `civitai` data and no `local_path`.
+
+#### `UpdatePolicyMode` and `UpdatePolicy`
+
+- Purpose: choose whether a dependency is fixed or update-following
+  ([models.py:65](../../src/store/models.py#L65), [models.py:385](../../src/store/models.py#L385)).
+- Fields: `mode` defaults to `pinned`.
+- Invariants: `follow_latest` is considered updatable only when a provider is registered
+  for the dependency strategy ([update_service.py:107](../../src/store/update_service.py#L107)).
+- Used by: `UpdateService.plan_update`, `UpdateService.is_updatable`.
+- Persistence: pack JSON.
+- Design note: update behavior is dependency-level, not pack-level. A custom pack with
+  a `follow_latest` Civitai dependency is backend-updatable even if UI considers custom
+  packs non-updatable.
+
+#### `ConflictMode` and `ConflictConfig`
+
+- Purpose: profile conflict policy
+  ([models.py:71](../../src/store/models.py#L71), [models.py:1012](../../src/store/models.py#L1012)).
+- Fields/values: `last_wins`, `first_wins`, `strict`; profile default `last_wins`.
+- Invariants: only `last_wins` is implemented in `ViewPlan.add_entry`, which replaces
+  existing entries with later packs ([view_builder.py:91](../../src/store/view_builder.py#L91)).
+- Used by: stored on `Profile`, copied into work profiles
+  ([profile_service.py:128](../../src/store/profile_service.py#L128)).
+- Persistence: profile JSON.
+- Design note: `FIRST_WINS` and `STRICT` are modeled but ignored by view planning.
+
+#### `PackCategory`
+
+- Purpose: pack origin/editability class
+  ([models.py:78](../../src/store/models.py#L78)).
+- Fields/values: `external`, `custom`, `install`.
+- Invariants: comments imply editability and installation semantics, but services do
+  not enforce most of that.
+- Used by: imported Civitai packs are `external` ([pack_service.py:510](../../src/store/pack_service.py#L510));
+  API-created custom packs are `custom` ([api.py:3310](../../src/store/api.py#L3310)).
+- Persistence: pack JSON.
+- Design note: `INSTALL` is not just a category. It implies scripts, process lifecycle,
+  UI roots, trust, logs, and health state. It should probably be a subtype object.
+
+#### `UIKindMap`
+
+- Purpose: maps asset kinds to UI-specific model folders
+  ([models.py:121](../../src/store/models.py#L121)).
+- Fields: `checkpoint`, `lora`, `vae`, `embedding`, `controlnet`, `upscaler`,
+  `clip`, `text_encoder`, `diffusion_model`, `unet`.
+- Invariants: `get_path()` maps by `AssetKind.value`
+  ([models.py:134](../../src/store/models.py#L134)).
+- Used by: `ViewBuilder.compute_plan`, `UIAttacher`, default UI config.
+- Persistence: config JSON.
+- Design note: missing `custom_node` and `unknown`. ViewBuilder falls back to
+  `models/<kind>`, but `UIAttacher` skips unmapped kinds, so attach is inconsistent
+  ([view_builder.py:85](../../src/store/view_builder.py#L85), [ui_attach.py:333](../../src/store/ui_attach.py#L333)).
+
+#### `UIConfig`
+
+- Purpose: known UI names and per-UI kind maps
+  ([models.py:139](../../src/store/models.py#L139)).
+- Fields: `known`, `kind_map`.
+- Invariants: default known UIs are `comfyui`, `forge`, `a1111`, `sdnext`.
+- Used by: `StoreConfig`, runtime initialization, view planning, attach.
+- Persistence: config JSON.
+- Design note: UI roots live outside this model in app config passed to UIAttacher,
+  producing a split between store state and application config.
+
+#### `ProviderConfig`
+
+- Purpose: provider defaults for file selection
+  ([models.py:199](../../src/store/models.py#L199)).
+- Fields: `primary_file_only_default`, `preferred_ext`.
+- Invariants: default Civitai/HF provider configs are written by `StoreConfig.create_default`
+  ([models.py:257](../../src/store/models.py#L257)).
+- Used by: limited. NEEDS VERIFICATION: current resolver code mostly uses selector
+  constraints rather than provider defaults directly.
+- Persistence: config JSON.
+
+#### `CivitaiSelectorConfig`, `BaseModelAliasSelector`, `BaseModelAlias`
+
+- Purpose: configured aliases for base model hints
+  ([models.py:205](../../src/store/models.py#L205), [models.py:214](../../src/store/models.py#L214),
+  [models.py:220](../../src/store/models.py#L220)).
+- Fields: Civitai `model_id`, `version_id`, `file_id`; alias kind/default filename/selector.
+- Invariants: default aliases currently use placeholder zeros
+  ([models.py:274](../../src/store/models.py#L274)).
+- Used by: `_create_base_model_dependency`, `BaseModelHintResolver`
+  ([pack_service.py:603](../../src/store/pack_service.py#L603), [dependency_resolver.py:209](../../src/store/dependency_resolver.py#L209)).
+- Persistence: config JSON.
+- Design note: placeholder zero IDs are normal config data in main, while resolve
+  redesign validation rejects zero IDs ([resolve_validation.py branch:64]).
+
+#### `ConfigDefaults`, `BackupConfig`, `StoreConfig`
+
+- Purpose: global defaults, backup config, root persisted config
+  ([models.py:227](../../src/store/models.py#L227), [models.py:235](../../src/store/models.py#L235),
+  [models.py:243](../../src/store/models.py#L243)).
+- Fields: default UI set, conflict mode, active/use base defaults, backup path/options,
+  providers, base aliases.
+- Invariants: `schema_` aliases to JSON `schema`; layout writes with aliases
+  ([layout.py:322](../../src/store/layout.py#L322)).
+- Used by: Store facade defaults, runtime init, backup service, UI attach.
+- Persistence: `state/config.json`.
+- Design note: `defaults.active_profile` and `defaults.use_base` do not appear to be
+  authoritative for runtime, which is in `data/runtime.json`.
+
+#### `UISets`
+
+- Purpose: named sets of UI targets
+  ([models.py:314](../../src/store/models.py#L314)).
+- Fields: `schema`, `sets`.
+- Invariants: default sets include named and singleton sets
+  ([models.py:321](../../src/store/models.py#L321)).
+- Used by: Store facade `get_ui_targets`, profile service, view builder.
+- Persistence: `state/ui_sets.json`.
+- Design note: default UI set name lives in `StoreConfig.defaults.ui_set`, while set
+  members live in `UISets`. That split is acceptable but needs migration discipline.
+
+### Pack, Source, Dependencies
+
+#### `CivitaiSelector`
+
+- Purpose: Civitai dependency selector
+  ([models.py:350](../../src/store/models.py#L350)).
+- Fields: `model_id`, optional `version_id`, optional `file_id`.
+- Invariants: current main does not reject `0`; branch validation does.
+- Used by: dependency resolver, import, update, resolve branch.
+- Persistence: pack JSON.
+- Design note: Civitai model/version/file identity is spread across this selector,
+  `PackSource`, `ArtifactProvider`, `BlobOrigin`, and `ModelInfo.civitai_air`.
+
+#### `HuggingFaceSelector`
+
+- Purpose: HuggingFace file selector
+  ([models.py:359](../../src/store/models.py#L359)).
+- Fields: `repo_id`, `filename`, optional `revision`, optional `subfolder`.
+- Invariants: strategy should require repo and filename; not enforced in main.
+- Used by: `HuggingFaceResolver`
+  ([dependency_resolver.py:270](../../src/store/dependency_resolver.py#L270)).
+- Persistence: pack JSON.
+- Design note: HF path can be represented as `subfolder + filename`; lock stores
+  `repo_id`, `filename`, `revision`, but not `subfolder` in `ArtifactProvider`.
+
+#### `SelectorConstraints`
+
+- Purpose: file selection filters
+  ([models.py:367](../../src/store/models.py#L367)).
+- Fields: `primary_file_only`, `file_ext`, `base_model_hint`.
+- Invariants: resolver helper applies primary and extension filters
+  ([dependency_resolver.py:344](../../src/store/dependency_resolver.py#L344)).
+- Used by: Civitai latest/file and base model resolver path.
+- Persistence: pack JSON.
+- Design note: `base_model_hint` duplicates `Pack.base_model`, dependency `selector.base_model`,
+  and branch candidate `base_model`.
+
+#### `DependencySelector`
+
+- Purpose: strategy plus provider-specific selector payload
+  ([models.py:374](../../src/store/models.py#L374)).
+- Fields: `strategy`, optional `civitai`, `huggingface`, `base_model`, `url`,
+  `local_path`, `constraints`.
+- Invariants: no discriminator validation; impossible and incomplete states are allowed.
+- Used by: all dependency resolution and update paths.
+- Persistence: pack JSON.
+- Design note: branch adds `canonical_source` to this object
+  ([branch models.py:381](../../src/store/models.py#L381) via git show). That is a
+  good direction for local/URL deps with remote provenance, but it makes the selector
+  both "how to obtain" and "what this really is".
+
+#### `ExposeConfig`
+
+- Purpose: UI-facing filename and trigger words
+  ([models.py:395](../../src/store/models.py#L395)).
+- Fields: `filename`, `trigger_words`.
+- Invariants: filename cannot start with dot, include path separators, nulls, or `..`
+  ([models.py:108](../../src/store/models.py#L108)).
+- Used by: view paths, inventory display names, blob manifest original filename.
+- Persistence: pack JSON.
+- Design note: `filename` is part of view identity and conflict behavior; changing it
+  changes runtime exposed paths but not the blob.
+
+#### `PackDependency`
+
+- Purpose: one asset dependency inside a pack
+  ([models.py:406](../../src/store/models.py#L406)).
+- Fields: `id`, `kind`, `required`, `selector`, `update_policy`, `expose`, `description`.
+- Invariants: `id` safe-name validation; pack validates unique IDs
+  ([models.py:416](../../src/store/models.py#L416), [models.py:894](../../src/store/models.py#L894)).
+- Used by: import, resolve, install, update, view build, inventory.
+- Persistence: pack JSON.
+- Design note: `required` is ignored by `resolve_pack`, which records unresolved deps
+  without distinguishing required vs optional ([pack_service.py:1153](../../src/store/pack_service.py#L1153)).
+
+#### `PackSource`
+
+- Purpose: source information for the pack as a whole
+  ([models.py:422](../../src/store/models.py#L422)).
+- Fields: `provider`, optional Civitai `model_id`, optional `version_id`, optional `url`.
+- Invariants: required on every `Pack`.
+- Used by: search result/provider display, import/custom creation.
+- Persistence: pack JSON.
+- Design flaw: this is per-pack, but dependencies are per-artifact. A custom pack can
+  contain Civitai, HF, local, and URL dependencies simultaneously. `Pack.source` then
+  becomes either misleading or merely "creation source".
+
+#### `PackResources`
+
+- Purpose: keep-in-git flags for pack resources
+  ([models.py:432](../../src/store/models.py#L432)).
+- Fields: `previews_keep_in_git`, `workflows_keep_in_git`.
+- Used by: stored on `Pack`; NEEDS VERIFICATION for enforcement.
+- Persistence: pack JSON.
+- Design note: flags exist, but resource path conventions are split:
+  previews under `resources/previews`, workflows at `pack_dir/workflows`
+  ([layout.py:181](../../src/store/layout.py#L181)).
+
+#### `PackDependencyRef`
+
+- Purpose: pack-to-pack dependency edge
+  ([models.py:438](../../src/store/models.py#L438)).
+- Fields: `pack_name`, `required`, `version_constraint`.
+- Invariants: safe pack name; `Pack` validates unique names and no self-reference
+  ([models.py:902](../../src/store/models.py#L902)).
+- Used by: API CRUD/status/tree and reverse update impact
+  ([api.py:2963](../../src/store/api.py#L2963), [update_service.py:256](../../src/store/update_service.py#L256)).
+- Persistence: pack JSON.
+- Design flaw: view/profile composition ignores this field. `_load_packs_for_profile`
+  only loads direct `profile.packs` ([profile_service.py:473](../../src/store/profile_service.py#L473)).
+
+#### `GenerationParameters`
+
+- Purpose: generation settings from Civitai or AI
+  ([models.py:460](../../src/store/models.py#L460)).
+- Fields: sampler/scheduler/steps/cfg/size/seed/LoRA strength/hires fields plus extras.
+- Invariants: `extra="allow"` and custom serializer drops `None`
+  ([models.py:477](../../src/store/models.py#L477), [models.py:763](../../src/store/models.py#L763)).
+- Used by: Civitai import AI extraction
+  ([pack_service.py:536](../../src/store/pack_service.py#L536)).
+- Persistence: pack JSON.
+- Design note: this model has a lot of AI normalization logic inside the core domain
+  model. Consider moving normalization to an adapter and keeping the persisted model
+  simpler.
+
+#### `ModelInfo`
+
+- Purpose: extended model metadata
+  ([models.py:776](../../src/store/models.py#L776)).
+- Fields: model type/base model/trigger words/hash fields/AIR/stats/published/strength.
+- Used by: Civitai import metadata, UI details.
+- Persistence: pack JSON.
+- Design note: contains source evidence like hashes and Civitai AIR, overlapping
+  with lock provider/hash identity.
+
+#### `WorkflowInfo`
+
+- Purpose: metadata for included ComfyUI workflows
+  ([models.py:794](../../src/store/models.py#L794)).
+- Fields: `name`, `filename`, optional description/source URL, `is_default`.
+- Used by: pack JSON/UI workflow features.
+- Persistence: pack JSON, with workflow files under pack directories.
+- Design note: workflow JSON is not modeled as first-class content. There is no
+  dependency graph extracted from workflow nodes.
+
+#### `PreviewInfo`
+
+- Purpose: image/video preview metadata
+  ([models.py:803](../../src/store/models.py#L803)).
+- Fields: filename, URL, NSFW, dimensions, metadata dict, media type, video details.
+- Invariants: media type is `Literal['image','video','unknown']`
+  ([models.py:819](../../src/store/models.py#L819)).
+- Used by: import, gallery, resolve preview analysis.
+- Persistence: pack JSON plus files under resources/previews.
+- Design note: preview `meta` is raw `Dict[str, Any]`, which is flexible but hides
+  the evidence contract needed by resolve/workflow import.
+
+#### `Pack`
+
+- Purpose: central persisted pack document
+  ([models.py:837](../../src/store/models.py#L837)).
+- Fields: schema, name, pack type/category/source, dependencies, pack dependencies,
+  resources, previews, cover, version/description/base/author/tags/user tags/trigger
+  words, created timestamp, parameters, model info, workflows.
+- Invariants: safe name; unique dependency IDs; unique pack deps; no self pack dep.
+- Used by: almost every store service.
+- Persistence: `state/packs/<pack>/pack.json`.
+- Design flaw: `Pack` is simultaneously package metadata, model import metadata,
+  dependency manifest, gallery/workflow container, update policy holder, and future
+  installer descriptor. Extensions will add more unrelated optional fields unless
+  it is split into typed facets.
+
+### Lock And Resolution State
+
+#### `ArtifactProvider`
+
+- Purpose: provider information for resolved artifacts
+  ([models.py:924](../../src/store/models.py#L924)).
+- Fields: provider enum; Civitai IDs; HF repo/filename/revision.
+- Used by: lock, inventory origin, blob manifest origin.
+- Persistence: lock JSON.
+- Design note: missing `subfolder`, URL, local original path, and source URL details.
+
+#### `ArtifactDownload`
+
+- Purpose: download URLs for a resolved artifact
+  ([models.py:937](../../src/store/models.py#L937)).
+- Fields: `urls`.
+- Used by: `install_pack`, update pending downloads.
+- Persistence: lock JSON.
+- Design note: no auth requirement, expiry, mirror priority, method, headers, or source
+  evidence. Civitai signed URLs may age out NEEDS VERIFICATION.
+
+#### `ArtifactIntegrity`
+
+- Purpose: integrity verification status
+  ([models.py:942](../../src/store/models.py#L942)).
+- Fields: `sha256_verified`.
+- Used by: lock and install mutation.
+- Persistence: lock JSON.
+- Design note: hash itself lives on `ResolvedArtifact.sha256`; integrity only stores a
+  boolean. It cannot distinguish "provider hash trusted" from "download verified".
+
+#### `ResolvedArtifact`
+
+- Purpose: fully or partially resolved downloadable artifact
+  ([models.py:947](../../src/store/models.py#L947)).
+- Fields: kind, optional SHA256, size, provider, download, integrity.
+- Used by: lock, view build, install, inventory, update.
+- Persistence: lock JSON.
+- Design note: `sha256` can be absent for HF/URL until download; install mutates lock
+  after download when hash was unknown ([pack_service.py:1288](../../src/store/pack_service.py#L1288)).
+
+#### `ResolvedDependency`
+
+- Purpose: lock entry tying dependency ID to artifact
+  ([models.py:963](../../src/store/models.py#L963)).
+- Fields: `dependency_id`, `artifact`.
+- Invariants: no validation that `dependency_id` exists in pack JSON.
+- Used by: lock, view build, inventory, updates.
+- Persistence: lock JSON.
+
+#### `UnresolvedDependency`
+
+- Purpose: lock entry for failed resolution
+  ([models.py:969](../../src/store/models.py#L969)).
+- Fields: `dependency_id`, `reason`, `details`.
+- Used by: resolve/status.
+- Persistence: lock JSON.
+- Design note: does not carry required/optional severity, retry strategy, or candidate
+  evidence.
+
+#### `PackLock`
+
+- Purpose: resolved state for a pack
+  ([models.py:976](../../src/store/models.py#L976)).
+- Fields: schema, pack name, resolved timestamp, resolved and unresolved lists.
+- Invariants: `is_fully_resolved()` only checks no unresolved entries, not that every
+  pack dependency has a resolved entry ([models.py:993](../../src/store/models.py#L993)).
+- Used by: install, view build, inventory, update, status.
+- Persistence: `state/packs/<pack>/lock.json`.
+- Design flaw: no generation/source fingerprint. It does not record which `pack.json`
+  dependency definitions it was resolved against, so stale locks are hard to detect.
+
+### Profiles, Runtime, Reports
+
+#### `ProfilePackEntry`
+
+- Purpose: ordered pack entry in a profile
+  ([models.py:1002](../../src/store/models.py#L1002)).
+- Fields: `name`.
+- Invariants: safe name.
+- Used by: `Profile.packs`, work profile creation, view planning.
+- Persistence: profile JSON.
+- Design note: current model has no `enabled`, but CLI references `pack_entry.enabled`
+  ([cli.py:527](../../src/store/cli.py#L527)). That is a real drift/bug.
+
+#### `Profile`
+
+- Purpose: ordered collection of packs plus conflict config
+  ([models.py:1017](../../src/store/models.py#L1017)).
+- Fields: schema, name, conflicts, packs.
+- Invariants: safe name; `add_pack` deduplicates then appends
+  ([models.py:1031](../../src/store/models.py#L1031)).
+- Used by: global/work profiles, view build, runtime activation.
+- Persistence: profile JSON.
+- Design note: profile has no direct `pack_dependencies` field. Pack-to-pack dependencies
+  are not expanded here.
+
+#### `UIRuntimeState` and `Runtime`
+
+- Purpose: runtime profile stack per UI
+  ([models.py:1053](../../src/store/models.py#L1053), [models.py:1058](../../src/store/models.py#L1058)).
+- Fields: stack defaults to `["global"]`; runtime maps UI name to state.
+- Invariants: pop refuses to remove base stack item; set_stack can set any list.
+- Used by: `use`, `back`, status, profiles page.
+- Persistence: `data/runtime.json`.
+- Design note: runtime stores profile names without referential integrity. If a profile
+  is deleted, stack entries can point to missing profiles until commands handle it.
+
+#### `MissingBlob`, `UnresolvedReport`, `ShadowedEntry`, `StatusReport`
+
+- Purpose: status/diagnostic response models
+  ([models.py:1110](../../src/store/models.py#L1110), [models.py:1118](../../src/store/models.py#L1118),
+  [models.py:1126](../../src/store/models.py#L1126), [models.py:1134](../../src/store/models.py#L1134)).
+- Fields: pack/dependency/blob data, unresolved reason, shadowed winner/loser, active UI map.
+- Used by: Store status/doctor, profile use result, CLI/API.
+- Persistence: response only.
+- Design note: `Store.status()` always returns `shadowed=[]` even though `ViewBuilder`
+  computes shadowed entries ([__init__.py:951](../../src/store/__init__.py#L951)).
+
+#### Update, Doctor, Search, Use/Back/Reset/Delete Models
+
+- `UpdateChange`, `UpdateCandidate`, `AmbiguousUpdate`, `PendingDownload`, `UpdatePlan`,
+  `UpdateOptions`, `UpdateResult`, `BatchUpdateResult`
+  ([models.py:1144](../../src/store/models.py#L1144)).
+- Purpose: update planning/application DTOs.
+- Persistence: response only, except updates mutate lock/pack.
+- Design note: `UpdateCandidate.provider` is raw `str` while providers elsewhere use
+  `ProviderName` ([models.py:1155](../../src/store/models.py#L1155)).
+- `DoctorActions`, `DoctorReport`
+  ([models.py:1216](../../src/store/models.py#L1216)).
+- Purpose: diagnostic/repair response.
+- Design note: DB rebuild is explicitly placeholder in Store doctor
+  ([__init__.py:1030](../../src/store/__init__.py#L1030)).
+- `SearchResultItem`, `SearchResult`
+  ([models.py:1235](../../src/store/models.py#L1235)).
+- Purpose: search response.
+- `UseResult`, `BackResult`, `ResetResult`, `DeleteResult`
+  ([models.py:1253](../../src/store/models.py#L1253)).
+- Purpose: command response DTOs.
+- Design note: `UseResult.shadowed` is populated during `ProfileService.use`, but
+  general status loses it unless views are rebuilt ([profile_service.py:240](../../src/store/profile_service.py#L240)).
+
+### Inventory, Blob, Backup, Sync
+
+#### `BlobStatus`, `BlobLocation`
+
+- Purpose: inventory state enums
+  ([models.py:1296](../../src/store/models.py#L1296), [models.py:1304](../../src/store/models.py#L1304)).
+- Fields: referenced/orphan/missing/backup_only; local_only/backup_only/both/nowhere.
+- Used by: inventory, cleanup, impact analysis.
+- Persistence: response only.
+- Design note: `BlobStatus.BACKUP_ONLY` means referenced but not local in service code;
+  backup-only orphan is emitted as `ORPHAN` with `location=BACKUP_ONLY`
+  ([inventory_service.py:170](../../src/store/inventory_service.py#L170)).
+
+#### `BlobOrigin`, `PackReference`
+
+- Purpose: origin and pack reference metadata
+  ([models.py:1312](../../src/store/models.py#L1312), [models.py:1324](../../src/store/models.py#L1324)).
+- Fields: provider IDs/repo filename; pack/dependency/kind/expose/size/origin.
+- Used by: inventory and blob manifest creation.
+- Persistence: response only and embedded in `BlobManifest`.
+- Design note: mirrors `ArtifactProvider`; should probably be a shared canonical source
+  or derived view.
+
+#### `InventoryItem`, `BackupStats`, `InventorySummary`, `InventoryResponse`
+
+- Purpose: blob inventory response
+  ([models.py:1334](../../src/store/models.py#L1334), [models.py:1359](../../src/store/models.py#L1359),
+  [models.py:1375](../../src/store/models.py#L1375), [models.py:1391](../../src/store/models.py#L1391)).
+- Fields: hash/kind/display/size/location/status/refs/origin/active UIs/verification/summary.
+- Used by: inventory endpoints and cleanup.
+- Persistence: response only.
+- Design note: `active_in_uis` is always `[]` in service construction with TODO
+  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).
+
+#### `CleanupResult`, `MigrateManifestsResult`, `ImpactAnalysis`
+
+- Purpose: inventory mutation/impact responses
+  ([models.py:1398](../../src/store/models.py#L1398), [models.py:1408](../../src/store/models.py#L1408),
+  [models.py:1418](../../src/store/models.py#L1418)).
+- Used by: cleanup, manifest migration, delete guards.
+- Persistence: response only.
+
+#### `BlobManifest`
+
+- Purpose: write-once orphan metadata
+  ([models.py:1435](../../src/store/models.py#L1435)).
+- Fields: integer version, created timestamp, original filename, kind, origin.
+- Invariants: write-once; `BlobStore.write_manifest` never overwrites
+  ([blob_store.py:560](../../src/store/blob_store.py#L560)).
+- Used by: inventory display for orphan blobs, installation manifest creation.
+- Persistence: `data/blobs/sha256/<prefix>/<sha>.meta.json`.
+- Design note: "immutable" is enforced by write path, but no hash/source authority is
+  stored beyond filename/kind/origin.
+
+#### Backup And State Sync Models
+
+- `BackupStatus`, `BackupOperationResult`, `BackupDeleteResult`
+  ([models.py:1454](../../src/store/models.py#L1454)).
+- Purpose: backup connection and operation responses.
+- `SyncItem`, `SyncResult`
+  ([models.py:1489](../../src/store/models.py#L1489)).
+- Purpose: blob backup push/pull result; `direction` is raw string.
+- `StateSyncStatus`, `StateSyncItem`, `StateSyncSummary`, `StateSyncResult`
+  ([models.py:1517](../../src/store/models.py#L1517)).
+- Purpose: state directory backup sync model.
+- Design note: `StateSyncStatus.CONFLICT` exists but `_analyze_state_file` returns
+  `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
+
+#### `APIResponse`
+
+- Purpose: generic API wrapper
+  ([models.py:1561](../../src/store/models.py#L1561)).
+- Fields: `ok`, optional result/error.
+- Used by: API layer where adopted.
+- Persistence: response only.
+
+### Related Dataclasses Outside `models.py`
+
+#### `PreviewDownloadConfig`, `DownloadProgressInfo`
+
+- Purpose: pack import preview/download operation DTOs
+  ([pack_service.py:72](../../src/store/pack_service.py#L72), [pack_service.py:93](../../src/store/pack_service.py#L93)).
+- Design note: service-local Pydantic models with `Literal` status.
+
+#### `ViewEntry`, `ViewPlan`, `BuildReport`
+
+- Purpose: derived view plan/build report
+  ([view_builder.py:51](../../src/store/view_builder.py#L51)).
+- Fields: pack/dependency/kind/expose/hash/destination; shadowed and missing lists.
+- Persistence: not persisted, except symlink filesystem output.
+- Design note: this is where conflict resolution actually happens, not in `Profile`.
+
+#### `AttachResult`
+
+- Purpose: UI attach/detach result DTO
+  ([ui_attach.py:34](../../src/store/ui_attach.py#L34)).
+- Persistence: response only.
+- Design note: method is raw string.
+
+## 2. Enum Audit
+
+### `PackCategory`
+
+- Current values cover origin/editability in a coarse way.
+- `CUSTOM` can cover workflow-imported packs if workflow import is just user-owned
+  metadata plus dependencies.
+- A new `WORKFLOW` category is useful only if workflow packs have distinct lifecycle,
+  e.g. extracted graph, workflow JSON validation, dependency suggestion, and UI wizard
+  state.
+- `INSTALL` should not remain only a category once executable behavior is added.
+  It needs a typed install facet with trust, script manifest, environment state, logs,
+  process controls, and UI root outputs.
+- Recommendation: keep `PackCategory` small as origin/editability, add subtype/facet
+  models: `WorkflowFacet`, `InstallFacet`, possibly `ExternalSourceFacet`.
+
+### `AssetKind`
+
+- Missing or weakly wired: custom node folders, workflows, UI install environments,
+  extensions/plugins, configs.
+- `CUSTOM_NODE` exists but is not covered by `UIKindMap` and `_kind_to_comfyui_name`
+  ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+- `WORKFLOW` is not an asset kind; workflows are separate `WorkflowInfo`.
+- A pack can mix dependency kinds because `Pack.dependencies` is a list of per-dep
+  kinds, while `Pack.pack_type` is one top-level kind. This top-level `pack_type` is
+  therefore descriptive, not exhaustive.
+- Recommendation: rename or document `Pack.pack_type` as `primary_kind`, and add asset
+  kinds only for assets that become blobs/views. Keep workflows separate if they are
+  pack resources, not model files.
+
+### `ProviderName`
+
+- Current provider enum covers Civitai, HuggingFace, local, URL.
+- Future providers can be represented as `URL` only if update/canonical semantics are
+  intentionally lost.
+- Recommendation: use `ProviderName` for known provider integrations, but add
+  `ProviderName.UNKNOWN` or a `provider_id: str` plus typed payload union if plugins
+  can introduce providers.
+
+### `SelectorStrategy`, `UpdatePolicyMode`, `ConflictMode`
+
+- `SelectorStrategy` is fully registered in `PackService._ensure_resolvers`
+  ([pack_service.py:1193](../../src/store/pack_service.py#L1193)).
+- `UpdatePolicyMode` is wired for Civitai latest where provider registered
+  ([__init__.py:246](../../src/store/__init__.py#L246)).
+- `ConflictMode` is not fully wired. `ViewPlan.add_entry` implements last-wins only.
+- Recommendation: either remove `FIRST_WINS`/`STRICT` until implemented or make
+  `ViewBuilder.compute_plan` branch on `profile.conflicts.mode`.
+
+### String-Typed Enums Hiding In Models
+
+- `PreviewInfo.media_type` is `Literal['image','video','unknown']`
+  ([models.py:819](../../src/store/models.py#L819)).
+- `DownloadProgressInfo.status` is a `Literal`
+  ([pack_service.py:115](../../src/store/pack_service.py#L115)).
+- `SyncResult.direction` and `StateSyncResult.direction` are raw strings
+  ([models.py:1500](../../src/store/models.py#L1500), [models.py:1550](../../src/store/models.py#L1550)).
+- `AttachResult.method` is a raw string
+  ([ui_attach.py:39](../../src/store/ui_attach.py#L39)).
+- Recommendation: promote repeated public response literals to enums if clients depend
+  on them.
+
+## 3. Pack Shape Audit
+
+### Cohesion
+
+- `Pack` fields are not cohesive around one lifecycle.
+- External model import fields: `source`, `model_info`, `previews`, `base_model`,
+  provider tags, trigger words.
+- Custom pack fields: `user_tags`, editable description, custom dependencies, workflows.
+- Install pack future fields are absent despite `PackCategory.INSTALL`.
+- Workflow future fields are partial: workflow metadata exists, but not imported workflow
+  JSON as typed graph/source.
+
+### `Pack.source`
+
+- `Pack.source` is required and per-pack ([models.py:843](../../src/store/models.py#L843)).
+- For Civitai imports, it records model/version/url ([pack_service.py:514](../../src/store/pack_service.py#L514)).
+- For custom packs, API writes `provider=LOCAL` even when future dependencies may be
+  remote ([api.py:3314](../../src/store/api.py#L3314)).
+- Design recommendation: reinterpret as `creation_source` or remove as authoritative
+  source. Dependency source identity should live per dependency/candidate/lock.
+
+### `pack_dependencies`
+
+- Model validation prevents duplicate names and self-reference
+  ([models.py:902](../../src/store/models.py#L902)).
+- API can add/remove/status/tree pack dependencies
+  ([api.py:3036](../../src/store/api.py#L3036), [api.py:3170](../../src/store/api.py#L3170)).
+- Update service can find reverse dependency impact
+  ([update_service.py:256](../../src/store/update_service.py#L256)).
+- Profile/view runtime does not compose them
+  ([profile_service.py:483](../../src/store/profile_service.py#L483), [view_builder.py:236](../../src/store/view_builder.py#L236)).
+- `version_constraint` is stored but not enforced.
+- Recommendation: decide whether these are operational. If yes, add dependency expansion
+  service with cycle detection, optional/required policy, version checks, and stable
+  view order.
+
+### Pack vs Lock
+
+- Pack is desired state; lock is resolved artifact state.
+- Pack dependency selector can say "Civitai latest"; lock says exactly which version/file/hash.
+- Lock can be updated without pack selector changing (`UpdateService.apply_update`)
+  ([update_service.py:346](../../src/store/update_service.py#L346)).
+- Pack can be changed without lock changing in resolve redesign apply path
+  ([branch pack_service.py:1217](../../src/store/pack_service.py#L1217) via git show).
+- Recommendation: add a lock `pack_fingerprint` or per-dependency selector fingerprint
+  so stale locks are visible.
+
+### Hash Authority
+
+- SHA256 appears in `ModelInfo.hash_sha256`, `ResolvedArtifact.sha256`,
+  `PendingDownload.sha256`, `InventoryItem.sha256`, `BlobManifest` path, and physical
+  blob path.
+- The authoritative content address should be the blob path/hash and lock artifact hash.
+- `ModelInfo.hash_sha256` should be treated as provider metadata, not runtime authority.
+- Divergence paths:
+  - lock has hash but blob missing;
+  - HF/URL lock has no hash until install mutates it;
+  - manifest exists for old origin after pack dependency renamed;
+  - pack model info hash differs from resolved dependency hash.
+
+### Storage Separation
+
+- `pack.json`: user/provider metadata and desired dependencies.
+- `lock.json`: resolved artifacts and download URLs.
+- `BlobManifest`: orphan fallback display metadata.
+- This separation is conceptually good.
+- Missing piece: explicit derivation metadata tying lock and manifest back to pack
+  dependency version/fingerprint.
+
+## 4. Dependency Model Audit
+
+- `PackDependency` is desired dependency.
+- `PackDependencyRef` is pack-to-pack edge.
+- `ResolvedDependency` is lock result.
+- Branch `ResolutionCandidate` is suggestion DTO
+  ([branch resolve_models.py:77](../../src/store/models.py#L77) via git show).
+- Branch `CanonicalSource` is remote identity independent of install strategy
+  ([branch models.py:381](../../src/store/models.py#L381) via git show).
+
+Design overlaps:
+
+- `DependencySelector.civitai` and `CanonicalSource` both can carry Civitai model/version/file.
+- `HuggingFaceSelector` and `CanonicalSource` both can carry HF repo/path/revision.
+- `ArtifactProvider` and `BlobOrigin` repeat provider identity.
+- `PackSource` overlaps only for external single-source packs.
+
+Unresolved expression:
+
+- Main supports unresolved deps by leaving them in pack JSON and recording lock
+  `UnresolvedDependency`.
+- It does not need placeholders in normal selectors, but current defaults and branch
+  evidence providers do use `model_id=0` placeholders
+  ([models.py:280](../../src/store/models.py#L280), [branch evidence_providers.py:198] via git show).
+- Recommendation: introduce explicit "unresolved candidate" or "hint" objects instead
+  of invalid selectors.
+
+Identity stability:
+
+- `dep.id` is stable unless user edits it. Lock depends on this string.
+- No immutable dependency UUID exists.
+- Rename/edit can orphan lock entries or break update history.
+- Recommendation: add immutable `dependency_uid` or forbid ID rename after lock exists.
+
+Multi-source candidates:
+
+- Branch candidates can represent multiple candidates per dependency.
+- PackDependency stores only one selected selector.
+- There is no first-class "alternatives" field. That is probably correct for pack JSON;
+  alternatives belong in candidate cache or review state.
+
+Required/optional:
+
+- `PackDependency.required` exists.
+- `PackDependencyRef.required` exists.
+- Resolve/install/status do not deeply honor optional severity.
+- Recommendation: optional unresolved deps should not make `PackLock.is_fully_resolved`
+  false unless policy says so, or lock should expose `required_unresolved`.
+
+## 5. Source, Evidence, Candidate
+
+- Current main has no `CanonicalSource`; resolve branch adds it to `DependencySelector`.
+- Branch candidate shape has `selector_data`, `canonical_source`, evidence groups,
+  display fields, provider, and base model ([branch resolve_models.py:77] via git show).
+- Branch apply reconstructs selector from `candidate.selector_data` and passes candidate
+  `canonical_source` to pack service ([branch resolve_service.py:289] via git show).
+- Branch pack service writes selector/canonical source only to `pack.json` and explicitly
+  does not touch lock ([branch pack_service.py:1226] via git show).
+
+Canonical reference proposal:
+
+- For blob identity: SHA256.
+- For Civitai source: `model_id + version_id + file_id` where available, plus SHA256
+  after resolution/download.
+- For HuggingFace source: `repo_id + revision + subfolder + filename`, with SHA256 when
+  available.
+- For local source: blob SHA256 plus optional original path as non-authoritative evidence.
+- For URL source: URL plus resolved SHA256; URL alone is not stable.
+
+Recommendation:
+
+- Keep `DependencySelector` as "how to resolve/download now".
+- Add a separate per-dependency `canonical_source` field or nested `SourceIdentity`
+  next to selector, not inside strategy payload, unless local/URL tracking requires it.
+- Replace `PackSource` with `creation_source` or a `PackOrigin` object that does not
+  pretend to identify every dependency.
+
+## 6. Profile, Runtime, View
+
+- `Profile.packs` is the only profile composition list
+  ([models.py:1022](../../src/store/models.py#L1022)).
+- There is no `Profile.pack_dependencies`.
+- Work profiles are named `work__<pack>` ([profile_service.py:83](../../src/store/profile_service.py#L83)).
+- Work profile creation copies base packs except target, then appends target for
+  last-wins behavior ([profile_service.py:134](../../src/store/profile_service.py#L134)).
+- Work profiles are updated on reuse, but no general garbage collection is evident in
+  the audited service.
+- Runtime stack stores profile names per UI; `use()` pushes, `back()` pops
+  ([profile_service.py:248](../../src/store/profile_service.py#L248), [profile_service.py:303](../../src/store/profile_service.py#L303)).
+- If underlying profile is deleted, runtime can hold stale names. `back(sync=True)` catches
+  `ProfileNotFoundError`; other flows may silently fail or activate stale views.
+- `ShadowedEntry` is computed in `ViewPlan.add_entry`; `BuildReport` carries it; `UseResult`
+  receives it; `Store.status()` does not compute it and returns empty.
+
+Recommendation:
+
+- Add `ProfileEntry.enabled` only if view builder honors it.
+- Implement `ConflictMode` or collapse it.
+- Add a profile stack repair/validation command for deleted profiles.
+- Persist or recompute shadowed entries consistently. Since views are derived, recompute
+  from current profile/locks when status asks for shadowed, or store build reports.
+
+## 7. Inventory, Blob, Backup
+
+- Inventory is derived live from physical blobs, backup blobs, and pack locks
+  ([inventory_service.py:79](../../src/store/inventory_service.py#L79)).
+- Reference map scans all pack locks and maps hash to pack references
+  ([inventory_service.py:221](../../src/store/inventory_service.py#L221)).
+- Orphan display falls back to write-once blob manifest
+  ([inventory_service.py:340](../../src/store/inventory_service.py#L340)).
+- Active UI tracking is modeled but not implemented (`active_in_uis=[]`)
+  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).
+- Backup blob sync is explicitly one-way by raw `direction` string `to_backup` or
+  `from_backup` ([backup_service.py:597](../../src/store/backup_service.py#L597)).
+- State sync claims `bidirectional`, but conflict detection is weak: differing files
+  become `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
+
+Recommendation:
+
+- Treat inventory active UI as derived, not stored.
+- Model sync direction as enum.
+- Define backup as push/pull, not mirror, unless deletion propagation is implemented.
+- For state sync, either remove `CONFLICT` or implement a base/snapshot marker.
+
+## 8. Resolve Redesign Integration
+
+- Branch `ResolutionCandidate` fits as a transient DTO, not as persisted pack state.
+- Branch `CanonicalSource` should become the shared source identity primitive, but it
+  should be reconciled with `PackSource`, `ArtifactProvider`, and `BlobOrigin`.
+- Field naming mismatches:
+  - current `PackSource.provider: ProviderName`;
+  - branch `CanonicalSource.provider: Literal["civitai","huggingface"]`;
+  - update candidate `provider: str`;
+  - candidate `provider` literal.
+- Applying a candidate likely needs:
+  - per-dependency canonical source;
+  - dependency selector update;
+  - optional expose filename/trigger update policy;
+  - lock invalidation or lock update;
+  - candidate evidence audit trail only if product wants explainability.
+- Branch apply currently ignores `lock_entry` and does not update lock
+  ([branch pack_service.py:1222] via git show).
+
+Recommendation:
+
+- Decide now whether apply updates lock. If not, make stale lock an explicit state in UI.
+- Make all candidates either applyable selectors or non-applyable hints. No `model_id=0`.
+- Bind candidate cache to `pack_name` and `dep_id`.
+
+## 9. Custom, Install, Workflow Pack Futures
+
+Custom packs:
+
+- Current `Pack` can represent custom packs without dependencies if source is `LOCAL`
+  and dependencies default empty.
+- API create currently calls `store.layout.pack_path`, which does not exist; layout has
+  `pack_dir` ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
+- Custom packs with mixed sources are poorly represented by per-pack `source`.
+
+Install packs:
+
+- `PackCategory.INSTALL` exists but no domain model for scripts, install dir, UI root,
+  health, ports, logs, trust, or process state.
+- Recommended fields/facets:
+  - `install_manifest`: scripts with hash, interpreter, args, environment policy;
+  - `install_dir`: local path controlled by store;
+  - `ui_roots`: produced UI target roots;
+  - `log_paths`: stdout/stderr/install logs;
+  - `process`: pid/ports/health/restart policy;
+  - `trust`: signer/source/risk acknowledgement.
+
+Workflow packs:
+
+- Current `WorkflowInfo` can list files, but not model workflow JSON as parsed data.
+- Imported workflow JSON should live as a pack resource plus typed extracted metadata:
+  nodes, model references, custom node refs, missing deps, source file hash, and import
+  wizard decisions.
+- `PackCategory.WORKFLOW` is optional if `WorkflowFacet` exists. Without a facet, a new
+  category will become another weak flag.
+
+## 10. UI / Attach Model
+
+- `UIKindMap` covers many model kinds for ComfyUI/Forge/A1111/SD.Next defaults, but not
+  `custom_node`.
+- ComfyUI extra_model_paths generation maps only a subset of kinds
+  ([ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+- Generic symlink attach iterates `AssetKind` but skips any kind with no kind-map path
+  ([ui_attach.py:333](../../src/store/ui_attach.py#L333)).
+- `default_ui_set` authority is split: default name in `StoreConfig.defaults.ui_set`,
+  actual set in `UISets`.
+- UI roots are passed to `UIAttacher` from app config, not persisted in store config
+  ([ui_attach.py:53](../../src/store/ui_attach.py#L53)).
+- `extra_model_paths.yaml` schema is built ad hoc as nested dictionaries, not modeled
+  ([ui_attach.py:94](../../src/store/ui_attach.py#L94)).
+
+Recommendation:
+
+- Add explicit UI attach config model: UI name, root, attach method, supported kind map.
+- Add ComfyUI YAML model if the app will edit and preserve user YAML repeatedly.
+- Decide whether custom nodes are install-pack assets rather than model blobs.
+
+## 11. Cross-Cutting Concerns
+
+Schema versioning:
+
+- Schema strings exist in file models, but load paths call direct `model_validate`
+  without migration dispatch ([layout.py:427](../../src/store/layout.py#L427)).
+- Recommendation: add `load_pack_document`/`migrate_pack` helpers and fail clearly on
+  unsupported future schemas.
+
+Pydantic:
+
+- Uses Pydantic v2 APIs (`field_validator`, `model_validator`, `model_serializer`).
+- No frozen models. Mutable lists are normal. This is convenient but makes accidental
+  in-place mutation common.
+- Recommendation: keep persisted models mutable for service ergonomics, but add command
+  methods for high-risk mutations or central write services.
+
+Validation:
+
+- Safe names prevent path separators and traversal, but dependency selectors are not
+  discriminated.
+- Recommendation: use discriminated unions for selector payloads:
+  `CivitaiFileSelector`, `HuggingFaceFileSelector`, `LocalFileSelector`, etc.
+
+Naming:
+
+- `pack`, `pack_name`, `name`, `pack_type`, `pack_category` are mostly consistent.
+- `pack_type` is misleading because pack can mix asset kinds. Prefer `primary_kind`.
+
+Serialization:
+
+- Aliased schema fields use `populate_by_name=True` and `by_alias=True` when layout
+  writes top-level models.
+- `GenerationParameters` custom serializer drops `None` and preserves extras.
+- NEEDS VERIFICATION: all API responses using `model_dump()` rather than
+  `model_dump(by_alias=True)` may expose `schema_` instead of `schema`.
+
+## 12. Observed Bugs / Smells
+
+1. `ProfilePackEntry.enabled` drift: model has no `enabled`, CLI accesses it
+   ([models.py:1002](../../src/store/models.py#L1002), [cli.py:527](../../src/store/cli.py#L527)).
+2. `Profile.conflicts.mode` ignored: view builder implements only last-wins
+   ([models.py:1012](../../src/store/models.py#L1012), [view_builder.py:91](../../src/store/view_builder.py#L91)).
+3. `StatusReport.shadowed` always empty in Store status
+   ([__init__.py:951](../../src/store/__init__.py#L951)).
+4. Placeholder Civitai IDs exist in default config
+   ([models.py:280](../../src/store/models.py#L280)).
+5. Resolve branch also emits placeholder `model_id=0` candidates in filename fallback
+   ([branch evidence_providers.py:198] via git show).
+6. `StoreLayout.pack_path()` does not exist, but API create pack calls it
+   ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
+7. `custom_node` asset kind is not attachable through current kind maps
+   ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+8. `version_constraint` on `PackDependencyRef` is stored but not enforced
+   ([models.py:452](../../src/store/models.py#L452)).
+9. `PackDependency.required` and `PackDependencyRef.required` are not reflected in
+   lock completeness or runtime composition.
+10. `StateSyncStatus.CONFLICT` is modeled but not produced by current comparison.
+11. `ArtifactProvider` lacks HF `subfolder`, while `HuggingFaceSelector` has it.
+12. `BlobStatus.BACKUP_ONLY` semantics are narrower than the enum name implies.
+
+## 13. Design Recommendations
+
+### Split `Pack`
+
+Keep:
+
+- `PackCore`: schema, name, category/origin, primary kind, version, description, tags.
+- `DependencyManifest`: model dependencies and pack dependencies.
+- `MediaFacet`: previews, cover, resources.
+- `GenerationFacet`: parameters/model info.
+- `WorkflowFacet`: workflow resources and extracted dependency hints.
+- `InstallFacet`: script/process/UI install metadata.
+
+### Merge Source Identity
+
+- Introduce one source identity model, likely evolved from branch `CanonicalSource`.
+- Use it in dependency desired state, lock provider/origin derivation, and blob manifest.
+- Keep provider-specific selector as an acquisition strategy.
+
+### Type-Narrow Selectors
+
+- Replace optional-field `DependencySelector` with a discriminated union.
+- Benefits: no invalid local selector without path, no Civitai strategy without Civitai
+  payload, no zero-ID placeholders.
+
+### Make Locks Staleness-Aware
+
+- Add lock-level `pack_fingerprint`.
+- Add per-resolved-entry `dependency_fingerprint`.
+- Show stale lock state in status and resolve UI.
+
+### Decide Operational Semantics For Pack Dependencies
+
+- If operational: expand required pack deps when building profiles/views.
+- If informational: rename to `related_packs` or `recommended_packs`.
+- Enforce `version_constraint` or remove it.
+
+### Wire Or Remove Modeled Fields
+
+- Implement `ConflictMode`.
+- Implement active UI inventory tracking or drop it from response.
+- Implement state sync conflicts or remove `CONFLICT`.
+- Add `ProfilePackEntry.enabled` intentionally or remove stale callers.
+
+### Schema Migration
+
+- Add migration helpers per persisted document.
+- Use schema version dispatch before Pydantic validation.
+- Keep migration tests with old fixture JSON.
+
+## 14. Open Questions For Owner
+
+1. Should `pack_dependencies` affect runtime composition, or are they advisory metadata?
+2. Should `apply_resolution()` update `lock.json`, invalidate it, or leave stale state
+   until explicit resolve?
+3. Is `Pack.source` meant to mean "creation source" or "all pack content source"?
+4. Do workflow imports deserve `PackCategory.WORKFLOW`, or should they be `CUSTOM` with
+   a workflow facet?
+5. Are install packs trusted first-party objects only, or can users import arbitrary
+   install packs?
+6. Should custom packs be backend-updatable when their dependencies use `FOLLOW_LATEST`?
+7. Should optional dependencies affect `PackLock.is_fully_resolved()`?
+8. Should dependency IDs be user-editable after a lock exists?
+9. Is ComfyUI custom node management part of store assets, install packs, or a separate
+   extension manager?
+10. Should backup state sync be push/pull only, or a true bidirectional merge with
+    conflict resolution?
+11. Should UI roots be persisted in store config or remain application config?
+12. What is the migration policy for existing `synapse.pack.v2` files once canonical
+    source lands?
+

exec
/bin/bash -lc 'wc -l plans/audits/codex-domain-audit.md' in /home/box/git/github/synapse
 succeeded in 0ms:
1095 plans/audits/codex-domain-audit.md

exec
/bin/bash -lc 'rg -n "NEEDS VERIFICATION|TODO|pack_path|enabled|CONFLICT|custom_node|CanonicalSource|PackSource|pack_dependencies" plans/audits/codex-domain-audit.md' in /home/box/git/github/synapse
 succeeded in 0ms:
19:   as partially-wired fields: `pack_dependencies`, `ConflictMode`, install packs,
25:   surfaces: `Pack.source`, `DependencySelector`, branch `CanonicalSource`,
30:5. `pack_dependencies` is modeled as operational but profile/view composition ignores
35:7. Current `ProfilePackEntry` does not have `enabled`, despite CLI code referencing it.
72:  `text_encoder`, `diffusion_model`, `embedding`, `custom_node`, `unet`, `unknown`
87:- Used by: `PackSource`, `ArtifactProvider`, `BlobOrigin`, update fallback.
153:- Design note: missing `custom_node` and `unknown`. ViewBuilder falls back to
175:- Used by: limited. NEEDS VERIFICATION: current resolver code mostly uses selector
230:  `PackSource`, `ArtifactProvider`, `BlobOrigin`, and `ModelInfo.civitai_air`.
294:#### `PackSource`
311:- Used by: stored on `Pack`; NEEDS VERIFICATION for enforcement.
410:  evidence. Civitai signed URLs may age out NEEDS VERIFICATION.
473:- Design note: current model has no `enabled`, but CLI references `pack_entry.enabled`
485:- Design note: profile has no direct `pack_dependencies` field. Pack-to-pack dependencies
564:- Design note: `active_in_uis` is always `[]` in service construction with TODO
598:- Design note: `StateSyncStatus.CONFLICT` exists but `_analyze_state_file` returns
599:  `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
715:### `pack_dependencies`
770:- Branch `CanonicalSource` is remote identity independent of install strategy
775:- `DependencySelector.civitai` and `CanonicalSource` both can carry Civitai model/version/file.
776:- `HuggingFaceSelector` and `CanonicalSource` both can carry HF repo/path/revision.
778:- `PackSource` overlaps only for external single-source packs.
814:- Current main has no `CanonicalSource`; resolve branch adds it to `DependencySelector`.
837:- Replace `PackSource` with `creation_source` or a `PackOrigin` object that does not
844:- There is no `Profile.pack_dependencies`.
859:- Add `ProfileEntry.enabled` only if view builder honors it.
878:  become `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
885:- For state sync, either remove `CONFLICT` or implement a base/snapshot marker.
890:- Branch `CanonicalSource` should become the shared source identity primitive, but it
891:  should be reconciled with `PackSource`, `ArtifactProvider`, and `BlobOrigin`.
893:  - current `PackSource.provider: ProviderName`;
894:  - branch `CanonicalSource.provider: Literal["civitai","huggingface"]`;
918:- API create currently calls `store.layout.pack_path`, which does not exist; layout has
946:  `custom_node`.
998:- NEEDS VERIFICATION: all API responses using `model_dump()` rather than
1003:1. `ProfilePackEntry.enabled` drift: model has no `enabled`, CLI accesses it
1013:6. `StoreLayout.pack_path()` does not exist, but API create pack calls it
1015:7. `custom_node` asset kind is not attachable through current kind maps
1021:10. `StateSyncStatus.CONFLICT` is modeled but not produced by current comparison.
1040:- Introduce one source identity model, likely evolved from branch `CanonicalSource`.
1066:- Implement state sync conflicts or remove `CONFLICT`.
1067:- Add `ProfilePackEntry.enabled` intentionally or remove stale callers.
1077:1. Should `pack_dependencies` affect runtime composition, or are they advisory metadata?

exec
/bin/bash -lc "git diff -- plans/audits/codex-domain-audit.md | sed -n '1,120p'" in /home/box/git/github/synapse
 succeeded in 0ms:
diff --git a/plans/audits/codex-domain-audit.md b/plans/audits/codex-domain-audit.md
new file mode 100644
index 0000000000000000000000000000000000000000..025f1f027c7782c98a603092a31822a5327609c4
--- /dev/null
+++ b/plans/audits/codex-domain-audit.md
@@ -0,0 +1,1095 @@
+# Synapse v2 Store Domain Model Audit
+
+Date: 2026-05-02
+
+Scope:
+
+- Primary model file: `src/store/models.py`.
+- Related domain/service files: `layout.py`, `__init__.py`, `pack_service.py`,
+  `profile_service.py`, `view_builder.py`, `dependency_resolver.py`,
+  `inventory_service.py`, `backup_service.py`, `update_service.py`,
+  `blob_store.py`, `ui_attach.py`.
+- Roadmap context: `plans/audits/CONSOLIDATED-FINDINGS.md`.
+- Resolve redesign comparison: `feat/resolve-model-redesign:src/store/resolve_models.py`
+  and touched model/write-path shape from that branch.
+
+## Executive Summary
+
+1. The domain model is usable today, but it is carrying several future-facing concepts
+   as partially-wired fields: `pack_dependencies`, `ConflictMode`, install packs,
+   custom nodes, workflows, backup state sync, and active UI inventory.
+2. `Pack` is doing too much: provider origin, dependency manifest, gallery metadata,
+   generation metadata, workflow metadata, editability, update behavior, and future
+   install-pack behavior are all on one object.
+3. Source identity is the biggest foundation risk. There are at least five identity
+   surfaces: `Pack.source`, `DependencySelector`, branch `CanonicalSource`,
+   `ResolvedArtifact.provider`, and `BlobManifest.origin`.
+4. Lock semantics are underspecified. The lock is the only place with resolved hashes
+   and download URLs, but update/apply/installation can mutate lock and blob state
+   independently. Divergence is normal, not exceptional.
+5. `pack_dependencies` is modeled as operational but profile/view composition ignores
+   it. API endpoints can create and show a dependency tree, while `use()` and `sync()`
+   do not recursively include those dependent packs.
+6. `AssetKind.CUSTOM_NODE` exists but is not mapped through `UIKindMap`, ComfyUI YAML
+   generation, or attach symlinks. This is a future workflow/custom-node blocker.
+7. Current `ProfilePackEntry` does not have `enabled`, despite CLI code referencing it.
+   This is model/API drift, not merely an ignored flag.
+8. Schema version strings exist in top-level persisted models, but there is no migration
+   runner, version dispatch, or compatibility policy in layout load paths.
+
+## Persistence Map
+
+- `state/config.json`: `StoreConfig` with `schema=synapse.config.v2`
+  ([models.py:243](../../src/store/models.py#L243), [layout.py:388](../../src/store/layout.py#L388)).
+- `state/ui_sets.json`: `UISets` with `schema=synapse.ui_sets.v1`
+  ([models.py:314](../../src/store/models.py#L314), [layout.py:399](../../src/store/layout.py#L399)).
+- `state/packs/<pack>/pack.json`: `Pack` with `schema=synapse.pack.v2`
+  ([models.py:837](../../src/store/models.py#L837), [layout.py:427](../../src/store/layout.py#L427)).
+- `state/packs/<pack>/lock.json`: `PackLock` with `schema=synapse.lock.v2`
+  ([models.py:976](../../src/store/models.py#L976), [layout.py:441](../../src/store/layout.py#L441)).
+- `state/profiles/<profile>/profile.json`: `Profile` with `schema=synapse.profile.v1`
+  ([models.py:1017](../../src/store/models.py#L1017), [layout.py:480](../../src/store/layout.py#L480)).
+- `data/runtime.json`: `Runtime` with `schema=synapse.runtime.v1`
+  ([models.py:1058](../../src/store/models.py#L1058), [layout.py:508](../../src/store/layout.py#L508)).
+- `data/blobs/sha256/<prefix>/<sha>`: content-addressed blobs
+  ([blob_store.py:88](../../src/store/blob_store.py#L88), [layout.py:229](../../src/store/layout.py#L229)).
+- `data/blobs/sha256/<prefix>/<sha>.meta.json`: `BlobManifest`
+  ([models.py:1435](../../src/store/models.py#L1435), [blob_store.py:533](../../src/store/blob_store.py#L533)).
+- `data/views/<ui>/profiles/<profile>` and `data/views/<ui>/active`: derived view state
+  ([layout.py:209](../../src/store/layout.py#L209), [view_builder.py:375](../../src/store/view_builder.py#L375)).
+- `data/.synapse.lock`: global file lock
+  ([layout.py:160](../../src/store/layout.py#L160), [layout.py:248](../../src/store/layout.py#L248)).
+
+## 1. Inventory Of Domain Objects
+
+### Config And UI Sets
+
+#### `AssetKind`
+
+- Purpose: vocabulary of assets Synapse can expose to UIs
+  ([models.py:31](../../src/store/models.py#L31)).
+- Fields/values: `checkpoint`, `lora`, `vae`, `controlnet`, `upscaler`, `clip`,
+  `text_encoder`, `diffusion_model`, `embedding`, `custom_node`, `unet`, `unknown`
+  ([models.py:33](../../src/store/models.py#L33)).
+- Invariants: enum values are used as serialized strings; no versioning or aliasing.
+- Used by: `Pack.pack_type`, `PackDependency.kind`, `ResolvedArtifact.kind`,
+  inventory, view planning, UI attach mapping.
+- Persistence: pack JSON, lock JSON, blob manifest, inventory/API responses.
+- Design note: `CUSTOM_NODE` is in the enum but missing from `UIKindMap` fields and
+  ComfyUI extra path mapping, so it is not fully operational.
+
+#### `ProviderName`
+
+- Purpose: supported provider identity enum
+  ([models.py:47](../../src/store/models.py#L47)).
+- Fields/values: `civitai`, `huggingface`, `local`, `url`.
+- Invariants: used in Pydantic provider/source models; no `unknown` provider.
+- Used by: `PackSource`, `ArtifactProvider`, `BlobOrigin`, update fallback.
+- Persistence: pack JSON, lock JSON, blob manifest, inventory.
+- Design note: fine for current providers, brittle for AI-discovered/community providers
+  unless the system accepts schema churn for every new provider.
+
+#### `SelectorStrategy`
+
+- Purpose: resolution strategy for a dependency
+  ([models.py:55](../../src/store/models.py#L55)).
+- Fields/values: `civitai_file`, `civitai_model_latest`, `huggingface_file`,
+  `base_model_hint`, `local_file`, `url_download`.
+- Invariants: strategy should imply which selector payload field is populated, but this
+  is not enforced by a discriminated union.
+- Used by: dependency resolvers, update providers, resolve redesign branch.
+- Persistence: pack JSON.
+- Design note: current model permits invalid combinations like `strategy=local_file`
+  with `civitai` data and no `local_path`.
+
+#### `UpdatePolicyMode` and `UpdatePolicy`
+
+- Purpose: choose whether a dependency is fixed or update-following
+  ([models.py:65](../../src/store/models.py#L65), [models.py:385](../../src/store/models.py#L385)).
+- Fields: `mode` defaults to `pinned`.
+- Invariants: `follow_latest` is considered updatable only when a provider is registered
+  for the dependency strategy ([update_service.py:107](../../src/store/update_service.py#L107)).
+- Used by: `UpdateService.plan_update`, `UpdateService.is_updatable`.
+- Persistence: pack JSON.
+- Design note: update behavior is dependency-level, not pack-level. A custom pack with
+  a `follow_latest` Civitai dependency is backend-updatable even if UI considers custom
+  packs non-updatable.
+
+#### `ConflictMode` and `ConflictConfig`
+
+- Purpose: profile conflict policy
+  ([models.py:71](../../src/store/models.py#L71), [models.py:1012](../../src/store/models.py#L1012)).
+- Fields/values: `last_wins`, `first_wins`, `strict`; profile default `last_wins`.
+- Invariants: only `last_wins` is implemented in `ViewPlan.add_entry`, which replaces
+  existing entries with later packs ([view_builder.py:91](../../src/store/view_builder.py#L91)).
+- Used by: stored on `Profile`, copied into work profiles
+  ([profile_service.py:128](../../src/store/profile_service.py#L128)).
+- Persistence: profile JSON.
+- Design note: `FIRST_WINS` and `STRICT` are modeled but ignored by view planning.
+
+#### `PackCategory`
+
+- Purpose: pack origin/editability class
+  ([models.py:78](../../src/store/models.py#L78)).
+- Fields/values: `external`, `custom`, `install`.
+- Invariants: comments imply editability and installation semantics, but services do
+  not enforce most of that.
+- Used by: imported Civitai packs are `external` ([pack_service.py:510](../../src/store/pack_service.py#L510));
+  API-created custom packs are `custom` ([api.py:3310](../../src/store/api.py#L3310)).
+- Persistence: pack JSON.
+- Design note: `INSTALL` is not just a category. It implies scripts, process lifecycle,
+  UI roots, trust, logs, and health state. It should probably be a subtype object.
+
+#### `UIKindMap`
+
+- Purpose: maps asset kinds to UI-specific model folders
+  ([models.py:121](../../src/store/models.py#L121)).
+- Fields: `checkpoint`, `lora`, `vae`, `embedding`, `controlnet`, `upscaler`,
+  `clip`, `text_encoder`, `diffusion_model`, `unet`.
+- Invariants: `get_path()` maps by `AssetKind.value`
+  ([models.py:134](../../src/store/models.py#L134)).
+- Used by: `ViewBuilder.compute_plan`, `UIAttacher`, default UI config.
+- Persistence: config JSON.
+- Design note: missing `custom_node` and `unknown`. ViewBuilder falls back to
+  `models/<kind>`, but `UIAttacher` skips unmapped kinds, so attach is inconsistent
+  ([view_builder.py:85](../../src/store/view_builder.py#L85), [ui_attach.py:333](../../src/store/ui_attach.py#L333)).
+
+#### `UIConfig`
+
+- Purpose: known UI names and per-UI kind maps
+  ([models.py:139](../../src/store/models.py#L139)).
+- Fields: `known`, `kind_map`.
+- Invariants: default known UIs are `comfyui`, `forge`, `a1111`, `sdnext`.
+- Used by: `StoreConfig`, runtime initialization, view planning, attach.
+- Persistence: config JSON.
+- Design note: UI roots live outside this model in app config passed to UIAttacher,
+  producing a split between store state and application config.
+
+#### `ProviderConfig`
+
+- Purpose: provider defaults for file selection
+  ([models.py:199](../../src/store/models.py#L199)).
+- Fields: `primary_file_only_default`, `preferred_ext`.
+- Invariants: default Civitai/HF provider configs are written by `StoreConfig.create_default`
+  ([models.py:257](../../src/store/models.py#L257)).
+- Used by: limited. NEEDS VERIFICATION: current resolver code mostly uses selector
+  constraints rather than provider defaults directly.
+- Persistence: config JSON.
+
+#### `CivitaiSelectorConfig`, `BaseModelAliasSelector`, `BaseModelAlias`
+
+- Purpose: configured aliases for base model hints
+  ([models.py:205](../../src/store/models.py#L205), [models.py:214](../../src/store/models.py#L214),
+  [models.py:220](../../src/store/models.py#L220)).
+- Fields: Civitai `model_id`, `version_id`, `file_id`; alias kind/default filename/selector.
+- Invariants: default aliases currently use placeholder zeros
+  ([models.py:274](../../src/store/models.py#L274)).
+- Used by: `_create_base_model_dependency`, `BaseModelHintResolver`
+  ([pack_service.py:603](../../src/store/pack_service.py#L603), [dependency_resolver.py:209](../../src/store/dependency_resolver.py#L209)).
+- Persistence: config JSON.
+- Design note: placeholder zero IDs are normal config data in main, while resolve
+  redesign validation rejects zero IDs ([resolve_validation.py branch:64]).
+
+#### `ConfigDefaults`, `BackupConfig`, `StoreConfig`
+
+- Purpose: global defaults, backup config, root persisted config
+  ([models.py:227](../../src/store/models.py#L227), [models.py:235](../../src/store/models.py#L235),
+  [models.py:243](../../src/store/models.py#L243)).
+- Fields: default UI set, conflict mode, active/use base defaults, backup path/options,
+  providers, base aliases.
+- Invariants: `schema_` aliases to JSON `schema`; layout writes with aliases
+  ([layout.py:322](../../src/store/layout.py#L322)).
+- Used by: Store facade defaults, runtime init, backup service, UI attach.
+- Persistence: `state/config.json`.
+- Design note: `defaults.active_profile` and `defaults.use_base` do not appear to be
+  authoritative for runtime, which is in `data/runtime.json`.
+
+#### `UISets`
+
+- Purpose: named sets of UI targets
+  ([models.py:314](../../src/store/models.py#L314)).
+- Fields: `schema`, `sets`.
+- Invariants: default sets include named and singleton sets
+  ([models.py:321](../../src/store/models.py#L321)).
+- Used by: Store facade `get_ui_targets`, profile service, view builder.
+- Persistence: `state/ui_sets.json`.
+- Design note: default UI set name lives in `StoreConfig.defaults.ui_set`, while set
+  members live in `UISets`. That split is acceptable but needs migration discipline.
+
+### Pack, Source, Dependencies
+
+#### `CivitaiSelector`
+
+- Purpose: Civitai dependency selector
+  ([models.py:350](../../src/store/models.py#L350)).
+- Fields: `model_id`, optional `version_id`, optional `file_id`.
+- Invariants: current main does not reject `0`; branch validation does.
+- Used by: dependency resolver, import, update, resolve branch.
+- Persistence: pack JSON.
+- Design note: Civitai model/version/file identity is spread across this selector,
+  `PackSource`, `ArtifactProvider`, `BlobOrigin`, and `ModelInfo.civitai_air`.
+
+#### `HuggingFaceSelector`
+
+- Purpose: HuggingFace file selector
+  ([models.py:359](../../src/store/models.py#L359)).
+- Fields: `repo_id`, `filename`, optional `revision`, optional `subfolder`.
+- Invariants: strategy should require repo and filename; not enforced in main.
+- Used by: `HuggingFaceResolver`
+  ([dependency_resolver.py:270](../../src/store/dependency_resolver.py#L270)).
+- Persistence: pack JSON.
+- Design note: HF path can be represented as `subfolder + filename`; lock stores
+  `repo_id`, `filename`, `revision`, but not `subfolder` in `ArtifactProvider`.
+
+#### `SelectorConstraints`
+
+- Purpose: file selection filters
+  ([models.py:367](../../src/store/models.py#L367)).
+- Fields: `primary_file_only`, `file_ext`, `base_model_hint`.
+- Invariants: resolver helper applies primary and extension filters
+  ([dependency_resolver.py:344](../../src/store/dependency_resolver.py#L344)).
+- Used by: Civitai latest/file and base model resolver path.
+- Persistence: pack JSON.
+- Design note: `base_model_hint` duplicates `Pack.base_model`, dependency `selector.base_model`,
+  and branch candidate `base_model`.
+
+#### `DependencySelector`
+
+- Purpose: strategy plus provider-specific selector payload
+  ([models.py:374](../../src/store/models.py#L374)).
+- Fields: `strategy`, optional `civitai`, `huggingface`, `base_model`, `url`,
+  `local_path`, `constraints`.
+- Invariants: no discriminator validation; impossible and incomplete states are allowed.
+- Used by: all dependency resolution and update paths.
+- Persistence: pack JSON.
+- Design note: branch adds `canonical_source` to this object
+  ([branch models.py:381](../../src/store/models.py#L381) via git show). That is a
+  good direction for local/URL deps with remote provenance, but it makes the selector
+  both "how to obtain" and "what this really is".
+
+#### `ExposeConfig`
+
+- Purpose: UI-facing filename and trigger words
+  ([models.py:395](../../src/store/models.py#L395)).
+- Fields: `filename`, `trigger_words`.
+- Invariants: filename cannot start with dot, include path separators, nulls, or `..`
+  ([models.py:108](../../src/store/models.py#L108)).
+- Used by: view paths, inventory display names, blob manifest original filename.
+- Persistence: pack JSON.
+- Design note: `filename` is part of view identity and conflict behavior; changing it
+  changes runtime exposed paths but not the blob.
+
+#### `PackDependency`
+
+- Purpose: one asset dependency inside a pack
+  ([models.py:406](../../src/store/models.py#L406)).
+- Fields: `id`, `kind`, `required`, `selector`, `update_policy`, `expose`, `description`.
+- Invariants: `id` safe-name validation; pack validates unique IDs
+  ([models.py:416](../../src/store/models.py#L416), [models.py:894](../../src/store/models.py#L894)).
+- Used by: import, resolve, install, update, view build, inventory.
+- Persistence: pack JSON.
+- Design note: `required` is ignored by `resolve_pack`, which records unresolved deps
+  without distinguishing required vs optional ([pack_service.py:1153](../../src/store/pack_service.py#L1153)).
+
+#### `PackSource`
+
+- Purpose: source information for the pack as a whole
+  ([models.py:422](../../src/store/models.py#L422)).
+- Fields: `provider`, optional Civitai `model_id`, optional `version_id`, optional `url`.
+- Invariants: required on every `Pack`.
+- Used by: search result/provider display, import/custom creation.
+- Persistence: pack JSON.
+- Design flaw: this is per-pack, but dependencies are per-artifact. A custom pack can
+  contain Civitai, HF, local, and URL dependencies simultaneously. `Pack.source` then
+  becomes either misleading or merely "creation source".
+
+#### `PackResources`
+
+- Purpose: keep-in-git flags for pack resources
+  ([models.py:432](../../src/store/models.py#L432)).
+- Fields: `previews_keep_in_git`, `workflows_keep_in_git`.
+- Used by: stored on `Pack`; NEEDS VERIFICATION for enforcement.
+- Persistence: pack JSON.
+- Design note: flags exist, but resource path conventions are split:
+  previews under `resources/previews`, workflows at `pack_dir/workflows`
+  ([layout.py:181](../../src/store/layout.py#L181)).
+
+#### `PackDependencyRef`
+
+- Purpose: pack-to-pack dependency edge
+  ([models.py:438](../../src/store/models.py#L438)).
+- Fields: `pack_name`, `required`, `version_constraint`.
+- Invariants: safe pack name; `Pack` validates unique names and no self-reference
+  ([models.py:902](../../src/store/models.py#L902)).
+- Used by: API CRUD/status/tree and reverse update impact
+  ([api.py:2963](../../src/store/api.py#L2963), [update_service.py:256](../../src/store/update_service.py#L256)).
+- Persistence: pack JSON.
+- Design flaw: view/profile composition ignores this field. `_load_packs_for_profile`
+  only loads direct `profile.packs` ([profile_service.py:473](../../src/store/profile_service.py#L473)).
+
+#### `GenerationParameters`
+
+- Purpose: generation settings from Civitai or AI
+  ([models.py:460](../../src/store/models.py#L460)).
+- Fields: sampler/scheduler/steps/cfg/size/seed/LoRA strength/hires fields plus extras.
+- Invariants: `extra="allow"` and custom serializer drops `None`
+  ([models.py:477](../../src/store/models.py#L477), [models.py:763](../../src/store/models.py#L763)).
+- Used by: Civitai import AI extraction
+  ([pack_service.py:536](../../src/store/pack_service.py#L536)).
+- Persistence: pack JSON.
+- Design note: this model has a lot of AI normalization logic inside the core domain
+  model. Consider moving normalization to an adapter and keeping the persisted model
+  simpler.
+
+#### `ModelInfo`
+
+- Purpose: extended model metadata
+  ([models.py:776](../../src/store/models.py#L776)).
+- Fields: model type/base model/trigger words/hash fields/AIR/stats/published/strength.
+- Used by: Civitai import metadata, UI details.
+- Persistence: pack JSON.
+- Design note: contains source evidence like hashes and Civitai AIR, overlapping
+  with lock provider/hash identity.
+
+#### `WorkflowInfo`
+
+- Purpose: metadata for included ComfyUI workflows
+  ([models.py:794](../../src/store/models.py#L794)).
+- Fields: `name`, `filename`, optional description/source URL, `is_default`.
+- Used by: pack JSON/UI workflow features.
+- Persistence: pack JSON, with workflow files under pack directories.
+- Design note: workflow JSON is not modeled as first-class content. There is no
+  dependency graph extracted from workflow nodes.
+
+#### `PreviewInfo`
+
+- Purpose: image/video preview metadata
+  ([models.py:803](../../src/store/models.py#L803)).
+- Fields: filename, URL, NSFW, dimensions, metadata dict, media type, video details.
+- Invariants: media type is `Literal['image','video','unknown']`
+  ([models.py:819](../../src/store/models.py#L819)).
+- Used by: import, gallery, resolve preview analysis.
+- Persistence: pack JSON plus files under resources/previews.
+- Design note: preview `meta` is raw `Dict[str, Any]`, which is flexible but hides
+  the evidence contract needed by resolve/workflow import.
+
+#### `Pack`
+
+- Purpose: central persisted pack document
+  ([models.py:837](../../src/store/models.py#L837)).
+- Fields: schema, name, pack type/category/source, dependencies, pack dependencies,
+  resources, previews, cover, version/description/base/author/tags/user tags/trigger
+  words, created timestamp, parameters, model info, workflows.
+- Invariants: safe name; unique dependency IDs; unique pack deps; no self pack dep.
+- Used by: almost every store service.
+- Persistence: `state/packs/<pack>/pack.json`.
+- Design flaw: `Pack` is simultaneously package metadata, model import metadata,
+  dependency manifest, gallery/workflow container, update policy holder, and future
+  installer descriptor. Extensions will add more unrelated optional fields unless
+  it is split into typed facets.
+
+### Lock And Resolution State
+
+#### `ArtifactProvider`
+
+- Purpose: provider information for resolved artifacts
+  ([models.py:924](../../src/store/models.py#L924)).
+- Fields: provider enum; Civitai IDs; HF repo/filename/revision.
+- Used by: lock, inventory origin, blob manifest origin.
+- Persistence: lock JSON.
+- Design note: missing `subfolder`, URL, local original path, and source URL details.
+
+#### `ArtifactDownload`
+
+- Purpose: download URLs for a resolved artifact
+  ([models.py:937](../../src/store/models.py#L937)).
+- Fields: `urls`.
+- Used by: `install_pack`, update pending downloads.
+- Persistence: lock JSON.
+- Design note: no auth requirement, expiry, mirror priority, method, headers, or source
+  evidence. Civitai signed URLs may age out NEEDS VERIFICATION.
+
+#### `ArtifactIntegrity`
+
+- Purpose: integrity verification status
+  ([models.py:942](../../src/store/models.py#L942)).
+- Fields: `sha256_verified`.
+- Used by: lock and install mutation.
+- Persistence: lock JSON.
+- Design note: hash itself lives on `ResolvedArtifact.sha256`; integrity only stores a
+  boolean. It cannot distinguish "provider hash trusted" from "download verified".
+
+#### `ResolvedArtifact`
+
+- Purpose: fully or partially resolved downloadable artifact
+  ([models.py:947](../../src/store/models.py#L947)).
+- Fields: kind, optional SHA256, size, provider, download, integrity.
+- Used by: lock, view build, install, inventory, update.
+- Persistence: lock JSON.
+- Design note: `sha256` can be absent for HF/URL until download; install mutates lock
+  after download when hash was unknown ([pack_service.py:1288](../../src/store/pack_service.py#L1288)).
+
+#### `ResolvedDependency`
+
+- Purpose: lock entry tying dependency ID to artifact
+  ([models.py:963](../../src/store/models.py#L963)).
+- Fields: `dependency_id`, `artifact`.
+- Invariants: no validation that `dependency_id` exists in pack JSON.
+- Used by: lock, view build, inventory, updates.
+- Persistence: lock JSON.
+
+#### `UnresolvedDependency`
+
+- Purpose: lock entry for failed resolution
+  ([models.py:969](../../src/store/models.py#L969)).
+- Fields: `dependency_id`, `reason`, `details`.
+- Used by: resolve/status.
+- Persistence: lock JSON.
+- Design note: does not carry required/optional severity, retry strategy, or candidate
+  evidence.
+
+#### `PackLock`
+
+- Purpose: resolved state for a pack
+  ([models.py:976](../../src/store/models.py#L976)).
+- Fields: schema, pack name, resolved timestamp, resolved and unresolved lists.
+- Invariants: `is_fully_resolved()` only checks no unresolved entries, not that every
+  pack dependency has a resolved entry ([models.py:993](../../src/store/models.py#L993)).
+- Used by: install, view build, inventory, update, status.
+- Persistence: `state/packs/<pack>/lock.json`.
+- Design flaw: no generation/source fingerprint. It does not record which `pack.json`
+  dependency definitions it was resolved against, so stale locks are hard to detect.
+
+### Profiles, Runtime, Reports
+
+#### `ProfilePackEntry`
+
+- Purpose: ordered pack entry in a profile
+  ([models.py:1002](../../src/store/models.py#L1002)).
+- Fields: `name`.
+- Invariants: safe name.
+- Used by: `Profile.packs`, work profile creation, view planning.
+- Persistence: profile JSON.
+- Design note: current model has no `enabled`, but CLI references `pack_entry.enabled`
+  ([cli.py:527](../../src/store/cli.py#L527)). That is a real drift/bug.
+
+#### `Profile`
+
+- Purpose: ordered collection of packs plus conflict config
+  ([models.py:1017](../../src/store/models.py#L1017)).
+- Fields: schema, name, conflicts, packs.
+- Invariants: safe name; `add_pack` deduplicates then appends
+  ([models.py:1031](../../src/store/models.py#L1031)).
+- Used by: global/work profiles, view build, runtime activation.
+- Persistence: profile JSON.
+- Design note: profile has no direct `pack_dependencies` field. Pack-to-pack dependencies
+  are not expanded here.
+
+#### `UIRuntimeState` and `Runtime`
+
+- Purpose: runtime profile stack per UI
+  ([models.py:1053](../../src/store/models.py#L1053), [models.py:1058](../../src/store/models.py#L1058)).
+- Fields: stack defaults to `["global"]`; runtime maps UI name to state.
+- Invariants: pop refuses to remove base stack item; set_stack can set any list.
+- Used by: `use`, `back`, status, profiles page.
+- Persistence: `data/runtime.json`.
+- Design note: runtime stores profile names without referential integrity. If a profile
+  is deleted, stack entries can point to missing profiles until commands handle it.
+
+#### `MissingBlob`, `UnresolvedReport`, `ShadowedEntry`, `StatusReport`
+
+- Purpose: status/diagnostic response models
+  ([models.py:1110](../../src/store/models.py#L1110), [models.py:1118](../../src/store/models.py#L1118),
+  [models.py:1126](../../src/store/models.py#L1126), [models.py:1134](../../src/store/models.py#L1134)).
+- Fields: pack/dependency/blob data, unresolved reason, shadowed winner/loser, active UI map.
+- Used by: Store status/doctor, profile use result, CLI/API.
+- Persistence: response only.
+- Design note: `Store.status()` always returns `shadowed=[]` even though `ViewBuilder`
+  computes shadowed entries ([__init__.py:951](../../src/store/__init__.py#L951)).
+
+#### Update, Doctor, Search, Use/Back/Reset/Delete Models
+
+- `UpdateChange`, `UpdateCandidate`, `AmbiguousUpdate`, `PendingDownload`, `UpdatePlan`,
+  `UpdateOptions`, `UpdateResult`, `BatchUpdateResult`
+  ([models.py:1144](../../src/store/models.py#L1144)).
+- Purpose: update planning/application DTOs.
+- Persistence: response only, except updates mutate lock/pack.
+- Design note: `UpdateCandidate.provider` is raw `str` while providers elsewhere use
+  `ProviderName` ([models.py:1155](../../src/store/models.py#L1155)).
+- `DoctorActions`, `DoctorReport`
+  ([models.py:1216](../../src/store/models.py#L1216)).
+- Purpose: diagnostic/repair response.
+- Design note: DB rebuild is explicitly placeholder in Store doctor
+  ([__init__.py:1030](../../src/store/__init__.py#L1030)).
+- `SearchResultItem`, `SearchResult`
+  ([models.py:1235](../../src/store/models.py#L1235)).
+- Purpose: search response.
+- `UseResult`, `BackResult`, `ResetResult`, `DeleteResult`
+  ([models.py:1253](../../src/store/models.py#L1253)).
+- Purpose: command response DTOs.
+- Design note: `UseResult.shadowed` is populated during `ProfileService.use`, but
+  general status loses it unless views are rebuilt ([profile_service.py:240](../../src/store/profile_service.py#L240)).
+
+### Inventory, Blob, Backup, Sync
+
+#### `BlobStatus`, `BlobLocation`
+
+- Purpose: inventory state enums
+  ([models.py:1296](../../src/store/models.py#L1296), [models.py:1304](../../src/store/models.py#L1304)).
+- Fields: referenced/orphan/missing/backup_only; local_only/backup_only/both/nowhere.
+- Used by: inventory, cleanup, impact analysis.
+- Persistence: response only.
+- Design note: `BlobStatus.BACKUP_ONLY` means referenced but not local in service code;
+  backup-only orphan is emitted as `ORPHAN` with `location=BACKUP_ONLY`
+  ([inventory_service.py:170](../../src/store/inventory_service.py#L170)).
+
+#### `BlobOrigin`, `PackReference`
+
+- Purpose: origin and pack reference metadata
+  ([models.py:1312](../../src/store/models.py#L1312), [models.py:1324](../../src/store/models.py#L1324)).
+- Fields: provider IDs/repo filename; pack/dependency/kind/expose/size/origin.
+- Used by: inventory and blob manifest creation.
+- Persistence: response only and embedded in `BlobManifest`.
+- Design note: mirrors `ArtifactProvider`; should probably be a shared canonical source
+  or derived view.
+
+#### `InventoryItem`, `BackupStats`, `InventorySummary`, `InventoryResponse`
+
+- Purpose: blob inventory response
+  ([models.py:1334](../../src/store/models.py#L1334), [models.py:1359](../../src/store/models.py#L1359),
+  [models.py:1375](../../src/store/models.py#L1375), [models.py:1391](../../src/store/models.py#L1391)).
+- Fields: hash/kind/display/size/location/status/refs/origin/active UIs/verification/summary.
+- Used by: inventory endpoints and cleanup.
+- Persistence: response only.
+- Design note: `active_in_uis` is always `[]` in service construction with TODO
+  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).
+
+#### `CleanupResult`, `MigrateManifestsResult`, `ImpactAnalysis`
+
+- Purpose: inventory mutation/impact responses
+  ([models.py:1398](../../src/store/models.py#L1398), [models.py:1408](../../src/store/models.py#L1408),
+  [models.py:1418](../../src/store/models.py#L1418)).
+- Used by: cleanup, manifest migration, delete guards.
+- Persistence: response only.
+
+#### `BlobManifest`
+
+- Purpose: write-once orphan metadata
+  ([models.py:1435](../../src/store/models.py#L1435)).
+- Fields: integer version, created timestamp, original filename, kind, origin.
+- Invariants: write-once; `BlobStore.write_manifest` never overwrites
+  ([blob_store.py:560](../../src/store/blob_store.py#L560)).
+- Used by: inventory display for orphan blobs, installation manifest creation.
+- Persistence: `data/blobs/sha256/<prefix>/<sha>.meta.json`.
+- Design note: "immutable" is enforced by write path, but no hash/source authority is
+  stored beyond filename/kind/origin.
+
+#### Backup And State Sync Models
+
+- `BackupStatus`, `BackupOperationResult`, `BackupDeleteResult`
+  ([models.py:1454](../../src/store/models.py#L1454)).
+- Purpose: backup connection and operation responses.
+- `SyncItem`, `SyncResult`
+  ([models.py:1489](../../src/store/models.py#L1489)).
+- Purpose: blob backup push/pull result; `direction` is raw string.
+- `StateSyncStatus`, `StateSyncItem`, `StateSyncSummary`, `StateSyncResult`
+  ([models.py:1517](../../src/store/models.py#L1517)).
+- Purpose: state directory backup sync model.
+- Design note: `StateSyncStatus.CONFLICT` exists but `_analyze_state_file` returns
+  `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
+
+#### `APIResponse`
+
+- Purpose: generic API wrapper
+  ([models.py:1561](../../src/store/models.py#L1561)).
+- Fields: `ok`, optional result/error.
+- Used by: API layer where adopted.
+- Persistence: response only.
+
+### Related Dataclasses Outside `models.py`
+
+#### `PreviewDownloadConfig`, `DownloadProgressInfo`
+
+- Purpose: pack import preview/download operation DTOs
+  ([pack_service.py:72](../../src/store/pack_service.py#L72), [pack_service.py:93](../../src/store/pack_service.py#L93)).
+- Design note: service-local Pydantic models with `Literal` status.
+
+#### `ViewEntry`, `ViewPlan`, `BuildReport`
+
+- Purpose: derived view plan/build report
+  ([view_builder.py:51](../../src/store/view_builder.py#L51)).
+- Fields: pack/dependency/kind/expose/hash/destination; shadowed and missing lists.
+- Persistence: not persisted, except symlink filesystem output.
+- Design note: this is where conflict resolution actually happens, not in `Profile`.
+
+#### `AttachResult`
+
+- Purpose: UI attach/detach result DTO
+  ([ui_attach.py:34](../../src/store/ui_attach.py#L34)).
+- Persistence: response only.
+- Design note: method is raw string.
+
+## 2. Enum Audit
+
+### `PackCategory`
+
+- Current values cover origin/editability in a coarse way.
+- `CUSTOM` can cover workflow-imported packs if workflow import is just user-owned
+  metadata plus dependencies.
+- A new `WORKFLOW` category is useful only if workflow packs have distinct lifecycle,
+  e.g. extracted graph, workflow JSON validation, dependency suggestion, and UI wizard
+  state.
+- `INSTALL` should not remain only a category once executable behavior is added.
+  It needs a typed install facet with trust, script manifest, environment state, logs,
+  process controls, and UI root outputs.
+- Recommendation: keep `PackCategory` small as origin/editability, add subtype/facet
+  models: `WorkflowFacet`, `InstallFacet`, possibly `ExternalSourceFacet`.
+
+### `AssetKind`
+
+- Missing or weakly wired: custom node folders, workflows, UI install environments,
+  extensions/plugins, configs.
+- `CUSTOM_NODE` exists but is not covered by `UIKindMap` and `_kind_to_comfyui_name`
+  ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+- `WORKFLOW` is not an asset kind; workflows are separate `WorkflowInfo`.
+- A pack can mix dependency kinds because `Pack.dependencies` is a list of per-dep
+  kinds, while `Pack.pack_type` is one top-level kind. This top-level `pack_type` is
+  therefore descriptive, not exhaustive.
+- Recommendation: rename or document `Pack.pack_type` as `primary_kind`, and add asset
+  kinds only for assets that become blobs/views. Keep workflows separate if they are
+  pack resources, not model files.
+
+### `ProviderName`
+
+- Current provider enum covers Civitai, HuggingFace, local, URL.
+- Future providers can be represented as `URL` only if update/canonical semantics are
+  intentionally lost.
+- Recommendation: use `ProviderName` for known provider integrations, but add
+  `ProviderName.UNKNOWN` or a `provider_id: str` plus typed payload union if plugins
+  can introduce providers.
+
+### `SelectorStrategy`, `UpdatePolicyMode`, `ConflictMode`
+
+- `SelectorStrategy` is fully registered in `PackService._ensure_resolvers`
+  ([pack_service.py:1193](../../src/store/pack_service.py#L1193)).
+- `UpdatePolicyMode` is wired for Civitai latest where provider registered
+  ([__init__.py:246](../../src/store/__init__.py#L246)).
+- `ConflictMode` is not fully wired. `ViewPlan.add_entry` implements last-wins only.
+- Recommendation: either remove `FIRST_WINS`/`STRICT` until implemented or make
+  `ViewBuilder.compute_plan` branch on `profile.conflicts.mode`.
+
+### String-Typed Enums Hiding In Models
+
+- `PreviewInfo.media_type` is `Literal['image','video','unknown']`
+  ([models.py:819](../../src/store/models.py#L819)).
+- `DownloadProgressInfo.status` is a `Literal`
+  ([pack_service.py:115](../../src/store/pack_service.py#L115)).
+- `SyncResult.direction` and `StateSyncResult.direction` are raw strings
+  ([models.py:1500](../../src/store/models.py#L1500), [models.py:1550](../../src/store/models.py#L1550)).
+- `AttachResult.method` is a raw string
+  ([ui_attach.py:39](../../src/store/ui_attach.py#L39)).
+- Recommendation: promote repeated public response literals to enums if clients depend
+  on them.
+
+## 3. Pack Shape Audit
+
+### Cohesion
+
+- `Pack` fields are not cohesive around one lifecycle.
+- External model import fields: `source`, `model_info`, `previews`, `base_model`,
+  provider tags, trigger words.
+- Custom pack fields: `user_tags`, editable description, custom dependencies, workflows.
+- Install pack future fields are absent despite `PackCategory.INSTALL`.
+- Workflow future fields are partial: workflow metadata exists, but not imported workflow
+  JSON as typed graph/source.
+
+### `Pack.source`
+
+- `Pack.source` is required and per-pack ([models.py:843](../../src/store/models.py#L843)).
+- For Civitai imports, it records model/version/url ([pack_service.py:514](../../src/store/pack_service.py#L514)).
+- For custom packs, API writes `provider=LOCAL` even when future dependencies may be
+  remote ([api.py:3314](../../src/store/api.py#L3314)).
+- Design recommendation: reinterpret as `creation_source` or remove as authoritative
+  source. Dependency source identity should live per dependency/candidate/lock.
+
+### `pack_dependencies`
+
+- Model validation prevents duplicate names and self-reference
+  ([models.py:902](../../src/store/models.py#L902)).
+- API can add/remove/status/tree pack dependencies
+  ([api.py:3036](../../src/store/api.py#L3036), [api.py:3170](../../src/store/api.py#L3170)).
+- Update service can find reverse dependency impact
+  ([update_service.py:256](../../src/store/update_service.py#L256)).
+- Profile/view runtime does not compose them
+  ([profile_service.py:483](../../src/store/profile_service.py#L483), [view_builder.py:236](../../src/store/view_builder.py#L236)).
+- `version_constraint` is stored but not enforced.
+- Recommendation: decide whether these are operational. If yes, add dependency expansion
+  service with cycle detection, optional/required policy, version checks, and stable
+  view order.
+
+### Pack vs Lock
+
+- Pack is desired state; lock is resolved artifact state.
+- Pack dependency selector can say "Civitai latest"; lock says exactly which version/file/hash.
+- Lock can be updated without pack selector changing (`UpdateService.apply_update`)
+  ([update_service.py:346](../../src/store/update_service.py#L346)).
+- Pack can be changed without lock changing in resolve redesign apply path
+  ([branch pack_service.py:1217](../../src/store/pack_service.py#L1217) via git show).
+- Recommendation: add a lock `pack_fingerprint` or per-dependency selector fingerprint
+  so stale locks are visible.
+
+### Hash Authority
+
+- SHA256 appears in `ModelInfo.hash_sha256`, `ResolvedArtifact.sha256`,
+  `PendingDownload.sha256`, `InventoryItem.sha256`, `BlobManifest` path, and physical
+  blob path.
+- The authoritative content address should be the blob path/hash and lock artifact hash.
+- `ModelInfo.hash_sha256` should be treated as provider metadata, not runtime authority.
+- Divergence paths:
+  - lock has hash but blob missing;
+  - HF/URL lock has no hash until install mutates it;
+  - manifest exists for old origin after pack dependency renamed;
+  - pack model info hash differs from resolved dependency hash.
+
+### Storage Separation
+
+- `pack.json`: user/provider metadata and desired dependencies.
+- `lock.json`: resolved artifacts and download URLs.
+- `BlobManifest`: orphan fallback display metadata.
+- This separation is conceptually good.
+- Missing piece: explicit derivation metadata tying lock and manifest back to pack
+  dependency version/fingerprint.
+
+## 4. Dependency Model Audit
+
+- `PackDependency` is desired dependency.
+- `PackDependencyRef` is pack-to-pack edge.
+- `ResolvedDependency` is lock result.
+- Branch `ResolutionCandidate` is suggestion DTO
+  ([branch resolve_models.py:77](../../src/store/models.py#L77) via git show).
+- Branch `CanonicalSource` is remote identity independent of install strategy
+  ([branch models.py:381](../../src/store/models.py#L381) via git show).
+
+Design overlaps:
+
+- `DependencySelector.civitai` and `CanonicalSource` both can carry Civitai model/version/file.
+- `HuggingFaceSelector` and `CanonicalSource` both can carry HF repo/path/revision.
+- `ArtifactProvider` and `BlobOrigin` repeat provider identity.
+- `PackSource` overlaps only for external single-source packs.
+
+Unresolved expression:
+
+- Main supports unresolved deps by leaving them in pack JSON and recording lock
+  `UnresolvedDependency`.
+- It does not need placeholders in normal selectors, but current defaults and branch
+  evidence providers do use `model_id=0` placeholders
+  ([models.py:280](../../src/store/models.py#L280), [branch evidence_providers.py:198] via git show).
+- Recommendation: introduce explicit "unresolved candidate" or "hint" objects instead
+  of invalid selectors.
+
+Identity stability:
+
+- `dep.id` is stable unless user edits it. Lock depends on this string.
+- No immutable dependency UUID exists.
+- Rename/edit can orphan lock entries or break update history.
+- Recommendation: add immutable `dependency_uid` or forbid ID rename after lock exists.
+
+Multi-source candidates:
+
+- Branch candidates can represent multiple candidates per dependency.
+- PackDependency stores only one selected selector.
+- There is no first-class "alternatives" field. That is probably correct for pack JSON;
+  alternatives belong in candidate cache or review state.
+
+Required/optional:
+
+- `PackDependency.required` exists.
+- `PackDependencyRef.required` exists.
+- Resolve/install/status do not deeply honor optional severity.
+- Recommendation: optional unresolved deps should not make `PackLock.is_fully_resolved`
+  false unless policy says so, or lock should expose `required_unresolved`.
+
+## 5. Source, Evidence, Candidate
+
+- Current main has no `CanonicalSource`; resolve branch adds it to `DependencySelector`.
+- Branch candidate shape has `selector_data`, `canonical_source`, evidence groups,
+  display fields, provider, and base model ([branch resolve_models.py:77] via git show).
+- Branch apply reconstructs selector from `candidate.selector_data` and passes candidate
+  `canonical_source` to pack service ([branch resolve_service.py:289] via git show).
+- Branch pack service writes selector/canonical source only to `pack.json` and explicitly
+  does not touch lock ([branch pack_service.py:1226] via git show).
+
+Canonical reference proposal:
+
+- For blob identity: SHA256.
+- For Civitai source: `model_id + version_id + file_id` where available, plus SHA256
+  after resolution/download.
+- For HuggingFace source: `repo_id + revision + subfolder + filename`, with SHA256 when
+  available.
+- For local source: blob SHA256 plus optional original path as non-authoritative evidence.
+- For URL source: URL plus resolved SHA256; URL alone is not stable.
+
+Recommendation:
+
+- Keep `DependencySelector` as "how to resolve/download now".
+- Add a separate per-dependency `canonical_source` field or nested `SourceIdentity`
+  next to selector, not inside strategy payload, unless local/URL tracking requires it.
+- Replace `PackSource` with `creation_source` or a `PackOrigin` object that does not
+  pretend to identify every dependency.
+
+## 6. Profile, Runtime, View
+
+- `Profile.packs` is the only profile composition list
+  ([models.py:1022](../../src/store/models.py#L1022)).
+- There is no `Profile.pack_dependencies`.
+- Work profiles are named `work__<pack>` ([profile_service.py:83](../../src/store/profile_service.py#L83)).
+- Work profile creation copies base packs except target, then appends target for
+  last-wins behavior ([profile_service.py:134](../../src/store/profile_service.py#L134)).
+- Work profiles are updated on reuse, but no general garbage collection is evident in
+  the audited service.
+- Runtime stack stores profile names per UI; `use()` pushes, `back()` pops
+  ([profile_service.py:248](../../src/store/profile_service.py#L248), [profile_service.py:303](../../src/store/profile_service.py#L303)).
+- If underlying profile is deleted, runtime can hold stale names. `back(sync=True)` catches
+  `ProfileNotFoundError`; other flows may silently fail or activate stale views.
+- `ShadowedEntry` is computed in `ViewPlan.add_entry`; `BuildReport` carries it; `UseResult`
+  receives it; `Store.status()` does not compute it and returns empty.
+
+Recommendation:
+
+- Add `ProfileEntry.enabled` only if view builder honors it.
+- Implement `ConflictMode` or collapse it.
+- Add a profile stack repair/validation command for deleted profiles.
+- Persist or recompute shadowed entries consistently. Since views are derived, recompute
+  from current profile/locks when status asks for shadowed, or store build reports.
+
+## 7. Inventory, Blob, Backup
+
+- Inventory is derived live from physical blobs, backup blobs, and pack locks
+  ([inventory_service.py:79](../../src/store/inventory_service.py#L79)).
+- Reference map scans all pack locks and maps hash to pack references
+  ([inventory_service.py:221](../../src/store/inventory_service.py#L221)).
+- Orphan display falls back to write-once blob manifest
+  ([inventory_service.py:340](../../src/store/inventory_service.py#L340)).
+- Active UI tracking is modeled but not implemented (`active_in_uis=[]`)
+  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).
+- Backup blob sync is explicitly one-way by raw `direction` string `to_backup` or
+  `from_backup` ([backup_service.py:597](../../src/store/backup_service.py#L597)).
+- State sync claims `bidirectional`, but conflict detection is weak: differing files
+  become `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
+
+Recommendation:
+
+- Treat inventory active UI as derived, not stored.
+- Model sync direction as enum.
+- Define backup as push/pull, not mirror, unless deletion propagation is implemented.
+- For state sync, either remove `CONFLICT` or implement a base/snapshot marker.
+
+## 8. Resolve Redesign Integration
+
+- Branch `ResolutionCandidate` fits as a transient DTO, not as persisted pack state.
+- Branch `CanonicalSource` should become the shared source identity primitive, but it
+  should be reconciled with `PackSource`, `ArtifactProvider`, and `BlobOrigin`.
+- Field naming mismatches:
+  - current `PackSource.provider: ProviderName`;
+  - branch `CanonicalSource.provider: Literal["civitai","huggingface"]`;
+  - update candidate `provider: str`;
+  - candidate `provider` literal.
+- Applying a candidate likely needs:
+  - per-dependency canonical source;
+  - dependency selector update;
+  - optional expose filename/trigger update policy;
+  - lock invalidation or lock update;
+  - candidate evidence audit trail only if product wants explainability.
+- Branch apply currently ignores `lock_entry` and does not update lock
+  ([branch pack_service.py:1222] via git show).
+
+Recommendation:
+
+- Decide now whether apply updates lock. If not, make stale lock an explicit state in UI.
+- Make all candidates either applyable selectors or non-applyable hints. No `model_id=0`.
+- Bind candidate cache to `pack_name` and `dep_id`.
+
+## 9. Custom, Install, Workflow Pack Futures
+
+Custom packs:
+
+- Current `Pack` can represent custom packs without dependencies if source is `LOCAL`
+  and dependencies default empty.
+- API create currently calls `store.layout.pack_path`, which does not exist; layout has
+  `pack_dir` ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
+- Custom packs with mixed sources are poorly represented by per-pack `source`.
+
+Install packs:
+
+- `PackCategory.INSTALL` exists but no domain model for scripts, install dir, UI root,
+  health, ports, logs, trust, or process state.
+- Recommended fields/facets:
+  - `install_manifest`: scripts with hash, interpreter, args, environment policy;
+  - `install_dir`: local path controlled by store;
+  - `ui_roots`: produced UI target roots;
+  - `log_paths`: stdout/stderr/install logs;
+  - `process`: pid/ports/health/restart policy;
+  - `trust`: signer/source/risk acknowledgement.
+
+Workflow packs:
+
+- Current `WorkflowInfo` can list files, but not model workflow JSON as parsed data.
+- Imported workflow JSON should live as a pack resource plus typed extracted metadata:
+  nodes, model references, custom node refs, missing deps, source file hash, and import
+  wizard decisions.
+- `PackCategory.WORKFLOW` is optional if `WorkflowFacet` exists. Without a facet, a new
+  category will become another weak flag.
+
+## 10. UI / Attach Model
+
+- `UIKindMap` covers many model kinds for ComfyUI/Forge/A1111/SD.Next defaults, but not
+  `custom_node`.
+- ComfyUI extra_model_paths generation maps only a subset of kinds
+  ([ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+- Generic symlink attach iterates `AssetKind` but skips any kind with no kind-map path
+  ([ui_attach.py:333](../../src/store/ui_attach.py#L333)).
+- `default_ui_set` authority is split: default name in `StoreConfig.defaults.ui_set`,
+  actual set in `UISets`.
+- UI roots are passed to `UIAttacher` from app config, not persisted in store config
+  ([ui_attach.py:53](../../src/store/ui_attach.py#L53)).
+- `extra_model_paths.yaml` schema is built ad hoc as nested dictionaries, not modeled
+  ([ui_attach.py:94](../../src/store/ui_attach.py#L94)).
+
+Recommendation:
+
+- Add explicit UI attach config model: UI name, root, attach method, supported kind map.
+- Add ComfyUI YAML model if the app will edit and preserve user YAML repeatedly.
+- Decide whether custom nodes are install-pack assets rather than model blobs.
+
+## 11. Cross-Cutting Concerns
+
+Schema versioning:
+
+- Schema strings exist in file models, but load paths call direct `model_validate`
+  without migration dispatch ([layout.py:427](../../src/store/layout.py#L427)).
+- Recommendation: add `load_pack_document`/`migrate_pack` helpers and fail clearly on
+  unsupported future schemas.
+
+Pydantic:
+
+- Uses Pydantic v2 APIs (`field_validator`, `model_validator`, `model_serializer`).
+- No frozen models. Mutable lists are normal. This is convenient but makes accidental
+  in-place mutation common.
+- Recommendation: keep persisted models mutable for service ergonomics, but add command
+  methods for high-risk mutations or central write services.
+
+Validation:
+
+- Safe names prevent path separators and traversal, but dependency selectors are not
+  discriminated.
+- Recommendation: use discriminated unions for selector payloads:
+  `CivitaiFileSelector`, `HuggingFaceFileSelector`, `LocalFileSelector`, etc.
+
+Naming:
+
+- `pack`, `pack_name`, `name`, `pack_type`, `pack_category` are mostly consistent.
+- `pack_type` is misleading because pack can mix asset kinds. Prefer `primary_kind`.
+
+Serialization:
+
+- Aliased schema fields use `populate_by_name=True` and `by_alias=True` when layout
+  writes top-level models.
+- `GenerationParameters` custom serializer drops `None` and preserves extras.
+- NEEDS VERIFICATION: all API responses using `model_dump()` rather than
+  `model_dump(by_alias=True)` may expose `schema_` instead of `schema`.
+
+## 12. Observed Bugs / Smells
+
+1. `ProfilePackEntry.enabled` drift: model has no `enabled`, CLI accesses it
+   ([models.py:1002](../../src/store/models.py#L1002), [cli.py:527](../../src/store/cli.py#L527)).
+2. `Profile.conflicts.mode` ignored: view builder implements only last-wins
+   ([models.py:1012](../../src/store/models.py#L1012), [view_builder.py:91](../../src/store/view_builder.py#L91)).
+3. `StatusReport.shadowed` always empty in Store status
+   ([__init__.py:951](../../src/store/__init__.py#L951)).
+4. Placeholder Civitai IDs exist in default config
+   ([models.py:280](../../src/store/models.py#L280)).
+5. Resolve branch also emits placeholder `model_id=0` candidates in filename fallback
+   ([branch evidence_providers.py:198] via git show).
+6. `StoreLayout.pack_path()` does not exist, but API create pack calls it
+   ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
+7. `custom_node` asset kind is not attachable through current kind maps
+   ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+8. `version_constraint` on `PackDependencyRef` is stored but not enforced
+   ([models.py:452](../../src/store/models.py#L452)).
+9. `PackDependency.required` and `PackDependencyRef.required` are not reflected in
+   lock completeness or runtime composition.
+10. `StateSyncStatus.CONFLICT` is modeled but not produced by current comparison.
+11. `ArtifactProvider` lacks HF `subfolder`, while `HuggingFaceSelector` has it.
+12. `BlobStatus.BACKUP_ONLY` semantics are narrower than the enum name implies.
+
+## 13. Design Recommendations
+
+### Split `Pack`
+
+Keep:
+
+- `PackCore`: schema, name, category/origin, primary kind, version, description, tags.
+- `DependencyManifest`: model dependencies and pack dependencies.
+- `MediaFacet`: previews, cover, resources.
+- `GenerationFacet`: parameters/model info.
+- `WorkflowFacet`: workflow resources and extracted dependency hints.
+- `InstallFacet`: script/process/UI install metadata.
+
+### Merge Source Identity
+
+- Introduce one source identity model, likely evolved from branch `CanonicalSource`.
+- Use it in dependency desired state, lock provider/origin derivation, and blob manifest.
+- Keep provider-specific selector as an acquisition strategy.
+
+### Type-Narrow Selectors
+
+- Replace optional-field `DependencySelector` with a discriminated union.
+- Benefits: no invalid local selector without path, no Civitai strategy without Civitai
+  payload, no zero-ID placeholders.
+
+### Make Locks Staleness-Aware
+
+- Add lock-level `pack_fingerprint`.
+- Add per-resolved-entry `dependency_fingerprint`.
+- Show stale lock state in status and resolve UI.
+
+### Decide Operational Semantics For Pack Dependencies
+
+- If operational: expand required pack deps when building profiles/views.
+- If informational: rename to `related_packs` or `recommended_packs`.
+- Enforce `version_constraint` or remove it.
+
+### Wire Or Remove Modeled Fields
+
+- Implement `ConflictMode`.
+- Implement active UI inventory tracking or drop it from response.
+- Implement state sync conflicts or remove `CONFLICT`.
+- Add `ProfilePackEntry.enabled` intentionally or remove stale callers.
+
+### Schema Migration
+
+- Add migration helpers per persisted document.
+- Use schema version dispatch before Pydantic validation.
+- Keep migration tests with old fixture JSON.
+
+## 14. Open Questions For Owner
+
+1. Should `pack_dependencies` affect runtime composition, or are they advisory metadata?
+2. Should `apply_resolution()` update `lock.json`, invalidate it, or leave stale state
+   until explicit resolve?
+3. Is `Pack.source` meant to mean "creation source" or "all pack content source"?
+4. Do workflow imports deserve `PackCategory.WORKFLOW`, or should they be `CUSTOM` with
+   a workflow facet?
+5. Are install packs trusted first-party objects only, or can users import arbitrary
+   install packs?
+6. Should custom packs be backend-updatable when their dependencies use `FOLLOW_LATEST`?
+7. Should optional dependencies affect `PackLock.is_fully_resolved()`?
+8. Should dependency IDs be user-editable after a lock exists?
+9. Is ComfyUI custom node management part of store assets, install packs, or a separate
+   extension manager?
+10. Should backup state sync be push/pull only, or a true bidirectional merge with
+    conflict resolution?
+11. Should UI roots be persisted in store config or remain application config?
+12. What is the migration policy for existing `synapse.pack.v2` files once canonical
+    source lands?
+

codex
Wrote the audit to [plans/audits/codex-domain-audit.md](/home/box/git/github/synapse/plans/audits/codex-domain-audit.md).

It is 1,095 lines and includes file:line refs, branch comparison for `feat/resolve-model-redesign`, `NEEDS VERIFICATION` marks, model inventory, enum audit, pack/dependency/source/profile/blob/UI findings, concrete refactor recommendations, and owner questions.

No tests were run; this was a read/design audit plus markdown file creation.
diff --git a/plans/audits/codex-domain-audit.md b/plans/audits/codex-domain-audit.md
new file mode 100644
index 0000000000000000000000000000000000000000..025f1f027c7782c98a603092a31822a5327609c4
--- /dev/null
+++ b/plans/audits/codex-domain-audit.md
@@ -0,0 +1,1095 @@
+# Synapse v2 Store Domain Model Audit
+
+Date: 2026-05-02
+
+Scope:
+
+- Primary model file: `src/store/models.py`.
+- Related domain/service files: `layout.py`, `__init__.py`, `pack_service.py`,
+  `profile_service.py`, `view_builder.py`, `dependency_resolver.py`,
+  `inventory_service.py`, `backup_service.py`, `update_service.py`,
+  `blob_store.py`, `ui_attach.py`.
+- Roadmap context: `plans/audits/CONSOLIDATED-FINDINGS.md`.
+- Resolve redesign comparison: `feat/resolve-model-redesign:src/store/resolve_models.py`
+  and touched model/write-path shape from that branch.
+
+## Executive Summary
+
+1. The domain model is usable today, but it is carrying several future-facing concepts
+   as partially-wired fields: `pack_dependencies`, `ConflictMode`, install packs,
+   custom nodes, workflows, backup state sync, and active UI inventory.
+2. `Pack` is doing too much: provider origin, dependency manifest, gallery metadata,
+   generation metadata, workflow metadata, editability, update behavior, and future
+   install-pack behavior are all on one object.
+3. Source identity is the biggest foundation risk. There are at least five identity
+   surfaces: `Pack.source`, `DependencySelector`, branch `CanonicalSource`,
+   `ResolvedArtifact.provider`, and `BlobManifest.origin`.
+4. Lock semantics are underspecified. The lock is the only place with resolved hashes
+   and download URLs, but update/apply/installation can mutate lock and blob state
+   independently. Divergence is normal, not exceptional.
+5. `pack_dependencies` is modeled as operational but profile/view composition ignores
+   it. API endpoints can create and show a dependency tree, while `use()` and `sync()`
+   do not recursively include those dependent packs.
+6. `AssetKind.CUSTOM_NODE` exists but is not mapped through `UIKindMap`, ComfyUI YAML
+   generation, or attach symlinks. This is a future workflow/custom-node blocker.
+7. Current `ProfilePackEntry` does not have `enabled`, despite CLI code referencing it.
+   This is model/API drift, not merely an ignored flag.
+8. Schema version strings exist in top-level persisted models, but there is no migration
+   runner, version dispatch, or compatibility policy in layout load paths.
+
+## Persistence Map
+
+- `state/config.json`: `StoreConfig` with `schema=synapse.config.v2`
+  ([models.py:243](../../src/store/models.py#L243), [layout.py:388](../../src/store/layout.py#L388)).
+- `state/ui_sets.json`: `UISets` with `schema=synapse.ui_sets.v1`
+  ([models.py:314](../../src/store/models.py#L314), [layout.py:399](../../src/store/layout.py#L399)).
+- `state/packs/<pack>/pack.json`: `Pack` with `schema=synapse.pack.v2`
+  ([models.py:837](../../src/store/models.py#L837), [layout.py:427](../../src/store/layout.py#L427)).
+- `state/packs/<pack>/lock.json`: `PackLock` with `schema=synapse.lock.v2`
+  ([models.py:976](../../src/store/models.py#L976), [layout.py:441](../../src/store/layout.py#L441)).
+- `state/profiles/<profile>/profile.json`: `Profile` with `schema=synapse.profile.v1`
+  ([models.py:1017](../../src/store/models.py#L1017), [layout.py:480](../../src/store/layout.py#L480)).
+- `data/runtime.json`: `Runtime` with `schema=synapse.runtime.v1`
+  ([models.py:1058](../../src/store/models.py#L1058), [layout.py:508](../../src/store/layout.py#L508)).
+- `data/blobs/sha256/<prefix>/<sha>`: content-addressed blobs
+  ([blob_store.py:88](../../src/store/blob_store.py#L88), [layout.py:229](../../src/store/layout.py#L229)).
+- `data/blobs/sha256/<prefix>/<sha>.meta.json`: `BlobManifest`
+  ([models.py:1435](../../src/store/models.py#L1435), [blob_store.py:533](../../src/store/blob_store.py#L533)).
+- `data/views/<ui>/profiles/<profile>` and `data/views/<ui>/active`: derived view state
+  ([layout.py:209](../../src/store/layout.py#L209), [view_builder.py:375](../../src/store/view_builder.py#L375)).
+- `data/.synapse.lock`: global file lock
+  ([layout.py:160](../../src/store/layout.py#L160), [layout.py:248](../../src/store/layout.py#L248)).
+
+## 1. Inventory Of Domain Objects
+
+### Config And UI Sets
+
+#### `AssetKind`
+
+- Purpose: vocabulary of assets Synapse can expose to UIs
+  ([models.py:31](../../src/store/models.py#L31)).
+- Fields/values: `checkpoint`, `lora`, `vae`, `controlnet`, `upscaler`, `clip`,
+  `text_encoder`, `diffusion_model`, `embedding`, `custom_node`, `unet`, `unknown`
+  ([models.py:33](../../src/store/models.py#L33)).
+- Invariants: enum values are used as serialized strings; no versioning or aliasing.
+- Used by: `Pack.pack_type`, `PackDependency.kind`, `ResolvedArtifact.kind`,
+  inventory, view planning, UI attach mapping.
+- Persistence: pack JSON, lock JSON, blob manifest, inventory/API responses.
+- Design note: `CUSTOM_NODE` is in the enum but missing from `UIKindMap` fields and
+  ComfyUI extra path mapping, so it is not fully operational.
+
+#### `ProviderName`
+
+- Purpose: supported provider identity enum
+  ([models.py:47](../../src/store/models.py#L47)).
+- Fields/values: `civitai`, `huggingface`, `local`, `url`.
+- Invariants: used in Pydantic provider/source models; no `unknown` provider.
+- Used by: `PackSource`, `ArtifactProvider`, `BlobOrigin`, update fallback.
+- Persistence: pack JSON, lock JSON, blob manifest, inventory.
+- Design note: fine for current providers, brittle for AI-discovered/community providers
+  unless the system accepts schema churn for every new provider.
+
+#### `SelectorStrategy`
+
+- Purpose: resolution strategy for a dependency
+  ([models.py:55](../../src/store/models.py#L55)).
+- Fields/values: `civitai_file`, `civitai_model_latest`, `huggingface_file`,
+  `base_model_hint`, `local_file`, `url_download`.
+- Invariants: strategy should imply which selector payload field is populated, but this
+  is not enforced by a discriminated union.
+- Used by: dependency resolvers, update providers, resolve redesign branch.
+- Persistence: pack JSON.
+- Design note: current model permits invalid combinations like `strategy=local_file`
+  with `civitai` data and no `local_path`.
+
+#### `UpdatePolicyMode` and `UpdatePolicy`
+
+- Purpose: choose whether a dependency is fixed or update-following
+  ([models.py:65](../../src/store/models.py#L65), [models.py:385](../../src/store/models.py#L385)).
+- Fields: `mode` defaults to `pinned`.
+- Invariants: `follow_latest` is considered updatable only when a provider is registered
+  for the dependency strategy ([update_service.py:107](../../src/store/update_service.py#L107)).
+- Used by: `UpdateService.plan_update`, `UpdateService.is_updatable`.
+- Persistence: pack JSON.
+- Design note: update behavior is dependency-level, not pack-level. A custom pack with
+  a `follow_latest` Civitai dependency is backend-updatable even if UI considers custom
+  packs non-updatable.
+
+#### `ConflictMode` and `ConflictConfig`
+
+- Purpose: profile conflict policy
+  ([models.py:71](../../src/store/models.py#L71), [models.py:1012](../../src/store/models.py#L1012)).
+- Fields/values: `last_wins`, `first_wins`, `strict`; profile default `last_wins`.
+- Invariants: only `last_wins` is implemented in `ViewPlan.add_entry`, which replaces
+  existing entries with later packs ([view_builder.py:91](../../src/store/view_builder.py#L91)).
+- Used by: stored on `Profile`, copied into work profiles
+  ([profile_service.py:128](../../src/store/profile_service.py#L128)).
+- Persistence: profile JSON.
+- Design note: `FIRST_WINS` and `STRICT` are modeled but ignored by view planning.
+
+#### `PackCategory`
+
+- Purpose: pack origin/editability class
+  ([models.py:78](../../src/store/models.py#L78)).
+- Fields/values: `external`, `custom`, `install`.
+- Invariants: comments imply editability and installation semantics, but services do
+  not enforce most of that.
+- Used by: imported Civitai packs are `external` ([pack_service.py:510](../../src/store/pack_service.py#L510));
+  API-created custom packs are `custom` ([api.py:3310](../../src/store/api.py#L3310)).
+- Persistence: pack JSON.
+- Design note: `INSTALL` is not just a category. It implies scripts, process lifecycle,
+  UI roots, trust, logs, and health state. It should probably be a subtype object.
+
+#### `UIKindMap`
+
+- Purpose: maps asset kinds to UI-specific model folders
+  ([models.py:121](../../src/store/models.py#L121)).
+- Fields: `checkpoint`, `lora`, `vae`, `embedding`, `controlnet`, `upscaler`,
+  `clip`, `text_encoder`, `diffusion_model`, `unet`.
+- Invariants: `get_path()` maps by `AssetKind.value`
+  ([models.py:134](../../src/store/models.py#L134)).
+- Used by: `ViewBuilder.compute_plan`, `UIAttacher`, default UI config.
+- Persistence: config JSON.
+- Design note: missing `custom_node` and `unknown`. ViewBuilder falls back to
+  `models/<kind>`, but `UIAttacher` skips unmapped kinds, so attach is inconsistent
+  ([view_builder.py:85](../../src/store/view_builder.py#L85), [ui_attach.py:333](../../src/store/ui_attach.py#L333)).
+
+#### `UIConfig`
+
+- Purpose: known UI names and per-UI kind maps
+  ([models.py:139](../../src/store/models.py#L139)).
+- Fields: `known`, `kind_map`.
+- Invariants: default known UIs are `comfyui`, `forge`, `a1111`, `sdnext`.
+- Used by: `StoreConfig`, runtime initialization, view planning, attach.
+- Persistence: config JSON.
+- Design note: UI roots live outside this model in app config passed to UIAttacher,
+  producing a split between store state and application config.
+
+#### `ProviderConfig`
+
+- Purpose: provider defaults for file selection
+  ([models.py:199](../../src/store/models.py#L199)).
+- Fields: `primary_file_only_default`, `preferred_ext`.
+- Invariants: default Civitai/HF provider configs are written by `StoreConfig.create_default`
+  ([models.py:257](../../src/store/models.py#L257)).
+- Used by: limited. NEEDS VERIFICATION: current resolver code mostly uses selector
+  constraints rather than provider defaults directly.
+- Persistence: config JSON.
+
+#### `CivitaiSelectorConfig`, `BaseModelAliasSelector`, `BaseModelAlias`
+
+- Purpose: configured aliases for base model hints
+  ([models.py:205](../../src/store/models.py#L205), [models.py:214](../../src/store/models.py#L214),
+  [models.py:220](../../src/store/models.py#L220)).
+- Fields: Civitai `model_id`, `version_id`, `file_id`; alias kind/default filename/selector.
+- Invariants: default aliases currently use placeholder zeros
+  ([models.py:274](../../src/store/models.py#L274)).
+- Used by: `_create_base_model_dependency`, `BaseModelHintResolver`
+  ([pack_service.py:603](../../src/store/pack_service.py#L603), [dependency_resolver.py:209](../../src/store/dependency_resolver.py#L209)).
+- Persistence: config JSON.
+- Design note: placeholder zero IDs are normal config data in main, while resolve
+  redesign validation rejects zero IDs ([resolve_validation.py branch:64]).
+
+#### `ConfigDefaults`, `BackupConfig`, `StoreConfig`
+
+- Purpose: global defaults, backup config, root persisted config
+  ([models.py:227](../../src/store/models.py#L227), [models.py:235](../../src/store/models.py#L235),
+  [models.py:243](../../src/store/models.py#L243)).
+- Fields: default UI set, conflict mode, active/use base defaults, backup path/options,
+  providers, base aliases.
+- Invariants: `schema_` aliases to JSON `schema`; layout writes with aliases
+  ([layout.py:322](../../src/store/layout.py#L322)).
+- Used by: Store facade defaults, runtime init, backup service, UI attach.
+- Persistence: `state/config.json`.
+- Design note: `defaults.active_profile` and `defaults.use_base` do not appear to be
+  authoritative for runtime, which is in `data/runtime.json`.
+
+#### `UISets`
+
+- Purpose: named sets of UI targets
+  ([models.py:314](../../src/store/models.py#L314)).
+- Fields: `schema`, `sets`.
+- Invariants: default sets include named and singleton sets
+  ([models.py:321](../../src/store/models.py#L321)).
+- Used by: Store facade `get_ui_targets`, profile service, view builder.
+- Persistence: `state/ui_sets.json`.
+- Design note: default UI set name lives in `StoreConfig.defaults.ui_set`, while set
+  members live in `UISets`. That split is acceptable but needs migration discipline.
+
+### Pack, Source, Dependencies
+
+#### `CivitaiSelector`
+
+- Purpose: Civitai dependency selector
+  ([models.py:350](../../src/store/models.py#L350)).
+- Fields: `model_id`, optional `version_id`, optional `file_id`.
+- Invariants: current main does not reject `0`; branch validation does.
+- Used by: dependency resolver, import, update, resolve branch.
+- Persistence: pack JSON.
+- Design note: Civitai model/version/file identity is spread across this selector,
+  `PackSource`, `ArtifactProvider`, `BlobOrigin`, and `ModelInfo.civitai_air`.
+
+#### `HuggingFaceSelector`
+
+- Purpose: HuggingFace file selector
+  ([models.py:359](../../src/store/models.py#L359)).
+- Fields: `repo_id`, `filename`, optional `revision`, optional `subfolder`.
+- Invariants: strategy should require repo and filename; not enforced in main.
+- Used by: `HuggingFaceResolver`
+  ([dependency_resolver.py:270](../../src/store/dependency_resolver.py#L270)).
+- Persistence: pack JSON.
+- Design note: HF path can be represented as `subfolder + filename`; lock stores
+  `repo_id`, `filename`, `revision`, but not `subfolder` in `ArtifactProvider`.
+
+#### `SelectorConstraints`
+
+- Purpose: file selection filters
+  ([models.py:367](../../src/store/models.py#L367)).
+- Fields: `primary_file_only`, `file_ext`, `base_model_hint`.
+- Invariants: resolver helper applies primary and extension filters
+  ([dependency_resolver.py:344](../../src/store/dependency_resolver.py#L344)).
+- Used by: Civitai latest/file and base model resolver path.
+- Persistence: pack JSON.
+- Design note: `base_model_hint` duplicates `Pack.base_model`, dependency `selector.base_model`,
+  and branch candidate `base_model`.
+
+#### `DependencySelector`
+
+- Purpose: strategy plus provider-specific selector payload
+  ([models.py:374](../../src/store/models.py#L374)).
+- Fields: `strategy`, optional `civitai`, `huggingface`, `base_model`, `url`,
+  `local_path`, `constraints`.
+- Invariants: no discriminator validation; impossible and incomplete states are allowed.
+- Used by: all dependency resolution and update paths.
+- Persistence: pack JSON.
+- Design note: branch adds `canonical_source` to this object
+  ([branch models.py:381](../../src/store/models.py#L381) via git show). That is a
+  good direction for local/URL deps with remote provenance, but it makes the selector
+  both "how to obtain" and "what this really is".
+
+#### `ExposeConfig`
+
+- Purpose: UI-facing filename and trigger words
+  ([models.py:395](../../src/store/models.py#L395)).
+- Fields: `filename`, `trigger_words`.
+- Invariants: filename cannot start with dot, include path separators, nulls, or `..`
+  ([models.py:108](../../src/store/models.py#L108)).
+- Used by: view paths, inventory display names, blob manifest original filename.
+- Persistence: pack JSON.
+- Design note: `filename` is part of view identity and conflict behavior; changing it
+  changes runtime exposed paths but not the blob.
+
+#### `PackDependency`
+
+- Purpose: one asset dependency inside a pack
+  ([models.py:406](../../src/store/models.py#L406)).
+- Fields: `id`, `kind`, `required`, `selector`, `update_policy`, `expose`, `description`.
+- Invariants: `id` safe-name validation; pack validates unique IDs
+  ([models.py:416](../../src/store/models.py#L416), [models.py:894](../../src/store/models.py#L894)).
+- Used by: import, resolve, install, update, view build, inventory.
+- Persistence: pack JSON.
+- Design note: `required` is ignored by `resolve_pack`, which records unresolved deps
+  without distinguishing required vs optional ([pack_service.py:1153](../../src/store/pack_service.py#L1153)).
+
+#### `PackSource`
+
+- Purpose: source information for the pack as a whole
+  ([models.py:422](../../src/store/models.py#L422)).
+- Fields: `provider`, optional Civitai `model_id`, optional `version_id`, optional `url`.
+- Invariants: required on every `Pack`.
+- Used by: search result/provider display, import/custom creation.
+- Persistence: pack JSON.
+- Design flaw: this is per-pack, but dependencies are per-artifact. A custom pack can
+  contain Civitai, HF, local, and URL dependencies simultaneously. `Pack.source` then
+  becomes either misleading or merely "creation source".
+
+#### `PackResources`
+
+- Purpose: keep-in-git flags for pack resources
+  ([models.py:432](../../src/store/models.py#L432)).
+- Fields: `previews_keep_in_git`, `workflows_keep_in_git`.
+- Used by: stored on `Pack`; NEEDS VERIFICATION for enforcement.
+- Persistence: pack JSON.
+- Design note: flags exist, but resource path conventions are split:
+  previews under `resources/previews`, workflows at `pack_dir/workflows`
+  ([layout.py:181](../../src/store/layout.py#L181)).
+
+#### `PackDependencyRef`
+
+- Purpose: pack-to-pack dependency edge
+  ([models.py:438](../../src/store/models.py#L438)).
+- Fields: `pack_name`, `required`, `version_constraint`.
+- Invariants: safe pack name; `Pack` validates unique names and no self-reference
+  ([models.py:902](../../src/store/models.py#L902)).
+- Used by: API CRUD/status/tree and reverse update impact
+  ([api.py:2963](../../src/store/api.py#L2963), [update_service.py:256](../../src/store/update_service.py#L256)).
+- Persistence: pack JSON.
+- Design flaw: view/profile composition ignores this field. `_load_packs_for_profile`
+  only loads direct `profile.packs` ([profile_service.py:473](../../src/store/profile_service.py#L473)).
+
+#### `GenerationParameters`
+
+- Purpose: generation settings from Civitai or AI
+  ([models.py:460](../../src/store/models.py#L460)).
+- Fields: sampler/scheduler/steps/cfg/size/seed/LoRA strength/hires fields plus extras.
+- Invariants: `extra="allow"` and custom serializer drops `None`
+  ([models.py:477](../../src/store/models.py#L477), [models.py:763](../../src/store/models.py#L763)).
+- Used by: Civitai import AI extraction
+  ([pack_service.py:536](../../src/store/pack_service.py#L536)).
+- Persistence: pack JSON.
+- Design note: this model has a lot of AI normalization logic inside the core domain
+  model. Consider moving normalization to an adapter and keeping the persisted model
+  simpler.
+
+#### `ModelInfo`
+
+- Purpose: extended model metadata
+  ([models.py:776](../../src/store/models.py#L776)).
+- Fields: model type/base model/trigger words/hash fields/AIR/stats/published/strength.
+- Used by: Civitai import metadata, UI details.
+- Persistence: pack JSON.
+- Design note: contains source evidence like hashes and Civitai AIR, overlapping
+  with lock provider/hash identity.
+
+#### `WorkflowInfo`
+
+- Purpose: metadata for included ComfyUI workflows
+  ([models.py:794](../../src/store/models.py#L794)).
+- Fields: `name`, `filename`, optional description/source URL, `is_default`.
+- Used by: pack JSON/UI workflow features.
+- Persistence: pack JSON, with workflow files under pack directories.
+- Design note: workflow JSON is not modeled as first-class content. There is no
+  dependency graph extracted from workflow nodes.
+
+#### `PreviewInfo`
+
+- Purpose: image/video preview metadata
+  ([models.py:803](../../src/store/models.py#L803)).
+- Fields: filename, URL, NSFW, dimensions, metadata dict, media type, video details.
+- Invariants: media type is `Literal['image','video','unknown']`
+  ([models.py:819](../../src/store/models.py#L819)).
+- Used by: import, gallery, resolve preview analysis.
+- Persistence: pack JSON plus files under resources/previews.
+- Design note: preview `meta` is raw `Dict[str, Any]`, which is flexible but hides
+  the evidence contract needed by resolve/workflow import.
+
+#### `Pack`
+
+- Purpose: central persisted pack document
+  ([models.py:837](../../src/store/models.py#L837)).
+- Fields: schema, name, pack type/category/source, dependencies, pack dependencies,
+  resources, previews, cover, version/description/base/author/tags/user tags/trigger
+  words, created timestamp, parameters, model info, workflows.
+- Invariants: safe name; unique dependency IDs; unique pack deps; no self pack dep.
+- Used by: almost every store service.
+- Persistence: `state/packs/<pack>/pack.json`.
+- Design flaw: `Pack` is simultaneously package metadata, model import metadata,
+  dependency manifest, gallery/workflow container, update policy holder, and future
+  installer descriptor. Extensions will add more unrelated optional fields unless
+  it is split into typed facets.
+
+### Lock And Resolution State
+
+#### `ArtifactProvider`
+
+- Purpose: provider information for resolved artifacts
+  ([models.py:924](../../src/store/models.py#L924)).
+- Fields: provider enum; Civitai IDs; HF repo/filename/revision.
+- Used by: lock, inventory origin, blob manifest origin.
+- Persistence: lock JSON.
+- Design note: missing `subfolder`, URL, local original path, and source URL details.
+
+#### `ArtifactDownload`
+
+- Purpose: download URLs for a resolved artifact
+  ([models.py:937](../../src/store/models.py#L937)).
+- Fields: `urls`.
+- Used by: `install_pack`, update pending downloads.
+- Persistence: lock JSON.
+- Design note: no auth requirement, expiry, mirror priority, method, headers, or source
+  evidence. Civitai signed URLs may age out NEEDS VERIFICATION.
+
+#### `ArtifactIntegrity`
+
+- Purpose: integrity verification status
+  ([models.py:942](../../src/store/models.py#L942)).
+- Fields: `sha256_verified`.
+- Used by: lock and install mutation.
+- Persistence: lock JSON.
+- Design note: hash itself lives on `ResolvedArtifact.sha256`; integrity only stores a
+  boolean. It cannot distinguish "provider hash trusted" from "download verified".
+
+#### `ResolvedArtifact`
+
+- Purpose: fully or partially resolved downloadable artifact
+  ([models.py:947](../../src/store/models.py#L947)).
+- Fields: kind, optional SHA256, size, provider, download, integrity.
+- Used by: lock, view build, install, inventory, update.
+- Persistence: lock JSON.
+- Design note: `sha256` can be absent for HF/URL until download; install mutates lock
+  after download when hash was unknown ([pack_service.py:1288](../../src/store/pack_service.py#L1288)).
+
+#### `ResolvedDependency`
+
+- Purpose: lock entry tying dependency ID to artifact
+  ([models.py:963](../../src/store/models.py#L963)).
+- Fields: `dependency_id`, `artifact`.
+- Invariants: no validation that `dependency_id` exists in pack JSON.
+- Used by: lock, view build, inventory, updates.
+- Persistence: lock JSON.
+
+#### `UnresolvedDependency`
+
+- Purpose: lock entry for failed resolution
+  ([models.py:969](../../src/store/models.py#L969)).
+- Fields: `dependency_id`, `reason`, `details`.
+- Used by: resolve/status.
+- Persistence: lock JSON.
+- Design note: does not carry required/optional severity, retry strategy, or candidate
+  evidence.
+
+#### `PackLock`
+
+- Purpose: resolved state for a pack
+  ([models.py:976](../../src/store/models.py#L976)).
+- Fields: schema, pack name, resolved timestamp, resolved and unresolved lists.
+- Invariants: `is_fully_resolved()` only checks no unresolved entries, not that every
+  pack dependency has a resolved entry ([models.py:993](../../src/store/models.py#L993)).
+- Used by: install, view build, inventory, update, status.
+- Persistence: `state/packs/<pack>/lock.json`.
+- Design flaw: no generation/source fingerprint. It does not record which `pack.json`
+  dependency definitions it was resolved against, so stale locks are hard to detect.
+
+### Profiles, Runtime, Reports
+
+#### `ProfilePackEntry`
+
+- Purpose: ordered pack entry in a profile
+  ([models.py:1002](../../src/store/models.py#L1002)).
+- Fields: `name`.
+- Invariants: safe name.
+- Used by: `Profile.packs`, work profile creation, view planning.
+- Persistence: profile JSON.
+- Design note: current model has no `enabled`, but CLI references `pack_entry.enabled`
+  ([cli.py:527](../../src/store/cli.py#L527)). That is a real drift/bug.
+
+#### `Profile`
+
+- Purpose: ordered collection of packs plus conflict config
+  ([models.py:1017](../../src/store/models.py#L1017)).
+- Fields: schema, name, conflicts, packs.
+- Invariants: safe name; `add_pack` deduplicates then appends
+  ([models.py:1031](../../src/store/models.py#L1031)).
+- Used by: global/work profiles, view build, runtime activation.
+- Persistence: profile JSON.
+- Design note: profile has no direct `pack_dependencies` field. Pack-to-pack dependencies
+  are not expanded here.
+
+#### `UIRuntimeState` and `Runtime`
+
+- Purpose: runtime profile stack per UI
+  ([models.py:1053](../../src/store/models.py#L1053), [models.py:1058](../../src/store/models.py#L1058)).
+- Fields: stack defaults to `["global"]`; runtime maps UI name to state.
+- Invariants: pop refuses to remove base stack item; set_stack can set any list.
+- Used by: `use`, `back`, status, profiles page.
+- Persistence: `data/runtime.json`.
+- Design note: runtime stores profile names without referential integrity. If a profile
+  is deleted, stack entries can point to missing profiles until commands handle it.
+
+#### `MissingBlob`, `UnresolvedReport`, `ShadowedEntry`, `StatusReport`
+
+- Purpose: status/diagnostic response models
+  ([models.py:1110](../../src/store/models.py#L1110), [models.py:1118](../../src/store/models.py#L1118),
+  [models.py:1126](../../src/store/models.py#L1126), [models.py:1134](../../src/store/models.py#L1134)).
+- Fields: pack/dependency/blob data, unresolved reason, shadowed winner/loser, active UI map.
+- Used by: Store status/doctor, profile use result, CLI/API.
+- Persistence: response only.
+- Design note: `Store.status()` always returns `shadowed=[]` even though `ViewBuilder`
+  computes shadowed entries ([__init__.py:951](../../src/store/__init__.py#L951)).
+
+#### Update, Doctor, Search, Use/Back/Reset/Delete Models
+
+- `UpdateChange`, `UpdateCandidate`, `AmbiguousUpdate`, `PendingDownload`, `UpdatePlan`,
+  `UpdateOptions`, `UpdateResult`, `BatchUpdateResult`
+  ([models.py:1144](../../src/store/models.py#L1144)).
+- Purpose: update planning/application DTOs.
+- Persistence: response only, except updates mutate lock/pack.
+- Design note: `UpdateCandidate.provider` is raw `str` while providers elsewhere use
+  `ProviderName` ([models.py:1155](../../src/store/models.py#L1155)).
+- `DoctorActions`, `DoctorReport`
+  ([models.py:1216](../../src/store/models.py#L1216)).
+- Purpose: diagnostic/repair response.
+- Design note: DB rebuild is explicitly placeholder in Store doctor
+  ([__init__.py:1030](../../src/store/__init__.py#L1030)).
+- `SearchResultItem`, `SearchResult`
+  ([models.py:1235](../../src/store/models.py#L1235)).
+- Purpose: search response.
+- `UseResult`, `BackResult`, `ResetResult`, `DeleteResult`
+  ([models.py:1253](../../src/store/models.py#L1253)).
+- Purpose: command response DTOs.
+- Design note: `UseResult.shadowed` is populated during `ProfileService.use`, but
+  general status loses it unless views are rebuilt ([profile_service.py:240](../../src/store/profile_service.py#L240)).
+
+### Inventory, Blob, Backup, Sync
+
+#### `BlobStatus`, `BlobLocation`
+
+- Purpose: inventory state enums
+  ([models.py:1296](../../src/store/models.py#L1296), [models.py:1304](../../src/store/models.py#L1304)).
+- Fields: referenced/orphan/missing/backup_only; local_only/backup_only/both/nowhere.
+- Used by: inventory, cleanup, impact analysis.
+- Persistence: response only.
+- Design note: `BlobStatus.BACKUP_ONLY` means referenced but not local in service code;
+  backup-only orphan is emitted as `ORPHAN` with `location=BACKUP_ONLY`
+  ([inventory_service.py:170](../../src/store/inventory_service.py#L170)).
+
+#### `BlobOrigin`, `PackReference`
+
+- Purpose: origin and pack reference metadata
+  ([models.py:1312](../../src/store/models.py#L1312), [models.py:1324](../../src/store/models.py#L1324)).
+- Fields: provider IDs/repo filename; pack/dependency/kind/expose/size/origin.
+- Used by: inventory and blob manifest creation.
+- Persistence: response only and embedded in `BlobManifest`.
+- Design note: mirrors `ArtifactProvider`; should probably be a shared canonical source
+  or derived view.
+
+#### `InventoryItem`, `BackupStats`, `InventorySummary`, `InventoryResponse`
+
+- Purpose: blob inventory response
+  ([models.py:1334](../../src/store/models.py#L1334), [models.py:1359](../../src/store/models.py#L1359),
+  [models.py:1375](../../src/store/models.py#L1375), [models.py:1391](../../src/store/models.py#L1391)).
+- Fields: hash/kind/display/size/location/status/refs/origin/active UIs/verification/summary.
+- Used by: inventory endpoints and cleanup.
+- Persistence: response only.
+- Design note: `active_in_uis` is always `[]` in service construction with TODO
+  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).
+
+#### `CleanupResult`, `MigrateManifestsResult`, `ImpactAnalysis`
+
+- Purpose: inventory mutation/impact responses
+  ([models.py:1398](../../src/store/models.py#L1398), [models.py:1408](../../src/store/models.py#L1408),
+  [models.py:1418](../../src/store/models.py#L1418)).
+- Used by: cleanup, manifest migration, delete guards.
+- Persistence: response only.
+
+#### `BlobManifest`
+
+- Purpose: write-once orphan metadata
+  ([models.py:1435](../../src/store/models.py#L1435)).
+- Fields: integer version, created timestamp, original filename, kind, origin.
+- Invariants: write-once; `BlobStore.write_manifest` never overwrites
+  ([blob_store.py:560](../../src/store/blob_store.py#L560)).
+- Used by: inventory display for orphan blobs, installation manifest creation.
+- Persistence: `data/blobs/sha256/<prefix>/<sha>.meta.json`.
+- Design note: "immutable" is enforced by write path, but no hash/source authority is
+  stored beyond filename/kind/origin.
+
+#### Backup And State Sync Models
+
+- `BackupStatus`, `BackupOperationResult`, `BackupDeleteResult`
+  ([models.py:1454](../../src/store/models.py#L1454)).
+- Purpose: backup connection and operation responses.
+- `SyncItem`, `SyncResult`
+  ([models.py:1489](../../src/store/models.py#L1489)).
+- Purpose: blob backup push/pull result; `direction` is raw string.
+- `StateSyncStatus`, `StateSyncItem`, `StateSyncSummary`, `StateSyncResult`
+  ([models.py:1517](../../src/store/models.py#L1517)).
+- Purpose: state directory backup sync model.
+- Design note: `StateSyncStatus.CONFLICT` exists but `_analyze_state_file` returns
+  `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
+
+#### `APIResponse`
+
+- Purpose: generic API wrapper
+  ([models.py:1561](../../src/store/models.py#L1561)).
+- Fields: `ok`, optional result/error.
+- Used by: API layer where adopted.
+- Persistence: response only.
+
+### Related Dataclasses Outside `models.py`
+
+#### `PreviewDownloadConfig`, `DownloadProgressInfo`
+
+- Purpose: pack import preview/download operation DTOs
+  ([pack_service.py:72](../../src/store/pack_service.py#L72), [pack_service.py:93](../../src/store/pack_service.py#L93)).
+- Design note: service-local Pydantic models with `Literal` status.
+
+#### `ViewEntry`, `ViewPlan`, `BuildReport`
+
+- Purpose: derived view plan/build report
+  ([view_builder.py:51](../../src/store/view_builder.py#L51)).
+- Fields: pack/dependency/kind/expose/hash/destination; shadowed and missing lists.
+- Persistence: not persisted, except symlink filesystem output.
+- Design note: this is where conflict resolution actually happens, not in `Profile`.
+
+#### `AttachResult`
+
+- Purpose: UI attach/detach result DTO
+  ([ui_attach.py:34](../../src/store/ui_attach.py#L34)).
+- Persistence: response only.
+- Design note: method is raw string.
+
+## 2. Enum Audit
+
+### `PackCategory`
+
+- Current values cover origin/editability in a coarse way.
+- `CUSTOM` can cover workflow-imported packs if workflow import is just user-owned
+  metadata plus dependencies.
+- A new `WORKFLOW` category is useful only if workflow packs have distinct lifecycle,
+  e.g. extracted graph, workflow JSON validation, dependency suggestion, and UI wizard
+  state.
+- `INSTALL` should not remain only a category once executable behavior is added.
+  It needs a typed install facet with trust, script manifest, environment state, logs,
+  process controls, and UI root outputs.
+- Recommendation: keep `PackCategory` small as origin/editability, add subtype/facet
+  models: `WorkflowFacet`, `InstallFacet`, possibly `ExternalSourceFacet`.
+
+### `AssetKind`
+
+- Missing or weakly wired: custom node folders, workflows, UI install environments,
+  extensions/plugins, configs.
+- `CUSTOM_NODE` exists but is not covered by `UIKindMap` and `_kind_to_comfyui_name`
+  ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+- `WORKFLOW` is not an asset kind; workflows are separate `WorkflowInfo`.
+- A pack can mix dependency kinds because `Pack.dependencies` is a list of per-dep
+  kinds, while `Pack.pack_type` is one top-level kind. This top-level `pack_type` is
+  therefore descriptive, not exhaustive.
+- Recommendation: rename or document `Pack.pack_type` as `primary_kind`, and add asset
+  kinds only for assets that become blobs/views. Keep workflows separate if they are
+  pack resources, not model files.
+
+### `ProviderName`
+
+- Current provider enum covers Civitai, HuggingFace, local, URL.
+- Future providers can be represented as `URL` only if update/canonical semantics are
+  intentionally lost.
+- Recommendation: use `ProviderName` for known provider integrations, but add
+  `ProviderName.UNKNOWN` or a `provider_id: str` plus typed payload union if plugins
+  can introduce providers.
+
+### `SelectorStrategy`, `UpdatePolicyMode`, `ConflictMode`
+
+- `SelectorStrategy` is fully registered in `PackService._ensure_resolvers`
+  ([pack_service.py:1193](../../src/store/pack_service.py#L1193)).
+- `UpdatePolicyMode` is wired for Civitai latest where provider registered
+  ([__init__.py:246](../../src/store/__init__.py#L246)).
+- `ConflictMode` is not fully wired. `ViewPlan.add_entry` implements last-wins only.
+- Recommendation: either remove `FIRST_WINS`/`STRICT` until implemented or make
+  `ViewBuilder.compute_plan` branch on `profile.conflicts.mode`.
+
+### String-Typed Enums Hiding In Models
+
+- `PreviewInfo.media_type` is `Literal['image','video','unknown']`
+  ([models.py:819](../../src/store/models.py#L819)).
+- `DownloadProgressInfo.status` is a `Literal`
+  ([pack_service.py:115](../../src/store/pack_service.py#L115)).
+- `SyncResult.direction` and `StateSyncResult.direction` are raw strings
+  ([models.py:1500](../../src/store/models.py#L1500), [models.py:1550](../../src/store/models.py#L1550)).
+- `AttachResult.method` is a raw string
+  ([ui_attach.py:39](../../src/store/ui_attach.py#L39)).
+- Recommendation: promote repeated public response literals to enums if clients depend
+  on them.
+
+## 3. Pack Shape Audit
+
+### Cohesion
+
+- `Pack` fields are not cohesive around one lifecycle.
+- External model import fields: `source`, `model_info`, `previews`, `base_model`,
+  provider tags, trigger words.
+- Custom pack fields: `user_tags`, editable description, custom dependencies, workflows.
+- Install pack future fields are absent despite `PackCategory.INSTALL`.
+- Workflow future fields are partial: workflow metadata exists, but not imported workflow
+  JSON as typed graph/source.
+
+### `Pack.source`
+
+- `Pack.source` is required and per-pack ([models.py:843](../../src/store/models.py#L843)).
+- For Civitai imports, it records model/version/url ([pack_service.py:514](../../src/store/pack_service.py#L514)).
+- For custom packs, API writes `provider=LOCAL` even when future dependencies may be
+  remote ([api.py:3314](../../src/store/api.py#L3314)).
+- Design recommendation: reinterpret as `creation_source` or remove as authoritative
+  source. Dependency source identity should live per dependency/candidate/lock.
+
+### `pack_dependencies`
+
+- Model validation prevents duplicate names and self-reference
+  ([models.py:902](../../src/store/models.py#L902)).
+- API can add/remove/status/tree pack dependencies
+  ([api.py:3036](../../src/store/api.py#L3036), [api.py:3170](../../src/store/api.py#L3170)).
+- Update service can find reverse dependency impact
+  ([update_service.py:256](../../src/store/update_service.py#L256)).
+- Profile/view runtime does not compose them
+  ([profile_service.py:483](../../src/store/profile_service.py#L483), [view_builder.py:236](../../src/store/view_builder.py#L236)).
+- `version_constraint` is stored but not enforced.
+- Recommendation: decide whether these are operational. If yes, add dependency expansion
+  service with cycle detection, optional/required policy, version checks, and stable
+  view order.
+
+### Pack vs Lock
+
+- Pack is desired state; lock is resolved artifact state.
+- Pack dependency selector can say "Civitai latest"; lock says exactly which version/file/hash.
+- Lock can be updated without pack selector changing (`UpdateService.apply_update`)
+  ([update_service.py:346](../../src/store/update_service.py#L346)).
+- Pack can be changed without lock changing in resolve redesign apply path
+  ([branch pack_service.py:1217](../../src/store/pack_service.py#L1217) via git show).
+- Recommendation: add a lock `pack_fingerprint` or per-dependency selector fingerprint
+  so stale locks are visible.
+
+### Hash Authority
+
+- SHA256 appears in `ModelInfo.hash_sha256`, `ResolvedArtifact.sha256`,
+  `PendingDownload.sha256`, `InventoryItem.sha256`, `BlobManifest` path, and physical
+  blob path.
+- The authoritative content address should be the blob path/hash and lock artifact hash.
+- `ModelInfo.hash_sha256` should be treated as provider metadata, not runtime authority.
+- Divergence paths:
+  - lock has hash but blob missing;
+  - HF/URL lock has no hash until install mutates it;
+  - manifest exists for old origin after pack dependency renamed;
+  - pack model info hash differs from resolved dependency hash.
+
+### Storage Separation
+
+- `pack.json`: user/provider metadata and desired dependencies.
+- `lock.json`: resolved artifacts and download URLs.
+- `BlobManifest`: orphan fallback display metadata.
+- This separation is conceptually good.
+- Missing piece: explicit derivation metadata tying lock and manifest back to pack
+  dependency version/fingerprint.
+
+## 4. Dependency Model Audit
+
+- `PackDependency` is desired dependency.
+- `PackDependencyRef` is pack-to-pack edge.
+- `ResolvedDependency` is lock result.
+- Branch `ResolutionCandidate` is suggestion DTO
+  ([branch resolve_models.py:77](../../src/store/models.py#L77) via git show).
+- Branch `CanonicalSource` is remote identity independent of install strategy
+  ([branch models.py:381](../../src/store/models.py#L381) via git show).
+
+Design overlaps:
+
+- `DependencySelector.civitai` and `CanonicalSource` both can carry Civitai model/version/file.
+- `HuggingFaceSelector` and `CanonicalSource` both can carry HF repo/path/revision.
+- `ArtifactProvider` and `BlobOrigin` repeat provider identity.
+- `PackSource` overlaps only for external single-source packs.
+
+Unresolved expression:
+
+- Main supports unresolved deps by leaving them in pack JSON and recording lock
+  `UnresolvedDependency`.
+- It does not need placeholders in normal selectors, but current defaults and branch
+  evidence providers do use `model_id=0` placeholders
+  ([models.py:280](../../src/store/models.py#L280), [branch evidence_providers.py:198] via git show).
+- Recommendation: introduce explicit "unresolved candidate" or "hint" objects instead
+  of invalid selectors.
+
+Identity stability:
+
+- `dep.id` is stable unless user edits it. Lock depends on this string.
+- No immutable dependency UUID exists.
+- Rename/edit can orphan lock entries or break update history.
+- Recommendation: add immutable `dependency_uid` or forbid ID rename after lock exists.
+
+Multi-source candidates:
+
+- Branch candidates can represent multiple candidates per dependency.
+- PackDependency stores only one selected selector.
+- There is no first-class "alternatives" field. That is probably correct for pack JSON;
+  alternatives belong in candidate cache or review state.
+
+Required/optional:
+
+- `PackDependency.required` exists.
+- `PackDependencyRef.required` exists.
+- Resolve/install/status do not deeply honor optional severity.
+- Recommendation: optional unresolved deps should not make `PackLock.is_fully_resolved`
+  false unless policy says so, or lock should expose `required_unresolved`.
+
+## 5. Source, Evidence, Candidate
+
+- Current main has no `CanonicalSource`; resolve branch adds it to `DependencySelector`.
+- Branch candidate shape has `selector_data`, `canonical_source`, evidence groups,
+  display fields, provider, and base model ([branch resolve_models.py:77] via git show).
+- Branch apply reconstructs selector from `candidate.selector_data` and passes candidate
+  `canonical_source` to pack service ([branch resolve_service.py:289] via git show).
+- Branch pack service writes selector/canonical source only to `pack.json` and explicitly
+  does not touch lock ([branch pack_service.py:1226] via git show).
+
+Canonical reference proposal:
+
+- For blob identity: SHA256.
+- For Civitai source: `model_id + version_id + file_id` where available, plus SHA256
+  after resolution/download.
+- For HuggingFace source: `repo_id + revision + subfolder + filename`, with SHA256 when
+  available.
+- For local source: blob SHA256 plus optional original path as non-authoritative evidence.
+- For URL source: URL plus resolved SHA256; URL alone is not stable.
+
+Recommendation:
+
+- Keep `DependencySelector` as "how to resolve/download now".
+- Add a separate per-dependency `canonical_source` field or nested `SourceIdentity`
+  next to selector, not inside strategy payload, unless local/URL tracking requires it.
+- Replace `PackSource` with `creation_source` or a `PackOrigin` object that does not
+  pretend to identify every dependency.
+
+## 6. Profile, Runtime, View
+
+- `Profile.packs` is the only profile composition list
+  ([models.py:1022](../../src/store/models.py#L1022)).
+- There is no `Profile.pack_dependencies`.
+- Work profiles are named `work__<pack>` ([profile_service.py:83](../../src/store/profile_service.py#L83)).
+- Work profile creation copies base packs except target, then appends target for
+  last-wins behavior ([profile_service.py:134](../../src/store/profile_service.py#L134)).
+- Work profiles are updated on reuse, but no general garbage collection is evident in
+  the audited service.
+- Runtime stack stores profile names per UI; `use()` pushes, `back()` pops
+  ([profile_service.py:248](../../src/store/profile_service.py#L248), [profile_service.py:303](../../src/store/profile_service.py#L303)).
+- If underlying profile is deleted, runtime can hold stale names. `back(sync=True)` catches
+  `ProfileNotFoundError`; other flows may silently fail or activate stale views.
+- `ShadowedEntry` is computed in `ViewPlan.add_entry`; `BuildReport` carries it; `UseResult`
+  receives it; `Store.status()` does not compute it and returns empty.
+
+Recommendation:
+
+- Add `ProfileEntry.enabled` only if view builder honors it.
+- Implement `ConflictMode` or collapse it.
+- Add a profile stack repair/validation command for deleted profiles.
+- Persist or recompute shadowed entries consistently. Since views are derived, recompute
+  from current profile/locks when status asks for shadowed, or store build reports.
+
+## 7. Inventory, Blob, Backup
+
+- Inventory is derived live from physical blobs, backup blobs, and pack locks
+  ([inventory_service.py:79](../../src/store/inventory_service.py#L79)).
+- Reference map scans all pack locks and maps hash to pack references
+  ([inventory_service.py:221](../../src/store/inventory_service.py#L221)).
+- Orphan display falls back to write-once blob manifest
+  ([inventory_service.py:340](../../src/store/inventory_service.py#L340)).
+- Active UI tracking is modeled but not implemented (`active_in_uis=[]`)
+  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).
+- Backup blob sync is explicitly one-way by raw `direction` string `to_backup` or
+  `from_backup` ([backup_service.py:597](../../src/store/backup_service.py#L597)).
+- State sync claims `bidirectional`, but conflict detection is weak: differing files
+  become `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).
+
+Recommendation:
+
+- Treat inventory active UI as derived, not stored.
+- Model sync direction as enum.
+- Define backup as push/pull, not mirror, unless deletion propagation is implemented.
+- For state sync, either remove `CONFLICT` or implement a base/snapshot marker.
+
+## 8. Resolve Redesign Integration
+
+- Branch `ResolutionCandidate` fits as a transient DTO, not as persisted pack state.
+- Branch `CanonicalSource` should become the shared source identity primitive, but it
+  should be reconciled with `PackSource`, `ArtifactProvider`, and `BlobOrigin`.
+- Field naming mismatches:
+  - current `PackSource.provider: ProviderName`;
+  - branch `CanonicalSource.provider: Literal["civitai","huggingface"]`;
+  - update candidate `provider: str`;
+  - candidate `provider` literal.
+- Applying a candidate likely needs:
+  - per-dependency canonical source;
+  - dependency selector update;
+  - optional expose filename/trigger update policy;
+  - lock invalidation or lock update;
+  - candidate evidence audit trail only if product wants explainability.
+- Branch apply currently ignores `lock_entry` and does not update lock
+  ([branch pack_service.py:1222] via git show).
+
+Recommendation:
+
+- Decide now whether apply updates lock. If not, make stale lock an explicit state in UI.
+- Make all candidates either applyable selectors or non-applyable hints. No `model_id=0`.
+- Bind candidate cache to `pack_name` and `dep_id`.
+
+## 9. Custom, Install, Workflow Pack Futures
+
+Custom packs:
+
+- Current `Pack` can represent custom packs without dependencies if source is `LOCAL`
+  and dependencies default empty.
+- API create currently calls `store.layout.pack_path`, which does not exist; layout has
+  `pack_dir` ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
+- Custom packs with mixed sources are poorly represented by per-pack `source`.
+
+Install packs:
+
+- `PackCategory.INSTALL` exists but no domain model for scripts, install dir, UI root,
+  health, ports, logs, trust, or process state.
+- Recommended fields/facets:
+  - `install_manifest`: scripts with hash, interpreter, args, environment policy;
+  - `install_dir`: local path controlled by store;
+  - `ui_roots`: produced UI target roots;
+  - `log_paths`: stdout/stderr/install logs;
+  - `process`: pid/ports/health/restart policy;
+  - `trust`: signer/source/risk acknowledgement.
+
+Workflow packs:
+
+- Current `WorkflowInfo` can list files, but not model workflow JSON as parsed data.
+- Imported workflow JSON should live as a pack resource plus typed extracted metadata:
+  nodes, model references, custom node refs, missing deps, source file hash, and import
+  wizard decisions.
+- `PackCategory.WORKFLOW` is optional if `WorkflowFacet` exists. Without a facet, a new
+  category will become another weak flag.
+
+## 10. UI / Attach Model
+
+- `UIKindMap` covers many model kinds for ComfyUI/Forge/A1111/SD.Next defaults, but not
+  `custom_node`.
+- ComfyUI extra_model_paths generation maps only a subset of kinds
+  ([ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+- Generic symlink attach iterates `AssetKind` but skips any kind with no kind-map path
+  ([ui_attach.py:333](../../src/store/ui_attach.py#L333)).
+- `default_ui_set` authority is split: default name in `StoreConfig.defaults.ui_set`,
+  actual set in `UISets`.
+- UI roots are passed to `UIAttacher` from app config, not persisted in store config
+  ([ui_attach.py:53](../../src/store/ui_attach.py#L53)).
+- `extra_model_paths.yaml` schema is built ad hoc as nested dictionaries, not modeled
+  ([ui_attach.py:94](../../src/store/ui_attach.py#L94)).
+
+Recommendation:
+
+- Add explicit UI attach config model: UI name, root, attach method, supported kind map.
+- Add ComfyUI YAML model if the app will edit and preserve user YAML repeatedly.
+- Decide whether custom nodes are install-pack assets rather than model blobs.
+
+## 11. Cross-Cutting Concerns
+
+Schema versioning:
+
+- Schema strings exist in file models, but load paths call direct `model_validate`
+  without migration dispatch ([layout.py:427](../../src/store/layout.py#L427)).
+- Recommendation: add `load_pack_document`/`migrate_pack` helpers and fail clearly on
+  unsupported future schemas.
+
+Pydantic:
+
+- Uses Pydantic v2 APIs (`field_validator`, `model_validator`, `model_serializer`).
+- No frozen models. Mutable lists are normal. This is convenient but makes accidental
+  in-place mutation common.
+- Recommendation: keep persisted models mutable for service ergonomics, but add command
+  methods for high-risk mutations or central write services.
+
+Validation:
+
+- Safe names prevent path separators and traversal, but dependency selectors are not
+  discriminated.
+- Recommendation: use discriminated unions for selector payloads:
+  `CivitaiFileSelector`, `HuggingFaceFileSelector`, `LocalFileSelector`, etc.
+
+Naming:
+
+- `pack`, `pack_name`, `name`, `pack_type`, `pack_category` are mostly consistent.
+- `pack_type` is misleading because pack can mix asset kinds. Prefer `primary_kind`.
+
+Serialization:
+
+- Aliased schema fields use `populate_by_name=True` and `by_alias=True` when layout
+  writes top-level models.
+- `GenerationParameters` custom serializer drops `None` and preserves extras.
+- NEEDS VERIFICATION: all API responses using `model_dump()` rather than
+  `model_dump(by_alias=True)` may expose `schema_` instead of `schema`.
+
+## 12. Observed Bugs / Smells
+
+1. `ProfilePackEntry.enabled` drift: model has no `enabled`, CLI accesses it
+   ([models.py:1002](../../src/store/models.py#L1002), [cli.py:527](../../src/store/cli.py#L527)).
+2. `Profile.conflicts.mode` ignored: view builder implements only last-wins
+   ([models.py:1012](../../src/store/models.py#L1012), [view_builder.py:91](../../src/store/view_builder.py#L91)).
+3. `StatusReport.shadowed` always empty in Store status
+   ([__init__.py:951](../../src/store/__init__.py#L951)).
+4. Placeholder Civitai IDs exist in default config
+   ([models.py:280](../../src/store/models.py#L280)).
+5. Resolve branch also emits placeholder `model_id=0` candidates in filename fallback
+   ([branch evidence_providers.py:198] via git show).
+6. `StoreLayout.pack_path()` does not exist, but API create pack calls it
+   ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
+7. `custom_node` asset kind is not attachable through current kind maps
+   ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
+8. `version_constraint` on `PackDependencyRef` is stored but not enforced
+   ([models.py:452](../../src/store/models.py#L452)).
+9. `PackDependency.required` and `PackDependencyRef.required` are not reflected in
+   lock completeness or runtime composition.
+10. `StateSyncStatus.CONFLICT` is modeled but not produced by current comparison.
+11. `ArtifactProvider` lacks HF `subfolder`, while `HuggingFaceSelector` has it.
+12. `BlobStatus.BACKUP_ONLY` semantics are narrower than the enum name implies.
+
+## 13. Design Recommendations
+
+### Split `Pack`
+
+Keep:
+
+- `PackCore`: schema, name, category/origin, primary kind, version, description, tags.
+- `DependencyManifest`: model dependencies and pack dependencies.
+- `MediaFacet`: previews, cover, resources.
+- `GenerationFacet`: parameters/model info.
+- `WorkflowFacet`: workflow resources and extracted dependency hints.
+- `InstallFacet`: script/process/UI install metadata.
+
+### Merge Source Identity
+
+- Introduce one source identity model, likely evolved from branch `CanonicalSource`.
+- Use it in dependency desired state, lock provider/origin derivation, and blob manifest.
+- Keep provider-specific selector as an acquisition strategy.
+
+### Type-Narrow Selectors
+
+- Replace optional-field `DependencySelector` with a discriminated union.
+- Benefits: no invalid local selector without path, no Civitai strategy without Civitai
+  payload, no zero-ID placeholders.
+
+### Make Locks Staleness-Aware
+
+- Add lock-level `pack_fingerprint`.
+- Add per-resolved-entry `dependency_fingerprint`.
+- Show stale lock state in status and resolve UI.
+
+### Decide Operational Semantics For Pack Dependencies
+
+- If operational: expand required pack deps when building profiles/views.
+- If informational: rename to `related_packs` or `recommended_packs`.
+- Enforce `version_constraint` or remove it.
+
+### Wire Or Remove Modeled Fields
+
+- Implement `ConflictMode`.
+- Implement active UI inventory tracking or drop it from response.
+- Implement state sync conflicts or remove `CONFLICT`.
+- Add `ProfilePackEntry.enabled` intentionally or remove stale callers.
+
+### Schema Migration
+
+- Add migration helpers per persisted document.
+- Use schema version dispatch before Pydantic validation.
+- Keep migration tests with old fixture JSON.
+
+## 14. Open Questions For Owner
+
+1. Should `pack_dependencies` affect runtime composition, or are they advisory metadata?
+2. Should `apply_resolution()` update `lock.json`, invalidate it, or leave stale state
+   until explicit resolve?
+3. Is `Pack.source` meant to mean "creation source" or "all pack content source"?
+4. Do workflow imports deserve `PackCategory.WORKFLOW`, or should they be `CUSTOM` with
+   a workflow facet?
+5. Are install packs trusted first-party objects only, or can users import arbitrary
+   install packs?
+6. Should custom packs be backend-updatable when their dependencies use `FOLLOW_LATEST`?
+7. Should optional dependencies affect `PackLock.is_fully_resolved()`?
+8. Should dependency IDs be user-editable after a lock exists?
+9. Is ComfyUI custom node management part of store assets, install packs, or a separate
+   extension manager?
+10. Should backup state sync be push/pull only, or a true bidirectional merge with
+    conflict resolution?
+11. Should UI roots be persisted in store config or remain application config?
+12. What is the migration policy for existing `synapse.pack.v2` files once canonical
+    source lands?
+

tokens used
167,791
Wrote the audit to [plans/audits/codex-domain-audit.md](/home/box/git/github/synapse/plans/audits/codex-domain-audit.md).

It is 1,095 lines and includes file:line refs, branch comparison for `feat/resolve-model-redesign`, `NEEDS VERIFICATION` marks, model inventory, enum audit, pack/dependency/source/profile/blob/UI findings, concrete refactor recommendations, and owner questions.

No tests were run; this was a read/design audit plus markdown file creation.
