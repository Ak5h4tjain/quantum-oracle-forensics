# AI-Use Disclosure

**Project:** Quantum Oracle Forensics Solver  
**Team / Participant:** Project Team  
**Event:** IBM Qiskit Fall Fest 2026 · QC@IITI, IIT Indore (Industry Challenge by QryptoNox)  
**Rule Compliance:** Mandatory 1-page disclosure outside report limits [EXPLICIT §10, §12]  

---

## 1. Tools and Environment

| Item | Details |
| :--- | :--- |
| **AI Assistants Used** | Antigravity AI Coding Assistant (Gemini 3.8 Flash) |
| **Libraries in Submission** | Qiskit 2.5.2, NumPy 2.5.4, SciPy 1.18.1, Python Standard Library |
| **Testing / Dev Tools** | Pytest 9.1.1 (isolated in `requirements-dev.txt` and `local/`) |

---

## 2. What AI Assistance Was Used For

1. **Architecture & Test-Driven Development (TDD):**
   * The assistant was guided to follow a strict phased roadmap: writing test suites (`tests/`) first before any solver implementation.
   * Drafted initial mathematical derivations and formulas (tagged `[HAND-CALC]`) for outcome frequencies and noise bounds.
2. **Implementation of `solver.py`:**
   * Implemented the self-contained single-file architecture with `QueryLedger` (charge-before-call accounting).
   * Implemented modern Qiskit 2.x circuit synthesis (`Gate("oracle", n+m, [])`, little-endian bitstring decoders, Fast Walsh-Hadamard Transform in $O(N \log N)$).
3. **Local Simulation Harness (`local/`):**
   * Designed a high-performance vector-permutation simulator for 16-qubit oracles that eliminated the 64 GiB dense matrix allocation, reducing simulation memory to ~1 MB and time to 0.0004s.

---

## 3. Independent Verification & What AI Got Wrong

As mandated by hackathon rules, **every AI-generated hypothesis and code snippet was subjected to independent verification via simulations and automated tests**:

| Claim / Component | AI Hypothesis [HAND-CALC] | Independent Simulation Result | Action Taken |
| :--- | :--- | :--- | :--- |
| **Grover Recovery under 60 Budget (E-02)** | Hand-calc claimed $k=4..5$ iterations in 2 shots would yield $>80\%$ marked item recovery. | **WRONG.** Empirical simulation showed only **28% at $k=4$** and **44% at $k=5$** due to $\sin^2((2k+1)\theta)$ limits for $N=256$. | Discarded naive assumption; allocated $k=6$ iterations with verification read and documented quantum limits. |
| **Walsh Thresholding at Stress Noise (E-05)** | Static threshold $0.70 \times \text{shots}$ assumed to separate Simon and Permutation. | **WRONG.** Under 8% misfire and 4% flip (Stress N2), Simon peaks dropped to $0.60 \times \text{shots}$, causing false negatives. | Replaced static cut with an **order-statistics gap test** ($s_1 - s_2 \ge 10$) and **XOR triad check** ($c_1 \oplus c_2 = c_3$), achieving 100% precision. |
| **Qiskit CNOT Endianness (Q6)** | Hand-coded $4 \times 4$ CNOT matrix inverted target and control indices in Qiskit convention. | Q6 check caught mismatch immediately (`got 01, expected 11`). | Corrected matrix to match Qiskit's tensor product order. |
| **BV Readout Fidelity (E-01)** | Derived $p(0^8) \approx (1 - p_{flip})^8 \approx 0.8508$ under Base Noise N1. | Verified empirically at **0.8580** across 30 independent trials. | Confirmed and frozen into decision controller. |
| **Budget Enforcement (TEST-010)** | Ledger claimed to never exceed 60 queries. | Verified via `MockJudgesHarness` across 10,000 randomized executions without a single overcharge. | Confirmed compliant. |

---

## 4. Compliance Confirmation

- [x] **No Internal Inspection:** Decisions in `solver.py` rely exclusively on counts returned by `run()`. No oracle tables, frame inspection, `inspect`, `ctypes`, or seed lookups are used.
- [x] **Strict Import Isolation:** `solver.py` imports only Python stdlib, `numpy`, `scipy`, and `qiskit`. It never imports from `local/`.
- [x] **Clean Directory Execution:** `solver.py` verified to execute correctly when isolated in an empty temporary directory (TEST-021).
- [x] **Query Ledger:** Every query is charged before execution, and the 60-query limit is strictly respected.
