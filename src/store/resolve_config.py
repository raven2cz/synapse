"""
Resolve configuration — tier boundaries, asset kind config, compatibility rules.

Based on PLAN-Resolve-Model.md v0.7.1 sections 2b, 2c, 2h, 4, 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional, Set

from .models import AssetKind


# =============================================================================
# Confidence Tiers — non-overlapping ranges
# =============================================================================

@dataclass(frozen=True)
class TierConfig:
    """Configuration for a confidence tier."""
    tier: int
    min: float   # inclusive
    max: float   # inclusive
    label: str


TIER_CONFIGS = [
    TierConfig(tier=1, min=0.90, max=1.00, label="Exact match"),
    TierConfig(tier=2, min=0.75, max=0.89, label="High confidence"),
    TierConfig(tier=3, min=0.50, max=0.74, label="Possible match"),
    TierConfig(tier=4, min=0.30, max=0.49, label="Hint only"),
]

# AI confidence ceiling — AI can never exceed TIER-2 max
AI_CONFIDENCE_CEILING = 0.89


def get_tier_for_confidence(confidence: float) -> int:
    """Return the tier number for a given confidence value.

    Uses >= comparison against tier minimums (sorted descending) to avoid
    gaps between tier boundaries.
    """
    for tc in TIER_CONFIGS:  # Already sorted T1→T4 (descending min)
        if confidence >= tc.min:
            return tc.tier
    return 4  # Below all tier minimums


def get_tier_ceiling(tier: int) -> float:
    """Return the maximum confidence allowed for a given tier."""
    for tc in TIER_CONFIGS:
        if tc.tier == tier:
            return tc.max
    return 0.49  # Default to Tier 4 ceiling


def get_tier_label(tier: int) -> str:
    """Return human-readable label for a tier."""
    for tc in TIER_CONFIGS:
        if tc.tier == tier:
            return tc.label
    return "Unknown"


# =============================================================================
# Asset Kind Configuration — per-kind settings for resolution
# =============================================================================

@dataclass(frozen=True)
class AssetKindConfig:
    """Per-kind configuration for model resolution."""
    extensions: FrozenSet[str]
    civitai_filter: Optional[str] = None
    hf_eligible: bool = False
    hf_hash_lookup: bool = False


ASSET_KIND_CONFIG: Dict[AssetKind, AssetKindConfig] = {
    AssetKind.CHECKPOINT: AssetKindConfig(
        extensions=frozenset({".safetensors", ".ckpt"}),
        civitai_filter="Checkpoint",
        hf_eligible=True,
        hf_hash_lookup=True,
    ),
    AssetKind.LORA: AssetKindConfig(
        extensions=frozenset({".safetensors"}),
        civitai_filter="LORA",
        hf_eligible=False,
        hf_hash_lookup=False,
    ),
    AssetKind.VAE: AssetKindConfig(
        extensions=frozenset({".safetensors", ".pt"}),
        civitai_filter="VAE",
        hf_eligible=True,
        hf_hash_lookup=False,
    ),
    AssetKind.CONTROLNET: AssetKindConfig(
        extensions=frozenset({".safetensors", ".pth"}),
        civitai_filter="Controlnet",
        hf_eligible=True,
        hf_hash_lookup=False,
    ),
    AssetKind.EMBEDDING: AssetKindConfig(
        extensions=frozenset({".safetensors", ".pt", ".bin"}),
        civitai_filter="TextualInversion",
        hf_eligible=False,
        hf_hash_lookup=False,
    ),
    AssetKind.UPSCALER: AssetKindConfig(
        extensions=frozenset({".pth", ".safetensors"}),
        civitai_filter="Upscaler",
        hf_eligible=False,
        hf_hash_lookup=False,
    ),
}


def get_kind_config(kind: AssetKind) -> AssetKindConfig:
    """Get configuration for an asset kind. Returns defaults for unknown kinds."""
    return ASSET_KIND_CONFIG.get(kind, AssetKindConfig(
        extensions=frozenset({".safetensors"}),
    ))


# Convenience set: asset kinds eligible for HuggingFace search
HF_ELIGIBLE_KINDS: FrozenSet[AssetKind] = frozenset(
    kind for kind, cfg in ASSET_KIND_CONFIG.items() if cfg.hf_eligible
)

# Auto-apply margin: minimum confidence gap between top-1 and top-2 candidate
# for automatic resolution during import. Candidates within this margin
# are presented to user for manual selection.
AUTO_APPLY_MARGIN = 0.15


# =============================================================================
# Cross-Kind Compatibility Rules
# =============================================================================

# base_model_category → compatible categories
COMPATIBILITY_RULES: Dict[str, Set[str]] = {
    "SD 1.5": {"SD 1.5"},
    "SDXL": {"SDXL", "Pony"},
    "Illustrious": {"SDXL", "Illustrious"},
    "Pony": {"SDXL", "Pony"},
    "Flux": {"Flux"},
    "Flux.1 D": {"Flux", "Flux.1 D"},
    "Flux.1 S": {"Flux", "Flux.1 S"},
    "SD 3.5": {"SD 3.5"},
}


def check_cross_kind_compatibility(
    pack_base_model: Optional[str],
    candidate_base_model: Optional[str],
    kind: AssetKind,
) -> list[str]:
    """Check if a candidate is compatible with the pack's base model.

    Returns list of warning strings (empty = compatible).
    No check for checkpoints — they define the base model.
    """
    # Checkpoints define the base model, no compatibility check
    if kind == AssetKind.CHECKPOINT:
        return []

    # If either is unknown, can't check
    if not pack_base_model or not candidate_base_model:
        return []

    pack_compat = COMPATIBILITY_RULES.get(pack_base_model)
    if pack_compat is None:
        return []  # Unknown base model, skip check

    if candidate_base_model not in pack_compat:
        return [
            f"Base model mismatch: pack uses '{pack_base_model}' "
            f"but candidate is for '{candidate_base_model}'"
        ]

    return []
