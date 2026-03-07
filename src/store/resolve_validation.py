"""
Resolve validation — per-strategy minimum field checks and cross-kind validation.

Based on PLAN-Resolve-Model.md v0.7.1 sections 5, 2h.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .models import AssetKind, DependencySelector, SelectorStrategy
from .resolve_config import check_cross_kind_compatibility
from .resolve_models import ApplyResult

# Per-strategy required fields: (field_path, human_label)
STRATEGY_REQUIREMENTS: Dict[SelectorStrategy, List[Tuple[str, str]]] = {
    SelectorStrategy.CIVITAI_FILE: [
        ("civitai.model_id", "Civitai model ID"),
        ("civitai.version_id", "Civitai version ID"),
        ("civitai.file_id", "Civitai file ID"),
    ],
    SelectorStrategy.CIVITAI_MODEL_LATEST: [
        ("civitai.model_id", "Civitai model ID"),
    ],
    SelectorStrategy.HUGGINGFACE_FILE: [
        ("huggingface.repo_id", "HuggingFace repo ID"),
        ("huggingface.filename", "HuggingFace filename"),
    ],
    SelectorStrategy.LOCAL_FILE: [
        ("local_path", "Local file: requires local_path"),
    ],
    SelectorStrategy.URL_DOWNLOAD: [
        ("url", "Download URL"),
    ],
    SelectorStrategy.BASE_MODEL_HINT: [
        ("base_model", "Base model alias"),
    ],
}


def _get_field(selector: DependencySelector, field_path: str) -> object:
    """Get a nested field from selector by dot-separated path."""
    parts = field_path.split(".")
    obj = selector
    for part in parts:
        if obj is None:
            return None
        obj = getattr(obj, part, None)
    return obj


def validate_selector_fields(selector: DependencySelector) -> ApplyResult:
    """Validate that a selector has all required fields for its strategy.

    Returns ApplyResult with success=False if validation fails.
    """
    reqs = STRATEGY_REQUIREMENTS.get(selector.strategy, [])
    missing = []

    for field_path, label in reqs:
        value = _get_field(selector, field_path)
        if value is None or value == "":
            missing.append(label)
        elif isinstance(value, int) and value == 0:
            missing.append(f"{label} (invalid zero value)")

    if missing:
        return ApplyResult(
            success=False,
            message=f"Selector validation failed: Missing required field: {missing[0]}",
        )

    return ApplyResult(success=True, message="Validation passed")


def validate_candidate(
    selector: DependencySelector,
    kind: AssetKind,
    pack_base_model: Optional[str] = None,
    candidate_base_model: Optional[str] = None,
) -> ApplyResult:
    """Full validation: field check + cross-kind compatibility.

    Returns ApplyResult. On success, compatibility_warnings may be non-empty
    (warnings don't block apply, but should be shown to the user).
    """
    # Step 1: Field validation
    field_result = validate_selector_fields(selector)
    if not field_result.success:
        return field_result

    # Step 2: Cross-kind compatibility
    warnings = check_cross_kind_compatibility(
        pack_base_model, candidate_base_model, kind,
    )

    return ApplyResult(
        success=True,
        message="Validation passed",
        compatibility_warnings=warnings,
    )


def validate_before_apply(
    selector: DependencySelector,
    kind: AssetKind,
    pack_base_model: Optional[str] = None,
    candidate_base_model: Optional[str] = None,
) -> ApplyResult:
    """Convenience alias for validate_candidate."""
    return validate_candidate(selector, kind, pack_base_model, candidate_base_model)
