"""Local harness simulator implementing run(circuit, shots).

Matches the judges' official harness:
- Signature: run(circuit: QuantumCircuit, shots: int) -> dict[str, int]
- Enforces <= 20 qubits.
- Replaces Gate("oracle", n+m, []) with the sealed oracle behavior.
- Injects oracle misfire noise (acts as identity).
- Injects readout bit-flip noise on classical measurement registers.
- Returns Qiskit counts dictionary (little-endian: bit 0 is at string[-1]).
"""

from typing import Dict, List, Optional
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from local.oracles import OracleInstance
from local.noise import NoiseModel, BASE_NOISE


class LocalRunner:
    def __init__(
        self,
        oracle: OracleInstance,
        noise: NoiseModel = BASE_NOISE,
        seed: Optional[int] = None,
    ):
        self.oracle = oracle
        self.noise = noise
        self.rng = np.random.default_rng(seed)

    def validate_circuit(self, circuit: QuantumCircuit) -> None:
        if circuit.num_qubits > 20:
            raise ValueError(f"Circuit has {circuit.num_qubits} qubits; maximum allowed is <= 20 qubits.")
        if circuit.num_clbits == 0:
            raise ValueError("Circuit must have at least 1 classical bit for measurement.")
        
        has_oracle = any(inst.operation.name == "oracle" for inst in circuit.data)
        if not has_oracle:
            raise ValueError("Circuit must contain at least one placeholder 'oracle' gate.")

    def _build_oracle_permutation(self, circuit_qubits: int, oracle_qubits: List[int]) -> np.ndarray:
        """Precomputes basis state permutation map for the oracle gate."""
        n = self.oracle.n
        m = self.oracle.m
        q_in = oracle_qubits[:n]
        q_tgt = oracle_qubits[n : n + m]
        
        # Precompute target bit flips for all 2^n inputs
        flip_masks = np.zeros(2**n, dtype=int)
        for x in range(2**n):
            fx = int(self.oracle.table[x])
            mask = 0
            for j in range(m):
                if (fx >> j) & 1:
                    mask |= (1 << q_tgt[j])
            flip_masks[x] = mask

        # Vectorized over all 2^circuit_qubits states
        all_k = np.arange(2**circuit_qubits, dtype=int)
        # Extract x from input qubits
        x_vals = np.zeros(2**circuit_qubits, dtype=int)
        for i, q in enumerate(q_in):
            x_vals |= ((all_k >> q) & 1) << i

        perm = all_k ^ flip_masks[x_vals]
        return perm

    def _simulate_circuit(
        self,
        circuit: QuantumCircuit,
        misfire_flags: List[bool],
        oracle_perms: Dict[int, np.ndarray],
    ) -> Statevector:
        """Simulates circuit step-by-step applying gates and oracle permutations."""
        N = circuit.num_qubits
        sv = Statevector.from_int(0, 2**N)
        
        oracle_idx = 0
        for inst in circuit.data:
            op = inst.operation
            q_indices = [circuit.find_bit(q).index for q in inst.qubits]
            
            if op.name == "oracle":
                misfired = misfire_flags[oracle_idx]
                oracle_idx += 1
                if not misfired:
                    perm = oracle_perms[tuple(q_indices)]
                    sv = Statevector(sv.data[perm])
            elif op.name == "measure":
                # Measurements are evaluated at the end
                continue
            elif op.name in ("barrier", "id"):
                continue
            else:
                sv = sv.evolve(op, q_indices)
                
        return sv

    def run(self, circuit: QuantumCircuit, shots: int) -> Dict[str, int]:
        """Official harness run method: run(circuit, shots) -> dict[str, int]."""
        self.validate_circuit(circuit)
        
        N = circuit.num_qubits
        C = circuit.num_clbits
        
        # Identify measurements: maps classical bit index -> qubit index
        meas_map = {}
        for inst in circuit.data:
            if inst.operation.name == "measure":
                q_idx = circuit.find_bit(inst.qubits[0]).index
                c_idx = circuit.find_bit(inst.clbits[0]).index
                meas_map[c_idx] = q_idx

        # Count oracle gates and precompute permutations
        oracle_calls = []
        for inst in circuit.data:
            if inst.operation.name == "oracle":
                q_indices = tuple(circuit.find_bit(q).index for q in inst.qubits)
                oracle_calls.append(q_indices)

        num_oracles = len(oracle_calls)
        unique_perms = {
            q_ind: self._build_oracle_permutation(N, list(q_ind))
            for q_ind in set(oracle_calls)
        }

        # Optimized execution:
        # If all shots have 1 oracle gate, we only have 2 possible statevectors (no-misfire and misfire)
        counts: Dict[str, int] = {}

        if num_oracles == 1:
            q_ind = oracle_calls[0]
            # Statevector with no misfire
            sv_normal = self._simulate_circuit(circuit, [False], unique_perms)
            probs_normal = sv_normal.probabilities()
            
            # Statevector with misfire (if p_misfire > 0)
            if self.noise.p_misfire > 0:
                sv_misfire = self._simulate_circuit(circuit, [True], unique_perms)
                probs_misfire = sv_misfire.probabilities()
            else:
                probs_misfire = probs_normal

            for _ in range(shots):
                is_misfire = self.noise.sample_misfire(self.rng)
                probs = probs_misfire if is_misfire else probs_normal
                sampled_basis = self.rng.choice(2**N, p=probs)
                
                # Extract classical bits
                raw_bits = np.zeros(C, dtype=int)
                for c_idx, q_idx in meas_map.items():
                    raw_bits[c_idx] = (sampled_basis >> q_idx) & 1
                    
                # Apply readout bit-flips
                final_bits = self.noise.apply_readout_flips(raw_bits, self.rng)
                
                # Little-endian string: bit 0 is at string[-1]
                # string format: c_{C-1} c_{C-2} ... c_1 c_0
                bitstring = "".join(str(final_bits[c]) for c in reversed(range(C)))
                counts[bitstring] = counts.get(bitstring, 0) + 1
        else:
            # Multi-oracle circuit (e.g. Grover with k steps)
            # Cache statevectors by misfire pattern
            pattern_cache = {}
            for _ in range(shots):
                pattern = tuple(self.noise.sample_misfire(self.rng) for _ in range(num_oracles))
                if pattern not in pattern_cache:
                    sv = self._simulate_circuit(circuit, list(pattern), unique_perms)
                    pattern_cache[pattern] = sv.probabilities()
                
                probs = pattern_cache[pattern]
                sampled_basis = self.rng.choice(2**N, p=probs)
                
                raw_bits = np.zeros(C, dtype=int)
                for c_idx, q_idx in meas_map.items():
                    raw_bits[c_idx] = (sampled_basis >> q_idx) & 1
                    
                final_bits = self.noise.apply_readout_flips(raw_bits, self.rng)
                bitstring = "".join(str(final_bits[c]) for c in reversed(range(C)))
                counts[bitstring] = counts.get(bitstring, 0) + 1

        return counts
