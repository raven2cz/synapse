"""
AI Services Module

Provides AI-powered functionality for Synapse using CLI-based providers:
- Ollama (local, GPU-accelerated)
- Gemini CLI (cloud, Google AI)
- Claude Code (cloud, Anthropic)

Falls back to rule-based extraction when AI is unavailable.
"""

from .service import AIService
from .settings import AIServicesSettings, ProviderConfig, TaskPriorityConfig
from .detection import detect_ai_providers
from .cache import AICache

__all__ = [
    "AIService",
    "AIServicesSettings",
    "ProviderConfig",
    "TaskPriorityConfig",
    "detect_ai_providers",
    "AICache",
]
