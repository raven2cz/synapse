import requests
import json
import sys

def find_video():
    url = "https://civitai.com/api/v1/models?limit=20&types=Checkpoint&sort=Most Downloaded"
    print(f"Fetching {url}...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        items = data.get("items", [])
        print(f"Scanned {len(items)} items.")
        
        for item in items:
            for version in item.get("modelVersions", []):
                for img in version.get("images", []):
                    # Check for video indicators
                    meta = img.get("meta")
                    url = img.get("url")
                    
                    # Heuristic for video:
                    # In API v1, videos might just be images with type='video' if that exists, 
                    # but usually they are identified by anim=true or similar in URL, 
                    # or it's just a gif/mp4.
                    
                    if "anim=true" in url or ".mp4" in url or ".webm" in url or img.get("type") == "video":
                        print("\n!!! FOUND VIDEO/ANIMATED !!!")
                        print(f"URL: {url}")
                        print(f"Details: {img}")
                        return url
                        
        print("No obvious videos found in top 20.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_video()
