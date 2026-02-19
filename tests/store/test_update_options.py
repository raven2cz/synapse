"""
Tests for Updates Phase: UpdateOptions, Preview Merge, Batch Apply

Unit tests:
- UpdateOptions model defaults and validation
- BatchUpdateResult model
- UpdateResult enriched fields
- URL canonicalization for preview dedup

Integration tests:
- _merge_previews_from_civitai() with mock Civitai
- _update_description_from_civitai() with mock Civitai
- _update_model_info_from_civitai() with mock Civitai
- apply_batch() with multiple packs
- update_pack() with options parameter

Smoke tests:
- Full plan → apply flow
- Description preservation without update_description option
- Batch apply with mixed results
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.store.models import (
    ArtifactDownload,
    ArtifactIntegrity,
    ArtifactProvider,
    AssetKind,
    BatchUpdateResult,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackDependency,
    PackLock,
    PackSource,
    PreviewInfo,
    ProviderName,
    ResolvedArtifact,
    ResolvedDependency,
    SelectorStrategy,
    SelectorConstraints,
    UpdateChange,
    UpdateOptions,
    UpdatePlan,
    UpdatePolicyMode,
    UpdatePolicy,
    UpdateResult,
)
from src.store.update_service import UpdateService


# =============================================================================
# Unit Tests: UpdateOptions Model
# =============================================================================


class TestUpdateOptionsModel:
    """Unit tests for UpdateOptions model."""

    def test_defaults_all_false(self):
        """All options should default to False."""
        opts = UpdateOptions()
        assert opts.merge_previews is False
        assert opts.update_description is False
        assert opts.update_model_info is False

    def test_set_merge_previews(self):
        opts = UpdateOptions(merge_previews=True)
        assert opts.merge_previews is True
        assert opts.update_description is False

    def test_set_all_options(self):
        opts = UpdateOptions(
            merge_previews=True,
            update_description=True,
            update_model_info=True,
        )
        assert opts.merge_previews is True
        assert opts.update_description is True
        assert opts.update_model_info is True

    def test_serializes(self):
        opts = UpdateOptions(merge_previews=True)
        data = opts.model_dump()
        assert data == {
            "merge_previews": True,
            "update_description": False,
            "update_model_info": False,
        }


# =============================================================================
# Unit Tests: BatchUpdateResult Model
# =============================================================================


class TestBatchUpdateResultModel:
    """Unit tests for BatchUpdateResult model."""

    def test_defaults(self):
        result = BatchUpdateResult()
        assert result.results == {}
        assert result.total_applied == 0
        assert result.total_failed == 0
        assert result.total_skipped == 0

    def test_with_results(self):
        result = BatchUpdateResult(
            results={"pack-a": {"applied": True}, "pack-b": {"error": "failed"}},
            total_applied=1,
            total_failed=1,
        )
        assert len(result.results) == 2
        assert result.total_applied == 1
        assert result.total_failed == 1

    def test_serializes(self):
        result = BatchUpdateResult(total_applied=3, total_skipped=1)
        data = result.model_dump()
        assert data["total_applied"] == 3
        assert data["total_skipped"] == 1


# =============================================================================
# Unit Tests: UpdateResult Enriched Fields
# =============================================================================


class TestUpdateResultEnriched:
    """Tests for enriched UpdateResult fields."""

    def test_new_fields_default(self):
        result = UpdateResult(pack="test", applied=True, lock_updated=True, synced=False)
        assert result.previews_merged == 0
        assert result.description_updated is False
        assert result.model_info_updated is False

    def test_new_fields_set(self):
        result = UpdateResult(
            pack="test",
            applied=True,
            lock_updated=True,
            synced=True,
            previews_merged=5,
            description_updated=True,
            model_info_updated=True,
        )
        assert result.previews_merged == 5
        assert result.description_updated is True
        assert result.model_info_updated is True

    def test_backward_compatible_serialization(self):
        """Old-style results without new fields should still work."""
        data = {"pack": "test", "applied": True, "lock_updated": True, "synced": False}
        result = UpdateResult(**data)
        assert result.previews_merged == 0


# =============================================================================
# Integration Tests: Preview Merge
# =============================================================================


class TestPreviewMerge:
    """Tests for _merge_previews_from_civitai()."""

    def _make_pack(self, previews=None):
        """Create a test pack with Civitai source."""
        return Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(
                provider=ProviderName.CIVITAI,
                model_id=12345,
                version_id=100,
            ),
            previews=previews or [],
        )

    def _make_service(self, civitai_response=None):
        """Create an UpdateService with mocked Civitai client."""
        from src.store.update_service import UpdateService

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = civitai_response or {
            "modelVersions": [
                {
                    "id": 100,
                    "images": [
                        {"url": "https://civitai.com/img/1.jpg", "type": "image", "width": 512, "height": 768},
                        {"url": "https://civitai.com/img/2.jpg", "type": "image", "width": 512, "height": 768},
                    ],
                }
            ]
        }

        service = UpdateService(
            layout=MagicMock(),
            blob_store=MagicMock(),
            view_builder=MagicMock(),
            civitai_client=mock_civitai,
        )
        return service

    def test_merge_adds_new_previews(self):
        """New previews should be added to pack."""
        pack = self._make_pack()
        service = self._make_service()

        added = service._merge_previews_from_civitai(pack)
        assert added == 2
        assert len(pack.previews) == 2

    def test_merge_deduplicates_by_url(self):
        """Existing previews with same URL should not be added again."""
        pack = self._make_pack(previews=[
            PreviewInfo(filename="1.jpg", url="https://civitai.com/img/1.jpg"),
        ])
        service = self._make_service()

        added = service._merge_previews_from_civitai(pack)
        assert added == 1  # Only img/2.jpg is new
        assert len(pack.previews) == 2

    def test_merge_preserves_existing(self):
        """User's custom previews should be preserved."""
        pack = self._make_pack(previews=[
            PreviewInfo(filename="custom.jpg", url="https://example.com/custom.jpg"),
        ])
        service = self._make_service()

        added = service._merge_previews_from_civitai(pack)
        assert added == 2
        assert len(pack.previews) == 3
        assert pack.previews[0].url == "https://example.com/custom.jpg"

    def test_merge_no_source(self):
        """Non-Civitai packs should return 0."""
        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.LOCAL),
        )
        service = self._make_service()

        added = service._merge_previews_from_civitai(pack)
        assert added == 0

    def test_merge_api_failure(self):
        """API failure should return 0 gracefully."""
        pack = self._make_pack()

        from src.store.update_service import UpdateService
        mock_civitai = MagicMock()
        mock_civitai.get_model.side_effect = Exception("API Error")
        service = UpdateService(
            layout=MagicMock(),
            blob_store=MagicMock(),
            view_builder=MagicMock(),
            civitai_client=mock_civitai,
        )

        added = service._merge_previews_from_civitai(pack)
        assert added == 0

    def test_merge_empty_images(self):
        """Version with no images should return 0."""
        pack = self._make_pack()
        service = self._make_service({"modelVersions": [{"id": 100, "images": []}]})

        added = service._merge_previews_from_civitai(pack)
        assert added == 0

    def test_merge_sets_media_type(self):
        """Video previews should get media_type='video'."""
        pack = self._make_pack()
        service = self._make_service({
            "modelVersions": [
                {
                    "id": 100,
                    "images": [
                        {"url": "https://civitai.com/vid/1.mp4", "type": "video"},
                    ],
                }
            ]
        })

        added = service._merge_previews_from_civitai(pack)
        assert added == 1
        assert pack.previews[0].media_type == "video"


# =============================================================================
# Integration Tests: Description Update
# =============================================================================


class TestDescriptionUpdate:
    """Tests for _update_description_from_civitai()."""

    def test_updates_description(self):
        from src.store.update_service import UpdateService

        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
            description="Old description",
        )

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {"description": "New description from Civitai"}
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        updated = service._update_description_from_civitai(pack)
        assert updated is True
        assert pack.description == "New description from Civitai"

    def test_no_change_same_description(self):
        from src.store.update_service import UpdateService

        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
            description="Same description",
        )

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {"description": "Same description"}
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        updated = service._update_description_from_civitai(pack)
        assert updated is False

    def test_no_source(self):
        from src.store.update_service import UpdateService

        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.LOCAL),
        )
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=MagicMock(),
        )

        updated = service._update_description_from_civitai(pack)
        assert updated is False


# =============================================================================
# Integration Tests: Model Info Update
# =============================================================================


class TestModelInfoUpdate:
    """Tests for _update_model_info_from_civitai()."""

    def test_updates_base_model(self):
        from src.store.update_service import UpdateService

        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=123, version_id=100),
            base_model="SD 1.5",
        )

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{"id": 100, "baseModel": "SDXL 1.0", "trainedWords": []}]
        }
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        updated = service._update_model_info_from_civitai(pack)
        assert updated is True
        assert pack.base_model == "SDXL 1.0"

    def test_updates_trigger_words(self):
        from src.store.update_service import UpdateService

        dep = PackDependency(
            id="lora",
            kind=AssetKind.LORA,
            selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_MODEL_LATEST),
            expose=ExposeConfig(filename="model.safetensors", trigger_words=["old_word"]),
        )
        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=123, version_id=100),
            dependencies=[dep],
        )

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{"id": 100, "baseModel": None, "trainedWords": ["new_word", "another"]}]
        }
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        updated = service._update_model_info_from_civitai(pack)
        assert updated is True
        assert set(pack.dependencies[0].expose.trigger_words) == {"new_word", "another"}


# =============================================================================
# Integration Tests: Batch Apply
# =============================================================================


class TestBatchApply:
    """Tests for apply_batch()."""

    def test_batch_empty_list(self):
        from src.store.update_service import UpdateService

        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        result = service.apply_batch([])
        assert result.total_applied == 0
        assert result.total_failed == 0
        assert result.total_skipped == 0

    def test_batch_result_serializes(self):
        result = BatchUpdateResult(
            results={"pack-a": {"applied": True}},
            total_applied=1,
        )
        data = result.model_dump()
        assert "results" in data
        assert "total_applied" in data
        assert data["total_applied"] == 1

    def test_batch_handles_errors_gracefully(self):
        from src.store.update_service import UpdateService

        mock_layout = MagicMock()
        mock_layout.load_pack.side_effect = Exception("Pack not found")

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        result = service.apply_batch(["nonexistent-pack"])
        assert result.total_failed == 1
        assert "nonexistent-pack" in result.results
        assert result.results["nonexistent-pack"]["applied"] is False


# =============================================================================
# Unit Tests: update_pack() with options
# =============================================================================


class TestUpdatePackWithOptions:
    """Tests for update_pack() accepting options parameter."""

    def test_options_parameter_accepted(self):
        """update_pack() should accept options without error."""
        from src.store.update_service import UpdateService

        mock_layout = MagicMock()
        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
        )
        mock_layout.load_pack.return_value = pack

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        # Should not raise - pack has no updatable deps, so returns up-to-date
        result = service.update_pack(
            "test-pack",
            options=UpdateOptions(merge_previews=True),
        )
        assert result.already_up_to_date is True


# =============================================================================
# Unit Tests: URL Canonicalization
# =============================================================================


class TestURLCanonicalization:
    """Tests for _canonicalize_url() used in preview dedup."""

    def test_strips_query_params(self):
        result = UpdateService._canonicalize_url(
            "https://civitai.com/img/1.jpg?width=450&anim=false"
        )
        assert result == "https://civitai.com/img/1.jpg"

    def test_strips_fragment(self):
        result = UpdateService._canonicalize_url(
            "https://civitai.com/img/1.jpg#section"
        )
        assert result == "https://civitai.com/img/1.jpg"

    def test_strips_both(self):
        result = UpdateService._canonicalize_url(
            "https://civitai.com/img/1.jpg?w=450#top"
        )
        assert result == "https://civitai.com/img/1.jpg"

    def test_no_params_unchanged(self):
        result = UpdateService._canonicalize_url(
            "https://civitai.com/img/1.jpg"
        )
        assert result == "https://civitai.com/img/1.jpg"

    def test_empty_string(self):
        assert UpdateService._canonicalize_url("") == ""

    def test_dedup_with_query_variants(self):
        """Same base URL with different query params should dedup."""
        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(
                provider=ProviderName.CIVITAI, model_id=123, version_id=100,
            ),
            previews=[
                PreviewInfo(
                    filename="1.jpg",
                    url="https://civitai.com/img/1.jpg?width=450&anim=false",
                ),
            ],
        )

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 100,
                "images": [
                    {
                        "url": "https://civitai.com/img/1.jpg?width=800",
                        "type": "image",
                    },
                    {
                        "url": "https://civitai.com/img/2.jpg?width=800",
                        "type": "image",
                    },
                ],
            }]
        }
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        added = service._merge_previews_from_civitai(pack)
        assert added == 1  # Only img/2.jpg is new, img/1.jpg deduped
        assert len(pack.previews) == 2


# =============================================================================
# Integration Tests: Full Plan → Apply Flow
# =============================================================================


class TestFullUpdateFlow:
    """Integration tests for complete plan → apply cycle."""

    def _make_updatable_pack(self):
        """Create a pack with an updatable dependency."""
        return Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
            dependencies=[
                PackDependency(
                    id="main-model",
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

    def _make_lock(self):
        """Create a lock with a resolved dependency."""
        return PackLock(
            pack="test-pack",
            resolved=[
                ResolvedDependency(
                    dependency_id="main-model",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.CHECKPOINT,
                        sha256="old_sha256",
                        size_bytes=1024,
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=123,
                            version_id=100,
                            file_id=1000,
                        ),
                        download=ArtifactDownload(
                            urls=["https://civitai.com/api/download/models/100"],
                        ),
                        integrity=ArtifactIntegrity(sha256_verified=True),
                    ),
                ),
            ],
        )

    def test_plan_detects_update(self):
        """Plan should detect when a newer version is available."""
        pack = self._make_updatable_pack()
        lock = self._make_lock()

        mock_layout = MagicMock()
        mock_layout.load_pack.return_value = pack
        mock_layout.load_pack_lock.return_value = lock
        mock_layout.list_packs.return_value = ["test-pack"]

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 200,  # Newer version
                "files": [{
                    "id": 2000,
                    "primary": True,
                    "name": "model.safetensors",
                    "hashes": {"SHA256": "NEW_SHA256"},
                    "sizeKB": 2048,
                    "downloadUrl": "https://civitai.com/api/download/models/200",
                }],
            }],
        }

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        plan = service.plan_update("test-pack")
        assert plan.already_up_to_date is False
        assert len(plan.changes) == 1
        assert plan.changes[0].dependency_id == "main-model"
        assert plan.changes[0].new["provider_version_id"] == 200

    def test_plan_up_to_date(self):
        """Plan should report up-to-date when on latest version."""
        pack = self._make_updatable_pack()
        lock = self._make_lock()

        mock_layout = MagicMock()
        mock_layout.load_pack.return_value = pack
        mock_layout.load_pack_lock.return_value = lock
        mock_layout.list_packs.return_value = ["test-pack"]

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "modelVersions": [{
                "id": 100,  # Same version
                "files": [{"id": 1000, "primary": True}],
            }],
        }

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        plan = service.plan_update("test-pack")
        assert plan.already_up_to_date is True
        assert len(plan.changes) == 0

    def test_apply_updates_lock(self):
        """Apply should update the lock with new version info."""
        lock = self._make_lock()

        mock_layout = MagicMock()
        mock_layout.load_pack_lock.return_value = lock

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        plan = UpdatePlan(
            pack="test-pack",
            already_up_to_date=False,
            changes=[
                UpdateChange(
                    dependency_id="main-model",
                    old={
                        "provider": "civitai",
                        "provider_model_id": 123,
                        "provider_version_id": 100,
                        "provider_file_id": 1000,
                        "sha256": "old_sha256",
                    },
                    new={
                        "provider": "civitai",
                        "provider_model_id": 123,
                        "provider_version_id": 200,
                        "provider_file_id": 2000,
                        "sha256": "new_sha256",
                    },
                ),
            ],
            ambiguous=[],
            impacted_packs=[],
        )

        updated_lock = service.apply_update("test-pack", plan)
        assert updated_lock.resolved[0].artifact.provider.version_id == 200
        assert updated_lock.resolved[0].artifact.provider.file_id == 2000
        assert updated_lock.resolved[0].artifact.sha256 == "new_sha256"
        mock_layout.save_pack_lock.assert_called_once()

    def test_is_updatable_with_follow_latest(self):
        """Pack with follow_latest policy should be updatable."""
        pack = self._make_updatable_pack()
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(),
            view_builder=MagicMock(),
        )
        assert service.is_updatable(pack) is True

    def test_is_not_updatable_without_policy(self):
        """Pack without follow_latest policy should not be updatable."""
        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
            dependencies=[
                PackDependency(
                    id="main-model",
                    kind=AssetKind.CHECKPOINT,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    ),
                    expose=ExposeConfig(filename="model.safetensors"),
                    # Default policy is PINNED
                ),
            ],
        )
        service = UpdateService(
            layout=MagicMock(), blob_store=MagicMock(),
            view_builder=MagicMock(),
        )
        assert service.is_updatable(pack) is False


# =============================================================================
# Smoke Tests: Description Preservation
# =============================================================================


class TestDescriptionPreservation:
    """Test that descriptions are NOT overwritten without explicit option."""

    def test_description_preserved_without_option(self):
        """Without update_description=True, description stays unchanged."""
        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
            description="My custom description",
        )

        mock_layout = MagicMock()
        mock_layout.load_pack.return_value = pack

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "description": "New Civitai description"
        }
        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        result = UpdateResult(
            pack="test-pack", applied=True, lock_updated=True, synced=False,
        )
        # Apply WITHOUT update_description
        service._apply_options(
            "test-pack",
            UpdateOptions(merge_previews=False, update_description=False),
            result,
        )
        assert pack.description == "My custom description"
        assert result.description_updated is False

    def test_description_updated_with_option(self):
        """With update_description=True, description should be overwritten."""
        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
            description="My custom description",
        )

        mock_layout = MagicMock()
        mock_layout.load_pack.return_value = pack

        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = {
            "description": "New Civitai description"
        }
        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        result = UpdateResult(
            pack="test-pack", applied=True, lock_updated=True, synced=False,
        )
        service._apply_options(
            "test-pack",
            UpdateOptions(update_description=True),
            result,
        )
        assert pack.description == "New Civitai description"
        assert result.description_updated is True


# =============================================================================
# Smoke Tests: Reverse Dependencies
# =============================================================================


class TestReverseDependencies:
    """Tests for _find_reverse_dependencies()."""

    def test_finds_reverse_deps(self):
        """Should find packs that depend on the given pack."""
        parent_pack = MagicMock()
        parent_pack.pack_dependencies = [MagicMock(pack_name="child-pack")]

        child_pack = MagicMock()
        child_pack.pack_dependencies = []

        mock_layout = MagicMock()
        mock_layout.list_packs.return_value = ["parent-pack", "child-pack"]
        mock_layout.load_pack.side_effect = lambda name: {
            "parent-pack": parent_pack,
            "child-pack": child_pack,
        }[name]

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        result = service._find_reverse_dependencies("child-pack")
        assert result == ["parent-pack"]

    def test_no_reverse_deps(self):
        """Should return empty list when no packs depend on it."""
        pack_a = MagicMock()
        pack_a.pack_dependencies = []
        pack_b = MagicMock()
        pack_b.pack_dependencies = []

        mock_layout = MagicMock()
        mock_layout.list_packs.return_value = ["pack-a", "pack-b"]
        mock_layout.load_pack.side_effect = lambda name: {
            "pack-a": pack_a, "pack-b": pack_b,
        }[name]

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        result = service._find_reverse_dependencies("pack-a")
        assert result == []

    def test_handles_load_errors(self):
        """Should skip packs that fail to load."""
        mock_layout = MagicMock()
        mock_layout.list_packs.return_value = ["pack-a", "broken-pack"]
        mock_layout.load_pack.side_effect = [
            MagicMock(pack_dependencies=[]),
            Exception("Corrupt pack"),
        ]

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        result = service._find_reverse_dependencies("target")
        assert result == []


# =============================================================================
# Smoke Tests: Batch Apply with Mixed Results
# =============================================================================


class TestBatchApplyMixed:
    """Smoke tests for batch apply with mixed outcomes."""

    def test_batch_mixed_success_and_failure(self):
        """Batch with one success and one failure should report both."""
        mock_layout = MagicMock()

        # good-pack has no updatable deps (no follow_latest) → up-to-date/skipped
        good_pack = Pack(
            name="good-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
        )
        good_lock = PackLock(pack="good-pack", resolved=[])

        def load_pack_side_effect(name):
            if name == "good-pack":
                return good_pack
            raise Exception("Pack not found")

        def load_lock_side_effect(name):
            if name == "good-pack":
                return good_lock
            return None

        mock_layout.load_pack.side_effect = load_pack_side_effect
        mock_layout.load_pack_lock.side_effect = load_lock_side_effect
        mock_layout.list_packs.return_value = []

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        result = service.apply_batch(["good-pack", "bad-pack"])
        # good-pack has no updatable deps → skipped
        # bad-pack raises exception → failed
        assert result.total_failed == 1
        assert result.total_skipped >= 1
        assert "bad-pack" in result.results
        assert result.results["bad-pack"]["applied"] is False

    def test_batch_all_up_to_date(self):
        """Batch where all packs are up-to-date should skip all."""
        mock_layout = MagicMock()
        pack = Pack(
            name="pack-a",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.LOCAL),
        )
        lock = PackLock(pack="pack-a", resolved=[])
        mock_layout.load_pack.return_value = pack
        mock_layout.load_pack_lock.return_value = lock
        mock_layout.list_packs.return_value = []

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        result = service.apply_batch(["pack-a"])
        # No updatable deps → already_up_to_date
        assert result.total_applied == 0
        assert result.total_failed == 0

    def test_batch_with_options_passed_through(self):
        """Options should be passed to each pack update."""
        mock_layout = MagicMock()
        pack = Pack(
            name="pack-a",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
        )
        lock = PackLock(pack="pack-a", resolved=[])
        mock_layout.load_pack.return_value = pack
        mock_layout.load_pack_lock.return_value = lock
        mock_layout.list_packs.return_value = []

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        options = UpdateOptions(merge_previews=True, update_description=True)
        result = service.apply_batch(["pack-a"], options=options)
        # Should complete without error (pack is up-to-date, skipped)
        assert result.total_failed == 0


# =============================================================================
# Smoke Tests: Check All Updates
# =============================================================================


class TestCheckAllUpdates:
    """Tests for check_all_updates()."""

    def test_check_all_skips_non_updatable(self):
        """Non-updatable packs should be skipped."""
        mock_layout = MagicMock()
        mock_layout.list_packs.return_value = ["pack-a"]

        pack = Pack(
            name="pack-a",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.LOCAL),
            # No dependencies = not updatable
        )
        mock_layout.load_pack.return_value = pack

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        plans = service.check_all_updates()
        assert plans == {}

    def test_check_all_handles_errors(self):
        """Errors during check should be skipped gracefully."""
        mock_layout = MagicMock()
        mock_layout.list_packs.return_value = ["broken-pack"]
        mock_layout.load_pack.side_effect = Exception("Corrupt")

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        plans = service.check_all_updates()
        assert plans == {}


# =============================================================================
# Edge Case Tests: Apply Update with Missing Dep
# =============================================================================


class TestApplyEdgeCases:
    """Edge case tests for apply_update()."""

    def test_apply_change_for_missing_dep_logs_warning(self):
        """Applying a change for a non-existent dep should log warning, not crash."""
        lock = PackLock(
            pack="test-pack",
            resolved=[
                ResolvedDependency(
                    dependency_id="existing-dep",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.CHECKPOINT,
                        sha256="abc",
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=1, version_id=1, file_id=1,
                        ),
                        download=ArtifactDownload(urls=["https://example.com"]),
                        integrity=ArtifactIntegrity(sha256_verified=True),
                    ),
                ),
            ],
        )

        mock_layout = MagicMock()
        mock_layout.load_pack_lock.return_value = lock

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        plan = UpdatePlan(
            pack="test-pack",
            already_up_to_date=False,
            changes=[
                UpdateChange(
                    dependency_id="nonexistent-dep",
                    old={"provider_version_id": 1},
                    new={"provider_version_id": 2, "provider_model_id": 1,
                         "provider_file_id": 2, "sha256": "def"},
                ),
            ],
            ambiguous=[],
            impacted_packs=[],
        )

        # Should NOT raise, just log warning
        updated_lock = service.apply_update("test-pack", plan)
        # Original dep should be unchanged
        assert updated_lock.resolved[0].dependency_id == "existing-dep"
        assert updated_lock.resolved[0].artifact.provider.version_id == 1
        mock_layout.save_pack_lock.assert_called_once()

    def test_apply_no_lock_raises(self):
        """Applying without a lock file should raise UpdateError."""
        from src.store.update_service import UpdateError

        mock_layout = MagicMock()
        mock_layout.load_pack_lock.return_value = None

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(),
        )

        plan = UpdatePlan(
            pack="test-pack", already_up_to_date=False,
            changes=[], ambiguous=[], impacted_packs=[],
        )

        with pytest.raises(UpdateError, match="No lock file"):
            service.apply_update("test-pack", plan)
