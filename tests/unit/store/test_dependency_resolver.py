"""
Tests for DependencyResolver protocol and implementations.

Verifies:
- Each resolver implementation satisfies the DependencyResolver protocol
- Registry dispatch in PackService works correctly
- Resolver isolation (each resolver handles its own strategy)
- Civitai, HuggingFace, URL, and Local file resolvers
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.store.dependency_resolver import (
    CivitaiFileResolver,
    CivitaiLatestResolver,
    BaseModelHintResolver,
    DependencyResolver,
    HuggingFaceResolver,
    LocalFileResolver,
    UrlResolver,
)
from src.store.models import (
    AssetKind,
    CivitaiSelector,
    DependencySelector,
    ExposeConfig,
    HuggingFaceSelector,
    PackDependency,
    ProviderName,
    SelectorConstraints,
    SelectorStrategy,
)


class TestDependencyResolverProtocol:
    """Tests for DependencyResolver protocol compliance."""

    def test_civitai_file_satisfies_protocol(self):
        resolver = CivitaiFileResolver(MagicMock())
        assert isinstance(resolver, DependencyResolver)

    def test_civitai_latest_satisfies_protocol(self):
        resolver = CivitaiLatestResolver(MagicMock())
        assert isinstance(resolver, DependencyResolver)

    def test_base_model_hint_satisfies_protocol(self):
        resolver = BaseModelHintResolver(MagicMock(), MagicMock())
        assert isinstance(resolver, DependencyResolver)

    def test_huggingface_satisfies_protocol(self):
        resolver = HuggingFaceResolver()
        assert isinstance(resolver, DependencyResolver)

    def test_url_satisfies_protocol(self):
        resolver = UrlResolver()
        assert isinstance(resolver, DependencyResolver)

    def test_local_file_satisfies_protocol(self):
        resolver = LocalFileResolver()
        assert isinstance(resolver, DependencyResolver)


class TestCivitaiFileResolver:
    """Tests for CivitaiFileResolver."""

    def _make_dep(self, version_id=100, file_id=1000):
        return PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai={"model_id": 123, "version_id": version_id, "file_id": file_id},
            ),
            expose=ExposeConfig(filename="model.safetensors"),
        )

    def test_resolves_pinned_file(self):
        mock_civitai = MagicMock()
        mock_civitai.get_model_version.return_value = {
            "files": [{
                "id": 1000, "primary": True, "name": "model.safetensors",
                "hashes": {"SHA256": "ABCDEF"},
                "sizeKB": 2048,
                "downloadUrl": "https://civitai.com/api/download/models/100",
            }],
        }
        resolver = CivitaiFileResolver(mock_civitai)
        result = resolver.resolve(self._make_dep())

        assert result is not None
        assert result.sha256 == "abcdef"
        assert result.provider.version_id == 100
        assert result.provider.file_id == 1000
        assert result.provider.name == ProviderName.CIVITAI

    def test_returns_none_without_civitai_selector(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = CivitaiFileResolver(MagicMock())
        assert resolver.resolve(dep) is None

    def test_returns_none_without_version_id(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai={"model_id": 123},
            ),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = CivitaiFileResolver(MagicMock())
        assert resolver.resolve(dep) is None


class TestCivitaiLatestResolver:
    """Tests for CivitaiLatestResolver."""

    def _make_dep(self, model_id=123):
        return PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                civitai={"model_id": model_id},
                constraints=SelectorConstraints(primary_file_only=True),
            ),
            expose=ExposeConfig(filename="model.safetensors"),
        )

    def test_resolves_latest_version(self):
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 200,
                "files": [{
                    "id": 2000, "primary": True, "name": "model.safetensors",
                    "hashes": {"SHA256": "NEWHASH"},
                    "sizeKB": 4096,
                    "downloadUrl": "https://civitai.com/api/download/models/200",
                }],
            }],
        }
        resolver = CivitaiLatestResolver(mock_civitai)
        result = resolver.resolve(self._make_dep())

        assert result is not None
        assert result.provider.version_id == 200
        assert result.sha256 == "newhash"

    def test_resolves_pinned_version_not_latest(self):
        """Critical regression test: when version_id is pinned, resolver MUST
        use get_model_version(version_id) and NOT blindly take versions[0].

        This was the root cause of all bundle pack downloads failing —
        multiple dependencies share the same model_id but have different
        version_ids. The old code always took versions[0] (latest), which
        could be gated/early-access, causing all downloads to fail.
        """
        mock_civitai = MagicMock()

        # get_model returns LATEST as versions[0] (id=999, gated)
        mock_civitai.get_model.return_value = {
            "modelVersions": [
                {
                    "id": 999,
                    "files": [{
                        "id": 9000, "primary": True, "name": "latest.safetensors",
                        "hashes": {"SHA256": "LATESTHASH"},
                        "downloadUrl": "https://civitai.com/api/download/models/999",
                    }],
                },
                {
                    "id": 200,
                    "files": [{
                        "id": 2000, "primary": True, "name": "pinned.safetensors",
                        "hashes": {"SHA256": "PINNEDHASH"},
                        "downloadUrl": "https://civitai.com/api/download/models/200",
                    }],
                },
            ],
        }

        # get_model_version returns the PINNED version data
        mock_civitai.get_model_version.return_value = {
            "id": 200,
            "files": [{
                "id": 2000, "primary": True, "name": "pinned.safetensors",
                "hashes": {"SHA256": "PINNEDHASH"},
                "downloadUrl": "https://civitai.com/api/download/models/200",
            }],
        }

        # Dependency has version_id=200 pinned
        dep = PackDependency(
            id="lora_v2",
            kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                civitai={"model_id": 123, "version_id": 200},
                constraints=SelectorConstraints(primary_file_only=True),
            ),
            expose=ExposeConfig(filename="pinned.safetensors"),
        )

        resolver = CivitaiLatestResolver(mock_civitai)
        result = resolver.resolve(dep)

        assert result is not None
        # Must resolve to pinned version 200, NOT latest 999
        assert result.provider.version_id == 200
        assert result.sha256 == "pinnedhash"
        assert "models/200" in result.download.urls[0]

        # Must call get_model_version, NOT get_model
        mock_civitai.get_model_version.assert_called_once_with(200)
        mock_civitai.get_model.assert_not_called()

    def test_multi_version_bundle_resolves_each_version(self):
        """Simulate a bundle pack with 6 LoRAs from the same model but
        different version_ids. Each must resolve to its own version.
        """
        mock_civitai = MagicMock()

        version_ids = [100, 200, 300, 400, 500, 600]

        def fake_get_model_version(vid):
            return {
                "id": vid,
                "files": [{
                    "id": vid * 10, "primary": True,
                    "name": f"lora_v{vid}.safetensors",
                    "hashes": {"SHA256": f"HASH{vid}"},
                    "downloadUrl": f"https://civitai.com/api/download/models/{vid}",
                }],
            }

        mock_civitai.get_model_version.side_effect = fake_get_model_version

        resolver = CivitaiLatestResolver(mock_civitai)

        for vid in version_ids:
            dep = PackDependency(
                id=f"lora_{vid}",
                kind=AssetKind.LORA,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai={"model_id": 42, "version_id": vid},
                ),
                expose=ExposeConfig(filename=f"lora_{vid}.safetensors"),
            )
            result = resolver.resolve(dep)
            assert result is not None
            assert result.provider.version_id == vid
            assert f"models/{vid}" in result.download.urls[0]
            assert result.sha256 == f"hash{vid}"

        # Should have called get_model_version 6 times, get_model 0 times
        assert mock_civitai.get_model_version.call_count == 6
        mock_civitai.get_model.assert_not_called()

    def test_pinned_version_with_file_id(self):
        """When both version_id and file_id are set, resolver should pick
        the exact file matching file_id.
        """
        mock_civitai = MagicMock()
        mock_civitai.get_model_version.return_value = {
            "id": 200,
            "files": [
                {"id": 2001, "name": "pruned.safetensors", "hashes": {"SHA256": "PRUNED"}},
                {"id": 2002, "name": "full.safetensors", "hashes": {"SHA256": "FULL"}},
            ],
        }

        dep = PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                civitai={"model_id": 123, "version_id": 200, "file_id": 2002},
            ),
            expose=ExposeConfig(filename="full.safetensors"),
        )

        resolver = CivitaiLatestResolver(mock_civitai)
        result = resolver.resolve(dep)

        assert result is not None
        assert result.provider.file_id == 2002
        assert result.sha256 == "full"

    def test_returns_none_for_empty_versions(self):
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {"modelVersions": []}
        resolver = CivitaiLatestResolver(mock_civitai)
        assert resolver.resolve(self._make_dep()) is None

    def test_returns_none_without_civitai_selector(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_MODEL_LATEST),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = CivitaiLatestResolver(MagicMock())
        assert resolver.resolve(dep) is None


class TestBaseModelHintResolver:
    """Tests for BaseModelHintResolver constraint handling."""

    def test_uses_select_file_with_constraints(self):
        """BaseModelHintResolver should use _select_file() with constraints,
        not just take files[0].
        """
        mock_civitai = MagicMock()
        mock_civitai.get_model_version.return_value = {
            "id": 300,
            "files": [
                {"id": 3001, "name": "model.ckpt", "primary": False, "hashes": {"SHA256": "CKPT"}},
                {"id": 3002, "name": "model.safetensors", "primary": True, "hashes": {"SHA256": "SAFE"}},
            ],
        }

        mock_layout = MagicMock()
        mock_config = MagicMock()
        mock_alias = MagicMock()
        mock_alias.selector.civitai.model_id = 10
        mock_alias.selector.civitai.version_id = 300
        mock_alias.selector.civitai.file_id = None
        mock_config.base_model_aliases.get.return_value = mock_alias
        mock_layout.load_config.return_value = mock_config

        dep = PackDependency(
            id="base_checkpoint",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(
                strategy=SelectorStrategy.BASE_MODEL_HINT,
                base_model="SDXL",
                constraints=SelectorConstraints(primary_file_only=True),
            ),
            expose=ExposeConfig(filename="sdxl.safetensors"),
        )

        resolver = BaseModelHintResolver(mock_civitai, mock_layout)
        result = resolver.resolve(dep)

        assert result is not None
        # Should prefer primary file via _select_file, not just files[0]
        assert result.provider.file_id == 3002
        assert result.sha256 == "safe"


class TestHuggingFaceResolver:
    """Tests for HuggingFaceResolver."""

    def test_resolves_hf_file(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(
                strategy=SelectorStrategy.HUGGINGFACE_FILE,
                huggingface={"repo_id": "org/model", "filename": "model.safetensors"},
            ),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = HuggingFaceResolver()
        result = resolver.resolve(dep)

        assert result is not None
        assert result.provider.name == ProviderName.HUGGINGFACE
        assert result.provider.repo_id == "org/model"
        assert "huggingface.co/org/model" in result.download.urls[0]
        assert result.download.urls[0].endswith("/model.safetensors")

    def test_resolves_hf_with_subfolder_and_revision(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(
                strategy=SelectorStrategy.HUGGINGFACE_FILE,
                huggingface={
                    "repo_id": "org/model",
                    "filename": "weights.bin",
                    "subfolder": "pytorch",
                    "revision": "v1.0",
                },
            ),
            expose=ExposeConfig(filename="weights.bin"),
        )
        resolver = HuggingFaceResolver()
        result = resolver.resolve(dep)

        assert result is not None
        url = result.download.urls[0]
        assert "/resolve/v1.0/" in url
        assert "/pytorch/" in url
        assert url.endswith("/weights.bin")

    def test_returns_none_without_hf_selector(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.CHECKPOINT,
            selector=DependencySelector(strategy=SelectorStrategy.HUGGINGFACE_FILE),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = HuggingFaceResolver()
        assert resolver.resolve(dep) is None


class TestUrlResolver:
    """Tests for UrlResolver."""

    def test_resolves_url(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.URL_DOWNLOAD,
                url="https://example.com/model.safetensors",
            ),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = UrlResolver()
        result = resolver.resolve(dep)

        assert result is not None
        assert result.provider.name == ProviderName.URL
        assert result.download.urls[0] == "https://example.com/model.safetensors"
        assert result.integrity.sha256_verified is False

    def test_returns_none_without_url(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.LORA,
            selector=DependencySelector(strategy=SelectorStrategy.URL_DOWNLOAD),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = UrlResolver()
        assert resolver.resolve(dep) is None


class TestLocalFileResolver:
    """Tests for LocalFileResolver."""

    def test_resolves_existing_file(self, tmp_path):
        test_file = tmp_path / "model.safetensors"
        test_file.write_bytes(b"fake model content")

        dep = PackDependency(
            id="model",
            kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.LOCAL_FILE,
                local_path=str(test_file),
            ),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = LocalFileResolver()
        result = resolver.resolve(dep)

        assert result is not None
        assert result.provider.name == ProviderName.LOCAL
        assert result.sha256 is not None
        assert result.integrity.sha256_verified is True
        assert result.size_bytes == len(b"fake model content")

    def test_returns_none_for_missing_file(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.LOCAL_FILE,
                local_path="/nonexistent/path/model.safetensors",
            ),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = LocalFileResolver()
        assert resolver.resolve(dep) is None

    def test_returns_none_without_local_path(self):
        dep = PackDependency(
            id="model",
            kind=AssetKind.LORA,
            selector=DependencySelector(strategy=SelectorStrategy.LOCAL_FILE),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        resolver = LocalFileResolver()
        assert resolver.resolve(dep) is None


class TestPackServiceResolverRegistry:
    """Tests for PackService resolver dispatch via registry."""

    def test_pack_service_uses_registry(self):
        """PackService should dispatch to registered resolvers."""
        from src.store.pack_service import PackService

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = None

        service = PackService(
            layout=MagicMock(),
            blob_store=MagicMock(),
            resolvers={SelectorStrategy.URL_DOWNLOAD: mock_resolver},
        )

        dep = PackDependency(
            id="test",
            kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.URL_DOWNLOAD,
                url="https://example.com/model.bin",
            ),
            expose=ExposeConfig(filename="model.bin"),
        )

        result = service._resolve_dependency(MagicMock(), dep, None)
        mock_resolver.resolve.assert_called_once_with(dep)

    def test_pack_service_returns_none_for_unknown_strategy(self):
        """Unknown strategy without resolver should return None."""
        from src.store.pack_service import PackService

        service = PackService(
            layout=MagicMock(),
            blob_store=MagicMock(),
            resolvers={SelectorStrategy.URL_DOWNLOAD: MagicMock()},
        )

        dep = PackDependency(
            id="test",
            kind=AssetKind.LORA,
            selector=DependencySelector(strategy=SelectorStrategy.HUGGINGFACE_FILE,
                                        huggingface={"repo_id": "x/y", "filename": "z"}),
            expose=ExposeConfig(filename="model.bin"),
        )

        result = service._resolve_dependency(MagicMock(), dep, None)
        assert result is None

    def test_pack_service_lazy_init_resolvers(self):
        """PackService should lazily init default resolvers when none provided."""
        from src.store.pack_service import PackService

        mock_civitai = MagicMock()
        mock_civitai.get_model_version.return_value = {
            "files": [{
                "id": 1, "name": "model.safetensors",
                "hashes": {"SHA256": "abc"},
                "downloadUrl": "https://civitai.com/api/download/models/100",
            }],
        }

        service = PackService(
            layout=MagicMock(),
            blob_store=MagicMock(),
            civitai_client=mock_civitai,
        )

        dep = PackDependency(
            id="test",
            kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai={"model_id": 1, "version_id": 100, "file_id": 1},
            ),
            expose=ExposeConfig(filename="model.safetensors"),
        )

        result = service._resolve_dependency(MagicMock(), dep, None)
        assert result is not None
        assert result.provider.name == ProviderName.CIVITAI
