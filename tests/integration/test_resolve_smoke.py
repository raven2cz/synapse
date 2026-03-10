"""
Smoke tests — full resolve lifecycle with real Store (tmp_path).

Tests the complete suggest/auto-apply flow as it runs during import,
using real Store + mock deps.
"""

import pytest
from unittest.mock import MagicMock

from src.store.models import (
    DependencySelector,
    SelectorStrategy,
    ResolveConfig,
)


# --- Fixtures ---

@pytest.fixture
def minimal_store(tmp_path):
    """Create a minimal Store with real layout for resolve testing."""
    from src.store import Store
    store = Store(root=tmp_path)
    return store


# =============================================================================
# Auto-apply flow
# =============================================================================

class TestAutoApplyFlow:
    """Smoke: _post_import_resolve auto-applies dominant candidates."""

    def test_post_import_resolve_with_no_deps(self, minimal_store):
        """Pack with no dependencies should not crash."""
        pack = MagicMock()
        pack.name = "empty-pack"
        pack.dependencies = []

        minimal_store._post_import_resolve(pack)

    def test_post_import_resolve_skips_pinned_deps(self, minimal_store):
        """Dependencies with non-BASE_MODEL_HINT strategy are skipped."""
        dep = MagicMock()
        dep.id = "dep-1"
        dep.selector = DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE)

        pack = MagicMock()
        pack.name = "pinned-pack"
        pack.dependencies = [dep]
        pack.previews = []

        # Should complete without errors — pinned deps are skipped
        minimal_store._post_import_resolve(pack)


# =============================================================================
# Migration helper
# =============================================================================

class TestMigrationHelper:
    """Smoke: migrate_resolve_deps iterates packs and reports actions."""

    def test_migrate_dry_run_empty_store(self, minimal_store):
        """Empty store → empty results."""
        results = minimal_store.migrate_resolve_deps(dry_run=True)
        assert results == []

    def test_migrate_reports_errors_gracefully(self, minimal_store):
        """Broken pack should be skipped, not crash migration."""
        minimal_store.list_packs = lambda: ["broken-pack"]
        minimal_store.get_pack = MagicMock(side_effect=Exception("corrupt"))

        results = minimal_store.migrate_resolve_deps(dry_run=True)
        assert results == []


# =============================================================================
# Config integration
# =============================================================================

class TestConfigInStore:
    """Smoke: Store uses config for resolve settings."""

    def test_try_load_config_graceful(self, minimal_store):
        """_try_load_config should not crash even if config missing."""
        # May return None (no config.json) or config object — either is fine
        config = minimal_store._try_load_config()
        # Just verify it doesn't raise
        assert config is None or hasattr(config, "resolve")

    def test_resolve_config_defaults(self):
        """ResolveConfig model should have correct defaults."""
        rc = ResolveConfig()
        assert rc.auto_apply_margin == 0.15
        assert rc.enable_ai is True


# =============================================================================
# Resolve service wiring
# =============================================================================

class TestResolveServiceWiring:
    """Smoke: ResolveService is properly wired in Store."""

    def test_resolve_service_exists(self, minimal_store):
        assert hasattr(minimal_store, "resolve_service")
        assert minimal_store.resolve_service is not None

    def test_resolve_service_has_config_getter(self, minimal_store):
        assert minimal_store.resolve_service._config_getter is not None

    def test_suggest_on_missing_dep(self, minimal_store):
        """Suggest for nonexistent dep returns empty with warning."""
        pack = MagicMock()
        pack.dependencies = []
        result = minimal_store.resolve_service.suggest(pack, "nonexistent")
        assert result.candidates == []
        assert any("not found" in w.lower() for w in result.warnings)

    def test_apply_resolution_method(self, minimal_store):
        """Store.apply_resolution delegates to resolve_service."""
        assert hasattr(minimal_store, "apply_resolution")
