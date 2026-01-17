import json
import collections
import sys
from pathlib import Path

def analyze(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    images = data.get("images", [])
    print(f"Total Images: {len(images)}")
    
    # Stats
    samplers = collections.Counter()
    steps_list = []
    cfg_list = []
    resources_counter = collections.Counter()
    nsfw_levels = collections.Counter()
    
    for img in images:
        norm = img.get("normalized", {})
        raw = img.get("raw", {})
        
        # Sampler
        if norm.get("sampler"):
            samplers[norm["sampler"]] += 1
            
        # Steps
        if norm.get("steps") is not None:
            steps_list.append(norm["steps"])
            
        # CFG
        if norm.get("cfgScale") is not None:
            cfg_list.append(norm["cfgScale"])
            
        # NSFW
        nsfw_levels[raw.get("nsfwLevel", "Unknown")] += 1
        
        # Resources
        # Usually in raw['meta']['meta']['civitaiResources'] or raw['meta']['civitaiResources']
        meta = raw.get("meta", {})
        if isinstance(meta, dict) and "meta" in meta and isinstance(meta["meta"], dict):
            meta = meta["meta"]
            
        civitai_resources = meta.get("civitaiResources", [])
        if isinstance(civitai_resources, list):
            for res in civitai_resources:
                if isinstance(res, dict) and "modelName" in res: # Or lookup by ID if name missing
                    name = res.get("modelName")
                    if not name and "modelVersionId" in res:
                         name = f"ID:{res['modelVersionId']}"
                    resources_counter[f"{res.get('type', 'unknown')}:{name}"] += 1
                elif isinstance(res, dict) and "modelVersionId" in res:
                    resources_counter[f"{res.get('type', 'unknown')}:ID_{res['modelVersionId']}"] += 1

    print("\n--- Statistics ---")
    print("\nNSFW Levels:")
    for k, v in nsfw_levels.most_common():
        print(f"  {k}: {v}")

    print("\nTop 5 Samplers:")
    for k, v in samplers.most_common(5):
        print(f"  {k}: {v}")
        
    if steps_list:
        print(f"\nSteps: Min={min(steps_list)}, Max={max(steps_list)}, Avg={sum(steps_list)/len(steps_list):.1f}")
    
    if cfg_list:
        print(f"CFG: Min={min(cfg_list)}, Max={max(cfg_list)}, Avg={sum(cfg_list)/len(cfg_list):.1f}")

    print("\nTop 10 Resources Used:")
    for k, v in resources_counter.most_common(10):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze(sys.argv[1])
    else:
        # Default fallback
        path = Path("/home/box/git/github/synapse/civitai_images_1949537.json")
        if path.exists():
            analyze(str(path))
        else:
            print("Usage: python analyze.py <json_file>")
