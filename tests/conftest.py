"""
Pytest Configuration and Global Fixtures.

This file is automatically loaded by pytest and provides:
- Shared fixtures available to all tests
- Pytest markers configuration
- Common test utilities

Author: Synapse Team
License: MIT
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Generator, Any

import pytest

# Ensure src/ is in Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# Re-export fixtures from helpers module
# =============================================================================

from tests.helpers.fixtures import (
    # Classes
    FakeCivitaiClient,
    FakeModel,
    FakeModelVersion,
    FakeFile,
    TestStoreContext,
    # Functions
    create_test_blob,
    compute_sha256_from_content,
    build_test_model,
    # Assertions
    assert_blob_exists,
    assert_blob_not_exists,
    assert_symlink_points_to,
    assert_active_points_to_profile,
    assert_pack_in_profile,
    assert_pack_not_in_profile,
    # Snapshot utilities
    normalize_report,
    compare_reports,
)


# =============================================================================
# Pytest Markers
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests requiring multiple components or external services"
    )
    config.addinivalue_line(
        "markers", "e2e: marks end-to-end tests requiring full system"
    )
    config.addinivalue_line(
        "markers", "civitai: marks tests involving Civitai API"
    )
    config.addinivalue_line(
        "markers", "database: marks tests requiring database setup"
    )


# =============================================================================
# Session-Scoped Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def src_root(project_root: Path) -> Path:
    """Return the src/ directory."""
    return project_root / "src"


# =============================================================================
# Function-Scoped Fixtures
# =============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test isolation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def fake_civitai_client() -> FakeCivitaiClient:
    """Create a fresh FakeCivitaiClient instance."""
    return FakeCivitaiClient()


@pytest.fixture
def test_store_context(fake_civitai_client: FakeCivitaiClient) -> Generator[TestStoreContext, None, None]:
    """Create an isolated test store context."""
    with TestStoreContext(civitai_client=fake_civitai_client) as ctx:
        yield ctx


@pytest.fixture
def sample_model(fake_civitai_client: FakeCivitaiClient) -> FakeModel:
    """Create and register a sample test model."""
    model = build_test_model(
        model_id=12345,
        version_id=67890,
        name="TestModel",
        model_type="LORA",
    )
    fake_civitai_client.add_model(model)
    return model


# =============================================================================
# Media Detection Fixtures
# =============================================================================

@pytest.fixture
def civitai_video_url() -> str:
    """Sample Civitai video URL."""
    return "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123/width=450/video.mp4"


@pytest.fixture
def civitai_image_url() -> str:
    """Sample Civitai image URL."""
    return "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123/width=450/preview.jpeg"


@pytest.fixture
def standard_video_url() -> str:
    """Sample standard video URL."""
    return "https://example.com/videos/sample.mp4"


@pytest.fixture
def standard_image_url() -> str:
    """Sample standard image URL."""
    return "https://example.com/images/sample.jpg"


# =============================================================================
# API Test Fixtures
# =============================================================================

@pytest.fixture
def api_test_client():
    """Create FastAPI TestClient for API testing."""
    try:
        from fastapi.testclient import TestClient
        from src.store.api import app
        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI test client not available")


# =============================================================================
# Collection Hooks
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests based on their location.

    - tests/integration/* -> @pytest.mark.integration
    - tests/e2e/* -> @pytest.mark.e2e
    """
    for item in items:
        # Get relative path
        rel_path = Path(item.fspath).relative_to(Path(__file__).parent)
        parts = rel_path.parts

        # Auto-mark based on directory
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
        elif "e2e" in parts:
            item.add_marker(pytest.mark.e2e)
