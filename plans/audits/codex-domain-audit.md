# Synapse v2 Store Domain Model Audit

Date: 2026-05-02

Scope:

- Primary model file: `src/store/models.py`.
- Related domain/service files: `layout.py`, `__init__.py`, `pack_service.py`,
  `profile_service.py`, `view_builder.py`, `dependency_resolver.py`,
  `inventory_service.py`, `backup_service.py`, `update_service.py`,
  `blob_store.py`, `ui_attach.py`.
- Roadmap context: `plans/audits/CONSOLIDATED-FINDINGS.md`.
- Resolve redesign comparison: `feat/resolve-model-redesign:src/store/resolve_models.py`
  and touched model/write-path shape from that branch.

## Executive Summary

1. The domain model is usable today, but it is carrying several future-facing concepts
   as partially-wired fields: `pack_dependencies`, `ConflictMode`, install packs,
   custom nodes, workflows, backup state sync, and active UI inventory.
2. `Pack` is doing too much: provider origin, dependency manifest, gallery metadata,
   generation metadata, workflow metadata, editability, update behavior, and future
   install-pack behavior are all on one object.
3. Source identity is the biggest foundation risk. There are at least five identity
   surfaces: `Pack.source`, `DependencySelector`, branch `CanonicalSource`,
   `ResolvedArtifact.provider`, and `BlobManifest.origin`.
4. Lock semantics are underspecified. The lock is the only place with resolved hashes
   and download URLs, but update/apply/installation can mutate lock and blob state
   independently. Divergence is normal, not exceptional.
5. `pack_dependencies` is modeled as operational but profile/view composition ignores
   it. API endpoints can create and show a dependency tree, while `use()` and `sync()`
   do not recursively include those dependent packs.
6. `AssetKind.CUSTOM_NODE` exists but is not mapped through `UIKindMap`, ComfyUI YAML
   generation, or attach symlinks. This is a future workflow/custom-node blocker.
7. Current `ProfilePackEntry` does not have `enabled`, despite CLI code referencing it.
   This is model/API drift, not merely an ignored flag.
8. Schema version strings exist in top-level persisted models, but there is no migration
   runner, version dispatch, or compatibility policy in layout load paths.

## Persistence Map

- `state/config.json`: `StoreConfig` with `schema=synapse.config.v2`
  ([models.py:243](../../src/store/models.py#L243), [layout.py:388](../../src/store/layout.py#L388)).
- `state/ui_sets.json`: `UISets` with `schema=synapse.ui_sets.v1`
  ([models.py:314](../../src/store/models.py#L314), [layout.py:399](../../src/store/layout.py#L399)).
- `state/packs/<pack>/pack.json`: `Pack` with `schema=synapse.pack.v2`
  ([models.py:837](../../src/store/models.py#L837), [layout.py:427](../../src/store/layout.py#L427)).
- `state/packs/<pack>/lock.json`: `PackLock` with `schema=synapse.lock.v2`
  ([models.py:976](../../src/store/models.py#L976), [layout.py:441](../../src/store/layout.py#L441)).
- `state/profiles/<profile>/profile.json`: `Profile` with `schema=synapse.profile.v1`
  ([models.py:1017](../../src/store/models.py#L1017), [layout.py:480](../../src/store/layout.py#L480)).
- `data/runtime.json`: `Runtime` with `schema=synapse.runtime.v1`
  ([models.py:1058](../../src/store/models.py#L1058), [layout.py:508](../../src/store/layout.py#L508)).
- `data/blobs/sha256/<prefix>/<sha>`: content-addressed blobs
  ([blob_store.py:88](../../src/store/blob_store.py#L88), [layout.py:229](../../src/store/layout.py#L229)).
- `data/blobs/sha256/<prefix>/<sha>.meta.json`: `BlobManifest`
  ([models.py:1435](../../src/store/models.py#L1435), [blob_store.py:533](../../src/store/blob_store.py#L533)).
- `data/views/<ui>/profiles/<profile>` and `data/views/<ui>/active`: derived view state
  ([layout.py:209](../../src/store/layout.py#L209), [view_builder.py:375](../../src/store/view_builder.py#L375)).
- `data/.synapse.lock`: global file lock
  ([layout.py:160](../../src/store/layout.py#L160), [layout.py:248](../../src/store/layout.py#L248)).

## 1. Inventory Of Domain Objects

### Config And UI Sets

#### `AssetKind`

- Purpose: vocabulary of assets Synapse can expose to UIs
  ([models.py:31](../../src/store/models.py#L31)).
- Fields/values: `checkpoint`, `lora`, `vae`, `controlnet`, `upscaler`, `clip`,
  `text_encoder`, `diffusion_model`, `embedding`, `custom_node`, `unet`, `unknown`
  ([models.py:33](../../src/store/models.py#L33)).
- Invariants: enum values are used as serialized strings; no versioning or aliasing.
- Used by: `Pack.pack_type`, `PackDependency.kind`, `ResolvedArtifact.kind`,
  inventory, view planning, UI attach mapping.
- Persistence: pack JSON, lock JSON, blob manifest, inventory/API responses.
- Design note: `CUSTOM_NODE` is in the enum but missing from `UIKindMap` fields and
  ComfyUI extra path mapping, so it is not fully operational.

#### `ProviderName`

- Purpose: supported provider identity enum
  ([models.py:47](../../src/store/models.py#L47)).
- Fields/values: `civitai`, `huggingface`, `local`, `url`.
- Invariants: used in Pydantic provider/source models; no `unknown` provider.
- Used by: `PackSource`, `ArtifactProvider`, `BlobOrigin`, update fallback.
- Persistence: pack JSON, lock JSON, blob manifest, inventory.
- Design note: fine for current providers, brittle for AI-discovered/community providers
  unless the system accepts schema churn for every new provider.

#### `SelectorStrategy`

- Purpose: resolution strategy for a dependency
  ([models.py:55](../../src/store/models.py#L55)).
- Fields/values: `civitai_file`, `civitai_model_latest`, `huggingface_file`,
  `base_model_hint`, `local_file`, `url_download`.
- Invariants: strategy should imply which selector payload field is populated, but this
  is not enforced by a discriminated union.
- Used by: dependency resolvers, update providers, resolve redesign branch.
- Persistence: pack JSON.
- Design note: current model permits invalid combinations like `strategy=local_file`
  with `civitai` data and no `local_path`.

#### `UpdatePolicyMode` and `UpdatePolicy`

- Purpose: choose whether a dependency is fixed or update-following
  ([models.py:65](../../src/store/models.py#L65), [models.py:385](../../src/store/models.py#L385)).
- Fields: `mode` defaults to `pinned`.
- Invariants: `follow_latest` is considered updatable only when a provider is registered
  for the dependency strategy ([update_service.py:107](../../src/store/update_service.py#L107)).
- Used by: `UpdateService.plan_update`, `UpdateService.is_updatable`.
- Persistence: pack JSON.
- Design note: update behavior is dependency-level, not pack-level. A custom pack with
  a `follow_latest` Civitai dependency is backend-updatable even if UI considers custom
  packs non-updatable.

#### `ConflictMode` and `ConflictConfig`

- Purpose: profile conflict policy
  ([models.py:71](../../src/store/models.py#L71), [models.py:1012](../../src/store/models.py#L1012)).
- Fields/values: `last_wins`, `first_wins`, `strict`; profile default `last_wins`.
- Invariants: only `last_wins` is implemented in `ViewPlan.add_entry`, which replaces
  existing entries with later packs ([view_builder.py:91](../../src/store/view_builder.py#L91)).
- Used by: stored on `Profile`, copied into work profiles
  ([profile_service.py:128](../../src/store/profile_service.py#L128)).
- Persistence: profile JSON.
- Design note: `FIRST_WINS` and `STRICT` are modeled but ignored by view planning.

#### `PackCategory`

- Purpose: pack origin/editability class
  ([models.py:78](../../src/store/models.py#L78)).
- Fields/values: `external`, `custom`, `install`.
- Invariants: comments imply editability and installation semantics, but services do
  not enforce most of that.
- Used by: imported Civitai packs are `external` ([pack_service.py:510](../../src/store/pack_service.py#L510));
  API-created custom packs are `custom` ([api.py:3310](../../src/store/api.py#L3310)).
- Persistence: pack JSON.
- Design note: `INSTALL` is not just a category. It implies scripts, process lifecycle,
  UI roots, trust, logs, and health state. It should probably be a subtype object.

#### `UIKindMap`

- Purpose: maps asset kinds to UI-specific model folders
  ([models.py:121](../../src/store/models.py#L121)).
- Fields: `checkpoint`, `lora`, `vae`, `embedding`, `controlnet`, `upscaler`,
  `clip`, `text_encoder`, `diffusion_model`, `unet`.
- Invariants: `get_path()` maps by `AssetKind.value`
  ([models.py:134](../../src/store/models.py#L134)).
- Used by: `ViewBuilder.compute_plan`, `UIAttacher`, default UI config.
- Persistence: config JSON.
- Design note: missing `custom_node` and `unknown`. ViewBuilder falls back to
  `models/<kind>`, but `UIAttacher` skips unmapped kinds, so attach is inconsistent
  ([view_builder.py:85](../../src/store/view_builder.py#L85), [ui_attach.py:333](../../src/store/ui_attach.py#L333)).

#### `UIConfig`

- Purpose: known UI names and per-UI kind maps
  ([models.py:139](../../src/store/models.py#L139)).
- Fields: `known`, `kind_map`.
- Invariants: default known UIs are `comfyui`, `forge`, `a1111`, `sdnext`.
- Used by: `StoreConfig`, runtime initialization, view planning, attach.
- Persistence: config JSON.
- Design note: UI roots live outside this model in app config passed to UIAttacher,
  producing a split between store state and application config.

#### `ProviderConfig`

- Purpose: provider defaults for file selection
  ([models.py:199](../../src/store/models.py#L199)).
- Fields: `primary_file_only_default`, `preferred_ext`.
- Invariants: default Civitai/HF provider configs are written by `StoreConfig.create_default`
  ([models.py:257](../../src/store/models.py#L257)).
- Used by: limited. NEEDS VERIFICATION: current resolver code mostly uses selector
  constraints rather than provider defaults directly.
- Persistence: config JSON.

#### `CivitaiSelectorConfig`, `BaseModelAliasSelector`, `BaseModelAlias`

- Purpose: configured aliases for base model hints
  ([models.py:205](../../src/store/models.py#L205), [models.py:214](../../src/store/models.py#L214),
  [models.py:220](../../src/store/models.py#L220)).
- Fields: Civitai `model_id`, `version_id`, `file_id`; alias kind/default filename/selector.
- Invariants: default aliases currently use placeholder zeros
  ([models.py:274](../../src/store/models.py#L274)).
- Used by: `_create_base_model_dependency`, `BaseModelHintResolver`
  ([pack_service.py:603](../../src/store/pack_service.py#L603), [dependency_resolver.py:209](../../src/store/dependency_resolver.py#L209)).
- Persistence: config JSON.
- Design note: placeholder zero IDs are normal config data in main, while resolve
  redesign validation rejects zero IDs ([resolve_validation.py branch:64]).

#### `ConfigDefaults`, `BackupConfig`, `StoreConfig`

- Purpose: global defaults, backup config, root persisted config
  ([models.py:227](../../src/store/models.py#L227), [models.py:235](../../src/store/models.py#L235),
  [models.py:243](../../src/store/models.py#L243)).
- Fields: default UI set, conflict mode, active/use base defaults, backup path/options,
  providers, base aliases.
- Invariants: `schema_` aliases to JSON `schema`; layout writes with aliases
  ([layout.py:322](../../src/store/layout.py#L322)).
- Used by: Store facade defaults, runtime init, backup service, UI attach.
- Persistence: `state/config.json`.
- Design note: `defaults.active_profile` and `defaults.use_base` do not appear to be
  authoritative for runtime, which is in `data/runtime.json`.

#### `UISets`

- Purpose: named sets of UI targets
  ([models.py:314](../../src/store/models.py#L314)).
- Fields: `schema`, `sets`.
- Invariants: default sets include named and singleton sets
  ([models.py:321](../../src/store/models.py#L321)).
- Used by: Store facade `get_ui_targets`, profile service, view builder.
- Persistence: `state/ui_sets.json`.
- Design note: default UI set name lives in `StoreConfig.defaults.ui_set`, while set
  members live in `UISets`. That split is acceptable but needs migration discipline.

### Pack, Source, Dependencies

#### `CivitaiSelector`

- Purpose: Civitai dependency selector
  ([models.py:350](../../src/store/models.py#L350)).
- Fields: `model_id`, optional `version_id`, optional `file_id`.
- Invariants: current main does not reject `0`; branch validation does.
- Used by: dependency resolver, import, update, resolve branch.
- Persistence: pack JSON.
- Design note: Civitai model/version/file identity is spread across this selector,
  `PackSource`, `ArtifactProvider`, `BlobOrigin`, and `ModelInfo.civitai_air`.

#### `HuggingFaceSelector`

- Purpose: HuggingFace file selector
  ([models.py:359](../../src/store/models.py#L359)).
- Fields: `repo_id`, `filename`, optional `revision`, optional `subfolder`.
- Invariants: strategy should require repo and filename; not enforced in main.
- Used by: `HuggingFaceResolver`
  ([dependency_resolver.py:270](../../src/store/dependency_resolver.py#L270)).
- Persistence: pack JSON.
- Design note: HF path can be represented as `subfolder + filename`; lock stores
  `repo_id`, `filename`, `revision`, but not `subfolder` in `ArtifactProvider`.

#### `SelectorConstraints`

- Purpose: file selection filters
  ([models.py:367](../../src/store/models.py#L367)).
- Fields: `primary_file_only`, `file_ext`, `base_model_hint`.
- Invariants: resolver helper applies primary and extension filters
  ([dependency_resolver.py:344](../../src/store/dependency_resolver.py#L344)).
- Used by: Civitai latest/file and base model resolver path.
- Persistence: pack JSON.
- Design note: `base_model_hint` duplicates `Pack.base_model`, dependency `selector.base_model`,
  and branch candidate `base_model`.

#### `DependencySelector`

- Purpose: strategy plus provider-specific selector payload
  ([models.py:374](../../src/store/models.py#L374)).
- Fields: `strategy`, optional `civitai`, `huggingface`, `base_model`, `url`,
  `local_path`, `constraints`.
- Invariants: no discriminator validation; impossible and incomplete states are allowed.
- Used by: all dependency resolution and update paths.
- Persistence: pack JSON.
- Design note: branch adds `canonical_source` to this object
  ([branch models.py:381](../../src/store/models.py#L381) via git show). That is a
  good direction for local/URL deps with remote provenance, but it makes the selector
  both "how to obtain" and "what this really is".

#### `ExposeConfig`

- Purpose: UI-facing filename and trigger words
  ([models.py:395](../../src/store/models.py#L395)).
- Fields: `filename`, `trigger_words`.
- Invariants: filename cannot start with dot, include path separators, nulls, or `..`
  ([models.py:108](../../src/store/models.py#L108)).
- Used by: view paths, inventory display names, blob manifest original filename.
- Persistence: pack JSON.
- Design note: `filename` is part of view identity and conflict behavior; changing it
  changes runtime exposed paths but not the blob.

#### `PackDependency`

- Purpose: one asset dependency inside a pack
  ([models.py:406](../../src/store/models.py#L406)).
- Fields: `id`, `kind`, `required`, `selector`, `update_policy`, `expose`, `description`.
- Invariants: `id` safe-name validation; pack validates unique IDs
  ([models.py:416](../../src/store/models.py#L416), [models.py:894](../../src/store/models.py#L894)).
- Used by: import, resolve, install, update, view build, inventory.
- Persistence: pack JSON.
- Design note: `required` is ignored by `resolve_pack`, which records unresolved deps
  without distinguishing required vs optional ([pack_service.py:1153](../../src/store/pack_service.py#L1153)).

#### `PackSource`

- Purpose: source information for the pack as a whole
  ([models.py:422](../../src/store/models.py#L422)).
- Fields: `provider`, optional Civitai `model_id`, optional `version_id`, optional `url`.
- Invariants: required on every `Pack`.
- Used by: search result/provider display, import/custom creation.
- Persistence: pack JSON.
- Design flaw: this is per-pack, but dependencies are per-artifact. A custom pack can
  contain Civitai, HF, local, and URL dependencies simultaneously. `Pack.source` then
  becomes either misleading or merely "creation source".

#### `PackResources`

- Purpose: keep-in-git flags for pack resources
  ([models.py:432](../../src/store/models.py#L432)).
- Fields: `previews_keep_in_git`, `workflows_keep_in_git`.
- Used by: stored on `Pack`; NEEDS VERIFICATION for enforcement.
- Persistence: pack JSON.
- Design note: flags exist, but resource path conventions are split:
  previews under `resources/previews`, workflows at `pack_dir/workflows`
  ([layout.py:181](../../src/store/layout.py#L181)).

#### `PackDependencyRef`

- Purpose: pack-to-pack dependency edge
  ([models.py:438](../../src/store/models.py#L438)).
- Fields: `pack_name`, `required`, `version_constraint`.
- Invariants: safe pack name; `Pack` validates unique names and no self-reference
  ([models.py:902](../../src/store/models.py#L902)).
- Used by: API CRUD/status/tree and reverse update impact
  ([api.py:2963](../../src/store/api.py#L2963), [update_service.py:256](../../src/store/update_service.py#L256)).
- Persistence: pack JSON.
- Design flaw: view/profile composition ignores this field. `_load_packs_for_profile`
  only loads direct `profile.packs` ([profile_service.py:473](../../src/store/profile_service.py#L473)).

#### `GenerationParameters`

- Purpose: generation settings from Civitai or AI
  ([models.py:460](../../src/store/models.py#L460)).
- Fields: sampler/scheduler/steps/cfg/size/seed/LoRA strength/hires fields plus extras.
- Invariants: `extra="allow"` and custom serializer drops `None`
  ([models.py:477](../../src/store/models.py#L477), [models.py:763](../../src/store/models.py#L763)).
- Used by: Civitai import AI extraction
  ([pack_service.py:536](../../src/store/pack_service.py#L536)).
- Persistence: pack JSON.
- Design note: this model has a lot of AI normalization logic inside the core domain
  model. Consider moving normalization to an adapter and keeping the persisted model
  simpler.

#### `ModelInfo`

- Purpose: extended model metadata
  ([models.py:776](../../src/store/models.py#L776)).
- Fields: model type/base model/trigger words/hash fields/AIR/stats/published/strength.
- Used by: Civitai import metadata, UI details.
- Persistence: pack JSON.
- Design note: contains source evidence like hashes and Civitai AIR, overlapping
  with lock provider/hash identity.

#### `WorkflowInfo`

- Purpose: metadata for included ComfyUI workflows
  ([models.py:794](../../src/store/models.py#L794)).
- Fields: `name`, `filename`, optional description/source URL, `is_default`.
- Used by: pack JSON/UI workflow features.
- Persistence: pack JSON, with workflow files under pack directories.
- Design note: workflow JSON is not modeled as first-class content. There is no
  dependency graph extracted from workflow nodes.

#### `PreviewInfo`

- Purpose: image/video preview metadata
  ([models.py:803](../../src/store/models.py#L803)).
- Fields: filename, URL, NSFW, dimensions, metadata dict, media type, video details.
- Invariants: media type is `Literal['image','video','unknown']`
  ([models.py:819](../../src/store/models.py#L819)).
- Used by: import, gallery, resolve preview analysis.
- Persistence: pack JSON plus files under resources/previews.
- Design note: preview `meta` is raw `Dict[str, Any]`, which is flexible but hides
  the evidence contract needed by resolve/workflow import.

#### `Pack`

- Purpose: central persisted pack document
  ([models.py:837](../../src/store/models.py#L837)).
- Fields: schema, name, pack type/category/source, dependencies, pack dependencies,
  resources, previews, cover, version/description/base/author/tags/user tags/trigger
  words, created timestamp, parameters, model info, workflows.
- Invariants: safe name; unique dependency IDs; unique pack deps; no self pack dep.
- Used by: almost every store service.
- Persistence: `state/packs/<pack>/pack.json`.
- Design flaw: `Pack` is simultaneously package metadata, model import metadata,
  dependency manifest, gallery/workflow container, update policy holder, and future
  installer descriptor. Extensions will add more unrelated optional fields unless
  it is split into typed facets.

### Lock And Resolution State

#### `ArtifactProvider`

- Purpose: provider information for resolved artifacts
  ([models.py:924](../../src/store/models.py#L924)).
- Fields: provider enum; Civitai IDs; HF repo/filename/revision.
- Used by: lock, inventory origin, blob manifest origin.
- Persistence: lock JSON.
- Design note: missing `subfolder`, URL, local original path, and source URL details.

#### `ArtifactDownload`

- Purpose: download URLs for a resolved artifact
  ([models.py:937](../../src/store/models.py#L937)).
- Fields: `urls`.
- Used by: `install_pack`, update pending downloads.
- Persistence: lock JSON.
- Design note: no auth requirement, expiry, mirror priority, method, headers, or source
  evidence. Civitai signed URLs may age out NEEDS VERIFICATION.

#### `ArtifactIntegrity`

- Purpose: integrity verification status
  ([models.py:942](../../src/store/models.py#L942)).
- Fields: `sha256_verified`.
- Used by: lock and install mutation.
- Persistence: lock JSON.
- Design note: hash itself lives on `ResolvedArtifact.sha256`; integrity only stores a
  boolean. It cannot distinguish "provider hash trusted" from "download verified".

#### `ResolvedArtifact`

- Purpose: fully or partially resolved downloadable artifact
  ([models.py:947](../../src/store/models.py#L947)).
- Fields: kind, optional SHA256, size, provider, download, integrity.
- Used by: lock, view build, install, inventory, update.
- Persistence: lock JSON.
- Design note: `sha256` can be absent for HF/URL until download; install mutates lock
  after download when hash was unknown ([pack_service.py:1288](../../src/store/pack_service.py#L1288)).

#### `ResolvedDependency`

- Purpose: lock entry tying dependency ID to artifact
  ([models.py:963](../../src/store/models.py#L963)).
- Fields: `dependency_id`, `artifact`.
- Invariants: no validation that `dependency_id` exists in pack JSON.
- Used by: lock, view build, inventory, updates.
- Persistence: lock JSON.

#### `UnresolvedDependency`

- Purpose: lock entry for failed resolution
  ([models.py:969](../../src/store/models.py#L969)).
- Fields: `dependency_id`, `reason`, `details`.
- Used by: resolve/status.
- Persistence: lock JSON.
- Design note: does not carry required/optional severity, retry strategy, or candidate
  evidence.

#### `PackLock`

- Purpose: resolved state for a pack
  ([models.py:976](../../src/store/models.py#L976)).
- Fields: schema, pack name, resolved timestamp, resolved and unresolved lists.
- Invariants: `is_fully_resolved()` only checks no unresolved entries, not that every
  pack dependency has a resolved entry ([models.py:993](../../src/store/models.py#L993)).
- Used by: install, view build, inventory, update, status.
- Persistence: `state/packs/<pack>/lock.json`.
- Design flaw: no generation/source fingerprint. It does not record which `pack.json`
  dependency definitions it was resolved against, so stale locks are hard to detect.

### Profiles, Runtime, Reports

#### `ProfilePackEntry`

- Purpose: ordered pack entry in a profile
  ([models.py:1002](../../src/store/models.py#L1002)).
- Fields: `name`.
- Invariants: safe name.
- Used by: `Profile.packs`, work profile creation, view planning.
- Persistence: profile JSON.
- Design note: current model has no `enabled`, but CLI references `pack_entry.enabled`
  ([cli.py:527](../../src/store/cli.py#L527)). That is a real drift/bug.

#### `Profile`

- Purpose: ordered collection of packs plus conflict config
  ([models.py:1017](../../src/store/models.py#L1017)).
- Fields: schema, name, conflicts, packs.
- Invariants: safe name; `add_pack` deduplicates then appends
  ([models.py:1031](../../src/store/models.py#L1031)).
- Used by: global/work profiles, view build, runtime activation.
- Persistence: profile JSON.
- Design note: profile has no direct `pack_dependencies` field. Pack-to-pack dependencies
  are not expanded here.

#### `UIRuntimeState` and `Runtime`

- Purpose: runtime profile stack per UI
  ([models.py:1053](../../src/store/models.py#L1053), [models.py:1058](../../src/store/models.py#L1058)).
- Fields: stack defaults to `["global"]`; runtime maps UI name to state.
- Invariants: pop refuses to remove base stack item; set_stack can set any list.
- Used by: `use`, `back`, status, profiles page.
- Persistence: `data/runtime.json`.
- Design note: runtime stores profile names without referential integrity. If a profile
  is deleted, stack entries can point to missing profiles until commands handle it.

#### `MissingBlob`, `UnresolvedReport`, `ShadowedEntry`, `StatusReport`

- Purpose: status/diagnostic response models
  ([models.py:1110](../../src/store/models.py#L1110), [models.py:1118](../../src/store/models.py#L1118),
  [models.py:1126](../../src/store/models.py#L1126), [models.py:1134](../../src/store/models.py#L1134)).
- Fields: pack/dependency/blob data, unresolved reason, shadowed winner/loser, active UI map.
- Used by: Store status/doctor, profile use result, CLI/API.
- Persistence: response only.
- Design note: `Store.status()` always returns `shadowed=[]` even though `ViewBuilder`
  computes shadowed entries ([__init__.py:951](../../src/store/__init__.py#L951)).

#### Update, Doctor, Search, Use/Back/Reset/Delete Models

- `UpdateChange`, `UpdateCandidate`, `AmbiguousUpdate`, `PendingDownload`, `UpdatePlan`,
  `UpdateOptions`, `UpdateResult`, `BatchUpdateResult`
  ([models.py:1144](../../src/store/models.py#L1144)).
- Purpose: update planning/application DTOs.
- Persistence: response only, except updates mutate lock/pack.
- Design note: `UpdateCandidate.provider` is raw `str` while providers elsewhere use
  `ProviderName` ([models.py:1155](../../src/store/models.py#L1155)).
- `DoctorActions`, `DoctorReport`
  ([models.py:1216](../../src/store/models.py#L1216)).
- Purpose: diagnostic/repair response.
- Design note: DB rebuild is explicitly placeholder in Store doctor
  ([__init__.py:1030](../../src/store/__init__.py#L1030)).
- `SearchResultItem`, `SearchResult`
  ([models.py:1235](../../src/store/models.py#L1235)).
- Purpose: search response.
- `UseResult`, `BackResult`, `ResetResult`, `DeleteResult`
  ([models.py:1253](../../src/store/models.py#L1253)).
- Purpose: command response DTOs.
- Design note: `UseResult.shadowed` is populated during `ProfileService.use`, but
  general status loses it unless views are rebuilt ([profile_service.py:240](../../src/store/profile_service.py#L240)).

### Inventory, Blob, Backup, Sync

#### `BlobStatus`, `BlobLocation`

- Purpose: inventory state enums
  ([models.py:1296](../../src/store/models.py#L1296), [models.py:1304](../../src/store/models.py#L1304)).
- Fields: referenced/orphan/missing/backup_only; local_only/backup_only/both/nowhere.
- Used by: inventory, cleanup, impact analysis.
- Persistence: response only.
- Design note: `BlobStatus.BACKUP_ONLY` means referenced but not local in service code;
  backup-only orphan is emitted as `ORPHAN` with `location=BACKUP_ONLY`
  ([inventory_service.py:170](../../src/store/inventory_service.py#L170)).

#### `BlobOrigin`, `PackReference`

- Purpose: origin and pack reference metadata
  ([models.py:1312](../../src/store/models.py#L1312), [models.py:1324](../../src/store/models.py#L1324)).
- Fields: provider IDs/repo filename; pack/dependency/kind/expose/size/origin.
- Used by: inventory and blob manifest creation.
- Persistence: response only and embedded in `BlobManifest`.
- Design note: mirrors `ArtifactProvider`; should probably be a shared canonical source
  or derived view.

#### `InventoryItem`, `BackupStats`, `InventorySummary`, `InventoryResponse`

- Purpose: blob inventory response
  ([models.py:1334](../../src/store/models.py#L1334), [models.py:1359](../../src/store/models.py#L1359),
  [models.py:1375](../../src/store/models.py#L1375), [models.py:1391](../../src/store/models.py#L1391)).
- Fields: hash/kind/display/size/location/status/refs/origin/active UIs/verification/summary.
- Used by: inventory endpoints and cleanup.
- Persistence: response only.
- Design note: `active_in_uis` is always `[]` in service construction with TODO
  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).

#### `CleanupResult`, `MigrateManifestsResult`, `ImpactAnalysis`

- Purpose: inventory mutation/impact responses
  ([models.py:1398](../../src/store/models.py#L1398), [models.py:1408](../../src/store/models.py#L1408),
  [models.py:1418](../../src/store/models.py#L1418)).
- Used by: cleanup, manifest migration, delete guards.
- Persistence: response only.

#### `BlobManifest`

- Purpose: write-once orphan metadata
  ([models.py:1435](../../src/store/models.py#L1435)).
- Fields: integer version, created timestamp, original filename, kind, origin.
- Invariants: write-once; `BlobStore.write_manifest` never overwrites
  ([blob_store.py:560](../../src/store/blob_store.py#L560)).
- Used by: inventory display for orphan blobs, installation manifest creation.
- Persistence: `data/blobs/sha256/<prefix>/<sha>.meta.json`.
- Design note: "immutable" is enforced by write path, but no hash/source authority is
  stored beyond filename/kind/origin.

#### Backup And State Sync Models

- `BackupStatus`, `BackupOperationResult`, `BackupDeleteResult`
  ([models.py:1454](../../src/store/models.py#L1454)).
- Purpose: backup connection and operation responses.
- `SyncItem`, `SyncResult`
  ([models.py:1489](../../src/store/models.py#L1489)).
- Purpose: blob backup push/pull result; `direction` is raw string.
- `StateSyncStatus`, `StateSyncItem`, `StateSyncSummary`, `StateSyncResult`
  ([models.py:1517](../../src/store/models.py#L1517)).
- Purpose: state directory backup sync model.
- Design note: `StateSyncStatus.CONFLICT` exists but `_analyze_state_file` returns
  `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).

#### `APIResponse`

- Purpose: generic API wrapper
  ([models.py:1561](../../src/store/models.py#L1561)).
- Fields: `ok`, optional result/error.
- Used by: API layer where adopted.
- Persistence: response only.

### Related Dataclasses Outside `models.py`

#### `PreviewDownloadConfig`, `DownloadProgressInfo`

- Purpose: pack import preview/download operation DTOs
  ([pack_service.py:72](../../src/store/pack_service.py#L72), [pack_service.py:93](../../src/store/pack_service.py#L93)).
- Design note: service-local Pydantic models with `Literal` status.

#### `ViewEntry`, `ViewPlan`, `BuildReport`

- Purpose: derived view plan/build report
  ([view_builder.py:51](../../src/store/view_builder.py#L51)).
- Fields: pack/dependency/kind/expose/hash/destination; shadowed and missing lists.
- Persistence: not persisted, except symlink filesystem output.
- Design note: this is where conflict resolution actually happens, not in `Profile`.

#### `AttachResult`

- Purpose: UI attach/detach result DTO
  ([ui_attach.py:34](../../src/store/ui_attach.py#L34)).
- Persistence: response only.
- Design note: method is raw string.

## 2. Enum Audit

### `PackCategory`

- Current values cover origin/editability in a coarse way.
- `CUSTOM` can cover workflow-imported packs if workflow import is just user-owned
  metadata plus dependencies.
- A new `WORKFLOW` category is useful only if workflow packs have distinct lifecycle,
  e.g. extracted graph, workflow JSON validation, dependency suggestion, and UI wizard
  state.
- `INSTALL` should not remain only a category once executable behavior is added.
  It needs a typed install facet with trust, script manifest, environment state, logs,
  process controls, and UI root outputs.
- Recommendation: keep `PackCategory` small as origin/editability, add subtype/facet
  models: `WorkflowFacet`, `InstallFacet`, possibly `ExternalSourceFacet`.

### `AssetKind`

- Missing or weakly wired: custom node folders, workflows, UI install environments,
  extensions/plugins, configs.
- `CUSTOM_NODE` exists but is not covered by `UIKindMap` and `_kind_to_comfyui_name`
  ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
- `WORKFLOW` is not an asset kind; workflows are separate `WorkflowInfo`.
- A pack can mix dependency kinds because `Pack.dependencies` is a list of per-dep
  kinds, while `Pack.pack_type` is one top-level kind. This top-level `pack_type` is
  therefore descriptive, not exhaustive.
- Recommendation: rename or document `Pack.pack_type` as `primary_kind`, and add asset
  kinds only for assets that become blobs/views. Keep workflows separate if they are
  pack resources, not model files.

### `ProviderName`

- Current provider enum covers Civitai, HuggingFace, local, URL.
- Future providers can be represented as `URL` only if update/canonical semantics are
  intentionally lost.
- Recommendation: use `ProviderName` for known provider integrations, but add
  `ProviderName.UNKNOWN` or a `provider_id: str` plus typed payload union if plugins
  can introduce providers.

### `SelectorStrategy`, `UpdatePolicyMode`, `ConflictMode`

- `SelectorStrategy` is fully registered in `PackService._ensure_resolvers`
  ([pack_service.py:1193](../../src/store/pack_service.py#L1193)).
- `UpdatePolicyMode` is wired for Civitai latest where provider registered
  ([__init__.py:246](../../src/store/__init__.py#L246)).
- `ConflictMode` is not fully wired. `ViewPlan.add_entry` implements last-wins only.
- Recommendation: either remove `FIRST_WINS`/`STRICT` until implemented or make
  `ViewBuilder.compute_plan` branch on `profile.conflicts.mode`.

### String-Typed Enums Hiding In Models

- `PreviewInfo.media_type` is `Literal['image','video','unknown']`
  ([models.py:819](../../src/store/models.py#L819)).
- `DownloadProgressInfo.status` is a `Literal`
  ([pack_service.py:115](../../src/store/pack_service.py#L115)).
- `SyncResult.direction` and `StateSyncResult.direction` are raw strings
  ([models.py:1500](../../src/store/models.py#L1500), [models.py:1550](../../src/store/models.py#L1550)).
- `AttachResult.method` is a raw string
  ([ui_attach.py:39](../../src/store/ui_attach.py#L39)).
- Recommendation: promote repeated public response literals to enums if clients depend
  on them.

## 3. Pack Shape Audit

### Cohesion

- `Pack` fields are not cohesive around one lifecycle.
- External model import fields: `source`, `model_info`, `previews`, `base_model`,
  provider tags, trigger words.
- Custom pack fields: `user_tags`, editable description, custom dependencies, workflows.
- Install pack future fields are absent despite `PackCategory.INSTALL`.
- Workflow future fields are partial: workflow metadata exists, but not imported workflow
  JSON as typed graph/source.

### `Pack.source`

- `Pack.source` is required and per-pack ([models.py:843](../../src/store/models.py#L843)).
- For Civitai imports, it records model/version/url ([pack_service.py:514](../../src/store/pack_service.py#L514)).
- For custom packs, API writes `provider=LOCAL` even when future dependencies may be
  remote ([api.py:3314](../../src/store/api.py#L3314)).
- Design recommendation: reinterpret as `creation_source` or remove as authoritative
  source. Dependency source identity should live per dependency/candidate/lock.

### `pack_dependencies`

- Model validation prevents duplicate names and self-reference
  ([models.py:902](../../src/store/models.py#L902)).
- API can add/remove/status/tree pack dependencies
  ([api.py:3036](../../src/store/api.py#L3036), [api.py:3170](../../src/store/api.py#L3170)).
- Update service can find reverse dependency impact
  ([update_service.py:256](../../src/store/update_service.py#L256)).
- Profile/view runtime does not compose them
  ([profile_service.py:483](../../src/store/profile_service.py#L483), [view_builder.py:236](../../src/store/view_builder.py#L236)).
- `version_constraint` is stored but not enforced.
- Recommendation: decide whether these are operational. If yes, add dependency expansion
  service with cycle detection, optional/required policy, version checks, and stable
  view order.

### Pack vs Lock

- Pack is desired state; lock is resolved artifact state.
- Pack dependency selector can say "Civitai latest"; lock says exactly which version/file/hash.
- Lock can be updated without pack selector changing (`UpdateService.apply_update`)
  ([update_service.py:346](../../src/store/update_service.py#L346)).
- Pack can be changed without lock changing in resolve redesign apply path
  ([branch pack_service.py:1217](../../src/store/pack_service.py#L1217) via git show).
- Recommendation: add a lock `pack_fingerprint` or per-dependency selector fingerprint
  so stale locks are visible.

### Hash Authority

- SHA256 appears in `ModelInfo.hash_sha256`, `ResolvedArtifact.sha256`,
  `PendingDownload.sha256`, `InventoryItem.sha256`, `BlobManifest` path, and physical
  blob path.
- The authoritative content address should be the blob path/hash and lock artifact hash.
- `ModelInfo.hash_sha256` should be treated as provider metadata, not runtime authority.
- Divergence paths:
  - lock has hash but blob missing;
  - HF/URL lock has no hash until install mutates it;
  - manifest exists for old origin after pack dependency renamed;
  - pack model info hash differs from resolved dependency hash.

### Storage Separation

- `pack.json`: user/provider metadata and desired dependencies.
- `lock.json`: resolved artifacts and download URLs.
- `BlobManifest`: orphan fallback display metadata.
- This separation is conceptually good.
- Missing piece: explicit derivation metadata tying lock and manifest back to pack
  dependency version/fingerprint.

## 4. Dependency Model Audit

- `PackDependency` is desired dependency.
- `PackDependencyRef` is pack-to-pack edge.
- `ResolvedDependency` is lock result.
- Branch `ResolutionCandidate` is suggestion DTO
  ([branch resolve_models.py:77](../../src/store/models.py#L77) via git show).
- Branch `CanonicalSource` is remote identity independent of install strategy
  ([branch models.py:381](../../src/store/models.py#L381) via git show).

Design overlaps:

- `DependencySelector.civitai` and `CanonicalSource` both can carry Civitai model/version/file.
- `HuggingFaceSelector` and `CanonicalSource` both can carry HF repo/path/revision.
- `ArtifactProvider` and `BlobOrigin` repeat provider identity.
- `PackSource` overlaps only for external single-source packs.

Unresolved expression:

- Main supports unresolved deps by leaving them in pack JSON and recording lock
  `UnresolvedDependency`.
- It does not need placeholders in normal selectors, but current defaults and branch
  evidence providers do use `model_id=0` placeholders
  ([models.py:280](../../src/store/models.py#L280), [branch evidence_providers.py:198] via git show).
- Recommendation: introduce explicit "unresolved candidate" or "hint" objects instead
  of invalid selectors.

Identity stability:

- `dep.id` is stable unless user edits it. Lock depends on this string.
- No immutable dependency UUID exists.
- Rename/edit can orphan lock entries or break update history.
- Recommendation: add immutable `dependency_uid` or forbid ID rename after lock exists.

Multi-source candidates:

- Branch candidates can represent multiple candidates per dependency.
- PackDependency stores only one selected selector.
- There is no first-class "alternatives" field. That is probably correct for pack JSON;
  alternatives belong in candidate cache or review state.

Required/optional:

- `PackDependency.required` exists.
- `PackDependencyRef.required` exists.
- Resolve/install/status do not deeply honor optional severity.
- Recommendation: optional unresolved deps should not make `PackLock.is_fully_resolved`
  false unless policy says so, or lock should expose `required_unresolved`.

## 5. Source, Evidence, Candidate

- Current main has no `CanonicalSource`; resolve branch adds it to `DependencySelector`.
- Branch candidate shape has `selector_data`, `canonical_source`, evidence groups,
  display fields, provider, and base model ([branch resolve_models.py:77] via git show).
- Branch apply reconstructs selector from `candidate.selector_data` and passes candidate
  `canonical_source` to pack service ([branch resolve_service.py:289] via git show).
- Branch pack service writes selector/canonical source only to `pack.json` and explicitly
  does not touch lock ([branch pack_service.py:1226] via git show).

Canonical reference proposal:

- For blob identity: SHA256.
- For Civitai source: `model_id + version_id + file_id` where available, plus SHA256
  after resolution/download.
- For HuggingFace source: `repo_id + revision + subfolder + filename`, with SHA256 when
  available.
- For local source: blob SHA256 plus optional original path as non-authoritative evidence.
- For URL source: URL plus resolved SHA256; URL alone is not stable.

Recommendation:

- Keep `DependencySelector` as "how to resolve/download now".
- Add a separate per-dependency `canonical_source` field or nested `SourceIdentity`
  next to selector, not inside strategy payload, unless local/URL tracking requires it.
- Replace `PackSource` with `creation_source` or a `PackOrigin` object that does not
  pretend to identify every dependency.

## 6. Profile, Runtime, View

- `Profile.packs` is the only profile composition list
  ([models.py:1022](../../src/store/models.py#L1022)).
- There is no `Profile.pack_dependencies`.
- Work profiles are named `work__<pack>` ([profile_service.py:83](../../src/store/profile_service.py#L83)).
- Work profile creation copies base packs except target, then appends target for
  last-wins behavior ([profile_service.py:134](../../src/store/profile_service.py#L134)).
- Work profiles are updated on reuse, but no general garbage collection is evident in
  the audited service.
- Runtime stack stores profile names per UI; `use()` pushes, `back()` pops
  ([profile_service.py:248](../../src/store/profile_service.py#L248), [profile_service.py:303](../../src/store/profile_service.py#L303)).
- If underlying profile is deleted, runtime can hold stale names. `back(sync=True)` catches
  `ProfileNotFoundError`; other flows may silently fail or activate stale views.
- `ShadowedEntry` is computed in `ViewPlan.add_entry`; `BuildReport` carries it; `UseResult`
  receives it; `Store.status()` does not compute it and returns empty.

Recommendation:

- Add `ProfileEntry.enabled` only if view builder honors it.
- Implement `ConflictMode` or collapse it.
- Add a profile stack repair/validation command for deleted profiles.
- Persist or recompute shadowed entries consistently. Since views are derived, recompute
  from current profile/locks when status asks for shadowed, or store build reports.

## 7. Inventory, Blob, Backup

- Inventory is derived live from physical blobs, backup blobs, and pack locks
  ([inventory_service.py:79](../../src/store/inventory_service.py#L79)).
- Reference map scans all pack locks and maps hash to pack references
  ([inventory_service.py:221](../../src/store/inventory_service.py#L221)).
- Orphan display falls back to write-once blob manifest
  ([inventory_service.py:340](../../src/store/inventory_service.py#L340)).
- Active UI tracking is modeled but not implemented (`active_in_uis=[]`)
  ([inventory_service.py:377](../../src/store/inventory_service.py#L377)).
- Backup blob sync is explicitly one-way by raw `direction` string `to_backup` or
  `from_backup` ([backup_service.py:597](../../src/store/backup_service.py#L597)).
- State sync claims `bidirectional`, but conflict detection is weak: differing files
  become `MODIFIED`, not `CONFLICT` ([backup_service.py:1004](../../src/store/backup_service.py#L1004)).

Recommendation:

- Treat inventory active UI as derived, not stored.
- Model sync direction as enum.
- Define backup as push/pull, not mirror, unless deletion propagation is implemented.
- For state sync, either remove `CONFLICT` or implement a base/snapshot marker.

## 8. Resolve Redesign Integration

- Branch `ResolutionCandidate` fits as a transient DTO, not as persisted pack state.
- Branch `CanonicalSource` should become the shared source identity primitive, but it
  should be reconciled with `PackSource`, `ArtifactProvider`, and `BlobOrigin`.
- Field naming mismatches:
  - current `PackSource.provider: ProviderName`;
  - branch `CanonicalSource.provider: Literal["civitai","huggingface"]`;
  - update candidate `provider: str`;
  - candidate `provider` literal.
- Applying a candidate likely needs:
  - per-dependency canonical source;
  - dependency selector update;
  - optional expose filename/trigger update policy;
  - lock invalidation or lock update;
  - candidate evidence audit trail only if product wants explainability.
- Branch apply currently ignores `lock_entry` and does not update lock
  ([branch pack_service.py:1222] via git show).

Recommendation:

- Decide now whether apply updates lock. If not, make stale lock an explicit state in UI.
- Make all candidates either applyable selectors or non-applyable hints. No `model_id=0`.
- Bind candidate cache to `pack_name` and `dep_id`.

## 9. Custom, Install, Workflow Pack Futures

Custom packs:

- Current `Pack` can represent custom packs without dependencies if source is `LOCAL`
  and dependencies default empty.
- API create currently calls `store.layout.pack_path`, which does not exist; layout has
  `pack_dir` ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
- Custom packs with mixed sources are poorly represented by per-pack `source`.

Install packs:

- `PackCategory.INSTALL` exists but no domain model for scripts, install dir, UI root,
  health, ports, logs, trust, or process state.
- Recommended fields/facets:
  - `install_manifest`: scripts with hash, interpreter, args, environment policy;
  - `install_dir`: local path controlled by store;
  - `ui_roots`: produced UI target roots;
  - `log_paths`: stdout/stderr/install logs;
  - `process`: pid/ports/health/restart policy;
  - `trust`: signer/source/risk acknowledgement.

Workflow packs:

- Current `WorkflowInfo` can list files, but not model workflow JSON as parsed data.
- Imported workflow JSON should live as a pack resource plus typed extracted metadata:
  nodes, model references, custom node refs, missing deps, source file hash, and import
  wizard decisions.
- `PackCategory.WORKFLOW` is optional if `WorkflowFacet` exists. Without a facet, a new
  category will become another weak flag.

## 10. UI / Attach Model

- `UIKindMap` covers many model kinds for ComfyUI/Forge/A1111/SD.Next defaults, but not
  `custom_node`.
- ComfyUI extra_model_paths generation maps only a subset of kinds
  ([ui_attach.py:142](../../src/store/ui_attach.py#L142)).
- Generic symlink attach iterates `AssetKind` but skips any kind with no kind-map path
  ([ui_attach.py:333](../../src/store/ui_attach.py#L333)).
- `default_ui_set` authority is split: default name in `StoreConfig.defaults.ui_set`,
  actual set in `UISets`.
- UI roots are passed to `UIAttacher` from app config, not persisted in store config
  ([ui_attach.py:53](../../src/store/ui_attach.py#L53)).
- `extra_model_paths.yaml` schema is built ad hoc as nested dictionaries, not modeled
  ([ui_attach.py:94](../../src/store/ui_attach.py#L94)).

Recommendation:

- Add explicit UI attach config model: UI name, root, attach method, supported kind map.
- Add ComfyUI YAML model if the app will edit and preserve user YAML repeatedly.
- Decide whether custom nodes are install-pack assets rather than model blobs.

## 11. Cross-Cutting Concerns

Schema versioning:

- Schema strings exist in file models, but load paths call direct `model_validate`
  without migration dispatch ([layout.py:427](../../src/store/layout.py#L427)).
- Recommendation: add `load_pack_document`/`migrate_pack` helpers and fail clearly on
  unsupported future schemas.

Pydantic:

- Uses Pydantic v2 APIs (`field_validator`, `model_validator`, `model_serializer`).
- No frozen models. Mutable lists are normal. This is convenient but makes accidental
  in-place mutation common.
- Recommendation: keep persisted models mutable for service ergonomics, but add command
  methods for high-risk mutations or central write services.

Validation:

- Safe names prevent path separators and traversal, but dependency selectors are not
  discriminated.
- Recommendation: use discriminated unions for selector payloads:
  `CivitaiFileSelector`, `HuggingFaceFileSelector`, `LocalFileSelector`, etc.

Naming:

- `pack`, `pack_name`, `name`, `pack_type`, `pack_category` are mostly consistent.
- `pack_type` is misleading because pack can mix asset kinds. Prefer `primary_kind`.

Serialization:

- Aliased schema fields use `populate_by_name=True` and `by_alias=True` when layout
  writes top-level models.
- `GenerationParameters` custom serializer drops `None` and preserves extras.
- NEEDS VERIFICATION: all API responses using `model_dump()` rather than
  `model_dump(by_alias=True)` may expose `schema_` instead of `schema`.

## 12. Observed Bugs / Smells

1. `ProfilePackEntry.enabled` drift: model has no `enabled`, CLI accesses it
   ([models.py:1002](../../src/store/models.py#L1002), [cli.py:527](../../src/store/cli.py#L527)).
2. `Profile.conflicts.mode` ignored: view builder implements only last-wins
   ([models.py:1012](../../src/store/models.py#L1012), [view_builder.py:91](../../src/store/view_builder.py#L91)).
3. `StatusReport.shadowed` always empty in Store status
   ([__init__.py:951](../../src/store/__init__.py#L951)).
4. Placeholder Civitai IDs exist in default config
   ([models.py:280](../../src/store/models.py#L280)).
5. Resolve branch also emits placeholder `model_id=0` candidates in filename fallback
   ([branch evidence_providers.py:198] via git show).
6. `StoreLayout.pack_path()` does not exist, but API create pack calls it
   ([api.py:3334](../../src/store/api.py#L3334), [layout.py:169](../../src/store/layout.py#L169)).
7. `custom_node` asset kind is not attachable through current kind maps
   ([models.py:42](../../src/store/models.py#L42), [ui_attach.py:142](../../src/store/ui_attach.py#L142)).
8. `version_constraint` on `PackDependencyRef` is stored but not enforced
   ([models.py:452](../../src/store/models.py#L452)).
9. `PackDependency.required` and `PackDependencyRef.required` are not reflected in
   lock completeness or runtime composition.
10. `StateSyncStatus.CONFLICT` is modeled but not produced by current comparison.
11. `ArtifactProvider` lacks HF `subfolder`, while `HuggingFaceSelector` has it.
12. `BlobStatus.BACKUP_ONLY` semantics are narrower than the enum name implies.

## 13. Design Recommendations

### Split `Pack`

Keep:

- `PackCore`: schema, name, category/origin, primary kind, version, description, tags.
- `DependencyManifest`: model dependencies and pack dependencies.
- `MediaFacet`: previews, cover, resources.
- `GenerationFacet`: parameters/model info.
- `WorkflowFacet`: workflow resources and extracted dependency hints.
- `InstallFacet`: script/process/UI install metadata.

### Merge Source Identity

- Introduce one source identity model, likely evolved from branch `CanonicalSource`.
- Use it in dependency desired state, lock provider/origin derivation, and blob manifest.
- Keep provider-specific selector as an acquisition strategy.

### Type-Narrow Selectors

- Replace optional-field `DependencySelector` with a discriminated union.
- Benefits: no invalid local selector without path, no Civitai strategy without Civitai
  payload, no zero-ID placeholders.

### Make Locks Staleness-Aware

- Add lock-level `pack_fingerprint`.
- Add per-resolved-entry `dependency_fingerprint`.
- Show stale lock state in status and resolve UI.

### Decide Operational Semantics For Pack Dependencies

- If operational: expand required pack deps when building profiles/views.
- If informational: rename to `related_packs` or `recommended_packs`.
- Enforce `version_constraint` or remove it.

### Wire Or Remove Modeled Fields

- Implement `ConflictMode`.
- Implement active UI inventory tracking or drop it from response.
- Implement state sync conflicts or remove `CONFLICT`.
- Add `ProfilePackEntry.enabled` intentionally or remove stale callers.

### Schema Migration

- Add migration helpers per persisted document.
- Use schema version dispatch before Pydantic validation.
- Keep migration tests with old fixture JSON.

## 14. Open Questions For Owner

1. Should `pack_dependencies` affect runtime composition, or are they advisory metadata?
2. Should `apply_resolution()` update `lock.json`, invalidate it, or leave stale state
   until explicit resolve?
3. Is `Pack.source` meant to mean "creation source" or "all pack content source"?
4. Do workflow imports deserve `PackCategory.WORKFLOW`, or should they be `CUSTOM` with
   a workflow facet?
5. Are install packs trusted first-party objects only, or can users import arbitrary
   install packs?
6. Should custom packs be backend-updatable when their dependencies use `FOLLOW_LATEST`?
7. Should optional dependencies affect `PackLock.is_fully_resolved()`?
8. Should dependency IDs be user-editable after a lock exists?
9. Is ComfyUI custom node management part of store assets, install packs, or a separate
   extension manager?
10. Should backup state sync be push/pull only, or a true bidirectional merge with
    conflict resolution?
11. Should UI roots be persisted in store config or remain application config?
12. What is the migration policy for existing `synapse.pack.v2` files once canonical
    source lands?

