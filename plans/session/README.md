# Claude Code Session Backup

## What's in the archive

`claude-session-synapse-2026-03-08.tar.gz` contains the **complete** Claude Code
project session directory for Synapse, including:

- All conversation transcripts (`.jsonl` files) — full history of all sessions
- Session metadata directories (subagents, tool-results)
- `sessions-index.json` — session index with timestamps, branches, summaries
- `memory/` — persistent auto-memory files (MEMORY.md, patterns.md, etc.)

**Last active session:** `99d1ab0e-2b50-41ae-870f-22b1d5af9c14`
- Branch: `feat/resolve-model-redesign`
- Work: Phase 1 complete (committed), Phase 2 PLAN detailed, ready for Block A (skill design)
- Context: Resolve Model Redesign — AI-enhanced dependency resolution

## Memory files (standalone backup)

Memory files are also stored separately in this directory for easy access
without extracting the full archive:

- `MEMORY.md` — main auto-memory (critical rules, active specs, workflows)
- `download-system.md` — download system architecture reference

These are the same files as in the archive under `memory/`.

## How to restore on another machine

### 1. Extract the archive

```bash
# The archive must be extracted to the Claude Code projects directory.
# The path encodes the project working directory.

mkdir -p ~/.claude/projects
cd ~/.claude/projects
tar xzf /path/to/claude-session-synapse-2026-03-08.tar.gz
```

This creates `~/.claude/projects/-home-box-git-github-synapse/` with all sessions.

### 2. Verify the path matches your project

Claude Code maps project directories to session directories by replacing `/` with `-`
in the absolute path. If your Synapse repo is at a different path than `/home/box/git/github/synapse`,
you need to rename the extracted directory:

```bash
# Example: if your repo is at /home/alice/projects/synapse
cd ~/.claude/projects
mv ./-home-box-git-github-synapse ./-home-alice-projects-synapse
```

### 2b. Restore memory files (if NOT extracting the full archive)

If you only want memory continuity without full session history:

```bash
# Create the project memory directory
PROJECT_DIR=$(echo "$PWD" | sed 's|/|-|g; s|^|/|; s|^/|-|')
mkdir -p ~/.claude/projects/${PROJECT_DIR}/memory

# Copy memory files
cp plans/session/MEMORY.md ~/.claude/projects/${PROJECT_DIR}/memory/
cp plans/session/download-system.md ~/.claude/projects/${PROJECT_DIR}/memory/
```

### 3. Resume the session

```bash
cd /path/to/synapse
claude --resume 99d1ab0e-2b50-41ae-870f-22b1d5af9c14
```

Or start a new session — Claude will automatically load `memory/MEMORY.md` and
the project's `CLAUDE.md` for context continuity.

### 4. What to tell Claude in the new session

If starting fresh (not resuming), tell Claude:

> Continue work on `feat/resolve-model-redesign` branch.
> Phase 1 is committed (c855dbe). Phase 2 PLAN is detailed in
> `plans/PLAN-Resolve-Model.md` — start with Block A (skill file design).

## Notes

- Archive size: ~90 MB (484 MB uncompressed)
- Sessions span: 2026-01-24 to 2026-03-08
- The `.jsonl` transcripts contain full conversation history including tool calls and results
- Memory files are also backed up — they persist across sessions automatically
