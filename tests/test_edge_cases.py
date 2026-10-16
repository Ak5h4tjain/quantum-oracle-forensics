"""TEST-023: Edge cases and contract robustness.

Rules [ER-009/010, AMB-06, AMB-12]:
- Always return (family, secret) with family in the provided families argument.
- Never crash, raise an unhandled exception, or return an invalid type.
- Secret type matches specification:
  - constant: int 0 or 1
  - balanced: None
  - linear: list [a, b] with a in 1..255, b in 0..1
  - grover: int in 0..255
  - randfun: None
  - simon: int in 1..255
  - simon2: list of 3 ascending ints [h1, h2, h3]
  - perm: None
- Handle single-family candidate lists and constrained budgets.
"""

import pytest
from local.oracles import get_reference_oracle
from local.local_run import LocalRunner
from local.noise import BASE_NOISE


def test_single_candidate_family():
    """If families contains only one candidate, solver must return it."""
    from solver import solve
    
    oracle = get_reference_oracle("constant-0")
    runner = LocalRunner(oracle=oracle, noise=BASE_NOISE, seed=77)
    
    family, secret = solve(
        n=8,
        m=1,
        budget=60,
        families=["constant"],
        run=runner.run
    )
    assert family == "constant"
    assert secret in (0, 1)


def test_tiny_budget_returns_valid_tuple():
    """Even with budget = 2, solver must return a valid (family, secret) without crashing."""
    from solver import solve
    
    oracle = get_reference_oracle("simon-1")
    runner = LocalRunner(oracle=oracle, noise=BASE_NOISE, seed=88)
    
    family, secret = solve(
        n=8,
        m=8,
        budget=2,
        families=["simon", "perm"],
        run=runner.run
    )
    assert family in ["simon", "perm"]
    if family == "simon":
        assert isinstance(secret, int) and 1 <= secret <= 255
    else:
        assert secret is None


def test_secret_return_types():
    """Verify secret types for all families."""
    from solver import format_secret
    
    assert format_secret("constant", 1) == 1
    assert format_secret("balanced", None) is None
    assert format_secret("linear", (5, 1)) == [5, 1]
    assert format_secret("grover", 42) == 42
    assert format_secret("randfun", None) is None
    assert format_secret("simon", 10) == 10
    assert format_secret("simon2", [6, 3, 5]) == [3, 5, 6]
    assert format_secret("perm", None) is None
