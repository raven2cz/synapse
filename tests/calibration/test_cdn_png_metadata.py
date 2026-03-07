"""
CDN PNG Metadata Calibration Test (C5, Block E)

Verifies whether Civitai CDN preserves PNG tEXt chunks (A1111/ComfyUI metadata).
This determines the reliability of E2 (preview_embedded) evidence source.

Result is recorded in PLAN-Resolve-Model.md.

Usage:
    uv run pytest tests/calibration/test_cdn_png_metadata.py -v -s

Requires network access (downloads from Civitai CDN).
"""

import logging
import struct
from typing import Dict, List, Optional

import httpx
import pytest
import pytest_asyncio

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.external, pytest.mark.calibration]

# Reuse browser headers from smoke tests
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://civitai.com/",
}

# Civitai API
CIVITAI_API = "https://civitai.com/api/v1"

# Known models for calibration
CALIBRATION_MODELS = [
    133005,   # Juggernaut XL
    4201,     # Realistic Vision
    795765,   # Illustrious XL
    101055,   # SD XL base
    257749,   # Pony Diffusion V6 XL
]


@pytest.fixture(scope="module")
def network_available():
    """Check if Civitai CDN is reachable."""
    try:
        with httpx.Client(timeout=10, headers=BROWSER_HEADERS) as client:
            resp = client.head("https://image.civitai.com", follow_redirects=True)
            return resp.status_code < 500
    except (httpx.HTTPError, httpx.TimeoutException):
        return False


def _fetch_model_images_sync(model_id: int, limit: int = 5) -> List[Dict]:
    """Fetch image metadata from Civitai API for a model."""
    url = f"{CIVITAI_API}/images"
    params = {"modelId": model_id, "limit": limit, "sort": "Most Reactions"}
    try:
        with httpx.Client(timeout=30, headers=BROWSER_HEADERS) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("items", [])
    except Exception as e:
        logger.warning("Failed to fetch images for model %d: %s", model_id, e)
        return []


def _download_image_sync(url: str) -> Optional[bytes]:
    """Download an image from Civitai CDN."""
    try:
        with httpx.Client(timeout=30, headers=BROWSER_HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        logger.warning("Failed to download %s: %s", url, e)
        return None


def _read_png_text_chunks(data: bytes) -> Dict[str, str]:
    """Read tEXt/iTXt chunks from PNG data without PIL."""
    chunks = {}
    if data[:4] != b"\x89PNG":
        return chunks

    pos = 8  # Skip PNG signature
    while pos < len(data) - 12:
        try:
            length = struct.unpack(">I", data[pos:pos+4])[0]
            chunk_type = data[pos+4:pos+8].decode("ascii", errors="replace")
            chunk_data = data[pos+8:pos+8+length]

            if chunk_type == "tEXt":
                null_pos = chunk_data.find(b"\x00")
                if null_pos > 0:
                    key = chunk_data[:null_pos].decode("latin-1")
                    value = chunk_data[null_pos+1:].decode("latin-1", errors="replace")
                    chunks[key] = value

            elif chunk_type == "iTXt":
                null_pos = chunk_data.find(b"\x00")
                if null_pos > 0:
                    key = chunk_data[:null_pos].decode("utf-8", errors="replace")
                    rest = chunk_data[null_pos+1:]
                    parts = rest.split(b"\x00", 3)
                    if len(parts) >= 4:
                        value = parts[3].decode("utf-8", errors="replace")
                        chunks[key] = value

            pos += 12 + length  # 4 length + 4 type + data + 4 CRC
        except (struct.error, IndexError):
            break

    return chunks


class TestCdnPngMetadata:
    """Calibration: Does Civitai CDN preserve PNG tEXt chunks?"""

    def test_fetch_and_check_png_metadata(self, network_available):
        """Download images from Civitai CDN and check for PNG tEXt chunks."""
        if not network_available:
            pytest.skip("Network unavailable — skipping CDN calibration")

        results = []
        png_count = 0
        png_with_text = 0
        api_meta_count = 0
        api_with_model = 0

        for model_id in CALIBRATION_MODELS:
            images = _fetch_model_images_sync(model_id, limit=3)
            if not images:
                continue

            for img in images:
                img_url = img.get("url", "")
                img_id = img.get("id", "unknown")

                # Check API metadata
                meta = img.get("meta") or {}
                has_meta = bool(meta)
                has_model = bool(meta.get("Model") or meta.get("model_name"))

                if has_meta:
                    api_meta_count += 1
                if has_model:
                    api_with_model += 1

                if not img_url:
                    continue

                data = _download_image_sync(img_url)
                if data is None:
                    continue

                is_actual_png = data[:4] == b"\x89PNG"

                entry = {
                    "model_id": model_id,
                    "image_id": img_id,
                    "is_png": is_actual_png,
                    "size_kb": len(data) // 1024,
                    "has_api_meta": has_meta,
                    "has_model": has_model,
                }

                if is_actual_png:
                    png_count += 1
                    text_chunks = _read_png_text_chunks(data)
                    entry["text_chunks"] = list(text_chunks.keys())

                    if text_chunks:
                        png_with_text += 1
                        print(f"  PNG with tEXt: model={model_id} img={img_id} chunks={list(text_chunks.keys())}")
                    else:
                        print(f"  PNG NO tEXt:   model={model_id} img={img_id}")
                else:
                    fmt = "JPEG" if data[:3] == b"\xff\xd8\xff" else "WebP" if data[:4] == b"RIFF" else "other"
                    print(f"  {fmt}:          model={model_id} img={img_id} size={len(data)//1024}KB")

                results.append(entry)

        total = len(results)
        print("\n" + "=" * 70)
        print("CDN PNG METADATA CALIBRATION REPORT")
        print("=" * 70)
        print(f"Total images checked:     {total}")
        print(f"Actual PNG files:         {png_count}")
        print(f"PNG with tEXt chunks:     {png_with_text}")
        print(f"API meta available:       {api_meta_count}/{total}")
        print(f"API meta with Model:      {api_with_model}/{total}")

        if png_count > 0:
            pct = (png_with_text / png_count) * 100
            print(f"\nPNG tEXt preservation rate: {pct:.0f}%")
            if pct < 50:
                print("CONCLUSION: CDN STRIPS tEXt — E2 is best-effort only")
            else:
                print("CONCLUSION: CDN preserves tEXt — E2 is reliable")
        else:
            print("\nNo PNG files in CDN responses (all JPEG/WebP)")
            print("CONCLUSION: CDN serves optimized formats, not original PNG")

        if total > 0:
            print(f"\nAPI meta.Model rate: {api_with_model}/{total} ({api_with_model/total*100:.0f}%)")
        print("=" * 70)

        if total == 0:
            pytest.skip("No images fetched — Civitai API rate-limited or unreachable")


class TestApiMetaReliability:
    """Calibration: How reliable is Civitai API meta.Model field?"""

    def test_api_meta_model_field(self, network_available):
        """Check how often meta.Model contains useful data."""
        if not network_available:
            pytest.skip("Network unavailable — skipping API meta calibration")

        total = 0
        with_model = 0
        with_resources = 0

        for model_id in CALIBRATION_MODELS:
            images = _fetch_model_images_sync(model_id, limit=5)
            for img in images:
                total += 1
                meta = img.get("meta") or {}
                if meta.get("Model") or meta.get("model_name"):
                    with_model += 1
                if meta.get("resources"):
                    with_resources += 1

        print("\n" + "=" * 70)
        print("API META RELIABILITY REPORT")
        print("=" * 70)
        print(f"Total images:              {total}")
        print(f"With meta.Model:           {with_model} ({with_model/max(total,1)*100:.0f}%)")
        print(f"With meta.resources[]:     {with_resources} ({with_resources/max(total,1)*100:.0f}%)")
        print("=" * 70)

        if total == 0:
            pytest.skip("No images fetched — Civitai API rate-limited or unreachable")
