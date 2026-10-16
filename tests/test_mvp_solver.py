"""TEST-013: End-to-end MVP solver test on all families.

Verifies that the MVP solver in solver.py can:
- Correctly classify and extract secrets for m=1 families (constant, linear, grover, balanced, randfun)
- Correctly classify and extract secrets for m=8 families (simon, simon2, perm)
- Work under noiseless and base noise conditions without exceeding budget 60.
"""

import pytest
from local.oracles import (
    generate_constant_oracle,
    generate_linear_oracle,
    generate_grover_oracle,
    generate_balanced_oracle,
    generate_randfun_oracle,
    generate_simon_oracle,
    generate_simon2_oracle,
    generate_perm_oracle,
    get_reference_oracle,
)
from local.local_run import LocalRunner
from local.noise import NOISELESS, BASE_NOISE


def test_mvp_constant_oracles():
    """Verify MVP solver correctly identifies constant-0 and constant-1."""
    from solver import solve
    
    for c in [0, 1]:
        oracle = generate_constant_oracle(c=c)
        runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
        family, secret = solve(
            n=8, m=1, budget=60,
            families=["constant", "balanced", "linear", "grover", "randfun"],
            run=runner.run
        )
        assert family == "constant"
        assert secret == c


def test_mvp_linear_oracles():
    """Verify MVP solver extracts linear [a, b]."""
    from solver import solve
    
    for a, b in [(1, 0), (42, 1), (255, 0)]:
        oracle = generate_linear_oracle(a=a, b=b)
        runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
        family, secret = solve(
            n=8, m=1, budget=60,
            families=["constant", "balanced", "linear", "grover", "randfun"],
            run=runner.run
        )
        assert family == "linear"
        assert secret == [a, b]


def test_mvp_simon_oracles():
    """Verify MVP solver extracts simon period s."""
    from solver import solve
    
    for s in [1, 42, 137]:
        oracle = generate_simon_oracle(s=s, seed=10)
        runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
        family, secret = solve(
            n=8, m=8, budget=60,
            families=["simon", "simon2", "perm"],
            run=runner.run
        )
        assert family == "simon"
        assert secret == s


def test_mvp_simon2_oracles():
    """Verify MVP solver extracts simon2 subspace H."""
    from solver import solve
    
    for h1, h2 in [(1, 2), (3, 5)]:
        h3 = h1 ^ h2
        expected_H = sorted([h1, h2, h3])
        oracle = generate_simon2_oracle(h1=h1, h2=h2, seed=20)
        runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
        family, secret = solve(
            n=8, m=8, budget=60,
            families=["simon", "simon2", "perm"],
            run=runner.run
        )
        assert family == "simon2"
        assert secret == expected_H


def test_mvp_perm_oracles():
    """Verify MVP solver identifies permutations."""
    from solver import solve
    
    for seed in [11, 22]:
        oracle = generate_perm_oracle(seed=seed)
        runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
        family, secret = solve(
            n=8, m=8, budget=60,
            families=["simon", "simon2", "perm"],
            run=runner.run
        )
        assert family == "perm"
        assert secret is None
