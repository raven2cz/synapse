"""
Tests for resolve_scoring.py — Noisy-OR, provenance grouping, tier ceiling.
"""

import pytest

from src.store.resolve_models import EvidenceGroup, EvidenceHit, EvidenceItem, CandidateSeed
from src.store.resolve_scoring import (
    get_tier_ceiling,
    group_by_provenance,
    noisy_or,
    score_candidate,
)
from src.store.models import DependencySelector, SelectorStrategy


def _make_hit(provenance: str, source: str, confidence: float) -> EvidenceHit:
    """Helper to create an EvidenceHit."""
    return EvidenceHit(
        candidate=CandidateSeed(
            key="test:1",
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai={"model_id": 1, "version_id": 1, "file_id": 1},
            ),
            display_name="test",
            provider_name="civitai",
        ),
        provenance=provenance,
        item=EvidenceItem(source=source, description="test", confidence=confidence),
    )


class TestNoisyOR:
    def test_empty(self):
        assert noisy_or([]) == 0.0

    def test_single_value(self):
        assert noisy_or([0.85]) == pytest.approx(0.85)

    def test_two_independent_groups(self):
        # 1 - (1-0.85)*(1-0.78) = 1 - 0.15*0.22 = 1 - 0.033 = 0.967
        result = noisy_or([0.85, 0.78])
        assert result == pytest.approx(0.967, abs=0.001)

    def test_three_groups(self):
        result = noisy_or([0.8, 0.6, 0.4])
        # 1 - (0.2)*(0.4)*(0.6) = 1 - 0.048 = 0.952
        assert result == pytest.approx(0.952, abs=0.001)

    def test_zero_confidence(self):
        assert noisy_or([0.0]) == pytest.approx(0.0)

    def test_perfect_confidence(self):
        assert noisy_or([1.0]) == pytest.approx(1.0)

    def test_perfect_always_wins(self):
        assert noisy_or([1.0, 0.5]) == pytest.approx(1.0)


class TestProvenanceGrouping:
    def test_same_image_groups_into_one(self):
        hits = [
            _make_hit("preview:001.png", "preview_embedded", 0.85),
            _make_hit("preview:001.png", "preview_api_meta", 0.82),
        ]
        groups = group_by_provenance(hits)
        assert len(groups) == 1
        assert "preview:001.png" in groups

    def test_different_images_stay_separate(self):
        hits = [
            _make_hit("preview:001.png", "preview_embedded", 0.85),
            _make_hit("preview:002.png", "preview_api_meta", 0.78),
        ]
        groups = group_by_provenance(hits)
        assert len(groups) == 2

    def test_group_confidence_is_max_of_items(self):
        hits = [
            _make_hit("preview:001.png", "preview_embedded", 0.85),
            _make_hit("preview:001.png", "preview_api_meta", 0.82),
        ]
        groups = group_by_provenance(hits)
        group = groups["preview:001.png"]
        assert group.combined_confidence == pytest.approx(0.85)

    def test_single_hit_per_group(self):
        hits = [_make_hit("hash:sha256", "hash_match", 0.95)]
        groups = group_by_provenance(hits)
        assert len(groups) == 1
        assert groups["hash:sha256"].combined_confidence == pytest.approx(0.95)

    def test_empty_hits(self):
        groups = group_by_provenance([])
        assert groups == {}


class TestGetTierCeiling:
    def test_tier1_evidence_ceiling_100(self):
        groups = [
            EvidenceGroup(
                provenance="hash:sha256",
                items=[EvidenceItem(source="hash_match", description="t", confidence=0.95)],
                combined_confidence=0.95,
            ),
        ]
        assert get_tier_ceiling(groups) == pytest.approx(1.0)

    def test_tier2_evidence_ceiling_089(self):
        groups = [
            EvidenceGroup(
                provenance="preview:001.png",
                items=[EvidenceItem(source="preview_embedded", description="t", confidence=0.85)],
                combined_confidence=0.85,
            ),
        ]
        assert get_tier_ceiling(groups) == pytest.approx(0.89)

    def test_tier3_evidence_ceiling_074(self):
        groups = [
            EvidenceGroup(
                provenance="file:name",
                items=[EvidenceItem(source="file_metadata", description="t", confidence=0.60)],
                combined_confidence=0.60,
            ),
        ]
        assert get_tier_ceiling(groups) == pytest.approx(0.74)

    def test_tier4_evidence_ceiling_049(self):
        groups = [
            EvidenceGroup(
                provenance="source:base",
                items=[EvidenceItem(source="source_metadata", description="t", confidence=0.40)],
                combined_confidence=0.40,
            ),
        ]
        assert get_tier_ceiling(groups) == pytest.approx(0.49)

    def test_mixed_tiers_uses_best(self):
        """When evidence from multiple tiers, ceiling from best tier."""
        groups = [
            EvidenceGroup(
                provenance="hash:sha256",
                items=[EvidenceItem(source="hash_match", description="t", confidence=0.95)],
                combined_confidence=0.95,
            ),
            EvidenceGroup(
                provenance="preview:001.png",
                items=[EvidenceItem(source="preview_embedded", description="t", confidence=0.85)],
                combined_confidence=0.85,
            ),
        ]
        assert get_tier_ceiling(groups) == pytest.approx(1.0)

    def test_empty_groups_default(self):
        assert get_tier_ceiling([]) == pytest.approx(0.49)


class TestScoreCandidate:
    def test_single_group(self):
        groups = [
            EvidenceGroup(
                provenance="preview:001.png",
                items=[EvidenceItem(source="preview_embedded", description="t", confidence=0.85)],
                combined_confidence=0.85,
            ),
        ]
        score = score_candidate(groups)
        # Noisy-OR of [0.85] = 0.85, ceiling = 0.89 → 0.85
        assert score == pytest.approx(0.85)

    def test_two_preview_groups_capped_by_tier2(self):
        """Spec example: two preview groups, ceiling T2=0.89."""
        groups = [
            EvidenceGroup(
                provenance="preview:001.png",
                items=[
                    EvidenceItem(source="preview_embedded", description="t", confidence=0.85),
                    EvidenceItem(source="preview_api_meta", description="t", confidence=0.82),
                ],
                combined_confidence=0.85,
            ),
            EvidenceGroup(
                provenance="preview:002.png",
                items=[EvidenceItem(source="preview_api_meta", description="t", confidence=0.78)],
                combined_confidence=0.78,
            ),
        ]
        score = score_candidate(groups)
        # Noisy-OR: 1 - (1-0.85)*(1-0.78) = 0.967
        # Ceiling: best evidence is T2 → 0.89
        # Final: min(0.967, 0.89) = 0.89
        assert score == pytest.approx(0.89)

    def test_hash_match_lifts_ceiling(self):
        """Adding hash match (T1) lifts ceiling to 1.0."""
        groups = [
            EvidenceGroup(
                provenance="hash:sha256",
                items=[EvidenceItem(source="hash_match", description="t", confidence=0.95)],
                combined_confidence=0.95,
            ),
            EvidenceGroup(
                provenance="preview:001.png",
                items=[EvidenceItem(source="preview_embedded", description="t", confidence=0.85)],
                combined_confidence=0.85,
            ),
        ]
        score = score_candidate(groups)
        # Noisy-OR: 1 - (1-0.95)*(1-0.85) = 1 - 0.05*0.15 = 0.9925
        # Ceiling: T1 → 1.0
        # Final: 0.9925
        assert score == pytest.approx(0.9925, abs=0.001)

    def test_empty_groups(self):
        assert score_candidate([]) == 0.0

    def test_tier3_only(self):
        groups = [
            EvidenceGroup(
                provenance="file:stem",
                items=[EvidenceItem(source="file_metadata", description="t", confidence=0.60)],
                combined_confidence=0.60,
            ),
        ]
        score = score_candidate(groups)
        # Noisy-OR: 0.60, ceiling: 0.74
        assert score == pytest.approx(0.60)
