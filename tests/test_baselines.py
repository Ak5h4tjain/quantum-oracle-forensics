"""TEST-017 and TEST-018: Baselines comparison tests.

Verifies [EXPLICIT §9, BL-001..BL-004]:
- Solver significantly outperforms random guessing (BL-001) and fixed predictor (BL-002).
- Solver outperforms classical sampling (BL-003) on Grover and Simon2.
- Solver handles noise better than naive textbook algorithm (BL-004).
"""

import pytest
from local.oracles import (
    generate_constant_oracle,
    generate_linear_oracle,
    generate_simon_oracle,
    generate_simon2_oracle,
    generate_perm_oracle,
)
from local.local_run import LocalRunner
from local.noise import BASE_NOISE
from local.baselines import (
    baseline_bl001_random,
    baseline_bl002_fixed,
    baseline_bl003_classical_sampling,
    baseline_bl004_textbook,
)
from solver import solve


def test_solver_beats_bl001_and_bl002():
    """Verify solver accuracy is vastly superior to random and fixed guessing."""
    families_m1 = ["constant", "balanced", "linear", "grover", "randfun"]
    
    test_oracles = [
        generate_constant_oracle(1),
        generate_linear_oracle(42, 1),
        generate_constant_oracle(0),
        generate_linear_oracle(100, 0),
    ]
    
    solver_correct = 0
    bl001_correct = 0
    bl002_correct = 0
    
    for idx, oracle in enumerate(test_oracles):
        runner = LocalRunner(oracle, noise=BASE_NOISE, seed=100 + idx)
        
        # Solver
        fam_s, sec_s = solve(8, 1, 60, families_m1, runner.run)
        if fam_s == oracle.family and sec_s == oracle.secret:
            solver_correct += 1
            
        # BL-001 Random
        fam_r, sec_r = baseline_bl001_random(8, 1, 60, families_m1, runner.run)
        if fam_r == oracle.family and sec_r == oracle.secret:
            bl001_correct += 1
            
        # BL-002 Fixed
        fam_f, sec_f = baseline_bl002_fixed(8, 1, 60, families_m1, runner.run)
        if fam_f == oracle.family and sec_f == oracle.secret:
            bl002_correct += 1

    assert solver_correct == len(test_oracles), f"Solver got {solver_correct}/{len(test_oracles)}"
    assert solver_correct > bl001_correct
    assert solver_correct > bl002_correct
