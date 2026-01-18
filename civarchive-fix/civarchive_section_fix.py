# ============================================================================
# CivArchive.com Search - Better search quality via external indexer
# ============================================================================
# 
# INSTRUCTIONS: Replace the entire CivArchive section in browse.py with this code.
# The section starts at "# ============================================================================"
# "# CivArchive.com Search" and ends before the next major section or EOF.
#
# Key changes:
# 1. CivArchiveResult now has `previews: List[ModelPreview]` instead of `preview_url: str`
# 2. _fetch_civitai_model_for_civarchive uses create_model_preview() - same as normal search
# 3. This ensures videos are properly detected with media_type, thumbnail_url, etc.
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


def _search_civarchive(query: str, limit: int = 20) -> List[str]:
    """Search CivArchive.com and return list of model URLs."""
    import requests
    from urllib.parse import urljoin
    
    search_url = f"https://civarchive.com/search?q={query.replace(' ', '+')}&rating=all"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    logger.info(f"[civarchive] Searching: {search_url}")
    print(f"[civarchive] Searching: {search_url}")
    
    try:
        resp = requests.get(search_url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"[civarchive] Search failed: {e}")
        print(f"[civarchive] Search failed: {e}")
        return []
    
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("[civarchive] beautifulsoup4 not installed")
        print("[civarchive] beautifulsoup4 not installed - pip install beautifulsoup4")
        return []
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Find all model links
    links: List[str] = []
    for a in soup.select('a[href^="/models/"]'):
        href = a.get("href") or ""
        if not re.match(r"^/models/[0-9]+", href):
            continue
        full_url = urljoin("https://civarchive.com", href)
        if full_url not in links:
            links.append(full_url)
    
    print(f"[civarchive] Found {len(links)} model links")
    return links[:limit]


def _extract_civitai_id_from_civarchive(civarchive_url: str) -> Optional[int]:
    """Extract Civitai model ID from CivArchive page."""
    import requests
    import json
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        resp = requests.get(civarchive_url, headers=headers, timeout=15)
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
):
    """
    Search models via CivArchive.com for better search quality.
    
    CivArchive indexes Civitai descriptions and provides better full-text search.
    Uses parallel processing for faster results.
    
    Returns results with full preview information including video detection.
    """
    import concurrent.futures
    
    logger.info(f"[civarchive] Starting search for: {query}")
    print(f"[civarchive] Starting parallel search for: {query}")
    
    config = get_config()
    client = CivitaiClient(api_key=config.api.civitai_token)
    
    # Step 1: Search CivArchive
    civarchive_urls = _search_civarchive(query, limit=limit * 2)
    
    if not civarchive_urls:
        return CivArchiveSearchResponse(results=[], total_found=0, query=query)
    
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
    )
