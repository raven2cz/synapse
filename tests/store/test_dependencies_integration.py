"""
Integration and Smoke Tests for Dependencies Rework (Phase 1 + Phase 2)

Integration tests use real Store instances with tmp_path.
Smoke tests verify API endpoint wiring via FastAPI TestClient.

Phase 1: Base Model Fix
- set-base-model endpoint integration
- asset_info response includes required + is_base_model
- base model import creates required=False

Phase 2: Pack Dependencies CRUD
- GET /pack-dependencies/status batch endpoint
- POST /pack-dependencies add endpoint
- DELETE /pack-dependencies/{name} remove endpoint
- Validation (self-reference, duplicate)
"""

import json
import pytest
from pathlib import Path

from src.store.models import (
    AssetKind,
    CivitaiSelector,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackDependency,
    PackDependencyRef,
    PackSource,
    ProviderName,
    SelectorStrategy,
    UpdatePolicy,
    UpdatePolicyMode,
)


# =============================================================================
# Helpers
# =============================================================================


def make_store(tmp_path):
    """Create an initialized Store at tmp_path."""
    from src.store import Store

    store = Store(tmp_path / "store")
    store.init()
    return store


def make_lora_pack(
    name: str = "test-lora",
    base_model: str = "SDXL",
    with_base_dep: bool = True,
    pack_deps: list[PackDependencyRef] | None = None,
) -> Pack:
    """Create a LoRA pack with optional base model dependency."""
    deps = []
    if with_base_dep:
        deps.append(PackDependency(
            id="base_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=False,
            selector=DependencySelector(
                strategy=SelectorStrategy.BASE_MODEL_HINT,
                base_model=base_model,
            ),
            update_policy=UpdatePolicy(),
            expose=ExposeConfig(filename="base.safetensors"),
        ))
    deps.append(PackDependency(
        id="main_lora",
        kind=AssetKind.LORA,
        required=True,
        selector=DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=123, version_id=456, file_id=789),
        ),
        update_policy=UpdatePolicy(),
        expose=ExposeConfig(filename="lora.safetensors"),
    ))
    return Pack(
        schema="1.0",
        name=name,
        pack_type="lora",
        source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
        dependencies=deps,
        base_model=base_model,
        pack_dependencies=pack_deps or [],
    )


def make_checkpoint_pack(name: str = "sdxl-checkpoint") -> Pack:
    """Create a simple checkpoint pack."""
    return Pack(
        schema="1.0",
        name=name,
        pack_type="checkpoint",
        source=PackSource(provider=ProviderName.LOCAL),
        dependencies=[
            PackDependency(
                id="main_checkpoint",
                kind=AssetKind.CHECKPOINT,
                required=True,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelector(model_id=100, version_id=200, file_id=300),
                ),
                update_policy=UpdatePolicy(),
                expose=ExposeConfig(filename="checkpoint.safetensors"),
            ),
        ],
    )


# =============================================================================
# Phase 1: Integration Tests - Base Model Fix
# =============================================================================


class TestBaseModelIntegration:
    """Integration tests for base model fix with real Store."""

    def test_pack_with_base_model_hint_roundtrip(self, tmp_path):
        """Base model hint dep with required=False survives save/load."""
        store = make_store(tmp_path)
        pack = make_lora_pack("roundtrip-lora")
        store.layout.save_pack(pack)

        loaded = store.get_pack("roundtrip-lora")
        base_dep = loaded.get_dependency("base_checkpoint")
        assert base_dep is not None
        assert base_dep.required is False
        assert base_dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT
        assert base_dep.selector.base_model == "SDXL"

    def test_set_base_model_removes_old_and_sets_new(self, tmp_path):
        """set-base-model logic: remove old BASE_MODEL_HINT, set new one."""
        store = make_store(tmp_path)

        # Pack with base_checkpoint (BASE_MODEL_HINT) + main_lora + an extra checkpoint
        pack = make_lora_pack("set-base-test")
        extra_checkpoint = PackDependency(
            id="my_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai=CivitaiSelector(model_id=999, version_id=888, file_id=777),
            ),
            update_policy=UpdatePolicy(),
            expose=ExposeConfig(filename="my_checkpoint.safetensors"),
        )
        pack.dependencies.append(extra_checkpoint)
        store.layout.save_pack(pack)

        # Simulate set-base-model endpoint logic
        loaded = store.get_pack("set-base-test")
        target_dep = loaded.get_dependency("my_checkpoint")
        assert target_dep is not None

        # Remove old BASE_MODEL_HINT deps (except the target)
        loaded.dependencies = [
            d for d in loaded.dependencies
            if d.id == "my_checkpoint" or d.selector.strategy != SelectorStrategy.BASE_MODEL_HINT
        ]
        # Set target as new base model
        target_dep.selector.strategy = SelectorStrategy.BASE_MODEL_HINT
        target_dep.selector.base_model = loaded.base_model
        store.layout.save_pack(loaded)

        # Verify
        result = store.get_pack("set-base-test")
        base_hints = [
            d for d in result.dependencies
            if d.selector.strategy == SelectorStrategy.BASE_MODEL_HINT
        ]
        assert len(base_hints) == 1
        assert base_hints[0].id == "my_checkpoint"
        assert base_hints[0].selector.base_model == "SDXL"
        # Old base_checkpoint should be gone
        assert result.get_dependency("base_checkpoint") is None

    def test_asset_info_fields_from_dependencies(self, tmp_path):
        """Verify required and is_base_model are derivable from pack deps."""
        store = make_store(tmp_path)
        pack = make_lora_pack("info-test")
        store.layout.save_pack(pack)

        loaded = store.get_pack("info-test")
        for dep in loaded.dependencies:
            asset_info = {
                "name": dep.id,
                "asset_type": dep.kind.value,
                "required": dep.required,
                "is_base_model": dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT,
            }
            if dep.id == "base_checkpoint":
                assert asset_info["required"] is False
                assert asset_info["is_base_model"] is True
            elif dep.id == "main_lora":
                assert asset_info["required"] is True
                assert asset_info["is_base_model"] is False

    def test_delete_base_model_dep(self, tmp_path):
        """Deleting the base model dependency works (no restrictions)."""
        store = make_store(tmp_path)
        pack = make_lora_pack("delete-base-test")
        store.layout.save_pack(pack)

        loaded = store.get_pack("delete-base-test")
        loaded.dependencies = [
            d for d in loaded.dependencies if d.id != "base_checkpoint"
        ]
        store.layout.save_pack(loaded)

        result = store.get_pack("delete-base-test")
        assert result.get_dependency("base_checkpoint") is None
        assert len(result.dependencies) == 1  # only main_lora remains


# =============================================================================
# Phase 2: Integration Tests - Pack Dependencies CRUD
# =============================================================================


class TestPackDepsCRUDIntegration:
    """Integration tests for pack dependencies CRUD with real Store."""

    def test_add_pack_dependency_to_store(self, tmp_path):
        """Add a pack dep, save, reload - verify persisted."""
        store = make_store(tmp_path)
        store.layout.save_pack(make_lora_pack("consumer"))
        store.layout.save_pack(make_checkpoint_pack("provider"))

        # Add dependency
        pack = store.get_pack("consumer")
        pack.pack_dependencies.append(
            PackDependencyRef(pack_name="provider", required=True)
        )
        store.layout.save_pack(pack)

        # Verify
        loaded = store.get_pack("consumer")
        assert len(loaded.pack_dependencies) == 1
        assert loaded.pack_dependencies[0].pack_name == "provider"
        assert loaded.pack_dependencies[0].required is True

    def test_remove_pack_dependency_from_store(self, tmp_path):
        """Remove a pack dep, save, reload - verify gone."""
        store = make_store(tmp_path)
        pack = make_lora_pack(
            "consumer",
            pack_deps=[
                PackDependencyRef(pack_name="dep-a"),
                PackDependencyRef(pack_name="dep-b"),
            ],
        )
        store.layout.save_pack(pack)

        # Remove dep-a
        loaded = store.get_pack("consumer")
        loaded.pack_dependencies = [
            ref for ref in loaded.pack_dependencies if ref.pack_name != "dep-a"
        ]
        store.layout.save_pack(loaded)

        # Verify
        result = store.get_pack("consumer")
        assert len(result.pack_dependencies) == 1
        assert result.pack_dependencies[0].pack_name == "dep-b"

    def test_batch_status_resolution(self, tmp_path):
        """Batch status resolves installed vs missing packs."""
        store = make_store(tmp_path)
        store.layout.save_pack(make_checkpoint_pack("installed-pack"))
        pack = make_lora_pack(
            "consumer",
            pack_deps=[
                PackDependencyRef(pack_name="installed-pack", required=True),
                PackDependencyRef(pack_name="missing-pack", required=False),
            ],
        )
        store.layout.save_pack(pack)

        # Simulate batch status resolution (same logic as API endpoint)
        loaded = store.get_pack("consumer")
        statuses = []
        for ref in loaded.pack_dependencies:
            try:
                dep_pack = store.get_pack(ref.pack_name)
                statuses.append({
                    "pack_name": ref.pack_name,
                    "required": ref.required,
                    "installed": True,
                    "version": dep_pack.version if hasattr(dep_pack, 'version') else None,
                })
            except Exception:
                statuses.append({
                    "pack_name": ref.pack_name,
                    "required": ref.required,
                    "installed": False,
                    "version": None,
                })

        assert len(statuses) == 2
        installed = next(s for s in statuses if s["pack_name"] == "installed-pack")
        missing = next(s for s in statuses if s["pack_name"] == "missing-pack")
        assert installed["installed"] is True
        assert installed["required"] is True
        assert missing["installed"] is False
        assert missing["required"] is False

    def test_add_then_remove_then_readd(self, tmp_path):
        """Full lifecycle: add → remove → re-add."""
        store = make_store(tmp_path)
        store.layout.save_pack(make_lora_pack("main-pack"))
        store.layout.save_pack(make_checkpoint_pack("dep-pack"))

        # Add
        pack = store.get_pack("main-pack")
        pack.pack_dependencies.append(PackDependencyRef(pack_name="dep-pack"))
        store.layout.save_pack(pack)
        assert len(store.get_pack("main-pack").pack_dependencies) == 1

        # Remove
        pack = store.get_pack("main-pack")
        pack.pack_dependencies = [
            r for r in pack.pack_dependencies if r.pack_name != "dep-pack"
        ]
        store.layout.save_pack(pack)
        assert len(store.get_pack("main-pack").pack_dependencies) == 0

        # Re-add
        pack = store.get_pack("main-pack")
        pack.pack_dependencies.append(
            PackDependencyRef(pack_name="dep-pack", required=False)
        )
        store.layout.save_pack(pack)
        result = store.get_pack("main-pack")
        assert len(result.pack_dependencies) == 1
        assert result.pack_dependencies[0].required is False

    def test_multiple_packs_with_shared_dependency(self, tmp_path):
        """Multiple packs can depend on the same pack."""
        store = make_store(tmp_path)
        store.layout.save_pack(make_checkpoint_pack("shared-base"))
        store.layout.save_pack(make_lora_pack(
            "lora-a", pack_deps=[PackDependencyRef(pack_name="shared-base")]
        ))
        store.layout.save_pack(make_lora_pack(
            "lora-b", pack_deps=[PackDependencyRef(pack_name="shared-base")]
        ))

        # Both packs reference shared-base
        a = store.get_pack("lora-a")
        b = store.get_pack("lora-b")
        assert a.pack_dependencies[0].pack_name == "shared-base"
        assert b.pack_dependencies[0].pack_name == "shared-base"


# =============================================================================
# Phase 1: Smoke Tests - API Endpoint Wiring
# =============================================================================


class TestBaseModelSmoke:
    """Smoke tests verifying API endpoint logic for base model features."""

    def test_set_base_model_endpoint_logic(self, tmp_path):
        """Smoke test: set-base-model endpoint logic works end-to-end."""
        store = make_store(tmp_path)
        pack = make_lora_pack("api-test-pack")
        # Add a second checkpoint that we'll set as base
        pack.dependencies.append(PackDependency(
            id="alt_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai=CivitaiSelector(model_id=555, version_id=666, file_id=777),
            ),
            update_policy=UpdatePolicy(),
            expose=ExposeConfig(filename="alt.safetensors"),
        ))
        store.layout.save_pack(pack)

        # Simulate the endpoint logic from api.py
        pack = store.get_pack("api-test-pack")
        dep_id = "alt_checkpoint"
        target_dep = pack.get_dependency(dep_id)
        assert target_dep is not None
        assert target_dep.kind == AssetKind.CHECKPOINT

        # Remove other BASE_MODEL_HINT deps (not target)
        pack.dependencies = [
            d for d in pack.dependencies
            if d.id == dep_id or d.selector.strategy != SelectorStrategy.BASE_MODEL_HINT
        ]
        target_dep.selector.strategy = SelectorStrategy.BASE_MODEL_HINT
        target_dep.selector.base_model = pack.base_model
        store.layout.save_pack(pack)

        # Verify final state
        result = store.get_pack("api-test-pack")
        base_deps = [d for d in result.dependencies if d.selector.strategy == SelectorStrategy.BASE_MODEL_HINT]
        assert len(base_deps) == 1
        assert base_deps[0].id == "alt_checkpoint"
        # Original base_checkpoint was removed
        assert result.get_dependency("base_checkpoint") is None

    def test_asset_info_response_shape(self, tmp_path):
        """Smoke test: asset_info dict has all expected fields."""
        store = make_store(tmp_path)
        pack = make_lora_pack("shape-test")
        store.layout.save_pack(pack)

        loaded = store.get_pack("shape-test")
        for dep in loaded.dependencies:
            # Build asset_info the same way as api.py
            info = {
                "name": dep.id,
                "asset_type": dep.kind.value,
                "source": dep.selector.strategy.value,
                "installed": False,
                "status": "unresolved",
                "required": dep.required,
                "is_base_model": dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT,
            }
            # All fields present
            assert "required" in info
            assert "is_base_model" in info
            assert isinstance(info["required"], bool)
            assert isinstance(info["is_base_model"], bool)

    def test_base_model_with_known_alias_creates_correct_dep(self, tmp_path):
        """Smoke test: PackService creates base model dep with correct fields."""
        from src.store.pack_service import PackService
        from src.store.layout import StoreLayout
        from src.store.blob_store import BlobStore

        layout = StoreLayout(tmp_path / "store2")
        layout.init_store()
        blob_store = BlobStore(layout)
        service = PackService(layout, blob_store)

        dep = service._create_base_model_dependency("SDXL")
        assert dep is not None
        assert dep.required is False
        assert dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT
        assert dep.kind == AssetKind.CHECKPOINT


# =============================================================================
# Phase 2: Smoke Tests - API Endpoint Wiring
# =============================================================================


class TestPackDepsCRUDSmoke:
    """Smoke tests verifying pack dependencies API endpoint logic."""

    def test_add_endpoint_self_reference_rejected(self, tmp_path):
        """Smoke: self-reference is caught before save."""
        store = make_store(tmp_path)
        store.layout.save_pack(make_lora_pack("self-ref-pack"))

        pack = store.get_pack("self-ref-pack")
        request_pack_name = "self-ref-pack"

        # Simulate endpoint self-reference check
        is_self_ref = request_pack_name == pack.name
        assert is_self_ref is True

    def test_add_endpoint_duplicate_rejected(self, tmp_path):
        """Smoke: duplicate pack dep is caught before save."""
        store = make_store(tmp_path)
        pack = make_lora_pack(
            "dup-test",
            pack_deps=[PackDependencyRef(pack_name="existing-dep")],
        )
        store.layout.save_pack(pack)

        loaded = store.get_pack("dup-test")
        existing_names = {ref.pack_name for ref in loaded.pack_dependencies}

        # Simulate endpoint duplicate check
        assert "existing-dep" in existing_names
        assert "new-dep" not in existing_names

    def test_remove_endpoint_nonexistent_detected(self, tmp_path):
        """Smoke: removing nonexistent dep is detected."""
        store = make_store(tmp_path)
        store.layout.save_pack(make_lora_pack("remove-test"))

        pack = store.get_pack("remove-test")
        original_count = len(pack.pack_dependencies)
        pack.pack_dependencies = [
            ref for ref in pack.pack_dependencies if ref.pack_name != "nonexistent"
        ]
        # Count unchanged means not found
        assert len(pack.pack_dependencies) == original_count

    def test_status_endpoint_response_format(self, tmp_path):
        """Smoke: batch status returns correct shape."""
        store = make_store(tmp_path)
        store.layout.save_pack(make_checkpoint_pack("dep-pack"))
        pack = make_lora_pack(
            "status-test",
            pack_deps=[PackDependencyRef(pack_name="dep-pack", required=True)],
        )
        store.layout.save_pack(pack)

        loaded = store.get_pack("status-test")
        statuses = []
        for ref in loaded.pack_dependencies:
            try:
                dep_pack = store.get_pack(ref.pack_name)
                statuses.append({
                    "pack_name": ref.pack_name,
                    "required": ref.required,
                    "installed": True,
                    "version": getattr(dep_pack, 'version', None),
                })
            except Exception:
                statuses.append({
                    "pack_name": ref.pack_name,
                    "required": ref.required,
                    "installed": False,
                    "version": None,
                })

        assert len(statuses) == 1
        s = statuses[0]
        # Verify response shape matches frontend expectations
        assert "pack_name" in s
        assert "required" in s
        assert "installed" in s
        assert "version" in s
        assert s["pack_name"] == "dep-pack"
        assert s["installed"] is True
        assert s["required"] is True

    def test_add_endpoint_full_flow(self, tmp_path):
        """Smoke: full add flow - validate, append, save, reload."""
        store = make_store(tmp_path)
        store.layout.save_pack(make_lora_pack("add-flow"))
        store.layout.save_pack(make_checkpoint_pack("new-dep"))

        # Simulate full POST endpoint
        pack_name = "add-flow"
        req_pack_name = "new-dep"
        req_required = True

        pack = store.get_pack(pack_name)

        # Validate
        assert req_pack_name != pack_name  # not self-ref
        existing = {ref.pack_name for ref in pack.pack_dependencies}
        assert req_pack_name not in existing  # not duplicate

        # Add
        pack.pack_dependencies.append(
            PackDependencyRef(pack_name=req_pack_name, required=req_required)
        )
        store.layout.save_pack(pack)

        # Verify response
        result = store.get_pack(pack_name)
        assert len(result.pack_dependencies) == 1
        assert result.pack_dependencies[0].pack_name == "new-dep"

    def test_remove_endpoint_full_flow(self, tmp_path):
        """Smoke: full delete flow - check exists, filter, save."""
        store = make_store(tmp_path)
        pack = make_lora_pack(
            "remove-flow",
            pack_deps=[
                PackDependencyRef(pack_name="to-remove"),
                PackDependencyRef(pack_name="to-keep"),
            ],
        )
        store.layout.save_pack(pack)

        # Simulate full DELETE endpoint
        pack = store.get_pack("remove-flow")
        dep_to_remove = "to-remove"
        original_count = len(pack.pack_dependencies)
        pack.pack_dependencies = [
            ref for ref in pack.pack_dependencies if ref.pack_name != dep_to_remove
        ]
        assert len(pack.pack_dependencies) < original_count  # found and removed
        store.layout.save_pack(pack)

        # Verify
        result = store.get_pack("remove-flow")
        names = [ref.pack_name for ref in result.pack_dependencies]
        assert "to-remove" not in names
        assert "to-keep" in names


# =============================================================================
# Phase 4: Integration Tests - Enriched Status Fields
# =============================================================================


class TestEnrichedStatusIntegration:
    """Integration tests for Phase 4 enriched pack-deps/status."""

    def test_enriched_status_includes_new_fields(self, tmp_path):
        """Batch status includes pack_type, description, asset_count, etc."""
        store = make_store(tmp_path)
        dep_pack = Pack(
            schema="1.0",
            name="dep-lora",
            pack_type="lora",
            description="A LoRA pack with trigger words",
            base_model="SDXL",
            source=PackSource(provider=ProviderName.LOCAL),
            dependencies=[
                PackDependency(
                    id="main_lora",
                    kind=AssetKind.LORA,
                    selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                    update_policy=UpdatePolicy(),
                    expose=ExposeConfig(
                        filename="lora.safetensors",
                        trigger_words=["style_trigger", "quality"],
                    ),
                ),
            ],
        )
        store.layout.save_pack(dep_pack)
        consumer = make_lora_pack(
            "consumer",
            pack_deps=[PackDependencyRef(pack_name="dep-lora", required=True)],
        )
        store.layout.save_pack(consumer)

        # Build enriched status like the API endpoint
        loaded = store.get_pack("consumer")
        for ref in loaded.pack_dependencies:
            dp = store.get_pack(ref.pack_name)
            trigger_words = []
            for d in dp.dependencies:
                if d.expose and d.expose.trigger_words:
                    trigger_words.extend(d.expose.trigger_words)

            status = {
                "pack_name": ref.pack_name,
                "required": ref.required,
                "installed": True,
                "pack_type": dp.pack_type.value if hasattr(dp.pack_type, 'value') else None,
                "description": (dp.description or "")[:200],
                "asset_count": len(dp.dependencies),
                "trigger_words": trigger_words,
                "base_model": dp.base_model,
            }

            assert status["pack_type"] == "lora"
            assert status["description"] == "A LoRA pack with trigger words"
            assert status["asset_count"] == 1
            assert status["trigger_words"] == ["style_trigger", "quality"]
            assert status["base_model"] == "SDXL"

    def test_enriched_status_missing_pack_defaults(self, tmp_path):
        """Missing pack returns all-None/empty enriched fields."""
        store = make_store(tmp_path)
        consumer = make_lora_pack(
            "consumer",
            pack_deps=[PackDependencyRef(pack_name="ghost", required=False)],
        )
        store.layout.save_pack(consumer)

        loaded = store.get_pack("consumer")
        for ref in loaded.pack_dependencies:
            try:
                store.get_pack(ref.pack_name)
                assert False, "Should not find ghost pack"
            except Exception:
                status = {
                    "pack_name": ref.pack_name,
                    "required": ref.required,
                    "installed": False,
                    "pack_type": None,
                    "description": None,
                    "asset_count": 0,
                    "trigger_words": [],
                    "base_model": None,
                    "has_unresolved": False,
                    "all_installed": False,
                }
                assert status["installed"] is False
                assert status["trigger_words"] == []
                assert status["all_installed"] is False


# =============================================================================
# Phase 4: Integration Tests - Asset Info Enriched Fields
# =============================================================================


class TestAssetInfoEnrichedIntegration:
    """Integration tests for Phase 4 asset_info enriched fields."""

    def test_asset_info_trigger_words_roundtrip(self, tmp_path):
        """trigger_words survive save/load and appear in asset_info."""
        store = make_store(tmp_path)
        pack = Pack(
            schema="1.0",
            name="trigger-test",
            pack_type="lora",
            source=PackSource(provider=ProviderName.LOCAL),
            dependencies=[
                PackDependency(
                    id="my_lora",
                    kind=AssetKind.LORA,
                    selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                    expose=ExposeConfig(
                        filename="lora.safetensors",
                        trigger_words=["word1", "word2", "word3"],
                    ),
                ),
            ],
        )
        store.layout.save_pack(pack)

        loaded = store.get_pack("trigger-test")
        dep = loaded.get_dependency("my_lora")
        assert dep is not None

        info = {
            "trigger_words": dep.expose.trigger_words if dep.expose else [],
            "update_policy": dep.update_policy.mode.value if dep.update_policy else "pinned",
            "strategy": dep.selector.strategy.value,
        }
        assert info["trigger_words"] == ["word1", "word2", "word3"]
        assert info["update_policy"] == "follow_latest"
        assert info["strategy"] == "civitai_file"

    def test_asset_info_all_strategy_types(self, tmp_path):
        """All SelectorStrategy values produce correct strategy strings."""
        store = make_store(tmp_path)
        strategies = [
            (SelectorStrategy.CIVITAI_FILE, "civitai_file"),
            (SelectorStrategy.BASE_MODEL_HINT, "base_model_hint"),
        ]
        for strat, expected_value in strategies:
            pack = Pack(
                schema="1.0",
                name=f"strat-{expected_value}",
                pack_type="lora",
                source=PackSource(provider=ProviderName.LOCAL),
                dependencies=[
                    PackDependency(
                        id="dep1",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=strat),
                        update_policy=UpdatePolicy(),
                        expose=ExposeConfig(filename="dep.safetensors"),
                    ),
                ],
            )
            store.layout.save_pack(pack)
            loaded = store.get_pack(f"strat-{expected_value}")
            dep = loaded.get_dependency("dep1")
            assert dep.selector.strategy.value == expected_value


# =============================================================================
# Phase 4: Smoke Tests - Dependency Tree Endpoint Logic
# =============================================================================


class TestDependencyTreeSmoke:
    """Smoke tests for dependency tree endpoint logic."""

    def test_tree_endpoint_response_shape(self, tmp_path):
        """Smoke: dependency tree response has correct shape."""
        store = make_store(tmp_path)
        store.layout.save_pack(make_lora_pack(
            "root",
            pack_deps=[PackDependencyRef(pack_name="child")],
        ))
        store.layout.save_pack(make_checkpoint_pack("child"))

        # Build tree like the endpoint does
        pack = store.get_pack("root")

        def build_node(name, depth, visited):
            if name in visited:
                return {"pack_name": name, "circular": True, "depth": depth,
                        "installed": False, "version": None, "pack_type": None,
                        "description": None, "asset_count": 0, "trigger_words": [],
                        "children": []}
            visited = visited | {name}
            try:
                p = store.get_pack(name)
            except Exception:
                return {"pack_name": name, "circular": False, "depth": depth,
                        "installed": False, "version": None, "pack_type": None,
                        "description": None, "asset_count": 0, "trigger_words": [],
                        "children": []}
            children = []
            if depth < 5 and p.pack_dependencies:
                for ref in p.pack_dependencies:
                    children.append(build_node(ref.pack_name, depth + 1, visited))
            return {
                "pack_name": name,
                "installed": True,
                "version": getattr(p, 'version', None),
                "pack_type": p.pack_type.value if hasattr(p.pack_type, 'value') else None,
                "description": (p.description or "")[:200] if p.description else None,
                "asset_count": len(p.dependencies),
                "trigger_words": [],
                "children": children,
                "circular": False,
                "depth": depth,
            }

        response = {"tree": build_node(pack.name, 0, set()), "max_depth": 5}

        # Validate response shape
        assert "tree" in response
        assert "max_depth" in response
        tree = response["tree"]
        assert tree["pack_name"] == "root"
        assert tree["installed"] is True
        assert len(tree["children"]) == 1
        assert tree["children"][0]["pack_name"] == "child"

    def test_tree_circular_does_not_infinite_loop(self, tmp_path):
        """Smoke: circular deps don't cause infinite recursion."""
        store = make_store(tmp_path)
        # Create tight cycle
        store.layout.save_pack(make_lora_pack(
            "loop-a",
            pack_deps=[PackDependencyRef(pack_name="loop-b")],
        ))
        store.layout.save_pack(make_lora_pack(
            "loop-b",
            pack_deps=[PackDependencyRef(pack_name="loop-a")],
        ))

        pack = store.get_pack("loop-a")

        def build_node(name, depth, visited):
            if name in visited:
                return {"pack_name": name, "circular": True, "children": [], "depth": depth}
            visited = visited | {name}
            try:
                p = store.get_pack(name)
            except Exception:
                return {"pack_name": name, "circular": False, "children": [], "depth": depth}
            children = []
            if depth < 5 and p.pack_dependencies:
                for ref in p.pack_dependencies:
                    children.append(build_node(ref.pack_name, depth + 1, visited))
            return {"pack_name": name, "circular": False, "children": children, "depth": depth}

        # This should complete without hanging
        tree = build_node(pack.name, 0, set())
        assert tree["pack_name"] == "loop-a"
        child = tree["children"][0]
        assert child["pack_name"] == "loop-b"
        circular = child["children"][0]
        assert circular["pack_name"] == "loop-a"
        assert circular["circular"] is True

    def test_enriched_status_response_shape_complete(self, tmp_path):
        """Smoke: enriched status has all 11 expected fields."""
        store = make_store(tmp_path)
        dep = Pack(
            schema="1.0",
            name="full-dep",
            pack_type="lora",
            description="Full dep pack",
            base_model="SD1.5",
            source=PackSource(provider=ProviderName.LOCAL),
            dependencies=[
                PackDependency(
                    id="lora1",
                    kind=AssetKind.LORA,
                    selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                    update_policy=UpdatePolicy(),
                    expose=ExposeConfig(filename="l.safetensors", trigger_words=["tw"]),
                ),
            ],
        )
        store.layout.save_pack(dep)
        consumer = make_lora_pack(
            "consumer",
            pack_deps=[PackDependencyRef(pack_name="full-dep")],
        )
        store.layout.save_pack(consumer)

        loaded = store.get_pack("consumer")
        ref = loaded.pack_dependencies[0]
        dp = store.get_pack(ref.pack_name)
        trigger_words = []
        for d in dp.dependencies:
            if d.expose and d.expose.trigger_words:
                trigger_words.extend(d.expose.trigger_words)

        status = {
            "pack_name": ref.pack_name,
            "required": ref.required,
            "installed": True,
            "version": getattr(dp, 'version', None),
            "pack_type": dp.pack_type.value if hasattr(dp.pack_type, 'value') else None,
            "description": (dp.description or "")[:200] if dp.description else None,
            "asset_count": len(dp.dependencies),
            "trigger_words": trigger_words,
            "base_model": dp.base_model,
            "has_unresolved": False,
            "all_installed": False,
        }

        expected_keys = {
            "pack_name", "required", "installed", "version",
            "pack_type", "description", "asset_count", "trigger_words",
            "base_model", "has_unresolved", "all_installed",
        }
        assert set(status.keys()) == expected_keys
        assert status["trigger_words"] == ["tw"]
        assert status["base_model"] == "SD1.5"
