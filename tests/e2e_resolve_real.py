#!/usr/bin/env python3
"""
Real E2E test: AI-powered dependency resolution with live providers.

Tests the full suggest pipeline with REAL AI providers (Gemini, Claude/Opus, Codex)
against 5 test scenarios:
  - 3 base model checkpoints (SDXL, Illustrious, Flux.1 Dev)
  - 2 LoRAs (anime style LoRA, realistic photo LoRA)

Usage:
  uv run python tests/e2e_resolve_real.py

Requirements:
  - gemini, claude, codex CLIs installed
  - Valid auth for each provider
  - avatar-engine skills in config/avatar/skills/
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.avatar.config import load_avatar_config, AvatarConfig
from src.avatar.task_service import AvatarTaskService
from src.store.evidence_providers import AIEvidenceProvider
from src.store.models import (
    AssetKind,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackDependency,
    PackSource,
    ProviderName,
    SelectorStrategy,
)
from src.store.resolve_config import AI_CONFIDENCE_CEILING
from src.store.resolve_models import (
    ResolveContext,
    SuggestOptions,
    PreviewModelHint,
)
from src.store.resolve_service import ResolveService

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("e2e_resolve")
logger.setLevel(logging.INFO)
# Enable task-service debug for diagnostics
logging.getLogger("src.avatar.task_service").setLevel(logging.DEBUG)


# =============================================================================
# Test Scenarios
# =============================================================================

@dataclass
class TestScenario:
    """A test scenario for dependency resolution."""
    name: str
    pack_type: str
    base_model: str
    dep_id: str
    dep_kind: AssetKind
    expose_filename: str
    description: str
    tags: list[str] = field(default_factory=list)
    preview_hints: list[dict] = field(default_factory=list)
    # Expected: what we consider a "correct" resolution
    expected_providers: list[str] = field(default_factory=list)  # civitai, huggingface
    expected_keywords: list[str] = field(default_factory=list)  # keywords in display_name


SCENARIOS: list[TestScenario] = [
    # --- 3 Base Models ---
    TestScenario(
        name="SDXL Base Checkpoint",
        pack_type="lora",
        base_model="SDXL",
        dep_id="base_checkpoint",
        dep_kind=AssetKind.CHECKPOINT,
        expose_filename="sd_xl_base_1.0.safetensors",
        description="Anime LoRA trained on SDXL base model. Requires SDXL 1.0 checkpoint.",
        tags=["anime", "sdxl", "style"],
        preview_hints=[
            {"filename": "sd_xl_base_1.0.safetensors", "raw_value": "SDXL Base 1.0",
             "source_type": "api_meta"},
        ],
        expected_providers=["civitai", "huggingface"],
        expected_keywords=["sdxl", "xl", "base", "1.0"],
    ),
    TestScenario(
        name="Illustrious XL Checkpoint",
        pack_type="lora",
        base_model="Illustrious",
        dep_id="base_checkpoint",
        dep_kind=AssetKind.CHECKPOINT,
        expose_filename="illustriousXL_v060.safetensors",
        description="Anime character LoRA based on Illustrious XL. High quality illustration style.",
        tags=["anime", "illustrious", "character"],
        preview_hints=[
            {"filename": "illustriousXL_v060.safetensors", "raw_value": "Illustrious XL v0.60",
             "source_type": "api_meta"},
        ],
        expected_providers=["civitai"],
        expected_keywords=["illustrious"],
    ),
    TestScenario(
        name="Flux.1 Dev Checkpoint",
        pack_type="lora",
        base_model="Flux.1 D",
        dep_id="base_checkpoint",
        dep_kind=AssetKind.CHECKPOINT,
        expose_filename="flux1-dev.safetensors",
        description="Flux LoRA for photorealistic generation. Requires Flux.1 Dev checkpoint from Black Forest Labs.",
        tags=["flux", "photorealistic", "realistic"],
        preview_hints=[
            {"filename": "flux1-dev.safetensors", "raw_value": "FLUX.1 [dev]",
             "source_type": "api_meta"},
        ],
        expected_providers=["huggingface"],
        expected_keywords=["flux", "dev", "black-forest"],
    ),
    # --- 2 LoRAs ---
    TestScenario(
        name="Detail Tweaker LoRA (SDXL)",
        pack_type="checkpoint",
        base_model="SDXL",
        dep_id="detail_lora",
        dep_kind=AssetKind.LORA,
        expose_filename="add-detail-xl.safetensors",
        description="SDXL checkpoint pack. Uses Detail Tweaker XL LoRA for enhanced detail rendering.",
        tags=["sdxl", "detail", "enhancer"],
        preview_hints=[
            {"filename": "add-detail-xl.safetensors", "raw_value": "Detail Tweaker XL",
             "source_type": "api_meta"},
        ],
        expected_providers=["civitai"],
        expected_keywords=["detail", "tweaker"],
    ),
    TestScenario(
        name="Pony Diffusion V6 XL (LoRA dependency)",
        pack_type="lora",
        base_model="Pony",
        dep_id="base_checkpoint",
        dep_kind=AssetKind.CHECKPOINT,
        expose_filename="ponyDiffusionV6XL.safetensors",
        description="Anime LoRA trained on Pony Diffusion V6 XL. Requires the Pony V6 checkpoint.",
        tags=["pony", "anime", "pdxl"],
        preview_hints=[
            {"filename": "ponyDiffusionV6XL.safetensors", "raw_value": "Pony Diffusion V6 XL",
             "source_type": "api_meta"},
        ],
        expected_providers=["civitai"],
        expected_keywords=["pony", "diffusion", "v6"],
    ),
]


# =============================================================================
# Test Runner
# =============================================================================

@dataclass
class CandidateResult:
    display_name: str
    provider: str
    confidence: float
    base_model: str
    reasoning: str


@dataclass
class TestResult:
    scenario: str
    provider_name: str
    success: bool
    candidates: list[CandidateResult]
    top_match: str
    top_confidence: float
    correct: bool  # Does top match look correct?
    duration_s: float
    error: str = ""
    warnings: list[str] = field(default_factory=list)


def _build_pack(scenario: TestScenario) -> Pack:
    """Build a minimal Pack object for the scenario."""
    return Pack(
        schema="1.0",
        name=f"test-{scenario.name.lower().replace(' ', '-')}",
        pack_type=scenario.pack_type,
        source=PackSource(provider=ProviderName.CIVITAI, model_id=99999),
        base_model=scenario.base_model,
        description=scenario.description,
        tags=scenario.tags,
        dependencies=[
            PackDependency(
                id=scenario.dep_id,
                kind=scenario.dep_kind,
                required=True,
                selector=DependencySelector(
                    strategy=SelectorStrategy.BASE_MODEL_HINT,
                    base_model=scenario.base_model,
                ),
                expose=ExposeConfig(filename=scenario.expose_filename),
            ),
        ],
    )


def _build_context(scenario: TestScenario, pack: Pack) -> ResolveContext:
    """Build ResolveContext for the scenario."""
    dep = pack.dependencies[0]
    hints = [
        PreviewModelHint(
            filename=h["filename"],
            raw_value=h["raw_value"],
            source_type=h["source_type"],
            source_image=h.get("source_image", "preview_001.png"),
        )
        for h in scenario.preview_hints
    ]
    return ResolveContext(
        pack=pack,
        dependency=dep,
        kind=scenario.dep_kind,
        preview_hints=hints,
    )


def _evaluate_correctness(scenario: TestScenario, candidates: list[dict]) -> bool:
    """Check if top candidate looks correct based on expected keywords."""
    if not candidates:
        return False
    top = candidates[0]
    name = (top.get("display_name", "") or "").lower()
    # Check if any expected keyword appears in the display name
    return any(kw.lower() in name for kw in scenario.expected_keywords)


def run_scenario_with_provider(
    scenario: TestScenario,
    provider_name: str,
) -> TestResult:
    """Run a single scenario with a specific AI provider."""
    pack = _build_pack(scenario)
    ctx = _build_context(scenario, pack)

    # Create fresh config for each run to avoid state leakage
    config = load_avatar_config()
    config.extraction.cache_enabled = False
    config.provider = provider_name
    avatar = AvatarTaskService(config=config)

    # Create AIEvidenceProvider directly
    ai_provider = AIEvidenceProvider(avatar_getter=lambda: avatar)

    start = time.time()
    try:
        result = ai_provider.gather(ctx)
        duration = time.time() - start

        # Extract candidates from EvidenceHit objects
        candidates = []
        for hit in result.hits:
            candidates.append({
                "display_name": hit.candidate.display_name or hit.candidate.key,
                "provider": hit.candidate.provider_name or "unknown",
                "confidence": hit.item.confidence,
                "base_model": "",  # Not directly on EvidenceHit
                "reasoning": hit.item.raw_value or hit.item.description,
            })

        # Sort by confidence
        candidates.sort(key=lambda c: c["confidence"], reverse=True)

        correct = _evaluate_correctness(scenario, candidates)
        top = candidates[0] if candidates else {}

        return TestResult(
            scenario=scenario.name,
            provider_name=provider_name,
            success=True,
            candidates=[
                CandidateResult(
                    display_name=c["display_name"],
                    provider=c["provider"],
                    confidence=c["confidence"],
                    base_model=c["base_model"],
                    reasoning=c.get("reasoning", ""),
                )
                for c in candidates[:5]
            ],
            top_match=top.get("display_name", "NONE"),
            top_confidence=top.get("confidence", 0.0),
            correct=correct,
            duration_s=duration,
            warnings=result.warnings,
        )
    except Exception as e:
        duration = time.time() - start
        return TestResult(
            scenario=scenario.name,
            provider_name=provider_name,
            success=False,
            candidates=[],
            top_match="ERROR",
            top_confidence=0.0,
            correct=False,
            duration_s=duration,
            error=str(e),
        )


# =============================================================================
# Main
# =============================================================================

# claude excluded: bridge process exits in non-interactive context (sandbox limitation)
PROVIDERS = ["gemini", "codex"]


def main():
    results: list[TestResult] = []

    total = len(SCENARIOS) * len(PROVIDERS)
    idx = 0

    for scenario in SCENARIOS:
        for provider in PROVIDERS:
            idx += 1
            logger.info(
                "[%d/%d] %s x %s ...",
                idx, total, scenario.name, provider,
            )
            result = run_scenario_with_provider(scenario, provider)
            results.append(result)

            status = "PASS" if result.correct else ("FAIL" if result.success else "ERR")
            logger.info(
                "  → %s  top=%s  conf=%.0f%%  %.1fs",
                status,
                result.top_match[:40],
                result.top_confidence * 100,
                result.duration_s,
            )

    # Print results table
    print("\n" + "=" * 120)
    print("RESOLVE MODEL E2E TEST RESULTS")
    print("=" * 120)
    print(
        f"{'Scenario':<30} {'Provider':<10} {'Status':<6} "
        f"{'Top Match':<40} {'Conf':<6} {'Time':<7} {'Correct':<8}"
    )
    print("-" * 120)

    pass_count = 0
    fail_count = 0
    err_count = 0

    for r in results:
        status = "PASS" if r.correct else ("FAIL" if r.success else "ERR")
        if r.correct:
            pass_count += 1
        elif r.success:
            fail_count += 1
        else:
            err_count += 1

        print(
            f"{r.scenario:<30} {r.provider_name:<10} {status:<6} "
            f"{r.top_match[:38]:<40} {r.top_confidence*100:>4.0f}%  "
            f"{r.duration_s:>5.1f}s  {'YES' if r.correct else 'NO':>5}"
        )

    print("-" * 120)
    print(
        f"Total: {len(results)} tests | "
        f"PASS: {pass_count} | FAIL: {fail_count} | ERR: {err_count} | "
        f"AI ceiling: {AI_CONFIDENCE_CEILING*100:.0f}%"
    )
    print("=" * 120)

    # Detailed results
    print("\n\nDETAILED CANDIDATES:")
    print("=" * 120)
    for r in results:
        if not r.candidates:
            continue
        print(f"\n{r.scenario} x {r.provider_name}:")
        for i, c in enumerate(r.candidates[:3], 1):
            print(
                f"  #{i} [{c.provider}] {c.display_name} "
                f"(conf={c.confidence*100:.0f}%, base={c.base_model})"
            )
            if c.reasoning:
                print(f"      → {c.reasoning[:80]}")
        if r.warnings:
            print(f"  Warnings: {r.warnings}")
        if r.error:
            print(f"  Error: {r.error}")

    # Exit code
    sys.exit(0 if err_count == 0 else 1)


if __name__ == "__main__":
    main()
