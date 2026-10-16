"""Oracle generators for all eight function families and reference instances.

Families:
- constant (m=1): f(x) = c, secret = c in {0, 1}
- balanced (m=1): sum f(x) = 128, secret = None
- linear (m=1): f(x) = a*x ^ b, secret = [a, b], a in 1..255, b in {0, 1}
- grover (m=1): f(x) = 1 if x == t else 0, secret = t in 0..255
- randfun (m=1): random function, secret = None
- simon (m=8): 2-to-1 with f(x ^ s) = f(x), secret = s in 1..255
- simon2 (m=8): 4-to-1 with 2D subspace H={0, h1, h2, h3}, secret = [h1, h2, h3] sorted
- perm (m=8): permutation of 0..255, secret = None
"""

from dataclasses import dataclass
from typing import Any, Callable, List, Optional
import numpy as np
from qiskit.quantum_info import Operator


@dataclass
class OracleInstance:
    family: str
    n: int
    m: int
    secret: Any
    table: np.ndarray  # Shape (2^n,), maps input x to output f(x)

    def evaluate(self, x: int) -> int:
        return int(self.table[x])

    def as_unitary(self) -> np.ndarray:
        """Constructs the (2^(n+m) x 2^(n+m)) unitary matrix for U|x>|y> = |x>|y ^ f(x)>.
        
        Qiskit endianness convention:
        input state index = x + y * 2^n = (y << n) | x
        where x is on qubits 0..n-1 and y is on qubits n..n+m-1.
        """
        dim = 2 ** (self.n + self.m)
        mat = np.zeros((dim, dim), dtype=complex)
        for x in range(2 ** self.n):
            fx = int(self.table[x])
            for y in range(2 ** self.m):
                in_idx = (y << self.n) | x
                out_idx = ((y ^ fx) << self.n) | x
                mat[out_idx, in_idx] = 1.0
        return mat

    def as_operator(self) -> Operator:
        """Returns Qiskit Operator representation."""
        return Operator(self.as_unitary())


def generate_constant_oracle(c: int, n: int = 8) -> OracleInstance:
    assert c in (0, 1)
    table = np.full(2**n, c, dtype=int)
    return OracleInstance(family="constant", n=n, m=1, secret=c, table=table)


def generate_balanced_oracle(seed: int = 42, n: int = 8) -> OracleInstance:
    rng = np.random.default_rng(seed)
    table = np.zeros(2**n, dtype=int)
    ones_indices = rng.choice(2**n, size=2**(n - 1), replace=False)
    table[ones_indices] = 1
    return OracleInstance(family="balanced", n=n, m=1, secret=None, table=table)


def generate_linear_oracle(a: int, b: int, n: int = 8) -> OracleInstance:
    assert 1 <= a < 2**n
    assert b in (0, 1)
    table = np.zeros(2**n, dtype=int)
    for x in range(2**n):
        table[x] = (bin(x & a).count("1") ^ b) & 1
    return OracleInstance(family="linear", n=n, m=1, secret=[a, b], table=table)


def generate_grover_oracle(t: int, n: int = 8) -> OracleInstance:
    assert 0 <= t < 2**n
    table = np.zeros(2**n, dtype=int)
    table[t] = 1
    return OracleInstance(family="grover", n=n, m=1, secret=t, table=table)


def generate_randfun_oracle(seed: int = 42, n: int = 8) -> OracleInstance:
    """Randfun oracle: each f(x) = 1 independently with probability 0.3."""
    rng = np.random.default_rng(seed)
    table = (rng.random(2**n) < 0.3).astype(int)
    return OracleInstance(family="randfun", n=n, m=1, secret=None, table=table)


def generate_simon_oracle(s: int, seed: int = 42, n: int = 8) -> OracleInstance:
    assert 1 <= s < 2**n
    rng = np.random.default_rng(seed)
    table = np.full(2**n, -1, dtype=int)
    available_outputs = rng.permutation(2**n)
    assigned_idx = 0
    for x in range(2**n):
        if table[x] == -1:
            val = available_outputs[assigned_idx]
            assigned_idx += 1
            table[x] = val
            table[x ^ s] = val
    return OracleInstance(family="simon", n=n, m=8, secret=s, table=table)


def generate_simon2_oracle(h1: int, h2: int, seed: int = 42, n: int = 8) -> OracleInstance:
    assert 1 <= h1 < 2**n
    assert 1 <= h2 < 2**n
    assert h1 != h2
    h3 = h1 ^ h2
    assert h3 != 0
    H = [0, h1, h2, h3]
    H_secret = sorted([h1, h2, h3])
    rng = np.random.default_rng(seed)
    table = np.full(2**n, -1, dtype=int)
    available_outputs = rng.permutation(2**n)
    assigned_idx = 0
    for x in range(2**n):
        if table[x] == -1:
            val = available_outputs[assigned_idx]
            assigned_idx += 1
            for h in H:
                table[x ^ h] = val
    return OracleInstance(family="simon2", n=n, m=8, secret=H_secret, table=table)


def generate_simon3_oracle(h1: int, h2: int, h3: int, seed: int = 42, n: int = 8) -> OracleInstance:
    """Extension: 3-Dimensional Hidden Subspace H (8-to-1 function).
    
    H is a 3D subspace spanned by linearly independent h1, h2, h3.
    Contains 2^3 = 8 elements (7 non-zero elements).
    """
    assert 1 <= h1 < 2**n
    assert 1 <= h2 < 2**n
    assert 1 <= h3 < 2**n
    # Verify linear independence over GF(2)
    H_set = {
        0,
        h1,
        h2,
        h3,
        h1 ^ h2,
        h1 ^ h3,
        h2 ^ h3,
        h1 ^ h2 ^ h3,
    }
    assert len(H_set) == 8, "Vectors h1, h2, h3 must be linearly independent over GF(2)!"
    H_secret = sorted(h for h in H_set if h != 0)

    rng = np.random.default_rng(seed)
    table = np.full(2**n, -1, dtype=int)
    available_outputs = rng.permutation(2**n)
    assigned_idx = 0
    for x in range(2**n):
        if table[x] == -1:
            val = available_outputs[assigned_idx]
            assigned_idx += 1
            for h in H_set:
                table[x ^ h] = val
    return OracleInstance(family="simon3", n=n, m=8, secret=H_secret, table=table)


def generate_perm_oracle(seed: int = 42, n: int = 8) -> OracleInstance:
    rng = np.random.default_rng(seed)
    table = rng.permutation(2**n)
    return OracleInstance(family="perm", n=n, m=8, secret=None, table=table)


def get_reference_oracle(name: str) -> OracleInstance:
    """Returns the official deterministic public reference examples from Section 4."""
    if name in ("constant-0", "ref-constant-0"):
        return generate_constant_oracle(c=0)
    elif name in ("constant-1", "ref-constant-1"):
        # Section 4: constant c=1, f(x)=1 for all x
        return generate_constant_oracle(c=1)
    elif name in ("linear-1-0", "linear-1"):
        return generate_linear_oracle(a=1, b=0)
    elif name in ("linear-178-1", "ref-linear"):
        # Section 4: linear a=178, b=1 -> f(0)=1, f(1)=1, f(2)=0, f(255)=1
        return generate_linear_oracle(a=178, b=1)
    elif name in ("grover-0", "grover"):
        return generate_grover_oracle(t=0)
    elif name in ("grover-173", "ref-grover"):
        # Section 4: grover t=173 -> f(173)=1, f(x)=0 otherwise
        return generate_grover_oracle(t=173)
    elif name in ("simon-1", "simon"):
        table = np.zeros(256, dtype=int)
        for x in range(256):
            table[x] = (x // 2)
        return OracleInstance(family="simon", n=8, m=8, secret=1, table=table)
    elif name in ("simon-105", "ref-simon"):
        # Section 4: simon s=105, f(x)=min(x, x ^ s) -> f(5)=5, f(108)=5, f(105)=0, f(200)=161
        s = 105
        table = np.array([min(x, x ^ s) for x in range(256)], dtype=int)
        return OracleInstance(family="simon", n=8, m=8, secret=s, table=table)
    elif name in ("simon2-1-2", "simon2"):
        table = np.zeros(256, dtype=int)
        for x in range(256):
            table[x] = (x // 4)
        return OracleInstance(family="simon2", n=8, m=8, secret=[1, 2, 3], table=table)
    elif name in ("simon2-15-49", "ref-simon2"):
        # Section 4: simon2 H={0, 15, 49, 62}, f(x)=min over h in H of (x ^ h)
        H = [0, 15, 49, 62]
        table = np.array([min(x ^ h for h in H) for x in range(256)], dtype=int)
        return OracleInstance(family="simon2", n=8, m=8, secret=[15, 49, 62], table=table)
    elif name in ("perm-identity", "perm"):
        table = np.arange(256, dtype=int)
        return OracleInstance(family="perm", n=8, m=8, secret=None, table=table)
    elif name in ("perm-37x11", "ref-perm"):
        # Section 4: perm f(x)=(37x + 11) mod 256 -> f(0)=11, f(1)=48, f(2)=85, f(255)=230
        table = np.array([(37 * x + 11) % 256 for x in range(256)], dtype=int)
        return OracleInstance(family="perm", n=8, m=8, secret=None, table=table)
    else:
        raise ValueError(f"Unknown reference oracle name: {name}")
