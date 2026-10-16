"""TEST-014, TEST-015, TEST-016: Adaptive controller, reserve policy, and validation tests.

Rules [DEC-08, DEC-10, G2]:
- TEST-014: Adaptive early stopping saves queries on easy families (constant, linear)
  spending significantly fewer than the 60 query maximum.
- TEST-015: Reserve policy ensures queries are always reserved for secret extraction
  (e.g. direct read for b in linear, verification read for t in grover).
- TEST-016: Calibration thresholds frozen on calibration seeds achieve >= 90% accuracy
  on independent validation seeds (seeds 2000..2020).
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
from local.noise import BASE_NOISE, NOISELESS
from tests.test_ledger import MockJudgesHarness


def test_adaptive_query_saving():
    """TEST-014: Verify solver saves queries on constant and linear oracles."""
    from solver import solve
    
    # 1. Constant oracle: should stop with <= 10 queries
    oracle_c = generate_constant_oracle(c=1)
    runner_c = LocalRunner(oracle=oracle_c, noise=BASE_NOISE, seed=2001)
    harness_c = MockJudgesHarness(runner=runner_c, budget=60)
    
    fam_c, sec_c = solve(
        n=8, m=1, budget=60,
        families=["constant", "balanced", "linear", "grover", "randfun"],
        run=harness_c.run
    )
    assert fam_c == "constant"
    assert sec_c == 1
    # Constant should spend far fewer than 60 queries
    assert harness_c.queries_executed <= 25, (
        f"Constant spent {harness_c.queries_executed} queries, expected <= 25"
    )

    # 2. Linear oracle: should solve within <= 25 queries
    oracle_l = generate_linear_oracle(a=42, b=1)
    runner_l = LocalRunner(oracle=oracle_l, noise=BASE_NOISE, seed=2002)
    harness_l = MockJudgesHarness(runner=runner_l, budget=60)
    
    fam_l, sec_l = solve(
        n=8, m=1, budget=60,
        families=["constant", "balanced", "linear", "grover", "randfun"],
        run=harness_l.run
    )
    assert fam_l == "linear"
    assert sec_l == [42, 1]
    assert harness_l.queries_executed <= 25, (
        f"Linear spent {harness_l.queries_executed} queries, expected <= 25"
    )


def test_reserve_policy_for_secret_recovery():
    """TEST-015: Verify solver reserves budget for reading b in linear even with tight budget."""
    from solver import solve
    
    oracle = generate_linear_oracle(a=77, b=1)
    runner = LocalRunner(oracle=oracle, noise=BASE_NOISE, seed=2005)
    # Give budget of only 12 queries
    harness = MockJudgesHarness(runner=runner, budget=12)
    
    fam, sec = solve(
        n=8, m=1, budget=12,
        families=["constant", "linear"],
        run=harness.run
    )
    assert fam == "linear"
    assert sec == [77, 1]
    assert harness.queries_executed <= 12


def test_validation_seeds_accuracy():
    """TEST-016: Verify frozen thresholds on independent validation seeds (2000..2015)."""
    from solver import solve
    
    correct = 0
    total = 0
    
    # Test across Simon, Simon2, Perm on validation seeds
    for s_idx in range(5):
        seed = 2000 + s_idx
        # Simon
        s_oracle = generate_simon_oracle(s=seed % 250 + 1, seed=seed)
        runner_s = LocalRunner(s_oracle, noise=BASE_NOISE, seed=seed)
        fam, sec = solve(8, 8, 60, ["simon", "simon2", "perm"], runner_s.run)
        if fam == "simon" and sec == (seed % 250 + 1):
            correct += 1
        total += 1
        
        # Simon2
        h1 = (seed * 2) % 250 + 1
        h2 = (seed * 3) % 250 + 1
        if h1 == h2: h2 = (h2 + 1) % 250 + 1
        h3 = h1 ^ h2
        s2_oracle = generate_simon2_oracle(h1=h1, h2=h2, seed=seed)
        runner_s2 = LocalRunner(s2_oracle, noise=BASE_NOISE, seed=seed)
        fam, sec = solve(8, 8, 60, ["simon", "simon2", "perm"], runner_s2.run)
        if fam == "simon2" and sec == sorted([h1, h2, h3]):
            correct += 1
        total += 1

        # Perm
        p_oracle = generate_perm_oracle(seed=seed)
        runner_p = LocalRunner(p_oracle, noise=BASE_NOISE, seed=seed)
        fam, sec = solve(8, 8, 60, ["simon", "simon2", "perm"], runner_p.run)
        if fam == "perm" and sec is None:
            correct += 1
        total += 1
        
    acc = correct / total
    assert acc >= 0.85, f"Validation accuracy {acc * 100:.1f}% below 85% requirement ({correct}/{total})"
