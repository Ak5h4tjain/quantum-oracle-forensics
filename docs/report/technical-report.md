# Quantum Oracle Forensics: Technical Report

**Event:** IBM Qiskit Fall Fest 2026 · QC@IITI, IIT Indore · Industry Challenge by QryptoNox  
**Target File:** `solver.py` (Self-contained, compliant single file)  
**Dependencies:** `qiskit>=2.0,<3`, `numpy`, `scipy`, Python standard library only  

---

## 1. Executive Summary & Architecture

The **Quantum Oracle Forensics** solver classifies sealed, noisy quantum oracles on $n = 8$ input bits ($N = 256$) into one of eight mathematical function families:
- **$m = 1$:** `constant`, `balanced`, `linear`, `grover`, `randfun`
- **$m = 8$:** `simon`, `simon2`, `perm`

It operates under strict constraints: a hard query budget of **60 oracle queries** (query cost = oracle gates $\times$ shots), $\le 20$ qubits, CPU execution under 120 seconds, and noisy oracle evaluations (4% misfire rate, 2% bit-flip readout noise, doubled in the stress setting).

### Architectural Invariants
1. **Self-Contained Single File (`solver.py`):** Strictly contains all circuit construction, signal processing, and decision logic. Completely isolated with zero imports from external helper or development directories (`local/`).
2. **Ledger-First Enforcement (`QueryLedger`):** Every circuit evaluation passes through an internal query ledger that computes `cost = oracle_gates * shots` and enforces **charge-before-call**. The 60-query budget is never exceeded under any branch or exception path.
3. **Reserve Policy:** The solver dynamically preserves budget for mandatory secret extraction (e.g. reserving 2 queries for direct evaluation of $b = f(0)$ in linear functions) before allocating probe shots.

---

## 2. Methodology & Statistical Decision Logic

The solver splits fundamentally on the output register dimension $m$:

```
               [ Input Oracle: n=8, m, budget <= 60 ]
                                 |
                 +---------------+---------------+
                 |                               |
              [ m = 8 ]                       [ m = 1 ]
                 |                               |
        Simon-Style Sampling             Bernstein-Vazirani Probe
        (48 shots on n+m=16)             (16 shots on n+1=9)
                 |                               |
       Fast Walsh-Hadamard               Analyze Outcome Distribution:
       Transform Spectrum                - Dominant non-zero peak (>=45%) -> LINEAR [a, b]
                 |                       - High 0^8 frequency (>=50%)     -> CONSTANT / GROVER
     Order Statistics & Triads:          - Low 0^8 frequency (<10%)       -> BALANCED / RANDFUN
     - Peak gap s1 - s2 >= 10   -> SIMON (s)     |
     - XOR Triad: c1^c2 in top  -> SIMON2 (H)    +--> Direct Reads & Grover Search
     - Uniform spectrum         -> PERM
```

### A. $m = 8$ Branch: Fast Walsh-Hadamard Transform (DEC-04)
For $m = 8$, the solver applies a Hadamard transform to the input register, queries the sealed oracle once, reapplies Hadamards, and measures $n = 8$ qubits over 48 shots. The observed counts $C(y)$ are converted into a frequency vector and transformed via an $O(N \log N)$ **Fast Walsh-Hadamard Transform (FWHT)**:
$$\hat{C}(v) = \sum_{y=0}^{255} C(y) (-1)^{y \cdot v}$$

1. **Simon ($s$):** Every measurement satisfies $y \cdot s = 0 \pmod 2$. The FWHT produces a solitary massive peak $\hat{C}(s) \approx 38$ with a large gap ($s_1 - s_2 \ge 10$) over the noise floor ($\le 22$).
2. **Simon2 ($H = \{0, h_1, h_2, h_3\}$):** Samples satisfy $y \cdot h = 0$ for all $h \in H$. The FWHT yields three co-dominant signal peaks forming an **XOR triad** ($h_1 \oplus h_2 = h_3$). The solver verifies that $c_1 \oplus c_2$ is present among top candidates with elevated amplitude.
3. **Permutation (`perm`):** Samples are uniformly distributed over all 256 inputs. The FWHT produces no solitary peak and no XOR triad, with all scores remaining below $0.62 \times \text{shots}$.

### B. $m = 1$ Branch: Phase-Kickback Probe & Direct Reads
1. **Linear ($f(x) = a \cdot x \oplus b$):** In the BV circuit (target in $|-\rangle$), phase kickback maps $(-1)^{a \cdot x \oplus b}$ directly to basis state $|a\rangle$. A dominant non-zero peak ($\ge 45\%$ of shots) identifies $a$. A single direct query at $x = 0$ reveals $b = f(0)$.
2. **Constant vs Grover:** Both produce a high frequency of $0^8$ in BV ($p(0^8) \approx 85\%$). A direct query at $x = 0$ tests $f(0)$:
   - If $f(0) = 1$: A second read at $x = 1$ separates `constant-1` from `grover` ($t = 0$).
   - If $f(0) = 0$: The solver runs a 6-step Grover amplification circuit ($k=6, \text{shots}=3$) to amplify potential target $t$. A candidate is verified with a direct read; if $f(t) = 1$, `grover` is returned, otherwise safe fallback `constant-0`.
3. **Balanced vs Randfun:** In balanced oracles, $0^8$ amplitude is theoretically 0 and only occurs via misfire noise ($4\%$). In randfun, empirical amplitude fluctuates uniformly.

---

## 3. Empirical Results & Budget Efficiency

All metrics were benchmarked across 160 independent test trials under Base Noise N1 ($p_{misfire} = 0.04, p_{flip} = 0.02$) with hard budget cap 60:

| Family | Family Accuracy | Secret Recovery | Mean Queries Spent | Query Savings vs Budget 60 |
| :--- | :---: | :---: | :---: | :---: |
| **constant** | **100.0%** | **100.0%** | **26.5** | **55.8% Saved** |
| **linear** | **100.0%** | **100.0%** | **18.0** | **70.0% Saved** |
| **simon** | **100.0%** | **100.0%** | **48.0** | **20.0% Saved** |
| **simon2** | **95.0%** | **95.0%** | **48.0** | **20.0% Saved** |
| **perm** | **100.0%** | **100.0%** | **48.0** | **20.0% Saved** |
| **balanced** | **90.0%** | **90.0%** | **16.0** | **73.3% Saved** |
| **grover** | **20.0%** | **20.0%** | **31.0** | **48.3% Saved** |
| **randfun** | **10.0%** | **10.0%** | **16.0** | **73.3% Saved** |
| **Overall** | **76.9%** | **76.9%** | **31.4** | **47.7% Average Savings** |

### Baselines Comparison
* **BL-001 (Uniform Random):** Achieves $20.0\%$ on $m=1$ and $33.3\%$ on $m=8$. Our solver delivers **76.9% overall** ($\mathbf{+51.9\%}$ absolute margin).
* **BL-002 (Fixed Predictor):** Fails with $0\%$ accuracy on all non-default families.
* **BL-003 (Classical Direct Sampling):** Consumes 32 queries without finding Simon collisions (requires birthday bound $> 16$ queries) and has $0\%$ chance of locating Grover marked items ($1/256$).
* **BL-004 (Naive Textbook):** Lacks readout noise tolerance and triad verification, misclassifying Simon2 as Simon under noise.

---

## 4. Honest Failure Analysis & Quantum Trade-offs

1. **Grover Amplification under Tight Query Budgets:**  
   For $N = 256$, optimal Grover amplification requires $k \approx \frac{\pi}{4}\sqrt{256} = 12$ iterations. Under a 60-query budget, running 12 iterations allows at most 2 shots ($25$ queries), where a single 4% misfire disrupts the entire unitary chain. At $k = 6$, probability of success per shot is mathematically bounded at $\approx 44\%$. When amplification fails to mark $t$, the solver deliberately falls back to `constant-0` to protect against false positives.
2. **Balanced vs Randfun Discrimination:**  
   Separating a balanced function ($\sum f = 128$) from a random Boolean function ($E[\sum f] = 128, \text{Var} = 64$) without queries to all 256 inputs requires sequential likelihood testing that exceeds remaining query budgets. The solver prioritizes structured families with secrets (`linear`, `constant`, `simon`, `simon2`) before spending budget on secretless distributions.

---

## 5. Innovation & Extensions (Section 11)

To demonstrate foundational depth beyond textbook algorithms, two major extensions were engineered:

1. **Quantum Error Mitigation via Linear Inversion & Contrast Unbiasing:**
   * **Misfire Identity Bias Subtraction (`mitigate_misfire_bias`):** Under an oracle misfire rate $p_{misfire}$, observed ground-state probability $p_{0,\text{obs}} = (1 - p_{misfire}) p_{0,\text{true}} + p_{misfire}$. Our solver applies linear inversion $p_{0,\text{mitigated}} = \max(0, \frac{p_{0,\text{obs}} - p_{misfire}}{1 - p_{misfire}})$ before thresholding.
   * **Readout Contrast Scaling (`mitigate_readout_score`):** Under symmetric bit-flip noise $p_{flip}$, the Walsh correlation spectrum attenuates by $(1 - 2p_{flip})^n$ (for $n=8, p=0.02$, attenuation is $\approx 0.8508$). The solver unbiases the raw FWHT spectrum before gap comparison.

2. **Higher-Dimensional Subspace Recovery (Simon3 Extension):**
   * Extends Simon's algorithm from 1D ($s \ne 0$) and 2D ($s_1, s_2, s_1 \oplus s_2$) to a **3-Dimensional Hidden Subspace** $H \subset \mathbb{F}_2^8$ with $\dim(H) = 3$ ($|H| = 8$, containing 7 non-zero elements).
   * Verified in `tests/test_extensions.py`: Recovers all 7 non-zero vectors in the Fano-plane closure $\{v_1, v_2, v_3, v_1 \oplus v_2, v_1 \oplus v_3, v_2 \oplus v_3, v_1 \oplus v_2 \oplus v_3\}$ using 48 FWHT shots and linear independence checks under Base Noise N1.

