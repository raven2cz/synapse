# Custom Avatars

Custom avatars extend avatar-engine with your own AI assistant characters.

## Directory Structure

Each custom avatar is a subdirectory containing an `avatar.json` file:

```
avatars/
  my-avatar/
    avatar.json       # Required — avatar metadata
    portrait.png      # Optional — avatar portrait image
    thumbnail.png     # Optional — small icon
```

## avatar.json Format

```json
{
  "name": "My Custom Avatar",
  "description": "A helpful assistant specialized in...",
  "personality": "friendly, concise, technical",
  "system_prompt_append": "Additional instructions for this avatar character."
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name shown in UI |
| `description` | string | No | Short description of the avatar |
| `personality` | string | No | Personality traits (used in prompts) |
| `system_prompt_append` | string | No | Extra text appended to system prompt |

## Built-in Avatars

Avatar-engine ships with 8 built-in avatars:

- **Bella** — Friendly and creative
- **Heart** — Warm and empathetic
- **Nicole** — Professional and precise
- **Sky** — Curious and explorative
- **Adam** — Technical and analytical
- **Michael** — Practical and efficient
- **George** — Experienced and thorough
- **Astronautka** — Adventurous and bold

## Notes

- Custom avatars are detected automatically on startup
- Subdirectories without `avatar.json` are ignored
- Invalid JSON files are skipped with a warning
- Avatar images are optional — the UI will show a text fallback
