"""
Tests for Preview CRUD API endpoints.

Comprehensive tests covering all real-world scenarios:

Upload (6 tests):
- Add to end, beginning, middle position
- Verify other previews not affected
- Invalid extension rejected
- Video has correct media_type

List (2 tests):
- Returns all previews
- Empty pack returns empty list

Reorder (5 tests):
- Move last to first
- Reverse order completely
- Swap first and second
- Preserve preview metadata after reorder
- Partial list appends unlisted

Set Cover (5 tests):
- Set second preview as cover (not first!)
- Set third preview as cover
- Change cover from one to another
- Cover persists after pack reload (modal reopen)
- Nonexistent preview fails

Delete (5 tests):
- Delete middle preview, verify others intact
- Delete first, verify shift
- Delete last
- Nonexistent fails
- Delete all leaves empty + files deleted

Batch Update (9 tests):
- Upload, delete, reorder, set cover
- Combined operations
- Error handling

Edge Cases (7 tests):
- Nonexistent packs, file overwrite, cover management, etc.
"""

import pytest
from pathlib import Path
from io import BytesIO

from fastapi.testclient import TestClient

from src.store import Store
from src.store.models import Pack, PackSource, AssetKind, PreviewInfo


@pytest.fixture
def test_store(tmp_path: Path):
    """Create a temporary store for testing."""
    store_root = tmp_path / "store"
    store_root.mkdir()
    store = Store(store_root)
    store.init()
    return store


@pytest.fixture
def test_pack(test_store: Store) -> Pack:
    """Create a test pack with some previews."""
    pack = Pack(
        name="test-pack",
        pack_type=AssetKind.LORA,
        source=PackSource(provider="local"),
        previews=[
            PreviewInfo(filename="preview1.jpg", url="/packs/test-pack/resources/previews/preview1.jpg", media_type="image"),
            PreviewInfo(filename="preview2.png", url="/packs/test-pack/resources/previews/preview2.png", media_type="image"),
            PreviewInfo(filename="preview3.mp4", url="/packs/test-pack/resources/previews/preview3.mp4", media_type="video"),
        ],
    )

    # Save pack
    test_store.layout.save_pack(pack)

    # Create preview files
    previews_dir = test_store.layout.pack_previews_path("test-pack")
    previews_dir.mkdir(parents=True, exist_ok=True)

    (previews_dir / "preview1.jpg").write_bytes(b"fake jpg content")
    (previews_dir / "preview2.png").write_bytes(b"fake png content")
    (previews_dir / "preview3.mp4").write_bytes(b"fake mp4 content")

    return pack


@pytest.fixture
def client(test_store: Store):
    """Create a test client with store dependency override."""
    from fastapi import FastAPI
    from src.store.api import v2_packs_router, require_initialized

    app = FastAPI()
    # Mount packs router at /api/packs like in production
    app.include_router(v2_packs_router, prefix="/api/packs")

    # Override the store dependency
    app.dependency_overrides[require_initialized] = lambda: test_store

    return TestClient(app)


class TestUploadPreview:
    """Tests for POST /{pack_name}/previews/upload."""

    def test_upload_adds_to_end_by_default(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test that uploading with position -1 adds to end."""
        file_content = b"new preview content"
        files = {"file": ("new_preview.jpg", BytesIO(file_content), "image/jpeg")}
        data = {"position": "-1", "nsfw": "false"}

        response = client.post(
            f"/api/packs/{test_pack.name}/previews/upload",
            files=files,
            data=data,
        )
        assert response.status_code == 200

        # Verify new preview is at end
        pack = test_store.get_pack(test_pack.name)
        assert len(pack.previews) == 4  # 3 original + 1 new
        assert pack.previews[3].filename == "new_preview.jpg"  # At end

        # Verify file was created
        previews_dir = test_store.layout.pack_previews_path(test_pack.name)
        assert (previews_dir / "new_preview.jpg").exists()
        assert (previews_dir / "new_preview.jpg").read_bytes() == file_content

    def test_upload_at_beginning(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test uploading at position 0 inserts at beginning."""
        files = {"file": ("first.jpg", BytesIO(b"content"), "image/jpeg")}
        data = {"position": "0", "nsfw": "false"}

        response = client.post(
            f"/api/packs/{test_pack.name}/previews/upload",
            files=files,
            data=data,
        )
        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        assert len(pack.previews) == 4
        assert pack.previews[0].filename == "first.jpg"  # At beginning
        assert pack.previews[1].filename == "preview1.jpg"  # Original first shifted

    def test_upload_at_middle_position(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test uploading at position 1 inserts in middle."""
        files = {"file": ("middle.jpg", BytesIO(b"content"), "image/jpeg")}
        data = {"position": "1", "nsfw": "false"}

        response = client.post(
            f"/api/packs/{test_pack.name}/previews/upload",
            files=files,
            data=data,
        )
        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        assert len(pack.previews) == 4
        assert pack.previews[0].filename == "preview1.jpg"
        assert pack.previews[1].filename == "middle.jpg"  # Inserted at position 1
        assert pack.previews[2].filename == "preview2.png"  # Shifted

    def test_upload_does_not_affect_other_previews(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test that uploading preserves existing preview data."""
        # Get original previews
        pack_before = test_store.get_pack(test_pack.name)
        original_count = len(pack_before.previews)

        files = {"file": ("new.jpg", BytesIO(b"content"), "image/jpeg")}
        data = {"position": "-1", "nsfw": "false"}

        response = client.post(
            f"/api/packs/{test_pack.name}/previews/upload",
            files=files,
            data=data,
        )
        assert response.status_code == 200

        pack_after = test_store.get_pack(test_pack.name)
        assert len(pack_after.previews) == original_count + 1

        # Original previews unchanged
        for i in range(original_count):
            assert pack_after.previews[i].filename == pack_before.previews[i].filename
            assert pack_after.previews[i].media_type == pack_before.previews[i].media_type

    def test_upload_preview_rejects_invalid_extension(self, client: TestClient, test_pack: Pack):
        """Test that uploading unsupported file types is rejected."""
        files = {"file": ("malware.exe", BytesIO(b"bad content"), "application/octet-stream")}
        data = {"position": "-1", "nsfw": "false"}

        response = client.post(
            f"/api/packs/{test_pack.name}/previews/upload",
            files=files,
            data=data,
        )

        assert response.status_code == 400
        assert "Unsupported file type" in response.text

    def test_upload_video_preview_has_correct_media_type(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test uploading a video preview sets media_type correctly."""
        files = {"file": ("video.mp4", BytesIO(b"fake video"), "video/mp4")}
        data = {"position": "-1", "nsfw": "false"}

        response = client.post(
            f"/api/packs/{test_pack.name}/previews/upload",
            files=files,
            data=data,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["media_type"] == "video"

        # Verify in pack data
        pack = test_store.get_pack(test_pack.name)
        video_preview = next(p for p in pack.previews if p.filename == "video.mp4")
        assert video_preview.media_type == "video"


class TestListPreviews:
    """Tests for GET /{pack_name}/previews."""

    def test_list_previews_returns_all(self, client: TestClient, test_pack: Pack):
        """Test listing all previews."""
        response = client.get(f"/api/packs/{test_pack.name}/previews")

        assert response.status_code == 200
        previews = response.json()
        assert len(previews) == 3
        filenames = [p["filename"] for p in previews]
        assert "preview1.jpg" in filenames
        assert "preview2.png" in filenames
        assert "preview3.mp4" in filenames

    def test_list_previews_empty_pack(self, client: TestClient, test_store: Store):
        """Test listing previews for pack with no previews."""
        # Create pack without previews
        pack = Pack(
            name="empty-pack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider="local"),
            previews=[],
        )
        test_store.layout.save_pack(pack)

        response = client.get("/api/packs/empty-pack/previews")

        assert response.status_code == 200
        assert response.json() == []


class TestReorderPreviews:
    """Tests for PATCH /{pack_name}/previews/order."""

    def test_move_last_to_first(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test moving last preview to first position."""
        # Original: [preview1, preview2, preview3]
        # New: [preview3, preview1, preview2]
        new_order = ["preview3.mp4", "preview1.jpg", "preview2.png"]

        response = client.patch(
            f"/api/packs/{test_pack.name}/previews/order",
            json={"order": new_order},
        )
        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        assert pack.previews[0].filename == "preview3.mp4"
        assert pack.previews[1].filename == "preview1.jpg"
        assert pack.previews[2].filename == "preview2.png"

    def test_reverse_order(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test reversing preview order completely."""
        # Original: [preview1, preview2, preview3]
        # New: [preview3, preview2, preview1]
        new_order = ["preview3.mp4", "preview2.png", "preview1.jpg"]

        response = client.patch(
            f"/api/packs/{test_pack.name}/previews/order",
            json={"order": new_order},
        )
        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        filenames = [p.filename for p in pack.previews]
        assert filenames == new_order

    def test_swap_first_and_second(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test swapping first two previews."""
        new_order = ["preview2.png", "preview1.jpg", "preview3.mp4"]

        response = client.patch(
            f"/api/packs/{test_pack.name}/previews/order",
            json={"order": new_order},
        )
        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        assert pack.previews[0].filename == "preview2.png"
        assert pack.previews[1].filename == "preview1.jpg"

    def test_reorder_preserves_preview_data(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test that reorder preserves all preview metadata."""
        # Get original preview3 data
        pack_before = test_store.get_pack(test_pack.name)
        preview3_before = next(p for p in pack_before.previews if p.filename == "preview3.mp4")
        assert preview3_before.media_type == "video"

        # Move preview3 to first position
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews/order",
            json={"order": ["preview3.mp4", "preview1.jpg", "preview2.png"]},
        )
        assert response.status_code == 200

        # Verify preview3 data is preserved after move
        pack_after = test_store.get_pack(test_pack.name)
        preview3_after = pack_after.previews[0]
        assert preview3_after.filename == "preview3.mp4"
        assert preview3_after.media_type == "video"  # Data preserved

    def test_reorder_partial_list_appends_unlisted(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test reordering with partial list - unlisted items go to end."""
        # Only specify two items - preview3 should go to end
        new_order = ["preview2.png", "preview1.jpg"]

        response = client.patch(
            f"/api/packs/{test_pack.name}/previews/order",
            json={"order": new_order},
        )
        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        filenames = [p.filename for p in pack.previews]
        assert filenames[0] == "preview2.png"
        assert filenames[1] == "preview1.jpg"
        assert filenames[2] == "preview3.mp4"  # Appended at end


class TestSetCoverPreview:
    """Tests for PATCH /{pack_name}/previews/{filename}/cover."""

    def test_set_cover_to_second_preview(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test setting second preview as cover - not first!"""
        # Initially no cover_url set (defaults to first)
        pack_before = test_store.get_pack(test_pack.name)
        assert pack_before.cover_url is None  # No explicit cover

        # Set second preview as cover
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews/preview2.png/cover"
        )
        assert response.status_code == 200

        # Verify cover_url is now preview2, NOT preview1
        pack = test_store.get_pack(test_pack.name)
        assert pack.cover_url is not None
        assert "preview2.png" in pack.cover_url
        assert "preview1.jpg" not in pack.cover_url

    def test_set_cover_to_third_preview(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test setting third (last) preview as cover."""
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews/preview3.mp4/cover"
        )
        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        assert "preview3.mp4" in pack.cover_url
        assert "preview1.jpg" not in pack.cover_url
        assert "preview2.png" not in pack.cover_url

    def test_change_cover_from_one_to_another(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test changing cover from preview2 to preview3."""
        # First set cover to preview2
        client.patch(f"/api/packs/{test_pack.name}/previews/preview2.png/cover")
        pack = test_store.get_pack(test_pack.name)
        assert "preview2.png" in pack.cover_url

        # Now change to preview3
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews/preview3.mp4/cover"
        )
        assert response.status_code == 200

        # Verify cover is now preview3, not preview2
        pack = test_store.get_pack(test_pack.name)
        assert "preview3.mp4" in pack.cover_url
        assert "preview2.png" not in pack.cover_url

    def test_cover_persists_after_reload(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test that cover setting persists after pack reload (simulates modal reopen)."""
        # Set cover to preview3 (not first!)
        client.patch(f"/api/packs/{test_pack.name}/previews/preview3.mp4/cover")

        # "Reload" pack - this is what happens when modal reopens
        pack_reloaded = test_store.get_pack(test_pack.name)

        # Cover should still be preview3, NOT defaulting back to first
        assert pack_reloaded.cover_url is not None
        assert "preview3.mp4" in pack_reloaded.cover_url
        assert "preview1.jpg" not in pack_reloaded.cover_url

    def test_set_cover_nonexistent_preview(self, client: TestClient, test_pack: Pack):
        """Test setting nonexistent preview as cover fails."""
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews/nonexistent.jpg/cover"
        )

        assert response.status_code == 404


class TestDeletePreview:
    """Tests for DELETE /{pack_name}/previews/{filename}."""

    def test_delete_middle_preview(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test deleting middle preview - verify others remain intact."""
        # Delete preview2 (the middle one)
        response = client.delete(
            f"/api/packs/{test_pack.name}/previews/preview2.png"
        )
        assert response.status_code == 200

        # Verify preview2 is gone but preview1 and preview3 remain
        pack = test_store.get_pack(test_pack.name)
        filenames = [p.filename for p in pack.previews]
        assert len(pack.previews) == 2
        assert "preview1.jpg" in filenames
        assert "preview2.png" not in filenames
        assert "preview3.mp4" in filenames

        # Verify file deleted from disk
        previews_dir = test_store.layout.pack_previews_path(test_pack.name)
        assert not (previews_dir / "preview2.png").exists()
        # But others still exist
        assert (previews_dir / "preview1.jpg").exists()
        assert (previews_dir / "preview3.mp4").exists()

    def test_delete_first_preview(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test deleting first preview - remaining previews should shift."""
        response = client.delete(
            f"/api/packs/{test_pack.name}/previews/preview1.jpg"
        )
        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        # preview2 should now be first
        assert pack.previews[0].filename == "preview2.png"
        assert pack.previews[1].filename == "preview3.mp4"
        assert len(pack.previews) == 2

    def test_delete_last_preview(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test deleting last preview - first two should remain."""
        response = client.delete(
            f"/api/packs/{test_pack.name}/previews/preview3.mp4"
        )
        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        filenames = [p.filename for p in pack.previews]
        assert filenames == ["preview1.jpg", "preview2.png"]

    def test_delete_nonexistent_preview(self, client: TestClient, test_pack: Pack):
        """Test deleting nonexistent preview fails."""
        response = client.delete(
            f"/api/packs/{test_pack.name}/previews/nonexistent.jpg"
        )

        assert response.status_code == 404

    def test_delete_all_previews(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test deleting all previews leaves empty list."""
        for filename in ["preview1.jpg", "preview2.png", "preview3.mp4"]:
            response = client.delete(
                f"/api/packs/{test_pack.name}/previews/{filename}"
            )
            assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        assert len(pack.previews) == 0

        # All files should be deleted
        previews_dir = test_store.layout.pack_previews_path(test_pack.name)
        assert not (previews_dir / "preview1.jpg").exists()
        assert not (previews_dir / "preview2.png").exists()
        assert not (previews_dir / "preview3.mp4").exists()


class TestBatchUpdatePreviews:
    """Tests for PATCH /{pack_name}/previews (batch update endpoint)."""

    def test_batch_upload_files(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test batch uploading new files."""
        files = [
            ("files", ("new1.jpg", BytesIO(b"content1"), "image/jpeg")),
            ("files", ("new2.png", BytesIO(b"content2"), "image/png")),
        ]

        response = client.patch(
            f"/api/packs/{test_pack.name}/previews",
            files=files,
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        assert len(result["uploaded"]) == 2
        assert "new1.jpg" in result["uploaded"]
        assert "new2.png" in result["uploaded"]

        # Verify files exist
        previews_dir = test_store.layout.pack_previews_path(test_pack.name)
        assert (previews_dir / "new1.jpg").exists()
        assert (previews_dir / "new2.png").exists()

    def test_batch_delete_files(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test batch deleting files."""
        import json

        response = client.patch(
            f"/api/packs/{test_pack.name}/previews",
            data={"deleted": json.dumps(["preview1.jpg", "preview2.png"])},
        )

        assert response.status_code == 200
        result = response.json()
        assert len(result["deleted"]) == 2
        assert "preview1.jpg" in result["deleted"]
        assert "preview2.png" in result["deleted"]

        # Verify files deleted
        pack = test_store.get_pack(test_pack.name)
        filenames = [p.filename for p in pack.previews]
        assert "preview1.jpg" not in filenames
        assert "preview2.png" not in filenames
        assert "preview3.mp4" in filenames  # Not deleted

    def test_batch_reorder(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test batch reordering."""
        import json

        new_order = ["preview3.mp4", "preview1.jpg", "preview2.png"]
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews",
            data={"order": json.dumps(new_order)},
        )

        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        filenames = [p.filename for p in pack.previews]
        assert filenames == new_order

    def test_batch_set_cover(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test batch setting cover."""
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews",
            data={"cover_filename": "preview2.png"},
        )

        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        assert "preview2.png" in pack.cover_url

    def test_batch_combined_operations(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test batch with upload, delete, reorder, and cover in one call."""
        import json

        files = [("files", ("newfile.jpg", BytesIO(b"new content"), "image/jpeg"))]
        data = {
            "deleted": json.dumps(["preview1.jpg"]),
            "order": json.dumps(["preview3.mp4", "preview2.png", "newfile.jpg"]),
            "cover_filename": "preview3.mp4",
        }

        response = client.patch(
            f"/api/packs/{test_pack.name}/previews",
            files=files,
            data=data,
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        assert len(result["uploaded"]) == 1
        assert "newfile.jpg" in result["uploaded"]
        assert len(result["deleted"]) == 1
        assert "preview1.jpg" in result["deleted"]

        # Verify final state
        pack = test_store.get_pack(test_pack.name)
        filenames = [p.filename for p in pack.previews]
        assert "preview1.jpg" not in filenames
        assert "newfile.jpg" in filenames
        assert filenames == ["preview3.mp4", "preview2.png", "newfile.jpg"]
        assert "preview3.mp4" in pack.cover_url

    def test_batch_no_operations(self, client: TestClient, test_pack: Pack):
        """Test batch with no operations returns success."""
        response = client.patch(f"/api/packs/{test_pack.name}/previews")

        assert response.status_code == 200
        result = response.json()
        assert result["uploaded"] == []
        assert result["deleted"] == []

    def test_batch_nonexistent_pack(self, client: TestClient):
        """Test batch on nonexistent pack fails."""
        response = client.patch("/api/packs/nonexistent-pack-xyz/previews")

        assert response.status_code == 400

    def test_batch_invalid_json_in_deleted(self, client: TestClient, test_pack: Pack):
        """Test batch with invalid JSON in deleted field fails."""
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews",
            data={"deleted": "not-valid-json"},
        )

        assert response.status_code == 400

    def test_batch_invalid_cover_silently_skipped(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test batch with nonexistent cover filename is silently skipped."""
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews",
            data={"cover_filename": "nonexistent.jpg"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["cover_changed"] is False

        # Original cover should be unchanged
        pack = test_store.get_pack(test_pack.name)
        assert "nonexistent.jpg" not in (pack.cover_url or "")


class TestEdgeCases:
    """Edge case tests for preview operations."""

    def test_upload_to_nonexistent_pack(self, client: TestClient):
        """Test uploading to nonexistent pack fails."""
        files = {"file": ("test.jpg", BytesIO(b"content"), "image/jpeg")}
        data = {"position": "-1", "nsfw": "false"}

        response = client.post(
            "/api/packs/nonexistent-pack-xyz/previews/upload",
            files=files,
            data=data,
        )

        assert response.status_code == 400

    def test_upload_overwrites_existing(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test uploading file with same name overwrites."""
        # Upload a file
        files = {"file": ("preview1.jpg", BytesIO(b"new content"), "image/jpeg")}
        data = {"position": "-1", "nsfw": "false"}

        response = client.post(
            f"/api/packs/{test_pack.name}/previews/upload",
            files=files,
            data=data,
        )

        assert response.status_code == 200

        # Verify content was overwritten
        previews_dir = test_store.layout.pack_previews_path(test_pack.name)
        content = (previews_dir / "preview1.jpg").read_bytes()
        assert content == b"new content"

    def test_upload_at_position_zero(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test uploading at position 0 inserts at beginning."""
        files = {"file": ("first.jpg", BytesIO(b"content"), "image/jpeg")}
        data = {"position": "0", "nsfw": "false"}

        response = client.post(
            f"/api/packs/{test_pack.name}/previews/upload",
            files=files,
            data=data,
        )

        assert response.status_code == 200

        pack = test_store.get_pack(test_pack.name)
        assert pack.previews[0].filename == "first.jpg"

    def test_delete_cover_clears_cover_url(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test that deleting the cover preview clears cover_url."""
        # First, set a cover
        client.patch(f"/api/packs/{test_pack.name}/previews/preview1.jpg/cover")

        pack = test_store.get_pack(test_pack.name)
        assert "preview1.jpg" in pack.cover_url

        # Now delete that preview
        response = client.delete(f"/api/packs/{test_pack.name}/previews/preview1.jpg")

        assert response.status_code == 200

        # cover_url should be cleared
        pack = test_store.get_pack(test_pack.name)
        assert pack.cover_url is None

    def test_list_nonexistent_pack(self, client: TestClient):
        """Test listing previews for nonexistent pack fails."""
        response = client.get("/api/packs/nonexistent-pack-xyz/previews")

        assert response.status_code == 400

    def test_set_cover_and_delete_atomically(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test batch operation: set cover on file that's being deleted fails gracefully."""
        import json

        # Try to set cover on preview1.jpg while also deleting it
        response = client.patch(
            f"/api/packs/{test_pack.name}/previews",
            data={
                "deleted": json.dumps(["preview1.jpg"]),
                "cover_filename": "preview1.jpg",
            },
        )

        assert response.status_code == 200
        result = response.json()

        # File should be deleted
        assert "preview1.jpg" in result["deleted"]
        # Cover change should fail (file no longer exists in previews)
        assert result["cover_changed"] is False

    def test_upload_set_as_cover(self, client: TestClient, test_pack: Pack, test_store: Store):
        """Test uploading with set_as_cover flag."""
        files = {"file": ("newcover.jpg", BytesIO(b"cover content"), "image/jpeg")}
        data = {"position": "-1", "nsfw": "false", "set_as_cover": "true"}

        response = client.post(
            f"/api/packs/{test_pack.name}/previews/upload",
            files=files,
            data=data,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["is_cover"] is True

        pack = test_store.get_pack(test_pack.name)
        assert "newcover.jpg" in pack.cover_url
