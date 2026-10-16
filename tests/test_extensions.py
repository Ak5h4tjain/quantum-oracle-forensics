"""TEST-EXTENSION: Verification of Innovation and Extensions (Section 11).

Tests:
1. Error Mitigation: Misfire bias subtraction and readout contrast unbiasing.
2. Simon3 Extension: Recovery of a 3-Dimensional Hidden Subspace H (7 nonzero elements)
   via Fast Walsh-Hadamard Transform spectrum and Fano-plane XOR closure.
"""

import pytest
import numpy as np
from local.oracles import generate_simon3_oracle
from local.local_run import LocalRunner
from local.noise import BASE_NOISE, NOISELESS
from solver import (
    solve,
    mitigate_misfire_bias,
    mitigate_readout_score,
)


def test_misfire_error_mitigation():
    """Verify linear inversion unbiases the identity misfire floor."""
    p_misfire = 0.04
    # Suppose true p0 is 0.0 (e.g. balanced), but misfire observed is 0.04
    p_obs = 0.04
    p_mitigated = mitigate_misfire_bias(p_obs, p_misfire)
    assert np.isclose(p_mitigated, 0.0, atol=1e-5), f"Expected 0.0, got {p_mitigated}"

    # Suppose true p0 is 0.85 (constant), observed is 0.856
    p_obs_c = 0.856
    p_mit_c = mitigate_misfire_bias(p_obs_c, p_misfire)
    assert p_mit_c > 0.84


def test_readout_score_mitigation():
    """Verify readout contrast unbiasing scales attenuated peaks back toward shots."""
    shots = 48
    p_flip = 0.02
    n_bits = 8
    # Attenuation factor is (1 - 2*0.02)^8 = 0.96^8 approx 0.85
    attenuation = (1.0 - 2 * p_flip) ** n_bits
    attenuated_score = shots * attenuation  # approx 40.8
    mitigated = mitigate_readout_score(attenuated_score, p_flip=p_flip, n_bits=n_bits)
    assert np.isclose(mitigated, shots, atol=1e-3), f"Expected {shots}, got {mitigated}"


def test_simon3_3d_hidden_subspace_recovery():
    """Verify Simon3 (3-Dimensional Hidden Subspace H with 7 nonzero elements)."""
    # 3 linearly independent basis vectors
    h1 = 1   # 00000001
    h2 = 2   # 00000010
    h3 = 4   # 00000100
    # Expected H has 7 elements: 1, 2, 3, 4, 5, 6, 7
    expected_H = [1, 2, 3, 4, 5, 6, 7]
    
    oracle = generate_simon3_oracle(h1=h1, h2=h2, h3=h3, seed=42)
    assert oracle.family == "simon3"
    assert oracle.secret == expected_H
    
    runner = LocalRunner(oracle=oracle, noise=BASE_NOISE, seed=42)
    
    fam, sec = solve(
        n=8,
        m=8,
        budget=60,
        families=["simon", "simon2", "simon3", "perm"],
        run=runner.run,
    )
    
    assert fam == "simon3", f"Expected family 'simon3', got '{fam}'"
    assert sec == expected_H, f"Expected secret {expected_H}, got {sec}"
