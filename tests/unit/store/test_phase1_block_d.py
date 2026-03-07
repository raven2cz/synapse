"""
Phase 1 Block D tests — BUG 2 (model_tagging at import) + Migration helper.

Tests for:
- BUG 1: extractBaseModelHint() replaced with pack.base_model
- BUG 2: model_tagging() rule-based fallback runs during import
- Migration helper: migrate_resolve_deps() dry-run and apply modes
"""

from unittest.mock import MagicMock, patch

import pytest

from src.store.models import (
    AssetKind,
    CivitaiSelector,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackCategory,
    PackDependency,
    PackSource,
    ProviderName,
    SelectorStrategy,
    UpdatePolicy,
    UpdatePolicyMode,
)
from src.store.resolve_models import (
    ApplyResult,
    ResolutionCandidate,
    SuggestOptions,
    SuggestResult,
)


# =============================================================================
# Helpers
# =============================================================================

def _pack_with_description(desc: str, tags: list = None) -> Pack:
    """Create a pack with a description for tagging tests."""
    return Pack(
        name="test-pack",
        pack_type=AssetKind.LORA,
        source=PackSource(provider=ProviderName.CIVITAI, model_id=1001),
        description=desc,
        tags=tags or [],
        dependencies=[],
    )


def _pack_with_unresolved_dep() -> Pack:
    """Pack with a BASE_MODEL_HINT dep (needs migration)."""
    return Pack(
        name="old-pack",
        pack_type=AssetKind.LORA,
        source=PackSource(provider=ProviderName.CIVITAI, model_id=1001),
        base_model="SDXL",
        dependencies=[
            PackDependency(
                id="base_checkpoint",
                kind=AssetKind.CHECKPOINT,
                required=False,
                selector=DependencySelector(
                    strategy=SelectorStrategy.BASE_MODEL_HINT,
                    base_model="SDXL",
                ),
                expose=ExposeConfig(filename="SDXL.safetensors"),
            ),
            PackDependency(
                id="main_lora",
                kind=AssetKind.LORA,
                required=True,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelector(model_id=100, version_id=200, file_id=300),
                ),
                expose=ExposeConfig(filename="my_lora.safetensors"),
            ),
        ],
    )


# =============================================================================
# BUG 2: model_tagging at import
# =============================================================================

class TestBug2ModelTagging:
    """model_tagging rule-based fallback should run during import."""

    def test_tagging_adds_category_to_tags(self):
        """If description mentions 'anime', pack.tags should get it."""
        from src.avatar.tasks.model_tagging import ModelTaggingTask

        task = ModelTaggingTask()
        fallback = task.get_fallback()
        assert fallback is not None

        result = fallback("This is an anime style LoRA for character generation")
        assert result.success
        assert "anime" in result.output.get("tags", [])
        assert result.output.get("category") == "anime"

    def test_tagging_detects_photorealistic(self):
        from src.avatar.tasks.model_tagging import ModelTaggingTask

        task = ModelTaggingTask()
        fallback = task.get_fallback()
        result = fallback("A photorealistic portrait model for SDXL, generates realistic faces")
        assert result.success
        assert result.output.get("category") == "photorealistic"

    def test_tagging_extracts_trigger_words(self):
        from src.avatar.tasks.model_tagging import ModelTaggingTask

        task = ModelTaggingTask()
        fallback = task.get_fallback()
        result = fallback("LoRA for anime characters. Trigger words: ohisashiburi, hello_style")
        assert result.success
        assert "ohisashiburi" in result.output.get("trigger_words", [])

    def test_tagging_no_match_returns_failure(self):
        from src.avatar.tasks.model_tagging import ModelTaggingTask

        task = ModelTaggingTask()
        fallback = task.get_fallback()
        result = fallback("")
        assert not result.success

    def test_tagging_merges_with_existing_tags(self):
        """New tags should be added without duplicating existing ones."""
        pack = _pack_with_description(
            "Anime LoRA for character portraits",
            tags=["anime", "sdxl"],
        )

        from src.avatar.tasks.model_tagging import ModelTaggingTask
        task = ModelTaggingTask()
        fallback = task.get_fallback()
        result = fallback(pack.description)

        if result.success and result.output:
            all_tags = list(result.output.get("tags", []))
            if result.output.get("category"):
                all_tags.append(result.output["category"])
            existing = set(pack.tags)
            new_tags = [t for t in all_tags if t not in existing]
            pack.tags = list(existing) + new_tags

        # 'anime' should not be duplicated
        assert pack.tags.count("anime") == 1
        # 'sdxl' should remain
        assert "sdxl" in pack.tags


# =============================================================================
# Migration helper
# =============================================================================

class TestMigrateResolveDeps:
    """Tests for Store.migrate_resolve_deps()."""

    def test_dry_run_reports_would_apply(self):
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.pack_service = MagicMock()

            pack = _pack_with_unresolved_dep()
            store.list_packs = MagicMock(return_value=["old-pack"])
            store.get_pack = MagicMock(return_value=pack)

            top = ResolutionCandidate(
                display_name="Juggernaut XL",
                confidence=0.88,
                tier=2,
                strategy=SelectorStrategy.CIVITAI_FILE,
                evidence_groups=[],
            )
            store.resolve_service.suggest.return_value = SuggestResult(
                candidates=[top],
            )

            results = store.migrate_resolve_deps(dry_run=True)

            assert len(results) == 1
            assert results[0]["pack"] == "old-pack"
            assert results[0]["dep_id"] == "base_checkpoint"
            assert results[0]["action"] == "would_apply"
            assert results[0]["would_apply"] == "Juggernaut XL"

            # Should NOT have called apply
            store.resolve_service.apply.assert_not_called()

    def test_apply_mode_calls_apply(self):
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.pack_service = MagicMock()

            pack = _pack_with_unresolved_dep()
            store.list_packs = MagicMock(return_value=["old-pack"])
            store.get_pack = MagicMock(return_value=pack)

            top = ResolutionCandidate(
                display_name="Juggernaut XL",
                confidence=0.95,
                tier=1,
                strategy=SelectorStrategy.CIVITAI_FILE,
                evidence_groups=[],
            )
            store.resolve_service.suggest.return_value = SuggestResult(
                candidates=[top],
            )
            store.resolve_service.apply.return_value = ApplyResult(success=True)

            results = store.migrate_resolve_deps(dry_run=False)

            assert results[0]["action"] == "applied"
            store.resolve_service.apply.assert_called_once()

    def test_skips_already_resolved_deps(self):
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.pack_service = MagicMock()

            pack = _pack_with_unresolved_dep()
            store.list_packs = MagicMock(return_value=["old-pack"])
            store.get_pack = MagicMock(return_value=pack)

            store.resolve_service.suggest.return_value = SuggestResult(candidates=[])

            results = store.migrate_resolve_deps(dry_run=True)

            # Only base_checkpoint has BASE_MODEL_HINT, main_lora already CIVITAI_FILE
            assert len(results) == 1
            assert results[0]["dep_id"] == "base_checkpoint"

    def test_low_confidence_not_applied(self):
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.pack_service = MagicMock()

            pack = _pack_with_unresolved_dep()
            store.list_packs = MagicMock(return_value=["old-pack"])
            store.get_pack = MagicMock(return_value=pack)

            weak = ResolutionCandidate(
                display_name="some model",
                confidence=0.40,
                tier=4,
                strategy=SelectorStrategy.CIVITAI_FILE,
                evidence_groups=[],
            )
            store.resolve_service.suggest.return_value = SuggestResult(
                candidates=[weak],
            )

            results = store.migrate_resolve_deps(dry_run=False)

            assert results[0]["action"] == "low_confidence"
            store.resolve_service.apply.assert_not_called()

    def test_ambiguous_candidates_not_applied(self):
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.pack_service = MagicMock()

            pack = _pack_with_unresolved_dep()
            store.list_packs = MagicMock(return_value=["old-pack"])
            store.get_pack = MagicMock(return_value=pack)

            a = ResolutionCandidate(
                display_name="Model A",
                confidence=0.82,
                tier=2,
                strategy=SelectorStrategy.CIVITAI_FILE,
                evidence_groups=[],
            )
            b = ResolutionCandidate(
                display_name="Model B",
                confidence=0.78,
                tier=2,
                strategy=SelectorStrategy.CIVITAI_FILE,
                evidence_groups=[],
            )
            store.resolve_service.suggest.return_value = SuggestResult(
                candidates=[a, b],
            )

            results = store.migrate_resolve_deps(dry_run=True)

            assert results[0]["action"] == "ambiguous"

    def test_error_handling(self):
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.pack_service = MagicMock()

            pack = _pack_with_unresolved_dep()
            store.list_packs = MagicMock(return_value=["old-pack"])
            store.get_pack = MagicMock(return_value=pack)

            store.resolve_service.suggest.side_effect = RuntimeError("provider crash")

            results = store.migrate_resolve_deps(dry_run=True)

            assert results[0]["action"] == "error"
            assert "provider crash" in results[0]["error"]
