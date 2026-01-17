"""
Tests for Synapse Store v2 - Blob Store

Tests:
- Blob storage and retrieval
- Hash computation and verification
- Deduplication
- Download operations (file:// URLs)
"""

import hashlib
import tempfile
from pathlib import Path

import pytest


class TestBlobStore:
    """Tests for BlobStore class."""
    
    def test_blob_path_structure(self):
        """Test blob path uses first 2 chars of hash as prefix."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            sha = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
            path = store.blob_path(sha)
            
            assert "ab" in path.parts
            assert path.name == sha
    
    def test_blob_exists_false_initially(self):
        """Test that non-existent blob returns False."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            sha = "abcdef" * 10 + "1234"
            assert not store.blob_exists(sha)
    
    def test_adopt_file(self):
        """Test adopting a local file into blob store."""
        from src.store import StoreLayout, BlobStore
        from src.store.blob_store import compute_sha256
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            # Create source file
            source = Path(tmpdir) / "source.bin"
            content = b"test content for hashing"
            source.write_bytes(content)
            
            expected_sha = hashlib.sha256(content).hexdigest()
            
            # Adopt
            result_sha = store.adopt(source)
            
            assert result_sha == expected_sha
            assert store.blob_exists(result_sha)
            
            # Verify content
            blob_path = store.blob_path(result_sha)
            assert blob_path.read_bytes() == content
    
    def test_adopt_deduplicates(self):
        """Test that adopting same content doesn't create duplicates."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            content = b"duplicate content"
            
            # Create two source files with same content
            source1 = Path(tmpdir) / "source1.bin"
            source2 = Path(tmpdir) / "source2.bin"
            source1.write_bytes(content)
            source2.write_bytes(content)
            
            # Adopt both
            sha1 = store.adopt(source1)
            sha2 = store.adopt(source2)
            
            # Same hash
            assert sha1 == sha2
            
            # Only one blob
            blobs = store.list_blobs()
            assert len(blobs) == 1
    
    def test_download_file_url(self):
        """Test downloading from file:// URL."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            # Create source file
            source = Path(tmpdir) / "download_source.bin"
            content = b"download test content"
            source.write_bytes(content)
            expected_sha = hashlib.sha256(content).hexdigest()
            
            # Download using file:// URL
            url = source.as_uri()
            result_sha = store.download(url, expected_sha)
            
            assert result_sha == expected_sha
            assert store.blob_exists(result_sha)
    
    def test_download_hash_verification_fails(self):
        """Test that wrong hash raises error."""
        from src.store import StoreLayout, BlobStore, HashMismatchError
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            # Create source file
            source = Path(tmpdir) / "source.bin"
            source.write_bytes(b"actual content")
            
            wrong_sha = "0" * 64
            
            with pytest.raises(HashMismatchError):
                store.download(source.as_uri(), wrong_sha)
    
    def test_download_skips_if_exists(self):
        """Test that download skips if blob already exists."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            content = b"existing content"
            sha = hashlib.sha256(content).hexdigest()
            
            # Pre-create blob
            blob_path = store.blob_path(sha)
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)
            
            # Download should return immediately
            result = store.download("file:///nonexistent", sha)
            assert result == sha
    
    def test_verify_blob(self):
        """Test blob verification."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            content = b"verify me"
            sha = hashlib.sha256(content).hexdigest()
            
            # Create blob
            blob_path = store.blob_path(sha)
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)
            
            # Verify should pass
            assert store.verify(sha)
            
            # Corrupt blob
            blob_path.write_bytes(b"corrupted")
            
            # Verify should fail
            assert not store.verify(sha)
    
    def test_remove_blob(self):
        """Test blob removal."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            # Create blob
            source = Path(tmpdir) / "source.bin"
            source.write_bytes(b"to be removed")
            sha = store.adopt(source)
            
            assert store.blob_exists(sha)
            
            # Remove
            removed = store.remove_blob(sha)
            
            assert removed
            assert not store.blob_exists(sha)
            
            # Remove again returns False
            assert not store.remove_blob(sha)
    
    def test_list_blobs(self):
        """Test listing all blobs."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            # Create some blobs
            for i in range(3):
                source = Path(tmpdir) / f"source_{i}.bin"
                source.write_bytes(f"content {i}".encode())
                store.adopt(source)
            
            blobs = store.list_blobs()
            assert len(blobs) == 3
    
    def test_total_size(self):
        """Test getting total blob store size."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            # Create blobs
            content1 = b"a" * 100
            content2 = b"b" * 200
            
            source1 = Path(tmpdir) / "s1.bin"
            source2 = Path(tmpdir) / "s2.bin"
            source1.write_bytes(content1)
            source2.write_bytes(content2)
            
            store.adopt(source1)
            store.adopt(source2)
            
            total = store.get_total_size()
            assert total == 300
    
    def test_clean_partial(self):
        """Test cleaning partial downloads."""
        from src.store import StoreLayout, BlobStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            store = BlobStore(layout)
            
            # Create fake partial files
            partial1 = store.blob_path("aa" + "0" * 62).with_suffix(".part")
            partial2 = store.blob_path("bb" + "0" * 62).with_suffix(".part")
            
            partial1.parent.mkdir(parents=True, exist_ok=True)
            partial2.parent.mkdir(parents=True, exist_ok=True)
            
            partial1.write_bytes(b"incomplete")
            partial2.write_bytes(b"partial")
            
            # Clean
            count = store.clean_partial()
            
            assert count == 2
            assert not partial1.exists()
            assert not partial2.exists()


class TestComputeSha256:
    """Tests for SHA256 computation."""
    
    def test_compute_sha256(self):
        """Test SHA256 computation for file."""
        from src.store.blob_store import compute_sha256
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.bin"
            content = b"hello world"
            path.write_bytes(content)
            
            result = compute_sha256(path)
            expected = hashlib.sha256(content).hexdigest()
            
            assert result == expected
    
    def test_compute_sha256_large_file(self):
        """Test SHA256 for larger file."""
        from src.store.blob_store import compute_sha256
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "large.bin"
            
            # 5MB file
            content = b"x" * (5 * 1024 * 1024)
            path.write_bytes(content)
            
            result = compute_sha256(path)
            expected = hashlib.sha256(content).hexdigest()
            
            assert result == expected
