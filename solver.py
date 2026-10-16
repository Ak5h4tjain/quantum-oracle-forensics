"""Quantum Oracle Forensics - Official Solver.

Rules:
- Self-contained file importing only standard library, numpy, scipy, and qiskit.
- Never imports from local/ or any external helper package.
- All quantum circuit queries to run(circuit, shots) are strictly charged through
  the QueryLedger prior to execution (charge-before-call). Hard budget limit = 60.
- No hardcoded answers, seed lookups, or frame introspection.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Set
import math
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Gate

ALL_FAMILIES = [
    "constant",
    "balanced",
    "linear",
    "grover",
    "randfun",
    "simon",
    "simon2",
    "simon3",
    "perm",
]


# ============================================================================
# 1. QUERY LEDGER (ARC-02: Charge-before-call)
# ============================================================================

class QueryLedger:
    """Strict query accountant.
    
    Guarantees:
    - Every run() call is counted: cost = (oracle gates in circuit) * shots.
    - Charge occurs BEFORE calling the harness run().
    - Never exceeds the allotted budget.
    """
    def __init__(
        self,
        run_fn: Callable[[QuantumCircuit, int], Dict[str, int]],
        budget: int = 60,
    ):
        self.run_fn = run_fn
        self.budget = budget
        self.spent = 0

    @property
    def remaining(self) -> int:
        return max(0, self.budget - self.spent)

    def charge_and_run(self, circuit: QuantumCircuit, shots: int) -> Dict[str, int]:
        if shots <= 0:
            return {}
        
        oracle_gates = sum(1 for inst in circuit.data if inst.operation.name == "oracle")
        if oracle_gates == 0:
            raise ValueError("Circuit submitted to run() must contain at least one 'oracle' gate.")
            
        cost = oracle_gates * shots
        if self.spent + cost > self.budget:
            raise RuntimeError(
                f"Ledger budget exceeded: tried to charge {cost} queries with {self.remaining} remaining!"
            )
            
        # Charge first
        self.spent += cost
        # Execute second
        return self.run_fn(circuit, shots)


# ============================================================================
# 2. CIRCUIT BUILDERS (Modern Qiskit 2.x standard)
# ============================================================================

def build_bv_circuit(n: int) -> QuantumCircuit:
    """Bernstein-Vazirani / phase-kickback circuit on n+1 qubits."""
    qc = QuantumCircuit(n + 1, n)
    # Target qubit in |-> = X H |0>
    qc.x(n)
    qc.h(n)
    # Input qubits in |+>^n
    qc.h(range(n))
    
    # Sealed oracle gate
    qc.append(Gate("oracle", n + 1, []), range(n + 1))
    
    # Uncompute input register
    qc.h(range(n))
    for i in range(n):
        qc.measure(i, i)
    return qc


def build_simon_circuit(n: int, m: int) -> QuantumCircuit:
    """Simon-style sampling circuit on n+m qubits measuring input register."""
    qc = QuantumCircuit(n + m, n)
    qc.h(range(n))
    qc.append(Gate("oracle", n + m, []), range(n + m))
    qc.h(range(n))
    for i in range(n):
        qc.measure(i, i)
    return qc


def build_direct_read_circuit(n: int, m: int, x: int) -> QuantumCircuit:
    """Direct query of f(x) by preparing x on input qubits and measuring target qubits."""
    qc = QuantumCircuit(n + m, m)
    for i in range(n):
        if (x >> i) & 1:
            qc.x(i)
    qc.append(Gate("oracle", n + m, []), range(n + m))
    for j in range(m):
        qc.measure(n + j, j)
    return qc


def build_grover_circuit(n: int, k_steps: int) -> QuantumCircuit:
    """Grover amplification circuit on n+1 qubits with k_steps iterations."""
    qc = QuantumCircuit(n + 1, n)
    # Target in |->
    qc.x(n)
    qc.h(n)
    # Input in |+>^n
    qc.h(range(n))
    
    for _ in range(k_steps):
        # Oracle query
        qc.append(Gate("oracle", n + 1, []), range(n + 1))
        # Grover diffusion operator D = 2|s><s| - I
        qc.h(range(n))
        qc.x(range(n))
        # Multi-controlled Z using MCX surrounded by H on target
        qc.h(n - 1)
        qc.mcx(list(range(n - 1)), n - 1)
        qc.h(n - 1)
        qc.x(range(n))
        qc.h(range(n))
        
    for i in range(n):
        qc.measure(i, i)
    return qc


# ============================================================================
# 3. DECODERS & TRANSFORMS
# ============================================================================

def bitstring_to_int(bitstring: str) -> int:
    """Parses Qiskit little-endian bitstring to integer.
    
    In Qiskit counts, classical bit 0 is at string[-1].
    """
    val = 0
    for i, char in enumerate(reversed(bitstring)):
        if char == "1":
            val |= (1 << i)
    return val


def fast_walsh_hadamard_transform(counts: np.ndarray) -> np.ndarray:
    """Fast Walsh-Hadamard Transform (FWHT) in O(N log N).
    
    Computes S(v) = sum_{y=0}^{255} C(y) (-1)^{y . v} for all v in 0..255.
    """
    a = counts.astype(float).copy()
    h = 1
    while h < len(a):
        for i in range(0, len(a), h * 2):
            for j in range(i, i + h):
                x = a[j]
                y = a[j + h]
                a[j] = x + y
                a[j + h] = x - y
        h *= 2
    return a


def format_secret(family: str, raw_secret: Any) -> Any:
    """Formats secret strictly according to challenge requirements (AMB-06, SRS)."""
    if family == "constant":
        return 0 if raw_secret is None else int(raw_secret)
    elif family == "balanced":
        return None
    elif family == "linear":
        if isinstance(raw_secret, (list, tuple)) and len(raw_secret) == 2:
            return [int(raw_secret[0]), int(raw_secret[1])]
        return [1, 0]
    elif family == "grover":
        return 0 if raw_secret is None else int(raw_secret)
    elif family == "randfun":
        return None
    elif family == "simon":
        return 1 if raw_secret is None else int(raw_secret)
    elif family == "simon2":
        if isinstance(raw_secret, (list, tuple, set)):
            sorted_h = sorted(int(h) for h in raw_secret if int(h) != 0)
            if len(sorted_h) == 3:
                return sorted_h
        return [1, 2, 3]
    elif family == "simon3":
        if isinstance(raw_secret, (list, tuple, set)):
            sorted_h = sorted(int(h) for h in raw_secret if int(h) != 0)
            if len(sorted_h) == 7:
                return sorted_h
        return [1, 2, 3, 4, 5, 6, 7]
    elif family == "perm":
        return None
    return raw_secret


# ============================================================================
# 3.5. ERROR MITIGATION EXTENSIONS (Section 11)
# ============================================================================

def mitigate_misfire_bias(p0_observed: float, p_misfire: float = 0.04) -> float:
    """Linear inversion error mitigation for oracle misfire identity bias."""
    return max(0.0, (p0_observed - p_misfire) / (1.0 - p_misfire))


def mitigate_readout_score(score: float, p_flip: float = 0.02, n_bits: int = 8) -> float:
    """Unbiases Walsh transform score against symmetric readout flip noise."""
    attenuation = (1.0 - 2.0 * p_flip) ** n_bits
    if attenuation <= 1e-4:
        return score
    return score / attenuation


# ============================================================================
# 4. FAMILY-SPECIFIC CONTROLLERS
# ============================================================================

def direct_read_majority(n: int, m: int, x: int, ledger: QueryLedger, shots: int = 3) -> int:
    """Performs direct queries of f(x) and returns majority output."""
    avail_shots = min(shots, ledger.remaining)
    if avail_shots <= 0:
        return 0
    qc = build_direct_read_circuit(n, m, x)
    counts = ledger.charge_and_run(qc, shots=avail_shots)
    if not counts:
        return 0
    # Find most common bitstring
    best_str = max(counts.items(), key=lambda item: item[1])[0]
    return bitstring_to_int(best_str)


def solve_m8(
    n: int,
    m: int,
    ledger: QueryLedger,
    families: List[str],
) -> Tuple[str, Any]:
    """Solves m = 8 oracles: simon, simon2, perm using Walsh-Hadamard transform.
    
    Calibrated empirically across E-05 under both Base (N1) and Stress (N2) noise:
    - 48 shots provides clean margin: signal ~38, background noise max ~22.
    - Simon exhibits a solitary peak (s1 >= 0.62*shots) with a gap >= 10 over runner-up.
    - Simon2 exhibits an XOR triad where both top peaks and their XOR have score >= 0.45*shots.
    - Permutation exhibits no triad and no large peak.
    """
    simon_shots = min(48, ledger.remaining)
    if simon_shots <= 0:
        choice = families[0]
        return choice, format_secret(choice, 1)

    qc_simon = build_simon_circuit(n, m)
    counts = ledger.charge_and_run(qc_simon, shots=simon_shots)
    
    # Vectorize counts over 2^n states
    c_vec = np.zeros(2**n, dtype=int)
    for bstr, cnt in counts.items():
        c_vec[bitstring_to_int(bstr)] = cnt
        
    # Compute Walsh-Hadamard spectrum
    scores = fast_walsh_hadamard_transform(c_vec)
    non_zero_scores = scores[1:]  # index 0 corresponds to v=1
    
    # Order statistics: sort candidate vectors (1..255) by score descending
    sorted_order = np.argsort(non_zero_scores)[::-1]
    sorted_candidates = sorted_order + 1
    sorted_scores = non_zero_scores[sorted_order]

    c1 = int(sorted_candidates[0])
    s1 = float(sorted_scores[0])
    c2 = int(sorted_candidates[1])
    s2 = float(sorted_scores[1])
    gap12 = s1 - s2

    # Branch 1: Simon (Single solitary peak with large gap over noise runner-up)
    if "simon" in families and s1 >= 0.62 * simon_shots and gap12 >= 10.0:
        return "simon", c1

    # Branch 1.5: Extension - Simon3 (3D Hidden Subspace, 7 non-zero elements)
    if "simon3" in families and s1 >= 0.50 * simon_shots:
        cand_pool = [int(c) for c in sorted_candidates[:12] if scores[c] >= 0.38 * simon_shots]
        if len(cand_pool) >= 7:
            for i in range(len(cand_pool)):
                for j in range(i + 1, len(cand_pool)):
                    for k in range(j + 1, len(cand_pool)):
                        v1, v2, v3 = cand_pool[i], cand_pool[j], cand_pool[k]
                        span = {v1, v2, v3, v1 ^ v2, v1 ^ v3, v2 ^ v3, v1 ^ v2 ^ v3}
                        if len(span) == 7 and all(scores[v] >= 0.35 * simon_shots for v in span):
                            return "simon3", sorted(list(span))

    # Branch 2: Simon2 Subspace Triad Check
    if "simon2" in families and s1 >= 0.55 * simon_shots and s2 >= 0.50 * simon_shots:
        c_xor = c1 ^ c2
        if c_xor in sorted_candidates[:6] and scores[c_xor] >= 0.45 * simon_shots:
            return "simon2", sorted([c1, c2, c_xor])

    # Branch 3: Simon fallback if prominent peak exists
    if "simon" in families and s1 >= 0.70 * simon_shots:
        return "simon", c1

    # Branch 4: Permutation
    if "perm" in families:
        return "perm", None
    elif "simon" in families:
        return "simon", c1
    elif "simon2" in families:
        return "simon2", sorted([c1, c2, c1 ^ c2])
    elif "simon3" in families:
        cand_pool = [int(c) for c in sorted_candidates[:7]]
        return "simon3", sorted(cand_pool)
    else:
        return families[0], None


def solve_m1(
    n: int,
    m: int,
    ledger: QueryLedger,
    families: List[str],
) -> Tuple[str, Any]:
    """Solves m = 1 oracles: constant, balanced, linear, grover, randfun."""
    # If only one candidate in families, handle immediately
    if len(families) == 1:
        fam = families[0]
        if fam == "constant":
            c = direct_read_majority(n, m, 0, ledger, shots=min(3, ledger.remaining))
            return "constant", c
        elif fam == "linear":
            # Reserve 1 shot for reading b
            bv_shots = min(4, max(1, ledger.remaining - 1)) if ledger.remaining > 1 else 1
            counts = ledger.charge_and_run(build_bv_circuit(n), shots=bv_shots)
            best_a = max(counts.items(), key=lambda item: item[1])[0]
            a = bitstring_to_int(best_a)
            b = direct_read_majority(n, m, 0, ledger, shots=1) if ledger.remaining > 0 else 0
            return "linear", [max(1, a), b]
    if ledger.remaining <= 0:
        choice = families[0]
        return choice, format_secret(choice, 0)

    # Reserve policy: preserve queries for reading b or verifying t
    needs_secret = any(f in ("linear", "constant", "grover") for f in families)
    reserve = 2 if needs_secret else 0
    if ledger.remaining > reserve:
        bv_shots = min(16, ledger.remaining - reserve)
    else:
        bv_shots = ledger.remaining
    
    qc_bv = build_bv_circuit(n)
    counts = ledger.charge_and_run(qc_bv, shots=bv_shots)
    
    total_bv = sum(counts.values())
    if total_bv == 0:
        return families[0], format_secret(families[0], 0)

    # Analyze BV counts
    int_counts: Dict[int, int] = {}
    for bstr, cnt in counts.items():
        int_counts[bitstring_to_int(bstr)] = cnt

    zero_count = int_counts.get(0, 0)
    zero_ratio = zero_count / total_bv

    # Find dominant non-zero string
    non_zero_counts = {k: v for k, v in int_counts.items() if k != 0}
    dominant_a, dominant_cnt = (0, 0)
    if non_zero_counts:
        dominant_a, dominant_cnt = max(non_zero_counts.items(), key=lambda item: item[1])
    dominant_ratio = dominant_cnt / total_bv

    # Branch 1: Linear oracle
    if dominant_ratio >= 0.45 and "linear" in families:
        b_val = 0
        if ledger.remaining > 0:
            b_val = direct_read_majority(n, m, 0, ledger, shots=min(2, ledger.remaining))
        return "linear", [dominant_a, b_val]

    # Branch 2: Constant or Grover (both have high zero_ratio in BV)
    if zero_ratio >= 0.50:
        # Direct read at x = 0
        f0 = direct_read_majority(n, m, 0, ledger, shots=min(3, ledger.remaining))
        
        if f0 == 1:
            # Could be constant-1 or grover with t=0
            f1 = direct_read_majority(n, m, 1, ledger, shots=min(3, ledger.remaining))
            if f1 == 1:
                if "constant" in families:
                    return "constant", 1
            else:
                if "grover" in families:
                    return "grover", 0
                elif "constant" in families:
                    return "constant", 1
        else:
            # f(0) == 0: could be constant-0 or grover with t != 0
            if "grover" in families and ledger.remaining >= 12:
                # Run Grover amplification (k=5 iterations, 2 shots = 10 queries)
                k_steps = 5
                shots_to_run = min(2, ledger.remaining // k_steps)
                qc_grover = build_grover_circuit(n, k_steps=k_steps)
                grover_counts = ledger.charge_and_run(qc_grover, shots=shots_to_run)
                
                # Check candidate t
                if grover_counts:
                    candidate_t_str = max(grover_counts.items(), key=lambda item: item[1])[0]
                    t_cand = bitstring_to_int(candidate_t_str)
                    
                    # Verification read on candidate t
                    if ledger.remaining > 0:
                        ft = direct_read_majority(n, m, t_cand, ledger, shots=min(2, ledger.remaining))
                        if ft == 1:
                            return "grover", t_cand
                            
            if "constant" in families:
                return "constant", 0
            elif "grover" in families:
                return "grover", 0

    # Branch 3: Balanced vs Randfun
    if "balanced" in families and "randfun" not in families:
        return "balanced", None
    elif "randfun" in families and "balanced" not in families:
        return "randfun", None
    elif "balanced" in families and "randfun" in families:
        # Balanced has exactly 128 ones (P(f(x)=1) = 0.50).
        # Randfun has each f(x)=1 independently with probability 0.30.
        read_queries = min(8, ledger.remaining)
        ones_count = 0
        sample_pts = [11, 47, 83, 119, 155, 191, 227, 251][:read_queries]
        for pt in sample_pts:
            ones_count += direct_read_majority(n, m, pt, ledger, shots=1)
        
        if read_queries >= 6:
            if ones_count >= 4 or (ones_count == 3 and zero_ratio <= 0.08):
                return "balanced", None
            else:
                return "randfun", None
        else:
            if zero_ratio <= 0.08:
                return "balanced", None
            else:
                return "randfun", None

    # Default fallback
    choice = families[0]
    return choice, format_secret(choice, 0)


# ============================================================================
# 5. OFFICIAL SOLVE ENTRYPOINT
# ============================================================================

def solve(
    n: int,
    m: int,
    budget: int,
    families: List[str],
    run: Callable[[QuantumCircuit, int], Dict[str, int]],
) -> Tuple[str, Any]:
    """Main solver entrypoint as specified by the hackathon challenge.
    
    Args:
        n: Number of input bits (always 8)
        m: Number of output bits (1 or 8)
        budget: Maximum total queries allowed (always <= 60)
        families: Subset of family names the oracle may belong to
        run: Harness execution function run(circuit, shots) -> counts
        
    Returns:
        (family, secret)
    """
    ledger = QueryLedger(run_fn=run, budget=budget)
    
    # Filter candidates by output width m
    m1_set = {"constant", "balanced", "linear", "grover", "randfun"}
    m8_set = {"simon", "simon2", "simon3", "perm"}
    
    valid_candidates = [f for f in families if (f in m1_set if m == 1 else f in m8_set)]
    if not valid_candidates:
        valid_candidates = families
        
    if m == 8:
        family, secret = solve_m8(n, m, ledger, valid_candidates)
    else:
        family, secret = solve_m1(n, m, ledger, valid_candidates)
        
    return family, format_secret(family, secret)
