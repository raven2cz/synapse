# Skills & Avatars

Skills inject domain knowledge into the AI's system prompt. Avatars customize the AI's visual appearance and personality. Both are extensible — you can create your own alongside the built-ins.

## Skills System

### How It Works

Skills are Markdown files (`.md`) that get appended to the AI's system prompt under a `# Domain Knowledge` section. Each skill adds a `## Skill: {name}` subsection. This gives the AI deep knowledge about specific topics without training.

The prompt is built in this order:
1. Base system prompt (from `avatar.yaml` or built-in default)
2. Built-in skills (alphabetical)
3. Custom skills (override same-named built-ins)

### Built-in Skills (9)

| Skill | File | Description |
|-------|------|-------------|
| Civitai Integration | `civitai-integration.md` | API endpoints, CDN URL transforms, auth, type mapping |
| Dependency Resolution | `dependency-resolution.md` | `AssetDependency` fields, source types, resolution process |
| Generation Params | `generation-params.md` | Core parameters (CFG, steps, sampler), hi-res fix, per-architecture tips |
| Install Packs | `install-packs.md` | Profile structure, directory layouts per UI, symlink views |
| Inventory Management | `inventory-management.md` | Blob status/location enums, operations, backup, safety guards |
| Model Types | `model-types.md` | Base architectures (SD 1.5 → Flux), compatibility, file formats |
| Pack Management | `pack-management.md` | Pack lifecycle, `pack.json` schema, import options |
| Synapse Basics | `synapse-basics.md` | Core concepts (Pack, Blob, Dependency, Profile), store layout |
| Workflow Creation | `workflow-creation.md` | ComfyUI format, common node types, workflow storage |

Built-in skills are installed at `~/.synapse/avatar/skills/` (copied from `config/avatar/skills/` during setup).

### Custom Skills

Create custom skills to teach the AI about your specific workflows, models, or conventions.

**Location:** `~/.synapse/avatar/custom-skills/`

**Format:** Any `.md` file. YAML frontmatter (if present) is automatically stripped.

```markdown
<!-- ~/.synapse/avatar/custom-skills/my-workflow.md -->
---
title: My Custom Workflow
---

# My Preferred Workflow

I use ComfyUI with the following standard setup:
- Base model: JuggernautXL v9
- LoRA: detail_tweaker_xl at weight 0.4
- Always use DPM++ 2M SDE Karras sampler
- Resolution: 1024x1024 for portraits, 1344x768 for landscapes
```

**Rules:**
- Only `.md` files are loaded
- Maximum file size: 50 KB per skill (larger files are skipped with a warning)
- Skills are sorted alphabetically
- Custom skills with the same filename as a built-in **override** the built-in

### Overriding Built-in Skills

To customize a built-in skill, create a file with the same name in the custom skills directory:

```bash
# Override the model-types skill with your own version
cp ~/.synapse/avatar/skills/model-types.md ~/.synapse/avatar/custom-skills/model-types.md
# Edit the custom version
```

The custom version completely replaces the built-in for that skill name.

### Verifying Skills

Check which skills are loaded via the API:

```bash
curl -s http://localhost:8000/api/avatar/config | python -m json.tool
# Look for: "skills_count": {"builtin": 9, "custom": 0}
```

Or in the UI: **Settings > AI Assistant > Skills** shows all loaded skills with their source (builtin/custom).

---

## Avatars

Avatars customize the AI assistant's visual appearance in the chat interface.

### Built-in Avatars (8)

| ID | Name |
|----|------|
| `bella` | Bella |
| `heart` | Heart |
| `nicole` | Nicole |
| `sky` | Sky |
| `adam` | Adam |
| `michael` | Michael |
| `george` | George |
| `astronautka` | Astronautka |

Plus the **Synapse** avatar — a custom avatar with animated bust images (idle, thinking, speaking states).

Avatars can be selected in the chat UI. The active avatar determines the bust image shown in compact mode.

### Custom Avatars

Create your own avatars in `~/.synapse/avatar/avatars/`:

```
~/.synapse/avatar/avatars/
  my-avatar/
    avatar.json       # Required — metadata and configuration
    portrait.png      # Optional — portrait image
    thumbnail.png     # Optional — small thumbnail
```

**`avatar.json` format:**

```json
{
  "name": "Display Name",
  "description": "Short description of the avatar",
  "personality": "friendly, concise",
  "system_prompt_append": "Extra instructions appended to the system prompt when this avatar is active."
}
```

**Rules:**
- Each avatar is a subdirectory with an `avatar.json` file (max 1 MB)
- Symlinks are skipped for security
- Invalid JSON files are skipped with a warning
- Images are optional — the UI shows a text fallback if not provided
- Custom avatars are auto-detected on server startup

### Listing Avatars

```bash
curl -s http://localhost:8000/api/avatar/avatars | python -m json.tool
# Returns: {"builtin": [...], "custom": [...]}
```

## See Also

- [Configuration](configuration.md) — Skills and avatar path settings
- [Architecture](architecture.md) — How skills are loaded and injected
- [Getting Started](getting-started.md) — First chat setup
