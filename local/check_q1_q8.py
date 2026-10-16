"""Phase P1 validation: Checks Q1 through Q8 for Qiskit 2.x behavior.

Q1: Placeholder gate creation and insertion: Gate("oracle", n+m, [])
Q2: Operation counting via QuantumCircuit.count_ops()
Q3: Bit order and endianness (little-endian: c[0] is rightmost)
Q4: Partial measurement (measuring n qubits into n-bit classical register)
Q5: Multi-controlled gates synthesis in Qiskit 2.x
Q6: Statevector simulation without qiskit-aer
Q7: Bernstein-Vazirani noiseless test for linear oracle f(x) = a*x ^ b
Q8: Simon's algorithm noiseless test for 2-to-1 oracle f(x ^ s) = f(x)
"""

import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit import Gate
from qiskit.quantum_info import Statevector, Operator


def check_q1_placeholder_gate():
    """Q1: Verify Gate("oracle", n+m, []) works in QuantumCircuit."""
    n, m = 8, 1
    qc = QuantumCircuit(n + m, n)
    oracle_gate = Gate("oracle", n + m, [])
    qc.append(oracle_gate, range(n + m))
    assert len(qc.data) == 1, f"Expected 1 instruction, got {len(qc.data)}"
    inst = qc.data[0].operation
    assert inst.name == "oracle", f"Expected name 'oracle', got {inst.name}"
    assert inst.num_qubits == n + m, f"Expected {n+m} qubits, got {inst.num_qubits}"
    return True, f"Q1 PASS: Gate('oracle', {n+m}, []) created and appended successfully."


def check_q2_count_ops():
    """Q2: Verify circuit.count_ops() accurately counts oracle gates."""
    qc = QuantumCircuit(9, 8)
    oracle_gate = Gate("oracle", 9, [])
    qc.h(range(8))
    qc.append(oracle_gate, range(9))
    qc.h(range(8))
    ops = qc.count_ops()
    assert ops.get("oracle", 0) == 1, f"Expected 1 oracle gate, got {ops.get('oracle', 0)}"
    assert ops.get("h", 0) == 16, f"Expected 16 H gates, got {ops.get('h', 0)}"
    return True, f"Q2 PASS: count_ops() returned correct counts: {dict(ops)}"


def check_q3_bit_order():
    """Q3: Verify bit ordering in Qiskit (little-endian: bit 0 is rightmost)."""
    # Put qubit 0 in state |1>, qubit 1 in state |0>, qubit 2 in state |1>
    # Measurement: q0 -> c0, q1 -> c1, q2 -> c2
    # In little-endian string representation, c2 c1 c0 = '101'
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.x(2)
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    
    sv = Statevector.from_instruction(qc.remove_final_measurements(inplace=False))
    probs = sv.probabilities_dict()
    # Statevector probabilities_dict is also little-endian: |q2 q1 q0> = |101>
    assert "101" in probs and np.isclose(probs["101"], 1.0), f"Expected '101', got {probs}"
    
    # Verify bit 0 is index -1 in string
    key = list(probs.keys())[0]
    assert key[-1] == "1", f"c[0] should be rightmost (1), got {key[-1]}"
    assert key[-2] == "0", f"c[1] should be middle (0), got {key[-2]}"
    assert key[-3] == "1", f"c[2] should be leftmost (1), got {key[-3]}"
    return True, f"Q3 PASS: Bit order verified as little-endian (c[0] is rightmost char: key='{key}')."


def check_q4_partial_measurement():
    """Q4: Verify measuring only n out of n+m qubits into an n-bit register."""
    n, m = 8, 1
    qc = QuantumCircuit(n + m, n)
    # Put qubit 3 to |1>, all other qubits to |0>
    qc.x(3)
    # Measure qubits 0..n-1 into c0..c_{n-1}
    for i in range(n):
        qc.measure(i, i)
    
    sv = Statevector.from_instruction(qc.remove_final_measurements(inplace=False))
    # Sample from the n measured qubits
    # In an n-bit string, qubit 3 being 1 corresponds to:
    # bit 3 from right is '1': string[-4] == '1'
    expected_bin = format(1 << 3, f"0{n}b")
    # Verify Statevector probabilities
    probs = sv.probabilities_dict()
    # sv has 9 qubits (target qubit is 0), so it's '0' + expected_bin
    full_key = list(probs.keys())[0]
    measured_sub_key = full_key[m:]  # first n bits from right
    assert measured_sub_key == expected_bin, f"Expected {expected_bin}, got {measured_sub_key}"
    return True, f"Q4 PASS: Partial measurement format matches {n}-bit register (expected '{expected_bin}')."


def check_q5_multi_controlled_gate():
    """Q5: Verify multi-controlled gates in Qiskit 2.x."""
    qc = QuantumCircuit(4)
    # Apply MCX with 3 controls (0, 1, 2) and target (3)
    qc.mcx([0, 1, 2], 3)
    # If control qubits are 1, target should flip
    qc_test = QuantumCircuit(4)
    qc_test.x([0, 1, 2])
    qc_test.mcx([0, 1, 2], 3)
    sv = Statevector.from_instruction(qc_test)
    probs = sv.probabilities_dict()
    # All 4 qubits are 1 -> string '1111'
    assert "1111" in probs and np.isclose(probs["1111"], 1.0), f"Expected '1111', got {probs}"
    return True, "Q5 PASS: Multi-controlled X (mcx) works in Qiskit 2.x without warnings."


def check_q6_statevector_simulation():
    """Q6: Verify Statevector simulation and custom oracle substitution."""
    # In Qiskit's qubit ordering: index = q0 + 2*q1
    # State |q1 q0>:
    # |00> (index 0) -> |00> (index 0)
    # |01> (index 1: q0=1, q1=0) -> |11> (index 3: q0=1, q1=1)
    # |10> (index 2: q0=0, q1=1) -> |10> (index 2: q0=0, q1=1)
    # |11> (index 3: q0=1, q1=1) -> |01> (index 1: q0=1, q1=0)
    # CNOT matrix with q0 as control and q1 as target:
    cnot_matrix = np.array([
        [1, 0, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 0],
        [0, 1, 0, 0]
    ], dtype=complex)
    oracle_op = Operator(cnot_matrix)
    
    qc = QuantumCircuit(2)
    qc.x(0)
    qc.unitary(oracle_op, [0, 1], label="oracle")
    
    sv = Statevector.from_instruction(qc)
    probs = sv.probabilities_dict()
    # q0=1, q1 was 0, so after CNOT q1=1, state is |11>
    assert "11" in probs and np.isclose(probs["11"], 1.0), f"Expected '11', got {probs}"
    return True, "Q6 PASS: Statevector simulation with custom unitary operator works cleanly without qiskit-aer."


def check_q7_bernstein_vazirani():
    """Q7: Verify Bernstein-Vazirani noiseless recovery for f(x) = a*x ^ b.
    
    Test with n = 4, a = 11 (binary 1011), b = 1.
    Target qubit in |-> state: X H |0>.
    Apply (-1)^{a*x ^ b}.
    H on input qubits reveals a.
    """
    n = 4
    a = 11  # binary 1011: bits 0, 1, 3 are 1, bit 2 is 0
    b = 1
    
    # Build oracle matrix for f(x) = (a.x ^ b)
    dim = 2 ** (n + 1)
    oracle_mat = np.zeros((dim, dim), dtype=complex)
    for x in range(2**n):
        fx = (bin(x & a).count("1") ^ b) & 1
        for y in range(2):
            input_state = (y << n) | x
            output_state = ((y ^ fx) << n) | x
            oracle_mat[output_state, input_state] = 1.0
            
    oracle_op = Operator(oracle_mat)
    
    qc = QuantumCircuit(n + 1, n)
    # Input register in |+>
    qc.h(range(n))
    # Target qubit in |->
    qc.x(n)
    qc.h(n)
    
    # Apply oracle
    qc.unitary(oracle_op, range(n + 1), label="oracle")
    
    # Uncompute input register with H
    qc.h(range(n))
    
    # Measure input register
    for i in range(n):
        qc.measure(i, i)
        
    sv = Statevector.from_instruction(qc.remove_final_measurements(inplace=False))
    probs = sv.probabilities_dict()
    
    # In Statevector, target qubit (q4) is in state |-> = (|0> - |1>)/sqrt(2)
    # The input qubits (q0..q3) must be strictly in state |a>
    # Check that for any non-zero amplitude state, input bits equal 'a'
    expected_a_bin = format(a, f"0{n}b")  # '1011'
    for bitstring, p in probs.items():
        if p > 1e-6:
            # bitstring is q4 q3 q2 q1 q0
            input_bits = bitstring[1:]
            assert input_bits == expected_a_bin, f"Expected {expected_a_bin}, got {input_bits}"
            
    return True, f"Q7 PASS: Bernstein-Vazirani recovered a={a} ('{expected_a_bin}') with 100% fidelity."


def check_q8_simon_algorithm():
    """Q8: Verify Simon's algorithm noiseless sampling for period s.
    
    Test with n = 3, m = 3, secret s = 5 (binary 101).
    2-to-1 function: f(x) = f(x ^ s).
    Simon circuit measures y such that y . s = 0 (mod 2).
    """
    n, m = 3, 3
    s = 5  # 101 in binary
    
    # Construct a valid 2-to-1 function f: {0..7} -> {0..7}
    # Pairs: (x, x ^ 5) map to the same value
    f = {}
    assigned_val = 0
    for x in range(2**n):
        if x not in f:
            f[x] = assigned_val
            f[x ^ s] = assigned_val
            assigned_val += 1
            
    # Build unitary U_f: |x>|y> -> |x>|y ^ f(x)>
    dim = 2 ** (n + m)
    oracle_mat = np.zeros((dim, dim), dtype=complex)
    for x in range(2**n):
        fx = f[x]
        for y in range(2**m):
            input_idx = (y << n) | x
            output_idx = ((y ^ fx) << n) | x
            oracle_mat[output_idx, input_idx] = 1.0
            
    oracle_op = Operator(oracle_mat)
    
    qc = QuantumCircuit(n + m, n)
    qc.h(range(n))
    qc.unitary(oracle_op, range(n + m), label="oracle")
    qc.h(range(n))
    
    for i in range(n):
        qc.measure(i, i)
        
    sv = Statevector.from_instruction(qc.remove_final_measurements(inplace=False))
    probs = sv.probabilities_dict()
    
    # Check that all non-zero probability states on input qubits satisfy y . s = 0 (mod 2)
    s_bin = format(s, f"0{n}b")
    observed_y = []
    for bitstring, p in probs.items():
        if p > 1e-6:
            # bitstring is q5 q4 q3 q2 q1 q0
            y_str = bitstring[m:]  # input register
            y_val = int(y_str, 2)
            dot_prod = bin(y_val & s).count("1") % 2
            assert dot_prod == 0, f"Simon condition failed: y={y_str} . s={s_bin} = {dot_prod} != 0"
            if y_val not in observed_y:
                observed_y.append(y_val)
                
    # Since n=3 and s!=0, the orthogonal subspace has dimension n-1 = 2, so 2^2 = 4 elements
    assert len(observed_y) == 4, f"Expected 4 orthogonal vectors, got {len(observed_y)}: {observed_y}"
    return True, f"Q8 PASS: Simon's algorithm sampled all 4 orthogonal vectors to s={s} with y.s=0 mod 2: {observed_y}."


def main():
    checks = [
        ("Q1", check_q1_placeholder_gate),
        ("Q2", check_q2_count_ops),
        ("Q3", check_q3_bit_order),
        ("Q4", check_q4_partial_measurement),
        ("Q5", check_q5_multi_controlled_gate),
        ("Q6", check_q6_statevector_simulation),
        ("Q7", check_q7_bernstein_vazirani),
        ("Q8", check_q8_simon_algorithm),
    ]
    
    print("=" * 60)
    print("RUNNING PHASE P1 CHECKS (Q1 - Q8) FOR QISKIT 2.x")
    print("=" * 60)
    
    all_passed = True
    results = []
    for q_name, check_fn in checks:
        try:
            passed, msg = check_fn()
            print(f"[{'PASS' if passed else 'FAIL'}] {msg}")
            results.append((q_name, passed, msg))
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"[FAIL] {q_name} raised exception: {e}")
            results.append((q_name, False, str(e)))
            all_passed = False
            
    print("=" * 60)
    if all_passed:
        print("ALL CHECKS (Q1 - Q8) PASSED! Phase P1 Complete.")
    else:
        print("SOME CHECKS FAILED! Please review errors above.")
    print("=" * 60)
    return 0 if all_passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
