"""Baselines BL-001 through BL-004 for Quantum Oracle Forensics.

BL-001: Uniform random guess among the allowed candidate families.
BL-002: Fixed majority-class predictor (predicts most likely family or fixed default).
BL-003: Pure classical direct query sampler (queries random classical inputs x).
BL-004: Standard textbook algorithm (BV and Simon) with no noise mitigation or adaptive stopping.
"""

from typing import Any, Callable, Dict, List, Tuple
import numpy as np
from qiskit import QuantumCircuit
from solver import (
    build_bv_circuit,
    build_simon_circuit,
    build_direct_read_circuit,
    bitstring_to_int,
    format_secret,
    fast_walsh_hadamard_transform,
)


def baseline_bl001_random(
    n: int,
    m: int,
    budget: int,
    families: List[str],
    run: Callable[[QuantumCircuit, int], Dict[str, int]],
    rng: np.random.Generator = None,
) -> Tuple[str, Any]:
    """BL-001: Pure uniform random guess among allowed families without queries."""
    if rng is None:
        rng = np.random.default_rng()
    fam = str(rng.choice(families))
    if fam == "constant":
        sec = int(rng.integers(0, 2))
    elif fam == "linear":
        sec = [int(rng.integers(1, 256)), int(rng.integers(0, 2))]
    elif fam == "grover":
        sec = int(rng.integers(0, 256))
    elif fam == "simon":
        sec = int(rng.integers(1, 256))
    elif fam == "simon2":
        h1 = int(rng.integers(1, 256))
        h2 = int(rng.integers(1, 256))
        sec = sorted([h1, h2, h1 ^ h2])
    else:
        sec = None
    return fam, format_secret(fam, sec)


def baseline_bl002_fixed(
    n: int,
    m: int,
    budget: int,
    families: List[str],
    run: Callable[[QuantumCircuit, int], Dict[str, int]],
) -> Tuple[str, Any]:
    """BL-002: Fixed constant predictor (predicts first valid family)."""
    fam = families[0]
    return fam, format_secret(fam, 0)


def baseline_bl003_classical_sampling(
    n: int,
    m: int,
    budget: int,
    families: List[str],
    run: Callable[[QuantumCircuit, int], Dict[str, int]],
    rng: np.random.Generator = None,
) -> Tuple[str, Any]:
    """BL-003: Pure classical direct query sampling (queries up to budget inputs)."""
    if rng is None:
        rng = np.random.default_rng()
        
    queried = {}
    shots_to_use = min(budget, 32)
    sample_inputs = rng.choice(2**n, size=shots_to_use, replace=False)
    
    for x in sample_inputs:
        qc = build_direct_read_circuit(n, m, int(x))
        cnts = run(qc, shots=1)
        if cnts:
            bstr = list(cnts.keys())[0]
            queried[int(x)] = bitstring_to_int(bstr)
            
    # Classify based on queried values
    outputs = list(queried.values())
    if m == 1:
        ones = outputs.count(1)
        zeros = outputs.count(0)
        if ones == len(outputs) and "constant" in families:
            return "constant", 1
        elif zeros == len(outputs) and "constant" in families:
            return "constant", 0
        elif "balanced" in families:
            return "balanced", None
        else:
            return families[0], None
    else:
        # Check for collisions f(x) == f(y)
        seen = {}
        for x, fx in queried.items():
            if fx in seen:
                collision_xor = x ^ seen[fx]
                if "simon" in families and collision_xor != 0:
                    return "simon", collision_xor
            seen[fx] = x
        if "perm" in families:
            return "perm", None
        else:
            return families[0], None


def baseline_bl004_textbook(
    n: int,
    m: int,
    budget: int,
    families: List[str],
    run: Callable[[QuantumCircuit, int], Dict[str, int]],
) -> Tuple[str, Any]:
    """BL-004: Naive textbook algorithm (consumes full budget, no noise mitigation)."""
    if m == 1:
        qc = build_bv_circuit(n)
        cnts = run(qc, shots=min(budget, 30))
        best_bstr = max(cnts.items(), key=lambda it: it[1])[0]
        val = bitstring_to_int(best_bstr)
        if val == 0:
            return ("constant", 0) if "constant" in families else (families[0], None)
        else:
            return ("linear", [val, 0]) if "linear" in families else (families[0], None)
    else:
        qc = build_simon_circuit(n, m)
        cnts = run(qc, shots=min(budget, 40))
        c_vec = np.zeros(256, dtype=int)
        for bstr, c in cnts.items():
            c_vec[bitstring_to_int(bstr)] = c
        scores = fast_walsh_hadamard_transform(c_vec)[1:]
        best_cand = int(np.argmax(scores) + 1)
        if "simon" in families:
            return "simon", best_cand
        elif "perm" in families:
            return "perm", None
        else:
            return families[0], None
