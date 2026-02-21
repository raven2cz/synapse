import os
import sys
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.store.layout import StoreLayout
from src.store.blob_store import BlobStore
from src.store.download_auth import CivitaiAuthProvider

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(threadName)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_blob_downloads():
    # Setup isolated layout
    test_dir = Path("/tmp/synapse_test_blobs")
    test_dir.mkdir(parents=True, exist_ok=True)
    layout = StoreLayout(test_dir)
    
    api_key = os.environ.get("CIVITAI_API_KEY", "")
    if not api_key:
        logger.warning("No CIVITAI_API_KEY set. This might cause HTML error pages for restricted models.")
        
    auth_provider = CivitaiAuthProvider(api_key)
    
    # 4 workers as in default BlobStore
    blob_store = BlobStore(layout=layout, max_workers=4, auth_providers=[auth_provider])
    
    # Let's try downloading a couple of files concurrently
    # These are random models from Civitai, some might be age-restricted
    downloads = [
        # Example 1: a small LORA or preview image
        ("https://civitai.com/api/download/models/128713?type=Model&format=SafeTensor", None),
        # Example 2: another small file
        ("https://civitai.com/api/download/models/130072?type=Model&format=SafeTensor", None),
        # Example 3: potentially restricted or large file
        ("https://civitai.com/api/download/models/106922?type=Model&format=SafeTensor", None),
    ]
    
    logger.info(f"Starting concurrent downloads with {blob_store.max_workers} workers...")
    
    def progress_cb(url, downloaded, total):
        # Only log occasionally to avoid spam
        if downloaded % (1024 * 1024 * 10) == 0:  # Every 10MB
            logger.info(f"Progress {url[-15:]}: {downloaded}/{total} bytes")
            
    try:
        results = blob_store.download_many(downloads, progress_callback=progress_cb)
        logger.info(f"Download results: {results}")
        
        # Verify they exist
        for url, sha256 in results.items():
            if blob_store.blob_exists(sha256):
                logger.info(f"Verified blob for {url} -> {sha256}")
            else:
                logger.error(f"Blob missing for {url} -> {sha256}")
                
    except Exception as e:
        logger.exception("Download failed with exception:")

if __name__ == "__main__":
    test_blob_downloads()
