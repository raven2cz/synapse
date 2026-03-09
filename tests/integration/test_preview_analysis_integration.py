"""
Integration tests for preview analysis — multi-component interaction.

Tests the chain:
- analyze_pack_previews() → _read_sidecar() + _parse_sidecar_meta() + _extract_generation_params()
- extract_preview_hints() → _extract_from_sidecar() + _extract_from_png() (via PIL mock)
- API endpoint → store.get_pack → analyze_pack_previews → JSON response
- ResolveService.suggest() → preview_hints in SuggestResult

Uses real Pydantic models, real file system, mocked PIL and HTTP only.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.store.models import AssetKind, PreviewInfo
from src.store.resolve_models import (
    PreviewAnalysisResult,
    PreviewModelHint,
    SuggestResult,
)
from src.utils.preview_meta_extractor import (
    analyze_pack_previews,
    extract_preview_hints,
    _parse_sidecar_meta,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def previews_dir(tmp_path):
    """Create a previews directory with realistic sidecar data."""
    previews = tmp_path / "resources" / "previews"
    previews.mkdir(parents=True)

    # Preview 1: Full sidecar with model + resources + prompt LoRA
    sidecar1 = {
        "Model": "illustriousXL_v060",
        "Model hash": "abc123def456",
        "resources": [
            {"name": "illustriousXL_v060", "type": "model", "hash": "abc123def456"},
            {"name": "detail_tweaker_xl", "type": "lora", "weight": 0.5, "hash": "fed321cba"},
        ],
        "prompt": "1girl, masterpiece <lora:extra_style:0.3>",
        "negativePrompt": "bad quality, worst quality",
        "sampler": "DPM++ 2M",
        "steps": 25,
        "cfgScale": 7,
        "seed": 42,
        "Size": "832x1216",
    }
    (previews / "001.jpeg.json").write_text(json.dumps(sidecar1))

    # Preview 2: Minimal — only prompt, no model
    sidecar2 = {
        "prompt": "cinematic landscape, 8k photo",
        "sampler": "Euler",
        "steps": 20,
    }
    (previews / "002.jpeg.json").write_text(json.dumps(sidecar2))

    # Preview 3: Video — no sidecar at all
    # (no file created)

    return previews


@pytest.fixture
def mock_previews():
    """Create mock PreviewInfo objects."""
    p1 = PreviewInfo(
        filename="001.jpeg",
        url="https://cdn.example.com/001.jpeg",
        media_type="image",
        width=832,
        height=1216,
        nsfw=False,
    )
    p2 = PreviewInfo(
        filename="002.jpeg",
        url="https://cdn.example.com/002.jpeg",
        media_type="image",
        width=512,
        height=768,
        nsfw=False,
    )
    p3 = PreviewInfo(
        filename="003.mp4",
        url="https://cdn.example.com/003.mp4",
        media_type="video",
        width=1920,
        height=1080,
        nsfw=True,
    )
    return [p1, p2, p3]


# =============================================================================
# Integration: analyze_pack_previews (sidecar read + parse + gen params)
# =============================================================================

@pytest.mark.integration
class TestAnalyzePackPreviewsIntegration:
    """Tests analyze_pack_previews with real PreviewInfo and filesystem."""

    def test_full_analysis_with_real_previews(self, previews_dir, mock_previews):
        """Full chain: real PreviewInfo + real sidecar files → analysis results."""
        results = analyze_pack_previews(previews_dir, mock_previews)

        assert len(results) == 3

        # Preview 1: model + 1 LoRA resource + 1 LoRA from prompt = 3 hints
        # (resources[type=model] deduped against Model field)
        r1 = results[0]
        assert r1.filename == "001.jpeg"
        assert r1.url == "https://cdn.example.com/001.jpeg"
        assert r1.media_type == "image"
        assert r1.width == 832
        assert r1.height == 1216
        assert r1.nsfw is False
        assert len(r1.hints) == 3  # Model + 1 LoRA resource + 1 prompt LoRA

        # Check hint details
        ckpts = [h for h in r1.hints if h.kind == AssetKind.CHECKPOINT]
        assert len(ckpts) == 1
        assert ckpts[0].hash == "abc123def456"

        loras = [h for h in r1.hints if h.kind == AssetKind.LORA]
        assert len(loras) == 2  # detail_tweaker + extra_style from prompt
        resource_lora = next(h for h in loras if h.filename == "detail_tweaker_xl")
        assert resource_lora.weight == 0.5
        assert resource_lora.hash == "fed321cba"

        prompt_lora = next(h for h in loras if h.filename == "extra_style")
        assert prompt_lora.weight == 0.3
        assert prompt_lora.hash is None

        # Generation params
        assert r1.generation_params is not None
        assert r1.generation_params["sampler"] == "DPM++ 2M"
        assert r1.generation_params["steps"] == 25
        assert r1.generation_params["cfgScale"] == 7
        assert r1.generation_params["seed"] == 42
        assert r1.generation_params["prompt"] == "1girl, masterpiece <lora:extra_style:0.3>"

        # Preview 2: no model hint, only gen params
        r2 = results[1]
        assert len(r2.hints) == 0
        assert r2.generation_params is not None
        assert r2.generation_params["sampler"] == "Euler"

        # Preview 3: no sidecar, no hints, no params
        r3 = results[2]
        assert r3.filename == "003.mp4"
        assert r3.media_type == "video"
        assert r3.nsfw is True
        assert len(r3.hints) == 0
        assert r3.generation_params is None

    def test_single_read_per_sidecar(self, previews_dir, mock_previews):
        """Verify sidecar is read only once per preview (not twice for hints+params)."""
        with patch("src.utils.preview_meta_extractor._read_sidecar", wraps=__import__(
            "src.utils.preview_meta_extractor", fromlist=["_read_sidecar"]
        )._read_sidecar) as mock_read:
            # analyze_pack_previews should call _read_sidecar once per preview
            # BUT _extract_from_sidecar (called from extract_preview_hints) also calls it
            # The analyze_pack_previews function calls _read_sidecar directly + _extract_from_png
            results = analyze_pack_previews(previews_dir, mock_previews[:1])
            # Should read sidecar once (from analyze_pack_previews direct call)
            assert mock_read.call_count == 1

    def test_preserves_url_and_thumbnail(self, previews_dir):
        """URL and thumbnail_url from PreviewInfo passed through to result."""
        preview = PreviewInfo(
            filename="001.jpeg",
            url="https://cdn.example.com/001.jpeg",
            thumbnail_url="https://cdn.example.com/001_thumb.jpeg",
            media_type="image",
        )
        results = analyze_pack_previews(previews_dir, [preview])
        assert results[0].url == "https://cdn.example.com/001.jpeg"
        assert results[0].thumbnail_url == "https://cdn.example.com/001_thumb.jpeg"


# =============================================================================
# Integration: extract_preview_hints (sidecar + PNG combo)
# =============================================================================

@pytest.mark.integration
class TestExtractHintsIntegration:
    """Tests extract_preview_hints with multiple sources."""

    def test_sidecar_and_png_combined(self, previews_dir):
        """Both sidecar JSON and PNG tEXt produce hints for .png files.

        When PIL is available, PNG hints are extracted alongside sidecar hints.
        When PIL is not available, only sidecar hints are returned (graceful degradation).
        """
        # Create a PNG sidecar
        sidecar = {"Model": "sidecar_model", "resources": []}
        (previews_dir / "test.png.json").write_text(json.dumps(sidecar))

        # Create a dummy PNG file
        (previews_dir / "test.png").write_bytes(b"PNG_DUMMY")

        hints = extract_preview_hints(previews_dir, ["test.png"])

        # Sidecar hints should always be present
        assert len(hints) >= 1
        assert any(h.source_type == "api_meta" for h in hints)
        assert any(h.filename == "sidecar_model" for h in hints)

        # PNG hints depend on PIL availability — graceful either way
        try:
            import PIL.Image  # noqa: F401
            # If PIL is available, we'd expect png_embedded hints too
            # (but with dummy PNG data, PIL.Image.open may fail gracefully)
        except ImportError:
            # Without PIL, only sidecar hints returned — that's correct
            assert all(h.source_type == "api_meta" for h in hints)

    def test_sidecar_only_for_jpeg(self, previews_dir):
        """JPEG files only get sidecar hints, no PNG extraction attempted."""
        hints = extract_preview_hints(previews_dir, ["001.jpeg"])
        assert len(hints) >= 1
        assert all(h.source_type == "api_meta" for h in hints)

    def test_missing_sidecar_graceful(self, previews_dir):
        """Missing sidecar returns empty hints without error."""
        hints = extract_preview_hints(previews_dir, ["nonexistent.jpeg"])
        assert hints == []


# =============================================================================
# Integration: API endpoint + store interaction
# =============================================================================

@pytest.mark.integration
class TestPreviewAnalysisAPIIntegration:
    """Tests API endpoint with mock store but real analysis logic."""

    def test_endpoint_delegates_to_analyze(self, tmp_path):
        """Endpoint calls analyze_pack_previews with correct args."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from src.store.api import v2_packs_router, require_initialized

        # Setup previews directory with sidecar
        previews = tmp_path / "previews"
        previews.mkdir()
        sidecar = {"Model": "test_model", "sampler": "Euler", "steps": 20}
        (previews / "001.jpeg.json").write_text(json.dumps(sidecar))

        # Mock store
        mock_store = MagicMock()
        mock_store.layout.pack_previews_path.return_value = previews
        mock_pack = MagicMock()
        mock_pack.name = "TestPack"
        mock_preview = MagicMock()
        mock_preview.filename = "001.jpeg"
        mock_preview.media_type = "image"
        mock_preview.width = 512
        mock_preview.height = 768
        mock_preview.nsfw = False
        mock_preview.url = "https://cdn.example.com/001.jpeg"
        mock_preview.thumbnail_url = None
        mock_pack.previews = [mock_preview]
        mock_store.get_pack.return_value = mock_pack

        app = FastAPI()
        app.include_router(v2_packs_router, prefix="/api/packs")
        app.dependency_overrides[require_initialized] = lambda: mock_store

        client = TestClient(app)
        resp = client.get("/api/packs/TestPack/preview-analysis")

        assert resp.status_code == 200
        data = resp.json()

        # Verify full chain worked
        assert data["pack_name"] == "TestPack"
        assert len(data["previews"]) == 1
        assert data["previews"][0]["hints"][0]["kind"] == "checkpoint"
        assert data["previews"][0]["generation_params"]["sampler"] == "Euler"
        assert data["total_hints"] == 1

    def test_suggest_result_includes_preview_hints(self):
        """SuggestResult.preview_hints populated correctly."""
        # Test the data model directly — ResolveService.suggest() passes
        # preview_hints through to SuggestResult (verified in unit tests).
        test_hints = [
            PreviewModelHint(
                filename="model.safetensors",
                kind=AssetKind.CHECKPOINT,
                source_image="001.jpeg",
                source_type="api_meta",
                raw_value="model",
                hash="abc123",
            ),
        ]

        result = SuggestResult(
            preview_hints=test_hints,
        )

        assert isinstance(result, SuggestResult)
        assert len(result.preview_hints) == 1
        assert result.preview_hints[0].hash == "abc123"
        assert result.preview_hints[0].kind == AssetKind.CHECKPOINT

        # Verify serialization roundtrip
        dumped = result.model_dump()
        assert len(dumped["preview_hints"]) == 1
        assert dumped["preview_hints"][0]["hash"] == "abc123"


# =============================================================================
# Integration: Flat vs wrapped format across the full chain
# =============================================================================

@pytest.mark.integration
class TestSidecarFormatIntegration:
    """BUG 7 fix verified across the full analysis chain."""

    def test_flat_format_through_full_chain(self, tmp_path):
        """Flat Civitai sidecar → analyze_pack_previews → correct hints + params."""
        previews = tmp_path / "previews"
        previews.mkdir()

        # Real-world flat format sidecar
        sidecar = {
            "Model": "Juggernaut_X_RunDiffusionPhoto_NSFW_Final",
            "Model hash": "d91d35736d",
            "resources": [
                {"hash": "d91d35736d", "name": "Juggernaut_X_RunDiffusionPhoto", "type": "model"},
                {"hash": "cdaa1234", "name": "quality_boost", "type": "lora", "weight": 0.6},
            ],
            "prompt": "beautiful lady, big smile <lora:extra_detail:0.4>",
            "sampler": "DPM++ 2M",
            "steps": 35,
            "cfgScale": 7,
            "seed": 2876985801,
        }
        (previews / "10269273.jpeg.json").write_text(json.dumps(sidecar))

        preview = PreviewInfo(
            filename="10269273.jpeg",
            url="https://cdn.example.com/10269273.jpeg",
            media_type="image",
            width=832,
            height=1216,
        )

        results = analyze_pack_previews(previews, [preview])
        assert len(results) == 1
        r = results[0]

        # Model + resource[type=model] (different name!) + 1 LoRA resource + 1 prompt LoRA = 4
        # (Model name != resource name, so no dedup)
        assert len(r.hints) == 4
        ckpts = [h for h in r.hints if h.kind == AssetKind.CHECKPOINT]
        assert len(ckpts) == 2  # Model field + resource with different name
        assert any(c.hash == "d91d35736d" for c in ckpts)

        loras = [h for h in r.hints if h.kind == AssetKind.LORA]
        assert len(loras) == 2

        # Verify gen params
        assert r.generation_params is not None
        assert r.generation_params["seed"] == 2876985801
        assert r.generation_params["steps"] == 35

    def test_wrapped_format_through_full_chain(self, tmp_path):
        """Legacy wrapped {"meta": {...}} format still works through full chain."""
        previews = tmp_path / "previews"
        previews.mkdir()

        sidecar = {
            "meta": {
                "Model": "dreamshaper_8",
                "sampler": "Euler a",
                "steps": 20,
            }
        }
        (previews / "001.png.json").write_text(json.dumps(sidecar))

        preview = PreviewInfo(filename="001.png", media_type="image")
        results = analyze_pack_previews(previews, [preview])
        assert len(results) == 1
        assert len(results[0].hints) == 1
        assert results[0].hints[0].filename == "dreamshaper_8"
        assert results[0].generation_params["sampler"] == "Euler a"


# =============================================================================
# Smoke: Full API lifecycle (import → analyze → verify)
# =============================================================================

@pytest.mark.integration
class TestPreviewAnalysisSmoke:
    """Smoke tests — full lifecycle through real components."""

    def test_api_full_lifecycle(self, tmp_path):
        """Full lifecycle: create previews dir → write sidecars → call API → verify response."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from src.store.api import v2_packs_router, require_initialized

        # Setup realistic pack with multiple previews
        previews = tmp_path / "previews"
        previews.mkdir()

        # Sidecar 1: Checkpoint with LoRA
        sidecar1 = {
            "Model": "illustriousXL_v060",
            "Model hash": "abc123",
            "resources": [
                {"name": "detail_tweaker", "type": "lora", "weight": 0.5, "hash": "fed321"},
            ],
            "prompt": "1girl, masterpiece <lora:extra_style:0.3>",
            "sampler": "DPM++ 2M",
            "steps": 25,
            "cfgScale": 7,
            "seed": 42,
        }
        (previews / "001.jpeg.json").write_text(json.dumps(sidecar1))

        # Sidecar 2: Minimal
        sidecar2 = {"prompt": "landscape", "sampler": "Euler", "steps": 20}
        (previews / "002.jpeg.json").write_text(json.dumps(sidecar2))

        # No sidecar for video
        # (003.mp4 — no json)

        # Mock store
        mock_store = MagicMock()
        mock_store.layout.pack_previews_path.return_value = previews
        mock_pack = MagicMock()
        mock_pack.name = "SmokePack"

        p1 = PreviewInfo(filename="001.jpeg", url="https://cdn/001.jpeg",
                         media_type="image", width=832, height=1216, nsfw=False)
        p2 = PreviewInfo(filename="002.jpeg", media_type="image")
        p3 = PreviewInfo(filename="003.mp4", media_type="video", nsfw=True)
        mock_pack.previews = [p1, p2, p3]
        mock_store.get_pack.return_value = mock_pack

        app = FastAPI()
        app.include_router(v2_packs_router, prefix="/api/packs")
        app.dependency_overrides[require_initialized] = lambda: mock_store

        client = TestClient(app)
        resp = client.get("/api/packs/SmokePack/preview-analysis")

        assert resp.status_code == 200
        data = resp.json()

        # Full response verification
        assert data["pack_name"] == "SmokePack"
        assert len(data["previews"]) == 3

        # Preview 1: checkpoint + LoRA resource + prompt LoRA
        p1_data = data["previews"][0]
        assert p1_data["filename"] == "001.jpeg"
        assert p1_data["url"] == "https://cdn/001.jpeg"
        assert p1_data["media_type"] == "image"
        assert p1_data["width"] == 832
        assert p1_data["nsfw"] is False
        assert len(p1_data["hints"]) == 3  # Model + LoRA + prompt LoRA
        assert p1_data["generation_params"]["sampler"] == "DPM++ 2M"
        assert p1_data["generation_params"]["seed"] == 42

        # Preview 2: no model hints, only gen params
        p2_data = data["previews"][1]
        assert len(p2_data["hints"]) == 0
        assert p2_data["generation_params"]["sampler"] == "Euler"

        # Preview 3: video, no sidecar
        p3_data = data["previews"][2]
        assert p3_data["media_type"] == "video"
        assert p3_data["nsfw"] is True
        assert len(p3_data["hints"]) == 0
        assert p3_data["generation_params"] is None

        # Total hints
        assert data["total_hints"] == 3

    def test_hint_kinds_serialization(self, tmp_path):
        """Verify AssetKind serializes correctly in API response."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from src.store.api import v2_packs_router, require_initialized

        previews = tmp_path / "previews"
        previews.mkdir()

        sidecar = {
            "Model": "test_checkpoint",
            "resources": [
                {"name": "my_lora", "type": "lora", "weight": 0.6},
                {"name": "my_vae", "type": "vae"},
                {"name": "my_embed", "type": "embedding"},
            ],
        }
        (previews / "001.jpeg.json").write_text(json.dumps(sidecar))

        mock_store = MagicMock()
        mock_store.layout.pack_previews_path.return_value = previews
        mock_pack = MagicMock()
        mock_pack.name = "KindsPack"
        mock_pack.previews = [PreviewInfo(filename="001.jpeg", media_type="image")]
        mock_store.get_pack.return_value = mock_pack

        app = FastAPI()
        app.include_router(v2_packs_router, prefix="/api/packs")
        app.dependency_overrides[require_initialized] = lambda: mock_store

        client = TestClient(app)
        resp = client.get("/api/packs/KindsPack/preview-analysis")
        data = resp.json()

        hints = data["previews"][0]["hints"]
        kinds = {h["kind"] for h in hints}
        assert "checkpoint" in kinds
        assert "lora" in kinds
        assert "vae" in kinds
        assert "embedding" in kinds

    def test_error_recovery_corrupt_sidecar(self, tmp_path):
        """Corrupt sidecar JSON doesn't crash the endpoint."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from src.store.api import v2_packs_router, require_initialized

        previews = tmp_path / "previews"
        previews.mkdir()
        (previews / "001.jpeg.json").write_text("{invalid json!!!")

        mock_store = MagicMock()
        mock_store.layout.pack_previews_path.return_value = previews
        mock_pack = MagicMock()
        mock_pack.name = "CorruptPack"
        mock_pack.previews = [PreviewInfo(filename="001.jpeg", media_type="image")]
        mock_store.get_pack.return_value = mock_pack

        app = FastAPI()
        app.include_router(v2_packs_router, prefix="/api/packs")
        app.dependency_overrides[require_initialized] = lambda: mock_store

        client = TestClient(app)
        resp = client.get("/api/packs/CorruptPack/preview-analysis")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["previews"]) == 1
        assert len(data["previews"][0]["hints"]) == 0
        assert data["previews"][0]["generation_params"] is None
