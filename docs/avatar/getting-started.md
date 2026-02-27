# Getting Started

This guide walks you through setting up the AI assistant in Synapse and having your first conversation.

## Prerequisites

1. **Python 3.11+** with [uv](https://github.com/astral-sh/uv) package manager
2. **Synapse** cloned and working (`./scripts/start-all.sh` runs successfully)
3. **At least one AI CLI provider** installed:

| Provider | Install | Verify |
|----------|---------|--------|
| Gemini | `pip install google-generativeai` | `which gemini` |
| Claude | [claude.ai/download](https://claude.ai/download) | `which claude` |
| Codex | `npm install -g @openai/codex` | `which codex` |

## Installation

### 1. Install avatar-engine Python package

```bash
cd ~/git/github/synapse
uv add "avatar-engine[web]"
```

Or for local development with a linked copy:

```bash
uv pip install -e "~/git/github/avatar-engine[web]"
```

### 2. Install frontend packages

```bash
cd apps/web
pnpm add @avatar-engine/react @avatar-engine/core
# Or link local development copies:
pnpm link ~/git/github/avatar-engine/packages/react
pnpm link ~/git/github/avatar-engine/packages/core
```

### 3. Install peer dependencies

```bash
cd apps/web
pnpm add react-markdown react-syntax-highlighter remark-gfm
pnpm add -D @types/react-syntax-highlighter
```

### 4. Copy avatar images

```bash
cp -r ~/git/github/avatar-engine/examples/web-demo/public/avatars apps/web/public/
```

### 5. Create configuration (optional)

```bash
mkdir -p ~/.synapse/store/state
cp config/avatar.yaml.example ~/.synapse/store/state/avatar.yaml
# Edit ~/.synapse/store/state/avatar.yaml to set your preferred provider
```

### 6. Start Synapse

```bash
./scripts/start-all.sh
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

### 7. Verify

```bash
curl -s http://localhost:8000/api/avatar/status | python -m json.tool
```

You should see:
```json
{
  "available": true,
  "state": "ready",
  "engine_installed": true,
  "engine_version": "1.0.0",
  "active_provider": "gemini"
}
```

## First Chat

Once Synapse is running with avatar-engine installed:

1. **Look for the FAB** — A floating action button appears in the bottom-right corner of every page
2. **Click the FAB** — Opens the compact chat drawer (slide-up panel)
3. **Type a message** — Try: "What packs do I have?"
4. **Expand to fullscreen** — Click the expand icon or press `Ctrl+Shift+F`

### Suggestion Chips

Each page shows context-aware suggestion chips above the chat input:

- **Packs page**: "Overview of my packs", "Any unresolved dependencies?", "Recommend a model"
- **Pack Detail**: "Explain this model", "Show dependencies", "Create a workflow"
- **Inventory**: "Disk usage summary", "Find orphan blobs", "Suggest cleanup"
- **Browse**: "Recommend a model", "Compare these models", "What's trending?"

Click any chip to send it as a message automatically.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+A` | Toggle FAB ↔ Compact mode |
| `Ctrl+Shift+F` | Toggle Compact ↔ Fullscreen mode |
| `Ctrl+Shift+H` | Toggle avatar bust visibility (compact mode) |
| `Escape` | Close current mode (Fullscreen → Compact → FAB) |

## Switching Providers

You can switch between AI providers at any time:

- **Compact mode**: Use the provider dropdown in the header
- **Fullscreen mode**: Use the provider selector in the status bar
- **Configuration**: Set default in `~/.synapse/store/state/avatar.yaml`

```yaml
# ~/.synapse/store/state/avatar.yaml
provider: gemini   # Default provider: gemini, claude, or codex
```

Provider switching preserves your conversation — the WebSocket stays connected and only the backend AI process changes.

## Next Steps

- [Configuration Reference](configuration.md) — Full `avatar.yaml` options
- [MCP Tools Reference](mcp-tools-reference.md) — What the AI can do
- [Skills & Avatars](skills-and-avatars.md) — Customize the AI's knowledge and appearance
