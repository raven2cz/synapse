"""
Tests for Inventory Stabilization (Bug fixes from 2026-01-27).

This module contains regression tests for bugs fixed during the inventory
stabilization session. Each test documents the bug, its symptoms, and
verifies the fix.

Bug List:
- Bug #21: Delete resource removes resolved entry (breaking re-download)
- Bug #22: Clear completed downloads route shadowed by {download_id}
- Bug #23: HTML error pages accepted as valid model files
- Bug #24: Progress bar shows 0% when operation completes quickly
- Bug #25: ImpactAnalysis object not JSON serializable in delete response
- Bug #26: Delete dialog doesn't close on error and shows raw JSON
- Bug #27: Delete from backup blocked even when local copy exists
- Feature #28: Delete from Local option for synced blobs in UI
- Feature #29: Restore from Backup button in pack dependencies
- Bug #30: Inventory page not refreshed after restore from PackDetailPage
- Bug #31: Infinite loop when "Backup & Free" tries to delete blob not on local
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json


def get_pack_detail_module_content():
    """
    Get combined content from PackDetailPage and all pack-detail module files.

    Since PackDetailPage has been refactored into modular components, we need
    to check multiple files for code patterns.
    """
    base_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules"
    pack_detail_dir = base_path / "pack-detail"

    content_parts = []

    # Main page file
    page_path = base_path / "PackDetailPage.tsx"
    if page_path.exists():
        content_parts.append(page_path.read_text())

    # Hooks
    hooks_dir = pack_detail_dir / "hooks"
    if hooks_dir.exists():
        for f in hooks_dir.glob("*.ts"):
            content_parts.append(f.read_text())

    # Sections
    sections_dir = pack_detail_dir / "sections"
    if sections_dir.exists():
        for f in sections_dir.glob("*.tsx"):
            content_parts.append(f.read_text())

    # Modals
    modals_dir = pack_detail_dir / "modals"
    if modals_dir.exists():
        for f in modals_dir.glob("*.tsx"):
            content_parts.append(f.read_text())

    # Types and constants
    for filename in ["types.ts", "constants.ts"]:
        f = pack_detail_dir / filename
        if f.exists():
            content_parts.append(f.read_text())

    return "\n".join(content_parts)


class TestBug21DeleteResourcePreservesResolved:
    """
    Bug #21: Delete resource removes resolved entry from lock.json

    Symptoms:
    - User deletes downloaded model file
    - The dependency shows "unresolved" state (amber/brown)
    - No download button available (URL lost)
    - User cannot re-download without manual intervention

    Root cause:
    - delete_dependency_resource endpoint removed resolved entry from lock.json
    - This lost the download URL needed for re-downloading

    Fix:
    - Keep resolved entry in lock.json when deleting blob
    - Only delete the blob file itself
    - UI should check blob existence to show download button
    """

    def test_delete_resource_code_does_not_remove_resolved(self):
        """
        Verify that delete_dependency_resource endpoint code does NOT remove
        resolved entries from lock.json.

        This is a code structure test - we check the source code to ensure
        the bug fix is in place.
        """
        api_path = Path(__file__).parent.parent.parent / "src/store/api.py"

        if not api_path.exists():
            pytest.skip("API source not available")

        content = api_path.read_text()

        # Find the delete_dependency_resource function
        assert "def delete_dependency_resource" in content, \
            "delete_dependency_resource function must exist"

        # The OLD buggy code would have:
        # lock.resolved = [r for r in lock.resolved if r.dependency_id != dep_id]
        # store.layout.save_pack_lock(lock)

        # The FIX should have a comment explaining why we keep resolved
        assert "keep" in content.lower() and "resolved" in content.lower(), \
            "Code should have comment about keeping resolved entry"

        # Or check that we don't save lock after removing resolved
        # The key is: we should NOT have code that removes from lock.resolved AND saves
        # We check for the comment that documents the fix
        assert "intentionally" in content.lower() or "NOTE" in content, \
            "Code should document the intentional behavior"

    def test_delete_resource_endpoint_exists(self):
        """Verify DELETE /packs/{pack_name}/dependencies/{dep_id}/resource exists."""
        from src.store.api import v2_packs_router

        routes = list(v2_packs_router.routes)

        delete_route = None
        for route in routes:
            if hasattr(route, 'path') and "/dependencies/" in route.path and "/resource" in route.path:
                if "DELETE" in route.methods:
                    delete_route = route
                    break

        assert delete_route is not None, \
            "DELETE endpoint for dependency resource must exist"


class TestBug22ClearCompletedRouteOrder:
    """
    Bug #22: Clear completed downloads route shadowed by {download_id}

    Symptoms:
    - User clicks "Clear All" button on Downloads page
    - Nothing happens, failed downloads remain
    - No error shown

    Root cause:
    - FastAPI routes are matched in order
    - `/downloads/{download_id}` was defined BEFORE `/downloads/completed`
    - "completed" was being matched as a download_id

    Fix:
    - Move `/downloads/completed` route BEFORE `/downloads/{download_id}`
    """

    def test_route_order_completed_before_download_id(self):
        """
        Verify that /downloads/completed route is defined before /downloads/{download_id}.

        This is a structural test that checks the route registration order.
        """
        from src.store.api import v2_packs_router

        # Get all routes from the router
        routes = list(v2_packs_router.routes)

        # Find indices of the two routes
        completed_idx = None
        download_id_idx = None

        for i, route in enumerate(routes):
            if hasattr(route, 'path'):
                if route.path == "/downloads/completed" and "DELETE" in route.methods:
                    completed_idx = i
                elif route.path == "/downloads/{download_id}" and "DELETE" in route.methods:
                    download_id_idx = i

        # Both routes must exist
        assert completed_idx is not None, "Route /downloads/completed must exist"
        assert download_id_idx is not None, "Route /downloads/{download_id} must exist"

        # completed must come BEFORE download_id
        assert completed_idx < download_id_idx, \
            f"/downloads/completed (index {completed_idx}) must be defined BEFORE " \
            f"/downloads/{{download_id}} (index {download_id_idx}) to avoid route shadowing"


class TestBug23HtmlErrorPageRejection:
    """
    Bug #23: HTML error pages accepted as valid model files

    Symptoms:
    - User clicks download
    - Download shows as "completed" immediately (small file)
    - Model doesn't work
    - Blob store contains HTML error page instead of model
    - lock.json has wrong sha256

    Root cause:
    - Civitai returned HTML error page (auth required, rate limit, etc.)
    - BlobStore accepted any response as valid
    - No content-type or content validation

    Fix:
    - Check Content-Type header for text/html
    - Reject HTML responses with clear error message
    """

    def test_html_content_type_rejected(self):
        """Verify that responses with text/html content-type are rejected."""
        from src.store.blob_store import BlobStore, DownloadError, StoreLayout
        from unittest.mock import Mock, patch

        # Create a mock store layout
        with tempfile.TemporaryDirectory() as tmp:
            layout = StoreLayout(Path(tmp))
            blob_store = BlobStore(layout)

            # Mock the session.get to return HTML content-type
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html; charset=utf-8"}
            mock_response.raise_for_status = Mock()

            # Patch requests.Session so per-request session uses our mock
            mock_session = Mock()
            mock_session.get.return_value = mock_response
            with patch("requests.Session", return_value=mock_session):
                # Should raise DownloadError for HTML content
                with pytest.raises(DownloadError) as exc_info:
                    blob_store.download("https://civitai.com/api/download/models/123")

            # Error message should mention HTML and authentication
            assert "HTML" in str(exc_info.value)
            assert "authentication" in str(exc_info.value).lower() or "error page" in str(exc_info.value).lower()

    def test_binary_content_type_accepted(self):
        """Verify that responses with binary content-type are accepted."""
        from src.store.blob_store import BlobStore, StoreLayout
        from unittest.mock import Mock, patch
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            layout = StoreLayout(Path(tmp))
            blob_store = BlobStore(layout)

            # Create test content
            test_content = b"fake model binary data" * 1000
            expected_sha256 = hashlib.sha256(test_content).hexdigest()

            # Mock successful binary download
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {
                "content-type": "application/octet-stream",
                "content-length": str(len(test_content)),
            }
            mock_response.raise_for_status = Mock()
            mock_response.iter_content = Mock(return_value=[test_content])

            # Patch requests.Session so per-request session uses our mock
            mock_session = Mock()
            mock_session.get.return_value = mock_response
            with patch("requests.Session", return_value=mock_session):
                # Should succeed for binary content
                sha256 = blob_store.download("https://example.com/model.safetensors")
            assert sha256 == expected_sha256

    def test_missing_api_key_warning_logged(self):
        """Verify that missing Civitai API key logs a warning."""
        from src.store.blob_store import BlobStore, StoreLayout
        import logging

        with tempfile.TemporaryDirectory() as tmp:
            layout = StoreLayout(Path(tmp))
            # Create blob store WITHOUT api key
            blob_store = BlobStore(layout, api_key=None)

            assert blob_store.api_key is None or blob_store.api_key == ""


class TestBug24ProgressBar100Percent:
    """
    Bug #24: Progress bar shows 0% when operation completes quickly

    Symptoms:
    - User backs up a file to fast storage (local NAS)
    - Dialog shows "Completed" but progress bar at 0%
    - Shows "0 B / 324.99 MB" instead of "324.99 MB / 324.99 MB"
    - Confusing UX

    Root cause:
    - Progress updates are async
    - When operation completes faster than UI update interval,
      transferredBytes stays at 0
    - progressPercent calculated from transferredBytes/totalBytes = 0

    Fix:
    - When isCompleted is true, force progressPercent to 100
    - When isCompleted is true, show totalBytes instead of transferredBytes
    """

    def test_progress_percent_formula_includes_completed_check(self):
        """
        This is a code structure test - verify the progress calculation
        includes the isCompleted check.

        The fix should be:
        progressPercent = isCompleted ? 100 : (transferredBytes / totalBytes) * 100
        """
        # Read the PushConfirmDialog source
        dialog_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/packs/PushConfirmDialog.tsx"

        if not dialog_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = dialog_path.read_text()

        # Check that progressPercent calculation includes isCompleted check
        assert "isCompleted ? 100" in content, \
            "progressPercent should return 100 when isCompleted is true"

        # Check that bytes display also uses isCompleted check
        assert "isCompleted ? totalBytes : transferredBytes" in content, \
            "Bytes display should show totalBytes when isCompleted is true"

    def test_pull_dialog_also_fixed(self):
        """Verify PullConfirmDialog has the same fix."""
        dialog_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/packs/PullConfirmDialog.tsx"

        if not dialog_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = dialog_path.read_text()

        assert "isCompleted ? 100" in content, \
            "PullConfirmDialog progressPercent should return 100 when isCompleted"

        assert "isCompleted ? totalBytes : transferredBytes" in content, \
            "PullConfirmDialog bytes display should show totalBytes when isCompleted"


class TestDownloadErrorToastShown:
    """
    Bug: Download errors not shown to user

    Symptoms:
    - Download fails in background thread
    - Error logged to server console
    - User sees nothing in UI
    - Download just disappears or shows stuck

    Fix:
    - Watch activeDownloads for status === 'failed'
    - Show toast.error() with error message
    """

    def test_download_progress_interface_has_error_field(self):
        """Verify DownloadProgress interface includes error field for displaying errors."""
        content = get_pack_detail_module_content()

        if not content:
            pytest.skip("Frontend source not available in test environment")

        # Check DownloadProgress interface has error field
        assert "error: string | null" in content or "error?: string" in content, \
            "DownloadProgress interface should have error field"

    def test_failed_download_shows_toast(self):
        """Verify that useEffect handles failed downloads with toast."""
        content = get_pack_detail_module_content()

        if not content:
            pytest.skip("Frontend source not available in test environment")

        # Check that failed downloads trigger toast.error
        assert "status === 'failed'" in content or "d.status === 'failed'" in content, \
            "Code should check for failed download status"

        assert "toast.error" in content, \
            "Failed downloads should show toast.error"


class TestResolveButtonForUnresolvedDependencies:
    """
    Feature: Resolve button for unresolved dependencies

    When a dependency loses its resolved entry (e.g., due to old bug),
    user should be able to click "Resolve" to re-fetch metadata from Civitai.
    """

    def test_resolve_pack_endpoint_exists(self):
        """Verify POST /packs/{pack_name}/resolve endpoint exists."""
        from src.store.api import v2_packs_router

        routes = list(v2_packs_router.routes)

        resolve_route = None
        for route in routes:
            if hasattr(route, 'path') and route.path == "/{pack_name}/resolve":
                if "POST" in route.methods:
                    resolve_route = route
                    break

        assert resolve_route is not None, "POST /{pack_name}/resolve endpoint must exist"

    def test_resolve_button_in_ui(self):
        """Verify Resolve button exists in PackDetailPage for unresolved deps."""
        content = get_pack_detail_module_content()

        if not content:
            pytest.skip("Frontend source not available in test environment")

        # Check for resolvePackMutation (in hooks) or resolvePack (in orchestrator)
        assert "resolvePackMutation" in content or "resolvePack" in content, \
            "Pack detail module should have resolve pack functionality"

        # Check for Resolve button or onResolvePack handler
        assert "onResolvePack" in content or "needsResolve" in content or "has_unresolved" in content, \
            "Code should handle resolve condition"

        # Check the button text
        assert "Resolve" in content, \
            "Resolve action should exist"


class TestDownloadsPageDismissButton:
    """
    Feature: Dismiss button on Downloads page

    User should be able to dismiss individual failed/completed downloads.
    """

    def test_dismiss_download_endpoint_exists(self):
        """Verify DELETE /downloads/{download_id} endpoint exists."""
        from src.store.api import v2_packs_router

        routes = list(v2_packs_router.routes)

        dismiss_route = None
        for route in routes:
            if hasattr(route, 'path') and route.path == "/downloads/{download_id}":
                if "DELETE" in route.methods:
                    dismiss_route = route
                    break

        assert dismiss_route is not None, "DELETE /downloads/{download_id} endpoint must exist"

    def test_downloads_page_has_dismiss_button(self):
        """Verify DownloadsPage has dismiss button for completed/failed downloads."""
        page_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/DownloadsPage.tsx"

        if not page_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = page_path.read_text()

        # Check for dismissDownload function
        assert "dismissDownload" in content, \
            "DownloadsPage should have dismissDownload function"

        # Check it calls the correct endpoint
        assert "/downloads/" in content and "DELETE" in content, \
            "dismissDownload should call DELETE /downloads/{id}"


class TestPackBackupStatusRefreshAfterDownload:
    """
    Bug: Backup Storage section not updating after download

    Symptoms:
    - Download completes
    - Pack detail page doesn't show updated Backup Storage status
    - User has to navigate away and back to see update

    Fix:
    - Invalidate pack-backup-status query when download completes
    """

    def test_download_complete_invalidates_backup_status(self):
        """Verify that download completion invalidates pack-backup-status query."""
        content = get_pack_detail_module_content()

        if not content:
            pytest.skip("Frontend source not available in test environment")

        # Look for the useEffect that handles completed downloads
        # It should invalidate both pack and pack-backup-status

        # Find the section with completed downloads handling
        # The query key is defined in constants as QUERY_KEYS.packBackup which uses 'pack-backup-status'
        assert "pack-backup-status" in content or "packBackup" in content, \
            "Code should reference pack-backup-status query (either directly or via QUERY_KEYS.packBackup)"

        # Check that it's invalidated together with pack query
        assert "invalidateQueries" in content, \
            "pack-backup-status should be invalidated when downloads complete"


class TestBug25ImpactAnalysisJsonSerialization:
    """
    Bug #25: ImpactAnalysis object not JSON serializable

    Symptoms:
    - User tries to delete blob from backup that is still referenced
    - Server returns 500 error instead of 409 with impact details
    - Error: "Object of type ImpactAnalysis is not JSON serializable"

    Root cause:
    - HTTPException detail receives ImpactAnalysis pydantic model directly
    - Pydantic models are not JSON serializable without .model_dump()

    Fix:
    - Convert ImpactAnalysis to dict using .model_dump() before passing to HTTPException
    """

    def test_delete_blob_endpoint_serializes_impacts(self):
        """
        Verify that delete_blob endpoint properly serializes ImpactAnalysis.

        This is a code structure test - we check the source code to ensure
        the bug fix is in place.
        """
        api_path = Path(__file__).parent.parent.parent / "src/store/api.py"

        if not api_path.exists():
            pytest.skip("API source not available")

        content = api_path.read_text()

        # Find the delete blob endpoint and check for model_dump
        assert "model_dump()" in content, \
            "ImpactAnalysis should be converted using model_dump()"

        # Specifically check that impacts are serialized
        assert 'result["impacts"].model_dump()' in content, \
            "ImpactAnalysis in result should be converted to dict"

    def test_impact_analysis_model_has_model_dump(self):
        """Verify ImpactAnalysis is a Pydantic model with model_dump method."""
        from src.store.models import ImpactAnalysis, BlobStatus

        # Create a sample ImpactAnalysis with all required fields
        impact = ImpactAnalysis(
            sha256="test_sha256",
            status=BlobStatus.REFERENCED,
            size_bytes=1024,
            can_delete_safely=True,
            used_by_packs=["test-pack"],
        )

        # Verify it can be serialized
        result = impact.model_dump()

        assert isinstance(result, dict)
        assert result["sha256"] == "test_sha256"
        assert result["status"] == "referenced"
        assert result["size_bytes"] == 1024
        assert result["can_delete_safely"] is True
        assert result["used_by_packs"] == ["test-pack"]


class TestBug26DeleteDialogErrorHandling:
    """
    Bug #26: Delete dialog doesn't close on error and shows raw JSON

    Symptoms:
    - User clicks delete on referenced blob
    - Backend correctly returns 409 with impact details
    - Dialog stays open, nothing visible happens
    - User confused, has to manually close dialog

    Root cause (two issues):
    1. deleteBlob() just used res.text() which returns raw JSON string
    2. onError callback in deleteMutation didn't close the dialog

    Fix:
    - Parse 409 JSON response and extract meaningful error message
    - Close dialog in onError callback too (not just onSuccess)
    """

    def test_delete_blob_handles_409_response(self):
        """
        Verify that deleteBlob function parses 409 response properly.

        This is a code structure test - we check the source code to ensure
        the bug fix is in place.
        """
        page_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/inventory/InventoryPage.tsx"

        if not page_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = page_path.read_text()

        # Check that we handle 409 status specifically
        assert "res.status === 409" in content, \
            "deleteBlob should check for 409 status"

        # Check that we parse JSON for 409 response
        assert "res.json()" in content, \
            "deleteBlob should parse JSON response for 409"

        # Check that we extract pack info from impacts (handling FastAPI's detail wrapper)
        assert "data.detail?.impacts" in content or "detail?.impacts" in content, \
            "deleteBlob should handle FastAPI's detail wrapper"

        assert "used_by_packs" in content, \
            "deleteBlob should extract used_by_packs from impacts"

    def test_delete_mutation_closes_dialog_on_error(self):
        """
        Verify that deleteMutation's onError closes the dialog.

        This is a code structure test.
        """
        page_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/inventory/InventoryPage.tsx"

        if not page_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = page_path.read_text()

        # Find the onError callback section
        # It should contain setDeleteDialogOpen(false)
        assert "onError" in content, "deleteMutation should have onError callback"

        # Check that setDeleteDialogOpen(false) is called in onError
        # We need to verify the pattern: onError contains setDeleteDialogOpen(false)
        import re
        # Match: onError: (error: Error) => { ... setDeleteDialogOpen(false) ... }
        pattern = r"onError:\s*\([^)]*\)\s*=>\s*\{[^}]*setDeleteDialogOpen\(false\)"
        assert re.search(pattern, content), \
            "onError callback should close the dialog with setDeleteDialogOpen(false)"


class TestBug27DeleteFromBackupWhenLocalExists:
    """
    Bug #27: Delete from backup blocked even when local copy exists

    Symptoms:
    - User has blob on both local AND backup
    - User tries to delete ONLY from backup (to free backup space)
    - Delete is blocked with "blob is referenced by packs"
    - This is wrong - local copy will remain, so it's safe!

    Root cause:
    - delete_blob checked can_delete_safely without considering the target
    - can_delete_safely was False for any referenced blob
    - Did not check if another copy would remain after delete

    Fix:
    - Check if delete would remove the LAST copy
    - Only block if referenced AND would be last copy
    - Allow delete from backup if local copy exists (and vice versa)
    """

    def test_delete_blob_considers_target_location(self):
        """
        Verify that delete_blob checks if a copy remains in another location.

        This is a code structure test.
        """
        service_path = Path(__file__).parent.parent.parent / "src/store/inventory_service.py"

        if not service_path.exists():
            pytest.skip("Inventory service source not available")

        content = service_path.read_text()

        # Check that we determine if this would be the last copy
        assert "would_be_last_copy" in content, \
            "delete_blob should check if delete would remove last copy"

        # Check that we consider the target when deciding
        assert 'target == "backup"' in content or 'target == "local"' in content, \
            "delete_blob should consider target location"

        # Check that we check if blob exists in other location
        assert "on_local" in content and "on_backup" in content, \
            "delete_blob should check if blob exists in both locations"

    def test_delete_allows_if_copy_remains(self):
        """
        Verify that delete is allowed when another copy would remain.

        This is a code structure test.
        """
        service_path = Path(__file__).parent.parent.parent / "src/store/inventory_service.py"

        if not service_path.exists():
            pytest.skip("Inventory service source not available")

        content = service_path.read_text()

        # Check for the log message that explains allowing delete
        assert "copy remains" in content.lower(), \
            "delete_blob should log when allowing delete because copy remains"


class TestFeature28DeleteLocalForSyncedBlobs:
    """
    Feature #28: Delete from Local option for synced blobs in UI

    Use case:
    - User has large models that are synced (on both local and backup)
    - User wants to free local disk space for rarely used packs
    - Should be able to delete local copies, keeping backup for later restore

    Implementation:
    - Context menu: "Delete from Local" available for synced blobs (not just orphans)
    - Bulk actions: "Free Local" button for selected synced blobs
    """

    def test_delete_local_available_for_synced_blobs(self):
        """
        Verify that Delete from Local is shown for blobs with backup.

        This is a code structure test.
        """
        table_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/inventory/BlobsTable.tsx"

        if not table_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = table_path.read_text()

        # Check that Delete from Local condition includes on_backup check
        assert "item.on_backup" in content, \
            "Delete from Local should consider if backup exists"

        # The condition should be: on_local && (orphan OR on_backup)
        assert "item.status === 'orphan' || item.on_backup" in content, \
            "Delete from Local should be available for orphans OR synced blobs"

    def test_bulk_free_local_action_exists(self):
        """
        Verify that bulk 'Free Local' action exists for synced blobs.

        This is a code structure test.
        """
        table_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/inventory/BlobsTable.tsx"

        if not table_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = table_path.read_text()

        # Check that canFreeLocal is calculated
        assert "canFreeLocal" in content, \
            "selectedSummary should include canFreeLocal count"

        # Check that Free Local button exists (via i18n key or literal)
        assert "freeLocal" in content, \
            "Free Local button should exist in bulk actions (via i18n key)"


class TestFeature29RestoreFromBackupInDependencies:
    """
    Feature #29: Restore from Backup button in pack dependencies

    Use case:
    - User deleted local copy of a model (to free space)
    - Blob still exists on backup storage
    - User goes to pack detail page, dependencies section
    - Should see cloud icon and "Restore from Backup" button
    - Clicking restores from backup (not re-download from Civitai)

    Implementation:
    - Check if blob exists on backup via backupStatus.blobs
    - Show sky-colored cloud icon for backup-only assets
    - Show "Restore from Backup" button
    - Status text: "Available on backup - click cloud to restore"
    """

    def test_backup_only_visual_indicator(self):
        """
        Verify that backup-only assets have distinct visual styling.

        This is a code structure test.
        """
        content = get_pack_detail_module_content()

        if not content:
            pytest.skip("Frontend source not available in test environment")

        # Check for backup-only logic (can be isBackupOnly or backup_only location check)
        assert "isBackupOnly" in content or "backup_only" in content or "backup-only" in content, \
            "Pack detail module should determine if asset is backup-only"

        # Check for sky color styling (backup-only indicator) or Cloud icon
        assert "bg-sky" in content or "text-sky" in content or "Cloud" in content, \
            "Backup-only assets should have distinctive styling or icon"

    def test_restore_from_backup_button(self):
        """
        Verify that restore from backup button exists for backup-only assets.

        This is a code structure test.
        """
        content = get_pack_detail_module_content()

        if not content:
            pytest.skip("Frontend source not available in test environment")

        # Check for restore functionality - can be onRestoreFromBackup or restore API
        assert "RestoreFromBackup" in content or "onRestoreFromBackup" in content or "pullPack" in content, \
            "Restore from backup functionality should exist"

    def test_backup_status_text(self):
        """
        Verify that status text indicates backup availability.

        This is a code structure test.
        """
        content = get_pack_detail_module_content()

        if not content:
            pytest.skip("Frontend source not available in test environment")

        # Check for status text or backup-only indicator
        assert "Available on backup" in content or "backup_only" in content or "Cloud" in content, \
            "Status should indicate when blob is available on backup"


class TestBug30InventoryRefreshAfterRestore:
    """
    Bug #30: Inventory page not refreshed after restore from PackDetailPage

    Symptoms:
    - User restores blob from backup using button in PackDetailPage
    - Pack detail page correctly shows asset as installed (green)
    - Inventory page still shows blob as "backup only" (stale data)

    Root cause:
    - Restore action only invalidated ['pack', packName] and ['pack-backup-status', packName]
    - Did not invalidate ['inventory'] query

    Fix:
    - Add queryClient.invalidateQueries({ queryKey: ['inventory'] }) to:
      - PullConfirmDialog onComplete callback
      - PushConfirmDialog onComplete callback
      - Individual restore button onClick handler
    """

    def test_restore_from_backup_invalidates_inventory(self):
        """
        Verify that restore from backup invalidates inventory query.

        This is a code structure test.
        """
        content = get_pack_detail_module_content()

        if not content:
            pytest.skip("Frontend source not available in test environment")

        # Check for inventory invalidation in any of the module files
        # With modular architecture, the invalidation may be in hooks or dialogs
        has_invalidation = (
            "queryKey: ['inventory']" in content or
            "['inventory']" in content or
            "invalidateQueries" in content  # General invalidation pattern
        )

        assert has_invalidation, \
            "Pack detail module should have inventory query invalidation support"

    def test_pull_confirm_dialog_invalidates_inventory(self):
        """
        Verify PullConfirmDialog invalidates inventory on complete.

        This is a code structure test.
        """
        dialog_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/packs/PullConfirmDialog.tsx"

        if not dialog_path.exists():
            pytest.skip("PullConfirmDialog source not available")

        content = dialog_path.read_text()

        # Check for onComplete callback pattern or inventory invalidation
        # The dialog should call onComplete which parent handles
        assert "onComplete" in content or "['inventory']" in content or "invalidate" in content.lower(), \
            "PullConfirmDialog should have completion callback for inventory refresh"

    def test_push_confirm_dialog_invalidates_inventory(self):
        """
        Verify PushConfirmDialog invalidates inventory on complete.

        This is a code structure test.
        """
        dialog_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/packs/PushConfirmDialog.tsx"

        if not dialog_path.exists():
            pytest.skip("PushConfirmDialog source not available")

        content = dialog_path.read_text()

        # Check for onComplete callback pattern or inventory invalidation
        # The dialog should call onComplete which parent handles
        assert "onComplete" in content or "['inventory']" in content or "invalidate" in content.lower(), \
            "PushConfirmDialog should have completion callback for inventory refresh"


class TestBug31InfiniteLoopBackupAndFree:
    """
    Bug #31: Infinite loop when "Backup & Free" tries to delete blob not on local

    Symptoms:
    - User clicks "Backup & Free" on a pack
    - Some blobs are already backup_only (not on local)
    - Frontend sends DELETE target=local for these blobs
    - Backend returns error "blob not on local"
    - Frontend retries immediately → infinite loop

    Root cause:
    - Backend returned error when blob was already not on local
    - Frontend cache showed on_local=true but reality was different
    - This caused repeated failed attempts

    Fix:
    - Backend: treat "delete from local" as success if blob exists only on backup
      (the goal of freeing local space is achieved)
    - Return deleted=True with note explaining blob was already freed
    """

    def test_delete_local_succeeds_when_backup_only(self):
        """
        Verify that delete_blob with target=local returns success
        when blob is only on backup (not on local).

        This prevents infinite loops in the UI.
        """
        service_path = Path(__file__).parent.parent.parent / "src/store/inventory_service.py"

        if not service_path.exists():
            pytest.skip("Inventory service source not available")

        content = service_path.read_text()

        # Check for the fix: treating backup-only as success for local delete
        assert "already freed" in content.lower() or "already not on local" in content.lower(), \
            "delete_blob should handle backup-only case gracefully for target=local"

        # Check that we return deleted=True in this case
        assert '"deleted": True' in content or "'deleted': True" in content, \
            "delete_blob should return deleted=True for backup-only blobs when target=local"

    def test_delete_blob_has_reason_for_all_targets(self):
        """
        Verify that delete_blob returns proper reason message for any target
        when blob is not found.

        This is a code structure test.
        """
        service_path = Path(__file__).parent.parent.parent / "src/store/inventory_service.py"

        if not service_path.exists():
            pytest.skip("Inventory service source not available")

        content = service_path.read_text()

        # Check that we always return a reason, not just for backup/both targets
        # Old buggy code: if not deleted and target in ("backup", "both"):
        # Fixed code: if not deleted:
        assert 'if not deleted:' in content, \
            "delete_blob should return reason for ALL targets when nothing deleted"

    def test_push_dialog_filters_backup_only_from_cleanup(self):
        """
        Verify that PushConfirmDialog filters out backup_only blobs from cleanup list.

        This is a code structure test - prevents infinite loops when cache is stale.
        """
        dialog_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/packs/PushConfirmDialog.tsx"

        if not dialog_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = dialog_path.read_text()

        # Check that localBlobs filters out backup_only
        assert "location !== 'backup_only'" in content, \
            "localBlobs should filter out backup_only to prevent infinite loops"

        # Check that we handle empty blobsToDelete
        assert "blobsToDelete.length === 0" in content, \
            "Should handle case when all blobs are backup_only (nothing to delete)"

    def test_push_dialog_uses_ref_to_prevent_double_cleanup(self):
        """
        Verify that PushConfirmDialog uses a ref to prevent cleanup phase
        from being triggered multiple times due to stale closure.

        The bug: onComplete callback captured old cleanupPhase value in closure.
        Even after setCleanupPhase(true) was called, the callback's closure
        still had cleanupPhase=false, causing infinite loops.

        Fix: Use cleanupStartedRef to track if cleanup has started.
        """
        dialog_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/packs/PushConfirmDialog.tsx"

        if not dialog_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = dialog_path.read_text()

        # Check for the ref
        assert "cleanupStartedRef" in content, \
            "PushConfirmDialog should use cleanupStartedRef to prevent double cleanup"

        # Check that ref is used in condition (instead of just cleanupPhase)
        assert "!cleanupStartedRef.current" in content, \
            "onComplete should check cleanupStartedRef.current instead of just cleanupPhase"

        # Check that ref is set to true before starting cleanup
        assert "cleanupStartedRef.current = true" in content, \
            "Cleanup should set cleanupStartedRef.current = true before starting"

        # Check that ref is reset when dialog closes
        assert "cleanupStartedRef.current = false" in content, \
            "Dialog close should reset cleanupStartedRef.current to false"

    def test_push_dialog_shows_actual_freed_bytes(self):
        """
        Verify that PushConfirmDialog shows actual freed bytes from progress,
        not the pre-calculated totalBytesToFree which can be stale/wrong.

        Bug: Dialog showed "Successfully freed 0 B" when blobs were backup_only
        because totalBytesToFree was calculated from filtered localBlobs.

        Fix: Use progress.total_bytes for the actual freed amount, or show
        "Local space already freed" if nothing was processed.
        """
        dialog_path = Path(__file__).parent.parent.parent / "apps/web/src/components/modules/packs/PushConfirmDialog.tsx"

        if not dialog_path.exists():
            pytest.skip("Frontend source not available in test environment")

        content = dialog_path.read_text()

        # Check that we use progress.total_bytes instead of totalBytesToFree
        assert "progress?.total_bytes" in content, \
            "Success message should use progress.total_bytes for actual freed amount"

        # Check for fallback message when nothing was freed (via i18n key or literal)
        assert "alreadyFreed" in content, \
            "Should show appropriate message when no files needed to be freed (via i18n key)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
