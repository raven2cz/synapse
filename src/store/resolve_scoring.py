"""
Resolve scoring — Noisy-OR combination, provenance grouping, tier ceiling.

Based on PLAN-Resolve-Model.md v0.7.1 section 2g.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .resolve_config import TIER_CONFIGS, get_tier_for_confidence
from .resolve_models import EvidenceGroup, EvidenceHit, EvidenceItem


def group_by_provenance(hits: List[EvidenceHit]) -> Dict[str, EvidenceGroup]:
    """Group evidence hits by provenance, per candidate.

    Within each group: combined_confidence = max(item.confidence).
    """
    groups: Dict[str, List[EvidenceItem]] = defaultdict(list)

    for hit in hits:
        groups[hit.provenance].append(hit.item)

    result: Dict[str, EvidenceGroup] = {}
    for provenance, items in groups.items():
        combined = max(item.confidence for item in items)
        result[provenance] = EvidenceGroup(
            provenance=provenance,
            items=items,
            combined_confidence=combined,
        )

    return result


def noisy_or(confidences: List[float]) -> float:
    """Combine independent confidence values using Noisy-OR.

    P(correct) = 1 - product(1 - c_i for each c_i)
    """
    if not confidences:
        return 0.0

    product = 1.0
    for c in confidences:
        product *= (1.0 - c)

    return 1.0 - product


def get_tier_ceiling(groups: List[EvidenceGroup]) -> float:
    """Get the tier ceiling — the max of the best evidence tier.

    The final confidence is capped by the maximum confidence allowed
    by the best (lowest-numbered) tier present in the evidence.
    """
    if not groups:
        return 0.49  # Default: Tier 4 ceiling

    best_tier = 4
    for group in groups:
        for item in group.items:
            tier = get_tier_for_confidence(item.confidence)
            if tier < best_tier:
                best_tier = tier

    # Return the max confidence of that tier
    for tc in TIER_CONFIGS:
        if tc.tier == best_tier:
            return tc.max

    return 0.49


def score_candidate(groups: List[EvidenceGroup]) -> float:
    """Score a candidate using provenance grouping + Noisy-OR + tier ceiling.

    Steps:
    1. Each group contributes its combined_confidence (max within group)
    2. Independent groups combine via Noisy-OR
    3. Final confidence is capped by the tier ceiling of the best evidence
    """
    if not groups:
        return 0.0

    # Step 1+2: Noisy-OR of group confidences
    group_confidences = [g.combined_confidence for g in groups]
    raw_score = noisy_or(group_confidences)

    # Step 3: Cap by tier ceiling
    ceiling = get_tier_ceiling(groups)
    return min(raw_score, ceiling)
