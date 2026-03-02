"""
API Tests for Parameter Extraction Endpoints

Tests cover:
- POST /api/packs/{pack_name}/parameters/extract endpoint
- Source types: image, aggregated, description
- Error handling for invalid inputs
- Integration with parameter_extractor utilities

Author: Synapse Team
License: MIT
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.store.api import v2_packs_router, require_initialized
from src.store.models import (
    Pack,
    PackSource,
    PreviewInfo,
    GenerationParameters,
    AssetKind,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_store():
    """Create a mock store with test pack."""
    store = MagicMock()
    store.initialized = True

    # Create test pack with previews that have metadata
    test_pack = Pack(
        name="test-pack",
        version="1.0.0",
        description="Test pack with CFG 7, Steps 25, Clip Skip 2 recommended settings.",
        pack_type=AssetKind.LORA,
        source=PackSource(provider="civitai", model_id=123, version_id=456),
        previews=[
            PreviewInfo(
                filename="preview1.jpg",
                url="http://example.com/preview1.jpg",
                nsfw=False,
                width=512,
                height=768,
                meta={
                    "prompt": "beautiful landscape, mountains",
                    "negativePrompt": "ugly, blurry",
                    "cfgScale": 7,
                    "steps": 25,
                    "sampler": "euler",
                    "seed": 12345,
                    "clipSkip": 2,
                },
            ),
            PreviewInfo(
                filename="preview2.jpg",
                url="http://example.com/preview2.jpg",
                nsfw=False,
                width=512,
                height=768,
                meta={
                    "prompt": "portrait of a woman",
                    "negativePrompt": "bad quality",
                    "cfgScale": 7.5,
                    "steps": 30,
                    "sampler": "euler",
                    "seed": 67890,
                    "clipSkip": 2,
                },
            ),
            PreviewInfo(
                filename="preview3.jpg",
                url="http://example.com/preview3.jpg",
                nsfw=False,
                width=512,
                height=768,
                # No meta - should be skipped in aggregation
                meta=None,
            ),
        ],
    )

    store.get_pack.return_value = test_pack
    return store


@pytest.fixture
def client(mock_store):
    """Create test client with mocked store."""
    app = FastAPI()
    # Mount packs router at /api/packs like in production
    app.include_router(v2_packs_router, prefix="/api/packs")

    # Override the store dependency
    app.dependency_overrides[require_initialized] = lambda: mock_store

    return TestClient(app)


# =============================================================================
# Extract from Image Tests
# =============================================================================

class TestExtractFromImage:
    """Tests for extracting parameters from specific preview image."""

    def test_extract_from_first_image(self, client):
        """Should extract parameters from first preview image."""
        response = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "image", "image_index": 0},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["source"] == "image"
        assert data["parameters"]["cfg_scale"] == 7
        assert data["parameters"]["steps"] == 25
        assert data["parameters"]["sampler"] == "euler"
        assert data["parameters"]["clip_skip"] == 2
        # Prompts should be excluded
        assert "prompt" not in data["parameters"]
        assert "negativePrompt" not in data["parameters"]

    def test_extract_from_second_image(self, client):
        """Should extract parameters from second preview image."""
        response = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "image", "image_index": 1},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["parameters"]["cfg_scale"] == 7.5
        assert data["parameters"]["steps"] == 30

    def test_extract_from_image_without_meta(self, client):
        """Should return empty parameters for image without meta."""
        response = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "image", "image_index": 2},  # preview3 has no meta
        )

        assert response.status_code == 200
        data = response.json()

        assert data["parameters"] == {}
        assert data["confidence"] == 0.0

    def test_extract_from_image_missing_index(self, client):
        """Should return 400 when image_index is missing."""
        response = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "image"},  # Missing image_index
        )

        assert response.status_code == 400
        assert "image_index required" in response.json()["detail"]

    def test_extract_from_image_invalid_index(self, client):
        """Should return 400 for invalid image index."""
        response = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "image", "image_index": 99},  # Out of range
        )

        assert response.status_code == 400
        assert "Invalid image_index" in response.json()["detail"]


# =============================================================================
# Extract Aggregated Tests
# =============================================================================

class TestExtractAggregated:
    """Tests for aggregating parameters from multiple preview images."""

    def test_aggregate_from_all_previews(self, client):
        """Should aggregate parameters from all previews with meta."""
        response = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "aggregated"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["source"] == "aggregated"
        assert data["preview_count"] == 2  # Only 2 previews have meta

        # Mode should select most common values
        # Both have sampler "euler", both have clip_skip 2
        assert data["parameters"]["sampler"] == "euler"
        assert data["parameters"]["clip_skip"] == 2

        # Confidence should be high for consistent values
        assert data["confidence"] > 0


class TestExtractFromDescription:
    """Tests for extracting parameters from pack description."""

    def test_extract_from_description(self, client):
        """Should extract parameters from pack description."""
        # Mock AIService to avoid real network calls to Ollama/etc.
        mock_ai_result = MagicMock()
        mock_ai_result.success = True
        mock_ai_result.output = {"cfg_scale": 7.0, "steps": 25, "clip_skip": 2}
        mock_ai_result.provider = "mock"

        mock_ai_service = MagicMock()
        mock_ai_service.extract_parameters.return_value = mock_ai_result

        with patch('src.avatar.ai_service.AvatarAIService', return_value=mock_ai_service):
            response = client.post(
                "/api/packs/test-pack/parameters/extract",
                json={"source": "description"},
            )

        assert response.status_code == 200
        data = response.json()

        # Source is 'description' or 'description:provider' if AI was used
        assert data["source"].startswith("description")
        # Values from mocked AI response
        assert data["parameters"].get("cfg_scale") == 7.0
        assert data["parameters"].get("steps") == 25
        assert data["parameters"].get("clip_skip") == 2


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_source(self, client):
        """Should return 400 for invalid source type."""
        response = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "invalid_source"},
        )

        assert response.status_code == 400
        assert "Invalid source" in response.json()["detail"]

    def test_pack_not_found(self, client, mock_store):
        """Should return 400 when pack not found."""
        from src.store.layout import PackNotFoundError
        mock_store.get_pack.side_effect = PackNotFoundError("Pack not found")

        response = client.post(
            "/api/packs/nonexistent-pack/parameters/extract",
            json={"source": "aggregated"},
        )

        assert response.status_code == 400


# =============================================================================
# Integration Tests
# =============================================================================

class TestParameterExtractionIntegration:
    """Integration tests for parameter extraction flow."""

    def test_extract_and_normalize_flow(self, client):
        """Should extract, normalize, and return consistent format."""
        # Extract from image
        response1 = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "image", "image_index": 0},
        )

        # Extract aggregated
        response2 = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "aggregated"},
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Both should return normalized keys (snake_case)
        params1 = response1.json()["parameters"]
        params2 = response2.json()["parameters"]

        # Keys should be snake_case, not camelCase
        assert "cfg_scale" in params1
        assert "cfgScale" not in params1
        assert "clip_skip" in params1
        assert "clipSkip" not in params1

    def test_extract_values_are_typed(self, client):
        """Extracted values should have correct types."""
        response = client.post(
            "/api/packs/test-pack/parameters/extract",
            json={"source": "image", "image_index": 0},
        )

        params = response.json()["parameters"]

        # Numeric params should be numbers, not strings
        assert isinstance(params["cfg_scale"], (int, float))
        assert isinstance(params["steps"], int)
        assert isinstance(params["seed"], int)
        assert isinstance(params["clip_skip"], int)

        # String params should be strings
        assert isinstance(params["sampler"], str)
