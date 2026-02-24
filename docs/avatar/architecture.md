# Architecture

This document describes the internal architecture of the avatar-engine integration in Synapse. It's intended for developers working on the codebase.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser                                  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ AvatarProvider (single useAvatarChat WebSocket)          │   │
│  │  ├── PermissionDialog (sibling)                          │   │
│  │  ├── AvatarWidget (FAB / Compact / Fullscreen)           │   │
│  │  │    ├── AvatarBust + CompactHeader + CompactInput      │   │
│  │  │    └── StatusBar + ChatPanel + CostTracker (fullscreen)│  │
│  │  └── SuggestionChips (per-page context-aware)            │   │
│  └──────────────────────────────────────────────────────────┘   │
│           │ WebSocket (ws://host/api/avatar/ws)                  │
│           │ REST (GET /api/avatar/status|config|skills|avatars)  │
└───────────┼─────────────────────────────────────────────────────┘
            │
┌───────────┼─────────────────────────────────────────────────────┐
│           ▼ FastAPI Backend                                      │
│                                                                  │
│  ┌─────────────────┐   ┌─────────────────────────────────────┐  │
│  │ avatar_router    │   │ avatar-engine (mounted app)          │  │
│  │ /api/avatar/*    │   │ /api/avatar/engine/*                 │  │
│  │  GET /status     │   │  WebSocket /ws                       │  │
│  │  GET /providers  │   │  REST endpoints                      │  │
│  │  GET /config     │   │  ├── AI CLI subprocess (gemini/      │  │
│  │  GET /skills     │   │  │   claude/codex)                   │  │
│  │  GET /avatars    │   │  └── MCP synapse-store server        │  │
│  └─────────────────┘   │      (21 tools → Store)               │  │
│                         └─────────────────────────────────────┘  │
│                                        │                         │
│                         ┌──────────────┼──────────────────────┐  │
│                         │   Synapse Store                      │  │
│                         │   PackService, InventoryService,     │  │
│                         │   BackupService, CivitaiClient       │  │
│                         └─────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Backend Architecture

### File Map

| File | Lines | Purpose |
|------|-------|---------|
| `src/avatar/__init__.py` | ~30 | Feature flag, version check, `AVATAR_ENGINE_AVAILABLE` |
| `src/avatar/config.py` | ~150 | `AvatarConfig` dataclass, YAML loading, path resolution |
| `src/avatar/routes.py` | ~200 | FastAPI router (5 endpoints), avatar-engine mount |
| `src/avatar/skills.py` | ~100 | Skill loading, system prompt building |
| `src/avatar/ai_service.py` | ~200 | `AvatarAIService` — drop-in AI parameter extraction |
| `src/avatar/mcp/__init__.py` | ~20 | MCP package init, conditional import |
| `src/avatar/mcp/__main__.py` | ~15 | Standalone MCP server entry point |
| `src/avatar/mcp/store_server.py` | ~700 | 21 MCP tool implementations + FastMCP registration |

### `__init__.py` — Feature Detection

```python
AVATAR_ENGINE_AVAILABLE: bool   # True if avatar_engine package is importable
AVATAR_ENGINE_VERSION: str|None # e.g. "1.0.0"
AVATAR_ENGINE_MIN_VERSION = "1.0.0"

def check_avatar_engine_compat() -> bool
```

All avatar features gracefully degrade when `AVATAR_ENGINE_AVAILABLE` is `False`. No import errors, no crashes — just `state: "no_engine"` in the status endpoint.

### `config.py` — Configuration

Key design decisions:
- Config is loaded lazily with a 30-second TTL cache (see `routes.py`)
- Invalid `provider` falls back to `"gemini"` with a warning
- Invalid `safety` falls back to `"safe"` with a warning
- Path resolution uses `~/.synapse` as default root, overridable via `$SYNAPSE_ROOT`
- Provider detection uses `shutil.which()` — no subprocess spawning

### `routes.py` — REST API + Engine Mount

**Status state machine:**

```
                   ┌── config.enabled == False ──→ "disabled"
                   │
engine installed? ──┤
                   │ Yes                    No
                   ▼                        ▼
            providers found?          providers found?
            │              │          │              │
            Yes            No         Yes            No
            ▼              ▼          ▼              ▼
         "ready"    "no_provider"  "no_engine"  "setup_required"
```

**`try_mount_avatar_engine(app)`:**
1. Check `AVATAR_ENGINE_AVAILABLE`
2. Run `check_avatar_engine_compat()` (warns if version too old)
3. Load config, skip if `enabled == False`
4. Build system prompt (base + skills via `build_system_prompt()`)
5. Call `avatar_engine.web.create_api_app(provider, config_path, system_prompt)`
6. Mount at `/api/avatar/engine`

### `skills.py` — System Prompt Builder

- Skills are `.md` files loaded from two directories (built-in + custom)
- YAML frontmatter is automatically stripped
- Custom skills with same filename override built-ins
- Max 50 KB per skill file
- All skills sorted alphabetically

### `ai_service.py` — AI Parameter Extraction

`AvatarAIService` is a drop-in replacement for the legacy `AIService`. Same public API (`extract_parameters(description)`) but uses avatar-engine instead of direct provider calls.

Key patterns:
- Lazy thread-safe singleton engine (double-checked locking)
- Three-strategy JSON extraction (direct parse, code fence, brace scanner)
- Cache layer (`AICache`) with configurable TTL
- Fallback to rule-based extraction on failure

### `mcp/store_server.py` — MCP Tools

The `_impl()` pattern: every MCP tool has a corresponding `_*_impl()` function that:
- Accepts an optional `store` parameter (for testing — inject a mock)
- Contains all business logic
- Is testable without the `mcp` package installed

The `@mcp.tool()` decorated functions are thin wrappers that call `_*_impl()`.

Store access uses a lazy singleton with double-checked locking (`_get_store()`).

## Frontend Architecture

### File Map

| File | Purpose |
|------|---------|
| `apps/web/src/components/avatar/AvatarProvider.tsx` | React context, single `useAvatarChat` instance |
| `apps/web/src/components/avatar/SuggestionChips.tsx` | Per-page suggestion buttons |
| `apps/web/src/lib/avatar/api.ts` | Type-safe API client, TanStack Query keys |
| `apps/web/src/lib/avatar/context.ts` | Page context builder, message prefix formatter |
| `apps/web/src/lib/avatar/suggestions.ts` | Per-page suggestion resolution with i18n keys |
| `apps/web/src/styles/avatar-overrides.css` | CSS bridge (Synapse colors → `--ae-*` variables) |

### AvatarProvider — The Core

Called once at the app root. Creates a single persistent WebSocket via `useAvatarChat()`.

Key responsibilities:
- Derives WebSocket URL from `location.protocol` and `location.host`
- On mount: fetches `/api/avatar/status` to check engine version compatibility
- Provides `sendWithContext()` — wraps `chat.sendMessage` with automatic page context prefix
- Exposes `compactRef` for external compact mode triggers

### Page Context System

**`context.ts`** builds structured context payloads:
```
PageId → AvatarPageContextPayload → "[Context: description, entity: name]"
```

Supported pages: `packs`, `pack-detail`, `inventory`, `profiles`, `downloads`, `browse`, `settings`, `avatar`.

**`suggestions.ts`** maps pages to i18n keys (3 suggestions per page). When on `/avatar`, it uses the **previous** page's context to show relevant suggestions.

### SuggestionChips

Reads current/previous page from `usePageContextStore`, resolves suggestion i18n keys, renders clickable chips. Clicking sends the translated text as a chat message.

## Key Design Decisions

1. **Single WebSocket**: `useAvatarChat()` is called once at app root. Mode switching (FAB → Compact → Fullscreen) never disconnects.

2. **Graceful degradation**: Every layer checks availability. Missing engine → status shows `no_engine`. Missing providers → `no_provider`. Config disabled → `disabled`. The app always works — just without AI features.

3. **`_impl()` pattern**: MCP tool logic is separated from MCP registration. The `_impl()` functions are pure Python, testable without `mcp` package. The `@mcp.tool()` wrappers are thin and untested.

4. **Skills override mechanism**: Custom skills with the same filename as built-ins completely replace them. No merge — full override. This keeps behavior predictable.

5. **Context-aware messaging**: `sendWithContext()` prepends page context so the AI knows what page the user is on. Uses **previous** context when on the avatar chat page itself.

6. **Synapse avatar bust**: Custom WebP images (idle, thinking, speaking) at `public/avatars/synapse/`. The `SYNAPSE_AVATAR` config is hardcoded in `AvatarProvider.tsx` and prepended to the library's built-in avatar list.

## Testing Strategy

Total: **511 tests** across 8 iterations.

| Layer | Tests | What's Tested |
|-------|-------|---------------|
| Backend config/routes | 31 | Config loading, validation, path resolution, status states |
| Frontend integration | 59 | AvatarProvider, Layout, CSS, i18n, WebSocket proxy |
| MCP Store tools | 84 | All 10 store `_impl()` functions with mock store |
| Skills system | 45 | Loading, frontmatter stripping, override, prompt building |
| Avatars/Settings UI | 72 | Endpoint responses, avatar listing, Settings components |
| Page context | 88 | Context building, suggestions, chips, sendWithContext |
| Advanced MCP tools | 57 | Civitai, Workflow, Dependency `_impl()` functions |
| AI service migration | 46 | AvatarAIService, JSON extraction, cache, fallback |
| Upgrade management | 29 | Version checks, compat, upgrade script |

Test pyramid: Unit tests (majority) → Integration tests → Smoke tests.

## See Also

- [Configuration](configuration.md) — `avatar.yaml` reference
- [MCP Tools Reference](mcp-tools-reference.md) — All 21 tools
- [Theming](theming.md) — CSS custom properties
