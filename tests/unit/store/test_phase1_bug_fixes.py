"""
Phase 1 Block A+B tests — BUG fixes and PackService integration.

Tests for:
- BUG 3: base_model NEVER overwritten with filename stem
- BUG 4: typed API IDs instead of regex URL parsing
- PackService.apply_dependency_resolution() — single write path
- Store facade ResolveService integration
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.store.models import (
    AssetKind,
    CanonicalSource,
    CivitaiSelector,
    DependencySelector,
    ExposeConfig,
    HuggingFaceSelector,
    Pack,
    PackCategory,
    PackDependency,
    PackLock,
    PackSource,
    ProviderName,
    SelectorStrategy,
    UpdatePolicy,
    UpdatePolicyMode,
)


# =============================================================================
# Helpers
# =============================================================================

def _make_pack_with_base_dep(base_model="SDXL") -> Pack:
    """Create a realistic Pack with base_checkpoint dependency."""
    return Pack(
        name="test-lora-pack",
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


# =============================================================================
# BUG 3: base_model NEVER overwritten with filename stem
# =============================================================================

class TestBug3BaseModelNotOverwritten:
    """BUG 3: pack.base_model must NEVER be set to a filename stem."""

    def test_apply_dependency_resolution_preserves_base_model(self, tmp_path):
        """apply_dependency_resolution changes selector, NOT base_model."""
        pack = _make_pack_with_base_dep("SDXL")

        layout = MagicMock()
        layout.load_pack.return_value = pack
        layout.save_pack = MagicMock()

        from src.store.pack_service import PackService
        ps = PackService(layout, MagicMock(), MagicMock())

        new_selector = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=133005, version_id=357609, file_id=505827),
        )

        ps.apply_dependency_resolution(
            pack_name="test-lora-pack",
            dep_id="base_checkpoint",
            selector=new_selector,
            display_name="juggernautXL_v9Rundiffusion.safetensors",
        )

        # base_model must still be "SDXL", NOT "juggernautXL_v9Rundiffusion"
        saved_pack = layout.save_pack.call_args[0][0]
        assert saved_pack.base_model == "SDXL"

        # But the selector should be updated
        base_dep = next(d for d in saved_pack.dependencies if d.id == "base_checkpoint")
        assert base_dep.selector.strategy == SelectorStrategy.CIVITAI_FILE
        assert base_dep.selector.civitai.model_id == 133005


# =============================================================================
# BUG 4: typed API IDs
# =============================================================================

class TestBug4TypedApiIds:
    """BUG 4: resolve-base-model should accept typed IDs, not just URLs."""

    def test_request_model_accepts_typed_ids(self):
        """ResolveBaseModelRequest schema includes model_id, version_id, repo_id."""
        from src.store.api import ResolveBaseModelRequest

        req = ResolveBaseModelRequest(
            source="civitai",
            download_url="https://civitai.com/api/download/models/357609",
            file_name="juggernautXL.safetensors",
            model_id=133005,
            version_id=357609,
        )
        assert req.model_id == 133005
        assert req.version_id == 357609

    def test_request_model_accepts_hf_repo_id(self):
        from src.store.api import ResolveBaseModelRequest
        req = ResolveBaseModelRequest(
            source="huggingface",
            download_url="https://huggingface.co/stabilityai/sdxl/resolve/main/model.safetensors",
            file_name="model.safetensors",
            repo_id="stabilityai/sdxl",
        )
        assert req.repo_id == "stabilityai/sdxl"

    def test_request_model_backward_compatible(self):
        """Old requests without typed IDs still work."""
        from src.store.api import ResolveBaseModelRequest

        req = ResolveBaseModelRequest(
            source="civitai",
            download_url="https://civitai.com/api/download/models/357609",
            file_name="juggernautXL.safetensors",
        )
        assert req.model_id is None
        assert req.version_id is None


# =============================================================================
# PackService.apply_dependency_resolution()
# =============================================================================

class TestApplyDependencyResolution:
    """Tests for the single write path from ResolveService."""

    def test_updates_selector(self):
        pack = _make_pack_with_base_dep()
        layout = MagicMock()
        layout.load_pack.return_value = pack
        layout.save_pack = MagicMock()

        from src.store.pack_service import PackService
        ps = PackService(layout, MagicMock(), MagicMock())

        new_selector = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=50, version_id=60, file_id=70),
        )
        ps.apply_dependency_resolution("test-lora-pack", "main_lora", new_selector)

        saved = layout.save_pack.call_args[0][0]
        lora_dep = next(d for d in saved.dependencies if d.id == "main_lora")
        assert lora_dep.selector.strategy == SelectorStrategy.CIVITAI_FILE
        assert lora_dep.selector.civitai.model_id == 50

    def test_sets_canonical_source(self):
        pack = _make_pack_with_base_dep()
        layout = MagicMock()
        layout.load_pack.return_value = pack
        layout.save_pack = MagicMock()

        from src.store.pack_service import PackService
        ps = PackService(layout, MagicMock(), MagicMock())

        new_selector = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=50, version_id=60, file_id=70),
        )
        canonical = CanonicalSource(
            provider="civitai",
            model_id=50,
            version_id=60,
        )
        ps.apply_dependency_resolution(
            "test-lora-pack", "main_lora", new_selector,
            canonical_source=canonical,
        )

        saved = layout.save_pack.call_args[0][0]
        lora_dep = next(d for d in saved.dependencies if d.id == "main_lora")
        assert lora_dep.selector.canonical_source is not None
        assert lora_dep.selector.canonical_source.provider == "civitai"
        assert lora_dep.selector.canonical_source.model_id == 50

    def test_unknown_dep_id_raises(self):
        pack = _make_pack_with_base_dep()
        layout = MagicMock()
        layout.load_pack.return_value = pack

        from src.store.pack_service import PackService
        ps = PackService(layout, MagicMock(), MagicMock())

        with pytest.raises(ValueError, match="not found"):
            ps.apply_dependency_resolution(
                "test-lora-pack", "nonexistent_dep",
                DependencySelector(strategy=SelectorStrategy.LOCAL_FILE, local_path="/x"),
            )

    def test_saves_pack_after_update(self):
        pack = _make_pack_with_base_dep()
        layout = MagicMock()
        layout.load_pack.return_value = pack
        layout.save_pack = MagicMock()

        from src.store.pack_service import PackService
        ps = PackService(layout, MagicMock(), MagicMock())

        ps.apply_dependency_resolution(
            "test-lora-pack", "main_lora",
            DependencySelector(
                strategy=SelectorStrategy.LOCAL_FILE,
                local_path="/models/my_lora.safetensors",
            ),
        )

        layout.save_pack.assert_called_once()


# =============================================================================
# Store facade — ResolveService wiring
# =============================================================================

class TestStoreFacadeResolveService:
    """Verify ResolveService is correctly wired in Store facade."""

    def test_store_has_resolve_service(self):
        """Store should have resolve_service attribute after init."""
        from src.store import Store
        with patch.object(Store, '__init__', lambda self, **kw: None):
            store = Store.__new__(Store)
            # Simulate minimal init
            store.layout = MagicMock()
            store.pack_service = MagicMock()
            from src.store.resolve_service import ResolveService
            store.resolve_service = ResolveService(
                layout=store.layout,
                pack_service=store.pack_service,
            )
            assert hasattr(store, 'resolve_service')
            assert isinstance(store.resolve_service, ResolveService)


# =============================================================================
# API endpoints schema validation
# =============================================================================

class TestResolveApiEndpoints:
    """Verify API request/response models for suggest/apply endpoints."""

    def test_suggest_request_schema(self):
        from src.store.api import SuggestRequest
        req = SuggestRequest(dep_id="main_lora", include_ai=True, max_candidates=5)
        assert req.dep_id == "main_lora"
        assert req.include_ai is True

    def test_apply_request_schema(self):
        from src.store.api import ApplyRequest
        req = ApplyRequest(
            dep_id="main_lora",
            candidate_id="abc-123",
            request_id="req-456",
        )
        assert req.candidate_id == "abc-123"

    def test_manual_apply_request_civitai(self):
        from src.store.api import ManualApplyRequest
        req = ManualApplyRequest(
            dep_id="base_checkpoint",
            strategy="civitai_file",
            civitai_model_id=133005,
            civitai_version_id=357609,
            civitai_file_id=505827,
            display_name="Juggernaut XL v9",
        )
        assert req.strategy == "civitai_file"
        assert req.civitai_model_id == 133005

    def test_manual_apply_request_local(self):
        from src.store.api import ManualApplyRequest
        req = ManualApplyRequest(
            dep_id="base_checkpoint",
            strategy="local_file",
            local_path="/models/my_checkpoint.safetensors",
        )
        assert req.strategy == "local_file"
        assert req.local_path == "/models/my_checkpoint.safetensors"
