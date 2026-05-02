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
- Hide mock script buttons nebo je labelovat "nonfunctional".
- Allow metadata/template preview only (read-only).
- Ship Profiles/Attach support pro **už nainstalovaná** UIs nezávisle (= BOD 5).

**Minimum před enabling execution (Release 2+):**
1. Backend script manifest + safe path resolution.
2. Explicit confirmation dialog s script path, hash, source, risk warning.
3. Script execution service: cwd confinement, env control, stdout/stderr capture, exit codes,
   task IDs, audit logs.
4. Process manager: PID, port, health checks, stop, timeout, restart policy.
5. WebSocket/SSE log streaming + persisted log retrieval.
6. Install result contract zapisující UI root do config/profile target data.
7. Per-UI health checks + templates.
8. Separate semantics pro model/blob updates vs UI application updates.

---

## BOD 4 — Workflow Wizard

**Branch:** `main`.
**Spec:** `plans/PLAN-Workflow-Wizard.md` (import je v Phase 6 advanced features, ale R1 ho chce jako core).

### Kde jsme
- **Pack workflow storage funguje** — `workflows/` dir + metadata v `pack.json`.
- **`POST /api/packs/{pack}/generate-workflow` existuje** — rule-based generování ComfyUI
  graph z pack deps + parameters. Není AI.
- **`POST /api/packs/{pack}/upload-workflow` existuje** pro upload existujícího workflow JSON
  do existujícího packu.
- **`PackWorkflowsSection` má UI pro generate/upload**, "Generate Default" tlačítko +
  "Upload Workflow" tlačítko.
- **Legacy `src/workflows/scanner.py` + `resolver.py` existují** — umí scanovat ComfyUI
  workflow JSON a najít model references.
- **MCP `scan_workflow` + `resolve_workflow_dependencies` tools existují** — dostupné chatu.
- **ComfyUI workflow symlink creation existuje** — `state/packs/<Pack>/workflows/*.json`
  → `<comfyui>/user/default/workflows/<Pack>__<workflow>.json`.

### Co chybí (HODNĚ)
- **Žádná wizard komponenta neexistuje.**
- **Žádný target UI selector** (ComfyUI vs Forge vs A1111 vs SD.Next).
- **Žádný preview-source selector** (default params vs preview image metadata).
- **Žádné configurable generator options.**
- **Žádný template directory.**
- **Žádný generator registry / abstract generator interface.** Současný v2 generátor je
  inline v `src/store/api.py`, nezapojený do `src/workflows`.
- **Forge / A1111 / SD.Next generátory NEEXISTUJÍ.** Žádné templates, žádné nodes.
- **`AssetKind` v v2 NEMÁ `WORKFLOW` kind** (legacy `AssetType.WORKFLOW` ano).
- **Global workflow import přes `ImportModal` je BROKEN** — UI posílá payload, backend
  request model neodpovídá.
- **Upload nescannuje a neresolvuje dependencies.** Upload nevaliduje workflow shape.
  Upload nevytváří custom pack. Upload nevytváří dependency záznamy. Upload nedetekuje
  custom nodes.
- **Generated workflow ignoruje hires/upscaler graph** i když parameters obsahují hires.
- **Generated workflow ignoruje** `params.scheduler`, `params.denoise`, VAE recommendations,
  ControlNet/IPAdapter/FreeU/refiner/inpainting/batch.
- **Generated workflow nepoužívá image-specific preview metadata** jako parameter source.
- **Generated workflow se nepojmenovává** podle selected source/look.
- **`src/workflows/scanner.py` + `resolver.py` NENÍ wired do v2 pack workflow upload/import.**
- **MCP workflow resolution je jen assistant/tool-facing.**
- **Profiles solve model symlinks, ale workflow import nedeklaruje deps**, takže Profiles
  nemůžou exposnout missing models.
- **ComfyUI workflow symlink target je hardcoded** v `src/store/api.py:4590-4592` na
  `config.comfyui.base_path / "user/default/workflows"` — žádný equivalent pro Forge/A1111/SD.Next.
- **Workflow upload modal se zavře hned po mutate call**, před success/failure feedback.
- **Pack plugin feature flags se nepoužívají k schování workflow sekce** v `PackDetailPage`.
- **Žádné test pro `POST /api/packs/{pack}/generate-workflow`** (output graph correctness).
- **Žádné test pro upload JSON validation a storage.**
- **Žádné test pro upload dependency scanning.**
- **Žádné test pro path traversal v workflow upload filenames.**

### Otázky pro uživatele
1. **Má imported ComfyUI workflow JSON vytvořit nový custom pack default, nebo zeptat se "add to existing"?**
2. **Mají workflow dependencies být `PackDependency` přímo, nebo `PackDependencyRef` na existující packy?**
3. **Mají custom nodes být dependencies, install packs, nebo separate dependency class v v2?**
4. **Má workflow storage být per-UI folders, nebo zachovat flat folder s `ui` metadata na `WorkflowInfo`?**
5. **Mají generated workflows být regenerated z parameters, nebo má JSON být editable a divergovat?**
6. **Jak normalizovat preview image metadata do `GenerationParameters` modelu?**
7. **A1111/Forge/SD.Next output: config text, JSON, PNG info block, nebo UI-specific preset?**
8. **Jak ComfyUI workflow validation handluje API-format vs UI-format workflows?**
9. **Jak workflow import handluje workflows vyžadující multiple model packs?**
10. **Jak active Profiles linkovat do actual UI installations aby workflows našly exposed filenames?**

### Napojení do aplikace
- **Vstupní bod 1 (existing pack):** `PackDetailPage` → `PackWorkflowsSection` → "Generate Default"
  → `POST /api/packs/{pack}/generate-workflow` → JSON → uložit do pack workflows.
- **Vstupní bod 2 (existing pack):** `PackWorkflowsSection` → "Upload Workflow" → file picker
  → `POST /api/packs/{pack}/upload-workflow` → JSON → uložit (BEZ scan/resolve).
- **Vstupní bod 3 (global import) — BROKEN TEĎ:** `ImportModal` → workflow tab → posílá
  workflow JSON, ale request model nesedí.
- **Workflow → ComfyUI cesta:** symlink `<pack>/workflows/*.json` →
  `<comfyui>/user/default/workflows/<Pack>__<workflow>.json`. Pro Forge/A1111/SD.Next
  ŽÁDNÁ podobná cesta neexistuje.
- **Codex doporučení (existing-first):**
  - **Nedělat separátní workflow systém.**
  - Reuse `src/workflows/scanner.py` + `resolver.py` pro import scanning.
  - Move/wrap inline ComfyUI generator z `src/store/api.py` do `src/workflows` s v2 modely.
  - Add generator registry/service.
  - Extend current `WorkflowInfo` rather than nový workflow database.
  - Wire upload/import → scan → nabídnout: (a) přidat scanned assets do custom packu,
    (b) link na existing packy, (c) resolve missing assets, (d) save as-is.
  - **Fix global Import modal/API mismatch před přidáním nového UI.**

---

## BOD 5 — App Connection (= Profiles, NE App Connector!)

**Branch:** `main`.
**Spec:** `plans/PLAN-Profiles.md` + `plans/PLAN-Model-Inventory.md` (sekce 9 — diagnostics TODO).
**KRITICKÉ:** Existující systém `ProfileService` + `ViewBuilder` + `UIAttacher` JE app connection. **NIKDY nevytvářet "App Connector" jako paralelní systém — rozšířit Profiles!**

### Kde jsme (silný foundation)
- **`ProfileService` (`src/store/profile_service.py`) — kompletní:** `ensure_work_profile`,
  `use`, `back`, `sync_profile`, `_install_missing_blobs` (auto-restore z backup),
  rollback při selhání, push/pop runtime stack.
- **`ViewBuilder` (`src/store/view_builder.py`) — kompletní:** atomic build (staging +
  rename), last-wins shadowing, ShadowedEntry tracking, Windows fallback (symlink → hardlink → copy),
  `clean_orphaned_views`, `activate`, `get_active_profile`.
- **`UIAttacher` (`src/store/ui_attach.py`) — kompletní pro 4 UIs:**
  - **ComfyUI:** `attach_comfyui_yaml` patchuje `extra_model_paths.yaml` se sekcí
    `synapse:` + per-kind absolute paths, vytvoří `.synapse.bak`.
  - **Forge / A1111 / SD.Next:** symlink `<ui_root>/<kind_path>/synapse` → `views/<ui>/active/<kind>`.
- **`UIKindMap` (`src/store/models.py`) — kompletní per-AssetKind path mapping** pro
  comfyui (`models/checkpoints`, `models/loras`, ...), forge / a1111 / sdnext
  (`models/Stable-diffusion`, `models/Lora`, `models/VAE`, ...).
- **`UIConfig.get_default_kind_maps()`** vrací default mapping pro všechny 4 UIs.
- **API endpoints existují:**
  - profiles: `/api/profiles/`, `/status`, `/use`, `/back`, `/sync`, `/reset`, `/{name}`
  - store-level attach: `/api/store/attach`, `/detach`, `/attach-status`
- **CLI exposed:** `synapse use`, `back`, `reset`, `profiles list/show`, `status`, `attach`,
  `detach`, `attach-status`, `sync`.
- **Settings page má `store_ui_roots`, `store_default_ui_set`, `store_ui_sets`** s
  diagnostics endpoint pro ComfyUI path detection.
- **`ProfilesPage` zobrazuje:** runtime status, back/reset mutations, shadowed files
  warning, history.
- **Backup auto-restore funguje** v `_install_missing_blobs`.
- **Tests existují** pro `ViewBuilder.compute_plan` (empty, single, conflict, build),
  `ProfileService.use/back`, attach/detach symlink creation, ComfyUI YAML, refresh.

### Co chybí (HLAVNÍ DÍRY)
**ProfilesPage UX díry:**
- **`ProfilesPage` NEMÁ Attach/Detach controls.** User vidí stack, ale nemá tlačítko
  "Connect ComfyUI" nebo "Disconnect Forge".
- **`ProfilesPage` NEMÁ UI roots configuration.** Settings to má, Profiles ne.
- **`ProfilesPage` NEUKAZUJE attached app health** (je ComfyUI běžící? Vidí synapse models?).
- **`ProfilesPage` NEUKAZUJE last synced / view built timestamp.**
- **`ProfilesPage` NEUKAZUJE missing blob count, build errors, unresolved deps.**
- **`StatusReport.shadowed` je VŽDY EMPTY** z `Store.status()` (`src/store/__init__.py:951-960`).
  ProfilesPage shadowed table tedy vždy prázdná.
- **Žádné stale orphaned views warnings.**

**Backend logic díry:**
- **`Profile.conflicts.mode` je modeled, ale `ViewBuilder` ignoruje.** Vždy last-wins.
  `first_wins` a `strict` modes nefungují.
- **`ProfilePackEntry.enabled` je v CLI viditelné, ale `ViewBuilder.compute_plan` ho
  nekontroluje.** Disabled pack se přesto symlinkuje.
- **`ProfileService._load_packs_for_profile()` swallows ALL pack load errors** (`:483-490`).
- **`ProfileService._install_missing_blobs()` swallows restore/download errors** (`:522-537`).
- **`UseResult` neobsahuje build report errors, missing blob counts, attach refresh results.**
- **`Store.sync()` NEREFRESHUJE attached UIs** po rebuildu views.
- **`Store.reset(sync=True)` NEREFRESHUJE attached UIs.**
- **`UpdateService._sync_after_update()` NEREFRESHUJE attached UIs.**
- **`ViewBuilder.clean_orphaned_views()` existuje, ale není wired do store ops.**
- **`delete_pack()` NEČISTÍ built view folders.**
- **`use(sync=False)` push runtime stack BEZ build/activate view.**
- **`back(sync=False)` zkusí activation a SUPRESSU JE failure** (`:343-349`).

**API/integrace díry:**
- **Profiles API NEEXPOSUJE attach/detach/status.** Jen store-level.
- **Profiles API `reset` returns legacy `ui_results` ale drops `ResetResult.notes`.**
- **CLI `sync` volá `store.sync(profile_name=profile, ui_set=ui_set)` i když `profile=None`** —
  `Store.sync()` requires string. Bug.
- **CLI `update` output treats `result.applied` as iterable length**, ale je to `bool`. Bug.
- **`download-asset` (přímý pack download) BYPASSU JE Profiles** — vytváří přímé ComfyUI
  symlinky mimo `views/`, může unlink existing real files (`:2702-2707`).
- **Custom pack creation NEPŘIDÁVÁ pack do globálního profilu.** Civitai import to dělá,
  custom create ne.
- **Custom pack creation volá `store.layout.pack_path()` (`:3334`)**, ale `StoreLayout`
  definuje jen `pack_dir()`. **NEEDS VERIFICATION** — možná crash.

**ComfyUI specific díry:**
- **ComfyUI path detection je jen `Path.exists()`** proti `config.comfyui.base_path`.
- **ComfyUI YAML attach include jen kinds s existing view folders** (`:123-136`) — pokud
  pack nemá LoRA, LoRA path není v YAML.
- **ComfyUI YAML PÍŠE absolute paths per kind, ne `base_path` style.**
- **ComfyUI custom nodes NEJSOU attached přes Profiles.**
- **ComfyUI workflows jsou managed přes separate endpoints, ne Profiles.**
- **ComfyUI attach status checkne JEN že `synapse` exists v YAML** (`:499-508`), ne
  že paths pointují na current active profile.

**Forge / A1111 / SD.Next díry:**
- **Existing root-level model filename conflicts NEDETEKOVÁNY.**
- **Existing non-symlink `synapse` folders → reported as errors, no migration path.**
- **A1111 + SD.Next NEJSOU v default `local` UI set** (jen comfyui + forge).
- **SD.Next mapping DUPLIKUJE A1111 mapping** — NEEDS VERIFICATION jestli je správné.
- **Forge mapping NEEDS VERIFICATION** pro všechny současné asset kinds.

**Settings/config díry:**
- **Settings ukládá `store_ui_roots` do app config**, backend píše do `config.settings`,
  ale **store UI targets čte z `state/ui_sets.json`.** Source-of-truth split.
- **Settings default UI-set changes neaktualizují `state/config.json`.**
- **Settings UI sets neaktualizují `state/ui_sets.json`.**
- **Store singleton se NERESETUJE když se mění `store_default_ui_set` nebo `store_ui_sets`** —
  jen když se mění UI roots.

### Otázky pro uživatele (HODNĚ — toto je core feature)
1. **Má se `ProfilesPage` stát canonical UI connection dashboard?**
2. **Mají Attach/Detach/Attach Status přejít z store-level UI do `ProfilesPage`?**
3. **Má `/api/profiles/status` zahrnout attach status pro každý UI?**
4. **Má `/api/profiles/status` zahrnout configured root path + existence pro každý UI?**
5. **Má UI installation detection zůstat path-exists only, nebo skenovat common locations?**
6. **Má být default UI targets v store state, app config, nebo unified source?**
7. **Mají Settings psát `state/config.json` a `state/ui_sets.json` pro Profile defaults?**
8. **Má `local` default zahrnout A1111 a SD.Next když roots existují?**
9. **Má `use(pack)` auto-attach UI pokud je configured ale detached?**
10. **Má `use(pack)` failnout / warnnout / continue když žádný target UI není attached?**
11. **Má `sync(profile)` automaticky refresh attached UIs?**
12. **Má `reset(sync=True)` automaticky refresh attached UIs?**
13. **Mají update downloads triggernout Profile view rebuild po dokončení?**
14. **Má `download-asset` přestat vytvářet přímé ComfyUI symlinky?**
15. **Má všechno app connection jít přes Profile views only?**
16. **Má ComfyUI použít absolute per-kind YAML paths nebo `base_path` style?**
17. **Mají A1111/Forge/SD.Next symlinks pointovat na stable `views/<ui>/active/...` místo
    resolved profile dirs?**
18. **Má `UIAttacher` někdy přepsat existing `synapse` real directories?**
19. **Co se má stát když UI už má model se stejným filename?**
20. **Má Profile conflict mode podporovat `first_wins` a `strict`, nebo simplified na last-wins?**
21. **Má `ProfilePackEntry.enabled` ovlivnit view building?**
22. **Mají custom nodes být managed Profiles?**
23. **Mají workflows být scoped active Profile?**
24. **Mají workflow symlinks být removed když pack opustí active Profile?**
25. **Má backup auto-restore během `use` být silent nebo confirm by user?**
26. **Má backup restore checknout disk space před copy?**
27. **Mají build errors a missing blobs být hard failures pro `use`, nebo warnings?**
28. **Má `UseResult` exponovat per-UI build a attach-refresh results?**
29. **Má Doctor čistit orphaned Profile views by default?**
30. **Má delete pack remove built view directories?**
31. **Má `ProfilesPage` zobrazit "model should now appear in ComfyUI as X" confirmation?**
32. **Má Profile status compute shadowed entries live, cache, nebo persist build reports?**
33. **Má Windows copy fallback být allowed (breaks content-addressed live-link semantics)?**
34. **Má app connection support "rescan UI models" command per UI?**

### Napojení do aplikace
- **Toto JE napojení na aplikace.** Není co přidávat jako paralelní systém.
- **Vstupní bod (TEĎ — Settings):** Settings → "ComfyUI Path" / "Forge Path" / atd. →
  `POST /api/system/settings` → store_ui_roots saved → store singleton reset.
- **Vstupní bod (TEĎ — ProfilesPage):** Sidebar "Profiles" → `ProfilesPage` → vidí stack,
  může `back/reset/use`. Attach je SKRYTÝ za store-level API.
- **Vstupní bod (CHYBÍ):** "Connect ComfyUI" tlačítko v ProfilesPage → API call → UIAttacher
  → diff dialog → confirm → patch yaml / vytvořit symlinks → success badge.
- **Use flow:** `POST /api/profiles/use` → `ProfileService.use(pack)` → ensure work profile
  → push runtime stack → `_install_missing_blobs` (z backup) → `sync_profile` (build views)
  → activate → **MISSING:** refresh attached UIs.
- **View build cesta:** `ViewBuilder.compute_plan(profile)` → `ShadowedEntry` last-wins
  resolve → atomic build do `data/views/<ui>/profiles/<profile>/_staging/` → rename na
  `data/views/<ui>/profiles/<profile>/` → activate symlink `data/views/<ui>/active/` →
  symlink/yaml entry → ComfyUI / A1111 / Forge / SD.Next vidí models.
- **Update napojení (DÍRA):** Updates downloadnou nový blob → lock state se updatne → views
  se NESYNCNOU → ProfilesPage status nereflektuje. Doctor / manual sync musí spustit user.

---

## BOD 6 — Built-in AI integration s graceful degradation

**Branch:** `main`.
**Spec:** `plans/PLAN-AI-Services.md` (probably stale).

### Kde jsme
- **AvatarEngine integration je solidní:**
  - `/api/avatar/status` returns `ready`, `disabled`, `incompatible`, `no_provider`,
    `no_engine`, `setup_required` — vždy 200.
  - `/api/avatar/config` GET/POST — exposuje a updatuje `enabled`, default provider,
    provider enabled/model.
  - Mount na `/api/avatar` s graceful fallback.
- **Master AI toggle funguje** v Settings → `enabled=false` → `Layout` schová `AvatarWidget`.
- **Provider config UI:** radio default, enable checkbox, model selector / free text.
  `(Not installed)` text pokud CLI chybí.
- **Dynamic models discovery:** `dynamicProviders` z avatar-engine, fallback na static
  `getModelsForProvider()`.
- **Cache UI:** stats, cleanup, clear.
- **One-shot toasts** pro `no_engine`, `no_provider`, `setup_required`, `incompatible`.
- **Generic task service `AvatarTaskService`** — cache → AI → parse/validate → fallback.
- **Task registry s `parameter_extraction` a `model_tagging`** (NE `dependency_resolution`
  na main; ten je na branchi).
- **Parameter extraction má reálný regexp fallback** (`RuleBasedProvider` →
  `src.utils.parameter_extractor.extract_from_description`).
- **Model tagging má keyword fallback** (ale není wired do production flow).
- **MCP store server má 21 tools** (list_packs, scan_workflow, find_model_by_hash,
  search_civitai, atd.) — dostupné chatu.
- **AI metadata:** `_extracted_by`, `_ai_fields` se ukládá do parameters → "bot badge"
  v `PackParametersSection` zobrazuje extraction source.
- **Pack parameter extraction on Civitai import:** `pack_service.py:536` extrahuje params
  z description, fallback chain.
- **`/api/ai/extract` endpoint** pro programmatic description extraction.

### Co chybí (HLAVNÍ DÍRY)
- **`enabled=false` se neenforce-uje na backendu.** UI text říká "all AI features inactive",
  ale `AvatarTaskService` neckontroluje `config.enabled`. Imports + `/api/ai/extract` můžou
  pořád běžet AI/fallback.
- **Žádný persistent global "AI unavailable" banner v app shell.** Jen one-shot toasts
  (easy to miss).
- **Žádný per-feature `Requires AI` badge.**
- **Pokud `enabled=true` ale engine je unavailable, `Layout` STÁLE rendruje `AvatarWidget`** —
  WebSocket behavior je delegated na avatar-engine React. **NEEDS VERIFICATION.**
- **`always_fallback_to_rule_based` je loaded ale nepoužívá se** (no enforcement).
- **Žádný provider fallback chain** napříč Gemini/Claude/Codex. `AvatarTaskService` používá
  jen `config.provider`.
- **Žádné task priority UI ani backend schema** (i když spec to chce).
- **Verzové konstrains nesedí:** `pyproject.toml` má `avatar-engine>=1.0.0,<2.0`, backend
  `__init__.py` requires `1.2.0`, frontend warns jen pod `1.0.0`. **Inconsistent.**
- **`config/avatar.yaml.example` říká "currently only parameter extraction"** ale registry
  má i model tagging. Stale.
- **`model_tagging` task existuje, je tested, ale ŽÁDNÝ caller v produkci.**
- **`/api/ai/extract` exists, ale frontend `extractParameters()` se nepoužívá** (dle search).
- **E2E testy odkazují na `/api/ai/providers` a `/api/ai/settings`** — ty endpointy v `main`
  NEEXISTUJÍ. Stale tests nebo missing endpoints.
- **`AvatarTaskService._ensure_engine_for_task()` v main vytvoří `AvatarEngine` BEZ
  `mcp_servers`, `additional_dirs`, `allowed_tools`, task-specific timeout.** Branch
  `feat/resolve-model-redesign` to opravuje.
- **Task base class v main NEMÁ `needs_mcp` ani `timeout_s`** (branch má).
- **`AvatarTaskService` nečte provider `enabled`** — disabled provider může být default.
- **`AvatarConfig.providers` ukládá jen `model` a `enabled`** — žádné priority ani runtime status.
- **`/api/avatar/status` reports `ready` když ANY provider CLI je installed**, ne nutně selected.
- **Cache key používá one provider/model** — žádná multi-provider chain telemetry.
- **Parameter extraction on import catches all errors silently** (`pack_service.py:560`).
- **AI feature integrace cross-feature nepropojené:**
  - **Custom pack creation/editing — žádné AI action points.**
  - **Profiles — žádná AI mapping assistance pro non-standard models.**
  - **Workflow generation — současný feature je rule-based, ne AI.**
  - **Chat suggestions advertise workflow/dependency actions, ale produkt features nevolají AI task service.**
- **MCP side-effect tools (`import_civitai_model`) můžou vytvořit packs a stáhnout GB**
  — approval UX musí být verified přes avatar-engine permission flow. **NEEDS VERIFICATION.**
- **Frontend lockfile state inconsistent:** `package.json` `^1.3.0`, `pnpm-lock.yaml` points
  na local `../../../avatar-engine` linky.
- **`AvatarStatus` frontend type omits `incompatible`**, i když testy ho expectují.
- **Žádný local `/api/avatar/models` endpoint.** Dynamic models jdou přes avatar-engine
  React/backend behavior. **NEEDS VERIFICATION.**

### Otázky pro uživatele
1. **Má `enabled=false` disablovat ALL backend AI service calls, nebo jen user-facing chat?**
2. **Má fallback běžet i když AI je disabled, nebo jen když AI fails?**
3. **Je `model_tagging` určený na import, custom pack creation, nebo future work?**
4. **Má R1 zahrnout branch `feat/resolve-model-redesign` před claimem "AI dependency resolution"?**
5. **Mají být `/api/ai/providers` a `/api/ai/settings` restored, nebo stale E2E tests removed?**
6. **Má `generate-workflow` být přejmenovaný na "Generate default workflow" aby nebudilo dojem AI?**
7. **Mají MCP side-effect tools být restricted za explicit avatar-engine permission policy?**
8. **Která verze je autoritativní: backend `1.2.0`, frontend `1.0.0`, npm `1.3.0`?**
9. **Mají model discovery errors být zobrazeny inline v Settings, ne jen toast?**

### Napojení do aplikace
- **Vstupní bod (chat):** `Layout` → `AvatarProvider` → `AvatarWidget` → user chat →
  avatar-engine přes `/api/avatar` mount → MCP servers (Synapse store, Civitai, workflow,
  dependencies).
- **Vstupní bod (programmatic):** `/api/ai/extract` (description → parameters) volá
  `AvatarTaskService.execute_task("parameter_extraction", ...)` → AI provider → fallback.
- **Vstupní bod (import):** `pack_service.import_civitai()` → po pack save → automatic
  parameter extraction → AI provider → fallback regexp → uložit do pack parameters.
- **AI metadata flow:** result.metadata `_extracted_by` + `_ai_fields` → uložit do
  pack.parameters → `PackParametersSection` zobrazí "bot badge".
- **Cache flow:** task cache klíč = `(task_name, input_text_hash, provider, model)` →
  cache hit skip AI → cache miss volá AI → uložit result.
- **MCP cesta (chat-only, NE programmatic):** chat → avatar-engine → tool call →
  `src/avatar/mcp/store_server.py` → Synapse Store API → response zpět.
- **Graceful degradation cesta:**
  - `enabled=false` → Layout schová widget → BUT backend stále běží AI z `/api/ai/extract`
    a importu (BUG).
  - Provider unavailable → `_extracted_by=rule_based` (parameter_extraction) nebo task error.
  - Engine import fails → `setup_required` toast → mount returns false.
  - Provider CLI not installed → `(Not installed)` v Settings → row disabled.

### Cross-references s ostatními body
- **BOD 1 (Resolve Model):** `DependencyResolutionTask` je na BRANCHI, ne main. Pokud R1
  zahrne branch, AI dependency resolution bude integrated. Pokud ne — AI jen přes chat/MCP.
- **BOD 2 (Custom Pack):** žádná AI integrace v create/edit modalech. MCP může v chatu
  navrhovat assets, ale není wired do UI.
- **BOD 4 (Workflow Wizard):** "Generate workflow" je rule-based. Pokud R1 chce AI generation,
  potřebuje nový `workflow_generation` task + UI badge.
- **BOD 5 (Profiles):** žádná AI assistance pro mapping non-standard modelů na base aliases.
- **BOD 3 (Install Pack):** N/A, install pack je future.

---

## ⏭️ Doporučený další krok

**Až se uživatel vrátí, projít s ním:**

1. **BOD 5 (Profiles) má 34 otázek** — nejvíc, protože je to core feature R1 a má největší
   integrační prostor. Začít tady.
2. **BOD 1 (Resolve Model) má 10 otázek** — branch decisions (v0.11.0 source of truth?
   apply lock? policy?).
3. **BOD 2 (Custom Pack) má 12 otázek** — hlavně dependency authoring + profile semantics
   pro `pack_dependencies`.
4. **BOD 4 (Workflow Wizard) má 10 otázek** — multi-UI generation strategy + import flow.
5. **BOD 6 (AI Integration) má 9 otázek** — graceful degradation enforcement + version sync.
6. **BOD 3 (Install Pack)** — codex doporučuje **NESHIPOVAT spustitelné install packs v R1**.
   Místo toho enable jen metadata/template preview + Profiles attach pro už nainstalovaná UIs.

**Priorita per uživatel (z roadmapy):** 1 (paralelně doma) → 5 → 2 → 4 → 6 → 3.

---

## 📌 Klíčové cross-cutting nálezy

1. **Profiles + UIAttacher = MOSTLY DONE.** Backend solid, ale **ProfilesPage UI je
   nedokončený** (chybí attach controls, configuration, health indicators). Není potřeba
   nový "App Connector" — rozšířit Profiles.

2. **`download-asset` BYPASSU JE Profiles.** Vytváří přímé ComfyUI symlinky mimo `views/`,
   může unlinknout existing real files. To je **architektonicky špatně** — všechno app
   connection by mělo jít přes Profile views.

3. **Custom pack create volá `store.layout.pack_path()` který neexistuje** (jen `pack_dir()`).
   **NEEDS VERIFICATION** — možná crash při create.

4. **`StatusReport.shadowed` je vždy empty.** ProfilesPage shadowed table tedy vždy prázdná.
   Hidden bug.

5. **Profile conflict mode + ProfilePackEntry.enabled jsou modeled ale ignored.** Buď
   dokončit nebo simplify model.

6. **`enabled=false` AI toggle se neenforce-uje na backendu.** Audit už označil jako bug.

7. **Tests heavily use `MagicMock`.** Provider unit testy by měly používat reálná Pydantic
   data ze známých Civitai/HF response shapes.

8. **Frontend Playwright E2E pro resolve je plně mockované.** Validuje UI flow, ne backend
   correctness.

9. **CLI bugs:** `sync` volá s `profile=None`, `update` treats `result.applied` as iterable.

10. **Duplicate code:** `PreviewMetaEvidenceProvider` duplikuje enrichment logic z
    `src/store/enrichment.py`.

11. **Frontend plugins testy mirror simplified definitions** místo reálné importu.

12. **MCP `search_huggingface` používá raw `requests`** místo `HuggingFaceClient`.

13. **Verzové konstrains avatar-engine nesedí** mezi `pyproject.toml`, `__init__.py`,
    `package.json`.
