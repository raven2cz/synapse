import requests
import json
import sys

def debug_civitai(version_id):
    url = f"https://civitai.com/api/v1/model-versions/{version_id}"
    print(f"Fetching {url}...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        images = data.get("images", [])
        print(f"Found {len(images)} images.")
        
        if images:
            print("\n--- Image 0 Structure ---")
            img = images[0]
            for k, v in img.items():
                print(f"{k}: {type(v).__name__} = {str(v)[:100]}")
            
            print("\n--- NSFW/Meta Checking ---")
            for i, img in enumerate(images[:5]):
                nsfw_val = img.get("nsfw")
                nsfw_level = img.get("nsfwLevel")
                meta = img.get("meta")
                print(f"Image {i}: nsfw={nsfw_val} (type {type(nsfw_val)}), nsfwLevel={nsfw_level}, meta={'PRESENT' if meta else 'NONE'}")
                if meta:
                     print(f"  Meta keys: {list(meta.keys())}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_civitai(2206450)
