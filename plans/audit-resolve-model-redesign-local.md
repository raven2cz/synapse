# Audit: Resolve Model Redesign, Local Branch State

Branch audited: `feat/resolve-model-redesign` at `5b30b99071070678878088766ec0d73e063b29f2`.

Scope note: audit used only the local branch contents available in this workspace. The user warned the newest commit may exist on another machine and may not be pushed; anything absent here is treated as absent locally.

## Executive Summary

1. The branch is much larger and newer than the stated context: `plans/PLAN-Resolve-Model.md` says `v0.11.0` and claims Phase 0+1+2+2.5+3+4 complete at the top, then later claims Phase 5 and Phase 6 complete too. See `plans/PLAN-Resolve-Model.md:3`, `plans/PLAN-Resolve-Model.md:1018`, `plans/PLAN-Resolve-Model.md:1239`, `plans/PLAN-Resolve-Model.md:1300`.
2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
3. The implementation is not fully aligned with the main spec. The biggest gaps are: manual Civitai/HF tabs are placeholders, preview hints are not kind-filtered in the resolver chain, canonical source is mostly not populated for remote suggestions, `analyze_previews` is modeled but unused, and apply writes only `pack.json`, not `pack.lock.json`.
4. Evidence provider coverage is partial. Civitai hash is implemented. HF hash is not a reverse lookup; it only verifies a pre-existing HF selector. Local hash exists through local import/cache, but not as a normal evidence provider in the suggest chain. AI evidence is wired into `ResolveService`, but runs whenever `include_ai=True`, not only after E1-E6 fail to produce Tier 1/2.
5. Tests are extensive by count, but many important ones are mocked/ceremonial. Backend unit and integration tests cover a lot of mechanics. Frontend E2E is fully mocked. Live AI E2E is a standalone script, not a normal pytest/CI test. NEEDS VERIFICATION: actual latest CI status and whether the "real provider" scripts were run on this local branch state.

## Branch Delta

1. `git diff --stat main..feat/resolve-model-redesign` reports 95 files changed, about 22,233 insertions and 1,355 deletions.
2. Major new backend files include `src/store/resolve_service.py`, `src/store/resolve_models.py`, `src/store/evidence_providers.py`, `src/store/enrichment.py`, `src/store/local_file_service.py`, `src/store/hash_cache.py`, and `src/avatar/tasks/dependency_resolution.py`.
3. Major frontend changes replace `BaseModelResolverModal.tsx` with `DependencyResolverModal.tsx`, `LocalResolveTab.tsx`, and `PreviewAnalysisTab.tsx`.
4. Test expansion is large: unit tests for resolve, evidence, local file service, preview extraction, AI task; integration/smoke tests; Playwright E2E; standalone live AI E2E scripts.

## Spec Version Drift

1. User context names `plans/PLAN-Resolve-Model.md` as v0.7.1, 1769 lines.
2. Local branch plan is `v0.11.0`, with 2439 added lines in the diff stat and top-level status saying Phase 0+1+2+2.5+3+4 complete. See `plans/PLAN-Resolve-Model.md:3`.
3. Many implementation files still say "Based on PLAN-Resolve-Model.md v0.7.1" in docstrings. See `src/store/resolve_service.py:5`, `src/store/resolve_models.py:4`, `src/store/evidence_providers.py:4`.
4. NEEDS VERIFICATION: whether this plan/version mismatch is expected local history or drift from another machine.

## Phase Coverage

### Phase 0: Infrastructure, Model, Calibration

Status: Mostly implemented, with caveats.

1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
3. Tier boundaries, HF eligibility, compatibility rules, AI ceiling, and auto-apply margin exist. See `src/store/resolve_config.py:28`, `src/store/resolve_config.py:35`, `src/store/resolve_config.py:80`, `src/store/resolve_config.py:132`, `src/store/resolve_config.py:173`.
4. Scoring implements provenance grouping, Noisy-OR, and tier ceiling. See `src/store/resolve_scoring.py:16`, `src/store/resolve_scoring.py:38`, `src/store/resolve_scoring.py:77`.
5. Hash cache exists with mtime+size invalidation and atomic save. See `src/store/hash_cache.py:36`, `src/store/hash_cache.py:67`, `src/store/hash_cache.py:84`.
6. Async hash helper exists. See `src/store/hash_cache.py:159`.
7. Preview extractor exists for sidecar JSON and PNG tEXt chunks. See `src/utils/preview_meta_extractor.py:97`, `src/utils/preview_meta_extractor.py:127`, `src/utils/preview_meta_extractor.py:252`, `src/utils/preview_meta_extractor.py:405`.
8. Caveat: calibration is not fully implemented. The plan itself says confidence calibration is deferred. See `plans/PLAN-Resolve-Model.md:604`.
9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.

### Phase 1: Import Pipeline and Bug Fixes

Status: Implemented mechanically, but behavior is narrower than the spec implies.

1. Store calls `_post_import_resolve(pack)` after Civitai import. See `src/store/__init__.py:592`.
2. `_post_import_resolve()` extracts preview hints from downloaded previews, calls `resolve_service.suggest()` with `include_ai=False`, and auto-applies Tier 1/2 if margin passes. See `src/store/__init__.py:604`, `src/store/__init__.py:624`, `src/store/__init__.py:632`, `src/store/__init__.py:655`.
3. It skips dependencies that are not `BASE_MODEL_HINT`, avoiding overwriting pinned deps. See `src/store/__init__.py:626`.
4. It checks `ApplyResult.success` before logging success. See `src/store/__init__.py:656`, `src/store/__init__.py:660`.
5. Suggest/apply API endpoints exist, but not at the exact spec path. The plan sketches `/dependencies/{dep_id}/suggest`; code uses pack-level body params: `/api/packs/{pack}/suggest-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
6. `SuggestRequest` has no `analyze_previews` field, even though `SuggestOptions` does. See `src/store/api.py:2247`, `src/store/resolve_models.py:135`.
7. Caveat: `ResolveService.suggest()` ignores `options.analyze_previews`; it only uses `preview_hints_override` or `dep._preview_hints`. See `src/store/resolve_service.py:201`.
8. Caveat: import preview hints are passed wholesale to every BASE_MODEL_HINT dep; filtering by dependency kind is not applied at this stage. See `src/store/__init__.py:636` and `src/store/evidence_providers.py:169`.

### Phase 2: AI-Enhanced Resolution and UI

Status: AI backend is wired; UI is partly wired; manual provider tabs are mocked/placeholders.

1. `DependencyResolutionTask` exists, has `needs_mcp=True`, timeout 180s, and loads five skill files. See `src/avatar/tasks/dependency_resolution.py:42`, `src/avatar/tasks/dependency_resolution.py:43`, `src/avatar/tasks/dependency_resolution.py:50`.
2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
3. `AIEvidenceProvider` builds structured text and calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:518`, `src/store/evidence_providers.py:525`.
4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
5. AI ceiling is enforced in both task parsing and evidence conversion. See `src/avatar/tasks/dependency_resolution.py:89`, `src/store/evidence_providers.py:844`.
6. `ResolveService` registers AI provider. See `src/store/resolve_service.py:166`.
7. `ResolveService.suggest()` skips AI unless `include_ai=True`. See `src/store/resolve_service.py:226`.
8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
9. UI modal exists with Candidates, Preview, Local, AI, Civitai, and HF tabs. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:61`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:346`.
10. AI tab is gated by `avatarAvailable`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:350`, `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
11. HF tab is gated by frontend `HF_ELIGIBLE_KINDS`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
12. Civitai manual tab is a placeholder: "Manual Civitai search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
13. HuggingFace manual tab is a placeholder: "Manual HuggingFace search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
14. This contradicts the plan's Phase 4 complete claim for provider polish/manual payloads from the UI. Backend manual apply exists; frontend manual search does not.

### Phase 2.5: Preview Enrichment

Status: Partially implemented.

1. `PreviewMetaEvidenceProvider` enriches hints via Civitai hash lookup, then Civitai name search. See `src/store/evidence_providers.py:143`, `src/store/evidence_providers.py:177`, `src/store/evidence_providers.py:246`, `src/store/evidence_providers.py:252`.
2. It uses `pack_service_getter` and is wired with PackService in `ResolveService._ensure_providers()`. See `src/store/evidence_providers.py:154`, `src/store/resolve_service.py:162`.
3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
5. Gap: no kind filtering in `PreviewMetaEvidenceProvider.gather()`. It iterates all hints and does not check `hint.kind` against `ctx.kind`. See `src/store/evidence_providers.py:169`.
6. The extractor has `filter_hints_by_kind()`, but `git grep` shows no production use. See `src/utils/preview_meta_extractor.py:584`.
7. This is a direct spec gap: plan requires kind-aware filtering. See `plans/PLAN-Resolve-Model.md:167`.

### Phase 3: Local Resolve

Status: Implemented and UI-integrated.

1. Backend local browse, recommendation, and import service exists. See `src/store/local_file_service.py:191`, `src/store/local_file_service.py:207`, `src/store/local_file_service.py:268`, `src/store/local_file_service.py:344`.
2. Path validation requires absolute path, no `..`, resolved path exists, extension allowlist, regular file. See `src/store/local_file_service.py:111`.
3. Local import hashes, copies into blob store, enriches, and applies resolution. See `src/store/local_file_service.py:377`, `src/store/local_file_service.py:390`, `src/store/local_file_service.py:414`, `src/store/local_file_service.py:428`.
4. API endpoints exist: browse-local, recommend-local, import-local with background executor and polling. See `src/store/api.py:2485`, `src/store/api.py:2502`, `src/store/api.py:2546`.
5. UI tab exists and calls recommend/import/poll endpoints. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:150`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
6. Caveat: local import applies via `resolve_service.apply_manual()` if reachable, otherwise falls back to `pack_service.apply_dependency_resolution()`. See `src/store/local_file_service.py:544`.
7. Caveat: fallback path bypasses validation if `resolve_service` is not available. See `src/store/local_file_service.py:554`.
8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.

### Phase 4: Provider Polish, Download, Cleanup

Status: Cleanup and validation mostly implemented; manual provider UI and lock/write behavior remain incomplete.

1. Deprecated `BaseModelResolverModal.tsx` is deleted according to diff stat.
2. `/resolve-base-model` appears removed; current resolve endpoints are `suggest-resolution`, `apply-resolution`, and `apply-manual-resolution`. See `src/store/api.py:2302`, `src/store/api.py:2342`, `src/store/api.py:2370`.
3. API boundary validates manual strategy fields. See `src/store/api.py:2383`.
4. `Apply & Download` UI does a compound apply then `/download-asset`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:401`, `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:437`.
5. NEEDS VERIFICATION: `download-asset` expects `asset_name`; UI sends `depId`. This may be correct if asset name equals dependency id, but the audit did not verify all pack shapes. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:442`.
6. Major gap: Civitai and HF manual tabs are not implemented. They cannot produce typed payloads from UI. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
7. Major gap: `PackService.apply_dependency_resolution()` explicitly does not touch `pack.lock.json`, contrary to earlier spec language that apply updates pack.json and pack.lock atomically. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
8. `lock_entry` is accepted but unused. See `src/store/pack_service.py:1223`, `src/store/pack_service.py:1237`.

### Phase 5: Deferred Polish

Status: Mostly implemented, but not all to full spec strength.

1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
2. `AUTO_APPLY_MARGIN` is centralized and config-readable. See `src/store/resolve_config.py:132`, `src/store/resolve_config.py:138`, `src/store/__init__.py:648`.
3. `compute_sha256_async()` exists. See `src/store/hash_cache.py:159`.
4. HF enrichment exists as `enrich_by_hf()` and is used in `enrich_file()`. See `src/store/enrichment.py:166`, `src/store/enrichment.py:294`.
5. HuggingFace client parses LFS `lfs.oid` into SHA256. See `src/clients/huggingface_client.py:36`.
6. HuggingFace client has `search_models()`. See `src/clients/huggingface_client.py:120`.
7. Caveat: `LocalFileService._get_hf_client()` looks for `pack_service.hf_client`, but other code references `pack_service.huggingface` for HF access in the plan and evidence provider uses `pack_service.huggingface`. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`. NEEDS VERIFICATION: actual PackService attribute name.
8. Caveat: MCP `search_huggingface` returns formatted text, not JSON. The plan says text may be OK for LLM, but "structured output" remains unresolved in code. See `plans/PLAN-Resolve-Model.md:1271`, `src/avatar/mcp/store_server.py:1229`.
9. Caveat: MCP HF search only fetches top-level `tree/main`, not recursive subfolders or model cards. See `src/avatar/mcp/store_server.py:1306`.

### Phase 6: Config, Aliases, Tests, AI Gate

Status: Implemented mechanically, but alias defaults and test realism are weak.

1. `ResolveConfig` exists under `StoreConfig.resolve`. See `src/store/models.py:243`, `src/store/models.py:257`.
2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
3. `AIEvidenceProvider.supports()` checks config flag and avatar object. See `src/store/evidence_providers.py:510`.
4. Alias provider reads `layout.load_config().base_model_aliases`. See `src/store/evidence_providers.py:692`.
5. Alias provider supports Civitai and HF targets. See `src/store/evidence_providers.py:713`, `src/store/evidence_providers.py:741`.
6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
7. Caveat: AI gate checks avatar object presence backend-side, not a status `available` field. It assumes a non-None avatar service is usable. See `src/store/evidence_providers.py:516`.

## Evidence Providers

### Civitai Hash Evidence

Status: Implemented and wired.

1. `HashEvidenceProvider` reads SHA256 from `dep.lock.sha256`. See `src/store/evidence_providers.py:75`.
2. It calls `pack_service.civitai.get_model_by_hash(sha256)`. See `src/store/evidence_providers.py:88`.
3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
4. It assigns `hash_match` evidence with confidence 0.95. See `src/store/evidence_providers.py:120`.
5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
6. Gap: it only reads hash from `dep.lock`; it does not hash local files as part of suggest. See `src/store/evidence_providers.py:75`.

### HuggingFace LFS OID Evidence

Status: Partial verification only, not discovery/reverse lookup.

1. HF LFS OID parsing exists in `HFFileInfo.from_api_response()`. See `src/clients/huggingface_client.py:36`.
2. `HashEvidenceProvider` calls `_hf_hash_lookup()` only when kind config says `hf_hash_lookup=True`. See `src/store/evidence_providers.py:133`.
3. Only checkpoints have `hf_hash_lookup=True`; VAE/controlnet are HF-eligible but hash lookup false. See `src/store/resolve_config.py:80`, `src/store/resolve_config.py:93`, `src/store/resolve_config.py:99`.
4. `_hf_hash_lookup()` requires dependency selector already has HF repo and filename. See `src/store/evidence_providers.py:624`, `src/store/evidence_providers.py:629`.
5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
6. `find_model_by_hash` MCP tool is Civitai-only. See `src/avatar/mcp/store_server.py:1143`.

### Local Hash Evidence

Status: Implemented in local import flow, not in resolver evidence chain.

1. `HashCache` can cache SHA256 by file path. See `src/store/hash_cache.py:36`.
2. `LocalFileService.recommend()` can compare cached hash with dependency expected hash. See `src/store/local_file_service.py:306`.
3. `LocalFileService.import_file()` hashes selected file and uses hash cache. See `src/store/local_file_service.py:377`.
4. `enrich_file()` then tries Civitai hash, Civitai name, HF name, filename fallback. See `src/store/enrichment.py:271`.
5. There is no `LocalHashEvidenceProvider` in `ResolveService._ensure_providers()`. See `src/store/resolve_service.py:160`.
6. So local hash is an import/local-tab feature, not part of normal `suggest_resolution()`.

### AI Evidence

Status: Wired, but broad and prompt-dependent.

1. `AIEvidenceProvider` is registered in the provider chain. See `src/store/resolve_service.py:166`.
2. It is skipped unless `include_ai=True`. See `src/store/resolve_service.py:226`.
3. It builds a text input with pack name/type/base_model/description/tags, dependency kind/hint/expose filename, and preview hints. See `src/store/evidence_providers.py:774`.
4. It calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:526`.
5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
6. Fallback when AI is off: provider is skipped; E1-E6 still run. See `src/store/evidence_providers.py:510`, `src/store/resolve_service.py:226`.
7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.

## UI Integration

### DependencyResolverModal

Status: Integrated as the primary modal.

1. `PackDetailPage` keeps resolver state and opens modal per asset. See `apps/web/src/components/modules/PackDetailPage.tsx:126`, `apps/web/src/components/modules/PackDetailPage.tsx:132`.
2. Opening the modal eagerly calls `suggestResolution()` without AI. See `apps/web/src/components/modules/PackDetailPage.tsx:141`.
3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
4. Candidate cards show confidence label, provider, base model, compatibility warning, evidence groups, and raw score when expanded. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:193`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:235`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:279`.
5. Apply and Apply & Download buttons are wired. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:616`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:631`.

### Civitai Tab

Status: Mocked/placeholder.

1. The tab is visible. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:351`.
2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.

### HuggingFace Tab

Status: Mocked/placeholder.

1. The tab is visible only for frontend HF-eligible kinds. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.

### Local Resolve Tab

Status: Functional.

1. It browses/recommends a directory using `/recommend-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:160`.
2. It imports a selected file using `/import-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`.
3. It polls `/api/store/imports/{import_id}`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
4. It displays browse/importing/success/error states. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:297`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:368`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:441`.

### Apply

Status: Wired, but cache binding is incomplete.

1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
4. UUID collision risk is low, but missing pack/dep binding is a correctness gap already noted in the plan as deferred. See `plans/PLAN-Resolve-Model.md:888`.

### AI Gate

Status: Implemented frontend and backend, with different semantics.

1. Frontend hides AI tab unless avatar status has `available=true`. See `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
2. Backend hides AI provider when config `resolve.enable_ai=false` or avatar getter returns None. See `src/store/evidence_providers.py:510`.
3. Backend does not check avatar runtime status `available`; it assumes non-None service can run. NEEDS VERIFICATION.

## Preview Analysis

Status: UI tab and backend extractor are wired; it is partly display-only.

1. Backend endpoint `/preview-analysis` analyzes preview sidecars and PNG text. See `src/store/api.py:2275`.
2. Frontend hook fetches `/api/packs/{pack}/preview-analysis`. See `apps/web/src/components/modules/pack-detail/hooks/usePreviewAnalysis.ts:10`.
3. Preview tab displays thumbnails, model references, hashes, weights, and generation params. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:64`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:116`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:182`.
4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
7. In backend suggest, preview hints are only available if `_post_import_resolve()` passes overrides or if a dependency has `_preview_hints`. See `src/store/resolve_service.py:201`.
8. The public suggest endpoint does not itself run preview analysis or pass preview hints. See `src/store/api.py:2302`, `src/store/api.py:2322`.
9. The tab fetches preview analysis separately, but those hints are not fed back into `onSuggest()`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:507`.

## AI Integration

Status: Real task and service wiring exist; live provider claims need verification.

1. `DependencyResolutionTask` is registered in default registry per plan; registry change present in diff stat, not deeply audited here. NEEDS VERIFICATION on exact registry line.
2. Task prompt is skill-file based; `build_system_prompt()` returns skill content only. See `src/avatar/tasks/dependency_resolution.py:53`.
3. Task parses and validates AI output with provider-specific required fields. See `src/avatar/tasks/dependency_resolution.py:63`, `src/avatar/tasks/dependency_resolution.py:127`.
4. Task has no fallback; E1-E6 are expected to provide non-AI coverage. See `src/avatar/tasks/dependency_resolution.py:164`.
5. `AvatarTaskService` starts `AvatarEngine` with MCP servers for `needs_mcp` tasks. See `src/avatar/task_service.py:336`.
6. MCP includes `search_civitai`, `analyze_civitai_model`, `find_model_by_hash`, `suggest_asset_sources`, and `search_huggingface`. See `src/avatar/mcp/store_server.py:1428`, `src/avatar/mcp/store_server.py:1434`, `src/avatar/mcp/store_server.py:1486`, `src/avatar/mcp/store_server.py:1492`, `src/avatar/mcp/store_server.py:1498`.
7. `find_model_by_hash` is Civitai-only despite AI prompt comments mentioning HF/hash capability. See `src/avatar/mcp/store_server.py:1143`.
8. `search_huggingface` performs real HTTP through `requests`, not through the shared HF client/session/token. See `src/avatar/mcp/store_server.py:1239`.
9. NEEDS VERIFICATION: whether avatar-engine permissions and MCP server config are actually present in local runtime config, not just `config/avatar.yaml.example`.

## Tests

### Unit Tests

Status: Broad coverage, often mocked.

1. Unit tests exist for models, config, validation, scoring, hash cache, providers, resolve service, preview extractor, local file service, enrichment, and AI task per diff stat.
2. `tests/unit/store/test_evidence_providers.py` heavily uses `MagicMock`. See grep output: many `MagicMock` references, e.g. `tests/unit/store/test_evidence_providers.py:32`.
3. This is fine for unit mechanics but does not prove real Civitai/HF data shape compatibility.
4. Some tests do use Pydantic models in other files per plan, but the most provider-critical unit file is mock-heavy. NEEDS VERIFICATION against real clients.

### Integration Tests

Status: Present but partly fake.

1. `test_resolve_integration.py` uses real `ResolveService` but mock PackService/Layout and fake providers. See `tests/integration/test_resolve_integration.py:1`, `tests/integration/test_resolve_integration.py:61`, `tests/integration/test_resolve_integration.py:77`.
2. `test_resolve_smoke.py` creates a real `Store(tmp_path)` but still uses MagicMock packs/deps for several scenarios. See `tests/integration/test_resolve_smoke.py:20`, `tests/integration/test_resolve_smoke.py:37`.
3. AI integration file claims real components but uses `MagicMock` for packs/deps and avatar. See `tests/integration/test_ai_resolve_integration.py:42`, grep lines.
4. These tests validate orchestration, not full end-to-end provider correctness.

### Smoke Tests

Status: Present, low-to-medium realism.

1. Store smoke checks service wiring and migration behavior. See `tests/integration/test_resolve_smoke.py:104`.
2. It does not perform a real Civitai import with actual downloaded sidecars in normal CI. NEEDS VERIFICATION.

### E2E Tests

Status: Two categories: mocked Playwright and standalone live scripts.

1. Playwright resolve E2E is explicitly offline and mocked. See `apps/web/e2e/resolve-dependency.spec.ts:1`.
2. Helpers "mock the backend completely." See `apps/web/e2e/helpers/resolve.helpers.ts:245`.
3. These tests cover UI flows but not backend resolver correctness.
4. `tests/e2e_resolve_real.py` is a standalone script for live providers, not a pytest test by default. See `tests/e2e_resolve_real.py:10`, `tests/e2e_resolve_real.py:331`.
5. It exits 0 if there are no provider errors, even if correctness failures occur; `sys.exit(0 if err_count == 0 else 1)` ignores `fail_count`. See `tests/e2e_resolve_real.py:412`.
6. That makes it unsuitable as a hard correctness gate without modification.

## Spec vs Code Gaps

1. API shape mismatch: spec says `/dependencies/{dep_id}/suggest` and `/dependencies/{dep_id}/apply`; code uses pack-level `/suggest-resolution`, `/apply-resolution`, `/apply-manual-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
2. `analyze_previews` option is defined but not exposed in API or used in service. See `src/store/resolve_models.py:135`, `src/store/api.py:2247`, `src/store/resolve_service.py:201`.
3. Preview provider does not filter hints by target kind. See `plans/PLAN-Resolve-Model.md:167`, `src/store/evidence_providers.py:169`.
4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
5. Manual Civitai and HF search tabs are placeholders. See `plans/PLAN-Resolve-Model.md:459`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
7. Candidate cache lacks pack/dep binding. See `plans/PLAN-Resolve-Model.md:888`, `src/store/resolve_service.py:75`.
8. Apply does not update `pack.lock.json`; PackService says it intentionally does not touch lock. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
10. HF search tool is not full tree/model-card inspection and not structured JSON. See `plans/PLAN-Resolve-Model.md:803`, `src/avatar/mcp/store_server.py:1229`.
11. HF hash lookup is verification of an existing selector, not general HF reverse lookup. See `src/store/evidence_providers.py:618`.
12. `HashEvidenceProvider.supports()` returns true for everything and only no-ops later; eligibility is not expressed at support level. See `src/store/evidence_providers.py:63`.
13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
14. Default alias config also uses placeholder zero IDs. See `src/store/models.py:281`.

## Refactor Candidates

1. Consolidate Civitai name/hash enrichment. `PreviewMetaEvidenceProvider` duplicates logic that now exists in `src/store/enrichment.py`. See `src/store/evidence_providers.py:230`, `src/store/enrichment.py:42`.
2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
4. Split AI provider orchestration into two passes: deterministic E1-E6 first, optional AI only if needed. See `src/store/resolve_service.py:216`.
5. Add kind filtering at resolver input boundary, not only extractor helper. See `src/utils/preview_meta_extractor.py:584`.
6. Create a shared HF search client/path for MCP, enrichment, and evidence rather than direct `requests` in MCP plus `HuggingFaceClient` elsewhere. See `src/avatar/mcp/store_server.py:1239`, `src/clients/huggingface_client.py:120`.
7. Decide whether apply should write lock data. Current PackService doc contradicts the earlier spec. See `src/store/pack_service.py:1228`.
8. Extract frontend provider manual search tabs into real components or remove placeholder tabs until implemented.
9. Clarify `pack_service.hf_client` vs `pack_service.huggingface` naming. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`.
10. Turn standalone live E2E scripts into pytest tests with explicit opt-in markers and fail on incorrect top match, not only provider errors. See `tests/e2e_resolve_real.py:412`.

## Open Questions for Owner

1. Is the local `v0.11.0` plan the source of truth, or should the audit compare against an older v0.7.1 from the missing machine?
2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
3. Should Civitai/HF manual tabs be implemented before Release 1, point 1, or are placeholders acceptable?
4. Should preview analysis hints feed back into `suggestResolution()` from the UI, or is preview analysis only informational after import?
5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
6. What is the authoritative HF client attribute on PackService: `hf_client` or `huggingface`?
7. Should AI run alongside deterministic providers when requested, or only after deterministic providers fail to produce Tier 1/2?
8. Should canonical source be required for all remote Civitai/HF candidates before apply?
9. Is HF reverse hash lookup explicitly out of scope due to HF API limitations, with only known-repo LFS verification required?
10. Which test command is the release gate: full pytest, Playwright E2E, live AI scripts, or a curated subset?
11. Are live provider results from `tests/e2e_resolve_real.py` stored anywhere reproducible, or only printed to terminal?
12. Should local import fallback bypass validation if `resolve_service` is unavailable, or should that path hard-fail?

## Release Risk Assessment

1. Backend core is real enough for continued integration work.
2. The UX is not feature-complete for manual Civitai/HF resolution despite tab presence.
3. Preview analysis is useful, but not fully integrated as a first-class resolve source in the UI.
4. AI integration is plausible, but relies on runtime avatar/MCP configuration and prompt behavior; local code alone does not prove live reliability.
5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
6. The largest spec compliance risk is that "Suggest / Apply is the single write path updating pack + lock" is not what PackService currently does.
