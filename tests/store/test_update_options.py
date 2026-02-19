"""
Tests for Updates Phase: UpdateOptions, Preview Merge, Batch Apply

Unit tests:
- UpdateOptions model defaults and validation
- BatchUpdateResult model
- UpdateResult enriched fields

Integration tests:
- _merge_previews_from_civitai() with mock Civitai
- _update_description_from_civitai() with mock Civitai
- _update_model_info_from_civitai() with mock Civitai
- apply_batch() with multiple packs
- update_pack() with options parameter
"""

import pytest
from unittest.mock import MagicMock, patch

from src.store.models import (
    AssetKind,
    BatchUpdateResult,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackDependency,
    PackSource,
    PreviewInfo,
    ProviderName,
    SelectorStrategy,
    UpdateOptions,
    UpdateResult,
)


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
