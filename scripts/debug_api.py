#!/usr/bin/env python3
"""
Debug script for testing Civitai and HuggingFace API integration.

Usage:
    cd synapse
    python scripts/debug_api.py
    
Set tokens via Settings in the UI, or environment variables:
    CIVITAI_API_TOKEN=xxx
    HF_TOKEN=xxx
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import json
import traceback

def log_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def log_success(msg: str):
    print(f"  ✓ {msg}")

def log_error(msg: str):
    print(f"  ✗ {msg}")

def log_info(msg: str):
    print(f"  ℹ {msg}")

def log_data(label: str, data):
    if isinstance(data, dict):
        print(f"  {label}:")
        for k, v in list(data.items())[:5]:
            print(f"      {k}: {str(v)[:80]}")
    else:
        print(f"  {label}: {str(data)[:200]}")


def test_config():
    """Test configuration loading."""
    log_section("Configuration")
    
    try:
        from config.settings import get_config
        config = get_config()
        
        log_success("Config loaded successfully")
        log_info(f"ComfyUI path: {config.comfyui.base_path}")
        log_info(f"Synapse data: {config.data_path}")
        log_info(f"Config file: {config.config_file}")
        log_info(f"Civitai token: {'SET (' + config.api.civitai_token[:8] + '...)' if config.api.civitai_token else 'NOT SET'}")
        log_info(f"HuggingFace token: {'SET (' + config.api.huggingface_token[:8] + '...)' if config.api.huggingface_token else 'NOT SET'}")
        
        return config
    except Exception as e:
        log_error(f"Config failed: {e}")
        traceback.print_exc()
        return None


def test_civitai_url_parse():
    """Test URL parsing."""
    log_section("Civitai URL Parsing")
    
    try:
        from src.clients.civitai_client import CivitaiClient
        
        client = CivitaiClient()
        
        test_urls = [
            "https://civitai.com/models/1949537/cherry-gig-western-style-illustrious",
            "https://civitai.com/models/12345",
            "https://civitai.com/models/12345?modelVersionId=67890",
        ]
        
        for url in test_urls:
            try:
                model_id, version_id = client.parse_civitai_url(url)
                log_success(f"URL parsed: model={model_id}, version={version_id}")
            except Exception as e:
                log_error(f"URL parse failed: {e}")
        
        return True
    except Exception as e:
        log_error(f"URL parsing failed: {e}")
        traceback.print_exc()
        return False


def test_civitai_search(config):
    """Test Civitai search API."""
    log_section("Civitai Search API")
    
    if not config.api.civitai_token:
        log_info("No Civitai token set - searching without auth")
    
    try:
        from src.clients.civitai_client import CivitaiClient
        
        client = CivitaiClient(api_key=config.api.civitai_token)
        log_success("CivitaiClient created")
        
        # Test search
        log_info("Searching for 'anime' models...")
        results = client.search_models(query="anime", limit=3)
        
        if isinstance(results, dict):
            items = results.get("items", [])
            total = results.get("metadata", {}).get("totalItems", 0)
            log_success(f"Search returned {len(items)} items (total: {total})")
            
            for model in items[:3]:
                log_info(f"  - [{model.get('id')}] {model.get('name')} ({model.get('type')})")
        else:
            log_error(f"Unexpected result type: {type(results)}")
            return False
        
        return True
    except Exception as e:
        log_error(f"Search failed: {e}")
        traceback.print_exc()
        return False


def test_civitai_model(config, model_id: int = 1949537):
    """Test Civitai get model API."""
    log_section(f"Civitai Get Model (ID: {model_id})")
    
    try:
        from src.clients.civitai_client import CivitaiClient
        
        client = CivitaiClient(api_key=config.api.civitai_token)
        
        log_info(f"Fetching model {model_id}...")
        model_data = client.get_model(model_id)
        
        if isinstance(model_data, dict):
            log_success(f"Model: {model_data.get('name')}")
            log_info(f"Type: {model_data.get('type')}")
            log_info(f"NSFW: {model_data.get('nsfw')}")
            log_info(f"Tags: {model_data.get('tags', [])[:5]}")
            
            versions = model_data.get("modelVersions", [])
            log_info(f"Versions: {len(versions)}")
            
            if versions:
                v = versions[0]
                log_info(f"Latest version: {v.get('name')} (ID: {v.get('id')})")
                log_info(f"Files: {len(v.get('files', []))}")
                log_info(f"Images: {len(v.get('images', []))}")
        else:
            log_error(f"Unexpected result type: {type(model_data)}")
            return False
        
        return True
    except Exception as e:
        log_error(f"Get model failed: {e}")
        traceback.print_exc()
        return False


def test_pack_builder(config):
    """Test PackBuilder from URL."""
    log_section("PackBuilder from Civitai URL")
    
    try:
        from src.core.pack_builder import PackBuilder
        
        builder = PackBuilder(config)
        log_success("PackBuilder created")
        
        url = "https://civitai.com/models/1949537/cherry-gig-western-style-illustrious"
        log_info(f"Building pack from: {url}")
        
        result = builder.build_from_civitai_url(url)
        
        if result.success:
            log_success(f"Pack built: {result.pack.metadata.name}")
            log_info(f"Version: {result.pack.metadata.version}")
            log_info(f"Dependencies: {len(result.pack.dependencies)}")
            log_info(f"Previews: {len(result.pack.previews)}")
            if result.warnings:
                for w in result.warnings:
                    log_info(f"Warning: {w}")
        else:
            log_error(f"Pack build failed: {result.errors}")
            return False
        
        return True
    except Exception as e:
        log_error(f"PackBuilder failed: {e}")
        traceback.print_exc()
        return False


def test_huggingface(config):
    """Test HuggingFace API."""
    log_section("HuggingFace API")
    
    if not config.api.huggingface_token:
        log_info("No HuggingFace token set - some gated repos may fail")
    
    try:
        from src.clients.huggingface_client import HuggingFaceClient
        
        client = HuggingFaceClient(token=config.api.huggingface_token)
        log_success("HuggingFaceClient created")
        
        # Test repo info
        test_repo = "stabilityai/stable-diffusion-xl-base-1.0"
        log_info(f"Fetching repo info: {test_repo}...")
        
        info = client.get_repo_info(test_repo)
        if info:
            log_success(f"Repo found: {info.get('id', 'unknown')}")
            log_info(f"Private: {info.get('private', False)}")
            log_info(f"Downloads: {info.get('downloads', 0)}")
        else:
            log_error("Repo info returned None")
            return False
        
        return True
    except Exception as e:
        log_error(f"HuggingFace failed: {e}")
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("  SYNAPSE API DEBUG SCRIPT")
    print("="*60)
    
    # Test config
    config = test_config()
    if not config:
        print("\n❌ Config failed - cannot continue")
        return 1
    
    results = []
    
    # Test Civitai
    results.append(("Civitai URL Parse", test_civitai_url_parse()))
    results.append(("Civitai Search", test_civitai_search(config)))
    results.append(("Civitai Get Model", test_civitai_model(config)))
    results.append(("PackBuilder", test_pack_builder(config)))
    
    # Test HuggingFace
    results.append(("HuggingFace", test_huggingface(config)))
    
    # Summary
    log_section("SUMMARY")
    all_passed = True
    for name, passed in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed - check output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
