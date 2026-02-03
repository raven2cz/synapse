"""
AI Providers Module

CLI-based AI providers for Synapse:
- OllamaProvider: Local GPU-accelerated inference
- GeminiProvider: Google Gemini CLI
- ClaudeProvider: Anthropic Claude Code CLI
- RuleBasedProvider: Fallback using regexp extraction
"""

from .base import AIProvider, ProviderResult
from .ollama import OllamaProvider
from .gemini import GeminiProvider
from .claude import ClaudeProvider
from .rule_based import RuleBasedProvider
from .registry import ProviderRegistry

__all__ = [
    "AIProvider",
    "ProviderResult",
    "OllamaProvider",
    "GeminiProvider",
    "ClaudeProvider",
    "RuleBasedProvider",
    "ProviderRegistry",
]
