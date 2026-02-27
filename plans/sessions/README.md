# Claude Code Session Transcripts

Archived session transcripts from all Claude Code projects on this machine.
Split into per-project zip files (GitHub 100 MB limit).

## Archive contents

- **Files:** `<project-name>.zip` — one zip per project
- **Source:** `~/.claude/projects/` (all projects, all sessions + subagents)
- **Format:** JSONL (one JSON object per line — each line is a conversation turn)
- **Total:** 935 files, 727 MB uncompressed → 132 MB compressed

### Projects included

| Zip file | Project path | Sessions | Subagents | Size |
|----------|-------------|----------|-----------|------|
| `-home-box-git-github-synapse.zip` | `~/git/github/synapse` | 49 | 250 | 65 MB |
| `-home-box-git-github-avatar-engine.zip` | `~/git/github/avatar-engine` | 135 | 264 | 43 MB |
| `-home-box-git-github-somewm.zip` | `~/git/github/somewm` | 53 | 61 | 14 MB |
| `-home-box-git-github-escape-game-engine.zip` | `~/git/github/escape-game-engine` | 2 | 0 | 5 MB |
| `-home-box.zip` | `~` (general) | 29 | 9 | 2.6 MB |
| `-home-box-org-vault.zip` | `~/org/vault` | 2 | 2 | 1.9 MB |
| `-home-box-git-github-gemini-cli.zip` | `~/git/github/gemini-cli` | 15 | 7 | 1.4 MB |
| `-home-box--config-ranger.zip` | `~/.config/ranger` | 10 | 4 | 467 KB |
| Others (6 small) | misc | 12 | 0 | < 100 KB |

## How to restore

### 1. Extract to Claude Code projects directory

```bash
# Restore ALL sessions
cd ~/.claude/projects
for zip in /path/to/plans/sessions/*.zip; do
    unzip -o "$zip"
done

# Or restore just one project
cd ~/.claude/projects
unzip /path/to/plans/sessions/-home-box-git-github-synapse.zip
```

This recreates the original directory structure:
```
~/.claude/projects/
├── -home-box-git-github-synapse/
│   ├── <session-uuid>.jsonl          # Main session transcript
│   └── <session-uuid>/
│       └── subagents/
│           └── agent-<id>.jsonl      # Subagent transcripts
├── -home-box-git-github-avatar-engine/
│   └── ...
└── ...
```

### 2. Resume a session in Claude Code

```bash
# List recent sessions for a project
cd ~/git/github/synapse
claude --resume     # Interactive session picker

# Resume a specific session by ID
claude --resume <session-uuid>
```

The session UUID is the filename without `.jsonl` extension, e.g.:
`d611fc00-23c6-4576-bbd3-6bc021057e39.jsonl` → `claude --resume d611fc00-23c6-4576-bbd3-6bc021057e39`

### 3. Read session transcripts

Each `.jsonl` file contains the full conversation history. To inspect:

```bash
# Pretty-print a session
cat ~/.claude/projects/-home-box-git-github-synapse/<uuid>.jsonl | python -m json.tool --no-ensure-ascii

# Search across all sessions for a topic
grep -rl "AvatarTaskService" ~/.claude/projects/-home-box-git-github-synapse/*.jsonl

# Count messages in a session
wc -l ~/.claude/projects/-home-box-git-github-synapse/<uuid>.jsonl
```

### 4. Directory name mapping

Claude Code encodes project paths as directory names by replacing `/` with `-`:

| Directory name | Original path |
|----------------|---------------|
| `-home-box-git-github-synapse` | `/home/box/git/github/synapse` |
| `-home-box-git-github-avatar-engine` | `/home/box/git/github/avatar-engine` |
| `-home-box-git-github-somewm` | `/home/box/git/github/somewm` |
| `-home-box` | `/home/box` (general, no project) |

## Notes

- Transcripts do NOT include `memory/` files or `CLAUDE.md` — those are in the repo
- Subagent transcripts are in `<session-uuid>/subagents/` subdirectories
- Sessions can be large (10-50 MB each for long conversations)
- Archive created: 2026-02-27
