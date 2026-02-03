"""
AI Prompts Module

Prompt templates for AI-powered tasks.
"""

from .parameter_extraction import (
    PARAMETER_EXTRACTION_PROMPT,
    build_extraction_prompt,
)

__all__ = [
    "PARAMETER_EXTRACTION_PROMPT",
    "build_extraction_prompt",
]
