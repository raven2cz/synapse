import requests

def get_civitai_thumbnail_url(url, width=450):
    if not url or 'civitai.com' not in url:
        return url
    
    try:
        # Simulate the JS logic roughly
        if 'width=' in url:
            # Replace param
             # Simplified for python - just append or replace
             pass
        
        # JS logic: 
        # const newParams = `anim=false,transcode=true,width=${width},optimized=true`
        # Inserts it into path.
        
        # Example input: https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/30832252-cc46-454a-4100-b98ece111c00/original=true/209756.jpeg
        # Target: https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/30832252-cc46-454a-4100-b98ece111c00/anim=false,transcode=true,width=450,optimized=true/209756.jpeg
        
        parts = url.split('/')
        # Find where to insert. Usually before the filename.
        # In JS: "if (paramsIndex >= 0) ... else if (pathParts.length >= 3) pathParts.splice(-1, 0, newParams)"
        
        new_params = f"anim=false,transcode=true,width={width},optimized=true"
        
        # Check for existing params like 'original=true'
        params_idx = -1
        for i, p in enumerate(parts):
            if '=' in p or p.startswith('width'):
                params_idx = i
                break
        
        if params_idx >= 0:
            parts[params_idx] = new_params
        elif len(parts) >= 3:
            parts.insert(-1, new_params)
            
        return "/".join(parts)
        
    except:
        return url

def check_urls():
    urls = [
        "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/30832252-cc46-454a-4100-b98ece111c00/original=true/209756.jpeg", # Item 2
        "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/557d0241-fd12-4900-12b9-72ccede5f700/original=true/65659.jpeg", # Item 3
        "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/5910465c-bf35-48b5-9691-40cba75b6287/original=true/1118803.jpeg", # Item 4
        "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/253d2073-74d9-4890-b50b-47e5f04b110a/original=true/57355737.jpeg" # Item 5
    ]
    
    print("Checking transformed URLs...")
    for u in urls:
        transformed = get_civitai_thumbnail_url(u)
        print(f"\nOriginal: {u}")
        print(f"Transformed: {transformed}")
        
        try:
            r = requests.head(transformed, timeout=5)
            print(f"Status: {r.status_code}")
            print(f"Content-Type: {r.headers.get('Content-Type')}")
            
            if r.status_code != 200:
                print("  *** FAILED ***")
            elif 'video' in r.headers.get('Content-Type', ''):
                print("  *** IS VIDEO (UNEXPECTED FOR IMAGE) ***")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_urls()
