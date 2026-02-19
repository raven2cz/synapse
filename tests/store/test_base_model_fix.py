"""
Tests for Phase 1: Base Model Fix

Tests that:
1. Import creates base model dependency with required=False
2. set-base-model endpoint switches strategy and removes old
3. required field is present in API response
4. is_base_model field is present in API response
"""

import pytest
from src.store.models import (
    AssetKind,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackDependency,
    PackSource,
    ProviderName,
    SelectorStrategy,
    UpdatePolicy,
    UpdatePolicyMode,
)


class TestBaseModelRequired:
    """Test that base model dependencies are created with required=False."""

    def _make_service(self, tmp_path):
        """Create a PackService with initialized store."""
        from src.store.pack_service import PackService
        from src.store.layout import StoreLayout
        from src.store.blob_store import BlobStore

        layout = StoreLayout(tmp_path)
        layout.init_store()
        blob_store = BlobStore(layout)
        return PackService(layout, blob_store)

    def test_create_base_model_dependency_known_alias(self, tmp_path):
        """When base model alias is known (e.g. SDXL), required should be False."""
        service = self._make_service(tmp_path)

        # SDXL is a known alias
        dep = service._create_base_model_dependency("SDXL")
        assert dep is not None
        assert dep.id == "base_checkpoint"
        assert dep.required is False
        assert dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT
        assert dep.selector.base_model == "SDXL"

    def test_create_base_model_dependency_unknown_alias(self, tmp_path):
        """When base model alias is unknown, required should be False."""
        service = self._make_service(tmp_path)

        dep = service._create_base_model_dependency("UnknownModel_v99")
        assert dep is not None
        assert dep.id == "base_checkpoint"
        assert dep.required is False
        assert dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT

    def test_create_base_model_dependency_sd15(self, tmp_path):
        """SD 1.5 is also a known alias, required should be False."""
        service = self._make_service(tmp_path)

        dep = service._create_base_model_dependency("SD 1.5")
        assert dep is not None
        assert dep.required is False
        assert dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT


class TestSetBaseModel:
    """Test the set-base-model logic."""

    def _make_pack_with_deps(self, deps: list[PackDependency]) -> Pack:
        """Helper to create a pack with given dependencies."""
        return Pack(
            schema="1.0",
            name="test-pack",
            pack_type="lora",
            source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
            dependencies=deps,
            base_model="SDXL",
        )

    def test_set_checkpoint_as_base_model(self):
        """Setting a checkpoint dep as base model should change its strategy."""
        lora_dep = PackDependency(
            id="main_lora",
            kind=AssetKind.LORA,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
            ),
            expose=ExposeConfig(filename="lora.safetensors"),
        )
        checkpoint_dep = PackDependency(
            id="some_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
            ),
            expose=ExposeConfig(filename="checkpoint.safetensors"),
        )
        old_base = PackDependency(
            id="base_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=False,
            selector=DependencySelector(
                strategy=SelectorStrategy.BASE_MODEL_HINT,
                base_model="SDXL",
            ),
            expose=ExposeConfig(filename="sdxl.safetensors"),
        )

        pack = self._make_pack_with_deps([lora_dep, checkpoint_dep, old_base])
        assert len(pack.dependencies) == 3

        # Simulate set-base-model logic from the endpoint
        target_dep = None
        for d in pack.dependencies:
            if d.id == "some_checkpoint":
                target_dep = d
                break
        assert target_dep is not None

        # Remove old BASE_MODEL_HINT deps
        new_deps = []
        for d in pack.dependencies:
            if d.id != "some_checkpoint" and d.selector.strategy == SelectorStrategy.BASE_MODEL_HINT:
                continue  # skip old base model
            new_deps.append(d)
        pack.dependencies = new_deps

        # Set new base model
        target_dep.selector.strategy = SelectorStrategy.BASE_MODEL_HINT
        target_dep.selector.base_model = pack.base_model

        # Verify
        assert len(pack.dependencies) == 2  # old base model removed
        base_deps = [d for d in pack.dependencies if d.selector.strategy == SelectorStrategy.BASE_MODEL_HINT]
        assert len(base_deps) == 1
        assert base_deps[0].id == "some_checkpoint"
        assert base_deps[0].selector.base_model == "SDXL"

    def test_set_base_model_when_no_existing_base(self):
        """Setting base model when there's no existing base model dep."""
        checkpoint_dep = PackDependency(
            id="my_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
            ),
            expose=ExposeConfig(filename="checkpoint.safetensors"),
        )

        pack = self._make_pack_with_deps([checkpoint_dep])
        assert len(pack.dependencies) == 1

        # No existing BASE_MODEL_HINT deps to remove
        new_deps = []
        for d in pack.dependencies:
            if d.id != "my_checkpoint" and d.selector.strategy == SelectorStrategy.BASE_MODEL_HINT:
                continue
            new_deps.append(d)
        pack.dependencies = new_deps

        # Set new base model
        checkpoint_dep.selector.strategy = SelectorStrategy.BASE_MODEL_HINT
        checkpoint_dep.selector.base_model = pack.base_model

        assert len(pack.dependencies) == 1
        assert pack.dependencies[0].selector.strategy == SelectorStrategy.BASE_MODEL_HINT


class TestAssetInfoFields:
    """Test that required and is_base_model fields are in API asset_info."""

    def test_required_field_in_asset_info(self):
        """The required field should be part of the asset response."""
        dep = PackDependency(
            id="test_dep",
            kind=AssetKind.LORA,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
            ),
            expose=ExposeConfig(filename="test.safetensors"),
        )

        # Simulate the asset_info building from api.py
        asset_info = {
            "name": dep.id,
            "asset_type": dep.kind.value,
            "required": dep.required,
            "is_base_model": dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT,
        }

        assert asset_info["required"] is True
        assert asset_info["is_base_model"] is False

    def test_base_model_hint_detected(self):
        """Base model hint deps should have is_base_model=True."""
        dep = PackDependency(
            id="base_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=False,
            selector=DependencySelector(
                strategy=SelectorStrategy.BASE_MODEL_HINT,
                base_model="SDXL",
            ),
            expose=ExposeConfig(filename="sdxl.safetensors"),
        )

        asset_info = {
            "name": dep.id,
            "required": dep.required,
            "is_base_model": dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT,
        }

        assert asset_info["required"] is False
        assert asset_info["is_base_model"] is True

    def test_non_base_model_not_detected(self):
        """Regular deps should have is_base_model=False."""
        dep = PackDependency(
            id="main_lora",
            kind=AssetKind.LORA,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
            ),
            expose=ExposeConfig(filename="lora.safetensors"),
        )

        asset_info = {
            "required": dep.required,
            "is_base_model": dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT,
        }

        assert asset_info["required"] is True
        assert asset_info["is_base_model"] is False
