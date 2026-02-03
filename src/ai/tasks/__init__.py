"""
AI Tasks Module

Task-specific logic for AI-powered operations.
"""

from .base import AITask, TaskResult
from .parameter_extraction import ParameterExtractionTask

__all__ = [
    "AITask",
    "TaskResult",
    "ParameterExtractionTask",
]
