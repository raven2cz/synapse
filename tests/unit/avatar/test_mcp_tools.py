"""
Unit tests for MCP store server tool implementations.

Tests _*_impl functions directly with mock Store. Does NOT require mcp package.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, PropertyMock, patch
from typing import List


# =============================================================================
# Helpers
# =============================================================================


def _make_mock_pack(
    name: str = "TestPack",
    pack_type: str = "lora",
    base_model: str = "SDXL 1.0",
    source_provider: str = "civitai",
    source_url: str = "https://civitai.com/models/123",
    dependencies: list = None,
    trigger_words: list = None,
    tags: list = None,
    description: str = None,
    version: str = None,
    author: str = None,
    parameters=None,
):
    """Create a mock Pack object."""
    pack = MagicMock()
    pack.name = name

    pack_type_mock = MagicMock()
    pack_type_mock.value = pack_type
    pack.pack_type = pack_type_mock

    pack.base_model = base_model
    pack.version = version
    pack.author = author
    pack.description = description
    pack.trigger_words = trigger_words or []
    pack.tags = tags or []

    source = MagicMock()
    source_prov = MagicMock()
    source_prov.value = source_provider
    source.provider = source_prov
    source.url = source_url
    source.model_id = 123
    pack.source = source

    pack.dependencies = dependencies or []
    pack.parameters = parameters

    return pack


def _make_mock_dependency(dep_id: str = "main", kind: str = "lora", filename: str = "model.safetensors"):
    """Create a mock PackDependency."""
    dep = MagicMock()
    dep.id = dep_id
    kind_mock = MagicMock()
    kind_mock.value = kind
    dep.kind = kind_mock
    expose = MagicMock()
    expose.filename = filename
    dep.expose = expose
    return dep


def _make_mock_inventory_item(
    sha256: str = "abcdef1234567890",
    kind: str = "lora",
    display_name: str = "test_model.safetensors",
    size_bytes: int = 1024 * 1024 * 100,  # 100 MB
    status: str = "orphan",
    used_by_packs: list = None,
):
    """Create a mock InventoryItem."""
    item = MagicMock()
    item.sha256 = sha256
    kind_mock = MagicMock()
    kind_mock.value = kind
    item.kind = kind_mock
    item.display_name = display_name
    item.size_bytes = size_bytes
    status_mock = MagicMock()
    status_mock.value = status
    item.status = status_mock
    item.used_by_packs = used_by_packs or []
    return item


def _make_mock_inventory_summary(
    blobs_total: int = 10,
    blobs_referenced: int = 8,
    blobs_orphan: int = 2,
    blobs_missing: int = 0,
    blobs_backup_only: int = 0,
    bytes_total: int = 1024 * 1024 * 1024 * 5,  # 5 GB
    bytes_referenced: int = 1024 * 1024 * 1024 * 4,
    bytes_orphan: int = 1024 * 1024 * 1024,
    bytes_by_kind: dict = None,
    disk_total: int = None,
    disk_free: int = None,
):
    """Create a mock InventorySummary."""
    summary = MagicMock()
    summary.blobs_total = blobs_total
    summary.blobs_referenced = blobs_referenced
    summary.blobs_orphan = blobs_orphan
    summary.blobs_missing = blobs_missing
    summary.blobs_backup_only = blobs_backup_only
    summary.bytes_total = bytes_total
    summary.bytes_referenced = bytes_referenced
    summary.bytes_orphan = bytes_orphan
    summary.bytes_by_kind = bytes_by_kind or {}
    summary.disk_total = disk_total
    summary.disk_free = disk_free
    return summary


def _make_mock_backup_status(
    enabled: bool = True,
    connected: bool = True,
    path: str = "/mnt/backup",
    total_blobs: int = 5,
    total_bytes: int = 1024 * 1024 * 500,
    free_space: int = 1024 * 1024 * 1024 * 100,
    last_sync: str = "2026-02-23T10:00:00",
    error: str = None,
    auto_backup_new: bool = False,
    warn_before_delete_last_copy: bool = True,
):
    """Create a mock BackupStatus."""
    status = MagicMock()
    status.enabled = enabled
    status.connected = connected
    status.path = path
    status.total_blobs = total_blobs
    status.total_bytes = total_bytes
    status.free_space = free_space
    status.last_sync = last_sync
    status.error = error
    status.auto_backup_new = auto_backup_new
    status.warn_before_delete_last_copy = warn_before_delete_last_copy
    return status


# =============================================================================
# Tests
# =============================================================================


class TestFormatSize:
    """Test the _format_size helper."""

    def test_bytes(self):
        from src.avatar.mcp.store_server import _format_size

        assert _format_size(0) == "0 B"
        assert _format_size(512) == "512 B"
        assert _format_size(1023) == "1023 B"

    def test_kilobytes(self):
        from src.avatar.mcp.store_server import _format_size

        assert _format_size(1024) == "1.0 KB"
        assert _format_size(1536) == "1.5 KB"
        assert _format_size(1024 * 100) == "100.0 KB"

    def test_megabytes(self):
        from src.avatar.mcp.store_server import _format_size

        assert _format_size(1024 * 1024) == "1.0 MB"
        assert _format_size(1024 * 1024 * 250) == "250.0 MB"

    def test_gigabytes(self):
        from src.avatar.mcp.store_server import _format_size

        assert _format_size(1024 * 1024 * 1024) == "1.00 GB"
        assert _format_size(1024 * 1024 * 1024 * 5) == "5.00 GB"
        assert _format_size(int(1024 * 1024 * 1024 * 2.5)) == "2.50 GB"


class TestListPacks:
    """Test _list_packs_impl."""

    def test_all_packs(self):
        from src.avatar.mcp.store_server import _list_packs_impl

        store = MagicMock()
        store.list_packs.return_value = ["PackA", "PackB"]
        store.get_pack.side_effect = lambda n: _make_mock_pack(
            name=n, pack_type="lora", base_model="SDXL 1.0"
        )

        result = _list_packs_impl(store=store)
        assert "Found 2 packs" in result
        assert "PackA" in result
        assert "PackB" in result
        assert "lora" in result
        assert "SDXL 1.0" in result

    def test_filtered(self):
        from src.avatar.mcp.store_server import _list_packs_impl

        store = MagicMock()
        store.list_packs.return_value = ["RealVis", "DetailTweaker", "BadDreams"]
        store.get_pack.side_effect = lambda n: _make_mock_pack(name=n)

        result = _list_packs_impl(store=store, name_filter="real")
        assert "RealVis" in result
        assert "DetailTweaker" not in result

    def test_limited(self):
        from src.avatar.mcp.store_server import _list_packs_impl

        store = MagicMock()
        store.list_packs.return_value = [f"Pack{i}" for i in range(10)]
        store.get_pack.side_effect = lambda n: _make_mock_pack(name=n)

        result = _list_packs_impl(store=store, limit=3)
        assert "showing first 3" in result
        assert "Pack0" in result
        assert "Pack2" in result
        # Pack3 should not appear
        assert "Pack3" not in result

    def test_empty(self):
        from src.avatar.mcp.store_server import _list_packs_impl

        store = MagicMock()
        store.list_packs.return_value = []

        result = _list_packs_impl(store=store)
        assert "No packs in the store" in result

    def test_empty_with_filter(self):
        from src.avatar.mcp.store_server import _list_packs_impl

        store = MagicMock()
        store.list_packs.return_value = ["PackA"]

        result = _list_packs_impl(store=store, name_filter="nonexistent")
        assert "No packs found matching" in result

    def test_error(self):
        from src.avatar.mcp.store_server import _list_packs_impl

        store = MagicMock()
        store.list_packs.side_effect = RuntimeError("store broken")

        result = _list_packs_impl(store=store)
        assert "Error:" in result


class TestGetPackDetails:
    """Test _get_pack_details_impl."""

    def test_full_details(self):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        deps = [_make_mock_dependency("main", "lora", "model.safetensors")]
        pack = _make_mock_pack(
            name="RealVis",
            pack_type="checkpoint",
            base_model="SDXL 1.0",
            version="4.0",
            author="SG",
            description="A realistic model",
            trigger_words=["realistic", "photo"],
            tags=["realistic", "photography"],
            dependencies=deps,
        )

        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_details_impl(store=store, pack_name="RealVis")
        assert "Pack: RealVis" in result
        assert "Type: checkpoint" in result
        assert "Base Model: SDXL 1.0" in result
        assert "Version: 4.0" in result
        assert "Author: SG" in result
        assert "A realistic model" in result
        assert "realistic, photo" in result
        assert "Dependencies (1)" in result
        assert "model.safetensors" in result

    def test_not_found(self):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        store = MagicMock()
        store.get_pack.side_effect = Exception("not found")

        result = _get_pack_details_impl(store=store, pack_name="NoSuchPack")
        assert "not found" in result.lower()

    def test_with_parameters(self):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        params = MagicMock()
        params.sampler = "DPM++ 2M"
        params.scheduler = "Karras"
        params.steps = 30
        params.cfg_scale = 7.0
        params.clip_skip = 2
        params.width = 1024
        params.height = 1024
        params.strength = None

        pack = _make_mock_pack(name="TestPack", parameters=params)
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_details_impl(store=store, pack_name="TestPack")
        assert "Generation Parameters" in result
        assert "DPM++ 2M" in result
        assert "Karras" in result
        assert "1024x1024" in result

    def test_empty_name(self):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        result = _get_pack_details_impl(store=MagicMock(), pack_name="")
        assert "pack_name is required" in result


class TestSearchPacks:
    """Test _search_packs_impl."""

    def test_found(self):
        from src.avatar.mcp.store_server import _search_packs_impl

        item = MagicMock()
        item.pack_name = "RealVis"
        item.pack_type = "checkpoint"
        item.provider = "civitai"

        result_mock = MagicMock()
        result_mock.items = [item]

        store = MagicMock()
        store.search.return_value = result_mock

        result = _search_packs_impl(store=store, query="real")
        assert "Found 1 pack" in result
        assert "RealVis" in result
        assert "checkpoint" in result

    def test_not_found(self):
        from src.avatar.mcp.store_server import _search_packs_impl

        result_mock = MagicMock()
        result_mock.items = []

        store = MagicMock()
        store.search.return_value = result_mock

        result = _search_packs_impl(store=store, query="nonexistent")
        assert "No packs found" in result

    def test_empty_query(self):
        from src.avatar.mcp.store_server import _search_packs_impl

        result = _search_packs_impl(store=MagicMock(), query="")
        assert "query is required" in result


class TestGetPackParameters:
    """Test _get_pack_parameters_impl."""

    def test_with_parameters(self):
        from src.avatar.mcp.store_server import _get_pack_parameters_impl

        params = MagicMock()
        params.sampler = "Euler a"
        params.scheduler = "Normal"
        params.steps = 25
        params.cfg_scale = 7.5
        params.clip_skip = None
        params.denoise = 0.5
        params.width = 512
        params.height = 768
        params.strength = 0.8
        params.eta = None
        params.hires_fix = True
        params.hires_scale = 2.0
        params.hires_steps = 15

        pack = _make_mock_pack(name="MyPack", parameters=params)
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_parameters_impl(store=store, pack_name="MyPack")
        assert "Generation Parameters for MyPack" in result
        assert "Euler a" in result
        assert "Steps: 25" in result
        assert "CFG Scale: 7.5" in result
        assert "Denoise: 0.5" in result
        assert "Size: 512" not in result  # Width without height check
        assert "Strength: 0.8" in result
        assert "Hires Fix: enabled" in result
        assert "Hires Scale: 2.0" in result

    def test_without_parameters(self):
        from src.avatar.mcp.store_server import _get_pack_parameters_impl

        pack = _make_mock_pack(name="MyPack", parameters=None)
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_parameters_impl(store=store, pack_name="MyPack")
        assert "no generation parameters" in result.lower()

    def test_pack_not_found(self):
        from src.avatar.mcp.store_server import _get_pack_parameters_impl

        store = MagicMock()
        store.get_pack.side_effect = Exception("nope")

        result = _get_pack_parameters_impl(store=store, pack_name="NoSuch")
        assert "not found" in result.lower()


class TestGetInventorySummary:
    """Test _get_inventory_summary_impl."""

    def test_normal(self):
        from src.avatar.mcp.store_server import _get_inventory_summary_impl

        summary = _make_mock_inventory_summary(
            bytes_by_kind={"checkpoint": 3 * 1024 ** 3, "lora": 500 * 1024 ** 2},
            disk_total=100 * 1024 ** 3,
            disk_free=50 * 1024 ** 3,
        )

        store = MagicMock()
        store.get_inventory_summary.return_value = summary

        result = _get_inventory_summary_impl(store=store)
        assert "Inventory Summary" in result
        assert "Total blobs: 10" in result
        assert "Referenced: 8" in result
        assert "Orphan: 2" in result
        assert "checkpoint" in result
        assert "lora" in result
        assert "Disk total" in result
        assert "Disk free" in result

    def test_empty(self):
        from src.avatar.mcp.store_server import _get_inventory_summary_impl

        summary = _make_mock_inventory_summary(
            blobs_total=0,
            blobs_referenced=0,
            blobs_orphan=0,
            bytes_total=0,
            bytes_referenced=0,
            bytes_orphan=0,
        )

        store = MagicMock()
        store.get_inventory_summary.return_value = summary

        result = _get_inventory_summary_impl(store=store)
        assert "Total blobs: 0" in result


class TestFindOrphanBlobs:
    """Test _find_orphan_blobs_impl."""

    def test_found(self):
        from src.avatar.mcp.store_server import _find_orphan_blobs_impl

        items = [
            _make_mock_inventory_item(
                sha256="abcdef1234567890abcdef1234567890",
                kind="lora",
                display_name="old_model.safetensors",
                size_bytes=100 * 1024 * 1024,
            ),
        ]

        response = MagicMock()
        response.items = items

        store = MagicMock()
        store.get_inventory.return_value = response

        result = _find_orphan_blobs_impl(store=store)
        assert "Found 1 orphan blob" in result
        assert "old_model.safetensors" in result
        assert "abcdef1234567890" in result

    def test_none(self):
        from src.avatar.mcp.store_server import _find_orphan_blobs_impl

        response = MagicMock()
        response.items = []

        store = MagicMock()
        store.get_inventory.return_value = response

        result = _find_orphan_blobs_impl(store=store)
        assert "No orphan blobs found" in result


class TestFindMissingBlobs:
    """Test _find_missing_blobs_impl."""

    def test_found(self):
        from src.avatar.mcp.store_server import _find_missing_blobs_impl

        items = [
            _make_mock_inventory_item(
                sha256="deadbeef12345678deadbeef12345678",
                kind="checkpoint",
                display_name="missing_model.safetensors",
                size_bytes=2 * 1024 ** 3,
                status="missing",
                used_by_packs=["RealVis"],
            ),
        ]

        response = MagicMock()
        response.items = items

        store = MagicMock()
        store.get_inventory.return_value = response

        result = _find_missing_blobs_impl(store=store)
        assert "Found 1 missing blob" in result
        assert "missing_model.safetensors" in result
        assert "RealVis" in result

    def test_none(self):
        from src.avatar.mcp.store_server import _find_missing_blobs_impl

        response = MagicMock()
        response.items = []

        store = MagicMock()
        store.get_inventory.return_value = response

        result = _find_missing_blobs_impl(store=store)
        assert "No missing blobs" in result


class TestGetBackupStatus:
    """Test _get_backup_status_impl."""

    def test_connected(self):
        from src.avatar.mcp.store_server import _get_backup_status_impl

        status = _make_mock_backup_status()
        store = MagicMock()
        store.get_backup_status.return_value = status

        result = _get_backup_status_impl(store=store)
        assert "Connected" in result
        assert "/mnt/backup" in result
        assert "Blobs: 5" in result

    def test_disconnected(self):
        from src.avatar.mcp.store_server import _get_backup_status_impl

        status = _make_mock_backup_status(
            connected=False,
            error="Drive not mounted",
        )
        store = MagicMock()
        store.get_backup_status.return_value = status

        result = _get_backup_status_impl(store=store)
        assert "NOT connected" in result
        assert "Drive not mounted" in result

    def test_disabled(self):
        from src.avatar.mcp.store_server import _get_backup_status_impl

        status = _make_mock_backup_status(enabled=False)
        store = MagicMock()
        store.get_backup_status.return_value = status

        result = _get_backup_status_impl(store=store)
        assert "not enabled" in result


class TestCheckPackUpdates:
    """Test _check_pack_updates_impl."""

    def test_up_to_date(self):
        from src.avatar.mcp.store_server import _check_pack_updates_impl

        plan = MagicMock()
        plan.changes = []

        store = MagicMock()
        store.check_updates.return_value = plan

        result = _check_pack_updates_impl(store=store, pack_name="TestPack")
        assert "up to date" in result

    def test_has_updates(self):
        from src.avatar.mcp.store_server import _check_pack_updates_impl

        change = MagicMock()
        change.dependency_id = "main"
        change.old = {"filename": "v1.safetensors"}
        change.new = {"filename": "v2.safetensors"}

        plan = MagicMock()
        plan.changes = [change]

        store = MagicMock()
        store.check_updates.return_value = plan

        result = _check_pack_updates_impl(store=store, pack_name="TestPack")
        assert "Updates available" in result
        assert "main" in result
        assert "v1.safetensors" in result
        assert "v2.safetensors" in result

    def test_check_all_up_to_date(self):
        from src.avatar.mcp.store_server import _check_pack_updates_impl

        plan = MagicMock()
        plan.changes = []

        store = MagicMock()
        store.check_all_updates.return_value = {"Pack1": plan, "Pack2": plan}

        result = _check_pack_updates_impl(store=store, pack_name="")
        assert "All packs are up to date" in result

    def test_check_all_has_updates(self):
        from src.avatar.mcp.store_server import _check_pack_updates_impl

        change = MagicMock()
        change.dependency_id = "main"

        plan_with = MagicMock()
        plan_with.changes = [change]

        plan_without = MagicMock()
        plan_without.changes = []

        store = MagicMock()
        store.check_all_updates.return_value = {
            "Pack1": plan_with,
            "Pack2": plan_without,
        }

        result = _check_pack_updates_impl(store=store, pack_name="")
        assert "1 pack has updates" in result
        assert "Pack1" in result

    def test_specific_pack_error(self):
        from src.avatar.mcp.store_server import _check_pack_updates_impl

        store = MagicMock()
        store.check_updates.side_effect = Exception("not found")

        result = _check_pack_updates_impl(store=store, pack_name="BadPack")
        assert "Error" in result or "not found" in result.lower()


class TestGetStorageStats:
    """Test _get_storage_stats_impl."""

    def test_with_data(self):
        from src.avatar.mcp.store_server import _get_storage_stats_impl

        summary = _make_mock_inventory_summary(
            bytes_total=5 * 1024 ** 3,
            bytes_by_kind={"checkpoint": 3 * 1024 ** 3, "lora": 2 * 1024 ** 3},
            disk_total=100 * 1024 ** 3,
            disk_free=50 * 1024 ** 3,
        )

        # Mock lock for pack size calculation
        resolved = MagicMock()
        resolved.artifact.size_bytes = 2 * 1024 ** 3

        lock = MagicMock()
        lock.resolved = [resolved]

        store = MagicMock()
        store.get_inventory_summary.return_value = summary
        store.list_packs.return_value = ["BigPack"]
        store.get_pack.return_value = _make_mock_pack(name="BigPack")
        store.get_pack_lock.return_value = lock

        result = _get_storage_stats_impl(store=store)
        assert "Storage Statistics" in result
        assert "checkpoint" in result
        assert "lora" in result
        assert "Disk usage" in result
        assert "BigPack" in result

    def test_per_kind_breakdown(self):
        from src.avatar.mcp.store_server import _get_storage_stats_impl

        summary = _make_mock_inventory_summary(
            bytes_total=1024 * 1024 * 100,
            bytes_by_kind={
                "checkpoint": 1024 * 1024 * 70,
                "lora": 1024 * 1024 * 30,
            },
        )

        store = MagicMock()
        store.get_inventory_summary.return_value = summary
        store.list_packs.return_value = []

        result = _get_storage_stats_impl(store=store)
        assert "checkpoint" in result
        assert "lora" in result
        assert "%" in result  # Percentage should be shown


class TestImportGuard:
    """Test that the module is importable without mcp."""

    def test_module_importable(self):
        """Module should always be importable, even without mcp."""
        from src.avatar.mcp.store_server import MCP_AVAILABLE, _format_size

        # MCP_AVAILABLE is either True or False depending on environment
        assert isinstance(MCP_AVAILABLE, bool)
        # _format_size should always work
        assert _format_size(1024) == "1.0 KB"

    def test_impl_functions_importable(self):
        """All _impl functions should be importable without mcp."""
        from src.avatar.mcp.store_server import (
            _list_packs_impl,
            _get_pack_details_impl,
            _search_packs_impl,
            _get_pack_parameters_impl,
            _get_inventory_summary_impl,
            _find_orphan_blobs_impl,
            _find_missing_blobs_impl,
            _get_backup_status_impl,
            _check_pack_updates_impl,
            _get_storage_stats_impl,
        )

        # All should be callable
        assert callable(_list_packs_impl)
        assert callable(_get_pack_details_impl)
        assert callable(_search_packs_impl)
        assert callable(_get_pack_parameters_impl)
        assert callable(_get_inventory_summary_impl)
        assert callable(_find_orphan_blobs_impl)
        assert callable(_find_missing_blobs_impl)
        assert callable(_get_backup_status_impl)
        assert callable(_check_pack_updates_impl)
        assert callable(_get_storage_stats_impl)


class TestListPacksSingleton:
    """Test list_packs with different pack counts."""

    def test_single_pack(self):
        from src.avatar.mcp.store_server import _list_packs_impl

        store = MagicMock()
        store.list_packs.return_value = ["OnlyPack"]
        store.get_pack.return_value = _make_mock_pack(name="OnlyPack")

        result = _list_packs_impl(store=store)
        assert "Found 1 pack:" in result
        # Singular, not plural
        assert "packs" not in result.split("\n")[0]

    def test_pack_load_error_graceful(self):
        """If one pack fails to load, it should still show in the list."""
        from src.avatar.mcp.store_server import _list_packs_impl

        store = MagicMock()
        store.list_packs.return_value = ["Good", "Bad"]
        store.get_pack.side_effect = [
            _make_mock_pack(name="Good"),
            Exception("corrupt pack"),
        ]

        result = _list_packs_impl(store=store)
        assert "Good" in result
        assert "Bad" in result
        assert "error loading" in result.lower()


class TestGetPackDetailsEdgeCases:
    """Test edge cases for _get_pack_details_impl."""

    def test_long_description_truncated(self):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        pack = _make_mock_pack(description="A" * 300)
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_details_impl(store=store, pack_name="Test")
        assert "..." in result

    def test_no_source_url(self):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        pack = _make_mock_pack()
        pack.source.url = None
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_details_impl(store=store, pack_name="Test")
        assert "URL:" not in result

    def test_no_dependencies(self):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        pack = _make_mock_pack(dependencies=[])
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_details_impl(store=store, pack_name="Test")
        assert "Dependencies" not in result

    def test_source_none(self):
        """Pack with source=None should show 'unknown' source."""
        from src.avatar.mcp.store_server import _get_pack_details_impl

        pack = _make_mock_pack()
        pack.source = None
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_details_impl(store=store, pack_name="Test")
        assert "Source: unknown" in result

    def test_no_base_model(self):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        pack = _make_mock_pack(base_model=None)
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_details_impl(store=store, pack_name="Test")
        assert "Base Model" not in result


# =============================================================================
# Error path tests (all tools should handle exceptions gracefully)
# =============================================================================


class TestErrorPaths:
    """Test error handling in all tool _impl functions."""

    def test_search_error(self):
        from src.avatar.mcp.store_server import _search_packs_impl

        store = MagicMock()
        store.search.side_effect = RuntimeError("search broken")

        result = _search_packs_impl(store=store, query="test")
        assert "Error:" in result

    def test_inventory_summary_error(self):
        from src.avatar.mcp.store_server import _get_inventory_summary_impl

        store = MagicMock()
        store.get_inventory_summary.side_effect = RuntimeError("boom")

        result = _get_inventory_summary_impl(store=store)
        assert "Error:" in result

    def test_find_orphans_error(self):
        from src.avatar.mcp.store_server import _find_orphan_blobs_impl

        store = MagicMock()
        store.get_inventory.side_effect = RuntimeError("boom")

        result = _find_orphan_blobs_impl(store=store)
        assert "Error:" in result

    def test_find_missing_error(self):
        from src.avatar.mcp.store_server import _find_missing_blobs_impl

        store = MagicMock()
        store.get_inventory.side_effect = RuntimeError("boom")

        result = _find_missing_blobs_impl(store=store)
        assert "Error:" in result

    def test_backup_status_error(self):
        from src.avatar.mcp.store_server import _get_backup_status_impl

        store = MagicMock()
        store.get_backup_status.side_effect = RuntimeError("boom")

        result = _get_backup_status_impl(store=store)
        assert "Error:" in result

    def test_storage_stats_error(self):
        from src.avatar.mcp.store_server import _get_storage_stats_impl

        store = MagicMock()
        store.get_inventory_summary.side_effect = RuntimeError("boom")

        result = _get_storage_stats_impl(store=store)
        assert "Error:" in result

    def test_check_updates_all_error(self):
        from src.avatar.mcp.store_server import _check_pack_updates_impl

        store = MagicMock()
        store.check_all_updates.side_effect = RuntimeError("boom")

        result = _check_pack_updates_impl(store=store, pack_name="")
        assert "Error:" in result


# =============================================================================
# Missing branch coverage
# =============================================================================


class TestMissingBranches:
    """Test branches not covered by existing tests."""

    def test_backup_no_free_space_no_last_sync(self):
        """Backup connected but free_space=None and last_sync=None."""
        from src.avatar.mcp.store_server import _get_backup_status_impl

        status = _make_mock_backup_status(free_space=None, last_sync=None)
        store = MagicMock()
        store.get_backup_status.return_value = status

        result = _get_backup_status_impl(store=store)
        assert "Connected" in result
        assert "Free space" not in result
        assert "Last sync" not in result

    def test_backup_auto_backup_enabled(self):
        from src.avatar.mcp.store_server import _get_backup_status_impl

        status = _make_mock_backup_status(auto_backup_new=True)
        store = MagicMock()
        store.get_backup_status.return_value = status

        result = _get_backup_status_impl(store=store)
        assert "Auto-backup new: yes" in result

    def test_parameters_all_none(self):
        """Parameters object exists but all fields are None."""
        from src.avatar.mcp.store_server import _get_pack_parameters_impl

        params = MagicMock()
        params.sampler = None
        params.scheduler = None
        params.steps = None
        params.cfg_scale = None
        params.clip_skip = None
        params.denoise = None
        params.width = None
        params.height = None
        params.strength = None
        params.eta = None
        params.hires_fix = None
        params.hires_scale = None
        params.hires_steps = None

        pack = _make_mock_pack(name="EmptyParams", parameters=params)
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_parameters_impl(store=store, pack_name="EmptyParams")
        assert "no generation parameters" in result.lower()

    def test_list_packs_no_base_model(self):
        """Pack with base_model=None should not show 'Base:' suffix."""
        from src.avatar.mcp.store_server import _list_packs_impl

        store = MagicMock()
        store.list_packs.return_value = ["NoBM"]
        store.get_pack.return_value = _make_mock_pack(name="NoBM", base_model=None)

        result = _list_packs_impl(store=store)
        assert "Base:" not in result
        assert "NoBM" in result

    def test_storage_stats_no_lock(self):
        """Pack with no lock file should be skipped in top packs."""
        from src.avatar.mcp.store_server import _get_storage_stats_impl

        summary = _make_mock_inventory_summary(bytes_total=1024)
        store = MagicMock()
        store.get_inventory_summary.return_value = summary
        store.list_packs.return_value = ["NoLock"]
        store.get_pack.return_value = _make_mock_pack(name="NoLock")
        store.get_pack_lock.return_value = None

        result = _get_storage_stats_impl(store=store)
        assert "Storage Statistics" in result
        assert "Top" not in result  # No top packs section

    def test_storage_stats_no_disk_total(self):
        """When disk_total is None, no 'Disk usage' line."""
        from src.avatar.mcp.store_server import _get_storage_stats_impl

        summary = _make_mock_inventory_summary(disk_total=None, disk_free=None)
        store = MagicMock()
        store.get_inventory_summary.return_value = summary
        store.list_packs.return_value = []

        result = _get_storage_stats_impl(store=store)
        assert "Disk usage" not in result

    def test_parameters_with_width_height(self):
        """Parameters showing Width and Height as separate fields."""
        from src.avatar.mcp.store_server import _get_pack_parameters_impl

        params = MagicMock()
        params.sampler = None
        params.scheduler = None
        params.steps = None
        params.cfg_scale = None
        params.clip_skip = None
        params.denoise = None
        params.width = 512
        params.height = 768
        params.strength = None
        params.eta = None
        params.hires_fix = None

        pack = _make_mock_pack(name="Sized", parameters=params)
        store = MagicMock()
        store.get_pack.return_value = pack

        result = _get_pack_parameters_impl(store=store, pack_name="Sized")
        assert "Width: 512" in result
        assert "Height: 768" in result


# =============================================================================
# Config validation tests (Phase 1 fixes)
# =============================================================================


class TestConfigValidation:
    """Test config field validation added in review."""

    def test_invalid_provider_falls_back(self, tmp_path):
        from src.avatar.config import load_avatar_config

        config_file = tmp_path / "avatar.yaml"
        config_file.write_text('provider: "gpt"\n')

        config = load_avatar_config(synapse_root=tmp_path, config_path=config_file)
        assert config.provider == "gemini"  # Fallback

    def test_invalid_safety_falls_back(self, tmp_path):
        from src.avatar.config import load_avatar_config

        config_file = tmp_path / "avatar.yaml"
        config_file.write_text('engine:\n  safety_instructions: "yolo"\n')

        config = load_avatar_config(synapse_root=tmp_path, config_path=config_file)
        assert config.safety == "safe"  # Fallback

    def test_valid_provider_accepted(self, tmp_path):
        from src.avatar.config import load_avatar_config

        config_file = tmp_path / "avatar.yaml"
        config_file.write_text('provider: "claude"\n')

        config = load_avatar_config(synapse_root=tmp_path, config_path=config_file)
        assert config.provider == "claude"

    def test_valid_safety_accepted(self, tmp_path):
        from src.avatar.config import load_avatar_config

        config_file = tmp_path / "avatar.yaml"
        config_file.write_text('engine:\n  safety_instructions: "unrestricted"\n')

        config = load_avatar_config(synapse_root=tmp_path, config_path=config_file)
        assert config.safety == "unrestricted"


class TestRoutesCaching:
    """Test config caching in routes."""

    def test_cache_invalidation(self):
        from src.avatar.routes import invalidate_avatar_cache, _cache

        _cache["config"] = "old"
        _cache["ts"] = 999999.0

        invalidate_avatar_cache()

        assert _cache["config"] is None
        assert _cache["ts"] == 0.0


# =============================================================================
# Civitai tools (Group A)
# =============================================================================


def _make_fake_civitai(models=None):
    """Create a mock CivitaiClient."""
    civitai = MagicMock()
    if models is None:
        models = []
    civitai.search_models.return_value = {
        "items": models,
        "metadata": {"totalItems": len(models), "currentPage": 1, "pageSize": 10},
    }
    return civitai


class TestSearchCivitai:
    """Test _search_civitai_impl."""

    def test_found(self):
        from src.avatar.mcp.store_server import _search_civitai_impl

        models = [
            {
                "id": 123, "name": "RealVis", "type": "Checkpoint",
                "modelVersions": [{"name": "v4.0", "baseModel": "SDXL 1.0"}],
            }
        ]
        civitai = _make_fake_civitai(models)

        result = _search_civitai_impl(civitai=civitai, query="RealVis")
        assert "Found 1 model" in result
        assert "RealVis" in result
        assert "Checkpoint" in result
        assert "ID: 123" in result

    def test_empty_results(self):
        from src.avatar.mcp.store_server import _search_civitai_impl

        civitai = _make_fake_civitai([])

        result = _search_civitai_impl(civitai=civitai, query="nonexistent")
        assert "No models found" in result

    def test_missing_query(self):
        from src.avatar.mcp.store_server import _search_civitai_impl

        result = _search_civitai_impl(civitai=MagicMock(), query="")
        assert "query is required" in result

    def test_api_error(self):
        from src.avatar.mcp.store_server import _search_civitai_impl

        civitai = MagicMock()
        civitai.search_models.side_effect = RuntimeError("API down")

        result = _search_civitai_impl(civitai=civitai, query="test")
        assert "Error:" in result


class TestAnalyzeCivitaiModel:
    """Test _analyze_civitai_model_impl."""

    def test_model_with_versions(self):
        from src.avatar.mcp.store_server import _analyze_civitai_model_impl

        civitai = MagicMock()
        civitai.parse_civitai_url.return_value = (123, None)
        civitai.get_model.return_value = {
            "id": 123, "name": "TestModel", "type": "LORA",
            "tags": ["style", "anime"],
            "creator": {"username": "ArtistX"},
            "description": "A nice model",
            "modelVersions": [
                {
                    "id": 456, "name": "v2.0", "baseModel": "SDXL",
                    "files": [{"name": "test.safetensors", "sizeKB": 2048, "primary": True}],
                    "trainedWords": ["style_x"],
                },
                {
                    "id": 457, "name": "v1.0", "baseModel": "SD 1.5",
                    "files": [{"name": "test_v1.safetensors", "sizeKB": 1024}],
                    "trainedWords": [],
                },
            ],
        }

        result = _analyze_civitai_model_impl(civitai=civitai, url="https://civitai.com/models/123")
        assert "Model: TestModel" in result
        assert "Type: LORA" in result
        assert "Creator: ArtistX" in result
        assert "style, anime" in result
        assert "Versions (2)" in result
        assert "v2.0" in result
        assert "v1.0" in result
        assert "test.safetensors" in result
        assert "style_x" in result

    def test_single_version(self):
        from src.avatar.mcp.store_server import _analyze_civitai_model_impl

        civitai = MagicMock()
        civitai.parse_civitai_url.return_value = (99, None)
        civitai.get_model.return_value = {
            "id": 99, "name": "Simple", "type": "VAE",
            "tags": [], "creator": None, "description": "",
            "modelVersions": [
                {"id": 100, "name": "v1", "baseModel": "SDXL", "files": [], "trainedWords": []},
            ],
        }

        result = _analyze_civitai_model_impl(civitai=civitai, url="https://civitai.com/models/99")
        assert "Model: Simple" in result
        assert "Versions (1)" in result

    def test_invalid_url(self):
        from src.avatar.mcp.store_server import _analyze_civitai_model_impl

        civitai = MagicMock()
        civitai.parse_civitai_url.side_effect = ValueError("Invalid Civitai URL: bad")

        result = _analyze_civitai_model_impl(civitai=civitai, url="bad")
        assert "Error:" in result

    def test_api_error(self):
        from src.avatar.mcp.store_server import _analyze_civitai_model_impl

        civitai = MagicMock()
        civitai.parse_civitai_url.return_value = (123, None)
        civitai.get_model.side_effect = RuntimeError("API error")

        result = _analyze_civitai_model_impl(civitai=civitai, url="https://civitai.com/models/123")
        assert "Error:" in result


class TestCompareModelVersions:
    """Test _compare_model_versions_impl."""

    def test_multiple_versions(self):
        from src.avatar.mcp.store_server import _compare_model_versions_impl

        civitai = MagicMock()
        civitai.parse_civitai_url.return_value = (123, None)
        civitai.get_model.return_value = {
            "id": 123, "name": "TestModel", "type": "LORA",
            "modelVersions": [
                {
                    "name": "v2.0", "baseModel": "SDXL",
                    "files": [{"sizeKB": 2048}], "trainedWords": ["a", "b"],
                    "publishedAt": "2026-01-15T10:00:00Z",
                },
                {
                    "name": "v1.0", "baseModel": "SD 1.5",
                    "files": [{"sizeKB": 1024}], "trainedWords": ["a"],
                    "publishedAt": "2025-06-01T10:00:00Z",
                },
            ],
        }

        result = _compare_model_versions_impl(civitai=civitai, url="https://civitai.com/models/123")
        assert "Version comparison" in result
        assert "v2.0" in result
        assert "v1.0" in result
        assert "Base Model" in result

    def test_single_version(self):
        from src.avatar.mcp.store_server import _compare_model_versions_impl

        civitai = MagicMock()
        civitai.parse_civitai_url.return_value = (123, None)
        civitai.get_model.return_value = {
            "id": 123, "name": "Solo", "type": "LORA",
            "modelVersions": [{"name": "v1.0"}],
        }

        result = _compare_model_versions_impl(civitai=civitai, url="https://civitai.com/models/123")
        assert "only 1 version" in result

    def test_api_error(self):
        from src.avatar.mcp.store_server import _compare_model_versions_impl

        civitai = MagicMock()
        civitai.parse_civitai_url.return_value = (123, None)
        civitai.get_model.side_effect = RuntimeError("boom")

        result = _compare_model_versions_impl(civitai=civitai, url="https://civitai.com/models/123")
        assert "Error:" in result


class TestImportCivitaiModel:
    """Test _import_civitai_model_impl."""

    def test_successful_import(self):
        from src.avatar.mcp.store_server import _import_civitai_model_impl

        pack = MagicMock()
        pack.name = "ImportedPack"
        pack_type = MagicMock()
        pack_type.value = "lora"
        pack.pack_type = pack_type
        pack.base_model = "SDXL"
        pack.dependencies = [MagicMock(), MagicMock()]
        source = MagicMock()
        source.url = "https://civitai.com/models/123"
        pack.source = source

        store = MagicMock()
        store.import_civitai.return_value = pack

        result = _import_civitai_model_impl(store=store, url="https://civitai.com/models/123")
        assert "Successfully imported" in result
        assert "ImportedPack" in result
        assert "lora" in result
        assert "Dependencies: 2" in result

    def test_custom_name(self):
        from src.avatar.mcp.store_server import _import_civitai_model_impl

        pack = MagicMock()
        pack.name = "CustomName"
        pack_type = MagicMock()
        pack_type.value = "checkpoint"
        pack.pack_type = pack_type
        pack.base_model = None
        pack.dependencies = []
        pack.source = None

        store = MagicMock()
        store.import_civitai.return_value = pack

        result = _import_civitai_model_impl(store=store, url="https://civitai.com/models/123", pack_name="CustomName")
        assert "CustomName" in result
        store.import_civitai.assert_called_once()
        call_kwargs = store.import_civitai.call_args[1]
        assert call_kwargs["pack_name"] == "CustomName"

    def test_invalid_url(self):
        from src.avatar.mcp.store_server import _import_civitai_model_impl

        store = MagicMock()
        store.import_civitai.side_effect = ValueError("Invalid URL")

        result = _import_civitai_model_impl(store=store, url="bad-url")
        assert "Error:" in result

    def test_import_error(self):
        from src.avatar.mcp.store_server import _import_civitai_model_impl

        store = MagicMock()
        store.import_civitai.side_effect = RuntimeError("Download failed")

        result = _import_civitai_model_impl(store=store, url="https://civitai.com/models/123")
        assert "Error:" in result


# =============================================================================
# Workflow tools (Group B)
# =============================================================================


def _make_workflow_json(nodes=None):
    """Create a workflow JSON string."""
    import json
    return json.dumps({"nodes": nodes or []})


class TestScanWorkflow:
    """Test _scan_workflow_impl."""

    def test_workflow_with_assets_and_nodes(self):
        from src.avatar.mcp.store_server import _scan_workflow_impl

        workflow = _make_workflow_json([
            {
                "id": 1, "type": "CheckpointLoaderSimple",
                "widgets_values": ["sdxl_base.safetensors"],
                "inputs": {}, "outputs": [], "properties": {},
            },
            {
                "id": 2, "type": "LoraLoader",
                "widgets_values": ["detail_tweaker.safetensors", 0.8, 0.8],
                "inputs": {}, "outputs": [], "properties": {},
            },
            {
                "id": 3, "type": "VHS_VideoCombine",
                "widgets_values": [],
                "inputs": {}, "outputs": [], "properties": {},
            },
        ])

        result = _scan_workflow_impl(workflow_json=workflow)
        assert "Workflow Scan Results" in result
        assert "Nodes: 3" in result
        assert "sdxl_base.safetensors" in result
        assert "detail_tweaker.safetensors" in result
        assert "VHS_VideoCombine" in result

    def test_empty_workflow(self):
        from src.avatar.mcp.store_server import _scan_workflow_impl

        result = _scan_workflow_impl(workflow_json=_make_workflow_json([]))
        assert "No model dependencies or custom nodes found" in result

    def test_invalid_json(self):
        from src.avatar.mcp.store_server import _scan_workflow_impl

        result = _scan_workflow_impl(workflow_json="{bad json")
        assert "Invalid JSON" in result

    def test_no_assets(self):
        from src.avatar.mcp.store_server import _scan_workflow_impl

        workflow = _make_workflow_json([
            {
                "id": 1, "type": "SaveImage",
                "widgets_values": ["output"],
                "inputs": {}, "outputs": [], "properties": {},
            },
        ])

        result = _scan_workflow_impl(workflow_json=workflow)
        assert "No model dependencies or custom nodes found" in result


class TestScanWorkflowFile:
    """Test _scan_workflow_file_impl."""

    def test_valid_file(self, tmp_path):
        from src.avatar.mcp.store_server import _scan_workflow_file_impl
        import json

        workflow_file = tmp_path / "test.json"
        workflow_file.write_text(json.dumps({
            "nodes": [
                {
                    "id": 1, "type": "CheckpointLoaderSimple",
                    "widgets_values": ["model.safetensors"],
                    "inputs": {}, "outputs": [], "properties": {},
                },
            ]
        }))

        result = _scan_workflow_file_impl(path=str(workflow_file))
        assert "test.json" in result
        assert "model.safetensors" in result

    def test_nonexistent_file(self):
        from src.avatar.mcp.store_server import _scan_workflow_file_impl

        result = _scan_workflow_file_impl(path="/tmp/no_such_file_12345.json")
        assert "File not found" in result

    def test_non_json_extension_rejected(self, tmp_path):
        from src.avatar.mcp.store_server import _scan_workflow_file_impl

        # Security: non-json files should be rejected
        txt_file = tmp_path / "secret.txt"
        txt_file.write_text("secret data")

        result = _scan_workflow_file_impl(path=str(txt_file))
        assert "Only .json" in result

    def test_invalid_json_file(self, tmp_path):
        from src.avatar.mcp.store_server import _scan_workflow_file_impl

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json")

        result = _scan_workflow_file_impl(path=str(bad_file))
        assert "Error" in result


class TestCheckWorkflowAvailability:
    """Test _check_workflow_availability_impl."""

    def test_all_available(self):
        from src.avatar.mcp.store_server import _check_workflow_availability_impl

        workflow = _make_workflow_json([
            {
                "id": 1, "type": "CheckpointLoaderSimple",
                "widgets_values": ["model_a.safetensors"],
                "inputs": {}, "outputs": [], "properties": {},
            },
        ])

        # Mock store inventory
        item = MagicMock()
        item.display_name = "model_a.safetensors"
        response = MagicMock()
        response.items = [item]

        store = MagicMock()
        store.get_inventory.return_value = response

        result = _check_workflow_availability_impl(store=store, workflow_json=workflow)
        assert "Available locally" in result
        assert "model_a.safetensors" in result
        assert "All dependencies are available locally" in result

    def test_some_missing(self):
        from src.avatar.mcp.store_server import _check_workflow_availability_impl

        workflow = _make_workflow_json([
            {
                "id": 1, "type": "CheckpointLoaderSimple",
                "widgets_values": ["model_a.safetensors"],
                "inputs": {}, "outputs": [], "properties": {},
            },
            {
                "id": 2, "type": "LoraLoader",
                "widgets_values": ["missing_lora.safetensors", 0.8, 0.8],
                "inputs": {}, "outputs": [], "properties": {},
            },
        ])

        item = MagicMock()
        item.display_name = "model_a.safetensors"
        response = MagicMock()
        response.items = [item]

        store = MagicMock()
        store.get_inventory.return_value = response

        result = _check_workflow_availability_impl(store=store, workflow_json=workflow)
        assert "Available locally (1)" in result
        assert "Missing (1)" in result
        assert "missing_lora.safetensors" in result

    def test_empty_workflow(self):
        from src.avatar.mcp.store_server import _check_workflow_availability_impl

        result = _check_workflow_availability_impl(store=MagicMock(), workflow_json=_make_workflow_json([]))
        assert "No model dependencies found" in result


class TestListCustomNodes:
    """Test _list_custom_nodes_impl."""

    def test_known_nodes_resolved(self):
        from src.avatar.mcp.store_server import _list_custom_nodes_impl

        workflow = _make_workflow_json([
            {
                "id": 1, "type": "VHS_VideoCombine",
                "widgets_values": [],
                "inputs": {}, "outputs": [], "properties": {},
            },
        ])

        result = _list_custom_nodes_impl(workflow_json=workflow)
        assert "ComfyUI-VideoHelperSuite" in result
        assert "github.com" in result

    def test_unknown_node(self):
        from src.avatar.mcp.store_server import _list_custom_nodes_impl

        workflow = _make_workflow_json([
            {
                "id": 1, "type": "SomeRandomCustomNode",
                "widgets_values": [],
                "inputs": {}, "outputs": [], "properties": {},
            },
        ])

        result = _list_custom_nodes_impl(workflow_json=workflow)
        assert "Unresolved" in result
        assert "SomeRandomCustomNode" in result

    def test_no_custom_nodes(self):
        from src.avatar.mcp.store_server import _list_custom_nodes_impl

        workflow = _make_workflow_json([
            {
                "id": 1, "type": "CheckpointLoaderSimple",
                "widgets_values": ["model.safetensors"],
                "inputs": {}, "outputs": [], "properties": {},
            },
        ])

        result = _list_custom_nodes_impl(workflow_json=workflow)
        assert "No custom nodes found" in result


# =============================================================================
# Dependency resolution tools (Group C)
# =============================================================================


class TestResolveWorkflowDeps:
    """Test _resolve_workflow_deps_impl."""

    def test_mixed_sources(self):
        from src.avatar.mcp.store_server import _resolve_workflow_deps_impl

        workflow = _make_workflow_json([
            {
                "id": 1, "type": "CheckpointLoaderSimple",
                "widgets_values": ["umt5_xxl_fp8_e4m3fn_scaled.safetensors"],
                "inputs": {}, "outputs": [], "properties": {},
            },
            {
                "id": 2, "type": "VHS_VideoCombine",
                "widgets_values": [],
                "inputs": {}, "outputs": [], "properties": {},
            },
        ])

        result = _resolve_workflow_deps_impl(workflow_json=workflow)
        assert "Model Assets" in result
        assert "huggingface" in result
        assert "Custom Node Packages" in result

    def test_all_local(self):
        from src.avatar.mcp.store_server import _resolve_workflow_deps_impl

        workflow = _make_workflow_json([
            {
                "id": 1, "type": "CheckpointLoaderSimple",
                "widgets_values": ["random_local_model.safetensors"],
                "inputs": {}, "outputs": [], "properties": {},
            },
        ])

        result = _resolve_workflow_deps_impl(workflow_json=workflow)
        assert "Model Assets" in result
        assert "random_local_model.safetensors" in result

    def test_empty_workflow(self):
        from src.avatar.mcp.store_server import _resolve_workflow_deps_impl

        result = _resolve_workflow_deps_impl(workflow_json=_make_workflow_json([]))
        assert "No dependencies found" in result


class TestFindModelByHash:
    """Test _find_model_by_hash_impl."""

    def test_found(self):
        from src.avatar.mcp.store_server import _find_model_by_hash_impl

        version = MagicMock()
        version.name = "v2.0"
        version.id = 456
        version.model_id = 123
        version.base_model = "SDXL"
        version.model_name = "TestModel"
        version.files = [{"name": "test.safetensors"}]

        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = version

        result = _find_model_by_hash_impl(civitai=civitai, hash_value="abcdef1234567890")
        assert "Found model version" in result
        assert "v2.0" in result
        assert "TestModel" in result

    def test_not_found(self):
        from src.avatar.mcp.store_server import _find_model_by_hash_impl

        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = None

        result = _find_model_by_hash_impl(civitai=civitai, hash_value="deadbeef")
        assert "No model found" in result

    def test_api_error(self):
        from src.avatar.mcp.store_server import _find_model_by_hash_impl

        civitai = MagicMock()
        civitai.get_model_by_hash.side_effect = RuntimeError("API error")

        result = _find_model_by_hash_impl(civitai=civitai, hash_value="abcdef")
        assert "Error:" in result


class TestSuggestAssetSources:
    """Test _suggest_asset_sources_impl."""

    def test_known_hf_model(self):
        from src.avatar.mcp.store_server import _suggest_asset_sources_impl

        result = _suggest_asset_sources_impl(
            asset_names="umt5_xxl_fp8_e4m3fn_scaled.safetensors"
        )
        assert "huggingface" in result
        assert "HF Repo:" in result

    def test_civitai_pattern(self):
        from src.avatar.mcp.store_server import _suggest_asset_sources_impl

        result = _suggest_asset_sources_impl(asset_names="anime_pony_v5.safetensors")
        assert "civitai" in result

    def test_unknown_model(self):
        from src.avatar.mcp.store_server import _suggest_asset_sources_impl

        result = _suggest_asset_sources_impl(asset_names="completely_unknown_file.bin")
        assert "local" in result

    def test_empty_input(self):
        from src.avatar.mcp.store_server import _suggest_asset_sources_impl

        result = _suggest_asset_sources_impl(asset_names="")
        assert "asset_names is required" in result


class TestNewImplFunctionsImportable:
    """Test that all new _impl functions are importable without mcp."""

    def test_all_new_impls_importable(self):
        from src.avatar.mcp.store_server import (
            _search_civitai_impl,
            _analyze_civitai_model_impl,
            _compare_model_versions_impl,
            _import_civitai_model_impl,
            _scan_workflow_impl,
            _scan_workflow_file_impl,
            _check_workflow_availability_impl,
            _list_custom_nodes_impl,
            _resolve_workflow_deps_impl,
            _find_model_by_hash_impl,
            _suggest_asset_sources_impl,
        )

        assert callable(_search_civitai_impl)
        assert callable(_analyze_civitai_model_impl)
        assert callable(_compare_model_versions_impl)
        assert callable(_import_civitai_model_impl)
        assert callable(_scan_workflow_impl)
        assert callable(_scan_workflow_file_impl)
        assert callable(_check_workflow_availability_impl)
        assert callable(_list_custom_nodes_impl)
        assert callable(_resolve_workflow_deps_impl)
        assert callable(_find_model_by_hash_impl)
        assert callable(_suggest_asset_sources_impl)
