"""
Tests for Phase 3: Updates + Dependency Impact

Unit tests:
- UpdatePlan model with impacted_packs field
- _find_reverse_dependencies() logic

Integration tests:
- plan_update() populates impacted_packs from real store data
- Full update flow with reverse dependencies

Smoke tests:
- API endpoint returns impacted_packs in response
- Empty impacted_packs when no reverse deps
"""

import pytest

from src.store.models import (
    AmbiguousUpdate,
    Pack,
    PackDependencyRef,
    PackSource,
    ProviderName,
    UpdateCandidate,
    UpdateChange,
    UpdatePlan,
)


# =============================================================================
# Unit Tests: UpdatePlan Model
# =============================================================================


class TestUpdatePlanModel:
    """Unit tests for UpdatePlan with impacted_packs field."""

    def test_impacted_packs_defaults_to_empty(self):
        """impacted_packs should default to empty list."""
        plan = UpdatePlan(pack="test-pack")
        assert plan.impacted_packs == []

    def test_impacted_packs_can_be_set(self):
        """impacted_packs accepts a list of pack names."""
        plan = UpdatePlan(
            pack="base-checkpoint",
            impacted_packs=["lora-pack-a", "lora-pack-b"],
        )
        assert plan.impacted_packs == ["lora-pack-a", "lora-pack-b"]
        assert len(plan.impacted_packs) == 2

    def test_impacted_packs_serializes(self):
        """impacted_packs should be in model_dump() output."""
        plan = UpdatePlan(
            pack="test-pack",
            changes=[
                UpdateChange(
                    dependency_id="main",
                    old={"version_id": 1},
                    new={"version_id": 2},
                )
            ],
            impacted_packs=["dep-a", "dep-b"],
        )
        data = plan.model_dump()
        assert "impacted_packs" in data
        assert data["impacted_packs"] == ["dep-a", "dep-b"]

    def test_impacted_packs_with_all_fields(self):
        """Full UpdatePlan with changes, ambiguous, and impacted_packs."""
        plan = UpdatePlan(
            pack="TestPack",
            already_up_to_date=False,
            changes=[
                UpdateChange(
                    dependency_id="main",
                    old={"version_id": 1},
                    new={"version_id": 2, "version_name": "v2.0"},
                )
            ],
            ambiguous=[
                AmbiguousUpdate(
                    dependency_id="optional",
                    candidates=[
                        UpdateCandidate(
                            provider="civitai",
                            provider_model_id=123,
                            provider_version_id=200,
                        )
                    ],
                )
            ],
            impacted_packs=["pack-x", "pack-y", "pack-z"],
        )

        data = plan.model_dump()
        assert len(data["changes"]) == 1
        assert len(data["ambiguous"]) == 1
        assert len(data["impacted_packs"]) == 3
        assert data["impacted_packs"] == ["pack-x", "pack-y", "pack-z"]

    def test_impacted_packs_in_up_to_date_plan(self):
        """Even up-to-date plans can have impacted_packs (for info)."""
        plan = UpdatePlan(
            pack="stable-pack",
            already_up_to_date=True,
            impacted_packs=["consumer-pack"],
        )
        assert plan.already_up_to_date is True
        assert plan.impacted_packs == ["consumer-pack"]


# =============================================================================
# Unit Tests: Reverse Dependency Scan
# =============================================================================


class TestFindReverseDependencies:
    """Unit tests for UpdateService._find_reverse_dependencies()."""

    def _make_store(self, tmp_path, packs: list[Pack]):
        """Create a store with given packs."""
        from src.store.layout import StoreLayout
        from src.store.blob_store import BlobStore
        from src.store.view_builder import ViewBuilder
        from src.store.update_service import UpdateService

        layout = StoreLayout(tmp_path)
        layout.init_store()
        for pack in packs:
            layout.save_pack(pack)

        blob_store = BlobStore(layout)
        view_builder = ViewBuilder(layout, blob_store)
        service = UpdateService(layout, blob_store, view_builder)
        return service

    def _pack(self, name: str, deps: list[str] | None = None) -> Pack:
        """Create a pack with given pack_dependencies."""
        return Pack(
            schema="1.0",
            name=name,
            pack_type="lora",
            source=PackSource(provider=ProviderName.LOCAL),
            pack_dependencies=[
                PackDependencyRef(pack_name=d) for d in (deps or [])
            ],
        )

    def test_no_reverse_deps(self, tmp_path):
        """Pack with no dependents returns empty list."""
        service = self._make_store(tmp_path, [
            self._pack("pack-a"),
            self._pack("pack-b"),
            self._pack("pack-c"),
        ])
        result = service._find_reverse_dependencies("pack-a")
        assert result == []

    def test_single_reverse_dep(self, tmp_path):
        """One pack depends on the target."""
        service = self._make_store(tmp_path, [
            self._pack("checkpoint"),
            self._pack("lora-pack", deps=["checkpoint"]),
        ])
        result = service._find_reverse_dependencies("checkpoint")
        assert result == ["lora-pack"]

    def test_multiple_reverse_deps(self, tmp_path):
        """Multiple packs depend on the target."""
        service = self._make_store(tmp_path, [
            self._pack("base-model"),
            self._pack("lora-a", deps=["base-model"]),
            self._pack("lora-b", deps=["base-model"]),
            self._pack("embedding", deps=["base-model"]),
        ])
        result = service._find_reverse_dependencies("base-model")
        assert result == ["embedding", "lora-a", "lora-b"]  # sorted

    def test_excludes_self(self, tmp_path):
        """Target pack is not included in reverse deps."""
        service = self._make_store(tmp_path, [
            self._pack("pack-a"),
            self._pack("pack-b", deps=["pack-a"]),
        ])
        result = service._find_reverse_dependencies("pack-a")
        assert "pack-a" not in result

    def test_indirect_deps_not_included(self, tmp_path):
        """Only direct dependents are included (no transitive)."""
        service = self._make_store(tmp_path, [
            self._pack("base"),
            self._pack("middle", deps=["base"]),
            self._pack("top", deps=["middle"]),  # depends on middle, not base
        ])
        result = service._find_reverse_dependencies("base")
        assert result == ["middle"]
        assert "top" not in result

    def test_nonexistent_pack(self, tmp_path):
        """Scanning for a pack that doesn't exist returns empty."""
        service = self._make_store(tmp_path, [
            self._pack("pack-a"),
        ])
        result = service._find_reverse_dependencies("nonexistent")
        assert result == []

    def test_results_are_sorted(self, tmp_path):
        """Results should be alphabetically sorted."""
        service = self._make_store(tmp_path, [
            self._pack("target"),
            self._pack("zebra-pack", deps=["target"]),
            self._pack("alpha-pack", deps=["target"]),
            self._pack("mid-pack", deps=["target"]),
        ])
        result = service._find_reverse_dependencies("target")
        assert result == ["alpha-pack", "mid-pack", "zebra-pack"]


# =============================================================================
# Integration Tests: plan_update with impacted_packs
# =============================================================================


class TestPlanUpdateWithImpact:
    """Integration tests for plan_update() populating impacted_packs."""

    def _setup_store(self, tmp_path, packs: list[Pack]):
        """Create store + update service with given packs."""
        from src.store.layout import StoreLayout
        from src.store.blob_store import BlobStore
        from src.store.view_builder import ViewBuilder
        from src.store.update_service import UpdateService

        layout = StoreLayout(tmp_path)
        layout.init_store()
        for pack in packs:
            layout.save_pack(pack)
        blob_store = BlobStore(layout)
        view_builder = ViewBuilder(layout, blob_store)
        service = UpdateService(layout, blob_store, view_builder)
        return service, layout

    def _pack(self, name: str, deps: list[str] | None = None) -> Pack:
        """Create a simple pack."""
        return Pack(
            schema="1.0",
            name=name,
            pack_type="lora",
            source=PackSource(provider=ProviderName.LOCAL),
            pack_dependencies=[
                PackDependencyRef(pack_name=d) for d in (deps or [])
            ],
        )

    def test_plan_update_includes_impacted_packs(self, tmp_path):
        """plan_update() should populate impacted_packs."""
        service, layout = self._setup_store(tmp_path, [
            self._pack("checkpoint-pack"),
            self._pack("lora-pack", deps=["checkpoint-pack"]),
        ])

        # plan_update needs a lock file (or returns empty plan)
        # Without lock, it still scans reverse deps
        plan = service.plan_update("checkpoint-pack")
        assert plan.impacted_packs == ["lora-pack"]

    def test_plan_update_empty_impacted(self, tmp_path):
        """plan_update() with no dependents returns empty impacted_packs."""
        service, layout = self._setup_store(tmp_path, [
            self._pack("isolated-pack"),
            self._pack("other-pack"),
        ])

        plan = service.plan_update("isolated-pack")
        assert plan.impacted_packs == []

    def test_plan_update_multiple_impacted(self, tmp_path):
        """plan_update() finds multiple reverse dependencies."""
        service, layout = self._setup_store(tmp_path, [
            self._pack("base"),
            self._pack("dep-a", deps=["base"]),
            self._pack("dep-b", deps=["base"]),
            self._pack("dep-c", deps=["base"]),
            self._pack("unrelated"),
        ])

        plan = service.plan_update("base")
        assert plan.impacted_packs == ["dep-a", "dep-b", "dep-c"]

    def test_plan_update_already_up_to_date_still_has_impacts(self, tmp_path):
        """Even up-to-date plans should list impacted packs."""
        service, layout = self._setup_store(tmp_path, [
            self._pack("stable-pack"),
            self._pack("consumer", deps=["stable-pack"]),
        ])

        plan = service.plan_update("stable-pack")
        # Without lock, already_up_to_date=False but no changes
        assert plan.impacted_packs == ["consumer"]


# =============================================================================
# Smoke Tests: API endpoint format
# =============================================================================


class TestUpdatePlanAPIFormat:
    """Smoke tests verifying the API response format includes impacted_packs."""

    def test_update_plan_json_has_impacted_packs(self):
        """API response (JSON) should include impacted_packs."""
        plan = UpdatePlan(
            pack="my-pack",
            already_up_to_date=True,
            impacted_packs=["dependent-a"],
        )
        data = plan.model_dump()

        # Simulates what FastAPI would serialize
        assert "impacted_packs" in data
        assert isinstance(data["impacted_packs"], list)
        assert data["impacted_packs"] == ["dependent-a"]

    def test_update_plan_json_empty_impacted(self):
        """API response with no impacts should have empty list."""
        plan = UpdatePlan(
            pack="lonely-pack",
            already_up_to_date=False,
            changes=[
                UpdateChange(
                    dependency_id="main",
                    old={"v": 1},
                    new={"v": 2},
                )
            ],
        )
        data = plan.model_dump()
        assert data["impacted_packs"] == []

    def test_update_check_response_includes_impacted(self):
        """Verify the response matches frontend UpdateCheckResponse type."""
        plan = UpdatePlan(
            pack="test-pack",
            already_up_to_date=False,
            changes=[
                UpdateChange(
                    dependency_id="dep1",
                    old={"version_name": "v1.0"},
                    new={"version_name": "v2.0"},
                )
            ],
            impacted_packs=["pack-a", "pack-b"],
        )

        # Simulates the check endpoint response structure
        response = {
            "pack": plan.pack,
            "has_updates": not plan.already_up_to_date and len(plan.changes) > 0,
            "changes_count": len(plan.changes),
            "ambiguous_count": len(plan.ambiguous),
            "plan": plan.model_dump(),
        }

        assert response["has_updates"] is True
        assert response["plan"]["impacted_packs"] == ["pack-a", "pack-b"]
        assert len(response["plan"]["changes"]) == 1

    def test_backward_compatible_plan_without_impacted(self):
        """Plans created without impacted_packs should default to []."""
        # Simulates loading old data from API that doesn't have impacted_packs
        old_plan_data = {
            "pack": "old-pack",
            "already_up_to_date": True,
            "changes": [],
            "ambiguous": [],
            # no impacted_packs key
        }
        plan = UpdatePlan.model_validate(old_plan_data)
        assert plan.impacted_packs == []
