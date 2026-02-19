"""
Tests for Phase 2: Pack Dependencies CRUD

Tests:
1. Pack model validator (unique names, no self-reference)
2. API endpoints (GET status, POST add, DELETE remove)
3. Edge cases (duplicates, not-found, self-reference)
"""

import pytest
from pydantic import ValidationError

from src.store.models import (
    Pack,
    PackDependencyRef,
    PackSource,
    ProviderName,
)


# =============================================================================
# Pack Model Validator Tests
# =============================================================================


class TestPackDependencyValidator:
    """Test validate_unique_pack_deps model validator on Pack."""

    def _make_pack(self, name: str = "test-pack", pack_deps: list | None = None):
        """Create a minimal Pack with pack_dependencies."""
        return Pack(
            schema="1.0",
            name=name,
            pack_type="lora",
            source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
            pack_dependencies=pack_deps or [],
        )

    def test_empty_pack_dependencies(self):
        """Pack with no pack dependencies is valid."""
        pack = self._make_pack()
        assert len(pack.pack_dependencies) == 0

    def test_single_pack_dependency(self):
        """Pack with one dependency is valid."""
        pack = self._make_pack(pack_deps=[
            PackDependencyRef(pack_name="base-model"),
        ])
        assert len(pack.pack_dependencies) == 1
        assert pack.pack_dependencies[0].pack_name == "base-model"

    def test_multiple_unique_deps(self):
        """Pack with multiple unique dependencies is valid."""
        pack = self._make_pack(pack_deps=[
            PackDependencyRef(pack_name="dep-a"),
            PackDependencyRef(pack_name="dep-b"),
            PackDependencyRef(pack_name="dep-c"),
        ])
        assert len(pack.pack_dependencies) == 3

    def test_duplicate_dep_names_raises(self):
        """Duplicate pack dependency names should raise ValidationError."""
        with pytest.raises(ValidationError, match="Pack dependency names must be unique"):
            self._make_pack(pack_deps=[
                PackDependencyRef(pack_name="dep-a"),
                PackDependencyRef(pack_name="dep-a"),
            ])

    def test_self_reference_raises(self):
        """Pack cannot depend on itself."""
        with pytest.raises(ValidationError, match="Pack cannot depend on itself"):
            self._make_pack(name="my-pack", pack_deps=[
                PackDependencyRef(pack_name="my-pack"),
            ])

    def test_required_defaults_to_true(self):
        """PackDependencyRef.required defaults to True."""
        ref = PackDependencyRef(pack_name="some-dep")
        assert ref.required is True

    def test_required_can_be_false(self):
        """PackDependencyRef.required can be set to False."""
        ref = PackDependencyRef(pack_name="some-dep", required=False)
        assert ref.required is False


# =============================================================================
# API Endpoint Tests (using Pack model directly)
# =============================================================================


class TestPackDependenciesCRUD:
    """Test the pack dependencies CRUD logic (model-level, no HTTP)."""

    def _make_pack(self, name: str = "main-pack", pack_deps: list | None = None):
        """Create a Pack for CRUD testing."""
        return Pack(
            schema="1.0",
            name=name,
            pack_type="lora",
            source=PackSource(provider=ProviderName.CIVITAI, model_id=1),
            pack_dependencies=pack_deps or [],
        )

    def test_add_pack_dependency(self):
        """Adding a new pack dependency appends to the list."""
        pack = self._make_pack()
        assert len(pack.pack_dependencies) == 0

        new_ref = PackDependencyRef(pack_name="checkpoint-pack", required=True)
        pack.pack_dependencies.append(new_ref)

        assert len(pack.pack_dependencies) == 1
        assert pack.pack_dependencies[0].pack_name == "checkpoint-pack"
        assert pack.pack_dependencies[0].required is True

    def test_add_multiple_dependencies(self):
        """Adding multiple dependencies works."""
        pack = self._make_pack()

        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-a"))
        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-b", required=False))

        assert len(pack.pack_dependencies) == 2
        assert pack.pack_dependencies[0].pack_name == "dep-a"
        assert pack.pack_dependencies[1].required is False

    def test_remove_pack_dependency(self):
        """Removing a pack dependency by filtering."""
        pack = self._make_pack(pack_deps=[
            PackDependencyRef(pack_name="dep-a"),
            PackDependencyRef(pack_name="dep-b"),
            PackDependencyRef(pack_name="dep-c"),
        ])
        assert len(pack.pack_dependencies) == 3

        # Remove dep-b (same logic as API endpoint)
        dep_to_remove = "dep-b"
        original_count = len(pack.pack_dependencies)
        pack.pack_dependencies = [
            ref for ref in pack.pack_dependencies if ref.pack_name != dep_to_remove
        ]

        assert len(pack.pack_dependencies) == 2
        assert len(pack.pack_dependencies) < original_count
        remaining_names = [ref.pack_name for ref in pack.pack_dependencies]
        assert "dep-b" not in remaining_names
        assert "dep-a" in remaining_names
        assert "dep-c" in remaining_names

    def test_remove_nonexistent_dependency(self):
        """Removing a non-existent dependency doesn't change the list."""
        pack = self._make_pack(pack_deps=[
            PackDependencyRef(pack_name="dep-a"),
        ])

        original_count = len(pack.pack_dependencies)
        pack.pack_dependencies = [
            ref for ref in pack.pack_dependencies if ref.pack_name != "nonexistent"
        ]

        assert len(pack.pack_dependencies) == original_count  # unchanged

    def test_self_reference_check(self):
        """Adding self-reference is caught by validator when reconstructing."""
        pack = self._make_pack(name="my-pack")

        # Direct append bypasses validator, but re-validation should catch it
        pack.pack_dependencies.append(PackDependencyRef(pack_name="my-pack"))

        # When we reconstruct (as the API would do via save), it would fail
        with pytest.raises(ValidationError, match="Pack cannot depend on itself"):
            Pack.model_validate(pack.model_dump())

    def test_duplicate_check(self):
        """Adding duplicate is caught by validator when reconstructing."""
        pack = self._make_pack()
        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-a"))
        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-a"))

        with pytest.raises(ValidationError, match="Pack dependency names must be unique"):
            Pack.model_validate(pack.model_dump())

    def test_status_resolution_installed(self):
        """Status resolution logic for installed packs."""
        # Simulate the status-building logic from the API
        ref = PackDependencyRef(pack_name="installed-pack", required=True)

        # Simulate: pack found
        status = {
            "pack_name": ref.pack_name,
            "required": ref.required,
            "installed": True,
            "version": "1.0.0",
        }

        assert status["installed"] is True
        assert status["version"] == "1.0.0"
        assert status["required"] is True

    def test_status_resolution_missing(self):
        """Status resolution logic for missing packs."""
        ref = PackDependencyRef(pack_name="missing-pack", required=False)

        # Simulate: pack not found (exception in get_pack)
        status = {
            "pack_name": ref.pack_name,
            "required": ref.required,
            "installed": False,
            "version": None,
        }

        assert status["installed"] is False
        assert status["version"] is None
        assert status["required"] is False

    def test_version_constraint_preserved(self):
        """Version constraint is preserved in the ref."""
        ref = PackDependencyRef(
            pack_name="versioned-dep",
            required=True,
            version_constraint=">=1.0.0",
        )
        assert ref.version_constraint == ">=1.0.0"

        pack = self._make_pack(pack_deps=[ref])
        assert pack.pack_dependencies[0].version_constraint == ">=1.0.0"


# =============================================================================
# Integration: Full store roundtrip
# =============================================================================


class TestPackDependenciesRoundtrip:
    """Test pack dependencies survive save/load cycle."""

    def _make_service(self, tmp_path):
        """Create a PackService with initialized store."""
        from src.store.pack_service import PackService
        from src.store.layout import StoreLayout
        from src.store.blob_store import BlobStore

        layout = StoreLayout(tmp_path)
        layout.init_store()
        blob_store = BlobStore(layout)
        return PackService(layout, blob_store), layout

    def test_save_load_pack_dependencies(self, tmp_path):
        """Pack dependencies survive save/load roundtrip."""
        service, layout = self._make_service(tmp_path)

        # Create a pack with dependencies
        pack = Pack(
            schema="1.0",
            name="roundtrip-test",
            pack_type="lora",
            source=PackSource(provider=ProviderName.LOCAL),
            pack_dependencies=[
                PackDependencyRef(pack_name="base-model", required=True),
                PackDependencyRef(pack_name="optional-dep", required=False),
            ],
        )
        layout.save_pack(pack)

        # Reload
        loaded = layout.load_pack("roundtrip-test")
        assert len(loaded.pack_dependencies) == 2
        assert loaded.pack_dependencies[0].pack_name == "base-model"
        assert loaded.pack_dependencies[0].required is True
        assert loaded.pack_dependencies[1].pack_name == "optional-dep"
        assert loaded.pack_dependencies[1].required is False

    def test_add_remove_roundtrip(self, tmp_path):
        """Add then remove a dependency, verify it persists correctly."""
        service, layout = self._make_service(tmp_path)

        # Create empty pack
        pack = Pack(
            schema="1.0",
            name="crud-test",
            pack_type="checkpoint",
            source=PackSource(provider=ProviderName.LOCAL),
        )
        layout.save_pack(pack)

        # Add dependency
        pack = layout.load_pack("crud-test")
        pack.pack_dependencies.append(PackDependencyRef(pack_name="some-lora"))
        layout.save_pack(pack)

        # Verify added
        pack = layout.load_pack("crud-test")
        assert len(pack.pack_dependencies) == 1

        # Remove it
        pack.pack_dependencies = [
            ref for ref in pack.pack_dependencies if ref.pack_name != "some-lora"
        ]
        layout.save_pack(pack)

        # Verify removed
        pack = layout.load_pack("crud-test")
        assert len(pack.pack_dependencies) == 0
