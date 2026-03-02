"""
Test to ensure no v1 API imports are used.

This test prevents accidental use of v1 PackRegistry or v1 packs router.
All pack operations must use v2 Store API.
"""

import ast
import os
from pathlib import Path
import pytest


def get_python_files(directory: Path):
    """Get all Python files in directory recursively."""
    files = []
    for root, dirs, filenames in os.walk(directory):
        # Skip __pycache__, .venv, node_modules, third_party
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.venv', 'node_modules', 'third_party', 'v1']]
        
        for filename in filenames:
            if filename.endswith('.py') and not filename.startswith('packs_v1_DEPRECATED'):
                files.append(Path(root) / filename)
    return files


class V1ImportChecker(ast.NodeVisitor):
    """AST visitor to check for v1 imports."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.violations = []
    
    def visit_Import(self, node):
        for alias in node.names:
            self._check_import(alias.name, node.lineno)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        if node.module:
            self._check_import(node.module, node.lineno)
            
            # Check for specific v1 imports
            for alias in node.names:
                full_name = f"{node.module}.{alias.name}"
                self._check_import(full_name, node.lineno)
        self.generic_visit(node)
    
    def _check_import(self, name: str, lineno: int):
        # Forbidden v1 imports
        v1_patterns = [
            'src.core.registry',           # v1 PackRegistry
            'PackRegistry',                 # v1 PackRegistry class
            '.routers.packs',               # v1 packs router
            'apps.api.src.routers.packs',   # v1 packs router full path
            'packs_router',                 # v1 packs router variable (unless it's v2)
        ]
        
        for pattern in v1_patterns:
            if pattern in name:
                # Exception: v2 API can reference itself
                if 'v2_packs_router' in name:
                    continue
                # Exception: v1 deprecated file itself
                if 'packs_v1_DEPRECATED' in self.filepath:
                    continue
                
                self.violations.append(
                    f"{self.filepath}:{lineno} - V1 import detected: {name}"
                )


def test_no_v1_imports():
    """Ensure no v1 API imports are used in the API codebase."""
    project_root = Path(__file__).parent.parent
    
    # ONLY check API directory - v1 models/registry can still exist but shouldn't be imported by API
    dirs_to_check = [
        project_root / 'apps' / 'api' / 'src',
    ]
    
    all_violations = []
    
    for check_dir in dirs_to_check:
        if not check_dir.exists():
            continue
            
        for py_file in get_python_files(check_dir):
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
                
                checker = V1ImportChecker(str(py_file))
                checker.visit(tree)
                
                all_violations.extend(checker.violations)
            except SyntaxError:
                pass  # Skip files with syntax errors
    
    if all_violations:
        violation_msg = "\n".join(all_violations)
        pytest.fail(
            f"V1 API imports detected! All pack operations must use v2 Store API.\n"
            f"Violations:\n{violation_msg}"
        )


def test_v1_packs_router_not_in_main():
    """Ensure main.py does not import v1 packs router."""
    main_py = Path(__file__).parent.parent / 'apps' / 'api' / 'src' / 'main.py'
    
    if not main_py.exists():
        pytest.skip("main.py not found")
    
    content = main_py.read_text()
    
    # Should NOT contain these actual imports
    forbidden = [
        'from .routers import packs_router',
        'from .routers.packs import',
        'from apps.api.src.routers import packs_router',
    ]
    
    for pattern in forbidden:
        assert pattern not in content, (
            f"main.py contains forbidden v1 import pattern: {pattern}\n"
            f"Use v2_packs_router from src.store.api instead!"
        )
    
    # Should contain v2 import
    assert 'v2_packs_router' in content, (
        "main.py must use v2_packs_router from src.store.api"
    )
    
    # Should include v2_packs_router in router registration
    assert 'app.include_router(v2_packs_router' in content, (
        "main.py must register v2_packs_router with app.include_router()"
    )


def test_routers_init_no_packs():
    """Ensure routers/__init__.py does not export packs_router."""
    init_py = Path(__file__).parent.parent / 'apps' / 'api' / 'src' / 'routers' / '__init__.py'
    
    if not init_py.exists():
        pytest.skip("routers/__init__.py not found")
    
    content = init_py.read_text()
    
    # Should NOT export packs_router
    assert 'packs_router' not in content or 'NO LONGER' in content, (
        "routers/__init__.py should not export packs_router.\n"
        "All pack operations must use v2_packs_router from src.store.api"
    )


def test_v2_api_has_required_endpoints():
    """Ensure v2 API has all required endpoints."""
    api_py = Path(__file__).parent.parent / 'src' / 'store' / 'api.py'
    
    if not api_py.exists():
        pytest.skip("api.py not found")
    
    content = api_py.read_text()
    
    # Required endpoints (must exist in v2 API)
    required_endpoints = [
        '@v2_packs_router.get("/"',                          # list packs
        '@v2_packs_router.get("/{pack_name}"',               # get pack
        '@v2_packs_router.delete("/{pack_name}"',            # delete pack
        '@v2_packs_router.post("/{pack_name}/download-asset"', # download asset
        '@v2_packs_router.get("/downloads/active"',          # active downloads
        '@v2_packs_router.delete("/downloads/completed"',    # clear downloads
        '@v2_packs_router.post("/{pack_name}/resolve-base-model"', # resolve base model
        '@v2_packs_router.patch("/{pack_name}/parameters"',  # update parameters
        '@v2_packs_router.post("/{pack_name}/generate-workflow"', # generate workflow
        '@v2_packs_router.post("/{pack_name}/workflow/upload-file"', # upload workflow
        '@v2_packs_router.delete("/{pack_name}/workflow/{filename}"', # delete workflow
        '@v2_packs_router.post("/import-model"',             # import local model
    ]
    
    missing = []
    for endpoint in required_endpoints:
        if endpoint not in content:
            missing.append(endpoint)
    
    if missing:
        pytest.fail(
            f"v2 API is missing required endpoints:\n" +
            "\n".join(f"  - {e}" for e in missing)
        )


def test_no_legacy_ai_imports():
    """Ensure no legacy src.ai imports remain — all AI code lives in src.avatar."""
    project_root = Path(__file__).parent.parent.parent

    dirs_to_check = [
        project_root / 'src',
        project_root / 'tests',
    ]

    violations = []

    for check_dir in dirs_to_check:
        if not check_dir.exists():
            continue

        for py_file in get_python_files(check_dir):
            try:
                content = py_file.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if node.module.startswith('src.ai.') or node.module == 'src.ai':
                            violations.append(
                                f"{py_file}:{node.lineno} - Legacy import: from {node.module}"
                            )
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith('src.ai.') or alias.name == 'src.ai':
                                violations.append(
                                    f"{py_file}:{node.lineno} - Legacy import: import {alias.name}"
                                )
            except SyntaxError:
                pass

    if violations:
        pytest.fail(
            f"Legacy src.ai imports detected! All AI code must use src.avatar.*\n"
            f"Violations:\n" + "\n".join(violations)
        )


def test_task_service_no_legacy_ai_imports():
    """task_service.py must not import from src.ai (legacy)."""
    task_service_py = Path(__file__).parent.parent.parent / 'src' / 'avatar' / 'task_service.py'

    if not task_service_py.exists():
        pytest.skip("task_service.py not found")

    content = task_service_py.read_text()
    assert 'from src.ai' not in content, (
        "task_service.py must not import from legacy src.ai module"
    )


def test_ai_service_is_reexport_only():
    """ai_service.py must contain only re-exports (no class definitions)."""
    ai_service_py = Path(__file__).parent.parent.parent / 'src' / 'avatar' / 'ai_service.py'

    if not ai_service_py.exists():
        pytest.skip("ai_service.py not found")

    content = ai_service_py.read_text()
    assert 'class ' not in content, (
        "ai_service.py must not define classes — it should only re-export from task_service.py"
    )


def test_default_registry_has_parameter_extraction():
    """get_default_registry() must include parameter_extraction task."""
    from src.avatar.tasks.registry import get_default_registry

    registry = get_default_registry()
    assert 'parameter_extraction' in registry.list_tasks(), (
        "Default registry must include parameter_extraction task"
    )


def test_default_registry_has_model_tagging():
    """get_default_registry() must include model_tagging task."""
    from src.avatar.tasks.registry import get_default_registry

    registry = get_default_registry()
    assert 'model_tagging' in registry.list_tasks(), (
        "Default registry must include model_tagging task"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
