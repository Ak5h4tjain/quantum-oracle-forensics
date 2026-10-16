"""TEST-002 to TEST-007: Reference example tests.

Verifies the deterministic public reference examples for each family:
- TEST-002: constant reference instances (c=0, c=1)
- TEST-003: linear reference instances (a=1 b=0, a=255 b=1)
- TEST-004: grover reference instances (t=0, t=1)
- TEST-005: simon reference instances (s=1)
- TEST-006: simon2 reference instances (h1=1, h2=2 -> H=[1, 2, 3])
- TEST-007: perm reference instance (identity permutation)
"""

import pytest
from local.oracles import (
    get_reference_oracle,
    OracleInstance,
)


def test_ref_constant_0():
    """TEST-002: Reference constant-0 oracle."""
    oracle = get_reference_oracle("constant-0")
    assert oracle.family == "constant"
    assert oracle.m == 1
    assert oracle.secret == 0
    for x in range(256):
        assert oracle.evaluate(x) == 0


def test_ref_constant_1():
    """TEST-002: Reference constant-1 oracle."""
    oracle = get_reference_oracle("constant-1")
    assert oracle.family == "constant"
    assert oracle.m == 1
    assert oracle.secret == 1
    for x in range(256):
        assert oracle.evaluate(x) == 1


def test_ref_linear():
    """TEST-003: Reference linear oracle (a=1, b=0)."""
    oracle = get_reference_oracle("linear-1-0")
    assert oracle.family == "linear"
    assert oracle.m == 1
    assert oracle.secret == [1, 0]
    for x in range(256):
        assert oracle.evaluate(x) == (x & 1)


def test_ref_grover():
    """TEST-004: Reference grover oracle (t=0)."""
    oracle = get_reference_oracle("grover-0")
    assert oracle.family == "grover"
    assert oracle.m == 1
    assert oracle.secret == 0
    assert oracle.evaluate(0) == 1
    for x in range(1, 256):
        assert oracle.evaluate(x) == 0


def test_ref_simon():
    """TEST-005: Reference simon oracle (s=1)."""
    oracle = get_reference_oracle("simon-1")
    assert oracle.family == "simon"
    assert oracle.m == 8
    assert oracle.secret == 1
    for x in range(256):
        assert oracle.evaluate(x) == oracle.evaluate(x ^ 1)


def test_ref_simon2():
    """TEST-006: Reference simon2 oracle (H=[1, 2, 3])."""
    oracle = get_reference_oracle("simon2-1-2")
    assert oracle.family == "simon2"
    assert oracle.m == 8
    assert oracle.secret == [1, 2, 3]
    for x in range(256):
        for h in [0, 1, 2, 3]:
            assert oracle.evaluate(x) == oracle.evaluate(x ^ h)


def test_ref_perm():
    """TEST-007: Reference perm oracle (identity permutation)."""
    oracle = get_reference_oracle("perm-identity")
    assert oracle.family == "perm"
    assert oracle.m == 8
    assert oracle.secret is None
    for x in range(256):
        assert oracle.evaluate(x) == x


def test_section4_exact_check_values():
    """Verifies all exact check values from Section 4 table in the PDF specification."""
    # 1. Linear: a = 178, b = 1
    lin = get_reference_oracle("ref-linear")
    assert lin.evaluate(0) == 1
    assert lin.evaluate(1) == 1
    assert lin.evaluate(2) == 0
    assert lin.evaluate(255) == 1
    assert lin.secret == [178, 1]

    # 2. Simon: s = 105, f(x) = min(x, x ^ s)
    sim = get_reference_oracle("ref-simon")
    assert sim.evaluate(5) == 5
    assert sim.evaluate(108) == 5
    assert sim.evaluate(105) == 0
    assert sim.evaluate(200) == 161
    assert sim.secret == 105

    # 3. Simon2: H = {0, 15, 49, 62}, f(x) = min over h in H of (x ^ h)
    sim2 = get_reference_oracle("ref-simon2")
    assert sim2.evaluate(0) == 0
    assert sim2.evaluate(15) == 0
    assert sim2.evaluate(49) == 0
    assert sim2.evaluate(62) == 0
    assert sim2.evaluate(1) == 1
    assert sim2.evaluate(200) == 199
    assert sim2.secret == [15, 49, 62]

    # 4. Perm: f(x) = (37x + 11) mod 256
    p = get_reference_oracle("ref-perm")
    assert p.evaluate(0) == 11
    assert p.evaluate(1) == 48
    assert p.evaluate(2) == 85
    assert p.evaluate(255) == 230
    assert p.secret is None

    # 5. Grover: t = 173
    grv = get_reference_oracle("ref-grover")
    assert grv.evaluate(173) == 1
    assert grv.evaluate(0) == 0
    assert grv.evaluate(100) == 0
    assert grv.secret == 173

    # 6. Constant: c = 1
    cst = get_reference_oracle("ref-constant-1")
    assert all(cst.evaluate(x) == 1 for x in [0, 1, 42, 100, 255])
    assert cst.secret == 1
