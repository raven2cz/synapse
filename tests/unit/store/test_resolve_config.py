"""
Tests for resolve_config.py — tier boundaries, asset kind config, compatibility.
"""

import pytest

from src.store.models import AssetKind
from src.store.resolve_config import (
    AI_CONFIDENCE_CEILING,
    ASSET_KIND_CONFIG,
    AUTO_APPLY_MARGIN,
    COMPATIBILITY_RULES,
    HF_ELIGIBLE_KINDS,
    TIER_CONFIGS,
    check_cross_kind_compatibility,
    get_kind_config,
    get_tier_ceiling,
    get_tier_for_confidence,
    get_tier_label,
)


class TestTierConfigs:
    def test_tiers_non_overlapping(self):
        """Tier ranges must not overlap (C1 fix)."""
        sorted_tiers = sorted(TIER_CONFIGS, key=lambda t: t.min)
        for i in range(len(sorted_tiers) - 1):
            assert sorted_tiers[i].max < sorted_tiers[i + 1].min, (
                f"Tier {sorted_tiers[i].tier} overlaps with tier {sorted_tiers[i + 1].tier}"
            )

    def test_tier_count(self):
        assert len(TIER_CONFIGS) == 4

    def test_ai_ceiling_within_tier2(self):
        """AI ceiling must be at TIER-2 max."""
        tier2 = next(t for t in TIER_CONFIGS if t.tier == 2)
        assert AI_CONFIDENCE_CEILING == tier2.max


class TestGetTierForConfidence:
    @pytest.mark.parametrize("confidence,expected_tier", [
        (0.95, 1),  # Hash match
        (0.92, 1),  # Filename exact
        (0.90, 1),  # Tier 1 boundary
        (0.85, 2),  # Preview meta
        (0.75, 2),  # Tier 2 boundary
        (0.60, 3),  # Stem match
        (0.50, 3),  # Tier 3 boundary
        (0.40, 4),  # Source metadata
        (0.30, 4),  # Tier 4 boundary
        (1.00, 1),  # Perfect match
    ])
    def test_confidence_to_tier(self, confidence, expected_tier):
        assert get_tier_for_confidence(confidence) == expected_tier

    def test_below_minimum(self):
        """Below 0.30 should still return tier 4."""
        assert get_tier_for_confidence(0.10) == 4

    def test_above_maximum(self):
        """Above 1.0 should still return tier 1."""
        assert get_tier_for_confidence(1.5) == 1


class TestGetTierCeiling:
    def test_tier1_ceiling(self):
        assert get_tier_ceiling(1) == 1.00

    def test_tier2_ceiling(self):
        assert get_tier_ceiling(2) == 0.89

    def test_tier3_ceiling(self):
        assert get_tier_ceiling(3) == 0.74

    def test_tier4_ceiling(self):
        assert get_tier_ceiling(4) == 0.49

    def test_unknown_tier(self):
        assert get_tier_ceiling(99) == 0.49


class TestGetTierLabel:
    def test_all_tiers_have_labels(self):
        for tc in TIER_CONFIGS:
            label = get_tier_label(tc.tier)
            assert label != "Unknown"
            assert len(label) > 0

    def test_unknown_tier(self):
        assert get_tier_label(99) == "Unknown"


class TestAssetKindConfig:
    def test_checkpoint_config(self):
        cfg = get_kind_config(AssetKind.CHECKPOINT)
        assert ".safetensors" in cfg.extensions
        assert ".ckpt" in cfg.extensions
        assert cfg.civitai_filter == "Checkpoint"
        assert cfg.hf_eligible is True
        assert cfg.hf_hash_lookup is True

    def test_lora_no_hf(self):
        """LoRA should not use HF search (C7)."""
        cfg = get_kind_config(AssetKind.LORA)
        assert cfg.hf_eligible is False
        assert cfg.hf_hash_lookup is False
        assert cfg.civitai_filter == "LORA"

    def test_vae_hf_eligible(self):
        cfg = get_kind_config(AssetKind.VAE)
        assert cfg.hf_eligible is True
        assert cfg.hf_hash_lookup is False

    def test_controlnet_hf_eligible(self):
        cfg = get_kind_config(AssetKind.CONTROLNET)
        assert cfg.hf_eligible is True

    def test_embedding_no_hf(self):
        cfg = get_kind_config(AssetKind.EMBEDDING)
        assert cfg.hf_eligible is False

    def test_unknown_kind_defaults(self):
        cfg = get_kind_config(AssetKind.UNKNOWN)
        assert ".safetensors" in cfg.extensions
        assert cfg.civitai_filter is None
        assert cfg.hf_eligible is False

    def test_all_configured_kinds_have_extensions(self):
        for kind, cfg in ASSET_KIND_CONFIG.items():
            assert len(cfg.extensions) > 0, f"{kind} has no extensions"


class TestCrossKindCompatibility:
    def test_checkpoint_always_compatible(self):
        """Checkpoints define base model — no check."""
        warnings = check_cross_kind_compatibility("SD 1.5", "SDXL", AssetKind.CHECKPOINT)
        assert warnings == []

    def test_sdxl_lora_compatible(self):
        warnings = check_cross_kind_compatibility("SDXL", "SDXL", AssetKind.LORA)
        assert warnings == []

    def test_pony_on_sdxl_compatible(self):
        """Pony is SDXL-based — should be compatible."""
        warnings = check_cross_kind_compatibility("SDXL", "Pony", AssetKind.LORA)
        assert warnings == []

    def test_sd15_on_sdxl_incompatible(self):
        warnings = check_cross_kind_compatibility("SDXL", "SD 1.5", AssetKind.LORA)
        assert len(warnings) == 1
        assert "mismatch" in warnings[0].lower()

    def test_flux_on_sdxl_incompatible(self):
        warnings = check_cross_kind_compatibility("SDXL", "Flux", AssetKind.LORA)
        assert len(warnings) == 1

    def test_unknown_pack_base_model(self):
        """Unknown base model should not produce warnings."""
        warnings = check_cross_kind_compatibility(None, "SDXL", AssetKind.LORA)
        assert warnings == []

    def test_unknown_candidate_base_model(self):
        warnings = check_cross_kind_compatibility("SDXL", None, AssetKind.LORA)
        assert warnings == []

    def test_illustrious_on_sdxl(self):
        """Illustrious is SDXL-compatible."""
        warnings = check_cross_kind_compatibility("Illustrious", "SDXL", AssetKind.LORA)
        assert warnings == []


class TestHFEligibleKinds:
    def test_checkpoint_eligible(self):
        assert AssetKind.CHECKPOINT in HF_ELIGIBLE_KINDS

    def test_vae_eligible(self):
        assert AssetKind.VAE in HF_ELIGIBLE_KINDS

    def test_controlnet_eligible(self):
        assert AssetKind.CONTROLNET in HF_ELIGIBLE_KINDS

    def test_lora_not_eligible(self):
        assert AssetKind.LORA not in HF_ELIGIBLE_KINDS

    def test_embedding_not_eligible(self):
        assert AssetKind.EMBEDDING not in HF_ELIGIBLE_KINDS

    def test_upscaler_not_eligible(self):
        assert AssetKind.UPSCALER not in HF_ELIGIBLE_KINDS

    def test_matches_config(self):
        """HF_ELIGIBLE_KINDS must match ASSET_KIND_CONFIG hf_eligible flags."""
        expected = {k for k, cfg in ASSET_KIND_CONFIG.items() if cfg.hf_eligible}
        assert HF_ELIGIBLE_KINDS == expected

    def test_is_frozen(self):
        assert isinstance(HF_ELIGIBLE_KINDS, frozenset)


class TestAutoApplyMargin:
    def test_default_value(self):
        assert AUTO_APPLY_MARGIN == 0.15

    def test_positive(self):
        assert AUTO_APPLY_MARGIN > 0

    def test_less_than_one(self):
        assert AUTO_APPLY_MARGIN < 1.0
