# Claude Session Archive

Archived Claude Code session transcripts for project continuity across machines.

## Sessions

| File | Date | Description |
|------|------|-------------|
| `nsfw-filter-session-2026-03-06.zip` | 2026-03-06 | NSFW Filter System design — 5 review rounds (Claude + Gemini 3.1 Pro), 22 issues resolved, spec v4.0.0 in Czech |

## How to restore

1. Unzip the session file:
   ```bash
   unzip plans/sessions/nsfw-filter-session-2026-03-06.zip -d ~/.claude/projects/-home-box-git-github-synapse/
   ```

2. Resume with Claude Code:
   ```bash
   cd ~/git/github/synapse
   claude --resume 070001ad-5e63-479d-94f5-095a27a38e2f
   ```

3. If the session is too large to resume, start a new session — Claude will read `CLAUDE.md` and `plans/PLAN-NSFW.md` automatically.

## Notes

- Session transcripts are JSONL files stored in `~/.claude/projects/<project-path>/`
- The session ID is the filename without `.jsonl` extension
- Transcripts contain the full conversation including tool calls and results
