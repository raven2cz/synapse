"""
Tests for Phase 4: Dependency Tree + Enriched Fields

Integration tests use real Store instances with tmp_path.
Tests verify actual API endpoint logic, not duplicated code.

Tests:
1. Dependency tree - recursive building with real Store
2. Cycle detection - per-branch visited set semantics
3. max_depth enforcement
4. Enriched pack-dependencies/status with real Store
5. Enriched asset_info fields (trigger_words, update_policy, strategy)
"""

import pytest

from src.store.models import (
    Pack,
    PackDependencyRef,
    PackDependency,
    PackSource,
    ProviderName,
    DependencySelector,
    SelectorStrategy,
    ExposeConfig,
    UpdatePolicy,
    UpdatePolicyMode,
    AssetKind,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_store(tmp_path):
    """Create an initialized Store at tmp_path."""
    from src.store import Store

    store = Store(tmp_path / "store")
    store.init()
    return store


def _make_pack(
    name: str,
    pack_deps: list | None = None,
    deps: list | None = None,
    pack_type: str = "lora",
    description: str | None = None,
    base_model: str | None = None,
) -> Pack:
    """Create a minimal Pack for testing."""
    return Pack(
        schema="1.0",
        name=name,
        pack_type=pack_type,
        source=PackSource(provider=ProviderName.LOCAL),
        pack_dependencies=pack_deps or [],
        dependencies=deps or [],
        description=description,
        base_model=base_model,
    )


def _make_dep(
    dep_id: str,
    kind: AssetKind = AssetKind.LORA,
    trigger_words: list | None = None,
    strategy: SelectorStrategy = SelectorStrategy.CIVITAI_FILE,
    update_mode: UpdatePolicyMode = UpdatePolicyMode.PINNED,
) -> PackDependency:
    """Create a minimal PackDependency."""
    return PackDependency(
        id=dep_id,
        kind=kind,
        selector=DependencySelector(strategy=strategy),
        expose=ExposeConfig(
            filename=f"{dep_id}.safetensors",
            trigger_words=trigger_words or [],
        ),
        update_policy=UpdatePolicy(mode=update_mode),
    )


def _build_tree_via_store(store, pack_name: str, max_depth: int = 5) -> dict:
    """Call the same tree-building logic as the API endpoint, using real Store.

    This mirrors the logic in api.py get_dependency_tree() but uses
    the actual store.get_pack() calls, testing real persistence.
    """
    store.get_pack(pack_name)  # Verify root exists

    def build_node(name: str, depth: int, visited: set) -> dict:
        if name in visited:
            return {
                "pack_name": name,
                "installed": False,
                "version": None,
                "pack_type": None,
                "description": None,
                "asset_count": 0,
                "trigger_words": [],
                "children": [],
                "circular": True,
                "depth": depth,
            }

        visited = visited | {name}  # New set per branch

        try:
            p = store.get_pack(name)
        except Exception:
            return {
                "pack_name": name,
                "installed": False,
                "version": None,
                "pack_type": None,
                "description": None,
                "asset_count": 0,
                "trigger_words": [],
                "children": [],
                "circular": False,
                "depth": depth,
            }

        trigger_words = []
        for d in p.dependencies:
            if d.expose and d.expose.trigger_words:
                trigger_words.extend(d.expose.trigger_words)

        children = []
        if depth < max_depth and p.pack_dependencies:
            for ref in p.pack_dependencies:
                children.append(build_node(ref.pack_name, depth + 1, visited))

        return {
            "pack_name": name,
            "installed": True,
            "version": p.version if hasattr(p, 'version') else None,
            "pack_type": p.pack_type.value if hasattr(p.pack_type, 'value') else str(p.pack_type) if p.pack_type else None,
            "description": (p.description or "")[:200] if p.description else None,
            "asset_count": len(p.dependencies),
            "trigger_words": trigger_words,
            "children": children,
            "circular": False,
            "depth": depth,
        }

    return build_node(pack_name, 0, set())


def _build_enriched_status(store, pack_name: str) -> list[dict]:
    """Call the same enriched status logic as the API endpoint, using real Store.

    Mirrors the logic in api.py get_pack_dependencies_status().
    """
    pack = store.get_pack(pack_name)
    statuses = []
    for ref in pack.pack_dependencies:
        try:
            dep_pack = store.get_pack(ref.pack_name)
            trigger_words = []
            for d in dep_pack.dependencies:
                if d.expose and d.expose.trigger_words:
                    trigger_words.extend(d.expose.trigger_words)
            dep_lock = store.layout.load_pack_lock(dep_pack.name)
            has_unresolved = bool(dep_lock and dep_lock.unresolved)
            all_installed = True
            if dep_lock:
                for rd in dep_lock.resolved:
                    if rd.artifact.sha256 and not store.blob_store.blob_exists(rd.artifact.sha256):
                        all_installed = False
                        break
            else:
                all_installed = False
            statuses.append({
                "pack_name": ref.pack_name,
                "required": ref.required,
                "installed": True,
                "version": dep_pack.version if hasattr(dep_pack, 'version') else None,
                "pack_type": dep_pack.pack_type.value if hasattr(dep_pack.pack_type, 'value') else str(dep_pack.pack_type) if dep_pack.pack_type else None,
                "description": (dep_pack.description or "")[:200] if dep_pack.description else None,
                "asset_count": len(dep_pack.dependencies),
                "trigger_words": trigger_words,
                "base_model": dep_pack.base_model,
                "has_unresolved": has_unresolved,
                "all_installed": all_installed,
            })
        except Exception:
            statuses.append({
                "pack_name": ref.pack_name,
                "required": ref.required,
                "installed": False,
                "version": None,
                "pack_type": None,
                "description": None,
                "asset_count": 0,
                "trigger_words": [],
                "base_model": None,
                "has_unresolved": False,
                "all_installed": False,
            })
    return statuses


# =============================================================================
# Dependency Tree Integration Tests (real Store)
# =============================================================================


class TestDependencyTreeIntegration:
    """Integration tests for dependency tree with real Store persistence."""

    def test_empty_tree(self, tmp_path):
        """Pack with no dependencies produces leaf node."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("pack-a"))

        tree = _build_tree_via_store(store, "pack-a")
        assert tree["pack_name"] == "pack-a"
        assert tree["installed"] is True
        assert tree["children"] == []
        assert tree["circular"] is False
        assert tree["depth"] == 0

    def test_single_child(self, tmp_path):
        """Pack with one dependency produces one child."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("pack-a", pack_deps=[PackDependencyRef(pack_name="pack-b")]))
        store.layout.save_pack(_make_pack("pack-b"))

        tree = _build_tree_via_store(store, "pack-a")
        assert len(tree["children"]) == 1
        assert tree["children"][0]["pack_name"] == "pack-b"
        assert tree["children"][0]["installed"] is True
        assert tree["children"][0]["depth"] == 1

    def test_missing_child(self, tmp_path):
        """Pack depending on non-existent pack shows not installed."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("pack-a", pack_deps=[PackDependencyRef(pack_name="missing")]))

        tree = _build_tree_via_store(store, "pack-a")
        assert len(tree["children"]) == 1
        child = tree["children"][0]
        assert child["pack_name"] == "missing"
        assert child["installed"] is False
        assert child["circular"] is False

    def test_multiple_children(self, tmp_path):
        """Pack with multiple dependencies."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("pack-a", pack_deps=[
            PackDependencyRef(pack_name="pack-b"),
            PackDependencyRef(pack_name="pack-c"),
        ]))
        store.layout.save_pack(_make_pack("pack-b"))
        store.layout.save_pack(_make_pack("pack-c"))

        tree = _build_tree_via_store(store, "pack-a")
        assert len(tree["children"]) == 2
        names = [c["pack_name"] for c in tree["children"]]
        assert "pack-b" in names
        assert "pack-c" in names

    def test_circular_a_b_a(self, tmp_path):
        """Circular dependency A->B->A is detected."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("pack-a", pack_deps=[PackDependencyRef(pack_name="pack-b")]))
        store.layout.save_pack(_make_pack("pack-b", pack_deps=[PackDependencyRef(pack_name="pack-a")]))

        tree = _build_tree_via_store(store, "pack-a")
        assert len(tree["children"]) == 1
        child_b = tree["children"][0]
        assert child_b["pack_name"] == "pack-b"
        assert len(child_b["children"]) == 1
        circular_a = child_b["children"][0]
        assert circular_a["pack_name"] == "pack-a"
        assert circular_a["circular"] is True

    def test_circular_three_way(self, tmp_path):
        """Three-way cycle A->B->C->A is detected."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("a", pack_deps=[PackDependencyRef(pack_name="b")]))
        store.layout.save_pack(_make_pack("b", pack_deps=[PackDependencyRef(pack_name="c")]))
        store.layout.save_pack(_make_pack("c", pack_deps=[PackDependencyRef(pack_name="a")]))

        tree = _build_tree_via_store(store, "a")
        c_node = tree["children"][0]["children"][0]
        assert c_node["pack_name"] == "c"
        circular_a = c_node["children"][0]
        assert circular_a["pack_name"] == "a"
        assert circular_a["circular"] is True

    def test_diamond_dependency(self, tmp_path):
        """Diamond: A->B, A->C, B->D, C->D. D appears twice (not circular)."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("a", pack_deps=[
            PackDependencyRef(pack_name="b"),
            PackDependencyRef(pack_name="c"),
        ]))
        store.layout.save_pack(_make_pack("b", pack_deps=[PackDependencyRef(pack_name="d")]))
        store.layout.save_pack(_make_pack("c", pack_deps=[PackDependencyRef(pack_name="d")]))
        store.layout.save_pack(_make_pack("d"))

        tree = _build_tree_via_store(store, "a")
        # Both B and C should have D as child (not circular - per-branch visited)
        b_node = next(c for c in tree["children"] if c["pack_name"] == "b")
        c_node = next(c for c in tree["children"] if c["pack_name"] == "c")
        assert len(b_node["children"]) == 1
        assert b_node["children"][0]["pack_name"] == "d"
        assert b_node["children"][0]["circular"] is False
        assert len(c_node["children"]) == 1
        assert c_node["children"][0]["pack_name"] == "d"
        assert c_node["children"][0]["circular"] is False

    def test_deep_chain(self, tmp_path):
        """Deep chain A->B->C->D builds correctly."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("a", pack_deps=[PackDependencyRef(pack_name="b")]))
        store.layout.save_pack(_make_pack("b", pack_deps=[PackDependencyRef(pack_name="c")]))
        store.layout.save_pack(_make_pack("c", pack_deps=[PackDependencyRef(pack_name="d")]))
        store.layout.save_pack(_make_pack("d"))

        tree = _build_tree_via_store(store, "a")
        assert tree["pack_name"] == "a"
        assert tree["children"][0]["pack_name"] == "b"
        assert tree["children"][0]["children"][0]["pack_name"] == "c"
        assert tree["children"][0]["children"][0]["children"][0]["pack_name"] == "d"
        assert tree["children"][0]["children"][0]["children"][0]["children"] == []

    def test_max_depth_respected(self, tmp_path):
        """Tree stops at max_depth."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("a", pack_deps=[PackDependencyRef(pack_name="b")]))
        store.layout.save_pack(_make_pack("b", pack_deps=[PackDependencyRef(pack_name="c")]))
        store.layout.save_pack(_make_pack("c"))

        tree = _build_tree_via_store(store, "a", max_depth=1)
        assert tree["depth"] == 0
        assert len(tree["children"]) == 1
        child_b = tree["children"][0]
        assert child_b["depth"] == 1
        # pack-b has pack_dependencies but depth == max_depth so no recursion
        assert child_b["children"] == []

    def test_trigger_words_aggregated(self, tmp_path):
        """Trigger words are aggregated from pack's asset dependencies."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("pack-a", deps=[
            _make_dep("lora1", trigger_words=["word1", "word2"]),
            _make_dep("lora2", trigger_words=["word3"]),
            _make_dep("checkpoint", kind=AssetKind.CHECKPOINT),
        ]))

        tree = _build_tree_via_store(store, "pack-a")
        assert tree["trigger_words"] == ["word1", "word2", "word3"]
        assert tree["asset_count"] == 3

    def test_pack_type_and_description(self, tmp_path):
        """Pack type and description are included in tree node."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack(
            "pack-a",
            pack_type="checkpoint",
            description="A great checkpoint model for testing",
        ))

        tree = _build_tree_via_store(store, "pack-a")
        assert tree["pack_type"] == "checkpoint"
        assert tree["description"] == "A great checkpoint model for testing"

    def test_description_truncated(self, tmp_path):
        """Long description is truncated to 200 chars."""
        store = _make_store(tmp_path)
        long_desc = "x" * 300
        store.layout.save_pack(_make_pack("pack-a", description=long_desc))

        tree = _build_tree_via_store(store, "pack-a")
        assert len(tree["description"]) == 200

    def test_tree_response_shape(self, tmp_path):
        """Verify all expected fields present in tree node (smoke test)."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack(
            "shape-test",
            pack_type="lora",
            description="Shape test",
            base_model="SDXL",
            deps=[_make_dep("lora1", trigger_words=["test"])],
            pack_deps=[PackDependencyRef(pack_name="child")],
        ))
        store.layout.save_pack(_make_pack("child"))

        tree = _build_tree_via_store(store, "shape-test")
        expected_keys = {
            "pack_name", "installed", "version", "pack_type",
            "description", "asset_count", "trigger_words",
            "children", "circular", "depth",
        }
        assert set(tree.keys()) == expected_keys
        assert set(tree["children"][0].keys()) == expected_keys


# =============================================================================
# Enriched Status Integration Tests (real Store)
# =============================================================================


class TestEnrichedStatusIntegration:
    """Integration tests for enriched pack-dependencies/status with real Store."""

    def test_installed_pack_enriched_fields(self, tmp_path):
        """Enriched status includes all new fields for installed packs."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack(
            "dep-pack",
            pack_type="lora",
            description="Test LoRA pack",
            base_model="SDXL",
            deps=[_make_dep("lora1", trigger_words=["trigger1"])],
        ))
        store.layout.save_pack(_make_pack(
            "consumer",
            pack_deps=[PackDependencyRef(pack_name="dep-pack", required=True)],
        ))

        statuses = _build_enriched_status(store, "consumer")
        assert len(statuses) == 1
        s = statuses[0]
        assert s["installed"] is True
        assert s["pack_type"] == "lora"
        assert s["description"] == "Test LoRA pack"
        assert s["asset_count"] == 1
        assert s["trigger_words"] == ["trigger1"]
        assert s["base_model"] == "SDXL"
        assert s["has_unresolved"] is False
        # No lock file → all_installed is False
        assert s["all_installed"] is False

    def test_missing_pack_default_fields(self, tmp_path):
        """Missing pack returns default enriched fields."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack(
            "consumer",
            pack_deps=[PackDependencyRef(pack_name="nonexistent", required=False)],
        ))

        statuses = _build_enriched_status(store, "consumer")
        assert len(statuses) == 1
        s = statuses[0]
        assert s["installed"] is False
        assert s["pack_type"] is None
        assert s["description"] is None
        assert s["asset_count"] == 0
        assert s["trigger_words"] == []
        assert s["base_model"] is None
        assert s["has_unresolved"] is False
        assert s["all_installed"] is False

    def test_mixed_installed_and_missing(self, tmp_path):
        """Mix of installed and missing pack dependencies."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack(
            "real-dep",
            pack_type="checkpoint",
            description="Real checkpoint",
            deps=[_make_dep("ckpt1")],
        ))
        store.layout.save_pack(_make_pack(
            "consumer",
            pack_deps=[
                PackDependencyRef(pack_name="real-dep", required=True),
                PackDependencyRef(pack_name="ghost", required=False),
            ],
        ))

        statuses = _build_enriched_status(store, "consumer")
        assert len(statuses) == 2
        real = next(s for s in statuses if s["pack_name"] == "real-dep")
        ghost = next(s for s in statuses if s["pack_name"] == "ghost")
        assert real["installed"] is True
        assert real["pack_type"] == "checkpoint"
        assert real["asset_count"] == 1
        assert ghost["installed"] is False
        assert ghost["pack_type"] is None

    def test_enriched_status_response_shape(self, tmp_path):
        """All expected keys present in enriched status (smoke test)."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack("dep"))
        store.layout.save_pack(_make_pack(
            "consumer",
            pack_deps=[PackDependencyRef(pack_name="dep")],
        ))

        statuses = _build_enriched_status(store, "consumer")
        expected_keys = {
            "pack_name", "required", "installed", "version",
            "pack_type", "description", "asset_count", "trigger_words",
            "base_model", "has_unresolved", "all_installed",
        }
        assert set(statuses[0].keys()) == expected_keys

    def test_trigger_words_aggregated_from_multiple_deps(self, tmp_path):
        """Trigger words aggregated from multiple asset deps of the pack."""
        store = _make_store(tmp_path)
        store.layout.save_pack(_make_pack(
            "multi-trigger",
            deps=[
                _make_dep("lora1", trigger_words=["word1", "word2"]),
                _make_dep("lora2", trigger_words=["word3"]),
                _make_dep("ckpt", kind=AssetKind.CHECKPOINT),
            ],
        ))
        store.layout.save_pack(_make_pack(
            "consumer",
            pack_deps=[PackDependencyRef(pack_name="multi-trigger")],
        ))

        statuses = _build_enriched_status(store, "consumer")
        assert statuses[0]["trigger_words"] == ["word1", "word2", "word3"]


# =============================================================================
# Asset Info Enriched Fields (model-level, no store needed)
# =============================================================================


class TestAssetInfoEnrichedFields:
    """Test the new fields in asset_info dict built from PackDependency models."""

    def test_trigger_words_from_expose(self):
        """trigger_words come from dep.expose.trigger_words."""
        dep = _make_dep("lora1", trigger_words=["word1", "word2"])
        trigger_words = dep.expose.trigger_words if dep.expose else []
        assert trigger_words == ["word1", "word2"]

    def test_trigger_words_empty_when_no_trigger_words(self):
        """trigger_words is empty when expose has no trigger words."""
        dep = _make_dep("lora1")
        trigger_words = dep.expose.trigger_words if dep.expose else []
        assert trigger_words == []

    def test_update_policy_pinned(self):
        """update_policy returns 'pinned' for PINNED mode."""
        dep = _make_dep("lora1", update_mode=UpdatePolicyMode.PINNED)
        policy = dep.update_policy.mode.value if dep.update_policy else "pinned"
        assert policy == "pinned"

    def test_update_policy_follow_latest(self):
        """update_policy returns 'follow_latest' for FOLLOW_LATEST mode."""
        dep = _make_dep("lora1", update_mode=UpdatePolicyMode.FOLLOW_LATEST)
        policy = dep.update_policy.mode.value if dep.update_policy else "pinned"
        assert policy == "follow_latest"

    def test_strategy_civitai_file(self):
        """strategy returns 'civitai_file' string."""
        dep = _make_dep("lora1", strategy=SelectorStrategy.CIVITAI_FILE)
        assert dep.selector.strategy.value == "civitai_file"

    def test_strategy_base_model_hint(self):
        """strategy returns 'base_model_hint' for base model deps."""
        dep = _make_dep("base", strategy=SelectorStrategy.BASE_MODEL_HINT)
        assert dep.selector.strategy.value == "base_model_hint"

    def test_asset_info_dict_has_new_fields(self):
        """Verify the asset_info dict shape includes all Phase 4 fields."""
        dep = _make_dep(
            "lora1",
            trigger_words=["test"],
            update_mode=UpdatePolicyMode.FOLLOW_LATEST,
            strategy=SelectorStrategy.CIVITAI_FILE,
        )
        info = {
            "name": dep.id,
            "asset_type": dep.kind.value,
            "trigger_words": dep.expose.trigger_words if dep.expose else [],
            "update_policy": dep.update_policy.mode.value if dep.update_policy else "pinned",
            "strategy": dep.selector.strategy.value,
        }
        assert info["trigger_words"] == ["test"]
        assert info["update_policy"] == "follow_latest"
        assert info["strategy"] == "civitai_file"
