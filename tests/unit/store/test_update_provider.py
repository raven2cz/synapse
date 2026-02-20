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
    UpdateChange,
    UpdatePlan,
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


class TestCivitaiProviderSameVersionUrl:
    """Tests for check_update returning download_url when version matches (pending downloads)."""

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

    def _make_current(self, version_id=100, file_id=1000, filename=None):
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
                    filename=filename,
                ),
            ),
        )

    def test_same_version_returns_download_url(self):
        """When version matches, should still return download_url for pending downloads."""
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 100,
                "files": [{
                    "id": 1000, "primary": True, "name": "model.safetensors",
                    "hashes": {"SHA256": "ABCDEF"}, "sizeKB": 512,
                    "downloadUrl": "https://civitai.com/api/download/models/100?id=1000",
                }],
            }],
        }
        provider = CivitaiUpdateProvider(mock_civitai)

        result = provider.check_update(
            self._make_dep(),
            self._make_current(version_id=100, file_id=1000, filename="model.safetensors"),
        )
        assert result is not None
        assert result.has_update is False
        assert result.download_url is not None
        assert "id=1000" in result.download_url
        assert result.file_id == 1000

    def test_same_version_multi_file_matches_correct_file(self):
        """For multi-file packs, same-version check should match correct file by name."""
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 100,
                "files": [
                    {"id": 1001, "name": "lora_a.safetensors",
                     "hashes": {"SHA256": "HASH_A"}},
                    {"id": 1002, "name": "lora_b.safetensors",
                     "hashes": {"SHA256": "HASH_B"}},
                    {"id": 1003, "name": "lora_c.safetensors",
                     "hashes": {"SHA256": "HASH_C"}},
                ],
            }],
        }
        provider = CivitaiUpdateProvider(mock_civitai)

        # Each dep should match its own file
        for fname, expected_id in [("lora_a.safetensors", 1001), ("lora_b.safetensors", 1002), ("lora_c.safetensors", 1003)]:
            result = provider.check_update(
                self._make_dep(),
                self._make_current(version_id=100, filename=fname),
            )
            assert result is not None
            assert result.has_update is False
            assert result.file_id == expected_id, f"Expected file_id {expected_id} for {fname}, got {result.file_id}"

    def test_same_version_no_files_returns_no_url(self):
        """When version matches but no files found, download_url should be None."""
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{"id": 100, "files": []}],
        }
        provider = CivitaiUpdateProvider(mock_civitai)

        result = provider.check_update(self._make_dep(), self._make_current())
        assert result is not None
        assert result.has_update is False
        assert result.download_url is None


class TestMultiFileMatching:
    """Tests for _match_file_for_dep - multi-file version matching."""

    def _make_current(self, filename):
        return ResolvedDependency(
            dependency_id="model",
            artifact=ResolvedArtifact(
                kind=AssetKind.CHECKPOINT,
                sha256="hash",
                provider=ArtifactProvider(
                    name=ProviderName.CIVITAI,
                    model_id=123,
                    version_id=100,
                    filename=filename,
                ),
            ),
        )

    def test_exact_filename_match(self):
        """Should match file by exact name."""
        files = [
            {"id": 1, "name": "model_a.safetensors"},
            {"id": 2, "name": "model_b.safetensors"},
        ]
        dep = MagicMock()
        current = self._make_current("model_b.safetensors")

        result = CivitaiUpdateProvider._match_file_for_dep(files, dep, current)
        assert result is not None
        assert result["id"] == 2

    def test_case_insensitive_match(self):
        """Should match case-insensitively."""
        files = [{"id": 1, "name": "Model.safetensors"}]
        current = self._make_current("model.safetensors")

        result = CivitaiUpdateProvider._match_file_for_dep(files, MagicMock(), current)
        assert result is not None
        assert result["id"] == 1

    def test_version_suffix_match(self):
        """Should match when version suffix changes (V1 -> V2)."""
        files = [{"id": 2, "name": "LoraV2.safetensors"}]
        current = self._make_current("LoraV1.safetensors")

        result = CivitaiUpdateProvider._match_file_for_dep(files, MagicMock(), current)
        assert result is not None
        assert result["id"] == 2

    def test_no_filename_returns_none(self):
        """No filename in lock should return None."""
        files = [{"id": 1, "name": "model.safetensors"}]
        current = self._make_current(None)

        result = CivitaiUpdateProvider._match_file_for_dep(files, MagicMock(), current)
        assert result is None


class TestPendingDownloads:
    """Tests for pending download detection in plan_update."""

    def test_missing_blob_detected_as_pending(self):
        """Deps with updated lock but missing blob should appear as pending downloads."""
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
                        civitai={"model_id": 123},
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
                    dependency_id="model",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.CHECKPOINT,
                        sha256="abc123",
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=123,
                            version_id=200,
                            file_id=2000,
                            filename="model.safetensors",
                        ),
                    ),
                ),
            ],
        )

        mock_layout = MagicMock()
        mock_layout.load_pack.return_value = pack
        mock_layout.load_pack_lock.return_value = lock
        mock_layout.list_packs.return_value = ["test"]

        mock_blob = MagicMock()
        mock_blob.blob_exists.return_value = False  # Blob missing!

        # Provider says "up to date" (version matches) but returns download_url
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 200,
                "files": [{
                    "id": 2000, "name": "model.safetensors",
                    "hashes": {"SHA256": "ABC123"},
                    "downloadUrl": "https://civitai.com/api/download/models/200?id=2000",
                }],
            }],
        }

        provider = CivitaiUpdateProvider(mock_civitai)
        service = UpdateService(
            layout=mock_layout, blob_store=mock_blob, view_builder=MagicMock(),
            providers={SelectorStrategy.CIVITAI_MODEL_LATEST: provider},
        )

        plan = service.plan_update("test")
        assert plan.already_up_to_date is False
        assert len(plan.pending_downloads) == 1
        assert plan.pending_downloads[0].dependency_id == "model"
        assert plan.pending_downloads[0].sha256 == "abc123"
        assert "id=2000" in plan.pending_downloads[0].download_url

    def test_existing_blob_not_pending(self):
        """Deps with existing blobs should not appear as pending."""
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
                        civitai={"model_id": 123},
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
                    dependency_id="model",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.CHECKPOINT,
                        sha256="abc123",
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=123,
                            version_id=200,
                            file_id=2000,
                        ),
                    ),
                ),
            ],
        )

        mock_layout = MagicMock()
        mock_layout.load_pack.return_value = pack
        mock_layout.load_pack_lock.return_value = lock
        mock_layout.list_packs.return_value = ["test"]

        mock_blob = MagicMock()
        mock_blob.blob_exists.return_value = True  # Blob exists!

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{"id": 200, "files": []}],
        }

        provider = CivitaiUpdateProvider(mock_civitai)
        service = UpdateService(
            layout=mock_layout, blob_store=mock_blob, view_builder=MagicMock(),
            providers={SelectorStrategy.CIVITAI_MODEL_LATEST: provider},
        )

        plan = service.plan_update("test")
        assert plan.already_up_to_date is True
        assert len(plan.pending_downloads) == 0

    def test_multi_file_pending_gets_correct_urls(self):
        """Each dep in multi-file pack should get its own correct download URL."""
        pack = Pack(
            name="monster",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=456),
            dependencies=[
                PackDependency(
                    id="lora_a",
                    kind=AssetKind.LORA,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                        civitai={"model_id": 456},
                    ),
                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                    expose=ExposeConfig(filename="lora_a.safetensors"),
                ),
                PackDependency(
                    id="lora_b",
                    kind=AssetKind.LORA,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                        civitai={"model_id": 456},
                    ),
                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                    expose=ExposeConfig(filename="lora_b.safetensors"),
                ),
            ],
        )
        lock = PackLock(
            pack="monster",
            resolved=[
                ResolvedDependency(
                    dependency_id="lora_a",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.LORA,
                        sha256="hash_a",
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=456,
                            version_id=300,
                            file_id=3001,
                            filename="lora_a.safetensors",
                        ),
                    ),
                ),
                ResolvedDependency(
                    dependency_id="lora_b",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.LORA,
                        sha256="hash_b",
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=456,
                            version_id=300,
                            file_id=3002,
                            filename="lora_b.safetensors",
                        ),
                    ),
                ),
            ],
        )

        mock_layout = MagicMock()
        mock_layout.load_pack.return_value = pack
        mock_layout.load_pack_lock.return_value = lock
        mock_layout.list_packs.return_value = ["monster"]

        mock_blob = MagicMock()
        mock_blob.blob_exists.return_value = False  # Both blobs missing

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 300,
                "files": [
                    {"id": 3001, "name": "lora_a.safetensors",
                     "hashes": {"SHA256": "HASH_A"}},
                    {"id": 3002, "name": "lora_b.safetensors",
                     "hashes": {"SHA256": "HASH_B"}},
                ],
            }],
        }

        provider = CivitaiUpdateProvider(mock_civitai)
        service = UpdateService(
            layout=mock_layout, blob_store=mock_blob, view_builder=MagicMock(),
            providers={SelectorStrategy.CIVITAI_MODEL_LATEST: provider},
        )

        plan = service.plan_update("monster")
        assert len(plan.pending_downloads) == 2

        # Each dep must have its own unique download URL with correct file_id
        urls = {p.dependency_id: p.download_url for p in plan.pending_downloads}
        assert "id=3001" in urls["lora_a"]
        assert "id=3002" in urls["lora_b"]
        # URLs must be different
        assert urls["lora_a"] != urls["lora_b"]


class TestApplyPreservesFilename:
    """Tests for apply_update preserving filename in lock."""

    def test_filename_preserved_after_apply(self):
        """apply_update should preserve filename from old lock entry."""
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
                        civitai={"model_id": 123},
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
                    dependency_id="model",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.CHECKPOINT,
                        sha256="old_hash",
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=123,
                            version_id=100,
                            file_id=1000,
                            filename="model.safetensors",
                        ),
                    ),
                ),
            ],
        )

        plan = UpdatePlan(
            pack="test",
            changes=[
                UpdateChange(
                    dependency_id="model",
                    old={"provider_version_id": 100},
                    new={
                        "provider": "civitai",
                        "provider_model_id": 123,
                        "provider_version_id": 200,
                        "provider_file_id": 2000,
                        "sha256": "new_hash",
                        "download_url": "https://civitai.com/api/download/models/200?id=2000",
                    },
                ),
            ],
        )

        mock_layout = MagicMock()
        mock_layout.load_pack_lock.return_value = lock
        mock_layout.load_pack.return_value = pack

        mock_civitai = MagicMock()
        provider = CivitaiUpdateProvider(mock_civitai)
        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(), view_builder=MagicMock(),
            providers={SelectorStrategy.CIVITAI_MODEL_LATEST: provider},
        )

        updated_lock = service.apply_update("test", plan)

        # filename should be preserved from old lock
        assert updated_lock.resolved[0].artifact.provider.filename == "model.safetensors"
        # Other fields should be updated
        assert updated_lock.resolved[0].artifact.provider.version_id == 200
        assert updated_lock.resolved[0].artifact.provider.file_id == 2000


class TestCivitaiProviderBuildDownloadUrl:
    """Tests for CivitaiUpdateProvider.build_download_url()."""

    def test_basic_url(self):
        provider = CivitaiUpdateProvider(MagicMock())
        url = provider.build_download_url(200, None)
        assert url == "https://civitai.com/api/download/models/200"

    def test_url_with_file_id(self):
        provider = CivitaiUpdateProvider(MagicMock())
        url = provider.build_download_url(200, 2000)
        assert "id=2000" in url
        assert "models/200" in url

    def test_url_format(self):
        provider = CivitaiUpdateProvider(MagicMock())
        url = provider.build_download_url(300, 3000)
        assert url == "https://civitai.com/api/download/models/300?id=3000"
