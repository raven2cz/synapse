# Synapse v2 Store — Domain Model Audit

**Created:** 2026-05-02
**Authors:** Claude Opus 4.7 (this file) + Codex GPT-5.5 high effort (`codex-domain-audit.md` companion)
**Goal:** Find DESIGN FLAWS in `src/store/models.py` and adjacent modules BEFORE
the team builds Release 1 finishing extensions on top of them. A rotten domain
model means every future extension is a bug-fix mission.

**Scope:** All Pydantic models in the store layer + how they are used (or not used)
by `pack_service`, `profile_service`, `view_builder`, `dependency_resolver`,
`inventory_service`, `backup_service`, `update_service`, `blob_store`, `ui_attach`,
`api.py`, `cli.py`, plus the `feat/resolve-model-redesign` branch additions.

**Companion file:** `plans/audits/codex-domain-audit.md` — independent audit by
Codex GPT-5.5 high effort (run in parallel with this one). Cross-reference both
before making decisions.

**How to read this file:** Sections 1-12 = factual findings with file:line refs.
Section 13 = concrete refactor recommendations. Section 14 = open questions for
the project owner. Section 14b = **detailní decision-session otázky pro vlastníka**
(Czech, s konkrétními příklady a volbami A/B/C). Severity tags: **HIGH** (production
crashes / data loss), **MEDIUM** (silent semantic drift, future extension blockers),
**LOW** (cosmetic / cleanup).

---

## ⚠️ TODO PŘED ROZHODOVÁNÍM (2026-05-02)

**STAV:** Audit byl proveden na `main` brachi. Branch `feat/resolve-model-redesign`
**není sloučená do main** a může mít už vyřešené některé z níže popsaných nálezů
(zejména Section 5, 8, 12 → resolve-redesign related).

**Plán:**
1. **Zítra (2026-05-03):** Přepnout na `feat/resolve-model-redesign` branch.
2. **Zkontrolovat každý finding** — je už opravený? Jakým způsobem? Pokud ano, škrtnout v auditu.
3. **Teprve potom decision session** (Section 14b níže) — odpovědi na otevřené otázky.
4. **Stabilization branch** `stabilization/release-1` — všechny mechanické fixy
   (H1 `pack_path`, H2 `pack_entry.enabled`, M9 error swallowing) + post-decision
   refactory půjdou tam, ne přímo do main.
5. **Audit Claude + Codex** stabilizačního planu před mergem do main.
6. **Test pass** na stabilization branchi (uživatel ručně otestuje).
7. **Merge do main** až po user OK.

---

## TL;DR — Top 10 issues

1. **HIGH — `store.layout.pack_path()` does not exist.** Called in 8 places in
   `src/store/api.py` (lines 3334, 3424, 4078, 4581, 4739, 4790, 4859, 4958).
   `StoreLayout` defines `pack_dir()` (layout.py:169) but never `pack_path()`.
   Runtime `AttributeError` on every code path that touches it (custom pack
   creation, rename, preview upload, workflow upload, asset injection).
2. **HIGH — `ProfilePackEntry.enabled` referenced by CLI but field doesn't exist.**
   `cli.py:527` reads `pack_entry.enabled`; `ProfilePackEntry` (models.py:1002)
   has only `name`. `synapse profile show <name>` is broken.
3. **HIGH — `pack_dependencies` is informational metadata only.**
   `view_builder.py` and `profile_service.py` never read `pack_dependencies`
   when building the view plan. A pack that depends on another pack via
   `pack_dependencies` will NOT pull in that pack's assets when used. The
   field exists, has CRUD, has a tree-status endpoint — but is functionally
   inert at runtime.
4. **MEDIUM — `StatusReport.shadowed` always `[]`.**
   `Store.status()` at `__init__.py:951-960` hardcodes the list to empty with
   the comment "would need to compute view plan for accurate info." The actual
   shadows are computed by `ViewBuilder.build()` and only persist transiently
   on `UseResult`/`BuildReport`, never re-derivable from disk.
5. **MEDIUM — `ConflictConfig.mode` modeled but never read.**
   `models.py:1014` defines the enum and field. `ViewBuilder.add_entry()`
   always behaves as `LAST_WINS` — `ConflictMode.FIRST_WINS` and `STRICT`
   are wishful thinking. Single grep across `src/store/` returns zero
   non-definition references.
6. **MEDIUM — `version_constraint` on `PackDependencyRef` never enforced.**
   `PackDependencyRef.version_constraint` (models.py:452) is a free-form
   string. No code reads it. Adding a `>=1.0.0` constraint does nothing.
7. **MEDIUM — Default `base_model_aliases` use placeholder zero IDs.**
   `StoreConfig._get_default_base_model_aliases()` (models.py:271-307) creates
   aliases with `model_id=0, version_id=0, file_id=0` and a comment saying
   "These are placeholder values". The `BaseModelHintResolver` therefore can
   never resolve a default alias to a real Civitai download.
8. **MEDIUM — `AssetKind.CUSTOM_NODE` has no UI path mapping.**
   `UIKindMap` (models.py:121) hardcodes 10 fields covering checkpoints, LoRA,
   VAE, controlnet, upscaler, clip, text_encoder, diffusion_model, embedding,
   unet — but NOT `custom_node` or `unknown`. `ViewBuilder.add_entry` falls back
   to `models/{kind.value}` (view_builder.py:87), which would route custom
   nodes to `models/custom_node/` — wrong, ComfyUI expects `custom_nodes/`.
9. **MEDIUM — Schema version fields exist but no migration code anywhere.**
   Each top-level model has a `schema_` field (`synapse.pack.v2`,
   `synapse.profile.v1`, etc.). Zero matches for `schema_version`,
   `migrate_pack`, or any migration logic in `src/store/`. The version is
   declarative-only — when v2 → v3 happens, it has to be hand-written.
10. **MEDIUM — Resolve-redesign `CanonicalSource` and main-branch `PackSource`
    are parallel hierarchies.** On the resolve-redesign branch,
    `CanonicalSource` lives on `DependencySelector` (per-dependency identity).
    On main, `PackSource` lives on `Pack` (per-pack identity, Civitai-only
    today). When the redesign merges, the two will coexist — but a custom pack
    with one Civitai dep and one HF dep cannot use `Pack.source`. The pack
    field is misplaced.

---

## 1. INVENTORY OF DOMAIN OBJECTS

All references are to `src/store/models.py` unless noted otherwise.
Every top-level model has a `schema_` field (Pydantic alias `schema`) used for
on-disk JSON, but **no migration logic ever consumes it.**

### 1a. Pack lifecycle (state/packs/&lt;Pack&gt;/)

| Model | Line | Persistence | Purpose / Notes |
|---|---|---|---|
| `Pack` | 837 | `state/packs/<name>/pack.json` | Main pack definition; combines source, deps, pack-deps, previews, parameters, model_info, workflows. Schema = `synapse.pack.v2`. |
| `PackSource` | 422 | embedded in Pack | Civitai-or-HuggingFace-or-URL source identity. Today only used for Civitai imports. **Does NOT exist for custom packs imported from a workflow** — those sources live nowhere. |
| `PackDependency` | 406 | embedded in Pack.dependencies | One per file dependency. Carries `id`, `kind`, `selector`, `update_policy`, `expose`, optional `description`. |
| `PackDependencyRef` | 438 | embedded in Pack.pack_dependencies | Pack-to-pack ref. Has `pack_name`, `required`, `version_constraint`. **`version_constraint` never enforced.** |
| `DependencySelector` | 372 | embedded in PackDependency.selector | OneOf-shaped: civitai/huggingface/base_model/url/local_path. **In resolve-redesign branch also gains `canonical_source` field — main branch doesn't.** |
| `CivitaiSelector` | 327 | embedded in DependencySelector.civitai | model_id / version_id / file_id. |
| `HuggingFaceSelector` | 333 | embedded in DependencySelector.huggingface | repo_id / filename / revision / subfolder. |
| `SelectorConstraints` | 367 | embedded in DependencySelector.constraints | primary_file_only / file_ext / base_model_hint. |
| `BaseModelAliasSelector` | 209 | embedded in BaseModelAlias.selector | Same shape as DependencySelector but only Civitai-typed today. |
| `BaseModelAlias` | 220 | StoreConfig.base_model_aliases | "SD1.5" → kind + filename + selector mapping. **Default values use zero IDs.** |
| `UpdatePolicy` | 414 (resolve branch) / wrapper class | embedded in PackDependency | mode = pinned/follow_latest. |
| `ExposeConfig` | 395 (resolve branch) / 393 main | embedded in PackDependency.expose | filename + trigger_words. The "expose" name conflates "filename in view tree" with "trigger words for prompt UX". |
| `PackResources` | 432 | embedded in Pack | previews_keep_in_git / workflows_keep_in_git booleans. |
| `PreviewInfo` | 770 | embedded in Pack.previews | URL, filename, NSFW, dimensions, meta, media_type, thumbnail_url. **First-class on Pack** — preview list is part of pack.json, not a sidecar. |
| `WorkflowInfo` | 783 (NEEDS VERIFICATION line) | embedded in Pack.workflows | ComfyUI workflow JSON descriptor. |
| `GenerationParameters` | 460 | embedded in Pack.parameters | extra="allow" — extensive AI normalization for sampler, cfg_scale, hires_fix etc. |
| `ModelInfo` | (search models.py for `class ModelInfo`) | embedded in Pack.model_info | Civitai-derived metadata: model_type, base_model, trigger_words, hashes, download_count, rating. |

### 1b. Pack lock (state/packs/&lt;Pack&gt;/pack.lock.json)

| Model | Line | Purpose |
|---|---|---|
| `PackLock` | 977 | Resolution snapshot. Schema = `synapse.lock.v2`. |
| `ResolvedDependency` | (NEEDS VERIFICATION) | Wraps dependency_id + ResolvedArtifact. |
| `ResolvedArtifact` | (NEEDS VERIFICATION) | kind, sha256, size_bytes, ArtifactProvider, ArtifactDownload, ArtifactIntegrity. |
| `ArtifactProvider` | — | Provider name + model_id/version_id/file_id (Civitai), repo_id (HF), filename. |
| `ArtifactDownload` | — | List of URLs. |
| `ArtifactIntegrity` | — | sha256_verified bool. |
| `UnresolvedDependency` | — | dependency_id + reason + details. |

The ID/hash split is **three-place**: SHA256 lives in (1) Pack.dependencies[*].selector
NOT, but in (2) PackLock.resolved[*].artifact.sha256, (3) blobs/<prefix>/<hash> file.
For HF/URL resolvers, sha256 is `None` until install completes (see
`pack_service.py:install_pack` which back-fills `resolved.artifact.sha256` and
saves the lock).

### 1c. Blob layer (data/blobs/&lt;prefix&gt;/&lt;sha256&gt;)

| Model | Line | Persistence | Purpose |
|---|---|---|---|
| `BlobManifest` | (NEEDS VERIFICATION ~line 1300) | `<sha256>.meta` JSON sidecar | Write-once metadata for orphan recovery: original_filename, kind, origin. |
| `BlobOrigin` | — | embedded in BlobManifest | Provider + model_id/version_id/file_id/repo_id/filename. Used for orphan blob attribution. |

### 1d. Inventory (computed live, not persisted)

| Model | Line | Purpose |
|---|---|---|
| `InventoryItem` | 1334 | One row per blob: sha256, kind, display_name, location, on_local/on_backup, status, used_by_packs, ref_count, origin, **active_in_uis (always [], TODO at inventory_service.py:377)**, verified. |
| `BlobStatus` | 1296 | enum: REFERENCED / ORPHAN / MISSING / BACKUP_ONLY. |
| `BlobLocation` | 1304 | enum: LOCAL_ONLY / BACKUP_ONLY / BOTH / NOWHERE. |
| `InventorySummary` | (NEEDS VERIFICATION) | Aggregated counts and bytes; embeds BackupStats. |
| `InventoryResponse` | — | { generated_at, summary, items[] }. |
| `PackReference` | — | One per pack-uses-blob edge: pack_name, dependency_id, kind, expose_filename, size_bytes, origin. |
| `ImpactAnalysis` | — | "If you delete this blob, here's what breaks." Has `active_in_uis` field — **also unused, per inventory_service.py:613**. |
| `CleanupResult`, `MigrateManifestsResult` | — | Operation results. |

### 1e. Backup (state/backup_config.json + external mount)

| Model | Line | Purpose |
|---|---|---|
| `BackupConfig` | 235 | enabled, path, auto_backup_new, warn_before_delete_last_copy. |
| `BackupStatus` | (NEEDS VERIFICATION) | Connected, mount path, free space, last sync. |
| `BackupStats` | (NEEDS VERIFICATION) | Per-blob counts (local_only / backup_only / both). |
| `BackupOperationResult`, `BackupDeleteResult`, `SyncItem`, `SyncResult` | — | Ops payloads. |

### 1f. Profile / runtime / view (state/profiles + data/runtime.json + data/views/)

| Model | Line | Persistence | Purpose |
|---|---|---|---|
| `Profile` | 1017 | `state/profiles/<name>/profile.json` | name + ConflictConfig + ProfilePackEntry list. Schema = `synapse.profile.v1`. |
| `ProfilePackEntry` | 1002 | embedded in Profile.packs | **Only `name`.** No `enabled` field, no `pack_dependencies` flattening. |
| `ConflictConfig` | 1012 | embedded in Profile | mode = ConflictMode (LAST_WINS default). **mode never read at runtime.** |
| `Runtime` | 1058 | `data/runtime.json` | ui dict → UIRuntimeState. push/pop stack. |
| `UIRuntimeState` | 1053 | embedded in Runtime | `stack: List[str]`, default `["global"]`. |
| `ViewPlan`, `ViewEntry`, `ShadowedEntry`, `BuildReport` | view_builder.py | Computed; not persisted as JSON, only as filesystem symlink trees in `data/views/<ui>/profiles/<profile>/`. |
| `StatusReport`, `DoctorReport`, `UseResult`, `BackResult`, `ResetResult`, `DeleteResult`, `SyncResult` | — | API/CLI output payloads. **`StatusReport.shadowed` always empty.** |

### 1g. Config / UI / providers

| Model | Line | Purpose |
|---|---|---|
| `StoreConfig` | 243 | state/config.json. defaults / ui / providers / base_model_aliases / backup. Schema = `synapse.config.v2`. |
| `ConfigDefaults` | 227 | ui_set / conflicts_mode / active_profile / use_base. |
| `UIConfig` | 139 | known UIs list + kind_map dict. |
| `UIKindMap` | 121 | **Hardcoded fields per kind. No `custom_node` mapping.** |
| `ProviderConfig` | 199 | primary_file_only_default / preferred_ext. |
| `UISets` | 314 | state/ui_sets.json. sets dict. |

### 1h. Resolve-redesign branch ONLY (`feat/resolve-model-redesign:src/store/resolve_models.py`)

| Model | Purpose |
|---|---|
| `EvidenceSource` (Literal) | hash_match / preview_embedded / preview_api_meta / source_metadata / file_metadata / alias_config / ai_analysis |
| `EvidenceItem`, `EvidenceGroup` | Tiered evidence with confidence + provenance |
| `CandidateSeed`, `EvidenceHit`, `ResolutionCandidate` | Suggest result rows |
| `PreviewModelHint`, `PreviewAnalysisResult` | Per-preview hint extraction |
| `ProviderResult` | Output of one evidence provider |
| `SuggestOptions`, `SuggestResult`, `ApplyResult` | Service contracts |
| `ManualResolveData` | Manual user input |
| `ResolveContext` | Provider input (pack + dep + layout) |
| `CanonicalSource` *(in models.py on branch, line 381)* | **Becomes a sibling of PackSource.** Per-dep identity for update tracking. |

Main-branch `models.py` does NOT have `CanonicalSource`. Importing the resolve
branch's `resolve_models.py` requires its parallel `CanonicalSource` to land
first — there's an integration plan boundary here.

---

## 2. ENUMS — exhaustiveness

### `AssetKind` (models.py:31, 12 values)

```
checkpoint, lora, vae, controlnet, upscaler, clip, text_encoder,
diffusion_model, embedding, custom_node, unet, unknown
```

**Findings:**
- **`custom_node` is in the enum but has no UIKindMap path.** `models/custom_node/`
  fall-back is wrong; ComfyUI expects `custom_nodes/`.
- **No `WORKFLOW` kind.** Imported workflows live in `Pack.workflows: List[WorkflowInfo]`,
  which is fine for the workflow-author UI, but if the team wants
  "workflow-as-dependency" (a workflow pack that requires another workflow as a
  prerequisite), there's no kind for it.
- **No `LYCORIS` / `LOCON` kind.** `pack_service.py:152-153` maps `"LoCon"` and
  `"DoRA"` to `AssetKind.LORA`. That's a workable shim, but loses fidelity for
  UI display ("this is a LoRA" vs "this is a LoCoN").
- **No `IP_ADAPTER`, `LLLITE`, `MOTION_MODULE`** for animatediff/controlnet
  variants. Civitai differentiates these — Synapse silently flattens.

### `ProviderName` (models.py:47, 4 values)

```
civitai, huggingface, local, url
```

- Covers current providers. **Adding `github` (for install pack manifests) or
  `direct_archive` (for ZIP custom nodes) is on the horizon for Install Pack
  (R1 Bod 3).** The enum is closed — adding values is straightforward.

### `SelectorStrategy` (models.py:55, 6 values)

```
civitai_file, civitai_model_latest, huggingface_file, base_model_hint,
local_file, url_download
```

- The "file vs model_latest" split is Civitai-specific. **HuggingFace has only
  one strategy (HUGGINGFACE_FILE) — no `huggingface_branch_latest` for
  follow-tracking-revision-on-main.** The asymmetry will bite when HF starts
  shipping update notifications.
- `base_model_hint` is essentially "use the configured alias." Conceptually it's
  not a *strategy* — it's an indirection. The resolver chains: hint → alias →
  CIVITAI_FILE. A discriminated union would be cleaner.

### `UpdatePolicyMode` (models.py:65, 2 values: pinned, follow_latest)

- The redesign plan mentions `manual_review` (keep showing update banner without
  auto-applying). Not modeled today.

### `ConflictMode` (models.py:71, 3 values: last_wins, first_wins, strict)

- **`first_wins` and `strict` are unimplemented.** `ViewBuilder.add_entry`
  always behaves as last_wins (line 92-101). Either remove the unused values or
  wire them.

### `PackCategory` (models.py:78, 3 values: external, custom, install)

- Covers planned categories per CLAUDE.md.
- **No `WORKFLOW` category.** Per the workflow wizard plan (R1 Bod 4), imported
  workflows currently piggyback on `custom`. If they get their own UI behavior,
  they'll need disambiguation — either via category or `user_tags`. The audit
  recommends `user_tags=["workflow-import"]` instead of growing the enum, but
  the team should decide.

### `BlobStatus` (models.py:1296), `BlobLocation` (models.py:1304)

- Tightly coupled. Status `BACKUP_ONLY` and Location `BACKUP_ONLY` mean
  different things (status = "referenced and only on backup" vs location =
  "physical location"). Naming collision is real — caused real bugs in
  Inventory UI per CLAUDE.md history.

---

## 3. PACK SHAPE — cohesion

### 3a. Pack.source vs PackDependency.selector

`Pack.source` (line 843) is required, single, and only meaningful for packs imported
from a single Civitai model. **For custom packs created from scratch (PackCategory.CUSTOM)
or composed of dependencies from multiple providers, `Pack.source` is misleading.**

Today every custom pack must still produce a `PackSource`. `pack_service.py:514`
shows the required-field constraint:

```python
pack = Pack(
    name=name,
    pack_type=asset_kind,
    pack_category=PackCategory.EXTERNAL,
    source=PackSource(provider=ProviderName.CIVITAI, ...),
    ...
)
```

For a workflow-imported custom pack with a Civitai LoRA + HF VAE, what should
`source` be? Today the API likely picks the "primary" model and stores it,
silently lying about composition.

**Recommendation:** Make `Pack.source` optional, OR move it to
`Pack.primary_source` (clearly only the import origin), OR drop it from Pack
entirely and derive it from the first dependency's selector.

### 3b. PackLock vs Pack split

| Field | Pack | PackLock | Authoritative? |
|---|---|---|---|
| sha256 | NOT stored | `resolved[*].artifact.sha256` | Lock |
| download URL | NOT stored | `resolved[*].artifact.download.urls` | Lock |
| size_bytes | NOT stored | `resolved[*].artifact.size_bytes` | Lock |
| filename | `dependencies[*].expose.filename` (target) | `resolved[*].artifact.provider.filename` (source) | Both — different meanings |
| kind | `dependencies[*].kind` | `resolved[*].artifact.kind` | **Duplicated** — and could diverge if the Pack edits the kind without re-resolving |
| selector | `dependencies[*].selector` | NOT stored | Pack |

**Smell:** `resolved.artifact.kind` is duplicated from `dep.kind`. In
`pack_service.py:_create_initial_lock_multi:697` it's set from `dep.kind`. In
`inventory_service.py:_build_reference_map:248-253`, when there's a mismatch
between `resolved.artifact.kind` and the corresponding `dep.kind`, the code
prefers `dep.kind` from the pack — confirming the lock copy is stale.

### 3c. PreviewInfo and WorkflowInfo first-class on Pack

`Pack.previews: List[PreviewInfo]` is part of pack.json. So is
`Pack.workflows: List[WorkflowInfo]`. This means:

- **One large pack with 100 previews → pack.json grows linearly.** The previews
  embed metadata dicts. Today's git-versioned `state/` strategy means every
  preview update bloats the diff.
- **Workflow JSON pointed to via `WorkflowInfo`** — the actual workflow JSON
  files live in `state/packs/<name>/resources/workflows/`, with descriptors in
  pack.json. This is fine.
- **Could move previews to a sidecar `previews.json`** to keep `pack.json`
  small. Future consideration.

### 3d. Storage paths

- `pack.json` → `state/packs/<name>/pack.json` (git-versioned)
- `pack.lock.json` → `state/packs/<name>/pack.lock.json` (git-versioned)
- `resources/previews/*.{jpg,mp4}` + `*.json` sidecars → git-versioned
- `resources/workflows/*.json` → git-versioned
- `data/blobs/<prefix>/<sha256>` + `.meta` → NOT git-versioned, content-addressed

Clean separation. **Inventory cross-cuts both** — `state/packs/*/pack.lock.json`
gives the references, `data/blobs/` gives the physical layer.

---

## 4. DEPENDENCY MODEL

### 4a. Field-level overlap

| Concept | PackDependency | PackDependencyRef | ResolutionCandidate (resolve branch) | CanonicalSource (resolve branch) |
|---|---|---|---|---|
| Identity | `id` (str) | `pack_name` | `candidate_id` (UUID) | (no surrogate id) |
| Kind | `kind` | — (whole-pack ref) | (carried in selector) | — |
| Required | `required` | `required` | — | — |
| Selector | `selector` | — | `strategy + selector_data` | — |
| Constraint | `selector.constraints` | `version_constraint` | — | — |
| Update policy | `update_policy` | — | — | — |
| Display | `description` | — | `display_name`, `display_description` | — |
| Confidence | — | — | `confidence`, `tier` | — |
| Evidence | — | — | `evidence_groups` | — |
| Provenance | — | — | `provider` | provider, model_id, version_id, file_id, repo_id, filename, subfolder, revision, sha256 |

**Findings:**
- `ResolutionCandidate.selector_data: Dict[str, Any]` is loose. The matching
  `apply` flow then needs to construct a typed `DependencySelector`. The
  conversion is in `pack_service.py:apply_dependency_resolution` on the resolve
  branch. **Loose typing means apply-time validation errors instead of
  suggest-time.**
- `version_constraint` on `PackDependencyRef` is a free-form string. **No code
  reads it.** A pack that says "I need pack X >=1.0.0" can be installed against
  pack X 0.5.0 with no warning.

### 4b. Recursive expansion of `pack_dependencies`

```bash
$ grep -rn "pack_dependencies" src/store/
src/store/update_service.py:258:  Find all packs that depend...
src/store/update_service.py:269:  dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
src/store/models.py:845: pack_dependencies: List[PackDependencyRef] = ...
src/store/api.py:2964/3051/3063/3091/3172: CRUD + tree status
src/store/pack_service.py:521: pack_dependencies=[]  # default empty on import
```

**Zero hits in `view_builder.py`, `profile_service.py`.**

So:
- The field is modeled.
- The CRUD API (add / remove / list / tree) exists.
- The status-tree endpoint walks `pack_dependencies` recursively (api.py:3172).
- **But the actual view-build pipeline never reads it.** A profile with a single
  pack `Style-LoRA-A` that has `pack_dependencies = [Base-Model-B]` will only
  render `Style-LoRA-A`'s own assets in the view tree — `Base-Model-B`'s LoRA
  will NOT be linked unless `Base-Model-B` is also explicitly in
  `profile.packs`.

This is the most important non-bug-but-still-broken design issue. **The team
must decide:** are pack_dependencies operational (alter view symlinks) or
informational (UI hint only)? See open questions.

### 4c. dep_id stability

`PackDependency.id` is set at import time from a sanitized version name
(`pack_service.py:447-454`). For a multi-version import, IDs are
`v{ver_id}_{safe_name}_{kind}`. For single-version, `main_{kind}`. The ID is
stable across re-resolution (same selector → same dep) but **NOT stable across
re-import** (a fresh import generates fresh IDs).

The `apply_dependency_resolution` path on the resolve branch uses the dep_id
as the lookup key (pack_service.py:1244-1247). If a user runs suggest, then
edits the pack manually, the dep_id might stay or it might be regenerated —
NEEDS VERIFICATION.

---

## 5. SOURCE / EVIDENCE / CANDIDATE

### 5a. Pack.source vs PackDependency.selector vs CanonicalSource (redesign)

```
Main branch:
  Pack.source: PackSource           ← pack-level Civitai origin only
  Pack.dependencies[*].selector     ← per-dep, has civitai/hf/local/url selectors

Resolve-redesign branch (additions):
  models.py:CanonicalSource         ← per-dep canonical identity for update tracking
  DependencySelector.canonical_source ← optional CanonicalSource on the selector
  ResolutionCandidate.canonical_source ← preferred future ref
```

**Three identity surfaces.** When a candidate is applied, `apply_dependency_resolution`
(pack_service.py:1217 on the resolve branch) writes the new selector AND copies
the candidate's `canonical_source` onto `dep.selector.canonical_source`.

**Risk:** If we later change `Pack.source` (e.g. for re-discovery on update),
`PackDependency.selector` and `DependencySelector.canonical_source` and
`ResolvedDependency.artifact.provider` could all drift. **There's no single
source of truth for "what is this dependency really?"**

### 5b. Civitai reference stability

For Civitai, the canonical reference triple is `(model_id, version_id, file_id)`.
Today this triple is duplicated in:
- `Pack.source.model_id, version_id` (pack-level, version_id can be stale)
- `PackDependency.selector.civitai.{model_id, version_id, file_id}` (current truth)
- `PackLock.resolved.artifact.provider.{model_id, version_id, file_id}` (post-resolve truth)
- (resolve branch) `DependencySelector.canonical_source.{model_id, version_id, file_id}`

For a HuggingFace dep, `(repo_id, revision, filename)`.
For a local file, the path is the only identity (with sha256 derived).

**Recommendation:** declare ONE canonical reference per dep (the resolve
branch's `CanonicalSource`), make `selector` a pure resolution-strategy choice,
and stop replicating across Pack.source.

---

## 6. PROFILE / RUNTIME / VIEW

### 6a. ProfilePackEntry — the missing `enabled` field

```python
class ProfilePackEntry(BaseModel):
    """A pack entry in a profile."""
    name: str
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_safe_name(v)
```

**Just `name`.** But:

```python
# src/store/cli.py:527
enabled = "[green]✓[/green]" if pack_entry.enabled else "[red]✗[/red]"
```

CLI accesses `pack_entry.enabled`, which Pydantic will raise `AttributeError`
on. **Severity: HIGH** — runs on `synapse profile show <name>`.

Decision matrix:
- Add `enabled: bool = True` to ProfilePackEntry → CLI works, but ViewBuilder
  must filter by it, otherwise the field is decorative.
- Remove the line from CLI → field stays undefined, no surprise.

The semantic question: **does a profile need per-pack enable/disable?** Probably
yes — "I want my profile to include LoRAs A, B, C, D, but disable C without
removing it." But this is a NEW feature, not a bug fix. Treat carefully.

### 6b. ConflictConfig.mode unused

Same shape as ProfilePackEntry.enabled — modeled, never enforced.
`ViewBuilder.add_entry` (view_builder.py:71) hard-codes "if same dst_relpath
exists, replace" = LAST_WINS. To support FIRST_WINS the loop becomes a no-op
on collision; STRICT raises.

### 6c. Runtime push/pop stack

`Runtime.ui[ui_name].stack` is a list of profile names. `push_profile()` /
`pop_profile()` operate on it. Default stack = `["global"]`.

**Invariants not enforced:**
- What if the underlying profile (e.g. `work__SomeLoRA`) is deleted while it's
  in the stack? `Store.status()` would surface a `Profile not found` error
  on read.
- What's the maximum stack depth? No bound.
- Can the same profile appear twice in the stack? No check.

This is a small thing today — the UI rarely creates pathological stacks — but
worth modeling explicitly when work__ profile lifecycle is formalized.

### 6d. ShadowedEntry computation

`ViewBuilder.compute_plan` (view_builder.py:212) returns ViewPlan with
`shadowed: List[ShadowedEntry]` populated correctly during plan construction
(view_builder.py:95-101). `BuildReport` carries this forward
(view_builder.py:300-306). `UseResult.shadowed` is populated by
ProfileService.use (profile_service.py:243).

**But `Store.status()` (init.py:951-960) hardcodes `shadowed: List[ShadowedEntry] = []`**
with the comment "would need to compute view plan for accurate info." The
StatusReport for the ACTIVE profile therefore never reflects shadowed state
on disk.

To fix: status() should re-run `view_builder.compute_plan(active_ui, profile, packs)`
to rebuild the shadow list. Cheap operation — no I/O.

### 6e. Work profile lifecycle (`work__<pack>`)

Defined in `profile_service.py:ensure_work_profile / update_work_profile`
(line 200 onwards). Created on first `use(pack)`, updated on subsequent
`use(pack)`. **Not garbage-collected** — old `work__` profiles linger in
`state/profiles/` indefinitely. CLAUDE.md does not mention a cleanup story.

For Release 1, this is fine. Long-term, when users have hundreds of
`work__SomeLoRA` profiles, a `synapse cleanup work-profiles` operation will
be needed.

---

## 7. INVENTORY / BLOB / BACKUP MODELS

### 7a. InventoryItem.active_in_uis is always empty

```python
# inventory_service.py:377 (in _build_item)
active_in_uis=[],  # TODO: Get from runtime
```

Same in `get_impacts()` at line 613. The field is declared, surfaced through the
API, **always returns []**. The "active in which UIs" information is needed
for the Inventory UI to show "this LoRA is currently linked into ComfyUI's view"
but cannot be derived from disk without walking `data/views/<ui>/active/...`
symlinks and matching their targets back to blobs.

### 7b. BlobManifest write-once semantics

`BlobStore.write_manifest()` (blob_store.py:560) explicitly does NOT overwrite:
```python
if path.exists():
    logger.debug(f"[BlobStore] Manifest already exists for {sha256[:12]}, skipping")
    return False
```

Good defensive behavior. Migration path (`InventoryService.migrate_manifests`,
inventory_service.py:844) is idempotent and safe.

### 7c. Backup as push/pull/mirror

`BackupConfig.path` is a single mount path. There's no notion of multiple
backup destinations or remote (S3/B2) backups. `auto_backup_new` triggers a
copy on every newly-installed blob. Sync is bidirectional (data flow inferred
from method names; see backup_service.py).

For Release 1: fine. **For Release 2+: cloud backup is a likely user request.**
The `BackupConfig` enum would grow to include backend type.

---

## 8. RESOLUTION REDESIGN INTEGRATION

### 8a. CanonicalSource lives where?

On the resolve-redesign branch:
- `models.py:CanonicalSource` (line 381 on branch) — top-level model.
- `DependencySelector.canonical_source: Optional[CanonicalSource]` — embedded.
- `ResolutionCandidate.canonical_source: Optional[CanonicalSource]` — embedded.
- `CandidateSeed.canonical_source: Optional[CanonicalSource]` — embedded.

**On main branch, NONE of these exist.** Merging the resolve branch will:
- Add `CanonicalSource` to `models.py`.
- Add the field to `DependencySelector`.
- Bring in `resolve_models.py` as a new file.

### 8b. apply path

`PackService.apply_dependency_resolution` (resolve branch, pack_service.py:1217)
overwrites `dep.selector` and optionally `dep.selector.canonical_source`.
**Does NOT touch:**
- `Pack.source` (pack-level)
- `PackLock` (separate path: `resolve_pack` regenerates)

If the user changes the dependency's selector via apply, but the lock is stale,
`view_builder.compute_plan` will use the stale lock's sha256 (still valid blob).
But on next `resolve_pack`, the lock regenerates with the new selector's
artifacts → new sha256 → blob re-download. This is correct, just non-obvious.

**Recommendation:** make `apply_dependency_resolution` invalidate the relevant
lock entry, or document explicitly that callers must call `resolve_pack` after
applying.

### 8c. Field name consistency

`models.py:CivitaiSelector` uses `model_id, version_id, file_id`.
`models.py:CanonicalSource` (resolve branch) uses `model_id, version_id,
file_id, repo_id, filename, subfolder, revision, sha256`.
`models.py:HuggingFaceSelector` uses `repo_id, filename, revision, subfolder`.
`models.py:ArtifactProvider` uses `model_id, version_id, file_id, repo_id, filename, revision`.

All consistent within the Civitai/HF respective tuples. Good.

---

## 9. CUSTOM / INSTALL / WORKFLOW PACK FUTURES

### 9a. Custom packs

Today: `PackCategory.CUSTOM`. Pack model accepts the custom category. **But
`Pack.source` is still required** — for a custom pack with no canonical
upstream, this field has to be filled with something fictional or the user
must accept that "source = my local creation" is misleading.

### 9b. Install packs

`PackCategory.INSTALL` enum value exists. Pack model supports it. **No
`Pack.script_manifest` / `Pack.install_dir` / `Pack.ui_root` / `Pack.log_paths` fields.**

For Install Pack future (R1 Bod 3, mostly NOT READY for R1), the team will need
to extend Pack with install-specific fields, OR introduce a new `InstallPack`
subtype, OR store install metadata in `pack_resources` somehow.

The codex audit for Install Pack (`codex-audit-3-install-pack.md`) recommended
NOT shipping it for R1; this audit concurs from a domain-model standpoint —
the model is not ready and force-fitting it would create technical debt.

### 9c. Workflow imports

R1 Bod 4 (Workflow Wizard) expects users to drag a workflow JSON onto a wizard,
which extracts model references and creates a custom pack. The workflow JSON
itself becomes `Pack.workflows[0]` (an existing field). The extracted models
become `Pack.dependencies`. Pack.pack_category = CUSTOM.

**The model already supports this.** The wizard is a UI / pipeline question, not
a domain model question.

### 9d. Where would script_manifest, install_dir, ui_root live?

Three options:
1. Extend `Pack` directly with `install_manifest: Optional[InstallManifest]`.
2. Extend `PackResources` (line 432) with install paths.
3. Discriminated union: `Pack.category_data: Union[ExternalPackData, CustomPackData, InstallPackData]`.

**Option 3** is cleanest but the most disruptive to existing pack.json files.
**Option 1** is least disruptive and maps to the existing schema_version story
(bump to v3, add migration).

---

## 10. UI / ATTACH MODEL

### 10a. UIKindMap covers current asset kinds — except custom_node

```python
class UIKindMap(BaseModel):
    checkpoint: str = "models/checkpoints"
    lora: str = "models/loras"
    vae: str = "models/vae"
    embedding: str = "models/embeddings"
    controlnet: str = "models/controlnet"
    upscaler: str = "models/upscale_models"
    clip: str = "models/clip"
    text_encoder: str = "models/text_encoders"
    diffusion_model: str = "models/diffusion_models"
    unet: str = "models/unet"
```

**Missing:** `custom_node` and `unknown`. ViewBuilder fall-back at view_builder.py:87:
```python
if not kind_path:
    kind_path = f"models/{kind.value}"
```
For a custom node, this becomes `models/custom_node/<filename>` which is wrong;
ComfyUI loads custom nodes from `custom_nodes/<dirname>/`, NOT a subdirectory of
`models/`. Even worse, custom nodes are typically directories with code, not
single safetensors files — a symlink approach won't work.

**Recommendation:** drop custom_node from AssetKind OR make UIKindMap aware of
"this kind is a directory installed elsewhere" semantics. This feeds into the
Install Pack design.

### 10b. default_ui_set storage

`StoreConfig.defaults.ui_set: str = "local"` (line 229) — single source of truth
for default UI set. `UISets` (line 314) maps set names → list of UI names.

Codex finding from earlier audit: there's a parallel "store_ui_sets" in the
React app config. **NEEDS VERIFICATION** — search frontend for this.

### 10c. extra_model_paths.yaml schema

`UIAttacher.generate_extra_model_paths_yaml()` (ui_attach.py:94) returns a
`Dict[str, Any]` and writes it via `yaml.safe_dump()`. The structure is
ad-hoc (built from UIKindMap fields).

**Recommendation:** if more knobs land (per-UI version overrides, multiple
profiles attached at once), introduce a typed `ExtraModelPathsConfig` model
with its own schema_version. Today not urgent.

---

## 11. CROSS-CUTTING CONCERNS

### 11a. Schema versioning

Six top-level models declare `schema_`:
- `synapse.config.v2` (StoreConfig)
- `synapse.ui_sets.v1` (UISets)
- `synapse.pack.v2` (Pack)
- `synapse.lock.v2` (PackLock)
- `synapse.profile.v1` (Profile)
- `synapse.runtime.v1` (Runtime)

`grep -rn "schema_version\|schema_migration\|migrate_pack" src/store/` returns
**zero matches**. The version field is purely declarative.

**When v2 → v3 lands, three things have to be solved at once:**
1. Pydantic must keep accepting old v2 docs (default values, optional fields).
2. A migration step must rewrite the doc to v3 on first read.
3. The `schema_` field gets bumped after migration.

None of this exists today. **Recommendation: write a `migrate_pack_json()` helper
NOW**, even if no-op, so the call site exists and migrations can be added later
without grepping for everywhere a Pack is loaded.

### 11b. Default factories, mutable shared state

Pydantic v2 with `Field(default_factory=...)` is correct. No bare `[]` /
`{}` defaults. **Good.**

### 11c. Pydantic v1 vs v2

`from pydantic import BaseModel, ConfigDict, Field, field_validator,
model_serializer, model_validator` (line 24) — Pydantic v2. Consistent
throughout. **Good.**

### 11d. JSON serialization round-trips

Two patterns to watch:
- `populate_by_name=True` on schema-tagged models so that `schema` (alias) and
  `schema_` (Python attr) both accept input. Output uses the alias. Round-trips
  work.
- `extra="allow"` on `GenerationParameters` (line 477) — extra fields survive
  round-trips. **But extra fields lose type info on load.** A frontend that
  sends `controlnet_strength: 0.5` will get back `0.5` but Pydantic won't
  validate it next time.
- `model_serializer` on GenerationParameters excludes None values to prevent
  ghost fields. **Verify** the deserialization side uses these gracefully.

### 11e. Naming: `pack` vs `Pack` vs `pack_name` vs `name`

Clean separation:
- `Pack` = the model class.
- `pack_name: str` = an identifier when you have just the name string.
- `pack` (lowercase) = a Pack instance.
- `Pack.name` = the pack's own name attribute.

**Consistent.** Nothing to fix.

### 11f. Field aliases that don't serialize symmetrically

The `schema_` field aliases as `schema`. On serialization, `model_dump(by_alias=True)`
emits `"schema": "synapse.pack.v2"`. On default `model_dump()`, it emits
`"schema_": "..."`. **`StoreLayout.write_json` (layout.py:357) uses what mode?**
NEEDS VERIFICATION.

---

## 12. OBSERVED BUGS / SMELLS — full list

| # | Severity | Issue | Refs |
|---|---|---|---|
| 1 | HIGH | `store.layout.pack_path()` does not exist — only `pack_dir()` does | api.py:3334, 3424, 4078, 4581, 4739, 4790, 4859, 4958; layout.py:169 |
| 2 | HIGH | `ProfilePackEntry.enabled` referenced by CLI but not defined | cli.py:527; models.py:1002 |
| 3 | MEDIUM | `pack_dependencies` is informational only — view planning ignores it | view_builder.py (no refs); profile_service.py (no refs) |
| 4 | MEDIUM | `StatusReport.shadowed` always empty (hardcoded) | __init__.py:951-960 |
| 5 | MEDIUM | `ConflictConfig.mode` modeled but never read | models.py:1014; view_builder.py:71 |
| 6 | MEDIUM | `version_constraint` declared but never enforced | models.py:452 |
| 7 | MEDIUM | Default `base_model_aliases` use placeholder zero IDs | models.py:271-307 |
| 8 | MEDIUM | `AssetKind.CUSTOM_NODE` has no UIKindMap path; fall-back wrong | models.py:121; view_builder.py:87 |
| 9 | MEDIUM | Schema `schema_` versions exist but no migration code | grep zero matches |
| 10 | MEDIUM | `InventoryItem.active_in_uis` always `[]` (TODO) | inventory_service.py:377, 613 |
| 11 | MEDIUM | `ResolvedArtifact.kind` duplicated from `PackDependency.kind`; can drift | pack_service.py:697; inventory_service.py:248-253 |
| 12 | MEDIUM | `Pack.source` required, but meaningless for multi-source custom packs | models.py:843 |
| 13 | LOW | `apply_dependency_resolution` doesn't invalidate stale lock entries | pack_service.py:1217 (resolve branch) |
| 14 | LOW | `BaseModelHintResolver` falls back through nested try/except, swallowing errors | dependency_resolver.py:264 |
| 15 | LOW | `Pack.pack_dependencies` has CRUD + tree endpoint but UI cannot rely on view changes | api.py:2964, 3051, 3063, 3091, 3172 |
| 16 | LOW | `work__<pack>` profiles are never garbage-collected | profile_service.py:200+ |

---

## 13. DESIGN RECOMMENDATIONS

### 13a. Fix the breakage first (HIGH severity)

1. **Rename calls in api.py** from `store.layout.pack_path()` to `store.layout.pack_dir()`,
   OR add a thin alias `pack_path = pack_dir` on StoreLayout. Decide which name is
   canonical and migrate. **2-line fix, blocks 8 endpoints.**
2. **Fix `cli.py:527`**: either remove the `.enabled` line, or add `enabled: bool = True`
   to `ProfilePackEntry` AND wire it into `ViewBuilder.compute_plan` (skip disabled
   pack entries). **If we add enabled, treat it as a Release 1+ feature with its own
   plan; don't backdoor it.**

### 13b. Decide pack_dependencies operational vs informational

Two camps:
- **Operational:** `view_builder.compute_plan` recursively expands `pack_dependencies`
  into a flat dependency list before processing. Required deps are added at the
  start; optional deps are added if installed.
  - Pro: composability — "Style LoRA pack depends on Base Model pack" auto-pulls
    the base.
  - Con: more complex view planning, surprise behavior.
- **Informational:** `pack_dependencies` is metadata for the UI to show "this pack
  goes with that pack" but profile semantics remain pack-by-pack.
  - Pro: predictable.
  - Con: user has to manually add base+style to each profile.

Today: informational, but accidentally so. **Pick one and document it.**

### 13c. Consolidate identity hierarchy

One canonical source-of-truth per dependency. The resolve-redesign branch's
`CanonicalSource` is the right anchor:

```
PackDependency
  ├── id (string identity within pack)
  ├── kind (asset kind)
  ├── selector (resolution strategy + selector data)
  │   └── canonical_source (CanonicalSource — frozen identity)
  └── ...

PackLock.resolved[*]
  ├── dependency_id (links back to Pack.dependencies[*].id)
  └── artifact
       ├── canonical_source (CanonicalSource — same identity, post-resolve)
       ├── sha256 (content identity)
       └── download.urls (resolution)
```

`ResolvedArtifact.provider` (today) collapses into `canonical_source`. Less
duplication, single update path.

### 13d. Schema migration scaffolding

```python
# Proposed: src/store/migrations.py
def migrate_pack_v2_to_v3(data: dict) -> dict:
    if data.get("schema") == "synapse.pack.v3":
        return data
    # Migration logic here
    data["schema"] = "synapse.pack.v3"
    return data

# In StoreLayout.load_pack:
data = json.load(...)
data = migrations.migrate_pack(data)
return Pack.model_validate(data)
```

Land the scaffolding now, even with no-op migrations. When v2 → v3 happens, the
implementation slot is already wired.

### 13e. Add discriminated unions where Optional fields imply oneOf

`DependencySelector` today is:
```python
class DependencySelector(BaseModel):
    strategy: SelectorStrategy
    civitai: Optional[CivitaiSelector] = None
    huggingface: Optional[HuggingFaceSelector] = None
    base_model: Optional[str] = None
    url: Optional[str] = None
    local_path: Optional[str] = None
    constraints: Optional[SelectorConstraints] = None
```

A discriminated union by `strategy` would replace the 5 optional fields with
5 typed variants. This is a Pydantic v2 feature (`Discriminator`). Stronger
typing at the cost of a more involved migration.

### 13f. Drop or wire ConflictMode

Either delete `ConflictConfig` entirely (everything's last_wins), OR wire
FIRST_WINS and STRICT into `ViewBuilder.add_entry`. Right now it's lying.

### 13g. Harden inventory's `active_in_uis`

Implement `_compute_active_in_uis()` by:
1. Reading `data/views/<ui>/active/...` symlinks.
2. Resolving each to its blob.
3. Building blob_sha256 → list[ui_name] map.
4. Pass to `_build_item`.

Cheap walk through filesystem on each `build_inventory` call; the numbers are
small (max blobs in a view).

---

## 14. OPEN QUESTIONS for project owner

1. **Should `pack_dependencies` be operational (alter view builder) or
   informational (UI hint only)?** Today it's broken-informational. This is the
   single biggest decision driving R1 Bod 2 (Custom Pack) UX.

2. **Should `ProfilePackEntry` have an `enabled` field?** If yes, it's a R1+
   feature with its own plan. If no, fix cli.py:527 and move on.

3. **Should `Pack.source` be optional or removed?** For custom/install/workflow
   packs the field is misleading.

4. **Drop or wire `ConflictMode`?** If wire, also surface in profile UI as a
   per-profile setting.

5. **Is `WORKFLOW` a `PackCategory` or a `user_tag`?** Audit recommends user_tag.

6. **Where should install pack metadata live?** Extend Pack, extend PackResources,
   or discriminated union?

7. **When are work__ profiles garbage-collected?** Today: never.

8. **Should the resolve-redesign `CanonicalSource` replace `Pack.source` and
   `ResolvedArtifact.provider` outright?** Audit recommends yes — but it's a
   migration.

9. **Should we add cloud backup support (S3/B2)?** Not R1, but BackupConfig
   needs to anticipate.

10. **Should HuggingFace gain a `huggingface_branch_latest` strategy** for
    revision-tracking? Symmetry with Civitai.

---

## 14b. Decision Session — detailní otázky pro vlastníka (CS)

> Tato sekce rozšiřuje Section 14 do konkrétních otázek s příklady. Vlastník musí
> odpovědět **PŘED** implementací bodů Custom Pack / Workflow Wizard / Install Packs /
> Profiles extension. Otázky jsou v češtině pro přesnost komunikace s vlastníkem.

### Otázka 1 — `pack_dependencies`: operational nebo jen informace?

**Aktuální stav:** Pack může mít `pack_dependencies: [{name: "SDXL-base", required: true}]` —
"tento pack potřebuje jiný pack". UI to umí přidat/odebrat, dependency-tree endpoint to
vykreslí. Ale když pak profile aktivuješ, `ViewBuilder` to **úplně ignoruje** — assety
z required pack deps se do ComfyUI nezkopírují.

**Reálný příklad:**
- Vytvoříš LoRA pack "MyLora-SDXL", deklaruješ `pack_dependencies: ["SDXL-base"]`.
- Aktivuješ profil obsahující "MyLora-SDXL" do ComfyUI.
- Aktuální stav: ComfyUI dostane jen LoRA. SDXL base musíš přidat do profilu **zvlášť**.

**Volby:**
- **A) Operational** — `ViewBuilder` rekurzivně expanduje `pack_dependencies` a stáhne
  jejich assety do view. Required deps vždy, optional deps jen když je user explicitně
  aktivuje. Cykly se chytnou už teď ve Phase 2 validátoru.
  - Plus: deklarativnější, "potřebuje SDXL" znamená SDXL přijde automaticky.
  - Minus: profile aktivace může protáhnout dlouhý dep tree, user možná nechce všechny
    transitivní deps.
- **B) Informational** — přejmenovat na `recommended_packs`, UI ukáže jen banner
  "Tento pack doporučuje také: X, Y". Žádné runtime side-effects.
  - Plus: jednodušší, transparentnější, žádné magické chování.
  - Minus: user musí každý dep ručně přidat do profilu (jako dnes).

**Můj tip:** **A operational pro `required: true`, B informational pro `required: false`**.
Required = deklarace "bez toho to nefunguje" → expand. Optional = "tohle se k tomu hodí"
→ jen banner.

**Refs:** `models.py:837 Pack.pack_dependencies`, `view_builder.py compute_plan()`,
DOMAIN-AUDIT Section 4 + 6.

---

### Otázka 2 — Po `apply_resolution()`: kde žije identita zdroje?

**Aktuální stav (na resolve-redesign branchi):** Pack má `Pack.source: PackSource` (kde
se importoval — Civitai URL/HuggingFace/Local) a `DependencySelector.canonical_source`
(resolved fyzický soubor). Když user spustí resolve dependency, redesign zapíše výsledek
do `selector.canonical_source`, ale **`Pack.source` zůstane**.

**Reálný příklad:**
- Importuješ pack z `civitai.com/models/12345` → `Pack.source = {provider: civitai, model_id: 12345}`.
- Pack má dependency `BaseLora` zatím unresolved.
- Resolver najde `BaseLora` na HuggingFace `huggingface.co/foo/bar`. Zapíše do
  `selector.canonical_source = {provider: hf, repo: "foo/bar"}`.
- **Otázka:** Co je teď `Pack.source`? Civitai (nezměněno) nebo HF (přepsáno)?

**Volby:**
- **A) `Pack.source` je creation source, immutable** — řekne "odkud pack vznikl". Po
  resolve se nemění. Current truth pro každou dep je v `selector.canonical_source`
  nebo v lock.json.
  - Plus: historický audit "odkud to máme", git diff je čistý.
  - Minus: UI musí zobrazit dvě věci ("imported from Civitai" + "currently resolved at HF").
- **B) `Pack.source` je current source, přepisuje se** — po resolve dostane nový pack
  origin. Creation se zapíše do nového `Pack.created_from` (immutable historie).
  - Plus: jedna pravda pro "kde to teď je".
  - Minus: ztratíš import metadata (např. Civitai trigger words by se musely zachovat zvlášť).
- **C) Pack.source je creation, lock.json je single source of truth pro current state** —
  `apply_resolution` aktualizuje **jen lock**, ne selector ani source. Pack.json je
  deklarativní wishlist, lock.json je co se opravdu vyresolvuje.
  - Plus: nejčistší architektura, lock je už dnes jediný s reálnými hashe.
  - Minus: vyžaduje rozhodnout, co dělá "save to pack.json after resolve" tlačítko
    (volitelně přesune ze locku do pack source, nebo nikoli).

**Můj tip:** **C** — lock.json už dnes drží sha256 a download URLs, je to přirozené
úložiště. Pack.json zůstane "co user chce", lock je "co se opravdu má". `apply_resolution`
updatuje lock + volitelně přepíše `selector.civitai_*` v pack.json (user explicit "this
is now my preferred source"). `Pack.source` zůstane creation marker.

**Refs:** branch `feat/resolve-model-redesign`, `pack_service.py apply_resolution`,
DOMAIN-AUDIT Section 5 + 8.

---

### Otázka 3 — Workflow imports: nová `PackCategory.WORKFLOW` nebo `CUSTOM` s facetem?

**Aktuální stav:** `PackCategory` má jen `EXTERNAL` (Civitai/HF), `CUSTOM` (manuálně
vyrobený), `INSTALL` (UI prostředí). Workflow Wizard (bod 4 z roadmapy) má importovat
ComfyUI workflow JSONu jako pack — kam patří?

**Reálný příklad:** User dropne `flux-portrait.json` (ComfyUI workflow) do Synapse.
Wizard rozparsuje, najde 3 modely uvnitř (Flux base, LoRA, VAE), dá uživateli vybrat
preview obrázek pro každý model, vytvoří pack.

**Volby:**
- **A) `PackCategory.WORKFLOW`** — nová samostatná kategorie. `Pack` pro workflow má
  povinné pole `workflow: WorkflowDefinition` (obsah workflow.json). Vlastní lifecycle:
  workflow je first-class artifact, ne resource.
  - Plus: čistá separace, Inventory umí filtr "workflow packs only", export workflow
    zpátky do souboru je trivial.
  - Minus: další enum hodnota, další logika v import wizardu, ViewBuilder musí umět
    workflow assety jinak než modely.
- **B) `PackCategory.CUSTOM` s facet polem** — workflow je "custom pack který má navíc
  `imported_workflow_ref: Path`". Žádný nový enum, jen optional field. Custom packs se
  rozdělí na "true custom" (manuálně vyrobený) a "workflow-imported".
  - Plus: méně modelových změn, snáz se napojí na existující Custom Pack flow.
  - Minus: fragmentace sémantiky — "custom pack" pak znamená 2 věci. Inventory filtr
    je složitější.

**Můj tip:** **A** — workflow je sémanticky jiný typ věci než custom-vyrobený model pack.
Lifecycle je jiný (workflow se mění jako celek, ne add/remove single asset), export je
jiný (zpět na .json). Discriminated union je čistá. Plus: jakmile budeš chtít přidat
WORKFLOW search v Browse, nebudeš to řešit přes "custom-with-flag" filter.

**Refs:** `models.py PackCategory`, DOMAIN-AUDIT Section 9.

---

### Otázka 4 — Install packs: jen Synapse-spravované, nebo user-uploadable?

**Aktuální stav:** `PackCategory.INSTALL` enum existuje, ale nemá data (nemodelované,
M7 finding). Před implementací musíme rozhodnout **trust model** — protože install pack
obsahuje **shell skripty které se spustí**.

**Reálný příklad:**
- A) User klikne "Install ComfyUI" → Synapse spustí předpřipravený skript ze svého repa,
  který naklonuje ComfyUI z `github.com/comfyanonymous/ComfyUI`, vytvoří venv, nainstaluje
  requirements.
- B) User stáhne třetí-strany install pack ".synapse-install" soubor z internetu, otevře
  v Synapse, klikne "install" → Synapse spustí jeho skript.

**Volby:**
- **A) First-party only** — install packy jsou součást Synapse repa nebo Synapse-
  spravovaného registru. User si nemůže přidat svůj. Pevný seznam: ComfyUI, Forge,
  A1111, SD.next, Fooocus.
  - Plus: bezpečné, žádný supply-chain attack, code review na úrovni Synapse projektu.
  - Minus: rigidní, user musí čekat na PR pro nový UI / vlastní fork.
- **B) User-uploadable s confirm dialog** — user může importovat ".synapse-install"
  odkudkoli, ale Synapse před spuštěním ukáže celý skript v read-only viewer + "I
  understand this will execute on my system" checkbox.
  - Plus: flexibilní, ekosystém může růst.
  - Minus: typický user neumí code-review shell skript. Útočník může zamaskovat malware.
- **C) Hybrid** — first-party builtin, plus opt-in feature flag pro user-uploadable
  s warning + sandboxing (Docker, bubblewrap).
  - Plus: defaultně bezpečné, power users mají únik.
  - Minus: 2x práce, sandbox je security tar pit.

**Můj tip:** **A pro Release 1**, **C v Release 2+**. Začneme se 4-5 first-party install
packy v Synapse repu. Až bude potřeba (a security model bude stabilní), přidáme
user-uploadable za feature flag.

**Refs:** `models.py PackCategory`, DOMAIN-AUDIT Section 9.

---

### Otázka 5 — ComfyUI custom_nodes: store assety / install pack / extension manager?

**Aktuální stav:** ComfyUI custom nodes jsou git repozitáře (např. `ComfyUI-Manager`,
`ComfyUI-AnimateDiff-Evolved`) nainstalované do `ComfyUI/custom_nodes/`.
`AssetKind.CUSTOM_NODE` enum hodnota existuje, ale UIKindMap ji nemá → ViewBuilder ji
zapíše špatně (`models/custom_node/` místo `custom_nodes/`).

**Reálný příklad:** Workflow z Civitai vyžaduje `ComfyUI-AnimateDiff-Evolved`. User by
mělo umět "nainstaluj custom node" v Synapse. Otázka je kam to patří.

**Volby:**
- **A) Store assety** — custom node je `AssetKind.CUSTOM_NODE`, žije v packu jako
  dependency, downloaduje se přes blob_store. UIKindMap dostane `custom_node:
  "custom_nodes"` mapping.
  - Plus: jednotný flow s modely, profile aktivace ho rozdistribuuje.
  - Minus: custom_nodes jsou git repos, ne single file. Blob_store je pro single-file
    assety. Buď clone-as-tarball, nebo úplně jiný storage.
- **B) Install packy** — custom_node je samostatný `PackCategory.INSTALL`-typed pack,
  "install custom-node X" spustí git clone + pip install requirements.
  - Plus: má smysl — custom node JE install operace (clone + install deps).
  - Minus: install_pack řešíme až v Release 1.1, takže Workflow Wizard by čekal.
- **C) Separátní extension manager** — `CustomNodeService` mimo Pack/Profile model.
  Žije v UI rootu (`ComfyUI/custom_nodes/`), Synapse ho neowne, jen seznam co je
  nainstalováno + clone/update operace.
  - Plus: respektuje to, že ComfyUI Manager už existuje a custom nodes mají vlastní
    ekosystém.
  - Minus: další systém, žije mimo Pack flow, není v Inventory.

**Můj tip:** **C pro Release 1**. Custom nodes jsou prostě jiná zvěř — git repos,
vlastní deps, vlastní update flow. ComfyUI už má `ComfyUI-Manager` extension který
tohle dělá. Synapse pro Release 1 jen ukáže "tohle workflow potřebuje tyhle custom_nodes",
odkáže usera ven a v UI rootu nech ho ať si je nainstaluje. Plný integration → Release 2.

**Refs:** `models.py:42 AssetKind.CUSTOM_NODE`, `models.py:121 UIKindMap`,
DOMAIN-AUDIT Section 10.

---

### Otázka 6 — `BlobLocation.CONFLICT`: implementovat sync nebo enum hodnotu odstranit?

**Aktuální stav:** `BlobLocation` enum má hodnoty `LOCAL_ONLY`, `BACKUP_ONLY`, `BOTH`,
`CONFLICT`. První tři se počítají v `_build_item()`, **`CONFLICT` se nikdy nenastaví**.
Backup sync je dnes one-way: `sync()` = "kopíruj local → backup". Pokud na backupu je
jiný blob se stejným sha256 (nemůže být — sha256 je content hash) ale **jiný název file
path**, není definováno co dělat.

**Reálný příklad:** User má `flux-base.safetensors` lokálně. Ze záloh dostane
`flux_base.safetensors` (jiný název, stejný hash). Mají žít vedle sebe? Mergnout? Rename?

**Volby:**
- **A) Push/pull only, odstranit `CONFLICT` enum** — sync je explicit one-way. User řekne
  "push local → backup" nebo "pull backup → local". Při kolizi názvu se rename (suffix
  _1, _2). Žádný auto-merge.
  - Plus: jednoduché, deterministické.
  - Minus: user musí explicitně zvolit směr pokaždé.
- **B) Bidirectional merge s conflict resolution UI** — když se backup a local liší,
  zobrazí dialog "Backup má X, local má Y, který chceš?". `CONFLICT` se zobrazí
  v Inventory tabulce.
  - Plus: full sync model, "true bidirectional".
  - Minus: víc UI, victims of merge dialogs nudí.

**Můj tip:** **A pro Release 1**. Sync model je už dnes jednoduchý, neexistuje use case
pro skutečný conflict (sha256 = content hash, takže rozdílný file path se stejným hashem
je jen alias). Odstranit `BlobLocation.CONFLICT` z enumu, jednodušší kód.

**Refs:** `models.py BlobLocation`, `inventory_service.py`, `backup_service.py`,
DOMAIN-AUDIT Section 7.

---

### Vedlejší 3 otázky závislé na #1 (rychlé odpovědi)

Pokud #1 bude **A operational**:

**6a)** `optional` deps v `pack_dependencies` — affectují `is_fully_resolved()`?
- **A)** Ano, optional unresolved = lock není fully resolved. Profile activation s warning.
- **B)** Ne, jen required affectují fully_resolved. Optional unresolved = no-op.
- **Tip:** B (jinak optional ztratí význam).

**6b)** Custom packs — backend-updatable když deps mají `FOLLOW_LATEST`?
- **A)** Ano, update job pravidelně přepíše lock.json novou verzí.
- **B)** Ne, FOLLOW_LATEST je jen UI hint, user musí kliknout "update".
- **Tip:** B (no surprise updates v custom packu, custom = user controls everything).

**6c)** Dependency IDs (např. `civitai.model_id`) — user-editable po vytvoření locku?
- **A)** Ano kdykoli, user může změnit zdroj.
- **B)** Po vytvoření locku read-only, jen "remove dependency" + "add new" flow.
- **Tip:** A v pack.json (declarative wish), automatický rebuild lock.json po změně.

---

### Odpovědi vlastníka

| Otázka | Volba | Datum | Poznámka |
|--------|-------|-------|----------|
| 1 — pack_dependencies | ❓ | TBD | TBD |
| 2 — apply_resolution | ❓ | TBD | TBD |
| 3 — WORKFLOW category | ❓ | TBD | TBD |
| 4 — install packs trust | ❓ | TBD | TBD |
| 5 — custom_nodes | ❓ | TBD | TBD |
| 6 — BlobLocation.CONFLICT | ❓ | TBD | TBD |
| 6a — optional deps fully_resolved | ❓ | TBD | TBD |
| 6b — FOLLOW_LATEST auto-update | ❓ | TBD | TBD |
| 6c — dep IDs editable | ❓ | TBD | TBD |

> Po vyplnění tabulky → vytvořit `plans/PLAN-Stabilization-Release-1.md` s konkrétním
> implementačním plánem podle odpovědí.

---

## 15. Companion file: `codex-domain-audit.md`

The codex audit is being written in parallel — read it after this one.
**Cross-validate findings before acting.** Where Claude says HIGH and codex
says MEDIUM, dig deeper. Where the two disagree on whether a field is wired,
read the source code one more time.

---

## Appendix A: Files read for this audit

| File | Lines | Role |
|---|---|---|
| `src/store/models.py` | 1573 | Domain models — primary subject |
| `src/store/layout.py` | 574 | Persistence paths and JSON I/O |
| `src/store/__init__.py` | 1693 | Store facade — confirmed `pack_path` calls |
| `src/store/pack_service.py` | 1349 | Pack import / resolve / install |
| `src/store/profile_service.py` | 539 | Profile lifecycle |
| `src/store/view_builder.py` | 527 | ViewPlan / build / activate |
| `src/store/dependency_resolver.py` | 368 | Per-strategy resolvers |
| `src/store/inventory_service.py` | 945 | Inventory + cleanup + impact + verify |
| `src/store/blob_store.py` | 611 | Content-addressed blob store |
| `src/store/ui_attach.py` (skim) | 585 | extra_model_paths.yaml + symlink attach |
| `src/store/api.py` (grep only) | ~5000 | Endpoint surface — confirmed pack_path bugs |
| `src/store/cli.py` (grep only) | ~1000 | CLI — confirmed pack_entry.enabled bug |
| `feat/resolve-model-redesign:src/store/resolve_models.py` | ~200 | Resolve DTOs (branch only) |
| `feat/resolve-model-redesign:src/store/models.py` (CanonicalSource block) | — | Branch additions |
| `plans/audits/codex-domain-audit-raw.md` (transcript scan) | 11291 | Codex's reading-only run; harvested 2 commentary blocks |

## Appendix B: How to act on this audit

1. Read this file end-to-end.
2. Read `codex-domain-audit.md` (companion) end-to-end.
3. Compile `MEMORY.md` decision pointer with disposition for each open question
   in section 14.
4. **Before any R1 finishing implementation begins**, fix HIGH severity bugs
   (pack_path AttributeError, cli.py:527 AttributeError) on a small dedicated
   branch.
5. Treat MEDIUM severity bugs as gating for the relevant R1 bod:
   - `pack_dependencies` semantics → blocks Bod 2 (Custom Pack) and Bod 4
     (Workflow Wizard).
   - Schema migration scaffolding → blocks any pack_category extension.
   - `ConflictConfig.mode` decision → blocks Profiles UX (Bod 5).
   - `CanonicalSource` consolidation → blocks resolve-redesign merge (Bod 1).
6. LOW severity issues are cleanup; track separately, not in R1 critical path.

---

*Audit by Claude Opus 4.7 — 2026-05-02. Cross-validate with `codex-domain-audit.md`.*
