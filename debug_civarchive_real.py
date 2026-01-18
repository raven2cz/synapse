import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

def _extract_civitai_id_from_civarchive(civarchive_url: str) -> int | None:
    """Extract Civitai model ID from CivArchive page."""
    import requests
    import json
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        resp = requests.get(civarchive_url, headers=headers, timeout=15)
        # resp.raise_for_status() 
    except Exception as e:
        print(f"Failed to fetch {civarchive_url}: {e}")
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

def debug_search(query: str):
    print(f"DEBUG: Searching for '{query}'...")
    
    search_url = f"https://civarchive.com/search?q={query.replace(' ', '+')}&rating=all&page=2"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    print(f"Fetching: {search_url}")
    
    try:
        resp = requests.get(search_url, headers=headers, timeout=30)
        print(f"Status Code: {resp.status_code}")
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # DEBUG: Print structure of first few links to verify selector
        print("\n--- HTML LINK ANALYSIS ---")
        all_links = soup.find_all("a")
        print(f"Total <a> tags: {len(all_links)}")
        
        # Test current selector
        target_links = []
        for a in soup.select('a[href^="/models/"]'):
            href = a.get("href") or ""
            if not re.match(r"^/models/[0-9]+", href):
                continue
            full_url = urljoin("https://civarchive.com", href)
            if full_url not in target_links:
                target_links.append(full_url)
        
        print(f"\nSelector 'a[href^=\"/models/\"]' found: {len(target_links)} specific model links")
        
        print("\n--- TESTING EXTRACTION (All found) ---")
        unique_ids = set()
        success_count = 0
        
        # Use simple sequential processing for debug script
        for i, link in enumerate(target_links):
            print(f"[{i}] Extracting from {link} ... ", end="", flush=True)
            mid = _extract_civitai_id_from_civarchive(link)
            if mid:
                print(f"SUCCESS -> ID: {mid}")
                success_count += 1
                unique_ids.add(mid)
            else:
                print("FAILED")
        
        print(f"\nStats:")
        print(f"  Total Links Processed: {len(target_links)}")
        print(f"  Successful Extractions: {success_count}")
        print(f"  Unique Model IDs: {len(unique_ids)}")
        print(f"  Unique IDs: {unique_ids}")

            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    debug_search("wan 2.2 nsfw")
