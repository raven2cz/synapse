
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = "/home/box/git/github/synapse"
sys.path.append(project_root)

# Mock config to avoid loading real settings which might fail
class MockConfig:
    pass

import unittest.mock as mock
sys.modules['config.settings'] = mock.MagicMock()
sys.modules['fastapi'] = mock.MagicMock()
sys.modules['fastapi.responses'] = mock.MagicMock()
sys.modules['src.core.models'] = mock.MagicMock()
sys.modules['src.core.registry'] = mock.MagicMock()
sys.modules['src.core.pack_builder'] = mock.MagicMock()
sys.modules['src.core.validator'] = mock.MagicMock()
sys.modules['src.workflows.generator'] = mock.MagicMock()

from pydantic import BaseModel
from typing import Optional, List

# Re-define the relevant parts from packs.py to test isolation
# (Or better, import them if possible, but mocking dependencies is hard)
# Let's try to import directly first, catching errors

try:
    from apps.api.src.routers.packs import PreviewInfo, PackDetail, AssetInfo
    print("Successfully imported models")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

# Create a dummy structure
meta_data = {
    "prompt": "test prompt",
    "sampler": "Euler a"
}

preview_data = {
    "filename": "test.jpg",
    "url": "http://test.com/test.jpg",
    "nsfw": False,
    "width": 100,
    "height": 100,
    "meta": meta_data
}

# Test PreviewInfo directly
try:
    p_info = PreviewInfo(**preview_data)
    print(f"PreviewInfo created: {p_info}")
    print(f"PreviewInfo dict: {p_info.model_dump()}")
    
    if p_info.meta == meta_data:
        print("SUCCESS: PreviewInfo preserves meta persistence")
    else:
        print("FAILURE: PreviewInfo lost meta persistence")
        print(f"Expected: {meta_data}")
        print(f"Got: {p_info.meta}")
        
except Exception as e:
    print(f"Error creating PreviewInfo: {e}")

