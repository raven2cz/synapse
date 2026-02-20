"""
Integration Tests for Parameter Extraction During Import

Tests that parameters are automatically extracted from Civitai model descriptions
when importing packs.

Author: Synapse Team
License: MIT
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.store import Store
from src.store.pack_service import PackService
from src.store.layout import StoreLayout
from src.store.models import GenerationParameters
from src.ai.providers.rule_based import RuleBasedProvider


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_civitai_client():
    """Create a mock Civitai client."""
    client = MagicMock()
    return client


@pytest.fixture
def temp_store(tmp_path: Path, mock_civitai_client) -> Store:
    """Create a temporary store for testing."""
    store_root = tmp_path / "synapse_store"
    store = Store(root=store_root, civitai_client=mock_civitai_client)
    store.init()
    return store


# =============================================================================
# Test Data
# =============================================================================

def make_model_data(description: str, model_id: int = 12345) -> dict:
    """Create mock Civitai model data with given description."""
    return {
        "id": model_id,
        "name": "Test Model",
        "type": "LORA",
        "description": description,
        "creator": {"username": "testuser"},
        "tags": ["test"],
        "stats": {"downloadCount": 100, "rating": 4.5},
        "modelVersions": [
            {
                "id": 67890,
                "name": "v1.0",
                "trainedWords": ["trigger"],
                "files": [
                    {
                        "name": "model.safetensors",
                        "sizeKB": 100,
                        "type": "Model",
                        "hashes": {"SHA256": "abc123", "AutoV2": "def456"},
                        "downloadUrl": "https://example.com/model.safetensors",
                    }
                ],
                "images": [],
                "baseModel": "SD 1.5",
            }
        ],
    }


def make_version_data(version_id: int = 67890) -> dict:
    """Create mock Civitai version data."""
    return {
        "id": version_id,
        "name": "v1.0",
        "trainedWords": ["trigger"],
        "files": [
            {
                "name": "model.safetensors",
                "sizeKB": 100,
                "type": "Model",
                "hashes": {"SHA256": "abc123", "AutoV2": "def456"},
                "downloadUrl": "https://example.com/model.safetensors",
            }
        ],
        "images": [],
        "baseModel": "SD 1.5",
    }


# =============================================================================
# Tests
# =============================================================================

class _RuleBasedOnlyAIService:
    """Fake AIService that only uses rule-based extraction (no network calls)."""

    def extract_parameters(self, description: str):
        """Extract parameters using rule-based provider only."""
        from src.ai.providers.rule_based import RuleBasedProvider

        provider = RuleBasedProvider()
        result = provider.execute(description)

        # Convert ProviderResult to TaskResult-like object
        class _Result:
            def __init__(self, pr):
                self.success = pr.success
                self.output = pr.output
                self.provider_id = "rule_based"

        return _Result(result)


class TestParameterExtractionDuringImport:
    """Tests for automatic parameter extraction during Civitai import."""

    @pytest.fixture(autouse=True)
    def _mock_ai(self):
        """Use rule_based AI provider only (no Ollama/Gemini/Claude network calls)."""
        with patch('src.ai.AIService', return_value=_RuleBasedOnlyAIService()):
            yield

    def test_import_extracts_parameters_from_description(
        self, temp_store: Store, mock_civitai_client
    ):
        """Parameters should be extracted from description during import."""
        description = """
        <p>Great model for portraits!</p>
        <p>Recommended settings: CFG 7, Steps 25, Clip Skip 2</p>
        <p>Sampler: euler, Strength: 0.8</p>
        """

        mock_civitai_client.get_model.return_value = make_model_data(description)
        mock_civitai_client.get_model_version.return_value = make_version_data()

        pack_service = PackService(
            layout=temp_store.layout,
            blob_store=temp_store.blob_store,
            civitai_client=mock_civitai_client,
        )

        pack = pack_service.import_from_civitai(
            url="https://civitai.com/models/12345",
            download_previews=False,
        )

        # Verify parameters were extracted
        assert pack.parameters is not None
        assert pack.parameters.cfg_scale == 7.0
        assert pack.parameters.steps == 25
        assert pack.parameters.clip_skip == 2
        assert pack.parameters.strength == 0.8

    def test_import_extracts_sampler_from_description(
        self, temp_store: Store, mock_civitai_client
    ):
        """Sampler should be extracted using dictionary matching."""
        description = "Use with sampler: DPM++ 2M Karras, CFG: 6"

        mock_civitai_client.get_model.return_value = make_model_data(description)
        mock_civitai_client.get_model_version.return_value = make_version_data()

        pack_service = PackService(
            layout=temp_store.layout,
            blob_store=temp_store.blob_store,
            civitai_client=mock_civitai_client,
        )

        pack = pack_service.import_from_civitai(
            url="https://civitai.com/models/12345",
            download_previews=False,
        )

        assert pack.parameters is not None
        assert pack.parameters.cfg_scale == 6.0
        assert "dpm++" in pack.parameters.sampler.lower()

    def test_import_extracts_hires_fix_from_context(
        self, temp_store: Store, mock_civitai_client
    ):
        """Hires fix should be inferred from context keywords like 'must'."""
        description = """
        <p>Highres-Fix is A Must!</p>
        <p>Hires: 2x, denoising: 0.5</p>
        """

        mock_civitai_client.get_model.return_value = make_model_data(description)
        mock_civitai_client.get_model_version.return_value = make_version_data()

        pack_service = PackService(
            layout=temp_store.layout,
            blob_store=temp_store.blob_store,
            civitai_client=mock_civitai_client,
        )

        pack = pack_service.import_from_civitai(
            url="https://civitai.com/models/12345",
            download_previews=False,
        )

        assert pack.parameters is not None
        assert pack.parameters.hires_fix is True
        assert pack.parameters.hires_scale == 2.0
        # Rule-based extractor puts denoise value on the general field
        assert pack.parameters.denoise == 0.5

    def test_import_extracts_best_value_from_range(
        self, temp_store: Store, mock_civitai_client
    ):
        """When description has range with 'best', extract the best value."""
        description = "CFG: 5-7 (7 is best), Steps: 20-30"

        mock_civitai_client.get_model.return_value = make_model_data(description)
        mock_civitai_client.get_model_version.return_value = make_version_data()

        pack_service = PackService(
            layout=temp_store.layout,
            blob_store=temp_store.blob_store,
            civitai_client=mock_civitai_client,
        )

        pack = pack_service.import_from_civitai(
            url="https://civitai.com/models/12345",
            download_previews=False,
        )

        assert pack.parameters is not None
        assert pack.parameters.cfg_scale == 7.0  # "best" value
        assert pack.parameters.steps == 30  # Higher from range

    def test_import_with_empty_description_has_no_parameters(
        self, temp_store: Store, mock_civitai_client
    ):
        """Pack with empty description should have no extracted parameters."""
        mock_civitai_client.get_model.return_value = make_model_data("")
        mock_civitai_client.get_model_version.return_value = make_version_data()

        pack_service = PackService(
            layout=temp_store.layout,
            blob_store=temp_store.blob_store,
            civitai_client=mock_civitai_client,
        )

        pack = pack_service.import_from_civitai(
            url="https://civitai.com/models/12345",
            download_previews=False,
        )

        # Parameters should be None or empty
        assert pack.parameters is None or len(pack.parameters.model_dump(exclude_none=True)) == 0

    def test_import_with_no_numeric_parameters_in_description(
        self, temp_store: Store, mock_civitai_client
    ):
        """Pack with description but no numeric parameters may still have info fields.

        AI extracts ALL information including compatibility notes, tips, etc.
        These non-numeric fields are preserved and displayed in the UI.
        """
        description = """
        <p>This is a great model for creating beautiful art!</p>
        <p>Works well with most checkpoints.</p>
        """

        mock_civitai_client.get_model.return_value = make_model_data(description)
        mock_civitai_client.get_model_version.return_value = make_version_data()

        pack_service = PackService(
            layout=temp_store.layout,
            blob_store=temp_store.blob_store,
            civitai_client=mock_civitai_client,
        )

        pack = pack_service.import_from_civitai(
            url="https://civitai.com/models/12345",
            download_previews=False,
        )

        # AI may extract non-numeric info like compatibility notes
        # These are valid and should be preserved
        if pack.parameters is not None:
            params_dict = pack.parameters.model_dump(exclude_none=True)
            # Remove metadata fields for counting
            params_dict.pop("_extracted_by", None)
            # No NUMERIC parameters expected (cfg_scale, steps, etc.)
            numeric_params = {
                k: v for k, v in params_dict.items()
                if k in {"cfg_scale", "steps", "clip_skip", "width", "height",
                         "sampler", "scheduler", "strength", "denoise", "seed",
                         "hires_fix", "hires_scale", "hires_denoise", "hires_steps"}
            }
            assert len(numeric_params) == 0, f"Expected no numeric parameters but got: {numeric_params}"

    def test_import_extracts_resolution_from_description(
        self, temp_store: Store, mock_civitai_client
    ):
        """Resolution should be extracted from WxH format."""
        description = "Recommended resolution: 512x768, CFG: 7"

        mock_civitai_client.get_model.return_value = make_model_data(description)
        mock_civitai_client.get_model_version.return_value = make_version_data()

        pack_service = PackService(
            layout=temp_store.layout,
            blob_store=temp_store.blob_store,
            civitai_client=mock_civitai_client,
        )

        pack = pack_service.import_from_civitai(
            url="https://civitai.com/models/12345",
            download_previews=False,
        )

        assert pack.parameters is not None
        assert pack.parameters.width == 512
        assert pack.parameters.height == 768

    def test_parameters_persist_after_pack_reload(
        self, temp_store: Store, mock_civitai_client
    ):
        """Extracted parameters should persist when pack is reloaded from disk."""
        description = "Settings: CFG 8, Steps 30, Clip Skip 1"

        mock_civitai_client.get_model.return_value = make_model_data(description)
        mock_civitai_client.get_model_version.return_value = make_version_data()

        pack_service = PackService(
            layout=temp_store.layout,
            blob_store=temp_store.blob_store,
            civitai_client=mock_civitai_client,
        )

        # Import pack
        original_pack = pack_service.import_from_civitai(
            url="https://civitai.com/models/12345",
            download_previews=False,
        )

        # Reload pack from disk
        reloaded_pack = temp_store.layout.load_pack(original_pack.name)

        # Verify parameters persisted
        assert reloaded_pack.parameters is not None
        assert reloaded_pack.parameters.cfg_scale == original_pack.parameters.cfg_scale
        assert reloaded_pack.parameters.steps == original_pack.parameters.steps
        assert reloaded_pack.parameters.clip_skip == original_pack.parameters.clip_skip
