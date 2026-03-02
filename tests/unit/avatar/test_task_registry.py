"""
Unit tests for TaskRegistry.

Tests instance-level registry: register, get, list, reset, auto-discovery.
"""

import pytest

from src.avatar.tasks.base import AITask, TaskResult
from src.avatar.tasks.registry import TaskRegistry, get_default_registry


# =============================================================================
# Fake tasks for testing
# =============================================================================


class FakeTaskA(AITask):
    task_type = "task_a"
    SKILL_NAMES = ("skill-a",)

    def build_system_prompt(self, skills_content: str) -> str:
        return f"Task A prompt. {skills_content}"

    def parse_result(self, raw_output):
        return raw_output


class FakeTaskB(AITask):
    task_type = "task_b"
    SKILL_NAMES = ()

    def build_system_prompt(self, skills_content: str) -> str:
        return "Task B prompt."

    def parse_result(self, raw_output):
        return raw_output


class FakeTaskNoType(AITask):
    task_type = ""

    def build_system_prompt(self, skills_content: str) -> str:
        return ""

    def parse_result(self, raw_output):
        return raw_output


# =============================================================================
# TestTaskRegistry
# =============================================================================


class TestTaskRegistry:
    """Test TaskRegistry core operations."""

    def test_register_and_get(self):
        """register() + get() happy path."""
        reg = TaskRegistry()
        task = FakeTaskA()
        reg.register(task)
        assert reg.get("task_a") is task

    def test_get_unknown_returns_none(self):
        """get() for unknown task type returns None."""
        reg = TaskRegistry()
        assert reg.get("nonexistent") is None

    def test_list_tasks_sorted(self):
        """list_tasks() returns sorted task type names."""
        reg = TaskRegistry()
        reg.register(FakeTaskB())
        reg.register(FakeTaskA())
        assert reg.list_tasks() == ["task_a", "task_b"]

    def test_list_tasks_empty(self):
        """list_tasks() on empty registry returns empty list."""
        reg = TaskRegistry()
        assert reg.list_tasks() == []

    def test_reset_clears_all(self):
        """reset() clears all registrations."""
        reg = TaskRegistry()
        reg.register(FakeTaskA())
        reg.register(FakeTaskB())
        assert len(reg.list_tasks()) == 2

        reg.reset()
        assert reg.list_tasks() == []
        assert reg.get("task_a") is None

    def test_duplicate_registration_overwrites(self):
        """Registering same task_type again overwrites the previous one."""
        reg = TaskRegistry()
        task1 = FakeTaskA()
        task2 = FakeTaskA()
        reg.register(task1)
        reg.register(task2)
        assert reg.get("task_a") is task2
        assert len(reg.list_tasks()) == 1

    def test_instance_isolation(self):
        """Two registry instances don't affect each other."""
        reg1 = TaskRegistry()
        reg2 = TaskRegistry()
        reg1.register(FakeTaskA())
        assert reg1.get("task_a") is not None
        assert reg2.get("task_a") is None

    def test_register_empty_task_type_raises(self):
        """Registering task with empty task_type raises ValueError."""
        reg = TaskRegistry()
        with pytest.raises(ValueError, match="non-empty task_type"):
            reg.register(FakeTaskNoType())


class TestDefaultRegistry:
    """Test get_default_registry() auto-discovery."""

    def test_default_registry_has_parameter_extraction(self):
        """Default registry auto-registers parameter_extraction."""
        reg = get_default_registry()
        assert "parameter_extraction" in reg.list_tasks()

    def test_default_registry_task_type(self):
        """Default registry parameter_extraction task has correct attributes."""
        reg = get_default_registry()
        task = reg.get("parameter_extraction")
        assert task is not None
        assert task.task_type == "parameter_extraction"
        assert task.SKILL_NAMES == ("generation-params",)

    def test_default_registry_task_has_fallback(self):
        """parameter_extraction task has a fallback."""
        reg = get_default_registry()
        task = reg.get("parameter_extraction")
        assert task.get_fallback() is not None

    def test_default_registry_has_model_tagging(self):
        """Default registry auto-registers model_tagging."""
        reg = get_default_registry()
        assert "model_tagging" in reg.list_tasks()
        task = reg.get("model_tagging")
        assert task is not None
        assert task.task_type == "model_tagging"
        assert task.get_fallback() is not None

    def test_default_registry_has_two_tasks(self):
        """Default registry has both built-in tasks."""
        reg = get_default_registry()
        tasks = reg.list_tasks()
        assert len(tasks) == 2
        assert "parameter_extraction" in tasks
        assert "model_tagging" in tasks
