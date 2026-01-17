#!/usr/bin/env python3
"""
Fetch Civitai image items (including generation meta) for a given model or model version,
capped by a global limit, and export to a JSON file.

Requirements:
  pip install requests

Examples:
  python civitai_fetch_images_meta.py --model-id 1949537 --limit 50
  python civitai_fetch_images_meta.py --model-version-id 2206450 --limit 80
  python civitai_fetch_images_meta.py --model-id 1949537 --limit 120 --sort Newest --nsfw any
  python civitai_fetch_images_meta.py --model-id 1949537 --official --limit 200
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests


API_BASE = "https://civitai.com/api/v1"


@dataclass
class FetchConfig:
    model_id: Optional[int]
    model_version_id: Optional[int]
    username: Optional[str]
    limit: int
    sort: str
    nsfw: str  # "true", "false", "any"
    timeout_sec: int
    sleep_sec: float
    max_pages: int


def _now_iso() -> str:
    # Use timezone-aware UTC if available or fallback
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _http_get_json(url: str, params: Optional[Dict[str, Any]], timeout_sec: int) -> Dict[str, Any]:
    r = requests.get(url, params=params, timeout=timeout_sec, headers={"Content-Type": "application/json"})
    r.raise_for_status()
    return r.json()


def _normalize_bool_choice(v: str) -> str:
    v = v.strip().lower()
    if v in ("true", "1", "yes", "y"):
        return "true"
    if v in ("false", "0", "no", "n"):
        return "false"
    if v in ("any", "both", "all", ""):
        return "any"
    raise ValueError(f"Invalid nsfw value: {v!r}. Use: true|false|any")


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _pick_meta(meta: Any, key_candidates: List[str]) -> Optional[Any]:
    """
    Pick a value from meta with several possible key names.
    """
    if not isinstance(meta, dict):
        return None
    for k in key_candidates:
        if k in meta:
            return meta.get(k)
    return None


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _normalize_image_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep the original item fields and add a normalized subsection for easy downstream use.
    """
    meta = item.get("meta")
    # Handle nested meta structure (API v1 sometimes wraps it)
    if isinstance(meta, dict) and "meta" in meta and isinstance(meta["meta"], dict):
        # Merge or prefer the inner meta if it looks like generation params
        # Use the inner meta for extraction
        meta = meta["meta"]

    normalized = {
        "prompt": _pick_meta(meta, ["prompt", "Prompt"]),
        "negativePrompt": _pick_meta(meta, ["negativePrompt", "Negative prompt", "negative_prompt"]),
        "sampler": _pick_meta(meta, ["sampler", "Sampler"]),
        "steps": _to_int(_pick_meta(meta, ["steps", "Steps"])),
        "cfgScale": _to_float(_pick_meta(meta, ["cfgScale", "CFG scale", "CFG Scale", "cfg_scale"])),
        "seed": _to_int(_pick_meta(meta, ["seed", "Seed"])),
        "clipSkip": _to_int(_pick_meta(meta, ["Clip skip", "clipSkip", "CLIP skip", "Clip Skip"])),
        "denoisingStrength": _to_float(_pick_meta(meta, ["Denoising strength", "denoisingStrength"])),
        "size": _pick_meta(meta, ["Size", "size"]),
        "modelName": _pick_meta(meta, ["Model", "model", "modelName"]),
    }

    # Return a dict that is still easy to traverse:
    # item["raw"] keeps the full API item (including full meta), and item["normalized"] is the helper view.
    return {
        "raw": item,
        "normalized": normalized,
    }


def _build_images_params(cfg: FetchConfig, per_request_limit: int, page: int) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "limit": per_request_limit,
        "page": page,
        "sort": cfg.sort,
    }
    if cfg.model_version_id is not None:
        params["modelVersionId"] = cfg.model_version_id
    elif cfg.model_id is not None:
        params["modelId"] = cfg.model_id
    
    if cfg.username:
        params["username"] = cfg.username

    # If nsfw is "any", do not send the param at all (API returns both).
    if cfg.nsfw in ("true", "false"):
        params["nsfw"] = (cfg.nsfw == "true")

    return params


def _extract_next_page(meta_block: Any) -> Optional[str]:
    if not isinstance(meta_block, dict):
        return None
    next_page = meta_block.get("nextPage")
    if isinstance(next_page, str) and next_page.strip():
        return next_page.strip()
    return None


def _parse_page_from_next_page_url(next_page_url: str) -> Optional[int]:
    try:
        u = urlparse(next_page_url)
        qs = parse_qs(u.query)
        page_vals = qs.get("page")
        if not page_vals:
            return None
        return int(page_vals[0])
    except Exception:
        return None


def _sanitize_next_page_url(next_page_url: str) -> str:
    """
    Some responses may return http:// instead of https://. Normalize to https.
    """
    u = urlparse(next_page_url)
    scheme = "https"
    return urlunparse((scheme, u.netloc, u.path, u.params, u.query, u.fragment))


def fetch_images(cfg: FetchConfig) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch images from the search/listing API (community images).
    """
    if cfg.limit <= 0:
        return [], {"note": "limit<=0, nothing fetched"}

    endpoint = f"{API_BASE}/images"
    remaining = cfg.limit
    page = 1

    seen_ids: set[int] = set()
    out: List[Dict[str, Any]] = []

    debug: Dict[str, Any] = {
        "endpoint": endpoint,
        "pagesRequested": 0,
        "duplicatesDetected": 0,
        "stoppedReason": None,
    }

    for _ in range(cfg.max_pages):
        if remaining <= 0:
            debug["stoppedReason"] = "limit_reached"
            break

        per_request = min(200, remaining)
        params = _build_images_params(cfg, per_request, page)

        debug["pagesRequested"] += 1
        data = _http_get_json(endpoint, params=params, timeout_sec=cfg.timeout_sec)

        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            debug["stoppedReason"] = "no_items"
            break

        new_count = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            img_id = _safe_int(it.get("id"))
            if img_id is None:
                continue
            if img_id in seen_ids:
                debug["duplicatesDetected"] += 1
                continue

            seen_ids.add(img_id)
            out.append(_normalize_image_item(it))
            remaining -= 1
            new_count += 1

            if remaining <= 0:
                break

        if remaining <= 0:
            debug["stoppedReason"] = "limit_reached"
            break

        # If pagination is broken and we keep getting the same page, avoid infinite loops.
        if new_count == 0:
            debug["stoppedReason"] = "no_new_items_in_page"
            break

        meta_block = data.get("metadata")
        next_page_url = _extract_next_page(meta_block)
        if not next_page_url:
            debug["stoppedReason"] = "no_next_page"
            break

        # Prefer the server-provided nextPage page number.
        next_page_url = _sanitize_next_page_url(next_page_url)
        next_page_num = _parse_page_from_next_page_url(next_page_url)
        if next_page_num is None:
            # Fallback: increment locally.
            page += 1
        else:
            page = next_page_num

        if cfg.sleep_sec > 0:
            time.sleep(cfg.sleep_sec)

    return out, debug


def fetch_model_summary(model_id: int, timeout_sec: int) -> Dict[str, Any]:
    endpoint = f"{API_BASE}/models/{model_id}"
    return _http_get_json(endpoint, params=None, timeout_sec=timeout_sec)


def fetch_official_images(cfg: FetchConfig) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch official images by merging data from /models/:id and /model-versions/:id.
    
    Logic:
    1. /models/:id returns ALL preview images (e.g. 20) but often lacks 'meta'.
    2. /model-versions/:id returns detailed images (e.g. 10) WITH 'meta'.
    3. We fetch both and merge metadata into the larger list.
    """
    if cfg.model_id is None:
        raise ValueError("Must provide --model-id for official fetch from model details.")

    # 1. Fetch full model details (source of truth for ALL preview images)
    # This gives us all images the UI shows (e.g. 20).
    model_data = fetch_model_summary(cfg.model_id, cfg.timeout_sec)
    
    endpoint_summary = f"{API_BASE}/models/{cfg.model_id}"
    debug = {
        "endpoint": endpoint_summary, 
        "version_endpoints_fetched": []
    }
    
    # 2. Build a map of detailed image data from version endpoints
    detailed_images_map: Dict[str, Dict[str, Any]] = {}
    
    model_versions = model_data.get("modelVersions", [])
    for ver_summary in model_versions:
        ver_id = ver_summary.get("id")
        if cfg.model_version_id and ver_id != cfg.model_version_id:
            continue
        
        if not ver_id:
            continue
            
        # Fetch detailed version data
        ver_endpoint = f"{API_BASE}/model-versions/{ver_id}"
        try:
            ver_data = _http_get_json(ver_endpoint, None, cfg.timeout_sec)
            debug["version_endpoints_fetched"].append(ver_endpoint)
        except Exception as e:
            print(f"WARN: Failed to fetch version {ver_id}: {e}", file=sys.stderr)
            continue
            
        # Index images by URL for merging
        for img in ver_data.get("images", []):
            url = img.get("url")
            if url:
                detailed_images_map[url] = img

    # 3. Iterate through the summary images (the complete list) and enrich
    out: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    
    for ver_summary in model_versions:
        if cfg.model_version_id and ver_summary.get("id") != cfg.model_version_id:
            continue
            
        summary_images = ver_summary.get("images", [])
        for summary_img in summary_images:
            url = summary_img.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Check if we have better data
            detailed_img = detailed_images_map.get(url)
            
            # Use detailed image if available (has meta), else summary image
            # Note: _normalize_image_item will handle normalization
            source_img = detailed_img if detailed_img else summary_img
            
            norm = _normalize_image_item(source_img)
            
            # Inject known model info
            if not norm["normalized"]["modelName"]:
                 norm["normalized"]["modelName"] = model_data.get("name")
            
            out.append(norm)
            
            if len(out) >= cfg.limit:
                break
        
        if len(out) >= cfg.limit:
            break
            
    return out, debug


def build_output(cfg: FetchConfig, images: List[Dict[str, Any]], debug: Dict[str, Any], model: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    # Compute simple meta key histogram for convenience.
    meta_keys: Dict[str, int] = {}
    for it in images:
        raw = it.get("raw", {})
        meta = raw.get("meta")
        if isinstance(meta, dict):
            for k in meta.keys():
                meta_keys[str(k)] = meta_keys.get(str(k), 0) + 1

    return {
        "fetchedAt": _now_iso(),
        "request": {
            "modelId": cfg.model_id,
            "modelVersionId": cfg.model_version_id,
            "username": cfg.username,
            "limit": cfg.limit,
            "sort": cfg.sort,
            "nsfw": cfg.nsfw,
            "official": True # Flag in output
        },
        "debug": debug,
        "model": model,  # May be None if not requested or not available.
        "summary": {
            "returnedImages": len(images),
            "uniqueMetaKeysCount": len(meta_keys),
            "metaKeyHistogram": meta_keys,
        },
        "images": images,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch Civitai image metadata (meta) and export as JSON.")
    p.add_argument("--limit", type=int, default=1000, help="Global max number of images to fetch (hard cap).")
    p.add_argument("--model-id", type=int, default=None, help="Civitai model id (use either model-id or model-version-id).")
    p.add_argument("--model-version-id", type=int, default=None, help="Civitai modelVersionId (preferred for a specific version).")
    p.add_argument("--username", type=str, default=None, help="Filter by username (only for community fetch).")
    p.add_argument("--sort", type=str, default="Newest", choices=["Most Reactions", "Most Comments", "Newest"], help="Sort order (community fetch only).")
    p.add_argument("--nsfw", type=str, default="any", help="true|false|any (any means do not filter).")
    p.add_argument("--official", action="store_true", help="Fetch ONLY official images from the model details (like Synapse UI).")
    p.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    p.add_argument("--sleep", type=float, default=0.2, help="Sleep between pages (seconds).")
    p.add_argument("--max-pages", type=int, default=50, help="Safety cap for pagination loops.")
    p.add_argument("--out", type=str, default=None, help="Output JSON file path.")
    p.add_argument("--no-model", action="store_true", help="Do not fetch /models/:id summary.")
    args = p.parse_args()

    nsfw = _normalize_bool_choice(args.nsfw)

    if args.model_id is None and args.model_version_id is None:
        print("ERROR: Provide --model-id or --model-version-id.", file=sys.stderr)
        return 2

    cfg = FetchConfig(
        model_id=args.model_id,
        model_version_id=args.model_version_id,
        username=args.username,
        limit=args.limit,
        sort=args.sort,
        nsfw=nsfw,
        timeout_sec=args.timeout,
        sleep_sec=args.sleep,
        max_pages=args.max_pages,
    )

    model_summary: Optional[Dict[str, Any]] = None
    if not args.no_model and cfg.model_id is not None:
        try:
            model_summary = fetch_model_summary(cfg.model_id, timeout_sec=cfg.timeout_sec)
        except Exception as e:
            # Non-fatal, we still return images.
            model_summary = {"error": f"Failed to fetch model summary: {type(e).__name__}: {e}"}

    try:
        if args.official:
            images, debug = fetch_official_images(cfg)
        else:
            images, debug = fetch_images(cfg)
    except requests.HTTPError as e:
        print(f"HTTP ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    out_obj = build_output(cfg, images, debug, model_summary)

    if args.out:
        out_path = args.out
    else:
        stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        suffix = f"model{cfg.model_id}" if cfg.model_id is not None else f"modelVersion{cfg.model_version_id}"
        mode_str = "_official_all" if args.official else ""
        out_path = f"civitai_images_meta_{suffix}{mode_str}_{stamp}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)

    print(f"OK: wrote {len(images)} images to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
