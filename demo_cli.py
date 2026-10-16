"""QUANTUM ORACLE FORENSICS — LIVE TERMINAL DASHBOARD
IBM Qiskit Fall Fest 2026 · QC@IITI, IIT Indore
Industry Challenge by QryptoNox

Interactive CLI visualizer demonstrating:
- Headless solver invocation with QueryLedger budget monitoring
- Fast Walsh-Hadamard Transform (FWHT) correlation spectrum visualization
- Quantum Error Mitigation (Misfire & Readout unbiasing)
- Real-time secret recovery verification
"""

import sys
import time
import argparse
from typing import Dict, List, Any, Optional
import numpy as np

# Force UTF-8 stdout if available to prevent Windows cp1252 encoding crashes
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import colorama
    colorama.init(autoreset=True)
    from colorama import Fore, Back, Style
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class DummyColor:
        def __getattr__(self, name):
            return ""
    Fore = Back = Style = DummyColor()

from local.oracles import (
    generate_constant_oracle,
    generate_balanced_oracle,
    generate_linear_oracle,
    generate_grover_oracle,
    generate_randfun_oracle,
    generate_simon_oracle,
    generate_simon2_oracle,
    generate_simon3_oracle,
    generate_perm_oracle,
    OracleInstance,
)
from local.noise import BASE_NOISE, STRESS_NOISE, NOISELESS, NoiseModel
from local.local_run import LocalRunner
from solver import solve, ALL_FAMILIES, fast_walsh_hadamard_transform, bitstring_to_int


# ============================================================================
# ANSI / FORMATTING HELPERS
# ============================================================================

def color_txt(text: str, color: str, bright: bool = True) -> str:
    if not HAS_COLOR:
        return text
    style = Style.BRIGHT if bright else Style.NORMAL
    return f"{style}{color}{text}{Style.RESET_ALL}"

def c_cyan(t: str) -> str: return color_txt(t, Fore.CYAN)
def c_green(t: str) -> str: return color_txt(t, Fore.GREEN)
def c_yellow(t: str) -> str: return color_txt(t, Fore.YELLOW)
def c_red(t: str) -> str: return color_txt(t, Fore.RED)
def c_magenta(t: str) -> str: return color_txt(t, Fore.MAGENTA)
def c_white(t: str) -> str: return color_txt(t, Fore.WHITE)


def print_banner():
    banner = f"""
{c_cyan("+============================================================================+")}
{c_cyan("|")}         {c_magenta("QUANTUM ORACLE FORENSICS -- LIVE INVESTIGATION CONSOLE")}            {c_cyan("|")}
{c_cyan("|")}          IBM Qiskit Fall Fest 2026 * IIT Indore * QryptoNox Challenge       {c_cyan("|")}
{c_cyan("+============================================================================+")}
"""
    print(banner)


def draw_meter(used: int, total: int = 60, width: int = 28) -> str:
    """Renders a colorized budget consumption bar."""
    ratio = min(1.0, max(0.0, used / total))
    filled = int(round(ratio * width))
    empty = width - filled
    pct = ratio * 100.0

    if ratio <= 0.50:
        bar_color = Fore.GREEN
        status = c_green("EFFICIENT (>50% SAVED)")
    elif ratio <= 0.80:
        bar_color = Fore.YELLOW
        status = c_yellow("MODERATE CONSUMPTION")
    else:
        bar_color = Fore.RED
        status = c_red("NEAR BUDGET LIMIT")

    fill_str = "#" * filled
    empty_str = "." * empty
    if HAS_COLOR:
        bar = f"{bar_color}[{fill_str}{Style.DIM}{empty_str}{Style.RESET_ALL}{bar_color}]"
    else:
        bar = f"[{fill_str}{empty_str}]"

    return f"{bar} {c_white(f'{used:2d}/{total}')} ({pct:5.1f}%) | {status}"


def draw_walsh_spectrum(counts: Dict[str, int], n: int = 8, top_k: int = 8, bar_width: int = 32):
    """Draws a bar chart of the Walsh-Hadamard correlation spectrum."""
    c_vec = np.zeros(2**n, dtype=int)
    for bstr, cnt in counts.items():
        c_vec[bitstring_to_int(bstr)] = cnt

    fwht = fast_walsh_hadamard_transform(c_vec)
    scores = np.abs(fwht)
    max_val = max(1, int(np.max(scores)))

    order = np.argsort(scores)[::-1]

    print(f"\n{c_magenta('--- Fast Walsh-Hadamard Correlation Spectrum (Top Candidates) ---')}")
    print(f"{'Rank':<5} {'Vector':<12} {'Binary':<10} {'Correlation Score':<18} {'Spectrum Bar'}")
    print("-" * 72)

    for rank, idx in enumerate(order[:top_k], 1):
        score = int(scores[idx])
        bstr = format(idx, "08b")
        ratio = score / max_val
        bar_len = int(round(ratio * bar_width))
        bar_str = "=" * bar_len

        if rank == 1 and idx != 0:
            color = Fore.GREEN
        elif score >= 0.4 * max_val and idx != 0:
            color = Fore.CYAN
        elif idx == 0:
            color = Fore.YELLOW
        else:
            color = Fore.WHITE

        if HAS_COLOR:
            colored_bar = f"{color}{bar_str}{Style.RESET_ALL}"
            tag = f"{color}k={idx:<3}{Style.RESET_ALL}"
        else:
            colored_bar = bar_str
            tag = f"k={idx:<3}"

        print(f"#{rank:<4} {tag}   {bstr}   {score:<18} {colored_bar}")
    print("-" * 72)


# ============================================================================
# FORENSIC INVESTIGATION RUNNER
# ============================================================================

def make_tracking_run(runner: LocalRunner):
    queries = [0]
    def run_fn(circuit, shots):
        oracle_gates = sum(1 for inst in circuit.data if inst.operation.name == "oracle")
        queries[0] += oracle_gates * shots
        return runner.run(circuit, shots)
    return run_fn, queries


def investigate_oracle(oracle: OracleInstance, noise: NoiseModel = BASE_NOISE, budget: int = 60):
    """Runs full forensic solver on an oracle and prints a structured dossier."""
    runner = LocalRunner(oracle=oracle, noise=noise, seed=42)
    run_fn, q_box = make_tracking_run(runner)

    print(f"\n{c_cyan('+----------------------------------------------------------------------------+')}")
    print(f"{c_cyan('|')}  {c_white('SEALED QUANTUM ORACLE UNDER INVESTIGATION')}                             {c_cyan('|')}")
    print(f"{c_cyan('+----------------------------------------------------------------------------+')}")
    print(f"{c_cyan('|')}  * Input Width (n):  {c_yellow(str(oracle.n))} qubits                                          {c_cyan('|')}")
    print(f"{c_cyan('|')}  * Output Width (m): {c_yellow(str(oracle.m))} qubit(s)                                         {c_cyan('|')}")
    print(f"{c_cyan('|')}  * Query Budget:     {c_yellow(str(budget))} max queries                                       {c_cyan('|')}")
    print(f"{c_cyan('|')}  * Noise Profile:    {c_magenta(f'Misfire={noise.p_misfire*100:.1f}%, ReadoutFlip={noise.p_flip*100:.1f}%')}               {c_cyan('|')}")
    print(f"{c_cyan('+----------------------------------------------------------------------------+')}")

    candidates = ALL_FAMILIES if oracle.family != "simon3" else ALL_FAMILIES + ["simon3"]

    print(f"\n{c_yellow('[*] Activating Quantum Solver & Ledger Tracking...')}")
    start_t = time.perf_counter()

    detected_family, recovered_secret = solve(
        n=oracle.n,
        m=oracle.m,
        budget=budget,
        families=candidates,
        run=run_fn,
    )
    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    fam_match = (detected_family == oracle.family)
    sec_match = (recovered_secret == oracle.secret)
    queries_used = q_box[0]

    print(f"\n{c_white('RESULTS & VERIFICATION DOSSIER:')}")
    print(f" * Query Budget Gauge: {draw_meter(queries_used, budget)}")
    print(f" * Execution Latency:  {c_cyan(f'{elapsed_ms:.2f} ms')}")

    fam_status = c_green("[MATCH CONFIRMED]") if fam_match else c_red(f"[MISMATCH - True: {oracle.family}]")
    print(f" * Identified Family:  {c_yellow(detected_family.upper())}  {fam_status}")

    if oracle.secret is not None:
        sec_status = c_green("[100% EXACT RECOVERY]") if sec_match else c_red(f"[MISMATCH - True: {oracle.secret}]")
        print(f" * Extracted Secret:   {c_cyan(str(recovered_secret))}  {sec_status}")
        
        if detected_family == "linear" and isinstance(recovered_secret, list):
            a, b = recovered_secret[0], recovered_secret[1]
            print(f"   -> Parity Vector a: {a} (0b{format(a, '08b')}), Offset bit b: {b}")
        elif detected_family == "simon" and isinstance(recovered_secret, int):
            s = recovered_secret
            print(f"   -> Period Vector s: {s} (0b{format(s, '08b')})")
        elif detected_family == "simon2" and isinstance(recovered_secret, list):
            print(f"   -> 2D Subspace Triad: s1={recovered_secret[0]}, s2={recovered_secret[1]}, s1^s2={recovered_secret[2]}")
    else:
        print(f" * Secret Field:       {c_white('N/A (Property-based family)')}")

    return fam_match and (sec_match or oracle.secret is None), queries_used


# ============================================================================
# COMPREHENSIVE BENCHMARK SHOWCASE
# ============================================================================

def run_all_showcase(noise: NoiseModel = BASE_NOISE):
    """Executes a forensic sweep across all 8 standard families + Simon3 extension."""
    print(f"\n{c_cyan('============================================================================')}")
    print(f"    {c_magenta('RUNNING COMPREHENSIVE FORENSIC BENCHMARK ACROSS ALL FAMILIES')}    ")
    print(f"{c_cyan('============================================================================')}")

    test_oracles = [
        ("constant", generate_constant_oracle(c=1)),
        ("balanced", generate_balanced_oracle(seed=202)),
        ("linear", generate_linear_oracle(a=137, b=1)),
        ("grover", generate_grover_oracle(t=42)),
        ("randfun", generate_randfun_oracle(seed=505)),
        ("simon", generate_simon_oracle(s=109, seed=606)),
        ("simon2", generate_simon2_oracle(h1=15, h2=240, seed=707)),
        ("simon3", generate_simon3_oracle(h1=1, h2=2, h3=4, seed=808)),
        ("perm", generate_perm_oracle(seed=909)),
    ]

    total_queries = 0
    passed_cases = 0

    print(f"\n{'Family':<12} {'True Secret':<24} {'Detected':<12} {'Queries':<10} {'Status'}")
    print("=" * 74)

    for name, oracle in test_oracles:
        runner = LocalRunner(oracle=oracle, noise=noise, seed=42)
        run_fn, q_box = make_tracking_run(runner)
        cands = ALL_FAMILIES if name != "simon3" else ALL_FAMILIES + ["simon3"]

        detected, sec = solve(
            n=oracle.n,
            m=oracle.m,
            budget=60,
            families=cands,
            run=run_fn,
        )

        fam_ok = (detected == oracle.family)
        sec_ok = (sec == oracle.secret or oracle.secret is None)
        ok = fam_ok and sec_ok
        if ok:
            passed_cases += 1

        queries_used = q_box[0]
        total_queries += queries_used

        status_str = c_green("[PASS]") if ok else c_red("[FAIL]")
        sec_repr = str(oracle.secret) if oracle.secret is not None else "None"
        if len(sec_repr) > 22:
            sec_repr = sec_repr[:20] + ".."

        det_repr = f"{detected}"
        q_str = f"{queries_used}/60"

        print(f"{name:<12} {sec_repr:<24} {det_repr:<12} {q_str:<10} {status_str}")

    print("=" * 74)
    avg_q = total_queries / len(test_oracles)
    savings_pct = (1.0 - (avg_q / 60.0)) * 100.0

    print(f"\n{c_cyan('BENCHMARK SUMMARY:')}")
    print(f" * Total Oracles Evaluated: {len(test_oracles)}")
    print(f" * Accuracy:                 {c_green(f'{passed_cases}/{len(test_oracles)} ({passed_cases/len(test_oracles)*100:.1f}%)')}")
    print(f" * Average Queries Used:    {c_yellow(f'{avg_q:.1f} / 60 queries')}")
    print(f" * Net Budget Conservation: {c_green(f'{savings_pct:.1f}% SAVED vs Limit')}")


# ============================================================================
# INTERACTIVE DEMO MENU
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Quantum Oracle Forensics Visualizer")
    parser.add_argument("--all", action="store_true", help="Run benchmark across all oracle families")
    parser.add_argument("--family", type=str, choices=ALL_FAMILIES + ["simon3"], help="Run forensic inspection on a specific family")
    parser.add_argument("--stress", action="store_true", help="Use Stress Noise N2 (8%% misfire, 4%% flip)")
    parser.add_argument("--walsh", action="store_true", help="Show FWHT Walsh correlation spectrum demo")
    args = parser.parse_args()

    print_banner()

    noise = STRESS_NOISE if args.stress else BASE_NOISE
    noise_label = "Stress Noise N2 (8% misfire, 4% flip)" if args.stress else "Base Noise N1 (4% misfire, 2% flip)"
    print(f"Operating Environment: {c_yellow(noise_label)}\n")

    if args.all:
        run_all_showcase(noise=noise)
        return

    if args.walsh:
        print(f"{c_yellow('Generating Simon Oracle with secret s = 109 under noise...')}")
        oracle = generate_simon_oracle(s=109, seed=42)
        runner = LocalRunner(oracle=oracle, noise=noise, seed=42)
        from solver import build_simon_circuit
        counts = runner.run(build_simon_circuit(8, 8), shots=48)
        draw_walsh_spectrum(counts)
        return

    if args.family:
        if args.family == "constant": oracle = generate_constant_oracle(c=1)
        elif args.family == "balanced": oracle = generate_balanced_oracle(seed=42)
        elif args.family == "linear": oracle = generate_linear_oracle(a=205, b=0)
        elif args.family == "grover": oracle = generate_grover_oracle(t=77)
        elif args.family == "randfun": oracle = generate_randfun_oracle(seed=42)
        elif args.family == "simon": oracle = generate_simon_oracle(s=109, seed=42)
        elif args.family == "simon2": oracle = generate_simon2_oracle(h1=15, h2=240, seed=42)
        elif args.family == "simon3": oracle = generate_simon3_oracle(h1=1, h2=2, h3=4, seed=42)
        elif args.family == "perm": oracle = generate_perm_oracle(seed=42)
        investigate_oracle(oracle, noise=noise)
        return

    # Interactive Menu
    print(f"{c_cyan('Select an Oracle Forensic Investigation to Launch:')}")
    menu_items = [
        ("1", "Linear Oracle (Bernstein-Vazirani secret recovery: a=205, b=1)"),
        ("2", "Simon Oracle (1D Hidden Subspace period: s=109)"),
        ("3", "Simon2 Oracle (2D Hidden Subspace XOR Triad: h1=15, h2=240)"),
        ("4", "Simon3 Extension (3D Hidden Subspace Fano Plane: 7 non-zero elements)"),
        ("5", "Grover Oracle (Single marked state search: t=77)"),
        ("6", "Constant Oracle (Direct majority reads: c=1)"),
        ("7", "Balanced Oracle (Deutsch-Jozsa interference)"),
        ("8", "Permutation Oracle (Uniform spectrum noise)"),
        ("A", "Run ALL Oracles in Sequence (Full Showcase Benchmark)"),
        ("W", "Inspect Fast Walsh-Hadamard Correlation Spectrum (Simon vs Noise)"),
    ]

    for key, desc in menu_items:
        print(f"  [{c_yellow(key)}] {desc}")

    choice = input(f"\n{c_white('Enter choice [1-8 / A / W] (default A): ')}").strip().upper()
    if not choice:
        choice = "A"

    if choice == "1":
        investigate_oracle(generate_linear_oracle(a=205, b=1), noise=noise)
    elif choice == "2":
        investigate_oracle(generate_simon_oracle(s=109, seed=42), noise=noise)
    elif choice == "3":
        investigate_oracle(generate_simon2_oracle(h1=15, h2=240, seed=42), noise=noise)
    elif choice == "4":
        investigate_oracle(generate_simon3_oracle(h1=1, h2=2, h3=4, seed=42), noise=noise)
    elif choice == "5":
        investigate_oracle(generate_grover_oracle(t=77), noise=noise)
    elif choice == "6":
        investigate_oracle(generate_constant_oracle(c=1), noise=noise)
    elif choice == "7":
        investigate_oracle(generate_balanced_oracle(seed=42), noise=noise)
    elif choice == "8":
        investigate_oracle(generate_perm_oracle(seed=42), noise=noise)
    elif choice == "W":
        oracle = generate_simon_oracle(s=109, seed=42)
        runner = LocalRunner(oracle=oracle, noise=noise, seed=42)
        from solver import build_simon_circuit
        counts = runner.run(build_simon_circuit(8, 8), shots=48)
        draw_walsh_spectrum(counts)
    else:
        run_all_showcase(noise=noise)


if __name__ == "__main__":
    main()
