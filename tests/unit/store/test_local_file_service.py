"""Tests for LocalFileService — browse, validate, recommend, import."""

import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.store.local_file_service import (
    ALLOWED_EXTENSIONS,
    LocalFileService,
    LocalFileInfo,
    PathValidationError,
    validate_directory,
    validate_path,
)


# =============================================================================
# Path Validation Tests
# =============================================================================


class TestValidatePath:
    """Security-critical path validation."""

    def test_rejects_empty_path(self):
        with pytest.raises(PathValidationError, match="Empty path"):
            validate_path("")

    def test_rejects_relative_path(self):
        with pytest.raises(PathValidationError, match="absolute"):
            validate_path("models/checkpoint.safetensors")

    def test_rejects_path_traversal(self, tmp_path):
        with pytest.raises(PathValidationError, match="traversal"):
            validate_path(str(tmp_path / ".." / "etc" / "passwd.safetensors"))

    def test_rejects_bad_extension(self, tmp_path):
        bad_file = tmp_path / "script.sh"
        bad_file.write_text("#!/bin/bash")
        with pytest.raises(PathValidationError, match="Extension.*not allowed"):
            validate_path(str(bad_file))

    def test_rejects_nonexistent_file(self):
        with pytest.raises(PathValidationError, match="Cannot resolve"):
            validate_path("/nonexistent/model.safetensors")

    def test_accepts_valid_safetensors(self, tmp_path):
        model = tmp_path / "model.safetensors"
        model.write_bytes(b"\x00" * 100)
        result = validate_path(str(model))
        assert result == model

    def test_accepts_valid_ckpt(self, tmp_path):
        model = tmp_path / "model.ckpt"
        model.write_bytes(b"\x00" * 100)
        result = validate_path(str(model))
        assert result == model

    def test_accepts_valid_pt(self, tmp_path):
        model = tmp_path / "model.pt"
        model.write_bytes(b"\x00" * 100)
        result = validate_path(str(model))
        assert result == model

    def test_accepts_valid_gguf(self, tmp_path):
        model = tmp_path / "model.gguf"
        model.write_bytes(b"\x00" * 100)
        result = validate_path(str(model))
        assert result == model

    @pytest.mark.skipif(os.name == "nt", reason="Unix-only symlink test")
    def test_rejects_directory(self, tmp_path):
        """Directories should be rejected (extension check catches it first)."""
        with pytest.raises(PathValidationError):
            validate_path(str(tmp_path))


class TestValidateDirectory:
    def test_rejects_empty(self):
        with pytest.raises(PathValidationError, match="Empty"):
            validate_directory("")

    def test_rejects_relative(self):
        with pytest.raises(PathValidationError, match="absolute"):
            validate_directory("models/")

    def test_rejects_nonexistent(self):
        with pytest.raises(PathValidationError, match="Cannot resolve"):
            validate_directory("/nonexistent/dir")

    def test_rejects_file(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        with pytest.raises(PathValidationError, match="Not a directory"):
            validate_directory(str(f))

    def test_accepts_valid_directory(self, tmp_path):
        result = validate_directory(str(tmp_path))
        assert result == tmp_path


# =============================================================================
# Browse Tests
# =============================================================================


class TestBrowse:
    def _make_service(self) -> LocalFileService:
        mock_hash_cache = MagicMock()
        mock_hash_cache.get.return_value = None
        mock_blob_store = MagicMock()
        return LocalFileService(
            hash_cache=mock_hash_cache,
            blob_store=mock_blob_store,
        )

    def test_lists_model_files(self, tmp_path):
        (tmp_path / "model.safetensors").write_bytes(b"\x00" * 1000)
        (tmp_path / "lora.pt").write_bytes(b"\x00" * 500)

        svc = self._make_service()
        result = svc.browse(str(tmp_path))
        assert result.total_count == 2
        assert result.error is None
        names = {f["name"] for f in result.files}
        assert names == {"model.safetensors", "lora.pt"}

    def test_ignores_non_model_files(self, tmp_path):
        (tmp_path / "model.safetensors").write_bytes(b"\x00" * 1000)
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "config.json").write_text("{}")
        (tmp_path / "script.py").write_text("pass")

        svc = self._make_service()
        result = svc.browse(str(tmp_path))
        assert result.total_count == 1
        assert result.files[0]["name"] == "model.safetensors"

    def test_empty_directory(self, tmp_path):
        svc = self._make_service()
        result = svc.browse(str(tmp_path))
        assert result.total_count == 0
        assert result.error is None

    def test_nonexistent_directory(self):
        svc = self._make_service()
        result = svc.browse("/nonexistent/path")
        assert result.error is not None

    def test_returns_file_sizes(self, tmp_path):
        (tmp_path / "big.safetensors").write_bytes(b"\x00" * 5000)
        svc = self._make_service()
        result = svc.browse(str(tmp_path))
        assert result.files[0]["size"] == 5000

    def test_returns_cached_hash(self, tmp_path):
        (tmp_path / "model.safetensors").write_bytes(b"\x00" * 100)
        mock_hash_cache = MagicMock()
        mock_hash_cache.get.return_value = "abc123"
        svc = LocalFileService(hash_cache=mock_hash_cache, blob_store=MagicMock())
        result = svc.browse(str(tmp_path))
        assert result.files[0]["cached_hash"] == "abc123"


# =============================================================================
# Recommend Tests
# =============================================================================


class TestRecommend:
    def _make_dep(self, filename="model.safetensors", sha256=None):
        dep = MagicMock()
        dep.name = filename
        dep.filename = filename
        dep.id = "dep-1"
        dep.selector = MagicMock()
        dep.selector.civitai = MagicMock() if sha256 else None
        if sha256:
            dep.selector.civitai.sha256 = sha256
        return dep

    def test_sha256_exact_match(self, tmp_path):
        model = tmp_path / "model.safetensors"
        model.write_bytes(b"test content")

        mock_hash_cache = MagicMock()
        mock_hash_cache.get.return_value = "abc123"
        svc = LocalFileService(hash_cache=mock_hash_cache, blob_store=MagicMock())

        dep = self._make_dep(sha256="abc123")
        recs = svc.recommend(str(tmp_path), dep)
        assert len(recs) > 0
        assert recs[0].match_type == "sha256_exact"
        assert recs[0].confidence == 1.0

    def test_filename_exact_match(self, tmp_path):
        (tmp_path / "ponyDiffusionV6XL.safetensors").write_bytes(b"\x00")
        svc = LocalFileService(hash_cache=MagicMock(get=MagicMock(return_value=None)), blob_store=MagicMock())

        dep = self._make_dep(filename="ponyDiffusionV6XL.safetensors")
        recs = svc.recommend(str(tmp_path), dep)
        assert recs[0].match_type == "filename_exact"
        assert recs[0].confidence == 0.85

    def test_filename_stem_match(self, tmp_path):
        (tmp_path / "juggernaut_xl_v9.safetensors").write_bytes(b"\x00")
        svc = LocalFileService(hash_cache=MagicMock(get=MagicMock(return_value=None)), blob_store=MagicMock())

        dep = self._make_dep(filename="juggernaut_xl.safetensors")
        recs = svc.recommend(str(tmp_path), dep)
        assert recs[0].match_type == "filename_stem"
        assert recs[0].confidence == 0.6

    def test_no_match(self, tmp_path):
        (tmp_path / "unrelated.safetensors").write_bytes(b"\x00")
        svc = LocalFileService(hash_cache=MagicMock(get=MagicMock(return_value=None)), blob_store=MagicMock())

        dep = self._make_dep(filename="ponyDiffusion.safetensors")
        recs = svc.recommend(str(tmp_path), dep)
        assert recs[0].match_type == "none"
        assert recs[0].confidence == 0.0

    def test_sorted_by_confidence(self, tmp_path):
        (tmp_path / "model.safetensors").write_bytes(b"\x00")
        (tmp_path / "other.safetensors").write_bytes(b"\x00")

        mock_hash_cache = MagicMock()
        mock_hash_cache.get.return_value = "abc123"
        svc = LocalFileService(hash_cache=mock_hash_cache, blob_store=MagicMock())

        dep = self._make_dep(filename="model.safetensors", sha256="abc123")
        recs = svc.recommend(str(tmp_path), dep)
        # SHA256 match should be first
        assert recs[0].match_type == "sha256_exact"


# =============================================================================
# Import Tests
# =============================================================================


class TestImportFile:
    def test_validates_path(self, tmp_path):
        svc = LocalFileService(hash_cache=MagicMock(), blob_store=MagicMock())
        result = svc.import_file("/nonexistent.safetensors", "pack", "dep")
        assert not result.success
        assert "Cannot resolve" in result.message

    def test_rejects_bad_extension(self, tmp_path):
        bad = tmp_path / "file.txt"
        bad.write_text("test")
        svc = LocalFileService(hash_cache=MagicMock(), blob_store=MagicMock())
        result = svc.import_file(str(bad), "pack", "dep")
        assert not result.success
        assert "not allowed" in result.message

    def test_successful_import(self, tmp_path):
        model = tmp_path / "model.safetensors"
        model.write_bytes(b"model data here")

        blob_dir = tmp_path / "blobs"
        blob_dir.mkdir()

        mock_hash_cache = MagicMock()
        mock_hash_cache.get.return_value = None
        mock_hash_cache.compute_and_cache.return_value = "fakehash"

        mock_blob_store = MagicMock()
        blob_path = blob_dir / "blob"
        mock_blob_store.blob_path.return_value = blob_path

        # Mock pack_service for apply
        mock_ps = MagicMock()
        mock_ps.get_pack.return_value = MagicMock(dependencies=[])
        mock_store = MagicMock()
        mock_store.resolve_service.apply_manual.return_value = MagicMock(success=True, message="OK")
        mock_ps._store = mock_store

        svc = LocalFileService(
            hash_cache=mock_hash_cache,
            blob_store=mock_blob_store,
            pack_service_getter=lambda: mock_ps,
        )

        result = svc.import_file(str(model), "test-pack", "dep-1", skip_enrichment=True)
        assert result.success
        assert result.display_name is not None
        mock_hash_cache.save.assert_called_once()

    def test_progress_callback(self, tmp_path):
        model = tmp_path / "model.safetensors"
        model.write_bytes(b"data")

        mock_blob_store = MagicMock()
        mock_blob_store.blob_path.return_value = tmp_path / "existing_blob"
        (tmp_path / "existing_blob").write_bytes(b"x")  # blob exists

        mock_hash_cache = MagicMock()
        mock_hash_cache.get.return_value = "existing_hash"

        svc = LocalFileService(
            hash_cache=mock_hash_cache,
            blob_store=mock_blob_store,
        )

        stages = []
        result = svc.import_file(
            str(model), "pack", "dep",
            skip_enrichment=True,
            progress_callback=lambda stage, p: stages.append((stage, p)),
        )
        # Should have hashing and copying stages at minimum
        stage_names = [s[0] for s in stages]
        assert "hashing" in stage_names
        assert "copying" in stage_names


# =============================================================================
# Enrichment Integration
# =============================================================================


class TestEnrichment:
    """Test enrichment pipeline integration (shared with enrichment.py)."""

    def test_enrichment_used_when_not_skipped(self, tmp_path):
        model = tmp_path / "model.safetensors"
        model.write_bytes(b"data")

        mock_blob_store = MagicMock()
        mock_blob_store.blob_path.return_value = tmp_path / "blob"

        mock_hash_cache = MagicMock()
        mock_hash_cache.get.return_value = None

        # Mock civitai client with hash lookup
        mock_civitai = MagicMock()
        mock_civitai.get_model_by_hash.return_value = None  # Not found

        mock_ps = MagicMock()
        mock_ps.civitai = mock_civitai
        mock_ps.get_pack.return_value = MagicMock(dependencies=[])

        svc = LocalFileService(
            hash_cache=mock_hash_cache,
            blob_store=mock_blob_store,
            pack_service_getter=lambda: mock_ps,
        )

        with patch("src.store.local_file_service.enrich_file") as mock_enrich:
            from src.store.enrichment import EnrichmentResult
            mock_enrich.return_value = EnrichmentResult(
                source="filename_only",
                display_name="model",
            )
            result = svc.import_file(str(model), "pack", "dep")

        mock_enrich.assert_called_once()
