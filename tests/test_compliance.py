"""TEST-020 and TEST-022: Compliance and leakage audit.

Rules [EXPLICIT §6, §10, ARC-01]:
- solver.py is self-contained in a single file.
- Allowed imports ONLY: Python standard library, numpy, scipy, qiskit.
- PROHIBITED: local/, qiskit-aer, pytest, matplotlib, etc.
- No leakage: No inspect, gc, or ctypes tricks to inspect caller frames.
- No file I/O to access oracle tables or secret state.
- No network calls.
"""

import ast
import os
import sys
from pathlib import Path
import pytest

ALLOWED_ROOT_MODULES = {
    # Allowed scientific libraries
    "numpy",
    "scipy",
    "qiskit",
    # Python standard library modules
    "math",
    "random",
    "typing",
    "collections",
    "itertools",
    "functools",
    "dataclasses",
    "copy",
    "enum",
    "sys",
    "os",
    "time",
    "abc",
    "operator",
}


def test_solver_file_exists_and_is_single_file():
    """Verify solver.py exists at repo root."""
    solver_path = Path("solver.py")
    assert solver_path.is_file(), "solver.py must exist at the repository root."


def test_solver_imports_compliance():
    """TEST-020: Parse AST of solver.py and verify all imported modules are allowed."""
    solver_path = Path("solver.py")
    if not solver_path.is_file():
        pytest.skip("solver.py not created yet")
        
    with open(solver_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename="solver.py")
        
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                assert root_pkg in ALLOWED_ROOT_MODULES, (
                    f"PROHIBITED IMPORT in solver.py: 'import {alias.name}'. "
                    f"Only stdlib, numpy, scipy, qiskit are allowed."
                )
                assert root_pkg != "local", "solver.py must NEVER import from local/!"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                assert root_pkg in ALLOWED_ROOT_MODULES, (
                    f"PROHIBITED FROM-IMPORT in solver.py: 'from {node.module} import ...'. "
                    f"Only stdlib, numpy, scipy, qiskit are allowed."
                )
                assert root_pkg != "local", "solver.py must NEVER import from local/!"
                assert "aer" not in node.module.lower(), (
                    f"PROHIBITED Qiskit Aer import in solver.py: '{node.module}'."
                )


def test_solver_no_forbidden_patterns():
    """TEST-022: Ensure solver.py does not contain inspect frame hacks or hardcoded answers."""
    solver_path = Path("solver.py")
    if not solver_path.is_file():
        pytest.skip("solver.py not created yet")
        
    with open(solver_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check forbidden strings
    forbidden = [
        "import inspect",
        "from inspect",
        "import ctypes",
        "from ctypes",
        "sys._getframe",
        "get_reference_oracle",
        "OracleInstance",
        "urllib",
        "requests",
        "socket",
    ]
    for term in forbidden:
        assert term not in content, f"Forbidden pattern '{term}' detected in solver.py!"
