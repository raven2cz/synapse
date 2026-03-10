"""
Phase 5 deferred items tests — base_model propagation, AUTO_APPLY_MARGIN,
async hash, HF enrichment, HuggingFaceClient.search_models.
"""

import hashlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from src.store.models import (
    AssetKind, CivitaiSelector, DependencySelector,
    HuggingFaceSelector, SelectorStrategy, CanonicalSource,
)


# =============================================================================
# 5.1 candidate_base_model propagation
# =============================================================================

class TestCandidateBaseModel:
    """ResolutionCandidate and CandidateSeed should carry base_model."""

    def test_candidate_seed_has_base_model_field(self):
        from src.store.resolve_models import CandidateSeed
        seed = CandidateSeed(
            key="test:1:2",
            selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
            display_name="Test",
            base_model="SDXL",
        )
        assert seed.base_model == "SDXL"

    def test_candidate_seed_base_model_default_none(self):
        from src.store.resolve_models import CandidateSeed
        seed = CandidateSeed(
            key="test:1:2",
            selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
            display_name="Test",
        )
        assert seed.base_model is None

    def test_resolution_candidate_has_base_model_field(self):
        from src.store.resolve_models import ResolutionCandidate
        c = ResolutionCandidate(
            confidence=0.95,
            tier=1,
            strategy=SelectorStrategy.CIVITAI_FILE,
            display_name="Test",
            base_model="SD 1.5",
        )
        assert c.base_model == "SD 1.5"

    def test_resolution_candidate_serializes_base_model(self):
        from src.store.resolve_models import ResolutionCandidate
        c = ResolutionCandidate(
            confidence=0.9,
            tier=1,
            strategy=SelectorStrategy.CIVITAI_FILE,
            display_name="Test",
            base_model="Flux",
        )
        data = c.model_dump()
        assert data["base_model"] == "Flux"

    def test_hash_provider_extracts_base_model(self):
        """HashEvidenceProvider should extract baseModel from CivitaiModelVersion dataclass."""
        from src.store.evidence_providers import HashEvidenceProvider
        from src.store.resolve_models import ResolveContext

        # Mock pack_service with civitai client returning dataclass-like object
        mock_ps = MagicMock()
        mock_civitai = MagicMock()
        mock_version = MagicMock()
        mock_version.model_id = 123
        mock_version.id = 456
        mock_version.base_model = "SDXL"
        mock_version.name = "TestModel"
        mock_version.files = []
        mock_civitai.get_model_by_hash.return_value = mock_version
        mock_ps.civitai = mock_civitai

        provider = HashEvidenceProvider(pack_service_getter=lambda: mock_ps)

        # Create context with a dep that has SHA256 in lock
        mock_dep = MagicMock()
        mock_dep.lock = MagicMock()
        mock_dep.lock.sha256 = "abc123" * 10 + "abcd"

        ctx = ResolveContext(
            pack=MagicMock(),
            dependency=mock_dep,
            dep_id="test",
            kind=AssetKind.CHECKPOINT,
            preview_hints=[],
            layout=MagicMock(),
        )

        result = provider.gather(ctx)
        assert len(result.hits) == 1
        assert result.hits[0].candidate.base_model == "SDXL"
        assert result.hits[0].candidate.display_name == "TestModel"


# =============================================================================
# 5.2 AUTO_APPLY_MARGIN
# =============================================================================

class TestAutoApplyMargin:
    """AUTO_APPLY_MARGIN should be importable and used consistently."""

    def test_auto_apply_margin_is_float(self):
        from src.store.resolve_config import AUTO_APPLY_MARGIN
        assert isinstance(AUTO_APPLY_MARGIN, float)
        assert 0.0 < AUTO_APPLY_MARGIN < 1.0

    def test_auto_apply_margin_default(self):
        from src.store.resolve_config import AUTO_APPLY_MARGIN
        assert AUTO_APPLY_MARGIN == 0.15

    def test_post_import_resolve_uses_constant(self):
        """__init__.py should import AUTO_APPLY_MARGIN, not hardcode 0.15."""
        source = (Path(__file__).parent.parent.parent.parent / "src" / "store" / "__init__.py").read_text()
        assert "AUTO_APPLY_MARGIN" in source
        # The hardcoded 0.15 should not appear in margin comparison
        import re
        # Find lines with "margin >= " — should use AUTO_APPLY_MARGIN
        margin_checks = re.findall(r"margin >= (.+)", source)
        for check in margin_checks:
            assert "0.15" not in check, f"Found hardcoded 0.15 in margin check: {check}"


# =============================================================================
# 5.3 Async hash computation
# =============================================================================

class TestAsyncHash:
    """compute_sha256_async should work correctly."""

    def test_async_function_exists(self):
        from src.store.hash_cache import compute_sha256_async
        import inspect
        assert inspect.iscoroutinefunction(compute_sha256_async)

    @pytest.mark.asyncio
    async def test_async_hash_matches_sync(self, tmp_path):
        from src.store.hash_cache import compute_sha256, compute_sha256_async

        # Create test file
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"hello world" * 1000)

        sync_hash = compute_sha256(test_file)
        async_hash = await compute_sha256_async(test_file)

        assert sync_hash == async_hash

    @pytest.mark.asyncio
    async def test_async_hash_correct_value(self, tmp_path):
        from src.store.hash_cache import compute_sha256_async

        test_file = tmp_path / "test.bin"
        content = b"test content for hashing"
        test_file.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        actual = await compute_sha256_async(test_file)

        assert actual == expected


# =============================================================================
# 5.4 HF enrichment
# =============================================================================

class TestHFEnrichment:
    """HF enrichment functions in enrichment.py."""

    def test_enrich_by_hf_returns_none_without_client(self):
        from src.store.enrichment import enrich_by_hf
        assert enrich_by_hf("test_model", None) is None

    def test_enrich_by_hf_returns_none_for_short_stem(self):
        from src.store.enrichment import enrich_by_hf
        mock_hf = MagicMock()
        assert enrich_by_hf("ab", mock_hf) is None

    def test_enrich_by_hf_finds_matching_repo(self):
        from src.store.enrichment import enrich_by_hf

        mock_hf = MagicMock()
        mock_hf.search_models.return_value = [
            {
                "id": "stabilityai/juggernaut-xl",
                "tags": ["stable-diffusion-xl", "safetensors"],
                "pipeline_tag": "text-to-image",
            }
        ]
        mock_file = MagicMock()
        mock_file.filename = "juggernaut_xl.safetensors"
        mock_file.sha256 = "abc123"
        mock_repo = MagicMock()
        mock_repo.files = [mock_file]
        mock_hf.get_repo_files.return_value = mock_repo

        result = enrich_by_hf("juggernaut_xl", mock_hf)
        assert result is not None
        assert result.source == "huggingface"
        assert result.strategy == SelectorStrategy.HUGGINGFACE_FILE
        assert result.huggingface.repo_id == "stabilityai/juggernaut-xl"
        assert result.base_model == "SDXL"

    def test_enrich_by_hf_skips_non_matching_repos(self):
        from src.store.enrichment import enrich_by_hf

        mock_hf = MagicMock()
        mock_hf.search_models.return_value = [
            {"id": "completely/different-model", "tags": []}
        ]

        result = enrich_by_hf("juggernaut_xl", mock_hf)
        assert result is None

    def test_enrich_file_pipeline_with_hf_fallback(self):
        """enrich_file should try HF after Civitai fails."""
        from src.store.enrichment import enrich_file

        mock_civitai = MagicMock()
        mock_civitai.get_model_by_hash.return_value = None
        mock_civitai.search_meilisearch.return_value = {"items": []}

        mock_hf = MagicMock()
        mock_hf.search_models.return_value = [
            {"id": "user/test-model", "tags": ["flux"]}
        ]
        mock_hf.get_repo_files.return_value = MagicMock(files=[])

        # HF found repo but no files → should fall to filename_only
        result = enrich_file(
            sha256="a" * 64,
            filename="test_model.safetensors",
            civitai_client=mock_civitai,
            hf_client=mock_hf,
        )
        # HF returned but no matching files → still enriches from repo
        # (get_repo_files returns empty files list → enrich_by_hf falls through)
        assert result.source in ("huggingface", "filename_only")

    def test_enrich_file_without_hf_client_works(self):
        """enrich_file should work without hf_client (backward compat)."""
        from src.store.enrichment import enrich_file

        mock_civitai = MagicMock()
        mock_civitai.get_model_by_hash.return_value = None
        mock_civitai.search_meilisearch.return_value = {"items": []}

        result = enrich_file(
            sha256="a" * 64,
            filename="test_model.safetensors",
            civitai_client=mock_civitai,
        )
        assert result.source == "filename_only"


# =============================================================================
# 5.5 HuggingFaceClient.search_models
# =============================================================================

class TestHuggingFaceClientSearch:
    """HuggingFaceClient.search_models() method."""

    def test_search_models_method_exists(self):
        from src.clients.huggingface_client import HuggingFaceClient
        client = HuggingFaceClient()
        assert hasattr(client, "search_models")
        assert callable(client.search_models)

    def test_search_models_returns_list(self):
        from src.clients.huggingface_client import HuggingFaceClient

        client = HuggingFaceClient()
        with patch.object(client.session, "get") as mock_get:
            mock_get.return_value.raise_for_status = MagicMock()
            mock_get.return_value.json.return_value = [
                {"id": "test/model", "tags": ["sdxl"]}
            ]

            results = client.search_models("test")
            assert isinstance(results, list)
            assert len(results) == 1

    def test_search_models_handles_error(self):
        from src.clients.huggingface_client import HuggingFaceClient

        client = HuggingFaceClient()
        with patch.object(client.session, "get", side_effect=Exception("timeout")):
            results = client.search_models("test")
            assert results == []

    def test_search_models_caps_limit(self):
        from src.clients.huggingface_client import HuggingFaceClient

        client = HuggingFaceClient()
        with patch.object(client.session, "get") as mock_get:
            mock_get.return_value.raise_for_status = MagicMock()
            mock_get.return_value.json.return_value = []

            client.search_models("test", limit=100)
            call_args = mock_get.call_args
            assert call_args[1]["params"]["limit"] == 20  # capped

    def test_hf_file_info_extracts_lfs_oid(self):
        """HFFileInfo should extract SHA256 from lfs.oid field."""
        from src.clients.huggingface_client import HFFileInfo

        # Real HF tree API response format
        data = {
            "path": "model.safetensors",
            "size": 1234567,
            "lfs": {
                "oid": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "size": 1234567,
            },
            "type": "file",
        }
        info = HFFileInfo.from_api_response(data)
        assert info.sha256 == "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        assert info.lfs is True

    def test_hf_file_info_no_lfs(self):
        """Non-LFS files should have sha256=None."""
        from src.clients.huggingface_client import HFFileInfo

        data = {"path": "README.md", "size": 100, "type": "file"}
        info = HFFileInfo.from_api_response(data)
        assert info.sha256 is None
        assert info.lfs is False


# =============================================================================
# 5.6 search_huggingface MCP base_model detection
# =============================================================================

class TestMCPBaseModelDetection:
    """search_huggingface MCP tool should detect base_model from tags."""

    def test_extract_base_model_from_tags(self):
        """Verify base model tag detection logic."""
        from src.store.enrichment import _extract_hf_base_model

        assert _extract_hf_base_model({"tags": ["stable-diffusion-xl"]}) == "SDXL"
        assert _extract_hf_base_model({"tags": ["sdxl", "lora"]}) == "SDXL"
        assert _extract_hf_base_model({"tags": ["stable-diffusion"]}) == "SD 1.5"
        assert _extract_hf_base_model({"tags": ["flux"]}) == "Flux"
        assert _extract_hf_base_model({"tags": ["pony"]}) == "Pony"
        assert _extract_hf_base_model({"tags": ["sd-3.5"]}) == "SD 3.5"
        assert _extract_hf_base_model({"tags": ["unknown-tag"]}) is None
        assert _extract_hf_base_model({"tags": []}) is None

    def test_shared_base_model_tags_constant(self):
        """HF_BASE_MODEL_TAGS should be importable as shared constant."""
        from src.store.enrichment import HF_BASE_MODEL_TAGS
        assert isinstance(HF_BASE_MODEL_TAGS, dict)
        assert "sdxl" in HF_BASE_MODEL_TAGS
        assert "sd-3.5" in HF_BASE_MODEL_TAGS

    def test_enrich_by_hf_limits_repo_checks(self):
        """enrich_by_hf should check at most 2 repos to avoid excessive network calls."""
        from src.store.enrichment import enrich_by_hf

        mock_hf = MagicMock()
        # Return 5 results, all with matching names
        mock_hf.search_models.return_value = [
            {"id": f"user/juggernaut-xl-{i}", "tags": ["sdxl"]}
            for i in range(5)
        ]
        # get_repo_files raises for all — tracks how many times called
        mock_hf.get_repo_files.side_effect = Exception("timeout")

        enrich_by_hf("juggernaut xl", mock_hf)
        # Should only check at most 2 repos (not all 5)
        assert mock_hf.get_repo_files.call_count <= 2
