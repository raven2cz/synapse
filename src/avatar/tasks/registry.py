"""
Task Registry

Instance-level registry for AI task types. Prevents test pollution
by avoiding class-level singletons.
"""

import logging
import threading
from typing import Dict, List, Optional

from .base import AITask

logger = logging.getLogger(__name__)


class TaskRegistry:
    """Registry of available AI task types.

    Instance-level (not a class singleton) to allow isolated testing.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, AITask] = {}

    def register(self, task: AITask) -> None:
        """Register a task type. Overwrites existing registration."""
        if not task.task_type:
            raise ValueError("Task must have a non-empty task_type")
        self._tasks[task.task_type] = task
        logger.debug("Registered task: %s", task.task_type)

    def get(self, task_type: str) -> Optional[AITask]:
        """Get task by type name, or None if not registered."""
        return self._tasks.get(task_type)

    def list_tasks(self) -> List[str]:
        """List all registered task type names, sorted."""
        return sorted(self._tasks.keys())

    def reset(self) -> None:
        """Clear all registrations. For testing only."""
        self._tasks.clear()


# Default global instance (lazy-populated, thread-safe init)
_default_registry = TaskRegistry()
_default_registry_lock = threading.Lock()
_default_registry_initialized = False


def get_default_registry() -> TaskRegistry:
    """Get the default task registry (auto-discovers on first call).

    Thread-safe: uses double-checked locking for one-time initialization.
    """
    global _default_registry_initialized
    if not _default_registry_initialized:
        with _default_registry_lock:
            if not _default_registry_initialized:
                from .model_tagging import ModelTaggingTask
                from .parameter_extraction import ParameterExtractionTask
                _default_registry.register(ParameterExtractionTask())
                _default_registry.register(ModelTaggingTask())
                _default_registry_initialized = True
    return _default_registry
