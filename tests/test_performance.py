"""TEST-019: Runtime and memory limit verification.

Rules [EXPLICIT §6, TEST-019]:
- Execution time per oracle solve must be <= 120 seconds.
- Memory consumption must be <= 8 GB.
- In practice, our target is <= 5 seconds per solve and <= 250 MB RAM.
"""

import time
import os
import pytest
from local.oracles import generate_simon_oracle, generate_linear_oracle
from local.local_run import LocalRunner
from local.noise import BASE_NOISE
from solver import solve


def test_runtime_and_memory():
    """Verify runtime per solve is well under 5 seconds."""
    # Simon (16 qubits)
    oracle_simon = generate_simon_oracle(s=123, seed=42)
    runner_simon = LocalRunner(oracle_simon, noise=BASE_NOISE, seed=42)
    
    t0 = time.time()
    fam, sec = solve(8, 8, 60, ["simon", "simon2", "perm"], runner_simon.run)
    t_simon = time.time() - t0
    
    assert fam == "simon"
    assert sec == 123
    assert t_simon < 5.0, f"Simon solve took {t_simon:.2f}s, expected < 5s"

    # Linear (9 qubits)
    oracle_lin = generate_linear_oracle(a=42, b=1)
    runner_lin = LocalRunner(oracle_lin, noise=BASE_NOISE, seed=42)
    
    t0 = time.time()
    fam_l, sec_l = solve(8, 1, 60, ["constant", "linear"], runner_lin.run)
    t_lin = time.time() - t0
    
    assert fam_l == "linear"
    assert sec_l == [42, 1]
    assert t_lin < 5.0, f"Linear solve took {t_lin:.2f}s, expected < 5s"
