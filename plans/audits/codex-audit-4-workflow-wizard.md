# Audit: Release 1 Point 4 - Workflow Wizard

Date: 2026-05-02

Scope:

- Spec reviewed: `plans/PLAN-Workflow-Wizard.md`
- Backend reviewed: `src/workflows/`, `src/store/api.py`, `src/store/models.py`, profile/view services, CLI/MCP workflow paths
- Frontend reviewed: pack detail workflow/parameters sections, upload/import modals, pack detail hooks/page
- Search terms: `workflow`, `comfyui`, `a1111`, `forge`, `sd.next`, `sdnext`, `generator`

## Executive Summary

- Workflow storage and simple ComfyUI generation exist, but the planned Workflow Wizard does not exist.
- The current UI has "Generate Default" and "Upload" buttons, not the 3-step wizard from the spec.
- Default workflow generation is ComfyUI-only.
- Forge, A1111, and SD.Next are supported by Profiles path mapping, but not by workflow/config generation.
- There is no template system under `src/workflow/templates` or `src/workflows/templates`.
- There are two separate generator implementations:
  - Legacy `src/workflows/generator.py` using `src.core.models`.
  - Current v2 API inline generator in `src/store/api.py`.
- Imported/uploaded workflow JSON can be attached to an existing pack.
- The global Import modal appears to claim workflow import, but the API request model requires `url`, so the frontend workflow import path is likely broken.
- Uploaded workflow JSON is not scanned for model/custom node dependencies in the pack-detail upload flow.
- MCP tools can scan/resolve workflow dependencies, but that capability is not wired into user-facing import/upload flows.
- Workflow files are stored separately under `state/packs/<Pack>/workflows/`; `pack.json` stores only metadata entries in `workflows`.
- Workflow activation is ComfyUI-specific symlink management to ComfyUI's workflow folder, separate from Profiles model symlink views.

## Spec Baseline

- The spec status is explicitly planning/draft: `plans/PLAN-Workflow-Wizard.md:3` and `plans/PLAN-Workflow-Wizard.md:4`.
- The spec requires preserving `pack.parameters`: `plans/PLAN-Workflow-Wizard.md:15`.
- The spec requires visual source selection from preview images: `plans/PLAN-Workflow-Wizard.md:16`.
- The spec requires all target UIs and modular templates: `plans/PLAN-Workflow-Wizard.md:17`.
- The spec requires storing generated workflows into the pack: `plans/PLAN-Workflow-Wizard.md:18`.
- The wizard should read, not modify, pack parameters: `plans/PLAN-Workflow-Wizard.md:33` through `plans/PLAN-Workflow-Wizard.md:40`.
- The UI design is a 3-step wizard:
  - Select Target UI: `plans/PLAN-Workflow-Wizard.md:80` through `plans/PLAN-Workflow-Wizard.md:93`.
  - Select Parameter Source: `plans/PLAN-Workflow-Wizard.md:95` through `plans/PLAN-Workflow-Wizard.md:119`.
  - Configure Workflow: `plans/PLAN-Workflow-Wizard.md:121` through `plans/PLAN-Workflow-Wizard.md:147`.
- Planned storage layout includes per-UI folders under `workflows/`: `plans/PLAN-Workflow-Wizard.md:156` through `plans/PLAN-Workflow-Wizard.md:168`.
- Planned template/generator layout is `src/workflow/templates`, `src/workflow/generators`, and `src/workflow/service.py`: `plans/PLAN-Workflow-Wizard.md:171` through `plans/PLAN-Workflow-Wizard.md:193`.
- Planned generator interface is an abstract `WorkflowGenerator` with UI name, extension, generate, and options methods: `plans/PLAN-Workflow-Wizard.md:195` through `plans/PLAN-Workflow-Wizard.md:227`.
- Planned supported UIs are ComfyUI, Forge, A1111, SDnext, Fooocus, and InvokeAI: `plans/PLAN-Workflow-Wizard.md:270` through `plans/PLAN-Workflow-Wizard.md:280`.
- All implementation phases remain unchecked in the spec: `plans/PLAN-Workflow-Wizard.md:283` through `plans/PLAN-Workflow-Wizard.md:320`.
- The spec's own open questions include per-UI model paths, editing, UI version differences, and validation: `plans/PLAN-Workflow-Wizard.md:330` through `plans/PLAN-Workflow-Wizard.md:338`.

## 1. What Exists

### Backend - Current v2 Store Models

- `src/store/models.py` is the current v2 store model layer.
- `PackResources` has `workflows_keep_in_git`: `src/store/models.py:432` through `src/store/models.py:435`.
- `PackDependencyRef` comments explicitly mention workflow packs depending on required LoRA/VAE packs: `src/store/models.py:438` through `src/store/models.py:445`.
- `GenerationParameters` supports known workflow-relevant fields plus `extra="allow"` for arbitrary fields: `src/store/models.py:460` through `src/store/models.py:478`.
- Parameter fields include sampler, scheduler, steps, cfg, clip skip, denoise, size, seed, LoRA strength, eta, and hires settings: `src/store/models.py:479` through `src/store/models.py:498`.
- `WorkflowInfo` is metadata only: `name`, `filename`, `description`, `source_url`, `is_default`: `src/store/models.py:794` through `src/store/models.py:800`.
- Current v2 `Pack` has `parameters`, `parameters_source`, `model_info`, and `workflows`: `src/store/models.py:869` through `src/store/models.py:875`.
- `Pack` supports `pack_category`, including custom packs: `src/store/models.py:78` through `src/store/models.py:89` and `src/store/models.py:837` through `src/store/models.py:843`.

### Backend - Workflow Storage Paths

- `StoreLayout.pack_workflows_path()` returns `state/packs/<Pack>/workflows`: `src/store/layout.py:189` through `src/store/layout.py:191`.
- This is flat `workflows/`, not `workflows/comfyui`, `workflows/forge`, etc.
- `src/store/api.py` enriches pack detail workflow entries from files under that folder: `src/store/api.py:1763` through `src/store/api.py:1811`.
- Files present on disk but missing from `pack.json` are exposed as orphaned workflows: `src/store/api.py:1813` through `src/store/api.py:1837`.

### Backend - Current v2 Workflow Endpoints

- List workflow files: `GET /api/packs/{pack_name}/workflows`: `src/store/api.py:4044` through `src/store/api.py:4065`.
- Generate default workflow: `POST /api/packs/{pack_name}/generate-workflow`: `src/store/api.py:4068` through `src/store/api.py:4148`.
- Create symlinks for all pack workflows to ComfyUI: `POST /api/packs/{pack_name}/workflow/symlink`: `src/store/api.py:4568` through `src/store/api.py:4627`.
- Create symlink for one workflow: `POST /api/packs/{pack_name}/workflow/{filename}/symlink`: `src/store/api.py:4630` through `src/store/api.py:4677`.
- Read workflow JSON: `GET /api/packs/{pack_name}/workflow/{filename}`: `src/store/api.py:4679` through `src/store/api.py:4703`.
- Delete workflow file and metadata: `DELETE /api/packs/{pack_name}/workflow/{filename}`: `src/store/api.py:4706` through `src/store/api.py:4759`.
- Add metadata for an already uploaded file: `POST /api/packs/{pack_name}/workflow/add`: `src/store/api.py:4771` through `src/store/api.py:4832`.
- Rename workflow display name and/or filename: `PATCH /api/packs/{pack_name}/workflow/{filename}`: `src/store/api.py:4841` through `src/store/api.py:4925`.
- Upload JSON file to a pack: `POST /api/packs/{pack_name}/workflow/upload-file`: `src/store/api.py:4928` through `src/store/api.py:4995`.

### Backend - Current v2 Generator

- Current API generation is inline in `src/store/api.py`, not in `src/workflows`.
- The endpoint loads the v2 `Pack`, detects architecture, collects checkpoint/LoRA deps, calls `_build_v2_workflow`, saves JSON, and updates `pack.workflows`: `src/store/api.py:4076` through `src/store/api.py:4133`.
- `_detect_architecture()` maps SD 1.x, SDXL, Pony, Illustrious, Flux, etc. to architecture strings: `src/store/api.py:4151` through `src/store/api.py:4190`.
- `_build_v2_workflow()` is explicitly a ComfyUI workflow builder: `src/store/api.py:4193` through `src/store/api.py:4194`.
- It reads `pack.parameters` or creates empty `GenerationParameters`: `src/store/api.py:4220` through `src/store/api.py:4221`.
- It maps width, height, sampler, scheduler, steps, cfg, and seed: `src/store/api.py:4231` through `src/store/api.py:4237`.
- It uses checkpoint dependency `expose.filename`: `src/store/api.py:4239` through `src/store/api.py:4242`.
- It builds prompt text from pack trigger words/model info: `src/store/api.py:4244` through `src/store/api.py:4253`.
- It creates ComfyUI nodes for `CheckpointLoaderSimple`, `LoraLoader`, optional `CLIPSetLastLayer`, `CLIPTextEncode`, `EmptyLatentImage`, `KSampler`, `VAEDecode`, and `SaveImage`: `src/store/api.py:4261` through `src/store/api.py:4547`.
- The final JSON has ComfyUI graph keys `nodes`, `links`, `groups`, `config`, `extra`, and `version`: `src/store/api.py:4548` through `src/store/api.py:4565`.

### Backend - Legacy `src/workflows`

- `src/workflows/__init__.py` exports scanner, resolver, and generator classes: `src/workflows/__init__.py:1` through `src/workflows/__init__.py:20`.
- `src/workflows/generator.py` is a legacy ComfyUI generator using `src.core.models`: `src/workflows/generator.py:15` through `src/workflows/generator.py:18`.
- Legacy `WorkflowGenerator` is concrete and ComfyUI-specific, not the abstract interface from the spec: `src/workflows/generator.py:204` through `src/workflows/generator.py:227`.
- It has a `NodeBuilder` helper for ComfyUI graph construction: `src/workflows/generator.py:87` through `src/workflows/generator.py:201`.
- It maps sampler/scheduler names: `src/workflows/generator.py:21` through `src/workflows/generator.py:65`.
- It detects base model architecture: `src/workflows/generator.py:67` through `src/workflows/generator.py:84` and `src/workflows/generator.py:229` through `src/workflows/generator.py:248`.
- It builds a similar ComfyUI graph with checkpoint, LoRA, CLIP skip, prompts, latent, sampler, VAE decode, preview, and save nodes: `src/workflows/generator.py:274` through `src/workflows/generator.py:507`.
- It returns `WorkflowInfo` metadata from `generate_pack_workflow()`: `src/workflows/generator.py:515` through `src/workflows/generator.py:525`.
- This legacy generator is not called by the current v2 pack detail workflow endpoint.

### Backend - Workflow Scanner and Resolver

- `src/workflows/scanner.py` parses ComfyUI workflow JSON and extracts model assets/custom nodes: `src/workflows/scanner.py:1` through `src/workflows/scanner.py:9`.
- It models `WorkflowNode`, `ScannedAsset`, and `WorkflowScanResult`: `src/workflows/scanner.py:20` through `src/workflows/scanner.py:77`.
- Loader-node mappings cover checkpoints, diffusion models, LoRAs, VAE, CLIP/text encoders, ControlNet, upscalers, and embeddings: `src/workflows/scanner.py:94` through `src/workflows/scanner.py:126`.
- It supports workflows where `nodes` is a list or a dict keyed by node id: `src/workflows/scanner.py:165` through `src/workflows/scanner.py:189`.
- It extracts model names from `widgets_values`: `src/workflows/scanner.py:194` through `src/workflows/scanner.py:208`.
- It has special extra extraction for `DualCLIPLoader`: `src/workflows/scanner.py:219` through `src/workflows/scanner.py:229`.
- It identifies custom nodes by non-core prefixes and `cnr_id`: `src/workflows/scanner.py:231` through `src/workflows/scanner.py:266`.
- It identifies output/input nodes: `src/workflows/scanner.py:241` through `src/workflows/scanner.py:247`.
- It can deduplicate asset references: `src/workflows/scanner.py:268` through `src/workflows/scanner.py:279`.
- `extract_dependencies_from_workflow()` returns asset dependencies only, not custom nodes: `src/workflows/scanner.py:316` through `src/workflows/scanner.py:321`.
- `src/workflows/resolver.py` maps workflow-scan output to model/custom-node sources: `src/workflows/resolver.py:1` through `src/workflows/resolver.py:8`.
- `NodeRegistry` can load ComfyUI-Manager custom node registry formats: `src/workflows/resolver.py:33` through `src/workflows/resolver.py:115`.
- `DependencyResolver` has known model patterns, known HuggingFace mappings, and known custom-node mappings: `src/workflows/resolver.py:117` through `src/workflows/resolver.py:216`.
- It resolves custom nodes to `CustomNodeDependency`: `src/workflows/resolver.py:221` through `src/workflows/resolver.py:255`.
- It enriches scanned assets with likely source info: `src/workflows/resolver.py:257` through `src/workflows/resolver.py:299`.
- It returns `(asset_deps, node_deps)` from `resolve_workflow_dependencies()`: `src/workflows/resolver.py:301` through `src/workflows/resolver.py:325`.

### Backend - MCP Workflow Tools

- MCP has `scan_workflow`, `scan_workflow_file`, `check_workflow_availability`, `list_custom_nodes`, and `resolve_workflow_dependencies`: `src/avatar/mcp/store_server.py:829` through `src/avatar/mcp/store_server.py:1118`.
- `scan_workflow` calls `WorkflowScanner` and reports assets/custom nodes: `src/avatar/mcp/store_server.py:833` through `src/avatar/mcp/store_server.py:876`.
- `scan_workflow_file` restricts to `.json` under an allowed base directory and scans via `WorkflowScanner`: `src/avatar/mcp/store_server.py:882` through `src/avatar/mcp/store_server.py:938`.
- `check_workflow_availability` compares scanned asset names to store inventory display names: `src/avatar/mcp/store_server.py:944` through `src/avatar/mcp/store_server.py:1001`.
- `list_custom_nodes` resolves custom node packages: `src/avatar/mcp/store_server.py:1007` through `src/avatar/mcp/store_server.py:1063`.
- `resolve_workflow_dependencies` resolves assets/custom nodes but returns a text report, not pack edits: `src/avatar/mcp/store_server.py:1071` through `src/avatar/mcp/store_server.py:1118`.

### Backend - Legacy CLI Workflow Paths

- CLI advertises `synapse import --workflow <file>` and `synapse run <pack-name> [--workflow]`: `cli.py:7` through `cli.py:17`.
- CLI imports legacy `src.core.pack_builder.PackBuilder` and `src.workflows.scanner.WorkflowScanner`: `cli.py:31` through `cli.py:38`.
- CLI workflow import calls `builder.build_from_workflow(workflow_path)`: `cli.py:132` through `cli.py:140`.
- `PackBuilder` in `src/core/pack_builder.py` does not define `build_from_workflow`; only `build_from_civitai_url` was found: `src/core/pack_builder.py:640`.
- CLI copies source workflow files to `pack_dir/workflows`: `cli.py:176` through `cli.py:187`.
- CLI derived workflow run is explicitly unavailable because `DerivedWorkflowGenerator` is missing: `cli.py:526` through `cli.py:550`.
- This legacy CLI path is likely stale/broken. NEEDS VERIFICATION: run CLI tests or direct `synapse import --workflow` once a configured legacy store is available.

### Frontend - Pack Workflow Section

- `PackWorkflowsSection` displays ComfyUI workflows with symlink management: `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:1` through `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:15`.
- It receives workflow list, pack name, unresolved-base-model flag, and handlers for symlink/delete/generate/upload: `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:35` through `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:72`.
- Each workflow card shows name, filename, default badge, ComfyUI link/broken status, local path, description, download, and delete actions: `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:89` through `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:240`.
- Download opens `/api/packs/{pack}/workflow/{filename}` in a browser tab: `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:201` through `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:215`.
- Header has Upload and Generate Default buttons: `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:279` through `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:310`.
- Generate is disabled when `needsBaseModel` is true: `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:291` through `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:323`.
- Empty state says to generate default or upload: `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:345` through `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:352`.

### Frontend - Pack Detail Wiring

- `PackDetailPage` always renders `PackWorkflowsSection` after dependencies: `apps/web/src/components/modules/PackDetailPage.tsx:383` through `apps/web/src/components/modules/PackDetailPage.tsx:400`.
- The unresolved flag passed to workflows is `pack.has_unresolved`: `apps/web/src/components/modules/PackDetailPage.tsx:385` through `apps/web/src/components/modules/PackDetailPage.tsx:388`.
- `PackDetailPage` always renders `PackParametersSection` below workflows: `apps/web/src/components/modules/PackDetailPage.tsx:402` through `apps/web/src/components/modules/PackDetailPage.tsx:410`.
- Upload workflow modal calls `packData.uploadWorkflow()` and closes immediately: `apps/web/src/components/modules/PackDetailPage.tsx:497` through `apps/web/src/components/modules/PackDetailPage.tsx:506`.
- No wizard component is imported or rendered in `PackDetailPage`.

### Frontend - Workflow Mutations

- Generate calls `POST /api/packs/{pack}/generate-workflow`: `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:359` through `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:377`.
- Create symlink calls `POST /api/packs/{pack}/workflow/symlink` with a filename body: `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:379` through `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:399`.
- Delete symlink calls `DELETE /api/packs/{pack}/workflow/{filename}/symlink`: `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:401` through `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:420`.
- Delete workflow calls `DELETE /api/packs/{pack}/workflow/{filename}`: `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:422` through `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:441`.
- Upload workflow calls `POST /api/packs/{pack}/workflow/upload-file`: `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:443` through `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:467`.

### Frontend - Upload Existing Workflow to Existing Pack

- `UploadWorkflowModal` accepts `.json`, name, and optional description: `apps/web/src/components/modules/pack-detail/modals/UploadWorkflowModal.tsx:29` through `apps/web/src/components/modules/pack-detail/modals/UploadWorkflowModal.tsx:49`.
- File selection auto-populates name from filename: `apps/web/src/components/modules/pack-detail/modals/UploadWorkflowModal.tsx:75` through `apps/web/src/components/modules/pack-detail/modals/UploadWorkflowModal.tsx:84`.
- Submit only sends file/name/description: `apps/web/src/components/modules/pack-detail/modals/UploadWorkflowModal.tsx:86` through `apps/web/src/components/modules/pack-detail/modals/UploadWorkflowModal.tsx:94`.
- The modal does not show scanned dependencies, missing models, custom nodes, or target UI.

### Frontend - Global Import Modal Workflow Tab

- `ImportModal` has tabs `url` and `workflow`: `apps/web/src/components/modules/ImportModal.tsx:14` through `apps/web/src/components/modules/ImportModal.tsx:20`.
- Workflow tab reads a JSON file and sends `{workflow_json: workflowJson}` to `/api/packs/import`: `apps/web/src/components/modules/ImportModal.tsx:61` through `apps/web/src/components/modules/ImportModal.tsx:83`.
- The API `ImportRequest` requires `url: str`: `src/store/api.py:188` through `src/store/api.py:216`.
- The `/api/packs/import` implementation only imports Civitai URLs via `store.import_civitai(...)`: `src/store/api.py:2046` through `src/store/api.py:2106`.
- Therefore global workflow import is not implemented in the v2 API and likely fails request validation. NEEDS VERIFICATION: exercise the UI/API path because Pydantic will likely reject the missing `url`.

### Frontend - Parameters

- `PackParametersSection` displays parameters dynamically by category: `apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:1` through `apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:13`.
- Categories include generation, resolution, hires, model, controlnet, inpainting, batch, advanced, SDXL, FreeU, IPAdapter, custom: `apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:38` through `apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:57`.
- AI note keys are explicitly separated from normal parameters for display: `apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:76` through `apps/web/src/components/modules/pack-detail/sections/PackParametersSection.tsx:127`.
- The edit modal converts string values to booleans/numbers/strings before saving: `apps/web/src/components/modules/pack-detail/modals/EditParametersModal.tsx:1103` through `apps/web/src/components/modules/pack-detail/modals/EditParametersModal.tsx:1127`.
- Parameter updates call `PATCH /api/packs/{pack}/parameters`: `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:274` through `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:294`.
- Backend parameter update merges into existing parameters and writes `pack.json`: `src/store/api.py:3492` through `src/store/api.py:3535`.
- This is general parameter editing, not workflow wizard source selection.

## 2. Create Flow

- A default workflow generation flow exists as a direct button.
- A wizard for default workflow generation does not exist.
- There is no Step 1 target UI selection.
- There is no Step 2 visual parameter-source selection from previews.
- There is no Step 3 workflow-specific configuration UI.
- There is no user-editable workflow name in the generate flow.
- There is no UI-specific option selection.
- There is no upscaler/controlnet/inpainting/batch generator configuration step.
- Actual generated target UI: ComfyUI only.
- Actual output format: ComfyUI JSON workflow.
- No Forge generator exists.
- No A1111 generator exists.
- No SD.Next generator exists.
- No per-UI templates exist.
- No `GeneratorOptions` or `ConfigOption` interface exists.
- Existing `WorkflowGenerator` classes are concrete ComfyUI builders, not the planned abstract generator interface.
- Current v2 generation is embedded in `src/store/api.py`, which is a maintenance/integration smell.
- Current legacy generation is in `src/workflows/generator.py`, but it uses legacy dataclasses and is not wired into v2 API.

## 3. Import Flow

- Existing-pack upload exists via Pack Detail.
- It lands in `state/packs/<Pack>/workflows/<filename>` through `upload_workflow_file()`: `src/store/api.py:4941` through `src/store/api.py:4955`.
- If a name is provided, metadata is appended to `pack.workflows`: `src/store/api.py:4956` through `src/store/api.py:4983`.
- The upload endpoint validates JSON syntax only: `src/store/api.py:4948` through `src/store/api.py:4952`.
- It does not validate that the JSON is a ComfyUI workflow.
- It does not scan for model dependencies.
- It does not scan for LoRA dependencies.
- It does not scan for VAE dependencies.
- It does not scan for text encoder/diffusion model dependencies.
- It does not scan for custom node dependencies.
- It does not add dependencies to the pack.
- It does not add pack-to-pack dependencies.
- It does not create a custom pack.
- Global workflow import UI exists but is likely broken, because the frontend sends `workflow_json` and the backend import request requires `url`.
- MCP has a working scan/resolve capability, but it is not connected to the upload/import UI.

## 4. Cross-Link With Resolve

- For generated workflows, the UI disables generation when `pack.has_unresolved` is true: `apps/web/src/components/modules/PackDetailPage.tsx:385` through `apps/web/src/components/modules/PackDetailPage.tsx:388`.
- The workflow section shows a "resolve first" tooltip when generation is disabled: `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:311` through `apps/web/src/components/modules/pack-detail/sections/PackWorkflowsSection.tsx:323`.
- For uploaded/imported workflows, no missing-model scan is run.
- Therefore no missing-model result is available to trigger resolve.
- `WorkflowScanner` plus `DependencyResolver` could produce dependencies, but no API endpoint wires them into `PackService.resolve_pack`.
- MCP `check_workflow_availability` checks inventory, but does not mutate pack dependencies: `src/avatar/mcp/store_server.py:944` through `src/avatar/mcp/store_server.py:1001`.
- MCP `resolve_workflow_dependencies` reports suggested sources, but does not create dependencies or call resolve: `src/avatar/mcp/store_server.py:1071` through `src/avatar/mcp/store_server.py:1118`.
- Result: import-to-resolve is not implemented.

## 5. Cross-Link With Custom Pack

- v2 models support `pack_category = custom`: `src/store/models.py:78` through `src/store/models.py:89`.
- Custom plugin declares workflows editable: `apps/web/src/components/modules/pack-detail/plugins/CustomPlugin.tsx:108` through `apps/web/src/components/modules/pack-detail/plugins/CustomPlugin.tsx:117`.
- Civitai plugin also allows workflow editing for imported external packs: `apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx:340` through `apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx:352`.
- Install plugin disables workflow editing: `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:271` through `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:280`.
- There is an endpoint to create an empty custom pack and create resources/workflows directories: `src/store/api.py:3284` and `src/store/api.py:3336`.
- Uploading a workflow to an existing pack does not change `pack_category`.
- Global workflow import does not create a custom pack in the v2 API.
- No import-workflow-to-custom-pack flow exists.
- No flow creates a workflow-only custom pack with scanned dependencies.
- No flow adds imported workflow dependencies as `pack_dependencies`.

## 6. Cross-Link With Parameters

- Current generation maps a small subset of `pack.parameters` into ComfyUI nodes.
- `width` and `height` map to `EmptyLatentImage.widgets_values`: `src/store/api.py:4231` through `src/store/api.py:4232` and `src/store/api.py:4427` through `src/store/api.py:4442`.
- `sampler` maps through `SAMPLER_MAPPING` into `KSampler.widgets_values`: `src/store/api.py:4195` through `src/store/api.py:4206` and `src/store/api.py:4233`.
- `scheduler` is not read from `params.scheduler`; scheduler is derived from `params.sampler`: `src/store/api.py:4208` through `src/store/api.py:4218` and `src/store/api.py:4234`.
- `steps` maps to `KSampler.widgets_values`: `src/store/api.py:4235` and `src/store/api.py:4445` through `src/store/api.py:4466`.
- `cfg_scale` maps to `KSampler.widgets_values`: `src/store/api.py:4236` and `src/store/api.py:4445` through `src/store/api.py:4466`.
- `seed` maps to `KSampler.widgets_values`, but falsey seed `0` becomes random seed `0` anyway due to `if params.seed and params.seed >= 0`: `src/store/api.py:4237`.
- `clip_skip` adds a `CLIPSetLastLayer` node only when greater than 1: `src/store/api.py:4338` through `src/store/api.py:4368`.
- `denoise` is not mapped; KSampler denoise is hardcoded to `1.0`: `src/store/api.py:4465`.
- `strength` in v2 `GenerationParameters` is not used for LoRA strength.
- LoRA strength uses `pack.model_info.strength_recommended` when available, otherwise `1.0`: `src/store/api.py:4294` through `src/store/api.py:4297`.
- `hires_fix`, `hires_upscaler`, `hires_steps`, `hires_denoise`, `hires_scale`, `hires_width`, and `hires_height` are not mapped.
- `vae` recommendations are displayed as AI notes in the UI but not mapped to a `VAELoader`.
- ControlNet/IPAdapter/FreeU/SDXL refiner/inpainting/batch fields are not mapped to nodes.
- Prompt mapping is not from `pack.parameters`; generated prompt is trigger words plus `masterpiece, best quality`.
- Negative prompt is hardcoded.
- Preview image metadata is not used in generation.
- The spec's "read `pack.parameters`, never modify" is partially met by generate flow; however generated workflow metadata is written back to `pack.json` under `workflows`.

## 7. Cross-Link With Profiles

- Profiles and view builder support ComfyUI, Forge, A1111, and SD.Next folder mappings: `src/store/models.py:139` through `src/store/models.py:196`.
- ViewBuilder builds per-UI symlink trees from resolved pack dependencies into UI-specific folders: `src/store/view_builder.py:212` through `src/store/view_builder.py:272`.
- It uses `kind_map.get_path(kind)` to choose target folders: `src/store/view_builder.py:85` through `src/store/view_builder.py:90`.
- It creates symlinks from view paths to blobs: `src/store/view_builder.py:318` through `src/store/view_builder.py:328`.
- It atomically activates a profile through an `active` symlink: `src/store/view_builder.py:375` through `src/store/view_builder.py:409`.
- `ProfileService.use()` builds and activates views for requested UIs: `src/store/profile_service.py:181` through `src/store/profile_service.py:255`.
- This solves model file placement when a pack dependency is resolved and installed.
- Workflow JSON itself is not rewritten to use profile paths.
- ComfyUI generated workflows reference exposed filenames, not absolute paths.
- For ComfyUI, this should work if ComfyUI is configured to see the active profile directory. NEEDS VERIFICATION: audit how UI environment is actually pointed at `data/views/comfyui/active`.
- Workflow symlinking to ComfyUI's `user/default/workflows` is separate from Profiles model symlinks: `src/store/api.py:4590` through `src/store/api.py:4612`.
- Forge/A1111/SD.Next do not have workflow/config symlink handling.

## 8. Editor

- There is no workflow JSON editor UI.
- Pack detail lets users download/read JSON through `GET /workflow/{filename}`.
- Pack detail lets users delete workflow files.
- Backend has a rename endpoint for display name and filename: `src/store/api.py:4841` through `src/store/api.py:4925`.
- Frontend does not expose rename/edit in the reviewed workflow section.
- Uploaded workflows are use-as-is.
- Generated workflows are use-as-is.
- The only editable related surface is pack parameters; changing parameters does not regenerate or patch existing workflow automatically.

## 9. Storage

- Workflow file content is stored as separate `.json` files under `state/packs/<Pack>/workflows/`.
- `pack.json` stores workflow metadata only in `workflows`: `src/store/models.py:794` through `src/store/models.py:800` and `src/store/models.py:874` through `src/store/models.py:875`.
- Generated workflow filename is `default_<safe_pack_name>.json`: `src/store/api.py:4112` through `src/store/api.py:4114`.
- Generated workflow file is written to the workflows directory: `src/store/api.py:4108` through `src/store/api.py:4117`.
- Existing default metadata is replaced before adding the new default: `src/store/api.py:4127` through `src/store/api.py:4129`.
- Uploaded workflow file uses the uploaded filename directly: `src/store/api.py:4944` through `src/store/api.py:4955`.
- The upload endpoint does not sanitize uploaded filename beyond whatever FastAPI supplies. NEEDS VERIFICATION: confirm Starlette `UploadFile.filename` normalization and add explicit safe filename validation.
- The plan wanted `workflows/comfyui/default.json`, `workflows/forge/default.json`, etc.; actual implementation is flat.
- `PackResources.workflows_keep_in_git` exists, but no workflow-specific git behavior was found.

## 10. Gaps

### Spec Gaps

- The spec says Workflow Wizard includes import, but import is only listed in Phase 6 advanced features: `plans/PLAN-Workflow-Wizard.md:315` through `plans/PLAN-Workflow-Wizard.md:319`.
- The release roadmap treats import as core Release 1 behavior; the plan should be updated to make import a first-class phase.
- The spec does not define how imported workflow dependencies should become pack dependencies or pack-to-pack dependencies.
- The spec does not define whether imported workflow packs should be `pack_type=custom`, `pack_type=workflow`, or another type.
- `AssetKind` in v2 has no `WORKFLOW` kind, unlike legacy `AssetType.WORKFLOW`.
- The spec asks for all UIs, but does not define A1111/Forge/SD.Next output schemas deeply enough.
- The spec does not define how to validate ComfyUI workflow compatibility with current ComfyUI versions.
- The spec does not define how custom node install should integrate with Profiles or install packs.

### Implementation Holes

- No wizard component exists.
- No target UI selector exists.
- No preview-source selector exists.
- No configurable generator options exist.
- No template directory exists.
- No generator registry exists.
- Current v2 generator is embedded in API code.
- Legacy generator is separate and likely unused.
- Global workflow import UI is not backed by the API request model.
- Upload does not scan or resolve dependencies.
- Upload does not validate workflow shape.
- Upload does not create custom pack.
- Upload does not create dependency records.
- Upload does not create pack dependency records.
- Upload does not detect custom nodes.
- Generated workflow does not include hires/upscaler graph even when parameters include hires fields.
- Generated workflow ignores `params.scheduler`.
- Generated workflow ignores `params.denoise`.
- Generated workflow ignores VAE recommendations.
- Generated workflow ignores ControlNet/IPAdapter/FreeU/refiner/inpainting/batch fields.
- Generated workflow does not support image-specific preview metadata as parameter source.
- Generated workflow does not name workflow from selected source/look.

### Integration Gaps

- `src/workflows` scanner/resolver exists but is not wired into v2 pack workflow upload/import endpoints.
- MCP workflow resolution exists but is only assistant/tool-facing.
- Current pack resolve flow resolves declared dependencies, not scanned workflow references.
- Profiles solve model symlinks, but workflow import does not make missing models declared dependencies, so Profiles cannot expose them.
- ComfyUI workflow symlink target is hardcoded to `config.comfyui.base_path / "user/default/workflows"`: `src/store/api.py:4590` through `src/store/api.py:4592`.
- No equivalent workflow/config placement exists for Forge, A1111, or SD.Next.
- Pack plugin feature flags are not used to hide the workflow section in `PackDetailPage`.
- The workflow upload modal closes immediately after mutate call, before success/failure is known.

### Test Gaps

- Existing `tests/store/test_pack_workflow.py` covers resolve/install and preview metadata, not workflow generation/import: `tests/store/test_pack_workflow.py:28` through `tests/store/test_pack_workflow.py:143`.
- MCP workflow scan/resolve has integration coverage: `tests/integration/test_mcp_store.py:304` through `tests/integration/test_mcp_store.py:361`.
- Parameter tests cover legacy parameter defaults, not current v2 API generation output: `tests/unit/core/test_parameters.py:239` through `tests/unit/core/test_parameters.py:282`.
- Route existence tests check workflow endpoints exist, not behavior.
- No test found for `POST /api/packs/{pack}/generate-workflow` output graph correctness.
- No test found for upload JSON validation and storage.
- No test found for upload dependency scanning.
- No test found for workflow import from the global Import modal.
- No test found for ComfyUI workflow symlink creation/deletion.
- No test found for path traversal in workflow upload filenames.
- No test found for multi-UI generator behavior.

### UX Holes

- User cannot choose ComfyUI vs Forge vs A1111 vs SD.Next when generating.
- User cannot choose default parameters vs preview image metadata.
- User cannot see scanned missing dependencies when uploading/importing a workflow.
- User cannot convert scanned dependencies into pack dependencies.
- User cannot resolve missing workflow dependencies directly from upload/import.
- User cannot create a custom workflow pack from an imported workflow.
- User cannot edit workflow JSON or graph after import.
- User cannot rename workflow from the visible workflow card despite backend support.
- "Generate Default" may be misleading because it only creates ComfyUI JSON.
- "Upload Workflow" accepts any JSON, not clearly validated as ComfyUI workflow.
- Global Import modal workflow tab likely fails, creating a broken user path.

### Open Questions

- Should imported ComfyUI workflow JSON create a new `custom` pack by default, or ask to add to an existing pack?
- Should workflow dependencies be represented as direct `PackDependency` entries or `PackDependencyRef` to existing packs?
- Should custom nodes be dependencies, install packs, or a separate dependency class in v2?
- Should workflow storage become per-UI folders now, or should the flat folder be kept with `ui` metadata added to `WorkflowInfo`?
- Should generated workflows be regenerated from parameters, or should workflow JSON become editable and diverge from parameters?
- How should preview image metadata be normalized into the same `GenerationParameters` model?
- Should A1111/Forge/SD.Next output be config text, JSON, PNG info block, or UI-specific preset?
- How should ComfyUI workflow validation handle API-format workflows versus UI-format workflows?
- How should workflow import handle workflows requiring multiple model packs?
- How should active Profiles be linked into actual UI installations so workflows find exposed filenames?

## Recommended Existing-First Path

- Do not build a separate workflow system.
- Reuse `src/workflows/scanner.py` and `src/workflows/resolver.py` for import scanning.
- Move or wrap the v2 inline ComfyUI generator from `src/store/api.py` into `src/workflows` using v2 `src.store.models`.
- Add a generator registry/service that the API calls.
- Extend current `WorkflowInfo` rather than inventing a separate workflow database.
- Keep current `state/packs/<Pack>/workflows/` storage unless per-UI folders are needed for Release 1.
- Wire upload/import to scan dependencies before save, then offer:
  - add scanned assets to this custom pack,
  - link to existing packs,
  - resolve missing assets,
  - save workflow as-is.
- Fix global Import modal/API mismatch before adding new UI.

## Status Matrix

| Requirement | Status | Evidence |
|---|---|---|
| Store workflows in pack | Partial | File under `workflows/` plus `pack.json` metadata |
| Generate default workflow | Partial | ComfyUI-only direct button/API |
| Wizard UI | Missing | No wizard component/path found |
| Target UI selection | Missing | No UI selector in workflow section |
| ComfyUI generation | Partial | Inline v2 graph builder |
| Forge generation | Missing | No generator/templates |
| A1111 generation | Missing | No generator/templates |
| SD.Next generation | Missing | No generator/templates |
| Template system | Missing | No template files found |
| Abstract generator interface | Missing | Concrete ComfyUI classes only |
| Preview parameter source | Missing | Preview metadata displayed/stored but not used for generation |
| Import ComfyUI workflow JSON | Partial/Broken | Existing-pack upload works; global import likely fails |
| Identify workflow dependencies | Partial | Scanner/MCP yes; upload/import no |
| Trigger resolve from import | Missing | No scan-to-resolve bridge |
| Create custom pack from workflow | Missing | No v2 import-workflow pack creation |
| Edit workflow after import | Missing | Use as-is; backend rename only |
| Profiles model dirs | Partial | Model symlink views exist; import does not declare deps |

