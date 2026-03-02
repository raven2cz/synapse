"""
Avatar Tasks Module

Task-specific logic for AI-powered operations.
"""

from .base import AITask, TaskResult
from .model_tagging import ModelTaggingTask
from .parameter_extraction import ParameterExtractionTask
from .registry import TaskRegistry, get_default_registry

__all__ = [
    "AITask",
    "TaskResult",
    "ModelTaggingTask",
    "ParameterExtractionTask",
    "TaskRegistry",
    "get_default_registry",
]
