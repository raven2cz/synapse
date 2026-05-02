# Audit: Release 1 Point 3 - Install Pack

Date: 2026-05-02
Scope: `PackCategory.INSTALL`, install-pack scripts, lifecycle, console, environment status, Profiles integration, Updates integration.

## Executive Summary

Install Pack is still FUTURE/prototype and is not release-ready.

The repo has only:

- `PackCategory.INSTALL` in `src/store/models.py:78`.
- A generic `Pack.pack_category` field in `src/store/models.py:837`.
- A frontend prototype plugin in `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:1`.
- Existing Profiles/view/attach code for already-configured UI roots.
- Existing model-pack update code for blob/dependency updates.

The repo does not have:

- Backend script execution endpoints.
- `ScriptRunner` or `ProcessManager`.
- Real install/start/stop/verify/update lifecycle.
- Real stdout/stderr streaming.
- Real PID/port/API health checks for UI environments.
- Install-pack templates for ComfyUI/Forge/A1111/SD.Next.
- A security model for arbitrary pack scripts.
- A data contract connecting install-pack-created UI roots to Profiles.
- UI application update semantics distinct from model/blob updates.

Release blocker: script execution means arbitrary local code execution. The plan acknowledges security concerns, but no security controls are implemented.

## Source Inventory

Main plan:

- `plans/PLAN-Install-Packs.md:1` declares "Install Packs - Full Implementation".
- `plans/PLAN-Install-Packs.md:3` to `plans/PLAN-Install-Packs.md:4` mark it draft/planning.
- `plans/PLAN-Install-Packs.md:15` to `plans/PLAN-Install-Packs.md:22` list prototype status and missing execution/streaming/process management.

Backend model:

- `src/store/models.py:78` defines `PackCategory`.
- `src/store/models.py:84` documents `INSTALL` as script-based UI-environment management.
- `src/store/models.py:88` defines `INSTALL = "install"`.
- `src/store/models.py:837` defines `Pack`.
- `src/store/models.py:842` defines `pack_category: PackCategory = PackCategory.EXTERNAL`.

Frontend prototype:

- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:2` labels the plugin `PROTOTYPE`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:6` says current status is prototype.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:9` to `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:13` list planned scripts, console, status, and install/start/stop buttons.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:16` says install packs are identified by `install-pack` user tag.

Requested component:

- `apps/web/src/components/modules/pack-detail/sections/PackScriptsSection.tsx` does not exist.
- Script cards are embedded in the prototype plugin instead.

## 1. What Exists - Backend

### Pack Category

Backend support is schema-only:

- `src/store/models.py:78` starts `PackCategory`.
- `src/store/models.py:84` documents install packs.
- `src/store/models.py:88` defines the `install` value.
- `src/store/models.py:842` stores category on `Pack`.

Missing from the model:

- No install-pack-specific model, script manifest, install root, managed UI kind, or lifecycle state fields.

### Pack Creation and Import

Generic pack creation creates only custom packs:

- `src/store/api.py:3262` defines `CreatePackRequest`.
- `src/store/api.py:3275` exposes `POST /api/packs/create`.
- `src/store/api.py:3310` constructs a `Pack`.
- `src/store/api.py:3313` hard-codes `pack_category=PackCategory.CUSTOM`.
- `src/store/api.py:3333` creates preview/workflow resource dirs, not script dirs.

Civitai import creates external packs:

- `src/store/pack_service.py:510` constructs imported pack data.
- `src/store/pack_service.py:513` sets `pack_category=PackCategory.EXTERNAL`.

Missing:

- No API creates `PackCategory.INSTALL`, creates scripts/config/log dirs, or enforces scripts/target UI.
- A user can still tag any normal pack as `install-pack` on the frontend.

### Script Endpoints

The plan defines endpoints, but they are not implemented:

- `plans/PLAN-Install-Packs.md:56` planned run endpoint.
- `plans/PLAN-Install-Packs.md:60` planned status endpoint.
- `plans/PLAN-Install-Packs.md:64` planned stop endpoint.
- `plans/PLAN-Install-Packs.md:68` planned logs endpoint.
- `plans/PLAN-Install-Packs.md:72` planned WebSocket stream.
- `plans/PLAN-Install-Packs.md:81` planned `script_runner.py`.
- `plans/PLAN-Install-Packs.md:87` planned `process_manager.py`.

Search result:

- No script-run endpoints in `src/store/api.py`.
- No `src/store/script_runner.py`.
- No `src/store/process_manager.py`.
- No install-pack subprocess wrapper, process registry, or log WebSocket found.

NEEDS VERIFICATION:

- Confirm no hidden app/router outside `src`, `apps/api`, and `apps/web` mounts install-pack script endpoints.

## 1. What Exists - Frontend

### Plugin Selection

InstallPlugin exists and is registered:

- `apps/web/src/components/modules/pack-detail/plugins/usePackPlugin.ts:21` imports plugins.
- `apps/web/src/components/modules/pack-detail/plugins/usePackPlugin.ts:24` imports `InstallPlugin`.
- `apps/web/src/components/modules/pack-detail/plugins/usePackPlugin.ts:34` registers `InstallPlugin`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:254` defines the plugin.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:257` sets priority 100.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:259` defines `appliesTo`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:261` matches only `pack.user_tags?.includes('install-pack')`.

Gap:

- Matching ignores `pack.pack?.pack_category === 'install'`.
- A real backend `PackCategory.INSTALL` pack without the tag will not match.
- A normal Civitai/custom pack with the tag will match.

### Mock Scripts

Script UI is mock-only:

- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:65` defines `ScriptsSection`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:70` says scripts are mock.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:72` hard-codes `install.sh`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:73` hard-codes `start.sh`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:74` hard-codes `stop.sh`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:75` hard-codes `update.sh`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:78` defines `handleRunScript`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:82` comments "Simulate script execution".
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:83` sleeps 2 seconds.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:86` always shows success.

Gap:

- No HTTP request, WebSocket, script discovery, `verify.sh`, exit code, failure, or log handling.

### Mock Environment Status

Environment status is mock-only:

- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:163` defines `EnvironmentStatus`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:165` says it is mock.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:167` hard-codes `installed: true`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:168` hard-codes `running: false`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:169` hard-codes version `1.0.0`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:203` renders install/start/stop buttons with no handlers.

Prototype UX:

- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:230` defines `PrototypeNotice`.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:240` renders prototype title.
- `apps/web/src/i18n/locales/en.json:581` says "Install Pack (Prototype)".
- `apps/web/src/i18n/locales/en.json:582` says full functionality is future work.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:290` console action only shows "coming soon".
- `apps/web/src/i18n/locales/en.json:585` says "Console feature coming soon".

## 2. Security Model

Current state:

- No real script execution exists today, so Synapse currently does not execute install-pack scripts.
- If the planned endpoints are implemented without controls, install packs become arbitrary local code execution.

Plan-level security is only a placeholder:

- `plans/PLAN-Install-Packs.md:230` starts Security Considerations.
- `plans/PLAN-Install-Packs.md:232` lists script validation.
- `plans/PLAN-Install-Packs.md:233` lists sandboxing.
- `plans/PLAN-Install-Packs.md:234` lists permissions.
- `plans/PLAN-Install-Packs.md:235` lists logging.
- `plans/PLAN-Install-Packs.md:236` lists user confirmation.

No implemented security controls found:

- No sandbox/container runner.
- No script allowlist beyond mock frontend names.
- No trusted source/signature/hash approval.
- No "view script before run".
- No destructive operation confirmation.
- No capability model.
- No low-privilege subprocess user.
- No path confinement.
- No environment/log secret redaction.
- No script execution audit log.

Release blocker:

- Backend script execution must not ship until the security model is implemented.
- Minimum controls: strict script-name validation, manifest, cwd confinement, explicit confirmation, script path/hash display, source/trust state, audit log, controlled env, stdout/stderr capture, and warning copy that scripts can modify local files.
- Preferred controls: sandbox/container or dedicated low-privilege process user with constrained filesystem and network policy.

NEEDS VERIFICATION:

- Whether Release 1 allows user-provided install packs at all.
- Whether official templates are signed/curated.
- Whether non-official scripts are disabled by default.
- Windows/macOS/Linux sandbox expectations.

## 3. Lifecycle

Plan:

- `plans/PLAN-Install-Packs.md:119` plans `install.sh`.
- `plans/PLAN-Install-Packs.md:120` plans `start.sh`.
- `plans/PLAN-Install-Packs.md:121` plans `stop.sh`.
- `plans/PLAN-Install-Packs.md:122` plans `update.sh`.
- `plans/PLAN-Install-Packs.md:123` plans `verify.sh`.

Current implementation:

- Frontend mock includes install/start/stop/update only.
- Frontend omits verify.
- Backend lifecycle is absent.
- No task IDs.
- No running/completed/failed state.
- No stop/kill semantics.
- No restart semantics.
- No timeout/concurrency policy.
- No long-running process survival after Synapse restart.

Spec gaps:

- No contract for scripts to report install dir, port, version, PID, readiness, or failure category.
- No contract for whether `start.sh` stays attached or daemonizes.
- No contract for whether `stop.sh` kills by PID, port, pidfile, or API.
- No per-UI lifecycle differences for ComfyUI, Forge, A1111, SD.Next.

NEEDS VERIFICATION:

- Whether `start.sh` is managed by Synapse as a long-running process.
- Whether Synapse must reconnect to UI processes after restart.
- Whether scripts may install Python/Git repos/virtualenvs/custom nodes/system packages.

## 4. Console Viewer

Plan:

- `plans/PLAN-Install-Packs.md:68` plans log fetch.
- `plans/PLAN-Install-Packs.md:72` plans WebSocket streaming.
- `plans/PLAN-Install-Packs.md:177` sketches `ScriptConsoleModal`.
- `plans/PLAN-Install-Packs.md:207` includes WebSocket streaming in Phase 1.
- `plans/PLAN-Install-Packs.md:213` includes `ScriptConsoleModal`.

Current state:

- `ScriptConsoleModal.tsx` does not exist.
- `PackScriptsSection.tsx` does not exist.
- `InstallPlugin.tsx:290` only shows "coming soon".
- No stdout/stderr capture.
- No log storage/retrieval.
- No frontend WebSocket/SSE stream for script logs.

NEEDS VERIFICATION:

- Log storage location.
- Log retention/truncation rules.
- Secret redaction rules.
- Whether both stdout and stderr must stream in order.

## 5. Environment Status

ComfyUI status endpoint is not a real health check:

- `apps/api/src/routers/comfyui.py:88` exposes `/api/comfyui/status`.
- `apps/api/src/routers/comfyui.py:90` says it checks connection status.
- `apps/api/src/routers/comfyui.py:93` says TODO "Actually check ComfyUI API".
- `apps/api/src/routers/comfyui.py:96` hard-codes `connected=True`.
- `apps/api/src/routers/comfyui.py:97` returns configured/default URL.

InstallPlugin status is mock:

- `InstallPlugin.tsx:165` says status should be fetched from backend later.
- `InstallPlugin.tsx:167` hard-codes installed.
- `InstallPlugin.tsx:168` hard-codes not running.

Missing:

- PID tracking, port checks, API pings, process tree tracking, version detection, readiness probes, and Forge/A1111/SD.Next status APIs.

NEEDS VERIFICATION:

- ComfyUI health probe: HTTP API ping or queue/system stats, probably port 8188.
- A1111/Forge/SD.Next health probe: API ping if enabled, fallback port check.
- Behavior when the UI is started outside Synapse.
- Meaning of "installed": directory exists, marker file, verify script, or API response.

## 6. Integration With Profiles

Existing Profiles are model/view oriented:

- `src/store/profile_service.py:181` implements `use`.
- `src/store/profile_service.py:191` ensures pack exists.
- `src/store/profile_service.py:192` creates/updates work profile.
- `src/store/profile_service.py:193` builds views.
- `src/store/profile_service.py:194` activates profile.
- `src/store/profile_service.py:248` updates runtime stack.
- `src/store/profile_service.py:493` installs missing blobs.
- `src/store/profile_service.py:530` downloads missing blob URLs.

Existing UI attachment assumes configured roots:

- `src/store/ui_attach.py:4` attaches active views to UI installations.
- `src/store/ui_attach.py:7` documents symlinks for A1111/Forge/SD.Next.
- `src/store/ui_attach.py:11` documents ComfyUI `extra_model_paths`.
- `src/store/ui_attach.py:56` takes `ui_roots`.
- `src/store/ui_attach.py:308` reads configured UI root.
- `src/store/ui_attach.py:315` fails if UI root does not exist.
- `src/store/ui_attach.py:351` creates `<ui_root>/<kind_path>/synapse`.
- `src/store/ui_attach.py:366` creates symlink.
- `src/store/__init__.py:1062` reads UI roots from config.
- `src/store/__init__.py:1072` falls back to home-directory UI roots.
- `src/store/__init__.py:1089` exposes attach.
- `src/store/__init__.py:1158` exposes refresh attached UIs.
- `src/store/__init__.py:1196` exposes attach status.

Profiles API/UI:

- `src/store/api.py:5011` exposes profile status.
- `src/store/api.py:5065` exposes profile use.
- `src/store/api.py:5098` exposes profile sync.
- `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:218` posts to `/api/profiles/use`.
- `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:223` hard-codes `ui_set: 'local'`.

Gap:

- Install packs do not create or persist UI roots.
- Install packs do not update `store.ui_roots`.
- Profiles do not depend on install packs.
- Attach code cannot use an install-pack-created path because no such handoff exists.

NEEDS VERIFICATION:

- Where install-pack-created roots are stored.
- Whether installing ComfyUI updates `config.store.ui_roots.comfyui`.
- Whether Profiles block activation if required UI install is missing/stopped.
- Whether multiple installs per UI kind are supported.

## 7. Integration With Updates

Existing update system updates model dependencies/blobs:

- `src/store/update_service.py:4` says provider-specific version checking and metadata sync.
- `src/store/update_service.py:45` defines automatic update strategies.
- `src/store/update_service.py:47` only includes `SelectorStrategy.CIVITAI_MODEL_LATEST`.
- `src/store/update_service.py:107` checks if a pack has updatable dependencies.
- `src/store/update_service.py:121` plans pack update.
- `src/store/update_service.py:150` iterates dependencies.
- `src/store/update_service.py:152` skips non-follow-latest dependencies.
- `src/store/update_service.py:445` applies high-level update.
- `src/store/update_service.py:491` applies lock update.
- `src/store/update_service.py:602` downloads new blobs and rebuilds views.

Updates API/UI:

- `src/store/api.py:5170` defines `updates_router`.
- `src/store/api.py:5195` exposes check pack updates.
- `src/store/api.py:5253` exposes apply update.
- `apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx:73` calls `/api/updates/check/{pack.name}`.
- `apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx:87` posts `/api/updates/apply`.
- `apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx:342` says updates only change model blobs.
- `apps/web/src/components/modules/pack-detail/plugins/CivitaiPlugin.tsx:348` enables update checking.
- `apps/web/src/components/modules/pack-detail/plugins/InstallPlugin.tsx:277` disables update checking.

Gap:

- Install pack `update.sh` is not wired to update system.
- No UI app version model.
- No rollback/downgrade model.
- No conflict model between UI app updates and model updates.
- No UI update status in Packs or Profiles.

NEEDS VERIFICATION:

- Whether UI updates use script lifecycle or update provider framework.
- Whether UI app updates appear in `/api/updates`.
- How UI update rollback/downgrade should work.

## 8. Templates

Plan:

- `plans/PLAN-Install-Packs.md:223` starts Phase 4 templates.
- `plans/PLAN-Install-Packs.md:224` plans ComfyUI template.
- `plans/PLAN-Install-Packs.md:225` plans Forge template.
- `plans/PLAN-Install-Packs.md:226` plans custom install-pack docs.

Current repo:

- No ComfyUI install-pack template found.
- No Forge install-pack template found.
- No A1111 install-pack template found.
- No SD.Next install-pack template found.
- Root `scripts/install.sh` is project setup, not an install-pack template.
- `config/avatar/skills/install-packs.md:1` is documentation, not a template.
- `config/avatar/skills/install-packs.md:44` describes model/profile install flow, not UI environment installation.

Missing:

- No sample `pack.json`, script manifest, `.env`/config example, or user-provided install-pack validation rules.

NEEDS VERIFICATION:

- Whether Release 1 includes official templates only.
- Whether templates live in repo, registry, or generated UI.

## 9. Tests

Existing tests cover only plugin selection/metadata:

- `apps/web/src/__tests__/pack-plugins.test.ts:311` tests InstallPlugin matching.
- `apps/web/src/__tests__/pack-plugins.test.ts:312` expects tag match.
- `apps/web/src/__tests__/pack-plugins.test.ts:317` expects no match without tag.
- `apps/web/src/__tests__/pack-plugins.test.ts:348` expects install plugin selected.
- `apps/web/src/__tests__/pack-plugins.test.ts:380` expects priority over CivitaiPlugin.
- `apps/web/src/__tests__/pack-plugins.test.ts:460` tests feature flags.
- `apps/web/src/__tests__/pack-plugins.test.ts:469` expects `canRunScripts: true`.
- `apps/web/src/__tests__/pack-plugins.test.ts:611` tests description length validation.
- `apps/web/src/__tests__/pack-plugins.test.ts:942` tests badge shape.

Missing tests:

- Backend script endpoint, path traversal, allowlist/manifest, confirmation/security, process, streaming, health probe, profile handoff, UI app update, template validation, and frontend lifecycle failure tests.

NEEDS VERIFICATION:

- Current tests may pass while install-pack behavior remains fully mocked.

## UX Holes and Open Questions

- Prototype banner admits feature is future, but mock script buttons still look actionable.
- Install/start/stop buttons have no handlers; console only says coming soon.
- No script output, arbitrary-code warning, script preview/hash/source display, install directory display, port conflict UI, Profiles handoff, UI update UX, or verify action.
- Open identity question: `pack_category=install`, `user_tags=['install-pack']`, or both?
- Open trust question: who authors trusted install packs, and are user-provided scripts allowed?
- Open runtime question: can scripts access network/files outside install dir, how are secrets redacted, how are Windows scripts handled, and how does Synapse recover after restart?
- Open integration question: can one UI kind have multiple roots, can Profiles target a specific install instance, and does UI update belong to `/api/updates` or script lifecycle?

## Release 1 Recommendation

Do not ship install-pack script execution in Release 1 unless security and lifecycle are implemented.

Acceptable Release 1 scope:

- Keep Install Pack disabled/prototype.
- Hide mock script buttons or label them nonfunctional.
- Allow metadata/template preview only.
- Ship Profiles/Attach support for already-installed UIs independently.

Minimum before enabling execution:

- Backend script manifest and safe path resolution.
- Explicit confirmation with script path, hash, source, and risk warning.
- Script execution service with cwd confinement, env control, stdout/stderr capture, exit codes, task IDs, and audit logs.
- Process manager with PID, port, health checks, stop, timeout, restart policy.
- WebSocket/SSE log streaming and persisted log retrieval.
- Install result contract that writes UI root into config/profile target data.
- Per-UI health checks and templates.
- Separate semantics for model/blob updates vs UI application updates.

## Final Status

Status: FUTURE/prototype confirmed.

Release readiness: not ready.

Primary blocker: no security model for arbitrary script execution.

Secondary blockers: no backend execution, lifecycle, console streaming, environment health, Profiles handoff, UI update semantics, or templates.
