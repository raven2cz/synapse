# PLAN: Install Packs - Full Implementation

**Version:** v0.1.0 (Draft)
**Status:** PLANNING
**Created:** 2026-02-03
**Author:** raven2cz + Claude Opus 4.5
**Branch:** TBD

---

## Executive Summary

Install Packs umožní uživatelům spravovat instalace různých UI prostředí (ComfyUI, Forge, SDnext, Fooocus, atd.) přímo ze Synapse.

**Aktuální stav:**
- ✅ `InstallPlugin.tsx` existuje jako PROTOTYPE (~326 řádků)
- ✅ PrototypeNotice banner
- ✅ ScriptsSection s mock skripty
- ✅ EnvironmentStatus komponenta
- ❌ Reálná exekuce skriptů
- ❌ Console output streaming
- ❌ Process management

---

## Motivation

### Proč Install Packs?

1. **Jednotné prostředí** - Synapse jako hub pro správu všech AI nástrojů
2. **Zjednodušená instalace** - One-click setup pro ComfyUI, Forge, atd.
3. **Správa verzí** - Upgrade/downgrade s jedním kliknutím
4. **Monitoring** - Real-time status běžících služeb
5. **Integrace** - Workflow generation přímo do běžícího UI

### Podporovaná UI prostředí (plánováno)

| UI | Priority | Notes |
|----|----------|-------|
| ComfyUI | High | Nejpopulárnější node-based |
| Forge | High | Fork A1111 s optimalizacemi |
| A1111 | Medium | Classic WebUI |
| SDnext | Medium | Fork A1111 |
| Fooocus | Low | Simplified UI |
| InvokeAI | Low | Jiná architektura |

---

## Architecture

### Backend API Endpoints

```python
# Nové API endpointy v src/store/api.py

POST /api/packs/{name}/scripts/{script}/run
# Spustí skript (install.sh, start.sh, stop.sh, update.sh)
# Returns: { task_id: str, status: "started" }

GET /api/packs/{name}/scripts/{script}/status
# Status běžícího procesu
# Returns: { status: "running" | "completed" | "failed", exit_code?: int }

POST /api/packs/{name}/scripts/{script}/stop
# Zastaví běžící proces
# Returns: { status: "stopped" }

GET /api/packs/{name}/scripts/{script}/logs
# Stream nebo fetch logs
# Returns: { logs: str[], complete: bool }

WebSocket /api/packs/{name}/scripts/{script}/stream
# Real-time log streaming
```

### Backend Services

```
src/
├── store/
│   ├── script_runner.py        # NEW: Script execution service
│   │   ├── ScriptRunner class
│   │   ├── Process management
│   │   ├── Log capture
│   │   └── Status tracking
│   │
│   ├── process_manager.py      # NEW: Multi-process management
│   │   ├── Process registry
│   │   ├── Start/stop control
│   │   └── Health checks
│   │
│   └── api.py                  # Extend with script endpoints
```

### Frontend Components

```
apps/web/src/components/modules/pack-detail/
├── plugins/
│   └── InstallPlugin.tsx       # EXTEND: Full implementation
│
├── sections/
│   └── PackScriptsSection.tsx  # NEW: Script management UI
│
└── modals/
    └── ScriptConsoleModal.tsx  # NEW: Console output viewer
```

---

## Script Structure

### Pack Directory Layout

```
pack/
├── pack.json
├── scripts/                    # NEW: Scripts directory
│   ├── install.sh             # Installation script
│   ├── start.sh               # Start server
│   ├── stop.sh                # Stop server
│   ├── update.sh              # Update to latest
│   └── verify.sh              # Verify installation
├── config/                     # NEW: Configuration
│   ├── .env                   # Environment variables
│   └── settings.json          # UI-specific settings
└── logs/                       # NEW: Log files
    └── *.log
```

### Script Requirements

Každý skript musí:
1. Být executable (`chmod +x`)
2. Exitovat s 0 při úspěchu
3. Logovat do stdout/stderr
4. Podporovat `--help` flag
5. Akceptovat environment variables z `.env`

---

## UI Design

### ScriptsSection

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔧 Scripts                                                  [≡] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 📦 install.sh                                    [▶ Run] │  │
│  │ Install ComfyUI and dependencies                         │  │
│  │ Last run: 2026-02-01 14:30 ✅ Success                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🚀 start.sh                          [■ Stop] [📋 Logs] │  │
│  │ Start ComfyUI server                                     │  │
│  │ Status: 🟢 Running on port 8188                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ⏹ stop.sh                                        [▶ Run] │  │
│  │ Stop ComfyUI server                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🔄 update.sh                                     [▶ Run] │  │
│  │ Update to latest version                                 │  │
│  │ Last run: Never                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### ScriptConsoleModal

```
┌─────────────────────────────────────────────────────────────────┐
│ 📋 Console: start.sh                              [Clear] [×]  │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ [14:30:01] Starting ComfyUI...                              ││
│ │ [14:30:02] Loading model: v1-5-pruned-emaonly.safetensors  ││
│ │ [14:30:05] Model loaded successfully                        ││
│ │ [14:30:05] Starting server on 0.0.0.0:8188                 ││
│ │ [14:30:06] ✅ Server ready at http://localhost:8188        ││
│ │ [14:30:10] Client connected from 127.0.0.1                 ││
│ │ █                                                           ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ Status: 🟢 Running    PID: 12345    Uptime: 5m 23s             │
│                                                                 │
│                                         [■ Stop]  [⟳ Restart] │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Backend Foundation
- [ ] `ScriptRunner` class - process execution, log capture
- [ ] `ProcessManager` - registry, health checks
- [ ] API endpoints - run, status, stop, logs
- [ ] WebSocket streaming for real-time logs
- [ ] Tests

### Phase 2: Frontend Components
- [ ] Extend `InstallPlugin.tsx` - remove prototype notice
- [ ] `PackScriptsSection.tsx` - script list with actions
- [ ] `ScriptConsoleModal.tsx` - real-time console output
- [ ] Status indicators, progress bars
- [ ] Tests

### Phase 3: Environment Management
- [ ] `.env` editor in UI
- [ ] Port configuration
- [ ] Auto-start on boot option
- [ ] Multiple instances support

### Phase 4: Pack Templates
- [ ] ComfyUI install pack template
- [ ] Forge install pack template
- [ ] Documentation for creating custom install packs

---

## Security Considerations

1. **Script Validation** - Verify script source before execution
2. **Sandboxing** - Consider running in containers
3. **Permissions** - Limit what scripts can do
4. **Logging** - Audit trail for all executions
5. **User Confirmation** - Confirm before destructive operations

---

## Related Plans

- **PLAN-Pack-Edit.md** - Original plugin system (InstallPlugin prototype)
- **PLAN-Workflow-Wizard.md** - Workflow generation for UIs

---

## Open Questions

| Question | Status |
|----------|--------|
| How to handle long-running processes after app restart? | Open |
| Should we use Docker for isolation? | Open |
| How to handle port conflicts? | Open |
| Auto-update mechanism? | Open |

---

*Created: 2026-02-03*
*Last Updated: 2026-02-03*
