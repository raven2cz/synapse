"""
Dependency Resolution Task

AI-powered dependency resolution for model packs. Uses MCP tools
(search_civitai, analyze_civitai_model, search_huggingface, find_model_by_hash)
to find matching models for unresolved dependencies.

The entire prompt lives in config/avatar/skills/model-resolution.md.
This module only handles: input formatting, output parsing, and validation.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import AITask

logger = logging.getLogger(__name__)

# AI confidence ceiling — AI provider cannot exceed TIER-2 (hash-based).
# Rule-based providers handle TIER-1 (0.90-1.00).
AI_CONFIDENCE_CEILING = 0.89

# Required fields per provider type
_CIVITAI_REQUIRED = {"display_name", "provider", "model_id", "confidence", "reasoning"}
_HF_REQUIRED = {"display_name", "provider", "repo_id", "filename", "confidence", "reasoning"}
_COMMON_REQUIRED = {"display_name", "provider", "confidence", "reasoning"}


class DependencyResolutionTask(AITask):
    """AI task for resolving model pack dependencies via MCP tool search.

    Flow:
    1. Caller formats pack metadata + dependency info into structured text
    2. Skills content (model-resolution.md + reference docs) = full system prompt
    3. AvatarEngine calls MCP tools (search, analyze) and returns JSON candidates
    4. parse_result() normalizes candidates and enforces confidence ceiling
    5. validate_output() ensures structural validity

    The prompt is NOT hardcoded here — it lives in config/avatar/skills/model-resolution.md
    so it can be edited without code changes.
    """

    task_type = "dependency_resolution"
    SKILL_NAMES = (
        "model-resolution",
        "dependency-resolution",
        "model-types",
        "civitai-integration",
        "huggingface-integration",
    )
    needs_mcp = True
    timeout_s = 180

    def build_system_prompt(self, skills_content: str) -> str:
        """Return skills content as the complete system prompt.

        Unlike other tasks, the entire prompt is in the skill files.
        model-resolution.md contains the task instructions, output format,
        confidence rules, and few-shot examples. The other 4 skill files
        provide reference knowledge (API docs, model types, etc.).
        """
        return skills_content

    def parse_result(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """Parse AI output into normalized candidate list.

        Handles:
        - Extracts candidates list from output
        - Enforces AI_CONFIDENCE_CEILING on each candidate
        - Validates per-provider required fields
        - Sorts by confidence descending
        - Preserves search_summary for diagnostics

        Returns:
            Dict with "candidates" (list) and "search_summary" (str).
        """
        if not isinstance(raw_output, dict):
            return {"candidates": [], "search_summary": "Invalid AI output format"}

        candidates_raw = raw_output.get("candidates", [])
        if not isinstance(candidates_raw, list):
            return {"candidates": [], "search_summary": "Missing candidates list"}

        parsed_candidates: List[Dict[str, Any]] = []

        for candidate in candidates_raw:
            if not isinstance(candidate, dict):
                continue

            # Enforce confidence ceiling
            confidence = candidate.get("confidence", 0.0)
            if not isinstance(confidence, (int, float)):
                confidence = 0.0
            candidate["confidence"] = min(float(confidence), AI_CONFIDENCE_CEILING)

            # Validate required fields based on provider
            provider = candidate.get("provider", "")
            if provider == "civitai":
                if not _CIVITAI_REQUIRED.issubset(candidate.keys()):
                    missing = _CIVITAI_REQUIRED - candidate.keys()
                    logger.warning(
                        "[dep-resolution] Civitai candidate missing fields: %s",
                        missing,
                    )
                    continue
            elif provider == "huggingface":
                if not _HF_REQUIRED.issubset(candidate.keys()):
                    missing = _HF_REQUIRED - candidate.keys()
                    logger.warning(
                        "[dep-resolution] HuggingFace candidate missing fields: %s",
                        missing,
                    )
                    continue
            else:
                if not _COMMON_REQUIRED.issubset(candidate.keys()):
                    continue

            parsed_candidates.append(candidate)

        # Sort by confidence descending
        parsed_candidates.sort(key=lambda c: c["confidence"], reverse=True)

        return {
            "candidates": parsed_candidates,
            "search_summary": raw_output.get("search_summary", ""),
        }

    def validate_output(self, output: Any) -> bool:
        """Validate parsed output structure.

        Accepts:
        - Empty candidates list (valid "no match" result)
        - Non-empty candidates with valid confidence bounds

        Rejects:
        - Non-dict output
        - Missing "candidates" key
        - Candidates with confidence > AI_CONFIDENCE_CEILING
        """
        if not isinstance(output, dict):
            return False

        candidates = output.get("candidates")
        if not isinstance(candidates, list):
            return False

        # Empty candidates is a valid "no match" result
        if not candidates:
            return True

        # Validate each candidate
        for c in candidates:
            if not isinstance(c, dict):
                return False
            conf = c.get("confidence", -1)
            if not isinstance(conf, (int, float)):
                return False
            if conf < 0 or conf > AI_CONFIDENCE_CEILING:
                return False
            if not c.get("display_name"):
                return False

        return True

    def get_fallback(self) -> None:
        """No fallback — E1-E6 evidence providers run independently of AI."""
        return None
