"""TEST-021: Clean directory isolated execution test.

Rules [AMB-16, TS-01]:
- solver.py must be 100% self-contained and run in a completely isolated directory.
- It must not require or import local/, tests/, or any helper files.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest


def test_solver_isolated_execution():
    """Copy solver.py alone into a clean temp directory and test importing and solving."""
    solver_src = Path("solver.py").resolve()
    assert solver_src.is_file()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_solver = Path(tmpdir) / "solver.py"
        shutil.copyfile(solver_src, tmp_solver)

        # Run python script inside isolated tempdir
        test_script = (
            "import sys\n"
            "from solver import solve, ALL_FAMILIES\n"
            "def dummy_run(circuit, shots):\n"
            "    return {'00000000': shots}\n"
            "fam, sec = solve(8, 1, 60, ['constant'], dummy_run)\n"
            "assert fam == 'constant'\n"
            "print('ISOLATED_OK')\n"
        )
        script_path = Path(tmpdir) / "test_isolated.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(test_script)

        res = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Clean directory execution failed: {res.stderr}"
        assert "ISOLATED_OK" in res.stdout
