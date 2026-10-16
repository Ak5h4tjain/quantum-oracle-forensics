"""TEST-001 and TEST-012: Harness contract verification.

Verifies:
- TEST-001: LocalRunner provides run(circuit, shots) returning dict[str, int].
- TEST-012: Circuit restrictions (placeholder Gate("oracle", n+m, []), <= 20 qubits, measurements).
- Counts consistency: sum(counts.values()) == shots.
- Bitstring length equals classical register size.
- Little-endian convention: classical bit 0 is at string[-1].
"""

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Gate
from local.oracles import get_reference_oracle
from local.local_run import LocalRunner
from local.noise import NOISELESS


def test_contract_basic_execution():
    """Verify run(circuit, shots) accepts circuit and returns valid counts."""
    oracle = get_reference_oracle("constant-0")
    runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
    
    n, m = 8, 1
    qc = QuantumCircuit(n + m, n)
    qc.append(Gate("oracle", n + m, []), range(n + m))
    for i in range(n):
        qc.measure(i, i)
        
    counts = runner.run(qc, shots=50)
    assert isinstance(counts, dict), f"Expected dict, got {type(counts)}"
    assert sum(counts.values()) == 50, f"Expected 50 total shots, got {sum(counts.values())}"
    for k, v in counts.items():
        assert isinstance(k, str)
        assert len(k) == n, f"Expected key length {n}, got {len(k)}: {k}"
        assert set(k).issubset({"0", "1"})
        assert isinstance(v, int) and v > 0


def test_contract_bit_order():
    """Verify bit order in returned counts conforms to Qiskit little-endian."""
    oracle = get_reference_oracle("constant-0")
    runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
    
    # Put qubit 0 to |1>, qubit 1 to |0>, qubit 2 to |1>
    qc = QuantumCircuit(9, 3)
    qc.x(0)
    qc.x(2)
    qc.append(Gate("oracle", 9, []), range(9))
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    
    counts = runner.run(qc, shots=10)
    # Expected: c2 c1 c0 = '101'
    assert counts == {"101": 10}, f"Expected {{'101': 10}}, got {counts}"


def test_contract_circuit_validation():
    """Verify runner rejects circuits exceeding 20 qubits or missing oracle."""
    oracle = get_reference_oracle("constant-0")
    runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
    
    # 21 qubits circuit should be rejected
    qc_too_many = QuantumCircuit(21, 1)
    qc_too_many.append(Gate("oracle", 9, []), range(9))
    qc_too_many.measure(0, 0)
    with pytest.raises(ValueError, match="<= 20 qubits"):
        runner.run(qc_too_many, shots=10)
        
    # Circuit without oracle gate should be rejected
    qc_no_oracle = QuantumCircuit(9, 1)
    qc_no_oracle.measure(0, 0)
    with pytest.raises(ValueError, match="oracle"):
        runner.run(qc_no_oracle, shots=10)
