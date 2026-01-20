import requests
import json
import sys

def debug_tifa():
    url = "https://civitai.com/api/v1/models"
    params = {
        "tag": "tifa",
        "limit": 5, # Fetch more items
        "sort": "Highest Rated" 
    }
    
    print(f"Fetching {url} with params {params}...")
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        items = data.get('items', [])
        if not items:
            print("No items found.")
            return

        for idx, item in enumerate(items):
            print(f"\nItem {idx+1}: {item.get('name')} (ID: {item.get('id')})")
            
            model_versions = item.get('modelVersions', [])
            if not model_versions:
                print("  No model versions.")
                continue
                
            # Check first version with images
            found_image = False
            for v in model_versions:
                images = v.get('images', [])
                if images:
                    first_image = images[0]
                    print(f"  Version {v.get('id')}: Found {len(images)} images.")
                    print(f"  First Image Type: {first_image.get('type')}") # 'image' or 'video'?
                    print(f"  First Image URL: {first_image.get('url')}")
                    print(f"  Meta: {first_image.get('meta')}")
                    
                    if first_image.get('type') == 'video':
                         print("  *** FOUND A VIDEO ***")
                    
                    found_image = True
                    break # Stop after finding first version with images (like UI usually does)
            
            if not found_image:
                print("  No images found in any version.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_tifa()
