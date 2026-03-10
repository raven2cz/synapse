"""Tests for enrichment.py — shared hash/name lookup utilities."""

from unittest.mock import MagicMock

import pytest

from src.store.enrichment import (
    EnrichmentResult,
    enrich_by_hash,
    enrich_by_name,
    enrich_file,
    extract_stem,
    _normalize_name,
    _kind_matches_civitai_type,
)
from src.store.models import AssetKind


# =============================================================================
# extract_stem
# =============================================================================


class TestExtractStem:
    def test_safetensors(self):
        assert extract_stem("ponyDiffusionV6XL.safetensors") == "ponyDiffusionV6XL"

    def test_underscores_to_spaces(self):
        assert extract_stem("sd_xl_turbo_1.0_fp16.safetensors") == "sd xl turbo 1.0 fp16"

    def test_dashes_to_spaces(self):
        assert extract_stem("controlnet-union-sdxl.safetensors") == "controlnet union sdxl"

    def test_ckpt(self):
        assert extract_stem("model.ckpt") == "model"


# =============================================================================
# _normalize_name
# =============================================================================


class TestNormalizeName:
    def test_basic(self):
        assert _normalize_name("Juggernaut_XL") == "juggernaut xl"

    def test_dashes(self):
        assert _normalize_name("My-Model-v2") == "my model v2"


# =============================================================================
# _kind_matches_civitai_type
# =============================================================================


class TestKindMatchesCivitaiType:
    def test_checkpoint(self):
        assert _kind_matches_civitai_type(AssetKind.CHECKPOINT, "Checkpoint")

    def test_lora(self):
        assert _kind_matches_civitai_type(AssetKind.LORA, "LORA")

    def test_locon(self):
        assert _kind_matches_civitai_type(AssetKind.LORA, "LoCon")

    def test_mismatch(self):
        assert not _kind_matches_civitai_type(AssetKind.CHECKPOINT, "LORA")

    def test_unknown_kind(self):
        assert not _kind_matches_civitai_type(AssetKind.UNKNOWN, "Checkpoint")


# =============================================================================
# enrich_by_hash
# =============================================================================


class TestEnrichByHash:
    def _make_civitai_version(self, model_id=123, version_id=456, name="Test Model"):
        """Create a mock CivitaiModelVersion dataclass."""
        obj = MagicMock()
        obj.model_id = model_id
        obj.id = version_id
        obj.name = name
        obj.base_model = "SDXL"
        obj.baseModel = "SDXL"
        obj.files = [{"id": 789, "hashes": {"SHA256": "abc123"}}]
        return obj

    def test_found(self):
        mock_client = MagicMock()
        mock_client.get_model_by_hash.return_value = self._make_civitai_version()

        result = enrich_by_hash("abc123", mock_client)
        assert result is not None
        assert result.source == "civitai_hash"
        assert result.civitai.model_id == 123
        assert result.civitai.version_id == 456
        assert result.canonical_source is not None

    def test_not_found(self):
        mock_client = MagicMock()
        mock_client.get_model_by_hash.return_value = None

        result = enrich_by_hash("abc123", mock_client)
        assert result is None

    def test_no_client(self):
        result = enrich_by_hash("abc123", None)
        assert result is None

    def test_exception_handled(self):
        mock_client = MagicMock()
        mock_client.get_model_by_hash.side_effect = Exception("API error")

        result = enrich_by_hash("abc123", mock_client)
        assert result is None

    def test_incomplete_result_no_model_id(self):
        obj = MagicMock()
        obj.model_id = None
        obj.id = 456
        obj.name = "Test"
        obj.base_model = None
        obj.baseModel = None
        obj.files = []

        mock_client = MagicMock()
        mock_client.get_model_by_hash.return_value = obj

        result = enrich_by_hash("abc", mock_client)
        assert result is None


# =============================================================================
# enrich_by_name
# =============================================================================


class TestEnrichByName:
    def test_found(self):
        mock_client = MagicMock()
        mock_client.search_meilisearch.return_value = {
            "items": [{"id": 100, "name": "Juggernaut XL", "type": "Checkpoint"}]
        }
        mock_client.get_model.return_value = {
            "modelVersions": [{"id": 200, "baseModel": "SDXL", "files": [{"id": 300}]}]
        }

        result = enrich_by_name("juggernaut xl", mock_client, AssetKind.CHECKPOINT)
        assert result is not None
        assert result.source == "civitai_name"
        assert result.civitai.model_id == 100
        assert result.civitai.version_id == 200
        assert result.display_name == "Juggernaut XL"

    def test_no_match(self):
        mock_client = MagicMock()
        mock_client.search_meilisearch.return_value = {"items": []}

        result = enrich_by_name("juggernaut xl", mock_client)
        assert result is None

    def test_kind_filter(self):
        mock_client = MagicMock()
        mock_client.search_meilisearch.return_value = {
            "items": [{"id": 100, "name": "Something", "type": "LORA"}]
        }

        # Should reject: we want checkpoint but found LORA
        result = enrich_by_name("something", mock_client, AssetKind.CHECKPOINT)
        assert result is None

    def test_short_stem_skipped(self):
        result = enrich_by_name("ab", MagicMock())
        assert result is None

    def test_no_client(self):
        result = enrich_by_name("test", None)
        assert result is None

    def test_name_similarity_check(self):
        """Names that don't match should be rejected."""
        mock_client = MagicMock()
        mock_client.search_meilisearch.return_value = {
            "items": [{"id": 100, "name": "Completely Different Model", "type": "Checkpoint"}]
        }

        result = enrich_by_name("juggernaut xl", mock_client)
        assert result is None


# =============================================================================
# enrich_file
# =============================================================================


class TestEnrichFile:
    def test_hash_first(self):
        """Hash lookup takes priority over name search."""
        mock_client = MagicMock()
        obj = MagicMock()
        obj.model_id = 1
        obj.id = 2
        obj.name = "Found by Hash"
        obj.base_model = None
        obj.baseModel = None
        obj.files = []
        mock_client.get_model_by_hash.return_value = obj

        result = enrich_file("abc", "model.safetensors", mock_client)
        assert result.source == "civitai_hash"

    def test_fallback_to_name(self):
        """Hash miss → name search."""
        mock_client = MagicMock()
        mock_client.get_model_by_hash.return_value = None
        mock_client.search_meilisearch.return_value = {
            "items": [{"id": 100, "name": "model", "type": "Checkpoint"}]
        }
        mock_client.get_model.return_value = {
            "modelVersions": [{"id": 200, "baseModel": "SDXL", "files": [{"id": 300}]}]
        }

        result = enrich_file("abc", "model.safetensors", mock_client)
        assert result.source == "civitai_name"

    def test_all_miss_filename_only(self):
        """Nothing found → filename_only."""
        mock_client = MagicMock()
        mock_client.get_model_by_hash.return_value = None
        mock_client.search_meilisearch.return_value = {"items": []}

        result = enrich_file("abc", "custom_model_v3.safetensors", mock_client)
        assert result.source == "filename_only"
        assert result.display_name == "custom model v3"

    def test_no_client(self):
        """No client → filename_only."""
        result = enrich_file("abc", "model.safetensors", None)
        assert result.source == "filename_only"
        assert result.display_name == "model"
