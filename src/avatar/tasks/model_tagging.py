"""
Model Tagging Task

Extracts tags, categories and content descriptors from model descriptions.
Used for automatic categorization during import.
"""

from typing import Any, Callable, Dict, List, Optional

from .base import AITask, TaskResult


# Known categories for validation
VALID_CATEGORIES = frozenset({
    "anime", "photorealistic", "illustration", "cartoon", "3d",
    "pixel-art", "sketch", "painting", "concept-art", "abstract",
})

VALID_CONTENT_TYPES = frozenset({
    "character", "landscape", "portrait", "full-body", "vehicle",
    "architecture", "animal", "food", "clothing", "weapon", "nsfw",
})


class ModelTaggingTask(AITask):
    """
    Task for extracting tags and categories from model descriptions.

    Extracts:
    - category: primary style category (anime, photorealistic, etc.)
    - content_types: what the model generates (character, landscape, etc.)
    - tags: free-form descriptive tags
    - trigger_words: activation words for LoRAs
    - base_model_hint: mentioned base model compatibility
    """

    task_type = "model_tagging"
    SKILL_NAMES = ("generation-params",)

    def build_system_prompt(self, skills_content: str) -> str:
        """Build tagging prompt with optional skills knowledge."""
        prompt = TAGGING_PROMPT
        if skills_content.strip():
            prompt += f"\n\n---\n\n# Reference Knowledge\n\n{skills_content}"
        return prompt

    def parse_result(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and normalize tagging result.

        Ensures:
        - category is a known string or 'other'
        - content_types is a list of strings
        - tags is a list of strings
        - trigger_words is a list of strings
        """
        if not isinstance(raw_output, dict):
            return {}

        result: Dict[str, Any] = {}

        # Category: normalize to known value
        cat = raw_output.get("category", "")
        if isinstance(cat, str):
            cat_lower = cat.lower().strip()
            result["category"] = cat_lower if cat_lower in VALID_CATEGORIES else "other"

        # Content types: ensure list of strings
        ct = raw_output.get("content_types", [])
        if isinstance(ct, list):
            result["content_types"] = [
                s.lower().strip() for s in ct
                if isinstance(s, str) and s.strip()
            ]
        elif isinstance(ct, str):
            result["content_types"] = [ct.lower().strip()]

        # Tags: ensure list of strings
        tags = raw_output.get("tags", [])
        if isinstance(tags, list):
            result["tags"] = [
                s.strip() for s in tags
                if isinstance(s, str) and s.strip()
            ]
        elif isinstance(tags, str):
            result["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

        # Trigger words: ensure list of strings
        tw = raw_output.get("trigger_words", [])
        if isinstance(tw, list):
            result["trigger_words"] = [
                s.strip() for s in tw
                if isinstance(s, str) and s.strip()
            ]
        elif isinstance(tw, str):
            result["trigger_words"] = [t.strip() for t in tw.split(",") if t.strip()]

        # Base model hint: optional string
        bm = raw_output.get("base_model_hint", "")
        if isinstance(bm, str) and bm.strip():
            result["base_model_hint"] = bm.strip()

        return result

    def validate_output(self, output: Any) -> bool:
        """Validate tagging output. Must have category or at least one tag."""
        if not isinstance(output, dict):
            return False
        return bool(
            output.get("category")
            or output.get("tags")
            or output.get("content_types")
        )

    def get_fallback(self) -> Optional[Callable[[str], TaskResult]]:
        """Return keyword-matching fallback for tagging."""

        def _fallback(description: str) -> TaskResult:
            tags = _extract_tags_by_keywords(description)
            if tags.get("category") or tags.get("tags"):
                return TaskResult(
                    success=True,
                    output=tags,
                    provider_id="rule_based",
                    model="keyword_match",
                )
            return TaskResult(
                success=False,
                error="No tags could be extracted from description",
                provider_id="rule_based",
            )

        return _fallback


def _extract_tags_by_keywords(text: str) -> Dict[str, Any]:
    """Simple keyword-based tag extraction."""
    text_lower = text.lower()
    result: Dict[str, Any] = {}

    # Detect category (specific multi-word categories first, then general)
    category_keywords = [
        ("concept-art", ["concept art", "concept-art"]),
        ("pixel-art", ["pixel art", "pixel-art", "8-bit", "16-bit"]),
        ("3d", ["3d render", "3d model", "blender"]),
        ("photorealistic", ["photorealistic", "realistic", "photo", "photography"]),
        ("anime", ["anime", "manga", "waifu", "animagine"]),
        ("cartoon", ["cartoon", "comic", "toon"]),
        ("illustration", ["illustration", "illustrated", "artwork"]),
        ("painting", ["painting", "oil paint", "watercolor"]),
    ]
    for cat, keywords in category_keywords:
        if any(kw in text_lower for kw in keywords):
            result["category"] = cat
            break

    # Detect content types
    content_keywords = {
        "character": ["character", "person", "figure"],
        "landscape": ["landscape", "scenery", "background", "environment"],
        "portrait": ["portrait", "face", "headshot"],
        "full-body": ["full body", "full-body"],
        "nsfw": ["nsfw", "adult", "explicit"],
    }
    content_types: List[str] = []
    for ct, keywords in content_keywords.items():
        if any(kw in text_lower for kw in keywords):
            content_types.append(ct)
    if content_types:
        result["content_types"] = content_types

    # Extract trigger words (simple pattern: "trigger word: X" or "trigger: X")
    import re
    tw_match = re.findall(
        r"trigger\s*(?:word)?s?\s*[:=]\s*([^\n<]+)",
        text_lower,
    )
    if tw_match:
        trigger_words = []
        for match in tw_match:
            for word in match.split(","):
                word = word.strip().strip('"').strip("'")
                if word and len(word) < 50:
                    trigger_words.append(word)
        if trigger_words:
            result["trigger_words"] = trigger_words

    # Collect free-form tags from detected attributes
    tags: List[str] = []
    if result.get("category"):
        tags.append(result["category"])
    tags.extend(result.get("content_types", []))
    if tags:
        result["tags"] = tags

    return result


TAGGING_PROMPT = """# Model Tagging Task

You are a model tagging engine for AI image generation models (Stable Diffusion, Flux, etc.).

## Instructions

Given a model description, extract tags and categorization metadata.

## Output Format

Return ONLY valid JSON with these fields:

```json
{
  "category": "anime|photorealistic|illustration|cartoon|3d|pixel-art|sketch|painting|concept-art|abstract|other",
  "content_types": ["character", "landscape", "portrait", ...],
  "tags": ["free-form", "descriptive", "tags"],
  "trigger_words": ["activation", "words"],
  "base_model_hint": "SDXL|SD1.5|Flux|Pony|..."
}
```

## Rules
- category MUST be one of the listed values
- content_types: what the model is designed to generate
- tags: descriptive tags about style, quality, purpose
- trigger_words: only if explicitly mentioned in the description
- base_model_hint: only if a base model is clearly mentioned
- Omit fields if no relevant information found (don't hallucinate)
- Return ONLY JSON, no explanation
"""
