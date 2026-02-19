"""
Synapse Store v2 - Update Provider Protocol

Defines the interface that all update providers must implement.
Each provider (Civitai, HuggingFace, etc.) implements this protocol
to handle version checking, download URL construction, and metadata sync.

The UpdateService uses providers via a registry keyed by SelectorStrategy,
keeping provider-specific logic fully encapsulated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .models import (
    Pack,
    PackDependency,
    ResolvedDependency,
    SelectorConstraints,
    UpdateCandidate,
)


@dataclass
class UpdateCheckResult:
    """
    Standardized result from a provider's update check.

    Returned by UpdateProvider.check_update() regardless of provider.
    """

    has_update: bool
    """Whether a newer version is available."""

    ambiguous: bool = False
    """Whether the update requires user selection (multiple file candidates)."""

    candidates: List[UpdateCandidate] = field(default_factory=list)
    """File candidates when ambiguous=True."""

    # Non-ambiguous update details:
    model_id: Optional[int] = None
    version_id: Optional[int] = None
    file_id: Optional[int] = None
    sha256: Optional[str] = None
    download_url: Optional[str] = None
    size_bytes: Optional[int] = None


@runtime_checkable
class UpdateProvider(Protocol):
    """
    Protocol for provider-specific update logic.

    Each provider (Civitai, HuggingFace, etc.) implements this interface.
    The UpdateService dispatches to the appropriate provider based on
    the dependency's selector.strategy.
    """

    def check_update(
        self,
        dep: PackDependency,
        current: ResolvedDependency,
    ) -> Optional[UpdateCheckResult]:
        """
        Check if a dependency has an update available.

        Args:
            dep: The pack dependency definition (selector, constraints, etc.)
            current: The currently resolved dependency from the lock file

        Returns:
            UpdateCheckResult if check succeeded, None if dependency
            cannot be checked by this provider.
        """
        ...

    def build_download_url(
        self,
        version_id: Optional[int],
        file_id: Optional[int],
    ) -> str:
        """
        Build a download URL for a specific version/file.

        Args:
            version_id: Provider-specific version identifier
            file_id: Provider-specific file identifier

        Returns:
            Full download URL string
        """
        ...

    def merge_previews(self, pack: Pack) -> int:
        """
        Merge new preview images/videos from the provider into the pack.

        Deduplicates against existing previews.

        Args:
            pack: Pack to merge previews into (modified in-place)

        Returns:
            Number of new previews added
        """
        ...

    def update_description(self, pack: Pack) -> bool:
        """
        Update the pack description from the provider.

        Args:
            pack: Pack to update (modified in-place)

        Returns:
            True if description was changed
        """
        ...

    def update_model_info(self, pack: Pack) -> bool:
        """
        Sync model info (base model, trigger words, etc.) from the provider.

        Args:
            pack: Pack to update (modified in-place)

        Returns:
            True if any info was changed
        """
        ...
