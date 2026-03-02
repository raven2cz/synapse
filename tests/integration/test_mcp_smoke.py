"""
Smoke/E2E tests for MCP store server and avatar routes.

Tests full lifecycle flows with real Store, mimicking actual usage patterns.
Mocks only HTTP (external network calls).

These tests verify that multiple MCP tools work correctly in sequence
and that output is consistent across tools.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.helpers.fixtures import (
    TestStoreContext,
    FakeCivitaiClient,
    build_test_model,
    FakeModel,
    FakeModelVersion,
    FakeFile,
    create_test_blob,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def smoke_store():
    """Create a store with multiple packs for smoke testing."""
    fake_civitai = FakeCivitaiClient()

    # Checkpoint pack
    _, ckpt_sha = create_test_blob("checkpoint_model_content")
    ckpt_model = FakeModel(
        id=1001,
        name="RealVisXL",
        type="Checkpoint",
        versions=[
            FakeModelVersion(
                id=2001,
                model_id=1001,
                name="v4.0",
                base_model="SDXL 1.0",
                trained_words=[],
                files=[FakeFile(id=3001, name="realvisxl_v4.safetensors", sha256=ckpt_sha).to_dict()],
                images=[],
            )
        ],
    )
    fake_civitai.add_model(ckpt_model)

    # LoRA pack
    _, lora_sha = create_test_blob("lora_model_content")
    lora_model = FakeModel(
        id=1002,
        name="DetailTweaker",
        type="LORA",
        versions=[
            FakeModelVersion(
                id=2002,
                model_id=1002,
                name="v1.0",
                base_model="SDXL 1.0",
                trained_words=["detail", "sharp"],
                files=[FakeFile(id=3002, name="detail_tweaker.safetensors", sha256=lora_sha).to_dict()],
                images=[],
            )
        ],
    )
    fake_civitai.add_model(lora_model)

    with TestStoreContext(civitai_client=fake_civitai) as ctx:
        ctx.store.init()
        yield ctx, fake_civitai


def _import_pack(ctx, model_id, pack_name=None):
    """Import a pack with mocked HTTP downloads."""
    with patch("src.store.blob_store.BlobStore._download_http") as mock_dl:
        def fake_download(url, expected_sha256=None, on_progress=None):
            if expected_sha256:
                blob_path = ctx.store.blob_store.blob_path(expected_sha256)
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                blob_path.write_bytes(b"fake model " + expected_sha256.encode()[:20])
            return expected_sha256

        mock_dl.side_effect = fake_download
        return ctx.store.import_civitai(
            url=f"https://civitai.com/models/{model_id}",
            download_previews=False,
            pack_name=pack_name,
        )


# =============================================================================
# Smoke Tests
# =============================================================================


@pytest.mark.integration
class TestMCPFullLifecycle:
    """Test full lifecycle: import → list → details → inventory → stats."""

    def test_import_then_list_then_details(self, smoke_store):
        """Import packs, then verify list and details tools return consistent data."""
        from src.avatar.mcp.store_server import (
            _list_packs_impl,
            _get_pack_details_impl,
            _search_packs_impl,
        )

        ctx, _ = smoke_store

        # Import both packs
        _import_pack(ctx, 1001)
        _import_pack(ctx, 1002)

        # List should show both
        list_result = _list_packs_impl(store=ctx.store)
        assert "Found 2 packs" in list_result
        assert "RealVisXL" in list_result
        assert "DetailTweaker" in list_result

        # Details should work for each
        detail1 = _get_pack_details_impl(store=ctx.store, pack_name="RealVisXL")
        assert "Pack: RealVisXL" in detail1
        assert "Source: civitai" in detail1

        detail2 = _get_pack_details_impl(store=ctx.store, pack_name="DetailTweaker")
        assert "Pack: DetailTweaker" in detail2

        # Search should find both
        search_all = _search_packs_impl(store=ctx.store, query="XL")
        assert "RealVisXL" in search_all

        search_lora = _search_packs_impl(store=ctx.store, query="Detail")
        assert "DetailTweaker" in search_lora

    def test_inventory_consistency(self, smoke_store):
        """Verify inventory summary matches storage stats after import."""
        from src.avatar.mcp.store_server import (
            _get_inventory_summary_impl,
            _get_storage_stats_impl,
        )

        ctx, _ = smoke_store
        _import_pack(ctx, 1001)

        # Inventory summary
        inv_result = _get_inventory_summary_impl(store=ctx.store)
        assert "Inventory Summary" in inv_result
        # After import, should have at least 1 blob
        assert "Total blobs: 0" not in inv_result

        # Storage stats should also show the blob
        stats_result = _get_storage_stats_impl(store=ctx.store)
        assert "Storage Statistics" in stats_result
        assert "Total blobs: 0" not in stats_result

    def test_orphan_lifecycle(self, smoke_store):
        """Create orphan blob, detect it, verify it appears in find_orphan_blobs."""
        from src.avatar.mcp.store_server import (
            _find_orphan_blobs_impl,
            _get_inventory_summary_impl,
        )

        ctx, _ = smoke_store

        # Create orphan blob (not referenced by any pack)
        orphan_sha = ctx.create_blob("orphan blob content xyz")

        # Should appear in orphan detection
        orphan_result = _find_orphan_blobs_impl(store=ctx.store)
        assert "orphan" in orphan_result.lower()
        assert orphan_sha[:16] in orphan_result

        # Summary should show 1 orphan
        summary = _get_inventory_summary_impl(store=ctx.store)
        assert "Orphan: 1" in summary

    def test_filter_and_limit(self, smoke_store):
        """Test filtering and limiting in list_packs."""
        from src.avatar.mcp.store_server import _list_packs_impl

        ctx, _ = smoke_store
        _import_pack(ctx, 1001)
        _import_pack(ctx, 1002)

        # Filter by name
        filtered = _list_packs_impl(store=ctx.store, name_filter="real")
        assert "RealVisXL" in filtered
        assert "DetailTweaker" not in filtered

        # Limit to 1
        limited = _list_packs_impl(store=ctx.store, limit=1)
        assert "showing first 1" in limited

    def test_empty_store_all_tools(self, smoke_store):
        """All tools should return sensible output on empty store."""
        from src.avatar.mcp.store_server import (
            _list_packs_impl,
            _search_packs_impl,
            _get_inventory_summary_impl,
            _find_orphan_blobs_impl,
            _find_missing_blobs_impl,
            _get_backup_status_impl,
            _get_storage_stats_impl,
            _check_pack_updates_impl,
        )

        ctx, _ = smoke_store

        # All should return without error
        assert "No packs" in _list_packs_impl(store=ctx.store)
        assert "No packs found" in _search_packs_impl(store=ctx.store, query="test")
        assert "Total blobs: 0" in _get_inventory_summary_impl(store=ctx.store)
        assert "No orphan" in _find_orphan_blobs_impl(store=ctx.store)
        assert "No missing" in _find_missing_blobs_impl(store=ctx.store)
        assert "not enabled" in _get_backup_status_impl(store=ctx.store).lower() or \
               "not connected" in _get_backup_status_impl(store=ctx.store).lower()
        assert "Storage Statistics" in _get_storage_stats_impl(store=ctx.store)
        assert "up to date" in _check_pack_updates_impl(store=ctx.store).lower()


@pytest.mark.integration
class TestSkillsSmoke:
    """Smoke tests for skills system with real skill files."""

    def test_skills_loaded_in_system_prompt(self):
        """Build prompt with real skill files from config/avatar/skills/."""
        from src.avatar.config import AvatarConfig
        from src.avatar.skills import build_system_prompt

        skills_dir = Path(__file__).parent.parent.parent / "config" / "avatar" / "skills"
        config = AvatarConfig(
            skills_dir=skills_dir,
            custom_skills_dir=Path("/tmp/nonexistent-custom-skills"),
        )
        prompt = build_system_prompt(config)

        # Should contain base prompt
        assert "Synapse AI assistant" in prompt
        # Should contain domain knowledge header
        assert "# Domain Knowledge" in prompt
        # Should contain at least some real skill files
        assert "## Skill:" in prompt
        # Verify known skill content from existing files
        assert "Pack" in prompt  # From synapse-basics or pack-management
        assert "Generation Parameters" in prompt or "cfg_scale" in prompt

    def test_custom_skills_override(self, tmp_path):
        """Custom skill with same name replaces built-in."""
        from src.avatar.config import AvatarConfig
        from src.avatar.skills import build_system_prompt

        skills_dir = Path(__file__).parent.parent.parent / "config" / "avatar" / "skills"

        # Create custom dir with an override
        custom_dir = tmp_path / "custom-skills"
        custom_dir.mkdir()
        (custom_dir / "synapse-basics.md").write_text(
            "# Custom Basics\nThis is the custom override version."
        )

        config = AvatarConfig(
            skills_dir=skills_dir,
            custom_skills_dir=custom_dir,
        )
        prompt = build_system_prompt(config)

        # Should contain custom override, not built-in
        assert "This is the custom override version." in prompt
        # The built-in synapse-basics content should NOT appear
        assert "Pack-First Model Manager" not in prompt


@pytest.mark.integration
class TestCivitaiToolsPipeline:
    """Smoke: search → analyze → compare → import pipeline."""

    def test_analyze_then_import_then_details(self, smoke_store):
        """Analyze model, import it, then verify details are consistent."""
        from src.avatar.mcp.store_server import (
            _analyze_civitai_model_impl,
            _import_civitai_model_impl,
            _get_pack_details_impl,
        )

        ctx, fake_civitai = smoke_store

        # Analyze
        analyze_result = _analyze_civitai_model_impl(
            civitai=fake_civitai,
            url="https://civitai.com/models/1001",
        )
        assert "RealVisXL" in analyze_result
        assert "Checkpoint" in analyze_result

        # Import
        _import_pack(ctx, 1001)

        # Details should be consistent with analyze
        details = _get_pack_details_impl(store=ctx.store, pack_name="RealVisXL")
        assert "Pack: RealVisXL" in details
        assert "Source: civitai" in details

    def test_search_then_analyze_then_compare(self, smoke_store):
        """Search → analyze → compare pipeline with FakeCivitaiClient."""
        from src.avatar.mcp.store_server import (
            _search_civitai_impl,
            _analyze_civitai_model_impl,
            _compare_model_versions_impl,
        )

        _, fake_civitai = smoke_store

        # Search
        search_result = _search_civitai_impl(civitai=fake_civitai, query="RealVis")
        assert "RealVisXL" in search_result

        # Analyze
        analyze_result = _analyze_civitai_model_impl(
            civitai=fake_civitai,
            url="https://civitai.com/models/1001",
        )
        assert "Versions (1)" in analyze_result

        # Compare (single version → "only 1 version")
        compare_result = _compare_model_versions_impl(
            civitai=fake_civitai,
            url="https://civitai.com/models/1001",
        )
        assert "only 1 version" in compare_result


@pytest.mark.integration
class TestWorkflowPipeline:
    """Smoke: scan → check availability → resolve deps pipeline."""

    def test_scan_then_check_availability(self, smoke_store):
        """Scan workflow, import pack, then check availability."""
        from src.avatar.mcp.store_server import (
            _scan_workflow_impl,
            _check_workflow_availability_impl,
        )
        import json

        ctx, _ = smoke_store
        _import_pack(ctx, 1001)

        workflow = json.dumps({
            "nodes": [
                {
                    "id": 1, "type": "CheckpointLoaderSimple",
                    "widgets_values": ["realvisxl_v4.safetensors"],
                    "inputs": {}, "outputs": [], "properties": {},
                },
                {
                    "id": 2, "type": "LoraLoader",
                    "widgets_values": ["not_imported.safetensors", 0.8, 0.8],
                    "inputs": {}, "outputs": [], "properties": {},
                },
            ]
        })

        # Scan finds both
        scan = _scan_workflow_impl(workflow_json=workflow)
        assert "realvisxl_v4.safetensors" in scan
        assert "not_imported.safetensors" in scan

        # Availability: one available, one missing
        avail = _check_workflow_availability_impl(store=ctx.store, workflow_json=workflow)
        assert "Missing" in avail
        assert "not_imported.safetensors" in avail

    def test_resolve_deps_then_suggest_sources(self, smoke_store):
        """Resolve deps → suggest sources pipeline."""
        from src.avatar.mcp.store_server import (
            _resolve_workflow_deps_impl,
            _suggest_asset_sources_impl,
        )
        import json

        workflow = json.dumps({
            "nodes": [
                {
                    "id": 1, "type": "CheckpointLoaderSimple",
                    "widgets_values": ["umt5_xxl_fp8_e4m3fn_scaled.safetensors"],
                    "inputs": {}, "outputs": [], "properties": {},
                },
            ]
        })

        # Resolve — should identify HuggingFace source
        resolve_result = _resolve_workflow_deps_impl(workflow_json=workflow)
        assert "huggingface" in resolve_result

        # Suggest sources — should match
        suggest_result = _suggest_asset_sources_impl(
            asset_names="umt5_xxl_fp8_e4m3fn_scaled.safetensors"
        )
        assert "huggingface" in suggest_result
        assert "HF Repo:" in suggest_result

    def test_scan_file_then_list_nodes_then_resolve(self, smoke_store, tmp_path):
        """Scan file → list custom nodes → resolve deps pipeline."""
        from src.avatar.mcp.store_server import (
            _scan_workflow_file_impl,
            _list_custom_nodes_impl,
            _resolve_workflow_deps_impl,
        )
        import json

        workflow_data = {
            "nodes": [
                {
                    "id": 1, "type": "CheckpointLoaderSimple",
                    "widgets_values": ["model.safetensors"],
                    "inputs": {}, "outputs": [], "properties": {},
                },
                {
                    "id": 2, "type": "VHS_VideoCombine",
                    "widgets_values": [],
                    "inputs": {}, "outputs": [], "properties": {},
                },
            ]
        }

        # Write file
        workflow_file = tmp_path / "workflow.json"
        workflow_file.write_text(json.dumps(workflow_data))

        # Scan file (pass _allowed_base for path traversal check in tests)
        file_result = _scan_workflow_file_impl(path=str(workflow_file), _allowed_base=tmp_path)
        assert "model.safetensors" in file_result
        assert "VHS_VideoCombine" in file_result

        # List custom nodes
        workflow_json = json.dumps(workflow_data)
        nodes_result = _list_custom_nodes_impl(workflow_json=workflow_json)
        assert "ComfyUI-VideoHelperSuite" in nodes_result

        # Resolve deps
        resolve_result = _resolve_workflow_deps_impl(workflow_json=workflow_json)
        assert "Model Assets" in resolve_result
        assert "Custom Node Packages" in resolve_result


@pytest.mark.integration
class TestAvatarRouteSmoke:
    """Smoke tests for avatar API routes."""

    def test_status_endpoint_returns_valid_state(self):
        """Status endpoint should always return a valid state string."""
        from src.avatar.routes import avatar_status, invalidate_avatar_cache

        invalidate_avatar_cache()
        result = avatar_status()

        assert "state" in result
        assert result["state"] in ("ready", "no_provider", "no_engine", "setup_required", "disabled")
        assert isinstance(result["available"], bool)
        assert isinstance(result["providers"], list)

    def test_config_endpoint_returns_valid_structure(self):
        """Config endpoint should return expected fields."""
        from src.avatar.routes import avatar_config_endpoint, invalidate_avatar_cache

        invalidate_avatar_cache()
        result = avatar_config_endpoint()

        assert "enabled" in result
        assert "provider" in result
        assert "safety" in result
        assert "skills_count" in result
        assert isinstance(result["skills_count"], dict)
        assert "builtin" in result["skills_count"]
        assert "custom" in result["skills_count"]

    def test_providers_endpoint_returns_list(self):
        """Providers endpoint should return list with known structure."""
        from src.avatar.routes import avatar_providers

        result = avatar_providers()

        assert isinstance(result, list)
        assert len(result) == 3  # gemini, claude, codex
        for provider in result:
            assert "name" in provider
            assert "installed" in provider
            assert isinstance(provider["installed"], bool)
