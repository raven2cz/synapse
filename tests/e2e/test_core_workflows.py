"""
End-to-End Tests for Core Synapse Workflows.

These tests verify REAL user scenarios and API contracts — testing the
complete chain from HTTP request → API endpoint → Store → Services →
disk state, and then verifying the response matches what the frontend
expects.

Each test creates a real Store on disk (via tmp_path), runs a complete
workflow, and verifies:
  1. The API response shape matches the frontend TypeScript contract
  2. On-disk state is correct (files, locks, blobs, symlinks)
  3. Edge cases that actually break the UI

Only external Civitai API calls are faked via FakeCivitaiClient.

Test groups:
  A. API Contract Tests — response shapes the frontend depends on
  B. User Journey Tests — complete multi-step workflows
  C. Edge Case Tests — things that have actually broken before
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers.fixtures import (
    FakeCivitaiClient,
    FakeFile,
    FakeModel,
    FakeModelVersion,
    create_test_blob,
    compute_sha256_from_content,
)


# =============================================================================
# Shared Fixtures
# =============================================================================

@pytest.fixture
def store_factory():
    """Factory for creating stores with common setup."""
    stores = []

    def _create(tmp_path, *, models=None, api_key=None):
        from src.store import Store

        fake_civitai = FakeCivitaiClient()
        if models:
            for m in models:
                fake_civitai.add_model(m)

        store = Store(tmp_path, civitai_client=fake_civitai, civitai_api_key=api_key)
        store.init()
        stores.append((store, fake_civitai))
        return store, fake_civitai

    yield _create


@pytest.fixture
def api_client_factory():
    """Factory for creating FastAPI TestClient with real store."""
    def _create(tmp_path, *, models=None, api_key=None):
        from src.store import Store, api as api_module
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from src.store.api import (
            store_router, v2_packs_router, profiles_router,
            updates_router, search_router,
        )

        fake_civitai = FakeCivitaiClient()
        if models:
            for m in models:
                fake_civitai.add_model(m)

        store = Store(tmp_path, civitai_client=fake_civitai, civitai_api_key=api_key)
        store.init()

        api_module._store_instance = store

        app = FastAPI()
        app.include_router(v2_packs_router, prefix="/api/packs")
        app.include_router(store_router, prefix="/api/store")
        app.include_router(profiles_router, prefix="/api/profiles")
        app.include_router(updates_router, prefix="/api/updates")
        app.include_router(search_router, prefix="/api/search")

        client = TestClient(app)
        yield client, store, fake_civitai

        api_module._store_instance = None

    return _create


def _make_lora(model_id, version_id, file_id, name="TestLora", sha256="aabbccdd"):
    """Create a LORA FakeModel with one version and one file."""
    return FakeModel(
        id=model_id, name=name, type="LORA",
        versions=[FakeModelVersion(
            id=version_id, model_id=model_id, name="v1.0",
            base_model="SDXL 1.0", trained_words=["trigger"],
            files=[FakeFile(
                id=file_id, name="model.safetensors", sha256=sha256,
                download_url=f"https://civitai.com/api/download/models/{version_id}",
            ).to_dict()],
            images=[{"url": f"https://image.civitai.com/preview_{version_id}.jpg",
                     "nsfw": False, "width": 512, "height": 512}],
        )],
    )


def _make_updatable_model(model_id, name, old_vid, old_fid, old_sha, new_vid, new_fid, new_sha):
    """Create a model with two versions (old + new) for update testing."""
    return FakeModel(
        id=model_id, name=name, type="LORA",
        versions=[
            FakeModelVersion(
                id=new_vid, model_id=model_id, name="v2.0",
                files=[FakeFile(
                    id=new_fid, name="model_v2.safetensors", sha256=new_sha,
                    download_url=f"https://civitai.com/api/download/models/{new_vid}",
                ).to_dict()],
            ),
            FakeModelVersion(
                id=old_vid, model_id=model_id, name="v1.0",
                files=[FakeFile(
                    id=old_fid, name="model_v1.safetensors", sha256=old_sha,
                    download_url=f"https://civitai.com/api/download/models/{old_vid}",
                ).to_dict()],
            ),
        ],
    )


def _create_pack_with_lock(store, *, name, model_id, version_id, file_id, sha256, policy="FOLLOW_LATEST"):
    """Create a pack + lock file on disk. Returns (pack, lock)."""
    from src.store.models import (
        AssetKind, CivitaiSelector, DependencySelector, ExposeConfig,
        Pack, PackDependency, PackLock, PackSource, ProviderName,
        ResolvedArtifact, ResolvedDependency, ArtifactProvider,
        ArtifactDownload, ArtifactIntegrity, SelectorStrategy,
        UpdatePolicy, UpdatePolicyMode,
    )

    mode = UpdatePolicyMode.FOLLOW_LATEST if policy == "FOLLOW_LATEST" else UpdatePolicyMode.PINNED

    pack = Pack(
        name=name,
        pack_type=AssetKind.LORA,
        source=PackSource(provider=ProviderName.CIVITAI, model_id=model_id),
        dependencies=[PackDependency(
            id="main", kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                civitai=CivitaiSelector(model_id=model_id),
            ),
            update_policy=UpdatePolicy(mode=mode),
            expose=ExposeConfig(filename="model.safetensors"),
        )],
    )
    store.layout.save_pack(pack)

    lock = PackLock(pack=name, resolved=[ResolvedDependency(
        dependency_id="main",
        artifact=ResolvedArtifact(
            kind=AssetKind.LORA, sha256=sha256,
            provider=ArtifactProvider(
                name=ProviderName.CIVITAI, model_id=model_id,
                version_id=version_id, file_id=file_id,
            ),
            download=ArtifactDownload(urls=[f"https://civitai.com/api/download/models/{version_id}"]),
            integrity=ArtifactIntegrity(sha256_verified=True),
        ),
    )])
    store.layout.save_pack_lock(lock)
    return pack, lock


def _plant_blob(store, content: bytes) -> str:
    """Write content directly to blob store, return sha256."""
    sha256 = hashlib.sha256(content).hexdigest().lower()
    blob_path = store.blob_store.blob_path(sha256)
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_bytes(content)
    return sha256


# =============================================================================
# A. API CONTRACT TESTS
#
# These verify that API responses match the TypeScript interfaces
# the frontend depends on. If any of these break, the UI crashes.
# =============================================================================


class TestCheckAllUpdatesAPIContract:
    """
    Frontend: updatesStore.ts line 141-145
    Calls GET /api/updates/check-all
    Expects: { packs_checked, packs_with_updates, total_changes, plans: {...} }
    Each plan in `plans` must match UpdatePlanEntry interface.
    """

    def test_response_has_required_top_level_fields(self, tmp_path, api_client_factory):
        """BulkUpdateCheckResponse must have all fields the frontend reads."""
        for client, store, _ in api_client_factory(tmp_path):
            resp = client.get("/api/updates/check-all")
            assert resp.status_code == 200
            data = resp.json()

            # Frontend reads these fields directly
            assert "packs_checked" in data
            assert "packs_with_updates" in data
            assert "total_changes" in data
            assert "plans" in data
            assert isinstance(data["plans"], dict)

    def test_plan_entry_matches_typescript_interface(self, tmp_path, api_client_factory):
        """Each plan in plans dict must match UpdatePlanEntry interface."""
        model = _make_updatable_model(
            100, "TestModel", old_vid=101, old_fid=1011, old_sha="old",
            new_vid=102, new_fid=1021, new_sha="new",
        )
        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            _create_pack_with_lock(
                store, name="TestPack", model_id=100,
                version_id=101, file_id=1011, sha256="old",
            )
            resp = client.get("/api/updates/check-all")
            data = resp.json()

            assert "TestPack" in data["plans"], f"Missing TestPack in plans: {data['plans'].keys()}"
            plan = data["plans"]["TestPack"]

            # UpdatePlanEntry interface from updatesStore.ts lines 3-22
            assert "pack" in plan
            assert "already_up_to_date" in plan
            assert "changes" in plan and isinstance(plan["changes"], list)
            assert "ambiguous" in plan and isinstance(plan["ambiguous"], list)
            assert "impacted_packs" in plan and isinstance(plan["impacted_packs"], list)

    def test_change_has_provider_version_id_for_dismissed_tracking(self, tmp_path, api_client_factory):
        """
        Frontend builds version key from change.new.provider_version_id.
        updatesStore.ts line 53: c.new.provider_version_id ?? '?'
        If this field is missing, dismissed tracking breaks silently.
        """
        model = _make_updatable_model(
            200, "VersionTrack", old_vid=201, old_fid=2011, old_sha="old",
            new_vid=202, new_fid=2021, new_sha="new",
        )
        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            _create_pack_with_lock(
                store, name="VersionTrackPack", model_id=200,
                version_id=201, file_id=2011, sha256="old",
            )
            resp = client.get("/api/updates/check-all")
            data = resp.json()
            plan = data["plans"]["VersionTrackPack"]

            assert len(plan["changes"]) >= 1
            change = plan["changes"][0]

            # These fields are read by the frontend
            assert "dependency_id" in change
            assert "old" in change and isinstance(change["old"], dict)
            assert "new" in change and isinstance(change["new"], dict)

            # Critical: frontend uses this for dismissed version key
            assert "provider_version_id" in change["new"], (
                "Missing provider_version_id in change.new — "
                "this breaks dismissed update tracking in the frontend"
            )
            assert change["new"]["provider_version_id"] == 202


class TestApplyUpdateAPIContract:
    """
    Frontend: updatesStore.ts line 213-222
    Calls POST /api/updates/apply with { pack, sync: false, options? }
    Expects: { applied: bool, ... }
    If `applied` is true, frontend queues downloads.
    """

    def test_apply_returns_applied_field(self, tmp_path, api_client_factory):
        """Frontend checks result.applied to decide whether to queue downloads."""
        model = _make_updatable_model(
            300, "ApplyTest", old_vid=301, old_fid=3011, old_sha="old",
            new_vid=302, new_fid=3021, new_sha="new",
        )
        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            _create_pack_with_lock(
                store, name="ApplyPack", model_id=300,
                version_id=301, file_id=3011, sha256="old",
            )
            resp = client.post("/api/updates/apply", json={
                "pack": "ApplyPack",
                "sync": False,
            })
            assert resp.status_code == 200
            data = resp.json()

            # Frontend reads these fields (updatesStore.ts line 222)
            assert "applied" in data, "Missing 'applied' field — frontend needs this to queue downloads"
            assert isinstance(data["applied"], bool)
            assert data["applied"] is True

            # Other fields the frontend might use
            assert "pack" in data
            assert "lock_updated" in data

    def test_apply_returns_full_update_result_shape(self, tmp_path, api_client_factory):
        """UpdateResult model fields should all be present."""
        model = _make_updatable_model(
            310, "FullResult", old_vid=311, old_fid=3111, old_sha="old",
            new_vid=312, new_fid=3121, new_sha="new",
        )
        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            _create_pack_with_lock(
                store, name="FullResultPack", model_id=310,
                version_id=311, file_id=3111, sha256="old",
            )
            resp = client.post("/api/updates/apply", json={
                "pack": "FullResultPack", "sync": False,
            })
            data = resp.json()

            # All UpdateResult fields (models.py lines 1184-1194)
            for field in ["pack", "applied", "lock_updated", "synced",
                          "already_up_to_date", "previews_merged",
                          "description_updated", "model_info_updated"]:
                assert field in data, f"Missing field '{field}' in UpdateResult"


class TestApplyBatchAPIContract:
    """
    Frontend: updatesStore.ts lines 291-298
    Calls POST /api/updates/apply-batch with { packs, sync, options? }
    Expects: { results: { packName: UpdateResult }, total_applied, total_failed }
    """

    def test_batch_response_has_required_fields(self, tmp_path, api_client_factory):
        model_a = _make_updatable_model(400, "BatchA", 401, 4011, "old_a", 402, 4021, "new_a")
        model_b = _make_updatable_model(500, "BatchB", 501, 5011, "old_b", 502, 5021, "new_b")

        for client, store, _ in api_client_factory(tmp_path, models=[model_a, model_b]):
            _create_pack_with_lock(store, name="BatchAPack", model_id=400, version_id=401, file_id=4011, sha256="old_a")
            _create_pack_with_lock(store, name="BatchBPack", model_id=500, version_id=501, file_id=5011, sha256="old_b")

            resp = client.post("/api/updates/apply-batch", json={
                "packs": ["BatchAPack", "BatchBPack"],
                "sync": False,
            })
            assert resp.status_code == 200
            data = resp.json()

            # Frontend reads these (updatesStore.ts lines 291-298)
            assert "results" in data and isinstance(data["results"], dict)
            assert "total_applied" in data
            assert "total_failed" in data

            # Each result must have 'applied'
            for pack_name, result in data["results"].items():
                assert "applied" in result, f"Missing 'applied' in batch result for {pack_name}"

            assert data["total_applied"] == 2


class TestListPacksAPIContract:
    """
    Frontend: PacksPage.tsx
    Calls GET /api/packs
    Expects: { packs: [{ name, version, description, pack_type, dependencies_count,
              has_unresolved, thumbnail, thumbnail_type, source_url, tags, user_tags,
              is_nsfw, is_nsfw_hidden, created_at }] }
    """

    def test_list_packs_response_shape(self, tmp_path, api_client_factory):
        model = _make_lora(600, 601, 6011, name="PackListTest")
        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            # Import a pack so we have something to list
            with patch.object(store.pack_service, "_download_previews", return_value=[]):
                store.import_civitai("https://civitai.com/models/600", selected_version_ids=[601])

            resp = client.get("/api/packs")
            assert resp.status_code == 200
            data = resp.json()

            assert "packs" in data
            assert len(data["packs"]) >= 1

            pack = data["packs"][0]

            # All fields the frontend reads from PackSummary
            required_fields = [
                "name", "version", "description", "pack_type",
                "dependencies_count", "has_unresolved",
                "thumbnail", "thumbnail_type",
                "tags", "user_tags",
                "is_nsfw", "is_nsfw_hidden",
            ]
            for field in required_fields:
                assert field in pack, f"Missing field '{field}' in pack list item"

            # thumbnail_type is critical for video support
            assert pack["thumbnail_type"] in ("image", "video"), (
                f"Invalid thumbnail_type: {pack['thumbnail_type']}"
            )


class TestStatusAPIContract:
    """
    Frontend uses GET /api/store/status
    Expects: StatusReport with { profile, ui_targets, active, missing_blobs, unresolved, shadowed }
    """

    def test_status_response_shape(self, tmp_path, api_client_factory):
        for client, store, _ in api_client_factory(tmp_path):
            resp = client.get("/api/store/status")
            assert resp.status_code == 200
            data = resp.json()

            # StatusReport fields (models.py lines 1134-1141)
            assert "profile" in data
            assert "ui_targets" in data and isinstance(data["ui_targets"], list)
            assert "active" in data and isinstance(data["active"], dict)
            assert "missing_blobs" in data and isinstance(data["missing_blobs"], list)
            assert "unresolved" in data and isinstance(data["unresolved"], list)
            assert "shadowed" in data and isinstance(data["shadowed"], list)


class TestProfilesStatusAPIContract:
    """
    Frontend: ProfilesPage.tsx, ProfileDropdown.tsx
    Calls GET /api/profiles/status
    Expects: { ui_statuses: [{ui, active_profile, stack, stack_depth}],
              shadowed: [], shadowed_count, updates_available }
    """

    def test_profiles_status_response_shape(self, tmp_path, api_client_factory):
        for client, store, _ in api_client_factory(tmp_path):
            resp = client.get("/api/profiles/status")
            assert resp.status_code == 200
            data = resp.json()

            assert "ui_statuses" in data and isinstance(data["ui_statuses"], list)
            assert "shadowed" in data and isinstance(data["shadowed"], list)
            assert "shadowed_count" in data
            assert "updates_available" in data

            # If there are UI statuses, verify their shape
            for ui_status in data["ui_statuses"]:
                assert "ui" in ui_status
                assert "active_profile" in ui_status
                assert "stack" in ui_status and isinstance(ui_status["stack"], list)
                assert "stack_depth" in ui_status


class TestDownloadTrackingAPIContract:
    """
    Frontend: DownloadsPage.tsx
    Calls GET /api/packs/downloads/active
    Expects: [{ download_id, pack_name, asset_name, filename, status,
               progress, downloaded_bytes, total_bytes, group_id, group_label }]
    """

    def test_downloads_active_returns_list(self, tmp_path, api_client_factory):
        for client, store, _ in api_client_factory(tmp_path):
            resp = client.get("/api/packs/downloads/active")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)

    def test_download_entry_has_group_fields(self, tmp_path, api_client_factory):
        """Download entries must include group_id and group_label for grouping."""
        model = _make_lora(700, 701, 7011, name="DlGroupTest")
        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            from src.store.models import (
                AssetKind, DependencySelector, ExposeConfig,
                Pack, PackDependency, PackLock, PackSource, ProviderName,
                ResolvedArtifact, ResolvedDependency, ArtifactProvider,
                ArtifactDownload, ArtifactIntegrity, SelectorStrategy,
            )

            # Create a minimal pack so download-asset can find the dependency
            pack = Pack(
                name="DlGroupPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.URL),
                dependencies=[PackDependency(
                    id="main_dep", kind=AssetKind.LORA,
                    selector=DependencySelector(strategy=SelectorStrategy.URL_DOWNLOAD,
                                                url="https://example.com/model.safetensors"),
                    expose=ExposeConfig(filename="model.safetensors"),
                )],
            )
            store.layout.save_pack(pack)

            lock = PackLock(pack="DlGroupPack", resolved=[ResolvedDependency(
                dependency_id="main_dep",
                artifact=ResolvedArtifact(
                    kind=AssetKind.LORA, sha256="abc123",
                    provider=ArtifactProvider(name=ProviderName.URL),
                    download=ArtifactDownload(urls=["https://example.com/model.safetensors"]),
                    integrity=ArtifactIntegrity(sha256_verified=False),
                ),
            )])
            store.layout.save_pack_lock(lock)

            # Queue a download with group fields
            resp = client.post("/api/packs/DlGroupPack/download-asset", json={
                "asset_name": "main_dep",
                "group_id": "update-12345",
                "group_label": "Pack Updates",
            })
            assert resp.status_code == 200

            # Check active downloads include group fields
            resp = client.get("/api/packs/downloads/active")
            downloads = resp.json()
            assert len(downloads) >= 1

            dl = downloads[0]
            required_fields = [
                "download_id", "pack_name", "asset_name", "filename",
                "status", "progress", "downloaded_bytes", "total_bytes",
                "group_id", "group_label",
            ]
            for field in required_fields:
                assert field in dl, f"Missing field '{field}' in download entry"

            assert dl["group_id"] == "update-12345"
            assert dl["group_label"] == "Pack Updates"

            # Cleanup
            from src.store.api import _active_downloads
            _active_downloads.clear()


class TestCheckSinglePackAPIContract:
    """
    Frontend: CivitaiPlugin.tsx
    Calls GET /api/updates/check/{packName}
    Expects: UpdateCheckResponse { pack, has_updates, changes_count, ambiguous_count, plan }
    """

    def test_check_single_pack_response_shape(self, tmp_path, api_client_factory):
        model = _make_updatable_model(800, "SingleCheck", 801, 8011, "old", 802, 8021, "new")
        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            _create_pack_with_lock(store, name="SinglePack", model_id=800,
                                   version_id=801, file_id=8011, sha256="old")

            resp = client.get("/api/updates/check/SinglePack")
            assert resp.status_code == 200
            data = resp.json()

            assert data["pack"] == "SinglePack"
            assert "has_updates" in data and isinstance(data["has_updates"], bool)
            assert "changes_count" in data
            assert "ambiguous_count" in data
            assert "plan" in data and isinstance(data["plan"], dict)

            # plan inside must also match UpdatePlanEntry
            plan = data["plan"]
            assert "changes" in plan
            assert "ambiguous" in plan


# =============================================================================
# B. USER JOURNEY TESTS
#
# These simulate complete multi-step user workflows.
# =============================================================================


class TestJourneyImportToList:
    """
    User scenario: Import a model from Civitai → see it in pack list
    with correct metadata.
    """

    def test_imported_pack_appears_in_list_with_correct_fields(self, tmp_path, api_client_factory):
        model = _make_lora(900, 901, 9011, name="MyNewLora", sha256="abc123")
        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            with patch.object(store.pack_service, "_download_previews", return_value=[]):
                pack = store.import_civitai("https://civitai.com/models/900", selected_version_ids=[901])

            resp = client.get("/api/packs")
            packs = resp.json()["packs"]

            # Find our pack
            our_pack = next((p for p in packs if "MyNewLora" in p["name"]), None)
            assert our_pack is not None, f"Imported pack not in list. Packs: {[p['name'] for p in packs]}"

            # Verify key fields
            assert our_pack["dependencies_count"] >= 1
            assert our_pack["pack_type"] in ("lora", "LORA")
            assert isinstance(our_pack["tags"], list)


class TestJourneyResolveAndVerifyLock:
    """
    User scenario: Create a pack with URL dep → resolve → verify lock
    has correct download URL and provider info.
    """

    def test_resolve_creates_valid_lock(self, tmp_path, store_factory):
        from src.store.models import (
            AssetKind, DependencySelector, ExposeConfig, Pack,
            PackDependency, PackSource, ProviderName, SelectorStrategy,
        )

        store, _ = store_factory(tmp_path)

        pack = Pack(
            name="resolve-journey",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.URL),
            dependencies=[PackDependency(
                id="main", kind=AssetKind.LORA,
                selector=DependencySelector(
                    strategy=SelectorStrategy.URL_DOWNLOAD,
                    url="https://example.com/my_model.safetensors",
                ),
                expose=ExposeConfig(filename="my_model.safetensors"),
            )],
        )
        store.layout.save_pack(pack)

        lock = store.resolve("resolve-journey")

        # Lock should exist on disk
        lock_path = store.layout.pack_lock_path("resolve-journey")
        assert lock_path.exists()

        # Read it back from disk (not from return value) to verify serialization
        disk_lock = store.layout.load_pack_lock("resolve-journey")
        assert disk_lock.pack == "resolve-journey"
        assert len(disk_lock.resolved) == 1

        resolved = disk_lock.resolved[0]
        assert resolved.dependency_id == "main"
        assert resolved.artifact.provider.name == ProviderName.URL
        assert "example.com/my_model.safetensors" in resolved.artifact.download.urls[0]

    def test_resolve_multi_strategy_pack(self, tmp_path, store_factory):
        """Pack with Civitai + URL deps should resolve both correctly."""
        from src.store.models import (
            AssetKind, CivitaiSelector, DependencySelector, ExposeConfig, Pack,
            PackDependency, PackSource, ProviderName, SelectorStrategy,
        )

        model = _make_lora(1000, 1001, 10011, sha256="civhash")
        store, _ = store_factory(tmp_path, models=[model])

        pack = Pack(
            name="multi-strategy",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=1000),
            dependencies=[
                PackDependency(
                    id="civ_dep", kind=AssetKind.LORA,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_FILE,
                        civitai=CivitaiSelector(model_id=1000, version_id=1001, file_id=10011),
                    ),
                    expose=ExposeConfig(filename="lora.safetensors"),
                ),
                PackDependency(
                    id="url_dep", kind=AssetKind.VAE,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.URL_DOWNLOAD,
                        url="https://example.com/vae.safetensors",
                    ),
                    expose=ExposeConfig(filename="vae.safetensors"),
                ),
            ],
        )
        store.layout.save_pack(pack)

        lock = store.resolve("multi-strategy")
        assert len(lock.resolved) == 2

        by_id = {r.dependency_id: r for r in lock.resolved}
        assert by_id["civ_dep"].artifact.provider.name == ProviderName.CIVITAI
        assert by_id["civ_dep"].artifact.sha256 == "civhash"
        assert by_id["url_dep"].artifact.provider.name == ProviderName.URL


class TestJourneyUpdateCycle:
    """
    User scenario: Have a pack on v1 → check for updates → see v2 is available
    → apply update → verify lock changed to v2 → verify on-disk lock file.
    """

    def test_full_update_check_apply_verify(self, tmp_path, api_client_factory):
        model = _make_updatable_model(1100, "UpdateJourney", 1101, 11011, "sha_v1", 1102, 11021, "sha_v2")

        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            _create_pack_with_lock(store, name="UpdateJourneyPack", model_id=1100,
                                   version_id=1101, file_id=11011, sha256="sha_v1")

            # Step 1: Check for updates via API
            resp = client.get("/api/updates/check-all")
            data = resp.json()
            assert data["packs_with_updates"] >= 1
            assert "UpdateJourneyPack" in data["plans"]

            plan = data["plans"]["UpdateJourneyPack"]
            assert len(plan["changes"]) == 1
            assert plan["changes"][0]["old"]["provider_version_id"] == 1101
            assert plan["changes"][0]["new"]["provider_version_id"] == 1102

            # Step 2: Apply update via API
            resp = client.post("/api/updates/apply", json={
                "pack": "UpdateJourneyPack",
                "sync": False,
            })
            assert resp.status_code == 200
            result = resp.json()
            assert result["applied"] is True

            # Step 3: Verify lock file on disk changed
            lock = store.layout.load_pack_lock("UpdateJourneyPack")
            resolved = lock.resolved[0]
            assert resolved.artifact.provider.version_id == 1102
            assert resolved.artifact.sha256 == "sha_v2"

            # Step 4: Check again — should report no updates
            resp = client.get("/api/updates/check/UpdateJourneyPack")
            data = resp.json()
            assert data["has_updates"] is False
            assert data["changes_count"] == 0

    def test_pinned_pack_not_offered_for_update(self, tmp_path, store_factory):
        """PINNED policy prevents update detection."""
        model = _make_updatable_model(1200, "PinnedModel", 1201, 12011, "old", 1202, 12021, "new")
        store, _ = store_factory(tmp_path, models=[model])

        _create_pack_with_lock(store, name="PinnedPack", model_id=1200,
                               version_id=1201, file_id=12011, sha256="old",
                               policy="PINNED")

        plan = store.check_updates("PinnedPack")
        assert len(plan.changes) == 0, "PINNED pack should not detect updates"

    def test_up_to_date_pack_reports_no_changes(self, tmp_path, store_factory):
        """Pack already at latest version should have 0 changes."""
        model = _make_lora(1300, 1301, 13011, sha256="current")
        store, _ = store_factory(tmp_path, models=[model])

        _create_pack_with_lock(store, name="UpToDate", model_id=1300,
                               version_id=1301, file_id=13011, sha256="current")

        plan = store.check_updates("UpToDate")
        assert len(plan.changes) == 0


class TestJourneyBatchUpdate:
    """
    User scenario: Multiple packs have updates → check all → batch apply
    → verify all locks updated.
    """

    def test_batch_check_and_apply(self, tmp_path, api_client_factory):
        model_a = _make_updatable_model(1400, "BatchA", 1401, 14011, "a_old", 1402, 14021, "a_new")
        model_b = _make_updatable_model(1500, "BatchB", 1501, 15011, "b_old", 1502, 15021, "b_new")

        for client, store, _ in api_client_factory(tmp_path, models=[model_a, model_b]):
            _create_pack_with_lock(store, name="BatchAP", model_id=1400, version_id=1401, file_id=14011, sha256="a_old")
            _create_pack_with_lock(store, name="BatchBP", model_id=1500, version_id=1501, file_id=15011, sha256="b_old")

            # Check all
            resp = client.get("/api/updates/check-all")
            data = resp.json()
            assert data["packs_with_updates"] >= 2

            # Batch apply
            resp = client.post("/api/updates/apply-batch", json={
                "packs": ["BatchAP", "BatchBP"],
                "sync": False,
            })
            data = resp.json()
            assert data["total_applied"] == 2

            # Verify both locks updated on disk
            lock_a = store.layout.load_pack_lock("BatchAP")
            lock_b = store.layout.load_pack_lock("BatchBP")
            assert lock_a.resolved[0].artifact.provider.version_id == 1402
            assert lock_b.resolved[0].artifact.provider.version_id == 1502


class TestJourneyInstallAndUse:
    """
    User scenario: Create pack → resolve → install blob → use pack
    → verify blob exists and pack is active.
    """

    def test_install_blob_via_file_url(self, tmp_path, store_factory):
        """Install using file:// URL places blob in store."""
        from src.store.models import (
            AssetKind, DependencySelector, ExposeConfig, Pack,
            PackDependency, PackLock, PackSource, ProviderName,
            ResolvedArtifact, ResolvedDependency, ArtifactProvider,
            ArtifactDownload, ArtifactIntegrity, SelectorStrategy,
        )

        store, _ = store_factory(tmp_path)

        content = b"fake safetensors model data for install test"
        sha256 = hashlib.sha256(content).hexdigest().lower()
        source_file = tmp_path / "source_model.safetensors"
        source_file.write_bytes(content)

        pack = Pack(
            name="install-test",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.URL),
            dependencies=[PackDependency(
                id="main", kind=AssetKind.LORA,
                selector=DependencySelector(strategy=SelectorStrategy.URL_DOWNLOAD,
                                            url=source_file.as_uri()),
                expose=ExposeConfig(filename="model.safetensors"),
            )],
        )
        store.layout.save_pack(pack)

        lock = PackLock(pack="install-test", resolved=[ResolvedDependency(
            dependency_id="main",
            artifact=ResolvedArtifact(
                kind=AssetKind.LORA, sha256=sha256, size_bytes=len(content),
                provider=ArtifactProvider(name=ProviderName.URL),
                download=ArtifactDownload(urls=[source_file.as_uri()]),
                integrity=ArtifactIntegrity(sha256_verified=True),
            ),
        )])
        store.layout.save_pack_lock(lock)

        store.install("install-test")

        assert store.blob_store.blob_exists(sha256)
        assert store.blob_store.verify(sha256)

    def test_use_pack_activates_it(self, tmp_path, store_factory):
        """use() should mark the pack as active."""
        from src.store.models import (
            AssetKind, DependencySelector, ExposeConfig, Pack,
            PackDependency, PackLock, PackSource, ProviderName,
            ResolvedArtifact, ResolvedDependency, ArtifactProvider,
            ArtifactDownload, ArtifactIntegrity, SelectorStrategy,
        )

        store, _ = store_factory(tmp_path)

        content = b"use-test model blob"
        sha256 = _plant_blob(store, content)

        pack = Pack(
            name="UseTestPack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=999),
            dependencies=[PackDependency(
                id="main", kind=AssetKind.LORA,
                selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                expose=ExposeConfig(filename="use_test.safetensors"),
            )],
        )
        store.layout.save_pack(pack)

        lock = PackLock(pack="UseTestPack", resolved=[ResolvedDependency(
            dependency_id="main",
            artifact=ResolvedArtifact(
                kind=AssetKind.LORA, sha256=sha256,
                provider=ArtifactProvider(name=ProviderName.CIVITAI),
                download=ArtifactDownload(urls=[]),
                integrity=ArtifactIntegrity(sha256_verified=True),
            ),
        )])
        store.layout.save_pack_lock(lock)

        store.profile_service.add_pack_to_global("UseTestPack")

        result = store.use("UseTestPack", ui_targets=[])

        # UseResult fields (models.py lines 1242-1250)
        assert result.pack == "UseTestPack"
        assert result.synced is not None  # bool
        assert isinstance(result.ui_targets, list)
        assert isinstance(result.notes, list)


# =============================================================================
# C. EDGE CASE TESTS
#
# Things that have actually broken or are likely to break.
# =============================================================================


class TestImportEdgeCases:
    """Edge cases during pack import from Civitai."""

    def test_checkpoint_import_creates_base_model_dep(self, tmp_path, store_factory):
        """
        Checkpoint models create a base_checkpoint dep with BASE_MODEL_HINT
        strategy BEFORE the main dep. This broke tests that assumed deps[0]
        was the main model.
        """
        from src.store.models import SelectorStrategy

        model = FakeModel(
            id=1600, name="CheckpointModel", type="Checkpoint",
            versions=[FakeModelVersion(
                id=1601, model_id=1600, name="v1.0",
                base_model="SDXL 1.0",
                files=[FakeFile(
                    id=16011, name="model.safetensors", sha256="ckpt_hash",
                    download_url="https://civitai.com/api/download/models/1601",
                ).to_dict()],
                images=[],
            )],
        )
        store, _ = store_factory(tmp_path, models=[model])

        with patch.object(store.pack_service, "_download_previews", return_value=[]):
            pack = store.import_civitai("https://civitai.com/models/1600", selected_version_ids=[1601])

        # Should have at least 2 deps: base_checkpoint + main
        assert len(pack.dependencies) >= 2, (
            f"Checkpoint should have base_checkpoint dep. Got: {[d.id for d in pack.dependencies]}"
        )

        # Find deps by strategy
        strategies = {d.id: d.selector.strategy for d in pack.dependencies}

        # The base_checkpoint should use BASE_MODEL_HINT
        base_deps = [d for d in pack.dependencies if d.selector.strategy == SelectorStrategy.BASE_MODEL_HINT]
        assert len(base_deps) >= 1, f"No BASE_MODEL_HINT dep found. Strategies: {strategies}"

        # The main model should use CIVITAI_MODEL_LATEST
        main_deps = [d for d in pack.dependencies
                     if d.selector.civitai and d.selector.civitai.model_id == 1600
                     and d.selector.strategy == SelectorStrategy.CIVITAI_MODEL_LATEST]
        assert len(main_deps) == 1, f"No main CIVITAI_MODEL_LATEST dep found. Strategies: {strategies}"

    def test_lora_import_also_gets_base_model_dep(self, tmp_path, store_factory):
        """
        LORA imports with base_model also get a base_checkpoint dep.
        This is important: ALL model types with base_model get it, not just Checkpoints.
        The base_checkpoint dep uses BASE_MODEL_HINT strategy and is PINNED.
        """
        from src.store.models import SelectorStrategy, UpdatePolicyMode

        model = _make_lora(1700, 1701, 17011, name="SimpleLora")
        store, _ = store_factory(tmp_path, models=[model])

        with patch.object(store.pack_service, "_download_previews", return_value=[]):
            pack = store.import_civitai("https://civitai.com/models/1700", selected_version_ids=[1701])

        # Both LORA and Checkpoint get a base_checkpoint dep when base_model is set
        assert len(pack.dependencies) >= 2

        # base_checkpoint should be PINNED and use BASE_MODEL_HINT
        base_deps = [d for d in pack.dependencies if d.id == "base_checkpoint"]
        assert len(base_deps) == 1
        assert base_deps[0].selector.strategy == SelectorStrategy.BASE_MODEL_HINT
        assert base_deps[0].update_policy.mode == UpdatePolicyMode.PINNED

        # Main dep should point to the right model
        main_deps = [d for d in pack.dependencies
                     if d.selector.civitai and d.selector.civitai.model_id == 1700]
        assert len(main_deps) == 1


class TestResolverRegistryEdgeCases:
    """Edge cases in the dependency resolver registry."""

    def test_unknown_strategy_returns_none(self, tmp_path, store_factory):
        """Unknown strategy should gracefully return None, not crash."""
        from src.store.models import (
            AssetKind, DependencySelector, ExposeConfig, Pack,
            PackDependency, PackSource, ProviderName, SelectorStrategy,
        )

        store, _ = store_factory(tmp_path)

        pack = Pack(
            name="unknown-strategy",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.URL),
            dependencies=[PackDependency(
                id="main", kind=AssetKind.LORA,
                selector=DependencySelector(
                    strategy=SelectorStrategy.HUGGINGFACE_FILE,
                    huggingface={"repo_id": "org/model", "filename": "model.safetensors"},
                ),
                expose=ExposeConfig(filename="model.safetensors"),
            )],
        )
        store.layout.save_pack(pack)

        # Should not crash — HF resolver should handle this
        lock = store.resolve("unknown-strategy")

        # HuggingFace resolver should produce a result
        assert len(lock.resolved) == 1
        assert lock.resolved[0].artifact.provider.name == ProviderName.HUGGINGFACE


class TestAuthProviderEdgeCases:
    """Edge cases in download auth provider integration."""

    def test_store_creates_auth_provider_with_api_key(self, tmp_path):
        """Store should wire CivitaiAuthProvider into BlobStore."""
        from src.store import Store
        from src.store.download_auth import CivitaiAuthProvider

        store = Store(tmp_path, civitai_api_key="test-key-xyz")
        store.init()

        assert len(store.blob_store._auth_providers) >= 1
        auth = store.blob_store._auth_providers[0]
        assert isinstance(auth, CivitaiAuthProvider)

    def test_auth_provider_matches_civitai_urls_only(self, tmp_path):
        """CivitaiAuthProvider should only match civitai.com URLs."""
        from src.store import Store

        store = Store(tmp_path, civitai_api_key="key")
        store.init()

        auth = store.blob_store._auth_providers[0]
        assert auth.matches("https://civitai.com/api/download/models/123") is True
        assert auth.matches("https://cdn.civitai.com/files/model.bin") is True
        assert auth.matches("https://huggingface.co/org/repo/model.bin") is False
        assert auth.matches("https://example.com/model.bin") is False

    def test_store_without_api_key_still_has_auth_provider(self, tmp_path):
        """BlobStore should always have CivitaiAuthProvider (even without key)."""
        from src.store import Store
        from src.store.download_auth import CivitaiAuthProvider

        store = Store(tmp_path)
        store.init()

        assert len(store.blob_store._auth_providers) >= 1
        assert isinstance(store.blob_store._auth_providers[0], CivitaiAuthProvider)


class TestUpdateServiceEdgeCases:
    """Edge cases in the update service."""

    def test_pack_without_lock_does_not_crash_on_check(self, tmp_path, store_factory):
        """check_updates on a pack with no lock.json should not crash."""
        from src.store.models import (
            AssetKind, CivitaiSelector, DependencySelector, ExposeConfig,
            Pack, PackDependency, PackSource, ProviderName, SelectorStrategy,
            UpdatePolicy, UpdatePolicyMode,
        )

        model = _make_lora(1800, 1801, 18011)
        store, _ = store_factory(tmp_path, models=[model])

        # Create pack WITHOUT lock file
        pack = Pack(
            name="NoLockPack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=1800),
            dependencies=[PackDependency(
                id="main", kind=AssetKind.LORA,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai=CivitaiSelector(model_id=1800),
                ),
                update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                expose=ExposeConfig(filename="model.safetensors"),
            )],
        )
        store.layout.save_pack(pack)

        # Should not crash — should return plan with 0 changes or handle gracefully
        try:
            plan = store.check_updates("NoLockPack")
            # If it returns, it should be a valid plan
            assert hasattr(plan, "changes")
        except Exception as e:
            # Some implementations might raise — but it shouldn't be an unhandled crash
            # Acceptable errors: "No lock file found"
            assert "lock" in str(e).lower() or "not found" in str(e).lower(), (
                f"Unexpected error: {e}"
            )

    def test_check_all_with_mixed_packs(self, tmp_path, api_client_factory):
        """
        check_all should handle a mix of updatable, up-to-date, and pinned packs
        without crashing.
        """
        model_updatable = _make_updatable_model(1900, "Updatable", 1901, 19011, "old", 1902, 19021, "new")
        model_current = _make_lora(2000, 2001, 20011, name="Current", sha256="cur")
        model_pinned = _make_updatable_model(2100, "Pinned", 2101, 21011, "p_old", 2102, 21021, "p_new")

        for client, store, _ in api_client_factory(
            tmp_path, models=[model_updatable, model_current, model_pinned]
        ):
            _create_pack_with_lock(store, name="UpdatablePack", model_id=1900,
                                   version_id=1901, file_id=19011, sha256="old")
            _create_pack_with_lock(store, name="CurrentPack", model_id=2000,
                                   version_id=2001, file_id=20011, sha256="cur")
            _create_pack_with_lock(store, name="PinnedPack", model_id=2100,
                                   version_id=2101, file_id=21011, sha256="p_old",
                                   policy="PINNED")

            resp = client.get("/api/updates/check-all")
            assert resp.status_code == 200
            data = resp.json()

            # packs_checked may vary depending on which packs have updatable deps
            assert data["packs_checked"] >= 1

            # Only the updatable pack should appear in plans (with actual changes)
            assert "UpdatablePack" in data["plans"], (
                f"UpdatablePack not in plans. Plans: {list(data['plans'].keys())}"
            )
            assert "CurrentPack" not in data["plans"], "Up-to-date pack should not be in plans"
            assert "PinnedPack" not in data["plans"], "Pinned pack should not be in plans"
            assert data["packs_with_updates"] >= 1


class TestLockFileSerialization:
    """
    Verify lock files serialize correctly to disk and can be read back.
    This catches issues where Pydantic models have aliases or config
    that changes the serialized field names.
    """

    def test_lock_roundtrip_preserves_all_fields(self, tmp_path, store_factory):
        """Write lock → read back → all fields preserved."""
        from src.store.models import (
            AssetKind, ArtifactProvider, ArtifactDownload, ArtifactIntegrity,
            PackLock, ProviderName, ResolvedArtifact, ResolvedDependency,
        )

        store, _ = store_factory(tmp_path)

        lock = PackLock(pack="roundtrip-test", resolved=[ResolvedDependency(
            dependency_id="dep1",
            artifact=ResolvedArtifact(
                kind=AssetKind.LORA,
                sha256="abc123def456",
                size_bytes=123456,
                provider=ArtifactProvider(
                    name=ProviderName.CIVITAI,
                    model_id=42,
                    version_id=100,
                    file_id=200,
                ),
                download=ArtifactDownload(urls=["https://civitai.com/api/download/models/100"]),
                integrity=ArtifactIntegrity(sha256_verified=True),
            ),
        )])

        store.layout.save_pack_lock(lock)
        loaded = store.layout.load_pack_lock("roundtrip-test")

        assert loaded.pack == "roundtrip-test"
        r = loaded.resolved[0]
        assert r.dependency_id == "dep1"
        assert r.artifact.sha256 == "abc123def456"
        assert r.artifact.size_bytes == 123456
        assert r.artifact.provider.name == ProviderName.CIVITAI
        assert r.artifact.provider.model_id == 42
        assert r.artifact.provider.version_id == 100
        assert r.artifact.provider.file_id == 200
        assert r.artifact.download.urls == ["https://civitai.com/api/download/models/100"]
        assert r.artifact.integrity.sha256_verified is True

    def test_lock_json_on_disk_uses_correct_field_names(self, tmp_path, store_factory):
        """Verify the actual JSON on disk has the field names the system expects."""
        from src.store.models import (
            AssetKind, ArtifactProvider, ArtifactDownload, ArtifactIntegrity,
            PackLock, ProviderName, ResolvedArtifact, ResolvedDependency,
        )

        store, _ = store_factory(tmp_path)

        lock = PackLock(pack="json-fields-test", resolved=[ResolvedDependency(
            dependency_id="main",
            artifact=ResolvedArtifact(
                kind=AssetKind.CHECKPOINT,
                sha256="deadbeef",
                provider=ArtifactProvider(name=ProviderName.HUGGINGFACE, repo_id="org/model"),
                download=ArtifactDownload(urls=["https://hf.co/model"]),
                integrity=ArtifactIntegrity(sha256_verified=False),
            ),
        )])

        store.layout.save_pack_lock(lock)

        # Read raw JSON to verify field names
        lock_path = store.layout.pack_lock_path("json-fields-test")
        raw = json.loads(lock_path.read_text())

        assert raw["pack"] == "json-fields-test"
        assert "resolved" in raw
        assert len(raw["resolved"]) == 1

        entry = raw["resolved"][0]
        assert "dependency_id" in entry
        assert "artifact" in entry
        assert "sha256" in entry["artifact"]
        assert "provider" in entry["artifact"]
        assert "download" in entry["artifact"]


class TestStoreInitialization:
    """Verify store init creates correct directory structure."""

    def test_init_creates_required_dirs(self, tmp_path):
        from src.store import Store

        store = Store(tmp_path)
        store.init()

        assert store.is_initialized()
        assert store.layout.packs_path.is_dir()
        assert store.layout.blobs_path.is_dir()

    def test_double_init_is_safe(self, tmp_path):
        """Calling init() twice should not break anything."""
        from src.store import Store

        store = Store(tmp_path)
        store.init()
        store.init()  # second call


# =============================================================================
# D. REFACTORING RISK TESTS
#
# Targeted tests for today's refactoring changes:
# 1. DependencyResolver registry (pack_service.py)
# 2. DownloadAuthProvider loop (blob_store.py)
# 3. UpdateService fallback URL removal (update_service.py)
# 4. CivitaiUpdateProvider.build_download_url format
#
# These verify the integration points between components, NOT just the
# individual pieces in isolation.
# =============================================================================


class TestUpdateApplyDownloadURLChain:
    """
    Critical chain: update apply → lock file gets download URL →
    download-asset reads URL from lock → BlobStore downloads.

    We changed update_service to use provider.build_download_url()
    instead of hardcoded fallback. Verify the URL ends up correct.
    """

    def test_download_url_in_lock_after_update_apply(self, tmp_path, store_factory):
        """
        After applying an update, the lock file must contain a valid
        download URL that download-asset can use.

        Risk: CivitaiUpdateProvider.build_download_url() now builds the URL.
        Old code used hardcoded f"https://civitai.com/api/download/models/{version_id}".
        New code adds ?type=Model&format=SafeTensor when file_id is present.
        """
        model = _make_updatable_model(2200, "UrlChain", 2201, 22011, "old_sha", 2202, 22021, "new_sha")
        store, _ = store_factory(tmp_path, models=[model])

        _create_pack_with_lock(store, name="UrlChainPack", model_id=2200,
                               version_id=2201, file_id=22011, sha256="old_sha")

        result = store.update("UrlChainPack")
        assert result.applied

        # Read lock from disk
        lock = store.layout.load_pack_lock("UrlChainPack")
        resolved = lock.resolved[0]

        # URL must be present and point to Civitai
        urls = resolved.artifact.download.urls
        assert len(urls) >= 1, "No download URLs in lock after update"

        url = urls[0]
        assert "civitai.com" in url, f"Download URL doesn't point to Civitai: {url}"
        assert "2202" in url, f"Download URL doesn't reference new version 2202: {url}"

    def test_download_url_is_usable_by_download_asset(self, tmp_path, api_client_factory):
        """
        After update, the download-asset endpoint should be able to find
        the download URL from the lock file.

        This tests the full chain: apply → lock → download-asset reads lock URL.
        """
        model = _make_updatable_model(2300, "DlAsset", 2301, 23011, "old", 2302, 23021, "new")

        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            _create_pack_with_lock(store, name="DlAssetPack", model_id=2300,
                                   version_id=2301, file_id=23011, sha256="old")

            # Apply update via API
            resp = client.post("/api/updates/apply", json={
                "pack": "DlAssetPack", "sync": False,
            })
            assert resp.json()["applied"] is True

            # Try to queue download — should NOT fail with "No download URL available"
            resp = client.post("/api/packs/DlAssetPack/download-asset", json={
                "asset_name": "main",
            })
            # Should succeed (start download) or at least not fail with 400 "no URL"
            assert resp.status_code == 200, (
                f"download-asset failed after update: {resp.status_code} {resp.json()}"
            )
            data = resp.json()
            assert data["status"] == "started"

            # Cleanup
            from src.store.api import _active_downloads
            _active_downloads.clear()


class TestResolverProducesValidDownloadURLs:
    """
    Verify that resolver-produced download URLs are usable.

    We moved URL construction from PackService._resolve_* methods
    to DependencyResolver classes. The URLs must be correct for
    download-asset to work.
    """

    def test_civitai_file_resolver_url_from_api_response(self, tmp_path, store_factory):
        """
        CivitaiFileResolver should use downloadUrl from Civitai API response,
        NOT construct it. The FakeCivitaiClient provides downloadUrl in file data.
        """
        model = _make_lora(2400, 2401, 24011, sha256="fileresolver")
        store, _ = store_factory(tmp_path, models=[model])

        from src.store.models import (
            AssetKind, CivitaiSelector, DependencySelector, ExposeConfig,
            Pack, PackDependency, PackSource, ProviderName, SelectorStrategy,
        )

        pack = Pack(
            name="file-resolver-test",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=2400),
            dependencies=[PackDependency(
                id="main", kind=AssetKind.LORA,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelector(model_id=2400, version_id=2401, file_id=24011),
                ),
                expose=ExposeConfig(filename="model.safetensors"),
            )],
        )
        store.layout.save_pack(pack)

        lock = store.resolve("file-resolver-test")
        resolved = lock.resolved[0]

        # URL should come from FakeCivitaiClient's downloadUrl field
        url = resolved.artifact.download.urls[0]
        assert url == "https://civitai.com/api/download/models/2401", (
            f"CivitaiFileResolver URL unexpected: {url}"
        )

    def test_civitai_latest_resolver_url_from_api_response(self, tmp_path, store_factory):
        """
        CivitaiLatestResolver should use downloadUrl from Civitai API,
        falling back to constructed URL only if API doesn't provide one.
        """
        model = _make_lora(2500, 2501, 25011, sha256="latestresolver")
        store, _ = store_factory(tmp_path, models=[model])

        from src.store.models import (
            AssetKind, CivitaiSelector, DependencySelector, ExposeConfig,
            Pack, PackDependency, PackSource, ProviderName, SelectorStrategy,
        )

        pack = Pack(
            name="latest-resolver-test",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=2500),
            dependencies=[PackDependency(
                id="main", kind=AssetKind.LORA,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai=CivitaiSelector(model_id=2500),
                ),
                expose=ExposeConfig(filename="model.safetensors"),
            )],
        )
        store.layout.save_pack(pack)

        lock = store.resolve("latest-resolver-test")
        resolved = lock.resolved[0]

        url = resolved.artifact.download.urls[0]
        assert "civitai.com" in url
        # Should reference the version
        assert "2501" in url, f"URL doesn't reference version 2501: {url}"

    def test_url_resolver_preserves_exact_url(self, tmp_path, store_factory):
        """URL resolver should pass through the URL exactly as specified."""
        from src.store.models import (
            AssetKind, DependencySelector, ExposeConfig,
            Pack, PackDependency, PackSource, ProviderName, SelectorStrategy,
        )

        store, _ = store_factory(tmp_path)

        original_url = "https://cdn.example.com/models/v2/my_model.safetensors?token=abc"
        pack = Pack(
            name="url-passthrough",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.URL),
            dependencies=[PackDependency(
                id="main", kind=AssetKind.LORA,
                selector=DependencySelector(
                    strategy=SelectorStrategy.URL_DOWNLOAD,
                    url=original_url,
                ),
                expose=ExposeConfig(filename="model.safetensors"),
            )],
        )
        store.layout.save_pack(pack)

        lock = store.resolve("url-passthrough")
        assert lock.resolved[0].artifact.download.urls[0] == original_url


class TestAuthProviderInDownloadPath:
    """
    Verify that the auth provider loop in BlobStore._download_http
    correctly handles different URL scenarios.

    We replaced hardcoded `if "civitai.com" in url` with a provider loop.
    """

    def test_civitai_url_gets_token_injected(self, tmp_path):
        """CivitaiAuthProvider should inject token into civitai.com URLs."""
        from src.store.download_auth import CivitaiAuthProvider

        auth = CivitaiAuthProvider(api_key="test-key-123")

        url = "https://civitai.com/api/download/models/100"
        result = auth.authenticate_url(url)
        assert "token=test-key-123" in result
        assert result.startswith(url)  # Original URL preserved

    def test_civitai_url_with_existing_query_params(self, tmp_path):
        """Token should be appended with & if URL already has query params."""
        from src.store.download_auth import CivitaiAuthProvider

        auth = CivitaiAuthProvider(api_key="mykey")

        url = "https://civitai.com/api/download/models/100?type=Model&format=SafeTensor"
        result = auth.authenticate_url(url)
        assert "&token=mykey" in result
        assert result.startswith(url)

    def test_non_civitai_url_passes_through_unchanged(self, tmp_path):
        """Non-Civitai URLs should not be modified by any auth provider."""
        from src.store import Store

        store = Store(tmp_path, civitai_api_key="secret")
        store.init()

        # Simulate what _download_http does
        url = "https://huggingface.co/org/model/resolve/main/weights.bin"
        download_url = url
        for auth_provider in store.blob_store._auth_providers:
            if auth_provider.matches(url):
                download_url = auth_provider.authenticate_url(url)
                break

        assert download_url == url, (
            f"Non-Civitai URL was modified: {download_url}"
        )

    def test_html_error_uses_provider_message_for_civitai(self):
        """When matched auth provider exists, error message should come from it."""
        from src.store.download_auth import CivitaiAuthProvider

        auth = CivitaiAuthProvider(api_key="key")
        msg = auth.auth_error_message()
        assert "Civitai" in msg
        assert "API key" in msg

    def test_blob_store_api_key_reaches_auth_provider(self, tmp_path):
        """
        API key flow: Store(civitai_api_key=X) → BlobStore(api_key=X)
        → CivitaiAuthProvider(api_key=X).

        If this chain breaks, Civitai downloads silently fail (403).
        """
        from src.store import Store
        from src.store.download_auth import CivitaiAuthProvider

        store = Store(tmp_path, civitai_api_key="my-secret-key")
        store.init()

        auth = store.blob_store._auth_providers[0]
        assert isinstance(auth, CivitaiAuthProvider)
        assert auth.api_key == "my-secret-key"

        # Verify it actually injects into URLs
        url = "https://civitai.com/api/download/models/999"
        authenticated = auth.authenticate_url(url)
        assert "token=my-secret-key" in authenticated


class TestUpdateProviderBuildDownloadUrl:
    """
    CivitaiUpdateProvider.build_download_url() is used by UpdateService
    when applying updates. Verify it produces valid URLs.

    Change: New code adds ?type=Model&format=SafeTensor when file_id is set.
    Old code was a plain fallback.
    """

    def test_build_url_with_version_only(self):
        """URL with just version_id should be a plain Civitai download URL."""
        from src.store.civitai_update_provider import CivitaiUpdateProvider

        provider = CivitaiUpdateProvider()
        url = provider.build_download_url(version_id=12345, file_id=None)
        assert url == "https://civitai.com/api/download/models/12345"

    def test_build_url_with_file_id(self):
        """URL with file_id adds query params for file selection."""
        from src.store.civitai_update_provider import CivitaiUpdateProvider

        provider = CivitaiUpdateProvider()
        url = provider.build_download_url(version_id=12345, file_id=67890)

        assert "civitai.com/api/download/models/12345" in url
        # Should have query params
        assert "?" in url

    def test_built_url_is_compatible_with_auth_provider(self):
        """
        URLs from build_download_url must work with CivitaiAuthProvider.
        Auth provider appends ?token=X or &token=X.
        If build_download_url produces a URL with existing query params,
        auth must use & not ?.
        """
        from src.store.civitai_update_provider import CivitaiUpdateProvider
        from src.store.download_auth import CivitaiAuthProvider

        update_provider = CivitaiUpdateProvider()
        auth_provider = CivitaiAuthProvider(api_key="test-key")

        # URL with file_id (has query params)
        url_with_params = update_provider.build_download_url(version_id=100, file_id=200)
        authenticated = auth_provider.authenticate_url(url_with_params)

        # Should not have double ?
        assert authenticated.count("?") == 1, (
            f"Double ? in authenticated URL: {authenticated}"
        )
        assert "&token=test-key" in authenticated

        # URL without file_id (no query params)
        url_no_params = update_provider.build_download_url(version_id=100, file_id=None)
        authenticated2 = auth_provider.authenticate_url(url_no_params)

        assert "?token=test-key" in authenticated2


class TestUpdateServiceProviderDispatch:
    """
    We replaced hardcoded fallback URLs with provider dispatch.
    Verify the update_service correctly delegates to providers
    and doesn't silently skip updates.
    """

    def test_update_apply_writes_correct_provider_info(self, tmp_path, store_factory):
        """
        After update apply, lock should have correct provider fields:
        model_id, version_id, file_id, provider name.
        """
        model = _make_updatable_model(2600, "ProvInfo", 2601, 26011, "old", 2602, 26021, "new")
        store, _ = store_factory(tmp_path, models=[model])

        _create_pack_with_lock(store, name="ProvInfoPack", model_id=2600,
                               version_id=2601, file_id=26011, sha256="old")

        result = store.update("ProvInfoPack")
        assert result.applied

        lock = store.layout.load_pack_lock("ProvInfoPack")
        artifact = lock.resolved[0].artifact

        assert artifact.provider.version_id == 2602
        assert artifact.provider.model_id == 2600
        assert artifact.sha256 == "new"
        # provider name should still be civitai
        assert artifact.provider.name.value == "civitai" or artifact.provider.name == "civitai"

    def test_update_apply_with_options_preserves_lock_integrity(self, tmp_path, api_client_factory):
        """
        Apply with merge_previews/update_description options should
        not corrupt the lock file.
        """
        model = _make_updatable_model(2700, "OptTest", 2701, 27011, "old", 2702, 27021, "new")

        for client, store, _ in api_client_factory(tmp_path, models=[model]):
            _create_pack_with_lock(store, name="OptTestPack", model_id=2700,
                                   version_id=2701, file_id=27011, sha256="old")

            resp = client.post("/api/updates/apply", json={
                "pack": "OptTestPack",
                "sync": False,
                "options": {
                    "merge_previews": True,
                    "update_description": True,
                    "update_model_info": True,
                },
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["applied"] is True

            # Lock should still be valid
            lock = store.layout.load_pack_lock("OptTestPack")
            assert lock.pack == "OptTestPack"
            assert len(lock.resolved) >= 1
            assert lock.resolved[0].artifact.sha256 is not None


class TestResolverRegistryIntegration:
    """
    Verify the resolver registry in PackService works correctly
    for all strategy types through the Store facade (not just unit tests).
    """

    def test_resolve_uses_correct_resolver_for_each_strategy(self, tmp_path, store_factory):
        """
        Create deps with different strategies and verify each resolves
        via the correct resolver.
        """
        from src.store.models import (
            AssetKind, CivitaiSelector, DependencySelector, ExposeConfig,
            HuggingFaceSelector, Pack, PackDependency, PackSource,
            ProviderName, SelectorStrategy,
        )

        model = _make_lora(2800, 2801, 28011, sha256="civ_sha")
        store, _ = store_factory(tmp_path, models=[model])

        # Pack with 3 different strategy deps
        pack = Pack(
            name="multi-resolver",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.URL),
            dependencies=[
                PackDependency(
                    id="civ", kind=AssetKind.LORA,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_FILE,
                        civitai=CivitaiSelector(model_id=2800, version_id=2801, file_id=28011),
                    ),
                    expose=ExposeConfig(filename="lora.safetensors"),
                ),
                PackDependency(
                    id="hf", kind=AssetKind.CHECKPOINT,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.HUGGINGFACE_FILE,
                        huggingface={"repo_id": "stabilityai/sdxl", "filename": "model.safetensors"},
                    ),
                    expose=ExposeConfig(filename="checkpoint.safetensors"),
                ),
                PackDependency(
                    id="url", kind=AssetKind.VAE,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.URL_DOWNLOAD,
                        url="https://example.com/vae.safetensors",
                    ),
                    expose=ExposeConfig(filename="vae.safetensors"),
                ),
            ],
        )
        store.layout.save_pack(pack)

        lock = store.resolve("multi-resolver")
        by_id = {r.dependency_id: r for r in lock.resolved}

        # Each dep should be resolved by its correct resolver
        assert by_id["civ"].artifact.provider.name == ProviderName.CIVITAI
        assert by_id["civ"].artifact.sha256 == "civ_sha"
        assert "civitai.com" in by_id["civ"].artifact.download.urls[0]

        assert by_id["hf"].artifact.provider.name == ProviderName.HUGGINGFACE
        assert "huggingface.co" in by_id["hf"].artifact.download.urls[0]

        assert by_id["url"].artifact.provider.name == ProviderName.URL
        assert by_id["url"].artifact.download.urls[0] == "https://example.com/vae.safetensors"

        assert store.is_initialized()
