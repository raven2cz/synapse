"""
Tests for evidence_providers.py — 6 evidence providers for dependency resolution.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.store.models import AssetKind, DependencySelector, SelectorStrategy
from src.store.resolve_models import (
    EvidenceHit,
    PreviewModelHint,
    ProviderResult,
    ResolveContext,
)
from src.store.evidence_providers import (
    AIEvidenceProvider,
    AliasEvidenceProvider,
    EvidenceProvider,
    FileMetaEvidenceProvider,
    HashEvidenceProvider,
    PreviewMetaEvidenceProvider,
    SourceMetaEvidenceProvider,
    _extract_stem,
    _hf_hash_lookup,
)


def _make_context(**kwargs) -> ResolveContext:
    """Create a minimal ResolveContext for testing."""
    defaults = {
        "pack": MagicMock(name="test_pack"),
        "dependency": MagicMock(name="test_dep"),
        "dep_id": "dep_001",
        "kind": AssetKind.CHECKPOINT,
    }
    defaults.update(kwargs)
    return ResolveContext(**defaults)


class TestEvidenceProviderProtocol:
    def test_hash_is_provider(self):
        p = HashEvidenceProvider(lambda: None)
        assert isinstance(p, EvidenceProvider)

    def test_preview_is_provider(self):
        p = PreviewMetaEvidenceProvider()
        assert isinstance(p, EvidenceProvider)

    def test_file_meta_is_provider(self):
        p = FileMetaEvidenceProvider()
        assert isinstance(p, EvidenceProvider)

    def test_alias_is_provider(self):
        p = AliasEvidenceProvider(lambda: None)
        assert isinstance(p, EvidenceProvider)

    def test_source_meta_is_provider(self):
        p = SourceMetaEvidenceProvider()
        assert isinstance(p, EvidenceProvider)

    def test_ai_is_provider(self):
        p = AIEvidenceProvider(lambda: None)
        assert isinstance(p, EvidenceProvider)


class TestHashEvidenceProvider:
    def test_tier_is_1(self):
        assert HashEvidenceProvider(lambda: None).tier == 1

    def test_supports_always_true(self):
        p = HashEvidenceProvider(lambda: None)
        ctx = _make_context()
        assert p.supports(ctx) is True

    def test_no_sha256_returns_empty(self):
        dep = MagicMock()
        dep.lock = None
        p = HashEvidenceProvider(lambda: None)
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)
        assert result.hits == []

    def test_hash_match_returns_hit(self):
        dep = MagicMock()
        dep.lock = MagicMock()
        dep.lock.sha256 = "abc123def456"

        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = {
            "modelId": 100,
            "id": 200,
            "model": {"name": "Test Model"},
            "files": [{"id": 300, "hashes": {"SHA256": "abc123def456"}}],
        }

        ps = MagicMock()
        ps.civitai = civitai

        p = HashEvidenceProvider(lambda: ps)
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].item.source == "hash_match"
        assert result.hits[0].item.confidence == 0.95
        assert result.hits[0].candidate.key == "civitai:100:200"

    def test_civitai_lookup_failure_warns(self):
        dep = MagicMock()
        dep.lock = MagicMock()
        dep.lock.sha256 = "abc123"

        civitai = MagicMock()
        civitai.get_model_by_hash.side_effect = Exception("API error")

        ps = MagicMock()
        ps.civitai = civitai

        p = HashEvidenceProvider(lambda: ps)
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)

        assert result.hits == []
        assert len(result.warnings) == 1
        assert "API error" in result.warnings[0]

    def test_hf_hash_match_returns_hit(self):
        """HF LFS SHA256 match → TIER-1 hit."""
        from src.store.models import HuggingFaceSelector

        dep = MagicMock()
        dep.lock = MagicMock()
        dep.lock.sha256 = "aabbccdd1122"
        dep.selector = MagicMock()
        dep.selector.huggingface = HuggingFaceSelector(
            repo_id="org/model", filename="model.safetensors",
        )

        hf_file = MagicMock()
        hf_file.filename = "model.safetensors"
        hf_file.sha256 = "aabbccdd1122"

        hf_client = MagicMock()
        hf_client.get_repo_files.return_value = MagicMock(files=[hf_file])

        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = None

        ps = MagicMock()
        ps.civitai = civitai
        ps.huggingface = hf_client

        p = HashEvidenceProvider(lambda: ps)
        ctx = _make_context(dependency=dep, kind=AssetKind.CHECKPOINT)
        result = p.gather(ctx)

        hf_hits = [h for h in result.hits if h.candidate.provider_name == "huggingface"]
        assert len(hf_hits) == 1
        assert hf_hits[0].item.source == "hash_match"
        assert hf_hits[0].item.confidence == 0.95
        assert hf_hits[0].candidate.key == "hf:org/model:model.safetensors"
        assert hf_hits[0].candidate.selector.strategy == SelectorStrategy.HUGGINGFACE_FILE

    def test_hf_hash_no_match_returns_empty(self):
        """HF LFS SHA256 doesn't match → no HF hit."""
        from src.store.models import HuggingFaceSelector

        dep = MagicMock()
        dep.lock = MagicMock()
        dep.lock.sha256 = "aabbccdd1122"
        dep.selector = MagicMock()
        dep.selector.huggingface = HuggingFaceSelector(
            repo_id="org/model", filename="model.safetensors",
        )

        hf_file = MagicMock()
        hf_file.filename = "model.safetensors"
        hf_file.sha256 = "different_hash"

        hf_client = MagicMock()
        hf_client.get_repo_files.return_value = MagicMock(files=[hf_file])

        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = None

        ps = MagicMock()
        ps.civitai = civitai
        ps.huggingface = hf_client

        p = HashEvidenceProvider(lambda: ps)
        ctx = _make_context(dependency=dep, kind=AssetKind.CHECKPOINT)
        result = p.gather(ctx)

        # Only Civitai was checked (no match), HF hash didn't match
        hf_hits = [h for h in result.hits if h.candidate.provider_name == "huggingface"]
        assert len(hf_hits) == 0

    def test_hf_hash_skipped_for_non_eligible_kind(self):
        """HF hash lookup skipped for kinds like LORA."""
        from src.store.models import HuggingFaceSelector

        dep = MagicMock()
        dep.lock = MagicMock()
        dep.lock.sha256 = "aabbccdd1122"
        dep.selector = MagicMock()
        dep.selector.huggingface = HuggingFaceSelector(
            repo_id="org/lora", filename="lora.safetensors",
        )

        hf_client = MagicMock()
        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = None

        ps = MagicMock()
        ps.civitai = civitai
        ps.huggingface = hf_client

        p = HashEvidenceProvider(lambda: ps)
        ctx = _make_context(dependency=dep, kind=AssetKind.LORA)
        p.gather(ctx)

        # HF client should NOT be called for LORA
        hf_client.get_repo_files.assert_not_called()

    def test_hf_hash_no_selector_skips(self):
        """No HF selector on dep → skip HF lookup."""
        dep = MagicMock()
        dep.lock = MagicMock()
        dep.lock.sha256 = "aabbccdd1122"
        dep.selector = MagicMock()
        dep.selector.huggingface = None

        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = None

        ps = MagicMock()
        ps.civitai = civitai

        p = HashEvidenceProvider(lambda: ps)
        ctx = _make_context(dependency=dep, kind=AssetKind.CHECKPOINT)
        result = p.gather(ctx)

        hf_hits = [h for h in result.hits if
                   getattr(h.candidate, 'provider_name', None) == "huggingface"]
        assert len(hf_hits) == 0


class TestPreviewMetaEvidenceProvider:
    def test_tier_is_2(self):
        assert PreviewMetaEvidenceProvider().tier == 2

    def test_supports_with_hints(self):
        p = PreviewMetaEvidenceProvider()
        hint = PreviewModelHint(
            filename="model.safetensors", source_image="001.png",
            source_type="api_meta", raw_value="model",
        )
        ctx = _make_context(preview_hints=[hint])
        assert p.supports(ctx) is True

    def test_supports_without_hints(self):
        p = PreviewMetaEvidenceProvider()
        ctx = _make_context(preview_hints=[])
        assert p.supports(ctx) is False

    def test_gather_produces_hits(self):
        p = PreviewMetaEvidenceProvider()
        hints = [
            PreviewModelHint(
                filename="illustriousXL_v060.safetensors",
                kind=AssetKind.CHECKPOINT,
                source_image="001.png",
                source_type="api_meta",
                raw_value="illustriousXL_v060",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        hit = result.hits[0]
        assert hit.item.source == "preview_api_meta"
        assert hit.item.confidence == 0.82
        assert hit.provenance == "preview:001.png"

    def test_png_embedded_higher_confidence(self):
        p = PreviewMetaEvidenceProvider()
        hints = [
            PreviewModelHint(
                filename="model.safetensors",
                source_image="001.png",
                source_type="png_embedded",
                raw_value="model",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert result.hits[0].item.confidence == 0.85
        assert result.hits[0].item.source == "preview_embedded"

    def test_unresolvable_hints_skipped(self):
        p = PreviewMetaEvidenceProvider()
        hints = [
            PreviewModelHint(
                filename="private_model.safetensors",
                source_image="001.png",
                source_type="api_meta",
                raw_value="private",
                resolvable=False,
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)
        assert result.hits == []


class TestPreviewMetaEnrichment:
    """Tests for preview hint → real Civitai ID enrichment."""

    def _make_civitai_version(self, model_id=1001, version_id=2001, name="TestModel"):
        """Create a mock CivitaiModelVersion dataclass."""
        v = MagicMock()
        v.model_id = model_id
        v.id = version_id
        v.name = name
        v.files = [{"id": 3001, "hashes": {"SHA256": "aabb1122"}}]
        return v

    def test_hash_lookup_resolves_real_ids(self):
        """When hint has a hash, provider resolves via get_model_by_hash."""
        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = self._make_civitai_version()

        ps = MagicMock()
        ps.civitai = civitai

        p = PreviewMetaEvidenceProvider(lambda: ps)
        hints = [
            PreviewModelHint(
                filename="juggernaut_xl.safetensors",
                kind=AssetKind.CHECKPOINT,
                source_image="001.png",
                source_type="api_meta",
                raw_value="juggernaut_xl",
                hash="aabb1122",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        hit = result.hits[0]
        assert hit.candidate.selector.strategy == SelectorStrategy.CIVITAI_FILE
        assert hit.candidate.selector.civitai.model_id == 1001
        assert hit.candidate.selector.civitai.version_id == 2001
        assert "civitai:1001:2001" in hit.candidate.key
        civitai.get_model_by_hash.assert_called_once_with("aabb1122")

    def test_hash_miss_falls_back_to_name_search(self):
        """When hash lookup fails, provider tries name search."""
        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = None
        civitai.search_meilisearch.return_value = {
            "items": [{"id": 5001, "name": "Juggernaut XL", "type": "Checkpoint"}],
        }
        civitai.get_model.return_value = {
            "modelVersions": [{"id": 6001, "files": [{"id": 7001}]}],
        }

        ps = MagicMock()
        ps.civitai = civitai

        p = PreviewMetaEvidenceProvider(lambda: ps)
        hints = [
            PreviewModelHint(
                filename="juggernaut_xl.safetensors",
                kind=AssetKind.CHECKPOINT,
                source_image="001.png",
                source_type="api_meta",
                raw_value="juggernaut_xl",
                hash="deadbeef",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        hit = result.hits[0]
        assert hit.candidate.selector.civitai.model_id == 5001
        assert hit.candidate.selector.civitai.version_id == 6001

    def test_no_civitai_client_keeps_placeholder(self):
        """Without civitai client, hints keep model_id=0 placeholder."""
        p = PreviewMetaEvidenceProvider(lambda: None)
        hints = [
            PreviewModelHint(
                filename="model.safetensors",
                source_image="001.png",
                source_type="api_meta",
                raw_value="model",
                hash="aabb",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].candidate.selector.civitai.model_id == 0

    def test_hash_cache_dedup(self):
        """Same hash is only looked up once via API."""
        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = self._make_civitai_version()

        ps = MagicMock()
        ps.civitai = civitai

        p = PreviewMetaEvidenceProvider(lambda: ps)
        hints = [
            PreviewModelHint(
                filename="model_a.safetensors", source_image="001.png",
                source_type="api_meta", raw_value="a", hash="samehash",
            ),
            PreviewModelHint(
                filename="model_b.safetensors", source_image="002.png",
                source_type="api_meta", raw_value="b", hash="samehash",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert len(result.hits) == 2
        # Both resolved, but only one API call
        civitai.get_model_by_hash.assert_called_once_with("samehash")
        for hit in result.hits:
            assert hit.candidate.selector.civitai.model_id == 1001

    def test_name_search_filters_by_kind(self):
        """Name search skips results with wrong model type."""
        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = None
        civitai.search_meilisearch.return_value = {
            "items": [
                {"id": 100, "name": "Test LoRA", "type": "LORA"},
                {"id": 200, "name": "Test Checkpoint", "type": "Checkpoint"},
            ],
        }
        civitai.get_model.return_value = {
            "modelVersions": [{"id": 201, "files": [{"id": 301}]}],
        }

        ps = MagicMock()
        ps.civitai = civitai

        p = PreviewMetaEvidenceProvider(lambda: ps)
        hints = [
            PreviewModelHint(
                filename="test.safetensors",
                kind=AssetKind.CHECKPOINT,
                source_image="001.png",
                source_type="api_meta",
                raw_value="test",
                hash="deadbeef",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        # Should pick Checkpoint (id=200), not LoRA (id=100)
        assert result.hits[0].candidate.selector.civitai.model_id == 200

    def test_enriched_confidence_boost(self):
        """Resolved hints get a confidence boost over placeholders."""
        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = self._make_civitai_version()

        ps = MagicMock()
        ps.civitai = civitai

        p = PreviewMetaEvidenceProvider(lambda: ps)
        hints = [
            PreviewModelHint(
                filename="model.safetensors", source_image="001.png",
                source_type="api_meta", raw_value="model", hash="aabb1122",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        # Base confidence 0.82 + 0.05 boost = 0.87
        assert result.hits[0].item.confidence == 0.87

    def test_hash_lookup_exception_handled(self):
        """API errors don't crash provider, hint falls back to placeholder."""
        civitai = MagicMock()
        civitai.get_model_by_hash.side_effect = ConnectionError("timeout")

        ps = MagicMock()
        ps.civitai = civitai

        p = PreviewMetaEvidenceProvider(lambda: ps)
        hints = [
            PreviewModelHint(
                filename="model.safetensors", source_image="001.png",
                source_type="api_meta", raw_value="model", hash="aabb",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].candidate.selector.civitai.model_id == 0
        assert any("hash lookup failed" in w for w in result.warnings)

    def test_no_pack_service_getter_keeps_placeholder(self):
        """Provider without pack_service_getter still works (placeholder mode)."""
        p = PreviewMetaEvidenceProvider()  # No getter
        hints = [
            PreviewModelHint(
                filename="model.safetensors", source_image="001.png",
                source_type="api_meta", raw_value="model",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].candidate.selector.civitai.model_id == 0

    def test_short_stem_skips_name_search(self):
        """Stems < 3 chars skip name search to avoid noisy results."""
        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = None

        ps = MagicMock()
        ps.civitai = civitai

        p = PreviewMetaEvidenceProvider(lambda: ps)
        hints = [
            PreviewModelHint(
                filename="ab.safetensors", source_image="001.png",
                source_type="api_meta", raw_value="ab",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        # Should keep placeholder, no search attempted
        assert result.hits[0].candidate.selector.civitai.model_id == 0
        civitai.search_meilisearch.assert_not_called()


class TestFileMetaEvidenceProvider:
    def test_tier_is_3(self):
        assert FileMetaEvidenceProvider().tier == 3

    def test_extracts_from_filename(self):
        dep = MagicMock()
        dep.filename = "illustriousXL_v060.safetensors"
        dep.name = None

        p = FileMetaEvidenceProvider()
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].item.source == "file_metadata"
        assert result.hits[0].item.confidence == 0.60

    def test_no_filename_returns_empty(self):
        dep = MagicMock()
        dep.filename = None
        dep.name = None

        p = FileMetaEvidenceProvider()
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)
        assert result.hits == []


class TestExtractStem:
    def test_safetensors(self):
        assert _extract_stem("model.safetensors") == "model"

    def test_ckpt(self):
        assert _extract_stem("model.ckpt") == "model"

    def test_no_extension(self):
        assert _extract_stem("model") == "model"

    def test_empty(self):
        assert _extract_stem(".safetensors") is None


class TestSourceMetaEvidenceProvider:
    def test_tier_is_4(self):
        assert SourceMetaEvidenceProvider().tier == 4

    def test_produces_hint_from_base_model(self):
        dep = MagicMock()
        dep.base_model = "SDXL"

        p = SourceMetaEvidenceProvider()
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].item.source == "source_metadata"
        assert result.hits[0].item.confidence == 0.40

    def test_no_base_model_returns_empty(self):
        dep = MagicMock()
        dep.base_model = None

        p = SourceMetaEvidenceProvider()
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)
        assert result.hits == []


def _make_task_result(success=True, output=None, error=None):
    """Create a mock TaskResult matching avatar.tasks.base.TaskResult."""
    tr = MagicMock()
    tr.success = success
    tr.output = output
    tr.error = error
    return tr


class TestAIEvidenceProvider:
    def test_tier_is_2(self):
        assert AIEvidenceProvider(lambda: None).tier == 2

    def test_supports_returns_false_when_avatar_none(self):
        p = AIEvidenceProvider(lambda: None)
        ctx = _make_context()
        assert p.supports(ctx) is False

    def test_supports_returns_true_after_set_avatar(self):
        avatar = MagicMock()
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        assert p.supports(ctx) is True

    def test_gather_returns_error_when_no_avatar(self):
        p = AIEvidenceProvider(lambda: None)
        ctx = _make_context()
        result = p.gather(ctx)
        assert result.error is not None

    def test_caps_confidence_at_089(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={
                "candidates": [
                    {"display_name": "High conf", "provider": "civitai",
                     "model_id": 123, "confidence": 0.99, "reasoning": "test"},
                ],
                "search_summary": "tested",
            }
        )
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].item.confidence == 0.89  # Capped

    def test_gather_calls_dependency_resolution_task(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={"candidates": [], "search_summary": ""}
        )

        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        p.gather(ctx)

        avatar.execute_task.assert_called_once()
        call_args = avatar.execute_task.call_args
        assert call_args[0][0] == "dependency_resolution"
        # Second arg is the formatted input text (string, not dict)
        assert isinstance(call_args[0][1], str)
        assert "PACK INFO:" in call_args[0][1]
        assert "DEPENDENCY TO RESOLVE:" in call_args[0][1]

    def test_gather_passes_structured_input(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={"candidates": [], "search_summary": ""}
        )

        pack = MagicMock()
        pack.name = "test_lora_v2"
        pack.type = "lora"
        pack.base_model = "SDXL"
        pack.description = "A test LoRA for portraits"
        pack.tags = ["portrait", "anime"]

        dep = MagicMock()
        dep.selector = MagicMock()
        dep.selector.base_model = "SDXL"
        dep.expose = MagicMock()
        dep.expose.filename = "sdxl_base.safetensors"

        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context(pack=pack, dependency=dep, dep_id="base_ckpt")
        p.gather(ctx)

        input_text = avatar.execute_task.call_args[0][1]
        assert "test_lora_v2" in input_text
        assert "lora" in input_text
        assert "SDXL" in input_text
        assert "base_ckpt" in input_text
        assert "sdxl_base.safetensors" in input_text

    def test_gather_civitai_candidate_with_full_ids(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={
                "candidates": [
                    {
                        "display_name": "Illustrious XL v0.1",
                        "provider": "civitai",
                        "model_id": 795765,
                        "version_id": 889818,
                        "file_id": 795432,
                        "base_model": "Illustrious",
                        "confidence": 0.85,
                        "reasoning": "Strong match.",
                    }
                ],
                "search_summary": "Found on Civitai.",
            }
        )
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)

        assert len(result.hits) == 1
        hit = result.hits[0]
        assert hit.candidate.display_name == "Illustrious XL v0.1"
        assert hit.candidate.provider_name == "civitai"
        assert hit.candidate.selector.strategy == SelectorStrategy.CIVITAI_FILE
        assert hit.candidate.selector.civitai.model_id == 795765
        assert hit.candidate.selector.civitai.version_id == 889818
        assert hit.candidate.selector.civitai.file_id == 795432
        assert hit.item.confidence == 0.85
        assert hit.item.source == "ai_analysis"
        assert "civitai:795765:889818" in hit.candidate.key

    def test_gather_civitai_candidate_without_version(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={
                "candidates": [
                    {
                        "display_name": "Some model",
                        "provider": "civitai",
                        "model_id": 100,
                        "version_id": None,
                        "file_id": None,
                        "confidence": 0.60,
                        "reasoning": "Partial.",
                    }
                ],
                "search_summary": "Searched.",
            }
        )
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].candidate.selector.strategy == SelectorStrategy.CIVITAI_MODEL_LATEST

    def test_gather_huggingface_candidate(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={
                "candidates": [
                    {
                        "display_name": "SDXL Base (HF)",
                        "provider": "huggingface",
                        "repo_id": "stabilityai/stable-diffusion-xl-base-1.0",
                        "filename": "sd_xl_base_1.0.safetensors",
                        "revision": "main",
                        "confidence": 0.72,
                        "reasoning": "HF match.",
                    }
                ],
                "search_summary": "Found on HF.",
            }
        )
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)

        assert len(result.hits) == 1
        hit = result.hits[0]
        assert hit.candidate.provider_name == "huggingface"
        assert hit.candidate.selector.strategy == SelectorStrategy.HUGGINGFACE_FILE
        assert hit.candidate.selector.huggingface.repo_id == "stabilityai/stable-diffusion-xl-base-1.0"
        assert hit.candidate.selector.huggingface.filename == "sd_xl_base_1.0.safetensors"
        assert "hf:" in hit.candidate.key

    def test_gather_mixed_providers(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={
                "candidates": [
                    {
                        "display_name": "Civitai model",
                        "provider": "civitai",
                        "model_id": 100,
                        "confidence": 0.85,
                        "reasoning": "Civitai match.",
                    },
                    {
                        "display_name": "HF model",
                        "provider": "huggingface",
                        "repo_id": "org/repo",
                        "filename": "model.safetensors",
                        "confidence": 0.72,
                        "reasoning": "HF match.",
                    },
                ],
                "search_summary": "Multi-provider.",
            }
        )
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)

        assert len(result.hits) == 2
        providers = {h.candidate.provider_name for h in result.hits}
        assert providers == {"civitai", "huggingface"}

    def test_gather_skips_invalid_candidates(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={
                "candidates": [
                    {"display_name": "No provider", "confidence": 0.50, "reasoning": "x"},
                    {"display_name": "Unknown provider", "provider": "other",
                     "confidence": 0.50, "reasoning": "x"},
                    {"display_name": "Civitai no model_id", "provider": "civitai",
                     "confidence": 0.50, "reasoning": "x"},
                    {"display_name": "HF no repo", "provider": "huggingface",
                     "filename": "x.safetensors", "confidence": 0.50, "reasoning": "x"},
                ],
                "search_summary": "All invalid.",
            }
        )
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)
        assert len(result.hits) == 0

    def test_gather_task_failure(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            success=False, error="Engine timeout"
        )
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)
        assert result.error is not None
        assert "Engine timeout" in result.error

    def test_gather_handles_exception(self):
        avatar = MagicMock()
        avatar.execute_task.side_effect = Exception("AI crashed")

        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)

        assert result.error is not None
        assert "AI crashed" in result.error

    def test_gather_empty_candidates(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={"candidates": [], "search_summary": "Nothing found."}
        )
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)
        assert result.hits == []

    def test_gather_includes_preview_hints_in_input(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = _make_task_result(
            output={"candidates": [], "search_summary": ""}
        )

        hints = [
            PreviewModelHint(
                filename="realvisxl_v40.safetensors",
                source_image="preview_001.png",
                source_type="api_meta",
                raw_value="RealVisXL V4.0",
            ),
        ]
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context(preview_hints=hints)
        p.gather(ctx)

        input_text = avatar.execute_task.call_args[0][1]
        assert "PREVIEW HINTS:" in input_text
        assert "realvisxl_v40.safetensors" in input_text
        assert "RealVisXL V4.0" in input_text
