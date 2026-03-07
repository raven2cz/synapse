"""
Resolve system DTOs — all data transfer objects for dependency resolution.

Based on PLAN-Resolve-Model.md v0.7.1 sections 2b, 2j, 11c.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .models import (
    AssetKind,
    CanonicalSource,
    CivitaiSelector,
    DependencySelector,
    HuggingFaceSelector,
    SelectorStrategy,
)

# --- Evidence source types ---

EvidenceSource = Literal[
    "hash_match",          # E1: SHA256 lookup (Tier 1)
    "preview_embedded",    # E2: PNG tEXt metadata (Tier 2)
    "preview_api_meta",    # E3: Civitai API sidecar meta (Tier 2)
    "source_metadata",     # E4: Civitai baseModel field (Tier 4)
    "file_metadata",       # E5: Filename patterns (Tier 3)
    "alias_config",        # E6: Configured aliases (Tier 3)
    "ai_analysis",         # E7: AI-assisted analysis (ceiling 0.89)
]


# --- Evidence items ---

class EvidenceItem(BaseModel):
    """A single piece of evidence from one source."""
    source: EvidenceSource
    description: str
    confidence: float  # 0.0 - 1.0, within tier bounds
    raw_value: Optional[str] = None


class EvidenceGroup(BaseModel):
    """Evidence items from the same provenance (e.g., one preview image).

    Within a group: combined_confidence = max(item.confidence).
    Between groups: Noisy-OR combination.
    """
    provenance: str  # "preview:001.png", "hash:sha256", "alias:SDXL"
    items: List[EvidenceItem] = Field(default_factory=list)
    combined_confidence: float = 0.0


# --- Candidate models ---

class CandidateSeed(BaseModel):
    """What an evidence provider found — a candidate with identification."""
    key: str  # Deduplication key: "civitai:model_id:version_id" or "local:/path"
    selector: DependencySelector
    canonical_source: Optional[CanonicalSource] = None
    display_name: str
    display_description: Optional[str] = None
    provider_name: Optional[Literal["civitai", "huggingface", "local", "url"]] = None


class EvidenceHit(BaseModel):
    """One finding = candidate + evidence why."""
    candidate: CandidateSeed
    provenance: str  # Which preview/hash/alias produced this
    item: EvidenceItem


class ResolutionCandidate(BaseModel):
    """A ranked candidate for dependency resolution."""
    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
    rank: int = 0
    confidence: float = Field(ge=0.0, le=1.0)
    tier: int = Field(ge=1, le=4)  # Confidence tier (1=highest, 4=lowest)
    strategy: SelectorStrategy
    selector_data: Dict[str, Any] = Field(default_factory=dict)
    canonical_source: Optional[CanonicalSource] = None
    evidence_groups: List[EvidenceGroup] = Field(default_factory=list)
    display_name: str = ""
    display_description: Optional[str] = None
    provider: Optional[Literal["civitai", "huggingface", "local", "url"]] = None
    compatibility_warnings: List[str] = Field(default_factory=list)


# --- Preview model hints ---

class PreviewModelHint(BaseModel):
    """A model reference extracted from a preview image's metadata."""
    filename: str              # "illustriousXL_v060.safetensors"
    kind: Optional[AssetKind] = None  # From ComfyUI node type
    source_image: str          # Which preview image
    source_type: Literal["api_meta", "png_embedded"]
    raw_value: str             # Raw value for debugging
    resolvable: bool = True    # False if private/unknown format


# --- Provider result ---

class ProviderResult(BaseModel):
    """Output of one evidence provider's gather() call."""
    hits: List[EvidenceHit] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


# --- Request/Response contracts ---

class SuggestOptions(BaseModel):
    """Options for suggest_resolution."""
    include_ai: bool = False       # Default OFF for import (R5)
    analyze_previews: bool = True
    max_candidates: int = 10


class SuggestResult(BaseModel):
    """Result of suggest — list of candidates + metadata."""
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    candidates: List[ResolutionCandidate] = Field(default_factory=list)
    pack_fingerprint: str = ""  # SHA hash of pack.json for stale detection
    warnings: List[str] = Field(default_factory=list)


class ApplyResult(BaseModel):
    """Result of apply — success/failure."""
    success: bool
    message: str = ""
    compatibility_warnings: List[str] = Field(default_factory=list)


class ManualResolveData(BaseModel):
    """Data from manual resolve (Civitai/HF/Local tab)."""
    strategy: SelectorStrategy
    civitai: Optional[CivitaiSelector] = None
    huggingface: Optional[HuggingFaceSelector] = None
    local_path: Optional[str] = None
    url: Optional[str] = None
    canonical_source: Optional[CanonicalSource] = None
    display_name: Optional[str] = None


# --- Resolve context (passed to providers) ---

class ResolveContext(BaseModel):
    """Context passed to evidence providers."""
    pack: Any  # Pack object
    dependency: Any  # PackDependency
    dep_id: str = ""
    kind: AssetKind = AssetKind.UNKNOWN
    preview_hints: List[PreviewModelHint] = Field(default_factory=list)
    layout: Any = None  # StoreLayout (for file-system access)

    class Config:
        arbitrary_types_allowed = True
