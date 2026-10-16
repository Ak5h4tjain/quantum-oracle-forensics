"""TEST-008: Mathematical invariants verification for all 8 oracle families.

Tests that each generator in local.oracles strictly satisfies the
mathematical definitions and invariants of its family.
"""

import pytest
import numpy as np
from local.oracles import (
    generate_constant_oracle,
    generate_balanced_oracle,
    generate_linear_oracle,
    generate_grover_oracle,
    generate_randfun_oracle,
    generate_simon_oracle,
    generate_simon2_oracle,
    generate_perm_oracle,
    OracleInstance,
)


def test_constant_oracle_invariants():
    """Constant oracle: f(x) == c for all x in 0..255, c in {0, 1}."""
    for c in [0, 1]:
        inst = generate_constant_oracle(c=c)
        assert inst.family == "constant"
        assert inst.m == 1
        assert inst.secret == c
        for x in range(256):
            assert inst.evaluate(x) == c


def test_balanced_oracle_invariants():
    """Balanced oracle: exactly 128 inputs evaluate to 0 and 128 to 1."""
    for seed in [42, 100, 2026]:
        inst = generate_balanced_oracle(seed=seed)
        assert inst.family == "balanced"
        assert inst.m == 1
        assert inst.secret is None
        outputs = [inst.evaluate(x) for x in range(256)]
        assert outputs.count(0) == 128
        assert outputs.count(1) == 128


def test_linear_oracle_invariants():
    """Linear oracle: f(x) = (a . x ^ b), a in 1..255, b in {0, 1}."""
    test_cases = [(1, 0), (255, 1), (42, 0), (137, 1)]
    for a, b in test_cases:
        inst = generate_linear_oracle(a=a, b=b)
        assert inst.family == "linear"
        assert inst.m == 1
        assert inst.secret == [a, b]
        for x in range(256):
            expected = (bin(x & a).count("1") ^ b) & 1
            assert inst.evaluate(x) == expected
            
        # Linearity check: f(x ^ y) = f(x) ^ f(y) ^ b
        for x, y in [(5, 12), (100, 200), (42, 42)]:
            assert inst.evaluate(x ^ y) == (inst.evaluate(x) ^ inst.evaluate(y) ^ b)


def test_grover_oracle_invariants():
    """Grover oracle: f(x) = 1 if x == t, else 0, for t in 0..255."""
    for t in [0, 42, 255]:
        inst = generate_grover_oracle(t=t)
        assert inst.family == "grover"
        assert inst.m == 1
        assert inst.secret == t
        for x in range(256):
            assert inst.evaluate(x) == (1 if x == t else 0)


def test_randfun_oracle_invariants():
    """Randfun oracle: pseudo-random function with output in {0, 1}."""
    for seed in [1, 2, 3]:
        inst = generate_randfun_oracle(seed=seed)
        assert inst.family == "randfun"
        assert inst.m == 1
        assert inst.secret is None
        outputs = [inst.evaluate(x) for x in range(256)]
        for y in outputs:
            assert y in (0, 1)


def test_simon_oracle_invariants():
    """Simon oracle: 2-to-1 function where f(x ^ s) = f(x) for s in 1..255."""
    for s in [1, 42, 255]:
        inst = generate_simon_oracle(s=s, seed=123)
        assert inst.family == "simon"
        assert inst.m == 8
        assert inst.secret == s
        values_seen = {}
        for x in range(256):
            fx = inst.evaluate(x)
            assert 0 <= fx < 256
            # Period property
            assert inst.evaluate(x ^ s) == fx
            if fx in values_seen:
                assert values_seen[fx] in (x, x ^ s)
            else:
                values_seen[fx] = x
        assert len(values_seen) == 128  # Exactly 128 unique pairs


def test_simon2_oracle_invariants():
    """Simon2 oracle: 4-to-1 function with 2D subspace H = {0, h1, h2, h3} under XOR."""
    # Test with basis e1, e2
    for h1, h2 in [(1, 2), (3, 5), (10, 20)]:
        h3 = h1 ^ h2
        H_expected = sorted([h1, h2, h3])
        inst = generate_simon2_oracle(h1=h1, h2=h2, seed=99)
        assert inst.family == "simon2"
        assert inst.m == 8
        assert inst.secret == H_expected
        assert len(H_expected) == 3
        # Subspace closure check
        full_H = [0] + H_expected
        for a in full_H:
            for b in full_H:
                assert (a ^ b) in full_H
                
        # 4-to-1 check
        values_seen = {}
        for x in range(256):
            fx = inst.evaluate(x)
            assert 0 <= fx < 256
            for h in full_H:
                assert inst.evaluate(x ^ h) == fx
            if fx not in values_seen:
                values_seen[fx] = set()
            values_seen[fx].add(x)
            
        assert len(values_seen) == 64  # Exactly 64 cosets of size 4
        for coset in values_seen.values():
            assert len(coset) == 4


def test_perm_oracle_invariants():
    """Perm oracle: Bijective function from 0..255 to 0..255."""
    for seed in [10, 20, 30]:
        inst = generate_perm_oracle(seed=seed)
        assert inst.family == "perm"
        assert inst.m == 8
        assert inst.secret is None
        outputs = [inst.evaluate(x) for x in range(256)]
        assert len(set(outputs)) == 256
