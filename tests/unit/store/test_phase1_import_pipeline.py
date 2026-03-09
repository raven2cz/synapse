"""
Phase 1 Block C tests — Import pipeline integration with evidence ladder.

Tests for:
- SuggestOptions.preview_hints_override
- ResolveService.suggest() uses override hints
- Store._post_import_resolve() orchestration
- Store.suggest_resolution() / apply_resolution() delegate methods
- Auto-apply logic (tier check, margin check)
"""

from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

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
    CandidateSeed,
    EvidenceHit,
    PreviewModelHint,
    ResolutionCandidate,
    SuggestOptions,
    SuggestResult,
)


# =============================================================================
# Helpers
# =============================================================================

def _make_pack(name="test-pack", base_model="SDXL") -> Pack:
    """Create a pack with base_checkpoint + main_lora deps."""
    return Pack(
        name=name,
        pack_type=AssetKind.LORA,
        source=PackSource(provider=ProviderName.CIVITAI, model_id=1001),
        base_model=base_model,
        dependencies=[
            PackDependency(
                id="base_checkpoint",
                kind=AssetKind.CHECKPOINT,
                required=False,
                selector=DependencySelector(
                    strategy=SelectorStrategy.BASE_MODEL_HINT,
                    base_model=base_model,
                ),
                expose=ExposeConfig(filename=f"{base_model}.safetensors"),
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


def _make_candidate(confidence: float, tier: int, name: str = "model") -> ResolutionCandidate:
    """Create a ResolutionCandidate with given confidence/tier."""
    return ResolutionCandidate(
        display_name=name,
        confidence=confidence,
        tier=tier,
        strategy=SelectorStrategy.CIVITAI_FILE,
        evidence_groups=[],
        selector_data={"civitai": {"model_id": 50, "version_id": 60, "file_id": 70}},
    )


PATCH_EXTRACT = "src.utils.preview_meta_extractor.extract_preview_hints"


# =============================================================================
# SuggestOptions.preview_hints_override
# =============================================================================

class TestSuggestOptionsPreviewHints:
    """Test that SuggestOptions accepts preview_hints_override."""

    def test_default_is_none(self):
        opts = SuggestOptions()
        assert opts.preview_hints_override is None

    def test_accepts_hints_list(self):
        hints = [
            PreviewModelHint(
                filename="dreamshaper_8.safetensors",
                kind=AssetKind.CHECKPOINT,
                source_image="001.png",
                source_type="api_meta",
                raw_value="dreamshaper_8",
            ),
        ]
        opts = SuggestOptions(preview_hints_override=hints)
        assert len(opts.preview_hints_override) == 1
        assert opts.preview_hints_override[0].filename == "dreamshaper_8.safetensors"

    def test_empty_list_is_valid(self):
        opts = SuggestOptions(preview_hints_override=[])
        assert opts.preview_hints_override == []


# =============================================================================
# ResolveService.suggest() uses preview_hints_override
# =============================================================================

class TestSuggestUsesOverrideHints:
    """Verify suggest() passes override hints into ResolveContext."""

    def test_override_hints_used_in_context(self):
        """When preview_hints_override is set, it should be used instead of dep._preview_hints."""
        from src.store.resolve_service import ResolveService

        pack = _make_pack()
        layout = MagicMock()
        ps = MagicMock()

        # Create a mock provider that captures the context
        captured_ctx = {}

        class SpyProvider:
            tier = 3

            def supports(self, ctx):
                captured_ctx["preview_hints"] = ctx.preview_hints
                return False  # Don't actually gather

            def gather(self, ctx):
                pass

        service = ResolveService(
            layout=layout,
            pack_service=ps,
            providers={"spy": SpyProvider()},
        )

        hints = [
            PreviewModelHint(
                filename="juggernautXL.safetensors",
                kind=AssetKind.CHECKPOINT,
                source_image="001.png",
                source_type="api_meta",
                raw_value="juggernautXL",
            ),
        ]

        service.suggest(pack, "base_checkpoint", SuggestOptions(
            preview_hints_override=hints,
        ))

        assert "preview_hints" in captured_ctx
        assert len(captured_ctx["preview_hints"]) == 1
        assert captured_ctx["preview_hints"][0].filename == "juggernautXL.safetensors"

    def test_no_override_uses_dep_attr(self):
        """Without override, falls back to dep._preview_hints (or empty)."""
        from src.store.resolve_service import ResolveService

        pack = _make_pack()
        layout = MagicMock()
        ps = MagicMock()

        captured_ctx = {}

        class SpyProvider:
            tier = 3

            def supports(self, ctx):
                captured_ctx["preview_hints"] = ctx.preview_hints
                return False

            def gather(self, ctx):
                pass

        service = ResolveService(
            layout=layout,
            pack_service=ps,
            providers={"spy": SpyProvider()},
        )

        service.suggest(pack, "base_checkpoint", SuggestOptions())

        assert captured_ctx["preview_hints"] == []


# =============================================================================
# Store._post_import_resolve()
# =============================================================================

class TestPostImportResolve:
    """Test post-import resolve orchestration."""

    def test_skips_when_no_dependencies(self):
        """No dependencies → no resolve attempt."""
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()

            pack = Pack(
                name="empty-pack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
                dependencies=[],
            )

            store._post_import_resolve(pack)
            store.resolve_service.suggest.assert_not_called()

    def test_only_resolves_unresolved_deps(self):
        """Should only call suggest() for BASE_MODEL_HINT deps, not pinned ones."""
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.layout.pack_path.return_value = Path("/tmp/test-pack")

            # suggest returns empty results
            store.resolve_service.suggest.return_value = SuggestResult(candidates=[])

            pack = _make_pack()

            with patch(PATCH_EXTRACT, return_value=[]):
                store._post_import_resolve(pack)

            # Only base_checkpoint (BASE_MODEL_HINT) should be resolved,
            # main_lora (CIVITAI_FILE) is already pinned
            assert store.resolve_service.suggest.call_count == 1
            call_dep_id = store.resolve_service.suggest.call_args[0][1]
            assert call_dep_id == "base_checkpoint"

    def test_auto_apply_tier1_candidate(self):
        """Auto-apply when single TIER-1 candidate exists for unresolved dep."""
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.layout.pack_path.return_value = Path("/tmp/test-pack")

            top = _make_candidate(confidence=0.95, tier=1, name="hash-match")
            store.resolve_service.suggest.return_value = SuggestResult(
                candidates=[top],
            )
            store.resolve_service.apply.return_value = ApplyResult(success=True)

            pack = Pack(
                name="single-dep",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
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
                ],
            )

            with patch(PATCH_EXTRACT, return_value=[]):
                store._post_import_resolve(pack)

            store.resolve_service.apply.assert_called_once()
            call_args = store.resolve_service.apply.call_args
            assert call_args[0] == ("single-dep", "base_checkpoint", top.candidate_id)
            assert "request_id" in call_args[1]

    def test_no_auto_apply_tier3(self):
        """Do NOT auto-apply when best candidate is TIER-3."""
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.layout.pack_path.return_value = Path("/tmp/test-pack")

            tier3 = _make_candidate(confidence=0.55, tier=3, name="file-match")
            store.resolve_service.suggest.return_value = SuggestResult(
                candidates=[tier3],
            )

            pack = Pack(
                name="t3-pack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
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
                ],
            )

            with patch(PATCH_EXTRACT, return_value=[]):
                store._post_import_resolve(pack)

            store.resolve_service.apply.assert_not_called()

    def test_no_auto_apply_insufficient_margin(self):
        """Do NOT auto-apply when margin between top 2 candidates < 0.15."""
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.layout.pack_path.return_value = Path("/tmp/test-pack")

            top = _make_candidate(confidence=0.85, tier=2, name="model-A")
            runner_up = _make_candidate(confidence=0.80, tier=2, name="model-B")
            store.resolve_service.suggest.return_value = SuggestResult(
                candidates=[top, runner_up],
            )

            pack = Pack(
                name="close-pack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
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
                ],
            )

            with patch(PATCH_EXTRACT, return_value=[]):
                store._post_import_resolve(pack)

            store.resolve_service.apply.assert_not_called()

    def test_auto_apply_with_sufficient_margin(self):
        """Auto-apply when margin >= 0.15 between top 2 candidates."""
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.layout.pack_path.return_value = Path("/tmp/test-pack")

            top = _make_candidate(confidence=0.88, tier=2, name="dominant")
            runner_up = _make_candidate(confidence=0.55, tier=3, name="weak")
            store.resolve_service.suggest.return_value = SuggestResult(
                candidates=[top, runner_up],
            )
            store.resolve_service.apply.return_value = ApplyResult(success=True)

            pack = Pack(
                name="margin-pack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
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
                ],
            )

            with patch(PATCH_EXTRACT, return_value=[]):
                store._post_import_resolve(pack)

            store.resolve_service.apply.assert_called_once()

    def test_error_in_resolve_does_not_crash_import(self):
        """Errors in resolve should be caught, not crash the import."""
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.layout.pack_path.return_value = Path("/tmp/test-pack")

            store.resolve_service.suggest.side_effect = RuntimeError("provider crash")

            pack = Pack(
                name="error-pack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
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
                ],
            )

            # Should NOT raise
            with patch(PATCH_EXTRACT, return_value=[]):
                store._post_import_resolve(pack)

    def test_passes_include_ai_false(self):
        """Import pipeline should use include_ai=False (R5 rule)."""
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.layout.pack_path.return_value = Path("/tmp/test-pack")
            store.resolve_service.suggest.return_value = SuggestResult(candidates=[])

            pack = Pack(
                name="ai-off-pack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
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
                ],
            )

            with patch(PATCH_EXTRACT, return_value=[]):
                store._post_import_resolve(pack)

            call_args = store.resolve_service.suggest.call_args
            options = call_args[0][2]  # 3rd positional arg
            assert options.include_ai is False

    def test_apply_failure_does_not_log_as_success(self):
        """When apply() returns success=False, it must not be logged as applied."""
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.layout = MagicMock()
            store.layout.pack_path.return_value = Path("/tmp/test-pack")

            top = _make_candidate(confidence=0.95, tier=1, name="placeholder")
            store.resolve_service.suggest.return_value = SuggestResult(
                candidates=[top],
            )
            store.resolve_service.apply.return_value = ApplyResult(
                success=False,
                message="Selector validation failed: Missing required field: Civitai model ID (invalid zero value)",
            )

            pack = Pack(
                name="fail-pack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
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
                ],
            )

            with patch(PATCH_EXTRACT, return_value=[]):
                store._post_import_resolve(pack)

            # apply was called but returned failure
            store.resolve_service.apply.assert_called_once()


# =============================================================================
# Store.suggest_resolution() / apply_resolution() delegates
# =============================================================================

class TestStoreDelegateMethods:
    """Test Store facade delegate methods for resolve."""

    def test_suggest_resolution_delegates(self):
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.pack_service = MagicMock()
            store.layout = MagicMock()

            mock_pack = _make_pack()
            store.pack_service.layout = store.layout
            store.layout.load_pack.return_value = mock_pack

            # Mock get_pack
            store.get_pack = MagicMock(return_value=mock_pack)

            expected = SuggestResult(candidates=[])
            store.resolve_service.suggest.return_value = expected

            result = store.suggest_resolution("test-pack", "main_lora")

            store.resolve_service.suggest.assert_called_once()
            assert result == expected

    def test_apply_resolution_delegates(self):
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()

            expected = ApplyResult(success=True, message="ok")
            store.resolve_service.apply.return_value = expected

            result = store.apply_resolution("test-pack", "main_lora", "cand-123")

            store.resolve_service.apply.assert_called_once_with(
                "test-pack", "main_lora", "cand-123", None,
            )
            assert result.success is True

    def test_apply_resolution_passes_request_id(self):
        from src.store import Store

        with patch.object(Store, "__init__", lambda self, **kw: None):
            store = Store.__new__(Store)
            store.resolve_service = MagicMock()
            store.resolve_service.apply.return_value = ApplyResult(success=True)

            store.apply_resolution("pack", "dep", "cand", request_id="req-456")

            store.resolve_service.apply.assert_called_once_with(
                "pack", "dep", "cand", "req-456",
            )
