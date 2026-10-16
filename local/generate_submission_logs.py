"""Generate all required logs for hackathon submission:
1. logs/final/confusion_matrix.csv (8x8 Confusion Matrix)
2. logs/final/accuracy_vs_budget.csv (Accuracy at 15, 30, 45, 60 query limits)
3. logs/baselines/baseline_comparison.csv (BL-001, BL-002, BL-003, BL-004 vs Our Solver)
"""

import json
import os
from pathlib import Path
import numpy as np

from local.noise import BASE_NOISE
from local.oracles import (
    generate_constant_oracle,
    generate_balanced_oracle,
    generate_linear_oracle,
    generate_grover_oracle,
    generate_randfun_oracle,
    generate_simon_oracle,
    generate_simon2_oracle,
    generate_perm_oracle,
)
from local.local_run import LocalRunner
from local.baselines import (
    baseline_bl001_random,
    baseline_bl002_fixed,
    baseline_bl003_classical_sampling,
    baseline_bl004_textbook,
)
from solver import solve, ALL_FAMILIES


FAMILIES = ["constant", "balanced", "linear", "grover", "randfun", "simon", "simon2", "perm"]


def generate_confusion_matrix():
    print("Generating Confusion Matrix from final experiment logs...")
    jsonl_path = Path("logs/final/e11_N1_budget60.jsonl")
    if not jsonl_path.is_file():
        print(f"Error: {jsonl_path} not found")
        return

    matrix = {tf: {pf: 0 for pf in FAMILIES} for tf in FAMILIES}
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            tf = item["true_family"]
            pf = item["pred_family"]
            if tf in matrix and pf in matrix[tf]:
                matrix[tf][pf] += 1

    out_csv = Path("logs/final/confusion_matrix.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8") as f:
        header = "true_family," + ",".join(FAMILIES) + ",total,accuracy_pct\n"
        f.write(header)
        for tf in FAMILIES:
            row_counts = [matrix[tf][pf] for pf in FAMILIES]
            row_total = sum(row_counts)
            acc = (matrix[tf][tf] / row_total * 100.0) if row_total > 0 else 0.0
            row_str = f"{tf}," + ",".join(str(c) for c in row_counts) + f",{row_total},{acc:.1f}\n"
            f.write(row_str)

    print(f"Saved: {out_csv}")


def generate_accuracy_vs_budget():
    print("Evaluating Accuracy vs Budget across [15, 30, 45, 60] queries...")
    budgets = [15, 30, 45, 60]
    trials_per_fam = 10
    results_by_budget = []

    for b in budgets:
        correct_fam = 0
        correct_sec = 0
        total_runs = 0
        total_queries_spent = 0

        for fam in FAMILIES:
            m = 8 if fam in ("simon", "simon2", "perm") else 1
            valid_fams = [f for f in ALL_FAMILIES if (f in ("simon", "simon2", "perm") if m == 8 else f not in ("simon", "simon2", "perm"))]

            for t in range(trials_per_fam):
                seed = 3000 + t * 7
                rng = np.random.default_rng(seed)
                if fam == "constant":
                    oracle = generate_constant_oracle(c=t % 2)
                    expected_sec = t % 2
                elif fam == "balanced":
                    oracle = generate_balanced_oracle(seed=seed)
                    expected_sec = None
                elif fam == "linear":
                    a = int(rng.integers(1, 256))
                    b = int(rng.integers(0, 2))
                    oracle = generate_linear_oracle(a=a, b=b)
                    expected_sec = [a, b]
                elif fam == "grover":
                    tar = int(rng.integers(0, 256))
                    oracle = generate_grover_oracle(t=tar)
                    expected_sec = tar
                elif fam == "randfun":
                    oracle = generate_randfun_oracle(seed=seed)
                    expected_sec = None
                elif fam == "simon":
                    s = int(rng.integers(1, 256))
                    oracle = generate_simon_oracle(s=s, seed=seed)
                    expected_sec = s
                elif fam == "simon2":
                    h1 = int(rng.integers(1, 256))
                    h2 = int(rng.integers(1, 256))
                    while h2 == h1:
                        h2 = int(rng.integers(1, 256))
                    oracle = generate_simon2_oracle(h1=h1, h2=h2, seed=seed)
                    expected_sec = sorted([h1, h2, h1 ^ h2])
                elif fam == "perm":
                    oracle = generate_perm_oracle(seed=seed)
                    expected_sec = None

                runner = LocalRunner(oracle=oracle, noise=BASE_NOISE, seed=seed)
                queries_used = 0

                def tracking_run(circuit, shots):
                    nonlocal queries_used
                    cost = sum(1 for inst in circuit.data if inst.operation.name == "oracle") * shots
                    queries_used += cost
                    return runner.run(circuit, shots)

                pred_fam, pred_sec = solve(
                    n=8, m=m, budget=b, families=valid_fams, run=tracking_run
                )

                if pred_fam == fam:
                    correct_fam += 1
                if pred_fam == fam and pred_sec == expected_sec:
                    correct_sec += 1

                total_runs += 1
                total_queries_spent += queries_used

        fam_acc = correct_fam / total_runs * 100.0
        sec_acc = correct_sec / total_runs * 100.0
        avg_q = total_queries_spent / total_runs
        results_by_budget.append({
            "budget": b,
            "trials": total_runs,
            "family_accuracy_pct": fam_acc,
            "secret_accuracy_pct": sec_acc,
            "avg_queries_used": avg_q,
            "budget_saved_pct": (1.0 - (avg_q / b)) * 100.0,
        })
        print(f"  Budget {b:2d} -> Family Acc: {fam_acc:5.1f}%, Secret Acc: {sec_acc:5.1f}%, Avg Queries: {avg_q:4.1f}")

    out_csv = Path("logs/final/accuracy_vs_budget.csv")
    with open(out_csv, "w", encoding="utf-8") as f:
        f.write("budget,trials,family_accuracy_pct,secret_accuracy_pct,avg_queries_used,budget_saved_pct\n")
        for r in results_by_budget:
            f.write(f"{r['budget']},{r['trials']},{r['family_accuracy_pct']:.2f},{r['secret_accuracy_pct']:.2f},{r['avg_queries_used']:.2f},{r['budget_saved_pct']:.2f}\n")
    print(f"Saved: {out_csv}")


def generate_baseline_comparison():
    print("Evaluating Baselines BL-001..BL-004 vs Solver...")
    trials_per_fam = 10
    baselines = {
        "BL-001 (Uniform Random)": baseline_bl001_random,
        "BL-002 (Fixed Majority)": baseline_bl002_fixed,
        "BL-003 (Classical Sampling)": baseline_bl003_classical_sampling,
        "BL-004 (Naive Textbook)": baseline_bl004_textbook,
        "Ours (Quantum Forensics)": solve,
    }

    comparison_data = []

    for bl_name, bl_fn in baselines.items():
        total_runs = 0
        correct_fam = 0
        correct_sec = 0
        total_q = 0

        for fam in FAMILIES:
            m = 8 if fam in ("simon", "simon2", "perm") else 1
            valid_fams = [f for f in ALL_FAMILIES if (f in ("simon", "simon2", "perm") if m == 8 else f not in ("simon", "simon2", "perm"))]

            for t in range(trials_per_fam):
                seed = 4000 + t * 11
                rng = np.random.default_rng(seed)
                if fam == "constant":
                    oracle = generate_constant_oracle(c=t % 2)
                    expected_sec = t % 2
                elif fam == "balanced":
                    oracle = generate_balanced_oracle(seed=seed)
                    expected_sec = None
                elif fam == "linear":
                    a = int(rng.integers(1, 256))
                    b = int(rng.integers(0, 2))
                    oracle = generate_linear_oracle(a=a, b=b)
                    expected_sec = [a, b]
                elif fam == "grover":
                    tar = int(rng.integers(0, 256))
                    oracle = generate_grover_oracle(t=tar)
                    expected_sec = tar
                elif fam == "randfun":
                    oracle = generate_randfun_oracle(seed=seed)
                    expected_sec = None
                elif fam == "simon":
                    s = int(rng.integers(1, 256))
                    oracle = generate_simon_oracle(s=s, seed=seed)
                    expected_sec = s
                elif fam == "simon2":
                    h1 = int(rng.integers(1, 256))
                    h2 = int(rng.integers(1, 256))
                    while h2 == h1:
                        h2 = int(rng.integers(1, 256))
                    oracle = generate_simon2_oracle(h1=h1, h2=h2, seed=seed)
                    expected_sec = sorted([h1, h2, h1 ^ h2])
                elif fam == "perm":
                    oracle = generate_perm_oracle(seed=seed)
                    expected_sec = None

                runner = LocalRunner(oracle=oracle, noise=BASE_NOISE, seed=seed)
                queries_used = 0

                def tracking_run(circuit, shots):
                    nonlocal queries_used
                    cost = sum(1 for inst in circuit.data if inst.operation.name == "oracle") * shots
                    queries_used += cost
                    return runner.run(circuit, shots)

                pred_fam, pred_sec = bl_fn(
                    n=8, m=m, budget=60, families=valid_fams, run=tracking_run
                )

                if pred_fam == fam:
                    correct_fam += 1
                if pred_fam == fam and pred_sec == expected_sec:
                    correct_sec += 1

                total_runs += 1
                total_q += queries_used

        f_acc = correct_fam / total_runs * 100.0
        s_acc = correct_sec / total_runs * 100.0
        avg_q = total_q / total_runs

        comparison_data.append({
            "model": bl_name,
            "family_accuracy_pct": f_acc,
            "secret_accuracy_pct": s_acc,
            "avg_queries": avg_q,
        })
        print(f"  {bl_name:<30} -> Fam Acc: {f_acc:5.1f}%, Sec Acc: {s_acc:5.1f}%, Avg Queries: {avg_q:4.1f}")

    out_csv = Path("logs/baselines/baseline_comparison.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8") as f:
        f.write("model,family_accuracy_pct,secret_accuracy_pct,avg_queries\n")
        for r in comparison_data:
            f.write(f"\"{r['model']}\",{r['family_accuracy_pct']:.2f},{r['secret_accuracy_pct']:.2f},{r['avg_queries']:.2f}\n")
    print(f"Saved: {out_csv}")


if __name__ == "__main__":
    generate_confusion_matrix()
    generate_accuracy_vs_budget()
    generate_baseline_comparison()
