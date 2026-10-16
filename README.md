# Quantum Oracle Forensics Solver

**IBM Qiskit Fall Fest 2026 · QC@IITI, IIT Indore · Industry Challenge by QryptoNox**  
**Submission File:** `solver.py` (Single-file, fully self-contained)  
**Dependencies:** `qiskit>=2.0,<3`, `numpy`, `scipy`, Python standard library  

---

## Overview

Given a sealed, noisy quantum oracle on $n = 8$ input bits ($N = 256$) with $m \in \{1, 8\}$ output bits and a strict budget of **60 noisy queries** (where query cost = oracle gates $\times$ shots), `solver.py` determines which of eight mathematical families the oracle belongs to and extracts its exact secret:

| Family | $m$ | Secret Description & Format |
| :--- | :---: | :--- |
| **constant** | 1 | $c \in \{0, 1\}$ |
| **balanced** | 1 | `None` |
| **linear** | 1 | `[a, b]` with $a \in \{1..255\}, b \in \{0, 1\}$ |
| **grover** | 1 | Marked item $t \in \{0..255\}$ |
| **randfun** | 1 | `None` |
| **simon** | 8 | Non-zero period $s \in \{1..255\}$ |
| **simon2** | 8 | Ascending list of 3 non-zero elements of 2D subspace $H = [h_1, h_2, h_3]$ |
| **perm** | 8 | `None` |

Noise profile: 4% oracle misfire (acts as identity), 2% readout bit-flip noise (doubled under stress setting).

---

## Repository Layout

```
.
├── solver.py                  # Official submission solver (single-file, self-contained)
├── requirements.txt           # Submission dependencies: qiskit>=2.0,<3, numpy, scipy
├── requirements-dev.txt       # Development dependencies: pytest, matplotlib, ruff
├── README.md                  # Project overview, usage, and validation guide
├── pytest.ini                 # Pytest configuration
├── docs/                      # Documentation package, specifications, and reports
│   └── report/
│       ├── technical-report.md # 3-page technical report
│       └── ai-use-disclosure.md # 1-page AI-use disclosure
├── local/                     # Local test harness and benchmark tools (never imported by solver.py)
│   ├── oracles.py             # Seeded generators for all 8 families + reference instances
│   ├── noise.py               # Misfire and bit-flip noise models
│   ├── local_run.py           # Vectorized permutation harness simulator
│   ├── baselines.py           # Baselines BL-001 through BL-004
│   ├── run_benchmark.py       # Reproducible experiment runner (E-01..E-11)
│   └── check_q1_q8.py         # Phase P1 Qiskit 2.x API & maths validation checks
├── tests/                     # Automated test suite (42 unit, contract & compliance tests)
├── configs/                   # Experiment parameters, noise presets, seed splits
└── logs/                      # Committed experiment results and benchmark summaries
```

---

## Setup & Quick Start

### 1. Environment Setup
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Verify API & Maths Checks (Q1–Q8)
```powershell
python local/check_q1_q8.py
```

### 3. Run the Automated Test Suite (46 Tests)
```powershell
pytest -v
```

### 4. Run the Full Benchmark Suite (E-11)
```powershell
python -m local.run_benchmark --experiment E-11 --noise N1 --trials 20 --budget 60
```

### 5. Launch the Interactive Terminal Visualizer (Demo Console)
```powershell
# Interactive menu: select any oracle family to investigate live
python demo_cli.py

# Comprehensive showcase benchmark across all families + query budget meter
python demo_cli.py --all

# Inspect Fast Walsh-Hadamard Transform (FWHT) correlation spectrum
python demo_cli.py --walsh

# Test a specific family under Stress Noise N2 (8% misfire, 4% flip)
python demo_cli.py --family simon2 --stress
```

---

## Architectural Guarantees & Verification

* **Zero Leakage / Pure Black-Box:** `solver.py` interacts with the oracle strictly through `run(circuit, shots)`. No inspect tricks, frame reading, or seed lookups.
* **Charge-Before-Call Query Ledger:** Every quantum query charges `oracle_gates * shots` against the remaining budget before dispatch. Budget cap 60 is strictly enforced across all branches.
* **Qiskit 2.x Compliant:** Modern `QuantumCircuit` constructors and `Gate("oracle", n+m, [])` placeholders. Zero legacy/deprecated syntax (`execute`, `Aer`).
* **Clean Directory Tested:** Verified to run and solve standalone in an isolated temporary directory with no helper packages present (TEST-021).
