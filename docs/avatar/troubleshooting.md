# Troubleshooting

Common issues and solutions for the avatar-engine integration.

## Status Check

Always start by checking the status endpoint:

```bash
curl -s http://localhost:8000/api/avatar/status | python -m json.tool
```

### Status States

| State | Meaning | Fix |
|-------|---------|-----|
| `ready` | Everything works | No action needed |
| `disabled` | Config has `enabled: false` | Set `enabled: true` in `~/.synapse/avatar.yaml` |
| `no_engine` | `avatar-engine` package not installed | `uv add "avatar-engine[web]"` |
| `no_provider` | Engine OK but no CLI providers found | Install `gemini`, `claude`, or `codex` CLI |
| `setup_required` | Neither engine nor providers installed | Install both (see [Getting Started](getting-started.md)) |

### Status Response Fields

```json
{
  "available": true,           // true only when state == "ready"
  "state": "ready",            // see table above
  "enabled": true,             // from config
  "engine_installed": true,    // avatar_engine package importable
  "engine_version": "1.0.0",   // installed version (null if not installed)
  "engine_min_version": "1.0.0", // minimum required version
  "active_provider": "gemini", // current provider (null if no provider)
  "safety": "safe",            // safety mode
  "providers": [               // detected CLI tools
    {"name": "gemini", "display_name": "Gemini CLI", "command": "gemini", "installed": true}
  ]
}
```

## Common Issues

### FAB Button Not Visible

1. **Check status**: `curl http://localhost:8000/api/avatar/status` — must be `"state": "ready"`
2. **Check config**: Ensure `enabled: true` in `~/.synapse/avatar.yaml`
3. **Check frontend**: Verify `@avatar-engine/react` is installed (`ls apps/web/node_modules/@avatar-engine/react`)
4. **Check console**: Open browser DevTools → Console for errors
5. **Check z-index**: The FAB uses `z-[1000]` — ensure no other elements overlap

### WebSocket Connection Failed

**Symptoms:** FAB appears but clicking shows "Disconnected" or spinner.

1. **Check backend is running**: `curl http://localhost:8000/api/avatar/status`
2. **Check Vite proxy**: Ensure `vite.config.ts` has WebSocket proxy:
   ```typescript
   '/api/avatar': {
     target: 'http://localhost:8000',
     ws: true,  // ← Must be true for WebSocket
   }
   ```
3. **Check browser console**: Look for WebSocket connection errors
4. **Check engine mount**: Backend logs should show "Avatar engine mounted at /api/avatar/engine"

### Provider Errors

#### Gemini: "API key not found"

```bash
# Check if gemini CLI works
gemini -p "Hello"

# Set API key if needed
export GEMINI_API_KEY="your-key"
```

#### Claude: "Not authenticated"

```bash
# Authenticate with Claude CLI
claude auth login
```

#### Codex: "No API key"

```bash
# Set OpenAI API key
export OPENAI_API_KEY="your-key"
```

### MCP Tools Not Working

**Symptoms:** AI says "I don't have access to tools" or tool calls fail.

1. **Check MCP availability**:
   ```bash
   python -c "from mcp.server.fastmcp import FastMCP; print('OK')"
   ```
   If this fails: `uv add "mcp>=1.0"`

2. **Check store access**: MCP tools need a valid Synapse store:
   ```bash
   curl http://localhost:8000/api/store/status
   ```

3. **Check Civitai token** (for Civitai tools):
   ```bash
   echo $CIVITAI_API_TOKEN  # Must be set for search/import
   ```

### Version Mismatch

**Symptoms:** Status shows `engine_installed: true` but features don't work.

```bash
# Check installed version
python -c "import avatar_engine; print(avatar_engine.__version__)"

# Check minimum required
curl -s http://localhost:8000/api/avatar/status | python -m json.tool | grep version

# Upgrade if needed
scripts/avatar-upgrade.sh
# or manually:
uv add "avatar-engine[web]>=1.0.0"
cd apps/web && pnpm update @avatar-engine/react @avatar-engine/core
```

### Skills Not Loading

```bash
# Check skills count
curl -s http://localhost:8000/api/avatar/config | python -m json.tool | grep skills_count

# List all skills
curl -s http://localhost:8000/api/avatar/skills | python -m json.tool

# Check skills directories exist
ls ~/.synapse/avatar/skills/
ls ~/.synapse/avatar/custom-skills/
```

Skills over 50 KB are silently skipped. Check backend logs for warnings.

### Custom Avatars Not Appearing

```bash
# List avatars
curl -s http://localhost:8000/api/avatar/avatars | python -m json.tool

# Check directory structure
ls ~/.synapse/avatar/avatars/my-avatar/
# Must contain avatar.json (valid JSON, max 1 MB)

# Symlinks are skipped
file ~/.synapse/avatar/avatars/my-avatar  # Must be a real directory
```

## Debug Commands

```bash
# Full status check
curl -s http://localhost:8000/api/avatar/status | python -m json.tool

# Provider detection
curl -s http://localhost:8000/api/avatar/providers | python -m json.tool

# Config (non-sensitive)
curl -s http://localhost:8000/api/avatar/config | python -m json.tool

# Skills list
curl -s http://localhost:8000/api/avatar/skills | python -m json.tool

# Avatars list
curl -s http://localhost:8000/api/avatar/avatars | python -m json.tool

# Check avatar-engine Python package
python -c "import avatar_engine; print(avatar_engine.__version__)"

# Check frontend packages
ls apps/web/node_modules/@avatar-engine/react/dist/
ls apps/web/node_modules/@avatar-engine/core/dist/

# Run upgrade script
scripts/avatar-upgrade.sh

# Test MCP server standalone
python -m src.avatar.mcp
# Should start and wait for stdio input (Ctrl+C to exit)
```

## Cache Issues

The status endpoint uses a 30-second in-memory cache. After config changes, either:
- Wait 30 seconds, or
- Restart the backend

```bash
# Restart backend
uv run uvicorn src.store.api:app --reload --port 8000
```

## See Also

- [Getting Started](getting-started.md) — Installation walkthrough
- [Configuration](configuration.md) — All configuration options
- [Architecture](architecture.md) — How the system works internally
