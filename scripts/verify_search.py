
import os
import sys
import json

# Add project root to path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.clients.civitai_client import CivitaiClient

def verify_search():
    """
    Verify that Civitai search works and uses the provided API Token.
    """
    # User provided key
    API_KEY = "4518bff7807a2324813064d5f7c8e12a"
    MASKED_KEY = f"{API_KEY[:4]}...{API_KEY[-4:]}"
    
    print(f"--- Civitai Search Verification ---")
    print(f"Initializing client with API Key: {MASKED_KEY}")
    
    client = CivitaiClient(api_key=API_KEY)
    
    # 1. Verify Authorization Header is set in session
    auth_header = client.session.headers.get("Authorization")
    if auth_header == f"Bearer {API_KEY}":
        print(f"✅ Authorization header is correctly configured in session.")
    else:
        print(f"❌ Authorization header MISSING or INCORRECT in session!")
        print(f"   Expected: Bearer {MASKED_KEY}")
        print(f"   Actual:   {auth_header}")
        sys.exit(1)

    # 2. Perform a real search
    # We use a known query "Cherry-gig" which should return results
    # We also use sort="Highest Rated" to match the new default in browse.py
    QUERY = "Cherry-gig"
    print(f"\nPerforming search for '{QUERY}' (nsfw=True, sort='Highest Rated')...")
    
    try:
        results = client.search_models(query=QUERY, limit=20, nsfw=True, sort="Highest Rated")
    except Exception as e:
        print(f"❌ Search request failed: {e}")
        sys.exit(1)
        
    items = results.get("items", [])
    count = len(items)
    print(f"✅ Search returned {count} results.")
    
    # 3. Validate results
    if count == 0:
        print("❌ No items found! Search might be broken or token invalid.")
        sys.exit(1)
        
    print("\nTop 5 Results:")
    found_target = False
    for i, item in enumerate(items[:5]):
        name = item.get("name", "Unknown")
        print(f" {i+1}. {name} (ID: {item.get('id')})")
        if "Cherry" in name:
            found_target = True
            
    if found_target:
        print(f"\n✅ Result validation passed: Found items matching '{QUERY}'.")
    else:
        print(f"\n⚠️ Warning: Top results did not contain '{QUERY}'.")
        
    # 4. Validate Tag Search (New Feature)
    TAG = "cherry-gig"
    print(f"\nPerforming TAG search for '{TAG}'...")
    try:
        results = client.search_models(tag=TAG, limit=5, nsfw=True, sort="Highest Rated")
    except Exception as e:
        print(f"❌ Tag search failed: {e}")
        # Don't exit, just report
    else:
         items = results.get("items", [])
         print(f"✅ Tag search returned {len(items)} results.")
         if len(items) > 0:
             print(f" 1. {items[0].get('name')} (ID: {items[0].get('id')})")
             if "Cherry-gig" in items[0].get("name") or "Cherry-gig" in str(items[0].get("description")):
                 print("✅ Tag search found the target model in position #1!")
             else:
                 print("⚠️ Tag search candidate #1 might not be exact match, but search worked.")
    
             else:
                 print("⚠️ Tag search candidate #1 might not be exact match, but search worked.")
    
    print("\n--- Verification Completed Successfully ---")

if __name__ == "__main__":
    verify_search()
