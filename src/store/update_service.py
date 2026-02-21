"""
Synapse Store v2 - Update Service

Orchestrates update operations for packs. Provider-specific logic
(version checking, URL construction, metadata sync) is delegated
to UpdateProvider implementations registered by SelectorStrategy.

The service itself is provider-agnostic — it handles planning,
lock file updates, batch operations, and post-update sync.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .blob_store import BlobStore
from .layout import StoreLayout

logger = logging.getLogger(__name__)
from .models import (
    AmbiguousUpdate,
    ArtifactDownload,
    ArtifactIntegrity,
    ArtifactProvider,
    BatchUpdateResult,
    Pack,
    PackLock,
    PendingDownload,
    ProviderName,
    ResolvedArtifact,
    ResolvedDependency,
    SelectorStrategy,
    UpdateChange,
    UpdateOptions,
    UpdatePlan,
    UpdatePolicyMode,
    UpdateResult,
)
from .update_provider import UpdateCheckResult, UpdateProvider
from .view_builder import ViewBuilder


# Strategies that support automatic updates (follow_latest policy)
UPDATABLE_STRATEGIES = frozenset({
    SelectorStrategy.CIVITAI_MODEL_LATEST,
    # Future: SelectorStrategy.HUGGINGFACE_LATEST, etc.
})


class UpdateError(Exception):
    """Base exception for update errors."""
    pass


class AmbiguousSelectionError(UpdateError):
    """Error when update requires explicit file selection."""

    def __init__(self, pack: str, ambiguous: List[AmbiguousUpdate]):
        self.pack = pack
        self.ambiguous = ambiguous
        super().__init__(f"Update for {pack} requires file selection")


class UpdateService:
    """
    Service for managing pack updates.

    Provider-agnostic orchestrator that delegates provider-specific
    operations to registered UpdateProvider implementations.
    """

    def __init__(
        self,
        layout: StoreLayout,
        blob_store: BlobStore,
        view_builder: ViewBuilder,
        providers: Optional[Dict[SelectorStrategy, UpdateProvider]] = None,
    ):
        """
        Initialize update service.

        Args:
            layout: Store layout manager
            blob_store: Blob store
            view_builder: View builder
            providers: Registry mapping SelectorStrategy -> UpdateProvider
        """
        self.layout = layout
        self.blob_store = blob_store
        self.view_builder = view_builder
        self._providers: Dict[SelectorStrategy, UpdateProvider] = providers or {}

    def register_provider(self, strategy: SelectorStrategy, provider: UpdateProvider) -> None:
        """Register an update provider for a selector strategy."""
        self._providers[strategy] = provider

    def _get_provider(self, strategy: SelectorStrategy) -> Optional[UpdateProvider]:
        """Get the provider for a given selector strategy."""
        return self._providers.get(strategy)

    # =========================================================================
    # Update Planning
    # =========================================================================

    def is_updatable(self, pack: Pack) -> bool:
        """
        Check if a pack has any updatable dependencies.

        A pack is updatable if it has at least one dependency with:
        - A registered provider for its selector strategy
        - update_policy.mode = follow_latest
        """
        for dep in pack.dependencies:
            if (dep.update_policy.mode == UpdatePolicyMode.FOLLOW_LATEST and
                    dep.selector.strategy in self._providers):
                return True
        return False

    def plan_update(self, pack_name: str) -> UpdatePlan:
        """
        Create an update plan for a pack.

        Checks each updatable dependency for new versions by delegating
        to the appropriate provider.

        Args:
            pack_name: Pack to check for updates

        Returns:
            UpdatePlan with changes and ambiguous selections
        """
        pack = self.layout.load_pack(pack_name)
        lock = self.layout.load_pack_lock(pack_name)

        if not lock:
            return UpdatePlan(
                pack=pack_name,
                already_up_to_date=False,
                changes=[],
                ambiguous=[],
                impacted_packs=self._find_reverse_dependencies(pack_name),
            )

        changes = []
        ambiguous = []
        lock_modified = False

        for dep in pack.dependencies:
            # Skip non-updatable dependencies
            if dep.update_policy.mode != UpdatePolicyMode.FOLLOW_LATEST:
                continue

            # Find provider for this strategy
            provider = self._get_provider(dep.selector.strategy)
            if not provider:
                continue

            # Get current lock entry
            current = lock.get_resolved(dep.id)
            if not current:
                continue

            # Check for updates via provider
            try:
                result = provider.check_update(dep, current)
                if result is None:
                    continue

                if result.ambiguous:
                    ambiguous.append(AmbiguousUpdate(
                        dependency_id=dep.id,
                        candidates=result.candidates,
                    ))
                elif result.has_update:
                    changes.append(UpdateChange(
                        dependency_id=dep.id,
                        old={
                            "provider": current.artifact.provider.name.value
                                if hasattr(current.artifact.provider.name, 'value')
                                else str(current.artifact.provider.name),
                            "provider_model_id": current.artifact.provider.model_id,
                            "provider_version_id": current.artifact.provider.version_id,
                            "provider_file_id": current.artifact.provider.file_id,
                            "sha256": current.artifact.sha256,
                        },
                        new={
                            "provider": current.artifact.provider.name.value
                                if hasattr(current.artifact.provider.name, 'value')
                                else str(current.artifact.provider.name),
                            "provider_model_id": result.model_id,
                            "provider_version_id": result.version_id,
                            "provider_file_id": result.file_id,
                            "sha256": result.sha256,
                            "download_url": result.download_url,
                            "filename": result.filename,
                            "size_bytes": result.size_bytes,
                        },
                    ))
                else:
                    # Self-heal: fill missing filename in lock from check result
                    if result.filename and not current.artifact.provider.filename:
                        current.artifact.provider.filename = result.filename
                        lock_modified = True
            except Exception as e:
                logger.warning("Failed to check updates for %s dep %s: %s", pack_name, dep.id, e)

        # Check for pending downloads (lock updated but blob not on disk)
        # Uses lock metadata only — NO API calls (those were already made above)
        pending_downloads = []
        for dep in pack.dependencies:
            resolved = lock.get_resolved(dep.id)
            if resolved and resolved.artifact.sha256:
                if not self.blob_store.blob_exists(resolved.artifact.sha256):
                    # Get download URL from lock (set during apply_update)
                    urls = resolved.artifact.download.urls if resolved.artifact.download else []
                    download_url = urls[0] if urls else ""
                    # Fallback: build URL from lock provider metadata
                    if not download_url:
                        prov = self._get_provider(dep.selector.strategy)
                        if prov:
                            download_url = prov.build_download_url(
                                resolved.artifact.provider.version_id,
                                resolved.artifact.provider.file_id,
                            )
                    pending_downloads.append(PendingDownload(
                        dependency_id=dep.id,
                        sha256=resolved.artifact.sha256,
                        download_url=download_url,
                        size_bytes=resolved.artifact.size_bytes,
                    ))

        already_up_to_date = (
            len(changes) == 0
            and len(ambiguous) == 0
            and len(pending_downloads) == 0
        )

        # Persist self-healed filename metadata in lock
        if lock_modified:
            self.layout.save_pack_lock(lock)

        # Scan for reverse dependencies (which packs depend on this one)
        impacted_packs = self._find_reverse_dependencies(pack_name)

        return UpdatePlan(
            pack=pack_name,
            already_up_to_date=already_up_to_date,
            changes=changes,
            ambiguous=ambiguous,
            pending_downloads=pending_downloads,
            impacted_packs=impacted_packs,
        )

    def _find_reverse_dependencies(self, pack_name: str) -> List[str]:
        """
        Find all packs that depend on the given pack via pack_dependencies.

        Returns:
            List of pack names that have pack_name in their pack_dependencies.
        """
        reverse_deps = []
        for other_name in self.layout.list_packs():
            if other_name == pack_name:
                continue
            try:
                other_pack = self.layout.load_pack(other_name)
                dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
                if pack_name in dep_names:
                    reverse_deps.append(other_name)
            except Exception:
                continue
        return sorted(reverse_deps)

    # =========================================================================
    # Update Application
    # =========================================================================

    def apply_update(
        self,
        pack_name: str,
        plan: UpdatePlan,
        choose: Optional[Dict[str, int]] = None,
    ) -> PackLock:
        """
        Apply an update plan to a pack.

        Uses the appropriate provider to build download URLs.

        Args:
            pack_name: Pack to update
            plan: Update plan from plan_update()
            choose: Optional dict mapping dep_id -> file_id for ambiguous selections

        Returns:
            Updated PackLock

        Raises:
            AmbiguousSelectionError: If plan has ambiguous entries without choose
        """
        # Handle ambiguous updates: auto-select first candidate when no choice provided
        if plan.ambiguous:
            if choose is None:
                choose = {}
            for amb in plan.ambiguous:
                if amb.dependency_id not in choose:
                    if amb.candidates:
                        auto_file_id = amb.candidates[0].provider_file_id
                        choose[amb.dependency_id] = auto_file_id
                        logger.warning(
                            "[UpdateService] Auto-selected file_id=%s for ambiguous "
                            "dependency %s (pack=%s, %d candidates)",
                            auto_file_id, amb.dependency_id, pack_name,
                            len(amb.candidates),
                        )

        # Load current lock and pack
        lock = self.layout.load_pack_lock(pack_name)
        if not lock:
            raise UpdateError(f"No lock file for pack: {pack_name}")

        pack = self.layout.load_pack(pack_name)

        # Apply changes
        for change in plan.changes:
            dep_id = change.dependency_id
            new_data = change.new

            # Find the provider for this dependency
            dep = pack.get_dependency(dep_id)
            provider = self._get_provider(dep.selector.strategy) if dep else None

            # Get download URL - prefer URL from check result, fallback to building
            version_id = new_data.get("provider_version_id")
            file_id = new_data.get("provider_file_id")
            if not provider:
                logger.warning("No provider for dependency %s (strategy=%s), skipping",
                              dep_id, dep.selector.strategy if dep else "unknown")
                continue
            download_url = new_data.get("download_url") or provider.build_download_url(version_id, file_id)

            # Resolve provider name from current lock entry
            provider_name = self._resolve_provider_name(new_data.get("provider"))

            # Find and update resolved entry
            found = False
            for i, resolved in enumerate(lock.resolved):
                if resolved.dependency_id == dep_id:
                    lock.resolved[i] = ResolvedDependency(
                        dependency_id=dep_id,
                        artifact=ResolvedArtifact(
                            kind=resolved.artifact.kind,
                            sha256=new_data.get("sha256"),
                            size_bytes=new_data.get("size_bytes") or resolved.artifact.size_bytes,
                            provider=ArtifactProvider(
                                name=provider_name,
                                model_id=new_data.get("provider_model_id"),
                                version_id=version_id,
                                file_id=file_id,
                                filename=new_data.get("filename") or resolved.artifact.provider.filename,
                            ),
                            download=ArtifactDownload(urls=[download_url]),
                            integrity=ArtifactIntegrity(sha256_verified=new_data.get("sha256") is not None),
                        ),
                    )
                    found = True
                    break
            if not found:
                logger.warning("Dependency %s not found in lock for pack %s, skipping", dep_id, pack_name)

        # Apply ambiguous selections
        if choose:
            for amb in plan.ambiguous:
                if amb.dependency_id in choose:
                    selected_file_id = choose[amb.dependency_id]

                    # Find the selected candidate
                    selected = None
                    for cand in amb.candidates:
                        if cand.provider_file_id == selected_file_id:
                            selected = cand
                            break

                    if selected:
                        # Find provider for this dependency
                        dep = pack.get_dependency(amb.dependency_id)
                        provider = self._get_provider(dep.selector.strategy) if dep else None

                        if not provider:
                            logger.warning("No provider for dependency %s, skipping ambiguous selection",
                                          amb.dependency_id)
                            continue
                        download_url = provider.build_download_url(
                            selected.provider_version_id,
                            selected.provider_file_id,
                        )

                        provider_name = self._resolve_provider_name(selected.provider)

                        # Find and update resolved entry
                        for i, resolved in enumerate(lock.resolved):
                            if resolved.dependency_id == amb.dependency_id:
                                lock.resolved[i] = ResolvedDependency(
                                    dependency_id=amb.dependency_id,
                                    artifact=ResolvedArtifact(
                                        kind=dep.kind if dep else resolved.artifact.kind,
                                        sha256=selected.sha256,
                                        size_bytes=selected.size_bytes or resolved.artifact.size_bytes,
                                        provider=ArtifactProvider(
                                            name=provider_name,
                                            model_id=selected.provider_model_id,
                                            version_id=selected.provider_version_id,
                                            file_id=selected.provider_file_id,
                                            filename=selected.filename or resolved.artifact.provider.filename,
                                        ),
                                        download=ArtifactDownload(urls=[download_url]),
                                        integrity=ArtifactIntegrity(sha256_verified=selected.sha256 is not None),
                                    ),
                                )
                                break

        # Update timestamp
        lock.resolved_at = datetime.now().isoformat()

        # Save updated lock
        self.layout.save_pack_lock(lock)

        return lock

    @staticmethod
    def _resolve_provider_name(provider_str: Optional[str]) -> ProviderName:
        """Resolve a provider string to ProviderName enum."""
        if not provider_str:
            return ProviderName.CIVITAI
        try:
            return ProviderName(provider_str)
        except ValueError:
            return ProviderName.CIVITAI

    # =========================================================================
    # High-Level Update Command
    # =========================================================================

    def update_pack(
        self,
        pack_name: str,
        dry_run: bool = False,
        choose: Optional[Dict[str, int]] = None,
        sync: bool = False,
        ui_targets: Optional[List[str]] = None,
        options: Optional[UpdateOptions] = None,
    ) -> UpdateResult:
        """
        High-level update command.

        Args:
            pack_name: Pack to update
            dry_run: If True, only plan without applying
            choose: Optional file selections for ambiguous updates
            sync: If True, download new blobs and rebuild views
            ui_targets: UI targets for sync (required if sync=True)
            options: Optional update options (merge previews, etc.)

        Returns:
            UpdateResult with details
        """
        # Create plan
        plan = self.plan_update(pack_name)

        if plan.already_up_to_date:
            return UpdateResult(
                pack=pack_name,
                applied=False,
                lock_updated=False,
                synced=False,
                ui_targets=[],
                already_up_to_date=True,
            )

        if dry_run:
            return UpdateResult(
                pack=pack_name,
                applied=False,
                lock_updated=False,
                synced=False,
                ui_targets=[],
                already_up_to_date=False,
            )

        # Apply update
        lock = self.apply_update(pack_name, plan, choose)

        result = UpdateResult(
            pack=pack_name,
            applied=True,
            lock_updated=True,
            synced=False,
            ui_targets=ui_targets or [],
        )

        # Apply options (merge previews, update description, etc.)
        if options:
            self._apply_options(pack_name, options, result)

        # Sync if requested
        if sync and ui_targets:
            result.synced = self._sync_after_update(pack_name, lock, ui_targets)

        return result

    def _apply_options(
        self,
        pack_name: str,
        options: UpdateOptions,
        result: UpdateResult,
    ) -> None:
        """Apply update options by delegating to the pack's provider."""
        pack = self.layout.load_pack(pack_name)
        provider = self._get_provider_for_pack(pack)
        if not provider:
            return

        changed = False

        if options.merge_previews:
            merged_count = provider.merge_previews(pack)
            result.previews_merged = merged_count
            if merged_count > 0:
                changed = True

        if options.update_description:
            updated = provider.update_description(pack)
            result.description_updated = updated
            if updated:
                changed = True

        if options.update_model_info:
            updated = provider.update_model_info(pack)
            result.model_info_updated = updated
            if updated:
                changed = True

        if changed:
            self.layout.save_pack(pack)

    def _get_provider_for_pack(self, pack: Pack) -> Optional[UpdateProvider]:
        """Find the appropriate provider for a pack based on its dependencies."""
        for dep in pack.dependencies:
            provider = self._get_provider(dep.selector.strategy)
            if provider:
                return provider
        return None

    def apply_batch(
        self,
        pack_names: List[str],
        choose: Optional[Dict[str, Dict[str, int]]] = None,
        sync: bool = False,
        ui_targets: Optional[List[str]] = None,
        options: Optional[UpdateOptions] = None,
    ) -> BatchUpdateResult:
        """
        Apply updates to multiple packs.

        Args:
            pack_names: List of packs to update
            choose: Optional nested dict: pack_name -> dep_id -> file_id
            sync: If True, download blobs and rebuild views
            ui_targets: UI targets for sync
            options: Optional update options

        Returns:
            BatchUpdateResult with per-pack results
        """
        batch_result = BatchUpdateResult()

        for pack_name in pack_names:
            try:
                pack_choose = choose.get(pack_name) if choose else None
                result = self.update_pack(
                    pack_name,
                    choose=pack_choose,
                    sync=sync,
                    ui_targets=ui_targets,
                    options=options,
                )
                batch_result.results[pack_name] = result.model_dump()
                if result.applied:
                    batch_result.total_applied += 1
                elif result.already_up_to_date:
                    batch_result.total_skipped += 1
            except Exception as e:
                batch_result.results[pack_name] = {
                    "error": str(e),
                    "applied": False,
                }
                batch_result.total_failed += 1

        return batch_result

    def _sync_after_update(
        self,
        pack_name: str,
        lock: PackLock,
        ui_targets: List[str],
    ) -> bool:
        """Download new blobs and rebuild views after update."""
        try:
            # Download new blobs
            for resolved in lock.resolved:
                sha256 = resolved.artifact.sha256
                urls = resolved.artifact.download.urls

                if sha256 and not self.blob_store.blob_exists(sha256) and urls and len(urls) > 0:
                    try:
                        self.blob_store.download(urls[0], sha256)
                    except Exception as e:
                        logger.warning("Failed to download blob %s: %s", sha256[:12], e)

            # Rebuild views for each UI
            runtime = self.layout.load_runtime()

            for ui in ui_targets:
                active_profile = runtime.get_active_profile(ui)
                if active_profile:
                    try:
                        profile = self.layout.load_profile(active_profile)
                        # Load packs for profile
                        packs_data = {}
                        for p in profile.packs:
                            try:
                                pack = self.layout.load_pack(p.name)
                                pack_lock = self.layout.load_pack_lock(p.name)
                                packs_data[p.name] = (pack, pack_lock)
                            except Exception:
                                continue

                        self.view_builder.build(ui, profile, packs_data)
                        self.view_builder.activate(ui, active_profile)
                    except Exception as e:
                        logger.warning("Failed to rebuild views for UI %s: %s", ui, e)

            return True
        except Exception:
            return False

    # =========================================================================
    # Batch Operations
    # =========================================================================

    def check_all_updates(self) -> Dict[str, UpdatePlan]:
        """
        Check for updates on all packs.

        Clears provider model caches before and after the check loop
        to avoid stale data while deduplicating API calls within a session.

        Returns:
            Dict mapping pack_name -> UpdatePlan
        """
        # Clear provider caches before check-all session
        for provider in self._providers.values():
            if hasattr(provider, "clear_cache"):
                provider.clear_cache()

        plans = {}

        for pack_name in self.layout.list_packs():
            try:
                pack = self.layout.load_pack(pack_name)
                if self.is_updatable(pack):
                    plans[pack_name] = self.plan_update(pack_name)
            except Exception as e:
                logger.debug("Skipping pack %s during update check: %s", pack_name, e)

        # Clear caches after session to free memory
        for provider in self._providers.values():
            if hasattr(provider, "clear_cache"):
                provider.clear_cache()

        return plans

    def get_updatable_packs(self) -> List[str]:
        """
        Get list of packs that have updates available.

        Returns:
            List of pack names with available updates
        """
        updatable = []

        plans = self.check_all_updates()
        for pack_name, plan in plans.items():
            if not plan.already_up_to_date:
                updatable.append(pack_name)

        return updatable
