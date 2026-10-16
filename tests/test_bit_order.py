"""TEST-011: Dedicated bit-order and endianness tests.

Ensures no endianness inversion between qubits and classical bits.
In Qiskit counts dictionary:
- string[-1] is classical bit 0
- string[-2] is classical bit 1
- string[-(i+1)] is classical bit i
"""

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Gate
from local.oracles import get_reference_oracle
from local.local_run import LocalRunner
from local.noise import NOISELESS


def test_single_qubit_positions():
    """Test measuring each individual qubit in an 8-qubit register."""
    oracle = get_reference_oracle("constant-0")
    runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=123)
    
    n, m = 8, 1
    for target_q in range(n):
        qc = QuantumCircuit(n + m, n)
        qc.x(target_q)
        qc.append(Gate("oracle", n + m, []), range(n + m))
        for i in range(n):
            qc.measure(i, i)
            
        counts = runner.run(qc, shots=5)
        expected_bitstring = "".join("1" if i == target_q else "0" for i in reversed(range(n)))
        assert counts == {expected_bitstring: 5}, (
            f"Failed for target qubit {target_q}: expected {expected_bitstring}, got {counts}"
        )
        # Verify rightmost character is bit 0
        assert expected_bitstring[-(target_q + 1)] == "1"


def test_multi_qubit_patterns():
    """Test measuring alternating bit patterns (0xAA and 0x55)."""
    oracle = get_reference_oracle("constant-0")
    runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=456)
    
    n, m = 8, 1
    patterns = [
        (0b10101010, "10101010"),  # 170
        (0b01010101, "01010101"),  # 85
        (0b11000011, "11000011"),  # 195
    ]
    
    for val, expected_str in patterns:
        qc = QuantumCircuit(n + m, n)
        for i in range(n):
            if (val >> i) & 1:
                qc.x(i)
        qc.append(Gate("oracle", n + m, []), range(n + m))
        for i in range(n):
            qc.measure(i, i)
            
        counts = runner.run(qc, shots=5)
        assert counts == {expected_str: 5}, f"Failed for val {val}: expected {expected_str}, got {counts}"
