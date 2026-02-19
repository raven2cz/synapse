"""
E2E Integration Tests for the full Update Flow.

Tests the complete chain: check → plan → apply → verify lock updated.
Only Civitai API is mocked (external dependency). The UpdateService,
layout, and models are tested as a realistic integrated unit.

Test scenarios:
- Single pack: check → plan → apply → lock updated with new version
- Batch: check-all → apply-batch → multiple locks updated
- With options: apply with merge_previews → previews merged into pack
- Multi-dependency pack: two deps, one updated, one pinned
- Ambiguous: multiple file candidates → choose → apply
- Already up-to-date: check returns no changes
- Mixed batch: some updated, some up-to-date, some broken
- Dry run: plan only, lock unchanged
"""

import pytest
from unittest.mock import MagicMock

from src.store.models import (
    ArtifactDownload,
    ArtifactIntegrity,
    ArtifactProvider,
    AssetKind,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackDependency,
    PackDependencyRef,
    PackLock,
    PackSource,
    PreviewInfo,
    ProviderName,
    ResolvedArtifact,
    ResolvedDependency,
    SelectorConstraints,
    SelectorStrategy,
    UpdateOptions,
    UpdatePolicy,
    UpdatePolicyMode,
)
from src.store.update_service import UpdateService


# =============================================================================
# Helpers: Build realistic packs + locks + Civitai responses
# =============================================================================


def _civitai_model_response(
    model_id: int,
    version_id: int,
    file_id: int,
    sha256: str,
    filename: str = "model.safetensors",
    extra_files: list | None = None,
    images: list | None = None,
    trained_words: list | None = None,
    description: str = "A test model",
    base_model: str = "SDXL 1.0",
):
    """Build a realistic Civitai API response for get_model()."""
    files = [
        {
            "id": file_id,
            "primary": True,
            "name": filename,
            "hashes": {"SHA256": sha256.upper()},
            "sizeKB": 2048,
            "downloadUrl": f"https://civitai.com/api/download/models/{version_id}",
        },
    ]
    if extra_files:
        files.extend(extra_files)

    return {
        "id": model_id,
        "name": "TestModel",
        "description": description,
        "modelVersions": [
            {
                "id": version_id,
                "name": f"v{version_id}",
                "baseModel": base_model,
                "trainedWords": trained_words or [],
                "files": files,
                "images": images or [
                    {"url": f"https://image.civitai.com/preview_{version_id}.jpg"},
                ],
            },
        ],
    }


def _make_pack(
    name: str,
    model_id: int,
    deps: list[PackDependency] | None = None,
    previews: list[PreviewInfo] | None = None,
    description: str = "My local description",
    version_id: int | None = None,
):
    """Build a pack with sensible defaults for update testing."""
    if deps is None:
        deps = [
            PackDependency(
                id="main-checkpoint",
                kind=AssetKind.CHECKPOINT,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai={"model_id": model_id},
                    constraints=SelectorConstraints(
                        primary_file_only=True,
                        file_ext=[".safetensors"],
                    ),
                ),
                update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                expose=ExposeConfig(filename="model.safetensors"),
            ),
        ]
    return Pack(
        name=name,
        pack_type=AssetKind.CHECKPOINT,
        source=PackSource(
            provider=ProviderName.CIVITAI,
            model_id=model_id,
            version_id=version_id,
        ),
        dependencies=deps,
        previews=previews or [],
        description=description,
    )


def _make_lock(
    pack_name: str,
    dep_id: str,
    model_id: int,
    version_id: int,
    file_id: int,
    sha256: str,
):
    """Build a lock with one resolved dependency."""
    return PackLock(
        pack=pack_name,
        resolved=[
            ResolvedDependency(
                dependency_id=dep_id,
                artifact=ResolvedArtifact(
                    kind=AssetKind.CHECKPOINT,
                    sha256=sha256,
                    size_bytes=1024 * 2048,
                    provider=ArtifactProvider(
                        name=ProviderName.CIVITAI,
                        model_id=model_id,
                        version_id=version_id,
                        file_id=file_id,
                    ),
                    download=ArtifactDownload(
                        urls=[f"https://civitai.com/api/download/models/{version_id}"],
                    ),
                    integrity=ArtifactIntegrity(sha256_verified=True),
                ),
            ),
        ],
    )


def _setup_service(packs: dict, locks: dict, civitai_responses: dict, all_pack_names: list | None = None):
    """
    Create an UpdateService with mocked layout and Civitai client.

    Args:
        packs: {pack_name: Pack}
        locks: {pack_name: PackLock | None}
        civitai_responses: {model_id: civitai_api_dict}
        all_pack_names: list of all pack names for list_packs() (defaults to packs.keys())
    """
    mock_layout = MagicMock()
    mock_layout.list_packs.return_value = list(all_pack_names or packs.keys())

    def load_pack(name):
        if name in packs:
            return packs[name]
        raise FileNotFoundError(f"Pack not found: {name}")

    def load_lock(name):
        return locks.get(name)

    mock_layout.load_pack.side_effect = load_pack
    mock_layout.load_pack_lock.side_effect = load_lock

    # save_pack_lock should update our locks dict so subsequent loads see the change
    def save_lock(lock_obj):
        locks[lock_obj.pack] = lock_obj

    mock_layout.save_pack_lock.side_effect = save_lock

    # save_pack should update our packs dict
    def save_pack(pack_obj):
        packs[pack_obj.name] = pack_obj

    mock_layout.save_pack.side_effect = save_pack

    mock_civitai = MagicMock()

    def get_model(model_id):
        if model_id in civitai_responses:
            return civitai_responses[model_id]
        raise Exception(f"Model {model_id} not found on Civitai")

    mock_civitai.get_model.side_effect = get_model

    service = UpdateService(
        layout=mock_layout,
        blob_store=MagicMock(),
        view_builder=MagicMock(),
        civitai_client=mock_civitai,
    )

    return service, mock_layout, mock_civitai


# =============================================================================
# E2E: Single Pack Full Flow
# =============================================================================


class TestE2ESinglePackFlow:
    """Full check → plan → apply → verify cycle for a single pack."""

    def test_check_finds_update_and_apply_updates_lock(self):
        """
        The core flow:
        1. Pack has dep on Civitai model 500, currently at version 100
        2. Civitai now has version 200
        3. plan_update() detects the change
        4. update_pack(sync=False) applies lock changes
        5. Lock now points to version 200 with new SHA256
        """
        pack = _make_pack("my-checkpoint", model_id=500)
        lock = _make_lock("my-checkpoint", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="aaa111")

        # Civitai returns newer version
        civitai = {
            500: _civitai_model_response(
                model_id=500, version_id=200, file_id=2000,
                sha256="bbb222",
            ),
        }

        service, mock_layout, _ = _setup_service(
            packs={"my-checkpoint": pack},
            locks={"my-checkpoint": lock},
            civitai_responses=civitai,
        )

        # Step 1: Check
        plan = service.plan_update("my-checkpoint")
        assert plan.already_up_to_date is False
        assert len(plan.changes) == 1
        assert plan.changes[0].dependency_id == "main-checkpoint"
        assert plan.changes[0].old["provider_version_id"] == 100
        assert plan.changes[0].new["provider_version_id"] == 200
        assert plan.changes[0].new["sha256"] == "bbb222"

        # Step 2: Apply (sync=False, like frontend does)
        result = service.update_pack("my-checkpoint", sync=False)
        assert result.applied is True
        assert result.lock_updated is True
        assert result.synced is False

        # Step 3: Verify lock was actually updated
        mock_layout.save_pack_lock.assert_called()
        saved_lock = mock_layout.save_pack_lock.call_args[0][0]
        resolved = saved_lock.resolved[0]
        assert resolved.dependency_id == "main-checkpoint"
        assert resolved.artifact.provider.version_id == 200
        assert resolved.artifact.provider.file_id == 2000
        assert resolved.artifact.sha256 == "bbb222"

    def test_already_up_to_date_skips_apply(self):
        """When Civitai has same version as lock, nothing happens."""
        pack = _make_pack("my-pack", model_id=500)
        lock = _make_lock("my-pack", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="aaa111")

        # Civitai returns SAME version
        civitai = {
            500: _civitai_model_response(
                model_id=500, version_id=100, file_id=1000,
                sha256="aaa111",
            ),
        }

        service, mock_layout, _ = _setup_service(
            packs={"my-pack": pack},
            locks={"my-pack": lock},
            civitai_responses=civitai,
        )

        plan = service.plan_update("my-pack")
        assert plan.already_up_to_date is True
        assert len(plan.changes) == 0

        result = service.update_pack("my-pack", sync=False)
        assert result.applied is False
        assert result.already_up_to_date is True
        mock_layout.save_pack_lock.assert_not_called()

    def test_dry_run_does_not_modify_lock(self):
        """dry_run=True creates plan but never applies it."""
        pack = _make_pack("my-pack", model_id=500)
        lock = _make_lock("my-pack", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="aaa111")

        civitai = {
            500: _civitai_model_response(
                model_id=500, version_id=200, file_id=2000,
                sha256="bbb222",
            ),
        }

        service, mock_layout, _ = _setup_service(
            packs={"my-pack": pack},
            locks={"my-pack": lock},
            civitai_responses=civitai,
        )

        result = service.update_pack("my-pack", dry_run=True, sync=False)
        assert result.applied is False
        assert result.already_up_to_date is False
        mock_layout.save_pack_lock.assert_not_called()


# =============================================================================
# E2E: Check-All + Batch Apply
# =============================================================================


class TestE2EBatchFlow:
    """Full check-all → apply-batch for multiple packs."""

    def test_check_all_then_apply_batch(self):
        """
        3 packs:
        - pack-a: has update (v100 → v200)
        - pack-b: has update (v300 → v400)
        - pack-c: up-to-date (v500 → v500)

        check_all_updates() finds 2 updates.
        apply_batch() updates both, skips pack-c.
        """
        pack_a = _make_pack("pack-a", model_id=10)
        lock_a = _make_lock("pack-a", "main-checkpoint",
                            model_id=10, version_id=100, file_id=1000,
                            sha256="hash_a_old")

        pack_b = _make_pack("pack-b", model_id=20)
        lock_b = _make_lock("pack-b", "main-checkpoint",
                            model_id=20, version_id=300, file_id=3000,
                            sha256="hash_b_old")

        pack_c = _make_pack("pack-c", model_id=30)
        lock_c = _make_lock("pack-c", "main-checkpoint",
                            model_id=30, version_id=500, file_id=5000,
                            sha256="hash_c")

        civitai = {
            10: _civitai_model_response(model_id=10, version_id=200, file_id=2000, sha256="hash_a_new"),
            20: _civitai_model_response(model_id=20, version_id=400, file_id=4000, sha256="hash_b_new"),
            30: _civitai_model_response(model_id=30, version_id=500, file_id=5000, sha256="hash_c"),
        }

        packs = {"pack-a": pack_a, "pack-b": pack_b, "pack-c": pack_c}
        locks = {"pack-a": lock_a, "pack-b": lock_b, "pack-c": lock_c}

        service, mock_layout, _ = _setup_service(packs, locks, civitai)

        # Step 1: Check all
        plans = service.check_all_updates()
        # pack-c is up-to-date, so only 2 should have updates
        packs_with_updates = {name for name, plan in plans.items() if not plan.already_up_to_date}
        assert packs_with_updates == {"pack-a", "pack-b"}

        # Step 2: Batch apply all 3 (pack-c will be skipped)
        result = service.apply_batch(["pack-a", "pack-b", "pack-c"], sync=False)
        assert result.total_applied == 2
        assert result.total_skipped == 1
        assert result.total_failed == 0

        # Step 3: Verify locks
        assert locks["pack-a"].resolved[0].artifact.provider.version_id == 200
        assert locks["pack-a"].resolved[0].artifact.sha256 == "hash_a_new"
        assert locks["pack-b"].resolved[0].artifact.provider.version_id == 400
        assert locks["pack-b"].resolved[0].artifact.sha256 == "hash_b_new"
        # pack-c unchanged
        assert locks["pack-c"].resolved[0].artifact.provider.version_id == 500

    def test_batch_with_broken_pack(self):
        """
        Batch with a non-existent pack should report failure
        but not block other packs.
        """
        pack_a = _make_pack("pack-a", model_id=10)
        lock_a = _make_lock("pack-a", "main-checkpoint",
                            model_id=10, version_id=100, file_id=1000,
                            sha256="hash_old")

        civitai = {
            10: _civitai_model_response(model_id=10, version_id=200, file_id=2000, sha256="hash_new"),
        }

        packs = {"pack-a": pack_a}
        locks = {"pack-a": lock_a}

        service, _, _ = _setup_service(
            packs, locks, civitai,
            all_pack_names=["pack-a"],
        )

        result = service.apply_batch(["pack-a", "nonexistent-pack"], sync=False)
        assert result.total_applied == 1
        assert result.total_failed == 1
        assert result.results["nonexistent-pack"]["applied"] is False
        assert "error" in result.results["nonexistent-pack"]
        # pack-a still succeeded
        assert locks["pack-a"].resolved[0].artifact.provider.version_id == 200


# =============================================================================
# E2E: Update With Options (previews, description, model info)
# =============================================================================


class TestE2EWithOptions:
    """Full flow with UpdateOptions: merge previews, update description, sync model info."""

    def test_apply_with_merge_previews(self):
        """
        Pack has 2 local previews. Civitai has 3 (one overlaps).
        After apply with merge_previews=True → 4 total previews.
        """
        pack = _make_pack(
            "my-pack", model_id=500, version_id=100,
            previews=[
                PreviewInfo(filename="local1.jpg", url="https://image.civitai.com/existing.jpg"),
                PreviewInfo(filename="custom.jpg", url="https://my-cdn.com/my-custom.jpg"),
            ],
        )
        lock = _make_lock("my-pack", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="aaa111")

        civitai = {
            500: _civitai_model_response(
                model_id=500, version_id=200, file_id=2000,
                sha256="bbb222",
                images=[
                    {"url": "https://image.civitai.com/existing.jpg"},  # Already exists
                    {"url": "https://image.civitai.com/new1.jpg"},      # New
                    {"url": "https://image.civitai.com/new2.jpg"},      # New
                ],
            ),
        }

        service, _, _ = _setup_service(
            packs={"my-pack": pack},
            locks={"my-pack": lock},
            civitai_responses=civitai,
        )

        result = service.update_pack(
            "my-pack", sync=False,
            options=UpdateOptions(merge_previews=True),
        )

        assert result.applied is True
        assert result.previews_merged == 2  # 2 new added
        # Pack should now have 4 previews (2 original + 2 new)
        assert len(pack.previews) == 4

    def test_apply_with_update_description(self):
        """apply with update_description=True overwrites local description."""
        pack = _make_pack("my-pack", model_id=500, description="My custom notes")
        lock = _make_lock("my-pack", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="aaa111")

        civitai = {
            500: _civitai_model_response(
                model_id=500, version_id=200, file_id=2000,
                sha256="bbb222",
                description="Updated author notes with changelog",
            ),
        }

        service, _, _ = _setup_service(
            packs={"my-pack": pack},
            locks={"my-pack": lock},
            civitai_responses=civitai,
        )

        result = service.update_pack(
            "my-pack", sync=False,
            options=UpdateOptions(update_description=True),
        )

        assert result.applied is True
        assert result.description_updated is True
        assert pack.description == "Updated author notes with changelog"

    def test_apply_without_options_preserves_description(self):
        """Without update_description, description stays as user set it."""
        pack = _make_pack("my-pack", model_id=500, description="My custom notes")
        lock = _make_lock("my-pack", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="aaa111")

        civitai = {
            500: _civitai_model_response(
                model_id=500, version_id=200, file_id=2000,
                sha256="bbb222",
                description="Totally different text",
            ),
        }

        service, _, _ = _setup_service(
            packs={"my-pack": pack},
            locks={"my-pack": lock},
            civitai_responses=civitai,
        )

        result = service.update_pack("my-pack", sync=False)
        assert result.applied is True
        assert result.description_updated is False
        assert pack.description == "My custom notes"

    def test_apply_with_model_info_sync(self):
        """update_model_info=True syncs base_model and trigger words."""
        pack = _make_pack("my-pack", model_id=500, version_id=100)
        pack.base_model = "SD 1.5"
        # Give the dep expose.trigger_words so they can be synced
        pack.dependencies[0].expose.trigger_words = ["old_trigger"]

        lock = _make_lock("my-pack", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="aaa111")

        civitai = {
            500: _civitai_model_response(
                model_id=500, version_id=200, file_id=2000,
                sha256="bbb222",
                base_model="SDXL 1.0",
                trained_words=["new_trigger", "style"],
            ),
        }

        service, _, _ = _setup_service(
            packs={"my-pack": pack},
            locks={"my-pack": lock},
            civitai_responses=civitai,
        )

        result = service.update_pack(
            "my-pack", sync=False,
            options=UpdateOptions(update_model_info=True),
        )

        assert result.applied is True
        assert result.model_info_updated is True
        assert pack.base_model == "SDXL 1.0"
        assert set(pack.dependencies[0].expose.trigger_words) == {"new_trigger", "style"}


# =============================================================================
# E2E: Multi-Dependency Pack
# =============================================================================


class TestE2EMultiDependency:
    """Pack with multiple dependencies: some updatable, some pinned."""

    def test_two_deps_one_updated_one_pinned(self):
        """
        Pack has:
        - main-checkpoint (follow_latest, model 500) → gets updated
        - extra-lora (pinned, model 600) → stays unchanged
        """
        deps = [
            PackDependency(
                id="main-checkpoint",
                kind=AssetKind.CHECKPOINT,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai={"model_id": 500},
                    constraints=SelectorConstraints(primary_file_only=True),
                ),
                update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                expose=ExposeConfig(filename="checkpoint.safetensors"),
            ),
            PackDependency(
                id="extra-lora",
                kind=AssetKind.LORA,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai={"model_id": 600},
                ),
                update_policy=UpdatePolicy(mode=UpdatePolicyMode.PINNED),  # Pinned!
                expose=ExposeConfig(filename="lora.safetensors"),
            ),
        ]

        pack = _make_pack("multi-pack", model_id=500, deps=deps)

        lock = PackLock(
            pack="multi-pack",
            resolved=[
                ResolvedDependency(
                    dependency_id="main-checkpoint",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.CHECKPOINT,
                        sha256="ckpt_old",
                        size_bytes=2048000,
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=500, version_id=100, file_id=1000,
                        ),
                        download=ArtifactDownload(urls=["https://civitai.com/api/download/models/100"]),
                        integrity=ArtifactIntegrity(sha256_verified=True),
                    ),
                ),
                ResolvedDependency(
                    dependency_id="extra-lora",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.LORA,
                        sha256="lora_hash",
                        size_bytes=128000,
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=600, version_id=300, file_id=3000,
                        ),
                        download=ArtifactDownload(urls=["https://civitai.com/api/download/models/300"]),
                        integrity=ArtifactIntegrity(sha256_verified=True),
                    ),
                ),
            ],
        )

        civitai = {
            500: _civitai_model_response(model_id=500, version_id=200, file_id=2000, sha256="ckpt_new"),
            600: _civitai_model_response(model_id=600, version_id=400, file_id=4000, sha256="lora_new"),
        }

        packs = {"multi-pack": pack}
        locks = {"multi-pack": lock}

        service, _, _ = _setup_service(packs, locks, civitai)

        # Check
        plan = service.plan_update("multi-pack")
        assert len(plan.changes) == 1  # Only checkpoint, lora is pinned
        assert plan.changes[0].dependency_id == "main-checkpoint"

        # Apply
        result = service.update_pack("multi-pack", sync=False)
        assert result.applied is True

        # Verify: checkpoint updated, lora unchanged
        updated_lock = locks["multi-pack"]
        ckpt = next(r for r in updated_lock.resolved if r.dependency_id == "main-checkpoint")
        lora = next(r for r in updated_lock.resolved if r.dependency_id == "extra-lora")

        assert ckpt.artifact.provider.version_id == 200
        assert ckpt.artifact.sha256 == "ckpt_new"
        assert lora.artifact.provider.version_id == 300  # Unchanged
        assert lora.artifact.sha256 == "lora_hash"      # Unchanged

    def test_two_updatable_deps_both_updated(self):
        """Both deps are follow_latest → both get updated."""
        deps = [
            PackDependency(
                id="checkpoint",
                kind=AssetKind.CHECKPOINT,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai={"model_id": 500},
                    constraints=SelectorConstraints(primary_file_only=True),
                ),
                update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                expose=ExposeConfig(filename="ckpt.safetensors"),
            ),
            PackDependency(
                id="lora",
                kind=AssetKind.LORA,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai={"model_id": 600},
                    constraints=SelectorConstraints(primary_file_only=True),
                ),
                update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                expose=ExposeConfig(filename="lora.safetensors"),
            ),
        ]

        pack = _make_pack("dual-pack", model_id=500, deps=deps)

        lock = PackLock(
            pack="dual-pack",
            resolved=[
                ResolvedDependency(
                    dependency_id="checkpoint",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.CHECKPOINT, sha256="ckpt_v1",
                        size_bytes=2048000,
                        provider=ArtifactProvider(name=ProviderName.CIVITAI,
                                                  model_id=500, version_id=100, file_id=1000),
                        download=ArtifactDownload(urls=["https://civitai.com/api/download/models/100"]),
                        integrity=ArtifactIntegrity(sha256_verified=True),
                    ),
                ),
                ResolvedDependency(
                    dependency_id="lora",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.LORA, sha256="lora_v1",
                        size_bytes=128000,
                        provider=ArtifactProvider(name=ProviderName.CIVITAI,
                                                  model_id=600, version_id=300, file_id=3000),
                        download=ArtifactDownload(urls=["https://civitai.com/api/download/models/300"]),
                        integrity=ArtifactIntegrity(sha256_verified=True),
                    ),
                ),
            ],
        )

        civitai = {
            500: _civitai_model_response(model_id=500, version_id=200, file_id=2000, sha256="ckpt_v2"),
            600: _civitai_model_response(model_id=600, version_id=400, file_id=4000, sha256="lora_v2"),
        }

        packs = {"dual-pack": pack}
        locks = {"dual-pack": lock}
        service, _, _ = _setup_service(packs, locks, civitai)

        plan = service.plan_update("dual-pack")
        assert len(plan.changes) == 2

        result = service.update_pack("dual-pack", sync=False)
        assert result.applied is True

        updated = locks["dual-pack"]
        ckpt = next(r for r in updated.resolved if r.dependency_id == "checkpoint")
        lora = next(r for r in updated.resolved if r.dependency_id == "lora")
        assert ckpt.artifact.provider.version_id == 200
        assert ckpt.artifact.sha256 == "ckpt_v2"
        assert lora.artifact.provider.version_id == 400
        assert lora.artifact.sha256 == "lora_v2"


# =============================================================================
# E2E: Ambiguous Selection
# =============================================================================


class TestE2EAmbiguousSelection:
    """Updates where Civitai returns multiple file candidates."""

    def test_ambiguous_resolved_with_choose(self):
        """
        Civitai returns 2 files (fp16 + fp32). User picks fp16 via choose dict.
        """
        pack = _make_pack("my-pack", model_id=500)
        # Remove primary_file_only constraint so both files match
        pack.dependencies[0].selector.constraints = None

        lock = _make_lock("my-pack", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="old_hash")

        civitai = {
            500: {
                "id": 500,
                "name": "TestModel",
                "description": "desc",
                "modelVersions": [{
                    "id": 200,
                    "name": "v2",
                    "baseModel": "SDXL",
                    "trainedWords": [],
                    "files": [
                        {
                            "id": 2001,
                            "primary": True,
                            "name": "model-fp32.safetensors",
                            "hashes": {"SHA256": "HASH_FP32"},
                            "sizeKB": 4096,
                            "downloadUrl": "https://civitai.com/api/download/models/200?file=fp32",
                        },
                        {
                            "id": 2002,
                            "primary": False,
                            "name": "model-fp16.safetensors",
                            "hashes": {"SHA256": "HASH_FP16"},
                            "sizeKB": 2048,
                            "downloadUrl": "https://civitai.com/api/download/models/200?file=fp16",
                        },
                    ],
                    "images": [],
                }],
            },
        }

        packs = {"my-pack": pack}
        locks_dict = {"my-pack": lock}
        service, _, _ = _setup_service(packs, locks_dict, civitai)

        # Step 1: Plan shows ambiguous
        plan = service.plan_update("my-pack")
        assert len(plan.ambiguous) == 1
        assert len(plan.changes) == 0
        assert plan.ambiguous[0].dependency_id == "main-checkpoint"
        assert len(plan.ambiguous[0].candidates) == 2

        # Step 2: Apply with choose (pick fp16 = file 2002)
        result = service.update_pack(
            "my-pack", sync=False,
            choose={"main-checkpoint": 2002},
        )
        assert result.applied is True

        updated = locks_dict["my-pack"]
        resolved = updated.resolved[0]
        assert resolved.artifact.provider.version_id == 200
        assert resolved.artifact.provider.file_id == 2002
        assert resolved.artifact.sha256 == "hash_fp16"

    def test_ambiguous_without_choose_raises(self):
        """Trying to apply ambiguous update without choose raises error."""
        from src.store.update_service import AmbiguousSelectionError

        pack = _make_pack("my-pack", model_id=500)
        pack.dependencies[0].selector.constraints = None

        lock = _make_lock("my-pack", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="old_hash")

        civitai = {
            500: {
                "id": 500, "name": "Test", "description": "",
                "modelVersions": [{
                    "id": 200, "name": "v2", "baseModel": "SDXL",
                    "trainedWords": [],
                    "files": [
                        {"id": 2001, "primary": True, "name": "a.safetensors",
                         "hashes": {"SHA256": "AAA"}, "sizeKB": 100},
                        {"id": 2002, "primary": False, "name": "b.safetensors",
                         "hashes": {"SHA256": "BBB"}, "sizeKB": 100},
                    ],
                    "images": [],
                }],
            },
        }

        service, _, _ = _setup_service(
            packs={"my-pack": pack},
            locks={"my-pack": lock},
            civitai_responses=civitai,
        )

        with pytest.raises(AmbiguousSelectionError):
            service.update_pack("my-pack", sync=False)


# =============================================================================
# E2E: Impacted Packs (reverse dependencies)
# =============================================================================


class TestE2EImpactedPacks:
    """When pack A depends on pack B, updating B shows A as impacted."""

    def test_update_plan_includes_impacted_packs(self):
        """
        pack-child depends on pack-parent via pack_dependencies.
        Updating pack-parent should list pack-child as impacted.
        """
        pack_parent = _make_pack("pack-parent", model_id=500)
        # pack-child depends on pack-parent
        pack_child = Pack(
            name="pack-child",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.LOCAL),
            pack_dependencies=[PackDependencyRef(pack_name="pack-parent")],
        )

        lock_parent = _make_lock("pack-parent", "main-checkpoint",
                                 model_id=500, version_id=100, file_id=1000,
                                 sha256="old")

        civitai = {
            500: _civitai_model_response(model_id=500, version_id=200, file_id=2000, sha256="new"),
        }

        service, _, _ = _setup_service(
            packs={"pack-parent": pack_parent, "pack-child": pack_child},
            locks={"pack-parent": lock_parent},
            civitai_responses=civitai,
            all_pack_names=["pack-parent", "pack-child"],
        )

        plan = service.plan_update("pack-parent")
        assert "pack-child" in plan.impacted_packs


# =============================================================================
# E2E: Full Cycle - Check All → Select → Apply Batch → Verify
# =============================================================================


class TestE2EFullCycle:
    """
    Simulates the complete frontend workflow:
    1. check_all_updates() — discovers what's available
    2. User selects packs (simulated by filtering)
    3. apply_batch() — applies selected
    4. Verify locks + results

    This is the closest to what the actual UI does.
    """

    def test_full_frontend_workflow(self):
        """
        5 packs:
        - pack-a: Civitai, follow_latest, has update → SELECTED, applied
        - pack-b: Civitai, follow_latest, has update → NOT selected (user unchecked)
        - pack-c: Civitai, follow_latest, up-to-date → not in batch
        - pack-d: Local source, no Civitai deps → skipped by check_all
        - pack-e: Civitai, pinned → skipped by check_all
        """
        # pack-a: updatable, has new version
        pack_a = _make_pack("pack-a", model_id=10)
        lock_a = _make_lock("pack-a", "main-checkpoint", model_id=10,
                            version_id=100, file_id=1000, sha256="a_old")

        # pack-b: updatable, has new version
        pack_b = _make_pack("pack-b", model_id=20)
        lock_b = _make_lock("pack-b", "main-checkpoint", model_id=20,
                            version_id=300, file_id=3000, sha256="b_old")

        # pack-c: updatable, but already on latest
        pack_c = _make_pack("pack-c", model_id=30)
        lock_c = _make_lock("pack-c", "main-checkpoint", model_id=30,
                            version_id=500, file_id=5000, sha256="c_current")

        # pack-d: local source, not updatable
        pack_d = Pack(
            name="pack-d",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.LOCAL),
        )

        # pack-e: Civitai but pinned
        pack_e = Pack(
            name="pack-e",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=50),
            dependencies=[
                PackDependency(
                    id="main-checkpoint",
                    kind=AssetKind.CHECKPOINT,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                        civitai={"model_id": 50},
                    ),
                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.PINNED),
                    expose=ExposeConfig(filename="model.safetensors"),
                ),
            ],
        )
        lock_e = _make_lock("pack-e", "main-checkpoint", model_id=50,
                            version_id=600, file_id=6000, sha256="e_hash")

        civitai = {
            10: _civitai_model_response(model_id=10, version_id=200, file_id=2000, sha256="a_new"),
            20: _civitai_model_response(model_id=20, version_id=400, file_id=4000, sha256="b_new"),
            30: _civitai_model_response(model_id=30, version_id=500, file_id=5000, sha256="c_current"),
            50: _civitai_model_response(model_id=50, version_id=700, file_id=7000, sha256="e_new"),
        }

        packs = {
            "pack-a": pack_a, "pack-b": pack_b, "pack-c": pack_c,
            "pack-d": pack_d, "pack-e": pack_e,
        }
        locks = {
            "pack-a": lock_a, "pack-b": lock_b, "pack-c": lock_c,
            "pack-e": lock_e,
        }

        service, _, _ = _setup_service(packs, locks, civitai)

        # === STEP 1: check_all_updates() (what the frontend does on "Check Updates" click) ===
        all_plans = service.check_all_updates()

        # pack-d: not updatable (local) → not in results
        assert "pack-d" not in all_plans
        # pack-e: not updatable (pinned) → not in results
        assert "pack-e" not in all_plans
        # pack-c: updatable but up-to-date
        assert "pack-c" in all_plans
        assert all_plans["pack-c"].already_up_to_date is True
        # pack-a and pack-b: have updates
        assert "pack-a" in all_plans
        assert all_plans["pack-a"].already_up_to_date is False
        assert "pack-b" in all_plans
        assert all_plans["pack-b"].already_up_to_date is False

        # === STEP 2: User selects only pack-a (unchecks pack-b) ===
        selected = ["pack-a"]

        # === STEP 3: apply_batch() with selected packs only ===
        result = service.apply_batch(selected, sync=False)
        assert result.total_applied == 1
        assert result.total_failed == 0

        # === STEP 4: Verify ===
        # pack-a: updated
        assert locks["pack-a"].resolved[0].artifact.provider.version_id == 200
        assert locks["pack-a"].resolved[0].artifact.sha256 == "a_new"
        # pack-b: NOT updated (user didn't select it)
        assert locks["pack-b"].resolved[0].artifact.provider.version_id == 300
        assert locks["pack-b"].resolved[0].artifact.sha256 == "b_old"

    def test_apply_batch_with_options(self):
        """Batch apply with options passes them through to each pack."""
        pack_a = _make_pack("pack-a", model_id=10, version_id=100,
                            description="Old description A",
                            previews=[PreviewInfo(filename="p1.jpg", url="https://existing.com/1.jpg")])
        lock_a = _make_lock("pack-a", "main-checkpoint", model_id=10,
                            version_id=100, file_id=1000, sha256="a_old")

        civitai = {
            10: _civitai_model_response(
                model_id=10, version_id=200, file_id=2000, sha256="a_new",
                description="New description A",
                images=[
                    {"url": "https://existing.com/1.jpg"},  # Already have
                    {"url": "https://image.civitai.com/new.jpg"},  # New
                ],
            ),
        }

        packs = {"pack-a": pack_a}
        locks = {"pack-a": lock_a}
        service, _, _ = _setup_service(packs, locks, civitai)

        result = service.apply_batch(
            ["pack-a"], sync=False,
            options=UpdateOptions(merge_previews=True, update_description=True),
        )

        assert result.total_applied == 1
        pack_result = result.results["pack-a"]
        assert pack_result["applied"] is True
        assert pack_result["previews_merged"] == 1
        assert pack_result["description_updated"] is True
        assert pack_a.description == "New description A"
        assert len(pack_a.previews) == 2  # 1 existing + 1 new


# =============================================================================
# E2E: Civitai API Errors
# =============================================================================


class TestE2ECivitaiErrors:
    """Graceful handling when Civitai API fails during check/apply."""

    def test_civitai_unreachable_during_check(self):
        """If Civitai API fails, pack is skipped (not crashed)."""
        pack = _make_pack("my-pack", model_id=500)
        lock = _make_lock("my-pack", "main-checkpoint",
                          model_id=500, version_id=100, file_id=1000,
                          sha256="hash")

        mock_civitai = MagicMock()
        mock_civitai.get_model.side_effect = ConnectionError("Civitai is down")

        mock_layout = MagicMock()
        mock_layout.list_packs.return_value = ["my-pack"]
        mock_layout.load_pack.return_value = pack
        mock_layout.load_pack_lock.return_value = lock

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        # plan_update should return up-to-date (error is swallowed per dep)
        plan = service.plan_update("my-pack")
        assert plan.already_up_to_date is True
        assert len(plan.changes) == 0

    def test_check_all_skips_packs_with_civitai_errors(self):
        """check_all skips packs that error out, returns others."""
        pack_ok = _make_pack("ok-pack", model_id=10)
        lock_ok = _make_lock("ok-pack", "main-checkpoint",
                             model_id=10, version_id=100, file_id=1000,
                             sha256="hash")

        pack_fail = _make_pack("fail-pack", model_id=20)
        lock_fail = _make_lock("fail-pack", "main-checkpoint",
                               model_id=20, version_id=200, file_id=2000,
                               sha256="hash2")

        def get_model(model_id):
            if model_id == 10:
                return _civitai_model_response(
                    model_id=10, version_id=100, file_id=1000, sha256="hash",
                )
            raise ConnectionError("Timeout")

        mock_civitai = MagicMock()
        mock_civitai.get_model.side_effect = get_model

        mock_layout = MagicMock()
        mock_layout.list_packs.return_value = ["ok-pack", "fail-pack"]

        def load_pack(name):
            return {"ok-pack": pack_ok, "fail-pack": pack_fail}[name]

        def load_lock(name):
            return {"ok-pack": lock_ok, "fail-pack": lock_fail}[name]

        mock_layout.load_pack.side_effect = load_pack
        mock_layout.load_pack_lock.side_effect = load_lock

        service = UpdateService(
            layout=mock_layout, blob_store=MagicMock(),
            view_builder=MagicMock(), civitai_client=mock_civitai,
        )

        plans = service.check_all_updates()
        # ok-pack should be present (up-to-date)
        assert "ok-pack" in plans
        # fail-pack: Civitai error → the dep check fails → appears up-to-date
        # (error is caught per-dependency, so plan is returned with no changes)
        assert "fail-pack" in plans
        assert plans["fail-pack"].already_up_to_date is True
