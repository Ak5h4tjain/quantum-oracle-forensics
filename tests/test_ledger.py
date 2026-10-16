"""TEST-010: Query ledger verification.

Rules [EXPLICIT §6, ARC-02]:
- Every call to run(circuit, shots) MUST be mediated by the query ledger.
- Circuit query cost = (number of 'oracle' gates in circuit) * shots.
- Charge before call: ledger must verify (spent + cost <= budget) before invoking run().
- The query budget (60) is NEVER exceeded under any circumstances.
"""

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Gate
from local.oracles import get_reference_oracle
from local.local_run import LocalRunner
from local.noise import NOISELESS, BASE_NOISE


class MockJudgesHarness:
    """Mock harness simulating the judges' environment and tracking queries independently."""
    def __init__(self, runner: LocalRunner, budget: int = 60):
        self.runner = runner
        self.budget = budget
        self.queries_executed = 0
        self.call_history = []

    def run(self, circuit: QuantumCircuit, shots: int) -> dict:
        oracle_count = sum(1 for inst in circuit.data if inst.operation.name == "oracle")
        cost = oracle_count * shots
        if self.queries_executed + cost > self.budget:
            raise RuntimeError(
                f"BUDGET EXCEEDED: attempted to use {self.queries_executed + cost} queries, limit is {self.budget}!"
            )
        self.queries_executed += cost
        self.call_history.append((oracle_count, shots, cost))
        return self.runner.run(circuit, shots)


def test_ledger_charge_before_call_enforcement():
    """Verify that solver importable and never exceeds the budget on any family."""
    from solver import solve, ALL_FAMILIES
    
    # Test across all reference oracles
    ref_names = [
        "constant-0", "constant-1", "linear-1-0", "grover-0",
        "simon-1", "simon2-1-2", "perm-identity"
    ]
    
    for name in ref_names:
        oracle = get_reference_oracle(name)
        runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
        harness = MockJudgesHarness(runner=runner, budget=60)
        
        family_candidate_list = [f for f in ALL_FAMILIES if (oracle.m == 1 and f in ["constant", "balanced", "linear", "grover", "randfun"]) or (oracle.m == 8 and f in ["simon", "simon2", "perm"])]
        
        family, secret = solve(
            n=oracle.n,
            m=oracle.m,
            budget=60,
            families=family_candidate_list,
            run=harness.run
        )
        
        assert harness.queries_executed <= 60, (
            f"Oracle {name} spent {harness.queries_executed} queries, exceeding 60!"
        )
        assert isinstance(family, str)
        assert family in family_candidate_list


def test_ledger_small_budget_never_exceeded():
    """Verify that even with a reduced budget (e.g. 20 queries), solver respects it."""
    from solver import solve
    
    oracle = get_reference_oracle("constant-0")
    runner = LocalRunner(oracle=oracle, noise=NOISELESS, seed=42)
    harness = MockJudgesHarness(runner=runner, budget=20)
    
    family, secret = solve(
        n=8,
        m=1,
        budget=20,
        families=["constant", "balanced"],
        run=harness.run
    )
    
    assert harness.queries_executed <= 20
