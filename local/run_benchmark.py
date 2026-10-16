"""Benchmark and experiment runner for Quantum Oracle Forensics.

Runs reproducible experiments E-01 through E-11, outputs JSONL logs
and computes empirical distributions to test and verify hand-calc numbers.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

from local.noise import NoiseModel, NOISELESS, BASE_NOISE, STRESS_NOISE
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
from solver import (
    build_bv_circuit,
    build_simon_circuit,
    build_direct_read_circuit,
    build_grover_circuit,
    fast_walsh_hadamard_transform,
    bitstring_to_int,
    solve,
    QueryLedger,
)


def load_config():
    cfg_path = Path("configs/experiments.json")
    if cfg_path.is_file():
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def run_experiment_e01(noise_key: str = "N1", trials: int = 50, out_dir: str = "logs/E-01"):
    """E-01: BV Phase-kickback signatures for m=1 families.
    
    Checks hand-calc predictions:
    - linear: dominant peak at 'a' with prob ~ (1 - p_misfire)*(1 - p_flip)^n
    - constant: prob(0^n) ~ (1 - p_flip)^n
    - grover: prob(0^n) ~ (1 - 2/256)^2 * (1 - p_flip)^n
    - balanced: prob(0^n) ~ p_misfire + small readout noise
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    noise_info = cfg.get("noise_configurations", {}).get(noise_key, {"p_misfire": 0.04, "p_flip": 0.02})
    noise = NoiseModel(p_misfire=noise_info["p_misfire"], p_flip=noise_info["p_flip"])
    
    results = []
    bv_shots = 50
    qc_bv = build_bv_circuit(n=8)
    
    families_to_test = ["constant", "grover", "linear", "balanced", "randfun"]
    summary_stats = {fam: {"p_zero": [], "p_peak": []} for fam in families_to_test}

    print(f"Running E-01 on {families_to_test} ({trials} trials each, noise={noise_key})...")

    for fam in families_to_test:
        for t in range(trials):
            seed = 1000 + t
            rng = np.random.default_rng(seed)
            if fam == "constant":
                oracle = generate_constant_oracle(c=t % 2)
            elif fam == "grover":
                oracle = generate_grover_oracle(t=rng.integers(0, 256))
            elif fam == "linear":
                oracle = generate_linear_oracle(a=rng.integers(1, 256), b=rng.integers(0, 2))
            elif fam == "balanced":
                oracle = generate_balanced_oracle(seed=seed)
            elif fam == "randfun":
                oracle = generate_randfun_oracle(seed=seed)

            runner = LocalRunner(oracle=oracle, noise=noise, seed=seed)
            counts = runner.run(qc_bv, shots=bv_shots)
            
            c_zero = counts.get("00000000", 0)
            p_zero = c_zero / bv_shots
            
            # Non-zero counts
            non_zero = {k: v for k, v in counts.items() if k != "00000000"}
            best_peak = max(non_zero.values()) if non_zero else 0
            p_peak = best_peak / bv_shots

            summary_stats[fam]["p_zero"].append(p_zero)
            summary_stats[fam]["p_peak"].append(p_peak)

            results.append({
                "family": fam,
                "trial": t,
                "p_zero": p_zero,
                "p_peak": p_peak,
                "counts_count": len(counts),
            })

    out_file = Path(out_dir) / f"e01_{noise_key}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"E-01 completed. Results written to {out_file}")
    print("-" * 55)
    print(f"{'Family':<12} | {'Mean p(0^8)':<15} | {'Mean p(peak)':<15}")
    print("-" * 55)
    for fam in families_to_test:
        m_zero = np.mean(summary_stats[fam]["p_zero"])
        m_peak = np.mean(summary_stats[fam]["p_peak"])
        print(f"{fam:<12} | {m_zero:<15.4f} | {m_peak:<15.4f}")
    print("-" * 55)


def run_experiment_e04(noise_key: str = "N1", trials: int = 50, out_dir: str = "logs/E-04"):
    """E-04: Linear secret recovery [a, b] vs BV shots."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    noise_info = cfg.get("noise_configurations", {}).get(noise_key, {"p_misfire": 0.04, "p_flip": 0.02})
    noise = NoiseModel(p_misfire=noise_info["p_misfire"], p_flip=noise_info["p_flip"])
    
    shot_options = [4, 8, 12, 16]
    accuracy_by_shots = {s: [] for s in shot_options}
    results = []

    print(f"Running E-04 on Linear recovery across shots {shot_options} (noise={noise_key})...")
    qc_bv = build_bv_circuit(n=8)

    for s in shot_options:
        correct = 0
        for t in range(trials):
            seed = 1000 + t
            rng = np.random.default_rng(seed)
            a_true = int(rng.integers(1, 256))
            b_true = int(rng.integers(0, 2))
            oracle = generate_linear_oracle(a=a_true, b=b_true)
            runner = LocalRunner(oracle=oracle, noise=noise, seed=seed)

            # Run BV
            counts = runner.run(qc_bv, shots=s)
            non_zero = {k: v for k, v in counts.items() if k != "00000000"}
            if non_zero:
                best_bstr = max(non_zero.items(), key=lambda it: it[1])[0]
                a_pred = bitstring_to_int(best_bstr)
            else:
                a_pred = 0

            # Read b at x=0 (1 shot)
            qc_read = build_direct_read_circuit(n=8, m=1, x=0)
            read_cnts = runner.run(qc_read, shots=1)
            b_pred = bitstring_to_int(list(read_cnts.keys())[0])

            is_correct = (a_pred == a_true and b_pred == b_true)
            if is_correct:
                correct += 1

            results.append({
                "shots": s, "trial": t, "a_true": a_true, "a_pred": a_pred,
                "b_true": b_true, "b_pred": b_pred, "correct": is_correct
            })
        acc = correct / trials
        accuracy_by_shots[s] = acc
        print(f"Shots = {s:2d} | Linear [a, b] Accuracy = {acc * 100:.1f}%")

    out_file = Path(out_dir) / f"e04_{noise_key}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")


def run_experiment_e05(noise_key: str = "N1", trials: int = 50, out_dir: str = "logs/E-05"):
    """E-05: Walsh classifier for m=8 (simon, simon2, perm)."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    noise_info = cfg.get("noise_configurations", {}).get(noise_key, {"p_misfire": 0.04, "p_flip": 0.02})
    noise = NoiseModel(p_misfire=noise_info["p_misfire"], p_flip=noise_info["p_flip"])
    
    shots = 36
    qc_simon = build_simon_circuit(n=8, m=8)
    families = ["simon", "simon2", "perm"]
    confusion = {true_fam: {pred_fam: 0 for pred_fam in families} for true_fam in families}
    secret_acc = {"simon": 0, "simon2": 0}
    results = []

    print(f"Running E-05: Simon/Simon2/Permutation classification ({trials} trials each, shots={shots}, noise={noise_key})...")

    for true_fam in families:
        for t in range(trials):
            seed = 1000 + t
            rng = np.random.default_rng(seed)
            if true_fam == "simon":
                s_true = int(rng.integers(1, 256))
                oracle = generate_simon_oracle(s=s_true, seed=seed)
                secret_expected = s_true
            elif true_fam == "simon2":
                h1 = int(rng.integers(1, 256))
                h2 = int(rng.integers(1, 256))
                while h2 == h1:
                    h2 = int(rng.integers(1, 256))
                h3 = h1 ^ h2
                secret_expected = sorted([h1, h2, h3])
                oracle = generate_simon2_oracle(h1=h1, h2=h2, seed=seed)
            elif true_fam == "perm":
                oracle = generate_perm_oracle(seed=seed)
                secret_expected = None

            runner = LocalRunner(oracle=oracle, noise=noise, seed=seed)
            counts = runner.run(qc_simon, shots=shots)

            c_vec = np.zeros(256, dtype=int)
            for bstr, cnt in counts.items():
                c_vec[bitstring_to_int(bstr)] = cnt

            scores = fast_walsh_hadamard_transform(c_vec)
            non_zero_scores = scores[1:]
            sorted_order = np.argsort(non_zero_scores)[::-1]
            sorted_candidates = sorted_order + 1
            sorted_scores = non_zero_scores[sorted_order]

            peak_threshold = max(8.0, 0.70 * shots)
            num_peaks = int(np.sum(sorted_scores >= peak_threshold))

            if num_peaks == 0:
                pred_fam = "perm"
                pred_secret = None
            elif num_peaks in (1, 2):
                pred_fam = "simon"
                pred_secret = int(sorted_candidates[0])
            else:
                pred_fam = "simon2"
                h1_p = int(sorted_candidates[0])
                h2_p = int(sorted_candidates[1])
                pred_secret = sorted([h1_p, h2_p, h1_p ^ h2_p])

            confusion[true_fam][pred_fam] += 1
            if true_fam == "simon" and pred_fam == "simon" and pred_secret == secret_expected:
                secret_acc["simon"] += 1
            elif true_fam == "simon2" and pred_fam == "simon2" and pred_secret == secret_expected:
                secret_acc["simon2"] += 1

            results.append({
                "true_family": true_fam,
                "pred_family": pred_fam,
                "true_secret": secret_expected,
                "pred_secret": pred_secret,
                "num_peaks": num_peaks,
                "top_score": float(sorted_scores[0]),
                "second_score": float(sorted_scores[1]),
            })

    out_file = Path(out_dir) / f"e05_{noise_key}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print("\nConfusion Matrix:")
    print(f"{'True \\ Pred':<12} | {'simon':<8} | {'simon2':<8} | {'perm':<8}")
    print("-" * 45)
    for tf in families:
        print(f"{tf:<12} | {confusion[tf]['simon']:<8} | {confusion[tf]['simon2']:<8} | {confusion[tf]['perm']:<8}")
    print("-" * 45)
    print(f"Simon secret recovery:  {secret_acc['simon']}/{trials} ({secret_acc['simon']/trials*100:.1f}%)")
    print(f"Simon2 secret recovery: {secret_acc['simon2']}/{trials} ({secret_acc['simon2']/trials*100:.1f}%)")


def run_experiment_e02(noise_key: str = "N1", trials: int = 30, out_dir: str = "logs/E-02"):
    """E-02: Grover k-step amplification sweep for constant vs grover."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    noise_info = cfg.get("noise_configurations", {}).get(noise_key, {"p_misfire": 0.04, "p_flip": 0.02})
    noise = NoiseModel(p_misfire=noise_info["p_misfire"], p_flip=noise_info["p_flip"])
    
    k_steps_list = [3, 4, 5, 6, 7]
    results = []

    print(f"Running E-02: Grover amplification sweep over k={k_steps_list} ({trials} trials each, noise={noise_key})...")

    for k in k_steps_list:
        successes = 0
        qc_grover = build_grover_circuit(n=8, k_steps=k)
        for t in range(trials):
            seed = 1000 + t
            rng = np.random.default_rng(seed)
            t_marked = int(rng.integers(0, 256))
            oracle = generate_grover_oracle(t=t_marked)
            runner = LocalRunner(oracle=oracle, noise=noise, seed=seed)

            # Sample 2 shots
            counts = runner.run(qc_grover, shots=2)
            best_cand = bitstring_to_int(max(counts.items(), key=lambda it: it[1])[0])

            # Verify candidate with 1 direct read
            qc_read = build_direct_read_circuit(n=8, m=1, x=best_cand)
            read_cnts = runner.run(qc_read, shots=1)
            ft = bitstring_to_int(list(read_cnts.keys())[0])

            if ft == 1 and best_cand == t_marked:
                successes += 1

            results.append({
                "k": k, "trial": t, "t_marked": t_marked, "best_cand": best_cand, "ft": ft,
                "success": (ft == 1 and best_cand == t_marked)
            })

        acc = successes / trials
        print(f"Grover steps k = {k:2d} (queries = {k*2+1:2d}) | Marked item recovery = {acc * 100:.1f}%")

    out_file = Path(out_dir) / f"e02_{noise_key}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")


def run_experiment_e11(noise_key: str = "N1", budget: int = 60, trials: int = 20, out_dir: str = "logs/final"):
    """E-11: Full benchmark across all 8 families on test split."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    noise_info = cfg.get("noise_configurations", {}).get(noise_key, {"p_misfire": 0.04, "p_flip": 0.02})
    noise = NoiseModel(p_misfire=noise_info["p_misfire"], p_flip=noise_info["p_flip"])

    all_8_families = [
        "constant", "balanced", "linear", "grover", "randfun",
        "simon", "simon2", "perm"
    ]
    results = []
    summary = {fam: {"correct_fam": 0, "correct_sec": 0, "queries": []} for fam in all_8_families}

    print(f"\n=======================================================")
    print(f"RUNNING E-11: FULL BENCHMARK (noise={noise_key}, budget={budget}, trials={trials}/family)")
    print(f"=======================================================")

    for fam in all_8_families:
        m = 8 if fam in ["simon", "simon2", "perm"] else 1
        valid_fams = [f for f in all_8_families if (8 if f in ["simon", "simon2", "perm"] else 1) == m]

        for t in range(trials):
            seed = 3000 + t
            rng = np.random.default_rng(seed)

            if fam == "constant":
                c = t % 2
                oracle = generate_constant_oracle(c=c)
                expected_sec = c
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
                h3 = h1 ^ h2
                oracle = generate_simon2_oracle(h1=h1, h2=h2, seed=seed)
                expected_sec = sorted([h1, h2, h3])
            elif fam == "perm":
                oracle = generate_perm_oracle(seed=seed)
                expected_sec = None

            runner = LocalRunner(oracle=oracle, noise=noise, seed=seed)
            queries_used = 0

            def counting_run(circuit, shots):
                nonlocal queries_used
                cost = sum(1 for inst in circuit.data if inst.operation.name == "oracle") * shots
                queries_used += cost
                return runner.run(circuit, shots)

            pred_fam, pred_sec = solve(
                n=8, m=m, budget=budget, families=valid_fams, run=counting_run
            )

            is_fam_correct = (pred_fam == fam)
            is_sec_correct = (pred_sec == expected_sec)

            if is_fam_correct:
                summary[fam]["correct_fam"] += 1
            if is_fam_correct and is_sec_correct:
                summary[fam]["correct_sec"] += 1
            summary[fam]["queries"].append(queries_used)

            results.append({
                "true_family": fam,
                "pred_family": pred_fam,
                "expected_secret": expected_sec,
                "pred_secret": pred_sec,
                "fam_correct": is_fam_correct,
                "sec_correct": is_sec_correct,
                "queries_used": queries_used,
            })

    out_file = Path(out_dir) / f"e11_{noise_key}_budget{budget}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Write summary CSV
    csv_file = Path(out_dir) / f"summary_{noise_key}_budget{budget}.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("family,trials,family_acc,secret_acc,avg_queries\n")
        print("\nSUMMARY TABLE:")
        print(f"{'Family':<12} | {'Family Acc':<12} | {'Secret Acc':<12} | {'Avg Queries':<12}")
        print("-" * 55)
        total_f_acc = 0
        total_s_acc = 0
        total_q = 0
        for fam in all_8_families:
            f_acc = summary[fam]["correct_fam"] / trials
            s_acc = summary[fam]["correct_sec"] / trials
            avg_q = float(np.mean(summary[fam]["queries"]))
            total_f_acc += f_acc
            total_s_acc += s_acc
            total_q += avg_q
            f.write(f"{fam},{trials},{f_acc:.4f},{s_acc:.4f},{avg_q:.2f}\n")
            print(f"{fam:<12} | {f_acc*100:<11.1f}% | {s_acc*100:<11.1f}% | {avg_q:<12.1f}")
        print("-" * 55)
        print(f"{'OVERALL':<12} | {total_f_acc/8*100:<11.1f}% | {total_s_acc/8*100:<11.1f}% | {total_q/8:<12.1f}")
    print(f"Results saved to {out_file} and {csv_file}\n")


def main():
    parser = argparse.ArgumentParser(description="Run Quantum Oracle Forensics experiments.")
    parser.add_argument("--experiment", type=str, required=True, choices=["E-01", "E-02", "E-04", "E-05", "E-11", "all"])
    parser.add_argument("--noise", type=str, default="N1", choices=["N0", "N1", "N2"])
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--budget", type=int, default=60)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    if args.experiment == "E-01" or args.experiment == "all":
        run_experiment_e01(noise_key=args.noise, trials=args.trials, out_dir=args.out or "logs/E-01")
    if args.experiment == "E-02" or args.experiment == "all":
        run_experiment_e02(noise_key=args.noise, trials=args.trials, out_dir=args.out or "logs/E-02")
    if args.experiment == "E-04" or args.experiment == "all":
        run_experiment_e04(noise_key=args.noise, trials=args.trials, out_dir=args.out or "logs/E-04")
    if args.experiment == "E-05" or args.experiment == "all":
        run_experiment_e05(noise_key=args.noise, trials=args.trials, out_dir=args.out or "logs/E-05")
    if args.experiment == "E-11" or args.experiment == "all":
        run_experiment_e11(noise_key=args.noise, budget=args.budget, trials=args.trials, out_dir=args.out or "logs/final")


if __name__ == "__main__":
    main()
