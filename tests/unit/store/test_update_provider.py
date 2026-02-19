"""
Tests for UpdateProvider protocol and CivitaiUpdateProvider implementation.

Verifies:
- CivitaiUpdateProvider satisfies the UpdateProvider protocol
- Provider dispatch in UpdateService works correctly
- Provider isolation (each provider handles its own strategy)
"""

import pytest
from unittest.mock import MagicMock

from src.store.civitai_update_provider import CivitaiUpdateProvider
from src.store.models import (
    ArtifactDownload,
    ArtifactIntegrity,
    ArtifactProvider,
    AssetKind,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackDependency,
    PackLock,
    PackSource,
    ProviderName,
    ResolvedArtifact,
    ResolvedDependency,
    SelectorConstraints,
    SelectorStrategy,
    UpdatePolicy,
    UpdatePolicyMode,
)
from src.store.update_provider import UpdateCheckResult, UpdateProvider
from src.store.update_service import UpdateService


class TestUpdateProviderProtocol:
    """Tests for UpdateProvider protocol compliance."""

    def test_civitai_provider_satisfies_protocol(self):
        """CivitaiUpdateProvider should be a valid UpdateProvider."""
        provider = CivitaiUpdateProvider(MagicMock())
        assert isinstance(provider, UpdateProvider)

    def test_protocol_has_required_methods(self):
        """Protocol should define all required methods."""
        provider = CivitaiUpdateProvider(MagicMock())
        assert hasattr(provider, 'check_update')
        assert hasattr(provider, 'build_download_url')
        assert hasattr(provider, 'merge_previews')
        assert hasattr(provider, 'update_description')
        assert hasattr(provider, 'update_model_info')


class TestProviderRegistry:
    """Tests for UpdateService provider registry."""

    def test_register_provider(self):
        """Should be able to register a provider for a strategy."""
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(), view_builder=MagicMock(),
        )
        provider = CivitaiUpdateProvider(MagicMock())
        service.register_provider(SelectorStrategy.CIVITAI_MODEL_LATEST, provider)

        assert service._get_provider(SelectorStrategy.CIVITAI_MODEL_LATEST) is provider

    def test_unknown_strategy_returns_none(self):
        """Unknown strategy should return None, not raise."""
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(), view_builder=MagicMock(),
        )
        assert service._get_provider(SelectorStrategy.HUGGINGFACE_FILE) is None

    def test_is_updatable_requires_registered_provider(self):
        """Pack should only be updatable if its strategy has a registered provider."""
        pack = Pack(
            name="test",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
            dependencies=[
                PackDependency(
                    id="model",
                    kind=AssetKind.CHECKPOINT,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    ),
                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                    expose=ExposeConfig(filename="model.safetensors"),
                ),
            ],
        )

        # Without provider registered
        service_no_provider = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(), view_builder=MagicMock(),
        )
        assert service_no_provider.is_updatable(pack) is False

        # With provider registered
        service_with_provider = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(), view_builder=MagicMock(),
            providers={SelectorStrategy.CIVITAI_MODEL_LATEST: CivitaiUpdateProvider(MagicMock())},
        )
        assert service_with_provider.is_updatable(pack) is True

    def test_plan_skips_deps_without_provider(self):
        """plan_update should skip dependencies without a registered provider."""
        pack = Pack(
            name="test",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.HUGGINGFACE),
            dependencies=[
                PackDependency(
                    id="hf-model",
                    kind=AssetKind.CHECKPOINT,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.HUGGINGFACE_FILE,
                        huggingface={"repo_id": "org/model", "filename": "model.safetensors"},
                    ),
                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                    expose=ExposeConfig(filename="model.safetensors"),
                ),
            ],
        )
        lock = PackLock(
            pack="test",
            resolved=[
                ResolvedDependency(
                    dependency_id="hf-model",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.CHECKPOINT,
                        sha256="abc",
                        provider=ArtifactProvider(
                            name=ProviderName.HUGGINGFACE,
                            repo_id="org/model",
                        ),
                    ),
                ),
            ],
        )

        mock_layout = MagicMock()
        mock_layout.load_pack.return_value = pack
        mock_layout.load_pack_lock.return_value = lock
        mock_layout.list_packs.return_value = ["test"]

        # Only Civitai provider registered - HF dep should be skipped
        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(), view_builder=MagicMock(),
            providers={SelectorStrategy.CIVITAI_MODEL_LATEST: CivitaiUpdateProvider(MagicMock())},
        )

        plan = service.plan_update("test")
        assert plan.already_up_to_date is True
        assert len(plan.changes) == 0


class TestCivitaiProviderCheckUpdate:
    """Tests for CivitaiUpdateProvider.check_update()."""

    def _make_dep(self, model_id=123):
        return PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                civitai={"model_id": model_id},
                constraints=SelectorConstraints(primary_file_only=True),
            ),
            update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
            expose=ExposeConfig(filename="model.safetensors"),
        )

    def _make_current(self, version_id=100, file_id=1000):
        return ResolvedDependency(
            dependency_id="model",
            artifact=ResolvedArtifact(
                kind=AssetKind.CHECKPOINT,
                sha256="old_hash",
                provider=ArtifactProvider(
                    name=ProviderName.CIVITAI,
                    model_id=123,
                    version_id=version_id,
                    file_id=file_id,
                ),
            ),
        )

    def test_detects_update(self):
        """Should detect when Civitai has a newer version."""
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 200,
                "files": [{
                    "id": 2000, "primary": True, "name": "model.safetensors",
                    "hashes": {"SHA256": "NEWHASH"}, "sizeKB": 1024,
                }],
            }],
        }
        provider = CivitaiUpdateProvider(mock_civitai)

        result = provider.check_update(self._make_dep(), self._make_current())
        assert result is not None
        assert result.has_update is True
        assert result.version_id == 200
        assert result.sha256 == "newhash"

    def test_up_to_date(self):
        """Should report no update when on latest."""
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{"id": 100, "files": []}],
        }
        provider = CivitaiUpdateProvider(mock_civitai)

        result = provider.check_update(self._make_dep(), self._make_current())
        assert result is not None
        assert result.has_update is False

    def test_no_civitai_selector_returns_none(self):
        """Dep without civitai selector should return None."""
        dep = PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(strategy=SelectorStrategy.LOCAL_FILE),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        provider = CivitaiUpdateProvider(MagicMock())

        result = provider.check_update(dep, self._make_current())
        assert result is None

    def test_ambiguous_multiple_files(self):
        """Multiple matching files should produce ambiguous result."""
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 200,
                "files": [
                    {"id": 2001, "primary": True, "name": "model-fp16.safetensors",
                     "hashes": {"SHA256": "HASH1"}},
                    {"id": 2002, "primary": True, "name": "model-fp32.safetensors",
                     "hashes": {"SHA256": "HASH2"}},
                ],
            }],
        }
        # No constraints that would filter to single file
        dep = PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                civitai={"model_id": 123},
            ),
            update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        provider = CivitaiUpdateProvider(mock_civitai)

        result = provider.check_update(dep, self._make_current())
        assert result is not None
        assert result.ambiguous is True
        assert len(result.candidates) == 2


class TestCivitaiProviderBuildDownloadUrl:
    """Tests for CivitaiUpdateProvider.build_download_url()."""

    def test_basic_url(self):
        provider = CivitaiUpdateProvider(MagicMock())
        url = provider.build_download_url(200, None)
        assert url == "https://civitai.com/api/download/models/200"

    def test_url_with_file_id(self):
        provider = CivitaiUpdateProvider(MagicMock())
        url = provider.build_download_url(200, 2000)
        assert "type=Model" in url
        assert "models/200" in url

    def test_url_format(self):
        provider = CivitaiUpdateProvider(MagicMock())
        url = provider.build_download_url(300, 3000)
        assert url == "https://civitai.com/api/download/models/300?type=Model&format=SafeTensor"
