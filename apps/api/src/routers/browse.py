"""
Browse Router

Search and browse Civitai models with enhanced search:
- tag: prefix for tag-based search
- url: prefix for direct model lookup
- Standard search as fallback
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Literal, Dict, Any
from pathlib import Path
import re

from src.clients.civitai_client import CivitaiClient
from src.utils.media_detection import detect_media_type, get_video_thumbnail_url
from config.settings import get_config


# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


class ModelPreview(BaseModel):
    """Model preview media (image or video)."""
    model_config = ConfigDict(protected_namespaces=())
    
    url: str
    nsfw: bool
    width: Optional[int] = None
    height: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None
    
    # Media type: 'image', 'video', or 'unknown'
    # Backend detects this from URL, frontend uses it for rendering
    media_type: Literal['image', 'video', 'unknown'] = 'image'
    
    # Video-specific fields
    duration: Optional[float] = None  # seconds
    has_audio: Optional[bool] = None
    thumbnail_url: Optional[str] = None


def create_model_preview(img: Dict[str, Any]) -> 'ModelPreview':
    """
    Create a ModelPreview from Civitai image data.
    Detects media type (image vs video) from URL.
    """
    url = img.get("url", "")
    
    # Detect media type from URL
    media_info = detect_media_type(url, use_head_request=False)
    media_type = media_info.type.value  # 'image', 'video', or 'unknown'
    
    # Get thumbnail for videos
    thumbnail_url = None
    if media_type == 'video':
        thumbnail_url = get_video_thumbnail_url(url)
    
    return ModelPreview(
        url=url,
        nsfw=img.get("nsfw", False) or img.get("nsfwLevel", 0) >= 2,
        width=img.get("width"),
        height=img.get("height"),
        meta=img.get("meta"),
        media_type=media_type,
        thumbnail_url=thumbnail_url,
    )


class ModelFile(BaseModel):
    """Model file info."""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    name: str
    size_kb: Optional[float] = None
    download_url: Optional[str] = None
    hash_autov2: Optional[str] = None
    hash_sha256: Optional[str] = None


class ModelVersion(BaseModel):
    """Model version info."""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    name: str
    base_model: Optional[str] = None
    download_url: Optional[str] = None
    file_size: Optional[int] = None
    trained_words: List[str] = []
    files: List[ModelFile] = []
    published_at: Optional[str] = None


class CivitaiModelResult(BaseModel):
    """Civitai model info for search results."""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    name: str
    description: Optional[str] = None
    type: str
    nsfw: bool
    tags: List[str] = []
    creator: Optional[str] = None
    stats: dict = {}
    versions: List[ModelVersion] = []
    previews: List[ModelPreview] = []


class SearchResult(BaseModel):
    """Search results."""
    model_config = ConfigDict(protected_namespaces=())
    
    items: List[CivitaiModelResult]
    total: int
    page: int
    page_size: int
    next_cursor: Optional[str] = None


class ModelDetail(BaseModel):
    """Full model details for modal view."""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    name: str
    description: Optional[str] = None
    type: str
    nsfw: bool
    tags: List[str] = []
    creator: Optional[str] = None
    trained_words: List[str] = []
    base_model: Optional[str] = None
    versions: List[ModelVersion] = []
    previews: List[ModelPreview] = []
    stats: dict = {}
    # Model info table fields
    download_count: Optional[int] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    published_at: Optional[str] = None
    hash_autov2: Optional[str] = None
    civitai_air: Optional[str] = None
    # Generation parameters from examples
    example_params: Optional[Dict[str, Any]] = None


def _parse_search_query(query: str) -> tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Parse search query for special prefixes.
    
    Returns: (clean_query, tag, model_id)
    - tag: if query starts with "tag:"
    - model_id: if query starts with "url:" or is a Civitai URL
    """
    if not query:
        return None, None, None
    
    query = query.strip()
    
    # Check for tag: prefix
    if query.lower().startswith("tag:"):
        tag = query[4:].strip()
        return None, tag, None
    
    # Check for url: prefix or direct URL
    if query.lower().startswith("url:"):
        url = query[4:].strip()
    elif query.startswith("https://civitai.com") or query.startswith("http://civitai.com"):
        url = query
    else:
        # Regular query
        return query, None, None
    
    # Parse Civitai URL to get model ID
    model_id = None
    
    # Pattern: /models/12345 or /models/12345/...
    match = re.search(r'/models/(\d+)', url)
    if match:
        model_id = int(match.group(1))
    
    return None, None, model_id


@router.get("/search", response_model=SearchResult)
async def search_models(
    query: Optional[str] = Query(None, description="Search query (supports tag: and url: prefixes)"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    username: Optional[str] = Query(None, description="Filter by username"),
    types: Optional[str] = Query(None, description="Model types (comma-separated)"),
    nsfw: Optional[bool] = Query(None, description="Include NSFW"),
    sort: Optional[str] = Query(None, description="Sort order"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Search Civitai models.
    
    Special prefixes:
    - tag:anime - Search by tag
    - url:https://civitai.com/models/12345 - Direct model lookup
    - https://civitai.com/models/12345 - Direct URL also works
    """
    logger.info(f"[SEARCH] query={query}, tag={tag}, types={types}, nsfw={nsfw}, cursor={cursor}")
    
    config = get_config()
    client = CivitaiClient(api_key=config.api.civitai_token)
    
    # Parse query for special prefixes
    clean_query, tag_from_query, model_id = _parse_search_query(query)
    logger.info(f"[SEARCH] Parsed: clean_query={clean_query}, tag_from_query={tag_from_query}, model_id={model_id}")
    
    # If we got a model ID from URL, return that single model
    if model_id:
        try:
            logger.info(f"[SEARCH] Fetching single model by ID: {model_id}")
            model_data = client.get_model(model_id)
            if not model_data:
                logger.warning(f"[SEARCH] Model {model_id} not found")
                return SearchResult(items=[], total=0, page=1, page_size=limit)
            
            # Convert to result format
            item = _convert_model_to_result(model_data)
            return SearchResult(
                items=[item],
                total=1,
                page=1,
                page_size=1,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch model: {str(e)}")
    
    # Use tag from query if provided
    if tag_from_query:
        tag = tag_from_query
        clean_query = None
    
    # Parse types
    type_list = types.split(",") if types else None
    
    # Set default sort
    if (clean_query or tag) and not sort:
        sort = "Highest Rated"
    elif not sort:
        sort = "Newest"
    
    try:
        results = client.search_models(
            query=clean_query,
            tag=tag,
            username=username,
            types=type_list,
            nsfw=nsfw,
            sort=sort,
            limit=limit,
            cursor=cursor,
        )
        
        items = []
        for model_data in results.get("items", []):
            item = _convert_model_to_result(model_data)
            if item:
                items.append(item)
        
        # Get next cursor from metadata
        next_cursor = results.get("metadata", {}).get("nextCursor")
        
        return SearchResult(
            items=items,
            total=results.get("metadata", {}).get("totalItems", len(items)),
            page=1,
            page_size=limit,
            next_cursor=next_cursor,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


def _convert_model_to_result(model_data: Dict[str, Any]) -> Optional[CivitaiModelResult]:
    """Convert raw API response to result model."""
    model_versions = model_data.get("modelVersions", [])
    
    # Skip models with no versions
    if not model_versions:
        return None
    
    versions = []
    previews = []
    
    # Get previews from first version
    first_version_images = model_versions[0].get("images", [])
    for img in first_version_images[:8]:
        previews.append(create_model_preview(img))
    
    for ver in model_versions:
        files = ver.get("files", [])
        primary_file = files[0] if files else {}
        
        # Get hashes
        hashes = primary_file.get("hashes", {})
        
        model_files = []
        for f in files:
            f_hashes = f.get("hashes", {})
            model_files.append(ModelFile(
                id=f.get("id", 0),
                name=f.get("name", ""),
                size_kb=f.get("sizeKB"),
                download_url=f.get("downloadUrl"),
                hash_autov2=f_hashes.get("AutoV2"),
                hash_sha256=f_hashes.get("SHA256"),
            ))
        
        versions.append(ModelVersion(
            id=ver.get("id", 0),
            name=ver.get("name", ""),
            base_model=ver.get("baseModel"),
            download_url=primary_file.get("downloadUrl"),
            file_size=int(primary_file.get("sizeKB", 0) * 1024) if primary_file.get("sizeKB") else None,
            trained_words=ver.get("trainedWords", []),
            files=model_files,
            published_at=ver.get("publishedAt"),
        ))
    
    return CivitaiModelResult(
        id=model_data.get("id", 0),
        name=model_data.get("name", ""),
        description=model_data.get("description", "")[:1000] if model_data.get("description") else None,
        type=model_data.get("type", ""),
        nsfw=model_data.get("nsfw", False),
        tags=model_data.get("tags", []),
        creator=model_data.get("creator", {}).get("username"),
        stats=model_data.get("stats", {}),
        versions=versions,
        previews=previews,
    )


@router.get("/model/{model_id}", response_model=ModelDetail)
async def get_model(model_id: int, version_id: Optional[int] = None):
    """Get full model details for modal view."""
    config = get_config()
    client = CivitaiClient(api_key=config.api.civitai_token)
    
    try:
        model_data = client.get_model(model_id)
        
        if not model_data:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
        
        # Get all previews
        previews = []
        trained_words = []
        base_model = None
        example_params = None
        hash_autov2 = None
        published_at = None
        
        versions = []
        for ver in model_data.get("modelVersions", []):
            files = ver.get("files", [])
            primary_file = files[0] if files else {}
            hashes = primary_file.get("hashes", {})
            
            # Build file list
            model_files = []
            for f in files:
                f_hashes = f.get("hashes", {})
                model_files.append(ModelFile(
                    id=f.get("id", 0),
                    name=f.get("name", ""),
                    size_kb=f.get("sizeKB"),
                    download_url=f.get("downloadUrl"),
                    hash_autov2=f_hashes.get("AutoV2"),
                    hash_sha256=f_hashes.get("SHA256"),
                ))
            
            versions.append(ModelVersion(
                id=ver.get("id", 0),
                name=ver.get("name", ""),
                base_model=ver.get("baseModel"),
                download_url=primary_file.get("downloadUrl"),
                file_size=int(primary_file.get("sizeKB", 0) * 1024) if primary_file.get("sizeKB") else None,
                trained_words=ver.get("trainedWords", []),
                files=model_files,
                published_at=ver.get("publishedAt"),
            ))
            
            # Collect previews from all versions
            for img in ver.get("images", []):
                if len(previews) < 50:
                    meta = img.get("meta", {})
                    previews.append(create_model_preview(img))
                    
                    # Get example params from first image with meta
                    if not example_params and meta:
                        example_params = {
                            "sampler": meta.get("sampler"),
                            "steps": meta.get("steps"),
                            "cfg_scale": meta.get("cfgScale"),
                            "clip_skip": meta.get("clipSkip"),
                            "seed": meta.get("seed"),
                        }
            
            # Collect trained words
            trained_words.extend(ver.get("trainedWords", []))
            
            # Get base model and hash from first/selected version
            if not base_model or (version_id and ver.get("id") == version_id):
                base_model = ver.get("baseModel")
                hash_autov2 = hashes.get("AutoV2")
                published_at = ver.get("publishedAt")
        
        # Get stats
        stats = model_data.get("stats", {})
        
        return ModelDetail(
            id=model_data.get("id", 0),
            name=model_data.get("name", ""),
            description=model_data.get("description"),
            type=model_data.get("type", ""),
            nsfw=model_data.get("nsfw", False),
            tags=model_data.get("tags", []),
            creator=model_data.get("creator", {}).get("username"),
            trained_words=list(set(trained_words)),
            base_model=base_model,
            versions=versions,
            previews=previews,
            stats=stats,
            download_count=stats.get("downloadCount"),
            rating=stats.get("rating"),
            rating_count=stats.get("ratingCount"),
            published_at=published_at,
            hash_autov2=hash_autov2,
            civitai_air=f"civitai: {model_id} @ {versions[0].id if versions else 0}",
            example_params=example_params,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model: {str(e)}")


@router.get("/model/{model_id}/version/{version_id}")
async def get_model_version(model_id: int, version_id: int):
    """Get specific model version details."""
    config = get_config()
    client = CivitaiClient(api_key=config.api.civitai_token)
    
    try:
        version_data = client.get_model_version(version_id)
        
        if not version_data:
            raise HTTPException(status_code=404, detail=f"Version not found: {version_id}")
        
        return version_data
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get version: {str(e)}")


# ============================================================================
# Base Model (Checkpoint) Search - Generic API for multiple sources
# ============================================================================

class BaseModelResult(BaseModel):
    """Base model search result - unified format for all sources."""
    model_config = ConfigDict(protected_namespaces=())
    
    model_id: str  # String to support different ID formats
    model_name: str
    creator: Optional[str] = None
    download_count: int = 0
    version_id: Optional[str] = None
    version_name: Optional[str] = None
    file_name: str
    size_kb: int = 0
    size_gb: Optional[float] = None
    download_url: str
    base_model: Optional[str] = None
    source: str  # 'civitai', 'huggingface', 'local', etc.
    source_url: Optional[str] = None  # Link to model page


class BaseModelSearchResponse(BaseModel):
    """Response for base model search."""
    model_config = ConfigDict(protected_namespaces=())
    
    results: List[BaseModelResult]
    total_found: int
    source: str
    search_query: str
    search_method: Optional[str] = None  # 'tag', 'query', etc.


def normalize_string(s: str) -> str:
    """Normalize string for comparison."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def pick_best_version(model: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pick the best version (most downloaded + newest)."""
    versions = model.get("modelVersions") or []
    if not versions:
        return None
    
    def sort_key(v: Dict[str, Any]):
        dl = int((v.get("stats") or {}).get("downloadCount") or 0)
        created = str(v.get("createdAt") or "")
        return (dl, created)
    
    return sorted(versions, key=sort_key, reverse=True)[0]


def pick_primary_file(version: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pick the primary file from version."""
    files = version.get("files") or []
    if not files:
        return None
    
    # Prefer primary file
    for f in files:
        if f.get("primary") is True:
            return f
    
    # Fallback to safetensors
    for f in files:
        if str(f.get("name", "")).lower().endswith(".safetensors"):
            return f
    
    return files[0]


def get_size_kb(f: Optional[Dict[str, Any]]) -> int:
    """Get file size in KB."""
    if not f:
        return 0
    v = f.get("sizeKb", f.get("sizeKB", 0))
    try:
        return int(v or 0)
    except Exception:
        return 0


# -----------------------------------------------------------------------------
# Civitai Search Implementation
# -----------------------------------------------------------------------------

def _search_civitai_checkpoints(
    query: str,
    prefer_name: Optional[str],
    limit: int,
    max_batches: int,
    api_token: Optional[str],
) -> BaseModelSearchResponse:
    """Search Civitai for checkpoints using cursor pagination."""
    import requests
    from urllib.parse import urlparse, parse_qsl
    
    logger.info(f"[civitai-search] Searching for: {query}")
    print(f"[civitai-search] Searching for: {query}")
    
    API_URL = "https://civitai.com/api/v1/models"
    
    def get_headers():
        h = {"User-Agent": "synapse-resolver/1.0", "Accept": "application/json"}
        if api_token:
            h["Authorization"] = f"Bearer {api_token}"
        return h
    
    def fetch_with_cursor(params: Dict[str, Any], max_batches: int) -> List[Dict[str, Any]]:
        """Fetch results using cursor-based pagination."""
        url = API_URL
        all_items: List[Dict[str, Any]] = []
        
        for batch_num in range(max_batches):
            logger.debug(f"[civitai-search] Fetching batch {batch_num + 1}")
            print(f"[civitai-search] Fetching batch {batch_num + 1}, url={url}")
            
            try:
                resp = requests.get(url, params=params, headers=get_headers(), timeout=30)
                
                if resp.status_code >= 400:
                    logger.warning(f"[civitai-search] API error: {resp.status_code}")
                    print(f"[civitai-search] API error: {resp.status_code} - {resp.text[:200]}")
                    break
                
                data = resp.json()
                items = data.get("items") or []
                all_items.extend(items)
                
                print(f"[civitai-search] Got {len(items)} items in batch, total: {len(all_items)}")
                
                # Check for next page (cursor pagination)
                meta = data.get("metadata") or {}
                next_page = meta.get("nextPage")
                
                if not next_page:
                    break
                
                # Parse next page URL for cursor
                parsed = urlparse(next_page)
                url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                params = dict(parse_qsl(parsed.query, keep_blank_values=True))
                
            except requests.RequestException as e:
                logger.error(f"[civitai-search] Request failed: {e}")
                print(f"[civitai-search] Request failed: {e}")
                break
        
        return all_items
    
    # Build search params - try tag first for known base models
    base_params: Dict[str, Any] = {
        "types": "Checkpoint",
        "sort": "Most Downloaded",
        "period": "AllTime",
        "primaryFileOnly": "true",
        "limit": "100",
    }
    
    # Extract potential tag from query
    search_method = "query"
    tag_candidates = ["Illustrious", "Pony", "SDXL", "SD 1.5", "SD1.5", "Flux", "AuraFlow"]
    for tag in tag_candidates:
        if tag.lower() in query.lower():
            base_params["tag"] = tag
            search_method = "tag"
            print(f"[civitai-search] Using tag search: {tag}")
            break
    
    if search_method == "query":
        base_params["query"] = query
        print(f"[civitai-search] Using query search: {query}")
    
    # Fetch items
    items = fetch_with_cursor(base_params, max_batches)
    
    print(f"[civitai-search] Total items fetched: {len(items)}")
    
    if not items:
        return BaseModelSearchResponse(
            results=[],
            total_found=0,
            source="civitai",
            search_query=query,
            search_method=search_method,
        )
    
    # Process results
    prefer_normalized = normalize_string(prefer_name or query)
    results: List[BaseModelResult] = []
    
    for item in items:
        version = pick_best_version(item)
        if not version:
            continue
        
        file = pick_primary_file(version)
        if not file:
            continue
        
        size_kb = get_size_kb(file)
        size_gb = round(size_kb / 1024 / 1024, 2) if size_kb > 0 else None
        
        download_url = version.get("downloadUrl") or f"https://civitai.com/api/download/models/{version.get('id')}"
        
        results.append(BaseModelResult(
            model_id=str(item.get("id", 0)),
            model_name=item.get("name", "Unknown"),
            creator=(item.get("creator") or {}).get("username"),
            download_count=int((item.get("stats") or {}).get("downloadCount") or 0),
            version_id=str(version.get("id", "")),
            version_name=version.get("name", ""),
            file_name=file.get("name", ""),
            size_kb=size_kb,
            size_gb=size_gb,
            download_url=download_url,
            base_model=version.get("baseModel"),
            source="civitai",
            source_url=f"https://civitai.com/models/{item.get('id')}",
        ))
    
    # Sort: prefer matching name first, then by downloads
    def sort_key(r: BaseModelResult):
        name_match = 0 if prefer_normalized and prefer_normalized in normalize_string(r.model_name) else 1
        return (name_match, -r.download_count, r.model_name.lower())
    
    results.sort(key=sort_key)
    results = results[:limit]
    
    print(f"[civitai-search] Returning {len(results)} results")
    
    return BaseModelSearchResponse(
        results=results,
        total_found=len(items),
        source="civitai",
        search_query=query,
        search_method=search_method,
    )


# -----------------------------------------------------------------------------
# Hugging Face Search Implementation
# -----------------------------------------------------------------------------

def _search_huggingface_checkpoints(
    query: str,
    prefer_name: Optional[str],
    limit: int,
    api_token: Optional[str],
) -> BaseModelSearchResponse:
    """Search Hugging Face for checkpoint models with proper file selection."""
    import requests
    
    logger.info(f"[huggingface-search] Searching for: {query}")
    print(f"[huggingface-search] Searching for: {query}")
    
    # Hugging Face Hub API
    API_URL = "https://huggingface.co/api/models"
    
    headers = {"Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    
    # Search parameters for diffusion models
    params = {
        "search": query,
        "filter": "diffusers",  # Filter for diffusion models
        "sort": "downloads",
        "direction": "-1",
        "limit": str(min(limit * 2, 100)),  # Fetch more, filter later
    }
    
    try:
        resp = requests.get(API_URL, params=params, headers=headers, timeout=30)
        
        if resp.status_code >= 400:
            logger.warning(f"[huggingface-search] API error: {resp.status_code}")
            print(f"[huggingface-search] API error: {resp.status_code}")
            return BaseModelSearchResponse(
                results=[],
                total_found=0,
                source="huggingface",
                search_query=query,
            )
        
        models = resp.json()
        print(f"[huggingface-search] Got {len(models)} models")
        
    except requests.RequestException as e:
        logger.error(f"[huggingface-search] Request failed: {e}")
        print(f"[huggingface-search] Request failed: {e}")
        return BaseModelSearchResponse(
            results=[],
            total_found=0,
            source="huggingface",
            search_query=query,
        )
    
    # Process results
    prefer_normalized = normalize_string(prefer_name or query)
    results: List[BaseModelResult] = []
    
    for model in models:
        model_id = model.get("id", "")  # e.g., "stabilityai/stable-diffusion-xl-base-1.0"
        
        # Fetch detailed file list from HF API
        files_url = f"https://huggingface.co/api/models/{model_id}"
        try:
            files_resp = requests.get(files_url, headers=headers, timeout=15)
            if files_resp.status_code == 200:
                model_detail = files_resp.json()
                siblings = model_detail.get("siblings") or []
            else:
                siblings = model.get("siblings") or []
        except Exception:
            siblings = model.get("siblings") or []
        
        # Find best safetensors file with preference order
        best_file = _select_best_hf_file(siblings)
        
        if not best_file:
            # No suitable file found, skip this model
            print(f"[huggingface-search] No suitable file for {model_id}")
            continue
        
        file_name = best_file.get("rfilename", "")
        
        # Construct download URL
        download_url = f"https://huggingface.co/{model_id}/resolve/main/{file_name}"
        
        # Get size if available
        size_bytes = best_file.get("size", 0)
        size_kb = size_bytes // 1024 if size_bytes else 0
        size_gb = round(size_kb / 1024 / 1024, 2) if size_kb > 0 else None
        
        results.append(BaseModelResult(
            model_id=model_id,
            model_name=model_id.split("/")[-1] if "/" in model_id else model_id,
            creator=model_id.split("/")[0] if "/" in model_id else None,
            download_count=model.get("downloads", 0),
            version_id=None,
            version_name=model.get("sha", "")[:8] if model.get("sha") else None,
            file_name=file_name,
            size_kb=size_kb,
            size_gb=size_gb,
            download_url=download_url,
            base_model=None,  # HF doesn't have this field directly
            source="huggingface",
            source_url=f"https://huggingface.co/{model_id}",
        ))
    
    # Sort by preference and downloads
    def sort_key(r: BaseModelResult):
        name_match = 0 if prefer_normalized and prefer_normalized in normalize_string(r.model_name) else 1
        return (name_match, -r.download_count, r.model_name.lower())
    
    results.sort(key=sort_key)
    results = results[:limit]
    
    print(f"[huggingface-search] Returning {len(results)} results")
    
    return BaseModelSearchResponse(
        results=results,
        total_found=len(models),
        source="huggingface",
        search_query=query,
    )


def _select_best_hf_file(siblings: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Select the best file from HuggingFace repo siblings.
    
    Priority order:
    1. safetensors with 'emaonly' in name
    2. safetensors with 'pruned' in name  
    3. safetensors with 'fp16' in name
    4. Any safetensors (not unet/vae/text_encoder parts)
    5. .ckpt files
    """
    if not siblings:
        return None
    
    safetensors_files = []
    ckpt_files = []
    
    for sib in siblings:
        filename = (sib.get("rfilename") or "").lower()
        
        # Skip component files (unet, vae, text_encoder)
        if any(x in filename for x in ["unet", "vae", "text_encoder", "tokenizer", "scheduler", "safety_checker"]):
            continue
        
        if filename.endswith(".safetensors"):
            safetensors_files.append(sib)
        elif filename.endswith(".ckpt"):
            ckpt_files.append(sib)
    
    # Score safetensors files by preference
    def score_file(sib: Dict[str, Any]) -> tuple:
        filename = (sib.get("rfilename") or "").lower()
        # Higher score = better
        emaonly = 1 if "emaonly" in filename or "ema-only" in filename else 0
        pruned = 1 if "pruned" in filename else 0
        fp16 = 1 if "fp16" in filename else 0
        size = sib.get("size", 0)  # Prefer larger files (more complete)
        return (emaonly, pruned, fp16, size)
    
    if safetensors_files:
        safetensors_files.sort(key=score_file, reverse=True)
        return safetensors_files[0]
    
    if ckpt_files:
        # Prefer emaonly/pruned ckpt files too
        ckpt_files.sort(key=score_file, reverse=True)
        return ckpt_files[0]
    
    return None


class HuggingFaceFile(BaseModel):
    """File info from HuggingFace repo."""
    filename: str
    size_bytes: int
    size_gb: Optional[float] = None
    download_url: str
    is_recommended: bool = False
    file_type: str  # 'safetensors', 'ckpt', 'other'


class HuggingFaceFilesResponse(BaseModel):
    """Response with files from HuggingFace repo."""
    repo_id: str
    files: List[HuggingFaceFile]
    recommended_file: Optional[str] = None
    has_suitable_files: bool = True


@router.get("/huggingface/files", response_model=HuggingFaceFilesResponse)
async def get_huggingface_files(
    repo_id: str = Query(..., description="HuggingFace repo ID (e.g., 'stabilityai/stable-diffusion-xl-base-1.0')"),
):
    """
    Get list of downloadable files from a HuggingFace repository.
    
    Returns files suitable for ComfyUI (safetensors, ckpt) with recommendation.
    """
    import requests
    
    logger.info(f"[huggingface-files] Getting files for: {repo_id}")
    print(f"[huggingface-files] Getting files for: {repo_id}")
    
    config = get_config()
    headers = {"Accept": "application/json"}
    if config.api.huggingface_token:
        headers["Authorization"] = f"Bearer {config.api.huggingface_token}"
    
    # Fetch model info with siblings
    api_url = f"https://huggingface.co/api/models/{repo_id}"
    
    try:
        resp = requests.get(api_url, headers=headers, timeout=30)
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=f"HuggingFace API error: {resp.status_code}")
        
        model_data = resp.json()
        siblings = model_data.get("siblings") or []
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from HuggingFace: {str(e)}")
    
    # Filter and categorize files
    files: List[HuggingFaceFile] = []
    
    # Skip component files
    skip_patterns = ["unet", "vae", "text_encoder", "tokenizer", "scheduler", "safety_checker", "feature_extractor"]
    
    for sib in siblings:
        filename = sib.get("rfilename", "")
        filename_lower = filename.lower()
        
        # Skip hidden, config, and component files
        if filename.startswith(".") or filename.endswith((".json", ".txt", ".md", ".py", ".bin")):
            continue
        if any(pattern in filename_lower for pattern in skip_patterns):
            continue
        
        # Determine file type
        if filename_lower.endswith(".safetensors"):
            file_type = "safetensors"
        elif filename_lower.endswith(".ckpt"):
            file_type = "ckpt"
        else:
            continue  # Skip other files
        
        size_bytes = sib.get("size", 0)
        size_gb = round(size_bytes / 1024 / 1024 / 1024, 2) if size_bytes > 0 else None
        
        download_url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
        
        files.append(HuggingFaceFile(
            filename=filename,
            size_bytes=size_bytes,
            size_gb=size_gb,
            download_url=download_url,
            is_recommended=False,
            file_type=file_type,
        ))
    
    # Select recommended file
    recommended = _select_best_hf_file(siblings)
    recommended_filename = recommended.get("rfilename") if recommended else None
    
    # Mark recommended file
    for f in files:
        if f.filename == recommended_filename:
            f.is_recommended = True
            break
    
    # Sort: recommended first, then safetensors, then by size
    def sort_files(f: HuggingFaceFile):
        return (
            0 if f.is_recommended else 1,
            0 if f.file_type == "safetensors" else 1,
            -(f.size_bytes or 0)
        )
    
    files.sort(key=sort_files)
    
    has_suitable = len(files) > 0
    
    print(f"[huggingface-files] Found {len(files)} suitable files, recommended: {recommended_filename}")
    
    return HuggingFaceFilesResponse(
        repo_id=repo_id,
        files=files,
        recommended_file=recommended_filename,
        has_suitable_files=has_suitable,
    )


# -----------------------------------------------------------------------------
# Unified Search Endpoint
# -----------------------------------------------------------------------------

@router.get("/base-models/search", response_model=BaseModelSearchResponse)
async def search_base_models(
    query: str = Query(..., min_length=2, description="Search query"),
    source: str = Query("civitai", description="Source: civitai, huggingface"),
    prefer_name: Optional[str] = Query(None, description="Prefer this name in results"),
    limit: int = Query(20, ge=1, le=50, description="Max results to return"),
    max_batches: int = Query(3, ge=1, le=5, description="Max API batches (Civitai only)"),
):
    """
    Search for base models (checkpoints) from various sources.
    
    Supported sources:
    - civitai: Civitai.com (uses cursor pagination, supports tag search)
    - huggingface: Hugging Face Hub (diffusers models)
    
    Returns unified format regardless of source.
    """
    logger.info(f"[base-models/search] source={source}, query={query}")
    print(f"[base-models/search] source={source}, query={query}")
    
    config = get_config()
    
    if source == "civitai":
        return _search_civitai_checkpoints(
            query=query,
            prefer_name=prefer_name,
            limit=limit,
            max_batches=max_batches,
            api_token=config.api.civitai_token,
        )
    
    elif source == "huggingface":
        return _search_huggingface_checkpoints(
            query=query,
            prefer_name=prefer_name,
            limit=limit,
            api_token=config.api.huggingface_token,
        )
    
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown source: {source}. Supported: civitai, huggingface"
        )


# ============================================================================
# CivArchive.com Search - Better search quality via external indexer
# ============================================================================

class CivArchiveResult(BaseModel):
    """CivArchive search result with Civitai data."""
    model_config = ConfigDict(protected_namespaces=())
    
    model_id: int
    model_name: str
    model_type: Optional[str] = None
    base_model: Optional[str] = None
    version_id: Optional[int] = None
    version_name: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    download_url: Optional[str] = None
    civitai_url: Optional[str] = None
    civarchive_url: Optional[str] = None
    creator: Optional[str] = None
    download_count: Optional[int] = None
    rating: Optional[float] = None
    nsfw: bool = False
    # CHANGED: Use List[ModelPreview] instead of preview_url: str
    # This matches the format of normal Civitai search results
    previews: List[ModelPreview] = []


class CivArchiveSearchResponse(BaseModel):
    """Response from CivArchive search."""
    model_config = ConfigDict(protected_namespaces=())

    results: List[CivArchiveResult]
    total_found: int
    query: str
    # Phase 5: Pagination support
    has_more: bool = False
    current_page: int = 1


def _search_civarchive(
    query: str,
    limit: int = 20,
    page: int = 1,
) -> tuple[List[str], bool]:
    """
    Search CivArchive.com and return list of model URLs.

    ONE page per request - simulates normal user behavior.
    User clicks "Load More" → next page is fetched.

    Args:
        query: Search query
        limit: Max results to return
        page: CivArchive page number (1-indexed)

    Returns:
        Tuple of (model_urls, has_more)
    """
    import requests
    from urllib.parse import urljoin

    # Full browser-like headers to avoid being blocked
    # Note: Do NOT include Accept-Encoding - let requests handle it automatically
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    search_url = f"https://civarchive.com/search?q={query.replace(' ', '+')}&rating=all&page={page}"
    logger.info(f"[civarchive] Searching page {page}: {search_url}")

    try:
        # Use session for connection pooling
        session = requests.Session()
        session.headers.update(headers)
        resp = session.get(search_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"[civarchive] Search failed page {page}: {e}")
        print(f"[civarchive] Search failed page {page}: {e}")
        return [], False

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return [], False

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find all model links - use *= selector for robustness
    links: List[str] = []
    for a in soup.select('a[href*="/models/"]'):
        href = a.get("href") or ""
        if not re.match(r"^/models/[0-9]+", href):
            continue
        full_url = urljoin("https://civarchive.com", href)
        if full_url not in links:
            links.append(full_url)

    logger.info(f"[civarchive] Found {len(links)} model links on page {page}")

    # has_more = True if we found results (there might be more pages)
    has_more = len(links) > 0

    return links[:limit * 3], has_more


def _extract_civitai_id_from_civarchive(civarchive_url: str) -> Optional[int]:
    """Extract Civitai model ID from CivArchive page."""
    import requests
    import json

    # Full browser-like headers to avoid being blocked
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }

    try:
        session = requests.Session()
        session.headers.update(headers)
        resp = session.get(civarchive_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"[civarchive] Failed to fetch {civarchive_url}: {e}")
        return None
    
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Try to extract from __NEXT_DATA__
    next_data_tag = soup.find("script", id="__NEXT_DATA__")
    if next_data_tag and next_data_tag.string:
        try:
            data = json.loads(next_data_tag.string)
            # Primary path
            version = data.get("props", {}).get("pageProps", {}).get("model", {}).get("version", {})
            model_id = version.get("civitai_model_id")
            if model_id:
                return int(model_id)
            # Fallback path
            model = data.get("props", {}).get("pageProps", {}).get("model", {})
            model_id = model.get("civitai_model_id")
            if model_id:
                return int(model_id)
        except Exception:
            pass
    
    # Fallback: Look for civitai.com links in HTML
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if "civitai.com/models/" in href:
            match = re.search(r"/models/(\d+)", href)
            if match:
                return int(match.group(1))
    
    # Fallback: Regex in full HTML
    match = re.search(r"civitai\.com/models/(\d+)", resp.text)
    if match:
        return int(match.group(1))
    
    return None


def _fetch_civitai_model_for_civarchive(model_id: int, civarchive_url: str, client: CivitaiClient) -> Optional[CivArchiveResult]:
    """
    Fetch model data from Civitai API for CivArchive result.
    
    IMPORTANT: Uses create_model_preview() to properly detect media type (image vs video).
    This ensures consistency with normal Civitai search results.
    """
    try:
        model_data = client.get_model(model_id)
        if not model_data:
            return None
        
        versions = model_data.get("modelVersions") or []
        version = versions[0] if versions else {}
        
        # Get primary file
        files = version.get("files") or []
        primary_file = None
        for f in files:
            if f.get("primary"):
                primary_file = f
                break
        if not primary_file and files:
            primary_file = files[0]
        
        file_name = primary_file.get("name") if primary_file else None
        file_size = None
        if primary_file:
            size_kb = primary_file.get("sizeKB") or primary_file.get("sizeKb")
            if size_kb:
                file_size = int(float(size_kb) * 1024)
        
        # CHANGED: Use create_model_preview() for proper media type detection
        # This is the same approach as _convert_model_to_result() for normal search
        previews = []
        first_version_images = version.get("images") or []
        for img in first_version_images[:8]:  # Max 8 previews, same as normal search
            previews.append(create_model_preview(img))
        
        stats = model_data.get("stats") or {}
        
        return CivArchiveResult(
            model_id=model_data.get("id"),
            model_name=model_data.get("name", "Unknown"),
            model_type=model_data.get("type"),
            base_model=version.get("baseModel"),
            version_id=version.get("id"),
            version_name=version.get("name"),
            file_name=file_name,
            file_size=file_size,
            download_url=version.get("downloadUrl"),
            civitai_url=f"https://civitai.com/models/{model_id}",
            civarchive_url=civarchive_url,
            creator=(model_data.get("creator") or {}).get("username"),
            download_count=stats.get("downloadCount"),
            rating=stats.get("rating"),
            nsfw=model_data.get("nsfw", False),
            # CHANGED: Pass previews list instead of single preview_url
            previews=previews,
        )
        
    except Exception as e:
        logger.warning(f"[civarchive] Failed to fetch model {model_id}: {e}")
        return None


@router.get("/search-civarchive", response_model=CivArchiveSearchResponse)
async def search_via_civarchive(
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=30, description="Max results"),
    page: int = Query(1, ge=1, le=50, description="Page number for pagination"),
):
    """
    Search models via CivArchive.com for better search quality.

    CivArchive indexes Civitai descriptions and provides better full-text search.
    One page per request - click "Load More" for next page.

    Phase 5: Added pagination support with page and pages_per_request parameters.
    - page=1, pages_per_request=3 → fetches CivArchive pages 1-3
    - page=2, pages_per_request=3 → fetches CivArchive pages 4-6
    - etc.

    Returns results with full preview information including video detection.
    """
    import concurrent.futures
    
    logger.info(f"[civarchive] Starting search for: {query}")
    print(f"[civarchive] Starting parallel search for: {query}")
    
    config = get_config()
    client = CivitaiClient(api_key=config.api.civitai_token)
    
    # Step 1: Search CivArchive - ONE page per request
    civarchive_urls, has_more = _search_civarchive(
        query,
        limit=limit * 3,
        page=page,
    )

    if not civarchive_urls:
        return CivArchiveSearchResponse(
            results=[],
            total_found=0,
            query=query,
            has_more=False,
            current_page=page,
        )
    
    print(f"[civarchive] Extracting Civitai IDs from {len(civarchive_urls)} URLs (parallel)...")

    # Step 2: Extract Civitai IDs in parallel
    url_to_id: Dict[str, Optional[int]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(_extract_civitai_id_from_civarchive, url): url for url in civarchive_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                model_id = future.result()
                url_to_id[url] = model_id
                if model_id:
                    print(f"[civarchive] Extracted ID {model_id} from {url}")
            except Exception as e:
                logger.warning(f"[civarchive] Failed to extract ID from {url}: {e}")
                url_to_id[url] = None
    
    # Filter valid IDs
    valid_items = [(url, mid) for url, mid in url_to_id.items() if mid is not None]
    seen_ids: set = set()
    unique_items = []
    for url, mid in valid_items:
        if mid not in seen_ids:
            seen_ids.add(mid)
            unique_items.append((url, mid))
    
    unique_items = unique_items[:limit]
    print(f"[civarchive] Found {len(unique_items)} unique model IDs, fetching from Civitai (parallel)...")
    
    # Step 3: Fetch model data from Civitai in parallel
    results: List[CivArchiveResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_item = {
            executor.submit(_fetch_civitai_model_for_civarchive, mid, url, client): (url, mid) 
            for url, mid in unique_items
        }
        for future in concurrent.futures.as_completed(future_to_item):
            url, mid = future_to_item[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
                    print(f"[civarchive] Fetched: {result.model_name} (ID: {mid})")
            except Exception as e:
                logger.warning(f"[civarchive] Failed to fetch model {mid}: {e}")
    
    # Sort by download count
    results.sort(key=lambda x: x.download_count or 0, reverse=True)
    
    print(f"[civarchive] Returning {len(results)} results")
    
    return CivArchiveSearchResponse(
        results=results,
        total_found=len(results),
        query=query,
        has_more=has_more,
        current_page=page,
    )
