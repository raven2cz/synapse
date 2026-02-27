"""
Avatar AI Service — backward compatibility re-exports.

All logic has moved to task_service.py. This module re-exports the public API
so that existing code patching `src.avatar.ai_service.AvatarAIService` continues
to work without changes.
"""

from .task_service import AvatarTaskService  # noqa: F401
from .task_service import AvatarTaskService as AvatarAIService  # noqa: F401
from .task_service import _extract_json  # noqa: F401
