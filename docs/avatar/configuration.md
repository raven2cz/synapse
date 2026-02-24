# Configuration Reference

Avatar-engine is configured via a YAML file at `~/.synapse/avatar.yaml`. All settings have sensible defaults — configuration is optional.

## Config File Location

The config loader checks these locations in order:

1. Explicit `config_path` parameter (programmatic use)
2. `$SYNAPSE_ROOT/avatar.yaml` (environment variable)
3. `~/.synapse/avatar.yaml` (default)

If no file is found, all defaults apply and the AI assistant works out of the box (assuming a provider CLI is installed).

## Minimal Configuration

```yaml
# ~/.synapse/avatar.yaml
provider: gemini
```

## Full Reference

```yaml
# ═══════════════════════════════════════════════════════════════
# Avatar Engine Configuration
# ═══════════════════════════════════════════════════════════════

# Master switch — set to false to completely disable the AI assistant
enabled: true

# Default AI provider: "gemini" | "claude" | "codex"
# Must have the corresponding CLI tool installed
provider: gemini

# Base system prompt prepended to all conversations
# Default includes Synapse-specific context; override only if needed
system_prompt: "You are a Synapse AI assistant..."

# ─── MCP Server Configuration ────────────────────────────────
# Additional MCP servers the AI can connect to
# The built-in synapse-store MCP server is always available

mcp_servers:
  synapse-store:
    command: "python"
    args: ["-m", "src.avatar.mcp"]
    env:
      SYNAPSE_ROOT: "~/.synapse"

# ─── Provider-Specific Configuration ─────────────────────────
# Each provider is a TOP-LEVEL key (not nested under "providers:")

gemini:
  model: "gemini-3-pro-preview"    # Model override (empty = provider default)
  # enabled: true                   # Enable/disable this specific provider

claude:
  model: "claude-sonnet-4-5"
  # enabled: true

codex:
  model: ""
  # enabled: true

# ─── Engine Settings ──────────────────────────────────────────
# Engine settings are nested under the "engine:" key

engine:
  working_dir: "~/.synapse"
  max_history: 100
  # Safety mode: safe (default) | ask (Gemini only) | unrestricted
  safety_instructions: safe
```

## Settings Detail

### `enabled`

Type: `boolean` | Default: `true`

Master switch for the entire avatar-engine integration. When `false`:
- The FAB button is hidden
- All `/api/avatar/*` endpoints return `state: "disabled"`
- The WebSocket endpoint is not mounted
- No provider CLI processes are started

### `provider`

Type: `string` | Default: `"gemini"` | Values: `"gemini"`, `"claude"`, `"codex"`

The default AI provider used when starting a new session. The provider must have its CLI tool installed and accessible in `$PATH`. Invalid values fall back to `"gemini"` with a warning.

Users can switch providers at runtime via the UI without changing this config.

### `system_prompt`

Type: `string` | Default: Built-in Synapse context prompt

The base system prompt sent to the AI provider. Skills (see [Skills & Avatars](skills-and-avatars.md)) are appended after this prompt automatically.

Override this only if you want to fundamentally change the AI's behavior. For adding domain knowledge, use custom skills instead.

### `gemini` / `claude` / `codex` (provider configs)

Type: `object` | Default: Not set (provider defaults apply)

Per-provider configuration. Each provider is a **top-level key** in the YAML (not nested under a `providers:` key). Supported fields:

- `model` (string): Override the default model. Leave empty to use the provider's default.
- `enabled` (boolean): Enable or disable this specific provider. A disabled provider won't appear in the provider switcher UI.

### `engine`

Type: `object` | Default: See sub-fields

Engine settings are nested under the `engine:` key.

#### `engine.safety_instructions`

Type: `string` | Default: `"safe"` | Values: `"safe"`, `"ask"`, `"unrestricted"`

Controls how the AI handles potentially destructive operations (like `import_civitai_model` which downloads files):

| Mode | Behavior |
|------|----------|
| `safe` | AI refuses destructive operations entirely |
| `ask` | AI shows a PermissionDialog before destructive operations |
| `unrestricted` | AI executes all operations without confirmation |

Invalid values fall back to `"safe"` with a warning.

#### `engine.working_dir`

Type: `string` | Default: `"~/.synapse"`

Working directory for the avatar-engine process. Tilde (`~`) is expanded to the user's home directory.

#### `engine.max_history`

Type: `integer` | Default: `100`

Maximum number of conversation messages kept in the backend's memory. Older messages are pruned to stay within this limit.

### `mcp_servers`

Type: `object` | Default: `{}`

Additional MCP (Model Context Protocol) servers to make available to the AI. The built-in `synapse-store` MCP server (21 tools) is always registered automatically.

Each server entry requires:
- `command` (string): The executable to run
- `args` (list): Command-line arguments
- `env` (object, optional): Environment variables

## Resolved Paths

The config loader automatically resolves these directories relative to the Synapse root:

| Path | Default | Purpose |
|------|---------|---------|
| `config_path` | `~/.synapse/avatar.yaml` | This config file |
| `skills_dir` | `~/.synapse/avatar/skills` | Built-in skill files |
| `custom_skills_dir` | `~/.synapse/avatar/custom-skills` | User custom skills |
| `avatars_dir` | `~/.synapse/avatar/avatars` | Custom avatar definitions |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `SYNAPSE_ROOT` | Override the default `~/.synapse` root directory |
| `CIVITAI_API_TOKEN` | Required for Civitai MCP tools (search, import) |

## See Also

- [Getting Started](getting-started.md) — Installation and first chat
- [Skills & Avatars](skills-and-avatars.md) — Custom skills and avatar creation
- [MCP Tools Reference](mcp-tools-reference.md) — What the AI can do with tools
